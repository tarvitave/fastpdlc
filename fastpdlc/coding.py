"""A code-writing runner for ST-04.

The reasoning stations only need one structured call. Develop is different: it has
to look at the tree and change it, which means tools and a loop.

This is deliberately a *small* coding agent, not a general one. It can read, write
and list files beneath one root, and nothing else — no shell, no network, no delete,
no rename. That is enough to implement a change and far short of what a general
agent can do to a machine, which matters because the thing driving it is a model.

Every path is resolved and checked against the root before any I/O, so `..`,
absolute paths and symlink escapes are refused rather than sanitised. The loop is
bounded; a run that will not converge stops and says so.

    from fastpdlc.coding import CodingRunner
    runner = CodingRunner(root=".", write=True)

`write=False` is the default: the agent sees the tree and proposes a diff without
touching anything. Opt in to letting a model edit your working tree.
"""
from __future__ import annotations

import json
import os
import pathlib
from typing import Any

from .orchestration import DEVELOP_SCHEMA, Station

MAX_TURNS = 12
MAX_READ_BYTES = 200_000
MAX_WRITE_BYTES = 400_000

SYSTEM = """\
You are the Develop station on an agent-built lifecycle. Implement the design you \
are given, and nothing beyond it.

You have three tools: list_files, read_file, write_file. There is no shell, no \
network, and no way to delete or rename. Read before you write — never write a file \
whose current contents you have not seen.

Work in small steps. When the change is complete, stop calling tools and return the \
final structured result: the files you changed and a concise diff summary for the \
test engineer and the reviewers.

You cannot merge, and you cannot run tests. A separate station tests your work, four \
critics try to refute it, a deterministic gate judges it, and a human decides."""

TOOLS = [
    {
        "name": "list_files",
        "description": "List files beneath a directory, relative to the project root.",
        "input_schema": {
            "type": "object",
            "properties": {
                "path": {"type": "string", "description": "relative directory, '.' for root"},
            },
            "required": ["path"],
        },
    },
    {
        "name": "read_file",
        "description": "Read a UTF-8 text file, relative to the project root.",
        "input_schema": {
            "type": "object",
            "properties": {"path": {"type": "string"}},
            "required": ["path"],
        },
    },
    {
        "name": "write_file",
        "description": "Create or overwrite a UTF-8 text file, relative to the project root.",
        "input_schema": {
            "type": "object",
            "properties": {
                "path": {"type": "string"},
                "content": {"type": "string"},
            },
            "required": ["path", "content"],
        },
    },
]


class PathOutsideRoot(Exception):
    """The agent asked for something outside the sandbox."""


class Sandbox:
    """Confined file access. Every path goes through `resolve` before any I/O."""

    def __init__(self, root: str | pathlib.Path, write: bool = False):
        self.root = pathlib.Path(root).resolve()
        self.write_enabled = write
        self.written: list[str] = []
        self.read: list[str] = []

    def resolve(self, relative: str) -> pathlib.Path:
        candidate = pathlib.Path(relative)
        if candidate.is_absolute():
            raise PathOutsideRoot(f"absolute paths are refused: {relative}")
        # resolve() collapses .. and follows symlinks, so the containment check
        # below cannot be fooled by either.
        target = (self.root / candidate).resolve()
        if target != self.root and self.root not in target.parents:
            raise PathOutsideRoot(f"outside the project root: {relative}")
        return target

    def list_files(self, relative: str = ".") -> str:
        base = self.resolve(relative or ".")
        if not base.is_dir():
            return f"not a directory: {relative}"
        names = []
        for entry in sorted(base.iterdir()):
            if entry.name.startswith(".") or entry.name in {"__pycache__", "node_modules"}:
                continue
            names.append(entry.name + ("/" if entry.is_dir() else ""))
        return "\n".join(names) or "(empty)"

    def read_file(self, relative: str) -> str:
        target = self.resolve(relative)
        if not target.is_file():
            return f"no such file: {relative}"
        if target.stat().st_size > MAX_READ_BYTES:
            return f"file too large to read ({target.stat().st_size} bytes): {relative}"
        self.read.append(relative)
        return target.read_text(encoding="utf-8", errors="replace")

    def write_file(self, relative: str, content: str) -> str:
        if not self.write_enabled:
            # Proposing is still useful: the diff summary is the deliverable.
            self.written.append(relative)
            return (f"DRY RUN: not written. Recorded {relative} "
                    f"({len(content)} chars) as a proposed change.")
        if len(content.encode()) > MAX_WRITE_BYTES:
            return f"refused: content exceeds {MAX_WRITE_BYTES} bytes"
        target = self.resolve(relative)
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(content, encoding="utf-8", newline="\n")
        self.written.append(relative)
        return f"wrote {relative} ({len(content)} chars)"


class CodingRunner:
    """Runs Develop as a bounded tool loop; every other station as one call."""

    def __init__(self, root: str | pathlib.Path = ".", *, write: bool = False,
                 api_key: str | None = None, max_turns: int = MAX_TURNS,
                 fallback: Any = None, model: str = "claude-opus-5"):
        self.sandbox = Sandbox(root, write=write)
        self.max_turns = max_turns
        self.model = model
        self._api_key = api_key or os.getenv("ANTHROPIC_API_KEY")
        self._client: Any = None
        # Non-Develop stations do not need tools; delegate them.
        from .runners import ClaudeRunner
        self.fallback = fallback or ClaudeRunner(api_key=self._api_key)

    def _get_client(self) -> Any:
        if self._client is not None:
            return self._client
        if not self._api_key:
            raise RuntimeError("ANTHROPIC_API_KEY is not set")
        try:
            import anthropic
        except ModuleNotFoundError as exc:
            raise RuntimeError(
                "the anthropic package is not installed: pip install 'fastpdlc[agents]'"
            ) from exc
        self._client = anthropic.Anthropic(api_key=self._api_key)
        return self._client

    def _dispatch(self, name: str, args: dict) -> str:
        try:
            if name == "list_files":
                return self.sandbox.list_files(args.get("path", "."))
            if name == "read_file":
                return self.sandbox.read_file(args["path"])
            if name == "write_file":
                return self.sandbox.write_file(args["path"], args.get("content", ""))
            return f"unknown tool: {name}"
        except PathOutsideRoot as exc:
            return f"REFUSED: {exc}"
        except (OSError, KeyError) as exc:
            return f"error: {exc}"

    def run(self, station: Station, prompt: str, schema: dict | None = None) -> dict:
        if station.id != "ST-04":
            return self.fallback.run(station, prompt, schema)

        client = self._get_client()
        messages: list[dict] = [{"role": "user", "content": prompt}]

        for _turn in range(self.max_turns):
            response = client.messages.create(
                model=self.model,
                max_tokens=16000,
                system=SYSTEM,
                thinking={"type": "adaptive"},
                output_config={"effort": station.effort or "high"},
                tools=TOOLS,
                messages=messages,
            )
            if getattr(response, "stop_reason", None) == "refusal":
                raise RuntimeError("ST-04 refused by safety classifier")

            if response.stop_reason != "tool_use":
                break

            messages.append({"role": "assistant", "content": response.content})
            results = []
            for block in response.content:
                if block.type != "tool_use":
                    continue
                results.append({
                    "type": "tool_result",
                    "tool_use_id": block.id,
                    "content": self._dispatch(block.name, block.input or {}),
                })
            # All tool results go back in ONE user message, or Claude learns to stop
            # calling tools in parallel.
            messages.append({"role": "user", "content": results})
        else:
            return {
                "files_changed": sorted(set(self.sandbox.written)),
                "diff_summary": (f"stopped after {self.max_turns} turns without "
                                 f"converging; treat this change as incomplete"),
                "self_notes": "turn limit reached",
            }

        # One more call, no tools, to get the structured result.
        messages.append({
            "role": "user",
            "content": "Return the final structured result for this change now.",
        })
        final = client.messages.create(
            model=self.model,
            max_tokens=8000,
            system=SYSTEM,
            output_config={"effort": "low",
                           "format": {"type": "json_schema",
                                      "schema": schema or DEVELOP_SCHEMA}},
            messages=messages,
        )
        text = "".join(b.text for b in final.content if b.type == "text")
        try:
            data = json.loads(text)
        except ValueError:
            data = {"files_changed": [], "diff_summary": text[:800]}

        # The sandbox is the source of truth about what actually changed -- not the
        # model's recollection of it.
        data["files_changed"] = sorted(set(self.sandbox.written))
        data.setdefault("self_notes", "")
        if not self.sandbox.write_enabled:
            data["self_notes"] += " (dry run: no files were written)"
        return data
