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
long = NT.bang_dai(dg_all, nam_hoc)

nh = ui.df(NHAP_HOC, nam_hoc)
nt = nh[nh["NoiTruBanTru"].str.startswith("Nội trú")
        & ~nh["TinhTrangHS"].isin(["Rút hồ sơ", "Không học tiếp"])]
HS = {str(r["id"]): {"ten": r["HoTen"] or "(Chưa có tên)",
                     "lop": r["LopHoc"] or (f"Khối {r['Khoi']}" if r["Khoi"] else "")}
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
    ids = NT.hs_ids(phong)
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
        up = st.file_uploader("File Excel danh sách nội trú", type=["xlsx"], key="nt_up")
        if up is None:
            return
        try:
            ds_sheet = NT.sheet_phong(up)
        except Exception as e:
            ui.error_state(e, compact=True)
            return
        if not ds_sheet:
            st.error("Không thấy sheet nào có cột \"Họ và tên\" và cột \"Phòng\".",
                     icon=":material/error:")
            return
        sheet = st.selectbox("Sheet", ds_sheet, key="nt_up_sheet",
                             help="App tự chọn sheet có đủ cột nhất")
        up.seek(0)
        ds, _ = NT.doc_ds_phong(up, sheet)
        g = NT.ghep_hs(ds, ui.records(NHAP_HOC), nam_hoc)
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
                                  f"NoiTru_ChuaGhep_{nam_hoc}.xlsx", key="nt_up_loi")
        if any(x["NhieuGV"] for x in kh):
            st.warning("Có phòng mà file ghi nhiều giáo viên — app lấy giáo viên xuất hiện nhiều "
                       "nhất; sửa lại ở khung Thêm / sửa phòng nếu cần.", icon=":material/warning:")
        st.caption("Khi áp dụng: phòng trùng tên trong năm được **cập nhật** (học sinh theo file), "
                   "phòng mới được tạo; em có trong file sẽ được bỏ khỏi phòng khác. Giáo viên chưa "
                   "có tài khoản vẫn được ghi tên; khi tạo tài khoản đúng họ tên, giáo viên đó tự "
                   "nhập được đánh giá phòng mình.")
        if st.button(f"Áp dụng: {len(kh)} phòng, {len(khop)} học sinh", type="primary",
                     icon=":material/done_all:", disabled=khop.empty, key="nt_up_go"):
            bar = st.progress(0.0, text="Đang ghi lên SharePoint…")
            kq = ui.mutate(NT.ap_dung_phan_phong, storage, phongs_all, nam_hoc, g, kh,
                           NHAP_HOC.name,
                           progress=lambda d, t: bar.progress(d / max(t, 1),
                                                              text=f"Đã ghi {d}/{t}"),
                           success="Đã nhập danh sách nội trú và phân phòng")
            if kq:
                st.rerun()


def render_phong():
    tks = [t for t in ui.records(TAI_KHOAN, optional=True)
           if str(t.get("HoatDong") or "Có") != "Không"]
    tks.sort(key=lambda t: (t.get("VaiTro") != "GV quản nhiệm", str(t.get("HoTen") or "")))
    render_nhap_excel(tks)
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
        chua = [i for i in HS if i not in o_phong]
        if chua:
            with st.expander(f"{len(chua)} học sinh nội trú chưa xếp phòng"):
                st.write(", ".join(ten_hs(i) for i in chua))
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
