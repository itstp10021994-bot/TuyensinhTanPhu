# Đồng bộ app với SharePoint qua Power Automate (Premium)

## Cách hoạt động

Mỗi lần bạn **lưu, chuyển bước, xác nhận giữ chỗ…** trên app, app gửi ngay một yêu cầu tới
**một flow Power Automate**. Flow ghi vào SharePoint (site `tuyensinh2`) bằng tài khoản của người
tạo flow, rồi trả kết quả về app. Không có bước "đồng bộ" riêng: **lưu trên app = lưu trên
SharePoint** (app chỉ báo "Đã lưu" khi SharePoint ghi thành công).

```
Người dùng ─► App (Streamlit) ──POST {key, method, uri, body}──► Flow "TuyenSinh-API"
                                                                  ├─ Kiểm tra key
                                                                  ├─ Send an HTTP request to SharePoint
                                                                  └─ Response ─► App
```

- 1 flow dùng cho mọi thao tác (đọc, thêm, sửa, xóa) trên cả **Data_TuyenSinh** và **Data_NhapHoc**.
- Sửa trực tiếp trên SharePoint thì app thấy sau tối đa 10 phút (hoặc bấm nút ⟳ trên thanh menu).
- Mỗi thao tác = 1 lần chạy flow; nhập 1.700 dòng dữ liệu cũ ≈ 1.700 lần chạy (vài phút).

---

## Bước 1 — Tạo flow (khoảng 10 phút, làm 1 lần)

1. Vào <https://make.powerautomate.com> → **+ Tạo** → **Luồng đám mây tức thời**
   (*Instant cloud flow*) → đặt tên `TuyenSinh-API` → chọn trigger
   **When a HTTP request is received** → **Tạo**.
2. Bấm vào trigger:
   - **Who can trigger the flow?** → **Anyone**.
   - **Request Body JSON Schema** → dán:
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
3. **+ Bước mới** → **Condition** (Điều kiện). Ở ô bên trái chọn **Expression** (biểu thức), dán:
   ```
   and(equals(triggerBody()?['key'], 'MAT-KHAU-CUA-BAN'), startsWith(triggerBody()?['uri'], '_api/web/lists'))
   ```
   Toán tử **is equal to**, ô bên phải gõ `true`.
   > Thay `MAT-KHAU-CUA-BAN` bằng một chuỗi bí mật tự đặt (ví dụ 24 ký tự ngẫu nhiên).
4. Nhánh **If no / False** → thêm **Response**: *Status Code* `403`, *Body* `Sai key`.
5. Nhánh **If yes / True** → thêm **Send an HTTP request to SharePoint**:

   | Ô | Nhập |
   |---|---|
   | Site Address | chọn `https://eduttc.sharepoint.com/sites/tuyensinh2` |
   | Method | chọn *Enter custom value* → Expression `triggerBody()?['method']` |
   | Uri | Expression `triggerBody()?['uri']` |
   | Headers | `Accept` = `application/json;odata=nometadata`<br>`Content-Type` = `application/json;odata=nometadata`<br>`IF-MATCH` = `*` |
   | Body | Expression `triggerBody()?['body']` |

6. Ngay dưới (vẫn trong nhánh True) thêm **Response**:
   - *Status Code*: Expression `outputs('Send_an_HTTP_request_to_SharePoint')?['statusCode']`
   - *Body*: Expression `body('Send_an_HTTP_request_to_SharePoint')`
   - Bấm **…** của Response → **Configure run after** (Cài đặt chạy sau) → tích cả
     **is successful** và **has failed** → Done. (Để app nhận được thông báo lỗi của SharePoint.)
7. **Lưu**. Mở lại trigger → sao chép **HTTP POST URL** (URL dài có `sig=`).

> Tài khoản tạo flow cần quyền **Owner** trên site `tuyensinh2` (để app tạo list và cột ở Bước 3).
> Giữ bí mật URL và key: ai có cả hai đều đọc/ghi được các list của site.

## Bước 2 — Khai báo trong app (Streamlit Cloud)

<https://share.streamlit.io> → app → **⋮ → Settings → Secrets** → dán, thay 2 giá trị của bạn → **Save**:

```toml
BACKEND = "powerautomate"
NAM_HOC = "2024-2025,2025-2026,2026-2027,2027-2028"
NAM_HOC_MAC_DINH = "2026-2027"
SP_LIST_Data_TuyenSinh = "Data_TuyenSinh"
SP_LIST_Data_NhapHoc = "Data_NhapHoc"
ADMIN_PASSWORD = "mat-khau-trang-cai-dat"   # bảo vệ trang Cài đặt & đồng bộ

[powerautomate]
flow_url = "DÁN HTTP POST URL Ở BƯỚC 1.7"
key = "MAT-KHAU-CUA-BAN"                    # giống key trong Condition ở bước 1.3
```

App tự khởi động lại. Thanh bên trái phải hiện **Dữ liệu: SharePoint**.

## Bước 3 — Tạo list và đưa dữ liệu cũ lên (trong app, không cần cài gì)

Mở app → menu **Hệ thống → Cài đặt & đồng bộ**:

1. **Kiểm tra kết nối** → báo "chưa có list" là bình thường ở lần đầu.
2. **Tạo list / thêm cột** → app tạo `Data_TuyenSinh` và `Data_NhapHoc` với đủ cột, đúng kiểu.
3. **Kiểm tra kết nối** lại → cả hai list báo *kết nối được, đủ cột*.
4. **Nhập dữ liệu từ Excel** → chọn file `Data_TuyenSinh_chuan_hoa.xlsx` → **Nhập … dòng**.
   Bị ngắt giữa chừng thì bấm nhập lại: dòng đã lên SharePoint được bỏ qua, không tạo trùng.
5. Vào **Hồ sơ nhập học** → bấm **Tạo hồ sơ** để tạo hồ sơ cho các học sinh đã ở bước Nhập học.

Từ đây mọi thao tác trên app được ghi thẳng lên SharePoint.

## Xử lý sự cố

| App báo | Nguyên nhân / cách xử lý |
|---|---|
| *Không có quyền truy cập SharePoint* (403) | Sai `key` trong Secrets so với Condition của flow, hoặc tài khoản flow thiếu quyền trên site |
| *Không tìm thấy list* (404) | Chưa tạo list (Bước 3.2) hoặc `SP_LIST_…` trong Secrets khác tên list |
| *Column '…' does not exist* | List thiếu cột → **Tạo list / thêm cột** |
| Lỗi 429 / chậm | Power Automate giới hạn tốc độ — app tự thử lại; nhập Excel lớn thì chờ vài phút |
| Xem chi tiết lỗi | Power Automate → flow `TuyenSinh-API` → **Lịch sử chạy (28 ngày)** |

Dùng máy tính có Python thì các bước ở Bước 3 cũng làm được bằng
`python scripts/setup_sharepoint.py` và `python scripts/import_excel.py …`.

---

## Đăng nhập bằng Microsoft 365 (ghi tên người nhập / người nhận hồ sơ)

Khi bật đăng nhập, mọi người phải đăng nhập bằng tài khoản Microsoft 365 của trường trước khi dùng
app. Tên tài khoản tự ghi vào **Người cập nhật** (Data tuyển sinh, Hồ sơ nhập học), **Người nhận
hồ sơ** (bảng ký nhận) và **Người nhận hồ sơ / Người xác nhận** (kế toán).

**1. Đăng ký app trên Microsoft Entra** (cần quyền quản trị Microsoft 365 của trường, hoặc nhờ IT):

1. Vào <https://entra.microsoft.com> → **Identity → Applications → App registrations →
   New registration**.
2. **Name**: `Tuyen sinh Tan Phu` · **Supported account types**: *Accounts in this organizational
   directory only (Single tenant)*.
3. **Redirect URI**: chọn **Web**, nhập `https://tuyensinhtanphu.streamlit.app/oauth2callback`
   (đúng địa chỉ app của bạn + `/oauth2callback`) → **Register**.
4. Trang **Overview**: sao chép **Application (client) ID** và **Directory (tenant) ID**.
5. **Certificates & secrets → New client secret** → chọn thời hạn → **Add** → sao chép cột
   **Value** (chỉ hiện 1 lần).

**2. Khai báo trong Secrets** của Streamlit Cloud (thêm vào cuối; dòng `AUTH_DOMAIN` phải đặt
ở **phía trên** dòng `[auth]`, cùng chỗ với `BACKEND = …`):

```toml
AUTH_DOMAIN = "igcschool.edu.vn"   # chỉ cho tài khoản @igcschool.edu.vn (bỏ dòng này nếu không cần)

[auth]
redirect_uri = "https://tuyensinhtanphu.streamlit.app/oauth2callback"
cookie_secret = "một-chuỗi-ngẫu-nhiên-dài-ít-nhất-32-ký-tự"

[auth.microsoft]
client_id = "Application (client) ID"
client_secret = "Value của client secret"
server_metadata_url = "https://login.microsoftonline.com/<Directory (tenant) ID>/v2.0/.well-known/openid-configuration"
```

Lưu Secrets → app khởi động lại và hiện màn hình **Đăng nhập với Microsoft 365**. Sau khi đăng
nhập, tên tài khoản hiện ở góc phải thanh menu (bấm vào để đăng xuất). Khi client secret hết hạn,
tạo secret mới ở bước 1.5 và cập nhật `client_secret`.

> Sau khi cập nhật app, vào **Cài đặt & đồng bộ → Kết nối & đồng bộ → Tạo list / thêm cột** để
> thêm cột *Người cập nhật*, *Người nhận hồ sơ* vào các list.

---

## Tài khoản & phân quyền của app (không cần quyền quản trị Microsoft 365)

1. Vào **Cài đặt & đồng bộ → Tài khoản & phân quyền** → **Tạo list tài khoản** (tạo list
   `DanhMuc_TaiKhoan` trên SharePoint; mật khẩu chỉ lưu dạng mã hóa).
2. Tạo **tài khoản Quản trị đầu tiên cho bạn**. Từ lúc có tài khoản, ai mở app cũng phải đăng nhập.
3. Tạo tài khoản cho từng nhân sự: họ tên, tên đăng nhập, mật khẩu, **vai trò** (Tuyển sinh, Kế
   toán, Giáo vụ, Chỉ xem báo cáo) và chỉnh **Trang được phép**. Tắt *Đang hoạt động* để khóa.
4. Nhân sự đăng nhập, tích **Ghi nhớ đăng nhập trên máy này** → 30 ngày không phải nhập lại.
   Đổi mật khẩu (góc phải thanh menu) hoặc bị khóa → các máy đang ghi nhớ phải đăng nhập lại.

Tên tài khoản được ghi vào hồ sơ: *Người cập nhật*, *Người nhận hồ sơ* (bảng ký nhận).
Nên thêm vào Secrets một khóa riêng để ký mã ghi nhớ đăng nhập (lưu trong bộ nhớ trình duyệt):
`COOKIE_SECRET = "chuỗi-ngẫu-nhiên-dài"` (nếu không có, app dùng `ADMIN_PASSWORD`).

## Trợ lý dữ liệu: bật AI hiểu câu hỏi (Google Gemini, miễn phí)

Trợ lý luôn chạy được mà không cần AI. Khi bật Gemini, trợ lý hiểu câu hỏi tự do tốt hơn
(vd "mấy đứa lớp mười vô học rồi vậy?"). **Chỉ câu hỏi được gửi cho Google**. Số liệu vẫn tính
trong app. Câu có họ tên hoặc số điện thoại, và câu tra cứu học sinh, được xử lý trong app,
không gửi đi.

1. Mở https://aistudio.google.com và đăng nhập bằng tài khoản Google (nên dùng tài khoản của trường).
2. Bấm **Get API key**, rồi **Create API key**. Chọn hoặc tạo một project, sau đó sao chép key
   (chuỗi bắt đầu bằng `AIza…`).
3. Vào Streamlit Cloud, chọn app, rồi **Settings → Secrets**, thêm dòng:

   ```toml
   GEMINI_API_KEY = "AIza..."
   # tùy chọn: đổi mô hình khi Google ra bản mới
   # GEMINI_MODEL = "gemini-2.5-flash"
   ```
4. Bấm **Save**. App tự khởi động lại. Ở trang **Trợ lý**, công tắc **AI hiểu câu hỏi** sẽ bật.

Lưu ý:
- Gói miễn phí giới hạn số lượt mỗi phút và mỗi ngày. Khi hết lượt, trợ lý tự quay về cách hiểu
  theo từ khóa và hiện dòng thông báo nhỏ.
- Ở gói miễn phí, Google có thể dùng nội dung gửi lên (ở đây chỉ là câu hỏi) để cải thiện sản phẩm.
- Báo lỗi "Không có mô hình…" nghĩa là Google đã đổi tên mô hình. Đặt `GEMINI_MODEL` theo tên
  mới trong AI Studio.
- Không chia sẻ API key. Nếu lộ key, xóa key cũ trong AI Studio và tạo key mới.
