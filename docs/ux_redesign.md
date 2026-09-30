# Thiết kế lại UX/UI — ghi chú thiết kế

## Đánh giá bản trước

| Hạng mục | Vấn đề | Cách xử lý |
|---|---|---|
| Information architecture | 5 mục ngang hàng, không nhóm; năm học đặt lạc lõng cạnh banner | Sidebar nhóm theo nghiệp vụ: *Tổng quan · Tuyển sinh · Tài chính · Phân tích*; **Năm học** là bối cảnh chung, đặt cố định ở sidebar |
| Navigation | Menu trên cùng + banner xanh lớn + footer xanh chiếm chỗ | Bỏ banner/footer. Logo + menu ở sidebar, tự thu gọn trên mobile. Trang chi tiết có đường dẫn quay lại và URL riêng (`?id=`), nên dùng được nút Back và chia sẻ link |
| Layout | Chia đôi 50/50: bảng bị cắt cột, form bị nhốt trong khung cuộn 470px | Mẫu **danh sách → trang chi tiết** cho bản ghi dài; **chỉnh nhanh cạnh danh sách** cho form ngắn (Kế toán); **hộp thoại** cho nhập nhanh |
| User flow | 4 nút trạng thái ngang hàng, không biết bước tiếp theo; không có thêm nhanh | **Stepper** Tư vấn → Nộp hồ sơ → Nhập học + **một nút chính cho bước tiếp theo**. Rút hồ sơ / Xóa / Đổi bước nằm trong menu *Thao tác*, luôn có hộp thoại xác nhận |
| Visual hierarchy | Không có tiêu đề trang; nút Xóa ngang hàng nút Lưu | Mỗi trang: tiêu đề + mô tả + vùng hành động bên phải; chỉ **1 nút chính** mỗi màn hình |
| Typography | Font mặc định, không phân cấp | Inter (hỗ trợ tiếng Việt), cỡ 15px; thang heading cố định; nhãn KPI nhỏ, số liệu đậm |
| Color system | Xanh đậm dùng tràn lan | Nền trung tính, 1 màu chính `#1D4ED8`; màu chỉ dùng cho **trạng thái** và luôn nhất quán giữa pill trong bảng, badge, stepper và biểu đồ |
| Component system | Mỗi trang tự dựng | `tuyensinh/ui.py`: `page_header`, `section`, `kpi_row/kpi`, `status_badge`, `stepper`, `empty_state`, `error_state`, `record_form`, `download_excel`, `mutate` |
| Form UX | Form dài một khối; trạng thái sửa trực tiếp trong form | Nhóm trường theo logic (Liên hệ / Học sinh / Trường cũ, điểm 2 hàng × 5 môn); bước tuyển sinh chỉ đổi qua hành động; ghi rõ "* là bắt buộc"; hồ sơ nhập học hiện **mức hoàn thiện** và **còn thiếu gì**, tab có số lượng trường thiếu |
| Table UX | Chữ trơn, không biết số lượng | Pill màu cho *Bước* và *Giữ chỗ*; cột tên được ghim; chiều cao theo số dòng; "Hiển thị x / y"; chọn dòng để mở |
| Search/filter UX | 3 dropdown + ô tìm tách rời | Thanh phân đoạn theo Bước **kèm số lượng**, ô tìm có biểu tượng, tìm cả SĐT dạng +84/có dấu cách, nút *Xóa bộ lọc* khi đang lọc |
| Modal UX | Không có | Thêm liên hệ (kiểm tra trùng trước khi lưu, "Lưu và thêm tiếp"), Rút hồ sơ (bắt buộc lý do), Xóa (nói rõ không hoàn tác, gợi ý dùng Rút hồ sơ) |
| Empty state | `st.info` chung chung | Biểu tượng + tiêu đề + hướng dẫn việc tiếp theo, phân biệt "chưa có dữ liệu" và "không khớp bộ lọc" |
| Loading state | — | Spinner "Đang tải dữ liệu…" / "Đang lưu…"; xuất Excel chỉ tạo file khi bấm |
| Error state | Lỗi thô | Thông báo dễ hiểu (mất kết nối / không có quyền / không tìm thấy / lỗi khác) + chi tiết kỹ thuật thu gọn + nút *Thử lại* |
| Mobile UX | Sidebar che nội dung, bảng + form xếp chồng dài | Sidebar tự thu gọn; KPI 2 thẻ/hàng; stepper xếp dọc; trang chi tiết một cột |
| Accessibility | Màu là tín hiệu duy nhất | Trạng thái luôn có chữ + biểu tượng; nhãn hiển thị cho mọi ô nhập; tương phản AA (kể cả chế độ tối); `aria-current` cho stepper; tôn trọng *reduced motion* |
| Performance | File VEMIS (3.321 xã) dựng lại mỗi lần tương tác; mỗi phiên có bộ đệm riêng nên dễ thấy dữ liệu cũ | Tải file lazy; bộ đếm phiên bản dữ liệu dùng chung cho mọi người dùng, ghi xong là mọi phiên đọc lại |

## Token

| Vai trò | Sáng | Tối |
|---|---|---|
| Màu chính | `#1D4ED8` | `#2563EB` |
| Nền / nền phụ | `#FFFFFF` / `#F3F5F8` | `#0F141B` / `#1A212B` |
| Viền | `#E3E7ED` | `#2A3340` |
| Chữ | `#111827` | `#E6EAF0` |

Trạng thái (dùng chung bảng, badge, biểu đồ): **Tư vấn** xanh dương `#2563EB` · **Nộp hồ sơ** cam `#D97706` ·
**Nhập học** xanh lá `#059669` · **Rút hồ sơ** xám `#6B7280` (không còn hoạt động).
Giữ chỗ: Chưa giữ chỗ xám · Đã giữ chỗ xanh lá · Hủy giữ chỗ đỏ · Đã hoàn phí tím.

Bo góc 8px, khoảng cách theo bội số 4px, tối đa 1 nút *primary* mỗi màn hình.
