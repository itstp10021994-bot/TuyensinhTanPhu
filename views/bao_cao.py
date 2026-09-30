"""Báo cáo thống kê tuyển sinh."""
import io

import altair as alt
import pandas as pd
import streamlit as st

from tuyensinh import ui
from tuyensinh.schema import KHOI, TRANG_THAI, TUYEN_SINH

# Màu cố định theo trạng thái (không đổi khi lọc)
STATUS_COLORS = ["#2a78d6", "#eb6834", "#1baf7a", "#eda100"]

nam_hoc = ui.nam_hoc()
ts = ui.df(TUYEN_SINH, nam_hoc)
if ts.empty:
    st.info(f"Chưa có dữ liệu tuyển sinh năm học {nam_hoc}.")
    st.stop()

c1, c2 = st.columns([1, 3])
d = pd.to_datetime(ts["NgayLienHe"])
rng = c1.date_input("Khoảng ngày liên hệ", value=(d.min().date(), d.max().date()),
                    format="DD/MM/YYYY")
if isinstance(rng, tuple) and len(rng) == 2:
    ts = ts[(d.dt.date >= rng[0]) & (d.dt.date <= rng[1])]

status_scale = alt.Scale(domain=list(TRANG_THAI), range=STATUS_COLORS)

# --- Bảng khối × trạng thái
pv = pd.crosstab(ts["Khoi"], ts["TrangThai"]).reindex(columns=list(TRANG_THAI), fill_value=0)
pv = pv.reindex([k for k in KHOI if k in pv.index])
pv["Tổng"] = pv.sum(axis=1)
pv["Tỷ lệ nhập học"] = (pv["Nhập học"] / pv["Tổng"]).fillna(0)
pv.index.name = "Khối"

st.markdown("##### Số lượng theo khối và trạng thái")
g1, g2 = st.columns([1, 1])
long = ts.groupby(["Khoi", "TrangThai"]).size().reset_index(name="Số HS")
g1.altair_chart(
    alt.Chart(long).mark_bar(cornerRadiusEnd=4, stroke="white", strokeWidth=2).encode(
        x=alt.X("Khoi:N", title="Khối", sort=list(KHOI), axis=alt.Axis(labelAngle=0)),
        y=alt.Y("Số HS:Q", title="Số HS"),
        color=alt.Color("TrangThai:N", title="Bước", scale=status_scale,
                        sort=list(TRANG_THAI), legend=alt.Legend(orient="top")),
        order=alt.Order("TrangThai:N"),
        tooltip=[alt.Tooltip("Khoi:N", title="Khối"), alt.Tooltip("TrangThai:N", title="Bước"),
                 "Số HS:Q"]),
    width="stretch")
g2.dataframe(pv.reset_index(), hide_index=True, width="stretch",
             column_config={"Tỷ lệ nhập học": st.column_config.ProgressColumn(
                 format="percent", min_value=0, max_value=1)})

st.markdown("##### Nguồn tuyển sinh")
n1, n2 = st.columns(2)
src = ts.assign(Nguon=ts["Nguon"].replace("", "Chưa rõ")).groupby("Nguon").agg(
    **{"Liên hệ": ("id", "count"),
       "Nhập học": ("TrangThai", lambda s: int((s == "Nhập học").sum()))}).reset_index()
src_long = src.melt("Nguon", var_name="Chỉ số", value_name="Số HS")
n1.altair_chart(
    alt.Chart(src_long).mark_bar(cornerRadiusEnd=4).encode(
        y=alt.Y("Nguon:N", title=None, sort="-x"),
        x=alt.X("Số HS:Q"),
        yOffset="Chỉ số:N",
        color=alt.Color("Chỉ số:N", title=None, legend=alt.Legend(orient="top"),
                        scale=alt.Scale(domain=["Liên hệ", "Nhập học"],
                                        range=["#2a78d6", "#1baf7a"])),
        tooltip=[alt.Tooltip("Nguon:N", title="Nguồn"), "Chỉ số:N", "Số HS:Q"]),
    width="stretch")

wk = ts.assign(Tuan=pd.to_datetime(ts["NgayLienHe"]).dt.to_period("W").dt.start_time)
wk = wk.groupby("Tuan").size().reset_index(name="Số liên hệ")
n2.altair_chart(
    alt.Chart(wk, title="Số liên hệ mới theo tuần").mark_line(point=True, strokeWidth=2,
                                                              color="#2a78d6").encode(
        x=alt.X("Tuan:T", title="Tuần", axis=alt.Axis(format="%d/%m")),
        y=alt.Y("Số liên hệ:Q"),
        tooltip=[alt.Tooltip("Tuan:T", title="Tuần bắt đầu", format="%d/%m/%Y"),
                 "Số liên hệ:Q"]),
    width="stretch")

st.markdown("##### Chế độ (HS nhập học)")
cd = ts[ts["TrangThai"] == "Nhập học"]
st.dataframe(pd.crosstab(cd["Khoi"], cd["CheDo"], margins=True, margins_name="Tổng")
             .rename_axis(index="Khối", columns=None).reset_index(), hide_index=True)

buf = io.BytesIO()
with pd.ExcelWriter(buf, engine="openpyxl") as xw:
    pv.reset_index().to_excel(xw, sheet_name="Khoi_TrangThai", index=False)
    src.rename(columns={"Nguon": "Nguồn"}).to_excel(xw, sheet_name="Nguon", index=False)
    ts.drop(columns=["Created", "Modified"]).to_excel(xw, sheet_name="Data_TuyenSinh", index=False)
st.download_button("Tải báo cáo Excel", buf.getvalue(), f"BaoCaoTuyenSinh_{nam_hoc}.xlsx",
                   icon=":material/download:", type="primary",
                   mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")
