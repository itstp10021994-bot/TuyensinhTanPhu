"""Báo cáo: các mẫu báo cáo (tuyển sinh, tài chính, nhập học, xu hướng) — biểu đồ, bảng, Excel.

Tính toán nằm ở tuyensinh/reports.py; trang này chỉ chọn mẫu, lọc, vẽ và xuất file.
"""
from datetime import date
from html import escape

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


# Dashboard của từng nhóm: ô chỉ số (mẫu báo cáo, thứ tự chỉ số) và các biểu đồ chọn lọc
DASH_CFG = {
    reports.G_TS: {
        "kpi": [("ts_khoi", 0), ("ts_khoi", 1), ("ts_khoi", 2), ("ts_rut", 0), ("ts_chedo", 1),
                ("ts_quahan", 0)],
        "panels": ["ts_khoi", "ts_thoigian", "ts_nguon", "ts_chedo", "ts_truongcu", "ts_tuvan"]},
    reports.G_KT: {
        "kpi": [("kt_giucho", 0), ("kt_giucho", 1), ("kt_hocphi", 0), ("kt_hocphi", 1),
                ("kt_hocphi", 2), ("kt_hoanphi", 1)],
        "panels": ["kt_giucho", "kt_hocphi", "kt_congno", "kt_hoanphi"]},
    reports.G_NH: {
        "kpi": [("nh_siso", 0), ("nh_siso", 1), ("nh_siso", 2), ("nh_tinhtrang", 2),
                ("nh_hoanthien", 0), ("nh_giayto", 0)],
        "panels": ["nh_siso", "nh_tinhtrang", "nh_hoanthien", "nh_giayto", "nh_diaban",
                   "nh_tohop"]},
    reports.G_XH: {
        "kpi": [("xh_tongquan", 1), ("xh_tongquan", 2), ("xh_tongquan", 3), ("xh_cungky", -1)],
        "panels": ["xh_tongquan", "xh_thang", "xh_khoi", "xh_nguon", "xh_cungky",
                   "xh_truongcu"]},
    reports.G_XNH: {
        "kpi": [("xnh_tongquan", 0), ("xnh_tongquan", 1), ("xnh_tongquan", 2),
                ("xnh_tongquan", 3), ("xnh_doichieu", 2)],
        "panels": ["xnh_tongquan", "xnh_khoi", "xnh_chedo", "xnh_doichieu", "xnh_diaban",
                   "xnh_truongcu"]},
}
H_O = 150  # chiều cao biểu đồ trong ô: dải chỉ số + 2 hàng ô vừa một màn hình
H_TC = 300  # trình chiếu: vừa màn hình 1920×1080 (16:9) khi bấm F11
# Trình chiếu: ẩn menu trái, thanh trên, bộ lọc, ô chọn mẫu; nội dung dùng hết bề ngang
TRINH_CHIEU_CSS = """<style>
section[data-testid="stSidebar"], [data-testid="stSidebarCollapsedControl"],
header[data-testid="stHeader"], .st-key-tp_toolbar, .st-key-tp_ai, .st-key-bc_loc,
.st-key-tp_page_head,
.st-key-bc_rep {display: none !important;}
.block-container {padding: .9rem 1.6rem 1rem !important; max-width: none !important;}
.bi-o b {font-size: 2.1rem;} .bi-o em {font-size: .86rem;} .bi-o {padding: .75rem 1.1rem .8rem;}
[class*="st-key-tp_card_bc_"] h4 {font-size: 1.05rem;}
[class*="st-key-tp_card_bc_"] {padding: .75rem 1rem .6rem;}
</style>"""


def _gon(spec: dict) -> dict:
    """Biểu đồ trong ô dashboard: thanh ngang giữ 6 mục lớn nhất; cột theo lớp gộp về khối."""
    data, x, y = spec["data"], spec["x"], spec["y"]
    ngang = spec["kind"] == "hbar" or spec.get("horizontal")
    if ngang and data[x].nunique() > 6:
        top = data.groupby(x)[y].sum().nlargest(6).index
        data = data[data[x].isin(top)]
    elif not ngang and spec["kind"] == "bar" and data[x].nunique() > 16:
        khoi = data[x].astype(str).str.extract(r"^(\d+)")[0]
        if khoi.notna().mean() > .8:  # cột theo lớp (6.1, 10A1…) -> theo khối
            data = (data.assign(_k=khoi.fillna("?")).groupby("_k", sort=False)[y].sum()
                    .reset_index())
            data["_n"] = pd.to_numeric(data["_k"], errors="coerce")
            data = data.sort_values("_n").assign(**{x: lambda d: "Khối " + d["_k"]})
            data = data[[x, y]]
    return {**spec, "data": data}


def _mo(rid_: str):
    S["bc_rep"] = rid_


def _o_chi_so(ds: list[tuple[str, object]]):
    """Dải ô số liệu lớn kiểu bảng điều khiển; ô tỷ lệ (%) có thanh đo bên dưới."""
    o = []
    for lbl, v in ds:
        gt = fmt_kpi(lbl, v)
        if isinstance(v, (int, float)) and any(w in lbl.lower() for w in MONEY_WORDS) \
                and abs(v) >= 1e6:  # tiền: gọn "62,0 tr" cho vừa ô
            gt = f"{v / 1e6:,.1f} tr".replace(",", "#").replace(".", ",").replace("#", ".")
        do = ""
        try:
            pct = float(str(v).rstrip("%").replace(",", ".")) if "tỷ lệ" in lbl.lower() \
                else None
        except ValueError:
            pct = None
        if pct is not None and 0 <= pct <= 100:
            do = f'<i class="do"><i style="width:{pct:.0f}%"></i></i>'
        o.append(f'<div class="bi-o"><em>{escape(lbl)}</em><b>{escape(gt)}</b>{do}</div>')
    st.html(f'<div class="bi-dai" style="--n:{len(o)}">{"".join(o)}</div>')


def dashboard(ds: list, ctx, sel_khoi, lon: bool = False):
    """Dashboard của nhóm: dải chỉ số + 4–6 biểu đồ chọn lọc (lưới 3×2), vừa một màn hình."""
    cfg = DASH_CFG.get(ds[0].group) if ds else None
    if not cfg:
        return
    p = {**MAC_DINH, **ctx.params, "moc": date.today()}
    kq = {}

    def chay(rid_):
        if rid_ not in kq:
            pp = dict(p)
            if rid_ == "xh_cungky" and len(pp.get("nam") or []) > 2:
                pp["nam"] = pp["nam"][-2:]
            c = reports.Ctx(ctx.ts, ctx.nh, ctx.ts_all, ctx.nam_hoc, pp, nh_all=ctx.nh_all)
            try:
                kq[rid_] = reports.BY_ID[rid_].fn(c)
            except Exception as e:  # một ô lỗi không làm hỏng cả dashboard
                kq[rid_] = e
        return kq[rid_]

    chi_so = []
    for rid_, i in cfg["kpi"]:
        res = chay(rid_)
        if not isinstance(res, Exception) and res.kpis and -len(res.kpis) <= i < len(res.kpis):
            chi_so.append(res.kpis[i])
    if chi_so:
        _o_chi_so(chi_so)
    cao = H_TC if lon else H_O
    panels = cfg["panels"]
    so_cot = 2 if len(panels) <= 4 else 3
    for i, rid_ in enumerate(panels):
        if i % so_cot == 0:
            cot = st.columns(so_cot, gap="small")
        r = reports.BY_ID[rid_]
        with cot[i % so_cot], st.container(key=f"tp_card_bc_{rid_}"):
            h = st.container(horizontal=True, vertical_alignment="center", wrap=False, gap=None)
            h.markdown(f"#### {r.title}", width="stretch")
            h.button("", key=f"bc_mo_{rid_}", on_click=_mo, args=(rid_,), help="Mở chi tiết",
                     icon=":material/open_in_full:", type="tertiary")
            res = chay(rid_)
            if isinstance(res, Exception):
                ui.error_state(res, compact=True)
            elif res.table.empty:
                st.html(f'<div class="bc-trong" style="height:{cao}px">Không có dữ liệu</div>')
            elif res.chart and len(res.chart.get("data", [])):
                BD.ve(_gon(res.chart), height=cao, gon=not lon, key=f"bc_dash_{rid_}")
            else:  # mẫu chỉ có bảng: vài dòng đầu
                st.dataframe(res.table.head(6), hide_index=True, width="stretch",
                             height=cao + 24)


# ------------------------------------------------------------------ trang
_hanh_dong = ui.page_header("Báo cáo", eyebrow="Phân tích")  # gọn: dashboard vừa một màn hình

# chọn nhóm (thanh ngang) + mẫu báo cáo (ô chọn) + bộ lọc chung — cùng một hàng
groups = list(dict.fromkeys(r.group for r in reports.REPORTS))
if S.get("bc_grp") not in groups:
    S["bc_grp"] = groups[0]
tc = bool(S.get("bc_tc")) and S.get("bc_rep", DASH) == DASH  # chế độ trình chiếu 16:9
if tc:
    st.html(TRINH_CHIEU_CSS)
    st.html(f'<div class="bi-banner"><b>BÁO CÁO {escape(str(S.get("bc_grp", "")).upper())}</b>'
            f'<span>Trường TH, THCS và THPT Tân Phú · Năm học {nam_hoc} · cập nhật '
            f'{date.today():%d/%m/%Y}</span></div>')
r1, r2 = st.columns([3, 1.4], vertical_alignment="bottom", gap="small")
# nút tải tất cả + trình chiếu: ở tiêu đề trang (khi trình chiếu tiêu đề ẩn -> đưa xuống hàng chọn)
all_slot = (r2.container(horizontal=True, gap="small", horizontal_alignment="right") if tc
            else _hanh_dong)
grp = r1.segmented_control("Nhóm báo cáo", groups, key="bc_grp", required=True,
                           label_visibility="collapsed")
in_grp = [r for r in reports.REPORTS if r.group == grp]
if S.get("bc_rep") not in [DASH] + [r.id for r in in_grp]:
    S["bc_rep"] = DASH  # vào nhóm: mở trang tổng hợp trước
rid = r2.selectbox("Mẫu báo cáo", [DASH] + [r.id for r in in_grp], key="bc_rep",
                   format_func=lambda i: "▦  Dashboard" if i == DASH
                   else reports.BY_ID[i].title, label_visibility="collapsed")

# trang tổng hợp: một "mẫu" giả, bộ lọc chung của nhóm (khối, ngày, năm học so sánh)
rep = reports.Report(DASH, grp, f"Tổng hợp: {grp}", "", None,
                     ("nam",) if any("nam" in r.params for r in in_grp) else ()) \
    if rid == DASH else reports.BY_ID[rid]
loc = st.container(key="bc_loc")  # bộ lọc (ẩn khi trình chiếu, vẫn giữ giá trị)
noi = st.container()
with loc:
    # ---- bộ lọc chung + tham số của mẫu
    f = st.columns([1.2, 2.2, 1.6], vertical_alignment="bottom", gap="small")
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
        params["nam"] = f[2].multiselect("Năm học so sánh", co_dl, default=mac_dinh,
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
    f2 = st.columns([1.2, 2.2, 1.6], vertical_alignment="bottom", gap="small")[2] \
        if "nam" in rep.params else f[2]
    if "moc" in rep.params:
        params["moc"] = f2.date_input(
            "Tính đến ngày", value=date.today(), format="DD/MM/YYYY", key="bc_moc",
            help=f"Mốc của năm học {nam_hoc}; các năm khác lấy cùng ngày/tháng tương ứng "
                 "(lùi đúng số năm).")
    if "ky" in rep.params:
        params["ky"] = f2.segmented_control("Kỳ", ["Tháng", "Tuần"], default="Tháng",
                                              required=True, key="bc_ky")
    if "top" in rep.params:
        params["top"] = f2.number_input("Số trường", 5, 200, 30, 5, key="bc_top")
    if "ngay" in rep.params:
        params["ngay"] = f2.number_input("Quá số ngày", 1, 365, 14, key="bc_ngay")

    ts = ts_year
    if rng and isinstance(rng, tuple) and len(rng) == 2:
        ts = ts[(d.dt.date >= rng[0]) & (d.dt.date <= rng[1])]
    nh = nh_year
    if sel_khoi:
        ts, nh = ts[ts["Khoi"].isin(sel_khoi)], nh[nh["Khoi"].isin(sel_khoi)]
    params["khoi"] = sel_khoi
    ctx = reports.Ctx(ts.reset_index(drop=True), nh.reset_index(drop=True), ts_all, nam_hoc,
                      params, nh_all=nh_all)

    with noi:
        if rid == DASH:
            dashboard(in_grp, ctx, sel_khoi, lon=tc)
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


all_slot.download_button("Tải tất cả", _all_reports, icon=":material/folder_zip:",
                         file_name=f"BaoCao_TongHop_{nam_hoc}_{date.today():%Y%m%d}.xlsx",
                         mime=ui.XLSX, on_click="ignore",
                         help="Tải tất cả báo cáo: một file Excel, mỗi báo cáo một sheet (theo "
                              "bộ lọc hiện tại)")
if rid == DASH:
    all_slot.button("Thoát" if tc else "Trình chiếu", key="bc_tc_nut",
                    icon=":material/close_fullscreen:" if tc else ":material/fit_screen:",
                    type="primary" if not tc else "secondary",
                    on_click=lambda: S.update(bc_tc=not S.get("bc_tc")),
                    help="Dashboard toàn màn hình 16:9 (ẩn menu và bộ lọc). Bấm F11 để trình chiếu "
                         "toàn màn hình trình duyệt.")
