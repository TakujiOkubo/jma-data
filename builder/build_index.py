#!/usr/bin/env python3
"""
build_index.py — write the site's landing stub.

The landing page stopped being a curated surface on 2026-08-23 (protocol
decision log: "the landing index retires to a stub"). It no longer scans or
lists pages: readers reach chart pages from the Substack articles that link
them, "browse my other work" is the Substack home page's job, and the JMA
Database is named as the paid privilege without a link (a public link would
land a free reader on the Cloudflare login wall). Copy approved verbatim by
Takuji, 2026-08-23.

The paid repo's build_index.py is a deliberate fork and still lists its
datasets — this stub applies to the public site only.

    python builder/build_index.py
"""

from __future__ import annotations

from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
T = dict(PAPER="#E9E7E0", INK="#2C2C2A", GREY="#888780", BLUE="#378ADD",
         FONT="DejaVu Sans, Segoe UI, system-ui, sans-serif")


def main() -> Path:
    out = REPO / "index.html"
    out.write_text(PAGE.format(**{k.lower(): v for k, v in T.items()}),
                   encoding="utf-8")
    return out


PAGE = """<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>Interactive charts — Japan Macro Advisors</title>
<style>
  *{{margin:0;padding:0;box-sizing:border-box}}
  body{{font-family:{font};background:{paper};color:{ink};line-height:1.6;
       padding:40px 20px 60px;max-width:820px;margin:0 auto}}
  .kicker{{font-size:12px;letter-spacing:.08em;text-transform:uppercase;color:{grey}}}
  h1{{font-size:30px;margin:10px 0 14px;line-height:1.2}}
  .intro{{font-size:16px;max-width:62ch;margin-bottom:18px}}
  .intro a{{color:{blue}}}
  footer{{font-size:12.5px;color:{grey};margin-top:34px;line-height:1.7}}
  footer a{{color:{blue}}}
  @media(max-width:640px){{body{{padding:24px 14px 40px}} h1{{font-size:24px}}}}
</style>
</head>
<body>
<div class="kicker">Japan Macro Advisors</div>
<h1>Interactive charts</h1>
<p class="intro">
  Interactive chart pages for my Substack articles are linked from the articles
  themselves — start at
  <a href="https://takujiokubo.substack.com">takujiokubo.substack.com</a>.
</p>
<p class="intro">
  The always-current datasets and the yield-curve model — the JMA Database —
  are a paid-subscriber privilege.
</p>
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
