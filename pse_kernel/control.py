# =============================================================================
# PSE-KALI — LIVE CONTROL CHANNEL (the human's hands on the SHARED_LIB)
# Thread-safe plumbing between the human (GUI) and the running swarm:
#   Mission        — a per-unit directive the human/commander sets, read live
#   Escalation     — a held action surfaced to the human to approve/deny
#   ControlChannel — command queue, escalation queue, log, pause/stop signals
# The kernel is untouched: missions only ever TIGHTEN within the config scope,
# and the authorization floor can never be approved away here (see engine).
# =============================================================================
import itertools
import queue
import threading


class Mission:
    """A live directive for one unit. `version` bumps on every change so an idle
    unit knows it has been re-tasked and should resume."""
    def __init__(self, unit, enabled=True, goal="", allowed_tools=None):
        self._lock = threading.Lock()
        self.unit = unit
        self.enabled = enabled
        self.goal = goal
        self.allowed_tools = allowed_tools     # None = all of the pack's tools
        self.version = 0

    def update(self, enabled=None, goal=None, allowed_tools=None):
        with self._lock:
            if enabled is not None:
                self.enabled = enabled
            if goal is not None:
                self.goal = goal
            if allowed_tools is not None:
                self.allowed_tools = allowed_tools
            self.version += 1

    def snapshot(self):
        with self._lock:
            return {"unit": self.unit, "enabled": self.enabled, "goal": self.goal,
                    "allowed_tools": self.allowed_tools, "version": self.version}


_esc_ids = itertools.count(1)


class Escalation:
    """A judgment hold handed to the human. Blocks the unit until resolved."""
    def __init__(self, unit, action, kind, reason):
        self.id = next(_esc_ids)
        self.unit = unit
        self.action = action
        self.kind = kind          # 'narcissistic' | 'borderline'
        self.reason = reason
        self._event = threading.Event()
        self.result = None        # 'approve' | 'deny'

    def resolve(self, decision):
        self.result = decision
        self._event.set()

    def wait(self, stop_event, poll=0.2):
        """Block until the human decides, or the engagement stops (-> deny)."""
        while not self._event.is_set():
            if stop_event.is_set():
                return "deny"
            self._event.wait(poll)
        return self.result


class ControlChannel:
    def __init__(self):
        self.commands = queue.Queue()      # human -> commander (text)
        self.escalations = queue.Queue()   # kernel -> human (Escalation)
        self.log = queue.Queue()           # system/commander -> GUI (text lines)
        self.paused = threading.Event()    # set = units idle (e.g. during a model swap)
        self.stop = threading.Event()      # set = tear down
        self.missions = {}                 # unit -> Mission

    def say(self, line):
        self.log.put(line)

    def command(self, text):
        self.commands.put(text)

    def escalate(self, unit, action, decision):
        e = Escalation(unit, action, decision.intervention.kind,
                       decision.intervention.reason)
        self.escalations.put(e)
        self.say(f"⚠ escalation #{e.id}: {unit} {action.get('tool')} "
                 f"{action.get('target')} — {e.kind}")
        return e
