"""Tạo (hoặc bổ sung cột cho) các list trên SharePoint theo tuyensinh/schema.py.

    python scripts/setup_sharepoint.py            # tạo list + cột còn thiếu
    python scripts/setup_sharepoint.py --dry-run  # chỉ in ra những gì sẽ làm
"""
import argparse

import _common  # noqa: F401

from tuyensinh import config
from tuyensinh.schema import ALL_LISTS, BOOL, CHOICE, DATE, NOTE, NUMBER, Field
from tuyensinh.storage.sharepoint import SharePointStorage


def column_def(f: Field) -> dict:
    col = {"name": f.key, "displayName": f.label}
    if f.type == DATE:
        col["dateTime"] = {"format": "dateOnly"}
    elif f.type == NUMBER:
        col["number"] = {"decimalPlaces": "none"}
    elif f.type == BOOL:
        col["boolean"] = {}
    elif f.type == NOTE:
        col["text"] = {"allowMultipleLines": True, "linesForEditing": 4}
    elif f.type == CHOICE and isinstance(f.options, tuple):
        col["choice"] = {"allowTextEntry": True, "choices": list(f.options),
                         "displayAs": "dropDownMenu"}
    else:  # text, hoặc lựa chọn theo danh mục lớn (tỉnh, xã, ...) -> lưu text
        col["text"] = {}
    if f.key in ("NamHoc", "TuyenSinhID", "TrangThai"):
        col["indexed"] = True
    return col


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--dry-run", action="store_true")
    args = ap.parse_args()
    sp = SharePointStorage.from_config()
    site = sp.site_id
    existing = {l.get("displayName"): l["id"] for l in
                sp.request("GET", f"/sites/{site}/lists?$select=id,name,displayName")["value"]}
    for ld in ALL_LISTS:
        name = config.list_name(ld.name)
        if name not in existing:
            print(f"+ Tạo list {name} ({len(ld.fields)} cột)")
            if not args.dry_run:
                sp.request("POST", f"/sites/{site}/lists", json={
                    "displayName": name, "description": ld.title,
                    "list": {"template": "genericList"},
                    "columns": [column_def(f) for f in ld.fields]})
            continue
        lid = existing[name]
        cols = {c["name"] for c in sp.request("GET", f"/sites/{site}/lists/{lid}/columns")["value"]}
        missing = [f for f in ld.fields if f.key not in cols]
        print(f"= List {name} đã có, thiếu {len(missing)} cột")
        for f in missing:
            print(f"   + {f.key} ({f.label})")
            if not args.dry_run:
                sp.request("POST", f"/sites/{site}/lists/{lid}/columns", json=column_def(f))
    print("Xong.")


if __name__ == "__main__":
    main()
