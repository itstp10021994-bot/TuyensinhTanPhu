"""Thành phần giao diện Streamlit dùng chung."""
from __future__ import annotations

from datetime import date

import pandas as pd
import streamlit as st

from . import config, danh_muc, services
from .schema import BOOL, CHOICE, DATE, NOTE, NUMBER, Field, ListDef
from .storage import Storage, create_storage

CSS = """
<style>
.block-container {padding-top: 3.5rem; padding-bottom: 1rem;}
.ts-header {background:#1f6fd1;color:#fff;padding:.45rem 1rem;border-radius:6px;
  font-weight:700;letter-spacing:.3px;text-align:center;font-size:1.05rem;margin-bottom:.4rem}
.ts-footer {background:#1f6fd1;color:#fff;text-align:center;font-style:italic;
  font-size:.8rem;padding:.3rem;border-radius:6px;margin-top:1.2rem}
.ts-card {border-left:4px solid #1f6fd1;padding:.1rem .6rem;margin:.2rem 0}
div[data-testid="stMetricValue"] {color:#1f6fd1}
</style>
"""


@st.cache_resource
def storage() -> Storage:
    return create_storage()


@st.cache_data(ttl=120, show_spinner="Đang tải dữ liệu…")
def _load(list_name: str, version: int) -> list[dict]:
    return storage().list_items(list_name)


def data_version() -> int:
    return st.session_state.setdefault("_data_v", 0)


def invalidate():
    """Gọi sau mỗi lần ghi để đọc lại dữ liệu mới."""
    st.session_state["_data_v"] = data_version() + 1


def df(ld: ListDef, nam_hoc: str | None = None) -> pd.DataFrame:
    out = services.to_df(ld, _load(ld.name, data_version()))
    if nam_hoc:
        out = out[out["NamHoc"] == nam_hoc]
    return out.reset_index(drop=True)


def nam_hoc() -> str:
    return st.session_state.get("nam_hoc", config.default_year())


def current_user() -> str:
    try:
        if st.user.is_logged_in:
            return st.user.get("name") or st.user.get("email") or ""
    except Exception:
        pass
    return st.session_state.get("nguoi_dung", "")


def header():
    st.markdown(CSS, unsafe_allow_html=True)
    c1, c2 = st.columns([5, 1], vertical_alignment="center")
    c1.markdown('<div class="ts-header">ỨNG DỤNG QUẢN LÝ TUYỂN SINH — '
                'TRƯỜNG TH, THCS & THPT TÂN PHÚ</div>', unsafe_allow_html=True)
    years = config.school_years()
    default = config.default_year()
    c2.selectbox("Năm học", years, index=years.index(default) if default in years else 0,
                 key="nam_hoc", label_visibility="collapsed")


def footer():
    st.markdown('<div class="ts-footer">Ứng dụng được phát triển bởi Trường TH, THCS và THPT '
                'Tân Phú</div>', unsafe_allow_html=True)


def show_errors(e: Exception):
    st.error(str(e))


def _to_date(v) -> date | None:
    if v is None or v is pd.NaT or v == "" or (isinstance(v, float) and pd.isna(v)):
        return None
    if isinstance(v, date):
        return v
    try:
        return pd.to_datetime(v).date()
    except (ValueError, TypeError):
        return None


def field_input(f: Field, record: dict, prefix: str, container=st):
    """Vẽ ô nhập cho trường `f`; giá trị lấy từ `record`. Trả về giá trị mới."""
    key = f"{prefix}_{f.key}"
    label = f.label + (" *" if f.required else "")
    v = record.get(f.key)
    if f.type == DATE:
        return container.date_input(label, value=_to_date(v), key=key, format="DD/MM/YYYY",
                                    min_value=date(1940, 1, 1), max_value=date(2100, 12, 31))
    if f.type == NUMBER:
        empty = v is None or v == "" or (isinstance(v, float) and pd.isna(v))
        money = f.key.startswith("SoTien")
        return container.number_input(label, value=None if empty else float(v), key=key,
                                      min_value=0.0, max_value=None if money else 10.0,
                                      step=100000.0 if money else 0.1,
                                      format="%.0f" if money else "%.1f")
    if f.type == BOOL:
        return container.checkbox(label, value=bool(v), key=key)
    if f.type == NOTE:
        return container.text_area(label, value=str(v or ""), key=key, height=80)
    if f.type == CHOICE:
        # Trường xã phụ thuộc tỉnh: lấy tỉnh đang chọn trên form
        ctx = dict(record)
        if isinstance(f.options, str) and f.options.startswith("@xa:"):
            tinh_key = f.options[4:]
            ctx[tinh_key] = st.session_state.get(f"{prefix}_{tinh_key}", record.get(tinh_key))
        opts = danh_muc.options_for(f, ctx)
        if v and v not in opts:
            opts = [v] + opts
        return container.selectbox(label, opts, index=opts.index(v) if v in opts else None,
                                   key=key, placeholder="Chọn…")
    return container.text_input(label, value=str(v or ""), key=key)


def record_form(fields: list[Field], record: dict, prefix: str, ncols: int = 3) -> dict:
    out = {}
    cols = st.columns(ncols)
    i = 0
    for f in fields:
        if f.type == NOTE:  # ô ghi chú chiếm cả dòng
            out[f.key] = field_input(f, record, prefix)
            cols, i = st.columns(ncols), 0
            continue
        out[f.key] = field_input(f, record, prefix, cols[i % ncols])
        i += 1
    return out


def download_excel(label: str, data: pd.DataFrame, file_name: str, sheet: str = "Data"):
    import io

    buf = io.BytesIO()
    with pd.ExcelWriter(buf, engine="openpyxl") as xw:
        data.to_excel(xw, index=False, sheet_name=sheet)
    st.download_button(label, buf.getvalue(), file_name=file_name, icon=":material/download:",
                       mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")
