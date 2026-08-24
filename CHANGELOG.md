# Changelog

All notable changes to FastPDLC. The format follows
[Keep a Changelog](https://keepachangelog.com/en/1.1.0/), and this project follows
[semantic versioning](https://semver.org/).

**Diagnostic codes are API.** A `PAC-NNN` is never renumbered — a check that changes
meaning gets a new code and the old one is retired. Changing the JSON bundle shape, a
config key, or the plugin `Registry` surface is a breaking change and bumps the major.

## [Unreleased]

Nothing yet.

## [0.3.0] — 2026-08-24

Quality and ergonomics. No breaking changes: every existing command behaves as it
did, and the additions are opt-in flags.

### Added

- **`fastpdlc validate --json`** — findings as structured output against a
  `fastpdlc-report/1` schema. Diagnostic codes were already an API; making a
  consumer regex the prose to find one defeated the point of having them.
- **`fastpdlc evidence --verify RECORD`** — recomputes every digest in a record and
  reports what no longer matches. Content-addressing is only worth something if
  somebody can check it; producing a record nobody can verify is a claim, not
  evidence. Needs no key, no trust in the issuer and no network.
- **Orchestrator runs are kept** at `.fastpdlc/runs/<id>-<timestamp>.json`. A run
  refuted after two repair rounds holds the four verdicts and their failing cases —
  the most useful thing it produced. Discarding it because nothing was proposed was
  backwards.
- An **opt-in integration test** (`pytest -m integration`, needs `ANTHROPIC_API_KEY`)
  that exercises one cheap station against the real endpoint. Everything else stubs
  the model, which meant an API change would have broken users rather than CI.

### Changed

- **`PAC-060` now names what drifted.** "the bundle is stale" tells you to run a
  command; "2 artifact(s) differ: +BR-idempotent, TERM-ledger" tells you whether it
  is the change you meant to make, which is the question a reviewer actually has.
  Additions are prefixed `+`, removals `-`.

### Quality

- Library coverage **72% → 90%**, 28 → 58 tests, concentrated where it was thinnest:
  the CLI (30 → 80%), the plugin loader (62 → 97%), the coding sandbox (40 → 82%)
  and the runners (52 → 81%).
- Python 3.10 compatibility verified by parsing every module at that feature level,
  rather than assumed from the classifier list.
- `ruff` config and an 85% coverage floor in CI. The floor exists to stop coverage
  rotting, not to be gamed upward.

## [0.2.1] — 2026-08-23

Packaging only. No library changes — `0.2.0` and `0.2.1` are identical to import
and run.

### Changed

- **The sdist ships only the package.** `0.2.0`'s source distribution defaulted to
  "everything not gitignored", which included the marketing site, the Terraform and
  the deploy config — 125 files, 221 KB. It contained no secrets, but a published
  artifact should not depend on a `.gitignore` staying correct forever, and a PyPI
  version can be yanked and never replaced. The sdist is now an allowlist: 30
  files, 42 KB, with no `site/`, `infra/` or `.fastpdlc/`.
- `0.2.0` is yanked in favour of this release. It is safe — nothing secret was ever
  in it — but there is no reason to keep distributing the wider tarball.

### Added

- `scripts/check_no_secrets.py` — refuses credential-shaped strings in the package
  tree, and with `--dist` in the built artifacts, plus any operational path in the
  sdist. Runs in CI on every push and in the publish workflow immediately before
  upload, which is the last moment a leak is still recallable.

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

[Unreleased]: https://github.com/tarvitave/fastpdlc/compare/v0.3.0...HEAD
[0.3.0]: https://github.com/tarvitave/fastpdlc/compare/v0.2.1...v0.3.0
[0.2.1]: https://github.com/tarvitave/fastpdlc/compare/v0.2.0...v0.2.1
[0.2.0]: https://github.com/tarvitave/fastpdlc/compare/v0.1.0...v0.2.0
[0.1.0]: https://github.com/tarvitave/fastpdlc/releases/tag/v0.1.0
