# Ứng dụng Quản lý Tuyển sinh — Trường TH, THCS & THPT Tân Phú

Phiên bản Python (Streamlit) thay cho app Power Apps. Dữ liệu vẫn lưu trên **SharePoint List**
(site `eduttc.sharepoint.com/sites/tuyensinh2`), ghi/đọc qua **1 flow Power Automate Premium** —
xem [docs/power_automate.md](docs/power_automate.md).

![Data tuyển sinh](docs/data_tuyen_sinh.png)

## Chức năng

| Mục | Nội dung |
|---|---|
| **Trang chủ** | Tổng quan theo năm học: số liên hệ, số HS theo trạng thái, liên hệ mới nhất |
| **Data tuyển sinh** | Form nhập đúng các cột của list *Data tuyển sinh* hiện có (Nam hoc, Ngày liên hệ, SĐT, Nguồn, Tài khoản FB, Người giới thiệu, Họ tên HS, Khối, Giới tính, Chế độ, Trường cũ, điểm Toán/Văn/Anh/TV 1–2, Hạnh kiểm 1–2, …). Danh sách lọc Lớp / Chế độ / Bước, tìm theo tên, SĐT, người đăng ký. Nút **Bước**: Tư vấn → Nộp hồ sơ → Nhập học / Rút hồ sơ (lý do rút ghi vào "Nội dung đã trao đổi"). Cảnh báo trùng tên + SĐT |
| **Hồ sơ nhập học** | Khi bấm **Nhập học**, hồ sơ được tạo tự động từ Data tuyển sinh (năm học, họ tên, ngày sinh, giới tính, lớp, chế độ, SĐT). Bổ sung đủ 54 cột theo biểu mẫu **Danh sách học sinh (VEMIS)**, chọn Tỉnh → Xã/Phường theo danh mục mới (34 tỉnh, 3.321 xã). Cột "Thiếu" cho biết HS còn thiếu thông tin quan trọng. **Xuất Excel đúng biểu mẫu VEMIS** theo lớp |
| **Kế toán** | Xác nhận giữ chỗ trên các cột có sẵn (*Tình trạng, Số tiền xác nhận, Người xác nhận*), theo dõi **hoàn phí** khi hủy giữ chỗ (*Tên chủ tài khoản, Ngân hàng, Số tài khoản*), **tổng hợp giữ chỗ** theo khối, xuất Excel |
| **Báo cáo** | Thống kê khối × trạng thái, tỷ lệ nhập học, nguồn tuyển sinh, liên hệ theo tuần, chế độ nội trú/bán trú; tải báo cáo Excel |

Chọn **năm học** ở góc trên bên phải — mọi trang đều lọc theo năm học.

## Cấu trúc dữ liệu (SharePoint List)

| List | Nội dung | Định nghĩa |
|---|---|---|
| **Data tuyển sinh** (có sẵn, GUID `d0608833-…`) | HS liên hệ / tư vấn / nộp hồ sơ / giữ chỗ. App khớp cột theo **tên hiển thị** | `TUYEN_SINH` trong [`tuyensinh/schema.py`](tuyensinh/schema.py) |
| **Data_NhapHoc** (app tạo) | HS đã xác nhận nhập học — đủ 54 cột biểu mẫu VEMIS + *Nam hoc*, liên kết qua `TuyenSinhID` | `NHAP_HOC` |

Cả hai list đều có cột **Nam hoc**; mọi trang lọc theo năm học chọn ở góc trên.
Danh mục (tỉnh, xã, dân tộc, tôn giáo, quốc tịch, diện chính sách, khuyết tật, nội trú/bán trú)
lấy từ file mẫu VEMIS, lưu ở `tuyensinh/data/danh_muc.json`.

## Chạy thử trên máy (không cần SharePoint)

```bash
python -m venv .venv
.venv\Scripts\activate          # Windows   (macOS/Linux: source .venv/bin/activate)
pip install -r requirements.txt
python scripts/seed_demo.py     # tạo 60 HS mẫu (tuỳ chọn)
streamlit run app.py            # mở http://localhost:8501
```

Mặc định `BACKEND=local` lưu vào file `data_local.sqlite3`.

## Kết nối SharePoint

**Cách khuyên dùng — Power Automate Premium** (không cần quyền quản trị Entra ID):
làm theo [docs/power_automate.md](docs/power_automate.md), rồi

```bash
python scripts/inspect_sharepoint.py          # kiểm tra kết nối, xem cột nào đã khớp
python scripts/setup_sharepoint.py            # tạo list Data_NhapHoc + cột còn thiếu
```

**Cách khác — Microsoft Graph**: đăng ký App trên Entra ID (quyền Application
`Sites.ReadWrite.All` hoặc `Sites.Selected`), đặt `BACKEND = "sharepoint"` và điền mục
`[sharepoint]` trong `secrets.toml`.

### Chuyển dữ liệu cũ

List *Data tuyển sinh* đang dùng được giữ nguyên nên không cần chuyển. Nếu có dữ liệu ở file
Excel (vd *Export to Excel* từ list), nhập bằng:

```bash
python scripts/import_excel.py tuyensinh data_tuyen_sinh.xlsx --nam-hoc 2026-2027 --dry-run
python scripts/import_excel.py nhaphoc hoc_sinh_toan_truong.xlsx --vemis --nam-hoc 2026-2027
```

Cột được nhận theo tên hiển thị trên SharePoint; cột "Nam hoc" trong file được giữ, `--nam-hoc`
chỉ dùng cho dòng để trống. File `.xls` VEMIS cần lưu lại thành `.xlsx` trước.

### Đăng nhập bằng tài khoản Microsoft 365 (tuỳ chọn)

Thêm mục `[auth]` vào `secrets.toml` (mẫu có trong `secrets.toml.example`) — app sẽ yêu cầu đăng nhập
và tự ghi tên người thao tác (người nhận hồ sơ, người xác nhận). Redirect URI của App registration
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
tuyensinh/services.py      # nghiệp vụ: lưu, chuyển bước, tạo hồ sơ nhập học, giữ chỗ
tuyensinh/export_vemis.py  # xuất Excel theo biểu mẫu VEMIS
tuyensinh/storage/         # powerautomate.py, sharepoint.py (Graph), local.py (SQLite), convert.py (khớp cột)
scripts/                   # setup_sharepoint, inspect_sharepoint, import_excel, seed_demo
tests/                     # pytest
```

Chạy kiểm thử: `pip install pytest && pytest`.
