"""Đọc/ghi SharePoint List thông qua 1 flow Power Automate (Premium).

Flow: "When a HTTP request is received" -> "Send an HTTP request to SharePoint" -> "Response".
App gửi {"key", "method", "uri", "body"}; flow chuyển nguyên yêu cầu tới REST API của site
và trả kết quả về. Không cần đăng ký App trên Entra ID. Cách tạo flow: docs/power_automate.md
"""
from __future__ import annotations

import re
import time

import requests

from .. import config
from ..schema import BOOL, CHOICE, DATE, NOTE, NUMBER, Field
from . import convert
from .base import Storage

_GUID = re.compile(r"^\{?[0-9a-fA-F]{8}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{12}\}?$")


def list_path(list_name: str) -> str:
    """Đường dẫn REST tới list: theo GUID (vd lấy từ file .iqy) hoặc theo tên hiển thị."""
    real = config.list_name(list_name)
    if _GUID.match(real):
        return f"_api/web/lists(guid'{real.strip('{}')}')"
    return f"_api/web/lists/GetByTitle('{real.replace(chr(39), chr(39) * 2)}')"


def field_xml(f: Field, internal: str) -> str:
    title = f.label.replace("&", "&amp;").replace('"', "&quot;").replace("<", "&lt;")
    attrs = f'DisplayName="{title}" Name="{internal}" StaticName="{internal}"'
    if f.type == DATE:
        return f'<Field Type="DateTime" Format="DateOnly" {attrs}/>'
    if f.type == NUMBER:
        return f'<Field Type="Number" Decimals="0" {attrs}/>'
    if f.type == BOOL:
        return f'<Field Type="Boolean" {attrs}><Default>0</Default></Field>'
    if f.type == NOTE:
        return f'<Field Type="Note" NumLines="4" RichText="FALSE" {attrs}/>'
    if f.type == CHOICE and isinstance(f.options, tuple):
        choices = "".join(f"<CHOICE>{c}</CHOICE>" for c in f.options)
        return f'<Field Type="Choice" FillInChoice="TRUE" {attrs}><CHOICES>{choices}</CHOICES></Field>'
    return f'<Field Type="Text" MaxLength="255" {attrs}/>'


class PowerAutomateStorage(Storage):
    def __init__(self, flow_url: str, key: str = "", site_url: str = ""):
        self.flow_url = flow_url
        self.key = key
        self.site_url = site_url.rstrip("/")
        self._session = requests.Session()
        self._maps: dict[str, convert.ColumnMap] = {}

    @classmethod
    def from_config(cls) -> "PowerAutomateStorage":
        pa = config.section("powerautomate")
        url = config.get("PA_FLOW_URL") or pa.get("flow_url")
        if not url:
            raise RuntimeError("Thiếu cấu hình [powerautomate] flow_url trong secrets.toml")
        return cls(url, config.get("PA_KEY") or pa.get("key", ""),
                   config.get("SP_SITE_URL") or pa.get("site_url", ""))

    # ------------------------------------------------------------------ gọi flow
    def call(self, method: str, uri: str, body: dict | None = None):
        payload = {"key": self.key, "method": method, "uri": uri, "body": body or {}}
        for attempt in range(4):
            r = self._session.post(self.flow_url, json=payload, timeout=120)
            if r.status_code in (429, 502, 503, 504):
                time.sleep(int(r.headers.get("Retry-After", 2 ** attempt)))
                continue
            if r.status_code >= 400:
                raise RuntimeError(f"Power Automate {method} {uri} -> {r.status_code}: {r.text[:500]}")
            if not r.content:
                return {}
            try:
                return r.json()
            except ValueError:
                return {}
        raise RuntimeError(f"Power Automate {method} {uri}: quá số lần thử lại")

    def _relative(self, next_link: str) -> str:
        i = next_link.find("_api/")
        return next_link[i:] if i >= 0 else next_link

    def colmap(self, list_name: str) -> convert.ColumnMap:
        """Đọc danh sách cột của list một lần để tìm tên nội bộ theo tên hiển thị."""
        if list_name not in self._maps:
            self._maps[list_name] = convert.ColumnMap(list_name, self.columns(list_name))
        return self._maps[list_name]

    def _item(self, list_name: str, it: dict) -> dict:
        item_id = it.get("Id", it.get("ID"))
        return self.colmap(list_name).from_sp(it, item_id, it.get("Created"), it.get("Modified"))

    def _select(self, list_name: str) -> str:
        people = self.colmap(list_name).person_columns
        if not people:
            return ""
        sel = ",".join(["*"] + [f"{p}/Title" for p in people])
        return f"&$select={sel}&$expand={','.join(people)}"

    # ------------------------------------------------------------------ CRUD
    def list_items(self, list_name):
        uri = f"{list_path(list_name)}/items?$top=5000{self._select(list_name)}"
        out = []
        while uri:
            data = self.call("GET", uri)
            out.extend(self._item(list_name, it) for it in data.get("value", []))
            nxt = data.get("odata.nextLink") or data.get("@odata.nextLink")
            uri = self._relative(nxt) if nxt else None
        return out

    def get_item(self, list_name, item_id):
        sel = self._select(list_name).lstrip("&")
        try:
            it = self.call("GET", f"{list_path(list_name)}/items({int(item_id)})"
                                  + (f"?{sel}" if sel else ""))
        except RuntimeError as e:
            if "404" in str(e):
                return None
            raise
        return self._item(list_name, it)

    def create_item(self, list_name, data):
        body = {k: v for k, v in self.colmap(list_name).to_sp(data).items() if v is not None}
        it = self.call("POST", f"{list_path(list_name)}/items", body)
        new_id = it.get("Id", it.get("ID"))
        return self.get_item(list_name, new_id) if new_id else it

    def update_item(self, list_name, item_id, data):
        self.call("PATCH", f"{list_path(list_name)}/items({int(item_id)})",
                  self.colmap(list_name).to_sp(data))
        return self.get_item(list_name, item_id)

    def delete_item(self, list_name, item_id):
        self.call("DELETE", f"{list_path(list_name)}/items({int(item_id)})")

    # ------------------------------------------------------------------ cấu trúc list
    def columns(self, list_name) -> list[dict]:
        data = self.call("GET", f"{list_path(list_name)}/fields?$filter=Hidden eq false"
                                "&$select=InternalName,Title,TypeAsString,ReadOnlyField")
        rows = data.get("value")
        if rows is None and isinstance(data.get("d"), dict):  # odata=verbose
            rows = data["d"].get("results")
        if not rows:
            raise RuntimeError(
                "Power Automate: flow chạy nhưng không trả danh sách cột về app. Kiểm tra bước "
                "Response trong nhánh True: Body = body('Send_an_HTTP_request_to_SharePoint') và "
                "header Accept = application/json;odata=nometadata. Phản hồi nhận được: "
                f"{str(data)[:300]}")
        return [{"name": c["InternalName"], "title": c["Title"], "type": c["TypeAsString"]}
                for c in rows if not c.get("ReadOnlyField")]

    def list_exists(self, list_name) -> bool:
        try:
            self.call("GET", f"{list_path(list_name)}?$select=Id")
            return True
        except RuntimeError as e:
            # chỉ coi là "chưa có list" khi chính SharePoint báo vậy; 404 khác (URL flow sai,
            # flow bị tắt…) là lỗi kết nối
            if "does not exist" in str(e):
                m = re.search(r"at site with URL '([^'\\]+)", str(e))
                if m:
                    self.site_seen = m.group(1)
                return False
            raise

    def list_titles(self) -> list[str]:
        """Các list đang có trên site mà flow kết nối (để chẩn đoán sai site / sai tên)."""
        data = self.call("GET", "_api/web/lists?$filter=Hidden eq false&$select=Title")
        return sorted(c["Title"] for c in data.get("value", []))

    def create_list(self, list_name, description=""):
        self.call("POST", "_api/web/lists", {"Title": config.list_name(list_name),
                                              "BaseTemplate": 100, "Description": description})

    def add_column(self, list_name, f: Field, internal: str):
        # Options=8: dùng Name làm tên nội bộ
        self.call("POST", f"{list_path(list_name)}/fields/CreateFieldAsXml",
                  {"parameters": {"SchemaXml": field_xml(f, internal), "Options": 8}})
        self._maps.pop(list_name, None)
