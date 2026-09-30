"""Nhập dữ liệu từ Excel vào list (chuyển dữ liệu từ Power Apps / file VEMIS).

    # Data tuyển sinh: file xuất từ list cũ; tên cột = key hoặc tên hiển thị trong schema
    python scripts/import_excel.py tuyensinh du_lieu_cu.xlsx --nam-hoc 2026-2027
    # Tên cột khác -> khai báo ánh xạ: --map "Họ tên=HoTenHS" --map "Lớp=Khoi"
    # Hồ sơ nhập học từ file mẫu "Danh sách học sinh" (VEMIS, 2 dòng tiêu đề)
    python scripts/import_excel.py nhaphoc hoc_sinh_toan_truong.xls --vemis --nam-hoc 2026-2027
"""
import argparse

import _common  # noqa: F401
import pandas as pd

from tuyensinh import services
from tuyensinh.export_vemis import COLUMNS, HEADER_ROW
from tuyensinh.schema import NHAP_HOC, TUYEN_SINH
from tuyensinh.storage import create_storage

LISTS = {"tuyensinh": TUYEN_SINH, "nhaphoc": NHAP_HOC}


def read_vemis(path: str) -> pd.DataFrame:
    raw = pd.read_excel(path, header=None, skiprows=HEADER_ROW + 1, dtype=str)
    raw = raw.iloc[:, :len(COLUMNS)]
    raw.columns = [key or "STT" for _, _, key in COLUMNS][:raw.shape[1]]
    raw = raw.dropna(subset=["HoTen"])
    for k in ("CanNgheo", "DoanVien", "DoiVien"):
        raw[k] = raw[k].fillna("").str.strip().str.lower().eq("x")
    for k in ("NgaySinh", "NgayVaoTruong", "NgayCapCanCuoc"):
        raw[k] = pd.to_datetime(raw[k], dayfirst=True, errors="coerce").dt.date
    return raw.drop(columns=["STT"])


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("list", choices=LISTS)
    ap.add_argument("file")
    ap.add_argument("--nam-hoc", required=True)
    ap.add_argument("--vemis", action="store_true", help="file theo biểu mẫu VEMIS")
    ap.add_argument("--map", action="append", default=[], help='"Cột Excel=KeyTrongSchema"')
    ap.add_argument("--dry-run", action="store_true")
    args = ap.parse_args()
    ld = LISTS[args.list]

    if args.vemis:
        df = read_vemis(args.file)
    else:
        df = pd.read_excel(args.file, dtype=str) if not args.file.endswith(".csv") \
            else pd.read_csv(args.file, dtype=str)
        rename = {f.label: f.key for f in ld.fields}
        rename.update(dict(m.split("=", 1) for m in args.map))
        df = df.rename(columns=rename)
    keep = [c for c in df.columns if c in ld.keys]
    print(f"Các cột nhận được: {keep}")
    print(f"Bỏ qua: {[c for c in df.columns if c not in ld.keys]}")
    df = df[keep].where(df[keep].notna(), None)

    storage = create_storage()
    ok = err = 0
    for i, row in df.iterrows():
        data = {k: v for k, v in row.to_dict().items() if v is not None}
        data["NamHoc"] = args.nam_hoc
        try:
            if args.dry_run:
                errs = services.validate(ld, data)
                if errs:
                    raise ValueError("; ".join(errs))
            elif ld is TUYEN_SINH:
                services.save_tuyen_sinh(storage, data)
            else:
                services.save_nhap_hoc(storage, data)
            ok += 1
        except ValueError as e:
            err += 1
            print(f"  Dòng {i + 2}: {e}")
    print(f"Thành công {ok}, lỗi {err}")


if __name__ == "__main__":
    main()
