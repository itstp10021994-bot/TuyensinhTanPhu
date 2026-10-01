"""Ứng dụng quản lý tuyển sinh — Trường TH, THCS & THPT Tân Phú.

Chạy:  streamlit run app.py
"""
import hmac
from pathlib import Path

import streamlit as st

from tuyensinh import config, ui

ROOT = Path(__file__).parent
st.set_page_config(page_title="Tuyển sinh · Tân Phú", page_icon=str(ROOT / "static/icon.svg"),
                   layout="wide", initial_sidebar_state="collapsed")
ui.inject_css()
_logo = ROOT / "static/logo_truong.png"
_logo = str(_logo if _logo.exists() else ROOT / "static/logo.svg")
st.logo(_logo, icon_image=_logo, size="large")  # menu ngang hiện icon_image


def _has_auth() -> bool:
    try:
        return "auth" in st.secrets
    except Exception:
        return False


if _has_auth() and not st.user.is_logged_in:
    # Màn hình đăng nhập (khi bật [auth] trong Secrets) — tài khoản Microsoft 365 của trường
    _, mid, _ = st.columns([1, 1.2, 1])
    with mid, st.container(border=True):
        st.image(_logo, width=260)
        st.markdown("### Đăng nhập")
        st.caption("Dùng tài khoản Microsoft 365 của trường để tiếp tục. Tên tài khoản được ghi "
                   "vào hồ sơ là người nhập / người nhận hồ sơ.")
        st.button("Đăng nhập với Microsoft 365", icon=":material/login:", type="primary",
                  width="stretch", on_click=st.login,
                  args=("microsoft",) if "microsoft" in st.secrets["auth"] else ())
    st.stop()

# Chỉ cho tài khoản thuộc tên miền của trường (AUTH_DOMAIN = "igcschool.edu.vn"), nếu có đặt
_domain = str(config.get("AUTH_DOMAIN", "") or "").strip().lower().lstrip("@")
if _has_auth() and _domain:
    _email = str(st.user.get("email") or st.user.get("preferred_username") or "").lower()
    if not _email.endswith("@" + _domain):
        st.error(f"Tài khoản **{_email or 'này'}** không thuộc tên miền **{_domain}** của trường.",
                 icon=":material/block:")
        st.button("Đăng xuất", icon=":material/logout:", on_click=st.logout)
        st.stop()

# ------------------------------------------------------------------ tài khoản của app
# Khi chưa bật Microsoft 365 ([auth]) mà list DanhMuc_TaiKhoan có tài khoản: bắt đăng nhập.
# "Ghi nhớ đăng nhập": mã đã ký (30 ngày) lưu trong bộ nhớ trình duyệt (localStorage)
# -> F5 / mở lại trên máy đó không phải nhập.
S = st.session_state
if not _has_auth() and not S.get("tk"):
    from tuyensinh import tai_khoan
    from tuyensinh.schema import TAI_KHOAN

    try:
        _items = ui.records(TAI_KHOAN, optional=True)
    except Exception:
        _items = []
    _tks = tai_khoan.dang_hoat_dong(_items)
    if _tks:
        _ma = ui.ghi_nho("ghi_nho_doc", "" if S.pop("_xoa_ghi_nho", False) else None)
        if _ma is None:  # chờ trình duyệt gửi mã đã lưu (rất nhanh)
            st.caption("Đang kiểm tra đăng nhập…")
            st.stop()
        if _ma and not S.get("_da_dang_xuat"):
            S["tk"] = tai_khoan.tu_ma_ghi_nho(_items, _ma, ui.cookie_secret())
    if _tks and not S.get("tk"):
        _, mid, _ = st.columns([1, 1.1, 1])
        with mid, st.container(border=True):
            st.image(_logo, width=260)
            st.markdown("### Đăng nhập")
            with st.form("dang_nhap", border=False):
                _u = st.text_input("Tên đăng nhập", autocomplete="username")
                _p = st.text_input("Mật khẩu", type="password", autocomplete="current-password")
                _nho = st.checkbox("Ghi nhớ đăng nhập trên máy này (30 ngày)", value=True)
                _ok = st.form_submit_button("Đăng nhập", type="primary", icon=":material/login:",
                                            width="stretch")
            if _ok:
                _tk = tai_khoan.dang_nhap(_tks, _u, _p)
                if _tk:
                    S["tk"] = _tk
                    S.pop("_da_dang_xuat", None)
                    _t = next(t for t in _items if str(t.get("id")) == _tk["id"])
                    # không tích ghi nhớ -> xóa mã cũ (nếu có) trên máy này
                    S["_ghi_nho"] = tai_khoan.tao_ma_ghi_nho(_t, ui.cookie_secret()) if _nho else ""
                    st.rerun()
                st.error("Sai tên đăng nhập hoặc mật khẩu.", icon=":material/error:")
            st.caption("Chưa có tài khoản hoặc quên mật khẩu: liên hệ người quản trị app.")
            # Lối vào dự phòng khi chưa có / quên tài khoản Quản trị: mật khẩu ADMIN_PASSWORD
            _co_qt = any(t.get("VaiTro") == "Quản trị" for t in _tks)
            with st.expander("Đăng nhập bằng mật khẩu quản trị (ADMIN_PASSWORD)",
                             expanded=not _co_qt):
                if not _co_qt:
                    st.warning("Chưa có tài khoản vai trò **Quản trị**. Đăng nhập bằng mật khẩu "
                               "quản trị để vào Cài đặt → Tài khoản & phân quyền và tạo.",
                               icon=":material/warning:")
                _pw = config.get("ADMIN_PASSWORD")
                if not _pw:
                    st.caption("Chưa đặt **ADMIN_PASSWORD** trong Secrets của app "
                               "(Streamlit Cloud → Manage app → Settings → Secrets).")
                else:
                    with st.form("dang_nhap_qt", border=False):
                        _mk = st.text_input("Mật khẩu quản trị", type="password")
                        _ok2 = st.form_submit_button("Vào bằng quyền quản trị",
                                                     icon=":material/admin_panel_settings:")
                    if _ok2:
                        if hmac.compare_digest(_mk.encode(), str(_pw).encode()):
                            S["tk"] = tai_khoan.phien_quan_tri()
                            S.pop("_da_dang_xuat", None)
                            st.rerun()
                        st.error("Sai mật khẩu quản trị.", icon=":material/error:")
        st.stop()
if "_ghi_nho" in S:  # lưu mã ghi nhớ sau khi đăng nhập; giữ đến khi trình duyệt xác nhận
    if ui.ghi_nho("ghi_nho_ghi", S["_ghi_nho"]) == S["_ghi_nho"]:
        S.pop("_ghi_nho")


def _dang_xuat():
    S.pop("tk", None)
    S["_da_dang_xuat"] = True  # mã ghi nhớ cũ của phiên này không tự đăng nhập lại
    S["_xoa_ghi_nho"] = True  # xóa mã ghi nhớ trên máy này


P = {
    "home": st.Page("views/trang_chu.py", title="Tổng quan", icon=":material/space_dashboard:",
                    default=True),
    "ts": st.Page("views/data_tuyen_sinh.py", title="Data tuyển sinh",
                  icon=":material/person_search:", url_path="data-tuyen-sinh"),
    "nh": st.Page("views/ho_so_nhap_hoc.py", title="Hồ sơ nhập học",
                  icon=":material/assignment_ind:", url_path="ho-so-nhap-hoc"),
    "kt": st.Page("views/ke_toan.py", title="Kế toán", icon=":material/payments:",
                  url_path="ke-toan"),
    "bc": st.Page("views/bao_cao.py", title="Báo cáo", icon=":material/monitoring:",
                  url_path="bao-cao"),
    "tl": st.Page("views/tro_ly.py", title="Conan Ro", icon=":material/auto_awesome:",
                  url_path="tro-ly"),
    "cd": st.Page("views/cai_dat.py", title="Cài đặt & đồng bộ", icon=":material/settings:",
                  url_path="cai-dat"),
}
# Thanh menu ngang như app cũ: Tổng quan · Data tuyển sinh · Hồ sơ nhập học · Kế toán · Báo cáo
# Phân quyền: tài khoản của app chỉ thấy các trang được phép (Quản trị: tất cả)
_pages = [P["home"], P["ts"], P["nh"], P["kt"], P["bc"], P["cd"]]
if S.get("tk"):
    _pages = [p for p in _pages if p.title in S["tk"]["Quyen"]] or [P["home"]]
# Trợ lý: ai cũng dùng được, câu trả lời tự giới hạn theo quyền xem của tài khoản
_pages.insert(len(_pages) - (_pages[-1] is P["cd"]), P["tl"])
_FILE = {"home": "trang_chu", "ts": "data_tuyen_sinh", "nh": "ho_so_nhap_hoc",
         "kt": "ke_toan", "bc": "bao_cao", "tl": "tro_ly", "cd": "cai_dat"}
# liên kết giữa các trang chỉ hiện khi tài khoản được vào trang đích (ui.page_link)
S["_trang_duoc_vao"] = {f"views/{_FILE[k]}.py" for k in P if P[k] in _pages}
pg = st.navigation(_pages, position="top")

# Thanh công cụ chung: năm học + người thao tác (thay cho thanh bên)
years = config.school_years()
default = config.default_year()
if st.session_state.get("nam_hoc") not in years:
    st.session_state["nam_hoc"] = default if default in years else years[0]
with st.container(horizontal=True, horizontal_alignment="right", vertical_alignment="center",
                  key="tp_toolbar", gap="small"):
    src = "SharePoint" if config.backend() != "local" else "Máy cục bộ (thử nghiệm)"
    st.caption(f":material/cloud_done: {src}")
    st.selectbox("Năm học", years, key="nam_hoc", label_visibility="collapsed", width=150,
                 help="Mọi trang đều hiển thị dữ liệu của năm học này.")
    # Trợ lý AI "Conan Ro": biểu tượng AI trên thanh đầu trang (thay cho mục menu)
    if P["tl"] in _pages:
        with st.container(key="tp_ai", width="content"):
            st.page_link(P["tl"], label="Conan Ro", icon=":material/auto_awesome:",
                         help="Hỏi trợ lý AI Conan Ro về dữ liệu tuyển sinh")
    if _has_auth():
        with st.popover(ui.current_user() or "Tài khoản", icon=":material/account_circle:"):
            st.button("Đăng xuất", icon=":material/logout:", on_click=st.logout,
                      type="tertiary")
    elif st.session_state.get("tk"):
        _tk = st.session_state["tk"]
        with st.popover(_tk["HoTen"], icon=":material/account_circle:"):
            st.caption(f"{_tk['TenDangNhap']} · {_tk['VaiTro']}")
            if not _tk.get("id"):  # vào bằng ADMIN_PASSWORD
                st.caption("Phiên quản trị tạm — hãy tạo tài khoản Quản trị trong Cài đặt.")
            else:
                with st.form("doi_mk", border=False):
                    _cu = st.text_input("Mật khẩu hiện tại", type="password")
                    _moi = st.text_input("Mật khẩu mới", type="password")
                    if st.form_submit_button("Đổi mật khẩu", icon=":material/key:"):
                        from tuyensinh import tai_khoan
                        from tuyensinh.schema import TAI_KHOAN

                        ui.mutate(tai_khoan.doi_mat_khau, ui.storage(), _tk["id"], _cu, _moi,
                                  ui.records(TAI_KHOAN, optional=True), success="Đã đổi mật khẩu")
            st.button("Đăng xuất", icon=":material/logout:", type="tertiary", on_click=_dang_xuat)
    else:
        who = st.session_state.get("nguoi_dung") or "Người thao tác"
        with st.popover(who, icon=":material/account_circle:"):
            st.text_input("Người thao tác", key="nguoi_dung", placeholder="Họ tên của bạn",
                          help="Ghi vào các cột Người nhận hồ sơ / Người xác nhận.")
    _toi = st.context.theme.type == "dark"
    if st.button("", icon=":material/light_mode:" if _toi else ":material/dark_mode:",
                 key="tp_theme", type="tertiary",
                 help="Chuyển sang giao diện sáng" if _toi else "Chuyển sang giao diện tối"):
        ui.doi_giao_dien("Light" if _toi else "Dark",
                         [getattr(P[k], "url_path", "") for k in P])
    st.button("", icon=":material/refresh:", key="tp_refresh", on_click=ui.refresh,
              help="Tải lại dữ liệu mới nhất từ SharePoint", type="tertiary")

try:
    if pg.url_path != "cai-dat":  # tải song song 2 list cho mọi trang (trang Cài đặt tự tải)
        from tuyensinh.schema import GIAY_TO, NHAP_HOC, TUYEN_SINH

        ui.preload(TUYEN_SINH, NHAP_HOC, GIAY_TO, optional=(GIAY_TO,))
    ui.apply_giay_to()
    pg.run()
except Exception as e:  # lỗi kết nối SharePoint, cấu hình...
    if type(e).__name__ in ("StopException", "RerunException", "RerunData"):
        raise
    ui.error_state(e)
