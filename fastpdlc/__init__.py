"""FastPDLC — the rubric, the gate, and the line that builds against them.

Declare your typed product artifacts (features, decisions, terms, rules, whatever
your project needs) in a ``product.config.yaml``; FastPDLC loads them, enforces the
schema + cross-references, compiles a JSON bundle, and fails CI if the committed
bundle drifts — turning a folder of hopeful markdown into code.

Three surfaces, in increasing order of ambition:

* ``build`` / ``validate`` — the compiler and the gate. Deterministic, two
  dependencies, no network. This is what CI runs.
* ``evidence`` — a content-addressed record of what was checked, when, on which
  commit, and with what result.
* ``orchestration`` — the agent-built lifecycle: Understand → Disambiguate (a
  human gate) → Design → Develop → Test → adversarial Verify, with bounded repair.
  Needs ``fastpdlc[agents]``; nothing else does.

The gate is never an agent. A judge that could be persuaded could not produce
evidence, so every station past it is deterministic or human by construction.
"""
from __future__ import annotations

from .config import ArtifactType, Config, Reference, load_config
from .diagnostics import CODES, Diagnostic, Report, register
from .engine import build, load, render_bundle, validate
from .evidence import build_record, render as render_evidence
from .orchestration import (
    LENSES,
    ROSTER,
    Orchestrator,
    RunReport,
    Runner,
    Station,
    StubRunner,
    Verdict,
    read_resolutions,
    write_questions,
)
from .plugin import Registry, load_plugin

__version__ = "0.2.1"

__all__ = [
    # config
    "ArtifactType",
    "Config",
    "Reference",
    "load_config",
    # diagnostics
    "CODES",
    "Diagnostic",
    "Report",
    "register",
    # engine
    "build",
    "load",
    "render_bundle",
    "validate",
    # evidence
    "build_record",
    "render_evidence",
    # the agent-built lifecycle
    "LENSES",
    "ROSTER",
    "Orchestrator",
    "RunReport",
    "Runner",
    "Station",
    "StubRunner",
    "Verdict",
    "read_resolutions",
    "write_questions",
    # plugins
    "Registry",
    "load_plugin",
    "__version__",
]
