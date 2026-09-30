import streamlit as st

from tuyensinh import ui
from tuyensinh.schema import TRANG_THAI, TUYEN_SINH

ts = ui.df(TUYEN_SINH, ui.nam_hoc())

st.subheader(f"Tổng quan tuyển sinh năm học {ui.nam_hoc()}")
counts = ts["TrangThai"].value_counts()
cols = st.columns(len(TRANG_THAI) + 1)
cols[0].metric("Tổng số liên hệ", len(ts), border=True)
for c, tt in zip(cols[1:], TRANG_THAI):
    c.metric(tt, int(counts.get(tt, 0)), border=True)

left, right = st.columns([3, 2])
with left:
    st.markdown("##### Liên hệ mới nhất")
    recent = ts.sort_values(["NgayLienHe", "id"], ascending=False).head(10)
    st.dataframe(
        recent[["NgayLienHe", "HoTenHS", "Khoi", "CheDo", "SDT", "TrangThai"]],
        hide_index=True, width="stretch",
        column_config={"NgayLienHe": st.column_config.DateColumn("Ngày liên hệ", format="DD/MM/YYYY"),
                       "HoTenHS": "Họ tên HS", "Khoi": "Khối", "CheDo": "Chế độ",
                       "SDT": "SĐT", "TrangThai": "Trạng thái"})
with right:
    st.markdown("##### Chức năng")
    st.page_link("views/data_tuyen_sinh.py", label="Data tuyển sinh — tư vấn, nhận hồ sơ",
                 icon=":material/person_search:")
    st.page_link("views/ho_so_nhap_hoc.py", label="Hồ sơ nhập học — thông tin HS, xuất VEMIS",
                 icon=":material/assignment_ind:")
    st.page_link("views/ke_toan.py", label="Kế toán — thu phí, xác nhận, tổng hợp",
                 icon=":material/payments:")
    st.page_link("views/bao_cao.py", label="Báo cáo — thống kê, biểu đồ",
                 icon=":material/bar_chart:")
    nhap_hoc = int(counts.get("Nhập học", 0))
    if len(ts):
        st.progress(nhap_hoc / len(ts), text=f"Tỷ lệ nhập học / liên hệ: {nhap_hoc / len(ts):.0%}")
