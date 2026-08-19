"""Derive the paid tier of the effective-rate panel from the free one.

The two tiers are the same five exhibits. Authoring the paid manifest by hand is
how they would come to disagree -- a value edited on one page and not the other
passes every gate each page runs on itself. So the paid manifest is generated
from the free one, and only the keys listed in OVERRIDES may differ. The charts
list is copied through untouched, which is what makes the cross-tier equality
gate in qa_panel.py true by construction rather than by inspection.

The tidy CSVs are copied byte-for-byte from the free page rather than re-cut
from the chart library: cut_data.py has already run its 43 checks against the
published figures on the free page's copies, and cutting again could only
introduce a difference.

Same shape as derive_boj_equity_bet_paid.py, which did this for the BoJ
equity-bet article on 2026-08-12.
"""
import filecmp
import json
import shutil
from collections import OrderedDict
from pathlib import Path

REPO = Path(r"C:\repos\jma-data")
FREE, PAID = "2026-08-18-jgb-effective-rate", "2026-08-18-jgb-effective-rate-paid"
EXHIBITS = 5

# Every key on which the two tiers are allowed to differ, and why.
OVERRIDES = {
    "slug": PAID,
    # The tiers differ here, and this is the key that makes the difference
    # load-bearing rather than cosmetic. Takuji, 2026-08-19: the FREE page is
    # listed on the landing index -- a free marketing page nobody can find does
    # half its job, the same reasoning as the QT monitor's free edition on
    # 2026-08-16. The paid page stays off the index.
    #
    # Without this override the paid page would inherit the free page's
    # "unlisted": false and quietly appear on the public landing page. It would
    # not have shipped silently -- the divergence assertion at the foot of this
    # script fails on any key that differs and is not declared here -- but the
    # failure would have read as a broken derivation rather than as the policy
    # decision it is. Note that listing is not access control either way:
    # jma-data is public, so "unlisted" only keeps a page off the index.
    "unlisted": True,
    # Inert -- the builder never reads it. It exists so the set of paid pages
    # can be queried while paid pages are still hosted in this public repo
    # (protocol section 5, the known gap).
    "audience": "paid",
    # Declared rather than inherited. "paid" would default downloads to true
    # anyway, but a page that offers its data should say so in its manifest
    # instead of leaving a reader to re-derive it from the tier. This is the
    # key that puts the Download CSV link on every card -- Takuji's ask for
    # this page, 2026-08-19.
    "downloads": True,
    "tier": "paid",
    # The free page's banner pitches the paid tier. On the paid page the reader
    # is already inside it, so the pitch is replaced by what this page IS,
    # keeping his closing sentence, English or Japanese included. Carried over
    # verbatim from the 2026-08-12 paid page, which he approved.
    #
    # It does NOT say "Only paid subscribers have access to this page". Takuji,
    # 2026-08-13: tone the exclusivity down, because nothing enforces it --
    # this page sits in a public repo and "unlisted" authenticates nobody, so
    # that sentence is false to any reader holding the URL. "Shared with paid
    # subscribers" is what is actually true, and qa_panel gates the stronger
    # claim's absence across this repo.
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
# the button a target would put the paid perk in public. Same reading as the
# 2026-08-12 page: per-card CSVs only. No key, no button, no .xlsx here.

free_path = REPO / FREE / "panel.json"
m = json.loads(free_path.read_text(encoding="utf-8"),
               object_pairs_hook=OrderedDict)

m["_derived_from"] = (
    "Generated from " + FREE + "/panel.json by "
    "builder/derive_jgb_effective_rate_paid.py. Do not hand-edit: edit the free "
    "manifest and re-derive, or the two tiers drift. Only slug, audience, "
    "downloads, tier, unlisted and bottom_banner differ; the charts list is "
    "copied through unchanged, which is what makes the cross-tier equality gate "
    "true by construction rather than by inspection.")

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
assert len(names) == EXHIBITS, f"expected {EXHIBITS} exhibit CSVs, got {len(names)}"

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
