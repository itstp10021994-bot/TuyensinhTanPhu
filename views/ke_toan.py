"""Kế toán: xác nhận tiền giữ chỗ, theo dõi hoàn phí, tổng hợp giữ chỗ.

Dùng các cột có sẵn của Data tuyển sinh: Tình trạng, Số tiền xác nhận, Người xác nhận,
Tên chủ tài khoản, Ngân hàng, Số tài khoản.
"""
import streamlit as st

from tuyensinh import services, ui
from tuyensinh.schema import KHOI, TINH_TRANG, TUYEN_SINH

S = st.session_state
S.setdefault("kt_v", 0)
nam_hoc = ui.nam_hoc()
storage = ui.storage()
ts = ui.df(TUYEN_SINH, nam_hoc)
ts["TinhTrang"] = ts["TinhTrang"].replace("", "Chưa giữ chỗ")
money = st.column_config.NumberColumn("Số tiền xác nhận", format="%,.0f đ")

giu = ts[ts["TinhTrang"] == "Đã giữ chỗ"]
m1, m2, m3, m4 = st.columns(4)
m1.metric("HS đã giữ chỗ", len(giu), border=True)
m2.metric("Tiền giữ chỗ đã xác nhận", f"{giu['SoTienXacNhan'].fillna(0).sum():,.0f} đ",
          border=True)
m3.metric("Hủy giữ chỗ (chờ hoàn phí)", int((ts["TinhTrang"] == "Hủy giữ chỗ").sum()),
          border=True)
m4.metric("Đã hoàn phí", int((ts["TinhTrang"] == "Đã hoàn phí").sum()), border=True)

tab_xn, tab_hp, tab_th = st.tabs(["Xác nhận giữ chỗ", "Hoàn phí", "Tổng hợp giữ chỗ"])

COLS = {"HoTenHS": "Họ tên HS", "Khoi": "Khối", "SDT": "SĐT", "TrangThai": "Bước",
        "TinhTrang": "Tình trạng", "SoTienXacNhan": money, "NguoiXacNhan": "Người xác nhận",
        "TenChuTaiKhoan": "Chủ tài khoản", "NganHang": "Ngân hàng", "SoTaiKhoan": "Số tài khoản"}

# ------------------------------------------------------------------ Xác nhận
with tab_xn:
    left, right = st.columns([3, 2], gap="medium")
    with left:
        f1, f2, f3 = st.columns([2, 1, 2])
        tt = f1.selectbox("Tình trạng", ["Tất cả", *TINH_TRANG], key="kt_tt")
        khoi = f2.selectbox("Khối", ["Tất cả", *KHOI], key="kt_khoi")
        q = f3.text_input("Tìm", placeholder="Tên HS / SĐT", key="kt_q")
        view = ts[ts["TrangThai"] != "Tư vấn"] if tt == "Tất cả" else ts[ts["TinhTrang"] == tt]
        if khoi != "Tất cả":
            view = view[view["Khoi"] == khoi]
        if q:
            view = view[view["HoTenHS"].str.lower().str.contains(q.lower(), regex=False)
                        | view["SDT"].str.contains(q, regex=False)]
        view = view.sort_values("HoTenHS").reset_index(drop=True)
        st.caption(f"{len(view)} học sinh" + (" (đã nộp hồ sơ trở lên)" if tt == "Tất cả" else ""))
        ev = st.dataframe(view[["HoTenHS", "Khoi", "TrangThai", "TinhTrang", "SoTienXacNhan",
                                "NguoiXacNhan"]], column_config=COLS, hide_index=True,
                          width="stretch", height=460, on_select="rerun",
                          selection_mode="single-row", key=f"kt_table_{S.kt_v}")
    with right:
        if not ev.selection.rows:
            st.info("Chọn học sinh để xác nhận giữ chỗ / hủy / hoàn phí.")
        else:
            r = view.loc[ev.selection.rows[0]].to_dict()
            st.markdown(f"<div class='ts-card'><b>{r['HoTenHS']}</b> — Khối {r['Khoi']} — "
                        f"{r['SDT']}</div>", unsafe_allow_html=True)
            p = f"kt_{r['id']}_{S.kt_v}"
            opts = list(TINH_TRANG) + ([r["TinhTrang"]] if r["TinhTrang"] not in TINH_TRANG else [])
            tinh_trang = st.selectbox("Tình trạng", opts, index=opts.index(r["TinhTrang"]),
                                      key=f"{p}_tt")
            cur = r.get("SoTienXacNhan")
            so_tien = st.number_input("Số tiền xác nhận", min_value=0.0, step=100000.0,
                                      format="%.0f", key=f"{p}_st",
                                      value=None if cur != cur or cur is None else float(cur))
            nguoi = st.text_input("Người xác nhận", key=f"{p}_ng",
                                  value=r.get("NguoiXacNhan") or ui.current_user())
            st.markdown("**Tài khoản hoàn phí** (khi hủy giữ chỗ)")
            c1, c2 = st.columns(2)
            chu_tk = c1.text_input("Tên chủ tài khoản", r.get("TenChuTaiKhoan", ""),
                                   key=f"{p}_chu")
            ngan_hang = c2.text_input("Ngân hàng", r.get("NganHang", ""), key=f"{p}_nh")
            so_tk = st.text_input("Số tài khoản", r.get("SoTaiKhoan", ""), key=f"{p}_stk")
            if st.button("Lưu xác nhận", icon=":material/check_circle:", type="primary",
                         width="stretch"):
                try:
                    services.xac_nhan_giu_cho(storage, r["id"], so_tien, nguoi, tinh_trang,
                                              TenChuTaiKhoan=chu_tk, NganHang=ngan_hang,
                                              SoTaiKhoan=so_tk)
                except ValueError as e:
                    ui.show_errors(e)
                else:
                    ui.invalidate()
                    S.kt_v += 1
                    st.toast("Đã lưu xác nhận", icon="✅")
                    st.rerun()

# ------------------------------------------------------------------ Hoàn phí
with tab_hp:
    hp = ts[ts["TinhTrang"].isin(["Hủy giữ chỗ", "Đã hoàn phí"])].sort_values("TinhTrang")
    st.caption("HS hủy giữ chỗ cần hoàn phí. Sau khi chuyển khoản, chọn HS ở tab "
               "*Xác nhận giữ chỗ* và đổi Tình trạng thành **Đã hoàn phí**.")
    show = hp[["HoTenHS", "Khoi", "SDT", "TinhTrang", "SoTienXacNhan", "TenChuTaiKhoan",
               "NganHang", "SoTaiKhoan", "GhiChu"]]
    st.dataframe(show, column_config={**COLS, "GhiChu": "Nội dung đã trao đổi"},
                 hide_index=True, width="stretch")
    ui.download_excel("Tải danh sách hoàn phí", show, f"HoanPhi_{nam_hoc}.xlsx", "HoanPhi")

# ------------------------------------------------------------------ Tổng hợp
with tab_th:
    sm = services.giu_cho_summary(ts)
    st.dataframe(sm, hide_index=True, width="stretch",
                 column_config={"Tiền đã giữ chỗ": money})
    detail = giu[["HoTenHS", "Khoi", "CheDo", "SDT", "TrangThai", "SoTienXacNhan",
                  "NguoiXacNhan"]].sort_values(["Khoi", "HoTenHS"])
    st.markdown("##### Danh sách HS đã giữ chỗ")
    st.dataframe(detail, hide_index=True, width="stretch",
                 column_config={**COLS, "CheDo": "Chế độ"})
    ui.download_excel("Tải Excel tổng hợp", detail, f"TongHopGiuCho_{nam_hoc}.xlsx", "GiuCho")
