"""Báo cáo: các mẫu báo cáo (tuyển sinh, tài chính, nhập học, xu hướng) — biểu đồ, bảng, Excel.

Tính toán nằm ở tuyensinh/reports.py; trang này chỉ chọn mẫu, lọc, vẽ và xuất file.
"""
from datetime import date

import pandas as pd
import streamlit as st

from tuyensinh import bieu_do as BD
from tuyensinh import dia_ban, reports, ui
from tuyensinh.schema import KHOI, NHAP_HOC, TUYEN_SINH

S = st.session_state
nam_hoc = ui.nam_hoc()
SCHOOL = "Trường TH, THCS và THPT Tân Phú"

MONEY_WORDS = ("tiền", "thanh toán", "còn lại", "đã thu")

ts_all = ui.df(TUYEN_SINH)
nh_all = ui.df(NHAP_HOC)
nh_year = ui.df(NHAP_HOC, nam_hoc)
ts_year = ts_all[ts_all["NamHoc"] == nam_hoc].reset_index(drop=True)


# ------------------------------------------------------------------ biểu đồ
def draw(spec: dict, height: int | None = None):
    """Biểu đồ của mẫu báo cáo — kiểu chung ở tuyensinh/bieu_do.py."""
    BD.ve(spec, height=height, key=f"bc_chart_{rid}")


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


def mot_bao_cao(rep, ctx, sel_khoi):
    """Một mẫu báo cáo: chỉ số, biểu đồ, bảng, tải Excel."""
    with st.container(border=True, key="bc_noi_dung"):
        h1, h2 = st.columns([3, 1.2], vertical_alignment="center")
        h1.markdown(f"#### {rep.title}")
        h1.caption(rep.desc + (f" · Khối {', '.join(sel_khoi)}" if sel_khoi else ""))
        try:
            res = rep.fn(ctx)
        except Exception as e:  # dữ liệu bất thường: báo lỗi của riêng mẫu này
            ui.error_state(e, compact=True)
            return
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
        elif res.chart:  # màn hình rộng: biểu đồ và bảng cạnh nhau
            ngang = res.chart.get("kind") in ("hbar",) or res.chart.get("horizontal")
            n = res.chart["data"][res.chart["x"]].nunique()
            if n > 14 or len(res.table.columns) > 7:  # biểu đồ dài / bảng nhiều cột: xếp dọc
                draw(res.chart, height=None if ngang else 270)
                table(res.table)
            else:
                g1, g2 = st.columns([1.35, 1], gap="medium")
                with g1:
                    draw(res.chart, height=max(300, 30 * n + 40) if ngang else 340)
                with g2:
                    table(res.table)
        else:
            table(res.table)
        if res.note:
            st.caption(f":material/info: {res.note}")


# ------------------------------------------------------------------ trang tổng hợp nhóm
DASH = "__tong_hop__"
MAC_DINH = {"cap": dia_ban.CAP[1], "tinh": "Tất cả", "loai": "Tất cả", "ky": "Tháng",
            "top": 10, "ngay": 14}


def _gon(spec: dict) -> dict:
    """Biểu đồ trong thẻ tổng hợp: thanh ngang nhiều mục chỉ giữ 8 mục lớn nhất."""
    data, x, y = spec["data"], spec["x"], spec["y"]
    ngang = spec["kind"] == "hbar" or spec.get("horizontal")
    if ngang and data[x].nunique() > 8:
        top = data.groupby(x)[y].sum().nlargest(8).index
        data = data[data[x].isin(top)]
    return {**spec, "data": data}


def _mo(rid_: str):
    S["bc_rep"] = rid_


def dashboard(ds: list, ctx, sel_khoi):
    """Mọi mẫu báo cáo của nhóm trên một trang: lưới thẻ (chỉ số + biểu đồ), bấm Chi tiết để mở."""
    for i, r in enumerate(ds):
        if i % 2 == 0:  # mỗi hàng 2 thẻ, thẳng hàng
            cot = st.columns(2, gap="small")
        p = {**MAC_DINH, **ctx.params, "moc": date.today()}
        if r.id == "xh_cungky" and len(p.get("nam") or []) > 2:
            p["nam"] = p["nam"][-2:]
        c = reports.Ctx(ctx.ts, ctx.nh, ctx.ts_all, ctx.nam_hoc, p, nh_all=ctx.nh_all)
        with cot[i % 2], st.container(key=f"tp_card_bc_{r.id}"):
            h = st.container(horizontal=True, vertical_alignment="center", wrap=False)
            h.markdown(f"#### {r.title}", width="stretch")
            h.button("", key=f"bc_mo_{r.id}", on_click=_mo, args=(r.id,), help="Mở chi tiết",
                     icon=":material/open_in_full:", type="tertiary")
            try:
                res = r.fn(c)
            except Exception as e:
                ui.error_state(e, compact=True)
                continue
            if res.kpis:
                st.html('<div class="bc-kpi">' + "".join(
                    f'<span><em>{lbl}</em><b>{fmt_kpi(lbl, v)}</b></span>'
                    for lbl, v in res.kpis[:4]) + "</div>")
            if res.table.empty:
                st.caption("Không có dữ liệu phù hợp bộ lọc.")
            elif res.chart and len(res.chart.get("data", [])):
                g = _gon(res.chart)
                ngang = g["kind"] == "hbar" or g.get("horizontal")
                so = g["data"][g["x"]].nunique() * (
                    g["data"][g["color"]].nunique() if g["kind"] == "group" else 1)
                BD.ve(g, height=min(340, max(230, 18 * so + 50)) if ngang else 230, gon=True,
                      key=f"bc_dash_{r.id}")
            else:
                st.dataframe(res.table.head(8), hide_index=True, width="stretch",
                             height=min(38 + 35 * min(len(res.table), 8), 320))


# ------------------------------------------------------------------ trang
actions = ui.page_header("Báo cáo", f"{len(reports.REPORTS)} mẫu báo cáo · năm học {nam_hoc}")
all_slot = actions.container(width="content")

nav, main = st.columns([1, 3.3], gap="medium")
with nav:
    groups = list(dict.fromkeys(r.group for r in reports.REPORTS))
    grp = st.selectbox("Nhóm báo cáo", groups, key="bc_grp", label_visibility="collapsed")
    in_grp = [r for r in reports.REPORTS if r.group == grp]
    if S.get("bc_rep") not in [DASH] + [r.id for r in in_grp]:
        S["bc_rep"] = DASH  # vào nhóm: mở trang tổng hợp trước
    with st.container(border=True):
        rid = st.radio("Mẫu báo cáo", [DASH] + [r.id for r in in_grp], key="bc_rep",
                       format_func=lambda i: "▦  Tổng hợp nhóm (dashboard)" if i == DASH
                       else reports.BY_ID[i].title,
                       label_visibility="collapsed")

# trang tổng hợp: một "mẫu" giả, bộ lọc chung của nhóm (khối, ngày, năm học so sánh)
rep = reports.Report(DASH, grp, f"Tổng hợp: {grp}", f"Tất cả {len(in_grp)} mẫu báo cáo của "
                     "nhóm trên một trang — bấm Chi tiết để mở từng mẫu.", None,
                     ("nam",) if any("nam" in r.params for r in in_grp) else ()) \
    if rid == DASH else reports.BY_ID[rid]
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
        nguon = [ts_all, nh_all] if rep.group == reports.G_XNH else [ts_all]
        co_dl = sorted({str(y) for d in nguon for y in d["NamHoc"].dropna().unique()
                        if str(y).strip()})
        so = 2 if rep.id == "xh_cungky" else 3  # cùng kỳ: mặc định năm này và năm trước
        mac_dinh = [y for y in co_dl if y <= nam_hoc][-so:] or co_dl[-so:]
        params["nam"] = st.multiselect("Năm học so sánh", co_dl, default=mac_dinh,
                                       key="bc_nam_ck" if so == 2 else "bc_nam",
                                       placeholder="Chọn 2–3 năm học",
                                       help=f"Mặc định {so} năm học gần nhất (tính đến năm đang "
                                            "chọn)")
    loc = [k for k in ("cap", "tinh", "loai") if k in rep.params]
    if loc:
        g = st.columns([2.2, 1.6, 1.6][:len(loc)], vertical_alignment="bottom", gap="small")
        o = dict(zip(loc, g))
        if "cap" in o:
            params["cap"] = o["cap"].segmented_control(
                "Chi tiết theo", list(dia_ban.CAP), default=dia_ban.CAP[1], required=True,
                key="bc_cap", help="Quận/huyện là địa giới CŨ (trước sáp nhập 2025), suy ra từ "
                                   "địa chỉ cũ hoặc phường/xã mới.")
        if "tinh" in o:
            nh_dia = rep.group in (reports.G_NH, reports.G_XNH)
            ds = (dia_ban.dia_ban_nh(nh_all) if nh_dia else dia_ban.dia_ban_ts(ts_all))[
                dia_ban.CAP[0]].value_counts()
            ds = [t for t in ds.index if t != dia_ban.CHUA_RO]
            params["tinh"] = o["tinh"].selectbox("Tỉnh/Thành", ["Tất cả", *ds], key="bc_tinh")
        if "loai" in o:
            params["loai"] = o["loai"].segmented_control(
                "Học sinh", ["Tất cả", "HS mới", "HS cũ học tiếp"], default="Tất cả",
                required=True, key="bc_loai",
                help="HS mới = qua tuyển sinh; HS cũ = học sinh của trường lên lớp")
    if "moc" in rep.params:
        params["moc"] = f[2].date_input(
            "Tính đến ngày", value=date.today(), format="DD/MM/YYYY", key="bc_moc",
            help=f"Mốc của năm học {nam_hoc}; các năm khác lấy cùng ngày/tháng tương ứng "
                 "(lùi đúng số năm).")
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
                      params, nh_all=nh_all)

    if rid == DASH:
        dashboard(in_grp, ctx, sel_khoi)
    else:
        mot_bao_cao(rep, ctx, sel_khoi)


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
