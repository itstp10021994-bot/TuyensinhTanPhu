"""Dự báo tuyển sinh mùa tới từ dữ liệu của app (Data tuyển sinh các năm).

Mùa tuyển sinh của năm học "Y-(Y+1)": từ 01/09/(Y-1) đến 31/08/Y. Mùa đang diễn ra = mùa có ngày
kết thúc gần nhất chưa qua.

Cách tính (minh bạch, không dùng mô hình phức tạp):
- Liên hệ cả mùa = liên hệ đến hôm nay × (cả mùa năm trước ÷ cùng kỳ năm trước) — tức giả định
  phần còn lại của mùa diễn ra giống các năm trước. Có nhiều năm thì lấy trung bình, khoảng dự
  báo là thấp nhất – cao nhất giữa các năm.
- Chưa có liên hệ nào (đầu mùa): lấy tổng các năm trước × tốc độ tăng giữa hai năm gần nhất.
- Chưa có năm trước: cộng thêm theo tốc độ trung bình 8 tuần gần nhất.
- Nhập học = liên hệ dự báo × tỷ lệ liên hệ → nhập học của năm trước (chưa có thì năm nay).
"""
from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date, timedelta

import pandas as pd

MUA_TUAN = 53


def nam_bat_dau(nam_hoc: str) -> int | None:
    try:
        return int(str(nam_hoc)[:4])
    except ValueError:
        return None


def mua(nam_hoc: str) -> tuple[date, date]:
    """(ngày bắt đầu, ngày kết thúc) mùa tuyển sinh của năm học."""
    y = nam_bat_dau(nam_hoc) or date.today().year
    return date(y - 1, 9, 1), date(y, 8, 31)


def nam_hoc_dang_tuyen(hom_nay: date) -> str:
    """Năm học đang tuyển: tháng 9 trở đi là năm học của năm sau."""
    y = hom_nay.year + (1 if hom_nay.month >= 9 else 0)
    return f"{y}-{y + 1}"


@dataclass
class KetQua:
    nam_hoc: str
    nam_truoc: str
    hom_nay: date
    bat_dau: date
    ket_thuc: date
    lh_den_nay: int = 0
    lh_cung_ky: int | None = None        # năm trước, cùng ngày trong mùa
    lh_nam_truoc: int | None = None      # năm trước, cả mùa
    du_bao_lh: int = 0
    du_bao_lh_thap: int = 0
    du_bao_lh_cao: int = 0
    ty_le_nh: float | None = None        # liên hệ -> nhập học
    du_bao_nh: int = 0
    nh_den_nay: int = 0
    bon_tuan_toi: int = 0
    cao_diem: list[str] = field(default_factory=list)
    cach_tinh: str = ""
    duong: pd.DataFrame = field(default_factory=pd.DataFrame)   # Tuần, Chuỗi, Số liên hệ (cộng dồn)
    theo_khoi: pd.DataFrame = field(default_factory=pd.DataFrame)
    so_nam_du_lieu: int = 0


def _ngay(s: pd.Series) -> pd.Series:
    return pd.to_datetime(s, errors="coerce")


def _lech(ts: pd.DataFrame, nam_hoc: str) -> pd.Series:
    """Số ngày từ đầu mùa của từng liên hệ thuộc năm học (bỏ ngày ngoài mùa / trống)."""
    bd, _ = mua(nam_hoc)
    x = ts[ts["NamHoc"] == nam_hoc]
    d = (_ngay(x["NgayLienHe"]) - pd.Timestamp(bd)).dt.days
    return d[(d >= 0) & (d <= 366)]


def _ty_le_nh(ts: pd.DataFrame, nam_hoc: str) -> float | None:
    x = ts[ts["NamHoc"] == nam_hoc]
    return (x["TrangThai"] == "Nhập học").sum() / len(x) if len(x) else None


def du_bao(ts: pd.DataFrame, hom_nay: date | None = None, nam_hoc: str | None = None) -> KetQua:
    """`ts`: Data tuyển sinh mọi năm (cột NamHoc, NgayLienHe, TrangThai, Khoi)."""
    hom_nay = hom_nay or date.today()
    nam_hoc = nam_hoc or nam_hoc_dang_tuyen(hom_nay)
    y = nam_bat_dau(nam_hoc)
    bd, kt = mua(nam_hoc)
    t = max(0, min((hom_nay - bd).days, 366))
    con_lai = max(0, (kt - hom_nay).days)
    kq = KetQua(nam_hoc, f"{y - 1}-{y}", hom_nay, bd, kt)

    cur = _lech(ts, nam_hoc)
    kq.lh_den_nay = int((cur <= t).sum())
    kq.nh_den_nay = int(((ts["NamHoc"] == nam_hoc) & (ts["TrangThai"] == "Nhập học")).sum())
    # các năm trước có dữ liệu (tối đa 3)
    truoc = []
    for k in range(1, 4):
        nh_k = f"{y - k}-{y - k + 1}"
        lk = _lech(ts, nh_k)
        if len(lk):
            truoc.append((nh_k, lk))
    kq.so_nam_du_lieu = len(truoc) + (1 if len(cur) else 0)
    if truoc and truoc[0][0] == kq.nam_truoc:
        kq.lh_nam_truoc = len(truoc[0][1])
        kq.lh_cung_ky = int((truoc[0][1] <= t).sum())

    # --- liên hệ cả mùa
    uoc = []
    if truoc and kq.lh_den_nay:
        for _, lk in truoc:
            ck = int((lk <= t).sum())
            if ck:
                uoc.append(kq.lh_den_nay * len(lk) / ck)
        kq.cach_tinh = ("Liên hệ đến nay × (cả mùa ÷ cùng kỳ) của "
                        + ", ".join(n for n, _ in truoc) + " — phần còn lại của mùa giả định "
                        "diễn ra như các năm trước.")
    if not uoc and truoc:
        tong = [len(lk) for _, lk in truoc]
        tang = tong[0] / tong[1] if len(tong) > 1 and tong[1] else 1.0
        uoc = [max(kq.lh_den_nay, tong[0] * tang)]
        if len(tong) > 1:
            uoc += [max(kq.lh_den_nay, tong[0]), max(kq.lh_den_nay, tong[0] * tang * tang)]
        kq.cach_tinh = (f"Mùa {nam_hoc} chưa đủ liên hệ để so cùng kỳ: lấy tổng mùa "
                        f"{truoc[0][0]} ({tong[0]})" + (f" × tốc độ tăng {tang:.0%} giữa hai năm "
                                                       "gần nhất." if len(tong) > 1 else "."))
    if not uoc:  # chỉ có năm nay: theo tốc độ 8 tuần gần nhất
        gan = int(((cur > t - 56) & (cur <= t)).sum())
        uoc = [kq.lh_den_nay + gan / 8 * con_lai / 7]
        kq.cach_tinh = ("Chưa có dữ liệu năm trước: liên hệ đến nay + tốc độ trung bình 8 tuần "
                        f"gần nhất ({gan / 8:.1f}/tuần) × số tuần còn lại của mùa.")
    kq.du_bao_lh = round(sum(uoc) / len(uoc))
    kq.du_bao_lh_thap = round(min(uoc))
    kq.du_bao_lh_cao = round(max(uoc))

    # --- nhập học
    for nh_k in (kq.nam_truoc, nam_hoc):
        r = _ty_le_nh(ts, nh_k)
        if r:
            kq.ty_le_nh = r
            break
    kq.du_bao_nh = max(kq.nh_den_nay, round(kq.du_bao_lh * (kq.ty_le_nh or 0)))

    # --- đường cộng dồn theo tuần: năm nay (thực tế), dự báo (theo hình dạng năm trước), năm trước
    tuan = [bd + timedelta(weeks=i) for i in range(MUA_TUAN)]
    mau = truoc[0][1] if truoc else None
    rows = []
    for d in tuan:
        ngay = (d - bd).days
        if ngay <= t:
            rows.append({"Tuần": d, "Chuỗi": f"Mùa {nam_hoc} (thực tế)",
                         "Liên hệ cộng dồn": int((cur <= ngay).sum())})
        if mau is not None:
            rows.append({"Tuần": d, "Chuỗi": f"Mùa {truoc[0][0]}",
                         "Liên hệ cộng dồn": int((mau <= ngay).sum())})
    du = _duong_du_bao(kq, tuan, t, mau)
    rows += du
    kq.duong = pd.DataFrame(rows, columns=["Tuần", "Chuỗi", "Liên hệ cộng dồn"])
    if du:
        sau4 = next((r["Liên hệ cộng dồn"] for r in du
                     if (r["Tuần"] - bd).days >= t + 28), du[-1]["Liên hệ cộng dồn"])
        kq.bon_tuan_toi = max(0, round(sau4 - kq.lh_den_nay))

    # --- cao điểm (tháng nhiều liên hệ nhất của các năm trước / năm nay)
    tat_ca = pd.concat([lk for _, lk in truoc] + [cur]) if truoc or len(cur) else pd.Series([])
    if len(tat_ca):
        thang = pd.Series([(bd + timedelta(days=int(v))).month for v in tat_ca]).value_counts()
        kq.cao_diem = [f"tháng {m}" for m in thang.head(3).index]

    # --- theo khối: tỷ trọng liên hệ (năm nay + năm trước) × dự báo
    nam = [nam_hoc] + [n for n, _ in truoc[:1]]
    x = ts[ts["NamHoc"].isin(nam)]
    if len(x):
        khoi = x["Khoi"].fillna("").replace("", "Chưa rõ")
        ty = khoi.value_counts(normalize=True)
        y_nay = ts[(ts["NamHoc"] == nam_hoc)
                   & (_ngay(ts["NgayLienHe"]) <= pd.Timestamp(hom_nay))]
        den = y_nay["Khoi"].fillna("").replace("", "Chưa rõ").value_counts()
        tk = pd.DataFrame({"Khối": ty.index, "Tỷ trọng": ty.values})
        tk["Liên hệ đến nay"] = [int(den.get(k, 0)) for k in tk["Khối"]]
        tk["Dự báo liên hệ"] = [max(int(den.get(k, 0)), round(kq.du_bao_lh * v))
                                for k, v in zip(tk["Khối"], tk["Tỷ trọng"])]
        tk["Dự báo nhập học"] = [round(v * (kq.ty_le_nh or 0)) for v in tk["Dự báo liên hệ"]]
        tk["_k"] = [int(k) if str(k).isdigit() else 99 for k in tk["Khối"]]
        kq.theo_khoi = tk.sort_values("_k").drop(columns=["_k"]).reset_index(drop=True)
    return kq


def _duong_du_bao(kq: KetQua, tuan: list[date], t: int, mau: pd.Series | None) -> list[dict]:
    """Từ hôm nay đến cuối mùa: theo tỷ lệ cộng dồn của năm trước (không có thì đường thẳng)."""
    if kq.du_bao_lh <= kq.lh_den_nay and t >= 366:
        return []
    out = []
    tong_mau = len(mau) if mau is not None else 0
    for d in tuan:
        ngay = (d - kq.bat_dau).days
        if ngay < t:
            continue
        if tong_mau:
            phan = (mau <= ngay).sum() / tong_mau
            phan_nay = (mau <= t).sum() / tong_mau
            con = kq.du_bao_lh - kq.lh_den_nay
            gt = kq.lh_den_nay + (con * (phan - phan_nay) / (1 - phan_nay) if phan_nay < 1
                                  else con)
        else:
            con_ngay = max(1, 366 - t)
            gt = kq.lh_den_nay + (kq.du_bao_lh - kq.lh_den_nay) * min(1, (ngay - t) / con_ngay)
        out.append({"Tuần": d, "Chuỗi": f"Mùa {kq.nam_hoc} (dự báo)",
                    "Liên hệ cộng dồn": round(float(gt), 1)})
    return out
