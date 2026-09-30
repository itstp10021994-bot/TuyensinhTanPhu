"""Ứng dụng quản lý tuyển sinh — Trường TH, THCS & THPT Tân Phú.

Chạy:  streamlit run app.py
"""
from pathlib import Path

import streamlit as st

from tuyensinh import config, ui

ROOT = Path(__file__).parent
st.set_page_config(page_title="Tuyển sinh · Tân Phú", page_icon=str(ROOT / "static/icon.svg"),
                   layout="wide", initial_sidebar_state="collapsed")
ui.inject_css()
st.logo(str(ROOT / "static/logo.svg"), icon_image=str(ROOT / "static/icon.svg"), size="large")


def _has_auth() -> bool:
    try:
        return "auth" in st.secrets
    except Exception:
        return False


if _has_auth() and not st.user.is_logged_in:
    # Màn hình đăng nhập (khi bật [auth] trong secrets.toml)
    _, mid, _ = st.columns([1, 1.2, 1])
    with mid, st.container(border=True):
        st.image(str(ROOT / "static/logo.svg"), width=220)
        st.markdown("### Đăng nhập")
        st.caption("Dùng tài khoản Microsoft 365 của trường để tiếp tục.")
        st.button("Đăng nhập với Microsoft", icon=":material/login:", type="primary",
                  width="stretch", on_click=st.login,
                  args=("microsoft",) if "microsoft" in st.secrets["auth"] else ())
    st.stop()

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
    "cd": st.Page("views/cai_dat.py", title="Cài đặt & đồng bộ", icon=":material/settings:",
                  url_path="cai-dat"),
}
# Thanh menu ngang như app cũ: Tổng quan · Data tuyển sinh · Hồ sơ nhập học · Kế toán · Báo cáo
pg = st.navigation([P["home"], P["ts"], P["nh"], P["kt"], P["bc"], P["cd"]], position="top")

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
    if _has_auth():
        with st.popover(ui.current_user() or "Tài khoản", icon=":material/account_circle:"):
            st.button("Đăng xuất", icon=":material/logout:", on_click=st.logout,
                      type="tertiary")
    else:
        who = st.session_state.get("nguoi_dung") or "Người thao tác"
        with st.popover(who, icon=":material/account_circle:"):
            st.text_input("Người thao tác", key="nguoi_dung", placeholder="Họ tên của bạn",
                          help="Ghi vào các cột Người nhận hồ sơ / Người xác nhận.")
    st.button("", icon=":material/refresh:", key="tp_refresh", on_click=ui.refresh,
              help="Tải lại dữ liệu mới nhất từ SharePoint", type="tertiary")

try:
    if pg.url_path != "cai-dat":  # tải song song 2 list cho mọi trang (trang Cài đặt tự tải)
        from tuyensinh.schema import NHAP_HOC, TUYEN_SINH

        ui.preload(TUYEN_SINH, NHAP_HOC)
    pg.run()
except Exception as e:  # lỗi kết nối SharePoint, cấu hình...
    if type(e).__name__ in ("StopException", "RerunException", "RerunData"):
        raise
    ui.error_state(e)
