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


class ClaudeRunner:
    """Runs a station as one structured Messages API call.

    Model and effort come from the station itself, so the cost/correctness dial is
    explicit per role rather than every station inheriting one default: a cheap
    model where the work is retrieval, the strongest tier where being
    confident-but-wrong is the failure that matters.
    """

    def __init__(self, api_key: str | None = None, *, max_tokens: int = 16000,
                 system: str = SYSTEM):
        self._api_key = api_key or os.getenv("ANTHROPIC_API_KEY")
        self._max_tokens = max_tokens
        self._system = system
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

        response = client.messages.create(
            model=station.model or "claude-opus-5",
            max_tokens=self._max_tokens,
            system=self._system,
            thinking={"type": "adaptive"},
            output_config=output_config,
            messages=[{"role": "user", "content": prompt}],
        )

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
