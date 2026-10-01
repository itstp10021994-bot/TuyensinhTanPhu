"""Data tuyển sinh — bố cục như app cũ: danh sách thẻ bên trái, chi tiết bên phải.

Lọc theo bước / khối / chế độ / giữ chỗ, tìm kiếm; học sinh đang chọn nằm ở ?id=...
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
        dups = services.find_duplicates(ui.records(TUYEN_SINH), values)
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


# ================================================================== thẻ danh sách (trái)
STEP_COLOR = {s: ui.STATUS[s]["hex"] for s in TRANG_THAI if "hex" in ui.STATUS.get(s, {})}


def set_step(item_id: str, step: str):
    if ui.mutate(services.set_trang_thai, storage, item_id, step, nguoi=ui.current_user(),
                 success=f"Đã chuyển sang {step}") is not None:
        if step == "Nhập học":
            st.toast("Đã tạo hồ sơ nhập học. Bổ sung thông tin ở mục Hồ sơ nhập học.",
                     icon=":material/school:")
        S.ts_v += 1
        st.rerun()


def card(r: dict, selected: bool):
    rid = r["id"]
    step = r["TrangThai"] or "Tư vấn"
    with ui.card_box(rid, selected):
        st.button(r["HoTenHS"] or "(Chưa có tên)", key=f"name_{rid}", on_click=open_record,
                  args=(rid,))
        color = STEP_COLOR.get(step, "#6B7280")
        giu = r["GiuCho"] or "Chưa giữ chỗ"
        st.html(
            f'<p class="tp-card"><span class="k">Khối:</span> <b>{r["Khoi"] or "—"}</b>'
            + (f'-{r["PhanHe"]}' if r["PhanHe"] else "")
            + f' &nbsp;·&nbsp; <span class="k">Chế độ:</span> <b>{r["CheDo"] or "—"}</b>'
            f' &nbsp;·&nbsp; <span class="k">SĐT:</span> <b>{r["SDT"] or "—"}</b><br>'
            f'<span class="k">Bước:</span> <b style="color:{color}">{step}</b>'
            f' &nbsp;·&nbsp; <span class="k">Liên hệ:</span> {ui.fmt_date(r["NgayLienHe"])}'
            f' &nbsp;·&nbsp; <span class="k">{giu}</span></p>')
        act = st.container(horizontal=True, gap="small")
        nxt = ui.next_step(step)
        if nxt and act.button(f"→ {nxt}", key=f"nxt_{rid}",
                              help="Xác nhận nhập học" if nxt == "Nhập học" else None):
            set_step(rid, nxt)
        if step != "Rút hồ sơ" and act.button("Rút HS", key=f"rut_{rid}"):
            withdraw_dialog(r)
        if act.button("Xóa", key=f"xoa_{rid}"):
            delete_dialog(r)


# ================================================================== chi tiết (phải)
def render_right(item_id: str | None):
    h2 = ui.detail_head("Thông tin chi tiết học sinh", "ts")
    save_top = h2.button("Lưu thay đổi", icon=":material/save:", key="ts_save_top",
                         width="stretch", disabled=not item_id)
    if not item_id:
        with st.container(border=True, height=700):
            ui.empty_state("touch_app", "Chọn một học sinh",
                           "Bấm vào tên học sinh ở danh sách bên trái để xem, tư vấn và cập nhật.")
        return
    rec = _find(item_id)
    if rec is None:
        with st.container(border=True):
            ui.empty_state("person_off", "Không tìm thấy học sinh",
                           "Liên hệ có thể đã bị xóa hoặc thuộc năm học khác.")
        return

    step = rec.get("TrangThai") or "Tư vấn"
    with st.container(border=True):
        t1, t2 = st.columns([3, 1.3], vertical_alignment="center")
        sub = " · ".join(x for x in [f"Khối {rec['Khoi']}" if rec.get("Khoi") else "",
                                     rec.get("SDT"), rec.get("CheDo"),
                                     f"Liên hệ {ui.fmt_date(rec.get('NgayLienHe'))}"] if x)
        t1.markdown(f"**{rec['HoTenHS'] or '(Chưa có tên)'}**  \n:gray[{sub}]")
        with t2.popover("Thao tác", icon=":material/more_horiz:", width="stretch"):
            st.caption("Đổi bước (sửa nhầm)")
            for s in [s for s in TRANG_THAI if s not in (step, "Rút hồ sơ")]:
                if st.button(s, icon=ui.STATUS[s]["icon"], width="stretch", key=f"set_{s}"):
                    set_step(item_id, s)
            st.divider()
            if step != "Rút hồ sơ" and st.button("Rút hồ sơ…", icon=":material/block:",
                                                  width="stretch"):
                withdraw_dialog(rec)
            if st.button("Xóa liên hệ…", icon=":material/delete:", width="stretch"):
                delete_dialog(rec)
        ui.stepper(step)
        nxt = ui.next_step(step)
        if nxt:
            label = "Xác nhận nhập học" if nxt == "Nhập học" else f"Chuyển sang {nxt}"
            if st.button(label, type="primary", icon=ui.STATUS[nxt]["icon"], key="ts_next"):
                set_step(item_id, nxt)
        elif step == "Rút hồ sơ":
            st.caption("Học sinh đã rút hồ sơ. Dùng **Thao tác → Đổi bước** nếu cần khôi phục.")

    prefix = f"ts_{item_id}_{S.ts_v}"
    values = {}
    tabs = st.tabs(["Liên hệ & tư vấn", "Học sinh", "Trường cũ & kết quả", "Giữ chỗ & hồ sơ"])
    with tabs[0], st.container(border=True):
        values.update(ui.record_form(
            [F(k) for k in ("NgayLienHe", "SDT", "NamHoc", "Nguon", "TenLienHe",
                            "NguoiGioiThieu", "TinhTrang", "NguoiNhanHoSo")], rec, prefix, 3))
        values.update(ui.record_form([F("GhiChu")], rec, prefix, 1))
    with tabs[1], st.container(border=True):
        values.update(ui.record_form(
            [F(k) for k in ("HoTenHS", "NgaySinh", "GioiTinh", "Khoi", "PhanHe", "CheDo")],
            rec, prefix, 3))
    with tabs[2], st.container(border=True):
        values.update(ui.record_form(
            [F(k) for k in ("TruongCu_Tinh", "TruongCu_PhuongXa", "TruongCu")],
            rec, prefix, 3, TRUONG_LABELS))
        if rec.get("TruongCu_DiaChiCu"):
            st.caption(f"Địa chỉ trường cũ trước sáp nhập: {rec['TruongCu_DiaChiCu']}")
        short = {"Toan1": "Toán", "Van1": "Văn", "Anh1": "Anh", "TV1": "Tiếng Việt",
                 "HanhKiem1": "Hạnh kiểm", "Toan2": "Toán", "Van2": "Văn",
                 "Anh2": "Anh", "TV2": "Tiếng Việt", "HanhKiem2": "Hạnh kiểm"}
        for n in ("1", "2"):
            st.markdown(f"**Kết quả {n}**")
            keys = [f"Toan{n}", f"Van{n}", f"Anh{n}", f"TV{n}", f"HanhKiem{n}"]
            values.update(ui.record_form([F(k) for k in keys], rec, prefix, 5, short))
    with tabs[3], st.container(border=True):
        c1, c2 = st.columns(2, gap="medium")
        with c1:
            st.markdown("**Giữ chỗ**")
            ui.kv([("Giữ chỗ", rec.get("GiuCho") or "Chưa giữ chỗ"),
                   ("Số tiền xác nhận", ui.money(rec.get("SoTienXacNhan"))),
                   ("Người xác nhận", rec.get("NguoiXacNhan")),
                   ("Ngân hàng hoàn phí", rec.get("NganHang"))])
            ui.page_link("views/ke_toan.py", label="Mở Kế toán", icon=":material/payments:")
        with c2:
            st.markdown("**Hồ sơ nhập học**")
            nh = ui.df(NHAP_HOC)
            mine = nh[nh["TuyenSinhID"] == item_id]
            if mine.empty:
                st.caption("Được tạo tự động khi xác nhận **Nhập học**.")
            else:
                pct = float(services.completeness(mine).iloc[0])
                st.progress(pct, text=f"Hoàn thiện {pct:.0%}")
                ui.page_link("views/ho_so_nhap_hoc.py", label="Mở hồ sơ nhập học",
                             icon=":material/assignment_ind:",
                             query_params={"id": mine.iloc[0]["id"]})
            ui.kv([("Tạo lúc", ui.fmt_date(rec.get("Created"))),
                   ("Cập nhật", ui.fmt_date(rec.get("Modified")))])

    save_bottom = st.button("Lưu thay đổi", type="primary", icon=":material/save:",
                            key="ts_save_bot", width="stretch")
    if save_top or save_bottom:
        values["TrangThai"] = step
        values["NamHoc"] = values.get("NamHoc") or nam_hoc
        dups = services.find_duplicates(ui.records(TUYEN_SINH), values, item_id)
        if ui.mutate(services.save_tuyen_sinh, storage, values, item_id,
                     success="Đã lưu thay đổi") is not None:
            if dups:
                st.toast(f"Lưu ý: có {len(dups)} liên hệ khác trùng họ tên và SĐT.",
                         icon=":material/content_copy:")
            S.ts_v += 1
            st.rerun()


# ================================================================== trang
FILTER_KEYS = ("ts_q", "ts_khoi", "ts_chedo", "ts_giucho")


def clear_filters():
    S.ts_q = ""
    S.ts_khoi = S.ts_chedo = S.ts_giucho = "Tất cả"


def filters(step: str):
    for k in FILTER_KEYS:
        S.setdefault(k, "" if k == "ts_q" else "Tất cả")
    q = st.text_input("Tìm kiếm", key="ts_q", icon=":material/search:",
                      label_visibility="collapsed",
                      placeholder="Nhập tên học sinh, SĐT, tên người liên hệ")
    c = st.columns(3, gap="small")
    khoi = c[0].selectbox("Khối", ["Tất cả", *KHOI], key="ts_khoi")
    che_do = c[1].selectbox("Chế độ", ["Tất cả", *CHE_DO], key="ts_chedo")
    giu = c[2].selectbox("Giữ chỗ", ["Tất cả", *GIU_CHO], key="ts_giucho")
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
        phone = services.phone_query(q)
        mask = (view["HoTenHS"].str.lower().str.contains(ql, regex=False)
                | view["TenLienHe"].str.lower().str.contains(ql, regex=False))
        if phone:
            mask |= view["SDT"].str.contains(phone, regex=False)
        view = view[mask]
    if bool(q.strip()) or any(S[k] != "Tất cả" for k in FILTER_KEYS[1:]):
        st.button("Xóa bộ lọc", icon=":material/filter_alt_off:", type="tertiary",
                  on_click=clear_filters)
    return (view.sort_values(["NgayLienHe", "id"], ascending=False).reset_index(drop=True),
            (step, q, khoi, che_do, giu))


def render_page():
    actions = ui.page_header("Data tuyển sinh", f"Năm học {nam_hoc}")
    export_slot = actions.container(width="content")
    add = actions.button("Thêm liên hệ", icon=":material/person_add:", type="primary")
    if add:
        new_contact_dialog()

    counts = ts["TrangThai"].value_counts()
    step = st.segmented_control(
        "Bước", ["Tất cả", *TRANG_THAI], default="Tất cả", required=True, key="ts_step",
        format_func=lambda s: f"{s}  {len(ts) if s == 'Tất cả' else int(counts.get(s, 0))}",
        label_visibility="collapsed")

    left, right = st.columns([1, 1.45], gap="medium")
    with left:
        if ts.empty:
            ui.empty_state("person_search", "Chưa có liên hệ nào",
                           f"Năm học {nam_hoc} chưa có dữ liệu. Bấm **Thêm liên hệ** hoặc chọn "
                           "năm học khác ở thanh trên.")
            view = ts
        else:
            view, fstate = filters(step)
            ui.card_list(view, "ts", card, qp.get("id"), filter_state=fstate)
    with right:
        render_right(qp.get("id"))

    cols = {f.key: f.label for f in TUYEN_SINH.fields}
    ui.download_excel("Xuất Excel", view[list(cols)].rename(columns=cols),
                      f"DataTuyenSinh_{nam_hoc}.xlsx", container=export_slot, key="ts_export")


# ================================================================== điều hướng
if qp.get("new"):
    del qp["new"]
    new_contact_dialog()
render_page()
