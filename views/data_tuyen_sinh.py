"""Data tuyển sinh.

Danh sách (lọc theo bước, tìm kiếm) → chọn dòng mở hồ sơ chi tiết (?id=...).
Thêm liên hệ mới bằng hộp thoại nhập nhanh (?new=1 để mở từ trang khác).
"""
import streamlit as st

from tuyensinh import services, ui
from tuyensinh.schema import CHE_DO, GIU_CHO, KHOI, NHAP_HOC, TRANG_THAI, TUYEN_SINH

S = st.session_state
S.setdefault("ts_v", 0)  # tăng để nạp lại form / xóa lựa chọn trong bảng
qp = st.query_params
nam_hoc = ui.nam_hoc()
storage = ui.storage()
ts = ui.df(TUYEN_SINH, nam_hoc)
F = TUYEN_SINH.get


def open_record(item_id: str):
    qp.clear()
    qp["id"] = item_id


def back_to_list():
    qp.clear()
    S.ts_v += 1


def _find(item_id: str) -> dict | None:
    hit = ts[ts["id"] == item_id]
    if hit.empty:  # có thể thuộc năm học khác
        all_ts = ui.df(TUYEN_SINH)
        hit = all_ts[all_ts["id"] == item_id]
    return hit.iloc[0].to_dict() if len(hit) else None


# ================================================================== hộp thoại
TRUONG_LABELS = {"TruongCu_Tinh": "Tỉnh/Thành phố", "TruongCu_PhuongXa": "Phường/Xã",
                 "TruongCu": "Tên trường"}


@st.dialog("Thêm liên hệ mới", width="large", on_dismiss="rerun")
def new_contact_dialog():
    S.setdefault("new_v", 0)
    prefix = f"new_{S.new_v}"
    record = {"NamHoc": nam_hoc, "NgayLienHe": services.today(), "TrangThai": "Tư vấn",
              "NguoiNhanHoSo": ui.current_user()}
    st.caption("Nhập thông tin tối thiểu để lưu liên hệ. Các thông tin khác bổ sung sau "
               "trong hồ sơ.")
    # Không dùng st.form: ô Phường/Xã và gợi ý trường phải đổi ngay khi chọn Tỉnh
    st.markdown("**Học sinh**")
    values = ui.record_form([F(k) for k in ("HoTenHS", "Khoi", "PhanHe", "GioiTinh")],
                            record, prefix, 4)
    st.markdown("**Liên hệ**")
    values.update(ui.record_form([F(k) for k in ("SDT", "TenLienHe", "Nguon")],
                                 record, prefix, 3))
    values.update(ui.record_form([F(k) for k in ("NgayLienHe", "NamHoc", "CheDo")],
                                 record, prefix, 3))
    st.markdown("**Trường cũ**")
    values.update(ui.record_form([F(k) for k in ("TruongCu_Tinh", "TruongCu_PhuongXa",
                                                 "TruongCu")], record, prefix, 3, TRUONG_LABELS))
    values.update(ui.record_form([F("GhiChu")], record, prefix, 1))
    ui.required_hint()
    c1, c2 = st.columns(2)
    save_open = c1.button("Lưu và mở hồ sơ", type="primary", width="stretch",
                          icon=":material/check:", key=f"{prefix}_save_open")
    save_more = c2.button("Lưu và thêm tiếp", width="stretch", icon=":material/add:",
                          key=f"{prefix}_save_more")
    values.update(TrangThai="Tư vấn", NguoiNhanHoSo=ui.current_user())
    confirmed = S.pop("_dup_confirm", False)
    if not (save_open or save_more or confirmed):
        return
    if not confirmed:
        S.pop("_dup_pending", None)
        dups = services.find_duplicates(storage, values)
        if dups:
            S["_dup_pending"] = (save_open, len(dups))
            st.warning(f"Đã có {len(dups)} liên hệ trùng họ tên và SĐT trong năm học "
                       f"{values.get('NamHoc')}. Bạn vẫn muốn lưu?",
                       icon=":material/content_copy:")
            c1, c2 = st.columns(2)
            c1.button("Vẫn lưu", type="primary", width="stretch",
                      on_click=lambda: S.update(_dup_confirm=True))
            c2.button("Quay lại sửa", width="stretch", on_click=lambda: S.pop("_dup_pending", None))
            return
    rec = ui.mutate(services.save_tuyen_sinh, storage, values,
                    success=f"Đã thêm {values.get('HoTenHS')}")
    if rec is None:
        return
    pending = S.pop("_dup_pending", None)
    open_after = pending[0] if pending else save_open
    S.new_v += 1
    if open_after:
        open_record(rec["id"])
        st.rerun()
    st.rerun(scope="fragment")  # "Lưu và thêm tiếp": giữ hộp thoại, form trống


@st.dialog("Rút hồ sơ")
def withdraw_dialog(rec: dict):
    st.write(f"Chuyển **{rec['HoTenHS']}** sang trạng thái **Rút hồ sơ**.")
    ly_do = st.text_area("Lý do rút hồ sơ *", placeholder="Ví dụ: chuyển sang trường khác gần nhà",
                         help="Được ghi thêm vào mục Nội dung đã trao đổi.")
    if rec.get("GiuCho") == "Đã giữ chỗ":
        st.info("Học sinh đã giữ chỗ. Nhớ báo kế toán đổi Tình trạng sang **Hủy giữ chỗ** "
                "để hoàn phí.", icon=":material/payments:")
    c1, c2 = st.columns(2)
    if c1.button("Xác nhận rút hồ sơ", type="primary", width="stretch", disabled=not ly_do.strip()):
        if ui.mutate(services.set_trang_thai, storage, rec["id"], "Rút hồ sơ", ly_do.strip(),
                     success="Đã chuyển sang Rút hồ sơ") is not None:
            S.ts_v += 1
            st.rerun()
    if c2.button("Hủy", width="stretch"):
        st.rerun()


@st.dialog("Xóa liên hệ")
def delete_dialog(rec: dict):
    st.write(f"Xóa vĩnh viễn **{rec['HoTenHS']}** ({rec['SDT']}) khỏi Data tuyển sinh?")
    st.caption("Không thể hoàn tác. Nếu học sinh chỉ không theo học nữa, hãy dùng **Rút hồ sơ**.")
    c1, c2 = st.columns(2)
    if c1.button("Xóa vĩnh viễn", type="primary", icon=":material/delete:", width="stretch"):
        if ui.mutate(storage.delete_item, TUYEN_SINH.name, rec["id"],
                     success="Đã xóa liên hệ") is not None:
            back_to_list()
            st.rerun()
    if c2.button("Giữ lại", width="stretch"):
        st.rerun()


# ================================================================== chi tiết
def render_detail(item_id: str):
    rec = _find(item_id)
    st.button("Data tuyển sinh", icon=":material/arrow_back:", type="tertiary",
              on_click=back_to_list)
    if rec is None:
        with ui.section():
            ui.empty_state("person_off", "Không tìm thấy học sinh",
                           "Liên hệ có thể đã bị xóa hoặc đường dẫn không đúng.")
        return

    step = rec.get("TrangThai") or "Tư vấn"
    sub = " · ".join(x for x in [f"Khối {rec['Khoi']}" if rec.get("Khoi") else "", rec.get("SDT"),
                                 f"Liên hệ {ui.fmt_date(rec.get('NgayLienHe'))}"] if x)
    actions = ui.page_header(rec["HoTenHS"] or "(Chưa có tên)", sub, eyebrow="Hồ sơ tuyển sinh")
    nxt = ui.next_step(step)
    if nxt:
        label = "Xác nhận nhập học" if nxt == "Nhập học" else f"Chuyển sang {nxt}"
        if actions.button(label, type="primary", icon=ui.STATUS[nxt]["icon"]):
            if ui.mutate(services.set_trang_thai, storage, item_id, nxt, nguoi=ui.current_user(),
                         success=f"Đã chuyển sang {nxt}") is not None:
                if nxt == "Nhập học":
                    st.toast("Đã tạo hồ sơ nhập học. Bổ sung thông tin ở mục Hồ sơ nhập học.",
                             icon=":material/school:")
                S.ts_v += 1
                st.rerun()
    with actions.popover("Thao tác", icon=":material/more_horiz:"):
        other = [s for s in TRANG_THAI if s not in (step, "Rút hồ sơ")]
        st.caption("Đổi bước (sửa nhầm)")
        for s in other:
            if st.button(s, icon=ui.STATUS[s]["icon"], width="stretch", key=f"set_{s}"):
                if ui.mutate(services.set_trang_thai, storage, item_id, s,
                             nguoi=ui.current_user(), success=f"Đã chuyển sang {s}") is not None:
                    S.ts_v += 1
                    st.rerun()
        st.divider()
        if step != "Rút hồ sơ" and st.button("Rút hồ sơ…", icon=":material/block:",
                                              width="stretch"):
            withdraw_dialog(rec)
        if st.button("Xóa liên hệ…", icon=":material/delete:", width="stretch"):
            delete_dialog(rec)

    with st.container(horizontal=True, gap="small"):
        ui.status_badge(step)
        ui.giu_cho_badge(rec.get("GiuCho"))
        st.badge(f"Năm học {rec.get('NamHoc') or '—'}", color="gray",
                 icon=":material/calendar_month:")
    ui.stepper(step)
    if step == "Rút hồ sơ":
        st.caption("Học sinh đã rút hồ sơ. Dùng **Thao tác → Đổi bước** nếu cần khôi phục.")
    st.space("small")

    main, side = st.columns([2.2, 1], gap="medium")
    with main:
        prefix = f"ts_{item_id}_{S.ts_v}"
        values = {}
        with ui.section("Liên hệ & tư vấn"):
            values.update(ui.record_form(
                [F(k) for k in ("NgayLienHe", "SDT", "NamHoc", "Nguon", "TenLienHe",
                                "NguoiGioiThieu", "TinhTrang", "NguoiNhanHoSo")], rec, prefix, 3))
            values.update(ui.record_form([F("GhiChu")], rec, prefix, 1))
        with ui.section("Học sinh"):
            values.update(ui.record_form(
                [F(k) for k in ("HoTenHS", "NgaySinh", "GioiTinh", "Khoi", "PhanHe", "CheDo")],
                rec, prefix, 3))
        with ui.section("Trường cũ & kết quả học tập"):
            values.update(ui.record_form(
                [F(k) for k in ("TruongCu_Tinh", "TruongCu_PhuongXa", "TruongCu")],
                rec, prefix, 3, {"TruongCu_Tinh": "Tỉnh/Thành phố",
                                 "TruongCu_PhuongXa": "Phường/Xã", "TruongCu": "Tên trường"}))
            if rec.get("TruongCu_DiaChiCu"):
                st.caption(f"Địa chỉ trường cũ trước sáp nhập: {rec['TruongCu_DiaChiCu']}")
            short = {"Toan1": "Toán", "Van1": "Văn", "Anh1": "Anh", "TV1": "Tiếng Việt",
                     "HanhKiem1": "Hạnh kiểm", "Toan2": "Toán", "Van2": "Văn",
                     "Anh2": "Anh", "TV2": "Tiếng Việt", "HanhKiem2": "Hạnh kiểm"}
            for n in ("1", "2"):
                st.markdown(f"**Kết quả {n}**")
                keys = [f"Toan{n}", f"Van{n}", f"Anh{n}", f"TV{n}", f"HanhKiem{n}"]
                values.update(ui.record_form([F(k) for k in keys], rec, prefix, 5, short))
        bar = st.container(horizontal=True, vertical_alignment="center")
        submitted = bar.button("Lưu thay đổi", type="primary", icon=":material/save:")
        bar.caption("Các trường có dấu * là bắt buộc.")
        if submitted:
            values["TrangThai"] = step
            values["NamHoc"] = values.get("NamHoc") or nam_hoc
            dups = services.find_duplicates(storage, values, item_id)
            if ui.mutate(services.save_tuyen_sinh, storage, values, item_id,
                         success="Đã lưu thay đổi") is not None:
                if dups:
                    st.toast(f"Lưu ý: có {len(dups)} liên hệ khác trùng họ tên và SĐT.",
                             icon=":material/content_copy:")
                S.ts_v += 1
                st.rerun()

    with side:
        with ui.section("Giữ chỗ"):
            ui.kv([("Giữ chỗ", rec.get("GiuCho") or "Chưa giữ chỗ"),
                   ("Số tiền xác nhận", ui.money(rec.get("SoTienXacNhan"))),
                   ("Người xác nhận", rec.get("NguoiXacNhan")),
                   ("Ngân hàng hoàn phí", rec.get("NganHang"))])
            st.page_link("views/ke_toan.py", label="Mở Kế toán", icon=":material/payments:")
        with ui.section("Hồ sơ nhập học"):
            nh = ui.df(NHAP_HOC)
            mine = nh[nh["TuyenSinhID"] == item_id]
            if mine.empty:
                st.caption("Được tạo tự động khi xác nhận **Nhập học**.")
            else:
                pct = float(services.completeness(mine).iloc[0])
                st.progress(pct, text=f"Hoàn thiện {pct:.0%}")
                st.page_link("views/ho_so_nhap_hoc.py", label="Mở hồ sơ nhập học",
                             icon=":material/assignment_ind:",
                             query_params={"id": mine.iloc[0]["id"]})
        with ui.section("Bản ghi"):
            ui.kv([("Tạo lúc", ui.fmt_date(rec.get("Created"))),
                   ("Cập nhật", ui.fmt_date(rec.get("Modified"))),
                   ("Mã", rec.get("id"))])


# ================================================================== danh sách
FILTER_KEYS = ("ts_q", "ts_khoi", "ts_chedo", "ts_giucho")


def clear_filters():
    S.ts_q = ""
    S.ts_khoi = S.ts_chedo = S.ts_giucho = "Tất cả"


def render_list():
    actions = ui.page_header("Data tuyển sinh", f"Liên hệ, tư vấn và hồ sơ học sinh · "
                             f"năm học {nam_hoc}")
    export_slot = actions.container(width="content")
    add = actions.button("Thêm liên hệ", icon=":material/person_add:", type="primary")

    if ts.empty:
        with ui.section():
            ui.empty_state("person_search", "Chưa có liên hệ nào",
                           f"Năm học {nam_hoc} chưa có dữ liệu. Thêm liên hệ đầu tiên hoặc "
                           "chọn năm học khác ở thanh bên.")
        if add:
            new_contact_dialog()
        return

    counts = ts["TrangThai"].value_counts()
    step = st.segmented_control(
        "Bước", ["Tất cả", *TRANG_THAI], default="Tất cả", required=True, key="ts_step",
        format_func=lambda s: f"{s}  {len(ts) if s == 'Tất cả' else int(counts.get(s, 0))}",
        label_visibility="collapsed")

    for k in FILTER_KEYS:
        S.setdefault(k, "" if k == "ts_q" else "Tất cả")
    c = st.columns([3, 1, 1, 1.2], vertical_alignment="bottom")
    q = c[0].text_input("Tìm kiếm", key="ts_q", icon=":material/search:",
                        placeholder="Tên học sinh, SĐT hoặc tên liên hệ")
    khoi = c[1].selectbox("Khối", ["Tất cả", *KHOI], key="ts_khoi")
    che_do = c[2].selectbox("Chế độ", ["Tất cả", *CHE_DO], key="ts_chedo")
    giu = c[3].selectbox("Giữ chỗ", ["Tất cả", *GIU_CHO], key="ts_giucho")

    view = ts
    if step and step != "Tất cả":
        view = view[view["TrangThai"] == step]
    if khoi != "Tất cả":
        view = view[view["Khoi"] == khoi]
    if che_do != "Tất cả":
        view = view[view["CheDo"] == che_do]
    if giu != "Tất cả":
        view = view[view["GiuCho"].replace("", "Chưa giữ chỗ") == giu]
    if q.strip():
        ql = q.strip().lower()
        phone = services.normalize_phone(q)
        mask = (view["HoTenHS"].str.lower().str.contains(ql, regex=False)
                | view["TenLienHe"].str.lower().str.contains(ql, regex=False))
        if phone:
            mask |= view["SDT"].str.contains(phone, regex=False)
        view = view[mask]
    view = view.sort_values(["NgayLienHe", "id"], ascending=False).reset_index(drop=True)
    filtered = bool(q.strip()) or any(S[k] != "Tất cả" for k in FILTER_KEYS[1:])

    meta = st.container(horizontal=True, vertical_alignment="center")
    meta.caption(f"Hiển thị **{len(view)}** / {len(ts)} học sinh")
    if filtered:
        meta.button("Xóa bộ lọc", icon=":material/filter_alt_off:", type="tertiary",
                    on_click=clear_filters)

    if view.empty:
        with ui.section():
            ui.empty_state("search_off", "Không có học sinh phù hợp",
                           "Thử từ khóa khác hoặc bỏ bớt bộ lọc.")
    else:
        show = view.assign(Buoc=ui.tag_col(view["TrangThai"]),
                           GiuCho=ui.tag_col(view["GiuCho"].replace("", "Chưa giữ chỗ")))
        ev = st.dataframe(
            show[["HoTenHS", "Khoi", "Buoc", "SDT", "NgayLienHe", "CheDo", "GiuCho"]],
            key=f"ts_table_{S.ts_v}", on_select="rerun", selection_mode="single-row",
            hide_index=True, width="stretch", height=ui.table_height(len(show)),
            column_config={
                "HoTenHS": st.column_config.TextColumn("Học sinh", width="medium", pinned=True),
                "Khoi": st.column_config.TextColumn("Khối", width="small"),
                "Buoc": ui.status_column(), "SDT": "SĐT",
                "NgayLienHe": st.column_config.DateColumn("Ngày liên hệ", **ui.DATE_COL),
                "CheDo": "Chế độ", "GiuCho": ui.giu_cho_column(),
            })
        st.caption("Chọn một dòng để mở hồ sơ học sinh.")
        if ev.selection.rows:
            open_record(view.loc[ev.selection.rows[0], "id"])
            st.rerun()

    cols = {f.key: f.label for f in TUYEN_SINH.fields}
    ui.download_excel("Xuất Excel", view[list(cols)].rename(columns=cols),
                      f"DataTuyenSinh_{nam_hoc}.xlsx", container=export_slot, key="ts_export")
    if add:
        new_contact_dialog()


# ================================================================== điều hướng
if qp.get("new"):
    del qp["new"]
    new_contact_dialog()
if qp.get("id"):
    render_detail(qp["id"])
else:
    render_list()
