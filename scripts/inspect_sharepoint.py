"""In các cột (tên hiển thị -> tên nội bộ, kiểu) của list và cách app đang khớp.

    python scripts/inspect_sharepoint.py            # các list của app
"""
import _common  # noqa: F401

from tuyensinh import config
from tuyensinh.schema import ALL_LISTS
from tuyensinh.storage import create_storage
from tuyensinh.storage.convert import ColumnMap

sp = create_storage()
for ld in ALL_LISTS:
    print(f"\n== {config.list_name(ld.name)} ({ld.title})")
    if not sp.list_exists(ld.name):
        print("   (chưa có list)")
        continue
    cols = sp.columns(ld.name)
    cm = ColumnMap(ld.name, cols)
    for c in cols:
        key = cm.key_of.get(c["name"], "")
        print(f"   {c['title']:<28} {c['name']:<40} {c['type']:<10} {key}")
    if cm.missing:
        print("   Chưa có cột cho:", ", ".join(ld.get(k).sp_title for k in cm.missing))
