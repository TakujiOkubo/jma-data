"""Derive the paid tier of the BoJ equity-bet panel from the free one.

The two tiers are the same eight exhibits. Authoring the paid manifest by hand
is how they would come to disagree -- a value edited on one page and not the
other passes every gate each page runs on itself. So the paid manifest is
generated from the free one, and only the keys listed in OVERRIDES may differ.
The charts list is copied through untouched, which is what makes the cross-tier
equality gate in qa_panel.py true by construction rather than by inspection.

The tidy CSVs are copied byte-for-byte from the free page rather than re-cut
from the chart library: the free page is already reviewed and live, and cutting
again could only introduce a difference.

Same shape as derive_fx_reserve_jpy_paid.py, which did this for the FX reserve
article on 2026-08-05.
"""
import filecmp
import json
import shutil
from collections import OrderedDict
from pathlib import Path

REPO = Path(r"C:\repos\jma-data")
FREE, PAID = "2026-08-12-boj-equity-bet", "2026-08-12-boj-equity-bet-paid"

# Every key on which the two tiers are allowed to differ, and why.
OVERRIDES = {
    "slug": PAID,
    # Inert -- the builder never reads it. It exists so the set of paid pages
    # can be queried while paid pages are still hosted in this public repo
    # (protocol section 5, the known gap).
    "audience": "paid",
    # Declared rather than inherited. "paid" would default downloads to true
    # anyway, but a page that offers its data should say so in its manifest
    # instead of leaving a reader to re-derive it from the tier.
    "downloads": True,
    "tier": "paid",
    # Takuji's free-page wording pitches the paid tier ("Paid subscribers have
    # access to data behind charts..."). On the paid page the reader is already
    # inside it, so the pitch is replaced by what this page IS, keeping his
    # closing sentence, English or Japanese included.
    #
    # It does NOT say "Only paid subscribers have access to this page", the
    # sentence the FX reserve paid page and the standing reserves page carry.
    # Takuji, 2026-08-13: tone the exclusivity down, because nothing enforces
    # it -- this page sits in a public repo and "unlisted" authenticates
    # nobody, so that sentence is false to any reader holding the URL. He is
    # content to share an ungated paid page in the meantime (about ten paid
    # subscribers; a password-protected page is still being designed). "Shared
    # with paid subscribers" is what is actually true, and qa_panel gates the
    # stronger claim's absence.
    "bottom_banner": (
        "The charts and data on this page are free to use and reproduce with "
        "attribution to Japan Macro Advisors. This page is shared with paid "
        "subscribers; each card links the tidy CSV behind its chart. Paid "
        "subscribers are encouraged to send questions on my research and "
        "receive priority in my replies in either English or Japanese."),
}

# Deliberately NOT set: "workbook". build_panel.py renders the workbook button
# only when the manifest declares that key -- downloads: true alone gives the
# per-card CSV links and nothing more. jma-data is a public repository and
# protocol section 4 reserves distribution of the .xlsx to Takuji, so giving
# the button a target would put the paid perk in public. Takuji confirmed this
# reading on 2026-08-12: per-card CSVs only. No key, no button, no .xlsx here.

free_path = REPO / FREE / "panel.json"
m = json.loads(free_path.read_text(encoding="utf-8"),
               object_pairs_hook=OrderedDict)

m["_derived_from"] = (
    "Generated from " + FREE + "/panel.json by builder/derive_boj_equity_bet_paid.py. "
    "Do not hand-edit: edit the free manifest and re-derive, or the two tiers "
    "drift. Only slug, audience, downloads, tier and bottom_banner differ; the "
    "charts list is copied through unchanged, which is what makes the "
    "cross-tier equality gate true by construction rather than by inspection.")

for k, v in OVERRIDES.items():
    m[k] = v

(REPO / PAID / "data").mkdir(parents=True, exist_ok=True)
(REPO / PAID / "panel.json").write_text(
    json.dumps(m, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")

# The CSVs the cards link. Copied from the reviewed free page, then proved
# identical -- a copy that silently failed would ship a paid page whose
# download links disagree with the chart above them.
names = [Path(c["csv"]).name for c in m["charts"]]
for name in names:
    src, dst = REPO / FREE / "data" / name, REPO / PAID / "data" / name
    shutil.copyfile(src, dst)
    assert filecmp.cmp(src, dst, shallow=False), f"copy differs: {name}"
assert len(names) == 8, f"expected 8 exhibit CSVs, got {len(names)}"

# Prove the only differences are the declared ones.
free = json.loads(free_path.read_text(encoding="utf-8"))
paid = json.loads((REPO / PAID / "panel.json").read_text(encoding="utf-8"))
allowed = set(OVERRIDES) | {"_derived_from"}
diff = {k for k in set(free) | set(paid) if free.get(k) != paid.get(k)}
assert diff <= allowed, f"unexpected tier divergence: {sorted(diff - allowed)}"
assert free["charts"] == paid["charts"], "chart specs differ between tiers"
assert "workbook" not in paid, "the paid page must declare no workbook"

print("paid manifest derived. Differing keys:", sorted(diff))
print("charts list identical across tiers:", len(free["charts"]), "exhibits")
print("data CSVs copied byte-identical:", len(names))
