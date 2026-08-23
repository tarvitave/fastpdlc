"""Tests for the FastPDLC engine: schema/id/reference/enum/staleness + the plugin API."""
from __future__ import annotations

import json
import pathlib

import pytest
import sys

import yaml

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1]))

from fastpdlc import build, register, render_bundle, validate  # noqa: E402
from fastpdlc.config import ArtifactType, Config, Reference  # noqa: E402
from fastpdlc.plugin import Registry  # noqa: E402


def _write(root: pathlib.Path, rel: str, meta: dict, body: str = "body") -> None:
    p = root / "product" / rel
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text("---\n" + yaml.safe_dump(meta, sort_keys=False) + "---\n" + body + "\n", encoding="utf-8")


def _config() -> Config:
    return Config(
        product_dir="product",
        output="build/b.json",
        types=[
            ArtifactType(
                name="terms",
                dir="terms",
                id_prefix="TERM-",
                required=["id", "term"],
                fields=["term", "kind", "see_also"],
                enums={"kind": ["money", "ops"]},
                references=[Reference(field="see_also", to="terms")],
            )
        ],
    )


def _codes(report) -> set[str]:
    return {d.code for d in report.diagnostics}


def _fresh(tmp_path, cfg) -> None:
    build(cfg, tmp_path)  # so PAC-060 (staleness) doesn't fire on unrelated tests


def test_valid_tree_passes(tmp_path):
    cfg = _config()
    _write(tmp_path, "terms/TERM-a.md", {"id": "TERM-a", "term": "A", "kind": "money"})
    _fresh(tmp_path, cfg)
    assert validate(cfg, tmp_path).ok


def test_missing_required_field_pac001(tmp_path):
    cfg = _config()
    _write(tmp_path, "terms/TERM-a.md", {"id": "TERM-a"})  # no `term`
    _fresh(tmp_path, cfg)
    assert "PAC-001" in _codes(validate(cfg, tmp_path))


def test_bad_prefix_pac010(tmp_path):
    cfg = _config()
    _write(tmp_path, "terms/BAD-a.md", {"id": "BAD-a", "term": "A"})
    _fresh(tmp_path, cfg)
    assert "PAC-010" in _codes(validate(cfg, tmp_path))


def test_filename_mismatch_pac011(tmp_path):
    cfg = _config()
    _write(tmp_path, "terms/TERM-wrong.md", {"id": "TERM-a", "term": "A"})
    _fresh(tmp_path, cfg)
    assert "PAC-011" in _codes(validate(cfg, tmp_path))


def test_unresolved_reference_pac020(tmp_path):
    cfg = _config()
    _write(tmp_path, "terms/TERM-a.md", {"id": "TERM-a", "term": "A", "see_also": ["TERM-ghost"]})
    _fresh(tmp_path, cfg)
    assert "PAC-020" in _codes(validate(cfg, tmp_path))


def test_enum_violation_pac030(tmp_path):
    cfg = _config()
    _write(tmp_path, "terms/TERM-a.md", {"id": "TERM-a", "term": "A", "kind": "banana"})
    _fresh(tmp_path, cfg)
    assert "PAC-030" in _codes(validate(cfg, tmp_path))


def test_stale_bundle_pac060(tmp_path):
    cfg = _config()
    _write(tmp_path, "terms/TERM-a.md", {"id": "TERM-a", "term": "A"})
    # never built -> missing/stale
    assert "PAC-060" in _codes(validate(cfg, tmp_path))


def test_build_is_deterministic(tmp_path):
    cfg = _config()
    _write(tmp_path, "terms/TERM-a.md", {"id": "TERM-a", "term": "A"})
    assert render_bundle(cfg, tmp_path) == render_bundle(cfg, tmp_path)


# ── plugin system ────────────────────────────────────────────────────────────
def test_plugin_validator_and_transformer_and_output(tmp_path):
    cfg = _config()
    _write(tmp_path, "terms/TERM-a.md", {"id": "TERM-a", "term": "A"})

    register("PAC-900", "custom: term has no body")
    reg = Registry()

    @reg.validator
    def bodies_present(bundle, config, root, report):
        for rec in bundle["terms"]:
            if not rec["body"]:
                report.add("PAC-900", "term has no body", rec["_file"])

    @reg.bundle_transformer
    def add_count(bundle, config, root):
        bundle["term_count"] = len(bundle["terms"])

    reg.extra_output("build/catalogue.json", lambda bundle, config, root: '{"n": %d}\n' % bundle["term_count"])

    written = build(cfg, tmp_path, reg)
    assert (tmp_path / "build" / "catalogue.json").exists()
    assert len(written) == 2  # main bundle + extra output
    # the transformer field is in the bundle
    import json
    assert json.loads((tmp_path / "build" / "b.json").read_text())["term_count"] == 1
    # validate is clean (bodies present, outputs fresh)
    assert validate(cfg, tmp_path, reg).ok

    # a body-less term trips the custom validator; a hand-edited catalogue trips PAC-060
    _write(tmp_path, "terms/TERM-b.md", {"id": "TERM-b", "term": "B"}, body="")
    build(cfg, tmp_path, reg)
    (tmp_path / "build" / "catalogue.json").write_text("stale\n")
    codes = _codes(validate(cfg, tmp_path, reg))
    assert "PAC-900" in codes and "PAC-060" in codes


def test_dates_in_frontmatter_serialize_to_iso(tmp_path):
    """YAML turns an unquoted 2026-02-04 into datetime.date; the bundle must still
    build, emitting ISO-8601 rather than blowing up in json.dumps."""
    (tmp_path / "product" / "posts").mkdir(parents=True)
    (tmp_path / "product" / "posts" / "POST-hello.md").write_text(
        "---\nid: POST-hello\ntitle: Hello\ndate: 2026-02-04\n---\nBody.\n",
        encoding="utf-8",
    )
    (tmp_path / "product.config.yaml").write_text(
        "product_dir: product\n"
        "output: build/out.json\n"
        "types:\n"
        "  - name: posts\n"
        "    dir: posts\n"
        "    id_prefix: 'POST-'\n"
        "    required: [id, title, date]\n"
        "    fields: [title, date]\n",
        encoding="utf-8",
    )
    from fastpdlc import engine
    from fastpdlc.config import load_config

    config = load_config(str(tmp_path / "product.config.yaml"))
    engine.build(config, str(tmp_path))
    bundle = json.loads((tmp_path / "build" / "out.json").read_text(encoding="utf-8"))
    assert bundle["posts"][0]["date"] == "2026-02-04"
    assert engine.validate(config, str(tmp_path)).ok


def _tiny_project(tmp_path):
    (tmp_path / "product" / "terms").mkdir(parents=True)
    (tmp_path / "product" / "terms" / "TERM-payment.md").write_text(
        "---\nid: TERM-payment\nterm: Payment\ndefinition: Moving money.\n---\nBody.\n",
        encoding="utf-8",
    )
    (tmp_path / "product.config.yaml").write_text(
        "product_dir: product\n"
        "output: build/out.json\n"
        "types:\n"
        "  - name: terms\n"
        "    dir: terms\n"
        "    id_prefix: 'TERM-'\n"
        "    required: [id, term, definition]\n"
        "    fields: [term, definition]\n",
        encoding="utf-8",
    )
    from fastpdlc.config import load_config
    return load_config(str(tmp_path / "product.config.yaml"))


def test_evidence_record_is_content_addressed(tmp_path):
    """Every artifact and the bundle carry a digest, so a record can be verified by
    recomputation rather than by trusting whoever produced it."""
    import hashlib

    from fastpdlc import engine, evidence

    config = _tiny_project(tmp_path)
    engine.build(config, str(tmp_path))
    record = evidence.build_record(config, str(tmp_path))

    assert record["schema"] == "fastpdlc-evidence/1"
    assert record["result"] == "pass"
    assert record["counts"] == {"terms": 1}

    artifact = record["artifacts"]["terms"][0]
    on_disk = (tmp_path / artifact["file"]).read_bytes()
    assert artifact["sha256"] == hashlib.sha256(on_disk).hexdigest()

    bundle_bytes = (tmp_path / "build" / "out.json").read_bytes()
    assert record["bundle"]["sha256"] == hashlib.sha256(bundle_bytes).hexdigest()
    assert record["bundle"]["matches_sources"] is True


def test_evidence_reports_staleness_and_failure(tmp_path):
    """A record of a failing run is still a valid record -- it just says so."""
    from fastpdlc import engine, evidence

    config = _tiny_project(tmp_path)
    engine.build(config, str(tmp_path))

    # edit a source without rebuilding: the classic drift
    (tmp_path / "product" / "terms" / "TERM-payment.md").write_text(
        "---\nid: TERM-payment\nterm: Payment\ndefinition: Changed.\n---\nBody.\n",
        encoding="utf-8",
    )
    record = evidence.build_record(config, str(tmp_path))

    assert record["result"] == "fail"
    assert record["bundle"]["matches_sources"] is False
    assert any(f["code"] == "PAC-060" for f in record["findings"])


def test_evidence_is_reproducible_apart_from_the_timestamp(tmp_path):
    """Two runs on one commit must agree; that is what makes historical evidence
    a checkout away rather than a feature."""
    from fastpdlc import engine, evidence

    config = _tiny_project(tmp_path)
    engine.build(config, str(tmp_path))

    first = evidence.build_record(config, str(tmp_path))
    second = evidence.build_record(config, str(tmp_path))
    first.pop("generated_at")
    second.pop("generated_at")
    assert evidence.render(first) == evidence.render(second)


def test_cli_surface_manifest_is_current():
    """site/api/cli_surface.json is generated from argparse and consumed by the
    newsletter generator. If it drifts, the newsletter starts rejecting true
    statements about our own CLI -- so gate it the way we gate everything else.

    This is PAC-060 applied to our own tooling: regenerate with
    `python site/tools/gen_cli_surface.py` and commit the result.
    """
    import importlib.util

    repo = pathlib.Path(__file__).resolve().parents[1]
    gen = repo / "site" / "tools" / "gen_cli_surface.py"
    committed = repo / "site" / "api" / "cli_surface.json"
    if not gen.exists() or not committed.exists():
        pytest.skip("site tooling not present")

    spec = importlib.util.spec_from_file_location("gen_cli_surface", gen)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)

    expected = module.render(module.build_surface())
    actual = committed.read_text(encoding="utf-8")
    assert actual == expected, (
        "cli_surface.json is stale -- run: python site/tools/gen_cli_surface.py"
    )


# ── the agent-built lifecycle ────────────────────────────────────────────────
def _orch(**kw):
    from fastpdlc import orchestration
    return orchestration, kw


def test_pipeline_runs_the_stations_in_order():
    from fastpdlc.orchestration import Orchestrator, StubRunner

    runner = StubRunner()
    report = Orchestrator(runner).run("FEAT-refunds")

    assert report.status == "proposed"
    assert [s.station for s in report.steps] == ["ST-01", "ST-02", "ST-03", "ST-04", "ST-05"]
    # all four lenses ran, and none of them shipped an opinion it did not have
    assert [v.lens for v in report.verdicts] == [
        "correctness", "coverage", "security", "reproduce"]
    assert report.repair_rounds == 0


def test_disambiguate_blocks_before_design():
    """Building the wrong thing correctly is the expensive failure: an open question
    must stop the line before the Architect starts."""
    from fastpdlc.orchestration import Orchestrator, StubRunner

    questions = [{"id": "q1", "dimension": "refund window start",
                  "question": "From authorization, settlement or delivery?"}]
    report = Orchestrator(StubRunner(questions=questions)).run("FEAT-refunds")

    assert report.status == "blocked"
    assert report.disambiguation == questions
    stations = [s.station for s in report.steps]
    assert stations == ["ST-01", "ST-02"]          # Design never ran
    assert "ST-03" not in stations


def test_resolved_questions_let_the_line_continue():
    from fastpdlc.orchestration import Orchestrator, StubRunner

    questions = [{"id": "q1", "dimension": "refund window start", "question": "?"}]
    report = Orchestrator(
        StubRunner(questions=questions),
        resolutions={"q1": "from settlement"},
    ).run("FEAT-refunds")

    assert report.status == "proposed"
    assert "ST-03" in [s.station for s in report.steps]


def test_a_blocking_verdict_triggers_bounded_repair():
    from fastpdlc.orchestration import Orchestrator, StubRunner

    refuting = {"security": {"lens": "security", "refuted": True, "severity": "blocker",
                             "reason": "no authz on the money path",
                             "failing_case": "unauthenticated POST /refunds"}}
    report = Orchestrator(StubRunner(verdicts=refuting)).run("FEAT-refunds")

    assert report.status == "refuted"
    assert report.repair_rounds == 2                       # the bound, not forever
    assert [v.lens for v in report.blocking] == ["security"]
    assert "ST-04" in [s.station for s in report.steps]     # repair ran on the developer


def test_minor_findings_do_not_block():
    """A gate that fires on nitpicks gets bypassed, and a bypassed gate is worse
    than none."""
    from fastpdlc.orchestration import Orchestrator, StubRunner

    nitpick = {"coverage": {"lens": "coverage", "refuted": True, "severity": "minor",
                            "reason": "could add one more edge case", "failing_case": ""}}
    report = Orchestrator(StubRunner(verdicts=nitpick)).run("FEAT-refunds")

    assert report.status == "proposed"
    assert report.blocking == []
    assert report.repair_rounds == 0


def test_a_failed_lens_abstains_rather_than_blocking():
    """An unreachable critic must never take down the line."""
    from fastpdlc.orchestration import Orchestrator, Station, VERDICT_SCHEMA

    class Flaky:
        def run(self, station, prompt, schema=None):
            if schema is VERDICT_SCHEMA and '"security"' in prompt:
                raise RuntimeError("provider unreachable")
            if schema is VERDICT_SCHEMA:
                return {"lens": "x", "refuted": False, "severity": "none", "reason": "ok"}
            return {"questions": [], "approach": "a", "files": [], "criteria_to_tests": [],
                    "files_changed": [], "diff_summary": "d",
                    "tests_added": [], "tests_passed": True, "coverage_notes": "c"}

    report = Orchestrator(Flaky()).run("FEAT-refunds")
    security = next(v for v in report.verdicts if v.lens == "security")
    assert security.refuted is False
    assert "inconclusive" in security.reason
    assert report.status == "proposed"


def test_the_orchestrator_cannot_merge_anything():
    """Its terminal state is a report. Autonomy stops where the stakes rise."""
    from fastpdlc import orchestration
    from fastpdlc.orchestration import Orchestrator, StubRunner

    report = Orchestrator(StubRunner()).run("FEAT-refunds")
    assert report.status in {"proposed", "refuted", "blocked", "error"}
    # no station on the line past the gate is an agent
    for sid in ("ST-07", "ST-08", "ST-09", "ST-10"):
        assert orchestration.BY_ID[sid].kind != orchestration.AGENT
    assert orchestration.BY_ID["ST-09"].kind == orchestration.HUMAN
