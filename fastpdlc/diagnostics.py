"""Stable diagnostic codes — the validator's public API.

Every validation error carries a stable ``PAC-NNN`` code, prepended to a human
message. Codes are an API: CI, dashboards, and humans refer to a *class* of failure
without matching on prose. **Never renumber an existing code** — retire it and add a
new one. Ranges mirror the original product-as-code design:

  * ``00x`` — required-field / schema
  * ``01x`` — id & graph integrity (prefix, filename, duplicates)
  * ``02x`` — cross-reference resolution
  * ``03x`` — enum / allowed-value
  * ``06x`` — generated-bundle staleness

Projects add their own checks (see ``hooks``) and register custom codes via
``register()`` — keep them in a project-specific range (e.g. ``9xx``) so they never
collide with the core set.
"""
from __future__ import annotations

from dataclasses import dataclass, field

# ── core code registry ───────────────────────────────────────────────────────
CODES: dict[str, str] = {
    "PAC-001": "artifact is missing a required field",
    "PAC-010": "artifact id does not start with its type's id_prefix",
    "PAC-011": "artifact id does not match its filename",
    "PAC-012": "duplicate artifact id within a type",
    "PAC-020": "a reference field does not resolve to a known artifact",
    "PAC-030": "a field value is not in the type's allowed set",
    "PAC-060": "the committed generated bundle is missing or stale",
}


def register(code: str, message: str) -> None:
    """Register (or re-document) a diagnostic code. A project owns its own code
    numbers — re-registering an existing code overrides its documentation, so a
    project that reuses the core numbers with its own meanings (or ships its own
    range) just works."""
    CODES[code] = message


@dataclass(frozen=True)
class Diagnostic:
    """A single finding: a stable code, a human message, and where it was found."""

    code: str
    message: str
    where: str = ""
    severity: str = "error"  # "error" (gating) or "warning" (advisory)

    def render(self) -> str:
        loc = f"{self.where}: " if self.where else ""
        return f"{self.code} {loc}{self.message}"


@dataclass
class Report:
    """Accumulates diagnostics from a validation run."""

    diagnostics: list[Diagnostic] = field(default_factory=list)

    def add(self, code: str, message: str, where: str = "", severity: str = "error") -> None:
        self.diagnostics.append(Diagnostic(code, message, where, severity))

    @property
    def errors(self) -> list[Diagnostic]:
        return [d for d in self.diagnostics if d.severity == "error"]

    @property
    def warnings(self) -> list[Diagnostic]:
        return [d for d in self.diagnostics if d.severity == "warning"]

    @property
    def ok(self) -> bool:
        return not self.errors
