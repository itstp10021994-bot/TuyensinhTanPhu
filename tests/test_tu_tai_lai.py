"""App tự bỏ bản đệm của list vừa bị sửa / xóa dòng thẳng trên SharePoint."""
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from tuyensinh import ui  # noqa: E402
from tuyensinh.storage import convert  # noqa: E402
from tuyensinh.storage.powerautomate import PowerAutomateStorage  # noqa: E402


class _Kho:
    def __init__(self, moc):
        self.moc, self.goi = moc, 0

    def lan_doi_cuoi(self, names):
        self.goi += 1
        return {n: self.moc[n] for n in names if n in self.moc}


def test_bo_ban_dem_list_vua_doi():
    store = ui._data_store()
    store["lists"].clear()
    store.pop("kt_at", None)
    now = datetime.now(timezone.utc)
    store["lists"]["A"] = {"luc": now - timedelta(minutes=2), "items": [1]}
    store["lists"]["B"] = {"luc": now - timedelta(minutes=2), "items": [2]}
    kho = _Kho({"A": now - timedelta(minutes=1),        # xóa dòng sau lúc tải -> tải lại
                "B": now - timedelta(minutes=5)})       # đổi trước lúc tải -> giữ
    ui._kiem_tra_thay_doi(kho)
    _cho_nen(store)
    assert "A" not in store["lists"] and "B" in store["lists"]
    ui._kiem_tra_thay_doi(kho)  # trong 30 giây: không hỏi lại SharePoint
    assert kho.goi == 1
    store["lists"].clear()


def _cho_nen(store):
    """Chờ lần kiểm tra chạy nền xong."""
    assert store["kt_lock"].acquire(timeout=5)
    store["kt_lock"].release()


def _dat(name, items):
    import threading
    store = ui._data_store()
    store["lists"][name] = {"lock": threading.Lock(), "items": items, "frames": {"x": 1},
                            "memo": {"y": 2}, "at": __import__("time").monotonic(),
                            "luc": datetime.now(timezone.utc) - timedelta(minutes=1)}
    return store["lists"][name]


def test_ghi_trong_app_cap_nhat_ban_dem_khong_tai_lai():
    store = ui._data_store()
    store["lists"].clear()
    e = _dat("L", [{"id": "1", "a": 1}, {"id": "2", "a": 2}])
    ui._ghi_dem("L", {"id": "2", "a": 20}, "2")          # sửa
    ui._ghi_dem("L", {"id": "3", "a": 3})                # thêm
    ui._ghi_dem("L", None, "1")                          # xóa
    assert e["items"] == [{"id": "2", "a": 20}, {"id": "3", "a": 3}]
    assert e["frames"] == {} and e["memo"] == {} and ui._fresh(e)
    assert ui._ban_ghi_dem("L", 3) == {"id": "3", "a": 3}
    # SharePoint báo đổi đúng lúc app vừa ghi: không bỏ bản đệm
    store.pop("kt_at", None)
    ui._kiem_tra_thay_doi(_Kho({"L": e["ghi_moc"]}))
    _cho_nen(store)
    assert store["lists"].get("L") is e
    # có người sửa thẳng trên SharePoint sau đó: bỏ bản đệm để tải lại
    store.pop("kt_at", None)
    ui._kiem_tra_thay_doi(_Kho({"L": e["ghi_moc"] + timedelta(minutes=1)}))
    _cho_nen(store)
    assert "L" not in store["lists"]
    store["lists"].clear()


def test_user_storage_ghi_qua_ban_dem(tmp_path):
    from tuyensinh.storage.local import LocalStorage
    base = LocalStorage(tmp_path / "x.db")
    r = base.create_item("Data_TuyenSinh", {"HoTenHS": "A", "NamHoc": "2026-2027"})
    store = ui._data_store()
    store["lists"].clear()
    e = _dat("Data_TuyenSinh", base.list_items("Data_TuyenSinh"))
    s = ui._UserStorage(base, "Cô Quỳnh")
    s.update_item("Data_TuyenSinh", r["id"], {"HoTenHS": "B"})
    moi = s.create_item("Data_TuyenSinh", {"HoTenHS": "C", "NamHoc": "2026-2027"})
    assert [x["HoTenHS"] for x in e["items"]] == ["B", "C"]
    assert e["items"][0]["NguoiCapNhat"] == "Cô Quỳnh"
    s.delete_item("Data_TuyenSinh", moi["id"])
    assert [x["HoTenHS"] for x in e["items"]] == ["B"]
    assert e["items"] == base.list_items("Data_TuyenSinh")
    store["lists"].clear()


def test_power_automate_lan_doi_cuoi(monkeypatch):
    pa = PowerAutomateStorage("http://x")
    monkeypatch.setattr(pa, "call", lambda *a, **k: {"value": [
        {"Id": "1", "Title": "Data_NhapHoc", "LastItemModifiedDate": "2026-10-31T03:00:00Z",
         "LastItemDeletedDate": "2026-10-31T04:00:00Z"}]})
    moc = pa.lan_doi_cuoi(["Data_NhapHoc", "Khac"])
    assert moc == {"Data_NhapHoc": convert.utc("2026-10-31T04:00:00Z")}
