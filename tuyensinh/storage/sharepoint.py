"""Lưu dữ liệu trên SharePoint Online (List) qua Microsoft Graph API.

Xác thực kiểu ứng dụng (client credentials): cần đăng ký App trên Microsoft Entra ID
với quyền Application `Sites.ReadWrite.All` (hoặc `Sites.Selected` + cấp quyền cho site).
Xem README.md mục "Cấu hình SharePoint".
"""
from __future__ import annotations

import threading
import time
from urllib.parse import urlparse

import msal
import requests

from .. import config
from ..schema import ALL_LISTS, BOOL, DATE, NUMBER, ListDef
from .base import Storage

GRAPH = "https://graph.microsoft.com/v1.0"
# Trường hệ thống, không gửi lên khi ghi
_READONLY = {"id", "Created", "Modified", "Author", "Editor", "ContentType", "Attachments",
             "@odata.etag", "LinkTitle", "LinkTitleNoMenu", "Edit", "ItemChildCount",
             "FolderChildCount", "_UIVersionString", "_ComplianceFlags", "_ComplianceTag",
             "_ComplianceTagWrittenTime", "_ComplianceTagUserId", "AppAuthorLookupId",
             "AppEditorLookupId", "AuthorLookupId", "EditorLookupId"}


def _schema_for(list_name: str) -> ListDef | None:
    for ld in ALL_LISTS:
        if ld.name == list_name:
            return ld
    return None


def to_graph(ld: ListDef | None, data: dict) -> dict:
    """Chuyển dict của ứng dụng sang fields của Graph."""
    out = {}
    types = {f.key: f.type for f in ld.fields} if ld else {}
    for k, v in data.items():
        if k in _READONLY:
            continue
        t = types.get(k)
        if v == "" or v is None:
            out[k] = None
        elif t == DATE:
            # Lưu 12:00 UTC để không bị lệch ngày do múi giờ của site
            out[k] = f"{str(v)[:10]}T12:00:00Z"
        elif t == NUMBER:
            out[k] = float(v)
        elif t == BOOL:
            out[k] = bool(v)
        else:
            out[k] = str(v)
    if ld is not None and "Title" not in out:
        for key in ("HoTenHS", "HoTen"):
            if data.get(key):
                out["Title"] = str(data[key])
                break
    return out


def from_graph(ld: ListDef | None, item: dict) -> dict:
    fields = dict(item.get("fields", {}))
    types = {f.key: f.type for f in ld.fields} if ld else {}
    out = {"id": str(item["id"]), "Created": item.get("createdDateTime"),
           "Modified": item.get("lastModifiedDateTime")}
    for k, v in fields.items():
        if k in _READONLY or k.startswith("@"):
            continue
        if types.get(k) == DATE and isinstance(v, str):
            v = v[:10]
        out[k] = v
    return out


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

    # ------------------------------------------------------------------ CRUD
    def list_items(self, list_name):
        ld = _schema_for(list_name)
        url = self._items_url(list_name) + "?expand=fields&$top=999"
        out = []
        while url:
            data = self.request("GET", url)
            out.extend(from_graph(ld, it) for it in data.get("value", []))
            url = data.get("@odata.nextLink")
        return out

    def get_item(self, list_name, item_id):
        try:
            it = self.request("GET", f"{self._items_url(list_name)}/{item_id}?expand=fields")
        except RuntimeError as e:
            if "404" in str(e):
                return None
            raise
        return from_graph(_schema_for(list_name), it)

    def create_item(self, list_name, data):
        body = {"fields": to_graph(_schema_for(list_name), data)}
        body["fields"] = {k: v for k, v in body["fields"].items() if v is not None}
        it = self.request("POST", self._items_url(list_name), json=body)
        return from_graph(_schema_for(list_name), it)

    def update_item(self, list_name, item_id, data):
        self.request("PATCH", f"{self._items_url(list_name)}/{item_id}/fields",
                     json=to_graph(_schema_for(list_name), data))
        return self.get_item(list_name, item_id)

    def delete_item(self, list_name, item_id):
        self.request("DELETE", f"{self._items_url(list_name)}/{item_id}")
