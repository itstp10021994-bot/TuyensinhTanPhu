"""Nhập danh sách nội trú + phân phòng từ Excel — dùng ở trang Nội trú và trang Cài đặt."""
import pandas as pd
import streamlit as st

from . import noi_tru as NT
from . import ui
from .schema import NHAP_HOC


def nhap_phan_phong(up, storage, nam_hoc: str, phongs_all: list[dict], nh: list[dict],
                    tks: list[dict], key: str):
    """Xem trước ghép học sinh / phòng từ file `up` rồi áp dụng khi bấm nút."""
    try:
        ds_sheet = NT.sheet_phong(up)
    except Exception as e:
        ui.error_state(e, compact=True)
        return
    if not ds_sheet:
        st.error("Không thấy sheet nào có cột \"Họ và tên\" và cột \"Phòng\".",
                 icon=":material/error:")
        return
    sheet = st.selectbox("Sheet", ds_sheet, key=f"{key}_sheet",
                         help="App tự chọn sheet có đủ cột nhất")
    up.seek(0)
    ds, _ = NT.doc_ds_phong(up, sheet)
    g = NT.ghep_hs(ds, nh, nam_hoc)
    kh = NT.ke_hoach_phong(g, tks)
    khop = g[g["Kết quả"] == NT.TT_KHOP]
    doi = khop[~khop["Chế độ (app)"].str.startswith("Nội trú")]
    k = st.columns(4)
    ui.kpi(k[0], "Học sinh trong file", len(g), f"{len(kh)} phòng")
    ui.kpi(k[1], "Ghép được", len(khop), f"{len(doi)} em sẽ đổi sang Nội trú")
    ui.kpi(k[2], "Không tìm thấy", int((g["Kết quả"] == NT.TT_KHONG_THAY).sum()),
           f"chưa có hồ sơ {nam_hoc}")
    ui.kpi(k[3], "Trùng tên, chưa rõ", int((g["Kết quả"] == NT.TT_TRUNG).sum()))
    bang_phong = pd.DataFrame([{
        "Phòng": x["TenPhong"], "Giáo viên": x["GiaoVien"],
        "Tài khoản": (x["TaiKhoan"] or {}).get("TenDangNhap") or "— chưa có, khớp theo tên",
        "Số HS ghép được": len(x["HocSinhIDs"]),
        "Ghi chú": ("File có nhiều GV: " + ", ".join(x["NhieuGV"])) if x["NhieuGV"] else ""}
        for x in kh])
    st.dataframe(bang_phong, hide_index=True, width="stretch",
                 height=min(38 + 35 * len(bang_phong), 420))
    loi = g[g["Kết quả"] != NT.TT_KHOP]
    if len(loi):
        with st.expander(f"{len(loi)} em chưa ghép được — xem và tải danh sách"):
            st.dataframe(loi[["Họ tên", "Lớp", "Giới tính", "Phòng", "Kết quả"]],
                         hide_index=True, width="stretch",
                         height=min(38 + 35 * len(loi), 400))
            ui.download_excel("Tải danh sách chưa ghép", loi.drop(columns=["HocSinhID"]),
                              f"NoiTru_ChuaGhep_{nam_hoc}.xlsx", key=f"{key}_loi")
    ngoai = [r for r in nh if str(r.get("NamHoc") or "") == nam_hoc
             and str(r.get("NoiTruBanTru") or "").startswith("Nội trú")
             and str(r.get("TinhTrangHS") or "") not in ("Rút hồ sơ", "Không học tiếp")
             and str(r.get("id")) not in set(khop["HocSinhID"])]
    if ngoai:
        with st.expander(f"{len(ngoai)} em app ghi Nội trú nhưng không có trong file"):
            st.caption("Áp dụng không đổi các em này: vẫn là Nội trú, giữ phòng đang ở (nếu có). "
                       "Em không còn ở nội trú thì sửa N.trú, B.trú trong hồ sơ.")
            bang = pd.DataFrame([{"Họ tên": r.get("HoTen"), "Lớp": r.get("LopHoc"),
                                  "Giới tính": r.get("GioiTinh")} for r in ngoai])
            st.dataframe(bang, hide_index=True, width="stretch",
                         height=min(38 + 35 * len(bang), 300))
            ui.download_excel("Tải danh sách", bang, f"NoiTru_KhongCoTrongFile_{nam_hoc}.xlsx",
                              key=f"{key}_ngoai")
    if any(x["NhieuGV"] for x in kh):
        st.warning("Có phòng mà file ghi nhiều giáo viên — app lấy giáo viên xuất hiện nhiều "
                   "nhất; sửa lại ở khung Thêm / sửa phòng nếu cần.", icon=":material/warning:")
    st.caption("Khi áp dụng: phòng trùng tên trong năm được **cập nhật** (học sinh theo file), "
               "phòng mới được tạo; em có trong file sẽ được bỏ khỏi phòng khác. Giáo viên chưa "
               "có tài khoản vẫn được ghi tên; khi tạo tài khoản đúng họ tên, giáo viên đó tự "
               "nhập được đánh giá phòng mình.")
    if st.button(f"Áp dụng: {len(kh)} phòng, {len(khop)} học sinh", type="primary",
                 icon=":material/done_all:", disabled=khop.empty, key=f"{key}_go"):
        bar = st.progress(0.0, text="Đang ghi lên SharePoint…")
        kq = ui.mutate(NT.ap_dung_phan_phong, storage, phongs_all, nam_hoc, g, kh,
                       NHAP_HOC.name,
                       progress=lambda d, t: bar.progress(d / max(t, 1),
                                                          text=f"Đã ghi {d}/{t}"),
                       success="Đã nhập danh sách nội trú và phân phòng")
        if kq:
            st.rerun()
