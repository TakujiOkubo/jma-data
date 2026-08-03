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
                 "subscribers have access to our Yield Curve Model estimate "
                 "output, including historical term premia decomposition "
                 "estimates as well as our forecasts that are periodically "
                 "updated. Paid subscribers are encouraged to send questions "
                 "on my research and receive priority in my replies in "
                 "either English or Japanese.")
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

    # The decomposition follow-ups (former charts 8-11) were removed
    # 2026-07-30: the page is the free public teaser, and the decomposition
    # is now the paid model page's content.
    gate("Behind the article" not in page,
         "the model-output section is gone (teaser page carries the "
         "published exhibits only)")


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
ANCHOR_TITLE = ("The long-run rate anchor: equilibrium real rate plus trend "
                "inflation expectations")


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
    gate(h2s[9:12] == ["About the model", ANCHOR_TITLE, ACM_TITLE],
         "anchor and ACM charts are embedded inside the About section")
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

    print("\nAnchor chart in the About section")
    _, lc_figs = load_delivered(REPO / "2026-07-20-long-climb")
    gate(manifest["charts"][9]["csv"]
         == "../2026-07-20-long-climb/data/chart-4-natural-rate-anchor.csv",
         "single-copy pattern: reads the Long Climb CSV by relative path")
    for name in ("π* (10Y inflation expectations)", "r* (equilibrium real rate)",
                 "i* = r* + π*"):
        tm, tl = trace(figs["chart_9"], name), trace(lc_figs["chart_4"], name)
        gate(list(tm["x"]) == list(tl["x"]) and list(tm["y"]) == list(tl["y"]),
             f"{name}: numerically identical to the Long Climb copy")
    gate(page.index("last era of free JGB pricing")
         < page.index(ANCHOR_TITLE)
         < page.index("<strong>Why we do not use a standard model.</strong>"),
         "anchor card sits between About blocks 1 and 2")
    gate("100bp" not in page and "rose by" not in page,
         "no pace claim in the softened anchor title")

    print("\nACM in the About section")
    gate(manifest["charts"][10]["csv"]
         == "../2026-07-20-long-climb/data/chart-5-tp-10y-jma-vs-acm.csv",
         "single-copy pattern: reads the Long Climb CSV by relative path")
    for name in ("JMA model", "Standard ACM"):
        tm, tl = trace(figs["chart_10"], name), trace(lc_figs["chart_5"], name)
        gate(tm["x"] == tl["x"] and tm["y"] == tl["y"],
             f"{name}: numerically identical to the Long Climb copy")
    jma = trace(figs["chart_10"], "JMA model")
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
    gate('href="https://takujiokubo.substack.com/p/'
         'japans-fiscal-vigilantes-are-mis"' in page,
         "What-goes-in links the curve-shape report")
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


# The chart library's own copies. A panel CSV that has drifted from the file
# the published PNG was drawn from is the one failure that cannot be seen by
# looking at the page, so it is checked byte-for-byte where the library is
# mounted, and skipped (loudly) where it is not.
LIBRARY = Path(r"G:\My Drive\charts")
FX_SOURCES = {
    "data/chart-1-world-fx-reserves-top-holders.csv":
        "global-reserves/top-holders/world_fx_reserves_top_holders_data.csv",
    "data/chart-2-usd-reserve-share-alloc.csv":
        "global-reserves/usd-reserve-share-alloc/usd_reserve_share_alloc_data.csv",
    "data/chart-3-jpn-fx-intervention-history.csv":
        "global-reserves/jpn-fx-intervention-history/jpn_fx_intervention_history_data.csv",
}


def qa_fx_carry_unwind(root, manifest, page, figs) -> None:
    """The FX carry-unwind panel: reserve league table, the dollar's reserve
    share, and 35 years of intervention against USD/JPY.

    The gates that matter are the ones the article can be checked against —
    every level and every date it prints — plus the two chart forms this panel
    introduced, where a plausible-looking drawing would be the easiest way to
    ship something that is not the published chart.
    """
    print("\nSource CSVs")
    for local, lib in FX_SOURCES.items():
        src = LIBRARY / lib
        if not src.exists():
            print(f"  SKIP  library not mounted — cannot check {local}")
            continue
        gate((root / local).read_bytes() == src.read_bytes(),
             f"{local.split('/')[-1]} is the chart library's file, unmodified")

    # ---- chart 1: the reserve league table, two panels ---------------------
    print("\nChart 1 — top FX reserve holders, level and % of GDP")
    f1 = figs["chart_1"]
    lvl, pct = f1["data"][0], f1["data"][1]
    src1 = list(csv.DictReader(open(root / manifest["charts"][0]["csv"],
                                    newline="", encoding="utf-8-sig")))
    ref = max(int(r["year"]) for r in src1)
    gate(ref == 2025, "reference year is end-2025, as the headline says", str(ref))
    gate(lvl["y"] == pct["y"],
         "both panels carry the same holders in the same order",
         "the re-ordering between them is the chart's point")
    gate(len(lvl["y"]) == 10, "top ten plotted", f"{len(lvl['y'])} rows")
    gate(lvl["x"] == sorted(lvl["x"], reverse=True),
         "ranked by the level panel, descending")
    # Russia's IMF figure stops a year early; plotting it here would put two
    # vintages in one bar chart, which is the failure the chart script guards.
    stale = [r["country"] for r in src1 if int(r["year"]) != ref]
    gate(all(c not in lvl["y"] for c in stale),
         "economies on an older vintage stay out of the panels",
         f"excluded: {', '.join(stale) or 'none'}")
    for country, level, share in (("China", 3357.9, 17.1), ("Japan", 1180.5, 26.6),
                                  ("Switzerland", 914.7, 87.6)):
        i = lvl["y"].index(country)
        gate(abs(lvl["x"][i] - level) < 1e-9 and abs(pct["x"][i] - share) < 1e-9,
             f"{country} = ${level:,.1f}bn / {share}% of GDP",
             f"{lvl['x'][i]} / {pct['x'][i]}")
    gate(lvl["y"].index("Japan") == 1,
         "Japan ranks 2nd, as the headline and the article both say")
    gate(lvl["y"][2] == "Switzerland" and abs(lvl["x"][2] - 914.7) < 1e-9,
         "Switzerland 3rd at $915bn, the article's comparison")
    gate(lvl["text"][0] == "3,358" and lvl["text"][1] == "1,180"
         and pct["text"][lvl["y"].index("Hong Kong")] == "100%",
         "value labels carry the scale (no x-axis ticks)")
    gate(not any(f1["layout"][a]["showgrid"]
                 for a in ("xaxis", "xaxis2", "yaxis", "yaxis2")),
         "no gridlines: on horizontal bars they would run vertical")
    gate(f1["layout"]["xaxis"]["domain"][1] <= f1["layout"]["xaxis2"]["domain"][0],
         "the two panels sit side by side, not overlaid")
    nar = f1.get("narrow")
    gate(bool(nar) and nar["layout"]["xaxis.domain"] == [0, 1]
         and nar["layout"]["yaxis.domain"][0] > nar["layout"]["yaxis2.domain"][1],
         "phone width stacks the panels instead of shrinking them")

    # ---- chart 2: the dollar's share of allocated reserves ------------------
    print("\nChart 2 — USD share of allocated FX reserves")
    f2 = figs["chart_2"]
    xs, ys = f2["data"][0]["x"], f2["data"][0]["y"]
    gate(xs[0].startswith("1995"),
         "window honoured (starts 1995 on the COFER basis, not 1980)", xs[0])
    by_year = dict(zip((x[:4] for x in xs), ys))
    gate(69.0 <= by_year["1999"] <= 72.0,
         "1999 is the article's 'about 70%'", f"{by_year['1999']}%")
    below = [y for y, v in sorted(by_year.items()) if v < 60.0]
    gate(below and below[0] == "2020" and len(below) == len(
         [y for y in sorted(by_year) if y >= "2020"]),
         "below 60% from 2020 onward and never back above — the article's claim",
         f"first year under 60: {below[0] if below else 'none'}")
    gate(ys[-1] == min(ys), "the last observation is the 30-year low of the title",
         f"{ys[-1]}% in {xs[-1][:4]}")

    # ---- chart 3: 35 years of intervention against USD/JPY -----------------
    print("\nChart 3 — intervention history")
    f3 = figs["chart_3"]
    buys = trace(f3, "Japan buys USD (sells yen)")
    sells = trace(f3, "Japan sells USD (buys yen)")
    line = trace(f3, "USD/JPY (right axis)")
    gate(all(v > 0 for v in buys["y"]) and all(v < 0 for v in sells["y"]),
         "sign separates the two directions — no bar on the wrong side")
    gross_sell = round(sum(buys["y"]), 2)
    gate(abs(gross_sell - 80.90) < 0.05,
         "gross yen-selling matches MOF's ¥80.9trn", f"¥{gross_sell}trn")
    gate(buys["x"][-1][:4] == "2011",
         "the last dollar purchase is 2011, as the article says", buys["x"][-1])
    quiet = [x for x in buys["x"] + sells["x"] if "2012" <= x[:4] <= "2021"]
    gate(not quiet, "no intervention 2012-2021 — the article's 'not once'",
         f"{len(quiet)} bars found in the window")
    gate(abs(sells["y"][-1] + 16.0) < 1e-9 and sells["x"][-1] == "2026-07-01",
         "the 30-31 July operation is the last bar, ¥16trn (~$100bn at ~¥160)",
         f"{sells['y'][-1]} at {sells['x'][-1]}")
    gate(abs(sells["y"][-2] + 11.7349) < 1e-9,
         "the April-May window is MOF's announced ¥11.73trn", f"{sells['y'][-2]}")
    ops = sells["marker"].get("opacity", [])
    gate(len(ops) == len(sells["y"]) and ops[-1] < 1.0
         and all(o == 1.0 for o in ops[:-1]),
         "only the provisional July bar is faded — the rest are MOF's record")
    gate(line["yaxis"] == "y2", "USD/JPY reads on the right axis")
    gate(abs(line["y"][-1] - 162.19) < 1e-9,
         "USD/JPY ends at the 2026Q3 average, above the ¥160 of the title",
         f"¥{line['y'][-1]}")
    gate(abs(min(line["y"]) - 77.31) < 1e-9,
         "the trough is the 2011 quarter Japan bought into", f"¥{min(line['y'])}")
    book = [s for s in f3["layout"]["shapes"]
            if s["yref"] == "y2" and s["line"].get("dash") == "dash"]
    gate(len(book) == 1 and book[0]["y0"] == 114.0,
         "the ¥114 book cost is drawn on the rate axis, dashed",
         "the report's own estimate, range ¥110-120")
    gate(any("114" in a["text"] for a in f3["layout"].get("annotations", [])),
         "the book-cost line is labelled")
    lay = f3["layout"]
    gate(lay["yaxis"]["range"] == [-19, 50] and lay["yaxis2"]["range"] == [-36, 171],
         "the axis offset is preserved: bars in the lower band, rate in the upper")
    gate(lay["yaxis2"]["showgrid"] is False,
         "only one axis carries gridlines")

    # ---- the page is the public teaser ------------------------------------
    print("\nTier")
    gate("Only paid subscribers" not in page,
         "public teaser: no paid-access banner on this page")


# --------------------------------------------------- scenario forecast pages
# The scenario table restated independently of make_scenario_data.py. Gating a
# page against the script that cut it would only prove the script is
# self-consistent; these figures come from the settled taxonomy (vault note
# scenario-naming-main-alternative-2026-08-02.md) and from the forecast tables
# printed in fan-sigma-12m-impact-2026-08-02.md.
RUNS = Path(r"G:\My Drive\Research\JGB_related\JGByieldcurve_forecast\runs")

SCENARIO = {
    "jgb-forecast-main": dict(
        name="Main Forecast",
        run="fan-sigma-after-v307",
        sibling="jgb-forecast-alternative",
        hikes=[("2026-10", 1.25), ("2027-03", 1.50)],
        terminal=1.50,
        # bp, from the note's V30.7 base forecast table
        printed={"2026-12": dict(Y10=312.1, Y20=399.5, Y30=447.2, Y40=440.6),
                 "2027-12": dict(Y10=328.2, Y20=380.2, Y30=402.4, Y40=408.4),
                 "2028-12": dict(Y10=314.0, Y20=369.0, Y30=381.0, Y40=392.6),
                 "2029-07": dict(Y10=312.6, Y20=367.4, Y30=379.5, Y40=391.2)},
    ),
    "jgb-forecast-alternative": dict(
        name="Alternative Forecast: Faster and Further",
        run="fan-sigma-after-v306",
        sibling="jgb-forecast-main",
        hikes=[("2026-09", 1.25), ("2027-03", 1.50), ("2027-12", 1.75)],
        terminal=1.75,
        # bp, from the note's V30.6 base forecast table
        printed={"2026-12": dict(Y10=306.6, Y20=397.3, Y30=445.5, Y40=439.3),
                 "2027-12": dict(Y10=344.6, Y20=391.0, Y30=410.6, Y40=415.0),
                 "2028-12": dict(Y10=336.1, Y20=379.8, Y30=389.3, Y40=399.2),
                 "2029-07": dict(Y10=327.2, Y20=378.1, Y30=387.8, Y40=397.8)},
    ),
}

# Horizon-end fan half-widths in bp, and the sigma behind them, as published in
# fan-sigma-12m-impact-2026-08-02.md. Identical on both scenarios by
# construction: sigma depends on US data only, not the BoJ path.
FAN_HALFWIDTH_2029 = {"10Y": 17.4, "20Y": 21.7, "30Y": 19.8, "40Y": 19.0}
SIGMA10_BP = 77.5
USTP_PEAK = ("2026-11", 122.2)
USTP_TERMINAL = ("2029-07", 94.5)
BAND = "±1 s.d. range"


def _run_rows(spec, which):
    stem = spec["run"]
    name = {"curve": "consolidated_curve", "fcst": "stage3_forecast"}[which]
    with open(RUNS / stem / f"{stem}_{name}.csv",
              newline="", encoding="utf-8-sig") as f:
        return list(csv.DictReader(f))


def qa_scenario_forecast(root, manifest, page, figs) -> None:
    """A scenario forecast page. The gates that matter here are (a) that the
    page is labelled with the scenario it actually carries — the branch version
    numbers invert the scenario rank, so a page mislabelled from a branch name
    would look entirely plausible — and (b) that the delivered numbers
    re-derive from the production run directory, not merely from the CSV this
    repo cut from it."""
    slug = manifest["slug"]
    spec = SCENARIO[slug]
    panel = list(csv.DictReader(open(root / "data/curve-panel.csv",
                                     newline="", encoding="utf-8-sig")))
    by_ym = {r["YM"]: r for r in panel}

    # ---- scenario identity: the inversion trap ----------------------------
    print("\nScenario identity")
    gate(spec["name"] in manifest["title"],
         f"page is titled as the {spec['name']}")

    src = {r["YM"].strip(): r for r in _run_rows(spec, "curve")}
    steps, prev = [], None
    pol = trace(figs["chart_5"], "BoJ policy rate")
    drawn = [t for t in figs["chart_5"]["data"] if t["name"] == "BoJ policy rate"]
    merged = [a if a is not None else b
              for a, b in zip(drawn[0]["y"], drawn[1]["y"])]
    xs = [x[:7] for x in pol["x"]]
    for ym, v in zip(xs, merged):
        if v is not None and prev is not None and abs(v - prev) > 1e-4 \
                and v > 1.0 + 1e-6:
            steps.append((ym, round(v, 2)))
        if v is not None:
            prev = v
    gate(steps == [(ym, r) for ym, r in spec["hikes"]],
         "the DELIVERED policy path carries exactly the declared hikes",
         str(steps))
    gate(abs(merged[-1] - spec["terminal"]) < 1e-6,
         f"terminal rate on the page is {spec['terminal']:.2f}%",
         f"{merged[-1]:.4f}")
    for ym, rate in spec["hikes"]:
        gate(f"{ym[:4]}" in page, f"hike year {ym[:4]} appears in the page text")
    month = {"01": "January", "02": "February", "03": "March", "04": "April",
             "05": "May", "06": "June", "07": "July", "08": "August",
             "09": "September", "10": "October", "11": "November",
             "12": "December"}
    for ym, _ in spec["hikes"]:
        want = f"{month[ym[5:7]]} {ym[:4]}"
        gate(want in page,
             f"assumptions text names the {want} increase")
    gate(f"{spec['terminal']:.2f} per cent" in page,
         f"assumptions text states the {spec['terminal']:.2f}% terminal rate")

    # ---- the delivered numbers re-derive from the production run ----------
    print("\nAgainst the production run directory")
    bad = 0
    for ym, r in by_ym.items():
        s = src.get(ym)
        if not s:
            bad += 1
            continue
        for t in ("2Y", "5Y", "10Y", "20Y", "30Y", "40Y"):
            a, b = (r[f"Yield_{t}"] or "").strip(), (s[f"Yield_{t}"] or "").strip()
            if a == "" and b == "":
                continue
            if a == "" or b == "" or abs(float(a) - float(b)) > 5e-5:
                bad += 1
    gate(not bad, f"every yield in the page CSV matches {spec['run']}",
         f"{len(by_ym)} months x 6 maturities")

    fc = _run_rows(spec, "fcst")
    fan_src = {}
    for r in fc:
        fan_src.setdefault((r["YM"].strip(), r["Tenor"].strip()),
                           {})[r["Scenario"].strip()] = float(r["Y_fcst"])
    bad = 0
    for (ym, t), legs in fan_src.items():
        r = by_ym.get(ym)
        if r is None:
            bad += 1
            continue
        for side, colname in (("up", "Fan_hi"), ("down", "Fan_lo")):
            v = (r[f"{colname}_{t}"] or "").strip()
            if v == "" or abs(float(v) - legs[side]) > 5e-5:
                bad += 1
    gate(not bad, "every fan bound matches the run's stage-3 forecast",
         f"{len(fan_src)} month-tenor pairs")

    # ---- the fan ----------------------------------------------------------
    print("\nUncertainty band")
    for cid, tenor in ((1, "10Y"), (2, "30Y")):
        f = figs[f"chart_{cid}"]
        edges = [t for t in f["data"] if t["name"] == BAND]
        gate(len(edges) == 2, f"chart {cid}: band drawn as two edges")
        hi, lo = edges
        gate(lo.get("fill") == "tonexty" and hi.get("line", {}).get("width") == 0,
             f"chart {cid}: lower edge fills up to the invisible upper edge")
        xs = [x[:7] for x in hi["x"]]
        idx = {x: i for i, x in enumerate(xs)}
        got = (hi["y"][idx["2029-07"]] - lo["y"][idx["2029-07"]]) / 2 * 100
        gate(abs(got - FAN_HALFWIDTH_2029[tenor]) < 0.1,
             f"{tenor}: horizon-end half-width is "
             f"±{FAN_HALFWIDTH_2029[tenor]}bp as published", f"±{got:.1f}bp")
        # The band must not appear over history: an uncertainty range drawn on
        # observations would be a straightforward misstatement.
        hist = [i for i, x in enumerate(xs)
                if by_ym[x]["Type"] == "actual" and x != "2026-07"]
        gate(all(hi["y"][i] is None and lo["y"][i] is None for i in hist),
             f"chart {cid}: no band over the observed period",
             f"{len(hist)} observed months")
        gate(hi["y"][idx["2026-07"]] == lo["y"][idx["2026-07"]],
             f"chart {cid}: band opens from the last observation at zero width")
        gate(all(t.get("hoverinfo") == "skip" for t in edges),
             f"chart {cid}: band edges stay out of the hover readout")

    f6 = figs["chart_6"]
    edges = [t for t in f6["data"] if t["name"] == BAND]
    xs6 = [x[:7] for x in edges[0]["x"]]
    i6 = {x: i for i, x in enumerate(xs6)}
    hw = (edges[0]["y"][i6["2029-07"]] - edges[1]["y"][i6["2029-07"]]) / 2
    gate(abs(hw - SIGMA10_BP) < 0.1,
         f"US TP fan half-width is the published sigma, {SIGMA10_BP}bp",
         f"{hw:.1f}bp")

    print("\nThe US term-premium assumption (shared by both scenarios)")
    assumed = trace(f6, "Assumed path")
    ia = {x[:7]: i for i, x in enumerate(assumed["x"])}
    for ym, want in (USTP_PEAK, USTP_TERMINAL):
        gate(abs(assumed["y"][ia[ym]] - want) < 0.1,
             f"assumed US TP at {ym} is {want}bp",
             f"{assumed['y'][ia[ym]]:.1f}bp")
    peak = max(v for v in assumed["y"] if v is not None)
    gate(abs(peak - USTP_PEAK[1]) < 0.1
         and assumed["x"][assumed["y"].index(peak)][:7] == USTP_PEAK[0],
         "the assumed path peaks where the assumption says it does")
    obs = trace(f6, "Observed (ACM)")
    gate(all(v is None for v in obs["y"][ia["2026-08"]:]),
         "the observed ACM series stops at the forecast origin")

    # ---- the published forecast tables ------------------------------------
    print("\nAgainst the printed forecast tables")
    ft = list(csv.DictReader(open(root / "data/forecast-table.csv",
                                  newline="", encoding="utf-8-sig")))
    ftr = {r["ym"]: r for r in ft}
    for ym, want in spec["printed"].items():
        for key, v in want.items():
            t = f"{key[1:]}Y"
            drawn = float(by_ym[ym][f"Yield_{t}"]) * 100
            gate(abs(drawn - v) < 0.06,
                 f"{ym} {t}: {v}bp as printed in the reference tables",
                 f"{drawn:.1f}bp")
        if ym in ftr:
            for key, v in want.items():
                t = f"{key[1:]}Y"
                gate(abs(float(ftr[ym][t]) * 100 - v) < 0.6,
                     f"forecast table {ym} {t} rounds to the printed figure",
                     f"{ftr[ym][t]}")
    gate(page.count("<tr") == len(ft) + 1, "every table row rendered")
    gate([r["kind"] for r in ft].count("actual") == 1,
         "exactly one actual-origin row above the rule")

    # ---- the curve chart ---------------------------------------------------
    print("\nCurve chart")
    f3 = figs["chart_3"]
    for ln in manifest["charts"][2]["lines"]:
        t = trace(f3, ln["label"])
        want = [round(float(by_ym[ln["ym"]][f"Yield_{n}Y"]), 3)
                for n in (2, 5, 10, 20, 30, 40)]
        gate(t["y"] == want, f"curve {ln['label']}: matches the panel row")

    # ---- relation to the model page and the sibling ------------------------
    print("\nSlim-page structure, sibling and tier")
    gate('href="../jgb-yield-curve-model/"' in page,
         "the model exposition is linked, not duplicated")
    gate("about" not in {c.get("kind") for c in manifest["charts"]}
         and 'class="about"' not in page,
         "no About/methodology section duplicated on this page")
    gate("It is seminal paper demostrating" not in page,
         "the report's reference list is not restated here")
    sib = manifest["sibling"]
    gate(sib["href"] == f'../{spec["sibling"]}/'
         and (REPO / spec["sibling"] / "index.html").exists(),
         "sibling link points at the other scenario page, which exists")
    gate(f'href="{sib["href"]}"' in page, "sibling link reaches the page")
    gate(manifest.get("unlisted") is True
         and f'href="{slug}/"' not in
         (REPO / "index.html").read_text(encoding="utf-8"),
         "unlisted: the page is not on the landing page")
    gate("Only paid subscribers" in page,
         "paid-access banner present (this is not a teaser page)")
    gate('class="assump"' in page and "What this forecast assumes" in page,
         "the assumptions block is on the page, above the charts")
    gate(page.index('class="assump"') < page.index('class="card"'),
         "assumptions are stated before any forecast number is shown")

    # ---- the two pages differ where they should, and only there -----------
    print("\nAgainst the sibling scenario")
    other = SCENARIO[spec["sibling"]]
    o_src = {r["YM"].strip(): r for r in _run_rows(other, "curve")}
    diff = sum(1 for ym in by_ym
               if ym in o_src and (src[ym]["Policy_Rate"] or "")
               != (o_src[ym]["Policy_Rate"] or ""))
    gate(diff > 0, "the two scenarios' policy paths genuinely differ",
         f"{diff} months")
    same = all(abs(float(src[ym]["US_TP10_base"]) -
                   float(o_src[ym]["US_TP10_base"])) < 5e-5
               for ym in by_ym
               if (src[ym]["US_TP10_base"] or "").strip()
               and (o_src[ym]["US_TP10_base"] or "").strip())
    gate(same, "the US term-premium assumption is identical on both scenarios")


QA = {"2026-07-20-long-climb": qa_long_climb,
      "jgb-yield-curve-model": qa_yield_curve,
      "2026-07-31-fx-carry-unwind": qa_fx_carry_unwind,
      "jgb-forecast-main": qa_scenario_forecast,
      "jgb-forecast-alternative": qa_scenario_forecast}

BOTTOM_BANNERS.update({s: MODEL_BOTTOM_BANNER for s in SCENARIO})


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
