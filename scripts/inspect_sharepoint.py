"""In danh sách list và cột (tên nội bộ) trên site — dùng để đối chiếu list cũ của Power Apps.

    python scripts/inspect_sharepoint.py [TenList]
"""
import sys

import _common  # noqa: F401

from tuyensinh.storage.sharepoint import SharePointStorage

sp = SharePointStorage.from_config()
site = sp.site_id
lists = sp.request("GET", f"/sites/{site}/lists?$select=id,name,displayName")["value"]
only = sys.argv[1] if len(sys.argv) > 1 else None
for l in lists:
    if only and only not in (l["displayName"], l["name"]):
        continue
    print(f"\n== {l['displayName']}  (id={l['id']})")
    if only or len(lists) < 15:
        for c in sp.request("GET", f"/sites/{site}/lists/{l['id']}/columns")["value"]:
            if not c.get("readOnly") and not c.get("hidden"):
                kind = next((k for k in ("text", "choice", "dateTime", "number", "boolean",
                                         "lookup", "personOrGroup") if k in c), "?")
                print(f"   {c['name']:<32} {kind:<14} {c.get('displayName')}")
