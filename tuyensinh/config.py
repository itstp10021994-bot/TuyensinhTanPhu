"""Đọc cấu hình từ .streamlit/secrets.toml hoặc biến môi trường.

Biến môi trường được ưu tiên hơn secrets (tiện khi chạy script / Docker).
"""
from __future__ import annotations

import os
from typing import Any


def _secrets() -> dict:
    try:
        import streamlit as st

        return dict(st.secrets)
    except Exception:  # không có secrets.toml hoặc không chạy trong streamlit
        return {}


def get(key: str, default: Any = None) -> Any:
    if key in os.environ:
        return os.environ[key]
    s = _secrets()
    if key in s:
        return s[key]
    sp = s.get("sharepoint") or {}
    short = key.removeprefix("SP_").lower()
    if key.startswith("SP_") and short in sp:
        return sp[short]
    return default


def backend() -> str:
    return str(get("BACKEND", "local")).lower()


def school_years() -> list[str]:
    raw = get("NAM_HOC", "2024-2025,2025-2026,2026-2027,2027-2028")
    if isinstance(raw, (list, tuple)):
        return list(raw)
    return [y.strip() for y in str(raw).split(",") if y.strip()]


def default_year() -> str:
    return str(get("NAM_HOC_MAC_DINH", school_years()[-2]))


def list_name(default: str) -> str:
    """Cho phép đổi tên list, vd SP_LIST_Data_TuyenSinh = "Data_tuyensinh"."""
    return str(get(f"SP_LIST_{default}", default))
