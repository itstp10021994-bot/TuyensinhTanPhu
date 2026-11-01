# Triển khai, sao lưu & khôi phục

Áp dụng cho bản 2.0.0 (nhánh `claude/affectionate-hamilton-yqdr6u`). Chỉ cần làm theo thứ tự.

## 1. Yêu cầu

- Python 3.11+, các gói trong `requirements.txt` (Streamlit ≥ 1.64, pandas, openpyxl, Altair,
  msal, requests, xlrd, python-calamine, Authlib). **Không thêm phụ thuộc mới** ở bản 2.0.
- Chạy thử trên máy: `pip install -r requirements.txt` rồi `streamlit run app.py`
  (không có Secrets → dùng SQLite cục bộ `data_local.sqlite3`).

## 2. Secrets (Streamlit Cloud → Manage app → Settings → Secrets)

Mẫu đầy đủ: `.streamlit/secrets.toml.example`. **Không bao giờ commit `secrets.toml`.**

| Khóa | Bắt buộc | Ý nghĩa |
|---|---|---|
| `BACKEND` | có | `powerautomate` (đang dùng) · `sharepoint` (Graph) · `local` (thử) |
| `[powerautomate] flow_url`, `key` | có | URL flow "When a HTTP request is received" và khóa riêng flow kiểm tra |
| `ADMIN_PASSWORD` | nên có | Mật khẩu khẩn cấp vào quyền Quản trị (khi chưa có / quên tài khoản Quản trị) |
| `COOKIE_SECRET` | **nên đặt** | Chuỗi ngẫu nhiên dài để ký mã "ghi nhớ đăng nhập 30 ngày". Không đặt thì app dùng `ADMIN_PASSWORD` / key flow |
| `NAM_HOC`, `NAM_HOC_MAC_DINH` | không | Danh sách năm học, năm mặc định |
| `SP_LIST_<tên list>` | không | Đổi tên / GUID list SharePoint nếu khác mặc định |
| `[auth]` + `AUTH_DOMAIN` | không | Đăng nhập Microsoft 365, chỉ cho tên miền trường |
| `GEMINI_API_KEY`, `GEMINI_MODEL` | không | Trợ lý AI (chỉ gửi câu hỏi, không gửi dữ liệu học sinh) |

Tạo chuỗi ngẫu nhiên cho `COOKIE_SECRET`: `python -c "import secrets; print(secrets.token_urlsafe(48))"`.

## 3. Việc cần làm một lần sau khi cập nhật bản 2.0

1. Mở app → **Cài đặt & đồng bộ → Nhật ký hoạt động** → bấm **Tạo list nhật ký** (tạo list
   `NhatKy_HoatDong` trên SharePoint). Từ đó app tự ghi mọi thao tác lưu / xóa / nhập và đăng nhập.
2. Kiểm tra **Tài khoản & phân quyền**: có ít nhất một tài khoản **Quản trị**. Bản 2.0 chỉ cho
   *Quản trị* xóa liên hệ Data tuyển sinh, *Quản trị / Giáo vụ* xóa hồ sơ nhập học.
3. (Khuyến nghị) đặt `COOKIE_SECRET` trong Secrets (mục 2).

## 4. Hành vi bảo mật mới (bản 2.0)

- SharePoint / flow lỗi khi đọc danh sách tài khoản → app **vẫn bắt đăng nhập** (không mở cửa).
  Chỉ khi list tài khoản *chưa được tạo* mới chạy chế độ không tài khoản (cài đặt lần đầu).
- Sai mật khẩu 5 lần → khóa tạm tên đăng nhập đó 5 phút (cả mật khẩu quản trị).
- Thông báo lỗi che `sig=`, key, token; chi tiết kỹ thuật chỉ Quản trị xem.

## 5. Sao lưu

| Cách | Khi nào | Làm thế nào |
|---|---|---|
| **Sao lưu Excel toàn bộ** | Định kỳ (tuần) và **trước mọi thao tác hàng loạt** (đối chiếu VEMIS, xóa, nhập file) | Cài đặt & đồng bộ → Nhập / xuất dữ liệu → **Tải bản sao lưu (Excel)** — mỗi list một sheet (không gồm tài khoản) |
| Lịch sử phiên bản SharePoint | Sửa nhầm một dòng | Mở list trên SharePoint → dòng → *Version history* → khôi phục |
| Thùng rác SharePoint | Xóa nhầm | Site → *Recycle bin* (giữ 93 ngày) → *Restore* |
| Xuất VEMIS | Trước khi nộp / đồng bộ VEMIS | Hồ sơ nhập học → Công cụ → Xuất VEMIS |

## 6. Khôi phục mã (rollback)

App chạy theo nhánh Git đã chọn trên Streamlit Cloud. Mỗi bước nâng cấp là **một commit riêng**,
nên có thể quay lại từng phần:

1. Xem lịch sử: `git log --oneline` (vd `dfe10cc` Bảo mật, `246a702` Design system, `a6cc209` Khung
   ứng dụng, `6bdc010` Bảng dữ liệu, `0f44f59` Biểu mẫu, `d0227e5` QA giao diện).
2. Hoàn tác một bước mà giữ các bước khác: `git revert <mã commit>` rồi `git push`. Streamlit
   Cloud tự cập nhật sau 1–2 phút.
3. Quay hẳn về một thời điểm: tạo nhánh từ commit cũ (`git switch -c ban-cu <mã>`; `git push -u
   origin ban-cu`) và chọn nhánh đó trong *Manage app → Settings*.
4. Dữ liệu **không** bị ảnh hưởng khi rollback mã (dữ liệu nằm trên SharePoint). List
   `NhatKy_HoatDong` để lại cũng không sao.

## 7. Kiểm tra sau triển khai

- [ ] Đăng nhập được bằng tài khoản thường và tài khoản Quản trị.
- [ ] Sai mật khẩu 5 lần → báo tạm khóa.
- [ ] Tổng quan, Data tuyển sinh (Thẻ + Bảng), Hồ sơ nhập học, Kế toán, Nội trú, Báo cáo
      (dashboard + Trình chiếu), Cài đặt mở bình thường.
- [ ] Lưu thử một hồ sơ → Cài đặt → Nhật ký hoạt động có dòng mới.
- [ ] Tài khoản không phải Quản trị không thấy nút **Xóa liên hệ**.
- [ ] `pytest` chạy đủ (108 bài) trước khi đẩy mã mới.
