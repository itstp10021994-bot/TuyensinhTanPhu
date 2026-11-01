"""Nội trú: nhận xét THEO THÁNG từng học sinh bằng lời (6 mục: nề nếp, học tập, sức khỏe -
tâm lý, điểm sáng, trao đổi và hỗ trợ, định hướng giáo dục) — mỗi em một cửa sổ nhận xét.

- Nhận xét tháng: lưới thẻ học sinh như Data tuyển sinh; bấm tên em -> cửa sổ nhận xét.
  Chỉ giáo viên quản nhiệm (em trong phòng mình), Tổ trưởng quản nhiệm và Quản trị (mọi em)
  mới thấy và viết được nhận xét.
- Báo cáo, Phòng & giáo viên: Tổ trưởng quản nhiệm và Quản trị.
"""
from datetime import date
from html import escape

import pandas as pd
import streamlit as st

from tuyensinh import bieu_do as BD
from tuyensinh import importer, ui
from tuyensinh.danh_muc import fold
from tuyensinh.ui_noi_tru import nhap_phan_phong
from tuyensinh import noi_tru as NT
from tuyensinh.schema import (NHAP_HOC, NOI_TRU_DANH_GIA, NOI_TRU_PHONG,
                              TAI_KHOAN, TUYEN_SINH)

S = st.session_state
qp = st.query_params
nam_hoc = ui.nam_hoc()
storage = ui.storage()
tk = S.get("tk")
quan_ly = NT.la_quan_ly(tk)
hom_nay = date.today()
CHUA_XEP = "— Chưa xếp phòng"

actions = ui.page_header("Nội trú", f"Nhận xét hằng tháng từng học sinh: nề nếp, học tập, sức "
                                    f"khỏe - tâm lý, điểm sáng, trao đổi, định hướng · năm học "
                                    f"{nam_hoc}",
                         eyebrow="Học sinh")

# ------------------------------------------------------------------ dữ liệu
phongs_all = ui.records(NOI_TRU_PHONG, optional=True)
dg_all = ui.records(NOI_TRU_DANH_GIA, optional=True)
loi = ui.list_error(NOI_TRU_PHONG) or ui.list_error(NOI_TRU_DANH_GIA)
if loi:
    chua_tao = "does not exist" in loi or "404" in loi
    with ui.section("Thiết lập phân hệ Nội trú" if chua_tao else "Không đọc được dữ liệu nội trú"):
        if chua_tao:
            st.info("Phân hệ Nội trú cần list **NoiTru_Phong** (phòng) và **NoiTru_DanhGiaThang** "
                    "(đánh giá theo tháng — mỗi học sinh mỗi tháng một dòng) trên SharePoint nhưng "
                    "chưa đủ. Đây là bước làm **một lần**; list đánh giá theo ngày cũ được giữ "
                    "nguyên.", icon=":material/info:")
            if quan_ly:
                st.markdown("Bấm **Tạo list nội trú** bên dưới — app tự tạo list còn thiếu và các "
                            "cột (khoảng 30 giây).")
            else:
                st.markdown("Nhờ **Quản trị** hoặc **Tổ trưởng quản nhiệm** mở trang này và bấm "
                            "**Tạo list nội trú**.")
        else:
            st.warning("Chưa đọc được list nội trú trên SharePoint (lỗi kết nối hoặc quyền).",
                       icon=":material/warning:")
        if quan_ly:
            with st.expander("Chi tiết kỹ thuật"):
                st.code(ui.an_bi_mat(loi), language=None, wrap_lines=True)
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

phongs = sorted(NT.phong_nam(phongs_all, nam_hoc),
                key=lambda p: NT._so_tu_nhien(str(p.get("TenPhong") or "")))
nh = ui.df(NHAP_HOC, nam_hoc)
dg = [r for r in dg_all if NT._s(r.get("NamHoc")) == nam_hoc]
# tên, lớp theo hồ sơ hiện tại; học sinh đã xóa hồ sơ không còn hiện trong đánh giá / báo cáo
long = NT.theo_ho_so(NT.bang_thang(dg, nam_hoc), ui.records(NHAP_HOC))
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


# ------------------------------------------------------------------ tháng đang xem
THANG = NT.thang_cua_nam(nam_hoc)
if "nt_thang" in S and S["nt_thang"] not in THANG:  # đổi năm học: về tháng mặc định
    del S["nt_thang"]
thang = actions.selectbox("Tháng đánh giá", THANG, key="nt_thang", format_func=NT.ten_thang,
                          index=THANG.index(NT.thang_mac_dinh(nam_hoc, hom_nay)),
                          width=190, label_visibility="collapsed")
x_thang = long[long["Tháng"] == thang]
da_dg = {str(r.get("HocSinhID")): r for r in dg if NT._s(r.get("Thang")) == thang}

phong_cua_toi = [p for p in phongs if NT.duoc_nhap(p, tk)]  # GV: phòng mình; quản lý: mọi phòng
# Chỉ người được đánh giá mới thấy nhận xét: GV quản nhiệm -> em phòng mình; Tổ trưởng quản
# nhiệm, Quản trị -> mọi em nội trú (kể cả em chưa xếp phòng)
HS_XEM = [(i, p) for p in phong_cua_toi for i in NT.hs_ids(p) if i in HS]
if quan_ly:
    HS_XEM += [(i, None) for i in HS if i not in o_phong]
DU = len(NT.KHOAN)


def _bang_xem() -> pd.DataFrame:
    rows = []
    for i, p in HS_XEM:
        r = da_dg.get(i)
        h = HS[i]
        dau = next((f"{NT.TEN[k]}: {NT._s(r.get(k))}" for k in NT.KHOAN
                    if r and NT._s(r.get(k))), "")
        rows.append({"id": i, "Học sinh": h["ten"], "Lớp": h["lop"],
                     "Phòng": (p or {}).get("TenPhong") or CHUA_XEP,
                     "PhongID": str((p or {}).get("id") or ""),
                     "Đã": r is not None, "Số mục": NT.so_muc(r), "Trích": dau,
                     "Người": NT._s((r or {}).get("NguoiDanhGia"))})
    return pd.DataFrame(rows, columns=["id", "Học sinh", "Lớp", "Phòng", "PhongID", "Đã",
                                       "Số mục", "Trích", "Người"])


BANG = _bang_xem()

# ------------------------------------------------------------------ chỉ số tháng
k = ui.kpi_row(4, key="nt_kpis")
n_da = int(BANG["Đã"].sum())
ui.kpi(k[0], "Học sinh nội trú", len(BANG),
       f"{len(phongs)} phòng · {sum(1 for _, p in HS_XEM if p is None)} em chưa xếp phòng"
       if quan_ly else f"{len(phong_cua_toi)} phòng của bạn")
ui.kpi(k[1], f"Đã nhận xét {NT.ten_thang(thang).lower()}", n_da,
       f"{n_da / len(BANG):.0%} học sinh" if len(BANG) else None)
ui.kpi(k[2], "Chưa nhận xét", len(BANG) - n_da)
ui.kpi(k[3], f"Đủ {DU} mục", int((BANG["Số mục"] == DU).sum()),
       f"{int((BANG['Đã'] & (BANG['Số mục'] < DU)).sum())} em còn thiếu mục")

ten_tab = [":material/rate_review: Nhận xét tháng"]
if quan_ly:
    ten_tab += [":material/monitoring: Báo cáo", ":material/meeting_room: Phòng & giáo viên"]
# key + on_change="rerun": giữ đúng tab đang mở sau mỗi thao tác, chỉ vẽ tab đang mở
if S.get("nt_tab") not in ten_tab:
    S.pop("nt_tab", None)
tabs = dict(zip(ten_tab, st.tabs(ten_tab, key="nt_tab", on_change="rerun")))


# ------------------------------------------------------------------ lưới thẻ học sinh
def mo_hs(hid: str):
    qp.clear()
    qp["hs"] = hid


def card(r: dict, selected: bool):
    rid = r["id"]
    with ui.card_box(rid, selected):
        menu = ui.card_head(r["Học sinh"], rid, mo_hs)
        if not r["Đã"]:
            tt = ui.pill("Chưa nhận xét", ui.TOKENS["warning"])
        elif r["Số mục"] == DU:
            tt = ui.pill(f"Đủ {DU} mục", ui.TOKENS["success"])
        else:
            tt = ui.pill(f"{r['Số mục']}/{DU} mục", ui.TOKENS["info"])
        trich = r["Trích"]
        trich = escape(trich[:80] + ("…" if len(trich) > 80 else "")) if trich else \
            "Bấm tên để viết nhận xét"
        st.html(f'<p class="tp-card">Lớp <b>{escape(r["Lớp"] or "—")}</b> · '
                f'{escape(r["Phòng"])} &nbsp;{tt}<br><span class="k">{trich}</span></p>')
        with menu:
            st.button("Mở nhận xét", key=f"mo_{rid}", width="stretch", on_click=mo_hs,
                      args=(rid,), icon=":material/open_in_new:")


def render_danh_gia():
    if BANG.empty:
        if quan_ly:
            ui.empty_state("meeting_room", "Chưa có học sinh nội trú",
                           f"Năm học {nam_hoc} chưa có học sinh nội trú. Đặt N.trú, B.trú = Nội "
                           "trú trong Hồ sơ nhập học, rồi xếp phòng ở tab Phòng & giáo viên.")
        else:
            ui.empty_state("meeting_room", "Bạn chưa được phân công phòng nội trú",
                           "Chỉ giáo viên quản nhiệm của phòng, Tổ trưởng quản nhiệm và Quản trị "
                           "mới đánh giá được học sinh. Liên hệ Tổ trưởng quản nhiệm để được "
                           "phân phòng.")
        return
    c1, c2, c3 = st.columns([1.6, 1.2, 2.2], vertical_alignment="bottom")
    q = c1.text_input("Tìm học sinh", key="nt_q", icon=":material/search:",
                      placeholder="Tên học sinh / lớp", label_visibility="collapsed")
    ten_p = list(dict.fromkeys(BANG["Phòng"]))
    chon_p = c2.selectbox("Phòng", ["Tất cả phòng", *ten_p], key="nt_loc_phong",
                          label_visibility="collapsed")
    loc = c3.segmented_control("Trạng thái", ["Tất cả", "Chưa nhận xét", "Còn thiếu mục",
                                              f"Đủ {DU} mục"], default="Tất cả", required=True,
                               key="nt_loc_tt", label_visibility="collapsed")
    v = BANG
    if q.strip():
        v = v[[fold(q) in fold(f"{a} {b}") for a, b in zip(v["Học sinh"], v["Lớp"])]]
    if chon_p != "Tất cả phòng":
        v = v[v["Phòng"] == chon_p]
    if loc == "Chưa nhận xét":
        v = v[~v["Đã"]]
    elif loc == "Còn thiếu mục":
        v = v[v["Đã"] & (v["Số mục"] < DU)]
    elif loc != "Tất cả":
        v = v[v["Số mục"] == DU]
    S["nt_thu_tu"] = v["id"].tolist()  # để "Lưu & em tiếp theo" đi đúng thứ tự đang xem
    ui.card_list(v, "nt", card, qp.get("hs"), filter_state=(q, chon_p, loc, thang), cols=3,
                 height=620)


# ------------------------------------------------------------------ cửa sổ nhận xét một em
def _dong_hs():
    qp.clear()


def _ke_tiep(hid: str) -> str | None:
    ds = S.get("nt_thu_tu") or [i for i, _ in HS_XEM]
    sau = ds[ds.index(hid) + 1:] + ds[:ds.index(hid)] if hid in ds else ds
    return next((i for i in sau if i not in da_dg), None) or (sau[0] if sau else None)


@ui.dialog("Nhận xét nội trú theo tháng", width="large", on_dismiss=_dong_hs)
def danh_gia_dialog(hid: str):
    if hid not in {i for i, _ in HS_XEM}:
        st.warning("Bạn không đánh giá được học sinh này — chỉ giáo viên quản nhiệm của phòng, "
                   "Tổ trưởng quản nhiệm và Quản trị.", icon=":material/lock:")
        return
    h = HS[hid]
    p = o_phong.get(hid)
    cu = da_dg.get(hid) or {}
    c1, c2 = st.columns([3, 1.4], vertical_alignment="center")
    c1.html(f'<p class="tp-card" style="font-size:1rem"><b style="font-size:1.15rem">'
            f'{escape(h["ten"])}</b><br>Lớp <b>{escape(h["lop"] or "—")}</b> · '
            f'{escape((p or {}).get("TenPhong") or CHUA_XEP)}'
            + (f' · GV {escape(p["GiaoVien"])}' if p and p.get("GiaoVien") else "")
            + f' · <b>{NT.ten_thang(thang)}</b></p>')
    with c2:
        if cu:
            st.badge(f"Đã lưu · {cu.get('NguoiDanhGia') or '—'} · "
                     f"{ui.fmt_date(cu.get('NgayDanhGia'))}", icon=":material/check_circle:",
                     color="green", width="stretch")
        else:
            st.badge("Chưa nhận xét tháng này", icon=":material/edit_note:", color="orange",
                     width="stretch")
    truoc = long[(long["HocSinhID"] == hid) & (long["Tháng"] < thang)].sort_values("Tháng")
    if len(truoc):
        with st.expander(f"Nhận xét các tháng trước ({len(truoc)})", icon=":material/history:"):
            t = truoc.assign(Tháng=truoc["Tháng"].map(NT.ten_thang))[["Tháng", *NT.COT_LOI]]
            st.dataframe(t, hide_index=True, width="stretch", height=min(38 + 35 * len(t), 260),
                         column_config={c: st.column_config.TextColumn(width="medium")
                                        for c in NT.COT_LOI})
    kk = f"nt_dg_{hid}_{thang}_{ui.data_version()}"
    with st.form(kk, border=False):
        vals = {}
        for i in range(0, DU, 2):
            for col, key in zip(st.columns(2), NT.KHOAN[i:i + 2]):
                vals[key] = col.text_area(NT.TEN[key], NT._s(cu.get(key)), key=f"{kk}_{key}",
                                          height=110, max_chars=NT.MAX_LOI)
        b1, b2 = st.columns(2)
        luu = b1.form_submit_button("Lưu nhận xét", type="primary", icon=":material/save:",
                                    width="stretch")
        tiep = b2.form_submit_button("Lưu & em tiếp theo", icon=":material/skip_next:",
                                     width="stretch")
    if luu or tiep:
        if ui.mutate(NT.luu_danh_gia_thang, storage, dg, nam_hoc, thang,
                     {"id": hid, "ten": h["ten"], "lop": h["lop"]}, p, vals, ui.current_user(),
                     success=f"Đã lưu nhận xét {h['ten']}") is not None:
            nxt = _ke_tiep(hid) if tiep else None
            qp.clear()
            if nxt and nxt != hid:
                qp["hs"] = nxt
            st.rerun()


# ------------------------------------------------------------------ báo cáo
def render_bao_cao():
    dang_nt = set(HS)
    th = NT.tong_hop_phong(x_thang, phongs, dang_nt)
    x = x_thang[x_thang["HocSinhID"].isin(dang_nt)]
    i = THANG.index(thang)
    n = len(dang_nt)
    n_da = x["HocSinhID"].nunique()
    k = ui.kpi_row(4, key="nt_bc_kpis")
    ui.kpi(k[0], "Hoàn thành nhận xét", f"{n_da / n:.0%}" if n else "—",
           f"{n_da}/{n} học sinh")
    ui.kpi(k[1], f"Đủ {DU} mục", int((x["Số mục"] == DU).sum()),
           f"{int((x['Số mục'] < DU).sum())} em còn thiếu mục")
    ui.kpi(k[2], "Chưa nhận xét", n - n_da)
    ui.kpi(k[3], "Phòng còn em chưa nhận xét",
           int((th["Chưa nhận xét"] > 0).sum()) if len(th) else 0, f"trên {len(phongs)} phòng")

    c1, c2 = st.columns(2, gap="small")
    with c1, ui.section("Tiến độ theo tháng", "Số học sinh đã có nhận xét mỗi tháng"):
        td = NT.tien_do_thang(long[long["HocSinhID"].isin(dang_nt)], THANG[:i + 1], n)
        if td["Đã nhận xét"].sum() == 0:
            ui.empty_state("bar_chart", "Chưa có dữ liệu")
        else:
            BD.ve({"kind": "bar", "data": td, "x": "Tháng", "y": "Đã nhận xét",
                   "giu_thu_tu": True}, height=210, gon=True, key="nt_bc_td")
    with c2, ui.section("Mục đã được nhận xét", f"{NT.ten_thang(thang)} · số học sinh có lời "
                                                "nhận xét ở từng mục"):
        mc = NT.muc_co_nhan_xet(x)
        if mc["Số HS"].sum() == 0:
            ui.empty_state("bar_chart", "Chưa có dữ liệu")
        else:
            BD.ve({"kind": "hbar", "data": mc, "x": "Mục", "y": "Số HS", "giu_thu_tu": True},
                  height=210, gon=True, key="nt_bc_muc")

    with ui.section("Tổng hợp theo phòng", f"{NT.ten_thang(thang)} · nhắc phòng còn em chưa "
                                           "nhận xét"):
        if th.empty:
            ui.empty_state("meeting_room", "Chưa có phòng")
        else:
            st.dataframe(th, hide_index=True, width="stretch",
                         height=min(38 + 35 * len(th), 420), column_config={
                             "Hoàn thành (%)": st.column_config.ProgressColumn(
                                 format="%.0f%%", min_value=0, max_value=100)})
    nx = NT.nhan_xet(x)
    with ui.section(f"Nhận xét {NT.ten_thang(thang).lower()}", f"{len(nx)} học sinh · bấm vào "
                                                             "ô để đọc đầy đủ"):
        tim = st.text_input("Tìm trong nhận xét", key="nt_bc_tim", icon=":material/search:",
                            placeholder="Tên học sinh, phòng hoặc nội dung nhận xét",
                            label_visibility="collapsed")
        if tim.strip():
            nx = nx[[fold(tim) in fold(" ".join(map(str, r)))
                     for r in nx.itertuples(index=False)]]
        if nx.empty:
            st.caption("Chưa có lời nhận xét nào phù hợp.")
        else:
            st.dataframe(nx.drop(columns=["Tháng"]), hide_index=True, width="stretch",
                         height=min(38 + 35 * len(nx), 520),
                         column_config={c: st.column_config.TextColumn(width="medium")
                                        for c in NT.COT_LOI})
    nam = long[long["HocSinhID"].isin(dang_nt)]
    ui.download_excel("Tải báo cáo (Excel)", {
        "Tong_hop_phong": th,
        "Thang_nay": x.drop(columns=["PhongID", "HocSinhID", "Số mục"]).assign(
            Tháng=lambda d: d["Tháng"].map(NT.ten_thang)),
        "Ca_nam": nam.drop(columns=["PhongID", "HocSinhID", "Số mục"]).assign(
            Tháng=lambda d: d["Tháng"].map(NT.ten_thang))},
        f"BaoCaoNoiTru_{thang}.xlsx", primary=True, key="nt_bc_xls")


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
        ca = st.checkbox(f"Chọn tất cả {len(ds)} em đang hiện", key="nt_cx_ca")
        bang = pd.DataFrame([{"Chọn": ca, "id": i, "Họ tên": HS[i]["ten"],
                              "Lớp": HS[i]["lop"], "Giới tính": HS[i]["gt"]} for i in ds],
                            columns=["Chọn", "id", "Họ tên", "Lớp", "Giới tính"])
        sua = st.data_editor(bang, hide_index=True, width="stretch",
                             height=min(38 + 35 * max(len(bang), 1), 360),
                             disabled=["Họ tên", "Lớp", "Giới tính"],
                             column_config={"id": None,
                                            "Chọn": st.column_config.CheckboxColumn(width="small")},
                             key=f"nt_cx_ed_{tim}_{khoi}_{gt}_{ca}_{ui.data_version()}")
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
        c1, c2 = st.columns([3.2, 1.2], vertical_alignment="center")
        c1.caption("Em không ở nội trú nữa: chuyển sang **Bán trú** — đổi cả hồ sơ nhập học "
                   "(N.trú, B.trú) và Data tuyển sinh (Chế độ); các em ra khỏi danh sách nội trú.")
        if c2.button(f"Chuyển {len(chon)} em sang Bán trú", width="stretch",
                     icon=":material/swap_horiz:", disabled=not chon, key="nt_cx_bt"):
            if ui.mutate(NT.chuyen_ban_tru, storage, ui.records(NHAP_HOC),
                         ui.records(TUYEN_SINH), chon,
                         success=f"Đã chuyển {len(chon)} em sang Bán trú") is not None:
                S.pop("nt_cx_ca", None)
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
        if "Nhận xét" in ten:
            render_danh_gia()
        elif "Báo cáo" in ten:
            render_bao_cao()
        else:
            render_phong()

ui.chay_mo_sau()
if qp.get("hs") and not ui.dialog_da_mo():  # bấm tên học sinh -> cửa sổ đánh giá, nền mờ
    danh_gia_dialog(qp.get("hs"))
