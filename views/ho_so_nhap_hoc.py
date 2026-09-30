"""Hồ sơ nhập học: thông tin đầy đủ theo biểu mẫu VEMIS + xuất Excel."""
from dataclasses import replace
from datetime import date

import streamlit as st

from tuyensinh import export_vemis, services, ui
from tuyensinh.schema import (G_CHUNG, G_DIACHI, G_GIADINH, G_GIAYTO, G_LIENLAC, NHAP_HOC,
                              TUYEN_SINH)

S = st.session_state
S.setdefault("nh_sel", None)
S.setdefault("nh_v", 0)
nam_hoc = ui.nam_hoc()
storage = ui.storage()

# Hồ sơ nhập học được tạo tự động khi HS chuyển sang "Nhập học" ở Data tuyển sinh.
ts = ui.df(TUYEN_SINH, nam_hoc)
nh = ui.df(NHAP_HOC, nam_hoc)
rut = set(ts.loc[ts["TrangThai"] == "Rút hồ sơ", "id"])
nh = nh[~nh["TuyenSinhID"].isin(rut)].reset_index(drop=True)

REQUIRED = [f.key for f in NHAP_HOC.fields if f.required] + [
    "GioiTinh", "DanToc", "ChoO_Tinh", "ChoO_Xa", "NoiSinh_Tinh", "DienThoaiSLL"]


def _missing(row) -> int:
    return sum(1 for k in REQUIRED if row.get(k) in ("", None))


def _reset(sel=None):
    S.nh_sel = sel
    S.nh_v += 1


nh["Thiếu"] = nh.apply(_missing, axis=1)
chua_co = ts[(ts["TrangThai"] == "Nhập học") & ~ts["id"].isin(nh["TuyenSinhID"])]
if len(chua_co):
    c1, c2 = st.columns([4, 1], vertical_alignment="center")
    c1.warning(f"{len(chua_co)} HS đã 'Nhập học' nhưng chưa có hồ sơ.")
    if c2.button("Tạo hồ sơ", icon=":material/sync:"):
        for _, r in chua_co.iterrows():
            services.sync_nhap_hoc(storage, r.to_dict())
        ui.invalidate()
        st.rerun()

left, right = st.columns([2, 5], gap="medium")
with left:
    lops = sorted(x for x in nh["LopHoc"].unique() if x)
    f1, f2 = st.columns([3, 2], vertical_alignment="bottom")
    lop = f1.selectbox("Lớp", ["Tất cả", *lops])
    f2.button("Thêm", icon=":material/add:", on_click=_reset, args=("new",), width="stretch",
              help="Thêm HS nhập học không qua Data tuyển sinh")
    q = st.text_input("Tìm", placeholder="Tên HS / mã HS", label_visibility="collapsed")
    view = nh if lop == "Tất cả" else nh[nh["LopHoc"] == lop]
    if q:
        ql = q.strip().lower()
        view = view[view["HoTen"].str.lower().str.contains(ql, regex=False)
                    | view["MaHocSinh"].str.lower().str.contains(ql, regex=False)]
    view = view.sort_values(["LopHoc", "HoTen"]).reset_index(drop=True)
    event = st.dataframe(
        view[["HoTen", "LopHoc", "Thiếu"]], key=f"nh_table_{S.nh_v}", on_select="rerun",
        selection_mode="single-row", hide_index=True, width="stretch", height=480,
        column_config={"HoTen": "Họ và tên", "LopHoc": "Lớp",
                       "Thiếu": st.column_config.NumberColumn(
                           "Thiếu", help="Số thông tin quan trọng còn trống")})
    if event.selection.rows:
        S.nh_sel = view.loc[event.selection.rows[0], "id"]

    st.download_button(
        f"Xuất Excel VEMIS ({len(view)} HS)", export_vemis.to_bytes(view),
        file_name=f"DanhSachHocSinh_{nam_hoc}_{lop if lop != 'Tất cả' else 'TatCa'}.xlsx",
        icon=":material/download:", width="stretch", type="primary",
        mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")

with right:
    sel = S.nh_sel
    if sel is None:
        st.info("Chọn học sinh bên trái để xem / bổ sung hồ sơ nhập học.")
        st.stop()
    if sel == "new":
        record = {"NamHoc": nam_hoc, "QuocTich": "Việt Nam", "DanToc": "Kinh",
                  "TonGiao": "Không", "DienChinhSach": "Không",
                  "NgayVaoTruong": date.today().isoformat()}
    elif (nh["id"] == sel).any():
        record = nh[nh["id"] == sel].iloc[0].to_dict()
    else:
        _reset()
        st.rerun()

    st.markdown(f"<h5>{record.get('HoTen') or 'Học sinh mới'}"
                f"{' — Lớp ' + record['LopHoc'] if record.get('LopHoc') else ''}</h5>",
                unsafe_allow_html=True)
    prefix = f"nh_{sel}_{S.nh_v}"
    values = {"NamHoc": record.get("NamHoc") or nam_hoc,
              "TuyenSinhID": record.get("TuyenSinhID", "")}
    groups = [G_CHUNG, G_DIACHI, G_GIAYTO, G_GIADINH, G_LIENLAC]
    for tab, g in zip(st.tabs(groups), groups):
        with tab:
            fields = [f for f in NHAP_HOC.fields if f.group == g]
            if g == G_DIACHI:
                # 4 cột cho các nhóm địa chỉ (SN, KDC, Tỉnh, Xã)
                for title, keys in [
                    ("Chỗ ở hiện nay", ["ChoO_SoNha", "ChoO_KhuDanCu", "ChoO_Tinh", "ChoO_Xa"]),
                    ("Hộ khẩu thường trú", ["HK_SoNha", "HK_KhuDanCu", "HK_Tinh", "HK_Xa"]),
                    ("Nơi sinh", ["NoiSinh_ThongTin", "NoiSinh_Tinh", "NoiSinh_Xa"]),
                    ("Quê quán", ["QueQuan_ThongTin", "QueQuan_Tinh", "QueQuan_Xa"]),
                    ("Nơi khai sinh", ["NoiKS_Tinh", "NoiKS_Xa"]),
                ]:
                    st.markdown(f"**{title}**")
                    fs = [replace(NHAP_HOC.get(k), label=NHAP_HOC.get(k).label.split(" - ")[-1])
                          for k in keys]
                    values.update(ui.record_form(fs, record, prefix, 4))
            else:
                values.update(ui.record_form(fields, record, prefix, 3))

    b1, b2, b3 = st.columns(3)
    if b1.button("Lưu hồ sơ", icon=":material/save:", type="primary", width="stretch"):
        try:
            rec = services.save_nhap_hoc(storage, values, None if sel == "new" else sel)
        except ValueError as e:
            ui.show_errors(e)
        else:
            ui.invalidate()
            st.toast("Đã lưu hồ sơ", icon="✅")
            _reset(rec["id"])
            st.rerun()
    b2.button("Đóng", icon=":material/close:", on_click=_reset, width="stretch")
    if sel != "new" and not record.get("TuyenSinhID"):
        if b3.button("Xóa hồ sơ", icon=":material/delete:", width="stretch"):
            storage.delete_item(NHAP_HOC.name, sel)
            ui.invalidate()
            _reset()
            st.rerun()
