"""Tests for the FastPDLC engine: schema/id/reference/enum/staleness + the plugin API."""
from __future__ import annotations

import json
import pathlib
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
