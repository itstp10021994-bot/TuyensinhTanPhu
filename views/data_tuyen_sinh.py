"""Data tuyển sinh: danh sách HS liên hệ (bên trái) + thông tin chi tiết (bên phải)."""
import streamlit as st

from tuyensinh import services, ui
from tuyensinh.schema import (CHE_DO, G_HOCSINH, G_LIENHE, G_TRUONGCU, KHOI, TRANG_THAI,
                              TUYEN_SINH)

S = st.session_state
S.setdefault("ts_sel", None)       # id đang chọn, "new" khi thêm mới
S.setdefault("ts_table_v", 0)      # đổi key bảng để xóa lựa chọn
nam_hoc = ui.nam_hoc()
storage = ui.storage()
ts = ui.df(TUYEN_SINH, nam_hoc)


def _reset(sel=None):
    S.ts_sel = sel
    S.ts_table_v += 1


left, right = st.columns([1, 1], gap="medium")

# ------------------------------------------------------------------ danh sách
with left:
    f1, f2, f3, f4 = st.columns([2, 2, 2, 1.5], vertical_alignment="bottom")
    lop = f1.selectbox("Lớp", ["Tất cả", *KHOI])
    che_do = f2.selectbox("Chế độ", ["Tất cả", *CHE_DO])
    trang_thai = f3.selectbox("Bước", ["Tất cả", *TRANG_THAI])
    f4.button("Thêm", icon=":material/add:", type="primary", on_click=_reset, args=("new",),
              width="stretch")
    q = st.text_input("Tìm", placeholder="Nhập tên học sinh, SĐT, tên người đăng ký",
                      label_visibility="collapsed")

    view = ts
    if lop != "Tất cả":
        view = view[view["Khoi"] == lop]
    if che_do != "Tất cả":
        view = view[view["CheDo"] == che_do]
    if trang_thai != "Tất cả":
        view = view[view["TrangThai"] == trang_thai]
    if q:
        ql = q.strip().lower()
        mask = (view["HoTenHS"].str.lower().str.contains(ql, regex=False)
                | view["SDT"].str.contains(services.normalize_phone(q) or ql, regex=False)
                | view["TenLienHe"].str.lower().str.contains(ql, regex=False))
        view = view[mask]
    view = view.sort_values(["NgayLienHe", "id"], ascending=False).reset_index(drop=True)

    st.caption(f"{len(view)} / {len(ts)} học sinh")
    event = st.dataframe(
        view[["HoTenHS", "Khoi", "TrangThai", "SDT", "NgayLienHe", "CheDo"]],
        key=f"ts_table_{S.ts_table_v}", on_select="rerun", selection_mode="single-row",
        hide_index=True, width="stretch", height=520,
        column_config={
            "HoTenHS": st.column_config.TextColumn("Tên HS", width="medium"),
            "Khoi": st.column_config.TextColumn("Lớp", width="small"),
            "CheDo": "Chế độ", "SDT": "SĐT",
            "NgayLienHe": st.column_config.DateColumn("Ngày LH", format="DD/MM/YYYY"),
            "TrangThai": "Bước",
        })
    rows = event.selection.rows
    if rows:
        S.ts_sel = view.loc[rows[0], "id"]

# ------------------------------------------------------------------ chi tiết
with right:
    st.markdown("<h5 style='text-align:center'>THÔNG TIN CHI TIẾT HỌC SINH</h5>",
                unsafe_allow_html=True)
    sel = S.ts_sel
    if sel is None:
        st.info("Chọn một học sinh trong danh sách hoặc bấm **Thêm** để thêm liên hệ.")
        st.stop()

    record = {} if sel == "new" else (ts[ts["id"] == sel].iloc[0].to_dict()
                                      if (ts["id"] == sel).any() else None)
    if record is None:
        _reset()
        st.rerun()
    if sel == "new":
        record = {"NamHoc": nam_hoc, "NgayLienHe": services.today(), "TrangThai": "Tư vấn",
                  "NguoiNhanHoSo": ui.current_user()}
    else:
        st.markdown(f"<div class='ts-card'><b>{record['HoTenHS']}</b> — Bước: "
                    f"<b>{record['TrangThai']}</b></div>", unsafe_allow_html=True)

    prefix = f"ts_{sel}_{S.ts_table_v}"  # đổi key để form nạp lại sau khi lưu
    values = {}
    with st.container(height=470):
        for g in (G_LIENHE, G_HOCSINH, G_TRUONGCU):
            st.markdown(f"**{g}**")
            fields = [f for f in TUYEN_SINH.fields if f.group == g]
            main = [f for f in fields if f.type != "note"]
            values.update(ui.record_form(main, record, prefix, 4 if g == G_TRUONGCU else 3))
            values.update(ui.record_form([f for f in fields if f.type == "note"],
                                         record, prefix, 1))
    values["NamHoc"] = values.get("NamHoc") or nam_hoc

    b1, b2, b3 = st.columns(3)
    if b1.button("Lưu chỉnh sửa", icon=":material/save:", type="primary", width="stretch"):
        dups = services.find_duplicates(storage, values, None if sel == "new" else sel)
        try:
            rec = services.save_tuyen_sinh(storage, values, None if sel == "new" else sel)
        except ValueError as e:
            ui.show_errors(e)
        else:
            ui.invalidate()
            if dups:
                st.toast(f"Lưu ý: có {len(dups)} HS trùng tên + SĐT trong năm học", icon="⚠️")
            st.toast("Đã lưu", icon="✅")
            _reset(rec["id"])
            st.rerun()
    b2.button("Đóng", icon=":material/close:", on_click=_reset, width="stretch")

    if sel != "new":
        @st.dialog("Xóa học sinh")
        def _confirm_delete():
            st.write(f"Xóa **{record['HoTenHS']}** khỏi Data tuyển sinh?")
            if st.button("Xóa", type="primary"):
                storage.delete_item(TUYEN_SINH.name, sel)
                ui.invalidate()
                _reset()
                st.rerun()

        if b3.button("Xóa", icon=":material/delete:", width="stretch"):
            _confirm_delete()

        @st.dialog("Rút hồ sơ")
        def _rut_ho_so():
            ly_do = st.text_area("Lý do rút hồ sơ")
            if st.button("Xác nhận rút hồ sơ", type="primary"):
                services.set_trang_thai(storage, sel, "Rút hồ sơ", ly_do)
                ui.invalidate()
                _reset(sel)
                st.rerun()

        st.markdown("###### Cập nhật trạng thái")
        icons = {"Tư vấn": ":material/support_agent:", "Nộp hồ sơ": ":material/upload_file:",
                 "Nhập học": ":material/school:", "Rút hồ sơ": ":material/logout:"}
        for c, tt in zip(st.columns(2) + st.columns(2), TRANG_THAI):
            active = record["TrangThai"] == tt
            if c.button(tt, icon=icons[tt], width="stretch", disabled=active,
                        type="primary" if active else "secondary", key=f"tt_{tt}"):
                if tt == "Rút hồ sơ":
                    _rut_ho_so()
                else:
                    services.set_trang_thai(storage, sel, tt, nguoi=ui.current_user())
                    ui.invalidate()
                    _reset(sel)
                    if tt == "Nhập học":
                        st.toast("Đã tạo hồ sơ nhập học — bổ sung thông tin ở mục "
                                 "Hồ sơ nhập học", icon="🎓")
                    st.rerun()

        tien = record.get("SoTienXacNhan")
        tien = f"{tien:,.0f}đ" if isinstance(tien, float) and tien == tien else "—"
        st.caption(f"Giữ chỗ: **{record.get('TinhTrang') or 'Chưa giữ chỗ'}** · Số tiền xác nhận "
                   f"**{tien}** · Người xác nhận: {record.get('NguoiXacNhan') or '—'}")
