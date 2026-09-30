import sys
from pathlib import Path

import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from tuyensinh import importer, services  # noqa: E402
from tuyensinh.schema import TUYEN_SINH  # noqa: E402
from tuyensinh.storage.local import LocalStorage  # noqa: E402


def _df():
    return pd.DataFrame([
        {"Title": "A", "HoTenHS": "Nguyễn A", "SDT": "0901111111", "NgayLienHe": "2026-05-01",
         "Khoi": "10", "NamHoc": "2026-2027"},
        # trùng hệt dòng trên (có trong dữ liệu cũ) -> vẫn phải giữ đủ 2 dòng
        {"Title": "A", "HoTenHS": "Nguyễn A", "SDT": "0901111111", "NgayLienHe": "2026-05-01",
         "Khoi": "10", "NamHoc": "2026-2027"},
        # thiếu ngày liên hệ, không có năm học -> dùng năm học mặc định
        {"Title": "B", "HoTenHS": "Trần B", "SDT": "0902222222", "Khoi": "6"},
    ])


def test_import_chay_lai_khong_trung(tmp_path):
    st = LocalStorage(tmp_path / "t.sqlite3")
    r1 = importer.import_rows(st, TUYEN_SINH, _df(), "2025-2026", workers=3)
    assert (r1["ok"], r1["skipped"], r1["errors"]) == (3, 0, [])
    r2 = importer.import_rows(st, TUYEN_SINH, _df(), "2025-2026", workers=3)
    assert (r2["ok"], r2["skipped"]) == (0, 3)
    df = services.load_df(st, TUYEN_SINH)
    assert len(df) == 3 and set(df["NamHoc"]) == {"2026-2027", "2025-2026"}


def test_import_kiem_tra_bat_buoc(tmp_path):
    st = LocalStorage(tmp_path / "t.sqlite3")
    r = importer.import_rows(st, TUYEN_SINH, _df(), "2025-2026", keep_all=False, workers=1)
    assert r["ok"] == 2 and len(r["errors"]) == 1 and "Ngày liên hệ" in r["errors"][0]["Lỗi"]


def test_read_frame_nhan_ten_hien_thi(tmp_path):
    p = tmp_path / "x.xlsx"
    pd.DataFrame({"Họ tên HS": ["A"], "SĐT": ["0901"], "Nam hoc": ["2026-2027"],
                  "Cột lạ": [1]}).to_excel(p, index=False)
    df, skipped = importer.read_frame(str(p), TUYEN_SINH)
    assert list(df.columns) == ["HoTenHS", "SDT", "NamHoc"] and skipped == ["Cột lạ"]


def test_link_tuyen_sinh(tmp_path):
    from tuyensinh import importer
    from tuyensinh.schema import TUYEN_SINH
    from tuyensinh.storage.local import LocalStorage

    st = LocalStorage(str(tmp_path / "t.db"))
    a = st.create_item(TUYEN_SINH.name, {"HoTenHS": "Trần Gia Bảo", "SDT": "0903750252",
                                         "NamHoc": "2025-2026"})
    b = st.create_item(TUYEN_SINH.name, {"HoTenHS": "Hồ Duy", "NgaySinh": "2013-09-08",
                                         "NamHoc": "2025-2026"})
    rows = [{"HoTen": "TRẦN GIA BẢO", "DienThoaiMe": "0903 750 252", "NamHoc": "2026-2027"},
            {"HoTen": "Hồ Duy", "NgaySinh": "2013-09-08 00:00:00", "NamHoc": "2025-2026"},
            {"HoTen": "Người Khác", "DienThoaiSLL": "0903750252"}]
    assert importer.link_tuyen_sinh(st, rows) == 2
    assert rows[0]["TuyenSinhID"] == str(a["id"]) and rows[1]["TuyenSinhID"] == str(b["id"])
    assert "TuyenSinhID" not in rows[2]


def test_link_existing(tmp_path):
    from tuyensinh import importer
    from tuyensinh.schema import NHAP_HOC, TUYEN_SINH
    from tuyensinh.storage.local import LocalStorage

    st = LocalStorage(str(tmp_path / "t.db"))
    ts = st.create_item(TUYEN_SINH.name, {"HoTenHS": "An", "SDT": "0901234567", "NamHoc": "2026-2027"})
    nh = st.create_item(NHAP_HOC.name, {"HoTen": "An", "DienThoaiSLL": "0901234567",
                                        "NamHoc": "2026-2027"})
    res = importer.link_existing(st)
    assert res == {"total": 1, "chua_lien_ket": 1, "lien_ket": 1}
    assert str(st.get_item(NHAP_HOC.name, nh["id"])["TuyenSinhID"]) == str(ts["id"])
