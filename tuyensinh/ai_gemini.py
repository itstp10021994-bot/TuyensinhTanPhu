"""Dùng Google Gemini (gói miễn phí) để HIỂU câu hỏi tự do của người dùng.

Chỉ gửi câu hỏi (và câu hỏi trước đó để hiểu ngữ cảnh) — KHÔNG gửi dữ liệu học sinh.
Gemini viết lại câu hỏi thành một "câu hỏi chuẩn" mà bộ máy trợ lý trong app (tro_ly.py)
hiểu được; mọi số liệu vẫn được tính trong app. Lỗi / hết lượt -> trả về None để trợ lý
dùng cách hiểu theo từ khóa như cũ.

Secrets: GEMINI_API_KEY (bắt buộc), GEMINI_MODEL (tùy chọn; mặc định thử gemini-2.5-flash,
không có thì tự hỏi Google danh sách mô hình và chọn bản Flash mới nhất).
"""
from __future__ import annotations

import json
import re
import time
from dataclasses import dataclass

import requests

from . import config

URL = "https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent"
MODEL = "gemini-2.5-flash"

HUONG_DAN = """Bạn là bộ chuyển đổi câu hỏi cho trợ lý dữ liệu tuyển sinh của một trường học
(khối 1–12, phân hệ IEP/ESL, chế độ nội trú/bán trú/ngoại trú). Nhiệm vụ: viết lại câu hỏi của
người dùng thành MỘT câu hỏi chuẩn, ngắn, tiếng Việt có dấu, theo đúng các mẫu dưới đây.
Không trả lời câu hỏi, không bịa số liệu.

Dữ liệu có: liên hệ tuyển sinh với các bước "tư vấn" → "nộp hồ sơ" → "nhập học", hoặc
"rút hồ sơ"; khối; hệ IEP/ESL; chế độ; giới tính; nguồn (Ban TS đến trường tư vấn, Bạn bè -
Người thân, Quảng cáo tự động, Mạng xã hội, Hotline, Trực tiếp, Gần nhà, Tự tìm hiểu, PHHS trường
giới thiệu, CBNV Trường-IGC, Giáo viên trường cũ, Đi trường TS); trường cũ, tỉnh, phường/xã của
trường cũ; người nhận hồ sơ; ngày liên hệ; giữ chỗ / hoàn phí / học phí; giấy tờ nhập học.

Mẫu câu chuẩn (ghép các phần khi cần):
- Đếm: "bao nhiêu học sinh nhập học khối 10 nội trú tháng 7" | "bao nhiêu liên hệ tuần này"
  | "bao nhiêu học sinh nữ nộp hồ sơ" | "bao nhiêu học sinh rút hồ sơ"
- Danh sách: "danh sách học sinh nhập học khối 6 hệ IEP"
- Thống kê: "thống kê liên hệ theo nguồn" | "nhập học theo khối" | "liên hệ theo tháng"
  (trục: khối, nguồn, tháng, tuần, bước, chế độ, giữ chỗ, giới tính, trường cũ, tỉnh, phường,
  người nhận)
- Xếp hạng: "trường cũ nào có nhiều học sinh nhập học nhất" | "tỉnh nào ít liên hệ nhất"
- Tỷ lệ: "tỷ lệ nhập học khối 10" | "tỷ lệ nhập học theo nguồn" | "nguồn nào hiệu quả nhất"
- So sánh năm: "nhập học khối 10 so với năm trước" | "liên hệ theo khối qua các năm"
  | "nhập học 3 năm gần đây" | "năm học 2024-2025 bao nhiêu nhập học"
  | cùng kỳ: "liên hệ tháng 4 so với năm trước"
- So sánh khối: "so sánh khối 6 và khối 10"
- Tổng quan: "tổng quan" | "tổng quan tháng này"
- Tra cứu: "tìm <họ tên>" | "tra cứu <số điện thoại>"
- Khác: "học sinh nào thiếu giấy tờ khối 6" | "tư vấn quá 14 ngày chưa chuyển bước"
  | "danh sách chưa giữ chỗ" | "học sinh còn nợ học phí" | "chờ hoàn phí" | "tổng tiền giữ chỗ"

Quy tắc:
- "lớp 10", "K10", "khối mười" → "khối 10". "trúng tuyển", "đã vào học" → "nhập học".
  "năm ngoái" → "năm trước". "học sinh mới"/"phụ huynh hỏi" → "liên hệ".
- Nếu câu hỏi nối tiếp câu trước (vd "còn khối 11?", "thế năm trước?"), hãy ghép với
  CÂU TRƯỚC thành một câu đầy đủ, độc lập.
- Thời gian tương đối (hôm nay, tuần này, tháng trước, 30 ngày qua…) giữ nguyên dạng chữ.
- Nếu câu hỏi không liên quan dữ liệu tuyển sinh, đặt ngoai_pham_vi = true.
"""

SCHEMA = {
    "type": "OBJECT",
    "properties": {
        "cau_hoi": {"type": "STRING", "description": "Câu hỏi chuẩn theo mẫu"},
        "ngoai_pham_vi": {"type": "BOOLEAN"},
    },
    "required": ["cau_hoi", "ngoai_pham_vi"],
}


@dataclass
class KetQua:
    cau_hoi: str | None = None
    ngoai_pham_vi: bool = False
    loi: str = ""


def tim_khoa() -> tuple[str, str]:
    """(API key, vị trí tìm thấy). Chấp nhận key ở cấp ngoài cùng của Secrets, nằm lẫn trong
    một mục [..] bất kỳ (lỗi hay gặp khi dán xuống cuối file), hoặc mục [gemini] api_key."""
    v = str(config.get("GEMINI_API_KEY") or "").strip().strip('"')
    if v:
        return v, "GEMINI_API_KEY"
    s = config._secrets()
    for k, val in s.items():  # khác chữ hoa/thường
        if str(k).strip().lower() == "gemini_api_key" and str(val).strip():
            return str(val).strip(), str(k)
    for muc, bang in s.items():
        if not hasattr(bang, "items"):
            continue
        for k, val in bang.items():
            ten = str(k).strip().lower()
            if (ten == "gemini_api_key" or (str(muc).lower() == "gemini" and ten in ("api_key", "key"))) \
                    and str(val).strip():
                return str(val).strip(), f"[{muc}] {k}"
    return "", ""


def co_khoa() -> bool:
    return bool(tim_khoa()[0])


LIST_URL = "https://generativelanguage.googleapis.com/v1beta/models"
_MO_HINH: dict[str, str] = {}  # key -> mô hình tự chọn (lưu trong tiến trình)
_DS_MO_HINH: dict[str, list[str]] = {}  # key -> các mô hình dùng được, tốt nhất trước
_BO_QUA = ("image", "tts", "audio", "live", "embedding", "vision", "learnlm", "gemma", "aqa",
           "computer-use", "robotics", "native")


def _diem(ten: str) -> tuple:
    """Xếp hạng mô hình: ưu tiên flash (không lite) bản ổn định, phiên bản mới nhất."""
    m = re.search(r"gemini-(\d+(?:\.\d+)?)", ten)
    phien_ban = float(m.group(1)) if m else 0.0
    loai = 3 if "flash" in ten and "lite" not in ten else 2 if "flash" in ten else \
        1 if "pro" in ten else 0
    on_dinh = 0 if any(x in ten for x in ("preview", "exp", "-0", "latest")) else 1
    return (loai, on_dinh, phien_ban, -len(ten))


def ds_mo_hinh(key: str, timeout: float = 10) -> list[str]:
    """Các mô hình Gemini key được dùng (generateContent), xếp tốt nhất trước (lưu đệm)."""
    if key in _DS_MO_HINH:
        return _DS_MO_HINH[key]
    ds, token = [], None
    try:
        for _ in range(5):
            r = requests.get(LIST_URL, params={"key": key, "pageSize": 200,
                                               **({"pageToken": token} if token else {})},
                             timeout=timeout)
            if not r.ok:
                return []
            data = r.json()
            ds += data.get("models", [])
            token = data.get("nextPageToken")
            if not token:
                break
    except (requests.RequestException, ValueError):
        return []
    ten = [str(m.get("name", "")).removeprefix("models/") for m in ds
           if "generateContent" in (m.get("supportedGenerationMethods") or [])]
    ten = [t for t in ten if t.startswith("gemini") and not any(x in t for x in _BO_QUA)]
    _DS_MO_HINH[key] = sorted(set(ten), key=_diem, reverse=True)
    return _DS_MO_HINH[key]


def chon_mo_hinh(key: str, timeout: float = 10) -> str | None:
    """Mô hình phù hợp nhất cho key (bản Flash ổn định mới nhất)."""
    if key not in _MO_HINH:
        ds = ds_mo_hinh(key, timeout)
        if not ds:
            return None
        _MO_HINH[key] = ds[0]
    return _MO_HINH[key]


def _thong_bao(r) -> str:
    try:
        return str(r.json().get("error", {}).get("message", ""))[:160]
    except (ValueError, AttributeError):
        return ""


def viet_lai(cau_hoi: str, truoc: str | None = None, nam_hoc: str = "",
             hom_nay: str = "", timeout: float = 12) -> KetQua:
    """Gửi câu hỏi (không kèm dữ liệu) cho Gemini để viết lại thành câu hỏi chuẩn."""
    key = tim_khoa()[0]
    if not key:
        return KetQua(loi="Chưa có GEMINI_API_KEY")
    model = str(config.get("GEMINI_MODEL") or _MO_HINH.get(key) or MODEL).strip()
    noi_dung = (f"Năm học đang xem: {nam_hoc}. Hôm nay: {hom_nay}.\n"
                f"CÂU TRƯỚC: {truoc or '(không có)'}\nCÂU HỎI: {cau_hoi}")
    cau_hinh = {"temperature": 0, "maxOutputTokens": 256,
                "responseMimeType": "application/json", "responseSchema": SCHEMA}
    body = {"systemInstruction": {"parts": [{"text": HUONG_DAN}]},
            "contents": [{"role": "user", "parts": [{"text": noi_dung}]}],
            "generationConfig": cau_hinh}

    def goi(m):
        return requests.post(URL.format(model=m), params={"key": key}, json=body,
                             timeout=timeout)
    try:
        r = goi(model)
        if r.status_code == 404:  # tên mô hình cũ / không có với key này -> tự chọn mô hình
            moi = chon_mo_hinh(key)
            if moi and moi != model:
                model, r = moi, goi(moi)
        if r.status_code == 400 and "api key" not in _thong_bao(r).lower():
            cau_hinh.pop("responseSchema")  # mô hình không nhận schema -> chỉ yêu cầu JSON
            r = goi(model)
        if r.status_code in (500, 502, 503, 504):  # quá tải tạm thời -> chờ chút, thử lại
            time.sleep(1.2)
            r = goi(model)
        if r.status_code in (429, 500, 502, 503, 504):
            # vẫn quá tải / hết lượt: thử mô hình khác (gói miễn phí tính lượt theo từng mô hình)
            for khac in [m for m in ds_mo_hinh(key) if m != model][:3]:
                r2 = goi(khac)
                if r2.ok:
                    model, r = khac, r2
                    _MO_HINH[key] = khac  # dùng tiếp mô hình này cho các câu sau
                    break
    except requests.RequestException as e:
        return KetQua(loi=f"Không kết nối được Gemini ({type(e).__name__})")
    if r.status_code == 429:
        return KetQua(loi="Gemini đã hết lượt miễn phí (thử lại sau ít phút)")
    if r.status_code in (500, 502, 503, 504):
        return KetQua(loi="Gemini đang quá tải (lỗi tạm thời phía Google, thử lại sau ít phút)")
    if r.status_code in (400, 401, 403):
        tb = _thong_bao(r)
        if r.status_code == 400 and "api key" not in tb.lower():
            return KetQua(loi=f"Gemini từ chối yêu cầu ({model}): {tb}")
        return KetQua(loi=f"GEMINI_API_KEY không hợp lệ hoặc chưa bật ({r.status_code})")
    if r.status_code == 404:
        return KetQua(loi=f"Không tìm được mô hình Gemini dùng được với key này ({model})")
    if not r.ok:
        return KetQua(loi=f"Gemini lỗi {r.status_code}: {_thong_bao(r)}")
    try:
        cand = r.json()["candidates"][0]
        text = "".join(p.get("text", "") for p in cand["content"]["parts"])
        text = re.sub(r"^```(?:json)?\s*|\s*```$", "", text.strip())
        data = json.loads(text[text.find("{"): text.rfind("}") + 1])
        cau = str(data.get("cau_hoi") or "").strip()
        return KetQua(cau or None, bool(data.get("ngoai_pham_vi")))
    except (KeyError, IndexError, ValueError, TypeError):
        return KetQua(loi="Không đọc được phản hồi của Gemini")
