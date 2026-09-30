"""Ứng dụng quản lý tuyển sinh — Trường TH, THCS & THPT Tân Phú.

Chạy:  streamlit run app.py
"""
import streamlit as st

from tuyensinh import ui

st.set_page_config(page_title="Quản lý tuyển sinh", page_icon=":material/school:",
                   layout="wide")


def _require_login():
    """Bật đăng nhập Microsoft khi có mục [auth] trong secrets.toml (xem README)."""
    try:
        has_auth = "auth" in st.secrets
    except Exception:
        has_auth = False
    if not has_auth:
        with st.sidebar:
            st.text_input("Người dùng", key="nguoi_dung", placeholder="Tên người thao tác")
        return
    if not st.user.is_logged_in:
        st.title("Quản lý tuyển sinh")
        st.button("Đăng nhập bằng tài khoản Microsoft 365", on_click=st.login,
                  args=("microsoft",) if "microsoft" in st.secrets["auth"] else ())
        st.stop()
    with st.sidebar:
        st.write(f"Xin chào **{ui.current_user()}**")
        st.button("Đăng xuất", on_click=st.logout)


_require_login()

pages = [
    st.Page("views/trang_chu.py", title="Trang chủ", icon=":material/home:", default=True),
    st.Page("views/data_tuyen_sinh.py", title="Data tuyển sinh", icon=":material/person_search:",
            url_path="data-tuyen-sinh"),
    st.Page("views/ho_so_nhap_hoc.py", title="Hồ sơ nhập học", icon=":material/assignment_ind:",
            url_path="ho-so-nhap-hoc"),
    st.Page("views/ke_toan.py", title="Kế toán", icon=":material/payments:", url_path="ke-toan"),
    st.Page("views/bao_cao.py", title="Báo cáo", icon=":material/bar_chart:", url_path="bao-cao"),
]
pg = st.navigation(pages, position="top")
ui.header()
try:
    pg.run()
except RuntimeError as e:  # lỗi kết nối SharePoint, ...
    st.error(f"Lỗi: {e}")
ui.footer()
