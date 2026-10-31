"""Cài đặt & đồng bộ: tài khoản, nhập / xuất dữ liệu, danh mục, kết nối SharePoint."""
import hmac

import pandas as pd
import streamlit as st

from tuyensinh import config, importer, services, tai_khoan, ui
from tuyensinh import noi_tru as NT
from tuyensinh.schema import (ALL_LISTS, GIAY_TO, GIAY_TO_NHAP_HOC, NHAP_HOC, NOI_TRU_DANH_GIA,
                              NOI_TRU_PHONG, QUYEN_MAC_DINH, TAI_KHOAN, TRANG, TUYEN_SINH, VAI_TRO)
from tuyensinh.ui_noi_tru import nhap_phan_phong

S = st.session_state
ui.page_header("Cài đặt & đồng bộ", "Tài khoản · nhập / xuất dữ liệu · danh mục · kết nối "
               "SharePoint")

# Bảo vệ trang bằng mật khẩu quản trị (ADMIN_PASSWORD trong Secrets), nếu có đặt
pw = config.get("ADMIN_PASSWORD")
if S.get("tk") and not ui.is_admin():
    with ui.section("Cần quyền quản trị"):
        st.info("Trang Cài đặt chỉ dành cho tài khoản vai trò **Quản trị**.",
                icon=":material/lock:")
    st.stop()
if pw and not S.get("_admin_ok") and not ui.is_admin():
    with ui.section("Cần quyền quản trị"):
        entered = st.text_input("Mật khẩu quản trị", type="password")
        if st.button("Mở khóa", type="primary", icon=":material/lock_open:"):
            if hmac.compare_digest(entered, str(pw)):
                S["_admin_ok"] = True
                st.rerun()
            st.error("Sai mật khẩu.")
    st.stop()

backend = config.backend()
storage = ui.storage()
MOI = "＋ Thêm khối mới"


def _khoi_key(k: str):
    a, _, b = k.partition("-")
    return (int(a) if a.isdigit() else 99, b)


MOI_TK = "＋ Thêm tài khoản mới"


def render_tai_khoan():
    """Danh sách tài khoản đăng nhập + trang được phép của từng người."""
    items = ui.records(TAI_KHOAN, optional=True)
    err = ui.list_error(TAI_KHOAN)
    ten_list = config.list_name(TAI_KHOAN.name)
    if err and "does not exist" not in err and "404" not in err:
        st.error(f"Không đọc được list **{ten_list}** (lỗi kết nối). Bấm ⟳ để thử lại.",
                 icon=":material/cloud_off:")
        return
    if err:
        c1, c2 = st.columns([3, 1.2], vertical_alignment="center")
        c1.warning(f"Chưa có list **{ten_list}** trên SharePoint — bấm nút bên cạnh để tạo, "
                   "sau đó thêm tài khoản.", icon=":material/info:")
        if c2.button("Tạo list tài khoản", type="primary", icon=":material/playlist_add:",
                     width="stretch", disabled=backend == "local"):
            with st.status("Đang tạo list…", expanded=True) as stt:
                try:
                    importer.setup_lists(storage, log=stt.write, lists=[TAI_KHOAN])
                    stt.update(label="Đã tạo list", state="complete")
                except Exception as e:
                    stt.update(label="Không tạo được list", state="error")
                    ui.error_state(e, compact=True)
                    return
            ui.refresh()
            st.rerun()
        return

    hd = tai_khoan.dang_hoat_dong(items)
    if not hd:
        st.info("Chưa có tài khoản nào: app đang mở tự do (ai cũng vào được). Tạo **tài khoản "
                "Quản trị đầu tiên cho bạn** — sau đó mọi người phải đăng nhập.",
                icon=":material/info:")
    elif not any(t.get("VaiTro") == "Quản trị" for t in hd):
        st.warning("Chưa có tài khoản **Quản trị** đang hoạt động — không ai vào được trang "
                   "Cài đặt bằng tài khoản. Hãy đặt ít nhất 1 người là Quản trị.",
                   icon=":material/warning:")

    left, right = st.columns([1.5, 1.2], gap="medium")
    with left, ui.section("Danh sách tài khoản", f"{len(hd)} đang hoạt động / {len(items)}"):
        if items:
            df = pd.DataFrame([{
                "Họ tên": t.get("HoTen"), "Tên đăng nhập": t.get("TenDangNhap"),
                "Vai trò": t.get("VaiTro"), "Trang được phép": ", ".join(tai_khoan.quyen(t)),
                "Hoạt động": str(t.get("HoatDong") or "Có") != "Không"} for t in items])
            st.dataframe(df, hide_index=True, width="stretch",
                         height=min(520, 38 + 35 * len(df)),
                         column_config={"Hoạt động": st.column_config.CheckboxColumn(width="small"),
                                        "Trang được phép": st.column_config.TextColumn(
                                            width="large")})
        else:
            ui.empty_state("group", "Chưa có tài khoản")
        st.caption("Vai trò Quản trị luôn có mọi trang (gồm Cài đặt). Người dùng tự đổi mật khẩu "
                   "ở góc phải thanh menu. Đổi mật khẩu / khóa tài khoản: các máy đang ghi nhớ "
                   "đăng nhập phải đăng nhập lại.")
    with right, ui.section("Thêm / sửa tài khoản"):
        theo_ten = {f"{t.get('HoTen')} ({t.get('TenDangNhap')})": t for t in items}
        chon = st.selectbox("Tài khoản", [MOI_TK, *theo_ten], key="tk_chon")
        t = theo_ten.get(chon, {})
        k = f"tk_{t.get('id', 'moi')}_{ui.data_version()}"
        ho_ten = st.text_input("Họ tên *", t.get("HoTen", ""), key=f"{k}_ten",
                               help="Tên này ghi vào hồ sơ: người nhập, người nhận hồ sơ")
        ten_dn = st.text_input("Tên đăng nhập *", t.get("TenDangNhap", ""), key=f"{k}_dn")
        co_qt = any(x.get("VaiTro") == "Quản trị" for x in hd)
        vai_mac_dinh = "Quản trị" if not co_qt and not t else (t.get("VaiTro") or "Tuyển sinh")
        vai = st.selectbox("Vai trò", VAI_TRO, index=VAI_TRO.index(vai_mac_dinh)
                           if vai_mac_dinh in VAI_TRO else 1, key=f"{k}_vai")
        if vai == "Quản trị":
            trang = list(TRANG)
            st.caption("Quản trị: được vào tất cả các trang.")
        else:
            co = tai_khoan.quyen(t) if t and t.get("VaiTro") == vai else \
                list(QUYEN_MAC_DINH.get(vai, ()))
            trang = st.multiselect("Trang được phép", [x for x in TRANG
                                                        if x != "Cài đặt & đồng bộ"],
                                   default=[x for x in co if x != "Cài đặt & đồng bộ"],
                                   key=f"{k}_trang_{vai}")
        mk = st.text_input("Mật khẩu" + (" *" if not t else " mới (để trống = giữ nguyên)"),
                           type="password", key=f"{k}_mk")
        hoat = st.toggle("Đang hoạt động", value=str(t.get("HoatDong") or "Có") != "Không",
                         key=f"{k}_hd", help="Tắt để khóa tài khoản (nghỉ việc…)")
        if st.button("Lưu tài khoản", type="primary", icon=":material/save:", width="stretch"):
            if ui.mutate(tai_khoan.luu, storage, items, ho_ten, ten_dn, vai, mk or None, hoat,
                         t.get("id"), trang, success=f"Đã lưu tài khoản {ten_dn}") is not None:
                S.pop("tk_chon", None)
                st.rerun()


def render_giay_to():
    """Chỉnh danh sách giấy tờ cần nộp của từng khối — lưu trên list DanhMuc_GiayTo."""
    items = ui.records(GIAY_TO, optional=True)
    err = ui.list_error(GIAY_TO)
    bang_sp = services.giay_to_tu_list(items)
    bang = bang_sp or services.giay_to_mac_dinh()
    ten_list = config.list_name(GIAY_TO.name)
    if err and "does not exist" not in err and "404" not in err:
        st.error(f"Không đọc được list **{ten_list}** (lỗi kết nối, không phải do chưa có list) — "
                 "app tạm dùng danh mục mặc định. Bấm ⟳ trên thanh menu để thử lại.",
                 icon=":material/cloud_off:")
        with st.expander("Chi tiết lỗi"):
            st.code(err[:1500], language=None)
    elif err:
        c1, c2 = st.columns([3, 1.2], vertical_alignment="center")
        c1.warning(f"Chưa có list **{ten_list}** trên SharePoint — app đang dùng danh mục mặc "
                   "định (Book1). Bấm nút bên cạnh để tạo list và chép danh mục mặc định lên, "
                   "sau đó chỉnh sửa tại đây.", icon=":material/info:")
        if c2.button("Tạo list giấy tờ", type="primary", icon=":material/playlist_add:",
                     width="stretch", disabled=backend == "local"):
            with st.status("Đang tạo list…", expanded=True) as stt:
                try:
                    importer.setup_lists(storage, log=stt.write, lists=[GIAY_TO])
                    stt.write("Chép danh mục mặc định (Book1)…")
                    for k, v in services.giay_to_mac_dinh().items():
                        services.luu_giay_to_khoi(storage, k, v, [])
                    stt.update(label="Đã tạo list và chép danh mục", state="complete")
                except Exception as e:
                    stt.update(label="Không tạo được list", state="error")
                    ui.error_state(e, compact=True)
                    return
            ui.refresh()
            st.rerun()
    elif not bang_sp:
        c1, c2 = st.columns([3, 1.2], vertical_alignment="center")
        c1.info(f"List **{ten_list}** đang trống — app dùng danh mục mặc định (Book1). Lần lưu "
                "đầu tiên sẽ chép toàn bộ danh mục mặc định lên SharePoint.",
                icon=":material/info:")
        if c2.button("Chép danh mục mặc định lên", icon=":material/cloud_upload:",
                     width="stretch"):
            def seed():
                for k, ds in services.giay_to_mac_dinh().items():
                    services.luu_giay_to_khoi(storage, k, ds, [])
            if ui.mutate(seed, success="Đã chép danh mục mặc định lên SharePoint") is not None:
                st.rerun()

    left, right = st.columns([1.1, 1.6], gap="medium")
    with left, ui.section("Danh mục hiện tại", f"{len(bang)} khối · nguồn: "
                          + ("SharePoint" if bang_sp else "mặc định (Book1)")):
        tong = pd.DataFrame([{"Khối": k, "Số giấy tờ": len(v)} for k, v in
                             sorted(bang.items(), key=lambda kv: _khoi_key(kv[0]))])
        st.dataframe(tong, hide_index=True, width="stretch",
                     height=min(520, 38 + 35 * max(len(tong), 1)))
    with right, ui.section("Chỉnh sửa giấy tờ của một khối",
                           "Chọn khối, thêm / bớt giấy tờ rồi bấm Lưu. Thứ tự trong ô là thứ tự "
                           "hiện khi thu hồ sơ."):
        khois = sorted(bang, key=_khoi_key)
        c1, c2 = st.columns(2)
        chon = c1.selectbox("Khối", [*khois, MOI], key="dm_khoi")
        if chon == MOI:
            khoi = c2.text_input("Tên khối mới", placeholder="Vd: 6, 10-IEP, 11-ESL",
                                 key="dm_khoi_moi").strip()
            mau = st.selectbox("Sao chép từ khối", ["(Trống)", *khois], key="dm_mau")
            hien_tai = [] if mau == "(Trống)" else bang[mau]
        else:
            khoi, hien_tai = chon, bang.get(chon, [])
            c2.caption(f"Khối **{khoi}** có **{len(hien_tai)}** giấy tờ. Ghi khối kèm phân hệ "
                       "(10-IEP) để tách IEP/ESL; ghi số khối (7) để dùng chung.")
        tat_ca = list(dict.fromkeys([*GIAY_TO_NHAP_HOC, *[g for v in bang.values() for g in v]]))
        ds = st.multiselect("Giấy tờ cần nộp", tat_ca, default=hien_tai, accept_new_options=True,
                            key=f"dm_ds_{khoi}_{ui.data_version()}",
                            placeholder="Chọn hoặc gõ tên giấy tờ mới rồi Enter")
        b1, b2 = st.columns(2)
        luu = b1.button(f"Lưu khối {khoi or '…'}", type="primary", icon=":material/save:",
                        width="stretch", disabled=bool(err) or not khoi or not ds)
        xoa = b2.button(f"Xóa khối {khoi or '…'}", icon=":material/delete:", width="stretch",
                        disabled=bool(err) or chon == MOI or not bang_sp)
        if luu:
            def save():
                if not bang_sp:  # lần đầu: chép các khối khác từ mặc định để không bị mất
                    for k, v in services.giay_to_mac_dinh().items():
                        if k != khoi:
                            services.luu_giay_to_khoi(storage, k, v, [])
                return services.luu_giay_to_khoi(storage, khoi, ds, items)
            if ui.mutate(save, success=f"Đã lưu {len(ds)} giấy tờ cho khối {khoi}") is not None:
                st.rerun()
        if xoa:
            if ui.mutate(services.luu_giay_to_khoi, storage, khoi, [], items,
                         success=f"Đã xóa khối {khoi}") is not None:
                st.rerun()
        if err:
            st.caption("Chưa lưu được vì chưa có list trên SharePoint.")

# ------------------------------------------------------------------ tình trạng chung
_tks = tai_khoan.dang_hoat_dong(ui.records(TAI_KHOAN, optional=True))
_k = ui.kpi_row(4, key="cd_kpis")
ui.kpi(_k[0], "Nơi lưu dữ liệu", "SharePoint" if backend != "local" else "Máy thử",
       "qua Power Automate" if backend == "powerautomate" else
       ("dữ liệu sẽ mất khi khởi động lại" if backend == "local" else backend))
ui.kpi(_k[1], "Tài khoản đang hoạt động", len(_tks))
ui.kpi(_k[2], "Dữ liệu tải lúc", f"{ui.loaded_at():%H:%M}", f"{ui.loaded_at():%d/%m/%Y}")
with _k[3]:
    st.button("Tải lại dữ liệu", icon=":material/refresh:", on_click=ui.refresh,
              width="stretch", help="Đọc lại toàn bộ list từ SharePoint")
    st.caption("Sửa thẳng trên SharePoint sẽ hiện lên app sau tối đa 10 phút, hoặc bấm nút này.")

tab_tk, tab_dl, tab_dm, tab_kn = st.tabs([":material/manage_accounts: Tài khoản & phân quyền",
                                         ":material/swap_vert: Nhập / xuất dữ liệu",
                                         ":material/checklist: Danh mục",
                                         ":material/cloud_sync: Kết nối SharePoint"],
                                        key="cd_tab", on_change="rerun")

# ------------------------------------------------------------------ nhập Excel
TEN_MAU = {TUYEN_SINH.name: "Data tuyển sinh", NHAP_HOC.name: "Hồ sơ nhập học",
           GIAY_TO.name: "Danh mục giấy tờ", TAI_KHOAN.name: "Tài khoản đăng nhập",
           NOI_TRU_PHONG.name: "Nội trú: phân phòng", NOI_TRU_DANH_GIA.name: "Nội trú: đánh giá"}


def _bao_loi(errors: list[dict]):
    if errors:
        err = pd.DataFrame(errors)
        st.dataframe(err, hide_index=True, width="stretch")
        ui.download_excel("Tải danh sách lỗi", err, "LoiNhapDuLieu.xlsx", key="dl_err")
        st.caption("Sửa lỗi rồi bấm nhập lại — các dòng đã ghi sẽ được bỏ qua.")


def render_nhap(up):
    """Bước 2: chọn list, xem trước, nhập."""
    try:
        sheets = pd.ExcelFile(up).sheet_names if up.name.lower().endswith(".xlsx") else []
    except Exception:
        sheets = []
    c1, c2, c3 = st.columns(3)
    guess = importer.guess_list(sheets)
    ld = c1.selectbox("Nhập vào list", ALL_LISTS, index=ALL_LISTS.index(guess),
                      format_func=lambda x: f"{TEN_MAU[x.name]} ({config.list_name(x.name)})")
    ld = next(x for x in ALL_LISTS if x.name == ld.name)  # selectbox trả bản sao, không phải chính đối tượng
    co_nam = ld not in (GIAY_TO, TAI_KHOAN)
    nam = c3.selectbox("Năm học" + (" cho dòng để trống" if ld in (TUYEN_SINH, NHAP_HOC) else ""),
                       config.school_years(), disabled=not co_nam,
                       index=config.school_years().index(ui.nam_hoc())
                       if ui.nam_hoc() in config.school_years() else 0)
    if ld is NOI_TRU_PHONG:  # ghép học sinh với hồ sơ nhập học rồi tạo phòng
        up.seek(0)
        nhap_phan_phong(up, storage, nam, ui.records(NOI_TRU_PHONG, optional=True),
                        ui.records(NHAP_HOC), ui.records(TAI_KHOAN, optional=True), "cd_nt")
        return
    default_sheet = ld.name if ld.name in sheets else (sheets[0] if sheets else None)
    sheet = c2.selectbox("Sheet", sheets, index=sheets.index(default_sheet)) if sheets else None
    du_lieu = ld in (TUYEN_SINH, NHAP_HOC)
    vemis = du_lieu and st.checkbox(
        "File theo biểu mẫu VEMIS (Danh sách học sinh, 2 dòng tiêu đề)", value=False,
        disabled=ld is not NHAP_HOC)
    bo_sung = keep_all = False
    if du_lieu:
        mode = st.radio("Cách nhập", ["Thêm dòng mới (bỏ qua dòng đã có)",
                                      "Bổ sung ô còn trống cho dòng đã có"], horizontal=True,
                        help="Bổ sung: điền các ô đang trống trên SharePoint (vd cột Khối bị "
                             "mất khi tạo list từ Excel) — không thêm dòng, không ghi đè ô đã có.")
        bo_sung = mode.startswith("Bổ sung")
        keep_all = st.checkbox("Giữ nguyên dữ liệu cũ (ghi cả dòng thiếu trường bắt buộc)",
                               value=True, disabled=bo_sung)
    try:
        up.seek(0)
        df, skipped = importer.read_frame(up, ld, sheet, vemis and ld is NHAP_HOC)
    except Exception as e:
        ui.error_state(e, compact=True)
        return
    st.caption(f"**{len(df)}** dòng · {len(df.columns)} cột nhận được"
               + (f" · bỏ qua cột: {', '.join(skipped)}" if skipped else ""))
    xem = df.head(20)
    if "MatKhau" in xem.columns:  # không hiện mật khẩu trên màn hình
        xem = xem.assign(MatKhau="••••••")
    st.dataframe(xem, hide_index=True, width="stretch", height=260)
    if bo_sung:
        if st.button(f"Bổ sung ô trống từ {len(df)} dòng", type="primary",
                     icon=":material/format_color_fill:", disabled=df.empty):
            bar = st.progress(0.0, text="Đang đọc dữ liệu trên SharePoint…")
            try:
                res = importer.fill_blanks(
                    storage, ld, df, nam,
                    progress=lambda d, t: bar.progress(d / max(t, 1),
                                                       text=f"Đã cập nhật {d}/{t} dòng"))
            except Exception as e:
                ui.error_state(e, compact=True)
            else:
                ui.invalidate()
                bar.progress(1.0, text="Hoàn tất")
                st.success(f"Đã bổ sung **{res['cells']}** ô trên **{res['updated']}** dòng · "
                           f"{res['not_found']} dòng trong file không tìm thấy trên list",
                           icon=":material/check_circle:")
        return
    if not st.button(f"Nhập {len(df)} dòng lên {config.list_name(ld.name)}", type="primary",
                     icon=":material/cloud_upload:", disabled=df.empty):
        return
    bar = st.progress(0.0, text="Đang chuẩn bị…")

    def prog(done, total):
        bar.progress(done / max(total, 1), text=f"Đã ghi {done}/{total}")

    try:
        if ld is TAI_KHOAN:
            res = importer.nhap_tai_khoan(storage, df, ui.records(TAI_KHOAN, optional=True))
            msg = (f"Đã tạo **{res['ok']}** tài khoản · bỏ qua **{res['skipped']}** tên đăng nhập "
                   f"đã có · lỗi **{len(res['errors'])}**")
        elif ld is NOI_TRU_DANH_GIA:
            res = NT.nhap_danh_gia(storage, df, ui.records(NOI_TRU_PHONG, optional=True),
                                   ui.records(NOI_TRU_DANH_GIA, optional=True), nam,
                                   ui.records(NHAP_HOC), ui.current_user(), progress=prog)
            msg = (f"Đã ghi đánh giá **{res['ok']}** lượt học sinh ({res['ban_ghi']} phòng-ngày)"
                   f" · lỗi **{len(res['errors'])}**")
        else:
            res = importer.import_rows(storage, ld, df, nam, keep_all=keep_all or not du_lieu,
                                       skip_existing=True, progress=prog)
            msg = (f"Đã ghi **{res['ok']}** dòng · bỏ qua **{res['skipped']}** dòng đã có"
                   f" · lỗi **{len(res['errors'])}**"
                   + (f" · liên kết **{res['linked']}** hồ sơ với Data tuyển sinh"
                      if ld is NHAP_HOC else ""))
    except Exception as e:
        ui.error_state(e, compact=True)
        return
    ui.invalidate()
    bar.progress(1.0, text="Hoàn tất")
    st.success(msg, icon=":material/check_circle:")
    _bao_loi(res["errors"])
    if ld is TAI_KHOAN:
        st.warning("Đã nhập xong: hãy **xóa file chứa mật khẩu** trên máy.",
                   icon=":material/delete:")


# ------------------------------------------------------------------ tài khoản
with tab_tk:
    render_tai_khoan()

# ------------------------------------------------------------------ danh mục
with tab_dm:
    render_giay_to()

# ------------------------------------------------------------------ nhập / xuất
with tab_dl:
    with ui.section("Việc dữ liệu ở các trang khác"):
        st.markdown("- **Chuyển học sinh cũ sang năm mới**: Hồ sơ nhập học → *Công cụ* → "
                    "*Lên lớp từ năm trước*.\n"
                    "- **Danh sách nội trú & phân phòng từ Excel**: Nội trú → *Phòng & giáo viên*.")
    # ------------------------------------------------------------------ 3. nhập Excel
    with ui.section("Nhập dữ liệu từ Excel",
                    "Có file mẫu cho cả 6 list SharePoint. Điền theo sheet HuongDan trong file, tải "
                    "lên, xem trước rồi bấm Nhập — app tự nhận list theo tên sheet. Nhận cả file "
                    "Export to Excel từ list và file VEMIS. Chạy lại an toàn: dòng đã có được bỏ "
                    "qua."):
        st.markdown("**Bước 1 — Tải file mẫu** của list cần nhập")
        g = st.columns(3)
        for i, ld_mau in enumerate(ALL_LISTS):
            g[i % 3].download_button(
                TEN_MAU[ld_mau.name], lambda ld_mau=ld_mau: importer.file_mau(ld_mau),
                file_name=f"Mau_{ld_mau.name}.xlsx", mime=ui.XLSX, on_click="ignore",
                icon=":material/download:", width="stretch", key=f"mau_{ld_mau.name}",
                help=f"List {config.list_name(ld_mau.name)}. Cột cam là bắt buộc, có ô chọn sẵn "
                     "và sheet HuongDan giải thích từng cột.")
        up = st.file_uploader("Bước 2 — Tải lên file đã điền", type=["xlsx", "csv"])
        if up is not None:
            render_nhap(up)

    # ------------------------------------------------------------------ 4. liên kết
    with ui.section("Liên kết hồ sơ nhập học với Data tuyển sinh",
                    "Dùng khi đưa Data_NhapHoc lên SharePoint bằng tay (tạo list từ Excel): gán "
                    "TuyenSinhID theo họ tên + SĐT / ngày sinh để nút Tạo hồ sơ không tạo trùng."):
        if st.button("Liên kết hồ sơ", icon=":material/link:", disabled=backend == "local"):
            bar = st.progress(0.0, text="Đang đọc dữ liệu…")
            try:
                res = importer.link_existing(
                    storage, progress=lambda d, t: bar.progress(d / max(t, 1),
                                                                text=f"Đã cập nhật {d}/{t} hồ sơ"))
            except Exception as e:
                ui.error_state(e, compact=True)
            else:
                ui.invalidate()
                bar.progress(1.0, text="Hoàn tất")
                st.success(f"{res['total']} hồ sơ · {res['chua_lien_ket']} hồ sơ chưa liên kết · "
                           f"liên kết được **{res['lien_ket']}**", icon=":material/check_circle:")

    with ui.section("Sao lưu dữ liệu",
                    "Tải toàn bộ dữ liệu (mọi năm học) ra một file Excel, mỗi list một sheet — "
                    "nên tải định kỳ để lưu trữ."):
        def _sao_luu():
            frames = {}
            for ld in (TUYEN_SINH, NHAP_HOC, NOI_TRU_PHONG, NOI_TRU_DANH_GIA, GIAY_TO):
                try:
                    frames[ld.name[:31]] = ui.df(ld)
                except Exception:
                    continue
            return ui.excel_bytes(frames)
        st.download_button("Tải bản sao lưu (Excel)", _sao_luu, icon=":material/backup:",
                           file_name=f"SaoLuu_TuyenSinh_{pd.Timestamp.now():%Y%m%d}.xlsx",
                           mime=ui.XLSX, on_click="ignore", type="primary")
        st.caption("Không gồm list tài khoản (có mật khẩu đã mã hóa).")

# ------------------------------------------------------------------ kết nối SharePoint
with tab_kn:
    # ------------------------------------------------------------------ 1. kết nối
    with ui.section("1. Kết nối", "App ghi/đọc SharePoint thông qua một flow Power Automate "
                    "(xem hướng dẫn tạo flow ở cuối trang)."):
        names = {"powerautomate": "Power Automate → SharePoint", "sharepoint": "Microsoft Graph → SharePoint",
                 "local": "Máy cục bộ (thử nghiệm) — dữ liệu KHÔNG lên SharePoint"}
        url = str(config.get("PA_FLOW_URL") or config.section("powerautomate").get("flow_url") or "")
        ui.kv([("Cách lưu dữ liệu", names.get(backend, backend)),
               ("Flow URL", (url[:48] + "…" + url[-8:]) if len(url) > 60 else (url or "—")),
               ("Các list SharePoint", ", ".join(config.list_name(ld.name)
                                                 for ld in ALL_LISTS))])
        if backend == "local":
            st.warning("Đang lưu trên máy chủ app, sẽ **mất khi app khởi động lại**. Làm theo hướng dẫn "
                       "bên dưới để chuyển sang SharePoint.", icon=":material/warning:")

        if st.button("Kiểm tra kết nối", icon=":material/lan:", disabled=backend == "local"):
            with st.spinner("Đang gọi flow…"):
                S["_check"] = importer.check_lists(storage)
        for row in S.get("_check", []):
            ld = row["list"]
            if row["loi"]:
                ui.error_state(RuntimeError(row["loi"]), compact=True)
                continue
            if not row["co_list"]:
                site = row.get("site") or "site đang cấu hình trong flow"
                msg = f"**{row['ten']}**: chưa có list trên **{site}**."
                others = row.get("lists_on_site")
                if others is not None:
                    msg += (" Các list đang có trên site này: " + (", ".join(others) or "(không có)")
                            + ". Nếu list của bạn nằm ở site khác, sửa **Site Address** trong bước "
                              "*Send an HTTP request to SharePoint* của flow; nếu tên list khác, sửa "
                              f"`SP_LIST_{ld.name}` trong Secrets. Chưa có thì bấm *Tạo list / thêm "
                              "cột* ở bước 2.")
                else:
                    msg += " Bấm *Tạo list / thêm cột* ở bước 2."
                st.warning(msg, icon=":material/playlist_add:")
            elif row["thieu"]:
                st.warning(f"**{row['ten']}**: kết nối được, khớp {len(row['khop'])} cột, thiếu "
                           f"{len(row['thieu'])} cột: "
                           + ", ".join(ld.get(k).sp_title for k in row["thieu"]),
                           icon=":material/rule:")
            else:
                st.success(f"**{row['ten']}**: kết nối được, đủ {len(row['khop'])} cột.",
                           icon=":material/check_circle:")

    # ------------------------------------------------------------------ 2. tạo list
    with ui.section("2. Tạo list / thêm cột còn thiếu",
                    f"Tạo / cập nhật toàn bộ {len(ALL_LISTS)} list SharePoint của app (list chưa có "
                    "thì tạo mới, list đã có thì thêm cột còn thiếu). Không xóa hay đổi cột đã có. "
                    "Tài khoản chạy flow cần quyền Owner trên site."):
        tinh_trang = {r["list"].name: r for r in S.get("_check", [])}

        def _tt(ld) -> str:
            r = tinh_trang.get(ld.name)
            if r is None:
                return "Chưa kiểm tra"
            if r["loi"]:
                return "Lỗi kết nối"
            if not r["co_list"]:
                return "Chưa có list"
            return f"Thiếu {len(r['thieu'])} cột" if r["thieu"] else "Đủ cột"

        st.dataframe(pd.DataFrame([{
            "List trên SharePoint": config.list_name(ld.name), "Dùng cho": ld.title,
            "Số cột": len(ld.fields), "Tình trạng": _tt(ld)} for ld in ALL_LISTS]),
            hide_index=True, width="stretch", column_config={
                "Dùng cho": st.column_config.TextColumn(width="large")})
        b1, b2 = st.columns(2)
        if b1.button("Tạo list / thêm cột (tất cả)", type="primary",
                     icon=":material/playlist_add:", disabled=backend == "local",
                     width="stretch"):
            try:
                with st.status("Đang thiết lập…", expanded=True) as stt:
                    importer.setup_lists(storage, log=stt.write, lists=ALL_LISTS)
                    stt.update(label="Đã thiết lập xong — đang kiểm tra lại…", state="running")
                    S["_check"] = importer.check_lists(storage)
                    stt.update(label="Đã thiết lập xong", state="complete")
                ui.refresh()
                st.rerun()
            except Exception as e:
                ui.error_state(e, compact=True)
        if b2.button("Kiểm tra tình trạng các list", icon=":material/fact_check:",
                     disabled=backend == "local", width="stretch"):
            with st.spinner("Đang kiểm tra…"):
                S["_check"] = importer.check_lists(storage)
            st.rerun()

    # ------------------------------------------------------------------ hướng dẫn
    with st.expander("Hướng dẫn tạo flow Power Automate và khai báo Secrets", icon=":material/help:"):
        st.markdown(open("docs/power_automate.md", encoding="utf-8").read())
