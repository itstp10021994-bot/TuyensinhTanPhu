import importlib.util
import sys
from pathlib import Path

import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from tuyensinh import danh_muc  # noqa: E402
from tuyensinh.schema import NHAP_HOC, TUYEN_SINH  # noqa: E402


def test_dia_gioi_moi_nhat():
    dm = danh_muc.load()
    assert len(dm["tinh"]) == 34
    assert sum(len(v) for v in dm["xa_theo_tinh"].values()) == 3321
    assert dm["nguon_dia_gioi"]["phien_ban"]
    # NQ 36, 39/2026/QH16: Đồng Nai, Quảng Ninh, Bắc Ninh là thành phố trực thuộc TW
    assert danh_muc.normalize_tinh("Tỉnh Đồng Nai") == "Thành phố Đồng Nai"
    assert "Phường Bố Hạ" in danh_muc.xa_of("Tỉnh Bắc Ninh")
    assert "Phường Tân Phú" in danh_muc.xa_of("Thành phố Hồ Chí Minh")
    # giữ cách viết của danh mục VEMIS
    assert "Xã Hòa Lạc" in danh_muc.xa_of("Thành phố Hà Nội")


def test_chuoi_phu_thuoc():
    assert danh_muc.parents(TUYEN_SINH.get("TruongCu")) == ["TruongCu_Tinh", "TruongCu_QuanHuyen"]
    assert danh_muc.parents(NHAP_HOC.get("ChoO_Xa")) == ["ChoO_Tinh"]
    keys = [f.key for f in TUYEN_SINH.fields]
    assert keys.index("TruongCu_Tinh") < keys.index("TruongCu_QuanHuyen") < keys.index("TruongCu")


def _load_script(name):
    spec = importlib.util.spec_from_file_location(name, ROOT / "scripts" / f"{name}.py")
    sys.path.insert(0, str(ROOT / "scripts"))
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def test_import_va_goi_y_truong(tmp_path, monkeypatch):
    csv_path = tmp_path / "truong_hoc.csv"
    monkeypatch.setattr(danh_muc, "TRUONG_CSV", csv_path)
    danh_muc._truong_index.cache_clear()
    src = tmp_path / "ds.xlsx"
    pd.DataFrame({"Tỉnh": ["TP Hồ Chí Minh", "Hồ Chí Minh", "Tỉnh Đồng Nai", "Hồ Chí Minh"],
                  "Phường/Xã": ["Tân Phú", "Phường Tân Phú", "Phường Trảng Bom", "Không có"],
                  "Tên trường": ["THCS A", "THCS A", "THCS B", "THCS C"]}).to_excel(src, index=False)
    mod = _load_script("import_truong_hoc")
    monkeypatch.setattr(sys, "argv", ["x", str(src)])
    mod.main()
    danh_muc._truong_index.cache_clear()
    assert danh_muc.truong_hoc("Thành phố Hồ Chí Minh", "Phường Tân Phú") == ["THCS A"]
    assert danh_muc.truong_hoc("Tỉnh Đồng Nai", "Phường Trảng Bom") == ["THCS B"]
    assert danh_muc.truong_hoc("Thành phố Hồ Chí Minh") == ["THCS A"]  # cả tỉnh
    assert danh_muc.options_for(TUYEN_SINH.get("TruongCu"),
                                {"TruongCu_Tinh": "Thành phố Hồ Chí Minh",
                                 "TruongCu_QuanHuyen": "Phường Tân Phú"}) == ["THCS A"]
    danh_muc._truong_index.cache_clear()


def test_build_truong_hoc_osm(tmp_path, monkeypatch):
    import json

    code = next(k for k, v in danh_muc.load()["ma_xa"].items()
                if v == ["Thành phố Hồ Chí Minh", "Phường Tân Phú"])
    square = {"type": "Polygon", "coordinates": [[[106.63, 10.76], [106.65, 10.76],
                                                    [106.65, 10.79], [106.63, 10.79],
                                                    [106.63, 10.76]]]}
    gis = tmp_path / "gis.ndjson"
    gis.write_text('{"index":{}}\n' + json.dumps(
        {"Code": "79", "Wards": [{"Code": code, "FullName": "Phường Tân Phú",
                                  "GIS": {"Geometry": square}}]}, ensure_ascii=False) + "\n",
        encoding="utf-8")
    osm = tmp_path / "osm.json"
    osm.write_text(json.dumps({"elements": [
        {"lat": 10.77, "lon": 106.64, "tags": {"amenity": "school", "name": "Trường THCS Thử"}},
        {"center": {"lat": 10.771, "lon": 106.641},
         "tags": {"amenity": "kindergarten", "name": "Hoa Sen"}},
        {"lat": 10.772, "lon": 106.64, "tags": {"amenity": "school", "name": "Trung tâm Anh ngữ X"}},
        {"lat": 21.0, "lon": 105.8, "tags": {"amenity": "school", "name": "Trường Tiểu học Xa"}},
    ]}, ensure_ascii=False), encoding="utf-8")
    out = tmp_path / "truong_hoc.csv"
    monkeypatch.setattr(danh_muc, "TRUONG_CSV", out)
    mod = _load_script("build_truong_hoc_osm")
    monkeypatch.setattr(mod, "OUT", out)
    monkeypatch.setattr(sys, "argv", ["x", "--osm", str(osm), "--gis", str(gis)])
    mod.main()
    rows = out.read_text(encoding="utf-8").splitlines()
    assert rows[1:] == ["Thành phố Hồ Chí Minh,Phường Tân Phú,Hoa Sen,Mầm non",
                        "Thành phố Hồ Chí Minh,Phường Tân Phú,Trường THCS Thử,THCS"]
    assert mod.cap_hoc("Trường TH-THCS-THPT Tân Phú", "school") == "Liên cấp"
    assert mod.cap_hoc("Trường THPT Trần Phú", "school") == "THPT"
    assert mod.cap_hoc("Trường Tiểu học Tân Sơn Nhì", "school") == "Tiểu học"
