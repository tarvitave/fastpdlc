"""FastPDLC — product-as-code as a validated graph, for any project.

Declare your typed product artifacts (features, decisions, terms, rules, whatever
your project needs) in a ``product.config.yaml``; FastPDLC loads them, enforces the
schema + cross-references, compiles a JSON bundle, and fails CI if the committed
bundle drifts — turning a folder of hopeful markdown into code.
"""
from __future__ import annotations

from .config import ArtifactType, Config, Reference, load_config
from .diagnostics import CODES, Diagnostic, Report, register
from .engine import build, load, render_bundle, validate
from .plugin import Registry, load_plugin

__version__ = "0.1.0"

__all__ = [
    "ArtifactType",
    "Config",
    "Reference",
    "load_config",
    "CODES",
    "Diagnostic",
    "Report",
    "register",
    "build",
    "load",
    "render_bundle",
    "validate",
    "Registry",
    "load_plugin",
    "__version__",
]
