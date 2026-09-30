"""Hồ sơ nhập học — bố cục như app Power Apps cũ.

Trái: lọc Khối / Lớp / Trạng thái + tìm kiếm, danh sách thẻ học sinh (20 thẻ/trang) với nút
Rút HS, Xếp lớp, Đăng ký xe, Nhóm môn, Xóa. Phải: "Thông tin chi tiết học sinh đăng ký nhập
học" theo tab (Thông tin học sinh, Cha mẹ / NGH, Quá trình học tập, Liên hệ khẩn cấp, Tài khoản
ngân hàng, Lựa chọn môn…) và nút Thu hồ sơ, Thanh toán học phí, Lưu hồ sơ. Học sinh đang chọn
nằm ở ?id=... để giữ khi tải lại trang.
"""
from dataclasses import replace
from datetime import date

import pandas as pd
import streamlit as st

from tuyensinh import export_vemis, services, ui
from tuyensinh.schema import (G_CHUNG, G_DIACHI, G_GIADINH, G_GIAYTO, G_HOCPHI, G_HOCTAP,
                              G_KHANCAP, G_LIENLAC, G_MON, G_NGANHANG, GIAY_TO_NHAP_HOC, MON_HOC,
                              NHAP_HOC, TINH_TRANG_HS, TUYEN_SINH)

S = st.session_state
S.setdefault("nh_v", 0)
qp = st.query_params
nam_hoc = ui.nam_hoc()
storage = ui.storage()
F = NHAP_HOC.get

TT_COLOR = {"Đang nhập hồ sơ": "blue", "Đang đóng phí": "orange", "Đã đóng phí": "green",
            "Học tiếp": "violet", "Không học tiếp": "gray", "Rút hồ sơ": "red"}
DANG_HOC = "Đang theo học"  # bộ lọc mặc định: bỏ HS đã rút / không học tiếp

ts = ui.df(TUYEN_SINH, nam_hoc)
nh = ui.df(NHAP_HOC, nam_hoc)
rut = set(ui.df(TUYEN_SINH).query("TrangThai == 'Rút hồ sơ'")["id"])
if len(nh):
    nh.loc[nh["TuyenSinhID"].isin(rut), "TinhTrangHS"] = "Rút hồ sơ"
    nh["HoanThien"] = (services.completeness(nh) * 100).round()
    nh["KhoiPH"] = nh.apply(lambda r: "-".join(x for x in (r["Khoi"], r["PhanHe"]) if x), axis=1)
else:
    nh["HoanThien"], nh["KhoiPH"] = [], []


def open_record(item_id: str):
    qp.clear()
    qp["id"] = item_id


def back_to_list():
    qp.clear()
    S.nh_v += 1


def done(res):
    if res is not None:
        S.nh_v += 1
        st.rerun()


# ================================================================== hộp thoại thao tác
@st.dialog("Xếp lớp")
def xep_lop_dialog(rec: dict):
    st.markdown(f"**{rec.get('HoTen')}** · Khối {rec.get('KhoiPH') or rec.get('Khoi') or '—'}")
    khoi = str(rec.get("Khoi") or "")
    lops = sorted({x for x in ui.df(NHAP_HOC, nam_hoc)["LopHoc"] if x})
    goi_y = [x for x in lops if khoi and x.startswith(khoi)] or lops
    cur = rec.get("LopHoc") or None
    lop = st.selectbox("Lớp", goi_y + ([cur] if cur and cur not in goi_y else []),
                       index=None if not cur else (goi_y + [cur]).index(cur),
                       accept_new_options=True, placeholder="Chọn hoặc gõ tên lớp (vd 10A1)")
    if st.button("Lưu", type="primary", icon=":material/check:", width="stretch",
                 disabled=not lop):
        done(ui.mutate(services.cap_nhat_nhap_hoc, storage, rec["id"], {"LopHoc": lop},
                       success=f"Đã xếp {rec.get('HoTen')} vào lớp {lop}"))


@st.dialog("Thu hồ sơ", width="large")
def thu_ho_so_dialog(rec: dict):
    ngay, docs = services.doc_ho_so(rec.get("HoSoDaNop"))
    st.markdown(f"**{rec.get('HoTen')}** — tích các giấy tờ đã nhận.")
    rows = [{"Giấy tờ": g, "Đã nộp": g in docs, "Bản": docs.get(g, "Bản gốc")}
            for g in [*GIAY_TO_NHAP_HOC, *[d for d in docs if d not in GIAY_TO_NHAP_HOC]]]
    ed = st.data_editor(
        pd.DataFrame(rows), hide_index=True, width="stretch", key=f"hs_{rec['id']}",
        disabled=["Giấy tờ"], height=ui.table_height(len(rows), 600),
        column_config={"Giấy tờ": st.column_config.TextColumn(width="large"),
                       "Đã nộp": st.column_config.CheckboxColumn(width="small"),
                       "Bản": st.column_config.SelectboxColumn(
                           options=["Bản gốc", "Bản sao"], width="small", required=True)})
    ngay = st.date_input("Ngày nộp", ngay or ui._to_date(rec.get("NgayNhanHoSo")) or date.today(),
                         format="DD/MM/YYYY")
    if st.button("Lưu hồ sơ đã nộp", type="primary", icon=":material/check:", width="stretch"):
        chon = {r["Giấy tờ"]: r["Bản"] for _, r in ed.iterrows() if r["Đã nộp"]}
        upd = {"HoSoDaNop": services.ghi_ho_so(ngay, chon) if chon else "",
               "NgayNhanHoSo": ngay}
        if not rec.get("TinhTrangHS"):
            upd["TinhTrangHS"] = "Đang nhập hồ sơ"
        done(ui.mutate(services.cap_nhat_nhap_hoc, storage, rec["id"], upd,
                       success=f"Đã lưu {len(chon)} giấy tờ của {rec.get('HoTen')}"))


def _num(v):
    try:
        return None if v is None or pd.isna(v) or v == "" else float(v)
    except (TypeError, ValueError):
        return None


@st.dialog("Thanh toán học phí")
def hoc_phi_dialog(rec: dict):
    st.markdown(f"**{rec.get('HoTen')}**")
    giu_cho = _num(rec.get("SoTienXacNhan"))
    if giu_cho:
        st.caption(f"Đã giữ chỗ: {ui.money(giu_cho)}")
    kw = {"min_value": 0.0, "step": 100000.0, "format": "%.0f"}
    c1, c2 = st.columns(2)
    phai = c1.number_input("Số tiền PHHS thanh toán (đ)", value=_num(rec.get("SoTienThanhToan")),
                           **kw)
    thu = c2.number_input("Tổng số tiền đã thu (đ)", value=_num(rec.get("TongDaThu")), **kw)
    goi_y = max((phai or 0) - (thu or 0), 0) if phai is not None and thu is not None else None
    con = c1.number_input("Số tiền còn lại (đ)",
                          value=goi_y if goi_y is not None else _num(rec.get("SoTienConLai")),
                          **kw, help="Tự tính = PHHS thanh toán − đã thu (có thể sửa)")
    ngay = c2.date_input("Ngày đóng", ui._to_date(rec.get("NgayDongPhi")) or date.today(),
                         format="DD/MM/YYYY")
    nguoi = st.text_input("Kế toán xác nhận", rec.get("KeToanXacNhan") or ui.current_user())
    de_xuat = "Đã đóng phí" if con == 0 and phai else "Đang đóng phí"
    tt = st.selectbox("Tình trạng hồ sơ", TINH_TRANG_HS, index=TINH_TRANG_HS.index(de_xuat))
    if st.button("Lưu thanh toán", type="primary", icon=":material/payments:", width="stretch"):
        done(ui.mutate(services.cap_nhat_nhap_hoc, storage, rec["id"],
                       {"SoTienThanhToan": phai, "TongDaThu": thu, "SoTienConLai": con,
                        "NgayDongPhi": ngay, "KeToanXacNhan": nguoi, "TinhTrangHS": tt},
                       success=f"Đã lưu học phí của {rec.get('HoTen')}"))


@st.dialog("Đăng ký xe đưa đón")
def xe_dialog(rec: dict):
    st.markdown(f"**{rec.get('HoTen')}**")
    tuyen = sorted({x for x in ui.df(NHAP_HOC)["DangKyXe"] if x})
    cur = rec.get("DangKyXe") or None
    opts = tuyen + ([cur] if cur and cur not in tuyen else [])
    xe = st.selectbox("Tuyến xe", opts, index=opts.index(cur) if cur else None,
                      accept_new_options=True, placeholder="Chọn tuyến hoặc gõ tuyến mới")
    diem = st.text_input("Điểm đón trả", rec.get("DiemDonTra") or "",
                         placeholder="Vd: Chợ Mới Long Thành")
    c1, c2 = st.columns(2)
    if c1.button("Lưu", type="primary", icon=":material/directions_bus:", width="stretch",
                 disabled=not xe):
        done(ui.mutate(services.cap_nhat_nhap_hoc, storage, rec["id"],
                       {"DangKyXe": xe, "DiemDonTra": diem},
                       success=f"Đã đăng ký xe {xe} cho {rec.get('HoTen')}"))
    if cur and c2.button("Hủy đăng ký xe", width="stretch"):
        done(ui.mutate(services.cap_nhat_nhap_hoc, storage, rec["id"],
                       {"DangKyXe": "", "DiemDonTra": ""}, success="Đã hủy đăng ký xe"))


@st.dialog("Rút hồ sơ")
def rut_dialog(rec: dict):
    st.markdown(f"Rút hồ sơ của **{rec.get('HoTen')}**?")
    st.caption("Hồ sơ được giữ lại với tình trạng *Rút hồ sơ*; Data tuyển sinh cũng chuyển sang "
               "Rút hồ sơ.")
    ly_do = st.text_area("Lý do", placeholder="Vd: chuyển trường gần nhà")
    c1, c2 = st.columns(2)
    if c1.button("Rút hồ sơ", type="primary", icon=":material/person_remove:", width="stretch"):
        done(ui.mutate(services.rut_ho_so_nhap_hoc, storage, rec, ly_do.strip(),
                       ui.current_user(), success=f"Đã rút hồ sơ {rec.get('HoTen')}"))
    if c2.button("Quay lại", width="stretch"):
        st.rerun()


@st.dialog("Xóa hồ sơ nhập học")
def delete_dialog(rec: dict):
    st.write(f"Xóa vĩnh viễn hồ sơ của **{rec.get('HoTen')}**?")
    st.caption("Không thể hoàn tác.")
    c1, c2 = st.columns(2)
    if c1.button("Xóa vĩnh viễn", type="primary", icon=":material/delete:", width="stretch"):
        if ui.mutate(storage.delete_item, NHAP_HOC.name, rec["id"], success="Đã xóa hồ sơ") \
                is not None:
            back_to_list()
            st.rerun()
    if c2.button("Giữ lại", width="stretch"):
        st.rerun()


# ================================================================== chi tiết
ADDRESS = [
    ("Chỗ ở hiện nay", ["ChoO_SoNha", "ChoO_KhuDanCu", "ChoO_Tinh", "ChoO_Xa"]),
    ("Hộ khẩu thường trú", ["HK_SoNha", "HK_KhuDanCu", "HK_Tinh", "HK_Xa"]),
    ("Nơi sinh", ["NoiSinh_ThongTin", "NoiSinh_Tinh", "NoiSinh_Xa"]),
    ("Quê quán", ["QueQuan_ThongTin", "QueQuan_Tinh", "QueQuan_Xa"]),
    ("Nơi khai sinh", ["NoiKS_Tinh", "NoiKS_Xa"]),
]
T_HS, T_CHAME = "Thông tin học sinh", "Cha mẹ / NGH"
TABS = [(T_HS, (G_CHUNG,)), (G_DIACHI, (G_DIACHI,)), (G_GIAYTO, (G_GIAYTO,)),
        (T_CHAME, (G_GIADINH, G_LIENLAC)), (G_HOCTAP, (G_HOCTAP,)),
        (G_KHANCAP, (G_KHANCAP,)), (G_NGANHANG, (G_NGANHANG,)), (G_MON, (G_MON,)),
        (G_HOCPHI, (G_HOCPHI,))]
TRUONG = ("TruongCu_Tinh", "TruongCu_PhuongXa", "TruongCu")
SHORT = lambda keys: {k: F(k).label.split(" - ")[-1] for k in keys}  # noqa: E731


def render_tab(name: str, groups: tuple, rec: dict, prefix: str) -> dict:
    form = ui.record_form
    v = {}
    if name == T_HS:
        skip = set(TRUONG) | {"LopCu"}
        v.update(form([f for f in NHAP_HOC.fields if f.group == G_CHUNG and f.key not in skip],
                      rec, prefix, 3))
        v.update(form([F("GhiChu")], rec, prefix, 1))
    elif name == G_DIACHI:
        for i, (title_g, keys) in enumerate(ADDRESS):
            if i:
                st.divider()
            st.markdown(f"**{title_g}**")
            fs = [replace(F(k), label=F(k).label.split(" - ")[-1]) for k in keys]
            v.update(form(fs, rec, prefix, 4))
        st.caption("Chọn Tỉnh/Tp trước để hiện danh sách Xã/Phường tương ứng.")
    elif name == G_GIAYTO:
        v.update(form([F(k) for k in ("CanCuoc", "NgayCapCanCuoc", "NoiCapCanCuoc", "MaBHYT",
                                      "DienChinhSach", "KhuyetTat", "NoiTruBanTru")],
                      rec, prefix, 3))
        st.markdown("**Đối tượng**")
        v.update(form([F(k) for k in ("CanNgheo", "DoanVien", "DoiVien")], rec, prefix, 3))
    elif name == T_CHAME:
        for who, keys in [
                ("Cha", ["TenCha", "NamSinhCha", "NgheNghiepCha", "CanCuocCha", "DienThoaiBo",
                         "EmailCha", "DonViCongTacCha"]),
                ("Mẹ", ["TenMe", "NamSinhMe", "NgheNghiepMe", "CanCuocMe", "DienThoaiMe",
                        "EmailMe", "DonViCongTacMe"]),
                ("Người giám hộ", ["NguoiGiamHo", "NamSinhNGH", "NgheNghiepNGH", "CanCuocNGH",
                                   "DienThoaiNGH", "EmailNGH"]),
                ("Liên lạc", ["DienThoaiSLL", "EmailSLL", "DienThoaiHS"])]:
            st.markdown(f"**{who}**")
            v.update(form([F(k) for k in keys], rec, prefix, 4))
    elif name == G_HOCTAP:
        st.markdown("**Trường cũ**")
        v.update(form([F(k) for k in (*TRUONG, "LopCu")], rec, prefix, 4, SHORT(TRUONG)))
        for dot in ("1", "2"):
            st.divider()
            st.markdown(f"**Kết quả {dot}**")
            v.update(form([F(f"HocLuc{dot}"), F(f"HanhKiem{dot}")], rec, prefix, 4))
            v.update(form([F(f"{k}{dot}") for k, _ in MON_HOC], rec, prefix, 5,
                          {f"{k}{dot}": ten for k, ten in MON_HOC}))
    elif name == G_KHANCAP:
        v.update(form([f for f in NHAP_HOC.fields if f.group == G_KHANCAP], rec, prefix, 3,
                      SHORT(["KhanCap_Ten", "KhanCap_SDT", "KhanCap_QuanHe"])))
    elif name in (G_NGANHANG, G_MON):
        if name == G_NGANHANG:
            st.caption("Tài khoản nhận hoàn phí (khi rút hồ sơ / hủy giữ chỗ).")
        else:
            st.caption("Tổ hợp môn lựa chọn (THPT), theo thứ tự ưu tiên.")
        v.update(form([f for f in NHAP_HOC.fields if f.group == name], rec, prefix, 3))
    else:  # Hồ sơ & học phí
        ngay, docs = services.doc_ho_so(rec.get("HoSoDaNop"))
        c1, c2 = st.columns([2, 1])
        with c1:
            st.markdown("**Hồ sơ đã nộp**")
            if docs:
                st.markdown("\n".join(f"- {g} — *{b}*" for g, b in docs.items()))
            else:
                st.caption("Chưa ghi nhận giấy tờ nào — bấm **Thu hồ sơ** ở trên.")
        c2.markdown("**Ngày nộp**")
        c2.markdown(ui.fmt_date(ngay or rec.get("NgayNhanHoSo")))
        st.divider()
        st.markdown("**Học phí**")
        v.update(form([F(k) for k in ("SoTienXacNhan", "SoTienThanhToan", "TongDaThu",
                                      "SoTienConLai", "NgayDongPhi", "KeToanXacNhan")],
                      rec, prefix, 3))
        st.markdown("**Xe đưa đón**")
        v.update(form([F("DangKyXe"), F("DiemDonTra")], rec, prefix, 2))
    return v


@st.dialog("Nhóm môn (tổ hợp môn lựa chọn)")
def mon_dialog(rec: dict):
    st.markdown(f"**{rec.get('HoTen')}** · Khối {rec.get('KhoiPH') or '—'}")
    vals = ui.record_form([F(k) for k in ("LuaChon1", "LuaChon2", "LuaChon3")], rec,
                          f"mon_{rec['id']}", 1)
    if st.button("Lưu", type="primary", icon=":material/check:", width="stretch"):
        done(ui.mutate(services.cap_nhat_nhap_hoc, storage, rec["id"], vals,
                       success=f"Đã lưu nhóm môn của {rec.get('HoTen')}"))


# ================================================================== giao diện (như app cũ)
CSS = """<style>
.st-key-nh_cards [data-testid="stVerticalBlockBorderWrapper"] {padding: 2px 0;}
.st-key-nh_cards button {min-height: 30px; padding: 2px 10px; font-size: .78rem;}
.st-key-nh_cards [class*="st-key-name_"] button {border: 0; background: none; padding: 0;
  min-height: 0; font-size: 1rem; font-weight: 600; color: var(--tp-primary, #1D4ED8);
  text-align: left; justify-content: flex-start;}
.st-key-nh_cards [class*="st-key-name_"] button p {text-align: left;}
.st-key-nh_cards [class*="st-key-card_sel"] {border-left: 4px solid #1D4ED8;
  background: rgba(37, 99, 235, .06); border-radius: 8px;}
.nh-card {font-size: .86rem; line-height: 1.55; margin: 0;}
.nh-card b {font-weight: 600;} .nh-card .k {opacity: .7;}
.nh-card .red {color: #DC2626;}
.st-key-nh_head {background: #EA580C; border-radius: 8px; padding: 8px 14px;}
.st-key-nh_head h3 {color: #fff !important; margin: 0; font-size: 1.05rem;}
.st-key-nh_head button {background: #fff; color: #1D4ED8; border: 0; font-weight: 600;}
.st-key-nh_cards [class*="st-key-xoa_"] button {background: #DC2626; border-color: #DC2626;
  color: #fff;}
.st-key-nh_cards [class*="st-key-rut_"] button {color: #DC2626;}
.nh-xe {font-size: .75rem; font-weight: 600; margin: 0; align-self: center;}
</style>"""


def card(r: dict, selected: bool):
    """Thẻ học sinh ở cột trái: thông tin + nút thao tác nhanh."""
    rid = r["id"]
    with st.container(border=True, key=f"card_sel_{rid}" if selected else f"card_{rid}"):
        st.button(r["HoTen"] or "(Chưa có tên)", key=f"name_{rid}", on_click=open_record,
                  args=(rid,))
        lop = r["LopHoc"] or '<span class="red">Chưa xếp lớp</span>'
        tt = r["TinhTrangHS"]
        st.html(
            f'<p class="nh-card"><span class="k">Khối:</span> <b>{r["KhoiPH"] or "—"}</b>'
            f' &nbsp;·&nbsp; <span class="k">Chế độ:</span> <b>{r["NoiTruBanTru"] or "—"}</b>'
            f' &nbsp;·&nbsp; <span class="k">Lớp:</span> <b>{lop}</b><br>'
            f'<span class="k">SĐT:</span> <b>{r["DienThoaiSLL"] or "—"}</b>'
            + (f' &nbsp;·&nbsp; <span class="k">Trạng thái:</span> {tt}' if tt else "") + "</p>")
        act = st.container(horizontal=True, gap="small", vertical_alignment="center")
        if tt != "Rút hồ sơ" and act.button("Rút HS", key=f"rut_{rid}"):
            rut_dialog(r)
        if act.button("Xếp lớp", key=f"lop_{rid}"):
            xep_lop_dialog(r)
        if act.button("Đăng ký xe", key=f"xe_{rid}"):
            xe_dialog(r)
        khoi = int(r["Khoi"]) if str(r["Khoi"]).isdigit() else 0
        if khoi >= 10 and act.button("Nhóm môn", key=f"mon_{rid}"):
            mon_dialog(r)
        if act.button("Xóa", key=f"xoa_{rid}"):
            delete_dialog(r)
        if r["DangKyXe"]:
            act.html(f'<p class="nh-xe">🚌 {r["DangKyXe"]}</p>')


def filters() -> pd.DataFrame:
    c = st.columns(3, gap="small")
    khois = sorted({x for x in nh["KhoiPH"] if x},
                   key=lambda s: (int(s.split("-")[0]) if s.split("-")[0].isdigit() else 99, s))
    khoi = c[0].selectbox("Khối", ["Tất cả", *khois], key="nh_khoi")
    lops = sorted(x for x in nh["LopHoc"].unique() if x)
    lop = c[1].selectbox("Lớp", ["Tất cả", "Chưa xếp lớp", *lops], key="nh_lop")
    tt = c[2].selectbox("Trạng thái", [DANG_HOC, "Tất cả", *TINH_TRANG_HS], key="nh_tt",
                        help=f"{DANG_HOC}: bỏ học sinh đã rút hồ sơ / không học tiếp")
    q = st.text_input("Tìm kiếm", icon=":material/search:", key="nh_q",
                      label_visibility="collapsed",
                      placeholder="Nhập tên học sinh, SĐT, tên người đăng ký (cha mẹ / NGH)")
    dang_hoc = nh[~nh["TinhTrangHS"].isin(["Rút hồ sơ", "Không học tiếp"])]
    view = dang_hoc if tt == DANG_HOC else nh if tt == "Tất cả" else nh[nh["TinhTrangHS"] == tt]
    if khoi != "Tất cả":
        view = view[view["KhoiPH"] == khoi]
    if lop == "Chưa xếp lớp":
        view = view[view["LopHoc"] == ""]
    elif lop != "Tất cả":
        view = view[view["LopHoc"] == lop]
    if q.strip():
        ql = q.strip().lower()
        mask = pd.Series(False, index=view.index)
        for col in ("HoTen", "MaHocSinh", "TenCha", "TenMe", "NguoiGiamHo", "KhanCap_Ten"):
            mask |= view[col].str.lower().str.contains(ql, regex=False)
        phone = services.phone_query(q)
        if phone:
            for col in ("DienThoaiSLL", "DienThoaiBo", "DienThoaiMe", "DienThoaiNGH"):
                mask |= view[col].map(services.normalize_phone).str.contains(phone, regex=False)
        view = view[mask]
    S["_nh_filter"] = (khoi, lop, tt, q)
    return view.sort_values(["LopHoc", "HoTen"]).reset_index(drop=True)


PAGE = 20


def render_left(view: pd.DataFrame, selected: str | None):
    pages = max(1, -(-len(view) // PAGE))
    fkey = hash(S.get("_nh_filter"))
    if S.get("_nh_fkey") != fkey:  # đổi bộ lọc -> về trang 1
        S["_nh_fkey"], S["nh_page"] = fkey, 1
    page = min(S.get("nh_page", 1), pages)
    with st.container(height=760, border=True, key="nh_cards"):
        if view.empty:
            ui.empty_state("search_off", "Không có học sinh phù hợp",
                           "Thử từ khóa hoặc bộ lọc khác.")
        for _, r in view.iloc[(page - 1) * PAGE: page * PAGE].iterrows():
            card(r.to_dict(), r["id"] == selected)
    nav = st.container(horizontal=True, vertical_alignment="center")
    nav.button("", icon=":material/chevron_left:", key="pg_prev", disabled=page <= 1,
               on_click=lambda: S.update(nh_page=page - 1))
    nav.caption(f"Trang **{page}/{pages}** · {len(view)} học sinh")
    nav.button("", icon=":material/chevron_right:", key="pg_next", disabled=page >= pages,
               on_click=lambda: S.update(nh_page=page + 1))


def load_record(item_id: str) -> tuple[dict | None, pd.DataFrame]:
    if item_id == "new":
        return ({"NamHoc": nam_hoc, "QuocTich": "Việt Nam", "DanToc": "Kinh",
                 "TonGiao": "Không", "DienChinhSach": "Không",
                 "NgayVaoTruong": date.today().isoformat(), "TinhTrangHS": "Đang nhập hồ sơ"},
                pd.DataFrame())
    hit = ui.df(NHAP_HOC)
    hit = hit[hit["id"] == item_id]
    if hit.empty:
        return None, hit
    rec = hit.iloc[0].to_dict()
    rec["KhoiPH"] = "-".join(x for x in (rec.get("Khoi"), rec.get("PhanHe")) if x)
    if rec.get("TuyenSinhID") in rut:
        rec["TinhTrangHS"] = "Rút hồ sơ"
    # Hồ sơ tạo trước khi có cột Trường cũ: lấy từ Data tuyển sinh (lưu khi bấm Lưu)
    src = ts[ts["id"] == rec.get("TuyenSinhID")]
    if len(src):
        for k in TRUONG:
            if not rec.get(k):
                rec[k] = src.iloc[0].get(k, "")
    return rec, hit


def render_right(item_id: str | None):
    with st.container(key="nh_head"):
        h1, h2 = st.columns([4, 1], vertical_alignment="center")
        h1.markdown("### Thông tin chi tiết học sinh đăng ký nhập học")
        save_top = h2.button("Lưu hồ sơ", icon=":material/save:", key="save_top",
                             width="stretch", disabled=not item_id)
    if not item_id:
        with st.container(border=True, height=700):
            ui.empty_state("touch_app", "Chọn một học sinh",
                           "Bấm vào tên học sinh ở danh sách bên trái để xem và cập nhật hồ sơ.")
        return
    rec, hit = load_record(item_id)
    if rec is None:
        with st.container(border=True):
            ui.empty_state("person_off", "Không tìm thấy hồ sơ",
                           "Hồ sơ có thể đã bị xóa hoặc thuộc năm học khác.")
        return

    new = item_id == "new"
    missing = [] if new else services.missing_fields(rec)
    with st.container(border=True):
        t1, t2 = st.columns([3, 1], vertical_alignment="center")
        sub = " · ".join(x for x in [f"Khối {rec['KhoiPH']}" if rec.get("KhoiPH") else "",
                                     rec.get("LopHoc") or ("" if new else "Chưa xếp lớp"),
                                     rec.get("NoiTruBanTru") or ""] if x)
        t1.markdown(f"**{rec.get('HoTen') or 'Hồ sơ mới'}**" + (f"  \n:gray[{sub}]" if sub else ""))
        if not new:
            with t2.popover("Khác", icon=":material/more_horiz:", width="stretch"):
                if rec.get("TuyenSinhID"):
                    st.page_link("views/data_tuyen_sinh.py", label="Xem liên hệ tuyển sinh",
                                 icon=":material/person_search:",
                                 query_params={"id": rec["TuyenSinhID"]})
                st.download_button("Xuất Excel VEMIS (1 HS)",
                                   lambda: export_vemis.to_bytes(hit),
                                   file_name=f"VEMIS_{rec.get('HoTen')}.xlsx", mime=ui.XLSX,
                                   on_click="ignore", icon=":material/download:", width="stretch")
            pct = 1 - len(missing) / len(services.NHAP_HOC_CAN_CO)
            st.progress(pct, text=f"Hoàn thiện {pct:.0%}" + (
                " · còn thiếu: " + ", ".join(services.NHAP_HOC_NHAN_NGAN[k] for k in missing)
                if missing else ""))

    prefix = f"nh_{item_id}_{S.nh_v}"
    values = {"TuyenSinhID": rec.get("TuyenSinhID", "")}
    n_miss = {name: sum(1 for k in missing if F(k).group in groups) for name, groups in TABS}
    tabs = st.tabs([f"{name} ({n_miss[name]})" if n_miss[name] else name for name, _ in TABS])
    for tab, (name, groups) in zip(tabs, TABS):
        with tab, st.container(border=True, height=560):
            values.update(render_tab(name, groups, rec, prefix))

    bar = st.columns(3, gap="small")
    if not new:
        if bar[0].button("Thu hồ sơ", icon=":material/folder_open:", width="stretch"):
            thu_ho_so_dialog(rec)
        if bar[1].button("Thanh toán học phí", icon=":material/payments:", width="stretch"):
            hoc_phi_dialog(rec)
    save_bottom = bar[2].button("Lưu hồ sơ", type="primary", icon=":material/save:",
                                key="save_bot", width="stretch")

    if save_top or save_bottom:
        values["NamHoc"] = values.get("NamHoc") or nam_hoc
        res = ui.mutate(services.save_nhap_hoc, storage, values, None if new else item_id,
                        success="Đã lưu hồ sơ")
        if res is not None:
            S.nh_v += 1
            if new:
                open_record(res["id"])
            st.rerun()


def render_page():
    st.html(CSS)
    actions = ui.page_header("Hồ sơ nhập học", f"Năm học {nam_hoc}")
    view_all = nh
    export_slot = actions.container(width="content")
    actions.button("Thêm hồ sơ", icon=":material/add:", on_click=open_record, args=("new",),
                   help="Thêm học sinh nhập học không qua Data tuyển sinh")

    chua_co = ts[(ts["TrangThai"] == "Nhập học") & ~ts["id"].isin(nh["TuyenSinhID"])]
    if len(chua_co):
        c1, c2 = st.columns([4, 1], vertical_alignment="center")
        c1.info(f"**{len(chua_co)} học sinh** đã xác nhận nhập học nhưng chưa có hồ sơ.",
                icon=":material/info:")
        if c2.button("Tạo hồ sơ", icon=":material/sync:", width="stretch"):
            bar = st.progress(0.0, text="Đang tạo hồ sơ…")
            n = ui.mutate(services.tao_ho_so_hang_loat, storage,
                          [r.to_dict() for _, r in chua_co.iterrows()],
                          progress=lambda d, t: bar.progress(d / max(t, 1),
                                                             text=f"Đã tạo {d}/{t} hồ sơ"),
                          success=f"Đã tạo {len(chua_co)} hồ sơ")
            if n is not None:
                st.rerun()

    selected = qp.get("id")
    left, right = st.columns([1, 1.45], gap="medium")
    with left:
        if view_all.empty:
            ui.empty_state("assignment_ind", "Chưa có hồ sơ nhập học",
                           "Hồ sơ được tạo tự động khi xác nhận Nhập học ở Data tuyển sinh.")
            view = view_all
        else:
            view = filters()
            render_left(view, selected)
    with right:
        render_right(selected)

    export = view.drop(columns=["HoanThien", "KhoiPH"], errors="ignore")
    export_slot.download_button(
        f"Xuất VEMIS ({len(view)})", lambda: export_vemis.to_bytes(export),
        file_name=f"DanhSachHocSinh_{nam_hoc}.xlsx", mime=ui.XLSX,
        icon=":material/download:", on_click="ignore", disabled=view.empty,
        help="Tải file Excel đúng biểu mẫu Danh sách học sinh (VEMIS) theo bộ lọc hiện tại")


render_page()
