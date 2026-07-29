#!/usr/bin/env python3
"""
build_panel.py — build the interactive companion panel for one article.

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
    charts: [ {n, kind, title, subtitle, ylabel, source, csv, ...} ]

    kind "line"     x, start, end, series[{col,label,color,dash}],
                    hlines[{y,label}], decimals
    kind "bar_line" x, resample ("year_end"), bars[{col,label,color}],
                    line{col,label,color}, flag_col, flag_note, decimals
    kind "table"    columns[{col,label}], row_label_col, rule_after_col/value
"""

from __future__ import annotations

import csv
import html
import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parent

# The chart library on Drive owns the interactive house tokens. Build-time only —
# the published page is static and carries the resolved values inline.
CHARTS_ROOT = Path(r"G:\My Drive\charts")

PLOTLY_CDN = "https://cdn.plot.ly/plotly-3.0.1.min.js"


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
    return f"{raw}-01" if len(raw) == 7 else raw


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
    for s in spec["series"]:
        ys = [to_float(r.get(s["col"])) for r in kept]
        ys = [None if y is None else round(y, dec) for y in ys]
        colour = s.get("color", T["BLUE"])
        line = dict(color=colour, width=s.get("width", 2))
        if s.get("dash"):
            line["dash"] = s["dash"]

        if not split_col:
            traces.append(dict(
                type="scatter", mode="lines", name=s["label"],
                x=xs, y=ys, line=line, connectgaps=False,
                hovertemplate=f"%{{y:.{dec}f}}<extra>{s['label']}</extra>",
            ))
            continue

        hist = [y if is_solid[i] else None for i, y in enumerate(ys)]
        # the projection leg keeps the last observed point so the two legs join
        proj = [y if (not is_solid[i] or i == boundary) else None
                for i, y in enumerate(ys)]
        traces.append(dict(
            type="scatter", mode="lines", name=s["label"], x=xs, y=hist,
            line=line, connectgaps=False,
            hovertemplate=f"%{{y:.{dec}f}}<extra>{s['label']}</extra>",
        ))
        traces.append(dict(
            type="scatter", mode="lines", name=s["label"], x=xs, y=proj,
            line=dict(color=colour, width=s.get("width", 2), dash="dot"),
            connectgaps=False, showlegend=False,
            hovertemplate=f"%{{y:.{dec}f}}<extra>{s['label']} (forecast)</extra>",
        ))

    layout = base_layout(spec, T, legend=len(spec["series"]) > 1)

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
    shapes, annos = [], []
    for h in spec.get("hlines", []):
        shapes.append(dict(
            type="line", xref="paper", x0=0, x1=1, yref="y",
            y0=h["y"], y1=h["y"],
            line=dict(color=T["GREY"], width=1.4, dash="dash"), layer="below",
        ))
        if h.get("label"):
            annos.append(dict(
                xref="paper", x=1, yref="y", y=h["y"], text=h["label"],
                showarrow=False, xanchor="left", yanchor="middle",
                font=dict(size=11, color=T["GREY"]), xshift=6,
            ))
    if shapes:
        layout["shapes"] = shapes
    if annos:
        layout["annotations"] = layout.get("annotations", []) + annos
    if spec.get("yrange"):
        layout["yaxis"]["range"] = spec["yrange"]

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
    if spec.get("yrange"):
        layout["yaxis"]["range"] = spec["yrange"]
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

    tot = spec["total"]
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
                   font=dict(size=12, color=T["GREY"])),
        **(dict(type="category")
           if scale == "category"
           else dict(type="linear", tickmode="array", tickvals=tenors,
                     ticktext=[f"{t}Y" for t in tenors])),
    )
    layout["hovermode"] = "x unified"
    layout["margin"]["b"] = layout["margin"]["b"] + 14   # room for the x title
    return dict(data=traces, layout=layout)


def base_layout(spec: dict, T: dict, legend: bool) -> dict:
    """The house frame: warm-gray canvas, white horizontal gridlines only, no
    spines, no tick marks, unified hover. Mirrors house_layout() in the chart
    library. The title is NOT set here — it is HTML above the plot, matching the
    house PNG's bold left headline and staying legible on a phone."""
    return dict(
        paper_bgcolor=T["PAPER"], plot_bgcolor=T["PAPER"],
        colorway=[T["BLUE"], T["CORAL"], T["AMBER"], T["GREY"]],
        font=dict(family=T["FONT_FAMILY"], color=T["INK"], size=13),
        xaxis=dict(showgrid=False, zeroline=False, showline=False, ticks="",
                   tickfont=dict(size=12, color=T["GREY"])),
        yaxis=dict(showgrid=True, gridcolor=T["GRID"], gridwidth=1.4,
                   zeroline=False, showline=False, ticks="",
                   tickfont=dict(size=12, color=T["GREY"]),
                   title=dict(text=spec.get("ylabel") or "",
                              font=dict(size=12, color=T["GREY"]))),
        hovermode="x unified",
        hoverlabel=dict(bgcolor="#FFFFFF", font_size=12, font_color=T["INK"],
                        font_family=T["FONT_FAMILY"]),
        # Legend BELOW the plot, as apply_house_style() does. Above the plot it
        # overlapped the data in five of the six Long Climb charts — chart 4
        # worst, where three long labels covered the recent bars. Below, it
        # cannot collide whatever the label length or the viewport width.
        margin=dict(l=58, r=54, t=16, b=74 if legend else 40),
        showlegend=legend,
        legend=dict(orientation="h", yanchor="top", y=-0.14, xanchor="center", x=0.5,
                    font=dict(size=12, color=T["GREY"]),
                    bgcolor="rgba(0,0,0,0)", bordercolor="rgba(0,0,0,0)"),
    )


# ----------------------------------------------------------------- table kind
def render_table(spec: dict, rows: list[dict]) -> str:
    """Chart 7 is a table, not a series. Rendered as HTML rather than a Plotly
    table: it stays selectable, copyable and readable at phone width, and the
    heavier rule under the actual-origin row survives."""
    cols = spec["columns"]
    rule_col, rule_val = spec.get("rule_after_col"), spec.get("rule_after_value")

    head = "".join(f"<th>{html.escape(c['label'])}</th>" for c in cols)
    body = []
    for r in rows:
        cells = "".join(f"<td>{html.escape((r.get(c['col']) or '').strip())}</td>"
                        for c in cols)
        cls = ' class="rule"' if rule_col and r.get(rule_col, "").strip() == rule_val else ""
        body.append(f"<tr{cls}>{cells}</tr>")
    return (f'<div class="tablewrap"><table class="fc"><thead><tr>{head}</tr></thead>'
            f'<tbody>{"".join(body)}</tbody></table></div>')


# ----------------------------------------------------------------------- page
def build(slug: str) -> Path:
    root = REPO / slug
    manifest = json.loads((root / "panel.json").read_text(encoding="utf-8"))
    T = load_house_tokens()

    cards, figs = [], []
    for spec in manifest["charts"]:
        n = spec["n"]
        rows = read_csv(root / spec["csv"])
        csv_name = Path(spec["csv"]).name

        if spec["kind"] == "table":
            inner = render_table(spec, rows)
        else:
            div_id = f"chart_{n}"
            kinds = {"line": fig_line, "bar_line": fig_bar_line,
                     "curve": fig_curve, "decomp": fig_decomp}
            fig = kinds[spec["kind"]](spec, rows, T)
            figs.append((div_id, fig))
            h = spec.get("height", 470)
            inner = (f'<div class="plot" id="{div_id}" '
                     f'style="height:{h}px;width:100%"></div>')

        sub = (f'<p class="sub">{html.escape(spec["subtitle"])}</p>'
               if spec.get("subtitle") else "")
        note = (f'<p class="note">{html.escape(spec["note"])}</p>'
                if spec.get("note") else "")
        label = spec.get("label") or f"Chart {n}"

        # An optional heading before this card, for a page that runs in parts —
        # e.g. the article's own charts, then the model work behind them.
        if spec.get("section"):
            note = (f'<p class="secnote">{html.escape(spec["section_note"])}</p>'
                    if spec.get("section_note") else "")
            cards.append(f'<div class="section"><h2>{html.escape(spec["section"])}'
                         f'</h2>{note}</div>')

        cards.append(f"""<section class="card" id="c{n}">
  <div class="chead">
    <span class="cnum">{html.escape(label)}</span>
    <a class="dl" href="{html.escape(spec['csv'])}" download>Download CSV</a>
  </div>
  <h2>{html.escape(spec["title"])}</h2>
  {sub}
  {inner}
  <p class="src">{html.escape(spec.get("source", ""))}</p>
  {note}
</section>""")

    figs_json = json.dumps(
        [{"id": i, "fig": f} for i, f in figs], separators=(",", ":"))

    m = manifest
    workbook = ""
    if m.get("workbook"):
        workbook = (f'<a class="btn" href="{html.escape(m["workbook"])}" download>'
                    f'Download the full workbook (Excel)</a>')

    # A standing dataset has no article to link back to; an article panel does.
    meta = html.escape(m["date"])
    if m.get("post_url"):
        meta += f' · <a href="{html.escape(m["post_url"])}">read the article</a>'

    page = PAGE.format(
        title=html.escape(m["title"]),
        meta=meta,
        standfirst=html.escape(m.get("standfirst", "")),
        footer_note=html.escape(m.get(
            "footer_note",
            "Every chart above is the one published in the article, "
            "drawn from the same data.")),
        cards="\n".join(cards),
        figs_json=figs_json,
        plotly=PLOTLY_CDN,
        workbook=workbook,
        paper=T["PAPER"], ink=T["INK"], grey=T["GREY"],
        blue=T["BLUE"], font=T["FONT_FAMILY"],
    )
    out = root / "index.html"
    out.write_text(page, encoding="utf-8")
    return out


PAGE = """<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>{title} — data | Japan Macro Advisors</title>
<style>
  *{{margin:0;padding:0;box-sizing:border-box}}
  body{{font-family:{font};background:{paper};color:{ink};
       line-height:1.55;padding:28px 20px 56px;max-width:1080px;margin:0 auto}}
  header{{margin-bottom:26px}}
  .kicker{{font-size:12px;letter-spacing:.08em;text-transform:uppercase;color:{grey}}}
  header h1{{font-size:27px;line-height:1.25;margin:8px 0 6px;font-weight:700}}
  header .meta{{font-size:13px;color:{grey}}}
  header .standfirst{{font-size:15px;color:{ink};margin-top:12px;max-width:62ch}}
  .btn{{display:inline-block;margin-top:16px;background:{blue};color:#fff;
       font-size:14px;font-weight:600;text-decoration:none;padding:9px 16px;
       border-radius:4px}}
  .btn:hover{{filter:brightness(1.07)}}
  .section{{margin:38px 0 18px;border-top:2px solid {ink};padding-top:14px}}
  .section h2{{font-size:15px;font-weight:700;letter-spacing:.04em;
              text-transform:uppercase}}
  .secnote{{font-size:14px;color:{grey};margin-top:6px;max-width:66ch}}
  .card{{background:#fff;border-radius:6px;padding:18px 20px 14px;margin-bottom:22px;
        box-shadow:0 1px 4px rgba(0,0,0,.07)}}
  .chead{{display:flex;justify-content:space-between;align-items:baseline;gap:12px}}
  .cnum{{font-size:12px;font-weight:700;letter-spacing:.06em;color:{grey};
        text-transform:uppercase}}
  .dl{{font-size:12px;color:{blue};text-decoration:none;white-space:nowrap}}
  .dl:hover{{text-decoration:underline}}
  .card h2{{font-size:19px;line-height:1.3;margin:6px 0 2px;font-weight:700}}
  .sub{{font-size:13px;color:{grey};margin-bottom:8px}}
  .plot{{margin-top:8px}}
  .src{{font-size:11px;color:{grey};margin-top:10px;line-height:1.5}}
  .note{{font-size:11px;color:{grey};margin-top:6px;font-style:italic}}
  .tablewrap{{overflow-x:auto;margin-top:10px}}
  table.fc{{border-collapse:collapse;font-size:14px;min-width:460px;width:100%}}
  table.fc th{{text-align:right;font-weight:600;color:{grey};font-size:12px;
              padding:7px 12px;border-bottom:1.5px solid {grey}}}
  table.fc th:first-child{{text-align:left}}
  table.fc td{{text-align:right;padding:8px 12px;border-bottom:1px solid #EDEBE4}}
  table.fc td:first-child{{text-align:left;font-weight:600}}
  table.fc tr.rule td{{border-bottom:2px solid {ink}}}
  footer{{font-size:12px;color:{grey};margin-top:30px;line-height:1.7}}
  footer a{{color:{blue}}}
  @media(max-width:640px){{
    body{{padding:18px 12px 40px}}
    header h1{{font-size:22px}}
    .card{{padding:14px 12px 10px}}
    .card h2{{font-size:17px}}
  }}
</style>
</head>
<body>
<header>
  <div class="kicker">Japan Macro Advisors — chart data</div>
  <h1>{title}</h1>
  <div class="meta">{meta}</div>
  <p class="standfirst">{standfirst}</p>
  {workbook}
</header>

{cards}

<footer>
  {footer_note}
  Hover to read values, drag to zoom, double-click to reset. Each card links its
  own CSV.<br>
  Japan Macro Advisors is independent research. Nothing here constitutes
  investment advice.<br>
  <a href="../">All data packs</a> ·
  <a href="https://takujiokubo.substack.com">takujiokubo.substack.com</a>
</footer>

<script src="{plotly}" charset="utf-8"></script>
<script>
  var FIGS = {figs_json};
  var CFG = {{responsive:true, displaylogo:false,
              modeBarButtonsToRemove:['lasso2d','select2d','autoScale2d']}};
  FIGS.forEach(function(f){{
    Plotly.newPlot(f.id, f.fig.data, f.fig.layout, CFG);
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
