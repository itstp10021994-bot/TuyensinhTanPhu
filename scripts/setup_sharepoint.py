"""Tạo list / bổ sung cột còn thiếu trên SharePoint theo tuyensinh/schema.py.

Dùng được với BACKEND = "powerautomate" hoặc "sharepoint". Cột được so khớp theo tên hiển thị,
nên list "Data tuyển sinh" có sẵn sẽ không bị tạo trùng cột.

    python scripts/setup_sharepoint.py --dry-run   # chỉ kiểm tra, in cột khớp / thiếu
    python scripts/setup_sharepoint.py             # tạo list + cột còn thiếu
"""
import argparse

import _common  # noqa: F401

from tuyensinh import config
from tuyensinh.schema import ALL_LISTS
from tuyensinh.storage import create_storage
from tuyensinh.storage.convert import ColumnMap


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--dry-run", action="store_true")
    args = ap.parse_args()
    sp = create_storage()
    if not hasattr(sp, "columns"):
        raise SystemExit("Đặt BACKEND = \"powerautomate\" hoặc \"sharepoint\" trong secrets.toml")
    for ld in ALL_LISTS:
        name = config.list_name(ld.name)
        if not sp.list_exists(ld.name):
            print(f"+ Tạo list {name}")
            if args.dry_run:
                continue
            sp.create_list(ld.name, ld.title)
        cm = ColumnMap(ld.name, sp.columns(ld.name))
        print(f"= {name} ({ld.title}): khớp {len(cm.internal)} cột, thiếu {len(cm.missing)}")
        for key, internal in cm.internal.items():
            print(f"    {ld.get(key).sp_title:<28} -> {internal}")
        for key in cm.missing:
            f = ld.get(key)
            print(f"  + thêm cột '{f.sp_title}' (tên nội bộ {key})")
            if not args.dry_run:
                sp.add_column(ld.name, f, key)
    print("Xong.")


if __name__ == "__main__":
    main()
