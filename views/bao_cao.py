"""Báo cáo thống kê tuyển sinh."""
import altair as alt
import pandas as pd
import streamlit as st

from tuyensinh import ui
from tuyensinh.schema import KHOI, TRANG_THAI, TUYEN_SINH

nam_hoc = ui.nam_hoc()
ts_all = ui.df(TUYEN_SINH, nam_hoc)
actions = ui.page_header("Báo cáo", f"Thống kê tuyển sinh · năm học {nam_hoc}")
export_slot = actions.container(width="content")

if ts_all.empty:
    with ui.section():
        ui.empty_state("monitoring", "Chưa có dữ liệu để báo cáo",
                       f"Năm học {nam_hoc} chưa có liên hệ nào.")
    st.stop()

STATUS_SCALE = alt.Scale(domain=list(TRANG_THAI), range=[ui.STATUS[s]["hex"] for s in TRANG_THAI])
AXIS = {"labelFontSize": 12, "titleFontSize": 12, "titleFontWeight": 500}


def chart(c: alt.Chart, height: int = 280) -> alt.Chart:
    return (c.properties(height=height).configure_axis(**AXIS).configure_view(strokeWidth=0)
            .configure_legend(orient="top", title=None, labelFontSize=12, symbolType="circle"))


# ------------------------------------------------------------------ bộ lọc
d = pd.to_datetime(ts_all["NgayLienHe"])
f1, f2 = st.columns([1.2, 3], vertical_alignment="bottom")
rng = f1.date_input("Ngày liên hệ", value=(d.min().date(), d.max().date()), format="DD/MM/YYYY",
                    key="bc_rng")
khois = [k for k in KHOI if k in set(ts_all["Khoi"])]
sel_khoi = f2.pills("Khối (bỏ trống = tất cả)", khois, selection_mode="multi", key="bc_khoi")
ts = ts_all
if isinstance(rng, tuple) and len(rng) == 2:
    ts = ts[(d.dt.date >= rng[0]) & (d.dt.date <= rng[1])]
if sel_khoi:
    ts = ts[ts["Khoi"].isin(sel_khoi)]

if ts.empty:
    with ui.section():
        ui.empty_state("filter_alt_off", "Không có dữ liệu trong bộ lọc",
                       "Mở rộng khoảng ngày hoặc bỏ chọn khối.")
    st.stop()

# ------------------------------------------------------------------ KPI
counts = ts["TrangThai"].value_counts()
total, nhap = len(ts), int(counts.get("Nhập học", 0))
nop = nhap + int(counts.get("Nộp hồ sơ", 0))
k = ui.kpi_row(4)
ui.kpi(k[0], "Liên hệ", total)
ui.kpi(k[1], "Nộp hồ sơ", nop, f"{nop / total:.0%} số liên hệ")
ui.kpi(k[2], "Nhập học", nhap, f"{nhap / nop:.0%} số hồ sơ" if nop else None)
ui.kpi(k[3], "Rút hồ sơ", int(counts.get("Rút hồ sơ", 0)))

# ------------------------------------------------------------------ theo khối
pv = pd.crosstab(ts["Khoi"], ts["TrangThai"]).reindex(columns=list(TRANG_THAI), fill_value=0)
pv = pv.reindex([k for k in KHOI if k in pv.index])
pv["Tổng"] = pv.sum(axis=1)
pv["Tỷ lệ nhập học"] = (pv["Nhập học"] / pv["Tổng"]).fillna(0)
pv.index.name = "Khối"

g1, g2 = st.columns([3, 2], gap="medium")
with g1, ui.section("Học sinh theo khối và bước"):
    long = ts.groupby(["Khoi", "TrangThai"]).size().reset_index(name="Số HS")
    long["thứ tự"] = long["TrangThai"].map({s: i for i, s in enumerate(TRANG_THAI)})
    st.altair_chart(chart(alt.Chart(long).mark_bar(stroke="white", strokeWidth=1.5).encode(
        x=alt.X("Khoi:N", title="Khối", sort=list(KHOI), axis=alt.Axis(labelAngle=0)),
        y=alt.Y("Số HS:Q", title="Số học sinh"),
        color=alt.Color("TrangThai:N", scale=STATUS_SCALE, sort=list(TRANG_THAI)),
        order=alt.Order("thứ tự:Q"),
        tooltip=[alt.Tooltip("Khoi:N", title="Khối"), alt.Tooltip("TrangThai:N", title="Bước"),
                 "Số HS:Q"])), width="stretch")
with g2, ui.section("Tỷ lệ nhập học theo khối"):
    st.dataframe(pv.reset_index()[["Khối", "Tổng", "Nhập học", "Tỷ lệ nhập học"]].assign(
                     **{"Tỷ lệ nhập học": (pv["Tỷ lệ nhập học"].values * 100).round()}),
                 hide_index=True, width="stretch",
                 column_config={"Tỷ lệ nhập học": st.column_config.ProgressColumn(
                     format="%d%%", min_value=0, max_value=100)})

# ------------------------------------------------------------------ nguồn + thời gian
n1, n2 = st.columns(2, gap="medium")
src = ts.assign(Nguon=ts["Nguon"].replace("", "Chưa rõ")).groupby("Nguon").agg(
    **{"Liên hệ": ("id", "count"),
       "Nhập học": ("TrangThai", lambda s: int((s == "Nhập học").sum()))}).reset_index()
src["Tỷ lệ"] = src["Nhập học"] / src["Liên hệ"]
with n1, ui.section("Nguồn tuyển sinh", "Số liên hệ và số nhập học theo nguồn"):
    src_long = src.melt(["Nguon", "Tỷ lệ"], ["Liên hệ", "Nhập học"], var_name="Chỉ số",
                        value_name="Số HS")
    st.altair_chart(chart(alt.Chart(src_long).mark_bar(cornerRadiusEnd=3, height=10).encode(
        y=alt.Y("Nguon:N", title=None, sort=alt.EncodingSortField("Số HS", "sum", "descending")),
        x=alt.X("Số HS:Q", title="Số học sinh"),
        yOffset=alt.YOffset("Chỉ số:N", sort=["Liên hệ", "Nhập học"]),
        color=alt.Color("Chỉ số:N", scale=alt.Scale(
            domain=["Liên hệ", "Nhập học"], range=[ui.STATUS["Tư vấn"]["hex"],
                                                   ui.STATUS["Nhập học"]["hex"]])),
        tooltip=[alt.Tooltip("Nguon:N", title="Nguồn"), "Chỉ số:N", "Số HS:Q",
                 alt.Tooltip("Tỷ lệ:Q", title="Tỷ lệ nhập học", format=".0%")]),
        height=max(220, 34 * len(src))), width="stretch")

with n2, ui.section("Liên hệ mới theo tuần"):
    wk = ts.assign(Tuan=pd.to_datetime(ts["NgayLienHe"]).dt.to_period("W").dt.start_time)
    wk = wk.groupby("Tuan").size().reset_index(name="Số liên hệ")
    line = alt.Chart(wk).encode(
        x=alt.X("Tuan:T", title=None, axis=alt.Axis(format="%d/%m", labelAngle=0)),
        y=alt.Y("Số liên hệ:Q", title="Số liên hệ"),
        tooltip=[alt.Tooltip("Tuan:T", title="Tuần bắt đầu", format="%d/%m/%Y"), "Số liên hệ:Q"])
    st.altair_chart(chart(line.mark_line(strokeWidth=2, color=ui.STATUS["Tư vấn"]["hex"])
                          + line.mark_point(size=40, filled=True,
                                            color=ui.STATUS["Tư vấn"]["hex"]),
                          height=max(220, 34 * len(src))), width="stretch")

# ------------------------------------------------------------------ chế độ
cd = ts[ts["TrangThai"] == "Nhập học"]
with ui.section("Chế độ của học sinh nhập học"):
    if cd.empty:
        ui.empty_state("hotel", "Chưa có học sinh nhập học")
    else:
        st.dataframe(pd.crosstab(cd["Khoi"].replace("", "Chưa rõ"),
                                 cd["CheDo"].replace("", "Chưa rõ"), margins=True,
                                 margins_name="Tổng")
                     .rename_axis(index="Khối", columns=None).reset_index(),
                     hide_index=True, width="stretch")

ui.download_excel("Tải báo cáo Excel", {
    "Khoi_Buoc": pv.reset_index(),
    "Nguon": src.rename(columns={"Nguon": "Nguồn"}),
    "Data_TuyenSinh": ts.drop(columns=["Created", "Modified"]),
}, f"BaoCaoTuyenSinh_{nam_hoc}.xlsx", container=export_slot, primary=True, key="bc_export")
