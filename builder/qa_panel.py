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


def qa_yield_curve(root, manifest, page, figs) -> None:
    panel = list(csv.DictReader(open(root / "data/jma-jgb-yield-curve-panel.csv",
                                     newline="", encoding="utf-8-sig")))
    by_ym = {r["YM"]: r for r in panel}
    last_actual = [r["YM"] for r in panel if r["Type"] == "actual"][-1]

    # ---- the identity, checked on what the page actually plots -------------
    print("\nChart 1 — 10Y decomposition")
    f1 = figs["chart_1"]
    bars = [t for t in f1["data"] if t["type"] == "bar"]
    lines = [t for t in f1["data"] if t["type"] == "scatter"]
    gate([t["name"] for t in bars] == ["Interest rate expectations", "Term premium"],
         "components drawn as stacked bars, expectations first")
    gate(f1["layout"]["barmode"] == "relative",
         "relative stacking, so a negative premium hangs below zero")
    gate(any(s["y0"] == 0 and s.get("xref") == "paper"
             for s in f1["layout"]["shapes"]), "zero line drawn")

    # the total line is split across two traces; merge them back
    total = [a if a is not None else b
             for a, b in zip(lines[0]["y"], lines[1]["y"])]
    rn, tp = bars[0]["y"], bars[1]["y"]
    breaks = [(lines[0]["x"][i], total[i], rn[i], tp[i])
              for i in range(len(total))
              if None not in (total[i], rn[i], tp[i])
              and abs(total[i] - (rn[i] + tp[i])) > 2e-3]
    gate(not breaks, "Yield = expectations + term premium on every plotted point",
         f"{len(total)} points checked" if not breaks else str(breaks[:2]))
    gate(min(v for v in tp if v is not None) < 0,
         "the term premium does go negative — the reason for relative stacking",
         f"min {min(v for v in tp if v is not None)}")

    # ---- history / projection split ---------------------------------------
    gate(len(lines) == 2 and lines[1].get("showlegend") is False,
         "total drawn as history + projection")
    gate(lines[1]["line"].get("dash") == "dot", "projection leg dotted")
    li = max(i for i, v in enumerate(lines[0]["y"]) if v is not None)
    gate(lines[0]["x"][li][:7] == last_actual,
         "solid history ends at the last actual month",
         f"{lines[0]['x'][li][:7]} == {last_actual}")
    gate(lines[1]["y"][li] is not None,
         "projection leg carries the last actual point, so the lines join")
    ops = bars[0]["marker"]["opacity"]
    gate(ops[li] == 1.0 and ops[li + 1] < 1.0,
         "projection bars lightened from the first forecast month")
    gate(any(a.get("text") == "forecast →" for a in f1["layout"].get("annotations", [])),
         "forecast boundary marked on the chart")

    # ---- chart 2: term premia, 40Y coverage --------------------------------
    print("\nChart 2 — term premia by maturity")
    f2 = figs["chart_2"]
    t40 = [t for t in f2["data"] if t["name"] == "40Y"][0]
    first_i = next(i for i, v in enumerate(t40["y"]) if v is not None)
    gate(t40["x"][first_i][:7] == "2007-11",
         "40Y term premium starts at first issuance, Nov 2007", t40["x"][first_i][:7])
    gate(all(v is None for v in t40["y"][:first_i]),
         "pre-issuance months are null, not zero")

    # ---- chart 4: the cross-section ----------------------------------------
    print("\nChart 4 — curve cross-section")
    f4 = figs["chart_4"]
    tenors = [2, 5, 10, 20, 30, 40]
    labels = [f"{t}Y" for t in tenors]
    gate(f4["layout"]["xaxis"].get("type") == "category",
         "maturities spaced evenly, so the short end is readable")
    for ln in manifest["charts"][3]["lines"]:
        t = trace(f4, ln["label"])
        gate(t["x"] == labels, f"{ln['label']}: plotted at every maturity")
        src = [round(float(by_ym[ln["ym"]][f"Yield_{n}Y"]), 3) for n in tenors]
        gate(t["y"] == src, f"{ln['label']}: matches the panel row for {ln['ym']}")

    # ---- cross-source: the curve vs the published forecast table -----------
    print("\nCross-source consistency")
    ft = list(csv.DictReader(open(root / "data/jgb-spot-yield-forecast.csv",
                                  newline="", encoding="utf-8-sig")))
    label_by_ym = {r["ym"]: r for r in ft}
    for ln in manifest["charts"][3]["lines"]:
        row = label_by_ym.get(ln["ym"])
        if not row:
            continue
        t = trace(f4, ln["label"])
        diffs = {f"{n}Y": round(t["y"][i] - float(row[f"{n}Y"]), 4)
                 for i, n in enumerate(tenors) if f"{n}Y" in row}
        worst = max(abs(v) for v in diffs.values())
        gate(worst <= 0.005,
             f"curve at {ln['ym']} agrees with the published forecast table",
             f"largest gap {worst:.4f}pp")

    # ---- chart 5: the table ------------------------------------------------
    print("\nTable")
    gate(page.count("<tr") == len(ft) + 1, "every table row rendered")
    gate('class="rule"' in page, "actual/forecast rule drawn")


QA = {"2026-07-20-long-climb": qa_long_climb,
      "jgb-yield-curve-model": qa_yield_curve}


def main(slug: str) -> int:
    root = REPO / slug
    manifest = json.loads((root / "panel.json").read_text(encoding="utf-8"))
    page, figs = load_delivered(root)
    print(f"QA {slug} — {len(manifest['charts'])} exhibits\n")
    qa_structure(manifest, page, figs)
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
