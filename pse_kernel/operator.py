# =============================================================================
# PSE-KALI — MODEL OPERATOR (the AI that drives the units)
# The operator proposes the next action for a unit; the KERNEL governs it. Three
# interchangeable backends behind one interface:
#   - ClaudeBackend      : Anthropic API (default model claude-opus-4-8)
#   - MistralBackend     : Mistral API
#   - LocalGGUFBackend   : llama-cpp-python, auto-sized to the machine
#   - MockBackend        : scripted JSON, for tests (no dependency)
#
# All heavy SDKs are imported lazily so the kernel runs (and tests pass) without
# them installed. Whatever the model proposes still passes score()+membrane():
# an out-of-scope suggestion is caught by the wall, not trusted because the model
# "wanted" it. That is the point of putting the model behind the kernel.
# =============================================================================
import json
import re
import threading

from .orchestrator import Operator, STOP, WAIT

# ---- the structured action the model must emit (JSON) ---------------------
ACTION_SCHEMA = {
    "type": "object",
    "additionalProperties": False,
    "properties": {
        "action":    {"type": "string", "enum": ["propose", "done"]},
        "tool":      {"type": "string"},
        "target":    {"type": "string"},
        "args":      {"type": "array", "items": {"type": "string"}},
        "rationale": {"type": "string"},
        "artifact":  {"type": ["string", "null"]},
    },
    "required": ["action", "tool", "target", "args", "rationale", "artifact"],
}

_SYSTEM = """You are a governed security operator driving the {unit} unit of an \
authorized penetration-testing engagement. You may use only these tools: {tools}.

Rules of engagement (HARD):
- Authorized scope (targets you may act on): {scope}
- Act ONLY within the authorized scope. Never propose an action against a target \
outside it.
- Prefer the least intrusive action that meets the objective; escalate intensity \
only when justified.
- If a needed artifact (e.g. a hash) has no in-scope provenance, do not act on it.

You do not decide what is allowed — a governance kernel scores every action and \
physically blocks anything outside the rules. Propose the single best next action.

Objective: {goal}

Respond with ONE JSON object only: {{"action":"propose"|"done", "tool":..., \
"target":..., "args":[...], "rationale":..., "artifact": <hash-or-null>}}. \
Use "done" when the objective is met.

Examples of the exact format (small models: copy this shape precisely):
{{"action":"propose","tool":"nmap","target":"10.10.10.5","args":["-sV","-T4"],"rationale":"enumerate services on an in-scope host","artifact":null}}
{{"action":"done","tool":"","target":"","args":[],"rationale":"objective met","artifact":null}}"""


# =============================================================================
# Backends — each returns the model's raw text (expected to be one JSON object)
# =============================================================================
class Backend:
    def complete(self, system, user):
        raise NotImplementedError


class ClaudeBackend(Backend):
    """Anthropic API. Structured outputs guarantee valid JSON back."""
    def __init__(self, model="claude-opus-4-8", max_tokens=1024, effort="medium"):
        import anthropic  # lazy
        self._client = anthropic.Anthropic()   # resolves key / ant profile
        self.model, self.max_tokens, self.effort = model, max_tokens, effort

    def complete(self, system, user):
        resp = self._client.messages.create(
            model=self.model,
            max_tokens=self.max_tokens,
            system=system,
            output_config={"effort": self.effort,
                           "format": {"type": "json_schema", "schema": ACTION_SCHEMA}},
            messages=[{"role": "user", "content": user}],
        )
        return next(b.text for b in resp.content if b.type == "text")


class MistralBackend(Backend):
    def __init__(self, model="mistral-large-latest", api_key=None):
        import os
        from mistralai import Mistral  # lazy
        self._client = Mistral(api_key=api_key or os.environ["MISTRAL_API_KEY"])
        self.model = model

    def complete(self, system, user):
        resp = self._client.chat.complete(
            model=self.model,
            messages=[{"role": "system", "content": system},
                      {"role": "user", "content": user}],
            response_format={"type": "json_object"},
        )
        return resp.choices[0].message.content


class LocalGGUFBackend(Backend):
    """llama-cpp-python. One lock: a single local model serves all units serially."""
    _lock = threading.Lock()

    def __init__(self, model_path, n_ctx=4096, n_gpu_layers=0, n_threads=None):
        from llama_cpp import Llama  # lazy
        kw = {"model_path": model_path, "n_ctx": n_ctx,
              "n_gpu_layers": n_gpu_layers, "verbose": False}
        if n_threads:
            kw["n_threads"] = n_threads   # 0/None -> llama-cpp auto-detects
        self._llm = Llama(**kw)

    def complete(self, system, user):
        with LocalGGUFBackend._lock:
            out = self._llm.create_chat_completion(
                messages=[{"role": "system", "content": system},
                          {"role": "user", "content": user}],
                response_format={"type": "json_object"},
                temperature=0.0, max_tokens=512)
        return out["choices"][0]["message"]["content"]


class MockBackend(Backend):
    """Scripted JSON strings, popped in order. For tests / offline demos."""
    def __init__(self, scripted):
        self._q = list(scripted)

    def complete(self, system, user):
        return self._q.pop(0) if self._q else json.dumps(
            {"action": "done", "tool": "", "target": "", "args": [],
             "rationale": "no more scripted actions", "artifact": None})


class SwappableBackend(Backend):
    """A proxy whose underlying backend can be replaced atomically at runtime —
    this is what lets the GUI hot-swap the local model mid-engagement. A swap
    waits for any in-flight call to finish (the lock is held during complete),
    so no unit ever sees a half-swapped model."""
    def __init__(self, backend, name="model"):
        self._b = backend
        self._lock = threading.Lock()
        self.name = name

    def complete(self, system, user):
        with self._lock:
            return self._b.complete(system, user)

    def swap(self, new_backend, name=None):
        with self._lock:
            old = self._b
            self._b = new_backend
            if name:
                self.name = name
        return old


class _LoadingBackend(Backend):
    """Placeholder installed while a new model loads after the old was freed."""
    def complete(self, system, user):
        raise RuntimeError("model is loading")


# =============================================================================
# Auto-size a local model to the machine (RAM probe)
# =============================================================================
def detect_ram_gb():
    try:
        with open("/proc/meminfo") as fh:
            for line in fh:
                if line.startswith("MemTotal:"):
                    return int(line.split()[1]) / (1024 * 1024)   # kB -> GB
    except OSError:
        pass
    return 4.0   # conservative fallback

def select_gguf(models):
    """models: [{'path':..., 'min_ram_gb':N}, ...] largest-first.
    Returns the largest model that fits available RAM with headroom."""
    ram = detect_ram_gb()
    for m in sorted(models, key=lambda m: m["min_ram_gb"], reverse=True):
        if ram >= m["min_ram_gb"]:
            return m["path"]
    return models[-1]["path"] if models else None


# =============================================================================
# Backend factory — "claude:claude-opus-4-8" | "mistral:mistral-large-latest"
#                   | "gguf:/path/model.gguf" | "mock"
# =============================================================================
def make_backend(spec, **kw):
    kind, _, arg = spec.partition(":")
    if kind == "claude":
        return ClaudeBackend(model=arg or "claude-opus-4-8", **kw)
    if kind == "mistral":
        return MistralBackend(model=arg or "mistral-large-latest", **kw)
    if kind == "gguf":
        return LocalGGUFBackend(model_path=arg, **kw)
    if kind == "mock":
        return MockBackend(kw.get("scripted", []))
    raise ValueError(f"unknown backend spec: {spec!r}")


# =============================================================================
# ModelOperator — plugs any backend into the orchestrator's Operator interface
# =============================================================================
def _parse_action(text):
    """Tolerant JSON extraction: strip code fences, grab the first object.
    Small local models are messy — this recovers the JSON from surrounding prose."""
    text = (text or "").strip()
    if text.startswith("```"):
        text = re.sub(r"^```[a-zA-Z]*\n?|\n?```$", "", text).strip()
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        m = re.search(r"\{.*\}", text, re.DOTALL)
        if not m:
            raise
        return json.loads(m.group(0))


def _validate(action, pack):
    """Reject malformed actions BEFORE the kernel sees them (a broken action
    isn't a governance decision, it's noise). Returns (ok, reason)."""
    if not isinstance(action, dict):
        return False, "reply was not a JSON object"
    kind = action.get("action")
    if kind == "done":
        return True, ""
    if kind != "propose":
        return False, "field 'action' must be 'propose' or 'done'"
    if action.get("tool") not in pack["tools"]:
        return False, (f"tool {action.get('tool')!r} is not one of this unit's "
                       f"tools {pack['tools']}")
    if not action.get("target"):
        return False, "field 'target' is required"
    if action.get("args") is not None and not isinstance(action["args"], list):
        return False, "field 'args' must be a list of strings"
    return True, ""


def selftest_backend(backend, pack, scope="10.0.0.0/24", goal="probe in-scope hosts"):
    """Confirm a backend actually emits one parseable, schema-valid action.
    Used by `run_engagement.py --selftest` before a real run."""
    from .context import EngagementContext
    op = ModelOperator(backend, pack, goal, [scope], max_steps=1)
    ctx = EngagementContext("SELFTEST", [scope], [])
    try:
        raw = backend.complete(op._system(), op._user(ctx))
    except Exception as e:                     # noqa
        return False, f"backend call failed: {e}"
    try:
        action = _parse_action(raw)
    except Exception as e:                     # noqa
        return False, f"unparseable JSON: {e}; got {raw[:160]!r}"
    ok, why = _validate(action, pack)
    return ok, (why or f"emits valid actions (sample tool={action.get('tool')!r})")


class ModelOperator(Operator):
    def __init__(self, backend, pack, goal, scope, max_steps=8, max_waits=400,
                 mission=None):
        self.backend = backend
        self.pack = pack
        self.goal = goal
        self.scope = scope
        self.max_steps = max_steps
        self.max_waits = max_waits   # bound the wait for a prerequisite finding
        self.mission = mission       # live directive (goal / tools / enabled), or None
        self._steps = 0
        self._waits = 0
        self._idle = False           # completed; idle until re-tasked (live mode)
        self._idle_ver = None
        self._history = []          # (action, verdict) for prompt context

    def _goal(self):
        if self.mission and self.mission.goal:
            return self.mission.goal
        return self.goal

    def _allowed_tools(self):
        base = self.pack["tools"]
        if self.mission and self.mission.allowed_tools:
            return [t for t in self.mission.allowed_tools if t in base]
        return base

    def _done_or_idle(self):
        """In live mode a finished unit idles (resumable when re-tasked); in
        batch mode it stops."""
        if self.mission:
            self._idle = True
            self._idle_ver = self.mission.version
            return WAIT
        return STOP

    def _system(self):
        return _SYSTEM.format(unit=self.pack["unit"],
                              tools=", ".join(self._allowed_tools()),
                              scope=", ".join(self.scope), goal=self._goal())

    def _user(self, context):
        findings = context.findings()
        lines = [f"Shared findings so far: {json.dumps(findings)[:800]}"]
        if self._history:
            lines.append("Your recent actions and how the kernel judged them:")
            for a, v in self._history[-4:]:
                lines.append(f"  - {a.get('tool')} {a.get('target')} -> {v}")
        lines.append("Propose the next action as one JSON object.")
        return "\n".join(lines)

    def propose(self, context, retries=2):
        # live mission gate: a disabled unit idles; a re-tasked idle unit resumes
        # with a fresh action budget.
        m = self.mission
        if m:
            if not m.enabled:
                return WAIT
            if self._idle:
                if m.version == self._idle_ver:
                    return WAIT
                self._idle = False
                self._steps = 0
        # tandem gate: a consumer unit (password<-hash, sniff<-host) idles until
        # its prerequisite finding exists, so it doesn't fire actions the kernel
        # would only hold. Bounded, so it never spins forever if recon produces
        # nothing.
        consumes = self.pack.get("consumes")
        if consumes and not context.findings(kind=consumes):
            if self._waits < self.max_waits:
                self._waits += 1
                return WAIT
        if self._steps >= self.max_steps:
            return self._done_or_idle()
        self._steps += 1
        allowed = self._allowed_tools()
        system = self._system()
        user = self._user(context)
        for attempt in range(retries + 1):      # tolerate small-model messiness
            try:
                action = _parse_action(self.backend.complete(system, user))
            except Exception as e:              # noqa
                user = (self._user(context) + f"\n\nYour previous reply was not "
                        f"valid JSON ({e}). Reply with EXACTLY one JSON object.")
                continue
            ok, why = _validate(action, self.pack)
            if ok and action.get("action") == "propose" and action.get("tool") not in allowed:
                ok, why = False, (f"tool {action.get('tool')!r} is not permitted by "
                                  f"the current mission (allowed: {allowed})")
            if not ok:
                user = (self._user(context) + f"\n\nYour previous action was "
                        f"rejected before scoring: {why}. Fix it; reply with one "
                        "JSON object.")
                continue
            if action.get("action") == "done":
                return self._done_or_idle()
            action.setdefault("unit", self.pack["unit"])
            action.setdefault("args", [])
            return action
        return self._done_or_idle()   # gave up after retries

    def record(self, action, verdict):
        """Called by the harness after evaluate() so the model sees consequences."""
        self._history.append((action, verdict))
