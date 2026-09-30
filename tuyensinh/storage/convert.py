"""Chuyển đổi dữ liệu app <-> cột SharePoint (dùng chung cho Graph và Power Automate).

List có sẵn trên SharePoint thường có tên nội bộ bị mã hóa (vd "Ng_x00e0_y_x0020_li_x00ea_n...")
nên app tự tìm cột theo **tên hiển thị** (`Field.sp_title`). Có thể ghi đè bằng
[field_map.<TenList>] trong secrets.toml.
"""
from __future__ import annotations

import unicodedata
from datetime import datetime
from zoneinfo import ZoneInfo

from .. import config
from ..schema import ALL_LISTS, BOOL, DATE, NUMBER, ListDef

# Kiểu cột SharePoint (REST TypeAsString / Graph) -> kiểu dùng khi đọc/ghi
SP_DATE, SP_NUMBER, SP_BOOL, SP_TEXT, SP_PERSON = "date", "number", "bool", "text", "person"
_TYPE = {"DateTime": SP_DATE, "Number": SP_NUMBER, "Currency": SP_NUMBER, "Boolean": SP_BOOL,
         "User": SP_PERSON, "UserMulti": SP_PERSON, "Lookup": SP_PERSON, "LookupMulti": SP_PERSON,
         "dateTime": SP_DATE, "number": SP_NUMBER, "currency": SP_NUMBER, "boolean": SP_BOOL,
         "personOrGroup": SP_PERSON, "lookup": SP_PERSON}


def schema_for(list_name: str) -> ListDef | None:
    for ld in ALL_LISTS:
        if ld.name == list_name:
            return ld
    return None


def _norm(s: str) -> str:
    return unicodedata.normalize("NFC", str(s)).strip().lower()


def date_out(v) -> str:
    # 12:00 UTC = 19:00 giờ VN: không bị lệch ngày khi SharePoint đổi múi giờ
    return f"{str(v)[:10]}T12:00:00Z"


def date_in(v) -> str:
    """"2026-08-05T17:00:00Z" (0h ngày 6/8 giờ VN, do Power Apps lưu) -> "2026-08-06"."""
    s = str(v)
    if len(s) <= 10 or not (s.endswith("Z") or "+" in s[10:]):
        return s[:10]
    dt = datetime.fromisoformat(s.replace("Z", "+00:00"))
    return dt.astimezone(ZoneInfo(config.timezone())).date().isoformat()


def _num_text(v) -> str:
    try:
        return f"{float(v):g}"
    except (TypeError, ValueError):
        return str(v)


class ColumnMap:
    """Ánh xạ key trong app <-> tên nội bộ cột của một list.

    `columns`: [{"name": tên nội bộ, "title": tên hiển thị, "type": kiểu}] lấy từ SharePoint;
    None khi chưa biết (dùng luôn key làm tên cột).
    """

    def __init__(self, list_name: str, columns: list[dict] | None = None):
        self.list_name = list_name
        self.ld = schema_for(list_name)
        self.known = columns is not None
        self.internal: dict[str, str] = {}
        self.sp_type: dict[str, str] = {}
        self.missing: list[str] = []
        fmap = config.field_map(list_name)
        by_title = {_norm(c["title"]): c for c in columns or []}
        by_name = {c["name"]: c for c in columns or []}
        for f in (self.ld.fields if self.ld else ()):
            col = None
            if f.key in fmap:
                col = by_name.get(fmap[f.key]) or {"name": fmap[f.key], "type": ""}
            elif columns is not None:
                col = by_name.get(f.key) or by_title.get(_norm(f.sp_title))
            else:
                col = {"name": f.key, "type": ""}
            if col is None:
                self.missing.append(f.key)
                continue
            self.internal[f.key] = col["name"]
            self.sp_type[f.key] = _TYPE.get(col.get("type", ""), SP_TEXT if columns else "")
        self.key_of = {v: k for k, v in self.internal.items()}
        if columns is not None:
            titles = {c["name"] for c in columns}
            self.has_title = "Title" in titles
        else:
            self.has_title = True

    @property
    def person_columns(self) -> list[str]:
        return [self.internal[k] for k, t in self.sp_type.items() if t == SP_PERSON]

    def to_sp(self, data: dict) -> dict:
        types = {f.key: f.type for f in self.ld.fields} if self.ld else {}
        out = {}
        for k, v in data.items():
            if k not in self.internal:
                continue  # trường hệ thống hoặc cột không có trên list
            spt = self.sp_type.get(k) or {DATE: SP_DATE, NUMBER: SP_NUMBER,
                                          BOOL: SP_BOOL}.get(types.get(k), SP_TEXT)
            if spt == SP_PERSON:
                continue  # cột Người (Person) chỉ đọc trong app
            if v == "" or v is None:
                v = None
            elif spt == SP_DATE:
                v = date_out(v)
            elif spt == SP_NUMBER:
                v = float(v)
            elif spt == SP_BOOL:
                v = bool(v) if not isinstance(v, str) else _norm(v) in ("x", "true", "1", "có")
            elif types.get(k) == NUMBER:
                v = _num_text(v)
            elif types.get(k) == BOOL:
                v = "x" if v else ""
            else:
                v = str(v)
            out[self.internal[k]] = v
        if self.has_title and "Title" not in out and self.ld is not None:
            for key in ("HoTenHS", "HoTen"):
                if data.get(key):
                    out["Title"] = str(data[key])
                    break
        return out

    def from_sp(self, fields: dict, item_id, created=None, modified=None) -> dict:
        types = {f.key: f.type for f in self.ld.fields} if self.ld else {}
        out = {"id": str(item_id), "Created": created or fields.get("Created"),
               "Modified": modified or fields.get("Modified")}
        for key, name in self.internal.items():
            if name not in fields:
                continue
            v = fields[name]
            if isinstance(v, dict):  # cột Người/Lookup đã $expand
                v = v.get("Title") or v.get("LookupValue") or ""
            elif isinstance(v, list):
                v = ", ".join(str(x.get("Title", x) if isinstance(x, dict) else x) for x in v)
            if v is None:
                v = ""
            elif types.get(key) == DATE and isinstance(v, str) and v:
                v = date_in(v)
            elif types.get(key) == NUMBER and isinstance(v, str):
                try:
                    v = float(v.replace(",", "."))
                except ValueError:
                    v = ""
            elif types.get(key) == BOOL and isinstance(v, str):
                v = _norm(v) in ("x", "true", "1", "có")
            out[key] = v
        return out
