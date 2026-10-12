# =============================================================================
# PSE-KALI — LIVE ENGINE (the running, human-steerable swarm)
# Ties the pieces together for live steering + model hot-swap:
#   - three mission-aware units run concurrently (orchestrator.Unit + control)
#   - a commander thread turns human commands into mission changes
#   - switch_model() hot-swaps the local GGUF behind the SwappableBackend
# The kernel is untouched; this is orchestration around it.
# =============================================================================
import os
import queue
import threading

from .orchestrator import Unit
from .operator import (ModelOperator, SwappableBackend, LocalGGUFBackend,
                       _LoadingBackend, make_backend)
from .commander import Commander
from .control import Mission, ControlChannel


def _free(backend):
    """Release a loaded llama-cpp model so its RAM comes back."""
    try:
        import gc
        if hasattr(backend, "_llm"):
            backend._llm = None
        del backend
        gc.collect()
    except Exception:   # noqa - freeing must never crash a swap
        pass


class LiveEngine:
    def __init__(self, context, packs, adapters, audit, proxy, commander,
                 control, goals, max_steps=1000):
        self.context = context
        self.packs = packs
        self.adapters = adapters
        self.audit = audit
        self.proxy = proxy            # SwappableBackend shared by commander + units
        self.commander = commander
        self.control = control
        for u in packs:               # a Mission per unit (created if absent)
            control.missions.setdefault(u, Mission(u, goal=goals.get(u, "")))
        self.units = [
            Unit(pack,
                 ModelOperator(proxy, pack, goals.get(u, ""), context.scope,
                               max_steps=max_steps, mission=control.missions[u]),
                 adapters[u], context, audit, control=control)
            for u, pack in packs.items()
        ]
        self._cmd_thread = None

    # ---- lifecycle ---------------------------------------------------------
    def start(self):
        for un in self.units:
            un.start()
        self._cmd_thread = threading.Thread(target=self._commander_loop, daemon=True)
        self._cmd_thread.start()
        self.control.say(f"engagement live — {len(self.units)} units running")

    def stop(self):
        self.control.stop.set()

    PRESETS = {
        "full":    {},   # empty => everything enabled
        "recon":   {"recon": True, "password": False, "sniff": False, "access": False},
        "passive": {"recon": True, "sniff": True, "password": False, "access": False},
        "stop":    {"recon": False, "password": False, "sniff": False, "access": False},
    }

    def apply_preset(self, name):
        """One-click mission preset (deterministic, no model needed)."""
        m = self.PRESETS.get(name)
        if m is None:
            return False
        for u in self.packs:
            self.control.missions[u].update(enabled=m.get(u, True))
        self.control.say(f"preset '{name}' applied")
        return True

    def authorize_scope(self, target, tools=None):
        """Human-only: widen the authorized scope for a new target and LOG it.
        The commander cannot do this — only the human, deliberately. This is how
        the authorization floor is lifted, and it is always in the audit."""
        tools = tools or sorted({t for p in self.packs.values() for t in p["tools"]})
        self.context.add_scope(target, tools)
        self.audit.append({"engagement": self.context.engagement_id,
                           "event": "scope_change", "added": target, "tools": tools})
        self.control.say(f"⚑ scope widened (logged): {target} authorized for "
                         f"{', '.join(tools)}")
        return True

    def _commander_loop(self):
        while not self.control.stop.is_set():
            try:
                cmd = self.control.commands.get(timeout=0.3)
            except queue.Empty:
                continue
            try:
                reply, changed = self.commander.plan(cmd, self.control.missions)
                tail = f"  [changed: {', '.join(changed)}]" if changed else ""
                self.control.say(f"commander: {reply}{tail}")
            except Exception as e:      # noqa
                self.control.say(f"commander error: {e}")

    # ---- model hot-swap ----------------------------------------------------
    def switch_model(self, path, opts=None, loader=None, fits=None):
        """Swap the local model live. `fits=False` frees the old model first
        (RAM-safe, brief pause); otherwise loads the new one then swaps (smooth).
        `loader` is injectable for tests. Returns True on success."""
        opts = opts or {}
        name = os.path.basename(path)
        loader = loader or (lambda: LocalGGUFBackend(path, **opts))
        self.control.paused.set()       # units idle while we swap
        try:
            self.control.say(f"loading {name} …")
            if fits is False:
                _free(self.proxy.swap(_LoadingBackend()))   # free old first
                self.proxy.swap(loader(), name=name)
            else:
                _free(self.proxy.swap(loader(), name=name))  # load, then free old
            self.audit.append({"engagement": self.context.engagement_id,
                               "event": "model_switch", "to": name})
            self.control.say(f"✓ model → {name}")
            return True
        except Exception as e:          # noqa
            self.control.say(f"✗ switch failed: {e} (keeping current model)")
            return False
        finally:
            self.control.paused.clear()


def assemble(packs, adapters, backend, scope, authz, goals, audit_path,
             engagement_id="ENG-LIVE"):
    """Wire a LiveEngine from parts. `backend` may be a plain backend (wrapped in
    a SwappableBackend here) or an already-built SwappableBackend. Returns
    (engine, context, control, proxy)."""
    from .context import EngagementContext
    from .audit import AuditLog
    ctx = EngagementContext(engagement_id, scope, authz)
    proxy = backend if isinstance(backend, SwappableBackend) else SwappableBackend(backend)
    control = ControlChannel()
    audit = AuditLog(audit_path)
    commander = Commander(proxy, packs)
    engine = LiveEngine(ctx, packs, adapters, audit, proxy, commander, control, goals)
    return engine, ctx, control, proxy
