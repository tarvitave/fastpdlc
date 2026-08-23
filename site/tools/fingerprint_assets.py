"""Content-fingerprint the CSS and JS links so a deploy is visible immediately.

The Caddyfile caches assets for an hour, which is right for performance and wrong
for correctness: after a deploy, returning visitors keep the old stylesheet until
the TTL expires. That is how a rebuilt homepage can render with the previous CSS
and look broken to everyone except whoever hard-refreshed.

Appending a hash of the file's own contents fixes it without shortening the TTL:
the URL changes exactly when the bytes change, so caches are bypassed when they
must be and used when they can be.

Run last, after every renderer:  python tools/fingerprint_assets.py
"""
from __future__ import annotations

import hashlib
import pathlib
import re

PUBLIC = pathlib.Path(__file__).resolve().parent.parent / "public"
ASSETS = ["styles.css", "blog.css", "main.js"]


def digest(path: pathlib.Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()[:10]


def main() -> int:
    versions = {}
    for name in ASSETS:
        path = PUBLIC / name
        if path.exists():
            versions[name] = digest(path)
        else:
            print(f"  skip {name} (missing)")

    changed = 0
    for page in sorted(PUBLIC.rglob("*.html")):
        text = original = page.read_text(encoding="utf-8")
        for name, ver in versions.items():
            # matches /name and /name?v=old, in href= or src=
            text = re.sub(
                rf'(["\'])/{re.escape(name)}(\?v=[0-9a-f]+)?\1',
                rf'\g<1>/{name}?v={ver}\g<1>',
                text,
            )
        if text != original:
            page.write_text(text, encoding="utf-8", newline="\n")
            changed += 1

    for name, ver in versions.items():
        print(f"  {name:12} v={ver}")
    print(f"  rewrote {changed} page(s)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
