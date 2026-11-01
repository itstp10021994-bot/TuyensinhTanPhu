"""Chuẩn hóa địa giới hành chính về danh mục mới (34 tỉnh, phường/xã mới)."""
import sys
from pathlib import Path

import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from tuyensinh import dia_gioi as DG  # noqa: E402
from tuyensinh.storage.local import LocalStorage  # noqa: E402


def test_chuan_tinh():
    assert DG.chuan_tinh("TP. Hồ Chí Minh") == "Thành phố Hồ Chí Minh"
    assert DG.chuan_tinh("tp hcm") == "Thành phố Hồ Chí Minh"
    assert DG.chuan_tinh("Tây Ninh") == "Tỉnh Tây Ninh"
    assert DG.chuan_tinh("Long An") == "Tỉnh Tây Ninh"           # tỉnh cũ -> tỉnh mới
    assert DG.chuan_tinh("Tỉnh Bình Dương") == "Thành phố Hồ Chí Minh"
    assert DG.chuan_tinh("Bà Rịa - Vũng Tàu") == "Thành phố Hồ Chí Minh"
    assert DG.chuan_tinh("Thành phố Hồ Chí Minh") == "Thành phố Hồ Chí Minh"
    assert DG.chuan_tinh("Atlantis") == "" and DG.chuan_tinh("") == ""
    bang = DG._bang_tinh()  # mọi tỉnh đích của bảng 63 -> 34 đều có trong danh mục mới
    assert all(DG._loi(v) in bang for v in DG.TINH_CU_MOI.values())


def test_chuan_xa():
    hcm = "Thành phố Hồ Chí Minh"
    assert DG.chuan_xa(hcm, "Phường Tân Phú") == "Phường Tân Phú"
    assert DG.chuan_xa(hcm, "P. Tân Phú") == "Phường Tân Phú"
    assert DG.chuan_xa(hcm, "phuong tan phu") == "Phường Tân Phú"
    assert DG.chuan_xa(hcm, "Phường 14") == ""                 # phường cũ đánh số: không đoán
    assert DG.chuan_xa(hcm, "Phường Không Có") == ""


def test_kiem_tra_va_ghi(tmp_path):
    st = LocalStorage(tmp_path / "d.sqlite3")
    a = st.create_item("Data_NhapHoc", {"HoTen": "An", "ChoO_Tinh": "TP. Hồ Chí Minh",
                                        "ChoO_Xa": "P. Tân Phú", "QueQuan_Tinh": "Nước Ngoài",
                                        "HK_Tinh": "TP. Hồ Chí Minh", "HK_Xa": "Phường 14"})
    st.create_item("Data_NhapHoc", {"HoTen": "Bình", "ChoO_Tinh": "Thành phố Hồ Chí Minh",
                                    "ChoO_Xa": "Phường Tân Phú"})
    items = st.list_items("Data_NhapHoc")
    thay, khong = DG.kiem_tra(items, "Data_NhapHoc")
    assert len(thay) == 1 and thay[0]["cot"] == {
        "ChoO_Tinh": ("TP. Hồ Chí Minh", "Thành phố Hồ Chí Minh"),
        "ChoO_Xa": ("P. Tân Phú", "Phường Tân Phú"),
        "HK_Tinh": ("TP. Hồ Chí Minh", "Thành phố Hồ Chí Minh")}
    assert khong == {("HK_Xa", "Thành phố Hồ Chí Minh", "Phường 14"): 1}  # nước ngoài: bỏ qua
    DG.ghi(st, "Data_NhapHoc", thay)
    # chọn tay cho ô không khớp
    items = st.list_items("Data_NhapHoc")
    thay2 = DG.ap_dung_anh_xa(items, "Data_NhapHoc",
                              {("HK_Xa", "Thành phố Hồ Chí Minh", "Phường 14"): "Phường Tân Sơn Nhì"})
    DG.ghi(st, "Data_NhapHoc", thay2)
    r = st.get_item("Data_NhapHoc", a["id"])
    assert (r["ChoO_Tinh"], r["ChoO_Xa"], r["HK_Xa"], r["QueQuan_Tinh"]) == \
        ("Thành phố Hồ Chí Minh", "Phường Tân Phú", "Phường Tân Sơn Nhì", "Nước Ngoài")
    assert DG.kiem_tra(st.list_items("Data_NhapHoc"), "Data_NhapHoc") == ([], {})


def test_chuan_bang_file_vemis():
    df = pd.DataFrame({"ChoO_Tinh": ["TP. Hồ Chí Minh", None], "ChoO_Xa": ["Phường Tân Phú", None]})
    out = DG.chuan_bang(df)
    assert out.iloc[0].tolist() == ["Thành phố Hồ Chí Minh", "Phường Tân Phú"]
