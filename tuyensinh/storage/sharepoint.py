"""Lưu dữ liệu trên SharePoint Online (List) qua Microsoft Graph API.

Xác thực kiểu ứng dụng (client credentials): cần đăng ký App trên Microsoft Entra ID
với quyền Application `Sites.ReadWrite.All` (hoặc `Sites.Selected` + cấp quyền cho site).
Xem README.md mục "Cấu hình SharePoint".
"""
from __future__ import annotations

import re
import threading
import time
from urllib.parse import urlparse

import msal
import requests

from .. import config
from ..schema import Field
from . import convert
from .base import Storage

GRAPH = "https://graph.microsoft.com/v1.0"



class SharePointStorage(Storage):
    def __init__(self, tenant_id: str, client_id: str, client_secret: str, site_url: str):
        self._app = msal.ConfidentialClientApplication(
            client_id,
            authority=f"https://login.microsoftonline.com/{tenant_id}",
            client_credential=client_secret,
        )
        self._site_url = site_url.rstrip("/")
        self._site_id: str | None = None
        self._list_ids: dict[str, str] = {}
        self._lock = threading.Lock()
        self._session = requests.Session()
        self._maps: dict[str, convert.ColumnMap] = {}

    @classmethod
    def from_config(cls) -> "SharePointStorage":
        missing = [k for k in ("SP_TENANT_ID", "SP_CLIENT_ID", "SP_CLIENT_SECRET", "SP_SITE_URL")
                   if not config.get(k)]
        if missing:
            raise RuntimeError("Thiếu cấu hình SharePoint: " + ", ".join(missing))
        return cls(config.get("SP_TENANT_ID"), config.get("SP_CLIENT_ID"),
                   config.get("SP_CLIENT_SECRET"), config.get("SP_SITE_URL"))

    # ------------------------------------------------------------------ HTTP
    def _token(self) -> str:
        res = self._app.acquire_token_for_client(scopes=["https://graph.microsoft.com/.default"])
        if "access_token" not in res:
            raise RuntimeError(f"Không lấy được token: {res.get('error_description', res)}")
        return res["access_token"]

    def request(self, method: str, url: str, **kw) -> dict:
        if not url.startswith("http"):
            url = GRAPH + url
        headers = {"Authorization": f"Bearer {self._token()}", "Accept": "application/json",
                   # cho phép lọc trên cột chưa đánh index
                   "Prefer": "HonorNonIndexedQueriesWarningMayFailRandomly"}
        for attempt in range(5):
            r = self._session.request(method, url, headers=headers, timeout=60, **kw)
            if r.status_code in (429, 503, 504):  # bị giới hạn tốc độ -> chờ rồi thử lại
                time.sleep(int(r.headers.get("Retry-After", 2 ** attempt)))
                continue
            if not r.ok:
                raise RuntimeError(f"Graph {method} {url} -> {r.status_code}: {r.text[:500]}")
            return r.json() if r.content else {}
        raise RuntimeError(f"Graph {method} {url}: quá số lần thử lại")

    # ------------------------------------------------------------------ site / list
    @property
    def site_id(self) -> str:
        if self._site_id is None:
            u = urlparse(self._site_url)
            self._site_id = self.request("GET", f"/sites/{u.hostname}:{u.path or '/'}")["id"]
        return self._site_id

    def list_id(self, list_name: str) -> str:
        with self._lock:
            if list_name not in self._list_ids:
                real = config.list_name(list_name)
                if re.fullmatch(r"\{?[0-9a-fA-F-]{36}\}?", real):
                    self._list_ids[list_name] = real.strip("{}")
                    return self._list_ids[list_name]
                data = self.request("GET", f"/sites/{self.site_id}/lists?$select=id,name,displayName")
                for l in data.get("value", []):
                    if real in (l.get("name"), l.get("displayName")):
                        self._list_ids[list_name] = l["id"]
                        break
                else:
                    raise RuntimeError(f"Không tìm thấy list '{real}' trên site {self._site_url}. "
                                       "Chạy: python scripts/setup_sharepoint.py")
            return self._list_ids[list_name]

    def _items_url(self, list_name: str) -> str:
        return f"/sites/{self.site_id}/lists/{self.list_id(list_name)}/items"

    # ------------------------------------------------------------------ cột
    def columns(self, list_name: str) -> list[dict]:
        data = self.request("GET", f"/sites/{self.site_id}/lists/{self.list_id(list_name)}/columns")
        out = []
        for c in data.get("value", []):
            if c.get("readOnly") or c.get("hidden"):
                continue
            kind = next((k for k in ("text", "choice", "dateTime", "number", "currency",
                                     "boolean", "lookup", "personOrGroup") if k in c), "text")
            out.append({"name": c["name"], "title": c.get("displayName", c["name"]), "type": kind})
        return out

    def colmap(self, list_name: str) -> convert.ColumnMap:
        if list_name not in self._maps:
            self._maps[list_name] = convert.ColumnMap(list_name, self.columns(list_name))
        return self._maps[list_name]

    def _from(self, list_name: str, it: dict) -> dict:
        return self.colmap(list_name).from_sp(it.get("fields", {}), it["id"],
                                              it.get("createdDateTime"),
                                              it.get("lastModifiedDateTime"))

    def list_exists(self, list_name: str) -> bool:
        try:
            self.list_id(list_name)
            return True
        except RuntimeError:
            return False

    def create_list(self, list_name: str, description: str = ""):
        self.request("POST", f"/sites/{self.site_id}/lists", json={
            "displayName": config.list_name(list_name), "description": description,
            "list": {"template": "genericList"}})

    def add_column(self, list_name: str, f: Field, internal: str):
        from ..schema import BOOL, CHOICE, DATE, NOTE, NUMBER

        col = {"name": internal, "displayName": f.sp_title}
        if f.type == DATE:
            col["dateTime"] = {"format": "dateOnly"}
        elif f.type == NUMBER:
            col["number"] = {}
        elif f.type == BOOL:
            col["boolean"] = {}
        elif f.type == NOTE:
            col["text"] = {"allowMultipleLines": True}
        elif f.type == CHOICE and isinstance(f.options, tuple):
            col["choice"] = {"allowTextEntry": True, "choices": list(f.options)}
        else:
            col["text"] = {}
        self.request("POST", f"/sites/{self.site_id}/lists/{self.list_id(list_name)}/columns",
                     json=col)
        self._maps.pop(list_name, None)

    # ------------------------------------------------------------------ CRUD
    def list_items(self, list_name):
        url = self._items_url(list_name) + "?expand=fields&$top=999"
        out = []
        while url:
            data = self.request("GET", url)
            out.extend(self._from(list_name, it) for it in data.get("value", []))
            url = data.get("@odata.nextLink")
        return out

    def get_item(self, list_name, item_id):
        try:
            it = self.request("GET", f"{self._items_url(list_name)}/{item_id}?expand=fields")
        except RuntimeError as e:
            if "404" in str(e):
                return None
            raise
        return self._from(list_name, it)

    def create_item(self, list_name, data):
        body = {k: v for k, v in self.colmap(list_name).to_sp(data).items() if v is not None}
        it = self.request("POST", self._items_url(list_name), json={"fields": body})
        return self._from(list_name, it)

    def update_item(self, list_name, item_id, data):
        self.request("PATCH", f"{self._items_url(list_name)}/{item_id}/fields",
                     json=self.colmap(list_name).to_sp(data))
        return self.get_item(list_name, item_id)

    def delete_item(self, list_name, item_id):
        self.request("DELETE", f"{self._items_url(list_name)}/{item_id}")
