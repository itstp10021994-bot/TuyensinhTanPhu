"""Ứng dụng quản lý tuyển sinh — Trường TH, THCS & THPT Tân Phú.

Chạy:  streamlit run app.py
"""
from pathlib import Path

import streamlit as st

from tuyensinh import config, ui

ROOT = Path(__file__).parent
st.set_page_config(page_title="Tuyển sinh · Tân Phú", page_icon=str(ROOT / "static/icon.svg"),
                   layout="wide", initial_sidebar_state="auto")
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
pg = st.navigation({"": [P["home"]], "Tuyển sinh": [P["ts"], P["nh"]],
                    "Tài chính": [P["kt"]], "Phân tích": [P["bc"]], "Hệ thống": [P["cd"]]},
                   position="sidebar")

with st.sidebar:
    years = config.school_years()
    default = config.default_year()
    st.selectbox("Năm học", years, index=years.index(default) if default in years else 0,
                 key="nam_hoc", help="Mọi trang đều hiển thị dữ liệu của năm học này.")
    if _has_auth():
        st.caption(f"Đăng nhập: **{ui.current_user()}**")
        st.button("Đăng xuất", icon=":material/logout:", on_click=st.logout, type="tertiary")
    else:
        st.text_input("Người thao tác", key="nguoi_dung", placeholder="Họ tên của bạn",
                      help="Ghi vào các cột Người nhận hồ sơ / Người xác nhận.")
    st.caption(f"Dữ liệu: {'SharePoint' if config.backend() != 'local' else 'Máy cục bộ (thử nghiệm)'}")

try:
    pg.run()
except Exception as e:  # lỗi kết nối SharePoint, cấu hình...
    if type(e).__name__ in ("StopException", "RerunException", "RerunData"):
        raise
    ui.error_state(e)
