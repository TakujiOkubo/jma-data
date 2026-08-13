"""Derive the paid manifest from the free one.

The two tiers are the same charts. Authoring the paid manifest by hand is how
they would come to disagree — a value edited on one page and not the other
passes every gate each page runs on itself. So the paid manifest is generated
from the free one, and only the keys listed in OVERRIDES may differ. The chart
list is copied through untouched.
"""
import json
from collections import OrderedDict
from pathlib import Path

REPO = Path(r"C:\repos\jma-data")
FREE, PAID = "2026-08-04-fx-reserve-jpy", "2026-08-04-fx-reserve-jpy-paid"

# Every key on which the two tiers are allowed to differ, and why.
OVERRIDES = {
    "slug": PAID,
    "tier": "paid",
    # The default bottom banner advertises the paid tier to a free reader. On
    # the paid page it has to say what this page IS, as the model pages do.
    #
    # It says "shared with", not "only ... have access to". Takuji, 2026-08-13:
    # nothing enforces exclusivity here -- jma-data is public and "unlisted"
    # authenticates nobody -- so the stronger sentence was false to any reader
    # holding the URL. He accepts an ungated paid page in the meantime while a
    # password-protected one is designed. qa_skin gates the claim's absence on
    # every page in this repo.
    "bottom_banner": (
        "The charts and data on this page are free to use and reproduce with "
        "attribution to Japan Macro Advisors. This page is shared with paid "
        "subscribers; each card links the tidy CSV behind its chart. Paid "
        "subscribers are encouraged to send questions on my research and "
        "receive priority in my replies."),
}

# Deliberately NOT set: "workbook". builder/build_panel.py renders the workbook
# button only when the manifest declares that key -- "tier": "paid" alone
# renders nothing. Protocol section 4.4 forbids uploading or linking the
# workbook, and jma-data is a public repository, so giving the button a target
# would put the paid perk in public. No key, no button, no .xlsx in the repo.

m = json.loads((REPO / FREE / "panel.json").read_text(encoding="utf-8"),
               object_pairs_hook=OrderedDict)

m["_derived_from"] = (
    "Generated from " + FREE + "/panel.json by builder/derive_fx_reserve_jpy_paid.py. Do not "
    "hand-edit: edit the free manifest and re-derive, or the two tiers drift. "
    "Only slug, tier and bottom_banner differ; the charts list is copied "
    "through unchanged, which is what makes the cross-tier equality gate true "
    "by construction rather than by inspection.")

for k, v in OVERRIDES.items():
    m[k] = v

(REPO / PAID).mkdir(exist_ok=True)
(REPO / PAID / "panel.json").write_text(
    json.dumps(m, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")

# Prove the only differences are the declared ones.
free = json.loads((REPO / FREE / "panel.json").read_text(encoding="utf-8"))
paid = json.loads((REPO / PAID / "panel.json").read_text(encoding="utf-8"))
allowed = set(OVERRIDES) | {"_derived_from"}
diff = {k for k in set(free) | set(paid) if free.get(k) != paid.get(k)}
assert diff <= allowed, f"unexpected tier divergence: {sorted(diff - allowed)}"
assert free["charts"] == paid["charts"], "chart specs differ between tiers"
print("paid manifest derived. Differing keys:", sorted(diff))
print("charts list identical across tiers:", len(free["charts"]), "exhibits")
