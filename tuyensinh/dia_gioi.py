"""Chuẩn hóa địa giới hành chính về danh mục MỚI (sau sáp nhập 2025: Tỉnh/Thành → Phường/Xã,
không còn cấp quận/huyện) — dùng cho Data tuyển sinh và Hồ sơ nhập học.

- Tỉnh: tên tắt / thiếu tiền tố ("TP. Hồ Chí Minh", "Tây Ninh") → tên chuẩn ("Thành phố Hồ Chí
  Minh", "Tỉnh Tây Ninh"); tên 63 tỉnh cũ → 34 tỉnh mới (Nghị quyết 202/2025/QH15).
- Phường/Xã: khớp với 3.321 phường/xã mới của tỉnh đó, chấp nhận "P.", "X.", "TT.", thiếu tiền tố.
- Không khớp chắc chắn (vd phường cũ "Phường 14", xã đã sáp nhập đổi tên) → KHÔNG tự đoán: liệt
  kê để người dùng chọn phường/xã mới tương ứng.
"""
from __future__ import annotations

import re

from . import danh_muc as DM

# Cặp cột (tỉnh, phường/xã) cần chuẩn hóa của từng list
CAP_COT = {
    "Data_TuyenSinh": [("TruongCu_Tinh", "TruongCu_PhuongXa")],
    "Data_NhapHoc": [("ChoO_Tinh", "ChoO_Xa"), ("HK_Tinh", "HK_Xa"),
                     ("NoiSinh_Tinh", "NoiSinh_Xa"), ("QueQuan_Tinh", "QueQuan_Xa"),
                     ("NoiKS_Tinh", "NoiKS_Xa"), ("TruongCu_Tinh", "TruongCu_PhuongXa")],
}

# 63 tỉnh cũ → 34 tỉnh mới (Nghị quyết 202/2025/QH15, hiệu lực 12/6/2025); tên lõi, không tiền tố
TINH_CU_MOI = {
    "ha giang": "Tuyên Quang", "yen bai": "Lào Cai", "bac kan": "Thái Nguyên",
    "vinh phuc": "Phú Thọ", "hoa binh": "Phú Thọ", "bac giang": "Bắc Ninh",
    "thai binh": "Hưng Yên", "hai duong": "Hải Phòng", "ha nam": "Ninh Bình",
    "nam dinh": "Ninh Bình", "quang binh": "Quảng Trị", "quang nam": "Đà Nẵng",
    "kon tum": "Quảng Ngãi", "binh dinh": "Gia Lai", "ninh thuan": "Khánh Hòa",
    "dak nong": "Lâm Đồng", "binh thuan": "Lâm Đồng", "phu yen": "Đắk Lắk",
    "binh duong": "Hồ Chí Minh", "ba ria vung tau": "Hồ Chí Minh", "ba ria": "Hồ Chí Minh",
    "vung tau": "Hồ Chí Minh", "binh phuoc": "Đồng Nai", "long an": "Tây Ninh",
    "soc trang": "Cần Thơ", "hau giang": "Cần Thơ", "ben tre": "Vĩnh Long",
    "tra vinh": "Vĩnh Long", "tien giang": "Đồng Tháp", "bac lieu": "Cà Mau",
    "kien giang": "An Giang", "thua thien hue": "Huế",
    "hcm": "Hồ Chí Minh", "tp hcm": "Hồ Chí Minh", "tphcm": "Hồ Chí Minh",
    "sai gon": "Hồ Chí Minh",
}

NUOC_NGOAI = {"nuoc ngoai", "nuoc ngoai (khac)", "ngoai nuoc"}
_TIEN_TO_TINH = re.compile(r"^(thanh pho|tinh|tp\.?|t\.)\s*", re.I)
_TIEN_TO_XA = re.compile(r"^(phuong|xa|dac khu|thi tran|p\.|x\.|tt\.|f\.)\s*", re.I)


def _s(v) -> str:
    return "" if v is None or (isinstance(v, float) and v != v) else " ".join(str(v).split())


def _loi(ten: str, mau=_TIEN_TO_TINH) -> str:
    """Tên lõi đã bỏ dấu, bỏ tiền tố, bỏ dấu câu: 'TP. Hồ Chí Minh' -> 'ho chi minh'."""
    f = DM.fold(ten).replace("-", " ").replace("–", " ")
    f = mau.sub("", f.strip())
    f = re.sub(r"['’`ʼ]", "", f)  # B'Lao / B’Lao / B''Lao' (danh mục) như nhau
    return " ".join(re.sub(r"[.,]", " ", f).split())


def _bang_tinh() -> dict[str, str]:
    d = DM.load()
    return {_loi(t): t for t in d["tinh"]}


def chuan_tinh(v) -> str:
    """Tên tỉnh/thành chuẩn (mới) hoặc "" nếu không nhận ra."""
    s = _s(v)
    if not s:
        return ""
    bang = _bang_tinh()
    if s in bang.values():
        return s
    loi = _loi(s)
    if loi in bang:
        return bang[loi]
    moi = TINH_CU_MOI.get(loi) or TINH_CU_MOI.get(loi.replace(" ", ""))
    return bang.get(_loi(moi), "") if moi else ""


def chuan_xa(tinh_chuan: str, v) -> str:
    """Tên phường/xã chuẩn (mới) trong tỉnh `tinh_chuan`, hoặc "" nếu không khớp chắc chắn."""
    s = _s(v)
    if not s or not tinh_chuan:
        return ""
    ds = DM.xa_of(tinh_chuan)
    if s in ds:
        return s
    f = re.sub(r"['’`ʼ]", "", DM.fold(s))
    dung = [x for x in ds if re.sub(r"['’`ʼ]", "", DM.fold(x)) == f]
    if len(dung) == 1:
        return dung[0]
    loi = _loi(s, _TIEN_TO_XA)
    if not loi or loi.isdigit():  # "Phường 14": phường cũ đánh số -> không đoán
        return ""
    loai = "phuong" if re.match(r"^(phuong|p\.|f\.)", f) else "xa" if re.match(r"^(xa|x\.)", f) \
        else ""
    ung = [x for x in ds if _loi(x, _TIEN_TO_XA) == loi]
    if loai and len(ung) > 1:
        ung = [x for x in ung if DM.fold(x).startswith(loai)] or ung
    return ung[0] if len(ung) == 1 else ""


def kiem_tra(items: list[dict], list_name: str) -> tuple[list[dict], dict]:
    """So các cặp (tỉnh, phường/xã) với danh mục mới.

    Trả về (thay: [{id, cot: {key: (cũ, mới)}}], khong_khop: {(cột, tỉnh chuẩn, xã gốc): số dòng}).
    Tỉnh không nhận ra cũng vào khong_khop (với xã = "")."""
    thay, khong = [], {}
    for r in items:
        doi = {}
        for ct, cx in CAP_COT.get(list_name, []):
            t0, x0 = _s(r.get(ct)), _s(r.get(cx))
            if (not t0 and not x0) or DM.fold(t0) in NUOC_NGOAI:  # nước ngoài: giữ nguyên
                continue
            t1 = chuan_tinh(t0) if t0 else ""
            if t0 and not t1:
                k = (ct, t0, "")
                khong[k] = khong.get(k, 0) + 1
                continue
            if t1 and t1 != r.get(ct):
                doi[ct] = (r.get(ct) or "", t1)
            if x0:
                x1 = chuan_xa(t1, x0)
                if x1 and x1 != r.get(cx):
                    doi[cx] = (r.get(cx) or "", x1)
                elif not x1:
                    k = (cx, t1, x0)
                    khong[k] = khong.get(k, 0) + 1
        if doi:
            thay.append({"id": str(r.get("id")), "ten": _s(r.get("HoTen") or r.get("HoTenHS")),
                         "cot": doi})
    return thay, khong


def ap_dung_anh_xa(items: list[dict], list_name: str, anh_xa: dict) -> list[dict]:
    """Ánh xạ người dùng chọn: {(cột xã, tỉnh chuẩn, xã gốc): xã mới} -> danh sách thay đổi
    (kèm chuẩn hóa tỉnh của cặp đó)."""
    thay = []
    for r in items:
        doi = {}
        for ct, cx in CAP_COT.get(list_name, []):
            t1 = chuan_tinh(r.get(ct))
            moi = anh_xa.get((cx, t1, _s(r.get(cx))))
            if moi:
                doi[cx] = (r.get(cx) or "", moi)
                if t1 != r.get(ct):
                    doi[ct] = (r.get(ct) or "", t1)
        if doi:
            thay.append({"id": str(r.get("id")), "ten": _s(r.get("HoTen") or r.get("HoTenHS")),
                         "cot": doi})
    return thay


def ghi(storage, list_name: str, thay: list[dict], progress=None) -> int:
    from concurrent.futures import ThreadPoolExecutor

    done = 0
    with ThreadPoolExecutor(max_workers=4) as pool:
        for _ in pool.map(lambda t: storage.update_item(
                list_name, t["id"], {k: v[1] for k, v in t["cot"].items()}), thay):
            done += 1
            if progress:
                progress(done, len(thay))
    return len(thay)


def chuan_bang(df, list_name: str = "Data_NhapHoc"):
    """Chuẩn hóa tại chỗ các cặp cột tỉnh / phường-xã của một DataFrame (vd file VEMIS vừa đọc);
    ô không khớp chắc chắn giữ nguyên."""
    for ct, cx in CAP_COT.get(list_name, []):
        if ct not in df or cx not in df:
            continue
        t1 = [chuan_tinh(t) or t for t in df[ct]]
        df[cx] = [chuan_xa(t, x) or x for t, x in zip(t1, df[cx])]
        df[ct] = t1
    return df
