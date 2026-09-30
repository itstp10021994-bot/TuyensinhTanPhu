# Kết nối app với SharePoint qua Power Automate (Premium)

App không ghi thẳng vào SharePoint mà gửi yêu cầu tới **một flow** có trigger HTTP.
Flow chuyển yêu cầu tới REST API của site `https://eduttc.sharepoint.com/sites/tuyensinh2`
bằng tài khoản của người tạo flow, rồi trả kết quả về app. Chỉ cần **1 flow** cho mọi thao tác
(đọc danh sách, thêm, sửa, xóa) trên cả 2 list *Data tuyển sinh* và *Data_NhapHoc*.

```
App Python ──POST {key, method, uri, body}──► Flow (HTTP trigger)
                                              ├─ Kiểm tra key
                                              ├─ Send an HTTP request to SharePoint
                                              └─ Response (trả kết quả cho app)
```

## Tạo flow

1. <https://make.powerautomate.com> → **Tạo** → **Luồng đám mây tức thời (Instant cloud flow)**
   → đặt tên `TuyenSinh-API` → chọn trigger **When a HTTP request is received** (Premium) → Tạo.
2. Trigger **When a HTTP request is received**
   - *Who can trigger the flow?*: **Anyone** (URL có chữ ký bí mật + key ở bước 3).
   - *Request Body JSON Schema*:
     ```json
     {
       "type": "object",
       "properties": {
         "key":    { "type": "string" },
         "method": { "type": "string" },
         "uri":    { "type": "string" },
         "body":   { "type": "object" }
       }
     }
     ```
3. **Condition** (Điều kiện) — chuyển sang chế độ biểu thức và nhập:
   ```
   and(equals(triggerBody()?['key'], 'DAT-MAT-KHAU-RIENG-O-DAY'), startsWith(triggerBody()?['uri'], '_api/web/lists'))
   ```
   so sánh `is equal to` `true`.
   - Nhánh **False**: thêm **Response**, Status code `403`, Body `Sai key`.
4. Nhánh **True**: thêm **Send an HTTP request to SharePoint**
   | Ô | Giá trị |
   |---|---|
   | Site Address | `https://eduttc.sharepoint.com/sites/tuyensinh2` |
   | Method | *Enter custom value* → biểu thức `triggerBody()?['method']` |
   | Uri | biểu thức `triggerBody()?['uri']` |
   | Headers | `Accept` = `application/json;odata=nometadata`<br>`Content-Type` = `application/json;odata=nometadata`<br>`IF-MATCH` = `*` |
   | Body | biểu thức `triggerBody()?['body']` |
5. Ngay sau đó (vẫn trong nhánh True) thêm **Response**
   - Status code: biểu thức `outputs('Send_an_HTTP_request_to_SharePoint')?['statusCode']`
   - Body: biểu thức `body('Send_an_HTTP_request_to_SharePoint')`
   - Bấm **…** → **Configure run after** → tích cả **is successful** và **has failed**
     (để app nhận được thông báo lỗi của SharePoint).
6. **Lưu**. Mở lại trigger, sao chép **HTTP POST URL**.

> Tài khoản tạo flow cần quyền **Chỉnh sửa** trên site tuyensinh2 (để tạo list Data_NhapHoc
> và thêm cột thì cần quyền **Quản lý / Owner**).

## Khai báo trong app

`.streamlit/secrets.toml`:

```toml
BACKEND = "powerautomate"
SP_LIST_Data_TuyenSinh = "d0608833-bddf-4d28-a7db-402eb246c017"   # GUID list Data tuyển sinh (từ file .iqy)
SP_LIST_Data_NhapHoc = "Data_NhapHoc"

[powerautomate]
flow_url = "https://prod-xx.southeastasia.logic.azure.com:443/workflows/.../invoke?api-version=...&sig=..."
key = "DAT-MAT-KHAU-RIENG-O-DAY"      # giống key trong Condition của flow
```

Kiểm tra kết nối và cách app khớp cột:

```bash
python scripts/inspect_sharepoint.py          # in cột của list, cột nào app đã khớp
python scripts/setup_sharepoint.py --dry-run  # xem cần tạo gì
python scripts/setup_sharepoint.py            # tạo list Data_NhapHoc + cột còn thiếu
```

App tìm cột theo **tên hiển thị** (ví dụ "Họ tên HS", "Nam hoc", "Bước") nên không cần biết tên
nội bộ. Nếu đổi tên hiển thị cột trên SharePoint, khai báo lại trong `secrets.toml`:

```toml
[field_map.Data_TuyenSinh]
HoTenHS = "Ten_x0020_HS"    # key trong app = tên nội bộ cột
```

## Ghi chú

- Mỗi thao tác của app = 1 lần chạy flow (tính vào hạn mức Power Automate Premium của tài khoản).
  App lưu tạm dữ liệu 2 phút và chỉ tải lại sau khi có thay đổi.
- Giữ bí mật **flow_url** và **key**: ai có cả hai đều đọc/ghi được các list của site.
- Cột kiểu **Người (Person)**, ví dụ nếu "Người nhận hồ sơ" là cột Person, app chỉ đọc tên,
  không ghi. Muốn app ghi được thì đổi cột đó sang kiểu *Single line of text*.
- Ngày được ghi lúc 12:00 UTC và đọc theo giờ Việt Nam nên không bị lệch 1 ngày.
