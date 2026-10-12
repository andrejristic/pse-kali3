"""PSE-Kali governance kernel — the moat.

One deterministic, inspectable scoring + membrane engine that governs any number
of concurrent security tool-units against a shared engagement context. Tool
behaviour is configured by packs; kernel code is domain-agnostic.
"""
from .constants import ATTRACTORS, EPSILON, EPSILON_AUTH, VAR_LIMIT
from .context import EngagementContext
from .audit import AuditLog, NullAudit
from .kernel import evaluate, Decision
from .membrane import Intervention
from .scoring import score
from .orchestrator import (Swarm, Unit, Operator, ScriptedOperator,
                           ReactiveOperator, ChainOperator, WAIT, STOP)
from .operator import (ModelOperator, make_backend, MockBackend, ClaudeBackend,
                       MistralBackend, LocalGGUFBackend, SwappableBackend,
                       detect_ram_gb, select_gguf, selftest_backend, ACTION_SCHEMA)
from .control import Mission, ControlChannel, Escalation
from .models import list_local_models, ram_free_gb
from .commander import Commander
from .engine import LiveEngine

__all__ = [
    "ATTRACTORS", "EPSILON", "EPSILON_AUTH", "VAR_LIMIT",
    "EngagementContext", "AuditLog", "NullAudit",
    "evaluate", "Decision", "Intervention", "score",
    "Swarm", "Unit", "Operator", "ScriptedOperator", "ReactiveOperator",
    "ChainOperator", "WAIT", "STOP",
    "ModelOperator", "make_backend", "MockBackend", "ClaudeBackend",
    "MistralBackend", "LocalGGUFBackend", "SwappableBackend", "detect_ram_gb",
    "select_gguf", "selftest_backend", "ACTION_SCHEMA",
    "Mission", "ControlChannel", "Escalation", "list_local_models",
    "ram_free_gb", "Commander", "LiveEngine",
]
