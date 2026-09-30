"""Nhập danh mục trường học (gợi ý "Trường cũ" theo Phường/Xã).

File Excel/CSV cần các cột (tên cột không phân biệt hoa/thường, có/không dấu):
    Tỉnh/Thành phố | Phường/Xã | Tên trường | Cấp học (tùy chọn)

Nguồn gợi ý: xuất danh sách trường từ CSDL ngành (csdl.moet.gov.vn) hoặc danh sách
Sở GD&ĐT gửi. Tên Tỉnh/Phường/Xã được đối chiếu với danh mục địa giới mới; dòng nào
không khớp sẽ được liệt kê để sửa.

    python scripts/import_truong_hoc.py ds_truong.xlsx           # thay toàn bộ danh mục
    python scripts/import_truong_hoc.py ds_truong.xlsx --append  # thêm vào danh mục hiện có
"""
import argparse
import csv

import _common  # noqa: F401
import pandas as pd

from tuyensinh import danh_muc

COLS = {"tinh": "Tỉnh/Thành phố", "xa": "Phường/Xã", "ten": "Tên trường", "cap": "Cấp học"}
ALIASES = {
    "tinh": ["tinh/thanh pho", "tinh", "tinh/tp", "tinh thanh"],
    "xa": ["phuong/xa", "xa/phuong", "xa", "phuong", "phuong xa"],
    "ten": ["ten truong", "truong", "ten"],
    "cap": ["cap hoc", "cap", "loai truong"],
}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("file")
    ap.add_argument("--append", action="store_true")
    args = ap.parse_args()
    df = (pd.read_csv(args.file, dtype=str) if args.file.lower().endswith(".csv")
          else pd.read_excel(args.file, dtype=str))
    rename = {}
    for c in df.columns:
        fc = danh_muc.fold(c)
        for k, names in ALIASES.items():
            if fc in names:
                rename[c] = k
    df = df.rename(columns=rename)
    missing = [COLS[k] for k in ("tinh", "xa", "ten") if k not in df.columns]
    if missing:
        raise SystemExit(f"Thiếu cột: {missing}. Các cột trong file: {list(df.columns)}")
    if "cap" not in df.columns:
        df["cap"] = ""

    tinh_by_fold = {danh_muc.fold(t): t for t in danh_muc.load()["tinh"]}
    rows, bad = [], []
    for i, r in df.fillna("").iterrows():
        ten = r["ten"].strip()
        if not ten:
            continue
        tinh_in = danh_muc.normalize_tinh(r["tinh"].strip())
        tinh = tinh_by_fold.get(danh_muc.fold(tinh_in))
        if tinh is None:  # cho phép viết tắt "Hồ Chí Minh", "TP HCM"...
            cand = [t for f, t in tinh_by_fold.items() if danh_muc.fold(r["tinh"]) in f]
            tinh = cand[0] if len(cand) == 1 else None
        xa_map = {danh_muc.fold(x): x for x in danh_muc.xa_of(tinh or "")}
        xa = xa_map.get(danh_muc.fold(r["xa"]))
        if xa is None:
            cand = [x for f, x in xa_map.items() if f.endswith(" " + danh_muc.fold(r["xa"]))]
            xa = cand[0] if len(cand) == 1 else None
        if not tinh or not xa:
            bad.append((i + 2, r["tinh"], r["xa"], ten))
            continue
        rows.append([tinh, xa, ten, r["cap"].strip()])

    existing = []
    if args.append and danh_muc.TRUONG_CSV.exists():
        with danh_muc.TRUONG_CSV.open(encoding="utf-8-sig") as fh:
            existing = [row for row in csv.reader(fh)][1:]
    seen, out = set(), []
    for row in existing + rows:
        k = (danh_muc.fold(row[0]), danh_muc.fold(row[1]), danh_muc.fold(row[2]))
        if k not in seen:
            seen.add(k)
            out.append(row)
    out.sort(key=lambda r: (r[0], r[1], r[2]))
    with danh_muc.TRUONG_CSV.open("w", encoding="utf-8", newline="") as fh:
        w = csv.writer(fh)
        w.writerow(list(COLS.values()))
        w.writerows(out)
    print(f"Đã ghi {len(out)} trường vào {danh_muc.TRUONG_CSV}")
    if bad:
        print(f"{len(bad)} dòng không khớp địa giới mới (dòng, tỉnh, xã, trường):")
        for b in bad[:30]:
            print("  ", b)


if __name__ == "__main__":
    main()
