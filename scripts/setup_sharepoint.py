"""Tạo list / bổ sung cột còn thiếu trên SharePoint (cũng làm được trong app: "Cài đặt & đồng bộ").

Dùng được với BACKEND = "powerautomate" hoặc "sharepoint". Cột được so khớp theo tên nội bộ hoặc
tên hiển thị, nên list có sẵn sẽ không bị tạo trùng cột.

    python scripts/setup_sharepoint.py --dry-run   # chỉ kiểm tra
    python scripts/setup_sharepoint.py             # tạo list + cột còn thiếu
"""
import argparse

import _common  # noqa: F401

from tuyensinh import importer
from tuyensinh.storage import create_storage


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--dry-run", action="store_true")
    args = ap.parse_args()
    sp = create_storage()
    if not hasattr(sp, "columns"):
        raise SystemExit("Đặt BACKEND = \"powerautomate\" hoặc \"sharepoint\" trong secrets.toml")
    for row in importer.check_lists(sp):
        ld = row["list"]
        if row["loi"]:
            print(f"! {row['ten']}: {row['loi']}")
            continue
        state = "đã có" if row["co_list"] else "CHƯA CÓ"
        print(f"= {row['ten']} ({ld.title}): {state}, khớp {len(row['khop'])} cột, "
              f"thiếu {len(row['thieu'])}")
        for key in row["thieu"]:
            print(f"    + {ld.get(key).sp_title} ({key})")
    if not args.dry_run:
        importer.setup_lists(sp)


if __name__ == "__main__":
    main()
