#!/usr/bin/env python3
"""
make_scenario_data.py — cut the two scenario forecast pages' CSVs from a
production run directory.

    python builder/make_scenario_data.py main
    python builder/make_scenario_data.py alternative
    python builder/make_scenario_data.py all

Each scenario page reads two files:

  data/curve-panel.csv     the monthly panel — yields, the risk-neutral /
                           term-premium split, the policy rate and the US term
                           premium paths — plus the +/-1 sigma fan bounds at
                           10/20/30/40Y, which exist only over the forecast.
  data/forecast-table.csv  the year-end forecast table, two decimals.

The run directories are read-only inputs. This script never re-runs the
forecast pipeline; if a number here looks wrong the pipeline is the place to
look, not this file.

Two traps this script is written around:

* The scenario names invert the branch version numbers. v30_7 (the *newer*
  branch, the *lower* 1.50% terminal) is Main; v30_6 (1.75%) is Alternative.
  ``--verify-hikes`` re-reads the Policy_Rate column and fails the cut if the
  hike months do not match what SCENARIOS declares, so a mislabelled page
  cannot be built silently.
* ``stage3_forecast.csv`` carries its tenor as "10Y", not as the integer 10,
  and its Scenario column as base/up/down. Both are matched as strings.
"""

from __future__ import annotations

import csv
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
RUNS = Path(r"G:\My Drive\Research\JGB_related\JGByieldcurve_forecast\runs")

# The scenario taxonomy, settled by Takuji 2026-08-02 (vault note
# scenario-naming-main-alternative-2026-08-02.md) and named for publication
# 2026-08-03. hikes[] is the acceptance test, not documentation: the cut fails
# if the run's Policy_Rate column disagrees.
SCENARIOS = {
    "main": dict(
        slug="jgb-forecast-main",
        run="fan-sigma-after-v307",
        branch="v30_7-changes",
        hikes=[("2026-10", 1.25), ("2027-03", 1.50)],
        terminal=1.50,
    ),
    "alternative": dict(
        slug="jgb-forecast-alternative",
        run="fan-sigma-after-v306",
        branch="v30_6-changes",
        hikes=[("2026-09", 1.25), ("2027-03", 1.50), ("2027-12", 1.75)],
        terminal=1.75,
    ),
}

TENORS = ["2Y", "5Y", "10Y", "20Y", "30Y", "40Y"]
FAN_TENORS = ["10Y", "20Y", "30Y", "40Y"]     # the fan exists only from 10Y out

PANEL_COLS = (
    ["YM", "Type", "Policy_Rate",
     # US_TP10 is the observed history; the base/up/down columns are the
     # assumed path and exist only from the forecast origin. The chart needs
     # both, so the observed leg is carried alongside the scenario legs.
     "US_TP10", "US_TP10_base", "US_TP10_up", "US_TP10_down",
     # ...and again in basis points, the unit term premia are quoted in. Same
     # numbers; carrying both avoids a chart whose axis disagrees with the
     # text beside it.
     "US_TP10_bp", "US_TP10_base_bp", "US_TP10_up_bp", "US_TP10_down_bp"]
    + [f"{p}_{t}" for t in TENORS for p in ("Yield", "RN", "TP")]
    + [f"{b}_{t}" for t in FAN_TENORS for b in ("Fan_hi", "Fan_lo")]
)

TABLE_ROWS = [("Dec 2026", "2026-12"), ("Dec 2027", "2027-12"),
              ("Dec 2028", "2028-12"), ("Jul 2029", "2029-07")]


def read_csv(path: Path) -> list[dict]:
    with path.open(newline="", encoding="utf-8-sig") as fh:
        return list(csv.DictReader(fh))


def num(v):
    """Blank cells stay blank. The 40Y series is empty before Nov 2007 and a
    zero there would be a fabricated observation, not a missing one."""
    if v is None:
        return None
    v = v.strip()
    if v == "" or v.upper() in {"NA", "NAN", "NULL"}:
        return None
    try:
        return float(v)
    except ValueError:
        return None


def fmt(v, dp):
    return "" if v is None else f"{v:.{dp}f}"


def verify_hikes(rows: list[dict], spec: dict, key: str) -> None:
    """Re-derive the hike schedule from Policy_Rate and check it against the
    declared scenario. This is the guard against the version-number inversion:
    a page must never be labelled from its branch name."""
    steps, prev = [], None
    for r in rows:
        pr = num(r.get("Policy_Rate"))
        if pr is None:
            continue
        if r.get("Type", "").strip() == "forecast" and prev is not None \
                and abs(pr - prev) > 1e-4:
            steps.append((r["YM"].strip(), round(pr, 4)))
        prev = pr

    # The origin month's step to 1.00% is the rounding of the 0.979% actual,
    # not a hike; hikes are the 25bp steps above it.
    hikes = [(ym, rate) for ym, rate in steps if rate > 1.0 + 1e-6]
    want = [(ym, rate) for ym, rate in spec["hikes"]]
    got = [(ym, round(rate, 2)) for ym, rate in hikes]
    if got != want:
        raise SystemExit(
            f"HIKE CHECK FAILED for '{key}' ({spec['run']}):\n"
            f"  declared : {want}\n"
            f"  in data  : {got}\n"
            "Refusing to cut. Check the run directory against the scenario "
            "table before relabelling anything."
        )
    terminal = got[-1][1]
    if abs(terminal - spec["terminal"]) > 1e-6:
        raise SystemExit(f"terminal {terminal} != declared {spec['terminal']}")
    print(f"  hike check OK: {got}, terminal {terminal:.2f}%")


def cut(key: str) -> None:
    spec = SCENARIOS[key]
    run = RUNS / spec["run"]
    stem = spec["run"]
    print(f"[{key}] {spec['slug']}  <-  {spec['run']} ({spec['branch']})")

    curve = read_csv(run / f"{stem}_consolidated_curve.csv")
    fcst = read_csv(run / f"{stem}_stage3_forecast.csv")
    verify_hikes(curve, spec, key)

    # Fan bounds, keyed (YM, tenor). stage3_forecast is long-format: one row
    # per scenario x month x tenor, tenor written "10Y" not 10.
    fan: dict[tuple[str, str], dict[str, float]] = {}
    for r in fcst:
        scen = r["Scenario"].strip()
        if scen not in ("up", "down"):
            continue
        ym, tenor = r["YM"].strip(), r["Tenor"].strip()
        y = num(r.get("Y_fcst"))
        if y is None:
            continue
        fan.setdefault((ym, tenor), {})[scen] = y

    # The base leg of stage3_forecast must agree with the panel's own forecast
    # yields — they come from the same solve, and a disagreement means the two
    # files are from different runs.
    base = {(r["YM"].strip(), r["Tenor"].strip()): num(r.get("Y_fcst"))
            for r in fcst if r["Scenario"].strip() == "base"}

    last_actual = max(r["YM"].strip() for r in curve
                      if r.get("Type", "").strip() == "actual")

    out_rows, checked = [], 0
    for r in curve:
        ym, typ = r["YM"].strip(), r.get("Type", "").strip()
        row = {"YM": ym, "Type": typ}
        row["Policy_Rate"] = fmt(num(r.get("Policy_Rate")), 4)
        for c in ("US_TP10", "US_TP10_base", "US_TP10_up", "US_TP10_down"):
            v = num(r.get(c))
            row[c] = fmt(v, 4)
            row[f"{c}_bp"] = fmt(None if v is None else v * 100, 1)
        for t in TENORS:
            for p in ("Yield", "RN", "TP"):
                row[f"{p}_{t}"] = fmt(num(r.get(f"{p}_{t}")), 4)

        for t in FAN_TENORS:
            hi = lo = None
            if typ == "forecast" and (ym, t) in fan:
                pair = fan[(ym, t)]
                hi, lo = pair.get("up"), pair.get("down")
                b = base.get((ym, t))
                y = num(r.get(f"Yield_{t}"))
                if b is not None and y is not None:
                    if abs(b - y) > 5e-4:
                        raise SystemExit(
                            f"base/panel mismatch {ym} {t}: "
                            f"stage3 {b:.4f} vs panel {y:.4f} - the two files "
                            "are not from the same run.")
                    checked += 1
            elif ym == last_actual:
                # Seed the band at the last observation so the fan opens from
                # the actual path rather than appearing detached from it.
                hi = lo = num(r.get(f"Yield_{t}"))
            row[f"Fan_hi_{t}"] = fmt(hi, 4)
            row[f"Fan_lo_{t}"] = fmt(lo, 4)
        out_rows.append(row)

    print(f"  base/panel agreement checked on {checked} cells")

    data_dir = REPO / spec["slug"] / "data"
    data_dir.mkdir(parents=True, exist_ok=True)

    panel_path = data_dir / "curve-panel.csv"
    with panel_path.open("w", newline="", encoding="utf-8") as fh:
        w = csv.DictWriter(fh, fieldnames=PANEL_COLS)
        w.writeheader()
        w.writerows(out_rows)
    print(f"  wrote {panel_path.relative_to(REPO)} ({len(out_rows)} rows)")

    # ---- forecast table (two decimals, the published precision) ----
    by_ym = {r["YM"]: r for r in out_rows}
    table = []
    ar = by_ym[last_actual]
    y, mo = last_actual.split("-")
    label = f"Current ({['Jan','Feb','Mar','Apr','May','Jun','Jul','Aug','Sep','Oct','Nov','Dec'][int(mo)-1]} {y})"
    table.append(dict(label=label, ym=last_actual, kind="actual",
                      **{t: fmt(num(ar[f"Yield_{t}"]), 2)
                         for t in TENORS if t != "2Y"}))
    for lab, ym in TABLE_ROWS:
        if ym not in by_ym:
            print(f"  ! forecast table row {ym} absent from the run - skipped")
            continue
        rr = by_ym[ym]
        table.append(dict(label=lab, ym=ym, kind="forecast",
                          **{t: fmt(num(rr[f"Yield_{t}"]), 2)
                             for t in TENORS if t != "2Y"}))

    table_path = data_dir / "forecast-table.csv"
    with table_path.open("w", newline="", encoding="utf-8") as fh:
        w = csv.DictWriter(fh, fieldnames=["label", "ym", "kind"]
                           + [t for t in TENORS if t != "2Y"])
        w.writeheader()
        w.writerows(table)
    print(f"  wrote {table_path.relative_to(REPO)} ({len(table)} rows)")

    hw = {t: (num(by_ym["2029-07"][f"Fan_hi_{t}"])
              - num(by_ym["2029-07"][f"Yield_{t}"])) * 100 for t in FAN_TENORS}
    print("  horizon-end fan half-width (bp): "
          + ", ".join(f"{t} +/-{v:.1f}" for t, v in hw.items()))


def main() -> None:
    which = sys.argv[1] if len(sys.argv) > 1 else "all"
    keys = list(SCENARIOS) if which == "all" else [which]
    for k in keys:
        if k not in SCENARIOS:
            raise SystemExit(f"unknown scenario '{k}' "
                             f"(choose from {', '.join(SCENARIOS)}, or 'all')")
        cut(k)


if __name__ == "__main__":
    main()
