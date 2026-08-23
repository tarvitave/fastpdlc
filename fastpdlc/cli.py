"""The ``fastpdlc`` command line: build | validate.

    fastpdlc build                       # regenerate the JSON bundle
    fastpdlc validate                    # schema + graph + staleness (CI gate)
    fastpdlc evidence -o build/ev.json   # content-addressed audit record
    fastpdlc -c product.config.yaml -p product_hooks.py validate

Exit code is non-zero iff validation found errors — wire ``fastpdlc validate`` into CI.
"""
from __future__ import annotations

import argparse
import pathlib
import sys

from . import engine, evidence
from .config import load_config
from .plugin import load_plugin


def _build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(prog="fastpdlc", description="Product-as-code as a validated graph.")
    p.add_argument("-c", "--config", default="product.config.yaml", help="path to product.config.yaml")
    p.add_argument("-C", "--root", default=".", help="project root (paths are resolved from here)")
    p.add_argument("-p", "--plugin", default=None, help="project plugin module or .py file")
    sub = p.add_subparsers(dest="cmd", required=True)
    sub.add_parser("build", help="regenerate the committed JSON bundle(s)")
    sub.add_parser("validate", help="schema + graph + staleness checks (CI gate)")
    ev = sub.add_parser(
        "evidence",
        help="emit a content-addressed record of what was checked, when, and on what",
    )
    ev.add_argument("-o", "--output", default=None,
                    help="write the record here instead of stdout")
    return p


def main(argv: list[str] | None = None) -> int:
    args = _build_parser().parse_args(argv)
    config = load_config(f"{args.root}/{args.config}" if args.root != "." else args.config)
    registry = load_plugin(args.plugin)

    if args.cmd == "build":
        for path in engine.build(config, args.root, registry):
            print(f"wrote {path}")
        return 0

    if args.cmd == "evidence":
        record = evidence.build_record(config, args.root, registry)
        text = evidence.render(record)
        if args.output:
            out = pathlib.Path(args.root) / args.output
            out.parent.mkdir(parents=True, exist_ok=True)
            out.write_text(text, encoding="utf-8", newline="\n")
            print(f"wrote {out}")
        else:
            sys.stdout.write(text)
        # Same gating semantics as validate: an evidence record of a failing run is
        # still worth having, but CI must not go green because you asked for one.
        return 1 if record["result"] == "fail" else 0

    report = engine.validate(config, args.root, registry)
    for w in report.warnings:
        print(f"WARN  {w.render()}")
    for e in report.errors:
        print(f"ERROR {e.render()}")
    counts = {name: len(recs) for name, recs in engine.load(config, args.root).items()}
    summary = ", ".join(f"{n} {c}" for n, c in counts.items())
    print(
        f"\nfastpdlc: {summary} — "
        f"{len(report.errors)} error(s), {len(report.warnings)} warning(s)."
    )
    return 1 if report.errors else 0


if __name__ == "__main__":
    sys.exit(main())
