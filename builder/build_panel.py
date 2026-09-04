#!/usr/bin/env python3
"""
build_panel.py — build the interactive companion panel for one article.

STATUS: PROTOTYPE (Takuji's ruling, 2026-07-29). This works and its output is
published, but how JMA distributes subscriber data is being reconsidered from
first principles. Hosting, the public repo, free-versus-gated and the
per-article unit are all provisional. The durable findings live in
`40.Projects/Substack/sessions/S04-2026-07-29.md` in the vault.

The original ruling also said not to extend the pattern to new articles before
that question was settled. Takuji lifted that on 2026-07-31, instructing a
panel for the FX carry-unwind note (`2026-07-31-fx-carry-unwind`, public
teaser). The distribution question itself is still open — a third panel is
still a decision, not a default.

The panel is the web-viewable twin of the XLSX data pack that ships below the
Substack paywall. Same input (the chart library's tidy ``*_data.csv`` files, in
article order), second output: one self-contained static page of interactive
Plotly charts, published to GitHub Pages.

    python builder/build_panel.py 2026-07-20-long-climb

Reads   <slug>/panel.json  (the manifest — see MANIFEST below)
        <slug>/data/*.csv  (copies of the chart library's tidy data files)
Writes  <slug>/index.html

WHY A MANIFEST. The data CSV carries numbers and nothing else. It cannot tell
you that chart 2 is windowed from 2017-12-31 though the file starts in 2000,
that chart 4 is year-end-sampled bars rather than a monthly line, that
``provisional`` is a flag column and not a series, or that ``tp_10y_bp`` should
be labelled "JMA model" in a legend. Those live in the chart scripts, which are
prose-and-matplotlib and not safely importable. So the manifest states them
once per article, seeded by hand from each script's TITLE / SOURCE / YLABEL
constants and checked against the published PNG.

HOUSE STYLE. Frame tokens come from the chart library's ``jma_plotly_style.py``
— the single source of truth for interactive charts — so a theme change there
reaches these panels on the next build. Titles, subtitles and source notes are
rendered as HTML rather than inside the figure, which matches the house PNG
(bold, left, above the plot) and keeps them crisp on a phone.

MANIFEST (panel.json)
    slug, title, date, post_url, standfirst, workbook (optional filename)
    downloads  true | false — does the page offer its data? Optional; defaults
            to (tier != "free"), the behaviour before the key existed.
    tier    "free" | "paid" — what the page says about subscribing. Required on
            every page built from 2026-08-05; omitted only on pre-rule pages.
    audience  "free" | "paid" — who the page is for. Inert: recorded so the set
            of paid pages is queryable, never read by this builder.
            See "WHAT A PAGE OFFERS" below for how downloads and tier interact.
    charts: [ {n, kind, title, subtitle, ylabel, source, csv, ...} ]

    kind "line"     x, start, end, series[{col,label,color,dash,connect_gaps,
                    hollow_col,hover_col}], hlines[{y,label}], vlines[{x,label}],
                    decimals, markers, marker_size, yrange, xrange
    kind "line_bars"
                    two stacked panels on ONE shared x-axis: the "line" kind's
                    series above, a bar series below, each with its own y-axis.
                    x, start, end, series[], split_col/solid_value,
                    bars{col,label,color,proj_color}, row_heights[2], row_gap,
                    yrange/ytick + ylabel (top), y2range/y2tick + ylabel2
                    (bottom), hlines[{y,label}], vlines[{x,label}], decimals
    kind "bar_line" x, resample ("year_end"), bars[{col,label,color}],
                    line{col,label,color} (optional), flag_col, flag_note,
                    hlines[{y,label}], decimals
    kind "ranked_bars"
                    label_col, year_col, top_n,
                    panels[{col,header,color,decimals,thousands,prefix,suffix}]
    kind "signed_bar_line"
                    year_col, q_col, value{col,pos_label,neg_label,
                    pos_color,neg_color}, flag_col, line{col,label,color},
                    yrange/ytick, y2range/y2tick, hlines2[{y,label}]
    kind "xy_map"   a map: one marker per entity on two scored dimensions, with
                    a date slider. frame_col, label_col, detail_col, dim_col,
                    value_col, x_dim, y_dim, extra_dims[], group_col, stale_col,
                    note_col, source_col, groups[{key,label,color,glyph}],
                    hollow_label, range[2], ticks[], neutral, xlabel/ylabel,
                    crosshair_notes[{x,y,text,xanchor,yanchor}], key_at[x,y,step],
                    slider_prefix, frame_labels{}, marker_size, dodge_within,
                    decimals. Long CSV: one row per frame x entity x dimension.

    kind "table"    columns[{col,label}], row_label_col, rule_after_col/value,
                    focal_col/focal_value (the row the headline is about, set
                    coral), strong_col/strong_value (the total row). Each must
                    match exactly one row or the build stops.
"""

from __future__ import annotations

import csv
import html
import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parent

# The footer nav's "All data packs" link points at the landing index. On the
# public site that index is a stub (2026-08-23), so the link leads nowhere
# useful and Takuji ruled it deleted (2026-08-24), keeping the Substack link.
# On the gated site the index is the JMA Database landing and the link stays.
# Same guard pattern as qa_panel's PUBLIC_REPO; this file is synced between
# the repos, so the branch must live in the code, not in a fork.
PUBLIC_REPO = REPO.name == "jma-data"
FOOTER_NAV = (
    '<p class="nav"><a href="https://takujiokubo.substack.com">'
    "takujiokubo.substack.com</a></p>"
    if PUBLIC_REPO else
    '<p class="nav"><a href="../">All data packs</a> ·\n'
    '  <a href="https://takujiokubo.substack.com">takujiokubo.substack.com</a></p>'
)

# The chart library on Drive owns the interactive house tokens. Build-time only —
# the published page is static and carries the resolved values inline.
CHARTS_ROOT = Path(r"G:\My Drive\charts")

PLOTLY_CDN = "https://cdn.plot.ly/plotly-3.0.1.min.js"

# ------------------------------------------------------------ fixed page blocks
# The page identity comes from WEB_REPORT_GUIDE.md §Page style tokens and the
# live template `JMA Web Report Template.dc.html` — warm-white page, 680px text
# column, 880px figure breakouts, PT Serif / Public Sans, masthead with the ink
# rule and tagline, and the template's disclaimer wording verbatim. The banner
# texts are fixed by decision (work order model-page-v2, 2026-07-30) and are
# IDENTICAL on every panel page. Edit these only by decision, never per page.
TOP_BANNER = ("The charts and data on this page are free to use and reproduce "
              "with attribution to Japan Macro Advisors.")
BOTTOM_BANNER = ("The charts and data on this page are free to use and "
                 "reproduce with attribution to Japan Macro Advisors. Paid "
                 "subscribers have access to our Yield Curve Model estimate "
                 "output, including historical term premia decomposition "
                 "estimates as well as our forecasts that are periodically "
                 "updated. Paid subscribers are encouraged to send questions "
                 "on my research and receive priority in my replies in "
                 "either English or Japanese.")
SUBSCRIBE_URL = "https://takujiokubo.substack.com/subscribe"

# WHAT A PAGE OFFERS. Two independent manifest keys, and they were one until
# 2026-08-12. Neither says who the page is for -- that is "audience", which this
# builder deliberately ignores, and the policy behind it is Takuji's, recorded in
# 40.Projects\Substack\_publication-protocol.md. Nothing about a page's subject
# matter follows from either key.
#
# "downloads" (bool, optional) -- does the page OFFER its data?
#            true  : per-card "Download CSV" links, the workbook button if a
#                    "workbook" is declared, and the closing line that says so.
#            false : none of those. The tidy CSVs stay in the page's data/ folder
#                    as build inputs and as the workbook's provenance, and the
#                    numbers are in the figure JSON either way -- this governs
#                    what is offered, not what is reachable.
#            absent: defaults to (tier != "free"), which is exactly the behaviour
#                    before this key existed, so every page already built rebuilds
#                    byte-identical.
#
# "tier" ("free" | "paid" | absent) -- what the page SAYS about subscribing.
#            "free" pages carry the perk block naming what a subscription buys,
#            above the Subscribe button. Retained under its old name because
#            renaming it would move bytes on every page already live.
#            absent = built before 2026-08-05; forward-only by decision, so do
#            not retrofit "tier" onto those pages.
#
# The perk block is suppressed when downloads are on, whatever the tier: a page
# that hands out its data cannot also advertise that data as the thing a
# subscription buys. Takuji reserved the free-page-with-downloads case as a
# per-page exception on 2026-08-11; this is what makes it expressible without
# omitting "tier" and thereby recording a new page as pre-rule.
# The perk sentence names what a subscription buys, above the Subscribe button
# on a free page. Rewritten 2026-08-20 (Takuji): it had promised "the data behind
# every chart as an Excel workbook, plus access to our JGB yield-curve model
# pages", written before the gated site existed. The paid offer is now the JMA
# Database at jma-data-paid.pages.dev, and he describes it to subscribers by
# naming the three datasets, so the page now says what his email says. The
# workbook is no longer named: it is still produced per report, but it is no
# longer the headline of what a subscription buys.
#
# Two lines at the 680px text column is the constraint he set — about 180
# characters, and this is 178. Measured in the rendered page, not estimated. It
# wraps further on a phone, as the sentence it replaces also did.
#
# This is a fixed block: changing it changes every free page carrying it, which
# is the point — one claim across the site, as with the exclusivity sentence
# retired on 2026-08-13.
#
# Restyled 2026-08-23 (Takuji, second round the same morning): first to a brand-blue
# accent card, then — his "not prominent enough" — to the headline-card form he
# picked from three louder rendered variants: full blue border, the lead clause
# promoted to a PT Serif headline on its own line (the colon becomes the line
# break; no word changed), body sentence below, larger button. qa_panel gates on
# class="perk" and on the sentence opening as plain text, so the body paragraph
# keeps its class and the headline carries the whole marker substring unsplit.
PERK_HTML = (
    '<div class="perkbox">\n'
    '  <h3>Paid subscribers get the JMA Database</h3>\n'
    '  <p class="perk">The proprietary estimates behind my research — the '
    "BoJ-QT progress monitor, the JGB yield-curve model, and global FX "
    "reserves back to 1980.</p>\n"
    f'  <a class="btn" href="{SUBSCRIBE_URL}">Subscribe</a>\n'
    '  </div>')
DISCLAIMER_HTML = ("This report is provided for information purposes only. It "
                   "does not constitute investment advice or an offer or "
                   "solicitation to buy or sell any security. While the "
                   "information herein is believed to be reliable, Japan Macro "
                   "Advisors makes no representation as to its accuracy or "
                   "completeness. &copy; 2026 Japan Macro Advisors. "
                   "All rights reserved.")


# ---------------------------------------------------------------- house tokens
def load_house_tokens() -> dict:
    """Read the palette from the chart library, or fall back to the same values.

    The fallback is not a second source of truth — it is a copy so the builder
    still runs on a machine without the Drive library mounted. If they ever
    disagree, the library wins; that is what the assertion below is for.
    """
    fallback = dict(
        BLUE="#378ADD", CORAL="#D85A30", FADED_BLUE="#A8CEEE",
        AMBER="#EF9F27", GREY="#888780", INK="#2C2C2A",
        PAPER="#E9E7E0", GRID="#FFFFFF",
        FONT_FAMILY="DejaVu Sans, Segoe UI, system-ui, sans-serif",
    )
    style_path = CHARTS_ROOT / "jma_plotly_style.py"
    if not style_path.exists():
        print(f"  ! {style_path} not found — using the vendored copy of the palette")
        return fallback

    sys.path.insert(0, str(CHARTS_ROOT))
    try:
        import jma_plotly_style as s  # noqa: E402
    finally:
        sys.path.pop(0)

    live = {k: getattr(s, k) for k in fallback if hasattr(s, k)}
    drift = {k: (fallback[k], live[k]) for k in live if fallback[k] != live[k]}
    if drift:
        print(f"  house palette changed in the library, adopting: {drift}")
    return {**fallback, **live}


# ------------------------------------------------------------------- csv input
def read_csv(path: Path) -> list[dict]:
    with open(path, newline="", encoding="utf-8-sig") as f:
        return list(csv.DictReader(f))


def to_float(v):
    """Empty string, whitespace and 'nan' all become None so Plotly leaves a gap.

    Never fall back to 0.0 — chart 1's 40Y column is empty for its first twenty
    years, and a zero there would draw a line along the axis that reads as a
    real yield.
    """
    if v is None:
        return None
    v = v.strip()
    if v == "" or v.lower() in ("nan", "na", "null", "none"):
        return None
    try:
        return float(v)
    except ValueError:
        return None


def x_iso(raw: str) -> str:
    """Normalise the x value to an ISO date Plotly can place on a time axis.

    The library uses two conventions: 'YYYY-MM-DD' for daily series and
    'YYYY-MM' for monthly ones. A bare 'YYYY-MM' is anchored to the first of
    the month; these are month-end observations, but the axis spans decades and
    the day-of-month is not readable at that scale.
    """
    raw = raw.strip()
    # Only a true 'YYYY-MM' gets the day anchor. Length alone is not enough: a
    # 7-character categorical x like "Germany" was becoming "Germany-01"
    # (defect found 2026-08-21 on the Canada page's Chart 1).
    is_year_month = (len(raw) == 7 and raw[:4].isdigit()
                     and raw[4] == "-" and raw[5:].isdigit())
    return f"{raw}-01" if is_year_month else raw


def in_window(raw: str, start: str | None, end: str | None) -> bool:
    """Window on the raw string. ISO dates sort lexically, and comparing
    'YYYY-MM' against a 'YYYY-MM-DD' bound works on the shared prefix."""
    v = raw.strip()
    if start and v < start[: len(v)]:
        return False
    if end and v > end[: len(v)]:
        return False
    return True


# ------------------------------------------------------------ figure assembly
def apply_hlines(spec: dict, layout: dict, T: dict) -> None:
    """Reference lines and their right-margin labels, added in place.

    Shared by fig_line and fig_bar_line rather than written twice. A reference
    line is the chart's argument, not decor — the Long Climb's 4% mark, the 2%
    target on the inflation-expectations bars — so the two kinds have to place
    and label it identically, and a copied block is where that stops being true.

    Extends rather than assigns: both callers may already have put a shape on
    the layout (the history/projection boundary marker in fig_line, the zero
    baseline in fig_bar_line), and a chart setting both would otherwise lose it.
    """
    shapes, annos = [], []
    for h in spec.get("hlines", []):
        shapes.append(dict(
            type="line", xref="paper", x0=0, x1=1, yref="y",
            y0=h["y"], y1=h["y"],
            line=dict(color=T["GREY"], width=1.4, dash="dash"), layer="below",
        ))
        if not h.get("label"):
            continue
        # "inside" sets the label just above the line at the left, where the
        # published consolidated-maturity chart puts it, instead of in the right
        # margin. A sentence-length label ("Pre-QQE consolidated level, 6.4y
        # (Mar 2013)") margined to fit would have taken 300px off a 1180px
        # frame — a quarter of the plot spent on the caption for one line.
        if h.get("label_pos") == "inside":
            annos.append(dict(
                xref="paper", x=0.02, yref="y", y=h["y"], text=h["label"],
                showarrow=False, xanchor="left", yanchor="bottom",
                font=dict(size=11, color=T["GREY"]), yshift=3,
            ))
        else:
            annos.append(dict(
                xref="paper", x=1, yref="y", y=h["y"], text=h["label"],
                showarrow=False, xanchor="left", yanchor="middle",
                font=dict(size=11, color=T["GREY"]), xshift=6,
            ))
    if shapes:
        layout["shapes"] = layout.get("shapes", []) + shapes
    if annos:
        layout["annotations"] = layout.get("annotations", []) + annos
        # A margined hline label sits in the right margin. The default 60px holds
        # a short one ("4%") but clipped "Terminal 1.50%" to "Terminal", so the
        # margin is sized to the longest label rather than left at a width
        # that happens to fit the labels used so far. Labels placed inside the
        # frame are excluded — they need no margin, and counting them would
        # reintroduce exactly the waste "inside" exists to avoid.
        margined = [h["label"] for h in spec["hlines"]
                    if h.get("label") and h.get("label_pos") != "inside"]
        if margined:
            layout["margin"]["r"] = max(layout["margin"]["r"],
                                        18 + int(max(map(len, margined)) * 6.6))


def x_ref(xs: list[str], i: int, cat: bool):
    """Where a shape or annotation on the x-axis must be anchored.

    On a date axis that is the x value itself. On a CATEGORY axis it must be the
    category's index: Plotly coerces a numeric-looking category value to a
    number, so a forecast boundary written as "2025" is placed at category slot
    2025 and stretches the axis to 2025 slots, squeezing fourteen fiscal years
    into the leftmost half per cent of the frame. Every numeric gate passes on
    that page -- the figure JSON is correct and only the drawing is wrong, which
    is why it was found by rendering it and looking.
    """
    return i if cat else xs[i]


def apply_vlines(spec: dict, layout: dict, T: dict, xs: list[str],
                 cat: bool = False) -> None:
    """Episode markers — a dotted vertical and a label at the top of the frame.

    The consolidated-maturity chart's CME / QQE / YCC / Exit marks are what let a
    reader attribute the fall and the recovery to the policy that caused them;
    without them the chart is two lines that happen to move. Written as a shared
    helper for the same reason apply_hlines is one.

    The x value is matched against the axis values actually plotted rather than
    passed through to Plotly raw: a marker for a month the page does not cover
    would otherwise be placed silently outside the frame, and the miss would look
    exactly like a chart that never declared it. A bare "YYYY-MM" resolves to
    whatever day of that month the series carries — these are month-end
    observations and the episode is the month, not the day. Extends, never
    assigns.
    """
    vl = spec.get("vlines", [])
    if not vl:
        return
    shapes, annos = [], []
    for v in vl:
        raw = str(v["x"]).strip()
        hits = [x for x in xs if x == raw or x.startswith(f"{raw}-")]
        if len(hits) != 1:
            raise SystemExit(
                f'panel.json: vline x={raw!r} matched {len(hits)} points on this '
                f"chart's axis ({xs[0]}..{xs[-1]}). Every marker must land on "
                "exactly one plotted point.")
        x = x_ref(xs, xs.index(hits[0]), cat)
        shapes.append(dict(
            type="line", xref="x", x0=x, x1=x, yref="paper", y0=0, y1=1,
            line=dict(color=T["GREY"], width=0.9, dash="dot"), layer="below",
        ))
        if v.get("label"):
            annos.append(dict(
                xref="x", x=x, yref="paper", y=1.0, yanchor="bottom",
                text=v["label"], showarrow=False, xanchor="center",
                font=dict(size=11, color=T["GREY"]),
            ))
    layout["shapes"] = layout.get("shapes", []) + shapes
    if annos:
        layout["annotations"] = layout.get("annotations", []) + annos
        # The labels sit above the plot area; give them the room the default
        # 16px top margin does not have, or they render clipped at the frame.
        layout["margin"]["t"] = max(layout["margin"]["t"], 34)


def series_traces(spec: dict, kept: list[dict], xs: list[str], T: dict,
                  dec: int, is_solid, boundary, yaxis: str | None = None) -> list:
    """The line traces for one panel — shared by "line" and "line_bars".

    Factored rather than copied: the two kinds must split history from
    projection identically, and a copied block is where that stops being true
    (apply_hlines carries the same warning). ``yaxis`` is emitted only when the
    caller passes one, so a single-panel chart's figure JSON is unchanged.

    ``connect_gaps`` is per series and defaults off. A gap is normally missing
    data and bridging it would invent an observation — but where a series is
    simply reported less often than the chart's grid (the UK publishes debt
    maturity quarterly against four monthly neighbours) every intermediate row
    is blank, and left unbridged the line renders as isolated invisible points.
    Declaring it per series rather than per chart keeps that judgement attached
    to the series whose frequency it describes.
    """
    traces = []
    for s in spec["series"]:
        ys = [to_float(r.get(s["col"])) for r in kept]
        ys = [None if y is None else round(y, dec) for y in ys]
        colour = s.get("color", T["BLUE"])
        line = dict(color=colour, width=s.get("width", 2))
        if s.get("dash"):
            line["dash"] = s["dash"]
        bridge = bool(s.get("connect_gaps", False))
        ax = dict(yaxis=yaxis) if yaxis else {}

        # Three opt-in decorations, added 2026-09-03 for a family of
        # per-entity score charts. Each is emitted ONLY where the manifest
        # declares it, and the
        # emitted keys are appended after the existing ones, so every chart
        # built before they existed rebuilds byte-identical.
        #
        #   markers      the series is a run of discrete readings, not a
        #                continuous measurement — each scored event is a point
        #   hollow_col   per point, not per series: a score still read from a
        #                Summary of Opinions with the minutes not yet published
        #                is drawn hollow, and one dimension can be provisional
        #                while its neighbours on the same date are settled
        #   hover_col    a per-point string appended to the hover readout. For
        #                the score charts it names the document the score was read
        #                from, which is also how a value carried forward from an
        #                earlier reading shows itself: its source is older than
        #                the point's own date
        mode, extra = "lines", {}
        if spec.get("markers"):
            mode = "lines+markers"
            # Per-series size, for the one case where a chart is short enough
            # that two series can sit on the same value with no line to tell
            # them apart: Plotly draws in manifest order, so the later series
            # hides the earlier one and a score the page claims to show is
            # simply not on it. Declaring descending sizes nests the markers
            # instead. Chart-level default otherwise, so nothing else moves.
            marker = dict(size=s.get("marker_size", spec.get("marker_size", 7)),
                          color=colour, line=dict(color=colour, width=2))
            if s.get("hollow_col"):
                blank = ("", "0", "no", "false")
                marker["color"] = [
                    T["PAPER"]
                    if str(r.get(s["hollow_col"], "")).strip().lower() not in blank
                    else colour
                    for r in kept]
            extra["marker"] = marker
        hov = f"%{{y:.{dec}f}}<extra>{s['label']}</extra>"
        if s.get("hover_col"):
            extra["customdata"] = [(r.get(s["hover_col"]) or "").strip()
                                   for r in kept]
            hov = (f"%{{y:.{dec}f}}  <span style=\"color:{T['GREY']}\">"
                   f"%{{customdata}}</span><extra>{s['label']}</extra>")

        if is_solid is None:
            traces.append(dict(
                type="scatter", mode=mode, name=s["label"],
                x=xs, y=ys, line=line, connectgaps=bridge,
                hovertemplate=hov,
                **ax, **extra,
            ))
            continue

        hist = [y if is_solid[i] else None for i, y in enumerate(ys)]
        # the projection leg keeps the last observed point so the two legs join
        proj = [y if (not is_solid[i] or i == boundary) else None
                for i, y in enumerate(ys)]
        # The observed leg takes the decorations; the dotted projection leg
        # stays a bare line, because a marker on a projection reads as an
        # observation and the whole point of the split is that it cannot.
        traces.append(dict(
            type="scatter", mode=mode, name=s["label"], x=xs, y=hist,
            line=line, connectgaps=bridge,
            hovertemplate=hov,
            **ax, **extra,
        ))
        traces.append(dict(
            type="scatter", mode="lines", name=s["label"], x=xs, y=proj,
            line=dict(color=colour, width=s.get("width", 2), dash="dot"),
            connectgaps=bridge, showlegend=False,
            hovertemplate=f"%{{y:.{dec}f}}<extra>{s['label']} (forecast)</extra>",
            **ax,
        ))
    return traces


def fig_line(spec: dict, rows: list[dict], T: dict) -> dict:
    xcol = spec.get("x", "date")
    start, end = spec.get("start"), spec.get("end")
    dec = spec.get("decimals", 3)

    kept = [r for r in rows if in_window(r[xcol], start, end)]
    xs = [x_iso(r[xcol]) for r in kept]

    # Optional history/projection split. When set, each series is drawn twice —
    # solid over the rows whose split_col equals solid_value, dashed over the
    # rest — so a reader can never mistake a projection for an observation.
    split_col = spec.get("split_col")
    solid_val = spec.get("solid_value", "actual")
    if split_col:
        is_solid = [str(r.get(split_col, "")).strip() == solid_val for r in kept]
        boundary = max((i for i, s in enumerate(is_solid) if s), default=None)
    else:
        is_solid, boundary = None, None

    traces = []

    # Optional uncertainty band, appended before the series so the lines draw
    # on top of it. Two traces: an invisible upper edge, then the lower edge
    # filled up to it. The band columns are blank over history, so the fill
    # covers the forecast only; connectgaps stays off so a gap is never bridged
    # and the band can never appear over a period it was not computed for.
    band = spec.get("band")
    if band:
        edges = {}
        for side in ("hi", "lo"):
            vals = [to_float(r.get(band[side])) for r in kept]
            edges[side] = [None if v is None else round(v, dec) for v in vals]
        blabel = band.get("label", "Uncertainty band")
        traces.append(dict(
            type="scatter", mode="lines", name=blabel, x=xs, y=edges["hi"],
            line=dict(width=0, color="rgba(0,0,0,0)"), showlegend=False,
            hoverinfo="skip", connectgaps=False,
        ))
        traces.append(dict(
            type="scatter", mode="lines", name=blabel, x=xs, y=edges["lo"],
            line=dict(width=0, color="rgba(0,0,0,0)"), fill="tonexty",
            fillcolor=band.get("fillcolor", "rgba(55,138,221,0.14)"),
            showlegend=True, hoverinfo="skip", connectgaps=False,
        ))

    traces += series_traces(spec, kept, xs, T, dec, is_solid, boundary)

    layout = base_layout(
        spec, T, legend=len(spec["series"]) > 1 or bool(spec.get("band")))

    if boundary is not None and boundary + 1 < len(xs):
        layout.setdefault("shapes", []).append(dict(
            type="line", xref="x", x0=xs[boundary], x1=xs[boundary],
            yref="paper", y0=0, y1=1,
            line=dict(color=T["GREY"], width=1.1, dash="dot"), layer="below"))
        layout.setdefault("annotations", []).append(dict(
            xref="x", x=xs[boundary], yref="paper", y=1.0, yanchor="bottom",
            text="forecast →", showarrow=False, xanchor="left", xshift=4,
            font=dict(size=11, color=T["GREY"])))

    # Reference lines (chart 1's 4% mark is the chart's whole argument, not decor)
    apply_hlines(spec, layout, T)
    apply_vlines(spec, layout, T, xs)
    if spec.get("yrange"):
        layout["yaxis"]["range"] = spec["yrange"]
    # A stated x window, for a run of charts a reader compares against each
    # other. Autoscale gives each its own span, so a member with one reading
    # fills the frame and a member whose series ends early does not visibly end
    # early. Opt-in, emitted only where declared.
    if spec.get("xrange"):
        layout["xaxis"]["range"] = spec["xrange"]

    return dict(data=traces, layout=layout)


def fig_line_bars(spec: dict, rows: list[dict], T: dict) -> dict:
    """Two stacked panels on one shared x-axis — the effective-rate chart's
    published form: rates above, the interest bill in yen below.

    Not expressible as "bar_line", which puts its bars and its line on the same
    y-axis: these two panels carry different quantities in different units (per
    cent and trillions of yen) and the published exhibit stacks them precisely so
    a reader can read up from a bar to the rate that produced it. One x-axis,
    drawn once at the bottom, is what keeps that reading honest — two separate
    cards with independently autoscaled x-ranges would not.

    The panels are laid out by hand rather than through plotly.subplots because
    the builder emits figure JSON directly and never imports plotly; the domains
    below are what make_subplots(row_heights=..., vertical_spacing=...) computes.
    """
    xcol = spec.get("x", "date")
    start, end = spec.get("start"), spec.get("end")
    dec = spec.get("decimals", 2)

    kept = [r for r in rows if in_window(str(r[xcol]), start, end)]
    xs = [x_iso(str(r[xcol])) for r in kept]

    split_col = spec.get("split_col")
    solid_val = spec.get("solid_value", "actual")
    if split_col:
        is_solid = [str(r.get(split_col, "")).strip() == solid_val for r in kept]
        boundary = max((i for i, s in enumerate(is_solid) if s), default=None)
    else:
        is_solid, boundary = None, None

    # ── top panel: the lines, on y ──
    traces = series_traces(spec, kept, xs, T, dec, is_solid, boundary)

    # ── bottom panel: the bars, on y2 ──
    b = spec["bars"]
    ys = [to_float(r.get(b["col"])) for r in kept]
    ys = [None if y is None else round(y, dec) for y in ys]
    solid_c = b.get("color", T["BLUE"])
    # The projection bars are drawn in the pale tint, as the published PNG does —
    # the same statement the dotted leg makes on the lines above, in the encoding
    # a bar has. With no split declared every bar is an observation.
    proj_c = b.get("proj_color", T["FADED_BLUE"])
    marker = dict(color=solid_c if is_solid is None else
                  [solid_c if s else proj_c for s in is_solid])
    traces.append(dict(
        type="bar", name=b["label"], x=xs, y=ys, marker=marker, yaxis="y2",
        hovertemplate=f"%{{y:.{dec}f}}<extra>{b['label']}</extra>",
    ))

    rh = spec.get("row_heights", [0.6, 0.4])
    gap = spec.get("row_gap", 0.06)
    h_top, h_bot = (1 - gap) * rh[0], (1 - gap) * rh[1]

    layout = base_layout(spec, T, legend=True)
    # One x-axis for both panels, anchored to the lower one so it is drawn once,
    # under the bars. Both panels' traces map to it.
    layout["xaxis"]["anchor"] = "y2"
    layout["xaxis"]["domain"] = [0, 1]
    # Category by default: this kind's x is typically a fiscal year ("2026"),
    # which a time axis would silently read as a calendar date, and the bars in
    # the lower panel want even spacing whatever the labels are.
    layout["xaxis"]["type"] = spec.get("xtype", "category")
    layout["yaxis"]["domain"] = [round(1 - h_top, 4), 1]
    layout["yaxis2"] = dict(
        domain=[0, round(h_bot, 4)], anchor="x",
        showgrid=True, gridcolor=T["GRID"], gridwidth=1.4,
        zeroline=False, showline=False, ticks="",
        tickfont=dict(size=18, color=T["GREY"]),
        title=dict(text=spec.get("ylabel2") or "",
                   font=dict(size=18, color=T["GREY"])),
    )
    for key, axis in (("yrange", "yaxis"), ("y2range", "yaxis2")):
        if spec.get(key):
            layout[axis]["range"] = spec[key]
    for key, axis in (("ytick", "yaxis"), ("y2tick", "yaxis2")):
        if spec.get(key):
            layout[axis]["tickmode"] = "array"
            layout[axis]["tickvals"] = spec[key]

    cat = layout["xaxis"]["type"] == "category"
    if boundary is not None and boundary + 1 < len(xs):
        # The boundary rule spans BOTH panels — yref "paper", so it runs the full
        # height of the frame rather than stopping at the top panel's floor.
        bx = x_ref(xs, boundary, cat)
        layout.setdefault("shapes", []).append(dict(
            type="line", xref="x", x0=bx, x1=bx,
            yref="paper", y0=0, y1=1,
            line=dict(color=T["GREY"], width=1.1, dash="dot"), layer="below"))
        layout.setdefault("annotations", []).append(dict(
            xref="x", x=bx, yref="paper", y=1.0, yanchor="bottom",
            text="forecast →", showarrow=False, xanchor="left", xshift=4,
            font=dict(size=11, color=T["GREY"])))

    apply_hlines(spec, layout, T)
    apply_vlines(spec, layout, T, xs, cat)
    return dict(data=traces, layout=layout)


def fig_bar_line(spec: dict, rows: list[dict], T: dict) -> dict:
    """Grouped bars with an overlay line — chart 4's published form.

    Sampled to one observation a year: at ~6px a bar, 290 monthly bars render
    as a solid block. Year-end (the last row of each year) rather than the
    annual mean, because that is what the article's figures quote.
    """
    xcol = spec.get("x", "ym")
    dec = spec.get("decimals", 2)

    if spec.get("resample") == "year_end":
        by_year: dict[str, dict] = {}
        for r in rows:                      # date-ordered; last write per year wins
            by_year[r[xcol].strip()[:4]] = r
        kept = [by_year[y] for y in sorted(by_year)]
        xs = [y for y in sorted(by_year)]   # category axis: bare years
    else:
        kept = list(rows)
        xs = [x_iso(r[xcol]) for r in kept]

    flag_col = spec.get("flag_col")
    flags = [str(r.get(flag_col, "")).strip() == "True" for r in kept] if flag_col else None

    traces = []
    for b in spec["bars"]:
        ys = [to_float(r.get(b["col"])) for r in kept]
        ys = [None if y is None else round(y, dec) for y in ys]
        # Provisional observations are drawn at reduced opacity — the PNG hatches
        # them; hatching is not available to a Plotly bar, and a faded bar reads
        # the same way ("not measured yet") without inventing a new encoding.
        marker = dict(color=b.get("color", T["BLUE"]))
        if flags:
            marker["opacity"] = [0.55 if f else 1.0 for f in flags]
        traces.append(dict(
            type="bar", name=b["label"], x=xs, y=ys, marker=marker,
            hovertemplate=f"%{{y:.{dec}f}}<extra>{b['label']}</extra>",
        ))

    if spec.get("line"):
        ln = spec["line"]
        ys = [to_float(r.get(ln["col"])) for r in kept]
        ys = [None if y is None else round(y, dec) for y in ys]
        traces.append(dict(
            type="scatter", mode="lines+markers", name=ln["label"], x=xs, y=ys,
            line=dict(color=ln.get("color", T["INK"]), width=2),
            marker=dict(size=5, color=ln.get("color", T["INK"])),
            hovertemplate=f"%{{y:.{dec}f}}<extra>{ln['label']}</extra>",
        ))

    layout = base_layout(spec, T, legend=True)
    layout["barmode"] = "group"
    layout["bargap"] = 0.25
    layout["xaxis"]["type"] = "category"
    # The zero baseline carries meaning here — it is the line r* falls through.
    layout["shapes"] = [dict(
        type="line", xref="paper", x0=0, x1=1, yref="y", y0=0, y1=0,
        line=dict(color=T["GREY"], width=1.1), layer="below",
    )]
    # After the baseline, so the helper extends that list instead of replacing it.
    apply_hlines(spec, layout, T)
    if spec.get("yrange"):
        layout["yaxis"]["range"] = spec["yrange"]
    return dict(data=traces, layout=layout)


def fig_ranked_bars(spec: dict, rows: list[dict], T: dict) -> dict:
    """Two side-by-side panels of horizontal bars over the SAME rows in the SAME
    order — the reserve league table beside the same reserves as a share of the
    holder's own GDP.

    The re-ordering between the panels is the chart's point, so the order is set
    once, by the first panel's column, and the second panel inherits it rather
    than sorting itself. Rows are filtered to the reference year (the latest one
    present) before ranking: the source CSV carries every candidate economy
    stamped with its own last observation, and mixing vintages inside one bar
    chart is exactly the failure the chart script guards against — Russia's
    figure stops a year early and would otherwise rank tenth on stale data.

    No gridlines: on horizontal bars a gridline is vertical, which house style
    forbids. The value labels at the bar ends carry the scale instead, which is
    also why neither x-axis shows ticks.
    """
    label_col = spec.get("label_col", "country")
    year_col = spec.get("year_col")
    panels = spec["panels"]

    kept = list(rows)
    if year_col:
        ref = max(int(r[year_col]) for r in kept)
        kept = [r for r in kept if int(r[year_col]) == ref]
    kept.sort(key=lambda r: -(to_float(r.get(panels[0]["col"])) or 0.0))
    kept = kept[: spec.get("top_n", 10)]

    names = [r[label_col].strip() for r in kept]
    # Plotly stacks the first category at the bottom; reversing the category
    # array puts rank 1 at the top, as the published chart has it.
    order = names[::-1]

    def fmt(v, p):
        if v is None:
            return ""
        dec = p.get("decimals", 0)
        s = f"{v:,.{dec}f}" if p.get("thousands") else f"{v:.{dec}f}"
        return f"{p.get('prefix', '')}{s}{p.get('suffix', '')}"

    traces, annos = [], []
    for i, p in enumerate(panels):
        axis = "" if i == 0 else str(i + 1)
        vals = [to_float(r.get(p["col"])) for r in kept]
        colour = p.get("color", T["BLUE"])
        traces.append(dict(
            type="bar", orientation="h", name=p["header"],
            x=vals, y=names, xaxis=f"x{axis}", yaxis=f"y{axis}",
            marker=dict(color=colour),
            text=[fmt(v, p) for v in vals], textposition="outside",
            textfont=dict(size=15, color=colour),
            cliponaxis=False,
            hovertemplate=f"%{{y}}<extra>{html.escape(p['header'])}: "
                          f"%{{x:,.{p.get('decimals', 0)}f}}"
                          f"{p.get('suffix', '')}</extra>",
        ))

    # Panel headers stand in for the axis titles, colour-matched to their bars,
    # exactly as the PNG does — there is no legend.
    # One panel is a plain horizontal bar chart (added 2026-08-12 for the BoJ
    # balance-sheet exhibits): full-width domain, no narrow-mode re-stacking.
    # The two-panel path is byte-identical to before.
    domains = [(0.0, 0.46), (0.54, 1.0)] if len(panels) > 1 else [(0.0, 1.0)]
    layout = base_layout(spec, T, legend=False)
    layout["bargap"] = 0.30
    # margin_l is spec-able (2026-08-12): the default 132 fits country names;
    # the BoJ balance-sheet lines are longer and clip without ~205.
    layout["margin"] = dict(l=spec.get("margin_l", 132), r=64, t=40, b=28)
    layout.pop("yaxis", None)
    layout.pop("xaxis", None)
    for i, p in enumerate(panels):
        axis = "" if i == 0 else str(i + 1)
        d0, d1 = domains[i]
        vals = [to_float(r.get(p["col"])) or 0.0 for r in kept]
        layout[f"xaxis{axis}"] = dict(
            domain=[d0, d1], anchor=f"y{axis}", showgrid=False, zeroline=False,
            showline=False, ticks="", showticklabels=False,
            range=[0, max(vals) * 1.22],   # headroom for the end labels
        )
        layout[f"yaxis{axis}"] = dict(
            domain=[0, 1], anchor=f"x{axis}", type="category",
            categoryorder="array", categoryarray=order,
            showgrid=False, zeroline=False, showline=False, ticks="",
            showticklabels=(i == 0),       # same rows, labelled once
            tickfont=dict(size=16, color=T["INK"]),
        )
        annos.append(dict(
            xref="paper", x=d0, yref="paper", y=1.02, yanchor="bottom",
            xanchor="left", text=p["header"], showarrow=False,
            font=dict(size=15, color=p.get("color", T["BLUE"])),
        ))
    layout["annotations"] = annos
    layout["hovermode"] = "closest"

    # Phone width. Side by side, each panel gets about 100px once the country
    # column is paid for — the bars vanish and the second panel's header runs
    # off the frame (measured: 36px past the edge at 375). Stacked, both panels
    # keep the full width and the shared order still reads down the page, which
    # is the comparison the chart exists to make.
    if len(panels) == 1:
        return dict(data=traces, layout=layout)
    narrow = {
        "maxwidth": 560, "height": spec.get("narrow_height", 720),
        "wide_height": spec.get("height", 470),
        "layout": {
            "xaxis.domain": [0, 1], "xaxis2.domain": [0, 1],
            "yaxis.domain": [0.56, 1], "yaxis2.domain": [0, 0.44],
            "yaxis2.showticklabels": True,
            "yaxis.tickfont.size": 13, "yaxis2.tickfont.size": 13,
            "annotations[0].y": 1.03, "annotations[1].y": 0.47,
            # stacked, the second header starts at the left edge like the first
            "annotations[1].x": 0.0,
            "margin.l": 104, "margin.r": 46, "margin.b": 12,
        },
        "wide": {
            "xaxis.domain": list(domains[0]), "xaxis2.domain": list(domains[1]),
            "yaxis.domain": [0, 1], "yaxis2.domain": [0, 1],
            "yaxis2.showticklabels": False,
            "yaxis.tickfont.size": 16, "yaxis2.tickfont.size": 16,
            "annotations[0].y": 1.02, "annotations[1].y": 1.02,
            "annotations[1].x": domains[1][0],
            "margin.l": 132, "margin.r": 64, "margin.b": 28,
        },
        "style": {"textfont.size": 12},
        "wide_style": {"textfont.size": 15},
    }
    return dict(data=traces, layout=layout, narrow=narrow)


def fig_signed_bar_line(spec: dict, rows: list[dict], T: dict) -> dict:
    """Signed quarterly bars with an overlay line on a second y-axis.

    Sign carries meaning rather than magnitude alone: a bar above the zero line
    is Japan buying dollars, one below it Japan selling, so the two directions
    are separate traces with their own colours and their own legend entries —
    which is where the PNG's direction arrows go on an interactive page.

    The two axes are deliberately offset (the left range runs far above the
    bars, the right far below the line) so the bars occupy the lower half of the
    frame and the exchange rate the upper half. That is not padding: it lets a
    reader read up from a bar to the rate that prevailed when it was
    transacted, and it is why both ranges and both tick sets are stated in the
    manifest rather than left to autoscale.
    """
    dec = spec.get("decimals", 2)
    ycol = spec["value"]["col"]
    flag_col = spec.get("flag_col")
    xcol = spec.get("x")

    def qdate(r):
        """Quarter → the ISO date of its first day, so the axis is a real time
        axis: 143 quarters as categories would render as an unreadable comb.

        An annual series declares `x` instead, and its dates are used as they
        stand. `year_col`/`q_col` stay the default, so a quarterly page built
        before this option existed draws exactly as it did."""
        if xcol:
            return r[xcol]
        y, q = int(r[spec.get("year_col", "year")]), int(r[spec.get("q_col", "q")])
        return f"{y}-{(q - 1) * 3 + 1:02d}-01"

    v = spec["value"]
    traces = []
    for sign, label, colour in (
            (1, v["pos_label"], v.get("pos_color", T["BLUE"])),
            (-1, v["neg_label"], v.get("neg_color", T["CORAL"]))):
        # Zero quarters are dropped rather than drawn flat — a zero-height bar
        # on a 143-quarter axis reads as a tick mark, i.e. as an operation.
        sel = [r for r in rows
               if (to_float(r.get(ycol)) or 0.0) * sign > 0]
        if not sel:
            continue
        flags = [str(r.get(flag_col, "")).strip() in ("1", "True", "true")
                 for r in sel] if flag_col else None
        marker = dict(color=colour)
        if flags and any(flags):
            # Provisional quarters are drawn at reduced opacity — the PNG
            # hatches them, which a Plotly bar cannot do; a faded bar reads the
            # same way ("announced or estimated, not yet in MOF's record").
            marker["opacity"] = [0.45 if f else 1.0 for f in flags]
        traces.append(dict(
            type="bar", name=label,
            x=[qdate(r) for r in sel],
            y=[round(to_float(r.get(ycol)), 4) for r in sel],
            # 0.22 of a year in ms — the quarterly default. An annual series
            # overrides it: a quarter-wide bar on a 45-year axis reads as a
            # spike rather than as one year's flow.
            marker=marker, width=spec.get("bar_width_ms", 6_946_560_000),
            hovertemplate=f"%{{y:.{dec}f}}<extra>{html.escape(label)}</extra>",
        ))

    if spec.get("line"):
        ln = spec["line"]
        sel = [r for r in rows if to_float(r.get(ln["col"])) is not None]
        ldec = ln.get("decimals", dec)
        traces.append(dict(
            type="scatter", mode="lines", name=ln["label"], yaxis="y2",
            x=[qdate(r) for r in sel],
            y=[round(to_float(r.get(ln["col"])), 4) for r in sel],
            line=dict(color=ln.get("color", T["AMBER"]), width=2.2),
            hovertemplate=f"%{{y:.{ldec}f}}<extra>{html.escape(ln['label'])}</extra>",
        ))

    layout = base_layout(spec, T, legend=True)
    layout["barmode"] = "overlay"
    layout["xaxis"]["hoverformat"] = spec.get("hoverformat", "%b %Y")
    if spec.get("yrange"):
        layout["yaxis"]["range"] = spec["yrange"]
    if spec.get("ytick"):
        layout["yaxis"]["tickmode"] = "array"
        layout["yaxis"]["tickvals"] = spec["ytick"]
    # The second axis exists to carry the overlay line. A bars-only chart has
    # nothing to put on it, and an empty right-hand axis would print a stray
    # 0-to-1 tick set beside the data.
    if spec.get("line") or spec.get("hlines2"):
        layout["yaxis2"] = dict(
            overlaying="y", side="right", showgrid=False, zeroline=False,
            showline=False, ticks="", tickfont=dict(size=18, color=T["GREY"]),
        )
    if spec.get("y2range") and "yaxis2" in layout:
        layout["yaxis2"]["range"] = spec["y2range"]
    if spec.get("y2tick") and "yaxis2" in layout:
        layout["yaxis2"]["tickmode"] = "array"
        layout["yaxis2"]["tickvals"] = spec["y2tick"]

    # The zero baseline separates buying from selling — it is the chart's axis
    # of meaning, not decoration.
    shapes = [dict(type="line", xref="paper", x0=0, x1=1, yref="y", y0=0, y1=0,
                   line=dict(color=T["GREY"], width=1.1), layer="below")]
    annos = []
    for h in spec.get("hlines2", []):
        shapes.append(dict(
            type="line", xref="paper", x0=0, x1=1, yref="y2",
            y0=h["y"], y1=h["y"],
            line=dict(color=T["INK"], width=1.3, dash="dash"), layer="below"))
        if h.get("label"):
            annos.append(dict(
                xref="paper", x=0.02, yref="y2", y=h["y"], text=h["label"],
                showarrow=False, xanchor="left", yanchor="bottom", yshift=3,
                font=dict(size=13, color=T["INK"])))
    layout["shapes"] = shapes
    if annos:
        layout["annotations"] = annos
    return dict(data=traces, layout=layout)


def fig_decomp(spec: dict, rows: list[dict], T: dict) -> dict:
    """Stacked decomposition: the components filled from the zero line, the
    total drawn over them as a line.

    Bars in ``relative`` mode, not a filled area stack. The term premium goes
    negative — 2Y is below zero through much of the 2000s — and a negative
    component has to hang below the axis while the positive one still rises
    from it. An area stack cannot do that; ``barmode="relative"`` is exactly
    this behaviour, and at monthly frequency the bars read as a filled block,
    which is the intended look.
    """
    xcol = spec.get("x", "YM")
    dec = spec.get("decimals", 3)
    kept = [r for r in rows if in_window(r[xcol], spec.get("start"), spec.get("end"))]
    xs = [x_iso(r[xcol]) for r in kept]

    split_col = spec.get("split_col")
    solid_val = spec.get("solid_value", "actual")
    if split_col:
        is_solid = [str(r.get(split_col, "")).strip() == solid_val for r in kept]
        boundary = max((i for i, s in enumerate(is_solid) if s), default=None)
    else:
        is_solid, boundary = None, None

    traces = []
    for c in spec["components"]:
        ys = [to_float(r.get(c["col"])) for r in kept]
        ys = [None if v is None else round(v, dec) for v in ys]
        marker = dict(color=c["color"], line=dict(width=0))
        if is_solid:
            # Projection bars are lightened. The dotted line above says the same
            # thing for the total; the bars need their own signal or the fill
            # reads as observed all the way to 2029.
            marker["opacity"] = [1.0 if s else 0.45 for s in is_solid]
        traces.append(dict(
            type="bar", name=c["label"], x=xs, y=ys, marker=marker,
            hovertemplate=f"%{{y:.{dec}f}}<extra>{c['label']}</extra>",
        ))

    # The total line is optional since 2026-08-12: the BoJ redemption wall is a
    # published stack with no total. Absent key -> no line; every page that
    # declares one is unchanged.
    tot = spec.get("total")
    if not tot:
        layout = base_layout(spec, T, legend=True)
        layout["barmode"] = "relative"
        layout["bargap"] = spec.get("bargap", 0)
        layout["shapes"] = [dict(type="line", xref="paper", x0=0, x1=1, yref="y",
                                 y0=0, y1=0, line=dict(color=T["INK"], width=1.1))]
        if boundary is not None and boundary + 1 < len(xs):
            layout["shapes"].append(dict(
                type="line", xref="x", x0=xs[boundary], x1=xs[boundary],
                yref="paper", y0=0, y1=1,
                line=dict(color=T["GREY"], width=1.1, dash="dot"), layer="below"))
            layout["annotations"] = [dict(
                xref="x", x=xs[boundary], yref="paper", y=1.0, yanchor="bottom",
                text="forecast →", showarrow=False, xanchor="left", xshift=4,
                font=dict(size=11, color=T["GREY"]))]
        if spec.get("yrange"):
            layout["yaxis"]["range"] = spec["yrange"]
        return dict(data=traces, layout=layout)
    tys = [to_float(r.get(tot["col"])) for r in kept]
    tys = [None if v is None else round(v, dec) for v in tys]
    colour = tot.get("color", T["INK"])
    if is_solid:
        hist = [v if is_solid[i] else None for i, v in enumerate(tys)]
        proj = [v if (not is_solid[i] or i == boundary) else None
                for i, v in enumerate(tys)]
        traces.append(dict(type="scatter", mode="lines", name=tot["label"], x=xs,
                           y=hist, line=dict(color=colour, width=2.2),
                           connectgaps=False,
                           hovertemplate=f"%{{y:.{dec}f}}<extra>{tot['label']}</extra>"))
        traces.append(dict(type="scatter", mode="lines", name=tot["label"], x=xs,
                           y=proj, showlegend=False,
                           line=dict(color=colour, width=2.2, dash="dot"),
                           connectgaps=False,
                           hovertemplate=f"%{{y:.{dec}f}}"
                                         f"<extra>{tot['label']} (forecast)</extra>"))
    else:
        traces.append(dict(type="scatter", mode="lines", name=tot["label"], x=xs,
                           y=tys, line=dict(color=colour, width=2.2),
                           connectgaps=False,
                           hovertemplate=f"%{{y:.{dec}f}}<extra>{tot['label']}</extra>"))

    layout = base_layout(spec, T, legend=True)
    layout["barmode"] = "relative"
    layout["bargap"] = 0
    layout["shapes"] = [dict(type="line", xref="paper", x0=0, x1=1, yref="y",
                             y0=0, y1=0, line=dict(color=T["INK"], width=1.1))]
    if boundary is not None and boundary + 1 < len(xs):
        layout["shapes"].append(dict(
            type="line", xref="x", x0=xs[boundary], x1=xs[boundary],
            yref="paper", y0=0, y1=1,
            line=dict(color=T["GREY"], width=1.1, dash="dot"), layer="below"))
        layout["annotations"] = [dict(
            xref="x", x=xs[boundary], yref="paper", y=1.0, yanchor="bottom",
            text="forecast →", showarrow=False, xanchor="left", xshift=4,
            font=dict(size=11, color=T["GREY"]))]
    if spec.get("yrange"):
        layout["yaxis"]["range"] = spec["yrange"]
    return dict(data=traces, layout=layout)


def fig_curve(spec: dict, rows: list[dict], T: dict) -> dict:
    """A cross-section: maturity on the x-axis, one line per date.

    The other kinds read down a column through time; this one reads across a
    row. It is how a yield curve is actually looked at, and it is the only view
    in which the shape of the forecast — steepening, flattening, inversion — is
    the thing you see rather than something you infer from six separate panels.
    """
    xcol = spec.get("x", "YM")
    dec = spec.get("decimals", 2)
    tenors = spec["tenors"]
    prefix = spec.get("value_prefix", "Yield_")
    by_x = {r[xcol].strip(): r for r in rows}

    # Maturities are spaced evenly by default rather than by their number of
    # years. On a linear axis 2Y and 5Y sit inside the leftmost 7% of a 40-year
    # span — crushed on a desktop and label-colliding on a phone — which hides
    # exactly the part of the curve the policy rate moves. Set "xscale":
    # "linear" to get true year spacing instead.
    scale = spec.get("xscale", "category")
    xvals = [f"{t}Y" for t in tenors] if scale == "category" else tenors

    traces = []
    for line in spec["lines"]:
        r = by_x.get(line["ym"])
        if r is None:
            raise KeyError(f"{line['ym']} not in {spec['csv']}")
        ys = [to_float(r.get(f"{prefix}{t}Y")) for t in tenors]
        ys = [None if y is None else round(y, dec) for y in ys]
        traces.append(dict(
            type="scatter", mode="lines+markers", name=line["label"],
            x=xvals, y=ys,
            line=dict(color=line.get("color", T["BLUE"]),
                      width=line.get("width", 2),
                      **({"dash": line["dash"]} if line.get("dash") else {})),
            marker=dict(size=6, color=line.get("color", T["BLUE"])),
            hovertemplate=f"%{{y:.{dec}f}}<extra>{line['label']}</extra>",
        ))

    layout = base_layout(spec, T, legend=True)
    layout["xaxis"].update(
        title=dict(text=spec.get("xlabel", "Maturity"),
                   font=dict(size=18, color=T["GREY"])),
        **(dict(type="category")
           if scale == "category"
           else dict(type="linear", tickmode="array", tickvals=tenors,
                     ticktext=[f"{t}Y" for t in tenors])),
    )
    layout["hovermode"] = "x unified"
    # The x title and the legend both live below the axis: at base_layout's
    # y=-0.14 the legend row sat ON the title (both pages' chart 6, caught in
    # Takuji's 2026-08-15 review). Push the legend below the title and give
    # the margin room for the two rows.
    layout["legend"] = {**layout["legend"], "y": -0.26}
    layout["margin"]["b"] = layout["margin"]["b"] + 58   # x title + legend row
    return dict(data=traces, layout=layout)


def _dodge_text(pts: list[tuple[float, float]], near: float) -> list[str]:
    """Choose a label side per point so two seats on nearly the same score do
    not print their names on top of each other.

    Plotly places `text` at a fixed offset from the marker and has no collision
    avoidance, so a map where three members sit within a quarter of a point —
    which is most meetings — renders as one unreadable smear unless the sides
    are assigned here. Points are walked in a stable order and each takes the
    first side not already used by a point within `near` on both axes."""
    sides = ["middle right", "top center", "bottom center", "middle left"]
    order = sorted(range(len(pts)), key=lambda i: (-pts[i][1], pts[i][0]))
    out, placed = ["middle right"] * len(pts), []
    for i in order:
        x, y = pts[i]
        taken = {s for (px, py, s) in placed
                 if abs(px - x) <= near and abs(py - y) <= near}
        side = next((s for s in sides if s not in taken), sides[0])
        out[i] = side
        placed.append((x, y, side))
    return out


def fig_xy_map(spec: dict, rows: list[dict], T: dict) -> dict:
    """A map, not a series: one marker per entity on two scored dimensions, with
    a slider that moves the whole map through dates.

    Built to match a reviewed matplotlib chart of the same map held in the
    chart library. Its conventions are kept here, because the two must not
    tell different stories:
    gridlines on BOTH axes (a point on a map is located in two dimensions, so a
    horizontal-only grid cannot place it), a fixed square range so a marker
    moving between frames means the seat moved and never that the axis did,
    neutral cross-hairs with their plain-English captions, and colour carrying a
    grouping derived from the y value rather than assigned.

    The CSV is long — one row per frame x entity x dimension — because that is
    what the resolution script emits. Two of the dimensions are plotted and any
    others ride along in the hover, so a reader can see the third score without
    a second chart.

    Frames are drawn as one trace pair each (scored, unscored) with only the
    last pair visible, and the slider toggles visibility. No animation frames:
    those would need the page's shared Plotly bootstrap to pass `frames` to
    newPlot, which would move bytes on every other page in both repos.
    """
    frame_col = spec.get("frame_col", "frame")
    label_col = spec.get("label_col", "label")
    dim_col = spec.get("dim_col", "dimension")
    val_col = spec.get("value_col", "score")
    x_dim, y_dim = spec["x_dim"], spec["y_dim"]
    extra_dims = spec.get("extra_dims", [])
    dec = spec.get("decimals", 2)
    lo, hi = spec.get("range", [0, 10])
    neutral = spec.get("neutral")
    groups = {g["key"]: g for g in spec.get("groups", [])}

    # frame -> label -> record. Insertion order is the CSV's, which is the
    # resolution script's chronological order; the slider inherits it.
    frames: dict[str, dict[str, dict]] = {}
    for r in rows:
        f = (r.get(frame_col) or "").strip()
        lab = (r.get(label_col) or "").strip()
        if not f or not lab:
            continue
        rec = frames.setdefault(f, {}).setdefault(lab, {"dims": {}, "row": r})
        rec["dims"][(r.get(dim_col) or "").strip()] = to_float(r.get(val_col))
        # The per-entity fields repeat on every dimension row; the plotted
        # dimensions are the authority for the ones that describe the marker.
        if (r.get(dim_col) or "").strip() == y_dim:
            rec["row"] = r
    if not frames:
        raise SystemExit(f"panel.json: xy_map chart {spec['n']} matched no rows "
                         f"in {spec['csv']}")

    keys = list(frames)
    traces, steps = [], []

    # The neutral cross-hairs are TRACES, not layout shapes, and they are the
    # first two so every frame's markers draw over them. A shape cannot do this
    # job here: on Plotly's "below" layer it renders beneath the gridlines, and
    # the house grid is opaque white, so the line disappears and the page is
    # left with two captions pointing at nothing (found in the render check,
    # 2026-09-03). On the "above" layer it would instead be drawn across the
    # markers. As traces they sit exactly where the published matplotlib twin
    # puts them: over the grid, under the seats.
    n_fixed = 0
    if neutral is not None:
        for x, y in (([neutral, neutral], [lo, hi]), ([lo, hi], [neutral, neutral])):
            traces.append(dict(
                type="scatter", mode="lines", name="neutral", visible=True,
                x=x, y=y, line=dict(color=T["GREY"], width=1.0, dash="dash"),
                opacity=0.7, hoverinfo="skip", showlegend=False))
        n_fixed = 2

    for fi, fkey in enumerate(keys):
        shown = fi == len(keys) - 1
        scored, unscored = [], []
        for lab, rec in frames[fkey].items():
            x, y = rec["dims"].get(x_dim), rec["dims"].get(y_dim)
            (scored if (x is not None and y is not None) else unscored).append(
                (lab, x, y, rec))

        # -- the seats that have both plotted scores
        pts = [(x, y) for _, x, y, _ in scored]
        # "dodge_within" is measured in SCORE units while a collision happens
        # in PIXELS, so it has to be set wider than the eye suggests: on the
        # PSI board map "Executives" is several times wider than 0.3 of a
        # point. Despite the name it dodges nothing but labels - it is the
        # only thing _dodge_text is given and no marker is ever displaced.
        sides = _dodge_text(pts, spec.get("dodge_within", 0.28))
        colours, edges, widths, texts, custom = [], [], [], [], []
        for lab, x, y, rec in scored:
            g = groups.get((rec["row"].get(spec.get("group_col", "")) or "").strip())
            gc = g["color"] if g else T["GREY"]
            # Hollow means the evidence behind the marker predates the previous
            # meeting: the seat has not been re-read, not that its score is soft.
            stale = bool((rec["row"].get(spec.get("stale_col", "")) or "").strip())
            colours.append(T["PAPER"] if stale else gc)
            edges.append(gc)
            widths.append(2.4 if stale else 1.4)
            texts.append(lab)
            # The hover is assembled here, not in the template, so a blank
            # field costs no empty line: each optional part carries its own
            # leading <br> or is the empty string.
            detail = (rec["row"].get(spec.get("detail_col", "")) or "").strip()
            tail = []
            for d in extra_dims:
                if rec["dims"].get(d) is not None:
                    tail.append(f"{d}: {rec['dims'][d]:.{dec}f}")
            src = (rec["row"].get(spec.get("source_col", "")) or "").strip()
            if src:
                tail.append(f'<span style="color:{T["GREY"]}">{src}</span>')
            note = (rec["row"].get(spec.get("note_col", "")) or "").strip()
            if note:
                tail.append(f'<span style="color:{T["GREY"]}">{note}</span>')
            custom.append([f" ({detail})" if detail else "",
                           ("<br>" + "<br>".join(tail)) if tail else ""])

        hov = (f"<b>%{{text}}</b>%{{customdata[0]}}<br>"
               f"{x_dim}: %{{x:.{dec}f}} · {y_dim}: %{{y:.{dec}f}}"
               f"%{{customdata[1]}}<extra></extra>")
        traces.append(dict(
            type="scatter", mode="markers+text", name=fkey, visible=shown,
            x=[x for _, x, _, _ in scored], y=[y for _, _, y, _ in scored],
            text=texts, textposition=sides,
            textfont=dict(size=13, color=T["INK"]),
            customdata=custom, hovertemplate=hov, showlegend=False,
            marker=dict(size=spec.get("marker_size", 15), color=colours,
                        line=dict(color=edges, width=widths)),
        ))

        # -- seats on the roster with no score. Shown at the margin, labelled,
        #    never dropped and never parked on the neutral cross-hairs, which
        #    would read as "this member is neutral".
        ux = lo + (hi - lo) * 0.045
        traces.append(dict(
            type="scatter", mode="markers+text", name=fkey + " (unscored)",
            visible=shown,
            x=[ux] * len(unscored),
            y=[lo + (hi - lo) * 0.10 + i * (hi - lo) * 0.075
               for i in range(len(unscored))],
            text=[f"  {lab} — not yet scored" for lab, _, _, _ in unscored],
            textposition=["middle right"] * len(unscored),
            textfont=dict(size=11, color=T["GREY"]),
            hoverinfo="skip", showlegend=False,
            marker=dict(size=13, color="rgba(0,0,0,0)",
                        line=dict(color=T["GREY"], width=1.4)),
        ))

        vis = [True] * n_fixed + [False] * (2 * len(keys))
        vis[n_fixed + 2 * fi] = vis[n_fixed + 2 * fi + 1] = True
        steps.append(dict(method="update", label=spec.get("frame_labels", {})
                          .get(fkey, fkey), args=[dict(visible=vis)]))

    layout = base_layout(spec, T, legend=False)
    layout["hovermode"] = "closest"
    layout["xaxis"].update(
        showgrid=True, gridcolor=T["GRID"], gridwidth=1.4,
        range=[lo, hi], tickmode="array", tickvals=spec.get("ticks", []),
        title=dict(text=spec.get("xlabel", ""),
                   font=dict(size=15, color=T["GREY"])))
    layout["yaxis"].update(
        range=[lo, hi], tickmode="array", tickvals=spec.get("ticks", []),
        title=dict(text=spec.get("ylabel", ""),
                   font=dict(size=15, color=T["GREY"])))
    layout["margin"] = dict(l=96, r=40, t=16, b=118)

    notes, n_cross = [], len(spec.get("crosshair_notes", []))
    for a in spec.get("crosshair_notes", []):
        notes.append(dict(x=a["x"], y=a["y"], text=a["text"], showarrow=False,
                          xanchor=a.get("xanchor", "left"),
                          yanchor=a.get("yanchor", "bottom"), align="left",
                          font=dict(size=11, color=T["GREY"])))

    # The colour key. The house style bans legends because a line can be
    # direct-labelled in its own colour; here the colour encodes a grouping
    # several markers share and there is nowhere to put it on a marker, so the
    # key is drawn as annotations in the corner the data cannot reach.
    if spec.get("key_at"):
        kx, ky, step = spec["key_at"]
        for i, g in enumerate(spec.get("groups", [])
                              + [dict(color=T["GREY"], label=spec.get(
                                  "hollow_label", ""), key="", glyph="○")]):
            if not g.get("label"):
                continue
            notes.append(dict(
                x=kx, y=ky - i * step, xanchor="left", yanchor="middle",
                showarrow=False, align="left",
                text=(f"<span style=\"color:{g['color']}\">"
                      f"{g.get('glyph', '●')}</span>  {g['label']}"),
                font=dict(size=11.5, color=T["INK"])))

    if notes:
        layout["annotations"] = notes
    layout["sliders"] = [dict(
        active=len(keys) - 1, steps=steps, x=0.06, xanchor="left",
        y=-0.20, yanchor="top", len=0.94, pad=dict(t=6, b=6),
        transition=dict(duration=0),
        currentvalue=dict(prefix=spec.get("slider_prefix", ""), xanchor="left",
                          font=dict(size=14, color=T["INK"])),
        tickcolor=T["GREY"], bordercolor="rgba(0,0,0,0)", bgcolor=T["GREY"],
        activebgcolor=T["INK"],
        font=dict(size=11, color=T["GREY"]))]

    # Phone width. Measured at 390px: the colour key's longest line, the x
    # cross-hair caption and the x-axis title all ran past the plot's right
    # edge, and an axis title truncated mid-word is exactly the defect no
    # numeric gate sees. The key is hidden rather than shrunk — at this width
    # its four lines cannot be made to fit and stay legible — so the figure's
    # caption has to carry the colour rule, and the manifest's "note" is the
    # place for it. The captions and titles shorten instead of disappearing,
    # because they are what make the neutral lines mean anything.
    narrow = {
        "maxwidth": spec.get("narrow_maxwidth", 560),
        "height": spec.get("narrow_height", spec.get("height", 470)),
        "wide_height": spec.get("height", 470),
        "layout": {
            "xaxis.title.text": spec.get("xlabel_narrow", spec.get("xlabel", "")),
            "yaxis.title.text": spec.get("ylabel_narrow", spec.get("ylabel", "")),
            "xaxis.title.font.size": 12, "yaxis.title.font.size": 12,
            "xaxis.tickfont.size": 13, "yaxis.tickfont.size": 13,
            "margin.l": 52, "margin.r": 16, "margin.b": 124,
        },
        "wide": {
            "xaxis.title.text": spec.get("xlabel", ""),
            "yaxis.title.text": spec.get("ylabel", ""),
            "xaxis.title.font.size": 15, "yaxis.title.font.size": 15,
            "xaxis.tickfont.size": 18, "yaxis.tickfont.size": 18,
            "margin.l": 96, "margin.r": 40, "margin.b": 118,
        },
        "style": {"textfont.size": 11},
        "wide_style": {"textfont.size": 13},
    }
    for i in range(n_cross, len(notes)):          # the colour key only
        narrow["layout"]["annotations[%d].visible" % i] = False
        narrow["wide"]["annotations[%d].visible" % i] = True
    for i, a in enumerate(spec.get("crosshair_notes", [])):
        if a.get("text_narrow"):
            narrow["layout"]["annotations[%d].text" % i] = a["text_narrow"]
            narrow["wide"]["annotations[%d].text" % i] = a["text"]
    return dict(data=traces, layout=layout, narrow=narrow)


def base_layout(spec: dict, T: dict, legend: bool) -> dict:
    """The house frame: warm-gray canvas, white horizontal gridlines only, no
    spines, no tick marks, unified hover. Mirrors house_layout() in the chart
    library. The title is NOT set here — it is HTML above the plot, matching the
    house PNG's bold left headline and staying legible on a phone."""
    # Axis text at 18px — tick labels and axis titles were 12px and unreadable
    # at the 840px figure width; enlarged 50% on Takuji's instruction
    # (2026-07-30). Margins hold the bigger labels.
    return dict(
        paper_bgcolor=T["PAPER"], plot_bgcolor=T["PAPER"],
        colorway=[T["BLUE"], T["CORAL"], T["AMBER"], T["GREY"]],
        font=dict(family=T["FONT_FAMILY"], color=T["INK"], size=13),
        xaxis=dict(showgrid=False, zeroline=False, showline=False, ticks="",
                   tickfont=dict(size=18, color=T["GREY"])),
        yaxis=dict(showgrid=True, gridcolor=T["GRID"], gridwidth=1.4,
                   zeroline=False, showline=False, ticks="",
                   tickfont=dict(size=18, color=T["GREY"]),
                   title=dict(text=spec.get("ylabel") or "",
                              font=dict(size=18, color=T["GREY"]))),
        hovermode="x unified",
        hoverlabel=dict(bgcolor="#FFFFFF", font_size=12, font_color=T["INK"],
                        font_family=T["FONT_FAMILY"]),
        # Legend BELOW the plot, as apply_house_style() does. Above the plot it
        # overlapped the data in five of the six Long Climb charts — chart 4
        # worst, where three long labels covered the recent bars. Below, it
        # cannot collide whatever the label length or the viewport width.
        margin=dict(l=84, r=60, t=16, b=92 if legend else 52),
        showlegend=legend,
        legend=dict(orientation="h", yanchor="top", y=-0.14, xanchor="center", x=0.5,
                    font=dict(size=12, color=T["GREY"]),
                    bgcolor="rgba(0,0,0,0)", bordercolor="rgba(0,0,0,0)"),
    )


# ----------------------------------------------------------------- table kind
def render_table(spec: dict, rows: list[dict]) -> str:
    """Chart 7 is a table, not a series. Rendered as HTML rather than a Plotly
    table: it stays selectable, copyable and readable at phone width, and the
    heavier rule under the actual-origin row survives.

    Two optional row accents, each declared per table and each emitting its CSS
    only when declared. "focal" is the row the table's headline is about — the
    coupon table is titled "35% of JGBs pay coupons of 0.5% or less" and the
    published exhibit sets that one row in coral, so a table rendered without it
    has lost the sentence it exists to support. "strong" is the total row. Both
    are drawn from the row's own value rather than its position, because a table
    that gains a bucket must not silently accent the wrong line.
    """
    cols = spec["columns"]
    rule_col, rule_val = spec.get("rule_after_col"), spec.get("rule_after_value")
    focal_col, focal_val = spec.get("focal_col"), spec.get("focal_value")
    strong_col, strong_val = spec.get("strong_col"), spec.get("strong_value")

    head = "".join(f"<th>{html.escape(c['label'])}</th>" for c in cols)
    body, hits = [], {"rule": 0, "focal": 0, "strong": 0}
    for r in rows:
        cells = "".join(f"<td>{html.escape((r.get(c['col']) or '').strip())}</td>"
                        for c in cols)
        names = []
        for name, col, val in (("rule", rule_col, rule_val),
                               ("focal", focal_col, focal_val),
                               ("strong", strong_col, strong_val)):
            if col and r.get(col, "").strip() == val:
                names.append(name)
                hits[name] += 1
        cls = f' class="{" ".join(names)}"' if names else ""
        body.append(f"<tr{cls}>{cells}</tr>")

    # A declared accent that matched no row is the failure this catches: the
    # value was renamed upstream, the table renders plausibly, and the row the
    # exhibit is about is no longer marked. Declaring it is asserting it exists.
    for name, col in (("rule", rule_col), ("focal", focal_col),
                      ("strong", strong_col)):
        if col and hits[name] != 1:
            raise SystemExit(
                f'panel.json: table {name!r} accent matched {hits[name]} rows, '
                f"expected exactly 1. Check {name}_value against the CSV.")
    return (f'<div class="tablewrap"><table class="fc"><thead><tr>{head}</tr></thead>'
            f'<tbody>{"".join(body)}</tbody></table></div>')


# ----------------------------------------------------------------------- page
def build(slug: str) -> Path:
    root = REPO / slug
    manifest = json.loads((root / "panel.json").read_text(encoding="utf-8"))
    T = load_house_tokens()

    # See TIER RULE above. A missing "tier" is a pre-rule page, not a mistake to
    # be defaulted away — but say so once, because every new page must declare it.
    tier = manifest.get("tier")
    if tier is None:
        # ASCII only: this console is cp932 and will not encode an em-dash.
        print(f'  note: {slug}/panel.json declares no "tier". Building with '
              "pre-2026-08-05 behaviour (downloads on). New pages must set "
              '"tier": "free" or "paid".')
    elif tier not in ("free", "paid"):
        raise SystemExit(f'panel.json: "tier" must be "free" or "paid", '
                         f"got {tier!r}")

    # See "WHAT A PAGE OFFERS" above. Absent, this resolves to the pre-2026-08-12
    # behaviour, which is what keeps every existing page byte-identical.
    if "downloads" in manifest:
        downloads = manifest["downloads"]
        if not isinstance(downloads, bool):
            raise SystemExit(f'panel.json: "downloads" must be true or false, '
                             f"got {downloads!r}")
    else:
        downloads = tier != "free"

    # A page that offers its data cannot also advertise that data as the thing a
    # subscription buys.
    show_perk = tier == "free" and not downloads

    # A visible way back to the landing index at the top of the page, for a
    # site whose reader needs one (the gated site's ask, 2026-08-14). Emitted
    # only for a page that declares it — an inert rule in every other page's
    # stylesheet would change bytes on pages that are meant to rebuild
    # byte-identical.
    site_nav = manifest.get("site_nav", False)
    if not isinstance(site_nav, bool):
        raise SystemExit(f'panel.json: "site_nav" must be true or false, '
                         f"got {site_nav!r}")

    # "More articles" line under the bottom banner — the funnel's pointer back
    # to the Substack home page (protocol decision log, 2026-08-23; wording
    # approved by Takuji). Opt-in like site_nav: pages that do not declare it
    # rebuild byte-identical.
    more_articles = manifest.get("more_articles", False)
    if not isinstance(more_articles, bool):
        raise SystemExit(f'panel.json: "more_articles" must be true or false, '
                         f"got {more_articles!r}")

    # Same rule as site_nav: the accent stylesheet is emitted only for a page
    # that declares an accent, so no page built before this key existed moves.
    table_accents = any(c.get("focal_col") or c.get("strong_col")
                        for c in manifest["charts"])

    cards, figs = [], []
    about_cards: dict[int, str] = {}   # exhibits embedded in the About section
    for spec in manifest["charts"]:
        n = spec["n"]
        rows = read_csv(root / spec["csv"])

        # An optional heading before this card, for a page that runs in parts —
        # e.g. the article's own charts, then the model work behind them.
        if spec.get("section"):
            secnote = (f'<p class="secnote">{html.escape(spec["section_note"])}</p>'
                       if spec.get("section_note") else "")
            cards.append(f'<div class="text"><div class="section">'
                         f'<h2>{html.escape(spec["section"])}</h2>{secnote}'
                         f'</div></div>')

        # Source + note render as one caption line under the figure, per the
        # template's figcaption (the guide's "caption line under each figure").
        caption_bits = []
        if spec.get("source"):
            caption_bits.append(html.escape(spec["source"]))
        if spec.get("note"):
            caption_bits.append(
                f'<span class="capnote">{html.escape(spec["note"])}</span>')
        caption = "<br>".join(caption_bits)

        if spec["kind"] == "table":
            body = (f'<div class="text">{render_table(spec, rows)}'
                    + (f'<p class="figcap">{caption}</p>' if caption else "")
                    + "</div>")
        else:
            div_id = f"chart_{n}"
            kinds = {"line": fig_line, "line_bars": fig_line_bars,
                     "bar_line": fig_bar_line,
                     "curve": fig_curve, "decomp": fig_decomp,
                     "ranked_bars": fig_ranked_bars,
                     "signed_bar_line": fig_signed_bar_line,
                     "xy_map": fig_xy_map}
            fig = kinds[spec["kind"]](spec, rows, T)
            figs.append((div_id, fig))
            h = spec.get("height", 470)
            # "step_buttons": one meeting at a time, for a chart whose
            # slider a reader would otherwise have to aim at. The markup
            # carries data-steps-for so the wiring finds its own plot.
            nav = ""
            if spec.get("step_buttons"):
                nav = (f'<div class="stepnav" data-steps-for="{div_id}">'
                       '<button type="button" class="stepbtn stepprev">'
                       '&lsaquo; Previous</button>'
                       '<button type="button" class="stepbtn stepnext">'
                       'Next &rsaquo;</button></div>')
            body = (f'<figure class="fig"><div class="frame">'
                    f'<div class="plot" id="{div_id}" '
                    f'style="height:{h}px;width:100%"></div></div>'
                    + nav
                    + (f"<figcaption>{caption}</figcaption>" if caption else "")
                    + "</figure>")

        sub = (f'<p class="sub">{html.escape(spec["subtitle"])}</p>'
               if spec.get("subtitle") else "")
        label = spec.get("label") or f"Chart {n}"

        # A page that offers no downloads shows the chart head bare, and a
        # single chart can opt out with "download": false while the rest of
        # the page keeps its links (Takuji, 2026-09-04: on one page the map
        # and its summary table offer no CSV while the per-entity charts do).
        # Absent, behaviour is unchanged, so no existing page moves a byte.
        dl = ("" if not downloads or spec.get("download") is False else
              f'\n      <a class="dl" href="{html.escape(spec["csv"])}" '
              "download>Download CSV</a>")

        card = f"""<section class="card" id="c{n}">
  <div class="text">
    <div class="chead">
      <span class="cnum">{html.escape(label)}</span>{dl}
    </div>
    <h2>{html.escape(spec["title"])}</h2>
    {sub}
  </div>
  {body}
</section>"""

        # "about_after_block": N lifts this exhibit out of the main run and
        # embeds it in the About section, directly after its Nth titled block
        # (the model-comparison chart sits beside the paragraph that argues it).
        if spec.get("about_after_block"):
            about_cards[spec["about_after_block"]] = card
        else:
            cards.append(card)

    figs_json = json.dumps(
        [{"id": i, "fig": f} for i, f in figs], separators=(",", ":"))

    m = manifest
    # One header slot, holding whichever of the two applies. A page with no
    # downloads states what a subscription buys instead of leaving it blank.
    workbook = ""
    if m.get("workbook") and not downloads:
        raise SystemExit('panel.json: a page that offers no downloads cannot '
                         'declare a "workbook" download')
    if show_perk:
        workbook = PERK_HTML
    elif m.get("workbook"):
        workbook = (f'<a class="btn" href="{html.escape(m["workbook"])}" download>'
                    f'Download the full workbook (Excel)</a>')

    # An article panel links its date back to the post; a standing dataset
    # carries a vintage stamp instead, so it takes no separate meta line.
    meta = ""
    if m.get("post_url"):
        meta = (f'<div class="meta">{html.escape(m["date"])} · '
                f'<a href="{html.escape(m["post_url"])}">read the article</a></div>')
    elif not m.get("stamp"):
        meta = f'<div class="meta">{html.escape(m["date"])}</div>'

    stamp = (f'<div class="stamp">{html.escape(m["stamp"])}</div>'
             if m.get("stamp") else "")

    # Lead text: "intro_html" carries pre-approved HTML (links, italics) and is
    # inserted verbatim; otherwise the plain standfirst is escaped as before.
    if m.get("intro_html"):
        lead = f'<p class="intro">{m["intro_html"]}</p>'
    elif m.get("standfirst"):
        lead = f'<p class="standfirst">{html.escape(m["standfirst"])}</p>'
    else:
        lead = ""

    # A scenario page states the assumptions its numbers rest on before it
    # shows any of them, so a reader cannot take a forecast path for a
    # unconditional prediction. Article panels carry no such block.
    assumptions = ""
    if m.get("assumptions"):
        a = m["assumptions"]
        items = "".join(
            f'<p><strong>{html.escape(it["head"])}</strong> '
            + (it["text_html"] if "text_html" in it else html.escape(it["text"]))
            + "</p>"
            for it in a.get("items", []))
        # The pointer to the fuller write-up. "url" is deliberately allowed to
        # be null: the report may not be published when the page is. In that
        # case the sentence still reads correctly as plain text, and the build
        # says so out loud rather than leaving a dead link or a silent TODO.
        more = ""
        if a.get("more"):
            mo = a["more"]
            url = mo.get("url")
            if url:
                # The anchor is a report title, so it is italicised to match
                # how intro_html renders one.
                anchor = html.escape(mo.get("anchor", "our report"))
                body = html.escape(mo["text"]).replace(
                    anchor,
                    f'<a href="{html.escape(url)}"><em>{anchor}</em></a>', 1)
            else:
                # Both wordings are authored up front, so publishing the report
                # is a single field change — set the url and the sentence stops
                # saying "forthcoming" and becomes a link in the same edit.
                # Nothing to remember, nothing to leave stale.
                body = html.escape(mo.get("text_pending", mo["text"]))
                print(f"  note: assumptions 'more' link is unset for {slug} — "
                      "using the pending wording, no link. Set "
                      "assumptions.more.url once the report is published.")
            more = f'<p class="assumpmore">{body}</p>'
        assumptions = (
            f'<div class="assump">'
            f'<div class="assumplabel">'
            f'{html.escape(a.get("heading", "Scenario assumptions"))}</div>'
            f"{items}{more}</div>")

    # The sibling scenario's page. Each of the two pages is only half the
    # picture, so the link out is part of the page, not a footnote.
    sibling = ""
    if m.get("sibling"):
        s = m["sibling"]
        sibling = (f'<div class="sib"><a href="{html.escape(s["href"])}">'
                   f'{html.escape(s["label"])} &rarr;</a>'
                   f'<span>{html.escape(s["text"])}</span></div>')

    # The About section (model page): lead-in, titled blocks, references.
    # references_html entries are pre-approved HTML copied verbatim from the
    # published report's appendix — inserted unescaped.
    about = ""
    if m.get("about"):
        a = m["about"]
        parts = []
        for i, b in enumerate(a.get("blocks", []), start=1):
            # "text_html" carries pre-approved HTML (links); "text" is escaped.
            body = b["text_html"] if "text_html" in b else html.escape(b["text"])
            parts.append(f'<p><strong>{html.escape(b["head"])}</strong> '
                         f"{body}</p>")
            if i in about_cards:
                # The embedded card breaks out to figure width, so the text
                # column is closed around it and reopened after.
                parts.append(f'</div>{about_cards[i]}'
                             f'<div class="text about-cont">')
        blocks = "".join(parts)
        refs = "".join(f"<p>{r}</p>" for r in a.get("references_html", []))
        if refs:
            refs = (f'<div class="refs"><div class="refslabel">References</div>'
                    f"{refs}</div>")
        about = (f'<div class="text about" id="about">'
                 f'<h2>{html.escape(a.get("heading", "About the model"))}</h2>'
                 f'<p>{html.escape(a["lead"])}</p>{blocks}{refs}</div>')

    # Article panels keep their closing line; a standing dataset's ending is
    # its About section, so the default applies only where a post exists.
    footer_note = m.get("footer_note",
                        "Every chart above is the one published in the "
                        "article, drawn from the same data."
                        if m.get("post_url") else "")
    endnote = ""
    if footer_note:
        # The closing sentence advertises the per-card CSV link, so it goes when
        # the link does — otherwise the page points at something that isn't there.
        csv_line = "" if not downloads else " Each card links its own CSV."
        endnote = (f'<p class="endnote text">{html.escape(footer_note)} '
                   "Hover to read values, drag to zoom, double-click to "
                   f"reset.{csv_line}</p>")

    page = PAGE.format(
        title=html.escape(m["title"]),
        mast_date=html.escape(m.get("masthead_date") or m["date"]),
        series_label=html.escape(m.get("series_label", "Chart data")),
        top_banner=html.escape(TOP_BANNER),
        # A page may carry its own approved bottom-banner wording (the model
        # page's paid-access text, Takuji 2026-07-30); the constant is the
        # default for article panels.
        bottom_banner=html.escape(m.get("bottom_banner", BOTTOM_BANNER)),
        subscribe_url=SUBSCRIBE_URL,
        # Same reason as scenario_css: an unused rule would change bytes on
        # pages that are meant to rebuild identically.
        perk_css=PERK_CSS if show_perk else "",
        more_articles=MORE_ARTICLES_HTML if more_articles else "",
        more_articles_css=MORE_ARTICLES_CSS if more_articles else "",
        topnav=TOPNAV_HTML if site_nav else "",
        topnav_css=TOPNAV_CSS if site_nav else "",
        table_accent_css=TABLE_ACCENT_CSS if table_accents else "",
        disclaimer=DISCLAIMER_HTML,
        footer_nav=FOOTER_NAV,
        meta=meta,
        stamp=stamp,
        lead=lead,
        # The scenario blocks and their styling are emitted only for a page
        # that uses them, so every existing page still rebuilds byte-identical
        # — which is what lets the frozen model page be rebuilt at all.
        header_extra=("\n  " + "\n  ".join(x for x in (assumptions, sibling) if x)
                      if (assumptions or sibling) else ""),
        scenario_css=SCENARIO_CSS if (assumptions or sibling) else "",
        step_css=STEP_CSS if any(c.get("step_buttons")
                                 for c in m["charts"]) else "",
        step_js=STEP_JS if any(c.get("step_buttons")
                               for c in m["charts"]) else "",
        step_wire=("      wireSteps(f);\r\n"
                   if any(c.get("step_buttons")
                          for c in m["charts"]) else ""),
        about=about,
        endnote=endnote,
        cards="\n".join(cards),
        figs_json=figs_json,
        plotly=PLOTLY_CDN,
        workbook=workbook,
        paper=T["PAPER"],
    )
    out = root / "index.html"
    out.write_text(page, encoding="utf-8")
    return out


# Styling for the scenario-page blocks. Held out of PAGE and injected only for
# a page that carries them: an unused rule in every other page's stylesheet
# would change bytes on pages that are meant to be frozen. Single braces — this
# is a format *value*, not part of the format template.
SCENARIO_CSS = """  .assump{margin:24px 0 0;border-left:3px solid #3b65a2;background:#f2f1ec;
          padding:16px 20px 4px}
  .assumplabel{font:700 11px 'Public Sans',sans-serif;letter-spacing:1.4px;
               color:#3b65a2;text-transform:uppercase;margin-bottom:10px}
  .assump p{font:400 15.5px/1.6 'PT Serif',serif;color:#2c2c2a;margin:0 0 12px;
            text-wrap:pretty}
  .assump p.assumpmore{font-style:italic;color:#54544e}
  .assump p.assumpmore a{color:#3b65a2}
  .sib{margin:18px 0 0;display:flex;flex-wrap:wrap;align-items:baseline;
       gap:4px 10px}
  .sib a{font:600 15px 'Public Sans',sans-serif;color:#3b65a2}
  .sib span{font:400 14px/1.6 'Public Sans',sans-serif;color:#737373}
"""

# The free page's subscription block, sitting where the workbook button would.
# Injected only on a free page, for the same byte-identity reason as above.
# Headline-card form chosen by Takuji 2026-08-23 (second round); border, rule
# and headline take the .btn blue so the card and its button read as one
# element. The .btn override is scoped to the card — the shared .btn elsewhere
# (bottom banner) is untouched.
PERK_CSS = """  .perkbox{margin:18px 0 0;border:1px solid #3b65a2;border-left:5px solid #3b65a2;
           background:#f4f6fa;padding:20px 24px}
  .perkbox h3{margin:0 0 6px;font:700 20px/1.3 'PT Serif',serif;color:#3b65a2}
  .perkbox .perk{margin:0;font:400 15.5px/1.6 'Public Sans',sans-serif;color:#2c2c2a}
  .perkbox .btn{margin-top:14px;font-size:15px;padding:11px 22px}
"""

# The "More articles" line under the bottom banner, injected only for a page
# declaring "more_articles": true (the seven free report pages, Takuji's set,
# 2026-08-23). Wording approved verbatim; matches the banner's measure.
MORE_ARTICLES_HTML = (
    '<p class="more-articles">More articles: '
    '<a href="https://takujiokubo.substack.com">takujiokubo.substack.com</a></p>'
)
MORE_ARTICLES_CSS = """  .more-articles{margin:14px auto 0;max-width:680px;
       font:400 13.5px 'Public Sans',sans-serif;color:#54544e}
  .more-articles a{color:#3b65a2}
"""

# The top-of-page link back to the landing index, injected only for a page
# declaring "site_nav": true. Label matches the footer's existing "All data
# packs" link so the two read as the same destination.
TOPNAV_CSS = """  .topnav{max-width:680px;margin:0 auto 20px;
          font:600 13px 'Public Sans',sans-serif}
"""
TOPNAV_HTML = '<p class="topnav"><a href="../">&larr; All data packs</a></p>\n'

# Table row accents, injected only for a page whose manifest declares one. An
# inert rule in every other page's stylesheet would move bytes on pages that are
# meant to rebuild byte-identical, which is why this is not in the fixed block.
# Coral and the ink weight are the same tokens the published table image uses.
TABLE_ACCENT_CSS = """  table.fc tr.focal td{color:#D85A30;font-weight:700}
  table.fc tr.strong td{font-weight:700}
"""

# Step buttons for a chart with a date slider (Takuji, 2026-09-04). Emitted
# only for a page that declares "step_buttons" on a chart, because an inert
# rule still changes bytes on every other page.
STEP_JS = """  // Step buttons drive the slider Plotly already built, rather than tracking
  // the current frame themselves: one source of truth for what is on screen,
  // so dragging the slider and clicking a button cannot disagree.
  function wireSteps(f){
    var wrap = document.querySelector('[data-steps-for="' + f.id + '"]');
    if(!wrap) return;
    var el = document.getElementById(f.id);
    var sl = f.fig.layout.sliders && f.fig.layout.sliders[0];
    if(!sl || !sl.steps || !sl.steps.length) return;
    var steps = sl.steps, last = steps.length - 1;
    var prev = wrap.querySelector('.stepprev');
    var next = wrap.querySelector('.stepnext');
    function at(){
      var s = el.layout && el.layout.sliders && el.layout.sliders[0];
      return (s && typeof s.active === 'number') ? s.active : last;
    }
    function sync(){
      var i = at(); prev.disabled = i <= 0; next.disabled = i >= last;
    }
    function go(d){
      var i = at() + d;
      if(i < 0 || i > last) return;
      Plotly.update(el, steps[i].args[0], {'sliders[0].active': i}).then(sync);
    }
    prev.addEventListener('click', function(){ go(-1); });
    next.addEventListener('click', function(){ go(1); });
    if(el.on) el.on('plotly_sliderchange', sync);
    sync();
  }
"""


STEP_CSS = """  .stepnav{display:flex;gap:8px;justify-content:flex-end;margin:10px 0 0}
  .stepbtn{font:600 13px 'Public Sans',sans-serif;cursor:pointer;
           border:1px solid #3b65a2;border-radius:3px;padding:4px 12px;
           color:#3b65a2;background:transparent}
  .stepbtn:hover:enabled{background:#3b65a2;color:#fff}
  .stepbtn:disabled{border-color:#c9c7c0;color:#c9c7c0;cursor:default}
"""


PAGE = """<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>{title} — data | Japan Macro Advisors</title>
<link rel="preconnect" href="https://fonts.googleapis.com">
<link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>
<link href="https://fonts.googleapis.com/css2?family=PT+Serif:ital,wght@0,400;0,700;1,400;1,700&amp;family=Public+Sans:wght@400;500;600;700&amp;display=swap" rel="stylesheet">
<style>
  /* Web Report page identity — WEB_REPORT_GUIDE.md §Page style tokens.
     The charts inside the frames keep the Plotly house theme untouched. */
  *{{margin:0;padding:0;box-sizing:border-box}}
  body{{font-family:'PT Serif',Georgia,serif;background:#FCFBF8;color:#2a2a28;
       line-height:1.7;padding:40px 20px 80px;max-width:880px;margin:0 auto}}
  a{{color:#3b65a2;text-decoration:none}}
  a:hover{{color:#2c4d7e;text-decoration:underline}}
  .text{{max-width:680px;margin-left:auto;margin-right:auto}}
{topnav_css}  .mrow{{display:flex;justify-content:space-between;align-items:flex-end;
        padding-bottom:12px;border-bottom:2px solid #1c1c1c}}
  .mrow img{{height:24px;width:auto;display:block;flex:none}}
  .mdate{{font:400 12px 'Public Sans',sans-serif;color:#737373}}
  .mrow2{{display:flex;justify-content:space-between;align-items:baseline;
         padding-top:6px}}
  .tagline{{font:italic 400 12px 'PT Serif',serif;color:#8a8a82}}
  .slabel{{font:600 10.5px 'Public Sans',sans-serif;letter-spacing:1.6px;
          color:#a08a5f;text-transform:uppercase}}
  .banner{{background:#f2f1ec;border:1px solid #e2e0d8;padding:11px 18px;
          margin:22px auto 0;max-width:680px;
          font:400 13px/1.55 'Public Sans',sans-serif;color:#54544e}}
  .banner.bottom{{margin-top:48px;padding:18px 20px;font-size:13.5px}}
  .btn{{display:inline-block;margin-top:12px;background:#3b65a2;color:#fff;
       font:600 14px 'Public Sans',sans-serif;text-decoration:none;
       padding:9px 16px;border-radius:4px}}
  .btn:hover{{background:#2c4d7e;color:#fff;text-decoration:none}}
{perk_css}{more_articles_css}  header{{margin-top:36px}}
  header h1{{font:700 36px/1.2 'PT Serif',serif;color:#1c1c1c;margin:0 0 14px;
            text-wrap:balance}}
  header .meta{{font:400 13px 'Public Sans',sans-serif;color:#737373;
               margin-bottom:14px}}
  .stamp{{background:#f2f1ec;border:1px solid #e2e0d8;padding:14px 18px;
         margin:0 0 18px;font:400 15.5px/1.55 'PT Serif',serif;color:#2c2c2a}}
  .intro,.standfirst{{font:400 17px/1.7 'PT Serif',serif;color:#2a2a28;
                     margin:0 0 6px;text-wrap:pretty}}
{scenario_css}{step_css}  .card{{margin-top:46px}}
  .chead{{display:flex;justify-content:space-between;align-items:baseline;
         gap:12px}}
  .cnum{{font:700 11px 'Public Sans',sans-serif;letter-spacing:1.4px;
        color:#737373;text-transform:uppercase}}
  .dl{{font:600 13px 'Public Sans',sans-serif;white-space:nowrap;
      border:1px solid #3b65a2;border-radius:3px;padding:4px 11px;
      color:#3b65a2}}
  .dl:hover{{background:#3b65a2;color:#fff;text-decoration:none}}
  .card h2{{font:700 23px/1.3 'PT Serif',serif;color:#1c1c1c;margin:6px 0 4px}}
  .sub{{font:400 13px 'Public Sans',sans-serif;color:#737373;margin-bottom:2px}}
  .fig{{margin:14px 0 0}}
  .frame{{border:1px solid #e4e2da;background:{paper}}}
  figcaption,.figcap{{max-width:680px;margin:8px auto 0;
    font:400 12.5px/1.5 'Public Sans',sans-serif;color:#8a8a82}}
  .capnote{{font-style:italic}}
  .section{{margin:56px 0 0;border-top:2px solid #1c1c1c;padding-top:16px}}
  .section h2{{font:700 23px/1.3 'PT Serif',serif;color:#1c1c1c}}
  .secnote{{font:400 14px/1.6 'Public Sans',sans-serif;color:#737373;
           margin-top:8px}}
  .tablewrap{{overflow-x:auto;margin-top:14px}}
  table.fc{{border-collapse:collapse;min-width:460px;width:100%;
           font:400 14px 'Public Sans',sans-serif}}
  table.fc th{{text-align:right;font-weight:600;color:#737373;font-size:12px;
              padding:7px 12px;border-bottom:1.5px solid #888780}}
  table.fc th:first-child{{text-align:left}}
  table.fc td{{text-align:right;padding:8px 12px;border-bottom:1px solid #EDEBE4}}
  table.fc td:first-child{{text-align:left;font-weight:600}}
  table.fc tr.rule td{{border-bottom:2px solid #1c1c1c}}
{table_accent_css}  .about{{margin-top:60px}}
  .about h2{{font:700 23px/1.3 'PT Serif',serif;color:#1c1c1c;margin:0 0 14px}}
  .about p,.about-cont p{{font:400 17px/1.7 'PT Serif',serif;color:#2a2a28;
           margin:0 0 18px;text-wrap:pretty}}
  .about-cont{{margin-top:34px}}
  .refs{{border-top:1px solid #d8d6ce;padding-top:16px;margin-top:26px}}
  .refslabel{{font:700 12px 'Public Sans',sans-serif;letter-spacing:1.4px;
             color:#737373;text-transform:uppercase;margin-bottom:10px}}
  .refs p{{font:400 13.5px/1.6 'PT Serif',serif;color:#54544e;margin:0 0 10px}}
  .endnote{{font:400 13px/1.7 'Public Sans',sans-serif;color:#737373;
           margin-top:44px}}
  .disclaimer{{font:400 10.5px/1.55 'Public Sans',sans-serif;color:#9a9a92;
              margin:14px auto 0;max-width:680px;text-wrap:pretty}}
  .nav{{font:400 12px 'Public Sans',sans-serif;color:#9a9a92;margin:10px auto 0;
       max-width:680px}}
  @media(max-width:640px){{
    body{{padding:24px 12px 48px}}
    header h1{{font-size:26px}}
    .card h2{{font-size:19px}}
  }}
</style>
</head>
<body>
{topnav}<div class="text">
  <div class="mrow">
    <img src="../assets/jma-logo.png" alt="Japan Macro Advisors">
    <span class="mdate">{mast_date}</span>
  </div>
  <div class="mrow2">
    <span class="tagline">Unbiased Opinion on Japan&rsquo;s Economy</span>
    <span class="slabel">{series_label}</span>
  </div>
</div>

<div class="banner top">{top_banner}</div>

<header class="text">
  <h1>{title}</h1>
  {meta}
  {stamp}
  {lead}
  {workbook}{header_extra}
</header>

{cards}

{about}

{endnote}

<div class="banner bottom">
  <p>{bottom_banner}</p>
  <a class="btn" href="{subscribe_url}">Subscribe</a>
</div>
{more_articles}
<p class="disclaimer">{disclaimer}</p>
{footer_nav}

<script src="{plotly}" charset="utf-8"></script>
<script>
  var FIGS = {figs_json};
  var CFG = {{responsive:true, displaylogo:false,
              modeBarButtonsToRemove:['lasso2d','select2d','autoScale2d']}};
  // A figure may carry a "narrow" block: a relayout patch for phone width and
  // its inverse, applied on load and on resize. Only the two-panel ranked-bars
  // chart uses one — side by side, its panels do not survive a 375px frame.
  function fitNarrow(f){{
    var n = f.fig.narrow; if(!n) return;
    var el = document.getElementById(f.id);
    var want = el.clientWidth <= n.maxwidth;
    if(el.dataset.narrow === String(want)) return;
    el.dataset.narrow = String(want);
    el.style.height = (want ? n.height : n.wide_height) + 'px';
    Plotly.relayout(el, want ? n.layout : n.wide);
    Plotly.restyle(el, want ? n.style : n.wide_style);
  }}
  window.addEventListener('resize', function(){{ FIGS.forEach(fitNarrow); }});

{step_js}  FIGS.forEach(function(f){{
    Plotly.newPlot(f.id, f.fig.data, f.fig.layout, CFG).then(function(){{
      fitNarrow(f);
{step_wire}      // A window resize is not the only way the frame changes width (an
      // orientation change on a phone, a container reflow after the webfont
      // lands). Observe the element itself as well.
      if(f.fig.narrow && window.ResizeObserver)
        new ResizeObserver(function(){{ fitNarrow(f); }})
          .observe(document.getElementById(f.id));
    }});
  }});
</script>
</body>
</html>
"""


if __name__ == "__main__":
    if len(sys.argv) != 2:
        sys.exit("usage: python builder/build_panel.py <slug>")
    print(f"building {sys.argv[1]}")
    print(f"  wrote {build(sys.argv[1])}")
