"""Gemini chỉ dùng để hiểu câu hỏi; dữ liệu học sinh không gửi đi; lỗi thì dùng cách thường."""
import json
from datetime import date

import pandas as pd

from tuyensinh import ai_gemini, tro_ly

TS = pd.DataFrame([
    {"id": "1", "HoTenHS": "Trần Huy Long", "Khoi": "10", "TrangThai": "Nhập học",
     "SDT": "0927666649", "NgayLienHe": "2026-07-05", "Nguon": "Hotline"},
    {"id": "2", "HoTenHS": "Lê Minh Anh", "Khoi": "6", "TrangThai": "Tư vấn",
     "SDT": "0909000111", "NgayLienHe": "2026-06-01", "Nguon": "Hotline"},
])
CTX = tro_ly.Ctx(TS, pd.DataFrame(), "2026-2027", hom_nay=date(2026, 7, 25))


def ai_gia(tra_ve=None, loi="", ngoai=False):
    goi = []

    def f(cau, truoc):
        goi.append((cau, truoc))
        return ai_gemini.KetQua(tra_ve, ngoai, loi)
    return f, goi


def test_ai_viet_lai_cau_hoi():
    f, goi = ai_gia("bao nhiêu học sinh nhập học khối 10")
    r = tro_ly.tra_loi("mấy đứa lớp mười vô học rồi vậy", CTX, ai=f)
    assert goi and r.ai_hieu == "bao nhiêu học sinh nhập học khối 10"
    assert "**1** học sinh nhập học (khối 10)" in r.text


def test_khong_gui_ten_va_so_dien_thoai():
    f, goi = ai_gia("x")
    assert "Trần Huy Long" in tro_ly.tra_loi("Trần Huy Long học lớp nào", CTX, ai=f).text
    tro_ly.tra_loi("tra cứu 0927 666 649", CTX, ai=f)
    tro_ly.tra_loi("tìm long", CTX, ai=f)
    assert goi == []  # không câu nào được gửi cho Gemini


def test_loi_va_ngoai_pham_vi():
    f, _ = ai_gia(loi="Gemini đã hết lượt miễn phí")
    r = tro_ly.tra_loi("bao nhiêu liên hệ", CTX, ai=f)
    assert "**2** liên hệ" in r.text and "hết lượt" in r.ai_loi
    f, _ = ai_gia("thời tiết", ngoai=True)
    assert "ngoài dữ liệu tuyển sinh" in tro_ly.tra_loi("mai trời mưa không", CTX, ai=f).text
    # AI viết lại thành câu bộ máy không hiểu -> quay về cách hiểu thường
    f, _ = ai_gia("abc xyz qwe")
    assert "**2** liên hệ" in tro_ly.tra_loi("bao nhiêu liên hệ", CTX, ai=f).text


class _Resp:
    def __init__(self, code, data=None):
        self.status_code, self._data, self.ok = code, data, code == 200

    def json(self):
        return self._data


def test_doc_phan_hoi_gemini(monkeypatch):
    monkeypatch.setenv("GEMINI_API_KEY", "k")
    gui = {}

    def post(url, params, json, timeout):
        gui.update(url=url, body=json)
        text = '{"cau_hoi": "nhập học theo khối", "ngoai_pham_vi": false}'
        return _Resp(200, {"candidates": [{"content": {"parts": [{"text": text}]}}]})
    monkeypatch.setattr(ai_gemini.requests, "post", post)
    kq = ai_gemini.viet_lai("hs vô học theo từng khối", "câu trước", "2026-2027", "25/07/2026")
    assert kq.cau_hoi == "nhập học theo khối" and not kq.loi
    assert "gemini-2.5-flash" in gui["url"]
    assert "hs vô học theo từng khối" in json.dumps(gui["body"], ensure_ascii=False)
    monkeypatch.setattr(ai_gemini.requests, "post", lambda *a, **k: _Resp(429))
    assert "hết lượt" in ai_gemini.viet_lai("x").loi
    monkeypatch.delenv("GEMINI_API_KEY")
    assert ai_gemini.viet_lai("x").loi == "Chưa có GEMINI_API_KEY"


def test_tim_khoa_moi_vi_tri(monkeypatch):
    monkeypatch.delenv("GEMINI_API_KEY", raising=False)
    for secrets, vi_tri in (({"GEMINI_API_KEY": "a1"}, "GEMINI_API_KEY"),
                            ({"powerautomate": {"url": "x", "GEMINI_API_KEY": "a1"}},
                             "[powerautomate] GEMINI_API_KEY"),
                            ({"gemini": {"api_key": "a1"}}, "[gemini] api_key"),
                            ({"gemini_api_key": "a1"}, "gemini_api_key")):
        monkeypatch.setattr(ai_gemini.config, "_secrets", lambda s=secrets: s)
        assert ai_gemini.tim_khoa() == ("a1", vi_tri)
    monkeypatch.setattr(ai_gemini.config, "_secrets", lambda: {"auth": {"x": "y"}})
    assert ai_gemini.tim_khoa() == ("", "") and not ai_gemini.co_khoa()


def test_tu_chon_mo_hinh_khi_404(monkeypatch):
    monkeypatch.setenv("GEMINI_API_KEY", "k2")
    ai_gemini._MO_HINH.clear()
    goi = []

    def post(url, params, json, timeout):
        goi.append(url)
        if "gemini-2.5-flash:" in url:
            return _Resp(404, {"error": {"message": "not found"}})
        text = '```json\n{"cau_hoi": "tổng quan", "ngoai_pham_vi": false}\n```'
        return _Resp(200, {"candidates": [{"content": {"parts": [{"text": text}]}}]})

    def get(url, params, timeout):
        return _Resp(200, {"models": [
            {"name": "models/gemini-3.0-flash-lite", "supportedGenerationMethods": ["generateContent"]},
            {"name": "models/gemini-3.0-flash", "supportedGenerationMethods": ["generateContent"]},
            {"name": "models/gemini-3.0-flash-image", "supportedGenerationMethods": ["generateContent"]},
            {"name": "models/gemini-3.0-pro", "supportedGenerationMethods": ["generateContent"]},
            {"name": "models/text-embedding-9", "supportedGenerationMethods": ["embedContent"]}]})
    monkeypatch.setattr(ai_gemini.requests, "post", post)
    monkeypatch.setattr(ai_gemini.requests, "get", get)
    kq = ai_gemini.viet_lai("tình hình")
    assert kq.cau_hoi == "tổng quan" and "gemini-3.0-flash:" in goi[-1]
    # lần sau dùng luôn mô hình đã chọn, không gọi tên cũ nữa
    goi.clear()
    ai_gemini.viet_lai("tình hình")
    assert len(goi) == 1 and "gemini-3.0-flash:" in goi[0]
