"""Nhập dữ liệu từ Excel vào list (có thể làm ngay trong app: trang "Cài đặt & đồng bộ").

    # File chuẩn hóa / "Export to Excel" từ list (cột Năm học trong file được giữ nguyên)
    python scripts/import_excel.py tuyensinh Data_TuyenSinh_chuan_hoa.xlsx --nam-hoc 2026-2027 --giu-nguyen
    # Tên cột khác -> khai báo ánh xạ: --map "Họ tên=HoTenHS" --map "Lớp=Khoi"
    # Hồ sơ nhập học từ file mẫu "Danh sách học sinh" (VEMIS, 2 dòng tiêu đề)
    python scripts/import_excel.py nhaphoc hoc_sinh_toan_truong.xlsx --vemis --nam-hoc 2026-2027
"""
import argparse

import _common  # noqa: F401

from tuyensinh import importer, services
from tuyensinh.schema import NHAP_HOC, TUYEN_SINH
from tuyensinh.storage import create_storage

LISTS = {"tuyensinh": TUYEN_SINH, "nhaphoc": NHAP_HOC}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("list", choices=LISTS)
    ap.add_argument("file")
    ap.add_argument("--nam-hoc", required=True)
    ap.add_argument("--vemis", action="store_true", help="file theo biểu mẫu VEMIS")
    ap.add_argument("--map", action="append", default=[], help='"Cột Excel=KeyTrongSchema"')
    ap.add_argument("--dry-run", action="store_true")
    ap.add_argument("--sheet", help="tên sheet (mặc định: sheet Data_TuyenSinh/Data_NhapHoc nếu có)")
    ap.add_argument("--giu-nguyen", action="store_true",
                    help="chuyển dữ liệu cũ: ghi cả dòng thiếu trường bắt buộc, không kiểm tra")
    ap.add_argument("--ghi-trung", action="store_true",
                    help="không bỏ qua dòng đã có trên list")
    args = ap.parse_args()
    ld = LISTS[args.list]

    df, skipped_cols = importer.read_frame(args.file, ld, args.sheet, args.vemis,
                                           dict(m.split("=", 1) for m in args.map))
    print(f"Các cột nhận được: {list(df.columns)}")
    print(f"Bỏ qua: {skipped_cols}")
    if args.dry_run:
        bad = 0
        for i, row in df.iterrows():
            data = {k: v for k, v in row.to_dict().items() if not importer._blank(v)}
            data.setdefault("NamHoc", args.nam_hoc)
            errs = services.validate(ld, data)
            if errs:
                bad += 1
                print(f"  Dòng {i + 2}: {'; '.join(errs)}")
        print(f"{len(df)} dòng, {bad} dòng thiếu trường bắt buộc")
        return
    res = importer.import_rows(create_storage(), ld, df, args.nam_hoc, keep_all=args.giu_nguyen,
                               skip_existing=not args.ghi_trung)
    for e in res["errors"]:
        print(f"  Dòng {e['Dòng']}: {e['Lỗi']}")
    print(f"Thành công {res['ok']}, bỏ qua (đã có) {res['skipped']}, lỗi {len(res['errors'])}")


if __name__ == "__main__":
    main()
