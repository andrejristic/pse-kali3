# =============================================================================
# PSE-KALI — COMMANDER (the SHARED_LIB's human-facing brain)
# The human talks to the commander in natural language; the commander turns that
# into per-unit MISSION updates (enable/disable, goal, which tools). This is the
# corpus's "SHARED_LIB writes mission into Core Self", made interactive.
#
# GOVERNANCE: the commander can only ever TIGHTEN within the config scope. It
# has no scope field and cannot widen it; `allowed_tools` is intersected with
# the unit's pack tools, so it can never grant a tool the unit doesn't have.
# The authorization floor stays a hard wall enforced by the kernel.
# =============================================================================
import json

from .operator import _parse_action

_COMMANDER_SYSTEM = """You are the commander of a governed, authorized security \
engagement. You direct the units by setting their missions; you do NOT run \
tools yourself, and you CANNOT change the authorized scope (that is a hard wall \
set by the human).

Units and the tools each may use:
{units_and_tools}

For each unit you may set: "enabled" (true/false), "goal" (one sentence), and \
"allowed_tools" (a SUBSET of that unit's tools above). You may only narrow a \
unit's tools, never add tools it doesn't have.

Given the human's command and the current missions, reply with ONE JSON object:
{{"missions": {{"<unit>": {{"enabled": <bool>, "goal": "<text>", \
"allowed_tools": ["<tool>", ...]}}, ...}}, "reply": "<one sentence to the human>"}}
Include only the units you are changing. Omit fields you are not changing."""


class Commander:
    def __init__(self, backend, packs):
        self.backend = backend
        self.packs = packs      # {unit: pack}

    def _system(self):
        units = "\n".join(f"- {u}: {', '.join(p['tools'])}"
                          for u, p in self.packs.items())
        return _COMMANDER_SYSTEM.format(units_and_tools=units)

    def _user(self, command, missions):
        cur = {u: m.snapshot() for u, m in missions.items()}
        return (f"Current missions: {json.dumps(cur)}\n"
                f"Human command: {command}\n"
                "Reply with one JSON object of the mission changes.")

    def plan(self, command, missions):
        """Apply the human's command to the live missions. Returns (reply, changed).
        Every change is validated: unknown units ignored, tools intersected with
        the pack's tools. Scope is never touched."""
        raw = self.backend.complete(self._system(), self._user(command, missions))
        data = _parse_action(raw)          # tolerant JSON parse
        changed = []
        for unit, upd in (data.get("missions") or {}).items():
            if unit not in self.packs or unit not in missions:
                continue
            tools = upd.get("allowed_tools")
            if tools is not None:
                pack_tools = self.packs[unit]["tools"]
                tools = [t for t in tools if t in pack_tools]   # subset only
            missions[unit].update(enabled=upd.get("enabled"),
                                  goal=upd.get("goal"), allowed_tools=tools)
            changed.append(unit)
        return data.get("reply", "(missions updated)"), changed
