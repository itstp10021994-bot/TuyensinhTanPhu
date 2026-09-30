"""Danh mục dùng chung (tỉnh, xã, dân tộc, tôn giáo, ...) lấy từ biểu mẫu VEMIS."""
from __future__ import annotations

import json
from functools import lru_cache
from pathlib import Path

from .schema import Field

_PATH = Path(__file__).parent / "data" / "danh_muc.json"


@lru_cache(maxsize=1)
def load() -> dict:
    return json.loads(_PATH.read_text(encoding="utf-8"))


def options_for(f: Field, record: dict | None = None) -> list[str]:
    """Trả về danh sách lựa chọn cho trường `f`.

    "@ten" lấy danh mục trong danh_muc.json; "@xa:TruongTinh" lấy danh sách xã
    theo tỉnh đang chọn ở trường TruongTinh của `record`.
    """
    opts = f.options
    if isinstance(opts, tuple):
        return list(opts)
    name = opts.lstrip("@")
    if name == "nam_hoc":
        from . import config

        return config.school_years()
    if name.startswith("xa:"):
        tinh = (record or {}).get(name[3:]) or ""
        return list(load()["xa_theo_tinh"].get(tinh, []))
    return list(load()[name])
