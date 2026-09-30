"""Kế toán: ghi nhận thu phí, xác nhận, tổng hợp giữ chỗ."""
import pandas as pd
import streamlit as st

from tuyensinh import services, ui
from tuyensinh.schema import HINH_THUC_TT, LOAI_PHI, THU_PHI, TUYEN_SINH, XAC_NHAN

nam_hoc = ui.nam_hoc()
storage = ui.storage()
ts = ui.df(TUYEN_SINH, nam_hoc)
tp = ui.df(THU_PHI, nam_hoc)
money = st.column_config.NumberColumn(format="%,.0f đ")

m1, m2, m3, m4 = st.columns(4)
m1.metric("Đã xác nhận", f"{tp.loc[tp.TrangThaiXN == 'Đã xác nhận', 'SoTien'].sum():,.0f} đ",
          border=True)
m2.metric("Chờ xác nhận", f"{tp.loc[tp.TrangThaiXN == 'Chờ xác nhận', 'SoTien'].sum():,.0f} đ",
          border=True)
m3.metric("Số phiếu chờ", int((tp.TrangThaiXN == "Chờ xác nhận").sum()), border=True)
m4.metric("HS đã giữ chỗ", tp.loc[(tp.LoaiPhi == "Phí giữ chỗ")
                                  & (tp.TrangThaiXN == "Đã xác nhận"), "TuyenSinhID"].nunique(),
          border=True)

tab_thu, tab_xn, tab_th = st.tabs(["Thu phí", "Xác nhận", "Tổng hợp giữ chỗ"])

# ------------------------------------------------------------------ Thu phí
with tab_thu:
    hs = ts[ts["TrangThai"] != "Rút hồ sơ"].sort_values("HoTenHS")
    labels = {r.id: f"{r.HoTenHS} — Khối {r.Khoi} — {r.SDT} ({r.TrangThai})"
              for r in hs.itertuples()}
    hs_id = st.selectbox("Học sinh", list(labels), format_func=labels.get, index=None,
                         placeholder="Chọn / gõ tên học sinh…")
    if hs_id:
        row = hs[hs["id"] == hs_id].iloc[0]
        with st.form("thu_phi", clear_on_submit=True):
            c1, c2, c3 = st.columns(3)
            loai = c1.selectbox("Loại phí *", LOAI_PHI)
            so_tien = c2.number_input("Số tiền *", min_value=0.0, step=100000.0, format="%.0f")
            ngay = c3.date_input("Ngày thu *", format="DD/MM/YYYY")
            c4, c5, c6 = st.columns(3)
            hinh_thuc = c4.selectbox("Hình thức", HINH_THUC_TT)
            so_phieu = c5.text_input("Số phiếu / Mã giao dịch")
            nguoi_thu = c6.text_input("Người thu", value=ui.current_user())
            ghi_chu = st.text_input("Ghi chú")
            if st.form_submit_button("Ghi nhận", icon=":material/add_card:", type="primary"):
                try:
                    services.add_payment(storage, {
                        "TuyenSinhID": hs_id, "NamHoc": nam_hoc, "HoTenHS": row.HoTenHS,
                        "Khoi": row.Khoi, "LoaiPhi": loai, "SoTien": so_tien, "NgayThu": ngay,
                        "HinhThuc": hinh_thuc, "SoPhieu": so_phieu, "NguoiThu": nguoi_thu,
                        "GhiChu": ghi_chu})
                except ValueError as e:
                    ui.show_errors(e)
                else:
                    ui.invalidate()
                    st.toast("Đã ghi nhận — chờ kế toán xác nhận", icon="✅")
                    st.rerun()
        mine = tp[tp["TuyenSinhID"] == hs_id]
        st.dataframe(mine[["NgayThu", "LoaiPhi", "SoTien", "HinhThuc", "SoPhieu",
                           "TrangThaiXN", "NguoiXacNhan"]],
                     hide_index=True, width="stretch",
                     column_config={"NgayThu": st.column_config.DateColumn("Ngày thu",
                                                                           format="DD/MM/YYYY"),
                                    "LoaiPhi": "Loại phí", "SoTien": money,
                                    "HinhThuc": "Hình thức", "SoPhieu": "Số phiếu",
                                    "TrangThaiXN": "Trạng thái", "NguoiXacNhan": "Người XN"})

# ------------------------------------------------------------------ Xác nhận
with tab_xn:
    loc = st.segmented_control("Hiển thị", XAC_NHAN, default="Chờ xác nhận")
    pend = tp if not loc else tp[tp["TrangThaiXN"] == loc]
    pend = pend.sort_values("NgayThu", ascending=False).reset_index(drop=True)
    if pend.empty:
        st.info("Không có phiếu thu nào.")
    else:
        edit = pend[["id", "NgayThu", "HoTenHS", "Khoi", "LoaiPhi", "SoTien", "HinhThuc",
                     "SoPhieu", "NguoiThu", "TrangThaiXN"]].copy()
        edit.insert(0, "Chọn", False)
        out = st.data_editor(
            edit, hide_index=True, width="stretch", key=f"xn_{ui.data_version()}",
            disabled=[c for c in edit.columns if c != "Chọn"],
            column_config={"id": None, "NgayThu": st.column_config.DateColumn(
                "Ngày thu", format="DD/MM/YYYY"), "HoTenHS": "Họ tên HS", "Khoi": "Khối",
                "LoaiPhi": "Loại phí", "SoTien": money, "HinhThuc": "Hình thức",
                "SoPhieu": "Số phiếu", "NguoiThu": "Người thu", "TrangThaiXN": "Trạng thái"})
        ids = out.loc[out["Chọn"], "id"].tolist()
        c1, c2, c3, _ = st.columns([1, 1, 1, 2])
        for c, (label, status, icon) in zip((c1, c2, c3), [
                ("Xác nhận", "Đã xác nhận", ":material/check_circle:"),
                ("Hoàn tiền", "Hoàn tiền", ":material/undo:"),
                ("Hủy phiếu", "Hủy", ":material/cancel:")]):
            if c.button(f"{label} ({len(ids)})", icon=icon, disabled=not ids, width="stretch",
                        type="primary" if status == "Đã xác nhận" else "secondary"):
                services.confirm_payments(storage, ids, ui.current_user(), status)
                ui.invalidate()
                st.rerun()

# ------------------------------------------------------------------ Tổng hợp
with tab_th:
    sm = services.payment_summary(ts, tp)
    chi = st.toggle("Chỉ HS chưa đóng phí giữ chỗ")
    if chi:
        col = sm["Phí giữ chỗ"] if "Phí giữ chỗ" in sm.columns else pd.Series(0, index=sm.index)
        sm = sm[col <= 0]
    fee_cols = [c for c in sm.columns if c in LOAI_PHI] + ["Tổng đã thu"]
    st.dataframe(sm.drop(columns=["TuyenSinhID"]), hide_index=True, width="stretch",
                 column_config={"HoTenHS": "Họ tên HS", "Khoi": "Khối", "CheDo": "Chế độ",
                                "SDT": "SĐT", "TrangThai": "Trạng thái",
                                **{c: money for c in fee_cols}})
    ui.download_excel("Tải Excel tổng hợp", sm.drop(columns=["TuyenSinhID"]),
                      f"TongHopThuPhi_{nam_hoc}.xlsx", "TongHop")
