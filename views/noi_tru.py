"""Nội trú: giáo viên quản nhiệm phòng đánh giá nề nếp và học bài tối của từng học sinh mỗi ngày.

- Nhập đánh giá: giáo viên quản nhiệm (phòng mình); Tổ trưởng quản nhiệm, Quản trị (mọi phòng).
  Mặc định mọi em "Tốt", chỉ sửa em có vấn đề.
- Xem đánh giá: mọi người vào được trang.
- Báo cáo, Phòng & giáo viên: Tổ trưởng quản nhiệm và Quản trị.
"""
from datetime import date, timedelta

import altair as alt
import pandas as pd
import streamlit as st

from tuyensinh import importer, ui
from tuyensinh.ui_noi_tru import nhap_phan_phong
from tuyensinh import noi_tru as NT
from tuyensinh.schema import (MUC_DANH_GIA, NHAP_HOC, NOI_TRU_DANH_GIA, NOI_TRU_PHONG,
                              TAI_KHOAN)

S = st.session_state
nam_hoc = ui.nam_hoc()
storage = ui.storage()
tk = S.get("tk")
quan_ly = NT.la_quan_ly(tk)
hom_nay = date.today()
THU = ["T2", "T3", "T4", "T5", "T6", "T7", "CN"]
MAU = {"Tốt": "#34C759", "Khá": "#007AFF", "Trung bình": "#FF9500", "Chưa tốt": "#FF3B30"}
NGAN = {"Tốt": "T", "Khá": "K", "Trung bình": "TB", "Chưa tốt": "CT"}

actions = ui.page_header("Nội trú", f"Đánh giá hằng ngày: nề nếp, học tập, sức khỏe - tâm lý "
                                    f"và nhận xét · năm học {nam_hoc}")

# ------------------------------------------------------------------ dữ liệu
phongs_all = ui.records(NOI_TRU_PHONG, optional=True)
dg_all = ui.records(NOI_TRU_DANH_GIA, optional=True)
loi = ui.list_error(NOI_TRU_PHONG) or ui.list_error(NOI_TRU_DANH_GIA)
if loi:
    chua_tao = "does not exist" in loi or "404" in loi
    with ui.section("Thiết lập phân hệ Nội trú" if chua_tao else "Không đọc được dữ liệu nội trú"):
        if chua_tao:
            st.info("Phân hệ Nội trú cần **2 list mới trên SharePoint** (NoiTru_Phong, "
                    "NoiTru_DanhGia) nhưng chưa được tạo. Đây là bước làm **một lần**.",
                    icon=":material/info:")
            if quan_ly:
                st.markdown("Bấm **Tạo list nội trú** bên dưới — app tự tạo list và các cột "
                            "(khoảng 30 giây).")
            else:
                st.markdown("Nhờ **Quản trị** hoặc **Tổ trưởng quản nhiệm** mở trang này và bấm "
                            "**Tạo list nội trú**.")
        else:
            st.warning("Chưa đọc được list nội trú trên SharePoint (lỗi kết nối hoặc quyền).",
                       icon=":material/warning:")
        with st.expander("Chi tiết kỹ thuật"):
            st.code(loi, language=None, wrap_lines=True)
        if quan_ly and st.button("Tạo list nội trú", type="primary",
                                 icon=":material/playlist_add:"):
            with st.status("Đang tạo list…", expanded=True) as stt:
                try:
                    importer.setup_lists(storage, log=stt.write,
                                         lists=[NOI_TRU_PHONG, NOI_TRU_DANH_GIA])
                    stt.update(label="Đã tạo list", state="complete")
                except Exception as e:
                    stt.update(label="Không tạo được list", state="error")
                    ui.error_state(e, compact=True)
                    st.stop()
            ui.refresh()
            st.rerun()
    st.stop()

phongs = NT.phong_nam(phongs_all, nam_hoc)
nh = ui.df(NHAP_HOC, nam_hoc)
# tên, lớp theo hồ sơ hiện tại; học sinh đã xóa hồ sơ không còn hiện trong đánh giá / báo cáo
long = NT.theo_ho_so(NT.bang_dai(dg_all, nam_hoc), ui.records(NHAP_HOC))
nt = nh[nh["NoiTruBanTru"].str.startswith("Nội trú")
        & ~nh["TinhTrangHS"].isin(["Rút hồ sơ", "Không học tiếp"])]
HS = {str(r["id"]): {"ten": r["HoTen"] or "(Chưa có tên)",
                     "lop": r["LopHoc"] or (f"Khối {r['Khoi']}" if r["Khoi"] else ""),
                     "khoi": r["Khoi"], "gt": r["GioiTinh"]}
      for _, r in nt.iterrows()}
o_phong = NT.phong_cua_hs(phongs)


def ten_hs(i: str) -> str:
    h = HS.get(i)
    return f"{h['ten']} · {h['lop']}" if h and h["lop"] else (h["ten"] if h else f"(HS {i})")


# ------------------------------------------------------------------ chỉ số hôm nay
hn = long[long["Ngày"] == hom_nay]
k = ui.kpi_row(4, key="nt_kpis")
ui.kpi(k[0], "Phòng nội trú", len(phongs))
ui.kpi(k[1], "Học sinh nội trú", len(HS), f"{len(set(o_phong) & set(HS))} em đã xếp phòng")
ui.kpi(k[2], "Phòng đã đánh giá hôm nay", f"{hn['PhongID'].nunique()}/{len(phongs)}")
ui.kpi(k[3], "Lượt TB / Chưa tốt hôm nay",
       int(sum(hn[c].isin(NT.CAN_CHU_Y).sum() for c in NT.COT_MUC)))

phong_cua_toi = [p for p in phongs if NT.duoc_nhap(p, tk)]  # GV: phòng mình; quản lý: mọi phòng
ten_tab = []
if phong_cua_toi or quan_ly:  # quản lý luôn thấy tab (chưa có phòng: hướng dẫn tạo phòng)
    ten_tab.append(":material/edit_note: Nhập đánh giá")
ten_tab.append(":material/visibility: Xem đánh giá")
if quan_ly:
    ten_tab += [":material/monitoring: Báo cáo", ":material/meeting_room: Phòng & giáo viên"]
# key + on_change="rerun": giữ đúng tab đang mở sau mỗi thao tác, chỉ vẽ tab đang mở
if S.get("nt_tab") not in ten_tab:
    S.pop("nt_tab", None)
tabs = dict(zip(ten_tab, st.tabs(ten_tab, key="nt_tab", on_change="rerun")))


def _to_mau(v):
    m = MAU.get(v) or MAU.get({x: k for k, x in NGAN.items()}.get(v, ""))
    return f"color: {m}; font-weight: 600" if m else ""


# ------------------------------------------------------------------ nhập đánh giá
def render_nhap():
    if not phong_cua_toi:
        ui.empty_state("meeting_room", "Chưa có phòng nội trú",
                       f"Năm học {nam_hoc} chưa có phòng. Vào tab Phòng & giáo viên để tạo phòng, "
                       "chọn giáo viên quản nhiệm và xếp học sinh — sau đó nhập đánh giá ở đây.")
        return
    c1, c2 = st.columns([1, 2], vertical_alignment="bottom")
    ngay = c1.date_input("Ngày", hom_nay, max_value=hom_nay, format="DD/MM/YYYY",
                         key="nt_ngay")
    phong = c2.selectbox("Phòng", phong_cua_toi, key="nt_phong",
                         format_func=lambda p: f"{p['TenPhong']}"
                         + (f" · {p['Khu']}" if p.get("Khu") else "")
                         + f" · {len(NT.hs_ids(p))} học sinh"
                         + (f" · GV {p['GiaoVien']}" if quan_ly and p.get("GiaoVien") else ""))
    ids = [i for i in NT.hs_ids(phong) if i in HS]  # bỏ em đã xóa hồ sơ / không còn nội trú
    if len(ids) < len(NT.hs_ids(phong)):
        st.caption(f":material/info: {len(NT.hs_ids(phong)) - len(ids)} em trong phòng không còn "
                   "là học sinh nội trú (hồ sơ đã xóa hoặc đổi chế độ) nên không hiện — Tổ trưởng "
                   "bỏ các em khỏi phòng ở tab Phòng & giáo viên.")
    if not ids:
        ui.empty_state("group_off", "Phòng chưa có học sinh",
                       "Tổ trưởng quản nhiệm xếp học sinh vào phòng ở tab Phòng & giáo viên.")
        return
    cu = NT.tim_ban_ghi(dg_all, phong["id"], ngay)
    da = {d.get("id"): d for d in NT.doc_du_lieu(cu)} if cu else {}
    if cu:
        st.success(f"Đã lưu đánh giá ngày {ngay:%d/%m/%Y} (người nhập: "
                   f"{cu.get('NguoiDanhGia') or '—'}). Sửa rồi bấm **Lưu** để cập nhật.",
                   icon=":material/check_circle:")
    else:
        st.info(f"Chưa nhập ngày {ngay:%d/%m/%Y}. Mọi em đang để **Tốt** — chỉ cần đổi các em "
                "có vấn đề rồi bấm **Lưu**.", icon=":material/info:")
    st.caption("Nề nếp, Học tập, Sức khỏe - Tâm lý: chọn mức (mặc định Tốt) và ghi nhận xét nếu "
               "cần. Ba cột cuối viết lời khi có. Bấm đúp vào ô để sửa; kéo ngang để xem hết cột.")
    rows = []
    for i in ids:
        d = da.get(i, {})
        h = HS.get(i, {"ten": d.get("ten") or f"(HS {i})", "lop": d.get("lop", "")})
        r = {"id": i, "Học sinh": h["ten"], "Lớp": h["lop"]}
        for m in NT.MUC:
            r[NT.TEN_MUC[m]] = d.get(m) or d.get(NT.CU.get(m, "")) or "Tốt"
        for m in NT.MUC:
            r[NT.TEN_NX[m]] = d.get(NT.NX[m]) or (d.get("GhiChu", "") if m == "NeNep" else "")
        for kk in NT.LOI:
            r[NT.TEN_LOI[kk]] = d.get(kk, "")
        rows.append(r)
    bang = pd.DataFrame(rows)
    cfg = {"id": None,
           "Học sinh": st.column_config.TextColumn(width="medium", pinned=True),
           "Lớp": st.column_config.TextColumn(width="small")}
    for m in NT.MUC:
        cfg[NT.TEN_MUC[m]] = st.column_config.SelectboxColumn(
            options=list(MUC_DANH_GIA), required=True, width=130)
    for c in NT.COT_LOI:
        cfg[c] = st.column_config.TextColumn(width=230, max_chars=NT.MAX_LOI)
    sua = st.data_editor(
        bang, hide_index=True, width="stretch", disabled=["Học sinh", "Lớp"],
        height=min(38 + 35 * len(bang), 720), column_config=cfg,
        key=f"nt_ed_{phong['id']}_{ngay}_{ui.data_version()}")
    can = int(sum(sua[c].isin(NT.CAN_CHU_Y).sum() for c in NT.COT_MUC))
    co_loi = int(sua[NT.COT_LOI].fillna("").ne("").any(axis=1).sum())
    b1, b2 = st.columns([3, 1.2], vertical_alignment="center")
    b2.caption(f"{len(sua)} học sinh · {can} lượt TB/Chưa tốt · {co_loi} em có nhận xét")
    if b1.button(f"Lưu đánh giá phòng {phong['TenPhong']} ngày {ngay:%d/%m/%Y}", type="primary",
                 icon=":material/save:", width="stretch"):
        dong = []
        for r in sua.fillna("").to_dict("records"):
            x = {"id": r["id"], "ten": r["Học sinh"], "lop": r["Lớp"]}
            for m in NT.MUC:
                x[m] = r[NT.TEN_MUC[m]]
                x[NT.NX[m]] = r[NT.TEN_NX[m]]
            for kk in NT.LOI:
                x[kk] = r[NT.TEN_LOI[kk]]
            dong.append(x)
        if ui.mutate(NT.luu_danh_gia, storage, dg_all, nam_hoc, ngay, phong, dong,
                     ui.current_user(), success=f"Đã lưu đánh giá phòng {phong['TenPhong']}"):
            st.rerun()


# ------------------------------------------------------------------ xem đánh giá
def _loc_khoang(key: str, mac_dinh_ngay: int):
    v = st.date_input("Khoảng ngày", (hom_nay - timedelta(days=mac_dinh_ngay), hom_nay),
                      format="DD/MM/YYYY", key=key)
    if isinstance(v, (tuple, list)) and len(v) == 2:
        return v[0], v[1]
    d = v[0] if isinstance(v, (tuple, list)) and v else (v or hom_nay)
    return d, d


def render_xem():
    c1, c2, c3 = st.columns([1.3, 1.6, 1.6], vertical_alignment="bottom")
    with c1:
        tu, den = _loc_khoang("nt_xem_kh", 6)
    ten_p = [p["TenPhong"] for p in phongs]
    chon = c2.multiselect("Phòng", ten_p, key="nt_xem_phong", placeholder="Tất cả phòng")
    q = c3.text_input("Tìm học sinh", key="nt_xem_q", icon=":material/search:",
                      placeholder="Tên học sinh")
    x = long[(long["Ngày"] >= tu) & (long["Ngày"] <= den)]
    if chon:
        x = x[x["Phòng"].isin(chon)]
    if q.strip():
        x = x[x["Học sinh"].str.lower().str.contains(q.strip().lower(), regex=False)]
    if x.empty:
        ui.empty_state("event_busy", "Chưa có đánh giá",
                       f"Không có đánh giá nào từ {tu:%d/%m} đến {den:%d/%m/%Y} theo bộ lọc.")
        return
    kieu = st.segmented_control("Hiển thị", ["Bảng theo ngày", "Nhận xét", "Danh sách chi tiết"],
                                default="Bảng theo ngày", required=True, key="nt_xem_kieu",
                                label_visibility="collapsed")
    if kieu == "Bảng theo ngày":
        muc = st.segmented_control("Mục", NT.COT_MUC, default=NT.COT_MUC[0],
                                   required=True, key="nt_xem_muc")
        p = x.assign(_v=x[muc].map(NGAN).fillna(""), _c=x["Ngày"].map(lambda d: f"{d:%d/%m}")) \
            .pivot_table(index=["Phòng", "Học sinh", "Lớp"], columns="_c", values="_v",
                         aggfunc="last", fill_value="")
        p = p[sorted(p.columns, key=lambda s: (s[3:], s[:2]))].reset_index()
        st.dataframe(p.style.map(_to_mau, subset=[c for c in p.columns
                                                  if c not in ("Phòng", "Học sinh", "Lớp")]),
                     hide_index=True, width="stretch", height=min(38 + 35 * len(p), 640))
        st.caption("T = Tốt · K = Khá · TB = Trung bình · CT = Chưa tốt · ô trống = chưa đánh giá")
    elif kieu == "Nhận xét":
        d = NT.nhan_xet(x).sort_values(["Ngày", "Phòng", "Học sinh"],
                                       ascending=[False, True, True])
        if d.empty:
            ui.empty_state("notes", "Chưa có lời nhận xét",
                           "Các em trong khoảng đã chọn chỉ được chấm mức, chưa có lời nhận xét.")
        else:
            st.dataframe(d, hide_index=True, width="stretch",
                         height=min(38 + 35 * len(d), 640), column_config={
                             "Ngày": st.column_config.DateColumn(format="DD/MM/YYYY"),
                             **{c: st.column_config.TextColumn(width="medium")
                                for c in NT.COT_LOI}})
            st.caption(f"{len(d)} lượt có nhận xét · bấm vào ô để đọc đầy đủ")
    else:
        d = x.sort_values(["Ngày", "Phòng", "Học sinh"], ascending=[False, True, True])
        d = d.drop(columns=["PhongID", "HocSinhID"])
        st.dataframe(d.style.map(_to_mau, subset=NT.COT_MUC), hide_index=True,
                     width="stretch", height=min(38 + 35 * len(d), 640),
                     column_config={"Ngày": st.column_config.DateColumn(format="DD/MM/YYYY")})
    ui.download_excel("Tải Excel", x.drop(columns=["PhongID", "HocSinhID"]),
                      f"DanhGiaNoiTru_{tu:%Y%m%d}_{den:%Y%m%d}.xlsx", key="nt_xem_xls")


# ------------------------------------------------------------------ báo cáo
def render_bao_cao():
    c1, c2, c3 = st.columns([1.3, 2, 1], vertical_alignment="bottom")
    with c1:
        tu, den = _loc_khoang("nt_bc_kh", 29)
    thu = c2.pills("Ngày có đánh giá", THU, selection_mode="multi", default=THU[:5],
                   key="nt_bc_thu", help="Dùng để tính số ngày chưa nhập của từng phòng")
    nguong = c3.number_input("Cần chú ý từ (lượt)", 1, 50, 2, key="nt_bc_nguong")
    ngays = NT.ngay_trong_khoang(tu, min(den, hom_nay), [THU.index(t) for t in thu or THU[:5]])
    x = long[(long["Ngày"] >= tu) & (long["Ngày"] <= den)]
    th = NT.tong_hop_phong(x, phongs, ngays)
    cc = NT.hoc_sinh_can_chu_y(x, nguong)
    k = ui.kpi_row(5, key="nt_bc_kpis")
    for col, ten in zip(k, NT.COT_MUC):
        v = NT._ty_le_tot(x[ten])
        ui.kpi(col, f"{ten} Tốt", "—" if v is None else f"{v}%")
    ui.kpi(k[3], "Phòng còn thiếu ngày", int((th["Ngày chưa nhập"] > 0).sum()) if len(th) else 0,
           f"trên {len(ngays)} ngày cần đánh giá")
    ui.kpi(k[4], "Học sinh cần chú ý", len(cc), f"từ {nguong} lượt TB/Chưa tốt")

    with ui.section("Tổng hợp theo phòng",
                    f"Từ {tu:%d/%m} đến {den:%d/%m/%Y} · tỷ lệ Tốt và số ngày đã nhập"):
        if th.empty:
            ui.empty_state("meeting_room", "Chưa có phòng")
        else:
            st.dataframe(th, hide_index=True, width="stretch",
                         height=min(38 + 35 * len(th), 520), column_config={
                             c: st.column_config.ProgressColumn(format="%.1f%%", min_value=0,
                                                                max_value=100)
                             for c in (f"{m} Tốt (%)" for m in NT.COT_MUC)})
    with ui.section("Học sinh cần chú ý",
                    f"Có từ {nguong} lượt Trung bình / Chưa tốt (cộng 3 mục chấm mức)"):
        if cc.empty:
            ui.empty_state("sentiment_satisfied", "Không có học sinh cần chú ý")
        else:
            st.dataframe(cc, hide_index=True, width="stretch",
                         height=min(38 + 35 * len(cc), 520))
    left, right = st.columns(2, gap="medium")
    with left, ui.section("Tỷ lệ Tốt theo ngày"):
        td = NT.theo_ngay(x)
        if td.empty:
            ui.empty_state("show_chart", "Chưa có dữ liệu")
        else:
            base = alt.Chart(td).encode(
                x=alt.X("Ngày:T", title=None, axis=alt.Axis(format="%d/%m")),
                y=alt.Y("Tỷ lệ Tốt (%):Q", title=None, scale=alt.Scale(domain=[0, 100])),
                color=alt.Color("Mục:N", scale=alt.Scale(range=["#007AFF", "#34C759", "#AF52DE"]),
                                legend=alt.Legend(orient="top", title=None)),
                tooltip=[alt.Tooltip("Ngày:T", format="%d/%m/%Y"), "Mục:N",
                         "Tỷ lệ Tốt (%):Q"])
            st.altair_chart((base.mark_line(strokeWidth=2) + base.mark_point(filled=True))
                            .properties(height=260), width="stretch")
    with right, ui.section("Phân bố mức đánh giá"):
        pb = NT.phan_bo_muc(x)
        if pb["Số lượt"].sum() == 0:
            ui.empty_state("bar_chart", "Chưa có dữ liệu")
        else:
            st.altair_chart(alt.Chart(pb).mark_bar(cornerRadiusEnd=4).encode(
                x=alt.X("Số lượt:Q", title=None, stack="normalize",
                        axis=alt.Axis(format="%")),
                y=alt.Y("Mục:N", title=None),
                color=alt.Color("Mức:N", sort=list(MUC_DANH_GIA), scale=alt.Scale(
                    domain=list(MUC_DANH_GIA), range=[MAU[m] for m in MUC_DANH_GIA]),
                    legend=alt.Legend(orient="top", title=None)),
                order=alt.Order("_o:Q"),
                tooltip=["Mục:N", "Mức:N", "Số lượt:Q"]).transform_calculate(
                _o="indexof(['Tốt','Khá','Trung bình','Chưa tốt'], datum['Mức'])")
                .properties(height=190), width="stretch")
    with ui.section("Tình hình nhập đánh giá",
                    "✓ đã nhập · ✗ chưa nhập — để nhắc giáo viên quản nhiệm"):
        ng = ngays[-31:]
        tn = NT.tinh_hinh_nhap(x, phongs, ng)
        if tn.empty or not ng:
            ui.empty_state("event_available", "Không có ngày cần đánh giá trong khoảng đã chọn")
        else:
            st.dataframe(tn.style.map(lambda v: "color: #FF3B30" if v == "✗" else
                                      ("color: #34C759" if v == "✓" else "")),
                         hide_index=True, width="stretch", height=min(38 + 35 * len(tn), 520))
            if len(ngays) > 31:
                st.caption("Chỉ hiện 31 ngày gần nhất; file Excel có đủ.")
    ui.download_excel("Tải báo cáo (Excel)", {
        "Tong_hop_phong": th, "Hoc_sinh_can_chu_y": cc,
        "Tinh_hinh_nhap": NT.tinh_hinh_nhap(x, phongs, ngays),
        "Chi_tiet": x.drop(columns=["PhongID", "HocSinhID"])},
        f"BaoCaoNoiTru_{tu:%Y%m%d}_{den:%Y%m%d}.xlsx", primary=True, key="nt_bc_xls")


# ------------------------------------------------------------------ phòng & giáo viên
MOI = "＋ Thêm phòng mới"


def render_nhap_excel(tks: list[dict]):
    """Nhập danh sách nội trú + phân phòng từ file Excel (vd sheet DSHS của Tổ quản nhiệm)."""
    with st.expander("Nhập danh sách nội trú & phân phòng từ Excel", icon=":material/upload_file:",
                     expanded=not phongs):
        st.caption("File cần có các cột **Họ và tên**, **Lớp**, **Giới tính**, **Phòng NT**, "
                   "**QN quản lý** (giáo viên). App ghép từng em với **Hồ sơ nhập học** năm "
                   f"{nam_hoc} theo họ tên (trùng tên thì xét lớp, khối, giới tính), đánh dấu "
                   "**Nội trú** và tạo phòng kèm giáo viên. Em chưa có hồ sơ năm này sẽ được liệt "
                   "kê để xử lý (vd chạy *Lên lớp từ năm trước* ở Hồ sơ nhập học).")
        st.download_button("Tải file mẫu", lambda: importer.file_mau(NOI_TRU_PHONG),
                           file_name=f"Mau_{NOI_TRU_PHONG.name}.xlsx", mime=ui.XLSX,
                           on_click="ignore", icon=":material/download:", key="nt_mau")
        up = st.file_uploader("File Excel danh sách nội trú", type=["xlsx"], key="nt_up")
        if up is None:
            return
        nhap_phan_phong(up, storage, nam_hoc, phongs_all, ui.records(NHAP_HOC), tks, "nt_up")


def render_chua_xep():
    """Học sinh nội trú (hồ sơ nhập học) chưa ở phòng nào: tick chọn rồi xếp vào phòng."""
    chua = [i for i in HS if i not in o_phong]
    if not chua:
        return
    with ui.section(f"{len(chua)} học sinh nội trú chưa xếp phòng",
                    "Hồ sơ nhập học có N.trú, B.trú = Nội trú nhưng chưa ở phòng nào. Tick chọn "
                    "các em, chọn phòng rồi bấm Xếp phòng."):
        c1, c2, c3 = st.columns([2, 1, 1])
        tim = c1.text_input("Tìm", key="nt_cx_tim", placeholder="Tên học sinh / lớp",
                            label_visibility="collapsed")
        khois = sorted({str(HS[i]["khoi"]) for i in chua if HS[i]["khoi"]},
                       key=lambda x: (len(x), x))
        khoi = c2.selectbox("Khối", ["Tất cả khối", *khois], key="nt_cx_khoi",
                            label_visibility="collapsed")
        gts = sorted({HS[i]["gt"] for i in chua if HS[i]["gt"]})
        gt = c3.selectbox("Giới tính", ["Nam và nữ", *gts], key="nt_cx_gt",
                          label_visibility="collapsed")
        from tuyensinh.danh_muc import fold
        ds = [i for i in chua
              if (not tim or fold(tim) in fold(f"{HS[i]['ten']} {HS[i]['lop']}"))
              and (khoi == "Tất cả khối" or str(HS[i]["khoi"]) == khoi)
              and (gt == "Nam và nữ" or HS[i]["gt"] == gt)]
        bang = pd.DataFrame([{"Chọn": False, "id": i, "Họ tên": HS[i]["ten"],
                              "Lớp": HS[i]["lop"], "Giới tính": HS[i]["gt"]} for i in ds],
                            columns=["Chọn", "id", "Họ tên", "Lớp", "Giới tính"])
        sua = st.data_editor(bang, hide_index=True, width="stretch",
                             height=min(38 + 35 * max(len(bang), 1), 360),
                             disabled=["Họ tên", "Lớp", "Giới tính"],
                             column_config={"id": None,
                                            "Chọn": st.column_config.CheckboxColumn(width="small")},
                             key=f"nt_cx_ed_{tim}_{khoi}_{gt}_{ui.data_version()}")
        chon = sua.loc[sua["Chọn"], "id"].tolist()
        theo_ten = {f"{p['TenPhong']} · {p.get('GiaoVien') or 'chưa có GV'} · "
                    f"{len(NT.hs_ids(p))} HS": p for p in phongs}
        c1, c2, c3 = st.columns([2, 1.2, 1.2], vertical_alignment="bottom")
        dich = c1.selectbox("Xếp vào phòng", [*theo_ten, MOI], key="nt_cx_phong")
        ten_moi = c2.text_input("Tên phòng mới", key="nt_cx_moi", placeholder="vd P101",
                                disabled=dich != MOI)
        if c3.button(f"Xếp {len(chon)} em vào phòng", type="primary", width="stretch",
                     icon=":material/meeting_room:", disabled=not chon, key="nt_cx_go"):
            if ui.mutate(NT.them_vao_phong, storage, phongs_all, nam_hoc, theo_ten.get(dich),
                         ten_moi, chon, success=f"Đã xếp {len(chon)} học sinh") is not None:
                st.rerun()
        st.caption("Em không có trong danh sách: mở hồ sơ ở **Hồ sơ nhập học**, đặt **N.trú, "
                   "B.trú = Nội trú** (tab Giấy tờ & chính sách) và kiểm tra đúng năm học.")


def render_khong_con_nt():
    """Em còn trong phòng nhưng hồ sơ đã bị xóa, không còn Nội trú hoặc đã nghỉ học."""
    thua = sorted({i for i in o_phong if i not in HS})
    if not thua:
        return
    tat_ca = {str(r["id"]): r for _, r in nh.iterrows()}

    def mo_ta(i):
        r = tat_ca.get(i)
        if r is None:
            return {"Họ tên": f"(hồ sơ {i} đã bị xóa)", "Lý do": "Không còn hồ sơ nhập học"}
        ly_do = (r["TinhTrangHS"] if r["TinhTrangHS"] in ("Rút hồ sơ", "Không học tiếp")
                 else f"Chế độ: {r['NoiTruBanTru'] or '(trống)'}")
        return {"Họ tên": r["HoTen"], "Lý do": ly_do}
    with ui.section(f"{len(thua)} em trong phòng không còn là học sinh nội trú",
                    "Hồ sơ đã bị xóa, đổi sang Bán trú / chế độ khác, hoặc đã rút / không học tiếp."):
        st.dataframe(pd.DataFrame([{"Phòng": o_phong[i].get("TenPhong"), **mo_ta(i)}
                                   for i in thua]), hide_index=True, width="stretch",
                     height=min(38 + 35 * len(thua), 300))
        if st.button(f"Bỏ {len(thua)} em khỏi phòng", icon=":material/person_remove:",
                     key="nt_kc_go"):
            if ui.mutate(NT.bo_khoi_phong, storage, phongs, thua,
                         success=f"Đã bỏ {len(thua)} em khỏi phòng") is not None:
                st.rerun()


def render_phong():
    tks = [t for t in ui.records(TAI_KHOAN, optional=True)
           if str(t.get("HoatDong") or "Có") != "Không"]
    tks.sort(key=lambda t: (t.get("VaiTro") != "GV quản nhiệm", str(t.get("HoTen") or "")))
    render_nhap_excel(tks)
    render_khong_con_nt()
    render_chua_xep()
    left, right = st.columns([1.4, 1.2], gap="medium")
    with left, ui.section("Danh sách phòng", f"{len(phongs)} phòng · năm học {nam_hoc}"):
        if phongs:
            st.dataframe(pd.DataFrame([{
                "Phòng": p.get("TenPhong"), "Khu": p.get("Khu"),
                "Giáo viên quản nhiệm": p.get("GiaoVien") or "— chưa phân công",
                "Số HS": len(NT.hs_ids(p))} for p in phongs]), hide_index=True,
                width="stretch", height=min(38 + 35 * len(phongs), 520))
        else:
            ui.empty_state("meeting_room", "Chưa có phòng", "Thêm phòng ở khung bên phải.")
    with right, ui.section("Thêm / sửa phòng"):
        theo_ten = {p["TenPhong"]: p for p in phongs}
        chon = st.selectbox("Phòng", [MOI, *theo_ten], key="nt_p_chon")
        p = theo_ten.get(chon, {})
        k = f"nt_p_{p.get('id', 'moi')}_{ui.data_version()}"
        ten = st.text_input("Tên phòng *", p.get("TenPhong", ""), key=f"{k}_ten",
                            placeholder="vd P101")
        khu = st.text_input("Khu / dãy nhà", p.get("Khu", ""), key=f"{k}_khu",
                            placeholder="vd Nam, Nữ, Dãy A")
        gv_opts = [None, *tks]
        gv_cu = next((t for t in tks if str(t.get("id")) == str(p.get("GiaoVienID"))), None)
        gv = st.selectbox("Giáo viên quản nhiệm", gv_opts,
                          index=gv_opts.index(gv_cu) if gv_cu else 0, key=f"{k}_gv",
                          format_func=lambda t: "— Chưa phân công —" if t is None else
                          f"{t.get('HoTen')} ({t.get('VaiTro')})",
                          help="Giáo viên này nhập đánh giá của phòng (Tổ trưởng và Quản trị "
                               "cũng nhập được mọi phòng). Tạo tài khoản vai trò \"GV quản "
                               "nhiệm\" ở Cài đặt → Tài khoản.")
        o_khac = {i for q in phongs if q.get("id") != p.get("id") for i in NT.hs_ids(q)}
        lua_chon = [i for i in HS if i not in o_khac]
        hien_tai = NT.hs_ids(p)
        lua_chon += [i for i in hien_tai if i not in lua_chon]
        hs = st.multiselect("Học sinh trong phòng", lua_chon,
                            default=[i for i in hien_tai if i in lua_chon], key=f"{k}_hs",
                            format_func=ten_hs, placeholder="Chọn học sinh nội trú",
                            help="Chỉ hiện học sinh nội trú (hồ sơ nhập học) chưa ở phòng khác.")
        ghi = st.text_area("Ghi chú", p.get("GhiChu", ""), key=f"{k}_gc", height=70)
        if st.button("Lưu phòng", type="primary", icon=":material/save:", width="stretch"):
            if ui.mutate(NT.luu_phong, storage, phongs_all, nam_hoc, ten, khu, gv, hs, ghi,
                         p.get("id"), success=f"Đã lưu phòng {ten}") is not None:
                S.pop("nt_p_chon", None)
                st.rerun()
        if p:
            with st.expander("Xóa phòng"):
                st.caption("Đánh giá đã lưu của phòng vẫn được giữ lại trong báo cáo.")
                if st.checkbox(f"Tôi muốn xóa phòng {p['TenPhong']}", key=f"{k}_xoa_ok") and \
                        st.button("Xóa phòng", icon=":material/delete:", key=f"{k}_xoa"):
                    if ui.mutate(storage.delete_item, NOI_TRU_PHONG.name, p["id"],
                                 success=f"Đã xóa phòng {p['TenPhong']}") is not None:
                        S.pop("nt_p_chon", None)
                        st.rerun()


for ten, tab in tabs.items():
    if not tab.open:
        continue
    with tab:
        if "Nhập" in ten:
            render_nhap()
        elif "Xem" in ten:
            render_xem()
        elif "Báo cáo" in ten:
            render_bao_cao()
        else:
            render_phong()

if not phong_cua_toi and tk and not quan_ly:
    st.caption(":material/info: Bạn chưa được phân công quản nhiệm phòng nào nên chỉ xem được "
               "đánh giá. Liên hệ Tổ trưởng quản nhiệm để được phân phòng.")
