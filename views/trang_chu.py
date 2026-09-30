"""Tổng quan: chỉ số chính, phễu tuyển sinh, việc cần xử lý, liên hệ gần đây."""
from datetime import date, timedelta

import altair as alt
import pandas as pd
import streamlit as st

from tuyensinh import services, ui
from tuyensinh.schema import NHAP_HOC, TRANG_THAI, TUYEN_SINH


nam_hoc = ui.nam_hoc()
ts = ui.df(TUYEN_SINH, nam_hoc)
nh = ui.df(NHAP_HOC, nam_hoc)

actions = ui.page_header("Tổng quan", f"Năm học {nam_hoc} · cập nhật lúc "
                         f"{ui.ago(ui.loaded_at())}")
actions.button("Làm mới", icon=":material/refresh:", on_click=ui.refresh)
if actions.button("Thêm liên hệ", icon=":material/person_add:", type="primary"):
    st.switch_page("views/data_tuyen_sinh.py", query_params={"new": "1"})

if ts.empty:
    with ui.section():
        ui.empty_state("person_search", f"Chưa có liên hệ nào trong năm học {nam_hoc}",
                       "Bắt đầu bằng việc thêm liên hệ đầu tiên, hoặc chọn năm học khác ở thanh bên.")
        _, c, _ = st.columns([2, 1, 2])
        if c.button("Thêm liên hệ đầu tiên", type="primary", width="stretch"):
            st.switch_page("views/data_tuyen_sinh.py", query_params={"new": "1"})
    st.stop()

# ------------------------------------------------------------------ KPI
counts = ts["TrangThai"].value_counts()
total = len(ts)
nop = int(counts.get("Nộp hồ sơ", 0)) + int(counts.get("Nhập học", 0))
nhap = int(counts.get("Nhập học", 0))
week_ago = date.today() - timedelta(days=7)
new_week = int((pd.to_datetime(ts["NgayLienHe"]).dt.date >= week_ago).sum())
giu = ts[ts["TinhTrang"] == "Đã giữ chỗ"]

k = ui.kpi_row(5)
ui.kpi(k[0], "Liên hệ", total, f"+{new_week} trong 7 ngày" if new_week else "Không có mới trong 7 ngày")
ui.kpi(k[1], "Đã nộp hồ sơ", nop, f"{nop / total:.0%} số liên hệ",
       help="Gồm cả học sinh đã nhập học")
ui.kpi(k[2], "Nhập học", nhap, f"{nhap / nop:.0%} số hồ sơ" if nop else None)
ui.kpi(k[3], "Tỷ lệ nhập học", f"{nhap / total:.0%}", "trên tổng số liên hệ")
ui.kpi(k[4], "Đã giữ chỗ", len(giu), ui.money(giu["SoTienXacNhan"].fillna(0).sum()))

# ------------------------------------------------------------------ phễu + việc cần làm
left, right = st.columns([3, 2], gap="medium")
with left, ui.section("Phễu tuyển sinh", "Số học sinh đang ở từng bước"):
    funnel = pd.DataFrame({"Bước": list(TRANG_THAI),
                           "Số HS": [int(counts.get(s, 0)) for s in TRANG_THAI]})
    funnel["Tỷ lệ"] = funnel["Số HS"] / total
    funnel["Nhãn"] = funnel.apply(lambda r: f"{r['Số HS']}  ·  {r['Tỷ lệ']:.0%}", axis=1)
    base = alt.Chart(funnel).encode(
        y=alt.Y("Bước:N", sort=list(TRANG_THAI), title=None,
                axis=alt.Axis(labelFontSize=13, labelPadding=8, ticks=False, domain=False)),
        x=alt.X("Số HS:Q", title=None, axis=None,
                scale=alt.Scale(domain=[0, max(funnel["Số HS"].max(), 1) * 1.25])),
        tooltip=["Bước:N", "Số HS:Q", alt.Tooltip("Tỷ lệ:Q", format=".0%")])
    bars = base.mark_bar(cornerRadiusEnd=4, height=26).encode(
        color=alt.Color("Bước:N", legend=None, scale=alt.Scale(
            domain=list(TRANG_THAI), range=[ui.STATUS[s]["hex"] for s in TRANG_THAI])))
    text = base.mark_text(align="left", dx=6, fontSize=12, color="#8B95A5").encode(text="Nhãn:N")
    st.altair_chart((bars + text).properties(height=190), width="stretch")

with right, ui.section("Cần xử lý", "Việc đang chờ trong năm học này"):
    nop_chua_giu = ts[(ts["TrangThai"].isin(["Nộp hồ sơ", "Nhập học"]))
                      & (ts["TinhTrang"].isin(["", "Chưa giữ chỗ"]))]
    rut = set(ts.loc[ts["TrangThai"] == "Rút hồ sơ", "id"])
    nh_live = nh[~nh["TuyenSinhID"].isin(rut)]
    thieu = int((services.completeness(nh_live) < 1).sum()) if len(nh_live) else 0
    hoan_phi = int((ts["TinhTrang"] == "Hủy giữ chỗ").sum())
    cu = pd.to_datetime(ts["NgayLienHe"]).dt.date < date.today() - timedelta(days=14)
    tu_van_cu = int(((ts["TrangThai"] == "Tư vấn") & cu).sum())
    todo = [
        (len(nop_chua_giu), "HS đã nộp hồ sơ nhưng chưa giữ chỗ", "views/ke_toan.py",
         ":material/payments:"),
        (thieu, "Hồ sơ nhập học còn thiếu thông tin", "views/ho_so_nhap_hoc.py",
         ":material/assignment_late:"),
        (hoan_phi, "Hủy giữ chỗ đang chờ hoàn phí", "views/ke_toan.py", ":material/undo:"),
        (tu_van_cu, "Liên hệ tư vấn quá 14 ngày chưa chuyển bước", "views/data_tuyen_sinh.py",
         ":material/schedule:"),
    ]
    pending = [t for t in todo if t[0]]
    if not pending:
        ui.empty_state("task_alt", "Không có việc tồn đọng", "Mọi hồ sơ đều đã được xử lý.")
    for n, label, page, icon in pending:
        with st.container(horizontal=True, vertical_alignment="center", gap="small"):
            st.page_link(page, label=label, icon=icon, width="stretch")
            st.badge(str(n), color="orange")

# ------------------------------------------------------------------ gần đây
with ui.section():
    h1, h2 = st.columns([3, 1], vertical_alignment="center")
    h1.markdown("#### Liên hệ gần đây")
    with h2.container(horizontal=True, horizontal_alignment="right"):
        st.page_link("views/data_tuyen_sinh.py", label="Xem tất cả",
                     icon=":material/arrow_forward:", icon_position="right")
    recent = ts.sort_values(["NgayLienHe", "id"], ascending=False).head(8).copy()
    recent["Bước"] = ui.tag_col(recent["TrangThai"])
    ev = st.dataframe(
        recent[["HoTenHS", "Khoi", "Bước", "SDT", "NgayLienHe", "Nguon"]],
        hide_index=True, width="stretch", on_select="rerun", selection_mode="single-row",
        key="home_recent",
        column_config={"HoTenHS": st.column_config.TextColumn("Học sinh", width="medium"),
                       "Khoi": st.column_config.TextColumn("Khối", width="small"),
                       "Bước": ui.status_column(), "SDT": "SĐT", "Nguon": "Nguồn",
                       "NgayLienHe": st.column_config.DateColumn("Ngày liên hệ", **ui.DATE_COL)})
    if ev.selection.rows:
        st.switch_page("views/data_tuyen_sinh.py",
                       query_params={"id": recent.iloc[ev.selection.rows[0]]["id"]})
    st.caption("Chọn một dòng để mở hồ sơ học sinh.")
