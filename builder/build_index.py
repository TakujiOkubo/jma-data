#!/usr/bin/env python3
"""
build_index.py — regenerate the site's landing page from the article manifests.

Scans every ``*/panel.json`` in the repo and lists them newest-first, so the
landing page cannot drift from what is actually published. Listing is opt-in:
only pages whose manifest declares ``"unlisted": false`` appear (2026-08-23).

    python builder/build_index.py
"""

from __future__ import annotations

import html
import json
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
T = dict(PAPER="#E9E7E0", INK="#2C2C2A", GREY="#888780", BLUE="#378ADD",
         FONT="DejaVu Sans, Segoe UI, system-ui, sans-serif")


def main() -> Path:
    packs = []
    for mf in sorted(REPO.glob("*/panel.json")):
        m = json.loads(mf.read_text(encoding="utf-8"))
        # Listing is opt-in (decision 2026-08-23): a page appears on the landing
        # index only when its manifest declares "unlisted": false. An absent key
        # keeps the page off the index, so a forgotten key hides a page rather
        # than exposing it.
        if m.get("unlisted", True):
            continue
        n_charts = len(m["charts"])
        packs.append((mf.parent.name, m, n_charts))
    # Article slugs start with their date; a standing dataset does not, so it
    # carries an explicit "sort" key instead.
    packs.sort(key=lambda p: p[1].get("sort") or p[0], reverse=True)

    rows = []
    for slug, m, n in packs:
        meta = f'{html.escape(m["date"])} · {n} exhibits'
        if m.get("post_url"):
            meta += f' · <a href="{html.escape(m["post_url"])}">read the article</a>'
        rows.append(f"""<li class="pack">
  <a class="ptitle" href="{html.escape(slug)}/">{html.escape(m["title"])}</a>
  <div class="pmeta">{meta}</div>
  <p class="pdesc">{html.escape(m.get("standfirst",""))}</p>
</li>""")

    page = PAGE.format(rows="\n".join(rows) or "<li>Nothing published yet.</li>",
                       n=len(packs), plural="" if len(packs) == 1 else "s",
                       **{k.lower(): v for k, v in T.items()})
    out = REPO / "index.html"
    out.write_text(page, encoding="utf-8")
    return out


PAGE = """<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>Chart data — Japan Macro Advisors</title>
<style>
  *{{margin:0;padding:0;box-sizing:border-box}}
  body{{font-family:{font};background:{paper};color:{ink};line-height:1.6;
       padding:40px 20px 60px;max-width:820px;margin:0 auto}}
  .kicker{{font-size:12px;letter-spacing:.08em;text-transform:uppercase;color:{grey}}}
  h1{{font-size:30px;margin:10px 0 14px;line-height:1.2}}
  .intro{{font-size:16px;max-width:62ch;margin-bottom:34px}}
  .intro a{{color:{blue}}}
  ul{{list-style:none}}
  .pack{{background:#fff;border-radius:6px;padding:18px 20px;margin-bottom:16px;
        box-shadow:0 1px 4px rgba(0,0,0,.07)}}
  .ptitle{{font-size:19px;font-weight:700;color:{ink};text-decoration:none;
          line-height:1.3;display:inline-block}}
  .ptitle:hover{{color:{blue}}}
  .pmeta{{font-size:12.5px;color:{grey};margin-top:4px}}
  .pmeta a{{color:{blue}}}
  .pdesc{{font-size:14px;color:{ink};margin-top:9px;max-width:66ch}}
  footer{{font-size:12.5px;color:{grey};margin-top:34px;line-height:1.7}}
  footer a{{color:{blue}}}
  @media(max-width:640px){{body{{padding:24px 14px 40px}} h1{{font-size:24px}}}}
</style>
</head>
<body>
<div class="kicker">Japan Macro Advisors</div>
<h1>Chart data</h1>
<p class="intro">
  The data behind the charts in
  <a href="https://takujiokubo.substack.com">my Substack articles</a>, plus the
  output of the JMA JGB yield-curve model. Every chart is redrawn so you can hover
  to read values, zoom into a period, and download the underlying series as CSV.
  {n} page{plural} so far.
</p>
<ul>
{rows}
</ul>
<footer>
  Japan Macro Advisors is independent research by Takuji Okubo. Nothing here
  constitutes investment advice.<br>
  Model output (term premia, natural-rate anchor, yield forecasts) is JMA's own
  estimate — please attribute it if you use it.<br>
  <a href="https://takujiokubo.substack.com">takujiokubo.substack.com</a>
</footer>
</body>
</html>
"""

if __name__ == "__main__":
    print(f"wrote {main()}")
