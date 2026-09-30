"""Hồ sơ nhập học: thông tin đầy đủ theo biểu mẫu VEMIS + xuất Excel.

Danh sách (mức hoàn thiện) → chọn dòng mở hồ sơ (?id=...). Hồ sơ được tạo tự động khi
học sinh được xác nhận "Nhập học" ở Data tuyển sinh.
"""
from dataclasses import replace
from datetime import date

import streamlit as st

from tuyensinh import export_vemis, services, ui
from tuyensinh.schema import (G_CHUNG, G_DIACHI, G_GIADINH, G_GIAYTO, G_LIENLAC, NHAP_HOC,
                              TUYEN_SINH)

S = st.session_state
S.setdefault("nh_v", 0)
qp = st.query_params
nam_hoc = ui.nam_hoc()
storage = ui.storage()
F = NHAP_HOC.get

ts = ui.df(TUYEN_SINH, nam_hoc)
nh = ui.df(NHAP_HOC, nam_hoc)
rut = set(ts.loc[ts["TrangThai"] == "Rút hồ sơ", "id"])
nh = nh[~nh["TuyenSinhID"].isin(rut)].reset_index(drop=True)
nh["HoanThien"] = (services.completeness(nh) * 100).round() if len(nh) else []


def open_record(item_id: str):
    qp.clear()
    qp["id"] = item_id


def back_to_list():
    qp.clear()
    S.nh_v += 1


# ================================================================== chi tiết
ADDRESS = [
    ("Chỗ ở hiện nay", ["ChoO_SoNha", "ChoO_KhuDanCu", "ChoO_Tinh", "ChoO_Xa"]),
    ("Hộ khẩu thường trú", ["HK_SoNha", "HK_KhuDanCu", "HK_Tinh", "HK_Xa"]),
    ("Nơi sinh", ["NoiSinh_ThongTin", "NoiSinh_Tinh", "NoiSinh_Xa"]),
    ("Quê quán", ["QueQuan_ThongTin", "QueQuan_Tinh", "QueQuan_Xa"]),
    ("Nơi khai sinh", ["NoiKS_Tinh", "NoiKS_Xa"]),
]


@st.dialog("Xóa hồ sơ nhập học")
def delete_dialog(rec: dict):
    st.write(f"Xóa vĩnh viễn hồ sơ của **{rec.get('HoTen')}**?")
    st.caption("Không thể hoàn tác.")
    c1, c2 = st.columns(2)
    if c1.button("Xóa vĩnh viễn", type="primary", icon=":material/delete:", width="stretch"):
        if ui.mutate(storage.delete_item, NHAP_HOC.name, rec["id"], success="Đã xóa hồ sơ") \
                is not None:
            back_to_list()
            st.rerun()
    if c2.button("Giữ lại", width="stretch"):
        st.rerun()


def render_detail(item_id: str):
    st.button("Hồ sơ nhập học", icon=":material/arrow_back:", type="tertiary",
              on_click=back_to_list)
    if item_id == "new":
        rec = {"NamHoc": nam_hoc, "QuocTich": "Việt Nam", "DanToc": "Kinh", "TonGiao": "Không",
               "DienChinhSach": "Không", "NgayVaoTruong": date.today().isoformat()}
    else:
        hit = ui.df(NHAP_HOC)
        hit = hit[hit["id"] == item_id]
        if hit.empty:
            with ui.section():
                ui.empty_state("person_off", "Không tìm thấy hồ sơ",
                               "Hồ sơ có thể đã bị xóa hoặc đường dẫn không đúng.")
            return
        rec = hit.iloc[0].to_dict()
        # Hồ sơ tạo trước khi có cột Trường cũ: lấy từ Data tuyển sinh (lưu khi bấm Lưu)
        src = ts[ts["id"] == rec.get("TuyenSinhID")]
        if len(src):
            for k in ("TruongCu", "TruongCu_QuanHuyen", "TruongCu_Tinh"):
                if not rec.get(k):
                    rec[k] = src.iloc[0].get(k, "")

    title = rec.get("HoTen") or "Hồ sơ mới"
    sub = " · ".join(x for x in [f"Lớp {rec['LopHoc']}" if rec.get("LopHoc") else "",
                                 f"Sinh ngày {ui.fmt_date(rec.get('NgaySinh'))}"
                                 if rec.get("NgaySinh") else "",
                                 f"Năm học {rec.get('NamHoc')}"] if x)
    actions = ui.page_header(title, sub, eyebrow="Hồ sơ nhập học")
    save_top = actions.button("Lưu hồ sơ", type="primary", icon=":material/save:", key="save_top")
    if item_id != "new":
        with actions.popover("Thao tác", icon=":material/more_horiz:"):
            if rec.get("TuyenSinhID"):
                st.page_link("views/data_tuyen_sinh.py", label="Xem liên hệ tuyển sinh",
                             icon=":material/person_search:",
                             query_params={"id": rec["TuyenSinhID"]})
            st.download_button("Xuất Excel VEMIS (1 HS)",
                               lambda: export_vemis.to_bytes(hit),
                               file_name=f"VEMIS_{title}.xlsx", mime=ui.XLSX, on_click="ignore",
                               icon=":material/download:", width="stretch")
            if not rec.get("TuyenSinhID") and st.button("Xóa hồ sơ…", icon=":material/delete:",
                                                        width="stretch"):
                delete_dialog(rec)

    missing = services.missing_fields(rec) if item_id != "new" else []
    if item_id != "new":
        pct = 1 - len(missing) / len(services.NHAP_HOC_CAN_CO)
        with st.container(border=True):
            c1, c2 = st.columns([1, 2], vertical_alignment="center")
            c1.progress(pct, text=f"Hoàn thiện **{pct:.0%}** thông tin tối thiểu")
            if missing:
                c2.caption("Còn thiếu: " + ", ".join(services.NHAP_HOC_NHAN_NGAN[k]
                                                    for k in missing))
            else:
                c2.caption("Đủ thông tin tối thiểu để xuất lên VEMIS.")

    prefix = f"nh_{item_id}_{S.nh_v}"
    values = {"TuyenSinhID": rec.get("TuyenSinhID", "")}
    groups = [G_CHUNG, G_DIACHI, G_GIAYTO, G_GIADINH, G_LIENLAC]
    tabs = st.tabs([f"{g} ({sum(1 for k in missing if F(k).group == g)})"
                    if any(F(k).group == g for k in missing) else g for g in groups])
    for tab, g in zip(tabs, groups):
        with tab, st.container(border=True):
            if g == G_DIACHI:
                for i, (title_g, keys) in enumerate(ADDRESS):
                    if i:
                        st.divider()
                    st.markdown(f"**{title_g}**")
                    fs = [replace(F(k), label=F(k).label.split(" - ")[-1]) for k in keys]
                    values.update(ui.record_form(fs, rec, prefix, 4))
                st.caption("Chọn Tỉnh/Tp trước để hiện danh sách Xã/Phường tương ứng.")
            elif g == G_GIADINH:
                for who, keys in [("Cha", ["TenCha", "NamSinhCha", "NgheNghiepCha", "CanCuocCha",
                                           "DonViCongTacCha"]),
                                  ("Mẹ", ["TenMe", "NamSinhMe", "NgheNghiepMe", "CanCuocMe",
                                          "DonViCongTacMe"])]:
                    st.markdown(f"**{who}**")
                    values.update(ui.record_form([F(k) for k in keys], rec, prefix, 3))
            elif g == G_GIAYTO:
                values.update(ui.record_form(
                    [F(k) for k in ("CanCuoc", "NgayCapCanCuoc", "NoiCapCanCuoc",
                                    "DienChinhSach", "KhuyetTat", "NoiTruBanTru")], rec, prefix, 3))
                st.markdown("**Đối tượng**")
                values.update(ui.record_form([F(k) for k in ("CanNgheo", "DoanVien", "DoiVien")],
                                             rec, prefix, 3))
            else:
                values.update(ui.record_form([f for f in NHAP_HOC.fields if f.group == g],
                                             rec, prefix, 3))
    bar = st.container(horizontal=True, vertical_alignment="center")
    save_bottom = bar.button("Lưu hồ sơ", type="primary", icon=":material/save:", key="save_bot")
    bar.caption("Các trường có dấu * là bắt buộc.")

    if save_top or save_bottom:
        values["NamHoc"] = values.get("NamHoc") or nam_hoc
        res = ui.mutate(services.save_nhap_hoc, storage, values,
                        None if item_id == "new" else item_id, success="Đã lưu hồ sơ")
        if res is not None:
            S.nh_v += 1
            if item_id == "new":
                open_record(res["id"])
            st.rerun()


# ================================================================== danh sách
def render_list():
    actions = ui.page_header("Hồ sơ nhập học",
                             f"Thông tin học sinh theo biểu mẫu VEMIS · năm học {nam_hoc}")
    export_slot = actions.container(width="content")
    actions.button("Thêm hồ sơ", icon=":material/add:", on_click=open_record, args=("new",),
                   help="Thêm học sinh nhập học không qua Data tuyển sinh")

    chua_co = ts[(ts["TrangThai"] == "Nhập học") & ~ts["id"].isin(nh["TuyenSinhID"])]
    if len(chua_co):
        with st.container(border=True):
            c1, c2 = st.columns([4, 1], vertical_alignment="center")
            c1.markdown(f":material/info: **{len(chua_co)} học sinh** đã xác nhận nhập học "
                        "nhưng chưa có hồ sơ.")
            if c2.button("Tạo hồ sơ", icon=":material/sync:", width="stretch"):
                def _sync_all():
                    for _, r in chua_co.iterrows():
                        services.sync_nhap_hoc(storage, r.to_dict())
                if ui.mutate(_sync_all, success=f"Đã tạo {len(chua_co)} hồ sơ") is not None:
                    st.rerun()

    if nh.empty:
        with ui.section():
            ui.empty_state("assignment_ind", "Chưa có hồ sơ nhập học",
                           "Hồ sơ được tạo tự động khi xác nhận Nhập học ở Data tuyển sinh.")
            _, c, _ = st.columns([2, 1, 2])
            c.page_link("views/data_tuyen_sinh.py", label="Đến Data tuyển sinh",
                        icon=":material/arrow_forward:")
        return

    du = int((nh["HoanThien"] >= 100).sum())
    k = ui.kpi_row(3)
    ui.kpi(k[0], "Học sinh nhập học", len(nh))
    ui.kpi(k[1], "Hồ sơ đủ thông tin", du, f"{du / len(nh):.0%}")
    ui.kpi(k[2], "Còn thiếu thông tin", len(nh) - du,
           help="Thiếu ít nhất một thông tin tối thiểu để xuất VEMIS")

    c = st.columns([3, 1, 1.4], vertical_alignment="bottom")
    q = c[0].text_input("Tìm kiếm", icon=":material/search:", placeholder="Tên học sinh hoặc mã HS",
                        key="nh_q")
    lops = sorted(x for x in nh["LopHoc"].unique() if x)
    lop = c[1].selectbox("Lớp", ["Tất cả", *lops], key="nh_lop")
    tt = c[2].segmented_control("Tình trạng hồ sơ", ["Tất cả", "Còn thiếu", "Đủ"],
                                default="Tất cả", required=True, key="nh_tt")
    view = nh if lop == "Tất cả" else nh[nh["LopHoc"] == lop]
    if tt == "Còn thiếu":
        view = view[view["HoanThien"] < 100]
    elif tt == "Đủ":
        view = view[view["HoanThien"] >= 100]
    if q.strip():
        ql = q.strip().lower()
        view = view[view["HoTen"].str.lower().str.contains(ql, regex=False)
                    | view["MaHocSinh"].str.lower().str.contains(ql, regex=False)]
    view = view.sort_values(["LopHoc", "HoTen"]).reset_index(drop=True)

    st.caption(f"Hiển thị **{len(view)}** / {len(nh)} hồ sơ")
    if view.empty:
        with ui.section():
            ui.empty_state("search_off", "Không có hồ sơ phù hợp", "Thử từ khóa hoặc bộ lọc khác.")
    else:
        show = view.assign(ConThieu=view.apply(
            lambda r: ", ".join(services.NHAP_HOC_NHAN_NGAN[k]
                                for k in services.missing_fields(r)), axis=1))
        ev = st.dataframe(
            show[["HoTen", "LopHoc", "NgaySinh", "GioiTinh", "DienThoaiSLL", "HoanThien",
                  "ConThieu"]],
            key=f"nh_table_{S.nh_v}", on_select="rerun", selection_mode="single-row",
            hide_index=True, width="stretch", height=ui.table_height(len(show)),
            column_config={
                "HoTen": st.column_config.TextColumn("Học sinh", width="medium", pinned=True),
                "LopHoc": st.column_config.TextColumn("Lớp", width="small"),
                "NgaySinh": st.column_config.DateColumn("Ngày sinh", **ui.DATE_COL),
                "GioiTinh": "Giới tính", "DienThoaiSLL": "SĐT liên lạc",
                "HoanThien": st.column_config.ProgressColumn(
                    "Hoàn thiện", format="%d%%", min_value=0, max_value=100, width="small"),
                "ConThieu": st.column_config.TextColumn("Còn thiếu", width="large"),
            })
        st.caption("Chọn một dòng để mở hồ sơ.")
        if ev.selection.rows:
            open_record(view.loc[ev.selection.rows[0], "id"])
            st.rerun()

    export = view.drop(columns=["HoanThien"])
    export_slot.download_button(
        f"Xuất VEMIS ({len(view)})", lambda: export_vemis.to_bytes(export),
        file_name=f"DanhSachHocSinh_{nam_hoc}_{lop if lop != 'Tất cả' else 'TatCa'}.xlsx",
        mime=ui.XLSX, icon=":material/download:", on_click="ignore", disabled=view.empty,
        help="Tải file Excel đúng biểu mẫu Danh sách học sinh (VEMIS) theo bộ lọc hiện tại")


if qp.get("id"):
    render_detail(qp["id"])
else:
    render_list()
