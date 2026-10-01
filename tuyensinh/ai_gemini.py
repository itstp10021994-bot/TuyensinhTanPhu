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

HUONG_DAN = """Bạn là bộ phân tích câu hỏi cho trợ lý dữ liệu tuyển sinh của một trường học
(khối 1–12, phân hệ IEP/ESL, chế độ Nội trú/Bán trú/Ngoại trú). Đọc câu hỏi tiếng Việt (có thể
không dấu, viết tắt, sai chính tả) và trả về JSON mô tả Ý ĐỊNH theo schema. Không trả lời câu
hỏi, không bịa số liệu.

Dữ liệu: mỗi liên hệ tuyển sinh có bước "Tư vấn" → "Nộp hồ sơ" → "Nhập học" (hoặc "Rút hồ sơ"),
khối, hệ, chế độ, giới tính, nguồn, trường cũ + tỉnh + phường/xã của trường cũ, người nhận hồ sơ,
tên phụ huynh, giữ chỗ, tình trạng tư vấn, ngày liên hệ, họ tên học sinh.
Nguồn có trong dữ liệu: Ban TS đến trường tư vấn, Bạn bè - Người thân, Quảng cáo tự động, Mạng xã
hội, Hotline, Trực tiếp, Gần nhà, Tự tìm hiểu, PHHS trường giới thiệu, CBNV Trường-IGC, Giáo viên
trường cũ, Đi trường TS.

Cách điền:
- loai: dem (bao nhiêu) | danh_sach (liệt kê, những ai) | thong_ke (theo/chia theo X) |
  xep_hang (X nào nhiều/ít nhất, top) | ty_le (tỷ lệ, hiệu quả, chuyển đổi) | tong_quan |
  tra_cuu (tìm 1 học sinh cụ thể theo họ tên đầy đủ / SĐT) | giay_to (thiếu giấy tờ) |
  tai_chinh (tiền, giữ chỗ, hoàn phí, học phí) | qua_han (tư vấn lâu chưa chuyển bước).
- doi_tuong: lien_he (mặc định, mọi liên hệ) | tu_van | nop_ho_so | nhap_hoc ("tuyển được",
  "trúng tuyển", "vào học") | rut_ho_so | chua_nhap_hoc.
- Bộ lọc dạng danh sách: nhiều giá trị = HOẶC ("khối 10 và 11" -> khoi ["10","11"]); các bộ lọc
  khác nhau kết hợp VÀ. khoi chỉ ghi số ("lớp 10", "K10" -> "10"; "10 IEP" -> "10-IEP").
- tinh / phuong_xa / truong_cu: ghi tên riêng ("Tây Ninh", "Phước Thái"). "từ Tây Ninh" -> tinh.
  "trường Phước Thái" -> truong_cu.
- ten: tên gọi ("tên An"); ho: họ ("họ Nguyễn"); ten_chua: "tên có chữ Minh".
- Thời gian: đổi thành tu_ngay / den_ngay (YYYY-MM-DD) dựa vào "Hôm nay"; "tháng 4" = tháng 4 gần
  nhất đã qua hoặc đang diễn ra; "tuần này" = thứ 2 đến hôm nay.
- nam_hoc: chỉ ghi khi người dùng nêu năm học / "năm trước" (dùng danh sách năm học được cung cấp).
  so_sanh_nam = true khi "so với năm trước", "qua các năm", "N năm gần đây" (so_nam = N).
- theo: trục khi thống kê / xếp hạng / tỷ lệ theo nhóm: khoi, nguon, thang, tuan, buoc, che_do,
  gioi_tinh, truong_cu, tinh, phuong_xa, nguoi_nhan, giu_cho, he, tinh_trang.
- thu_tu: "it" khi hỏi ít nhất/thấp nhất, ngược lại "nhieu"; top: số dòng ("top 5").
- ty_le_cua: nhap_hoc (mặc định) | nop_ho_so | rut_ho_so. "nguồn nào hiệu quả nhất" -> loai ty_le,
  theo nguon.
- Câu nối tiếp ("còn khối 11 thì sao?", "năm trước?"): dùng CÂU TRƯỚC làm nền, chỉ thay phần mới.
- cau_hoi: viết lại câu hỏi đầy đủ, ngắn gọn, tiếng Việt có dấu (để hiển thị cho người dùng).
- Không liên quan dữ liệu tuyển sinh -> ngoai_pham_vi = true.
"""

_DS = {"type": "ARRAY", "items": {"type": "STRING"}}
SCHEMA = {
    "type": "OBJECT",
    "properties": {
        "cau_hoi": {"type": "STRING"},
        "ngoai_pham_vi": {"type": "BOOLEAN"},
        "loai": {"type": "STRING", "enum": ["dem", "danh_sach", "thong_ke", "xep_hang", "ty_le",
                                            "tong_quan", "tra_cuu", "giay_to", "tai_chinh",
                                            "qua_han"]},
        "doi_tuong": {"type": "STRING", "enum": ["lien_he", "tu_van", "nop_ho_so", "nhap_hoc",
                                                 "rut_ho_so", "chua_nhap_hoc"]},
        "khoi": _DS, "he": _DS, "che_do": _DS, "nguon": _DS, "tinh": _DS, "phuong_xa": _DS,
        "truong_cu": _DS, "nguoi_nhan": _DS, "giu_cho": _DS, "tinh_trang": _DS, "phu_huynh": _DS,
        "gioi_tinh": {"type": "STRING", "enum": ["", "Nam", "Nữ"]},
        "ten": {"type": "STRING"}, "ho": {"type": "STRING"}, "ten_chua": {"type": "STRING"},
        "tu_ngay": {"type": "STRING"}, "den_ngay": {"type": "STRING"},
        "nam_hoc": _DS, "so_sanh_nam": {"type": "BOOLEAN"}, "so_nam": {"type": "INTEGER"},
        "theo": {"type": "STRING", "enum": ["", "khoi", "nguon", "thang", "tuan", "buoc", "che_do",
                                           "gioi_tinh", "truong_cu", "tinh", "phuong_xa",
                                           "nguoi_nhan", "giu_cho", "he", "tinh_trang"]},
        "thu_tu": {"type": "STRING", "enum": ["", "nhieu", "it"]},
        "top": {"type": "INTEGER"},
        "ty_le_cua": {"type": "STRING", "enum": ["", "nhap_hoc", "nop_ho_so", "rut_ho_so"]},
        "tim": {"type": "STRING"}, "so_ngay": {"type": "INTEGER"},
        "tai_chinh": {"type": "STRING", "enum": ["", "tong", "chua_giu_cho", "hoan_phi",
                                                "con_no"]},
    },
    "required": ["cau_hoi", "ngoai_pham_vi", "loai"],
}


@dataclass
class KetQua:
    cau_hoi: str | None = None
    ngoai_pham_vi: bool = False
    loi: str = ""
    mo_hinh: str = ""  # mô hình đã trả lời (để hiển thị / chẩn đoán)
    y_dinh: dict | None = None  # ý định có cấu trúc (loai + bộ lọc) -> truy_van.thuc_hien


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


def _phien_ban(model: str) -> float:
    m = re.search(r"gemini-(\d+(?:\.\d+)?)", model)
    return float(m.group(1)) if m else 0.0


def _suy_nghi(model: str) -> dict | None:
    """Giảm 'suy nghĩ' (thinking) để trả lời nhanh: việc ở đây chỉ là viết lại câu hỏi."""
    v = _phien_ban(model)
    if v >= 3:
        return {"thinkingLevel": "low"}
    if v >= 2.5:
        return {"thinkingBudget": 128 if "pro" in model else 0}
    return None


def _goi(key: str, model: str, body: dict, timeout: float):
    """Gọi 1 mô hình; tự bỏ thiết lập thinking / responseSchema nếu mô hình không nhận."""
    cfg = dict(body["generationConfig"])
    if tn := _suy_nghi(model):
        cfg["thinkingConfig"] = tn
    for _ in range(3):
        r = requests.post(URL.format(model=model), params={"key": key},
                          json={**body, "generationConfig": cfg}, timeout=timeout)
        tb = _thong_bao(r).lower() if r.status_code == 400 else ""
        if r.status_code != 400 or "api key" in tb:
            return r
        if "thinking" in tb and "thinkingConfig" in cfg:
            cfg.pop("thinkingConfig")
        elif "responseSchema" in cfg:
            cfg.pop("responseSchema")  # mô hình không nhận schema -> chỉ yêu cầu JSON
        else:
            return r
    return r


def _doc(r, model: str) -> KetQua:
    try:
        cand = r.json()["candidates"][0]
        text = "".join(p.get("text", "") for p in cand["content"]["parts"]
                       if not p.get("thought"))
        text = re.sub(r"^```(?:json)?\s*|\s*```$", "", text.strip())
        data = json.loads(text[text.find("{"): text.rfind("}") + 1])
        cau = str(data.get("cau_hoi") or "").strip()
        y_dinh = {k: v for k, v in data.items() if k not in ("cau_hoi", "ngoai_pham_vi")
                  and v not in (None, "", [], 0, False)}
        return KetQua(cau or None, bool(data.get("ngoai_pham_vi")), mo_hinh=model,
                      y_dinh=y_dinh if y_dinh.get("loai") else None)
    except (KeyError, IndexError, ValueError, TypeError):
        return KetQua(loi=f"Không đọc được phản hồi của Gemini ({model})", mo_hinh=model)


def viet_lai(cau_hoi: str, truoc: str | None = None, nam_hoc: str = "",
             hom_nay: str = "", timeout: float = 20, tong_thoi_gian: float = 40,
             cac_nam: list[str] | None = None) -> KetQua:
    """Gửi câu hỏi (không kèm dữ liệu) cho Gemini để viết lại thành câu hỏi chuẩn.
    Lỗi 404 / quá tải / hết lượt / quá thời gian -> thử các mô hình khác key được dùng."""
    key = tim_khoa()[0]
    if not key:
        return KetQua(loi="Chưa có GEMINI_API_KEY")
    dat_rieng = str(config.get("GEMINI_MODEL") or "").strip()
    model = dat_rieng or _MO_HINH.get(key) or MODEL
    noi_dung = (f"Năm học đang xem: {nam_hoc}. Các năm học có dữ liệu: "
                f"{', '.join(cac_nam or []) or nam_hoc}. Hôm nay: {hom_nay}.\n"
                f"CÂU TRƯỚC: {truoc or '(không có)'}\nCÂU HỎI: {cau_hoi}")
    body = {"systemInstruction": {"parts": [{"text": HUONG_DAN}]},
            "contents": [{"role": "user", "parts": [{"text": noi_dung}]}],
            "generationConfig": {"temperature": 0, "maxOutputTokens": 2048,
                                 "responseMimeType": "application/json",
                                 "responseSchema": SCHEMA}}
    het_gio = time.monotonic() + tong_thoi_gian
    da_thu, loi_cuoi, r = [], "", None
    hang_doi = [model]
    while hang_doi and time.monotonic() < het_gio - 3:
        m = hang_doi.pop(0)
        if m in da_thu:
            continue
        da_thu.append(m)
        try:
            r = _goi(key, m, body, min(timeout, het_gio - time.monotonic()))
            if r.status_code in (500, 502, 503, 504) and len(da_thu) == 1:
                time.sleep(1.2)  # quá tải tạm thời -> thử lại một lần
                r = _goi(key, m, body, min(timeout, het_gio - time.monotonic()))
        except requests.Timeout:
            loi_cuoi = f"Gemini trả lời quá chậm ({m})"
            # chậm -> ưu tiên bản lite (nhanh hơn)
            hang_doi += sorted([x for x in ds_mo_hinh(key) if x not in da_thu],
                               key=lambda x: "lite" not in x)[:2]
            continue
        except requests.RequestException as e:
            return KetQua(loi=f"Không kết nối được Gemini ({type(e).__name__})")
        if r.ok:
            kq = _doc(r, m)
            if not dat_rieng and not kq.loi:
                _MO_HINH[key] = m  # dùng tiếp mô hình chạy được cho các câu sau
            return kq
        if r.status_code in (404, 429, 500, 502, 503, 504):
            loi_cuoi = {404: f"Không có mô hình '{m}'",
                        429: "Gemini đã hết lượt miễn phí (thử lại sau ít phút)"}.get(
                r.status_code, "Gemini đang quá tải (lỗi tạm thời phía Google, thử lại sau ít phút)")
            hang_doi += [x for x in ds_mo_hinh(key) if x not in da_thu][:3]
            continue
        tb = _thong_bao(r)
        if r.status_code in (400, 401, 403) and (r.status_code != 400 or "api key" in tb.lower()):
            return KetQua(loi=f"GEMINI_API_KEY không hợp lệ hoặc chưa bật ({r.status_code})")
        return KetQua(loi=f"Gemini lỗi {r.status_code} ({m}): {tb}")
    return KetQua(loi=loi_cuoi or "Gemini không phản hồi")
