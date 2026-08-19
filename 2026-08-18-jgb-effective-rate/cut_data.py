#!/usr/bin/env python3
"""Cut this page's tidy CSVs from the chart library's master files.

PATH A (substack-page skill step 1): the source of truth is the committed master
CSV behind each published exhibit, never a pipeline run. What each cut keeps,
drops and reshapes — and why — is the exhibit ledger in the report record,
`30.Reports/2026-08/2026-08-18-jgb-effective-rate-sub.md`. This script is the
ledger executed; if the two disagree the ledger is what a reader was told.

Every cut re-derives the figure the report prints and refuses to write on
disagreement. The point is not that the masters might be wrong — it is that a
cut that silently selects the wrong column produces a plausible page. The 1.5%
main case sits beside the 2% case in one of these files under a near-identical
name, and the report shows only the 2% case.

    python 2026-08-18-jgb-effective-rate/cut_data.py
"""
from __future__ import annotations

import csv
from pathlib import Path

CHARTS = Path(r"G:\My Drive\charts")
RESEARCH = Path(r"G:\My Drive\Research\JGB_related\jgb_market_presence\supply\effective_rate")
OUT = Path(__file__).resolve().parent / "data"
OUT.mkdir(exist_ok=True)

checks: list[tuple[str, object, object]] = []


def check(what: str, got, want) -> None:
    checks.append((what, got, want))


def write(name: str, fieldnames: list[str], rows: list[dict]) -> None:
    path = OUT / name
    with open(path, "w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=fieldnames, lineterminator="\n")
        w.writeheader()
        w.writerows(rows)
    print(f"  {name}: {len(rows)} rows x {len(fieldnames)} cols")


def read(path: Path) -> list[dict]:
    with open(path, newline="", encoding="utf-8") as f:
        return list(csv.DictReader(f))


def f(v):
    return None if v in ("", None) else float(v)


# ---------------------------------------------------------------- 1. Table 1
# Master is the table script's own upstream input; this chart folder holds no
# *_data.csv. Formatted here to the precision the published table prints,
# because the page renders the table as text and a reader compares it to the
# report cell by cell.
src = read(RESEARCH / "coupon_decomposition_2026-07.csv")
key0 = list(src[0].keys())[0]                     # the label column is unnamed
LABELS = {"T-bills*": "T-bills*", "<=0.5%": "Coupon \u2264 0.5%",
          "0.6-1.0%": "0.6\u20131.0%", "1.1-2.0%": "1.1\u20132.0%",
          ">2.0%": "> 2.0%", "All marketable": "All marketable"}
rows = []
for r in src:
    lab = LABELS[r[key0]]
    rows.append({
        "bucket": lab,
        "outstanding": f"{float(r['trn']):,.0f}",
        "share": f"{float(r['share_pct']):.0f}%",
        # The T-bill figure is an auction yield, not a coupon; the asterisk is
        # what the footnote hangs on and the published table carries it.
        "avg_coupon": f"{float(r['avg_coupon']):.2f}%"
                      + ("*" if lab.startswith("T-bills") else ""),
    })
by = {r["bucket"]: r for r in rows}
check("table: total outstanding", by["All marketable"]["outstanding"], "1,259")
check("table: total avg coupon", by["All marketable"]["avg_coupon"], "1.00%")
check("table: <=0.5% share", by["Coupon \u2264 0.5%"]["share"], "35%")
check("table: <=0.5% outstanding", by["Coupon \u2264 0.5%"]["outstanding"], "443")
check("table: T-bill yield", by["T-bills*"]["avg_coupon"], "0.88%*")
check("table: rows", len(rows), 6)
write("chart-1-coupon-composition.csv",
      ["bucket", "outstanding", "share", "avg_coupon"], rows)

# ------------------------------------------------------------------ 2. Chart 1
# The 2% terminal-rate scenario is the published one (SCEN = "risk200" in the
# script, Takuji's ruling 2026-08-18). The 1.5% main case lives in the same file
# under *_main and is deliberately not cut: publishing it would put a second,
# lower path in front of a reader the report never showed.
src = read(CHARTS / "fiscal/jgb-effective-rate/jgb_effective_rate_data.csv")
rows = [{"fy": r["fy"],
         "policy_rate": r["policy_rate_avg_risk200"],
         "eff_rate": r["eff_rate_all_risk200"],
         "interest_bill": r["interest_bill_trn_risk200"],
         "phase": r["type"]} for r in src]
by = {r["fy"]: r for r in rows}
# Report: ~1.1% in FY2026 rising to 1.6% in FY2028; bill ~Y21trn, double FY2025.
check("chart 1: FY2026 effective rate", round(f(by["2026"]["eff_rate"]), 1), 1.1)
check("chart 1: FY2028 effective rate", round(f(by["2028"]["eff_rate"]), 1), 1.6)
check("chart 1: FY2028 policy rate", f(by["2028"]["policy_rate"]), 2.0)
check("chart 1: FY2028 interest bill", round(f(by["2028"]["interest_bill"]), 1), 21.3)
check("chart 1: FY2025 interest bill", round(f(by["2025"]["interest_bill"]), 1), 10.6)
check("chart 1: last actual year", [r["fy"] for r in rows if r["phase"] == "actual"][-1], "2025")
check("chart 1: main case not cut",
      [c for c in rows[0] if "main" in c], [])
write("chart-2-effective-rate.csv",
      ["fy", "policy_rate", "eff_rate", "interest_bill", "phase"], rows)

# ------------------------------------------------------------------ 3. Chart 2
# Germany dropped (Takuji 2026-08-19, the Indebted Five). The UK column is
# quarterly against four monthly neighbours and stays sparse here; the manifest
# bridges it on that series alone.
src = read(CHARTS / "fiscal/g6-debt-avg-maturity/g6_debt_avg_maturity_data.csv")
COUNTRY = [("jpn_debtmat_m", "japan"), ("gbr_debtmat_q", "uk"),
           ("fra_debtmat_aft_m", "france"), ("ita_debtmat_mef_m", "italy"),
           ("usa_debtmat_m", "us")]
rows = [dict({"date": r["date"]}, **{out: r.get(col, "") for col, out in COUNTRY})
        for r in src if r["date"] >= "2001-01-01"]


def last(col: str, data=None):
    for r in reversed(data or rows):
        if r[col] not in ("", None):
            return float(r[col])
    raise AssertionError(col)


# Report: Japan 8.6y, France 8.5, Italy 7.0, US 5.8, UK 13.4.
check("chart 2: Japan latest", round(last("japan"), 1), 8.6)
check("chart 2: France latest", round(last("france"), 1), 8.5)
check("chart 2: Italy latest", round(last("italy"), 1), 7.0)
check("chart 2: US latest", round(last("us"), 1), 5.8)
check("chart 2: UK latest", round(last("uk"), 1), 13.4)
check("chart 2: Germany dropped", [c for c in rows[0] if "deu" in c or c == "germany"], [])
check("chart 2: UK is sparse (quarterly on a monthly grid)",
      sum(1 for r in rows if r["uk"]) < len(rows) // 2, True)
write("chart-3-debt-avg-maturity.csv",
      ["date", "japan", "uk", "france", "italy", "us"], rows)

# ------------------------------------------------------------------ 4. Chart 3
# History and IMF projection arrive as two columns per country; merged to one
# column plus a phase flag so the builder draws the projection dashed. Germany
# dropped; Canada was never in this file and its absence is why the claim reads
# "Indebted Five" and not G7.
src = read(CHARTS / "fiscal/g6-gg-net-interest-pgdp/g6_gg_net_interest_pgdp_data.csv")
CODES = [("jpn", "japan"), ("usa", "us"), ("ita", "italy"),
         ("fra", "france"), ("gbr", "uk")]
rows = []
for r in src:
    if r["date"] < "1999-12-31":
        continue
    out, phases = {"date": r["date"]}, set()
    for code, name in CODES:
        hist = r.get(f"{code}_gg_net_interest_pgdp_a", "")
        proj = r.get(f"{code}_gg_net_interest_pgdp_proj_a", "")
        # Lossless merge: the ledger records that the two are never both set.
        assert not (hist and proj), f"{r['date']} {code}: history and projection both set"
        out[name] = hist or proj
        if hist or proj:
            phases.add("actual" if hist else "projection")
    assert len(phases) <= 1, f"{r['date']}: mixed phases {phases}"
    out["phase"] = phases.pop() if phases else ""
    rows.append(out)
by = {r["date"][:4]: r for r in rows}
# Report, 2026: JP 0.3, US 3.8, IT 3.6, UK 2.7, FR 2.2. 2031: JP 1.7, US 4.3,
# IT 4.3, FR 3.3, UK 3.0.
for yr, want in (("2026", {"japan": 0.3, "us": 3.8, "italy": 3.6, "uk": 2.7, "france": 2.2}),
                 ("2031", {"japan": 1.7, "us": 4.3, "italy": 4.3, "france": 3.3, "uk": 3.0})):
    for name, v in want.items():
        check(f"chart 3: {name} {yr}", round(f(by[yr][name]), 1), v)
check("chart 3: Japan lowest of the five in 2031",
      min(CODES, key=lambda c: f(by["2031"][c[1]]))[1], "japan")
check("chart 3: last actual year",
      [r["date"][:4] for r in rows if r["phase"] == "actual"][-1], "2024")
check("chart 3: Germany dropped", [c for c in rows[0] if "deu" in c or c == "germany"], [])
write("chart-4-net-interest-pgdp.csv",
      ["date", "japan", "us", "italy", "france", "uk", "phase"], rows)

# ------------------------------------------------------------------ 5. Chart 4
# band_hi / band_lo reproduce the published fill_between(where=gross >=
# consolidated): the two lines cross before QQE and that stretch is left
# unshaded. gap_years is dropped — it is the difference of the two exactly.
src = read(CHARTS / "boj/consolidated-maturity/japan_govt_debt_avg_maturity_data.csv")
rows = []
for r in src:
    g, c = float(r["gross_years"]), float(r["consolidated_years"])
    shaded = g >= c
    rows.append({"date": r["date"], "gross_years": r["gross_years"],
                 "consolidated_years": r["consolidated_years"],
                 "band_hi": r["gross_years"] if shaded else "",
                 "band_lo": r["consolidated_years"] if shaded else ""})
check("chart 4: gross latest", round(float(rows[-1]["gross_years"]), 1), 8.6)
check("chart 4: consolidated latest", round(float(rows[-1]["consolidated_years"]), 1), 6.5)
ref = [r for r in rows if r["date"].startswith("2013-03")][0]
check("chart 4: pre-QQE consolidated (Mar 2013)",
      round(float(ref["consolidated_years"]), 1), 6.4)
check("chart 4: pre-QQE stretch left unshaded", ref["band_hi"], "")
trough = min((r for r in rows if r["date"] >= "2013-06"),
             key=lambda r: float(r["consolidated_years"]))
check("chart 4: consolidated trough", round(float(trough["consolidated_years"]), 1), 5.0)
check("chart 4: trough month", trough["date"][:7], "2021-05")
# Every episode marker the manifest declares must be a month this CSV carries.
dates = {r["date"][:7] for r in rows}
for ym in ("2010-10", "2013-04", "2016-09", "2024-03"):
    check(f"chart 4: episode {ym} present", ym in dates, True)
write("chart-5-consolidated-maturity.csv",
      ["date", "gross_years", "consolidated_years", "band_hi", "band_lo"], rows)

# ---------------------------------------------------------------------- verdict
print()
bad = [(w, g, x) for w, g, x in checks if g != x]
for w, g, x in checks:
    print(f"  {'ok ' if g == x else 'BAD'}  {w}: {g!r}" + ("" if g == x else f" != {x!r}"))
print(f"\n{len(checks) - len(bad)}/{len(checks)} checks agree with the report")
if bad:
    raise SystemExit("cut refused: the master disagrees with the published figure")
