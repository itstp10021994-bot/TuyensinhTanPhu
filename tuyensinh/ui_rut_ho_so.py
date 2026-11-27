"""Lưu trữ rút hồ sơ (list LuuTru_RutHoSo): xem, lọc, tải Excel danh sách học sinh đã rút và lý do.

Mỗi lần rút hồ sơ (Data tuyển sinh hoặc Hồ sơ nhập học) app tự ghi một dòng; hồ sơ đã rút từ
trước khi có lưu trữ được bổ sung bằng nút "Bổ sung hồ sơ đã rút" (lấy lý do từ ghi chú).
"""
from __future__ import annotations

import pandas as pd
import streamlit as st

from . import config, services, ui
from .schema import NHAP_HOC, RUT_HO_SO, TUYEN_SINH

_COT = {"NgayRut": "Ngày rút", "HoTen": "Họ tên", "NgaySinh": "Ngày sinh", "Khoi": "Khối",
        "LopHoc": "Lớp", "SDT": "SĐT", "CheDo": "Chế độ", "Buoc": "Rút ở bước",
        "LyDo": "Lý do", "NguoiThucHien": "Người thực hiện", "NamHoc": "Năm học"}


def _ngay(v) -> str:
    d = pd.to_datetime(v, errors="coerce")
    return "" if pd.isna(d) else f"{d:%d/%m/%Y}"


def bang(items: list[dict]) -> pd.DataFrame:
    """Bảng hiển thị / xuất Excel, mới nhất lên đầu."""
    if not items:
        return pd.DataFrame(columns=list(_COT.values()))
    df = pd.DataFrame(items).reindex(columns=[*_COT, "id"])
    df["_d"] = pd.to_datetime(df["NgayRut"], errors="coerce")
    df = df.sort_values(["_d", "id"], ascending=False, na_position="last")
    df["NgayRut"] = df["NgayRut"].map(_ngay)
    df["NgaySinh"] = df["NgaySinh"].map(_ngay)
    return df[list(_COT)].fillna("").rename(columns=_COT).reset_index(drop=True)


def _bo_sung(storage, thieu: list[dict]) -> int:
    for d in thieu:
        services.ghi_rut_ho_so(storage, d)
    return len(thieu)


def render(storage, key: str = "rut"):
    items = ui.records(RUT_HO_SO, optional=True)
    err = ui.list_error(RUT_HO_SO)
    if err and "does not exist" not in err and "404" not in err:
        st.error("Không đọc được list lưu trữ rút hồ sơ (lỗi kết nối). Bấm ⟳ trên thanh menu để "
                 "thử lại.", icon=":material/cloud_off:")
        return
    if err:
        st.info(f"List **{config.list_name(RUT_HO_SO.name)}** sẽ được tạo tự động trên SharePoint "
                "ở lần rút hồ sơ đầu tiên (hoặc khi bấm “Bổ sung hồ sơ đã rút”).",
                icon=":material/info:")
        items = []

    thieu = services.rut_chua_luu_tru(ui.records(TUYEN_SINH), ui.records(NHAP_HOC), items)
    if thieu:
        c1, c2 = st.columns([3, 1.3], vertical_alignment="center")
        c1.warning(f"**{len(thieu)} hồ sơ** đã rút từ trước chưa có trong lưu trữ. Bấm bổ sung để "
                   "ghi lại (lý do lấy từ ghi chú của hồ sơ).", icon=":material/history:")
        if c2.button("Bổ sung hồ sơ đã rút", icon=":material/playlist_add:", type="primary",
                     width="stretch", key=f"{key}_bs"):
            n = ui.mutate(_bo_sung, storage, thieu, success=f"Đã bổ sung {len(thieu)} hồ sơ")
            if n is not None:
                ui.refresh()
                st.rerun()

    df = bang(items)
    nams = sorted({str(x) for x in df["Năm học"] if x}, reverse=True)
    c1, c2 = st.columns([1, 2], vertical_alignment="bottom")
    nam = c1.selectbox("Năm học", ["Tất cả", *nams], key=f"{key}_nam")
    tim = c2.text_input("Tìm", placeholder="Họ tên, lớp, lý do, SĐT…", key=f"{key}_tim",
                        label_visibility="collapsed").strip().lower()
    if nam != "Tất cả":
        df = df[df["Năm học"] == nam]
    if tim:
        df = df[df.astype(str).apply(lambda r: tim in " ".join(r).lower(), axis=1)]

    k = ui.kpi_row(3, key=f"{key}_kpis")
    ui.kpi(k[0], "Hồ sơ đã rút", len(df))
    ui.kpi(k[1], "Rút sau nhập học", int((df["Rút ở bước"] == "Sau nhập học").sum()))
    ui.kpi(k[2], "Có ghi lý do", int((df["Lý do"].astype(str).str.strip() != "").sum()))

    if df.empty:
        ui.empty_state("folder_off", "Chưa có hồ sơ rút",
                       "Mỗi lần rút hồ sơ, học sinh và lý do được lưu vào đây.")
        return
    st.dataframe(df, hide_index=True, width="stretch", height=min(38 + 35 * len(df), 460),
                 column_config={"Lý do": st.column_config.TextColumn(width="large")})
    ui.download_excel(f"Tải danh sách ({len(df)})", df, "LuuTru_RutHoSo.xlsx", key=f"{key}_xls")
