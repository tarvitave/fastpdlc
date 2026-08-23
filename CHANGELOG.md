# Changelog

All notable changes to FastPDLC. The format follows
[Keep a Changelog](https://keepachangelog.com/en/1.1.0/), and this project follows
[semantic versioning](https://semver.org/).

**Diagnostic codes are API.** A `PAC-NNN` is never renumbered — a check that changes
meaning gets a new code and the old one is retired. Changing the JSON bundle shape, a
config key, or the plugin `Registry` surface is a breaking change and bumps the major.

## [Unreleased]

Nothing yet.

## [0.2.0] — 2026-08-23

Two new surfaces on top of the compiler and the gate. `build` and `validate` are
unchanged: same two runtime dependencies, no network, still the thing CI runs.

### Added

- **`fastpdlc orchestrate`** — the agent-built lifecycle over one artifact:
  Understand → Disambiguate → Design → Develop → Test → adversarial Verify, with a
  bounded repair loop. Control flow is deterministic; reasoning happens inside a
  station. Requires the new `agents` extra.
- **Four refuting lenses** at Verify — correctness, coverage, security, reproduce —
  running in parallel, each defaulting to *refuted* unless convinced. Minor findings
  deliberately do not block: a gate that fires on nitpicks gets bypassed.
- **`--cross-provider`** adds a fifth verdict from a non-Claude model via OpenRouter,
  so the critic cannot share the builder's blind spots. Uses stdlib `urllib`, so the
  core gains no dependency. Skipped without `OPENROUTER_API_KEY`; abstains rather
  than blocking if the call fails.
- **`--write`** lets the Develop station edit files through a bounded tool loop
  (list, read, write) confined to the project root. Containment is checked after path
  resolution, so `..`, absolute paths and symlink escapes are refused rather than
  sanitised. No shell, no network, no delete, no rename. Off by default.
- **`--dry-run`** exercises the whole pipeline offline with no model calls.
- **The human gate as a file** — `.fastpdlc/disambiguations/<id>.json`. Run one writes
  the open questions and stops, a person fills in each `answer`, run two proceeds. A
  blocking human gate cannot live inside one autonomous run, so it is two-phase by
  construction. `--resolve id=answer` does the same inline.
- **`fastpdlc evidence`** — a content-addressed record of what was checked, when, on
  which commit, and with what result. Every artifact, the config and the bundle carry
  a SHA-256, so a record is verified by recomputing digests rather than by trusting
  its issuer. Exit code follows `validate`, so CI can gate and record in one step.
- **`agents` extra** — `pip install 'fastpdlc[agents]'` pulls in `anthropic`. Nothing
  else in the library needs it.
- Public API: `Orchestrator`, `Runner`, `Station`, `StubRunner`, `Verdict`, `ROSTER`,
  `LENSES`, `read_resolutions`, `write_questions`, `build_record` are exported from
  the package root.

### Fixed

- YAML parses an unquoted `date: 2026-02-04` into a `datetime.date`, which
  `json.dumps` could not serialize — any project with a date field in frontmatter hit
  this. Bundles now emit ISO-8601 strings. Found by using the tool on its own blog.

### Notes

The orchestrator cannot merge: its terminal state is a report, and every station past
the gate is deterministic or human by construction. It also cannot run tests — Develop
has no shell — so a passing test report is a *claim* your CI still has to check.
Assembling a pull request and reading production back into intent are the caller's
job; the library has no git and no network.

## [0.1.0] — 2026-08-22

First release. The engine extracted from the pharthing / KibiPay payments platform,
verified by a byte-identical parity test.

### Added

- `fastpdlc build` — compile typed artifacts into one deterministic JSON bundle
  (sorted keys, fixed formatting, no timestamps).
- `fastpdlc validate` — schema, id integrity, cross-references and staleness. Exit
  code is the CI gate.
- Diagnostic codes: `PAC-001` required field, `PAC-010`/`011`/`012` id integrity,
  `PAC-020` reference resolution, `PAC-030` enum membership, `PAC-060` bundle
  staleness.
- Plugins — project validators, bundle transformers, extra staleness-gated outputs,
  and custom diagnostic codes in a project range.
- A reusable GitHub Action and a copier template.
- LGPL-3.0-or-later: copyleft on the engine, and importing it as a library does not
  place your project under the LGPL.

[Unreleased]: https://github.com/tarvitave/fastpdlc/compare/v0.2.0...HEAD
[0.2.0]: https://github.com/tarvitave/fastpdlc/compare/v0.1.0...v0.2.0
[0.1.0]: https://github.com/tarvitave/fastpdlc/releases/tag/v0.1.0
