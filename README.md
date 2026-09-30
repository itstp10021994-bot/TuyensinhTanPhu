# Ứng dụng Quản lý Tuyển sinh — Trường TH, THCS & THPT Tân Phú

Phiên bản Python (Streamlit) thay cho app Power Apps. Dữ liệu vẫn lưu trên **SharePoint List**.

![Data tuyển sinh](docs/data_tuyen_sinh.png)

## Chức năng

| Mục | Nội dung |
|---|---|
| **Trang chủ** | Tổng quan theo năm học: số liên hệ, số HS theo trạng thái, liên hệ mới nhất |
| **Data tuyển sinh** | Danh sách HS chưa nhập học (lọc Lớp / Chế độ / Trạng thái, tìm theo tên, SĐT, người đăng ký) + form chi tiết. Nút trạng thái **Tư vấn → Nộp hồ sơ → Nhập học / Rút hồ sơ** (tự ghi ngày, hỏi lý do rút). Cảnh báo trùng tên + SĐT |
| **Hồ sơ nhập học** | Khi HS chuyển sang *Nhập học*, hồ sơ được tạo tự động (điền sẵn họ tên, ngày sinh, lớp, chế độ, SĐT). Bổ sung đủ 54 cột theo biểu mẫu **Danh sách học sinh (VEMIS)**, chọn Tỉnh → Xã/Phường theo danh mục mới (34 tỉnh, 3.321 xã). Cột "Thiếu" cho biết HS còn thiếu thông tin quan trọng. **Xuất Excel đúng biểu mẫu VEMIS** theo lớp |
| **Kế toán** | Ghi nhận thu phí (giữ chỗ, nhập học, học phí, …) → kế toán **xác nhận / hoàn tiền / hủy** → **tổng hợp giữ chỗ** theo HS, lọc HS chưa đóng phí giữ chỗ, xuất Excel |
| **Báo cáo** | Thống kê khối × trạng thái, tỷ lệ nhập học, nguồn tuyển sinh, liên hệ theo tuần, chế độ nội trú/bán trú; tải báo cáo Excel |

Chọn **năm học** ở góc trên bên phải — mọi trang đều lọc theo năm học.

## Cấu trúc dữ liệu (3 SharePoint List)

| List | Nội dung | Định nghĩa |
|---|---|---|
| `Data_TuyenSinh` | HS liên hệ / tư vấn / nộp hồ sơ (chưa nhập học) | `TUYEN_SINH` trong [`tuyensinh/schema.py`](tuyensinh/schema.py) |
| `Data_NhapHoc` | HS đã xác nhận nhập học — đủ thông tin theo biểu mẫu VEMIS, liên kết qua cột `TuyenSinhID` | `NHAP_HOC` |
| `Data_ThuPhi` | Các khoản thu và trạng thái xác nhận của kế toán | `THU_PHI` |

Danh mục (tỉnh, xã, dân tộc, tôn giáo, quốc tịch, diện chính sách, khuyết tật, nội trú/bán trú)
được lấy từ file mẫu VEMIS, lưu ở `tuyensinh/data/danh_muc.json`.

## Chạy thử trên máy (không cần SharePoint)

```bash
python -m venv .venv
.venv\Scripts\activate          # Windows   (macOS/Linux: source .venv/bin/activate)
pip install -r requirements.txt
python scripts/seed_demo.py     # tạo 60 HS mẫu (tuỳ chọn)
streamlit run app.py            # mở http://localhost:8501
```

Mặc định `BACKEND=local` lưu vào file `data_local.sqlite3`.

## Cấu hình SharePoint

1. **Đăng ký ứng dụng** tại <https://entra.microsoft.com> → *App registrations* → *New registration*.
   - *API permissions* → Microsoft Graph → **Application permissions** → `Sites.ReadWrite.All`
     (hoặc `Sites.Selected` rồi cấp quyền riêng cho site Tuyển sinh) → **Grant admin consent**.
   - *Certificates & secrets* → tạo **Client secret**.
   - Ghi lại *Tenant ID*, *Client ID*, *Client secret*.
2. Sao chép `.streamlit/secrets.toml.example` thành `.streamlit/secrets.toml`, điền:
   ```toml
   BACKEND = "sharepoint"
   [sharepoint]
   tenant_id = "..."
   client_id = "..."
   client_secret = "..."
   site_url = "https://<tentruong>.sharepoint.com/sites/<TenSite>"
   ```
3. Tạo các list và cột:
   ```bash
   python scripts/setup_sharepoint.py --dry-run   # xem trước
   python scripts/setup_sharepoint.py
   ```
   Nếu list đã tồn tại, script chỉ **thêm các cột còn thiếu**, không xoá dữ liệu.

### Dùng lại list cũ của Power Apps / chuyển dữ liệu

- Xem tên cột nội bộ của list cũ: `python scripts/inspect_sharepoint.py "Tên list cũ"`.
- Cách 1 — **giữ list cũ**: đặt `SP_LIST_Data_TuyenSinh = "Tên list cũ"` trong `secrets.toml`
  rồi chạy `setup_sharepoint.py` để bổ sung cột. Cột cũ có tên khác schema thì sửa `key` trong
  `tuyensinh/schema.py` cho khớp tên nội bộ.
- Cách 2 — **list mới + nhập dữ liệu**: xuất list cũ ra Excel rồi
  ```bash
  python scripts/import_excel.py tuyensinh du_lieu_cu.xlsx --nam-hoc 2026-2027 \
      --map "Tên HS=HoTenHS" --map "Lớp=Khoi"
  # nhập HS toàn trường từ file VEMIS (lưu file .xls thành .xlsx trước)
  python scripts/import_excel.py nhaphoc hoc_sinh_toan_truong.xlsx --vemis --nam-hoc 2026-2027
  ```
  Thêm `--dry-run` để kiểm tra lỗi trước khi ghi.

### Đăng nhập bằng tài khoản Microsoft 365 (tuỳ chọn)

Thêm mục `[auth]` vào `secrets.toml` (mẫu có trong `secrets.toml.example`) — app sẽ yêu cầu đăng nhập
và tự ghi tên người thao tác (người tư vấn, người xác nhận thu phí). Redirect URI của App registration
phải là `https://<địa-chỉ-app>/oauth2callback`.

## Triển khai

- **Máy chủ trong trường / Windows**: `streamlit run app.py --server.port 80`
  (có thể chạy như Windows Service bằng NSSM).
- **Streamlit Community Cloud**: đẩy repo lên GitHub → <https://share.streamlit.io> → dán nội dung
  `secrets.toml` vào mục *Secrets*.
- Docker / Azure App Service: lệnh khởi động `streamlit run app.py --server.port $PORT --server.address 0.0.0.0`.

## Cấu trúc mã nguồn

```
app.py                     # điểm vào, thanh menu trên cùng, chọn năm học, đăng nhập
views/                     # các trang: trang_chu, data_tuyen_sinh, ho_so_nhap_hoc, ke_toan, bao_cao
tuyensinh/schema.py        # định nghĩa list & cột (thêm/sửa trường tại đây)
tuyensinh/services.py      # nghiệp vụ: lưu, chuyển trạng thái, tạo hồ sơ nhập học, thu phí
tuyensinh/export_vemis.py  # xuất Excel theo biểu mẫu VEMIS
tuyensinh/storage/         # sharepoint.py (Microsoft Graph) và local.py (SQLite)
scripts/                   # setup_sharepoint, inspect_sharepoint, import_excel, seed_demo
tests/                     # pytest
```

Chạy kiểm thử: `pip install pytest && pytest`.
