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
    assert "A" not in store["lists"] and "B" in store["lists"]
    ui._kiem_tra_thay_doi(kho)  # trong 30 giây: không hỏi lại SharePoint
    assert kho.goi == 1
    store["lists"].clear()


def test_power_automate_lan_doi_cuoi(monkeypatch):
    pa = PowerAutomateStorage("http://x")
    monkeypatch.setattr(pa, "call", lambda *a, **k: {"value": [
        {"Id": "1", "Title": "Data_NhapHoc", "LastItemModifiedDate": "2026-10-31T03:00:00Z",
         "LastItemDeletedDate": "2026-10-31T04:00:00Z"}]})
    moc = pa.lan_doi_cuoi(["Data_NhapHoc", "Khac"])
    assert moc == {"Data_NhapHoc": convert.utc("2026-10-31T04:00:00Z")}
