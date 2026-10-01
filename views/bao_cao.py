"""Báo cáo: 24 mẫu báo cáo (tuyển sinh, tài chính, nhập học) — xem biểu đồ, bảng, xuất Excel.

Tính toán nằm ở tuyensinh/reports.py; trang này chỉ chọn mẫu, lọc, vẽ và xuất file.
"""
from datetime import date

import altair as alt
import pandas as pd
import streamlit as st

from tuyensinh import reports, ui
from tuyensinh.schema import KHOI, NHAP_HOC, TRANG_THAI, TUYEN_SINH

S = st.session_state
nam_hoc = ui.nam_hoc()
SCHOOL = "Trường TH, THCS và THPT Tân Phú"

# Bảng màu phân loại (thứ tự cố định, đã kiểm tra mù màu) — bước tuyển sinh dùng màu trạng thái
CAT = ["#2a78d6", "#eb6834", "#1baf7a", "#eda100", "#e87ba4", "#008300", "#4a3aa7", "#e34948"]
ONE = CAT[0]
STATUS_SCALE = alt.Scale(domain=list(TRANG_THAI), range=[ui.STATUS[s]["hex"] for s in TRANG_THAI])
AXIS = {"labelFontSize": 12, "titleFontSize": 12, "titleFontWeight": 500, "gridOpacity": .35,
        "domainOpacity": .4, "tickOpacity": .4}
MONEY_WORDS = ("tiền", "thanh toán", "còn lại", "đã thu")

ts_all = ui.df(TUYEN_SINH)
nh_year = ui.df(NHAP_HOC, nam_hoc)
ts_year = ts_all[ts_all["NamHoc"] == nam_hoc].reset_index(drop=True)


# ------------------------------------------------------------------ biểu đồ
def _cfg(c: alt.Chart, height: int) -> alt.Chart:
    return (c.properties(height=height).configure_axis(**AXIS).configure_view(strokeWidth=0)
            .configure_legend(orient="top", title=None, labelFontSize=12, symbolType="circle"))


def draw(spec: dict):
    data = spec["data"]
    if data is None or len(data) == 0:
        return
    kind, x, y = spec["kind"], spec["x"], spec["y"]
    color = spec.get("color")
    horiz = spec.get("horizontal") or kind == "hbar"
    yfmt = ",.0f"
    tip = [alt.Tooltip(f"{x}:N", title=x)] + ([alt.Tooltip(f"{color}:N", title=color)]
                                                if color else []) + \
        [alt.Tooltip(f"{y}:Q", title=y, format=yfmt)]
    n = data[x].nunique()
    if kind == "line":
        fmt = "%m/%Y" if spec.get("fmt") == "%m/%Y" else "%d/%m"
        base = alt.Chart(data).encode(
            x=alt.X(f"{x}:T", title=None, axis=alt.Axis(format=fmt, labelAngle=0)),
            y=alt.Y(f"{y}:Q", title=None),
            color=alt.Color(f"{color}:N", scale=alt.Scale(range=[CAT[0], CAT[2]])),
            tooltip=[alt.Tooltip(f"{x}:T", title="Kỳ", format=spec.get("fmt", "%d/%m/%Y")),
                     alt.Tooltip(f"{color}:N", title="Chỉ số"), alt.Tooltip(f"{y}:Q", title="Số HS")])
        c = base.mark_line(strokeWidth=2) + base.mark_point(size=60, filled=True, stroke="white",
                                                            strokeWidth=1.5)
        st.altair_chart(_cfg(c, 300), width="stretch")
        return
    if kind == "line_cat":  # trục danh mục có thứ tự (tháng trong chu kỳ) × nhiều năm
        doms = list(dict.fromkeys(data[color]))
        base = alt.Chart(data).encode(
            x=alt.X(f"{x}:N", title=None, sort=list(dict.fromkeys(data[x])),
                    axis=alt.Axis(labelAngle=0 if n <= 14 else -40)),
            y=alt.Y(f"{y}:Q", title=None, axis=alt.Axis(format="d")),
            color=alt.Color(f"{color}:N", scale=alt.Scale(domain=doms, range=CAT[:len(doms)])),
            tooltip=tip)
        c = base.mark_line(strokeWidth=2) + base.mark_point(size=60, filled=True, stroke="white",
                                                            strokeWidth=1.5)
        st.altair_chart(_cfg(c, 320), width="stretch")
        return
    cat_axis = alt.Axis(labelLimit=260, labelAngle=0) if horiz else \
        alt.Axis(labelAngle=0 if n <= 12 else -40, labelLimit=140)
    # thanh ngang: xếp giảm dần; cột đứng: giữ thứ tự của bảng (khối, lớp, năm học…)
    sort = alt.EncodingSortField(y, "sum", "descending") if horiz else list(
        dict.fromkeys(data[x]))
    cat = alt.Y(f"{x}:N", title=None, sort=sort, axis=cat_axis) if horiz else \
        alt.X(f"{x}:N", title=None, sort=sort, axis=cat_axis)
    money = spec.get("money")
    vax = alt.Axis(labelExpr="format(datum.value / 1e6, ',.0f') + ' tr'") if money else \
        alt.Axis(format="d")
    val = alt.X(f"{y}:Q", title=None, axis=vax) if horiz else alt.Y(f"{y}:Q", title=None, axis=vax)
    if money:  # nhãn "89,8 tr" (triệu đồng)
        data = data.assign(_lbl=[f"{v / 1e6:,.1f} tr".replace(",", "#").replace(".", ",")
                                 .replace("#", ".") for v in data[y]])
    enc = {"x": val, "y": cat} if horiz else {"x": cat, "y": val}
    mark = alt.Chart(data).mark_bar(cornerRadiusEnd=4, stroke="white", strokeWidth=2,
                                    **({"height": {"band": .7}} if horiz else
                                       {"width": {"band": .7}}))
    if kind == "stack":
        enc["color"] = alt.Color(f"{color}:N", scale=STATUS_SCALE, sort=list(TRANG_THAI))
        enc["order"] = alt.Order("_o:Q")
        data = data.assign(_o=data[color].map({s: i for i, s in enumerate(TRANG_THAI)}))
        mark = alt.Chart(data).mark_bar(stroke="white", strokeWidth=2)
    elif kind in ("stack_cat", "group"):
        doms = list(dict.fromkeys(data[color]))
        enc["color"] = alt.Color(f"{color}:N", scale=alt.Scale(
            domain=doms, range=[CAT[0], CAT[2]] if kind == "group" and len(doms) == 2
            else CAT[:len(doms)]))
        if kind == "group":
            if horiz:
                enc["yOffset"] = alt.YOffset(f"{color}:N")
            else:
                enc["xOffset"] = alt.XOffset(f"{color}:N")
        else:
            mark = alt.Chart(data).mark_bar(stroke="white", strokeWidth=2)
    else:
        mark = mark.encode(color=alt.value(ONE))
    h = max(240, min(700, 30 * n * (2 if kind == "group" else 1))) if horiz else 300
    labels = None
    if kind in ("hbar", "bar") and n <= 25:  # nhãn giá trị ở đầu thanh
        labels = alt.Chart(data).mark_text(
            align="left" if horiz else "center", baseline="middle" if horiz else "bottom",
            dx=4 if horiz else 0, dy=0 if horiz else -4, fontSize=11, color="#64748B").encode(
            **({"x": val, "y": cat} if horiz else {"x": cat, "y": val}),
            text=alt.Text("_lbl:N") if money else alt.Text(f"{y}:Q", format=",.0f"))
    c = mark.encode(**enc, tooltip=tip)
    st.altair_chart(_cfg(c + labels if labels is not None else c, h), width="stretch")


def fmt_kpi(label: str, v) -> str:
    if isinstance(v, (int, float)) and not isinstance(v, bool):
        if any(w in label.lower() for w in MONEY_WORDS):
            return ui.money(v)
        return f"{v:,.0f}".replace(",", ".") if float(v).is_integer() else f"{v:,.1f}"
    return str(v)


def table(df: pd.DataFrame):
    cfg = {}
    for c in df.columns:
        if "(đ)" in c:
            cfg[c] = st.column_config.NumberColumn(format="localized")
        elif "(%)" in c:
            cfg[c] = st.column_config.ProgressColumn(format="%.1f%%", min_value=0, max_value=100)
        elif df[c].dtype == object and len(df) and isinstance(df[c].dropna().iloc[0]
                                                             if df[c].notna().any() else None,
                                                             date):
            cfg[c] = st.column_config.DateColumn(format="DD/MM/YYYY")
    st.dataframe(df, hide_index=True, width="stretch", column_config=cfg,
                 height=min(560, 38 + 35 * max(len(df), 1)))


# ------------------------------------------------------------------ trang
actions = ui.page_header("Báo cáo", f"{len(reports.REPORTS)} mẫu báo cáo · năm học {nam_hoc}")
all_slot = actions.container(width="content")

nav, main = st.columns([1, 3.3], gap="medium")
with nav:
    groups = list(dict.fromkeys(r.group for r in reports.REPORTS))
    grp = st.selectbox("Nhóm báo cáo", groups, key="bc_grp", label_visibility="collapsed")
    in_grp = [r for r in reports.REPORTS if r.group == grp]
    if S.get("bc_rep") not in [r.id for r in in_grp]:
        S["bc_rep"] = in_grp[0].id
    with st.container(border=True):
        rid = st.radio("Mẫu báo cáo", [r.id for r in in_grp], key="bc_rep",
                       format_func=lambda i: reports.BY_ID[i].title,
                       label_visibility="collapsed")

rep = reports.BY_ID[rid]
with main:
    # ---- bộ lọc chung + tham số của mẫu
    f = st.columns([1.3, 2.4, 1.1], vertical_alignment="bottom", gap="small")
    d = pd.to_datetime(ts_year["NgayLienHe"], errors="coerce")
    rng = None
    if rep.group == reports.G_TS and d.notna().any():
        rng = f[0].date_input("Ngày liên hệ", value=(d.min().date(), d.max().date()),
                              format="DD/MM/YYYY", key="bc_rng")
    khois = [k for k in KHOI if k in set(ts_year["Khoi"]) | set(nh_year["Khoi"])]
    sel_khoi = f[1].pills("Khối", khois, selection_mode="multi", key="bc_khoi",
                          help="Bỏ trống = tất cả khối")
    params = {}
    if "nam" in rep.params:
        co_dl = sorted(y for y in ts_all["NamHoc"].dropna().unique() if str(y).strip())
        mac_dinh = [y for y in co_dl if y <= nam_hoc][-3:] or co_dl[-3:]
        params["nam"] = st.multiselect("Năm học so sánh", co_dl, default=mac_dinh,
                                       key="bc_nam", placeholder="Chọn 2–3 năm học",
                                       help="Mặc định 3 năm học gần nhất (tính đến năm đang chọn)")
    if "ky" in rep.params:
        params["ky"] = f[2].segmented_control("Kỳ", ["Tháng", "Tuần"], default="Tháng",
                                              required=True, key="bc_ky")
    if "top" in rep.params:
        params["top"] = f[2].number_input("Số trường", 5, 200, 30, 5, key="bc_top")
    if "ngay" in rep.params:
        params["ngay"] = f[2].number_input("Quá số ngày", 1, 365, 14, key="bc_ngay")

    ts = ts_year
    if rng and isinstance(rng, tuple) and len(rng) == 2:
        ts = ts[(d.dt.date >= rng[0]) & (d.dt.date <= rng[1])]
    nh = nh_year
    if sel_khoi:
        ts, nh = ts[ts["Khoi"].isin(sel_khoi)], nh[nh["Khoi"].isin(sel_khoi)]
    params["khoi"] = sel_khoi
    ctx = reports.Ctx(ts.reset_index(drop=True), nh.reset_index(drop=True), ts_all, nam_hoc,
                      params)

    # ---- nội dung báo cáo
    with st.container(border=True):
        h1, h2 = st.columns([3, 1.2], vertical_alignment="center")
        h1.markdown(f"#### {rep.title}")
        h1.caption(rep.desc + (f" · Khối {', '.join(sel_khoi)}" if sel_khoi else ""))
        try:
            res = rep.fn(ctx)
        except Exception as e:  # dữ liệu bất thường: báo lỗi của riêng mẫu này
            ui.error_state(e, compact=True)
            st.stop()
        items = reports.export_items(rep, res)
        h2.download_button("Tải báo cáo (Excel)", lambda: reports.excel(items, SCHOOL, nam_hoc),
                           file_name=f"{rep.id}_{nam_hoc}.xlsx", mime=ui.XLSX,
                           icon=":material/download:", on_click="ignore", width="stretch",
                           type="primary")
        if res.kpis:
            cols = st.columns(len(res.kpis))
            for col, (label, v) in zip(cols, res.kpis):
                ui.kpi(col, label, fmt_kpi(label, v))
        if res.table.empty:
            ui.empty_state("inbox", "Không có dữ liệu", "Không có học sinh phù hợp với bộ lọc.")
        else:
            if res.chart:
                draw(res.chart)
            table(res.table)
        if res.note:
            st.caption(f":material/info: {res.note}")


def _all_reports() -> bytes:
    items = []
    for r in reports.REPORTS:
        if r.id == "nh_danhsach":  # danh sách lớp xuất riêng (nhiều sheet)
            continue
        try:
            items += reports.export_items(r, r.fn(ctx))
        except Exception:
            continue
    return reports.excel(items, SCHOOL, nam_hoc)


all_slot.download_button("Tải tất cả báo cáo", _all_reports,
                         file_name=f"BaoCao_TongHop_{nam_hoc}_{date.today():%Y%m%d}.xlsx",
                         mime=ui.XLSX, icon=":material/folder_zip:", on_click="ignore",
                         help="Một file Excel, mỗi báo cáo một sheet (theo bộ lọc hiện tại)")
