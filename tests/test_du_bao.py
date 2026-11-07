"""Dự báo tuyển sinh mùa tới."""
import sys
from datetime import date
from pathlib import Path

import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from tuyensinh import du_bao as DB  # noqa: E402

def _ts(rows):
    return pd.DataFrame(rows, columns=["NamHoc", "NgayLienHe", "TrangThai", "Khoi"])


def test_du_bao_theo_cung_ky_nam_truoc():
    rows = []
    # mùa 2026-2027: 100 liên hệ, 40 trước 01/11/2025, 25 nhập học
    for i in range(100):
        d = date(2025, 10, 1) if i < 40 else date(2026, 4, 1)
        rows.append(("2026-2027", d, "Nhập học" if i < 25 else "Tư vấn", "10" if i % 2 else "6"))
    # mùa 2027-2028: 50 liên hệ đến 01/11/2026
    rows += [("2027-2028", date(2026, 10, 15), "Tư vấn", "10")] * 50
    kq = DB.du_bao(_ts(rows), date(2026, 11, 1))
    assert kq.nam_hoc == "2027-2028" and kq.lh_den_nay == 50
    assert kq.lh_cung_ky == 40 and kq.lh_nam_truoc == 100
    assert kq.du_bao_lh == 125  # 50 × 100 / 40
    assert kq.ty_le_nh == 0.25 and kq.du_bao_nh == 31
    assert kq.bon_tuan_toi == 0  # năm trước không có liên hệ nào trong 4 tuần tới
    assert set(kq.duong["Chuỗi"]) == {"Mùa 2027-2028 (thực tế)", "Mùa 2026-2027",
                                      "Mùa 2027-2028 (dự báo)"}
    assert kq.duong[kq.duong["Chuỗi"].str.contains("dự báo")]["Liên hệ cộng dồn"].max() == 125
    assert kq.theo_khoi["Dự báo liên hệ"].sum() >= 120


def test_du_bao_dau_mua_va_chi_co_nam_nay():
    rows = [("2026-2027", date(2026, 3, 1), "Nhập học", "10")] * 30
    kq = DB.du_bao(_ts(rows), date(2026, 11, 1))  # mùa 2027-2028 chưa có liên hệ
    assert kq.lh_den_nay == 0 and kq.du_bao_lh == 30 and kq.du_bao_nh == 30
    kq = DB.du_bao(_ts(rows), date(2026, 3, 29))  # chỉ có năm nay: theo tốc độ 8 tuần
    assert kq.nam_hoc == "2026-2027" and kq.lh_cung_ky is None and kq.du_bao_lh > 30
    assert DB.nam_hoc_dang_tuyen(date(2026, 8, 31)) == "2026-2027"
    assert DB.nam_hoc_dang_tuyen(date(2026, 9, 1)) == "2027-2028"
    assert DB.du_bao(_ts([]), date(2026, 11, 1)).du_bao_lh == 0
