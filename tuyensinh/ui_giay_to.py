"""Cấu hình loại giấy tờ cần thu theo khối (list DanhMuc_GiayTo) — dùng chung cho trang
"Giấy tờ cần thu" (bộ phận Tuyển sinh) và Cài đặt → Danh mục.

Bảng ma trận: mỗi dòng một loại giấy tờ, mỗi cột một khối (kèm phân hệ IEP/ESL); tick ô = khối
đó phải nộp. Thứ tự dòng = thứ tự hiện khi thu hồ sơ. Chỉ học sinh mới (nhập từ Data tuyển
sinh) phải nộp; học sinh cũ lên lớp không tính.
"""
from __future__ import annotations

import pandas as pd
import streamlit as st

from . import config, importer, services, ui
from .schema import GIAY_TO, GIAY_TO_NHAP_HOC


def _khoi_key(k: str):
    a, _, b = k.partition("-")
    return (int(a) if a.isdigit() else 99, b)


def _ma_tran(bang: dict[str, list[str]], khois: list[str], them: list[str]) -> pd.DataFrame:
    giay = list(dict.fromkeys([*GIAY_TO_NHAP_HOC, *[g for k in khois for g in bang.get(k, [])],
                               *them]))
    return pd.DataFrame([{"Giấy tờ": g, **{k: g in bang.get(k, []) for k in khois}}
                         for g in giay])


def _tao_list(storage, ten_list: str, err: str) -> bool:
    """List chưa có / lỗi đọc: hiện thông báo + nút tạo. Trả về True nếu đọc được list."""
    if err and "does not exist" not in err and "404" not in err:
        st.error(f"Không đọc được list **{ten_list}** (lỗi kết nối) — app tạm dùng danh mục mặc "
                 "định, chưa lưu được. Bấm ⟳ trên thanh menu để thử lại.",
                 icon=":material/cloud_off:")
        if ui.is_admin():
            with st.expander("Chi tiết lỗi"):
                st.code(ui.an_bi_mat(err[:1500]), language=None)
        return False
    if err:
        c1, c2 = st.columns([3, 1.2], vertical_alignment="center")
        c1.warning(f"Chưa có list **{ten_list}** trên SharePoint — app đang dùng danh mục mặc "
                   "định (Book1). Bấm nút bên cạnh để tạo list (làm một lần), sau đó chỉnh tại "
                   "đây.", icon=":material/info:")
        if c2.button("Tạo list giấy tờ", type="primary", icon=":material/playlist_add:",
                     width="stretch", key="gt_tao"):
            with st.status("Đang tạo list…", expanded=True) as stt:
                try:
                    importer.setup_lists(storage, log=stt.write, lists=[GIAY_TO])
                    stt.write("Chép danh mục mặc định (Book1)…")
                    for k, v in services.giay_to_mac_dinh().items():
                        services.luu_giay_to_khoi(storage, k, v, [])
                    stt.update(label="Đã tạo list và chép danh mục", state="complete")
                except Exception as e:  # noqa: BLE001
                    stt.update(label="Không tạo được list", state="error")
                    ui.error_state(e, compact=True)
                    return False
            ui.refresh()
            st.rerun()
        return False
    return True


def luu_ma_tran(storage, sua: pd.DataFrame, khois: list[str], bang_sp: dict,
                items: list[dict]) -> int:
    """Ghi các khối khác với SharePoint (lần đầu: ghi đủ mọi khối). Khối bỏ tick hết = xóa."""
    n = 0
    for k in khois:
        ds = [str(g).strip() for g, c in zip(sua["Giấy tờ"], sua[k]) if c and str(g).strip()]
        if not bang_sp or ds != bang_sp.get(k, []):
            services.luu_giay_to_khoi(storage, k, ds, items)
            n += 1
    return n


def render(storage, key: str = "gt"):
    items = ui.records(GIAY_TO, optional=True)
    err = ui.list_error(GIAY_TO)
    bang_sp = services.giay_to_tu_list(items)
    bang = bang_sp or services.giay_to_mac_dinh()
    ten_list = config.list_name(GIAY_TO.name)
    doc_duoc = _tao_list(storage, ten_list, err)

    S = st.session_state
    them_k = S.setdefault(f"{key}_khoi_moi", [])
    them_g = S.setdefault(f"{key}_giay_moi", [])
    khois = sorted({*bang, *them_k}, key=_khoi_key)

    k = ui.kpi_row(3, key=f"{key}_kpis")
    ui.kpi(k[0], "Số khối / phân hệ", len(khois))
    ui.kpi(k[1], "Loại giấy tờ", len(_ma_tran(bang, khois, them_g)))
    ui.kpi(k[2], "Nguồn danh mục", "SharePoint" if bang_sp else "Mặc định (Book1)")

    with ui.section("Giấy tờ cần thu theo khối",
                    "Tick ô = khối đó phải nộp giấy tờ. Chỉ áp dụng cho học sinh mới (nhập từ Data "
                    "tuyển sinh); học sinh cũ lên lớp không phải nộp lại. Sửa xong bấm Lưu."):
        bt = st.container(horizontal=True, gap="small", vertical_alignment="bottom")
        with bt.popover("Thêm khối", icon=":material/add:"):
            moi = st.text_input("Tên khối", placeholder="Vd 6-ESL, 10-IEP hoặc 7",
                                key=f"{key}_k_ten").strip()
            mau = st.selectbox("Sao chép giấy tờ từ khối", ["(Trống)", *khois], key=f"{key}_k_mau")
            st.caption("Ghi khối kèm phân hệ (10-IEP, 10-ESL) để tách IEP / ESL; ghi số khối (7) "
                       "để dùng chung cho cả khối.")
            if st.button("Thêm cột khối", type="primary", disabled=not moi or moi in khois,
                         key=f"{key}_k_go"):
                them_k.append(moi)
                if mau != "(Trống)":
                    bang = {**bang, moi: list(bang.get(mau, []))}
                    S[f"{key}_mau_{moi}"] = list(bang[moi])
                st.rerun()
        with bt.popover("Thêm loại giấy tờ", icon=":material/note_add:"):
            g = st.text_input("Tên giấy tờ", placeholder="Vd Giấy xác nhận cư trú",
                              key=f"{key}_g_ten").strip()
            if st.button("Thêm dòng", type="primary", disabled=not g, key=f"{key}_g_go"):
                them_g.append(g)
                st.rerun()
        for kk in them_k:  # khối mới sao chép từ khối có sẵn
            if f"{key}_mau_{kk}" in S:
                bang = {**bang, kk: S[f"{key}_mau_{kk}"]}

        bang_xem = _ma_tran(bang, khois, them_g)
        sua = st.data_editor(
            bang_xem, hide_index=True, width="stretch", num_rows="fixed",
            height=min(38 + 35 * len(bang_xem), 640), disabled=["Giấy tờ"],
            column_config={"Giấy tờ": st.column_config.TextColumn(width=205, pinned=True),
                           **{kk: st.column_config.CheckboxColumn(
                               kk, width=70, help=f"Khối {kk}: {len(bang.get(kk, []))} giấy tờ")
                              for kk in khois}},
            key=f"{key}_ed_{ui.data_version()}_{len(khois)}_{len(them_g)}")
        goc = bang_sp or services.giay_to_mac_dinh()
        doi = [kk for kk in khois
               if [g for g, c in zip(sua["Giấy tờ"], sua[kk]) if c] != goc.get(kk, [])]
        c1, c2 = st.columns([3, 1.2], vertical_alignment="center")
        c1.caption(("Đang sửa: " + ", ".join(
            f"**{kk}** {sum(bool(c) for c in sua[kk])} giấy tờ" for kk in doi))
                   if doi else "Chưa có thay đổi · " + " · ".join(
                       f"{kk}: **{len(bang.get(kk, []))}**" for kk in khois)
                   + " giấy tờ. Bỏ tick hết một cột = xóa khối đó.")
        if c2.button("Lưu danh mục", type="primary", icon=":material/save:", width="stretch",
                     disabled=not doc_duoc or not (doi or not bang_sp), key=f"{key}_luu"):
            if ui.mutate(luu_ma_tran, storage, sua, khois, bang_sp, items,
                         success="Đã lưu danh mục giấy tờ") is not None:
                for kk in list(them_k):
                    S.pop(f"{key}_mau_{kk}", None)
                them_k.clear()
                them_g.clear()
                st.rerun()
        if not doc_duoc:
            st.caption("Chưa lưu được vì chưa có list trên SharePoint.")
        ui.download_excel("Tải danh mục (Excel)", sua.replace({True: "x", False: ""}),
                          "DanhMuc_GiayTo.xlsx", key=f"{key}_xls")
