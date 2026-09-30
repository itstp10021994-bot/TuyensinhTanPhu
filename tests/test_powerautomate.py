"""Giả lập flow Power Automate + REST API SharePoint để kiểm tra PowerAutomateStorage."""
import re
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from tuyensinh import services  # noqa: E402
from tuyensinh.schema import NHAP_HOC, TUYEN_SINH  # noqa: E402
from tuyensinh.storage import powerautomate  # noqa: E402
from tuyensinh.storage.powerautomate import PowerAutomateStorage, list_path  # noqa: E402
from test_services import HS, SP_COLUMNS  # noqa: E402

TS_GUID = "d0608833-bddf-4d28-a7db-402eb246c017"


class FakeFlow:
    """Nhận payload {key, method, uri, body} như flow thật và thao tác trên list trong bộ nhớ."""

    def __init__(self):
        self.lists = {f"lists(guid'{TS_GUID}')": {"cols": [dict(c) for c in SP_COLUMNS], "items": {}},
                      "lists/GetByTitle('Data_NhapHoc')": {"cols": None, "items": {}}}
        self.next_id = 1
        self.calls = []

    def post(self, url, json, timeout):
        assert json["key"] == "bi-mat"
        self.calls.append((json["method"], json["uri"]))
        status, body = self.handle(json["method"], json["uri"], json["body"])
        return FakeResp(status, body)

    def handle(self, method, uri, body):
        m = re.match(r"_api/web/(lists\(guid'[^']+'\)|lists/GetByTitle\('[^']+'\))(.*)", uri)
        if not m:
            return 400, {"error": "bad uri"}
        lst = self.lists[m.group(1)]
        rest = m.group(2)
        if rest.startswith("/DefaultView/ViewFields"):
            view = lst.setdefault("view", ["LinkTitle"])
            add = re.search(r"AddViewField\('([^']+)'\)", rest)
            if add:
                view.append(add.group(1))
                return 200, {}
            return 200, {"Items": list(view)}
        if rest.startswith("/fields"):
            if method == "POST":  # CreateFieldAsXml
                xml = body["parameters"]["SchemaXml"]
                name = re.search(r'\sName="([^"]+)"', xml).group(1)
                title = re.search(r'DisplayName="([^"]+)"', xml).group(1)
                lst["cols"].append({"name": name, "title": title, "type": "Text"})
                return 200, {}
            return 200, {"value": [{"InternalName": c["name"], "Title": c["title"],
                                    "TypeAsString": c["type"]} for c in lst["cols"] or []]}
        if rest.startswith("?$select=Id"):
            return (404, {"error": "does not exist"}) if lst["cols"] is None else (200, {})
        mi = re.match(r"/items\((\d+)\)", rest)
        if rest.startswith("/items") and not mi:
            if method == "GET":
                return 200, {"value": list(lst["items"].values())}
            item = {**body, "Id": self.next_id, "ID": self.next_id}
            lst["items"][self.next_id] = item
            self.next_id += 1
            return 201, item
        iid = int(mi.group(1))
        if iid not in lst["items"]:
            return 404, {"error": "not found"}
        if method == "GET":
            return 200, lst["items"][iid]
        if method == "PATCH":
            lst["items"][iid].update(body)
            return 204, None
        if method == "DELETE":
            del lst["items"][iid]
            return 200, None
        return 400, {}


class FakeResp:
    def __init__(self, status, body):
        import json as _j
        self.status_code = status
        self.content = b"" if body is None else _j.dumps(body).encode()
        self.text = self.content.decode()
        self.headers = {}
        self._body = body

    def json(self):
        return self._body


@pytest.fixture
def pa(monkeypatch):
    monkeypatch.setenv("SP_LIST_Data_TuyenSinh", TS_GUID)
    flow = FakeFlow()
    st = PowerAutomateStorage("https://flow.example/invoke", key="bi-mat")
    st._session = flow
    return st, flow


def test_list_path():
    assert list_path("Data_NhapHoc") == "_api/web/lists/GetByTitle('Data_NhapHoc')"


def test_setup_creates_missing_nhap_hoc_list_columns(pa):
    st, flow = pa
    assert not st.list_exists("Data_NhapHoc")
    flow.lists["lists/GetByTitle('Data_NhapHoc')"]["cols"] = []  # như sau create_list
    for f in NHAP_HOC.fields:
        st.add_column(NHAP_HOC.name, f, f.key)
    assert {c["name"] for c in st.columns(NHAP_HOC.name)} == set(NHAP_HOC.keys)
    assert powerautomate.field_xml(TUYEN_SINH.get("NgaySinh"), "X").startswith(
        '<Field Type="DateTime" Format="DateOnly"')


def test_full_flow_through_power_automate(pa, monkeypatch):
    st, flow = pa
    flow.lists["lists/GetByTitle('Data_NhapHoc')"]["cols"] = [
        {"name": f.key, "title": f.sp_title, "type": "DateTime" if f.type == "date" else "Text"}
        for f in NHAP_HOC.fields]
    rec = services.save_tuyen_sinh(st, {**HS, "Toan1": 9})
    raw = flow.lists[f"lists(guid'{TS_GUID}')"]["items"][int(rec["id"])]
    by_title = {c["title"]: c["name"] for c in SP_COLUMNS}
    assert raw[by_title["Nam hoc"]] == "2026-2027" and raw[by_title["Bước"]] == "Tư vấn"
    assert raw[by_title["Toán 1"]] == "9"
    assert rec["HoTenHS"] == "Trần Huy Long" and rec["NgaySinh"] == "2011-05-02"

    services.set_trang_thai(st, rec["id"], "Nhập học")
    nh = services.nhap_hoc_of(st, rec["id"])
    assert nh["HoTen"] == "Trần Huy Long" and nh["NamHoc"] == "2026-2027"
    assert nh["NgaySinh"] == "2011-05-02" and nh["LopHoc"] == "10"

    st.delete_item(TUYEN_SINH.name, rec["id"])
    assert st.get_item(TUYEN_SINH.name, rec["id"]) is None
    assert all(u.startswith("_api/web/lists") for _, u in flow.calls)


def test_colmap_list_tao_tu_excel():
    """List tạo từ Excel: tên nội bộ field_N, tên hiển thị = key."""
    from tuyensinh.schema import TUYEN_SINH
    from tuyensinh.storage.convert import ColumnMap
    cols = [{"name": "Title", "title": "Title", "type": "Text"}] + [
        {"name": f"field_{i}", "title": f.key, "type": "Text"}
        for i, f in enumerate(TUYEN_SINH.fields, 1)]
    cm = ColumnMap(TUYEN_SINH.name, cols)
    assert cm.missing == []
    assert cm.internal["NamHoc"] == "field_1"
    assert cm.to_sp({"HoTenHS": "A"})[cm.internal["HoTenHS"]] == "A"


def test_them_moi_vao_list_tao_tu_excel(pa):
    """List tạo từ Excel: field_N, Khối là cột Số; thêm mới chỉ tốn 1 lần gọi flow."""
    st, flow = pa
    lst = flow.lists[f"lists(guid'{TS_GUID}')"]
    lst["cols"] = [{"name": "Title", "title": "Title", "type": "Text"}] + [
        {"name": f"field_{i}", "title": f.key,
         "type": "Number" if f.key == "Khoi" else "DateTime" if f.type == "date" else "Text"}
        for i, f in enumerate(TUYEN_SINH.fields, 1)]
    st.colmap(TUYEN_SINH.name)
    n = len(flow.calls)
    rec = services.save_tuyen_sinh(st, dict(HS))
    assert len(flow.calls) - n == 1  # chỉ POST, dùng luôn bản ghi SharePoint trả về
    raw = lst["items"][int(rec["id"])]
    khoi = st.colmap(TUYEN_SINH.name).internal["Khoi"]
    assert raw[khoi] == 10.0 and raw["Title"] == "Trần Huy Long"
    assert rec["Khoi"] == "10" and rec["HoTenHS"] == "Trần Huy Long"
    got = st.list_items(TUYEN_SINH.name)
    assert got[0]["Khoi"] == "10"
    assert "$select=Id,Created,Modified,field_1" in flow.calls[-1][1]



def test_setup_hien_du_cot(pa):
    from tuyensinh import importer
    st, flow = pa
    flow.lists["lists/GetByTitle('Data_NhapHoc')"]["cols"] = []
    importer.setup_lists(st, log=lambda m: None)
    view = flow.lists["lists/GetByTitle('Data_NhapHoc')"]["view"]
    assert set(NHAP_HOC.keys) <= set(view)
    n = len(flow.calls)
    importer.setup_lists(st, log=lambda m: None)  # chạy lại: không thêm trùng
    assert not any("AddViewField" in u for _, u in flow.calls[n:])
