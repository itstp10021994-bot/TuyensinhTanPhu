# Báo cáo kiểm tra dự án (PHASE 1 — Audit)

Ứng dụng: **Quản lý tuyển sinh — Trường TH, THCS & THPT Tân Phú (IGC)**
Ngày kiểm tra: 01/11/2026 · Nhánh: `claude/affectionate-hamilton-yqdr6u`
Phạm vi: đọc mã nguồn, cấu hình, kiểm thử tự động. **Không sửa mã trong bước này.**

---

## 1. Tổng quan kỹ thuật

| Hạng mục | Hiện trạng |
|---|---|
| Ngôn ngữ / framework | Python 3.11, **Streamlit 1.66** (requirements: `>=1.64`), pandas 3.1, Altair 6.3 |
| Điểm vào | `app.py` — đăng nhập, khai báo trang (`st.navigation`), thanh công cụ (năm học, tài khoản, giao diện sáng/tối, tải lại, trợ lý AI) |
| Trang (`views/`) | Tổng quan · Data tuyển sinh · Hồ sơ nhập học · Kế toán · Nội trú · Báo cáo · Trợ lý AI "Conan Ro" · Cài đặt & đồng bộ |
| Nghiệp vụ (`tuyensinh/`) | `services.py` (tuyển sinh, nhập học, giấy tờ, lên lớp), `reports.py` (36 mẫu báo cáo), `noi_tru.py` (phòng, đánh giá), `importer.py` (Excel/VEMIS, đối chiếu), `tai_khoan.py` (tài khoản, mật khẩu), `dia_ban.py`, `danh_muc.py`, `export_vemis.py`, `bien_nhan.py`, `tro_ly.py` + `ai_gemini.py` |
| Giao diện dùng chung | `tuyensinh/ui.py` (~1.150 dòng: CSS, thẻ, danh sách thẻ, hộp thoại, KPI, bộ nhớ đệm), `tuyensinh/bieu_do.py` (biểu đồ Altair chung) |
| Kho dữ liệu | `tuyensinh/storage/`: **Power Automate** (đang dùng — flow chuyển yêu cầu REST tới SharePoint), **Microsoft Graph** (tùy chọn), **SQLite cục bộ** (thử nghiệm) |
| Danh sách SharePoint | 6 list: `Data_TuyenSinh`, `Data_NhapHoc`, `DanhMuc_GiayTo`, `DanhMuc_TaiKhoan`, `NoiTru_Phong`, `NoiTru_DanhGia` (định nghĩa ở `schema.py`) |
| Tích hợp | SharePoint (qua Power Automate), Microsoft 365 đăng nhập (tùy chọn `[auth]`), Gemini (trợ lý AI — chỉ gửi câu hỏi), GitHub Action tự cập nhật `truong_hoc.csv` |
| Cấu hình | `.streamlit/config.toml` (theme Apple: `#007AFF`, nền `#F5F5F7`, font Inter, có theme tối), `secrets.toml.example` (không commit secrets — đã kiểm tra) |
| Kiểm thử | 13 file `tests/`, **105 bài — tất cả đạt** |
| Triển khai | Streamlit Community Cloud (đang dùng); bản Hugging Face Spaces ở `deploy/huggingface/` |

## 2. Kiến trúc hiện tại so với cấu trúc đề xuất

Dự án **đã tách lớp khá rõ**, tương đương cấu trúc đề xuất nhưng khác tên thư mục:

| Đề xuất | Hiện có |
|---|---|
| `pages/` | `views/` (dùng `st.navigation`, không dùng thư mục `pages/` tự động) |
| `services/` | `tuyensinh/services.py`, `reports.py`, `noi_tru.py`, `importer.py` |
| `core/database.py` | `tuyensinh/storage/` (3 backend chung một interface `Storage`) |
| `core/authentication.py`, `permissions.py` | `tuyensinh/tai_khoan.py` + phần đăng nhập trong `app.py` |
| `components/` | `tuyensinh/ui.py`, `bieu_do.py`, `ui_noi_tru.py` |
| `styles/*.css` | CSS viết trong chuỗi Python ở `ui.py` (`CSS`, `CSS_TOI`) |
| `utils/formatters.py` | rải rác: `ui.money`, `reports._pct`, `importer.ngay_chuan`… |

**Đánh giá:** kiến trúc ổn định, có kiểm thử. **Không nên đổi tên / dời thư mục hàng loạt** (rủi ro, không đem lại giá trị cho người dùng). Đề xuất tái cấu trúc *dần*: tách CSS ra `static/styles/*.css`, tách `ui.py` thành vài module thành phần.

## 3. Xác thực & phân quyền

- **Hai cách đăng nhập:** tài khoản trong list `DanhMuc_TaiKhoan` (mật khẩu băm **PBKDF2-SHA256, 200.000 vòng**, có muối) hoặc Microsoft 365 (`st.login`, giới hạn tên miền `AUTH_DOMAIN`). Có mật khẩu khẩn cấp `ADMIN_PASSWORD` (so sánh `hmac.compare_digest`).
- **Ghi nhớ đăng nhập 30 ngày:** mã ký HMAC gồm cả mật khẩu đã băm — đổi mật khẩu là mã cũ mất hiệu lực.
- **Phân quyền theo trang:** 7 vai trò (Quản trị, Tuyển sinh, Kế toán, Giáo vụ, Chỉ xem báo cáo, GV quản nhiệm, Tổ trưởng quản nhiệm). Trang không được phép **không được đăng ký** với `st.navigation` → không mở được kể cả gõ URL (kiểm soát phía máy chủ, không chỉ ẩn nút).
- **Phân quyền trong trang:** Cài đặt kiểm tra lại vai trò Quản trị; Nội trú kiểm tra `duoc_nhap` (GV chỉ nhập phòng mình).

## 4. Phát hiện — xếp theo mức độ

### 🔴 Nghiêm trọng (bảo mật)

1. **Đăng nhập "mở cửa" khi không đọc được list tài khoản.** `app.py` chỉ bắt đăng nhập khi đọc được ít nhất 1 tài khoản đang hoạt động. Nếu SharePoint / Power Automate lỗi tạm thời, `ui.records(TAI_KHOAN, optional=True)` trả về rỗng → **ai mở link cũng vào được mọi trang** (kể cả Cài đặt) mà không cần mật khẩu.
   → *Đề xuất:* chỉ cho "chế độ không tài khoản" khi list **đọc thành công và thật sự rỗng**; lỗi đọc thì hiện màn hình đăng nhập + báo lỗi kết nối (fail-closed).
2. **"Chi tiết kỹ thuật" của lỗi hiện cho mọi người dùng.** `ui.error_state` in nguyên thông báo lỗi / traceback. Với lỗi mạng của thư viện `requests`, thông báo có thể chứa **nguyên URL flow Power Automate kèm chữ ký `sig=`** (khóa truy cập flow).
   → *Đề xuất:* chỉ Quản trị thấy chi tiết; luôn che `sig=…`, `key`, token trong thông báo.

### 🟠 Quan trọng

3. **Không giới hạn số lần đăng nhập sai** (dò mật khẩu). → Khóa tạm 5 phút sau 5 lần sai / tên đăng nhập.
4. **Xóa bản ghi chỉ dựa vào quyền vào trang.** Ai vào được Data tuyển sinh / Hồ sơ nhập học đều xóa được (có hộp thoại xác nhận). → Đề xuất giới hạn nút Xóa cho Quản trị / Giáo vụ (cần anh/chị duyệt vì đổi quy trình).
5. **Chưa có nhật ký hoạt động** (ai sửa / xóa gì, lúc nào). Mới có cột "Người cập nhật". Nhật ký đầy đủ cần **thêm 1 list SharePoint** → cần duyệt (thay đổi lược đồ).

### 🟡 Giao diện / trải nghiệm

6. **Thiết kế đã theo hướng Apple** (màu, font Inter, tab kiểu segmented, thẻ trắng, sáng/tối) nhưng **token chưa tập trung**: màu viết cứng ở nhiều nơi (`ui.py`, `bieu_do.py`, `noi_tru.py`, `config.toml`). Bảng màu biểu đồ (`bieu_do.py`, bộ màu đã kiểm định mù màu) khác bảng màu trạng thái của prompt (`#34C759`, `#FF9F0A`, `#FF3B30`).
7. **CSS ~500 dòng nằm trong chuỗi Python**, một số selector phụ thuộc cấu trúc DOM nội bộ của Streamlit (`data-testid`, `st-emotion-cache`) → dễ vỡ khi nâng cấp Streamlit.
8. **Tiêu đề trang chưa thống nhất:** Báo cáo đã bỏ tiêu đề lớn, các trang khác còn; chưa có breadcrumb / mô tả ngắn chuẩn.
9. **Thanh bên:** đã nhóm theo bộ phận, có biểu tượng; **chưa có** khối thông tin người dùng + phiên bản ở chân thanh bên (đang nằm ở thanh trên).
10. **Bảng dữ liệu:** Data tuyển sinh / Hồ sơ nhập học dùng **lưới thẻ** (có tìm kiếm, lọc, phân trang 21 thẻ/trang, hộp thoại chi tiết). Chưa có chế độ **bảng** (sắp xếp theo cột, chọn nhiều dòng để thao tác hàng loạt) cho người xử lý số lượng lớn.
11. **Biểu đồ dùng Altair**, prompt đề xuất Plotly. Altair đã có sẵn, nhẹ, hỗ trợ tooltip/hover và theme sáng/tối. **Đề xuất giữ Altair** (quy tắc "không thêm phụ thuộc không cần thiết").
12. **Responsive:** đã kiểm tra ở 1920 / 1440 / 390. **Chưa kiểm tra** 1366 / 1024 / 768.

### ⚪ Nhỏ

13. 2 cảnh báo lint: `views/tro_ly.py:278` f-string thừa; `reports.py:17` import `KHOI` không dùng.
14. Báo cáo "Kết quả học tập đầu vào" (`nh_hocluc`) lỗi `mean` khi cột điểm là chuỗi trong dữ liệu thô — trong app đã ép kiểu nên chạy được; nên ép kiểu ngay trong hàm báo cáo.
15. Địa bàn quận/huyện cũ: hồ sơ cập nhật từ VEMIS chỉ có phường/xã mới → báo cáo theo quận cũ thiếu (đã xử lý hiển thị; cần bảng tra phường mới → quận cũ chính thức nếu muốn so theo quận).

## 5. Hiệu năng

- Đọc **cả list** qua Power Automate (trang 500 dòng, 4 luồng song song), lưu đệm **dùng chung mọi người** (`cache_resource`), tự tải lại khi SharePoint báo có thay đổi (kiểm tra 30 giây/lần) hoặc sau 10 phút.
- Lọc / tìm kiếm / phân trang bằng pandas trên máy chủ — đủ nhanh với vài chục nghìn dòng.
- Dữ liệu đệm **không theo người dùng** (mọi vai trò cùng đọc list), quyền được kiểm soát ở mức trang → chấp nhận được; Trợ lý AI tự giới hạn theo quyền.
- Không có truy vấn SQL tự ghép chuỗi (SQLite dùng tham số; SharePoint qua REST).

## 6. Kế hoạch triển khai đề xuất

| Bước | Nội dung | Ảnh hưởng dữ liệu / nghiệp vụ |
|---|---|---|
| **A. Bảo mật (ưu tiên)** | (1) fail-closed khi lỗi đọc tài khoản; (2) che chi tiết lỗi + mã `sig`; (3) khóa tạm khi đăng nhập sai nhiều lần | Không đổi dữ liệu |
| **B. Design system** | Gom token màu / chữ / khoảng cách / bo góc vào một chỗ (`static/styles/tokens.css` + `ui.TOKENS`); tách CSS khỏi Python; bảng màu trạng thái theo prompt | Không |
| **C. Khung ứng dụng** | Tiêu đề trang thống nhất (tiêu đề + mô tả + nút chính), thanh bên có khối người dùng + phiên bản, chiều rộng nội dung thống nhất | Không |
| **D. Bảng dữ liệu** | Thêm chế độ **Bảng** cho Data tuyển sinh / Hồ sơ nhập học (sắp xếp, chọn nhiều, badge trạng thái, thanh lọc gọn + lọc nâng cao thu gọn), giữ chế độ Thẻ | Không |
| **E. Biểu mẫu** | Rà các form: nhóm trường, đánh dấu bắt buộc, kiểm tra tại chỗ — **giữ nguyên quy tắc kiểm tra & ánh xạ cột** | Không |
| **F. Responsive & QA** | Kiểm tra 1920/1440/1366/1024/768/390, sửa vỡ bố cục; dọn lint | Không |
| **G. Triển khai** | Hướng dẫn secrets, biến môi trường, sao lưu / khôi phục | Không |
| *Cần duyệt* | Giới hạn quyền Xóa theo vai trò (#4); Nhật ký hoạt động — thêm list SharePoint (#5) | Đổi quy trình / thêm list |
