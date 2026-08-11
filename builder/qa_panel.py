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
import html
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

    # What the page offers is gated in BOTH directions, so a page that offers
    # downloads and one that does not cannot drift into each other's state.
    #
    # The two keys are resolved here from the manifest rather than imported from
    # build_panel.py, deliberately: importing the rule would gate the builder
    # against itself. This restatement must be kept in step with the
    # "WHAT A PAGE OFFERS" block there.
    tier = manifest.get("tier")
    if "downloads" in manifest:
        downloads = manifest["downloads"]
    else:
        downloads = tier != "free"          # pre-2026-08-12 behaviour
    show_perk = tier == "free" and not downloads

    if not downloads:
        for c in manifest["charts"]:
            gate(f'href="{c["csv"]}"' not in page,
                 f"chart {c['n']} offers no CSV download")
        gate('class="dl"' not in page and "Download CSV" not in page,
             "no download control anywhere on the page")
        gate("Download the full workbook" not in page,
             "no workbook download on a page that offers none")
        gate("Each card links its own CSV" not in page,
             "closing line does not advertise a link that is not there")
    else:
        for c in manifest["charts"]:
            gate(f'href="{c["csv"]}"' in page, f"chart {c['n']} CSV link present")

    # Gated both ways. A page that hands out its data must not also advertise
    # that data as the thing a subscription buys -- which is the state a free
    # page with downloads would otherwise ship in.
    perk_present = ('class="perk"' in page
                    and "Paid subscribers receive the data behind every chart"
                    in page)
    gate(perk_present == show_perk,
         "perk block present exactly when the page offers no downloads and "
         f"declares tier free (expected {show_perk}, found {perk_present})")

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

# The reserves dataset carries its own approved wording: paid access, and an
# annual rather than on-request update cadence, because it moves once a year
# when the IMF closes its COFER year.
RESERVES_BOTTOM_BANNER = (
    "The charts and data on this page are free to use and reproduce with "
    "attribution to Japan Macro Advisors. Only paid subscribers have access "
    "to this page. The series are updated once a year, when the IMF closes "
    "its COFER year.")

# The paid tier of an article panel is a third case: it is a report's charts,
# not a standing dataset, so it keeps the per-card downloads but must not
# advertise the paid tier to a reader who is already inside it.
FXJPY_PAID_BOTTOM_BANNER = (
    "The charts and data on this page are free to use and reproduce with "
    "attribution to Japan Macro Advisors. Only paid subscribers have access "
    "to this page. Each card links the tidy CSV behind its chart. Paid "
    "subscribers are encouraged to send questions on my research and receive "
    "priority in my replies.")

BOTTOM_BANNERS = {"jgb-yield-curve-model": MODEL_BOTTOM_BANNER,
                  "global-fx-reserve-share": RESERVES_BOTTOM_BANNER,
                  "2026-08-04-fx-reserve-jpy-paid": FXJPY_PAID_BOTTOM_BANNER}


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

# The paid decomposition pages carry the same scenario, from the same runs, in a
# different layout. Everything scenario-specific is shared with the slim pages
# above; only the chart ids differ, so they are named rather than hard-coded.
for _paid, _slim in (("jgb-yield-curve-main", "jgb-forecast-main"),
                     ("jgb-yield-curve-alternative",
                      "jgb-forecast-alternative")):
    SCENARIO[_paid] = dict(SCENARIO[_slim])
SCENARIO["jgb-yield-curve-main"]["sibling"] = "jgb-yield-curve-alternative"
SCENARIO["jgb-yield-curve-alternative"]["sibling"] = "jgb-yield-curve-main"

IDS = {
    "jgb-forecast-main": dict(policy=5, curve=3, ustp=6, curve_spec=2,
                              yband={"10Y": 1, "30Y": 2}, tpband={}),
    "jgb-forecast-alternative": dict(policy=5, curve=3, ustp=6, curve_spec=2,
                                     yband={"10Y": 1, "30Y": 2}, tpband={}),
    # The paid pages carry no band (removed 2026-08-03), so they name no
    # banded charts. Charts 7/8 and 10/11 are still there as 2022-onward
    # close-ups of the yield and term-premium paths.
    "jgb-yield-curve-main": dict(policy=12, curve=6, ustp=13, curve_spec=5,
                                 yband={}, tpband={}),
    "jgb-yield-curve-alternative": dict(policy=12, curve=6, ustp=13,
                                        curve_spec=5, yband={}, tpband={}),
}


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
    ids = IDS[slug]
    panel = list(csv.DictReader(open(root / "data/curve-panel.csv",
                                     newline="", encoding="utf-8-sig")))
    by_ym = {r["YM"]: r for r in panel}

    # ---- scenario identity: the inversion trap ----------------------------
    print("\nScenario identity")
    gate(spec["name"] in manifest["title"],
         f"page is titled as the {spec['name']}")

    src = {r["YM"].strip(): r for r in _run_rows(spec, "curve")}
    steps, prev = [], None
    pol = trace(figs[f"chart_{ids['policy']}"], "BoJ policy rate")
    drawn = [t for t in figs[f"chart_{ids['policy']}"]["data"]
             if t["name"] == "BoJ policy rate"]
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
    # A page either draws the band everywhere it declares one, or nowhere at
    # all. The paid pages had it removed (Takuji, 2026-08-03); the parked slim
    # pages still carry it. Both states are gated, so neither can drift.
    has_band = any(c.get("band") for c in manifest["charts"])

    print("\nUncertainty band" if has_band else "\nUncertainty band removed")
    if not has_band:
        stray = [(cid, t.get("name")) for cid, f in figs.items()
                 for t in f["data"]
                 if t.get("name") == BAND or t.get("fill") == "tonexty"]
        gate(not stray, "no band trace reaches any chart on this page",
             f"{len(figs)} figures checked")
        gate(BAND not in page and "uncertainty band" not in page.lower(),
             "no band is referred to in the page text")
        gate(not any("Fan_" in str(c.get("band", "")) for c in manifest["charts"]),
             "no chart spec declares a band")

    for tenor, cid in ids["yband"].items():
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

    # The band on the term-premium charts must be exactly as wide as the band
    # on the yield charts. That is the claim the paid page makes in words —
    # that the whole fan is term-premium uncertainty because the expected-rate
    # path does not move between legs — so it is checked, not asserted.
    for tenor, cid in ids["tpband"].items():
        ye = [t for t in figs[f"chart_{ids['yband'][tenor]}"]["data"]
              if t["name"] == BAND]
        te = [t for t in figs[f"chart_{cid}"]["data"] if t["name"] == BAND]
        yx = {x[:7]: i for i, x in enumerate(ye[0]["x"])}
        tx = {x[:7]: i for i, x in enumerate(te[0]["x"])}
        shared = [m for m in yx if m in tx
                  and ye[0]["y"][yx[m]] is not None
                  and te[0]["y"][tx[m]] is not None]
        worst = max(abs((ye[0]["y"][yx[m]] - ye[1]["y"][yx[m]])
                        - (te[0]["y"][tx[m]] - te[1]["y"][tx[m]]))
                    for m in shared) * 100
        gate(worst < 0.15 and len(shared) >= 36,
             f"{tenor}: the TP band is the same width as the yield band",
             f"{len(shared)} months, worst gap {worst:.2f}bp")

    f6 = figs[f"chart_{ids['ustp']}"]
    if has_band:
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
    f3 = figs[f"chart_{ids['curve']}"]
    for ln in manifest["charts"][ids["curve_spec"]]["lines"]:
        t = trace(f3, ln["label"])
        want = [round(float(by_ym[ln["ym"]][f"Yield_{n}Y"]), 3)
                for n in (2, 5, 10, 20, 30, 40)]
        gate(t["y"] == want, f"curve {ln['label']}: matches the panel row")

    # ---- relation to the model page and the sibling ------------------------
    # The builder emits <div class="text about" id="about">, so match the id —
    # a 'class="about"' test would never fire and would pass either way.
    if manifest.get("about"):
        print("\nSelf-contained paid page")
        gate('id="about"' in page and "About the model" in page,
             "the full About section is on the page, not linked away")
        gate('href="../jgb-yield-curve-model/"' not in page,
             "does not defer to the superseded model page")
    else:
        print("\nSlim-page structure")
        gate('href="../jgb-yield-curve-model/"' in page,
             "the model exposition is linked, not duplicated")
        gate('id="about"' not in page,
             "no About/methodology section duplicated on this page")
        # Match a reference the list always carries, not a typo — the typo was
        # corrected 2026-08-03 and a test for it would now pass on any page.
        gate("Pricing the Term Structure with Linear Regressions" not in page
             and 'class="refs"' not in page,
             "the report's reference list is not restated here")

    print("\nSibling and tier")
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
    gate('class="assump"' in page
         and manifest["assumptions"]["heading"] in page,
         "the assumptions block is on the page, above the charts")
    gate(page.index('class="assump"') < page.index('class="card"'),
         "assumptions are stated before any forecast number is shown")
    if manifest["assumptions"].get("more"):
        mo = manifest["assumptions"]["more"]
        wording = mo["text"] if mo.get("url") else mo.get("text_pending",
                                                          mo["text"])
        # Compare the RENDERED sentence, not the raw string: once the report is
        # published the anchor is wrapped in <a><em>, so the manifest text is
        # no longer a literal substring of the page.
        frag = re.search(r'<p class="assumpmore">(.*?)</p>', page, re.S)
        shown = re.sub(r"<[^>]+>", "", frag.group(1)) if frag else ""
        gate(shown.strip() == wording,
             "the assumptions block points to the fuller write-up",
             shown.strip()[:70] + "…")
        gate(len(manifest["assumptions"]["items"]) == 2,
             "the assumptions block is the trimmed two-bullet version",
             f"{len(manifest['assumptions']['items'])} bullets")
        # The report was unpublished when these pages were built, so the
        # pointer is deliberately not a link yet. Whichever state it is in has
        # to be internally consistent: a set url must reach the page as an
        # anchor, an unset one must leave no half-built link behind.
        if mo.get("url"):
            gate(f'<a href="{mo["url"]}"><em>{mo["anchor"]}</em></a>' in page,
                 "the report pointer is a working link")
            gate("forthcoming" not in page,
                 "the pending wording is gone now the report is published")
        else:
            gate('class="assumpmore"' in page
                 and '<a href="">' not in page
                 and 'href="None"' not in page,
                 "report not yet published: the pointer renders as plain text, "
                 "with no dead link")

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


def qa_scenario_model(root, manifest, page, figs) -> None:
    """The paid decomposition page. Everything the slim page is checked for,
    plus the things that make this page worth paying for: that the yield really
    is the sum of the two components it is drawn as, at every maturity and over
    the projection as well as the history, and that the methodology it carries
    is the approved text rather than a paraphrase."""
    qa_scenario_forecast(root, manifest, page, figs)

    slug = manifest["slug"]
    spec = SCENARIO[slug]
    panel = list(csv.DictReader(open(root / "data/curve-panel.csv",
                                     newline="", encoding="utf-8-sig")))
    by_ym = {r["YM"]: r for r in panel}

    print("\nDecomposition at each maturity, history and projection")
    for cid, tenor in zip(range(1, 6), ["10Y", "5Y", "20Y", "30Y", "40Y"]):
        f = figs[f"chart_{cid}"]
        bars = [t for t in f["data"] if t["type"] == "bar"]
        lines = [t for t in f["data"] if t["type"] == "scatter"]
        total = [a if a is not None else b
                 for a, b in zip(lines[0]["y"], lines[1]["y"])]
        rn, tp = bars[0]["y"], bars[1]["y"]
        pts = [i for i in range(len(total))
               if None not in (total[i], rn[i], tp[i])]
        breaks = sum(1 for i in pts if abs(total[i] - (rn[i] + tp[i])) > 2e-3)
        gate(not breaks and f["layout"]["barmode"] == "relative",
             f"{tenor}: yield = expectations + term premium, relative stack",
             f"{len(pts)} points")
        # the projection has to be decomposed too, not just the history
        fc = [i for i in pts if by_ym[lines[0]["x"][i][:7]]["Type"] == "forecast"]
        gate(len(fc) >= 36,
             f"{tenor}: the decomposition runs through the projection",
             f"{len(fc)} projected months")
    t40 = [t for t in figs["chart_5"]["data"] if t["type"] == "bar"][1]
    first = next(i for i, v in enumerate(t40["y"]) if v is not None)
    gate(t40["x"][first][:7] == "2007-11" and
         all(v is None for v in t40["y"][:first]),
         "40Y decomposition starts Nov 2007, nulls before")
    gate(min(by_ym) == "2002-07",
         "the page carries the full history back to 2002, as the model page did",
         f"first month {min(by_ym)}")

    print("\nTerm premia and risk-neutral rates")
    f9 = figs["chart_9"]
    for lbl, want in TP_COLORS.items():
        legs = [t for t in f9["data"] if t["name"] == lbl]
        gate(bool(legs) and all(t["line"]["color"] == want for t in legs),
             f"TP {lbl} drawn in {want}")
    t5h, t5p = [t for t in f9["data"] if t["name"] == "5Y"]
    tp5 = [a if a is not None else b for a, b in zip(t5h["y"], t5p["y"])]
    bad = sum(1 for i, v in enumerate(tp5) if v is not None and abs(
        v - (float(by_ym[t5h["x"][i][:7]]["Yield_5Y"])
             - float(by_ym[t5h["x"][i][:7]]["RN_5Y"]))) > 2e-3)
    gate(not bad, "TP chart: identity holds on every plotted 5Y point",
         f"{sum(1 for v in tp5 if v is not None)} points")
    gate(len({t["name"] for t in figs["chart_12"]["data"]}) == 3,
         "policy chart carries its three series")

    # RN identical across legs is what licenses the whole TP-band argument.
    fc = _run_rows(spec, "fcst")
    legs = {}
    for r in fc:
        legs.setdefault((r["YM"].strip(), r["Tenor"].strip()),
                        {})[r["Scenario"].strip()] = float(r["RN_fcst"])
    spread = max(max(v.values()) - min(v.values()) for v in legs.values())
    gate(spread < 1e-9,
         "risk-neutral path is identical in the upper, central and lower runs",
         f"{len(legs)} pairs, max spread {spread:.2e}")

    print("\nAbout section: approved text and embedded exhibits")
    model = json.loads((REPO / "jgb-yield-curve-model" / "panel.json")
                       .read_text(encoding="utf-8"))
    gate(manifest["about"]["blocks"] == model["about"]["blocks"],
         "the four methodology blocks are the approved text, verbatim")
    gate(manifest["about"]["references_html"]
         == model["about"]["references_html"],
         "the reference list is the approved text, verbatim")
    gate(manifest["about"]["lead"] == model["about"]["lead"],
         "the About lead-in is the approved text, verbatim")

    _, lc_figs = load_delivered(REPO / "2026-07-20-long-climb")
    gate(manifest["charts"][14]["csv"]
         == "../2026-07-20-long-climb/data/chart-4-natural-rate-anchor.csv",
         "anchor chart: single-copy pattern, read by relative path")
    for name in ("π* (10Y inflation expectations)", "r* (equilibrium real rate)",
                 "i* = r* + π*"):
        tm, tl = trace(figs["chart_14"], name), trace(lc_figs["chart_4"], name)
        gate(list(tm["x"]) == list(tl["x"]) and list(tm["y"]) == list(tl["y"]),
             f"{name}: numerically identical to the Long Climb copy")
    for name in ("JMA model", "Standard ACM"):
        tm, tl = trace(figs["chart_15"], name), trace(lc_figs["chart_5"], name)
        gate(tm["x"] == tl["x"] and tm["y"] == tl["y"],
             f"{name}: numerically identical to the Long Climb copy")
    jma = trace(figs["chart_15"], "JMA model")
    v = jma["y"][jma["x"].index("2026-07-01")] / 100
    gate(0.6 <= v <= 0.7,
         "About's 0.6%-0.7% claim brackets the delivered mid-July 10Y TP",
         f"{v:.4f}%")
    gate(page.index("last era of free JGB pricing")
         < page.index(ANCHOR_TITLE)
         < page.index("<strong>Why we do not use a standard model.</strong>"),
         "anchor card sits between About blocks 1 and 2")
    gate(page.index("The chart below shows the difference.") < page.index(ACM_TITLE),
         "ACM card sits after the block that argues it")


# ------------------------------------------------ the Warsh article panel
# Every figure below is a claim the article makes in words. The manifest's own
# notes state them precisely enough to check, which is what these gates do:
# each one re-derives a printed number from the delivered page and, where the
# number originates in the forecast pipeline, from the production run directory
# rather than from the CSV this repo cut from it.
WARSH_TITLES = [
    "Long Term Inflation Expectation: Getting Closer to 2%",
    "US 30Y Treasury Yield: Highest Since 2007",
    "US Curve 2-30Y Spread: The sharp steepening on FOMC day",
    "US 10Y Term premia: Rising till Nov 2026",
    "Main forecast: JGB spot yields, %",
    "Alternative forecast: JGB spot yields, %",
    "The 30-year peaks near 4.5%, then declines",
]
# The scenario each forecast table belongs to, and the policy path its caption
# claims. Swapping the two CSVs is the failure this page is most exposed to:
# both tables are the same shape and either would render without complaint.
WARSH_TABLES = {
    5: dict(scenario="Main", run="fan-sigma-after-v307",
            hikes=[("2026-10", 1.25), ("2027-03", 1.50)]),
    6: dict(scenario="Alternative", run="fan-sigma-after-v306",
            hikes=[("2026-09", 1.25), ("2027-03", 1.50), ("2027-12", 1.75)]),
}
WARSH_FLAT = {"fan-sigma-after-v307": "ustp-flat-v307",
              "fan-sigma-after-v306": "ustp-flat-v306"}


def _run_curve(run: str) -> dict:
    with open(RUNS / run / f"{run}_consolidated_curve.csv",
              newline="", encoding="utf-8-sig") as f:
        return {r["YM"].strip(): r for r in csv.DictReader(f)}


def qa_warsh_panel(root, manifest, page, figs) -> None:
    """The free companion panel to "The Warsh Factor in the JGB Curve"."""
    def csv_rows(name):
        with open(root / "data" / name, newline="", encoding="utf-8-sig") as f:
            return list(csv.DictReader(f))

    print("\nTitles and order")
    h2s = re.findall(r"<h2>(.*?)</h2>", page)
    gate(h2s[:7] == WARSH_TITLES, "the seven exhibits run in the article's order",
         str([t[:20] for t in h2s[:7]]))
    gate(f'href="{manifest["post_url"]}"' in page, "links back to the article")

    print("\nChart 1 — inflation expectations approaching 2%")
    f1 = figs["chart_1"]
    ys = [v for v in trace(f1, "10Y inflation expectations")["y"] if v is not None]
    gate(any(abs(s.get("y0", 0) - 2.0) < 1e-9 for s in f1["layout"]["shapes"]),
         "the 2% target line is drawn")
    gate(any(a["text"] == "BoJ 2% target"
             for a in f1["layout"].get("annotations", [])),
         "the 2% line is labelled")
    latest = ys[-1]
    gate(abs(latest - 1.74) < 0.005,
         "the latest bar is 1.74%, as the caption states", f"{latest:.4f}%")
    gate(0 < 2.0 - latest < 0.30,
         "'getting closer to 2%': the latest reading is within 30bp, still below",
         f"{(2.0-latest)*100:.0f}bp short")
    rises = 0
    for i in range(len(ys) - 1, 0, -1):
        if ys[i] > ys[i - 1]:
            rises += 1
        else:
            break
    gate(rises >= 6, "at least six consecutive annual rises, per the caption",
         f"{rises}")

    print("\nChart 2 — 'Highest Since 2007', audited not asserted")
    f2 = figs["chart_2"]
    t2 = trace(f2, "US 30Y Treasury yield")
    pts = [(x[:10], y) for x, y in zip(t2["x"], t2["y"]) if y is not None]
    line = next(s["y0"] for s in f2["layout"]["shapes"])
    gate(abs(line - 5.21) < 1e-9, "the reference line is the 5.21% latest close")
    gate(abs(pts[-1][1] - 5.21) < 5e-3 and pts[-1][0] == "2026-07-30",
         "the line equals the last drawn observation", str(pts[-1]))
    after = [p for p in pts if p[0] > "2007-07-12" and p[1] > 5.21]
    gate(not after,
         "nothing drawn exceeds 5.21% after 12 July 2007 — the headline holds",
         f"{len(after)} exceedances")
    before = [p for p in pts if p[0] <= "2007-07-12" and p[1] > 5.21]
    gate(bool(before),
         "...and something before it does, so 'since 2007' is not vacuous",
         f"{len(before)} earlier points, max {max(p[1] for p in before)}")

    print("\nChart 3 — the FOMC-day steepening")
    t3 = trace(figs["chart_3"], "30Y minus 2Y")
    sp = {x[:10]: y for x, y in zip(t3["x"], t3["y"]) if y is not None}
    gate(abs(sp["2026-07-28"] - 83) < 0.5 and abs(sp["2026-07-29"] - 98) < 0.5,
         "83bp to 98bp across the FOMC decision, as the caption states",
         f"{sp['2026-07-28']:.0f} -> {sp['2026-07-29']:.0f}")
    ks = sorted(sp)
    moves = [(ks[i], sp[ks[i]] - sp[ks[i - 1]]) for i in range(1, len(ks))]
    biggest = max(moves, key=lambda m: m[1])
    gate(biggest[0] == "2026-07-29" and abs(biggest[1] - 15) < 0.5,
         "+15bp is the sharpest one-day steepening in the drawn window",
         f"{biggest[0]} {biggest[1]:+.0f}bp")
    gate(abs(sp[ks[0]] - 139) < 0.5 and 35 < sp[ks[0]] - sp[ks[-1]] < 45,
         "the year opened at 139bp and is still ~40bp steeper than now",
         f"{sp[ks[0]]:.0f} -> {sp[ks[-1]]:.0f}bp")

    print("\nChart 4 — the assumed US term-premium path")
    f4 = figs["chart_4"]
    legs = [t for t in f4["data"] if t["name"] == "10Y term premium"]
    gate(len(legs) == 2, "observed and assumed legs are drawn separately")
    merged = [a if a is not None else b for a, b in zip(legs[0]["y"], legs[1]["y"])]
    xs = [x[:7] for x in legs[0]["x"]]
    at = dict(zip(xs, merged))
    # The figure rounds to the chart's `decimals`, so a claim stated to a tenth
    # is checked on the SOURCE, and the figure is checked against that source at
    # the precision it is drawn in. Comparing a rounded pixel value against an
    # unrounded claim only measures the rounding.
    src4 = {r["ym"]: float(r["tp10_bp"]) for r in csv_rows("chart-4-us-tp10.csv")
            if (r.get("tp10_bp") or "").strip()}
    dec4 = next(c for c in manifest["charts"] if c["n"] == 4).get("decimals", 3)
    gate(all(v is None or abs(v - round(src4[ym], dec4)) < 1e-9
             for ym, v in at.items() if ym in src4),
         "every drawn point is its source value at the chart's precision",
         f"{len(src4)} months, {dec4}dp")
    peak_ym = max(src4, key=src4.get)
    gate(peak_ym == "2026-11" and abs(src4[peak_ym] - 122.2) < 0.05,
         "the path peaks at 122bp just past the November midterms",
         f"{src4[peak_ym]:.1f}bp at {peak_ym}")
    last4 = src4[max(src4)]
    gate(abs(last4 - 94.5) < 0.05, "and retains 94bp at the horizon",
         f"{last4:.1f}bp")
    gate("122bp" in page and "94bp" in page,
         "the caption quotes both figures as the chart rounds them")
    base = src4.get("2026-05")
    if base is not None:
        half = base + (src4[peak_ym] - base) / 2
        gate(abs(last4 - half) < 1.0,
             "the terminal level is half the shock retained, as described",
             f"baseline {base:.1f} peak {src4[peak_ym]:.1f} -> half {half:.1f}bp")

    print("\nCharts 5 and 6 — the forecast tables, against the production runs")
    seen = {}
    for n, spec in WARSH_TABLES.items():
        c = next(c for c in manifest["charts"] if c["n"] == n)
        gate(spec["scenario"].lower() in c["title"].lower(),
             f"chart {n} is titled as the {spec['scenario']} forecast")
        tbl = csv_rows(Path(c["csv"]).name)
        seen[n] = tbl
        src = _run_curve(spec["run"])
        bad = []
        for r in tbl:
            ym = {"Current (Jul 2026)": "2026-07", "Dec 2026": "2026-12",
                  "Dec 2027": "2027-12", "Dec 2028": "2028-12",
                  "Jul 2029": "2029-07"}.get(r["label"].strip())
            if ym is None:
                bad.append(f"unmapped row {r['label']}")
                continue
            for t in ("5Y", "10Y", "20Y", "30Y", "40Y"):
                want = round(float(src[ym][f"Yield_{t}"]), 2)
                if abs(float(r[t]) - want) > 5e-3:
                    bad.append(f"{ym} {t}: {r[t]} vs {want}")
        gate(not bad, f"chart {n}: every cell matches {spec['run']}",
             f"{len(tbl)}x5 cells" if not bad else "; ".join(bad[:3]))
        # the caption's policy path, re-derived from the run itself
        steps, prev = [], None
        for ym, row in sorted(src.items()):
            pr = float(row["Policy_Rate"])
            if row["Type"].strip() == "forecast" and prev is not None \
                    and abs(pr - prev) > 1e-4 and pr > 1.0 + 1e-6:
                steps.append((ym, round(pr, 2)))
            prev = pr
        gate(steps == [(y, r) for y, r in spec["hikes"]],
             f"chart {n}: the caption's policy path is the run's", str(steps))
        for ym, rate in spec["hikes"]:
            month = ["January","February","March","April","May","June","July",
                     "August","September","October","November","December"][int(ym[5:7])-1]
            gate(f"{rate:.2f}% from {month} {ym[:4]}" in page
                 or f"{rate:.2f}% terminal from {month} {ym[:4]}" in page,
                 f"chart {n}: caption names {rate:.2f}% from {month} {ym[:4]}")
    gate(seen[5] != seen[6],
         "the two tables are not the same file — a swap or duplicate would show here")

    print("\nChart 7 — the two scenario paths")
    f7 = figs["chart_7"]
    names = [t["name"] for t in f7["data"]]
    gate(names.index("Alternative") < names.index("Main"),
         "Alternative is drawn first so Main sits on top, per the manifest note")
    def merge(name):
        a, b = [t for t in f7["data"] if t["name"] == name]
        return dict(zip([x[:7] for x in a["x"]],
                        [p if p is not None else q for p, q in zip(a["y"], b["y"])]))
    main, alt = merge("Main"), merge("Alternative")
    # The 8.3bp claim is about the forecast, so it is checked on the source at
    # full precision. At the chart's 2dp the same gap can READ as 9bp — that is
    # the display rounding, not a broken claim, and is asserted separately so a
    # future reader is not surprised by it.
    src7 = {r["ym"]: r for r in csv_rows("chart-7-jgb-30y-scenarios.csv")}
    exact = {ym: (float(r["alt_pct"]) - float(r["main_pct"])) * 100
             for ym, r in src7.items()
             if (r.get("alt_pct") or "").strip() and (r.get("main_pct") or "").strip()}
    worst = max(exact.items(), key=lambda kv: abs(kv[1]))
    gate(abs(worst[1]) <= 8.35,
         "the two paths never differ by more than 8.3bp, as the caption states",
         f"max {worst[1]:+.2f}bp at {worst[0]}")
    drawn_gap = max(abs(alt[ym] - main[ym]) * 100 for ym in main
                    if main[ym] is not None and alt.get(ym) is not None)
    gate(drawn_gap <= abs(worst[1]) + 1.0,
         "the 2dp drawn series widens that gap by less than a basis point",
         f"drawn max {drawn_gap:.1f}bp vs source {abs(worst[1]):.2f}bp")
    peak = max((v for v in main.values() if v is not None))
    peak_ym = next(k for k, v in main.items() if v == peak)
    gate(4.45 <= peak <= 4.55 and peak_ym.startswith("2026"),
         "the 30-year peaks near 4.5% in 2026, as the title claims",
         f"{peak:.3f}% at {peak_ym}")
    gate(abs(main["2028-06"] - 3.8) < 0.06,
         "...and is down to about 3.8% by mid-2028",
         f"{main['2028-06']:.3f}%")
    hist = [ym for ym in main if ym <= "2026-07"]
    gate(all(abs(main[ym] - alt[ym]) < 1e-9 for ym in hist),
         "over history the two lines carry the same actual", f"{len(hist)} months")
    for name, col, spec in (("Main", "main_pct", WARSH_TABLES[5]),
                            ("Alternative", "alt_pct", WARSH_TABLES[6])):
        src = _run_curve(spec["run"])
        bad = sum(1 for ym, r in src7.items()
                  if (r.get(col) or "").strip() and ym in src
                  and abs(float(r[col]) - float(src[ym]["Yield_30Y"])) > 1e-3)
        gate(not bad, f"{name}: the page's 30Y is {spec['run']}'s own",
             f"{len(src7)} months")
        series = merge(name)
        off = sum(1 for ym, v in series.items()
                  if v is not None and ym in src7
                  and (src7[ym].get(col) or "").strip()
                  and abs(v - round(float(src7[ym][col]), 2)) > 1e-9)
        gate(not off, f"{name}: every drawn point is its source at 2dp")

    print("\nThe standfirst's 10bp claim, against the no-Warsh runs")
    for scen, spec in (("Main", WARSH_TABLES[5]), ("Alternative", WARSH_TABLES[6])):
        w, fl = _run_curve(spec["run"]), _run_curve(WARSH_FLAT[spec["run"]])
        d = (float(w["2026-12"]["Yield_10Y"]) - float(fl["2026-12"]["Yield_10Y"])) * 100
        gate(8.0 <= d <= 12.0,
             f"{scen}: the Warsh factor adds ~10bp to the 10Y at end-2026",
             f"{d:+.1f}bp")


def qa_global_fx_reserve_shares(root, manifest, page, figs) -> None:
    """Standing reserves dataset. The gates check the drawn values against the
    published sources the page claims to match, against the figures its own
    About text asserts, and against the deletions — which are editorial rulings
    and so are gated on absence."""
    C = {c["n"]: c for c in manifest["charts"]}
    # n -> (name, first year of our own series, first year of the published one)
    # The euro chart draws the published series only: ours is identical to it
    # over the whole span, so drawing both would be drawing one series twice
    # (Takuji, 2026-08-05). n_lines records what each chart should carry.
    CCY = {1: ("US dollar", 1980, 1995, 3),
           2: ("Euro", None, 1999, 2),
           3: ("Japanese yen", 1980, 1995, 3),
           4: ("Pound sterling", 1980, 1995, 3),
           5: ("Swiss franc", 1980, 1995, 3)}
    # Exhibit numbering: 1-5 are the per-currency charts, 6-9 the flow charts
    # (all four read one dataset), 10 the decomposition table. Every number
    # below is a manifest `n`, and the CSV filenames carry the same number —
    # sterling and the franc were inserted at 4 and 5 on 2026-08-07, and their
    # flow charts at 8 and 9 the same day, pushing the table down twice. If a
    # chart number moves again, it moves here too.
    FLOW_N = (6, 7, 8, 9)
    FLOW_CSV_N = 6           # the one dataset all the flow charts read
    TABLE_N = 10

    print("\nTier")
    gate(manifest.get("tier") == "paid", "declared paid tier",
         manifest.get("tier", "MISSING"))

    # ---- the rotated y-axis titles fit inside their plots --------------------
    # The y-axis title is drawn rotated, so a long one runs out of PLOT HEIGHT,
    # not width, and Plotly does not shrink or wrap it — it simply overflows the
    # figure and is clipped. That is how the flow charts shipped on 2026-08-05
    # reading "...reserves per ye". Measured in Chrome at this page's 18px axis
    # font: 47 characters rendered 435px, so 9.3px per character, and the plot
    # area is the figure height less its own top and bottom margins.
    print("\nAxis titles fit their plots")
    PX_PER_CHAR = 9.3
    for c in manifest["charts"]:
        if c["kind"] == "table":
            continue
        lay = figs["chart_%d" % c["n"]]["layout"]
        avail = (c.get("height", 470) - lay["margin"]["t"] - lay["margin"]["b"])
        need = len(lay["yaxis"]["title"]["text"]) * PX_PER_CHAR
        gate(need <= avail,
             "chart %d: the rotated y-axis title fits its plot" % c["n"],
             "needs ~%dpx of %dpx" % (need, avail))

    # ---- charts 1-3: three measures per currency ---------------------------
    # The page's central claim is that our series IS the published one wherever
    # the IMF publishes on a comparable basis. Gate it year by year, not at a
    # spot: a single matching endpoint would pass on a series that drifts.
    for n, (name, ours_from, cofer_from, n_lines) in CCY.items():
        print("\nChart %d — %s" % (n, name))
        f = figs["chart_%d" % n]
        pub = dict(col(root, C[n]["csv"], "cofer"))
        cer = dict(col(root, C[n]["csv"], "cer"))
        gate(min(pub) == "%d-12-31" % cofer_from,
             "published series starts %d" % cofer_from, min(pub))
        gate(max(pub) == max(cer) == "2025-12-31",
             "every drawn measure stops at 2025")

        if ours_from is None:
            # Euro: our series is not drawn, so the endpoint anchor is the
            # published series itself.
            gate(min(cer) == "2000-12-31",
                 "constant-rate series starts 2000", min(cer))
            gate(abs(cer["2025-12-31"] - pub["2025-12-31"]) < 1e-9,
                 "base-year identity: constant-rate 2025 = published 2025",
                 "%s" % cer["2025-12-31"])
            gate("ar_cofer" not in
                 open(root / C[n]["csv"], encoding="utf-8-sig").readline(),
                 "the duplicate JMA column is gone from the file too")
        else:
            our = dict(col(root, C[n]["csv"], "ar_cofer"))
            gate(min(our) == "%d-12-31" % ours_from,
                 "JMA series starts %d" % ours_from, min(our))
            # From 2000 our panel simply carries the published COFER numbers,
            # stored to two decimals. A cell whose 2dp value sits on a rounding
            # boundary can land 0.1 away at the one decimal we publish —
            # rounding, not disagreement. The gate holds that bound rather than
            # exact equality, which fails on four cells out of seventy-eight.
            shared = [d for d in our if d in pub and int(d[:4]) >= 2000]
            worst = max(abs(our[d] - pub[d]) for d in shared)
            apart = sum(1 for d in shared if abs(our[d] - pub[d]) > 1e-9)
            gate(worst <= 0.1 + 1e-9,
                 "from 2000 the JMA and published series are the same, to "
                 "rounding (%d years)" % len(shared),
                 "max diff %.1f, %d year(s) round apart" % (worst, apart))
            gate(abs(cer["2025-12-31"] - our["2025-12-31"]) < 1e-9,
                 "base-year identity: constant-rate 2025 = observed 2025",
                 "%s" % cer["2025-12-31"])

        # exclude the band's own edge traces, which are lines with a fill
        drawn = [t for t in f["data"] if t.get("mode") == "lines"
                 and not t.get("fill") and t.get("line", {}).get("width")]
        gate(len(drawn) == n_lines, "%d measures drawn" % n_lines,
             "%d lines" % len(drawn))
        labels = {t.get("name") for t in drawn}
        gate("JMA: Annual Reports + COFER" not in labels,
             "our series is labelled JMA estimates, not by its sources")

    # the pre-2000 divergence the notes describe, in both directions
    usd_pub = dict(col(root, C[1]["csv"], "cofer"))
    usd_our = dict(col(root, C[1]["csv"], "ar_cofer"))
    gate(usd_our["1995-12-31"] > usd_pub["1995-12-31"],
         "1995: the ECU look-through puts the JMA dollar above the published one",
         "%s vs %s" % (usd_our["1995-12-31"], usd_pub["1995-12-31"]))
    gate(usd_pub["1998-12-31"] > usd_our["1998-12-31"],
         "1998: the allocated-only denominator puts the published dollar above ours",
         "%s vs %s" % (usd_pub["1998-12-31"], usd_our["1998-12-31"]))
    gate(abs(usd_our["1997-12-31"] - 66.8) < 1e-9,
         "USD 1997 = 66.8 (differs from the printed AR by the two adjustments)",
         "%s" % usd_our["1997-12-31"])
    gate(abs(round(usd_our["1998-12-31"] - 65.7, 1) - 0.6) < 1e-9,
         "USD 1998 sits 0.6 above the printed AR-2003 row (65.7)",
         "%s" % usd_our["1998-12-31"])
    for n, want in ((1, 56.4), (2, 20.4), (3, 5.8), (4, 4.4), (5, 0.2)):
        # the euro chart draws the published series only, so that is its anchor
        src = "cofer" if CCY[n][1] is None else "ar_cofer"
        v = dict(col(root, C[n]["csv"], src))["2025-12-31"]
        gate(abs(v - want) < 1e-9,
             "%s 2025 = published COFER %s" % (CCY[n][0], want), "%s" % v)

    # Sterling and the franc diverge sharply from their own constant-rate line
    # in the early years, in opposite directions, and that divergence IS the
    # measure — the franc appreciated hugely against the dollar over the 45
    # years that followed, sterling did not. Gated so that a future "fix"
    # flattening either line fails loudly, and so that the CHF chart's y-axis
    # is never trimmed below the constant-rate peak it has to hold.
    for n, ccy, above in ((4, "Pound sterling", False), (5, "Swiss franc", True)):
        cer80 = dict(col(root, C[n]["csv"], "cer"))["1980-12-31"]
        our80 = dict(col(root, C[n]["csv"], "ar_cofer"))["1980-12-31"]
        gate((cer80 > our80) == above,
             "%s 1980: constant-rate sits %s the observed share"
             % (ccy, "above" if above else "below"),
             "%s vs %s" % (cer80, our80))
        hi = max(v for _d, v in col(root, C[n]["csv"], "cer"))
        gate(C[n]["yrange"][0] <= 0 + 1e-9 and C[n]["yrange"][1] >= hi,
             "%s: y-axis holds the constant-rate peak" % ccy,
             "peak %s, yrange %s" % (hi, C[n]["yrange"]))
    gate(abs(dict(col(root, C[5]["csv"], "cer"))["1980-12-31"] - 7.2) < 1e-9,
         "CHF 1980 constant-rate = 7.2 (not the 3.5 observed share)")

    print("\nResidual-treatment range")
    # Measured on the published one-decimal file, not on the source, so a spread
    # can print 0.1 wider than the source's: the franc's widest source year is
    # 1984, 5.65 against 5.44 — 0.21pp, which rounds apart to 5.7 and 5.4.
    for n, want in ((1, 2.2), (2, 0.2), (3, 0.3), (4, 0.1), (5, 0.3)):
        a = dict(col(root, C[n]["csv"], "cer"))
        b = dict(col(root, C[n]["csv"], "cer_alt_rule"))
        spread = max(abs(a[d] - b[d]) for d in a)
        gate(abs(round(spread, 1) - want) < 1e-9,
             "%s: residual-rule range = %spp" % (CCY[n][0], want),
             "%.2f" % spread)
    gate(any(t.get("fill") == "tonexty" for t in figs["chart_1"]["data"]),
         "dollar range drawn as a band")
    for n, ccy in ((3, "yen"), (4, "sterling"), (5, "franc")):
        gate(not any(t.get("fill") == "tonexty" for t in figs["chart_%d" % n]["data"]),
             "no band on the %s, whose range is too narrow to draw" % ccy)

    # ---- charts 6-9: annual net accumulation --------------------------------
    # Sterling and the franc got flow charts on 2026-08-07 (Takuji), reversing
    # the work order's ruling that their flow belonged in the download only.
    # The euro is the one charted currency with no flow chart: its flow starts
    # in 2001, not 1981, so it is the odd one out and gated as such.
    FLOW_CCY = {6: ("dollar", "usd"), 7: ("yen", "jpy"),
                8: ("sterling", "gbp"), 9: ("franc", "chf")}
    print("\nCharts 6-9 — annual net addition/shedding")
    src = C[FLOW_CSV_N]["csv"]
    gate(all(C[n]["csv"] == src for n in FLOW_N),
         "all %d flow charts read one dataset, so they cannot disagree"
         % len(FLOW_N))
    gate(sum(1 for c in manifest["charts"]
             if c["kind"] == "signed_bar_line") == len(FLOW_N),
         "%d flow charts, no more" % len(FLOW_N))
    gate({C[n]["value"]["col"] for n in FLOW_N}
         == {c for _n, c in FLOW_CCY.values()},
         "the flow charts draw the dollar, the yen, sterling and the franc")
    gate("eur" not in {C[n]["value"]["col"] for n in FLOW_N},
         "no euro flow chart: its flow starts 2001, not 1981")
    usd4 = dict(col(root, src, "usd"))
    gate(abs(usd4["1986-12-31"] - 5.9) < 1e-9,
         "USD 1986 = +5.9 (the largest single year of dollar buying)",
         "%s" % usd4["1986-12-31"])
    eur4 = col(root, src, "eur")
    gate(eur4[0][0] == "2001-12-31",
         "euro flow starts 2001, its first COFER-on-COFER link", eur4[0][0])
    for n in FLOW_N:
        ccy, c = FLOW_CCY[n]
        f = figs["chart_%d" % n]
        got = col(root, src, c)
        gate(got[0][0] == "1981-12-31" and got[-1][0] == "2025-12-31"
             and len(got) == 45,
             "%s: the drawn column runs 1981-2025" % ccy,
             "%s to %s, %d rows" % (got[0][0], got[-1][0], len(got)))
        gate(len(f["data"]) == 2, "%s: added and shed drawn as two traces" % ccy,
             "%d traces" % len(f["data"]))
        gate("yaxis2" not in f["layout"],
             "%s: no empty right-hand axis on a bars-only chart" % ccy)
        gate(all(t.get("width") == 25246080000 for t in f["data"]),
             "%s: bars are one year wide, not one quarter" % ccy)
        # A flow axis clipped at the data's own edge hides the year it matters
        # most. Every flow chart must hold its column with room to spare.
        lo, hi = C[n]["yrange"]
        vals = [v for _d, v in got]
        gate(lo < min(vals) and hi > max(vals),
             "%s: y-axis holds the whole column, clipping nothing" % ccy,
             "data %.1f to %.1f, yrange %s" % (min(vals), max(vals),
                                               C[n]["yrange"]))

    # ---- chart 10: the decomposition table ----------------------------------
    print("\nTable 10 — 2000-2025 decomposition")
    with open(root / C[TABLE_N]["csv"], newline="", encoding="utf-8-sig") as fh:
        rows6 = list(csv.DictReader(fh))
    gate([r["currency"] for r in rows6]
         == ["US dollar", "Euro", "Japanese yen", "Pound sterling",
             "Swiss franc"],
         "five rows, in the page's currency order",
         ", ".join(r["currency"] for r in rows6))
    gate(C[TABLE_N]["label"] == "Table %d" % TABLE_N,
         "the table's printed label is its manifest number",
         C[TABLE_N].get("label", "MISSING"))
    for r in rows6:
        chg = float(r["change"])
        real = float(r["real_reallocation"])
        val = float(r["valuation"])
        gate(abs(chg - (real + val)) < 1e-9,
             "%s: change = real + valuation, as printed" % r["currency"],
             "%s = %s + %s" % (chg, real, val))
    d6 = {r["currency"]: r for r in rows6}
    gate(abs(float(d6["US dollar"]["change"]) + 13.32) < 1e-9,
         "dollar 2000-25 change = -13.32")
    gate(abs(float(d6["Euro"]["change"]) - 2.84) < 1e-9,
         "euro 2000-25 change = +2.84")
    gate(float(d6["Euro"]["real_reallocation"]) < 0,
         "euro's real reallocation over 2000-25 is negative")
    gate(abs(float(d6["Pound sterling"]["change"]) - 1.00) < 1e-9,
         "sterling 2000-25 change = +1.00")
    gate(abs(float(d6["Swiss franc"]["change"]) + 0.07) < 1e-9,
         "franc 2000-25 change = -0.07")
    # the table's 2000 column must be the same number the charts draw
    for n, (name, _o, _c, _l) in CCY.items():
        src = "cofer" if CCY[n][1] is None else "ar_cofer"
        v = dict(col(root, C[n]["csv"], src))["2000-12-31"]
        gate(abs(round(float(d6[name]["share_2000"]), 1) - v) < 1e-9,
             "%s: table's 2000 share matches the chart" % name, "%s" % v)

    # ---- the deletions ------------------------------------------------------
    # Each is an editorial ruling, so each is gated on absence: a dropped column
    # with no gate gets restored by the next person to touch the page.
    print("\nDeletions (gated on absence)")
    # Sterling and the franc left this list on 2026-08-07, when they became
    # part of the page. Everything still on it is a currency the page does not
    # carry in any form, chart or download.
    banned = ("cad", "aud", "cny", "unspecified", "other",
              "dem", "frf", "nlg", "allocest")
    for n in (1, 2, 3, 4, 5, FLOW_CSV_N):
        with open(root / C[n]["csv"], newline="", encoding="utf-8-sig") as fh:
            names = [h.lower() for h in csv.DictReader(fh).fieldnames]
        gate(not any(b in h for h in names for b in banned),
             "chart %d: carries no currency outside the page's set" % n,
             ", ".join(names))
        with open(root / C[n]["csv"], newline="", encoding="utf-8-sig") as fh:
            yrs = [int(r["date"][:4]) for r in csv.DictReader(fh)]
        gate(min(yrs) >= 1980 and max(yrs) == 2025,
             "chart %d: no year before 1980, none after 2025" % n,
             "%d-%d" % (min(yrs), max(yrs)))
        with open(root / C[n]["csv"], newline="", encoding="utf-8-sig") as fh:
            bad = [v for r in csv.DictReader(fh) for k, v in r.items()
                   if k != "date" and v and "." in v
                   and len(v.split(".")[-1]) > 1]
        gate(not bad, "chart %d: published to one decimal, the precision the "
                      "pre-2000 sources support" % n,
             "%d over-precise" % len(bad))


FXJPY_FREE = "2026-08-04-fx-reserve-jpy"
FXJPY_PAID = "2026-08-04-fx-reserve-jpy-paid"

FXJPY_TITLES = [
    "The yen is making a comeback as a global currency",
    "USD's slide from dominance through depreciation and quantity",
    "The euro's rise stalled after the euro crisis",
    "Yen leads the diversification away from USD",
    "Reserve managers consistently sold USD since 2010",
]


def qa_fx_reserve_jpy(root, manifest, page, figs) -> None:
    """Both tiers of "Good-bye USD Dominance, Hello Again JPY".

    One report, two pages that differ only in whether they offer the data. One
    gate function therefore serves both: the value gates below are the failure
    the tier split introduces, because each page passes its own structural
    gates while quietly disagreeing with the other about a number. Every value
    is lifted from the report's figure check, which already reconciled the post
    against the JMA v10 unadjusted panel and the cer-v4 constant-rate build --
    it is not re-derived here.
    """
    def at(fig, name, year):
        """The drawn value at a year-end, from the delivered figure JSON."""
        t = trace(fig, name)
        for x, y in zip(t["x"], t["y"]):
            if x[:4] == str(year) and y is not None:
                return y
        return None

    def drawn(fig, name):
        return [(x, y) for x, y in zip(trace(fig, name)["x"],
                                       trace(fig, name)["y"]) if y is not None]

    print("\nTitles, order and provenance")
    h2s = re.findall(r"<h2>(.*?)</h2>", page)
    gate([html.unescape(t) for t in h2s[:5]] == FXJPY_TITLES,
         "the five exhibits run in the published order",
         str([t[:18] for t in h2s[:5]]))
    gate(f'href="{manifest["post_url"]}"' in page, "links back to the article")
    gate(manifest["post_url"].endswith("/p/good-bye-usd-dominance-hello-again"),
         "post_url is the URL opened on 2026-08-05, not a guessed slugification")

    print("\nChart 1 - the yen's comeback")
    f1 = figs["chart_1"]
    for year, want in ((1980, 4.55), (1991, 8.73), (2009, 3.35), (2025, 5.84)):
        got = at(f1, "JPY share", year)
        gate(got is not None and abs(got - want) < 5e-3,
             f"JPY {year} reads {want}, as the post prints", f"{got}")
    ys = [y for _, y in drawn(f1, "JPY share")]
    xs = [x for x, _ in drawn(f1, "JPY share")]
    peak = max(range(len(ys)), key=lambda i: ys[i])
    gate(xs[peak][:4] == "1991", "1991 is the peak of the whole series, not just a high",
         f"max {ys[peak]} at {xs[peak][:4]}")
    seg = [(x, y) for x, y in zip(xs, ys) if "1991" <= x[:4] <= "2009"]
    gate(min(seg, key=lambda p: p[1])[0][:4] == "2009",
         "2009 is the trough of the 1991-2009 slide the post describes")

    print("\nChart 2 - the dollar's slide")
    f2 = figs["chart_2"]
    for year, want in ((1975, 79.36), (2015, 64.16), (2016, 64.67), (2025, 56.42)):
        got = at(f2, "Unadjusted", year)
        gate(got is not None and abs(got - want) < 5e-3,
             f"USD {year} reads {want}, as the post prints", f"{got}")
    post2010 = [(x, y) for x, y in drawn(f2, "Unadjusted") if x[:4] >= "2010"]
    gate(max(post2010, key=lambda p: p[1])[0][:4] == "2016",
         "2016 is the 2010-2025 peak, which is what makes it the post's start point")
    gate(abs(at(f2, "Unadjusted", 2025) - at(f2, "Constant exchange rates", 2025)) < 5e-3,
         "the two lines converge at 2025, the constant-rate base year")

    print("\nChart 3 - the euro stalls")
    f3 = figs["chart_3"]
    obs3 = drawn(f3, "Unadjusted")
    gate(abs(at(f3, "Unadjusted", 2009) - 24.05) < 5e-3,
         "EUR 2009 peak reads 24.05", f"{at(f3, 'Unadjusted', 2009)}")
    gate(max(obs3, key=lambda p: p[1])[0][:4] == "2009",
         "2009 is the peak of the drawn window, not merely a local high")
    band = [y for x, y in obs3 if "2015" <= x[:4] <= "2025"]
    gate(abs(min(band) - 18.91) < 5e-3 and abs(max(band) - 20.56) < 5e-3,
         "the 2015-2025 band is 18.91-20.56, the range behind 'hovering around 20%'",
         f"{min(band)}-{max(band)}")
    gate(all(x[:4] >= "1980" for x, _ in obs3),
         "the chart windows from 1980 though the file starts in 1975")
    # The 2019 constant-rate cell shipped as 19.82 -- that year's OBSERVED share,
    # overwritten when this chart was split out of majors_share_cer on
    # 2026-08-05, and drawn in the PNG published with the post. Corrected to the
    # parent chart's 20.93. Gated in both directions: the value must be right,
    # and it must not equal the observed share, which is the shape the error had.
    cer19, obs19 = at(f3, "Constant exchange rates", 2019), at(f3, "Unadjusted", 2019)
    gate(abs(cer19 - 20.93) < 5e-3,
         "EUR 2019 constant-rate reads 20.93, the corrected value", f"{cer19}")
    gate(abs(cer19 - obs19) > 1.0,
         "the 2019 constant-rate value is not a copy of that year's observed share",
         f"cer {cer19} vs observed {obs19}")
    coincide = [x[:4] for x, y in obs3
                if abs(y - dict(drawn(f3, "Constant exchange rates"))[x]) < 1e-9]
    gate(coincide == ["2025"],
         "the two euro lines coincide only at 2025, the constant-rate base year",
         str(coincide))

    print("\nChart 4 - diversification, and the RMB turning")
    f4 = figs["chart_4"]
    rmb = drawn(f4, "RMB")
    gate(abs(at(f4, "RMB", 2021) - 2.85) < 5e-3
         and abs(at(f4, "RMB", 2025) - 1.95) < 5e-3,
         "RMB 2.85 in 2021 falling to 1.95 in 2025", f"{at(f4, 'RMB', 2025)}")
    gate(max(rmb, key=lambda p: p[1])[0][:4] == "2021",
         "2021 is the RMB peak, so the fall is from the peak and not from a plateau")
    gate(abs(at(f4, "CAD", 2025) - 2.50) < 5e-3
         and abs(at(f4, "AUD", 2025) - 2.02) < 5e-3,
         "CAD 2.50 and AUD 2.02 in 2025")
    gate(at(f4, "RMB", 2025) < at(f4, "AUD", 2025) < at(f4, "CAD", 2025),
         "the RMB sits below both the Australian and the Canadian dollar in 2025")
    gate(at(f4, "JPY", 2025) == max(at(f4, c, 2025) for c in ("JPY", "CAD", "AUD", "RMB")),
         "the yen is the largest of the four in 2025, which is the chart's headline")

    print("\nChart 5 - what reserve managers did, year by year")
    f5 = figs["chart_5"]
    flows = dict(drawn(f5, "Added to USD") + drawn(f5, "Shed from USD"))
    y22 = next(v for x, v in flows.items() if x[:4] == "2022")
    gate(abs(y22 - (-2.214)) < 5e-4,
         "2022 shedding reads -2.214pp, the post's 'about 2.2%'", f"{y22}")
    since = {x[:4]: v for x, v in flows.items() if x[:4] >= "2010"}
    neg = sum(1 for v in since.values() if v < 0)
    gate(neg >= 13 and neg / len(since) > 0.75,
         "'consistently sold since 2010': most years since 2010 are negative",
         f"{neg} of {len(since)}")
    gate(min(flows) [:4] == "1981",
         "the series starts in 1981, the 1980 estimate being excluded by ruling")
    gate("pp of global FX reserves per year" in str(f5["layout"]["yaxis"]),
         "exhibit 5 is labelled as a flow in pp per year, not as a share")

    print("\nEditorial deletions - gated on absence")
    with open(root / manifest["charts"][0]["csv"], encoding="utf-8-sig") as fh:
        hdr1 = fh.readline().strip().split(",")
    gate(hdr1 == ["date", "jpy_observed"],
         "chart 1 ships without jpy_cer, the column the published chart never drew",
         str(hdr1))
    gate(all("cer" not in t["name"].lower() for t in f1["data"])
         and len(f1["data"]) == 1,
         "chart 1 draws one line, as published")
    with open(root / manifest["charts"][4]["csv"], encoding="utf-8-sig") as fh:
        hdr5 = fh.readline().strip().split(",")
    gate(hdr5 == ["date", "usd_netaccum"],
         "chart 5 ships one net-accumulation column, with no r2 residual variant",
         str(hdr5))

    print("\nWhat this page offers")
    # Resolved from the manifest the same way build_panel.py resolves it, and
    # restated rather than imported so the gate cannot agree with the builder by
    # construction. Which of the two variants this is comes off the slug, not off
    # the tier: the two are independent, and reading one from the other is the
    # conflation this key was split to remove.
    tier = manifest["tier"]
    downloads = manifest["downloads"] if "downloads" in manifest else tier != "free"
    is_paid_variant = manifest["slug"] == FXJPY_PAID

    if downloads:
        gate(page.count("Download CSV") == len(manifest["charts"]),
             "one CSV download per exhibit",
             f"{page.count('Download CSV')}")
    else:
        gate("Download CSV" not in page and 'class="dl"' not in page,
             "no per-chart download offered")
        gate("Download the full workbook" not in page,
             "no workbook download offered")

    if is_paid_variant:
        gate("workbook" not in manifest,
             "the paid page declares no workbook download: the .xlsx is Takuji's "
             "to send and jma-data is public")
        gate("Only paid subscribers have access to this page" in page,
             "paid page says so")

    print("\nCross-tier equality")
    sibling = REPO / (FXJPY_FREE if is_paid_variant else FXJPY_PAID)
    if not (sibling / "index.html").exists():
        gate(False, "the sibling tier is built, so the two can be compared",
             f"{sibling.name} has no index.html")
        return
    _, sfigs = load_delivered(sibling)
    same = True
    for c in manifest["charts"]:
        cid = f"chart_{c['n']}"
        mine = {t["name"]: t["y"] for t in figs[cid]["data"]}
        theirs = {t["name"]: t["y"] for t in sfigs[cid]["data"]}
        if mine != theirs:
            same = False
            gate(False, f"chart {c['n']} draws the same values on both tiers")
    gate(same, "every exhibit draws identical values on the free and paid pages",
         f"5 exhibits vs {sibling.name}")


BOJ_EB_TITLES = [
    "Majority of BoJ's assets are low-yielding",
    "80% of BoJ's funding costs move with policy rate",
    "Funding cost passed JGB income in FY2025",
    "Low-yielding JGBs take a decade to roll off the BoJ",
    "Policy rate scenarios",
    "10-year JGB yield scenarios",
    "BoJ portfolio P/L: losses as the policy rate rises to 2.0%",
    "Reserves to decline by 50% by FY2028",
    "30-year JGB yield scenarios",
    "Remittance to public coffer drops to zero as rates rise",
    "A fiscal crisis pushes the BoJ into sustained loss",
]


def qa_boj_equity_bet(root, manifest, page, figs) -> None:
    """The free panel to "The BoJ's Equity Bet Is Paying for QE Exit".

    Eight published exhibits in post order, then three built-for-the-report
    charts behind a section header. Every figure the report prints is
    re-derived from the delivered files; the balance-sheet exhibits are tables
    (no plotly figure), so their gates run on the delivered CSVs and the page
    HTML. Engine figures are the distribution-growth basis of 2026-08-11.
    """
    def csv_rows(name):
        with open(root / "data" / name, newline="", encoding="utf-8-sig") as f:
            return list(csv.DictReader(f))

    def series_pairs(fig, name):
        # split_col emits a solid and a dashed trace per series, same name:
        # merge them into {x: y} keeping the non-null value.
        out = {}
        for t in fig["data"]:
            if t.get("name") == name:
                for x, y in zip(t["x"], t["y"]):
                    if y is not None:
                        out[x] = y
        return out

    print("\nTitles, order, section")
    h2s = re.findall(r"<h2>(.*?)</h2>", page.replace("&#x27;", "'"))
    ex = [t for t in h2s if t in BOJ_EB_TITLES]
    gate(len(ex) == 11 and ex == BOJ_EB_TITLES,
         "the eleven exhibits run in ledger order", str(len(ex)))
    gate(page.count("Built for the report, held out of the post") == 1,
         "the held-out section header appears exactly once")
    gate(f'href="{manifest["post_url"]}"' in page, "links back to the post")

    print("\nExhibits 1-2 — the balance sheet (tables; gates on delivered CSVs)")
    a = csv_rows("chart-1-balance-sheet-assets.csv")
    gate(len(a) == 8, "assets table: seven lines plus the at-market memo",
         f"{len(a)} rows")
    tot_a = sum(float(r["trn"]) for r in a[:-1])
    gate(abs(tot_a - 639.551) < 0.01, "asset lines sum to the published ¥639.55trn",
         f"{tot_a:.3f}")
    gate(abs(float(a[-1]["trn"]) - 107.57) < 0.02,
         "the ETF-at-market memo is ¥107.6trn", a[-1]["trn"])
    li = csv_rows("chart-2-balance-sheet-liabilities.csv")
    gate(len(li) == 7 and abs(sum(float(r["trn"]) for r in li) - 639.551) < 0.01,
         "liability lines sum to the same total")
    res = [r for r in li if r["line_en"] == "Reserves"]
    gate(len(res) == 1 and abs(float(res[0]["trn"]) - 440.365) < 0.001,
         "the Reserves row carries ¥440.4trn at 1.00%", res and res[0]["trn"])
    rep = sum(float(r["trn"]) for r in li if r["moves_with_policy_rate"] == "Yes")
    gate(abs(rep - 506.827) < 0.01 and abs(rep / 639.551 - 0.792) < 0.002,
         "repricing liabilities are ¥506.8trn = 79.2%, the title's 80%",
         f"{rep:.3f} = {rep / 639.551 * 100:.1f}%")

    print("\nExhibit 3 — the carry crossing")
    inc = series_pairs(figs["chart_3"], "JGB income")
    paid = series_pairs(figs["chart_3"], "Interest paid")
    gate(len(inc) == 9 and len(paid) == 9, "both lines span FY2020-FY2028",
         f"{len(inc)}/{len(paid)}")
    gate(abs(inc["2025"] - 2.52) < 0.005 and abs(paid["2025"] - 3.09) < 0.005,
         "FY2025: income 2.52 against 3.09 paid", f"{inc['2025']}/{paid['2025']}")
    gate(paid["2024"] < inc["2024"] and paid["2025"] > inc["2025"],
         "the crossing is AT FY2025 — the title's claim, audited")

    print("\nExhibit 4 — the redemption wall")
    f4 = figs["chart_4"]
    bands = {t["name"]: [y for y in t["y"] if y is not None]
             for t in f4["data"] if t["type"] == "bar"}
    gate(len(bands) == 4, "four display bands, as published", str(len(bands)))
    coral = sum(bands["Yield at purchase: below zero"])
    gate(abs(coral - 37.4) < 0.2, "the below-zero band totals ¥37.4trn",
         f"{coral:.1f}")
    grand = sum(sum(v) for v in bands.values())
    gate(abs(grand - 519.4) < 0.5, "the stack totals the ¥519.4trn book",
         f"{grand:.1f}")

    print("\nExhibits 5, 6, 9 — the scenario paths")
    ends = {"chart_5": ("Base case", 1.50, "2.0% case", 2.00,
                        "Accelerated 2.5%", 2.50),
            "chart_6": ("Base case", 3.13, "2.0% case", 3.61,
                        "Accelerated 2.5%", 4.06),
            "chart_9": ("Base case", 3.80, "2.0% case", 4.31,
                        "Accelerated 2.5%", 4.81)}
    for cid, (n1, v1, n2, v2, n3, v3) in ends.items():
        for name, want in ((n1, v1), (n2, v2), (n3, v3)):
            pairs = series_pairs(figs[cid], name)
            # Base spans the full window, 2022-01..2029-07 = 91 months; the two
            # alternative scenarios exist only from the 2026-07 seam = 37.
            expect_n = 91 if name == n1 else 37
            gate(len(pairs) == expect_n,
                 f"{cid} {name}: exactly {expect_n} monthly points",
                 str(len(pairs)))
            last = pairs[max(pairs)]
            gate(abs(last - want) < 0.005, f"{cid} {name} ends at {want:.2f}",
                 f"{last:.2f}")
        base = series_pairs(figs[cid], n1)
        for name in (n2, n3):
            pairs = series_pairs(figs[cid], name)
            first = min(pairs)
            gate(first == "2026-07-01" and abs(pairs[first] - base[first]) < 1e-9,
                 f"{cid} {name} starts at the 2026-07 seam on the actual value")

    print("\nExhibit 7 — P/L under three scenarios")
    f7 = figs["chart_7"]
    b7 = {t["name"]: t["y"] for t in f7["data"]}
    gate([round(v, 2) for v in b7["Base case"]] == [0.69, 0.58, 2.04],
         "base case +0.69 / +0.58 / +2.04", str(b7["Base case"]))
    gate(abs(b7["2.0% case"][1] - (-0.44)) < 0.005,
         "the 2.0% case loses 0.44 in FY2027", str(b7["2.0% case"][1]))
    gate([round(v, 2) for v in b7["Accelerated 2.5%"][1:]] == [-1.78, -1.11],
         "the accelerated case loses 1.78 then 1.11",
         str(b7["Accelerated 2.5%"][1:]))

    print("\nExhibit 8 — reserves halve")
    f8 = figs["chart_8"]
    t8 = next(t for t in f8["data"] if t["type"] == "bar")
    vals = dict(zip(t8["x"], t8["y"]))
    gate(len(vals) == 10, "ten fiscal-year bars", str(len(vals)))
    gate(abs(vals["FY2023"] - 561) < 1 and abs(vals["FY2028"] - 282) < 1,
         "561 at FY2023, 282 at FY2028", f"{vals['FY2023']}/{vals['FY2028']}")
    ratio = vals["FY2028"] / vals["FY2023"]
    gate(0.49 <= ratio <= 0.52, "the title's halving claim holds",
         f"{ratio:.3f}")
    faded = t8["marker"]["opacity"].count(0.55)
    gate(faded == 4, "exactly the four estimate bars render faded", str(faded))

    print("\nExhibit 10 — the remittance")
    b10 = {t["name"]: t["y"] for t in figs["chart_10"]["data"]}
    for name, want in (("Base case", 2.74), ("2.0% case", 0.80),
                       ("Accelerated 2.5%", 0.38)):
        got = sum(b10[name])
        gate(abs(got - want) < 0.011, f"{name} three-year total {want:.2f}",
             f"{got:.2f}")
    zeros = [b10["2.0% case"][1], b10["Accelerated 2.5%"][1],
             b10["Accelerated 2.5%"][2]]
    gate(all(abs(z) < 0.005 for z in zeros),
         "the three zero-payment years are drawn at zero", str(zeros))

    print("\nExhibit 11 — the stagflation")
    b11 = {t["name"]: t["y"] for t in figs["chart_11"]["data"]}
    gate([round(v, 2) for v in b11["Stagflation crisis"][1:]] ==
         [-3.21, -2.80, -1.48],
         "stagflation loses 3.21 / 2.80 / 1.48 across FY2027-29",
         str(b11["Stagflation crisis"][1:]))
    gate(abs(b11["Base case"][0] - 0.69) < 0.005
         and abs(b11["Stagflation crisis"][0] - 0.51) < 0.005,
         "FY2026 is +0.69 base against +0.51 stagflation")

    print("\nWhat the free page must not offer")
    gate(page.count("Download CSV") == 0,
         "no per-chart download link on any of the eleven exhibits")
    gate("Download the full workbook" not in page,
         "no workbook button")
    gate("workbook" not in manifest, "and no workbook declared")
    gate("Paid subscribers receive the data behind every chart" in page,
         "the free-tier perk block states what a subscription buys")


QA = {"2026-07-20-long-climb": qa_long_climb,
      "2026-08-12-boj-equity-bet": qa_boj_equity_bet,
      "jgb-yield-curve-model": qa_yield_curve,
      FXJPY_FREE: qa_fx_reserve_jpy,
      FXJPY_PAID: qa_fx_reserve_jpy,
      "2026-07-31-fx-carry-unwind": qa_fx_carry_unwind,
      "jgb-forecast-main": qa_scenario_forecast,
      "jgb-forecast-alternative": qa_scenario_forecast,
      "jgb-yield-curve-main": qa_scenario_model,
      "jgb-yield-curve-alternative": qa_scenario_model,
      "2026-08-03-jgb-warsh": qa_warsh_panel,
      "global-fx-reserve-share": qa_global_fx_reserve_shares}

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
