# =============================================================================
# PSE-KALI — CONCURRENT ORCHESTRATOR (the minimal swarm)
# Runs N tool-units as concurrent workers over ONE shared EngagementContext and
# ONE audit log. Each worker loop:
#     operator.propose() -> action | WAIT | STOP
#     kernel.evaluate(action) -> Decision (scored, membrane-checked, logged)
#     if allowed: adapter(action) executes in lab -> findings -> shared store
# Units feed each other through the store WHILE all are still running.
#
# The operator is where the AI lives (a local GGUF proposes the next action).
# It is an interface so the demo can drive it with deterministic scripts and
# the harness can later drop in the model with no orchestrator change.
# =============================================================================
import threading

from .kernel import evaluate

WAIT = "__WAIT__"   # operator has no action yet (e.g. waiting on findings)
STOP = "__STOP__"   # operator is done


class Operator:
    """Proposes the next action for a unit. Return an action dict, WAIT, or STOP."""
    def propose(self, context):
        raise NotImplementedError


class ScriptedOperator(Operator):
    """Emits a fixed list of actions, then STOP. For the source unit (recon)."""
    def __init__(self, actions):
        self._actions = list(actions)
        self._i = 0

    def propose(self, context):
        if self._i >= len(self._actions):
            return STOP
        a = self._actions[self._i]
        self._i += 1
        return a


class ReactiveOperator(Operator):
    """Watches the shared store for findings of `consumes` kind and proposes an
    action per new finding. Finishes once `done_event` is set and the backlog is
    drained — i.e. once the upstream unit has stopped producing."""
    def __init__(self, consumes, make_action, done_event, poll=0.005):
        self.consumes = consumes
        self.make_action = make_action
        self.done_event = done_event
        self.poll = poll
        self._seen = set()

    def propose(self, context):
        for f in context.findings(kind=self.consumes):
            key = (f.get("artifact"), f.get("target"))
            if key not in self._seen:
                self._seen.add(key)
                return self.make_action(f)
        return STOP if self.done_event.is_set() else WAIT


class ChainOperator(Operator):
    """Runs a sequence of operators: advances to the next only when the current
    one is STOP. Lets a unit do scripted steps first, then react to findings."""
    def __init__(self, operators):
        self.ops = list(operators)
        self.i = 0

    def propose(self, context):
        while self.i < len(self.ops):
            r = self.ops[self.i].propose(context)
            if r is STOP:
                self.i += 1
                continue
            return r
        return STOP


class Unit(threading.Thread):
    def __init__(self, pack, operator, adapter, context, audit,
                 poll=0.005, on_finish=None, control=None):
        super().__init__(name=pack["unit"], daemon=True)
        self.pack = pack
        self.operator = operator
        self.adapter = adapter            # (action, context) -> [findings]
        self.context = context
        self.audit = audit
        self.poll = poll
        self.on_finish = on_finish        # called once the unit stops (e.g. set an Event)
        self.control = control            # live control channel (pause/escalation), or None
        self.trajectory = []              # per-unit, for Borderline
        self.decisions = []               # for the monitor / assertions

    def _execute(self, action):
        for finding in (self.adapter(action, self.context) or []) if self.adapter else []:
            self.context.add_finding(finding)

    def run(self):
        try:
            while True:
                if self.control:
                    if self.control.stop.is_set():
                        break
                    if self.control.paused.is_set():   # e.g. during a model swap
                        self._sleep()
                        continue
                action = self.operator.propose(self.context)
                if action is STOP:
                    break
                if action is WAIT:
                    self._sleep()
                    continue
                action.setdefault("unit", self.pack["unit"])
                dec = evaluate(action, self.context, self.trajectory,
                               self.pack, self.audit)
                self.decisions.append(dec)
                if hasattr(self.operator, "record"):
                    verdict = "allowed" if dec.allowed else dec.intervention.kind
                    self.operator.record(action, verdict)

                if dec.allowed:
                    if self.control:
                        self.control.say(f"{self.pack['unit']} ✓ {action.get('tool')} "
                                         f"{action.get('target')}")
                    self._execute(action)
                elif self.control:
                    self._handle_hold(action, dec)
        finally:
            if self.on_finish:
                self.on_finish()

    def _handle_hold(self, action, dec):
        """A held action under live control. The authorization floor is a hard
        wall — surfaced, never one-click approved. Judgment holds (over-reach,
        capitulation, borderline) go to the human to approve or deny."""
        kind = dec.intervention.kind
        if kind == "unauthorized":
            self.control.say(f"⛔ {self.pack['unit']} {action.get('tool')} "
                             f"{action.get('target')} DENIED — floor (needs a scope change)")
            return
        esc = self.control.escalate(self.pack["unit"], action, dec)
        if esc.wait(self.control.stop) == "approve":
            self.control.say(f"✓ #{esc.id} approved — executing despite {kind} hold")
            self.audit.append({"engagement": self.context.engagement_id,
                               "unit": self.pack["unit"], "tool": action.get("tool"),
                               "target": action.get("target"),
                               "event": "human_override", "hold": kind})
            self._execute(action)
        else:
            self.control.say(f"✗ #{esc.id} denied")

    def _sleep(self):
        # bounded wait without importing time at module top (kept simple)
        ev = threading.Event()
        ev.wait(self.poll)


class Swarm:
    """Starts all units concurrently and waits for them to finish."""
    def __init__(self, units):
        self.units = units

    def run(self):
        for u in self.units:
            u.start()
        for u in self.units:
            u.join()
        return self.units
