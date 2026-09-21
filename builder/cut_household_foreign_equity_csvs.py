"""Cut the eight tidy CSVs for the household report's free chart page.

Path A: every number comes from the chart library's committed master CSV, never
from a pipeline run. The ledger below is the one written into the report record
(30.Reports/2026-09/2026-09-15-household-foreign-equity-sub.md); that record
carries the reason for every dropped column, and the chart-data-workbook skill
reads it rather than re-reading the report.

`n` is the exhibit's number in the published article, not its position on this
page, so the page's "Chart 4" is the article's chart 4. The article has twelve
exhibits; this page carries the eight that are time series (Takuji: "just
listing time series charts in this report as interactive charts").

Four derivations happen here rather than in the manifest, because the builder's
manifest cannot express them. Each asserts what it found before it writes.

1. Chart 1 merges three fund columns into one band and two direct columns into
   another, exactly as hh_foreign_assets_by_type.py does (Takuji, 2026-09-20:
   eight bands were too many).
2. Chart 2 converts the master's yen billions to the chart's trillions.
3. Chart 7 is the script's `--long --per-month` cut: a quarterly-era issue is
   spread over the three months it covers, so heights are comparable across the
   cadence break at 2010-12.
4. Chart 8 forward-fills the BoJ's rate on current-account balances from the
   regime table onto the month-end grid of the deposit-rate file. The pre-
   2024-03-21 tiered regime is left blank because the published chart does not
   draw it.
"""
import csv
from datetime import date
from pathlib import Path

LIB = Path(r"G:\My Drive\charts")
HH = LIB / "household-assets"
REPO = Path(r"C:\repos\jma-data")
SLUG = "2026-09-15-household-foreign-equity"
OUT = REPO / SLUG / "data"

MONTH = ["", "Jan", "Feb", "Mar", "Apr", "May", "Jun",
         "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"]


def load(path: Path) -> list[dict]:
    with path.open(newline="", encoding="utf-8-sig") as f:
        rows = list(csv.DictReader(f))
    if not rows:
        raise SystemExit(f"{path} is empty")
    return rows


def write(name: str, cols: list[str], rows: list[dict], msg: str) -> None:
    body = "".join(",".join(str(r.get(c, "")) for c in cols) + "\n" for r in rows)
    (OUT / name).write_text(",".join(cols) + "\n" + body, encoding="utf-8",
                            newline="")
    print(f"  {name:<44} {len(rows):>4} rows  {msg}")


def need(rows: list[dict], cols: list[str], what: str) -> None:
    have = list(rows[0].keys())
    missing = [c for c in cols if c not in have]
    if missing:
        raise SystemExit(f"{what}: master lacks {missing}; has {have}")


OUT.mkdir(parents=True, exist_ok=True)
print(f"cutting {SLUG}/data from the chart-library masters")

# ---------------------------------------------------------------- chart 1
# Households' foreign assets by type. Six bands, two of them merges the
# producing script makes in load(); reproduced here against the same columns.
src = HH / "hh-foreign-assets-by-type" / "hh_foreign_assets_by_type_fy_data.csv"
rows = load(src)
need(rows, ["end_date", "funds_stock_scaled_tn", "funds_bond_scaled_tn",
            "funds_balanced_foreign_scaled_tn", "funds_other_scaled_tn",
            "funds_reit_scaled_tn", "fx_deposits_tn", "direct_debt_tn",
            "direct_equity_tn", "direct_fund_shares_tn"], "chart 1")
c1 = []
for r in rows:
    d = date.fromisoformat(r["end_date"])
    c1.append(dict(
        as_of=f"{MONTH[d.month]} {d.year}",
        end_date=r["end_date"],
        funds_equity_tn=f'{float(r["funds_stock_scaled_tn"]):.4f}',
        funds_bond_tn=f'{float(r["funds_bond_scaled_tn"]):.4f}',
        funds_balanced_other_tn=f'{float(r["funds_balanced_foreign_scaled_tn"]) + float(r["funds_other_scaled_tn"]) + float(r["funds_reit_scaled_tn"]):.4f}',
        fx_deposits_and_bonds_tn=f'{float(r["fx_deposits_tn"]) + float(r["direct_debt_tn"]):.4f}',
        direct_equity_tn=f'{float(r["direct_equity_tn"]):.4f}',
        direct_fund_shares_tn=f'{float(r["direct_fund_shares_tn"]):.4f}',
    ))
BANDS1 = ["funds_equity_tn", "funds_bond_tn", "funds_balanced_other_tn",
          "fx_deposits_and_bonds_tn", "direct_equity_tn", "direct_fund_shares_tn"]
tot_first = sum(float(c1[0][c]) for c in BANDS1)
tot_last = sum(float(c1[-1][c]) for c in BANDS1)
assert abs(tot_first - 57.84) < 0.05, tot_first     # the article's "58 trillion yen"
assert abs(tot_last - 189.25) < 0.05, tot_last      # the article's and headline's 189
assert c1[0]["as_of"] == "Mar 2010" and c1[-1]["as_of"] == "Jun 2026", c1[-1]
write("chart-1-foreign-assets-by-type.csv", ["as_of", "end_date"] + BANDS1, c1,
      f"band sum {tot_first:.1f} -> {tot_last:.1f} tn")

# ---------------------------------------------------------------- chart 2
# All household assets in five parts. yen bn -> yen tn; the last two rows are
# JMA estimates and carry the flag the manifest splits on.
src = HH / "hh-total-asset-composition" / "hh_total_asset_composition_data.csv"
rows = load(src)
need(rows, ["year", "land_bn", "other_real_bn", "deposits_bn",
            "insurance_pension_bn", "securities_other_bn", "total_assets_bn",
            "is_estimate"], "chart 2")
PARTS2 = [("land", "land_bn"), ("other_real", "other_real_bn"),
          ("deposits", "deposits_bn"), ("insurance_pension", "insurance_pension_bn"),
          ("securities_other", "securities_other_bn")]
c2 = []
for r in rows:
    y = float(r["year"])
    # 2025.5 is the end-June 2026 estimate; every other row is a calendar
    # year-end stock. The label is "Mon YYYY" and never a bare year, for two
    # reasons: it says which month the stock is measured at, and it keeps the
    # x values off Plotly's numeric path. A numeric-looking category value is
    # coerced to a number, which puts this chart's estimate boundary at
    # category slot 2024 on a 58-slot axis (the builder records that defect
    # from the Canada page, where every numeric gate passed and only the
    # drawing was wrong).
    label = "Jun 2026" if y == 2025.5 else f"Dec {int(y)}"
    row = dict(as_of=label, is_estimate=r["is_estimate"])
    for name, col in PARTS2:
        row[f"{name}_tn"] = f'{float(r[col]) / 1000.0:.3f}'
    c2.append(row)
est = [r["as_of"] for r in c2 if r["is_estimate"] == "True"]
assert est == ["Dec 2025", "Jun 2026"], est
assert c2[0]["as_of"] == "Dec 1969", c2[0]
assert not any(r["as_of"].isdigit() for r in c2), "a bare-year category breaks the boundary marker"
land90 = next(r for r in c2 if r["as_of"] == "Dec 1990")
t90 = sum(float(land90[f"{n}_tn"]) for n, _ in PARTS2)
t_now = sum(float(c2[-1][f"{n}_tn"]) for n, _ in PARTS2)
s90 = float(land90["land_tn"]) / t90 * 100
s_now = float(c2[-1]["land_tn"]) / t_now * 100
assert round(s90) == 54 and round(s_now) == 21, (s90, s_now)   # the chart's headline
write("chart-2-household-assets-composition.csv",
      ["as_of", "is_estimate"] + [f"{n}_tn" for n, _ in PARTS2], c2,
      f"land {s90:.1f}% (1990) -> {s_now:.1f}% (Jun 2026)")

# ---------------------------------------------------------------- chart 4
# Fund fees. The master is long (one row per year per series); pivoted to one
# column per series. The eMAXIS Slim All Country marker is a single 2025 point
# and is dropped: the builder draws lines, and a one-point line is invisible.
# Its 0.06% is carried in the chart's note instead.
src = HH / "hh-fund-fees" / "hh_fund_fees_data.csv"
rows = load(src)
need(rows, ["year", "series", "fee_pct"], "chart 4")
fsa = [r for r in rows if r["series"] == "fsa_all_funds_weighted"]
emx = [r for r in rows if r["series"] == "emaxis_slim_all_country"]
assert len(emx) == 1 and emx[0]["year"] == "2025", emx
assert len(fsa) == 25 and fsa[0]["year"] == "2001" and fsa[-1]["year"] == "2025", len(fsa)
c4 = [dict(year=r["year"], avg_fee_pct=r["fee_pct"]) for r in fsa]
lookup = {r["year"]: float(r["fee_pct"]) for r in fsa}
for y, v in (("2001", 1.52), ("2010", 1.46), ("2020", 1.30), ("2025", 0.94)):
    assert abs(lookup[y] - v) < 0.005, (y, lookup[y])    # the article's four figures
EMAXIS_FEE = float(emx[0]["fee_pct"])
assert round(EMAXIS_FEE, 2) == 0.06, EMAXIS_FEE          # the article's "as little as 0.06%"
write("chart-4-fund-fees.csv", ["year", "avg_fee_pct"], c4,
      f"{lookup['2001']:.2f}% -> {lookup['2025']:.2f}%; eMAXIS {EMAXIS_FEE:.5f}% dropped")

# ---------------------------------------------------------------- chart 6
# Foreign-equity fund inflows, the script's VIEW_START = 2022-01. yen bn -> tn.
src = HH / "hh-foreign-equity-fund-flows" / "hh_foreign_equity_fund_flows_data.csv"
rows = load(src)
need(rows, ["month", "foreign_equity_bn", "foreign_equity_3m_avg_bn"], "chart 6")
VIEW6 = "2022-01"
c6 = [dict(month=r["month"],
           net_inflow_tn=f'{float(r["foreign_equity_bn"]) / 1000.0:.4f}',
           avg_3m_tn=f'{float(r["foreign_equity_3m_avg_bn"]) / 1000.0:.4f}')
      for r in rows if r["month"] >= VIEW6]
assert c6 and c6[0]["month"] == VIEW6, c6[0]
assert all(float(r["net_inflow_tn"]) >= 0 for r in c6), "a negative month needs the coral trace"
# "the fastest since at least 2010" rests on the 3-month average peaking last,
# measured over the WHOLE master and not only the view window
all_ma = [(r["month"], float(r["foreign_equity_3m_avg_bn"]))
          for r in rows if r["foreign_equity_3m_avg_bn"]]
assert max(all_ma, key=lambda t: t[1])[0] == c6[-1]["month"], max(all_ma, key=lambda t: t[1])
jja = [float(r["net_inflow_tn"]) for r in c6 if r["month"] >= "2026-06"]
assert len(jja) == 3 and abs(sum(jja) / 3 - 1.7) < 0.05, jja   # the article's 1.7trn a month
write("chart-6-foreign-equity-fund-flows.csv",
      ["month", "net_inflow_tn", "avg_3m_tn"], c6,
      f"Jun-Aug 2026 average {sum(jja) / 3:.2f} tn/mo")

# ---------------------------------------------------------------- chart 7
# Retail JGB sales, --long --per-month. Quarterly-era issues (to 2010-12) are
# spread over the three months they cover; the flag drives the faded bars the
# published chart uses for that era.
src = HH / "hh-retail-jgb-monthly" / "hh_retail_jgb_monthly_data.csv"
rows = load(src)
need(rows, ["month", "total_bn"], "chart 7")
QUARTERLY_END = "2010-12"
c7 = []
for r in rows:
    q = r["month"] <= QUARTERLY_END
    c7.append(dict(month=r["month"],
                   sales_tn=f'{float(r["total_bn"]) / 1000.0 / (3.0 if q else 1.0):.4f}',
                   quarterly="True" if q else ""))
assert c7[0]["month"] == "2003-03" and c7[-1]["month"] == "2026-09", (c7[0], c7[-1])
over_1tn = [r["month"] for r in c7 if float(r["sales_tn"]) >= 1.0]
assert over_1tn == ["2026-08", "2026-09"], over_1tn   # the chart's headline, on this basis
n_q = sum(1 for r in c7 if r["quarterly"])
write("chart-7-retail-jgb-per-month.csv", ["month", "sales_tn", "quarterly"], c7,
      f"{n_q} issues spread over 3 months each; >=1tn in {over_1tn}")

# ---------------------------------------------------------------- chart 8
# The BoJ's rate on current-account balances against what savers are offered.
# Two masters: the monthly deposit-rate file and the reserve-rate regime table.
folder = HH / "hh-reserve-rate-vs-deposit-rates"
rows = load(folder / "hh_deposit_rates_and_coupon_monthly_data.csv")
steps = load(folder / "hh_reserve_rate_steps_data.csv")
need(rows, ["month", "fixed5_rate_pct", "time_5to6y_contracted_pct"], "chart 8")
need(steps, ["regime", "rate_pct", "effective_date"], "chart 8 steps")
single = [s for s in steps if s["regime"] == "single" and s["rate_pct"]]
assert len(single) == 5 and single[0]["effective_date"] == "2024-03-21", single[0]
assert [s["rate_pct"] for s in single] == ["0.1", "0.25", "0.5", "0.75", "1.0"], single


def reserve_rate_at_month_end(ym: str) -> str:
    """The rate in force at the last day of month `ym`, or blank before the
    first single-rate regime — the tiered structure the chart does not draw."""
    y, m = int(ym[:4]), int(ym[5:])
    last = date(y + (m == 12), (m % 12) + 1, 1).toordinal() - 1
    live = [s for s in single
            if date.fromisoformat(s["effective_date"]).toordinal() <= last]
    return live[-1]["rate_pct"] if live else ""


VIEW8 = "2023-01"
c8 = [dict(month=r["month"],
           boj_reserve_rate_pct=reserve_rate_at_month_end(r["month"]),
           retail_jgb_5y_pct=r["fixed5_rate_pct"],
           time_deposit_5y_pct=r["time_5to6y_contracted_pct"])
      for r in rows if r["month"] >= VIEW8]
assert c8[0]["month"] == "2023-01" and c8[-1]["month"] == "2026-10", (c8[0], c8[-1])
assert c8[0]["boj_reserve_rate_pct"] == "", c8[0]
first_step = next(r for r in c8 if r["boj_reserve_rate_pct"])
assert first_step["month"] == "2024-03" and first_step["boj_reserve_rate_pct"] == "0.1", first_step
assert c8[-1]["boj_reserve_rate_pct"] == "1.0", c8[-1]
last_jgb = [r for r in c8 if r["retail_jgb_5y_pct"]][-1]
last_dep = [r for r in c8 if r["time_deposit_5y_pct"]][-1]
# the chart's computed headline: "Retail JGBs pay 2.2%, 5-year time deposits 1.2%"
assert f'{float(last_jgb["retail_jgb_5y_pct"]):.1f}' == "2.2", last_jgb
assert f'{float(last_dep["time_deposit_5y_pct"]):.1f}' == "1.2", last_dep
write("chart-8-retail-jgb-vs-deposit-rates.csv",
      ["month", "boj_reserve_rate_pct", "retail_jgb_5y_pct", "time_deposit_5y_pct"],
      c8, f'retail JGB {last_jgb["retail_jgb_5y_pct"]}%, 5y deposit {last_dep["time_deposit_5y_pct"]}%')

# ---------------------------------------------------------------- chart 9
src = HH / "hh-time-deposit-share" / "hh_time_deposit_yoy_data.csv"
rows = load(src)
need(rows, ["month", "yoy_change_pct"], "chart 9")
c9 = [dict(month=r["month"], yoy_change_pct=r["yoy_change_pct"]) for r in rows]
assert c9[0]["month"] == "1999-04" and c9[-1]["month"] == "2026-07", (c9[0], c9[-1])
pos = [r["month"] for r in c9 if float(r["yoy_change_pct"]) > 0]
prev_pos = max(m for m in pos if m < "2024-01")
run_start = min(m for m in pos if m > "2024-01")
# the chart's computed headline: "...for the first time since 2011"
assert (prev_pos, run_start) == ("2011-07", "2025-01"), (prev_pos, run_start)
assert all(float(r["yoy_change_pct"]) > 0 for r in c9 if r["month"] >= run_start)
assert abs(float(c9[-1]["yoy_change_pct"]) - 4.16) < 0.005, c9[-1]  # the article's 4.2%
write("chart-9-time-deposits-yoy.csv", ["month", "yoy_change_pct"], c9,
      f'latest {c9[-1]["month"]} {float(c9[-1]["yoy_change_pct"]):+.2f}%')

# ---------------------------------------------------------------- chart 10
# BoJ ownership share by maturity. The master stores FRACTIONS; the chart is in
# per cent. History to 2026-08, projection after it.
src = LIB / "boj" / "ownership-share-segments-1-5" / "japan_boj_ownership_share_1_5_data.csv"
rows = load(src)
need(rows, ["YM", "seg_1_5", "seg_5_10", "seg_10_25", "seg_25p"], "chart 10")
VIEW10, HIST_END = "2010-01", "2026-08"
SEGS = ["seg_1_5", "seg_5_10", "seg_10_25", "seg_25p"]
c10 = [dict({f"{s}_pct": f'{float(r[s]) * 100.0:.3f}' for s in SEGS},
            YM=r["YM"],
            phase="actual" if r["YM"] <= HIST_END else "projection")
       for r in rows if r["YM"] >= VIEW10]
assert c10[0]["YM"] == "2010-01" and c10[-1]["YM"] == "2030-12", (c10[0], c10[-1])
hist = [r for r in c10 if r["phase"] == "actual"]
assert hist[-1]["YM"] == HIST_END, hist[-1]
aug = hist[-1]
assert round(float(aug["seg_1_5_pct"]), 1) == 58.3, aug   # the merged-segment check
assert round(float(aug["seg_5_10_pct"]), 1) == 51.8, aug
write("chart-10-boj-ownership-by-maturity.csv",
      ["YM", "phase"] + [f"{s}_pct" for s in SEGS], c10,
      f'history to {HIST_END}, projection to {c10[-1]["YM"]}')

print(f"\n8 exhibits written to {OUT}")
