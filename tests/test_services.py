import io
import sys
from pathlib import Path

import pandas as pd
import pytest
from openpyxl import load_workbook

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from tuyensinh import danh_muc, export_vemis, services  # noqa: E402
from tuyensinh.schema import NHAP_HOC, THU_PHI, TUYEN_SINH  # noqa: E402
from tuyensinh.storage.local import LocalStorage  # noqa: E402
from tuyensinh.storage.sharepoint import from_graph, to_graph  # noqa: E402

HS = {"NamHoc": "2026-2027", "NgayLienHe": "2026-08-06", "SDT": "0927 666 649",
      "HoTenHS": "Trần Huy Long", "Khoi": "10", "CheDo": "Nội trú", "GioiTinh": "Nam",
      "NgaySinh": "2011-05-02"}


@pytest.fixture
def storage(tmp_path):
    return LocalStorage(tmp_path / "t.sqlite3")


def test_save_validates_required(storage):
    with pytest.raises(ValueError, match="Họ tên HS"):
        services.save_tuyen_sinh(storage, {**HS, "HoTenHS": ""})
    with pytest.raises(ValueError, match="SĐT"):
        services.save_tuyen_sinh(storage, {**HS, "SDT": "123"})


def test_phone_normalized_and_default_status(storage):
    rec = services.save_tuyen_sinh(storage, HS)
    assert rec["SDT"] == "0927666649"
    assert rec["TrangThai"] == "Tư vấn"
    assert services.normalize_phone("+84 927 666 649") == "0927666649"


def test_nhap_hoc_creates_enrollment_record(storage):
    rec = services.save_tuyen_sinh(storage, HS)
    rec = services.set_trang_thai(storage, rec["id"], "Nhập học")
    assert rec["NgayNhapHoc"] and rec["NgayNopHoSo"]
    nh = services.nhap_hoc_of(storage, rec["id"])
    assert nh["HoTen"] == "Trần Huy Long"
    assert nh["LopHoc"] == "10" and nh["NoiTruBanTru"] == "Nội trú"
    assert nh["DienThoaiSLL"] == "0927666649"
    # Chuyển lại không tạo trùng; hồ sơ bị ẩn khi rút hồ sơ
    services.set_trang_thai(storage, rec["id"], "Nhập học")
    assert len(storage.list_items(NHAP_HOC.name)) == 1
    services.set_trang_thai(storage, rec["id"], "Rút hồ sơ", "Chuyển trường")
    assert services.nhap_hoc_df(storage, "2026-2027").empty


def test_status_via_form_save(storage):
    rec = services.save_tuyen_sinh(storage, {**HS, "TrangThai": "Nhập học"})
    assert services.nhap_hoc_of(storage, rec["id"]) is not None


def test_duplicates(storage):
    services.save_tuyen_sinh(storage, HS)
    assert len(services.find_duplicates(storage, {**HS, "SDT": "0927666649"})) == 1


def test_payments_summary(storage):
    rec = services.save_tuyen_sinh(storage, {**HS, "TrangThai": "Nộp hồ sơ"})
    p = services.add_payment(storage, {"TuyenSinhID": rec["id"], "NamHoc": "2026-2027",
                                       "LoaiPhi": "Phí giữ chỗ", "SoTien": 2_000_000})
    services.add_payment(storage, {"TuyenSinhID": rec["id"], "NamHoc": "2026-2027",
                                   "LoaiPhi": "Học phí", "SoTien": 5_000_000})
    with pytest.raises(ValueError):
        services.add_payment(storage, {"TuyenSinhID": rec["id"], "NamHoc": "2026-2027",
                                       "LoaiPhi": "Học phí", "SoTien": 0})
    services.confirm_payments(storage, [p["id"]], "Kế toán A")
    ts = services.load_df(storage, TUYEN_SINH, "2026-2027")
    tp = services.load_df(storage, THU_PHI, "2026-2027")
    sm = services.payment_summary(ts, tp)
    assert sm.loc[0, "Phí giữ chỗ"] == 2_000_000
    assert sm.loc[0, "Tổng đã thu"] == 2_000_000  # học phí chưa xác nhận


def test_export_vemis_layout(storage):
    rec = services.save_tuyen_sinh(storage, {**HS, "TrangThai": "Nhập học"})
    nh = services.nhap_hoc_of(storage, rec["id"])
    services.save_nhap_hoc(storage, {**nh, "DoanVien": True, "ChoO_Tinh": "Thành phố Hồ Chí Minh"},
                           nh["id"])
    df = services.nhap_hoc_df(storage, "2026-2027")
    wb = load_workbook(io.BytesIO(export_vemis.to_bytes(df)))
    ws = wb["Sheet1"]
    assert len(export_vemis.COLUMNS) == 54
    assert ws.cell(7, 12).value == "Chỗ ở hiện nay" and ws.cell(8, 12).value == "SN/Xóm"
    assert ws.cell(7, 54).value == "Ghi chú"
    row = [c.value for c in ws[9]]
    assert row[0] == 1 and row[6] == "Trần Huy Long" and row[7] == "02/05/2011"
    assert row[14] == "Thành phố Hồ Chí Minh" and row[34] == "x"
    assert row[46] == "0927666649"


def test_every_enrollment_field_is_exported():
    exported = {k for _, _, k in export_vemis.COLUMNS if k}
    assert exported == set(NHAP_HOC.keys) - {"TuyenSinhID", "NamHoc"}


def test_danh_muc_xa_depends_on_tinh():
    f = NHAP_HOC.get("ChoO_Xa")
    assert danh_muc.options_for(f, {}) == []
    xa = danh_muc.options_for(f, {"ChoO_Tinh": "Thành phố Hồ Chí Minh"})
    assert any("Tân Phú" in x for x in xa)
    assert "Kinh" in danh_muc.options_for(NHAP_HOC.get("DanToc"))


def test_graph_conversion_roundtrip():
    g = to_graph(TUYEN_SINH, {"id": "5", "HoTenHS": "A", "NgaySinh": "2011-05-02", "Khoi": "10"})
    assert g == {"HoTenHS": "A", "NgaySinh": "2011-05-02T12:00:00Z", "Khoi": "10", "Title": "A"}
    back = from_graph(TUYEN_SINH, {"id": "5", "fields": {**g, "@odata.etag": "x"}})
    assert back["NgaySinh"] == "2011-05-02" and back["id"] == "5"
    assert to_graph(THU_PHI, {"SoTien": "2000000"})["SoTien"] == 2_000_000.0


def test_to_df_types():
    df = services.to_df(THU_PHI, [{"id": "1", "SoTien": "100", "NgayThu": "2026-01-02"}])
    assert df.loc[0, "SoTien"] == 100 and str(df.loc[0, "NgayThu"]) == "2026-01-02"
    assert isinstance(df, pd.DataFrame)


def test_empty_dates_roundtrip_from_dataframe(storage):
    rec = services.save_tuyen_sinh(storage, {**HS, "NgaySinh": ""})
    row = services.load_df(storage, TUYEN_SINH).iloc[0].to_dict()
    services.save_tuyen_sinh(storage, row, rec["id"])
    assert storage.get_item(TUYEN_SINH.name, rec["id"])["NgaySinh"] == ""
