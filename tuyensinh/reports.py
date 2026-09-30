"""Các mẫu báo cáo (tính toán thuần pandas — trang Báo cáo chỉ hiển thị và xuất Excel).

Mỗi báo cáo nhận `Ctx` (dữ liệu đã lọc) và trả về `Result`: bảng số liệu, chỉ số tóm tắt và
gợi ý biểu đồ. Thêm mẫu mới: viết hàm `_ten(ctx) -> Result` và đăng ký trong `REPORTS`.
"""
from __future__ import annotations

import io
from dataclasses import dataclass, field
from datetime import date, datetime
from typing import Callable

import pandas as pd

from . import services
from .schema import GIAY_TO_NHAP_HOC, KHOI, TRANG_THAI

G_TS, G_KT, G_NH = "Tuyển sinh", "Tài chính", "Nhập học"


@dataclass
class Ctx:
    ts: pd.DataFrame            # Data tuyển sinh của năm học (đã lọc khối / ngày)
    nh: pd.DataFrame            # Hồ sơ nhập học của năm học (đã lọc khối)
    ts_all: pd.DataFrame        # Data tuyển sinh mọi năm (so sánh năm học)
    nam_hoc: str
    params: dict = field(default_factory=dict)


@dataclass
class Result:
    table: pd.DataFrame
    kpis: list[tuple[str, object]] = field(default_factory=list)
    chart: dict | None = None     # {"kind": bar|hbar|stack|group|line, "x", "y", "color"...}
    note: str = ""
    sheets: dict[str, pd.DataFrame] | None = None  # xuất nhiều sheet (vd danh sách theo lớp)


@dataclass
class Report:
    id: str
    group: str
    title: str
    desc: str
    fn: Callable[[Ctx], Result]
    params: tuple = ()  # tham số riêng: "ky" (tuần/tháng), "top", "ngay"


# ------------------------------------------------------------------ tiện ích
def _pct(a, b) -> float:
    return round(100 * a / b, 1) if b else 0.0


def _khoi_order(values) -> list[str]:
    vals = [v for v in dict.fromkeys(list(values)) if v != ""]
    return sorted(vals, key=lambda s: (int(s.split("-")[0]) if str(s).split("-")[0].isdigit()
                                       else 99, str(s)))


def _blank(s: pd.Series, label: str = "Chưa rõ") -> pd.Series:
    return s.fillna("").astype(str).str.strip().replace("", label)


def _steps(df: pd.DataFrame, by: str) -> pd.DataFrame:
    """Số HS theo `by` × bước + tổng + tỷ lệ nộp hồ sơ / nhập học."""
    t = pd.crosstab(df[by], df["TrangThai"]).reindex(columns=list(TRANG_THAI), fill_value=0)
    t["Tổng"] = t.sum(axis=1)
    nop = t["Nộp hồ sơ"] + t["Nhập học"]
    t["Tỷ lệ nộp hồ sơ (%)"] = [_pct(a, b) for a, b in zip(nop, t["Tổng"])]
    t["Tỷ lệ nhập học (%)"] = [_pct(a, b) for a, b in zip(t["Nhập học"], t["Tổng"])]
    return t


def _total_row(t: pd.DataFrame, label_col: str, pct_cols=()) -> pd.DataFrame:
    tot = t.select_dtypes("number").sum()
    row = {c: tot.get(c, "") for c in t.columns}
    row[label_col] = "Tổng cộng"
    for c, (num, den) in dict(pct_cols).items():
        row[c] = _pct(tot[num], tot[den])
    return pd.concat([t, pd.DataFrame([row])], ignore_index=True)


def _long(t: pd.DataFrame, id_col: str, cols: list[str], var="Nhóm", val="Số HS"):
    return t[t[id_col] != "Tổng cộng"].melt(id_col, cols, var_name=var, value_name=val)


def _num(s: pd.Series) -> pd.Series:
    return pd.to_numeric(s, errors="coerce").fillna(0)


# ------------------------------------------------------------------ tuyển sinh
def ts_khoi(c: Ctx) -> Result:
    t = _steps(c.ts.assign(Khoi=_blank(c.ts["Khoi"])), "Khoi")
    t = t.reindex(_khoi_order(t.index.tolist()) + (["Chưa rõ"] if "Chưa rõ" in t.index else []))
    t = t.rename_axis("Khối").reset_index()
    t = _total_row(t, "Khối", {"Tỷ lệ nộp hồ sơ (%)": ("Nộp hồ sơ", "Tổng"),
                               "Tỷ lệ nhập học (%)": ("Nhập học", "Tổng")})
    tot = t.iloc[-1]
    return Result(t, [("Liên hệ", int(tot["Tổng"])), ("Nhập học", int(tot["Nhập học"])),
                      ("Tỷ lệ nhập học", f"{tot['Tỷ lệ nhập học (%)']}%"),
                      ("Rút hồ sơ", int(tot["Rút hồ sơ"]))],
                  {"kind": "stack", "data": _long(t, "Khối", list(TRANG_THAI), "Bước"),
                   "x": "Khối", "y": "Số HS", "color": "Bước"})


def ts_nguon(c: Ctx) -> Result:
    t = _steps(c.ts.assign(Nguon=_blank(c.ts["Nguon"])), "Nguon")
    t = t.sort_values("Tổng", ascending=False).rename_axis("Nguồn").reset_index()
    t = t[["Nguồn", "Tổng", "Nộp hồ sơ", "Nhập học", "Rút hồ sơ", "Tỷ lệ nộp hồ sơ (%)",
           "Tỷ lệ nhập học (%)"]].rename(columns={"Tổng": "Liên hệ"})
    best = t[t["Liên hệ"] >= 10].sort_values("Tỷ lệ nhập học (%)", ascending=False)
    t = _total_row(t, "Nguồn", {"Tỷ lệ nộp hồ sơ (%)": ("Nộp hồ sơ", "Liên hệ"),
                                "Tỷ lệ nhập học (%)": ("Nhập học", "Liên hệ")})
    return Result(t, [("Số nguồn", len(t) - 1),
                      ("Nguồn nhiều liên hệ nhất", t.iloc[0]["Nguồn"] if len(t) > 1 else "—"),
                      ("Tỷ lệ nhập học cao nhất (≥10 liên hệ)",
                       f"{best.iloc[0]['Nguồn']} · {best.iloc[0]['Tỷ lệ nhập học (%)']}%"
                       if len(best) else "—")],
                  {"kind": "group", "data": _long(t, "Nguồn", ["Liên hệ", "Nhập học"], "Chỉ số"),
                   "x": "Nguồn", "y": "Số HS", "color": "Chỉ số", "horizontal": True})


def ts_thoigian(c: Ctx) -> Result:
    ky = c.params.get("ky", "Tháng")
    d = pd.to_datetime(c.ts["NgayLienHe"], errors="coerce")
    df = c.ts.assign(_d=d).dropna(subset=["_d"])
    per = df["_d"].dt.to_period("M" if ky == "Tháng" else "W").dt.start_time
    g = df.assign(Ky=per).groupby("Ky").agg(
        **{"Liên hệ mới": ("id", "count"),
           "Đã nộp hồ sơ": ("TrangThai", lambda s: int(s.isin(["Nộp hồ sơ", "Nhập học"]).sum())),
           "Đã nhập học": ("TrangThai", lambda s: int((s == "Nhập học").sum()))}).reset_index()
    g["Lũy kế liên hệ"] = g["Liên hệ mới"].cumsum()
    fmt = "%m/%Y" if ky == "Tháng" else "%d/%m/%Y"
    t = g.assign(**{ky: g["Ky"].dt.strftime(fmt)}).drop(columns="Ky")
    t = t[[ky, "Liên hệ mới", "Đã nộp hồ sơ", "Đã nhập học", "Lũy kế liên hệ"]]
    peak = g.loc[g["Liên hệ mới"].idxmax()] if len(g) else None
    return Result(t, [(f"Số {ky.lower()}", len(g)),
                      (f"{ky} nhiều liên hệ nhất",
                       f"{peak['Ky'].strftime(fmt)} · {peak['Liên hệ mới']}" if peak is not None
                       else "—"),
                      (f"Trung bình / {ky.lower()}",
                       round(g["Liên hệ mới"].mean(), 1) if len(g) else 0)],
                  {"kind": "line", "data": g.melt("Ky", ["Liên hệ mới", "Đã nhập học"],
                                                  var_name="Chỉ số", value_name="Số HS"),
                   "x": "Ky", "y": "Số HS", "color": "Chỉ số", "fmt": fmt},
                  note="Tính theo Ngày liên hệ; cột Đã nộp / Đã nhập học là trạng thái hiện tại "
                       "của các liên hệ trong kỳ đó.")


def ts_tuvan(c: Ctx) -> Result:
    t = _steps(c.ts.assign(Nguoi=_blank(c.ts["NguoiNhanHoSo"], "Chưa phân công")), "Nguoi")
    t = t.sort_values("Tổng", ascending=False).rename_axis("Người nhận hồ sơ").reset_index()
    t = t[["Người nhận hồ sơ", "Tổng", "Tư vấn", "Nộp hồ sơ", "Nhập học", "Rút hồ sơ",
           "Tỷ lệ nhập học (%)"]].rename(columns={"Tổng": "Số HS phụ trách"})
    t = _total_row(t, "Người nhận hồ sơ", {"Tỷ lệ nhập học (%)": ("Nhập học", "Số HS phụ trách")})
    return Result(t, [("Số người phụ trách", len(t) - 1)],
                  {"kind": "stack", "data": _long(t, "Người nhận hồ sơ",
                                                  list(TRANG_THAI), "Bước"),
                   "x": "Người nhận hồ sơ", "y": "Số HS", "color": "Bước", "horizontal": True})


def ts_tinhtrang(c: Ctx) -> Result:
    df = c.ts.assign(TT=_blank(c.ts["TinhTrang"]), Khoi=_blank(c.ts["Khoi"]))
    t = pd.crosstab(df["TT"], df["Khoi"])
    t = t[_khoi_order(t.columns) + (["Chưa rõ"] if "Chưa rõ" in t.columns else [])]
    t["Tổng"] = t.sum(axis=1)
    t = t.sort_values("Tổng", ascending=False).rename_axis("Tình trạng tư vấn").reset_index()
    t.columns.name = None
    t = _total_row(t, "Tình trạng tư vấn")
    return Result(t, [],
                  {"kind": "hbar", "data": t[t["Tình trạng tư vấn"] != "Tổng cộng"],
                   "x": "Tình trạng tư vấn", "y": "Tổng"})


def ts_truongcu(c: Ctx) -> Result:
    top = int(c.params.get("top", 30))
    df = c.ts[c.ts["TruongCu"].str.strip() != ""]
    g = df.groupby(["TruongCu", "TruongCu_Tinh"]).agg(
        **{"Liên hệ": ("id", "count"),
           "Nhập học": ("TrangThai", lambda s: int((s == "Nhập học").sum()))}).reset_index()
    g["Tỷ lệ nhập học (%)"] = [_pct(a, b) for a, b in zip(g["Nhập học"], g["Liên hệ"])]
    g = g.sort_values(["Liên hệ", "Nhập học"], ascending=False).head(top)
    t = g.rename(columns={"TruongCu": "Trường cũ", "TruongCu_Tinh": "Tỉnh/Thành"})
    return Result(t, [("Số trường có học sinh liên hệ", df["TruongCu"].nunique()),
                      ("Liên hệ có ghi trường cũ", f"{len(df)}/{len(c.ts)}")],
                  {"kind": "group", "data": t.head(15).melt("Trường cũ", ["Liên hệ", "Nhập học"],
                                                             var_name="Chỉ số",
                                                             value_name="Số HS"),
                   "x": "Trường cũ", "y": "Số HS", "color": "Chỉ số", "horizontal": True})


def ts_diaban(c: Ctx) -> Result:
    df = c.ts.assign(Tinh=_blank(c.ts["TruongCu_Tinh"]), Xa=_blank(c.ts["TruongCu_PhuongXa"]))
    g = df.groupby(["Tinh", "Xa"]).agg(
        **{"Liên hệ": ("id", "count"),
           "Nhập học": ("TrangThai", lambda s: int((s == "Nhập học").sum()))}).reset_index()
    g = g.sort_values(["Liên hệ"], ascending=False)
    tinh = g.groupby("Tinh")[["Liên hệ", "Nhập học"]].sum().sort_values("Liên hệ",
                                                                        ascending=False)
    t = g.rename(columns={"Tinh": "Tỉnh/Thành (trường cũ)", "Xa": "Phường/Xã"})
    tinh_t = tinh.rename_axis("Tỉnh/Thành").reset_index()
    return Result(t, [("Số tỉnh/thành", len(tinh)), ("Số phường/xã", len(g))],
                  {"kind": "group", "data": tinh_t.head(12).melt(
                      "Tỉnh/Thành", ["Liên hệ", "Nhập học"], var_name="Chỉ số",
                      value_name="Số HS"),
                   "x": "Tỉnh/Thành", "y": "Số HS", "color": "Chỉ số", "horizontal": True},
                  sheets={"Theo_tinh": tinh_t, "Theo_phuong_xa": t})


def ts_chedo(c: Ctx) -> Result:
    df = c.ts[c.ts["TrangThai"] == "Nhập học"]
    df = df.assign(Khoi=_blank(df["Khoi"]), CheDo=_blank(df["CheDo"]),
                   PhanHe=_blank(df["PhanHe"], "Thường"))
    t = pd.crosstab(df["Khoi"], [df["CheDo"]])
    t2 = pd.crosstab(df["Khoi"], df["PhanHe"])
    t = t.join(t2, rsuffix=" (phân hệ)")
    t["Tổng"] = df.groupby("Khoi").size() if len(df) else 0
    t = t.reindex(_khoi_order(t.index)).rename_axis("Khối").reset_index()
    t.columns.name = None
    t = _total_row(t.fillna(0), "Khối")
    long = df.groupby(["Khoi", "CheDo"]).size().reset_index(name="Số HS")
    return Result(t, [("Học sinh nhập học", len(df)),
                      ("Nội trú", int((df["CheDo"] == "Nội trú").sum())),
                      ("Bán trú", int((df["CheDo"] == "Bán trú").sum()))],
                  {"kind": "stack_cat", "data": long.rename(columns={"Khoi": "Khối",
                                                                    "CheDo": "Chế độ"}),
                   "x": "Khối", "y": "Số HS", "color": "Chế độ"},
                  note="Chỉ tính học sinh ở bước Nhập học.")


def ts_quahan(c: Ctx) -> Result:
    ngay = int(c.params.get("ngay", 14))
    d = pd.to_datetime(c.ts["NgayLienHe"], errors="coerce")
    days = (pd.Timestamp(date.today()) - d).dt.days
    df = c.ts.assign(SoNgay=days)
    df = df[(df["TrangThai"] == "Tư vấn") & (df["SoNgay"] > ngay)].sort_values("SoNgay",
                                                                               ascending=False)
    t = df[["HoTenHS", "Khoi", "SDT", "NgayLienHe", "SoNgay", "TinhTrang", "NguoiNhanHoSo",
            "Nguon", "GhiChu"]].rename(columns={
        "HoTenHS": "Học sinh", "Khoi": "Khối", "SDT": "SĐT", "NgayLienHe": "Ngày liên hệ",
        "SoNgay": "Số ngày chưa chuyển bước", "TinhTrang": "Tình trạng tư vấn",
        "NguoiNhanHoSo": "Người phụ trách", "Nguon": "Nguồn", "GhiChu": "Nội dung đã trao đổi"})
    by = _blank(df["NguoiNhanHoSo"], "Chưa phân công").value_counts().rename_axis(
        "Người phụ trách").reset_index(name="Số HS")
    return Result(t, [("Liên hệ quá hạn", len(t)),
                      ("Quá 30 ngày", int((df["SoNgay"] > 30).sum()))],
                  {"kind": "hbar", "data": by, "x": "Người phụ trách", "y": "Số HS"},
                  note=f"Học sinh còn ở bước Tư vấn hơn {ngay} ngày kể từ ngày liên hệ.")


def ts_rut(c: Ctx) -> Result:
    df = c.ts[c.ts["TrangThai"] == "Rút hồ sơ"]
    t = df[["HoTenHS", "Khoi", "SDT", "NgayLienHe", "GiuCho", "SoTienXacNhan", "NguoiNhanHoSo",
            "GhiChu"]].rename(columns={
        "HoTenHS": "Học sinh", "Khoi": "Khối", "SDT": "SĐT", "NgayLienHe": "Ngày liên hệ",
        "GiuCho": "Giữ chỗ", "SoTienXacNhan": "Tiền giữ chỗ", "NguoiNhanHoSo": "Người phụ trách",
        "GhiChu": "Lý do / nội dung trao đổi"})
    by = _blank(df["Khoi"]).value_counts().rename_axis("Khối").reset_index(name="Số HS")
    return Result(t, [("Rút hồ sơ", len(df)), ("Tỷ lệ trên liên hệ", f"{_pct(len(df), len(c.ts))}%"),
                      ("Đã giữ chỗ trước khi rút",
                       int(df["GiuCho"].isin(["Đã giữ chỗ", "Hủy giữ chỗ", "Đã hoàn phí"]).sum()))],
                  {"kind": "bar", "data": by, "x": "Khối", "y": "Số HS"})


def ts_sosanh(c: Ctx) -> Result:
    df = c.ts_all.assign(NamHoc=_blank(c.ts_all["NamHoc"]))
    t = _steps(df, "NamHoc").sort_index().rename_axis("Năm học").reset_index()
    t = t[["Năm học", "Tổng", "Tư vấn", "Nộp hồ sơ", "Nhập học", "Rút hồ sơ",
           "Tỷ lệ nộp hồ sơ (%)", "Tỷ lệ nhập học (%)"]].rename(columns={"Tổng": "Liên hệ"})
    return Result(t, [("Số năm học", len(t))],
                  {"kind": "group", "data": t.melt("Năm học", ["Liên hệ", "Nhập học"],
                                                   var_name="Chỉ số", value_name="Số HS"),
                   "x": "Năm học", "y": "Số HS", "color": "Chỉ số"},
                  note="So sánh mọi năm học (không áp dụng bộ lọc năm học / ngày).")


# ------------------------------------------------------------------ tài chính
def kt_giucho(c: Ctx) -> Result:
    df = c.ts.assign(Khoi=_blank(c.ts["Khoi"]), Giu=_blank(c.ts["GiuCho"], "Chưa giữ chỗ"),
                     Tien=_num(c.ts["SoTienXacNhan"]))
    t = pd.crosstab(df["Khoi"], df["Giu"])
    t["Tiền đã xác nhận (đ)"] = df.groupby("Khoi")["Tien"].sum()
    t = t.reindex(_khoi_order(t.index)).fillna(0).rename_axis("Khối").reset_index()
    t.columns.name = None
    t = _total_row(t, "Khối")
    tien = df["Tien"].sum()
    return Result(t, [("Đã giữ chỗ", int((df["Giu"] == "Đã giữ chỗ").sum())),
                      ("Tổng tiền giữ chỗ", tien),
                      ("Hủy / hoàn phí", int(df["Giu"].isin(["Hủy giữ chỗ", "Đã hoàn phí"]).sum()))],
                  {"kind": "stack_cat", "data": df[df["Giu"] != "Chưa giữ chỗ"].groupby(
                      ["Khoi", "Giu"]).size().reset_index(name="Số HS").rename(
                      columns={"Khoi": "Khối", "Giu": "Giữ chỗ"}),
                   "x": "Khối", "y": "Số HS", "color": "Giữ chỗ"},
                  note="Theo Data tuyển sinh (kế toán xác nhận giữ chỗ).")


def kt_hocphi(c: Ctx) -> Result:
    df = c.nh.assign(Khoi=_blank(c.nh["Khoi"]), Phai=_num(c.nh["SoTienThanhToan"]),
                     Thu=_num(c.nh["TongDaThu"]), Con=_num(c.nh["SoTienConLai"]),
                     Giu=_num(c.nh["SoTienXacNhan"]))
    g = df.groupby("Khoi").agg(**{
        "Số HS": ("id", "count"),
        "HS đã ghi học phí": ("Phai", lambda s: int((s > 0).sum())),
        "Tiền giữ chỗ (đ)": ("Giu", "sum"), "PHHS thanh toán (đ)": ("Phai", "sum"),
        "Đã thu (đ)": ("Thu", "sum"), "Còn lại (đ)": ("Con", "sum"),
        "HS còn nợ": ("Con", lambda s: int((s > 0).sum()))})
    t = g.reindex(_khoi_order(g.index)).rename_axis("Khối").reset_index()
    t = _total_row(t, "Khối")
    tot = t.iloc[-1]
    return Result(t, [("PHHS thanh toán", tot["PHHS thanh toán (đ)"]),
                      ("Còn lại", tot["Còn lại (đ)"]), ("HS còn nợ", int(tot["HS còn nợ"]))],
                  {"kind": "bar", "data": t[t["Khối"] != "Tổng cộng"], "x": "Khối",
                   "y": "Còn lại (đ)", "money": True},
                  note="Theo Hồ sơ nhập học (nút Thanh toán học phí).")


def kt_congno(c: Ctx) -> Result:
    df = c.nh[_num(c.nh["SoTienConLai"]) > 0].sort_values(["Khoi", "LopHoc", "HoTen"])
    t = df[["HoTen", "Khoi", "LopHoc", "DienThoaiSLL", "SoTienThanhToan", "TongDaThu",
            "SoTienConLai", "NgayDongPhi", "KeToanXacNhan"]].rename(columns={
        "HoTen": "Học sinh", "Khoi": "Khối", "LopHoc": "Lớp", "DienThoaiSLL": "SĐT",
        "SoTienThanhToan": "PHHS thanh toán (đ)", "TongDaThu": "Đã thu (đ)",
        "SoTienConLai": "Còn lại (đ)", "NgayDongPhi": "Ngày đóng",
        "KeToanXacNhan": "Kế toán"})
    return Result(t, [("HS còn nợ", len(t)), ("Tổng còn lại", _num(df["SoTienConLai"]).sum())])


def kt_hoanphi(c: Ctx) -> Result:
    df = c.ts[c.ts["GiuCho"].isin(["Hủy giữ chỗ", "Đã hoàn phí"])].sort_values(["GiuCho",
                                                                               "HoTenHS"])
    t = df[["HoTenHS", "Khoi", "SDT", "GiuCho", "SoTienXacNhan", "TenChuTaiKhoan", "NganHang",
            "SoTaiKhoan", "NguoiXacNhan"]].rename(columns={
        "HoTenHS": "Học sinh", "Khoi": "Khối", "SDT": "SĐT", "GiuCho": "Tình trạng",
        "SoTienXacNhan": "Số tiền (đ)", "TenChuTaiKhoan": "Chủ tài khoản",
        "NganHang": "Ngân hàng", "SoTaiKhoan": "Số tài khoản", "NguoiXacNhan": "Người xác nhận"})
    cho = df[df["GiuCho"] == "Hủy giữ chỗ"]
    return Result(t, [("Chờ hoàn phí", len(cho)),
                      ("Tiền chờ hoàn", _num(cho["SoTienXacNhan"]).sum()),
                      ("Đã hoàn phí", int((df["GiuCho"] == "Đã hoàn phí").sum()))])


# ------------------------------------------------------------------ nhập học
def _nh_dang_hoc(c: Ctx) -> pd.DataFrame:
    return c.nh[~c.nh["TinhTrangHS"].isin(["Rút hồ sơ", "Không học tiếp"])]


def nh_siso(c: Ctx) -> Result:
    df = _nh_dang_hoc(c)
    df = df.assign(Lop=_blank(df["LopHoc"], "Chưa xếp lớp"), Khoi=_blank(df["Khoi"]))
    g = df.groupby(["Khoi", "Lop"]).agg(**{
        "Sĩ số": ("id", "count"),
        "Nam": ("GioiTinh", lambda s: int((s == "Nam").sum())),
        "Nữ": ("GioiTinh", lambda s: int((s == "Nữ").sum())),
        "Nội trú": ("NoiTruBanTru", lambda s: int(s.str.startswith("Nội trú").sum())),
        "Bán trú": ("NoiTruBanTru", lambda s: int(s.str.startswith("Bán trú").sum())),
        "IEP": ("PhanHe", lambda s: int((s == "IEP").sum())),
        "ESL": ("PhanHe", lambda s: int((s == "ESL").sum()))}).reset_index()
    order = {k: i for i, k in enumerate(_khoi_order(g["Khoi"]))}
    g = g.sort_values(["Khoi", "Lop"], key=lambda s: s.map(order) if s.name == "Khoi" else s)
    t = _total_row(g.rename(columns={"Khoi": "Khối", "Lop": "Lớp"}), "Khối")
    t.loc[t.index[-1], "Lớp"] = ""
    return Result(t, [("Học sinh đang theo học", len(df)),
                      ("Số lớp", df.loc[df["Lop"] != "Chưa xếp lớp", "Lop"].nunique()),
                      ("Chưa xếp lớp", int((df["Lop"] == "Chưa xếp lớp").sum()))],
                  {"kind": "bar", "data": g[g["Lop"] != "Chưa xếp lớp"].rename(
                      columns={"Lop": "Lớp"}), "x": "Lớp", "y": "Sĩ số"},
                  note="Không tính học sinh đã rút hồ sơ / không học tiếp.")


def nh_tinhtrang(c: Ctx) -> Result:
    df = c.nh.assign(Khoi=_blank(c.nh["Khoi"]), TT=_blank(c.nh["TinhTrangHS"]))
    t = pd.crosstab(df["Khoi"], df["TT"])
    t["Tổng"] = t.sum(axis=1)
    t = t.reindex(_khoi_order(t.index)).rename_axis("Khối").reset_index()
    t.columns.name = None
    t = _total_row(t, "Khối")
    return Result(t, [(k, int((df["TT"] == k).sum())) for k in
                      ("Đang nhập hồ sơ", "Đang đóng phí", "Đã đóng phí", "Rút hồ sơ")],
                  {"kind": "stack_cat", "data": df.groupby(["Khoi", "TT"]).size().reset_index(
                      name="Số HS").rename(columns={"Khoi": "Khối", "TT": "Tình trạng"}),
                   "x": "Khối", "y": "Số HS", "color": "Tình trạng"})


def nh_hoanthien(c: Ctx) -> Result:
    df = _nh_dang_hoc(c)
    miss = df.apply(services.missing_fields, axis=1)
    df = df.assign(Lop=_blank(df["LopHoc"], "Chưa xếp lớp"), _m=miss.map(len))
    g = df.groupby("Lop").agg(**{"Số HS": ("id", "count"),
                                 "Đủ thông tin": ("_m", lambda s: int((s == 0).sum())),
                                 "Còn thiếu": ("_m", lambda s: int((s > 0).sum()))})
    g["Tỷ lệ đủ (%)"] = [_pct(a, b) for a, b in zip(g["Đủ thông tin"], g["Số HS"])]
    t = g.rename_axis("Lớp").reset_index()
    t = _total_row(t, "Lớp", {"Tỷ lệ đủ (%)": ("Đủ thông tin", "Số HS")})
    thieu = pd.Series([services.NHAP_HOC_NHAN_NGAN[k] for m in miss for k in m])
    top = thieu.value_counts().rename_axis("Thông tin còn thiếu").reset_index(name="Số HS")
    return Result(t, [("Đủ thông tin VEMIS", int(t.iloc[-1]["Đủ thông tin"])),
                      ("Còn thiếu", int(t.iloc[-1]["Còn thiếu"]))],
                  {"kind": "hbar", "data": top, "x": "Thông tin còn thiếu", "y": "Số HS"},
                  sheets={"Theo_lop": t, "Thong_tin_thieu": top})


def nh_giayto(c: Ctx) -> Result:
    df = _nh_dang_hoc(c)
    parsed = df["HoSoDaNop"].map(lambda v: services.doc_ho_so(v)[1])
    rows = []
    for g in GIAY_TO_NHAP_HOC:
        goc = sum(1 for d in parsed if d.get(g) == "Bản gốc")
        sao = sum(1 for d in parsed if d.get(g) == "Bản sao")
        rows.append({"Giấy tờ": g, "Bản gốc": goc, "Bản sao": sao, "Đã nộp": goc + sao,
                     "Chưa nộp": len(df) - goc - sao,
                     "Tỷ lệ đã nộp (%)": _pct(goc + sao, len(df))})
    t = pd.DataFrame(rows)
    can = ["Phiếu đăng ký nhập học", "Thỏa thuận của Cha mẹ/Người giám hộ học sinh với nhà "
           "trường", "Giấy khai sinh"]
    thieu = df[parsed.map(lambda d: any(g not in d for g in can)).astype(bool)]
    ds = thieu.assign(Thieu=[", ".join(g for g in can if g not in d)
                             for d in parsed[thieu.index]])[
        ["HoTen", "Khoi", "LopHoc", "DienThoaiSLL", "Thieu"]].rename(columns={
            "HoTen": "Học sinh", "Khoi": "Khối", "LopHoc": "Lớp", "DienThoaiSLL": "SĐT",
            "Thieu": "Còn thiếu"})
    return Result(t, [("Chưa nộp hồ sơ nào", int((parsed.map(len) == 0).sum())),
                      ("Thiếu giấy tờ bắt buộc", len(ds))],
                  {"kind": "hbar", "data": t, "x": "Giấy tờ", "y": "Đã nộp"},
                  note="Giấy tờ bắt buộc: Phiếu đăng ký nhập học, Thỏa thuận với nhà trường, "
                       "Giấy khai sinh. Danh sách HS thiếu nằm ở sheet riêng khi xuất Excel.",
                  sheets={"Thong_ke_giay_to": t, "HS_thieu_giay_to": ds})


def nh_xe(c: Ctx) -> Result:
    df = _nh_dang_hoc(c)
    df = df[(df["DangKyXe"] != "") & df["NoiTruBanTru"].str.startswith("Nội trú")]
    g = df.groupby("DangKyXe").agg(**{"Số HS": ("id", "count"),
                                      "Số điểm đón": ("DiemDonTra", "nunique")})
    g = g.sort_values("Số HS", ascending=False).rename_axis("Tuyến xe").reset_index()
    ds = df.sort_values(["DangKyXe", "DiemDonTra", "HoTen"])[
        ["DangKyXe", "DiemDonTra", "HoTen", "Khoi", "LopHoc", "DienThoaiSLL", "TenCha",
         "TenMe"]].rename(columns={"DangKyXe": "Tuyến xe", "DiemDonTra": "Điểm đón trả",
                                   "HoTen": "Học sinh", "Khoi": "Khối", "LopHoc": "Lớp",
                                   "DienThoaiSLL": "SĐT", "TenCha": "Cha", "TenMe": "Mẹ"})
    sheets = {"Tong_hop": g, **{f"Xe_{x}"[:31]: d for x, d in ds.groupby("Tuyến xe")}}
    return Result(ds, [("HS đăng ký xe", len(df)), ("Số tuyến", len(g))],
                  {"kind": "hbar", "data": g, "x": "Tuyến xe", "y": "Số HS"},
                  note="Chỉ học sinh nội trú. Xuất Excel: mỗi tuyến một sheet (danh sách đón trả).",
                  sheets=sheets)


def nh_tohop(c: Ctx) -> Result:
    df = _nh_dang_hoc(c)
    df = df[df["Khoi"].isin(["10", "11", "12"])]
    t = pd.crosstab(_blank(df["LuaChon1"], "Chưa chọn"), df["Khoi"])
    t["Tổng"] = t.sum(axis=1)
    t = t.sort_values("Tổng", ascending=False).rename_axis("Tổ hợp (lựa chọn 1)").reset_index()
    t.columns.name = None
    t = _total_row(t, "Tổ hợp (lựa chọn 1)")
    return Result(t, [("HS khối 10–12", len(df)),
                      ("Chưa chọn tổ hợp", int((df["LuaChon1"] == "").sum()))],
                  {"kind": "hbar", "data": t[t.iloc[:, 0] != "Tổng cộng"],
                   "x": "Tổ hợp (lựa chọn 1)", "y": "Tổng"})


def nh_diaban(c: Ctx) -> Result:
    df = _nh_dang_hoc(c)
    df = df.assign(Tinh=_blank(df["ChoO_Tinh"]), Xa=_blank(df["ChoO_Xa"]))
    g = df.groupby(["Tinh", "Xa"]).size().reset_index(name="Số HS").sort_values(
        "Số HS", ascending=False)
    tinh = df["Tinh"].value_counts().rename_axis("Tỉnh/Thành").reset_index(name="Số HS")
    t = g.rename(columns={"Tinh": "Tỉnh/Thành (chỗ ở)", "Xa": "Phường/Xã"})
    return Result(t, [("Số tỉnh/thành", int((tinh["Tỉnh/Thành"] != "Chưa rõ").sum())),
                      ("Chưa có địa chỉ", int((df["Tinh"] == "Chưa rõ").sum()))],
                  {"kind": "hbar", "data": tinh.head(12), "x": "Tỉnh/Thành", "y": "Số HS"},
                  sheets={"Theo_tinh": tinh, "Theo_phuong_xa": t})


def nh_hocluc(c: Ctx) -> Result:
    df = _nh_dang_hoc(c)
    df = df.assign(Khoi=_blank(df["Khoi"]), HL=_blank(df["HocLuc1"]))
    t = pd.crosstab(df["HL"], df["Khoi"])
    t = t[_khoi_order(t.columns) + (["Chưa rõ"] if "Chưa rõ" in t.columns else [])]
    t["Tổng"] = t.sum(axis=1)
    t = t.sort_values("Tổng", ascending=False).rename_axis("Học lực (kết quả 1)").reset_index()
    t.columns.name = None
    diem = df.groupby("Khoi")[["Toan1", "Van1", "Anh1"]].mean().round(2)
    diem = diem.reindex(_khoi_order(diem.index)).rename_axis("Khối").reset_index().rename(
        columns={"Toan1": "Toán TB", "Van1": "Văn TB", "Anh1": "Anh TB"})
    return Result(t, [("Có điểm Toán", int(df["Toan1"].notna().sum()))],
                  {"kind": "hbar", "data": t, "x": "Học lực (kết quả 1)", "y": "Tổng"},
                  sheets={"Hoc_luc": t, "Diem_TB_theo_khoi": diem})


def nh_danhsach(c: Ctx) -> Result:
    df = _nh_dang_hoc(c)
    df = df.assign(Lop=_blank(df["LopHoc"], "Chưa xếp lớp")).sort_values(["Lop", "HoTen"])
    cols = {"HoTen": "Họ và tên", "NgaySinh": "Ngày sinh", "GioiTinh": "Giới tính",
            "KhoiPH": "Khối", "NoiTruBanTru": "Chế độ", "DienThoaiSLL": "SĐT liên lạc",
            "TenCha": "Cha", "TenMe": "Mẹ", "TruongCu": "Trường cũ"}
    df = df.assign(KhoiPH=[f"{k}-{p}" if k and p else k or p
                           for k, p in zip(df["Khoi"], df["PhanHe"])])
    sheets = {}
    for lop, d in df.groupby("Lop", sort=True):
        x = d[list(cols)].rename(columns=cols)
        x.insert(0, "STT", range(1, len(x) + 1))
        sheets[str(lop)[:31]] = x
    t = df[["Lop", *cols]].rename(columns={"Lop": "Lớp", **cols})
    return Result(t, [("Số lớp", len(sheets)), ("Học sinh", len(df))],
                  note="Xuất Excel: mỗi lớp một sheet, có STT — dùng in danh sách lớp.",
                  sheets=sheets)


REPORTS = [
    Report("ts_khoi", G_TS, "Phễu tuyển sinh theo khối",
           "Số học sinh ở từng bước (tư vấn → nộp hồ sơ → nhập học) theo khối, tỷ lệ chuyển đổi.",
           ts_khoi),
    Report("ts_nguon", G_TS, "Hiệu quả nguồn tuyển sinh",
           "Liên hệ, nộp hồ sơ, nhập học và tỷ lệ chuyển đổi của từng nguồn.", ts_nguon),
    Report("ts_thoigian", G_TS, "Liên hệ theo thời gian",
           "Số liên hệ mới theo tháng / tuần, lũy kế và số đã nhập học.", ts_thoigian, ("ky",)),
    Report("ts_tuvan", G_TS, "Kết quả theo người phụ trách",
           "Số học sinh mỗi người nhận hồ sơ phụ trách và kết quả chuyển đổi.", ts_tuvan),
    Report("ts_tinhtrang", G_TS, "Tình trạng tư vấn",
           "Phân bố tình trạng tư vấn (cần tư vấn thêm, đang cân nhắc…) theo khối.",
           ts_tinhtrang),
    Report("ts_truongcu", G_TS, "Trường cũ có nhiều học sinh",
           "Top trường cũ theo số liên hệ và số nhập học.", ts_truongcu, ("top",)),
    Report("ts_diaban", G_TS, "Địa bàn tuyển sinh",
           "Liên hệ và nhập học theo tỉnh/thành, phường/xã của trường cũ (địa giới mới).",
           ts_diaban),
    Report("ts_chedo", G_TS, "Chế độ & phân hệ nhập học",
           "Học sinh nhập học theo khối × nội trú/bán trú × IEP/ESL.", ts_chedo),
    Report("ts_quahan", G_TS, "Liên hệ tư vấn quá hạn",
           "Danh sách học sinh ở bước Tư vấn quá lâu chưa chuyển bước — cần gọi lại.",
           ts_quahan, ("ngay",)),
    Report("ts_rut", G_TS, "Danh sách rút hồ sơ", "Học sinh rút hồ sơ kèm lý do.", ts_rut),
    Report("ts_sosanh", G_TS, "So sánh các năm học",
           "Liên hệ, nộp hồ sơ, nhập học của các năm học.", ts_sosanh),
    Report("kt_giucho", G_KT, "Giữ chỗ theo khối",
           "Số học sinh đã giữ chỗ, hủy, hoàn phí và tổng tiền giữ chỗ theo khối.", kt_giucho),
    Report("kt_hocphi", G_KT, "Tổng hợp học phí theo khối",
           "Tiền PHHS thanh toán, đã thu, còn lại và số học sinh còn nợ theo khối.", kt_hocphi),
    Report("kt_congno", G_KT, "Danh sách còn nợ học phí",
           "Học sinh còn số tiền phải thu.", kt_congno),
    Report("kt_hoanphi", G_KT, "Danh sách hủy giữ chỗ / hoàn phí",
           "Học sinh hủy giữ chỗ chờ hoàn phí và đã hoàn phí, kèm tài khoản nhận.", kt_hoanphi),
    Report("nh_siso", G_NH, "Sĩ số theo lớp",
           "Sĩ số, nam/nữ, nội trú/bán trú, IEP/ESL của từng lớp.", nh_siso),
    Report("nh_tinhtrang", G_NH, "Tình trạng hồ sơ nhập học",
           "Đang nhập hồ sơ / đang đóng phí / đã đóng phí / rút… theo khối.", nh_tinhtrang),
    Report("nh_hoanthien", G_NH, "Mức hoàn thiện hồ sơ (VEMIS)",
           "Số hồ sơ đủ thông tin tối thiểu theo lớp và các thông tin hay thiếu.", nh_hoanthien),
    Report("nh_giayto", G_NH, "Giấy tờ đã thu",
           "Số học sinh đã nộp từng loại giấy tờ (bản gốc / bản sao), danh sách còn thiếu.",
           nh_giayto),
    Report("nh_xe", G_NH, "Đăng ký xe đưa đón",
           "Số học sinh nội trú theo tuyến xe và danh sách đón trả từng tuyến.", nh_xe),
    Report("nh_tohop", G_NH, "Tổ hợp môn lựa chọn (THPT)",
           "Số học sinh khối 10–12 theo tổ hợp môn lựa chọn 1.", nh_tohop),
    Report("nh_diaban", G_NH, "Địa bàn cư trú học sinh",
           "Học sinh theo tỉnh/thành, phường/xã chỗ ở hiện nay (địa giới mới).", nh_diaban),
    Report("nh_hocluc", G_NH, "Kết quả học tập đầu vào",
           "Học lực kết quả 1 theo khối và điểm trung bình Toán / Văn / Anh.", nh_hocluc),
    Report("nh_danhsach", G_NH, "Danh sách học sinh theo lớp",
           "Danh sách từng lớp (STT, họ tên, ngày sinh, chế độ, liên lạc) để in.", nh_danhsach),
]
BY_ID = {r.id: r for r in REPORTS}


# ------------------------------------------------------------------ xuất Excel
def excel(items: list[tuple[str, str, pd.DataFrame]], school: str, nam_hoc: str) -> bytes:
    """Workbook có tiêu đề trường, tên báo cáo, ngày lập; mỗi mục một sheet."""
    from openpyxl.styles import Alignment, Border, Font, PatternFill, Side
    from openpyxl.utils import get_column_letter

    buf = io.BytesIO()
    thin = Side(style="thin", color="CBD5E1")
    used = set()
    with pd.ExcelWriter(buf, engine="openpyxl") as xw:
        for title, sheet, df in items:
            name = "".join(ch for ch in sheet if ch not in '[]:*?/\\')[:31] or "Sheet"
            base, i = name, 2
            while name in used:
                name = f"{base[:28]}_{i}"
                i += 1
            used.add(name)
            df = df.copy()
            for col in df.columns:
                if df[col].dtype == object:
                    df[col] = df[col].map(lambda v: v.strftime("%d/%m/%Y")
                                          if isinstance(v, (date, datetime)) and pd.notna(v)
                                          else "" if v is pd.NaT else v)
            df.to_excel(xw, sheet_name=name, index=False, startrow=4)
            ws = xw.sheets[name]
            ws["A1"] = school.upper()
            ws["A1"].font = Font(bold=True, size=11, color="1D4ED8")
            ws["A2"] = title.upper()
            ws["A2"].font = Font(bold=True, size=14)
            ws["A3"] = f"Năm học {nam_hoc} · Ngày lập {date.today():%d/%m/%Y}"
            ws["A3"].font = Font(italic=True, size=10, color="64748B")
            for c in ws[5]:
                c.font = Font(bold=True, color="FFFFFF")
                c.fill = PatternFill("solid", fgColor="1D4ED8")
                c.alignment = Alignment(horizontal="center", vertical="center", wrap_text=True)
            ws.row_dimensions[5].height = 32
            for row in ws.iter_rows(min_row=5, max_row=ws.max_row, max_col=max(1, df.shape[1])):
                for c in row:
                    c.border = Border(top=thin, bottom=thin, left=thin, right=thin)
                    if isinstance(c.value, (int, float)) and c.row > 5:
                        hdr = str(ws.cell(5, c.column).value or "")
                        c.number_format = "#,##0" if "(đ)" in hdr or "Tiền" in hdr else \
                            "0.0" if "(%)" in hdr or " TB" in hdr else "#,##0"
            last = ws.max_row
            if last > 5 and any(str(ws.cell(last, j).value) == "Tổng cộng" for j in (1, 2)):
                for c in ws[last]:
                    c.font = Font(bold=True)
                    c.fill = PatternFill("solid", fgColor="EEF2FF")
            for j, col in enumerate(df.columns, 1):
                w = max([len(str(col))] + [len(str(v)) for v in df[col].head(300)])
                ws.column_dimensions[get_column_letter(j)].width = min(max(8, w + 2), 50)
            ws.freeze_panes = "A6"
            ws.print_title_rows = "5:5"
            ws.page_setup.orientation = "landscape" if df.shape[1] > 6 else "portrait"
            ws.page_setup.fitToWidth = 1
            ws.sheet_properties.pageSetUpPr.fitToPage = True
            ws.page_setup.fitToHeight = 0
    return buf.getvalue()


def export_items(rep: Report, res: Result) -> list[tuple[str, str, pd.DataFrame]]:
    if res.sheets:
        return [(f"{rep.title} — {k.replace('_', ' ')}", k, v) for k, v in res.sheets.items()]
    return [(rep.title, rep.title, res.table)]
