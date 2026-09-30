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
MONEY = st.column_config.TextColumn("Số tiền")  # đã định dạng sẵn, ô trống hiện "—"


def with_money(frame):
    return frame.assign(SoTienXacNhan=frame["SoTienXacNhan"].map(ui.money))


actions = ui.page_header("Kế toán", f"Xác nhận giữ chỗ và hoàn phí · năm học {nam_hoc}")
export_slot = actions.container(width="content")

giu = ts[ts["TinhTrang"] == "Đã giữ chỗ"]
cho_hoan = ts[ts["TinhTrang"] == "Hủy giữ chỗ"]
chua = ts[ts["TrangThai"].isin(["Nộp hồ sơ", "Nhập học"]) & (ts["TinhTrang"] == "Chưa giữ chỗ")]
k = ui.kpi_row(4)
ui.kpi(k[0], "Đã giữ chỗ", len(giu))
ui.kpi(k[1], "Tiền giữ chỗ đã xác nhận", ui.money(giu["SoTienXacNhan"].fillna(0).sum()))
ui.kpi(k[2], "Nộp hồ sơ, chưa giữ chỗ", len(chua),
       help="Học sinh ở bước Nộp hồ sơ / Nhập học nhưng chưa có xác nhận giữ chỗ")
ui.kpi(k[3], "Chờ hoàn phí", len(cho_hoan))

tab_xn, tab_hp, tab_th = st.tabs(["Xác nhận giữ chỗ", f"Hoàn phí ({len(cho_hoan)})",
                                  "Tổng hợp theo khối"])

# ------------------------------------------------------------------ Xác nhận
with tab_xn:
    left, right = st.columns([3, 2], gap="medium")
    with left:
        # HS cần kế toán xử lý: đã nộp hồ sơ / nhập học, hoặc đã có giao dịch giữ chỗ
        pool = ts[ts["TrangThai"].isin(["Nộp hồ sơ", "Nhập học"])
                  | (ts["TinhTrang"] != "Chưa giữ chỗ")]
        counts = pool["TinhTrang"].value_counts()
        tt = st.segmented_control(
            "Tình trạng", ["Tất cả", *TINH_TRANG],
            default="Chưa giữ chỗ" if counts.get("Chưa giữ chỗ", 0) else "Tất cả", required=True,
            key="kt_tt", label_visibility="collapsed",
            format_func=lambda s: f"{s}  {len(pool) if s == 'Tất cả' else int(counts.get(s, 0))}")
        c1, c2 = st.columns([3, 1], vertical_alignment="bottom")
        q = c1.text_input("Tìm kiếm", placeholder="Tên học sinh hoặc SĐT", key="kt_q",
                          icon=":material/search:")
        khoi = c2.selectbox("Khối", ["Tất cả", *KHOI], key="kt_khoi")
        view = pool if tt == "Tất cả" else pool[pool["TinhTrang"] == tt]
        if khoi != "Tất cả":
            view = view[view["Khoi"] == khoi]
        if q.strip():
            ql = q.strip().lower()
            phone = services.normalize_phone(q)
            mask = view["HoTenHS"].str.lower().str.contains(ql, regex=False)
            if phone:
                mask |= view["SDT"].str.contains(phone, regex=False)
            view = view[mask]
        view = view.sort_values("HoTenHS").reset_index(drop=True)
        st.caption(f"**{len(view)}** học sinh")
        ev = None
        if view.empty:
            ui.empty_state("inbox", "Không có học sinh", "Không có học sinh nào ở tình trạng này.")
        else:
            show = with_money(view).assign(Buoc=ui.tag_col(view["TrangThai"]),
                                           GiuCho=ui.tag_col(view["TinhTrang"]))
            ev = st.dataframe(
                show[["HoTenHS", "Khoi", "Buoc", "GiuCho", "SoTienXacNhan"]],
                hide_index=True, width="stretch", height=ui.table_height(len(show), 480),
                on_select="rerun", selection_mode="single-row", key=f"kt_table_{S.kt_v}",
                column_config={"HoTenHS": st.column_config.TextColumn("Học sinh", width="medium"),
                               "Khoi": st.column_config.TextColumn("Khối", width="small"),
                               "Buoc": ui.status_column(), "GiuCho": ui.giu_cho_column("Tình trạng"),
                               "SoTienXacNhan": MONEY})

    with right:
        if ev is None or not ev.selection.rows:
            with ui.section():
                ui.empty_state("touch_app", "Chọn một học sinh",
                               "Chọn học sinh trong danh sách để xác nhận giữ chỗ, hủy hoặc "
                               "ghi nhận hoàn phí.")
        else:
            r = view.loc[ev.selection.rows[0]].to_dict()
            with ui.section():
                st.markdown(f"#### {r['HoTenHS']}")
                st.caption(f"Khối {r['Khoi']} · {r['SDT']} · {r['TrangThai']}")
                p = f"kt_{r['id']}_{S.kt_v}"
                with st.form(f"f_{p}", border=False, enter_to_submit=False):
                    opts = list(TINH_TRANG) + ([r["TinhTrang"]] if r["TinhTrang"] not in TINH_TRANG
                                               else [])
                    suggest = "Đã giữ chỗ" if r["TinhTrang"] == "Chưa giữ chỗ" else r["TinhTrang"]
                    tinh_trang = st.selectbox("Tình trạng", opts, index=opts.index(suggest))
                    cur = r.get("SoTienXacNhan")
                    so_tien = st.number_input(
                        "Số tiền xác nhận (đ)", min_value=0.0, step=100000.0, format="%.0f",
                        value=None if cur is None or cur != cur else float(cur),
                        placeholder="Ví dụ 2000000")
                    nguoi = st.text_input("Người xác nhận",
                                          value=r.get("NguoiXacNhan") or ui.current_user())
                    st.markdown("**Tài khoản nhận hoàn phí**")
                    st.caption("Chỉ cần khi hủy giữ chỗ / hoàn phí.")
                    chu_tk = st.text_input("Tên chủ tài khoản", r.get("TenChuTaiKhoan", ""))
                    c1, c2 = st.columns(2)
                    ngan_hang = c1.text_input("Ngân hàng", r.get("NganHang", ""))
                    so_tk = c2.text_input("Số tài khoản", r.get("SoTaiKhoan", ""))
                    ok = st.form_submit_button("Lưu xác nhận", type="primary", width="stretch",
                                               icon=":material/check_circle:")
                if ok:
                    if ui.mutate(services.xac_nhan_giu_cho, storage, r["id"], so_tien, nguoi,
                                 tinh_trang, TenChuTaiKhoan=chu_tk, NganHang=ngan_hang,
                                 SoTaiKhoan=so_tk,
                                 success=f"Đã lưu: {r['HoTenHS']} — {tinh_trang}") is not None:
                        S.kt_v += 1
                        st.rerun()
                st.page_link("views/data_tuyen_sinh.py", label="Xem hồ sơ tuyển sinh",
                             icon=":material/open_in_new:", query_params={"id": r["id"]})

# ------------------------------------------------------------------ Hoàn phí
with tab_hp:
    hp = ts[ts["TinhTrang"].isin(["Hủy giữ chỗ", "Đã hoàn phí"])].sort_values(
        ["TinhTrang", "HoTenHS"], ascending=[False, True])
    if hp.empty:
        with ui.section():
            ui.empty_state("task_alt", "Không có yêu cầu hoàn phí",
                           "Học sinh hủy giữ chỗ sẽ xuất hiện ở đây.")
    else:
        st.caption("Sau khi chuyển khoản hoàn phí, chọn học sinh ở tab **Xác nhận giữ chỗ** và "
                   "đổi Tình trạng thành **Đã hoàn phí**.")
        show = with_money(hp).assign(GiuCho=ui.tag_col(hp["TinhTrang"]))
        st.dataframe(show[["HoTenHS", "Khoi", "SDT", "GiuCho", "SoTienXacNhan", "TenChuTaiKhoan",
                           "NganHang", "SoTaiKhoan", "GhiChu"]],
                     hide_index=True, width="stretch", height=ui.table_height(len(show)),
                     column_config={"HoTenHS": st.column_config.TextColumn("Học sinh", pinned=True),
                                    "Khoi": "Khối", "SDT": "SĐT",
                                    "GiuCho": ui.giu_cho_column("Tình trạng"),
                                    "SoTienXacNhan": MONEY, "TenChuTaiKhoan": "Chủ tài khoản",
                                    "NganHang": "Ngân hàng", "SoTaiKhoan": "Số tài khoản",
                                    "GhiChu": st.column_config.TextColumn("Nội dung đã trao đổi",
                                                                          width="large")})
        ui.download_excel("Tải danh sách hoàn phí", hp[
            ["HoTenHS", "Khoi", "SDT", "TinhTrang", "SoTienXacNhan", "TenChuTaiKhoan", "NganHang",
             "SoTaiKhoan"]], f"HoanPhi_{nam_hoc}.xlsx", key="hp_export")

# ------------------------------------------------------------------ Tổng hợp
with tab_th:
    sm = services.giu_cho_summary(ts)
    with ui.section("Theo khối", "Số học sinh theo tình trạng giữ chỗ và tổng tiền đã xác nhận"):
        st.dataframe(sm.assign(**{"Tiền đã giữ chỗ": sm["Tiền đã giữ chỗ"].map(ui.money)}),
                     hide_index=True, width="stretch")
    detail = giu[["HoTenHS", "Khoi", "CheDo", "SDT", "TrangThai", "SoTienXacNhan",
                  "NguoiXacNhan"]].sort_values(["Khoi", "HoTenHS"])
    with ui.section("Học sinh đã giữ chỗ", f"{len(detail)} học sinh"):
        if detail.empty:
            ui.empty_state("payments", "Chưa có học sinh giữ chỗ")
        else:
            st.dataframe(with_money(detail).assign(Buoc=ui.tag_col(detail["TrangThai"])).drop(
                columns=["TrangThai"]), hide_index=True, width="stretch",
                height=ui.table_height(len(detail), 420),
                column_config={"HoTenHS": "Học sinh", "Khoi": "Khối", "CheDo": "Chế độ",
                               "SDT": "SĐT", "Buoc": ui.status_column(), "SoTienXacNhan": MONEY,
                               "NguoiXacNhan": "Người xác nhận"})

ui.download_excel("Xuất Excel", {"TongHop": sm, "DaGiuCho": detail, "HoanPhi": cho_hoan[
    ["HoTenHS", "Khoi", "SDT", "SoTienXacNhan", "TenChuTaiKhoan", "NganHang", "SoTaiKhoan"]]},
    f"KeToan_GiuCho_{nam_hoc}.xlsx", container=export_slot, key="kt_export")
