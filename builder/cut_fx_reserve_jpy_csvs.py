"""Cut the five tidy CSVs for both tiers from the chart-library masters.

One ledger, two pages: the same files are written into the free page's data/
and the paid page's data/, so the two tiers cannot disagree about a number.

The only editorial deletion is Chart 1's `jpy_cer`. It exists in the master but
the published chart's SERIES list plots `jpy_observed` alone, so carrying it
would put a line on the page that was never in the report.
"""
import csv
from pathlib import Path

LIB = Path(r"G:\My Drive\charts\global-reserves")
REPO = Path(r"C:\repos\jma-data")
FREE, PAID = "2026-08-04-fx-reserve-jpy", "2026-08-04-fx-reserve-jpy-paid"

LEDGER = [
    (1, "chart-1-jpy-share.csv",
     "jpy-share-unadj-vs-cer/jpy_share_unadj_vs_cer_data.csv",
     ["date", "jpy_observed"]),                       # jpy_cer dropped — see docstring
    (2, "chart-2-usd-share.csv",
     "usd-share-unadj-vs-cer/usd_share_unadj_vs_cer_data.csv",
     ["date", "usd_observed", "usd_cer"]),
    (3, "chart-3-eur-share.csv",
     "eur-share-unadj-vs-cer/eur_share_unadj_vs_cer_data.csv",
     ["date", "eur_observed", "eur_cer"]),
    (4, "chart-4-jpy-cad-aud-rmb-shares.csv",
     "jpy-cad-aud-cny-share-unadj/jpy_cad_aud_cny_share_unadj_data.csv",
     ["date", "jpy_unadj", "cad_unadj", "aud_unadj", "cny_unadj"]),
    (5, "chart-5-usd-net-accumulation.csv",
     "usd-netaccum-annual/usd_reserve_netaccum_data.csv",
     ["date", "usd_netaccum"]),
]

for slug in (FREE, PAID):
    (REPO / slug / "data").mkdir(parents=True, exist_ok=True)

for n, name, src, cols in LEDGER:
    with open(LIB / src, newline="", encoding="utf-8") as f:
        rows = list(csv.DictReader(f))
        have = list(rows[0].keys())
    missing = [c for c in cols if c not in have]
    if missing:
        raise SystemExit(f"chart {n}: master lacks {missing}; has {have}")
    dropped = [c for c in have if c not in cols]

    body = "".join(
        ",".join((r.get(c) or "") for c in cols) + "\n" for r in rows)
    text = ",".join(cols) + "\n" + body
    for slug in (FREE, PAID):
        (REPO / slug / "data" / name).write_text(text, encoding="utf-8",
                                                 newline="")
    print(f"chart {n}: {len(rows):>3} rows, cols={cols}"
          + (f"  DROPPED {dropped}" if dropped else ""))

# The two tiers must be byte-identical in their data, not merely equivalent.
for _, name, _, _ in LEDGER:
    a = (REPO / FREE / "data" / name).read_bytes()
    b = (REPO / PAID / "data" / name).read_bytes()
    assert a == b, f"{name} differs between tiers"
print("\nfree and paid data/ are byte-identical.")
