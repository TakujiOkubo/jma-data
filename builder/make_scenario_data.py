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

* A scenario's name does not stay attached to its hike path. The path that was
  published as the Alternative until 2026-09 (Sep-26 / Mar-27 / Dec-27 to
  1.75%) is the **Main** from the August 2026 vintage on, and the Alternative
  moved up to a 2.00% terminal. So a run directory recognised from memory, or a
  page labelled from the path it used to carry, is exactly the error to expect
  here. ``verify_hikes`` re-reads the Policy_Rate column and fails the cut if
  the hike months do not match what SCENARIOS declares, so a mislabelled page
  cannot be built silently. (It replaced an earlier trap in the same place: the
  July vintage's branch version numbers ran opposite to its terminal rates.)
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
#
# Vintage: AUGUST 2026 (origin 2026-08, forecast 2026-09 -> 2029-08), the runs
# of session S79 (2026-09-01). Takuji promoted the former Alternative to Main
# and moved the Alternative up to the 2.00% case on 2026-09-04. The retired
# 1.50% run (fan-sigma-after-v307) is not published anywhere from that date.
#
# ONE ASSUMPTION DIFFERS BEYOND THE POLICY PATH, and the pages must say so.
# The 2.00% run carries scenario-dependent reversion targets for the super-long
# and belly term premia (--superlong-normal / --belly-normal, register item
# 10a, introduced S76); the Main run leaves both at the model's own estimates.
# Read back from pipeline_run_registry.csv, not re-invented:
#   superlong_normal = 20Y=154.3447,30Y=194.9790,40Y=205.0735
#   belly_normal     = 5Y=43.3254,10Y=102.6125
# S76 measured that channel at roughly +68bp on the 30Y against +21bp for an
# entire 50bp step in the terminal rate, so a page that named only the BoJ path
# would invite the reader to credit the wrong assumption with the difference.
#
# Each scenario feeds TWO pages from one cut, so they can never drift apart:
#   jgb-yield-curve-*  the paid page - decomposition-led, RN/TP detail, the
#                      full About section. Supersedes the frozen model page
#                      (Takuji, 2026-08-03, reversing the S05 freeze).
#   jgb-forecast-*     the slim page built earlier the same day, PARKED
#                      unlinked pending Takuji's decision on a free tier.
SCENARIOS = {
    "main": dict(
        slugs=["jgb-yield-curve-main", "jgb-forecast-main"],
        run="v30-aug2026-terminal175-main",
        branch="v30_16-changes",
        hikes=[("2026-09", 1.25), ("2027-03", 1.50), ("2027-12", 1.75)],
        terminal=1.75,
    ),
    "alternative": dict(
        slugs=["jgb-yield-curve-alternative", "jgb-forecast-alternative"],
        run="v30-aug2026-terminal200-risk",
        branch="v30_16-changes",
        hikes=[("2026-09", 1.25), ("2027-03", 1.50), ("2027-07", 1.75),
               ("2027-12", 2.00)],
        terminal=2.00,
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
    + [f"{b}_{t}" for t in FAN_TENORS
       # The fan is carried on the term premium as well as the yield. That is
       # not decoration: the risk-neutral leg is identical in the up, base and
       # down runs, so the whole band is term-premium uncertainty. On a page
       # about the decomposition, the band belongs where it originates.
       for b in ("Fan_hi", "Fan_lo", "Fan_hi_TP", "Fan_lo_TP")]
)

# The last row is the forecast horizon's own end month, which moves with the
# origin: July 2029 for the July-2026 vintage, August 2029 for the August one.
# It is stated rather than derived because it is the row the page's prose and
# its "projected to ..." line have to agree with, and a silent shift there is
# the kind that reads as a typo months later.
TABLE_ROWS = [("Dec 2026", "2026-12"), ("Dec 2027", "2027-12"),
              ("Dec 2028", "2028-12"), ("Aug 2029", "2029-08")]


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
    print(f"[{key}] {', '.join(spec['slugs'])}  <-  {spec['run']} ({spec['branch']})")

    curve = read_csv(run / f"{stem}_consolidated_curve.csv")
    fcst = read_csv(run / f"{stem}_stage3_forecast.csv")
    verify_hikes(curve, spec, key)

    # Fan bounds, keyed (YM, tenor). stage3_forecast is long-format: one row
    # per scenario x month x tenor, tenor written "10Y" not 10.
    fan: dict[tuple[str, str], dict[str, tuple]] = {}
    for r in fcst:
        scen = r["Scenario"].strip()
        if scen not in ("up", "down"):
            continue
        ym, tenor = r["YM"].strip(), r["Tenor"].strip()
        y, tp = num(r.get("Y_fcst")), num(r.get("TP_fcst"))
        if y is None:
            continue
        fan.setdefault((ym, tenor), {})[scen] = (y, tp)

    # The risk-neutral leg must be identical in all three runs: the scenario
    # fan prices a US term-premium move, which by construction enters only the
    # term premium. If this ever fails, the band on the TP charts would be
    # attributing to the term premium something the expectations path also did.
    rn: dict[tuple[str, str], dict[str, float]] = {}
    for r in fcst:
        rn.setdefault((r["YM"].strip(), r["Tenor"].strip()),
                      {})[r["Scenario"].strip()] = num(r.get("RN_fcst"))
    off = [k for k, legs in rn.items()
           if max(legs.values()) - min(legs.values()) > 1e-9]
    if off:
        raise SystemExit(
            f"RN differs across scenario legs on {len(off)} month-tenor pairs "
            f"(e.g. {off[:3]}). The fan is supposed to be pure term premium; "
            "refusing to cut TP band columns that would misattribute it.")
    print(f"  RN identical across up/base/down on {len(rn)} pairs "
          "- the band is term-premium only")

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
            hi = lo = hi_tp = lo_tp = None
            if typ == "forecast" and (ym, t) in fan:
                pair = fan[(ym, t)]
                (hi, hi_tp) = pair.get("up", (None, None))
                (lo, lo_tp) = pair.get("down", (None, None))
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
                hi_tp = lo_tp = num(r.get(f"TP_{t}"))
            row[f"Fan_hi_{t}"] = fmt(hi, 4)
            row[f"Fan_lo_{t}"] = fmt(lo, 4)
            row[f"Fan_hi_TP_{t}"] = fmt(hi_tp, 4)
            row[f"Fan_lo_TP_{t}"] = fmt(lo_tp, 4)
        out_rows.append(row)

    print(f"  base/panel agreement checked on {checked} cells")

    data_dirs = []
    for slug in spec["slugs"]:
        # Only cut data for pages that actually exist here. The parked slim
        # pages live on the scenario-forecast-pages branch and are absent from
        # the deploy branch; without this, a refresh on the deploy branch would
        # silently recreate them as orphan data folders with no manifest.
        if not (REPO / slug / "panel.json").exists():
            print(f"  skipping {slug}: no panel.json on this branch")
            continue
        d = REPO / slug / "data"
        d.mkdir(parents=True, exist_ok=True)
        data_dirs.append(d)
        with (d / "curve-panel.csv").open("w", newline="",
                                          encoding="utf-8") as fh:
            w = csv.DictWriter(fh, fieldnames=PANEL_COLS)
            w.writeheader()
            w.writerows(out_rows)
        print(f"  wrote {slug}\\data\\curve-panel.csv ({len(out_rows)} rows)")
    data_dir = data_dirs[0]

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

    for d in data_dirs:
        with (d / "forecast-table.csv").open("w", newline="",
                                             encoding="utf-8") as fh:
            w = csv.DictWriter(fh, fieldnames=["label", "ym", "kind"]
                               + [t for t in TENORS if t != "2Y"])
            w.writeheader()
            w.writerows(table)
    print(f"  wrote forecast-table.csv to {len(data_dirs)} pages "
          f"({len(table)} rows)")

    # Read the horizon end off the run rather than naming a month: the fan is
    # widest at the last projected month, and a hardcoded one silently reports
    # the second-to-last after an origin roll.
    horizon_end = max(r["YM"] for r in out_rows if r["Type"] == "forecast")
    hw = {t: (num(by_ym[horizon_end][f"Fan_hi_{t}"])
              - num(by_ym[horizon_end][f"Yield_{t}"])) * 100
          for t in FAN_TENORS}
    print(f"  fan half-width at the horizon end ({horizon_end}, bp): "
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
