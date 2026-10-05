"""Địa bàn 3 cấp cho báo cáo: Tỉnh/Thành (mới) → Quận/Huyện (cũ) → Phường/Xã (mới).

Sau sáp nhập 2025 không còn cấp quận/huyện, nhưng nhà trường vẫn quen theo dõi theo quận
cũ (Tân Phú, Tân Bình, Bình Tân…). Quận/huyện cũ được lấy theo thứ tự:

1. Data tuyển sinh: cột "Địa chỉ cũ (trước sáp nhập)" của trường cũ, vd
   "Quận Tân Phú, Thành phố Hồ Chí Minh".
2. Phường/xã mới → quận/huyện cũ, học từ chính dữ liệu tuyển sinh: các liên hệ có cả phường/xã
   mới và địa chỉ cũ cho biết phường mới thuộc quận cũ nào (lấy quận chiếm đa số).

Không suy ra được thì để "Chưa rõ quận/huyện".
"""
from __future__ import annotations

import re

import pandas as pd

CHUA_RO = "Chưa rõ"
CHUA_RO_QUAN = "Chưa rõ quận/huyện"
CAP = ("Tỉnh/Thành", "Quận/Huyện (cũ)", "Phường/Xã (mới)")
_DON_VI = re.compile(r"^(Quận|Huyện|Thị xã|Thành phố)\s+(.+)$", re.I)


def _s(v) -> str:
    return "" if v is None or (isinstance(v, float) and v != v) else str(v).strip()


def quan_cu(dia_chi_cu) -> str:
    """'Quận Tân Phú, Thành phố Hồ Chí Minh' → 'Quận Tân Phú'; chỉ có tỉnh → ''.

    'Thành phố Thủ Đức, Thành phố Hồ Chí Minh' → 'Thành phố Thủ Đức' (cấp huyện);
    'Thành phố Hồ Chí Minh' (một phần) → '' vì đó là cấp tỉnh.
    """
    phan = [p.strip() for p in _s(dia_chi_cu).split(",") if p.strip()]
    if len(phan) < 2:
        return ""
    m = _DON_VI.match(phan[-2])
    if not m:
        return ""
    return f"{m.group(1)[0].upper()}{m.group(1)[1:].lower()} {m.group(2).strip()}"


def bang_phuong_quan(ts: pd.DataFrame, ty_le: float = 0.6) -> dict[tuple[str, str], str]:
    """(Tỉnh mới, Phường/Xã mới) → quận/huyện cũ, học từ Data tuyển sinh (mọi năm)."""
    if ts is None or ts.empty or "TruongCu_DiaChiCu" not in ts:
        return {}
    d = pd.DataFrame({"t": ts["TruongCu_Tinh"].map(_s), "x": ts["TruongCu_PhuongXa"].map(_s),
                      "q": ts["TruongCu_DiaChiCu"].map(quan_cu)})
    d = d[(d["t"] != "") & (d["x"] != "") & (d["q"] != "")]
    if d.empty:
        return {}
    dem = d.groupby(["t", "x", "q"]).size()
    out = {}
    for (t, x), g in dem.groupby(level=[0, 1]):
        top = g.idxmax()[2]
        if g.max() / g.sum() >= ty_le:
            out[(t, x)] = top
    return out


def _gan(tinh: pd.Series, xa: pd.Series, quan: pd.Series | None,
         bang: dict[tuple[str, str], str]) -> pd.DataFrame:
    tinh, xa = tinh.map(_s), xa.map(_s)
    q = quan.map(_s) if quan is not None else pd.Series("", index=tinh.index)
    tu_bang = [bang.get((t, x), "") for t, x in zip(tinh, xa)]
    q = q.where(q != "", pd.Series(tu_bang, index=tinh.index))
    return pd.DataFrame({
        CAP[0]: tinh.replace("", CHUA_RO),
        CAP[1]: q.replace("", CHUA_RO_QUAN),
        CAP[2]: xa.replace("", CHUA_RO),
    }, index=tinh.index)


def dia_ban_ts(ts: pd.DataFrame, bang: dict | None = None) -> pd.DataFrame:
    """3 cấp địa bàn của TRƯỜNG CŨ cho từng liên hệ tuyển sinh."""
    bang = bang_phuong_quan(ts) if bang is None else bang
    return _gan(ts["TruongCu_Tinh"], ts["TruongCu_PhuongXa"],
                ts["TruongCu_DiaChiCu"].map(quan_cu) if "TruongCu_DiaChiCu" in ts else None,
                bang)


def dia_ban_nh(nh: pd.DataFrame, bang: dict | None = None) -> pd.DataFrame:
    """3 cấp địa bàn CHỖ Ở HIỆN NAY của học sinh nhập học (thiếu thì lấy hộ khẩu)."""
    bang = bang or {}

    def col(a, b):
        x = nh[a].map(_s) if a in nh else pd.Series("", index=nh.index)
        y = nh[b].map(_s) if b in nh else pd.Series("", index=nh.index)
        return x.where(x != "", y)

    tinh = col("ChoO_Tinh", "HK_Tinh")
    co_cho_o = nh["ChoO_Tinh"].map(_s) != "" if "ChoO_Tinh" in nh else tinh == ""
    xa = col("ChoO_Xa", "HK_Xa").where(co_cho_o | (tinh != ""), "")
    return _gan(tinh, xa, None, bang)


def nhan(df: pd.DataFrame, cap: str) -> pd.Series:
    """Nhãn hiển thị cho cấp đã chọn (kèm cấp trên để không trùng tên)."""
    if cap == CAP[0]:
        return df[CAP[0]]
    if cap == CAP[1]:
        return df[CAP[1]] + " · " + df[CAP[0]].str.replace("Thành phố ", "TP. ", regex=False)
    return df[CAP[2]] + " · " + df[CAP[1]]
