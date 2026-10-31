"""Tổng quan: bảng điều khiển gọn trong một màn hình — chỉ số chính, phễu, xu hướng theo tuần,
nguồn liên hệ, liên hệ theo khối, sĩ số đang học, việc cần xử lý."""
from datetime import date, timedelta
from html import escape

import pandas as pd
import streamlit as st

from tuyensinh import bieu_do as BD
from tuyensinh import services, ui
from tuyensinh.schema import KHOI, NHAP_HOC, TRANG_THAI, TUYEN_SINH

nam_hoc = ui.nam_hoc()
ts = ui.df(TUYEN_SINH, nam_hoc)
nh = ui.df(NHAP_HOC, nam_hoc)
NGHI = ("Rút hồ sơ", "Không học tiếp")
H = 172  # chiều cao biểu đồ: hai hàng biểu đồ + hàng chỉ số vừa một màn hình

actions = ui.page_header("Tổng quan", f"Năm học {nam_hoc} · cập nhật lúc "
                         f"{ui.ago(ui.loaded_at())}")
if ui.co_trang("views/data_tuyen_sinh.py") and \
        actions.button("Thêm liên hệ", icon=":material/person_add:", type="primary"):
    ui.switch_page("views/data_tuyen_sinh.py", query_params={"new": "1"})

if ts.empty and nh.empty:
    with ui.section():
        ui.empty_state("person_search", f"Chưa có dữ liệu năm học {nam_hoc}",
                       "Bắt đầu bằng việc thêm liên hệ đầu tiên, hoặc chọn năm học khác ở thanh trên.")
    st.stop()

# ------------------------------------------------------------------ số liệu
counts = ts["TrangThai"].value_counts()
total = len(ts)
nop = int(counts.get("Nộp hồ sơ", 0)) + int(counts.get("Nhập học", 0))
nhap = int(counts.get("Nhập học", 0))
ngay_lh = pd.to_datetime(ts["NgayLienHe"], errors="coerce")
hom_nay = date.today()
new_week = int((ngay_lh.dt.date >= hom_nay - timedelta(days=7)).sum())
giu = ts[ts["GiuCho"] == "Đã giữ chỗ"]
dang_hoc = nh[~nh["TinhTrangHS"].isin(NGHI)]
hs_moi = int((dang_hoc["TuyenSinhID"].fillna("") != "").sum())
noi_tru = int(dang_hoc["NoiTruBanTru"].fillna("").str.startswith("Nội trú").sum())

# liên hệ theo tuần (12 tuần gần nhất) — dùng cho đường xu hướng và đường nhỏ trong thẻ
tuan = ngay_lh.dt.to_period("W-SUN").dt.start_time
moc = pd.Timestamp(hom_nay - timedelta(days=hom_nay.weekday())) - pd.Timedelta(weeks=11)
cac_tuan = pd.date_range(moc, periods=12, freq="7D")
lh_tuan = tuan[tuan >= moc].value_counts().reindex(cac_tuan, fill_value=0)
nh_tuan = tuan[(tuan >= moc) & (ts["TrangThai"] == "Nhập học")].value_counts().reindex(
    cac_tuan, fill_value=0)


def _pct(a, b):
    return f"{a / b:.0%}" if b else "—"


with st.container(key="tq"):
    # -------------------------------------------------------------- hàng chỉ số
    k = ui.kpi_row(6)
    ui.kpi(k[0], "Liên hệ", total, f"+{new_week} / 7 ngày")
    ui.kpi(k[1], "Đã nộp hồ sơ", nop, f"{_pct(nop, total)} liên hệ",
           help="Gồm cả học sinh đã nhập học")
    ui.kpi(k[2], "Nhập học", nhap, f"{_pct(nhap, total)} liên hệ",
           help=f"{_pct(nhap, nop)} số hồ sơ đã nộp")
    ui.kpi(k[3], "Đã giữ chỗ", len(giu), ui.money(giu["SoTienXacNhan"].fillna(0).sum()))
    ui.kpi(k[4], "Đang học", len(dang_hoc), f"{hs_moi} mới · {len(dang_hoc) - hs_moi} cũ",
           help="Hồ sơ nhập học năm này, không tính rút / không học tiếp")
    ui.kpi(k[5], "Nội trú", noi_tru, f"{_pct(noi_tru, len(dang_hoc))} đang học")

    # -------------------------------------------------------------- hàng 1: phễu · xu hướng · nguồn
    c1, c2, c3 = st.columns([1, 1.25, 1], gap="small")
    with c1, ui.section("Phễu tuyển sinh", "Số học sinh ở từng bước · % trên tổng liên hệ"):
        f = pd.DataFrame({"Bước": list(TRANG_THAI),
                          "Số HS": [int(counts.get(s, 0)) for s in TRANG_THAI]})
        BD.ve({"kind": "hbar", "data": f, "x": "Bước", "y": "Số HS", "giu_thu_tu": True,
               "mau_theo_nhom": True}, height=H, gon=True, key="tq_phieu")
    with c2, ui.section("Xu hướng 12 tuần", "Liên hệ mới mỗi tuần và số em trong đó đã nhập học"):
        xh = pd.concat([
            pd.DataFrame({"Tuần": cac_tuan, "Chỉ số": "Liên hệ mới", "Số HS": lh_tuan.values}),
            pd.DataFrame({"Tuần": cac_tuan, "Chỉ số": "Đã nhập học", "Số HS": nh_tuan.values})])
        BD.ve({"kind": "line", "data": xh, "x": "Tuần", "y": "Số HS",
               "color": "Chỉ số", "fmt": "%d/%m",
               "tipfmt": "tuần %d/%m"}, height=H, gon=True, key="tq_xh")
    with c3, ui.section("Nguồn liên hệ", "6 nguồn nhiều nhất"):
        ng = ts["Nguon"].fillna("").replace("", "Chưa ghi").value_counts()
        ng = pd.concat([ng.head(6), pd.Series({"Khác": ng.iloc[6:].sum()})]) if len(ng) > 7 \
            else ng
        nguon = ng.rename_axis("Nguồn").reset_index(name="Số HS")
        BD.ve({"kind": "hbar", "data": nguon, "x": "Nguồn", "y": "Số HS", "giu_thu_tu": True},
              height=H, gon=True, key="tq_nguon")

    # -------------------------------------------------------------- hàng 2: khối · sĩ số · việc
    d1, d2, d3 = st.columns([1.25, 1.1, .9], gap="small")
    with d1, ui.section("Liên hệ theo khối", "Mỗi khối chia theo bước tuyển sinh"):
        g = ts.assign(Khoi=ts["Khoi"].fillna("").replace("", "?")).groupby(
            ["Khoi", "TrangThai"]).size().reset_index(name="Số HS")
        thu_tu = [k for k in KHOI if k in set(g["Khoi"])] + (["?"] if "?" in set(g["Khoi"])
                                                              else [])
        g["Khoi"] = pd.Categorical(g["Khoi"], thu_tu, ordered=True)
        g = g.sort_values("Khoi").assign(Khối=lambda d: "K" + d["Khoi"].astype(str)).rename(
            columns={"TrangThai": "Bước"})
        BD.ve({"kind": "stack", "data": g, "x": "Khối", "y": "Số HS", "color": "Bước"},
              height=H, gon=True, key="tq_khoi")
    with d2, ui.section("Sĩ số đang học theo khối", "Nội trú / bán trú — hồ sơ nhập học"):
        if dang_hoc.empty:
            ui.empty_state("school", "Chưa có hồ sơ nhập học")
        else:
            che_do = dang_hoc["NoiTruBanTru"].fillna("").map(
                lambda v: "Nội trú" if v.startswith("Nội trú") else
                "Bán trú" if v.startswith("Bán trú") else "Khác / chưa ghi")
            s = dang_hoc.assign(CheDo=che_do, Khoi=dang_hoc["Khoi"].fillna("").replace("", "?"))
            s = s.groupby(["Khoi", "CheDo"]).size().reset_index(name="Số HS")
            thu_tu = [k for k in KHOI if k in set(s["Khoi"])] + (["?"] if "?" in set(s["Khoi"])
                                                                  else [])
            s["Khoi"] = pd.Categorical(s["Khoi"], thu_tu, ordered=True)
            s = s.sort_values(["Khoi", "CheDo"]).assign(
                Khối=lambda d: "K" + d["Khoi"].astype(str)).rename(columns={"CheDo": "Chế độ"})
            BD.ve({"kind": "stack_cat", "data": s, "x": "Khối", "y": "Số HS",
                   "color": "Chế độ"}, height=H, gon=True, key="tq_siso")
    with d3, ui.section("Cần xử lý", "Việc đang chờ trong năm học"):
        nop_chua_giu = ts[(ts["TrangThai"].isin(["Nộp hồ sơ", "Nhập học"]))
                          & (ts["GiuCho"].isin(["", "Chưa giữ chỗ"]))]
        rut = set(ts.loc[ts["TrangThai"] == "Rút hồ sơ", "id"])
        nh_live = nh[~nh["TuyenSinhID"].isin(rut)]
        thieu = int((services.completeness(nh_live) < 1).sum()) if len(nh_live) else 0
        hoan_phi = int((ts["GiuCho"] == "Hủy giữ chỗ").sum())
        cu = ngay_lh.dt.date < hom_nay - timedelta(days=14)
        tu_van_cu = int(((ts["TrangThai"] == "Tư vấn") & cu).sum())
        todo = [(len(nop_chua_giu), "Đã nộp hồ sơ, chưa giữ chỗ", "views/ke_toan.py"),
                (thieu, "Hồ sơ nhập học thiếu thông tin", "views/ho_so_nhap_hoc.py"),
                (hoan_phi, "Hủy giữ chỗ chờ hoàn phí", "views/ke_toan.py"),
                (tu_van_cu, "Tư vấn quá 14 ngày chưa chuyển bước", "views/data_tuyen_sinh.py")]
        pending = [t for t in todo if t[0] and ui.co_trang(t[2])]
        if not pending:
            ui.empty_state("task_alt", "Không có việc tồn đọng")
        for n, label, page in pending:
            c = st.container(horizontal=True, vertical_alignment="center", gap="small",
                             wrap=False)
            c.html(f'<div class="tq-todo"><span class="n">{n}</span>{escape(label)}</div>',
                   width="stretch")
            with c:
                ui.page_link(page, label="", icon=":material/arrow_forward:")
