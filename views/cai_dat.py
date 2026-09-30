"""Cài đặt & đồng bộ: kiểm tra kết nối Power Automate/SharePoint, tạo list, nhập dữ liệu Excel."""
import hmac

import pandas as pd
import streamlit as st

from tuyensinh import config, importer, ui
from tuyensinh.schema import NHAP_HOC, TUYEN_SINH

S = st.session_state
ui.page_header("Cài đặt & đồng bộ", "Kết nối SharePoint qua Power Automate, tạo list và "
               "đưa dữ liệu cũ lên")

# Bảo vệ trang bằng mật khẩu quản trị (ADMIN_PASSWORD trong Secrets), nếu có đặt
pw = config.get("ADMIN_PASSWORD")
if pw and not S.get("_admin_ok"):
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

# ------------------------------------------------------------------ 1. kết nối
with ui.section("1. Kết nối", "App ghi/đọc SharePoint thông qua một flow Power Automate "
                "(xem hướng dẫn tạo flow ở cuối trang)."):
    names = {"powerautomate": "Power Automate → SharePoint", "sharepoint": "Microsoft Graph → SharePoint",
             "local": "Máy cục bộ (thử nghiệm) — dữ liệu KHÔNG lên SharePoint"}
    url = str(config.get("PA_FLOW_URL") or config.section("powerautomate").get("flow_url") or "")
    ui.kv([("Cách lưu dữ liệu", names.get(backend, backend)),
           ("Flow URL", (url[:48] + "…" + url[-8:]) if len(url) > 60 else (url or "—")),
           ("List Data tuyển sinh", config.list_name(TUYEN_SINH.name)),
           ("List Hồ sơ nhập học", config.list_name(NHAP_HOC.name))])
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
                "Tạo list Data_TuyenSinh, Data_NhapHoc (nếu chưa có) và thêm cột còn thiếu. "
                "Không xóa hay đổi cột đã có. Tài khoản chạy flow cần quyền Owner trên site."):
    if st.button("Tạo list / thêm cột", icon=":material/playlist_add:",
                 disabled=backend == "local"):
        logs = []
        try:
            with st.status("Đang thiết lập…", expanded=True) as stt:
                importer.setup_lists(storage, log=lambda m: (logs.append(m), stt.write(m)))
                stt.update(label="Đã thiết lập xong", state="complete")
            S.pop("_check", None)
        except Exception as e:
            ui.error_state(e, compact=True)

# ------------------------------------------------------------------ 3. nhập Excel
with ui.section("3. Nhập dữ liệu từ Excel",
                "Dùng file Data_TuyenSinh_chuan_hoa.xlsx (hoặc file Export to Excel từ list). "
                "Chạy lại an toàn: dòng đã có trên list sẽ được bỏ qua."):
    up = st.file_uploader("File Excel", type=["xlsx", "csv"])
    if up is not None:
        try:
            sheets = pd.ExcelFile(up).sheet_names if up.name.lower().endswith(".xlsx") else []
        except Exception:
            sheets = []
        c1, c2, c3 = st.columns(3)
        guess = importer.guess_list(sheets)
        ld = c1.selectbox("Nhập vào list", [TUYEN_SINH, NHAP_HOC], index=[TUYEN_SINH, NHAP_HOC].index(guess),
                          format_func=lambda x: f"{x.title} ({config.list_name(x.name)})")
        default_sheet = ld.name if ld.name in sheets else (sheets[0] if sheets else None)
        sheet = c2.selectbox("Sheet", sheets, index=sheets.index(default_sheet)) if sheets else None
        nam = c3.selectbox("Năm học cho dòng để trống", config.school_years(),
                           index=config.school_years().index(ui.nam_hoc())
                           if ui.nam_hoc() in config.school_years() else 0)
        vemis = st.checkbox("File theo biểu mẫu VEMIS (Danh sách học sinh, 2 dòng tiêu đề)",
                            value=False, disabled=ld is not NHAP_HOC)
        keep_all = st.checkbox("Giữ nguyên dữ liệu cũ (ghi cả dòng thiếu trường bắt buộc)",
                               value=True)
        try:
            up.seek(0)
            df, skipped = importer.read_frame(up, ld, sheet, vemis and ld is NHAP_HOC)
        except Exception as e:
            ui.error_state(e, compact=True)
            st.stop()
        st.caption(f"**{len(df)}** dòng · {len(df.columns)} cột nhận được"
                   + (f" · bỏ qua cột: {', '.join(skipped)}" if skipped else ""))
        st.dataframe(df.head(20), hide_index=True, width="stretch", height=260)
        if st.button(f"Nhập {len(df)} dòng lên {config.list_name(ld.name)}", type="primary",
                     icon=":material/cloud_upload:", disabled=df.empty):
            bar = st.progress(0.0, text="Đang chuẩn bị…")

            def prog(done, total):
                bar.progress(done / max(total, 1), text=f"Đã ghi {done}/{total} dòng")

            try:
                res = importer.import_rows(storage, ld, df, nam, keep_all=keep_all,
                                           skip_existing=True, progress=prog)
            except Exception as e:
                ui.error_state(e, compact=True)
            else:
                ui.invalidate()
                bar.progress(1.0, text="Hoàn tất")
                st.success(f"Đã ghi **{res['ok']}** dòng · bỏ qua **{res['skipped']}** dòng đã có"
                           f" · lỗi **{len(res['errors'])}**"
                           + (f" · liên kết **{res['linked']}** hồ sơ với Data tuyển sinh"
                              if ld is NHAP_HOC else ""), icon=":material/check_circle:")
                if res["errors"]:
                    err = pd.DataFrame(res["errors"])
                    st.dataframe(err, hide_index=True, width="stretch")
                    ui.download_excel("Tải danh sách lỗi", err, "LoiNhapDuLieu.xlsx", key="dl_err")
                    st.caption("Sửa lỗi rồi bấm nhập lại — các dòng đã ghi sẽ được bỏ qua.")

# ------------------------------------------------------------------ 4. liên kết
with ui.section("4. Liên kết hồ sơ nhập học với Data tuyển sinh",
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

# ------------------------------------------------------------------ hướng dẫn
with st.expander("Hướng dẫn tạo flow Power Automate và khai báo Secrets", icon=":material/help:"):
    st.markdown(open("docs/power_automate.md", encoding="utf-8").read())
