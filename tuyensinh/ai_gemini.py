"""Dùng Google Gemini (gói miễn phí) để HIỂU câu hỏi tự do của người dùng.

Chỉ gửi câu hỏi (và câu hỏi trước đó để hiểu ngữ cảnh) — KHÔNG gửi dữ liệu học sinh.
Gemini viết lại câu hỏi thành một "câu hỏi chuẩn" mà bộ máy trợ lý trong app (tro_ly.py)
hiểu được; mọi số liệu vẫn được tính trong app. Lỗi / hết lượt -> trả về None để trợ lý
dùng cách hiểu theo từ khóa như cũ.

Secrets: GEMINI_API_KEY (bắt buộc), GEMINI_MODEL (mặc định gemini-2.5-flash).
"""
from __future__ import annotations

import json
import re
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


def co_khoa() -> bool:
    return bool(str(config.get("GEMINI_API_KEY") or "").strip())


def viet_lai(cau_hoi: str, truoc: str | None = None, nam_hoc: str = "",
             hom_nay: str = "", timeout: float = 12) -> KetQua:
    """Gửi câu hỏi (không kèm dữ liệu) cho Gemini để viết lại thành câu hỏi chuẩn."""
    key = str(config.get("GEMINI_API_KEY") or "").strip()
    if not key:
        return KetQua(loi="Chưa có GEMINI_API_KEY")
    model = str(config.get("GEMINI_MODEL") or MODEL).strip()
    noi_dung = (f"Năm học đang xem: {nam_hoc}. Hôm nay: {hom_nay}.\n"
                f"CÂU TRƯỚC: {truoc or '(không có)'}\nCÂU HỎI: {cau_hoi}")
    body = {
        "systemInstruction": {"parts": [{"text": HUONG_DAN}]},
        "contents": [{"role": "user", "parts": [{"text": noi_dung}]}],
        "generationConfig": {"temperature": 0, "maxOutputTokens": 256,
                             "responseMimeType": "application/json",
                             "responseSchema": SCHEMA},
    }
    try:
        r = requests.post(URL.format(model=model), params={"key": key}, json=body,
                          timeout=timeout)
    except requests.RequestException as e:
        return KetQua(loi=f"Không kết nối được Gemini ({type(e).__name__})")
    if r.status_code == 429:
        return KetQua(loi="Gemini đã hết lượt miễn phí (thử lại sau ít phút)")
    if r.status_code in (400, 401, 403):
        return KetQua(loi=f"GEMINI_API_KEY không hợp lệ hoặc chưa bật ({r.status_code})")
    if r.status_code == 404:
        return KetQua(loi=f"Không có mô hình '{model}' — kiểm tra GEMINI_MODEL")
    if not r.ok:
        return KetQua(loi=f"Gemini lỗi {r.status_code}")
    try:
        text = r.json()["candidates"][0]["content"]["parts"][0]["text"]
        data = json.loads(re.sub(r"^```(?:json)?|```$", "", text.strip()))
        cau = str(data.get("cau_hoi") or "").strip()
        return KetQua(cau or None, bool(data.get("ngoai_pham_vi")))
    except (KeyError, IndexError, ValueError, TypeError):
        return KetQua(loi="Không đọc được phản hồi của Gemini")
