#!/usr/bin/env python3
"""
qa_panel.py — check a built panel against its sources.

Runs on the DELIVERED index.html, not on the builder's intermediates: it pulls
the FIGS payload back out of the page and re-derives every gate from that. A
gate computed on anything other than the object that ships is not a gate.

    python builder/qa_panel.py 2026-07-20-long-climb
"""

from __future__ import annotations

import csv
import json
import re
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
FAILED = []


def gate(ok: bool, name: str, detail: str = "") -> None:
    print(f"  {'PASS' if ok else 'FAIL'}  {name}" + (f" — {detail}" if detail else ""))
    if not ok:
        FAILED.append(name)


def load_delivered(root: Path):
    page = (root / "index.html").read_text(encoding="utf-8")
    m = re.search(r"var FIGS = (\[.*?\]);\n", page, re.S)
    figs = {f["id"]: f["fig"] for f in json.loads(m.group(1))}
    return page, figs


def col(root: Path, csv_name: str, c: str):
    """(x, value) pairs from the source CSV, blanks dropped."""
    out = []
    with open(root / csv_name, newline="", encoding="utf-8-sig") as f:
        rdr = csv.DictReader(f)
        xcol = "date" if "date" in rdr.fieldnames else "ym"
        for r in rdr:
            v = (r.get(c) or "").strip()
            if v:
                out.append((r[xcol].strip(), float(v)))
    return out


def trace(fig, name):
    return next(t for t in fig["data"] if t["name"] == name)


def qa_structure(manifest, page, figs) -> None:
    print("Structure")
    n_plot = sum(1 for c in manifest["charts"] if c["kind"] != "table")
    gate(len(figs) == n_plot, "every non-table chart reached the page",
         f"{len(figs)} figures for {n_plot} specs")
    for c in manifest["charts"]:
        gate(f'href="{c["csv"]}"' in page, f"chart {c['n']} CSV link present")
    gate("cdn.plot.ly" in page, "Plotly source declared")
    gate(page.count('class="card"') == len(manifest["charts"]),
         "one card per exhibit")


# The fixed page blocks, restated here FROM THE WORK ORDER / TEMPLATE rather
# than imported from build_panel.py — importing them would gate the builder
# against itself. Wording is final (work order model-page-v2, 2026-07-30;
# disclaimer from `JMA Web Report Template.dc.html`).
TOP_BANNER = ("The charts and data on this page are free to use and reproduce "
              "with attribution to Japan Macro Advisors.")
BOTTOM_BANNER = ("The charts and data on this page are free to use and "
                 "reproduce with attribution to Japan Macro Advisors. Paid "
                 "subscribers receive the Excel workbooks behind each report, "
                 "regular outputs from this yield curve model, updated "
                 "estimates on request, and priority replies in English or "
                 "Japanese.")
DISCLAIMER = ("This report is provided for information purposes only. It "
              "does not constitute investment advice or an offer or "
              "solicitation to buy or sell any security. While the "
              "information herein is believed to be reliable, Japan Macro "
              "Advisors makes no representation as to its accuracy or "
              "completeness. &copy; 2026 Japan Macro Advisors. "
              "All rights reserved.")

# The model page carries its own approved bottom-banner wording (Takuji,
# 2026-07-30 — paid-access + update-on-request terms); article panels keep
# the generic subscriber line above.
MODEL_BOTTOM_BANNER = (
    "The charts and data on this page are free to use and reproduce with "
    "attribution to Japan Macro Advisors. Only paid subscribers have access "
    "to this page. We will update our yield curve model estimates "
    "periodically, but in case the published estimate is more than 2 weeks "
    "old, paid subscribers can request an updated estimate and we should be "
    "able to reply within 2 business days.")

BOTTOM_BANNERS = {"jgb-yield-curve-model": MODEL_BOTTOM_BANNER}


def qa_skin(page, bottom_banner) -> None:
    """The Web Report page identity — same fixed blocks on every panel page,
    with the bottom-banner wording checked against this page's approved text."""
    print("\nPage skin (fixed blocks)")
    gate("../assets/jma-logo.png" in page
         and "Unbiased Opinion on Japan&rsquo;s Economy" in page,
         "masthead: logo + tagline present")
    gate("fonts.googleapis.com/css2?family=PT+Serif" in page
         and "Public+Sans" in page, "PT Serif / Public Sans loaded")
    gate("background:#FCFBF8" in page, "warm-white page background token")
    gate("border:1px solid #e4e2da" in page, "figure frame token present")
    gate(page.count(TOP_BANNER) == 2,
         "free-to-use line present top and bottom")
    gate(bottom_banner in page,
         "bottom banner carries this page's approved wording")
    gate('href="https://takujiokubo.substack.com/subscribe"' in page,
         "subscribe link present")
    gate(DISCLAIMER in page, "disclaimer wording verbatim from the template")
    gate(page.index('class="banner top"') < page.index("<header"),
         "top banner sits under the masthead, above the title")
    gate(page.index('class="banner bottom"') < page.index('class="disclaimer"'),
         "bottom banner sits above the disclaimer")


def qa_long_climb(root, manifest, page, figs) -> None:
    # ---- chart 1: 20Y / 40Y par yields ------------------------------------
    print("\nChart 1 — 20Y/40Y par yields")
    f1 = figs["chart_1"]
    src20, src40 = col(root, manifest["charts"][0]["csv"], "jgb_20y_d"), \
                   col(root, manifest["charts"][0]["csv"], "jgb_40y_d")
    t20, t40 = trace(f1, "20Y"), trace(f1, "40Y")
    gate(sum(1 for y in t20["y"] if y is not None) == len(src20),
         "20Y point count matches CSV", f"{len(src20)} points")
    gate(sum(1 for y in t40["y"] if y is not None) == len(src40),
         "40Y point count matches CSV", f"{len(src40)} points")
    gate(t40["y"][0] is None and t40["connectgaps"] is False,
         "40Y pre-2007 gap is null, not zero")
    gate(abs(t40["y"][-1] - 3.801) < 1e-9, "40Y last value = published 3.801%",
         f"{t40['y'][-1]}")
    gate(any(s["y0"] == 4.0 for s in f1["layout"].get("shapes", [])),
         "4% reference line drawn")

    # ---- chart 2: 30Y spot, windowed --------------------------------------
    print("\nChart 2 — 30Y spot, three markets")
    f2 = figs["chart_2"]
    gate(f2["data"][0]["x"][0] >= "2017-12-31",
         "window honoured (starts end-2017, not 2000)", f2["data"][0]["x"][0])
    gate(len(f2["data"]) == 3, "three markets plotted")
    gate(abs(trace(f2, "JGBs")["y"][-1] - 4.200) < 0.001,
         "JGB 30Y June-end = 4.1998 published", f"{trace(f2,'JGBs')['y'][-1]}")

    # ---- chart 3: 40Y stabilization ---------------------------------------
    print("\nChart 3 — 40Y stabilization")
    f3 = figs["chart_3"]
    ys = [y for y in f3["data"][0]["y"] if y is not None]
    xs = f3["data"][0]["x"]
    peak_i = max(range(len(ys)), key=lambda i: ys[i])
    gate(abs(max(ys) - 4.043) < 1e-9, "peak = published 4.043%", f"{max(ys)}")
    gate(xs[peak_i] == "2026-05-19", "peak date = published 19 May 2026", xs[peak_i])
    gate(abs(ys[-1] - 3.801) < 1e-9, "last = published 3.801%", f"{ys[-1]}")

    # ---- chart 4: natural-rate anchor, year-end bars -----------------------
    print("\nChart 4 — natural-rate anchor")
    f4 = figs["chart_4"]
    src = list(csv.DictReader(open(root / manifest["charts"][3]["csv"],
                                   newline="", encoding="utf-8-sig")))
    years = sorted({r["ym"][:4] for r in src})
    tpi = trace(f4, "π* (10Y inflation expectations)")
    gate(tpi["x"] == years, "one bar per year, year-end sampled",
         f"{len(years)} years from {len(src)} monthly rows")
    gate(f4["layout"]["barmode"] == "group", "bars grouped, not stacked")
    last = [r for r in src if r["ym"][:4] == years[-1]][-1]
    gate(abs(tpi["y"][-1] - round(float(last["pi_star_10y"]), 2)) < 1e-9,
         "latest π* matches the year's last monthly row", f"{tpi['y'][-1]}")
    gate(abs(trace(f4, "i* = r* + π*")["y"][-1] - 1.86) < 0.005,
         "latest i* = published 1.86%", f"{trace(f4,'i* = r* + π*')['y'][-1]}")
    gate("provisional" not in [t["name"] for t in f4["data"]],
         "boolean flag column not plotted as a series")
    ops = tpi["marker"]["opacity"]
    gate(ops[-1] < 1.0 and ops[0] == 1.0, "provisional years faded, measured ones not")

    # ---- chart 5: TP 10Y, basis points ------------------------------------
    print("\nChart 5 — 10Y term premium")
    f5 = figs["chart_5"]
    gate("bp" in f5["layout"]["yaxis"]["title"]["text"], "y-axis states basis points")
    jma, acm = trace(f5, "JMA model"), trace(f5, "Standard ACM")
    gate(abs(jma["y"][-1] - 64.07) < 1e-9 and abs(acm["y"][-1] - 124.14) < 1e-9,
         "latest values match CSV", f"JMA {jma['y'][-1]}bp, ACM {acm['y'][-1]}bp")

    # ---- chart 6: TP 30Y/40Y, windowed ------------------------------------
    print("\nChart 6 — 30Y/40Y term premium")
    f6 = figs["chart_6"]
    gate(f6["data"][0]["x"][0] == "2010-01-01",
         "window honoured (starts 2010, not 2006)", f6["data"][0]["x"][0])
    gate(abs(trace(f6, "30Y")["y"][-1] - 2.070) < 0.001
         and abs(trace(f6, "40Y")["y"][-1] - 1.876) < 0.001,
         "latest = published 30Y 2.070% / 40Y 1.876%",
         f"{trace(f6,'30Y')['y'][-1]} / {trace(f6,'40Y')['y'][-1]}")

    # ---- chart 7: forecast table ------------------------------------------
    print("\nChart 7 — forecast table")
    src7 = list(csv.DictReader(open(root / manifest["charts"][6]["csv"],
                                    newline="", encoding="utf-8-sig")))
    gate(page.count("<tr") == len(src7) + 1, "every table row rendered",
         f"{len(src7)} data rows + header")
    for r in src7:
        row_ok = all(f">{r[t]}</td>" in page for t in ["5Y", "10Y", "20Y", "30Y", "40Y"])
        gate(row_ok, f"row '{r['label']}' values present verbatim")
    gate('class="rule"' in page, "actual/forecast rule drawn")

    # ---- charts 8-11: the decomposition follow-ups -------------------------
    # These carry claims in their captions ("of the 2.55pp rise ... 1.89pp is
    # expectations"). A caption is a number like any other and gets a gate:
    # recomputed here from what the page actually plots.
    print("\nCharts 8-11 — decomposition at each maturity")
    claimed = {                     # tenor: (rise, from expectations, from TP)
        "10Y": (2.55, 1.89, 0.66),
        "20Y": (3.15, 1.83, 1.31),
        "30Y": (3.47, 1.71, 1.76),
        "40Y": (3.26, 1.65, 1.61),
    }
    for n, tenor in zip(range(8, 12), ["10Y", "20Y", "30Y", "40Y"]):
        f = figs[f"chart_{n}"]
        bars = [t for t in f["data"] if t["type"] == "bar"]
        lines = [t for t in f["data"] if t["type"] == "scatter"]
        total = [a if a is not None else b for a, b in zip(lines[0]["y"], lines[1]["y"])]
        rn, tp = bars[0]["y"], bars[1]["y"]

        breaks = sum(1 for i in range(len(total))
                     if None not in (total[i], rn[i], tp[i])
                     and abs(total[i] - (rn[i] + tp[i])) > 2e-3)
        gate(not breaks, f"{tenor}: yield = expectations + term premium throughout")

        xs = [x[:7] for x in lines[0]["x"]]
        i0, i1 = xs.index("2022-01"), xs.index("2026-07")
        got = (total[i1] - total[i0], rn[i1] - rn[i0], tp[i1] - tp[i0])
        want = claimed[tenor]
        off = max(abs(g - w) for g, w in zip(got, want))
        gate(off <= 0.006,
             f"{tenor}: the caption's 2022-26 split matches the plotted data",
             f"rise {got[0]:.2f} / exp {got[1]:.2f} / TP {got[2]:.2f}pp")
        gate(f["layout"]["barmode"] == "relative", f"{tenor}: relative stacking")

    f40 = figs["chart_11"]
    t40 = [t for t in f40["data"] if t["type"] == "bar"][1]
    first = next(i for i, v in enumerate(t40["y"]) if v is not None)
    gate(t40["x"][first][:7] == "2007-11",
         "40Y decomposition starts at first issuance, Nov 2007", t40["x"][first][:7])
    gate("Behind the article" in page, "section divider rendered before chart 8")


TP_COLORS = {"5Y": "#A8CEEE", "10Y": "#378ADD", "20Y": "#888780",
             "30Y": "#D85A30", "40Y": "#EF9F27"}



MODEL_TITLES = [
    "10-year JGB yield: risk-neutral component and term premium",
    "5-year JGB yield: risk-neutral component and term premium",
    "20-year JGB yield: risk-neutral component and term premium",
    "30-year JGB yield: risk-neutral component and term premium",
    "40-year JGB yield: risk-neutral component and term premium",
    "Spot yield curve: current estimate and forecast year-ends",
    "Forecast table: spot yields to 2029",
    "Term premia by maturity: 5 to 40 years",
    "Policy rate and risk-neutral rates: 2-year and 10-year",
]
ACM_TITLE = "10-year term premium: standard ACM versus JMA model"


def qa_yield_curve(root, manifest, page, figs) -> None:
    """The model page: decomposition-led run, curve + forecast table, TP and
    policy charts, with the ACM comparison embedded in the About section."""
    panel = list(csv.DictReader(open(
        root / "data/jma-jgb-yield-curve-panel.csv",
        newline="", encoding="utf-8-sig")))
    by_ym = {r["YM"]: r for r in panel}

    print("\nTitles and order")
    h2s = re.findall(r"<h2>(.*?)</h2>", page)
    gate(h2s[:9] == MODEL_TITLES,
         "the nine main exhibits run in the agreed order",
         str([t[:22] for t in h2s[:9]]))
    gate(h2s[9:11] == ["About the model", ACM_TITLE],
         "ACM chart is embedded inside the About section")
    gate('href="jgb-yield-curve-model/"' in
         (REPO / "index.html").read_text(encoding="utf-8"),
         "model page listed on the landing page")

    print("\nDecomposition at each maturity")
    for cid, tenor in zip(range(1, 6), ["10Y", "5Y", "20Y", "30Y", "40Y"]):
        f = figs[f"chart_{cid}"]
        bars = [t for t in f["data"] if t["type"] == "bar"]
        lines = [t for t in f["data"] if t["type"] == "scatter"]
        total = [a if a is not None else b
                 for a, b in zip(lines[0]["y"], lines[1]["y"])]
        rn, tp = bars[0]["y"], bars[1]["y"]
        breaks = sum(1 for i in range(len(total))
                     if None not in (total[i], rn[i], tp[i])
                     and abs(total[i] - (rn[i] + tp[i])) > 2e-3)
        gate(not breaks and f["layout"]["barmode"] == "relative",
             f"{tenor}: yield = expectations + term premium, relative stack",
             f"{sum(1 for v in total if v is not None)} points")
    t40 = [t for t in figs["chart_5"]["data"] if t["type"] == "bar"][1]
    first = next(i for i, v in enumerate(t40["y"]) if v is not None)
    gate(t40["x"][first][:7] == "2007-11" and
         all(v is None for v in t40["y"][:first]),
         "40Y decomposition starts Nov 2007, nulls before")

    print("\nCurve, table, TP and policy charts")
    f6 = figs["chart_6"]
    tenors = [2, 5, 10, 20, 30, 40]
    for ln in manifest["charts"][5]["lines"]:
        t = trace(f6, ln["label"])
        src = [round(float(by_ym[ln["ym"]][f"Yield_{n}Y"]), 3) for n in tenors]
        gate(t["y"] == src, f"curve {ln['label']}: matches the panel row")
    ft = list(csv.DictReader(open(
        root / "data/jgb-spot-yield-forecast.csv",
        newline="", encoding="utf-8-sig")))
    gate(page.count("<tr") == len(ft) + 1, "every table row rendered")
    gate(page.index(">Spot yield curve:") < page.index(">Forecast table:")
         < page.index(">Term premia by maturity:"),
         "curve → table → TP chart order on the page")

    f7 = figs["chart_7"]
    for lbl, want in TP_COLORS.items():
        legs = [t for t in f7["data"] if t["name"] == lbl]
        gate(bool(legs) and all(t["line"]["color"] == want for t in legs),
             f"TP {lbl} drawn in {want}")
    t5h, t5p = [t for t in f7["data"] if t["name"] == "5Y"]
    tp5 = [a if a is not None else b for a, b in zip(t5h["y"], t5p["y"])]
    bad = sum(1 for i, v in enumerate(tp5) if v is not None and abs(
        v - (float(by_ym[t5h["x"][i][:7]]["Yield_5Y"])
             - float(by_ym[t5h["x"][i][:7]]["RN_5Y"]))) > 2e-3)
    gate(not bad, "TP chart: identity holds on every plotted 5Y point",
         f"{sum(1 for v in tp5 if v is not None)} points")
    gate(len({t["name"] for t in figs["chart_8"]["data"]}) == 3,
         "policy chart carries its three series")

    print("\nACM in the About section")
    gate(manifest["charts"][9]["csv"]
         == "../2026-07-20-long-climb/data/chart-5-tp-10y-jma-vs-acm.csv",
         "single-copy pattern: reads the Long Climb CSV by relative path")
    _, lc_figs = load_delivered(REPO / "2026-07-20-long-climb")
    for name in ("JMA model", "Standard ACM"):
        tm, tl = trace(figs["chart_9"], name), trace(lc_figs["chart_5"], name)
        gate(tm["x"] == tl["x"] and tm["y"] == tl["y"],
             f"{name}: numerically identical to the Long Climb copy")
    jma = trace(figs["chart_9"], "JMA model")
    v = jma["y"][jma["x"].index("2026-07-01")] / 100
    gate(0.6 <= v <= 0.7,
         "About's 0.6%-0.7% claim brackets the delivered mid-July 10Y TP",
         f"{v:.4f}%")
    gate("The chart below shows the difference." in page
         and "The chart above shows the difference." not in page,
         "block 2 says 'below' — the chart follows the paragraph")
    gate(page.index("significantly overestimate the premium")
         < page.index(ACM_TITLE)
         < page.index("<strong>What goes in.</strong>"),
         "ACM card sits between About blocks 2 and 3")

    print("\nPage texts")
    gate("Model vintage: 19 July 2026. Estimates are revised periodically, "
         "and updated estimates are available for paid users upon request."
         in page, "vintage stamp verbatim")
    gate('href="https://takujiokubo.substack.com/p/'
         'the-long-climb-in-jgb-yields-is-nearly"' in page,
         "intro links the report")
    for head in ["What the model is.", "Why we do not use a standard model.",
                 "What goes in.", "What we publish, and what we do not."]:
        gate(f"<strong>{head}</strong>" in page, f"About block: {head}")
    for ref, anchor in [
        ("Adrian, Crump &amp; Moench (2013)", "term-premia-tabs"),
        ("Bauer &amp; Rudebusch (2020)", "Interest Rates Under Falling Stars"),
        ("Bank of Japan Monetary Affairs Department", "rev26e04.htm"),
        ("Osada &amp; Nakazawa (BoJ, 2024)", "rev24e04.htm"),
    ]:
        gate(ref in page and anchor in page, f"reference present: {ref[:24]}…")
    gate("around 1.2%" in page, "the report's 1.2% standard-ACM figure quoted")


QA = {"2026-07-20-long-climb": qa_long_climb,
      "jgb-yield-curve-model": qa_yield_curve}


def main(slug: str) -> int:
    root = REPO / slug
    manifest = json.loads((root / "panel.json").read_text(encoding="utf-8"))
    page, figs = load_delivered(root)
    print(f"QA {slug} — {len(manifest['charts'])} exhibits\n")
    qa_structure(manifest, page, figs)
    qa_skin(page, BOTTOM_BANNERS.get(slug, BOTTOM_BANNER))
    if slug not in QA:
        print(f"\n  ! no article-specific gates for {slug} — structure only.")
        print("    Add them: the gates that matter check the drawn values "
              "against the figures the article prints.")
    else:
        QA[slug](root, manifest, page, figs)

    print()
    if FAILED:
        print(f"{len(FAILED)} GATE(S) FAILED: {FAILED}")
        return 1
    print("all gates pass")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1] if len(sys.argv) > 1 else "2026-07-20-long-climb"))
