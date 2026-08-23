"""Rebuild the homepage around the agent-built lifecycle.

Three changes, all of them repositioning rather than decoration:

1. The hero rail becomes the ST-01..ST-10 roster instead of the PAC codes. The
   codes are still the product, but they are ST-08 -- one station, not the story.
2. The hero copy says what the thing is now: versioned intent, a workforce that
   builds against it, and a deterministic judge.
3. A new section for ST-06's four refuting lenses, which is the most persuasive
   idea in the model and had no home on the site at all.

Run from site/:  python tools/rebuild_home.py
"""
from __future__ import annotations

import pathlib
import sys

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))
from stations import LENSES, rail_cards  # noqa: E402

HOME = pathlib.Path(__file__).resolve().parent.parent / "public" / "index.html"


def _between(text: str, start: str, end: str) -> str:
    a = text.index(start)
    b = text.index(end, a)
    return text[a:b + len(end)]


LENS_SECTION = """
<!-- ══ the four refuting lenses ═══════════════════════════════════════════ -->
<section class="section band-cream" id="lenses">
  <div class="wrap">
    <div class="section-head reveal">
      <span class="eyebrow">ST-06 &middot; Verify</span>
      <h2>Four critics, each trying to refute the work.</h2>
      <p class="lede">The agent that builds a change does not get to grade it. A separate
        station attacks the result through four independent lenses, on a different provider
        &mdash; so the critic cannot share the builder's blind spots. Diversity is a
        correctness lever, not a nicety.</p>
    </div>

    <div class="lenses">
      %s
    </div>

    <div class="proof-note reveal" style="margin-top:2rem">
      <span class="badge">The principle</span>
      <p>Provenance is not correctness. Knowing which agent wrote a line tells you nothing
        about whether the line is right &mdash; so <strong>correctness is stacked on top, in
        depth</strong>: an adversarial test station, four refuting lenses, then a deterministic
        gate, then a human.</p>
    </div>
  </div>
</section>
"""


def lens_cards() -> str:
    """Each critic gets a face, seeded differently so four agents do not read as one
    agent copied four times. These are ST-06 stations, so the face is accurate here
    rather than decorative — and this was the one place on the page with agents and
    no faces."""
    from stations import _face

    out = []
    for i, (name, colour, question) in enumerate(LENSES):
        out.append(f"""<article class="lens reveal" style="--c:{colour}">
        <div class="lens-head">{_face(colour, i + 2)}<h3>{name}</h3></div>
        <p>{question}</p>
        <span class="badge">agent critic</span>
      </article>""")
    return "\n      ".join(out)


def main() -> int:
    html = HOME.read_text(encoding="utf-8")

    # ── 1. hero rail: PAC chips -> station roster ────────────────────────────
    old_rail = _between(html, '<div class="rail" aria-hidden="true">', "</div>\n  </div>")
    new_rail = ('<div class="rail" aria-hidden="true">\n    '
                '<div class="rail-track" id="railTrack">\n      '
                + rail_cards()
                + "\n    </div>\n  </div>")
    html = html.replace(old_rail, new_rail, 1)

    # ── 2. hero copy ────────────────────────────────────────────────────────
    html = html.replace(
        "<h1>Product and code, behind <span class=\"hl\">one gate.</span></h1>",
        "<h1>A workforce builds it. A <span class=\"hl\">gate judges it.</span></h1>")

    old_sub_start = '      <p class="lede hero-sub">'
    old_sub = _between(html, old_sub_start, "</p>")
    new_sub = """      <p class="lede hero-sub">
        Product intent lives as <strong>versioned source</strong>. A team of agents builds
        against it. Then a deterministic gate judges the result &mdash; the same
        <code style="font-family:var(--mono)">PAC-NNN</code> rubric on every pull request,
        including an agent's own. Agents propose, gates enforce, a human merges.
      </p>"""
    html = html.replace(old_sub, new_sub, 1)

    html = html.replace("> One gate for product and code</span>",
                        "> Agents never auto-merge</span>")
    html = html.replace("> Any language, any repo</span>",
                        "> Deterministic judge, always</span>")

    # ── 3. lenses section, before the timeline ──────────────────────────────
    anchor = '<!-- ══ timeline ═══'
    if "id=\"lenses\"" not in html:
        html = html.replace(anchor, (LENS_SECTION % lens_cards()) + "\n" + anchor, 1)

    # ── 4. nav ──────────────────────────────────────────────────────────────
    html = html.replace('      <a href="/lifecycle.html">Lifecycle</a>\n',
                        '      <a href="/lifecycle.html">Lifecycle</a>\n      <a href="#lenses">Lenses</a>\n', 1)

    HOME.write_text(html, encoding="utf-8", newline="\n")
    print(f"rebuilt {HOME.name}")
    print(f"  rail       : 10 stations")
    print(f"  lenses     : {len(LENSES)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
