"""Station runners — where the model actually gets called.

The orchestrator owns control flow; a runner owns one step's reasoning. Keeping
them apart is the spec's second principle, and it is why the pipeline is testable
without a network: swap `ClaudeRunner` for `StubRunner` and the wiring is unchanged.

`anthropic` is an optional dependency. FastPDLC's core job is validation, and a
missing SDK must not stop `fastpdlc validate` from running in CI.
"""
from __future__ import annotations

import json
import os
from typing import Any

from .orchestration import Station

SYSTEM = """\
You are one station on an agent-built software lifecycle.

The rules of the line:
- You own exactly one column of the work. Do not do another station's job.
- Return the structured result you were asked for and nothing else.
- Never claim something was verified that you did not verify.
- You propose; a deterministic gate judges and a human merges. You cannot ship.

Product intent is versioned source and the rubric already exists. You are labour
against it, not an author of it."""


_UNSET: Any = object()


def resolve_thinking(explicit: Any = _UNSET) -> dict | None:
    """The Anthropic ``thinking`` config to send, or ``None`` to omit the param.

    Not every model supports extended thinking — Haiku, in particular, rejects
    ``{"type": "adaptive"}`` with a 400 — so this must be controllable rather than
    hard-wired on. Precedence: an explicit value passed to the runner (including an
    explicit ``None``) wins; otherwise the ``FASTPDLC_THINKING`` env var; otherwise
    adaptive. Accepted env values: ``adaptive`` (default), ``off``/``none``/``0``/``""``
    to omit, or ``enabled:<budget_tokens>`` for fixed-budget extended thinking.
    """
    if explicit is not _UNSET:
        return explicit
    raw = os.getenv("FASTPDLC_THINKING", "adaptive").strip().lower()
    if raw in ("", "off", "none", "no", "0", "false"):
        return None
    if raw.startswith("enabled"):
        _, _, budget = raw.partition(":")
        try:
            return {"type": "enabled", "budget_tokens": int(budget)}
        except ValueError:
            return {"type": "enabled", "budget_tokens": 8000}
    return {"type": "adaptive"}


def create_message(client: Any, base_kwargs: dict, thinking: dict | None) -> tuple[Any, bool]:
    """``messages.create`` that degrades gracefully when a model rejects ``thinking``.

    A station running a model without extended-thinking support (e.g. the Haiku
    ``Understand`` station) would otherwise 400 and sink the whole run at step one.
    When ``thinking`` is set and the API rejects *specifically* the thinking param,
    retry the same call once without it. Returns ``(response, thinking_was_accepted)``
    so the caller can stop sending it on later calls in the same process.
    """
    if thinking is not None:
        try:
            return client.messages.create(thinking=thinking, **base_kwargs), True
        except Exception as exc:
            if "thinking" not in str(exc).lower():
                raise
            # Model doesn't support this thinking mode — fall through and omit it.
    return client.messages.create(**base_kwargs), False


class ClaudeRunner:
    """Runs a station as one structured Messages API call.

    Model and effort come from the station itself, so the cost/correctness dial is
    explicit per role rather than every station inheriting one default: a cheap
    model where the work is retrieval, the strongest tier where being
    confident-but-wrong is the failure that matters.
    """

    def __init__(self, api_key: str | None = None, *, max_tokens: int = 16000,
                 system: str = SYSTEM, thinking: Any = _UNSET):
        self._api_key = api_key or os.getenv("ANTHROPIC_API_KEY")
        self._max_tokens = max_tokens
        self._system = system
        self._thinking = resolve_thinking(thinking)
        self._thinking_supported = True   # flipped off once a model 400s on it
        self._client: Any = None

    def _get_client(self) -> Any:
        if self._client is not None:
            return self._client
        if not self._api_key:
            raise RuntimeError(
                "ANTHROPIC_API_KEY is not set -- use --dry-run for the stub runner")
        try:
            import anthropic
        except ModuleNotFoundError as exc:
            raise RuntimeError(
                "the anthropic package is not installed: pip install 'fastpdlc[agents]'"
            ) from exc
        self._client = anthropic.Anthropic(api_key=self._api_key)
        return self._client

    def run(self, station: Station, prompt: str, schema: dict | None = None) -> dict:
        client = self._get_client()

        output_config: dict[str, Any] = {"effort": station.effort or "high"}
        if schema is not None:
            output_config["format"] = {"type": "json_schema", "schema": schema}

        base_kwargs = {
            "model": station.model or "claude-opus-5",
            "max_tokens": self._max_tokens,
            "system": self._system,
            "output_config": output_config,
            "messages": [{"role": "user", "content": prompt}],
        }
        thinking = self._thinking if self._thinking_supported else None
        response, accepted = create_message(client, base_kwargs, thinking)
        if thinking is not None and not accepted:
            self._thinking_supported = False  # this model rejects it; skip it hereafter

        if getattr(response, "stop_reason", None) == "refusal":
            raise RuntimeError(f"{station.id} refused by safety classifier")

        text = "".join(b.text for b in response.content if b.type == "text")
        if schema is None:
            return {"text": text}
        try:
            return json.loads(text)
        except ValueError as exc:
            raise RuntimeError(f"{station.id} returned unparseable JSON") from exc


# ── the cross-provider adversary ─────────────────────────────────────────────
# The structural break in the correlated-validation loop: a critic from a DIFFERENT
# model provider, so it cannot share the builder's blind spots. Diversity is a
# correctness lever, not a nicety.
#
# stdlib only, on purpose. `validate` must stay dependency-light, and this lens is
# opt-in via OPENROUTER_API_KEY -- with the key absent the run is byte-identical to
# native-only. A critic that cannot be reached ABSTAINS; it must never block a line.
CROSS_PROVIDER_LENS = "cross-provider(openrouter)"

_CROSS_SYSTEM = (
    "You are an adversarial code reviewer. Try to REFUTE the change -- default to "
    "refuted=true if you are not convinced it is correct and safe. Reply with STRICT "
    "JSON only, no prose and no markdown fences, matching exactly: "
    '{"lens":"' + CROSS_PROVIDER_LENS + '","refuted":<bool>,'
    '"severity":"blocker|major|minor|none",'
    '"reason":<string>,"failing_case":<string>}'
)


class CrossProviderLens:
    """One more verdict, from a non-Claude model routed through OpenRouter."""

    ENDPOINT = "https://openrouter.ai/api/v1/chat/completions"

    def __init__(self, api_key: str | None = None, model: str | None = None,
                 timeout: float = 60.0):
        self.api_key = api_key or os.getenv("OPENROUTER_API_KEY", "")
        self.model = model or os.getenv("OPENROUTER_MODEL", "openai/gpt-4o")
        self.timeout = timeout

    @property
    def enabled(self) -> bool:
        return bool(self.api_key)

    def verdict(self, context: str) -> dict:
        """Always returns a verdict-shaped dict. Never raises."""
        from .orchestration import Verdict

        if not self.enabled:
            return dataclasses_asdict(
                Verdict.benign(CROSS_PROVIDER_LENS, "OPENROUTER_API_KEY not set"))

        import urllib.error
        import urllib.request

        body = json.dumps({
            "model": self.model,
            "temperature": 0,
            "response_format": {"type": "json_object"},
            "messages": [
                {"role": "system", "content": _CROSS_SYSTEM},
                {"role": "user", "content": context},
            ],
        }).encode()

        request = urllib.request.Request(
            self.ENDPOINT, data=body, method="POST",
            headers={"Authorization": f"Bearer {self.api_key}",
                     "Content-Type": "application/json"},
        )
        try:
            with urllib.request.urlopen(request, timeout=self.timeout) as response:
                payload = json.loads(response.read().decode())
            content = payload["choices"][0]["message"]["content"]
            data = json.loads(content)
        except (urllib.error.URLError, OSError, ValueError, KeyError, IndexError) as exc:
            return dataclasses_asdict(
                Verdict.benign(CROSS_PROVIDER_LENS, f"{type(exc).__name__}"))

        data["lens"] = CROSS_PROVIDER_LENS
        return data


def dataclasses_asdict(obj) -> dict:
    import dataclasses
    return dataclasses.asdict(obj)
