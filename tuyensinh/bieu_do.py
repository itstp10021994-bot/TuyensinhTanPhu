"""Biểu đồ dùng chung (Tổng quan, Báo cáo, Nội trú): một bảng màu, một kiểu trục, một kiểu nhãn.

Quy tắc:
- Màu phân loại theo thứ tự cố định (đã kiểm tra mù màu, có bản cho nền tối), không lặp vòng.
- Bước tuyển sinh dùng màu trạng thái riêng (Tư vấn / Nộp hồ sơ / Nhập học / Rút hồ sơ).
- Cột / thanh mảnh, đầu bo 4px, khe 2px màu nền giữa các khối; đường 2px, điểm tròn có viền nền.
- Trục và lưới chìm; chữ dùng màu chữ (không dùng màu của dữ liệu); một trục giá trị.
- Có chú giải khi ≥ 2 nhóm; nhãn giá trị chỉ ở đầu thanh (không ghi số lên mọi điểm).
- Rê chuột: thanh hiện tooltip; đường có vạch dọc + tooltip theo kỳ.
"""
from __future__ import annotations

import altair as alt
import pandas as pd
import streamlit as st

# Bảng màu phân loại: [nền sáng, nền tối] — cùng 8 sắc độ, thứ tự cố định
CAT_SANG = ["#2a78d6", "#eb6834", "#1baf7a", "#eda100", "#e87ba4", "#008300", "#6250d6",
            "#e34948"]
CAT_TOI = ["#3987e5", "#d95926", "#199e70", "#c98500", "#d55181", "#008300", "#9085e9",
           "#e66767"]
# Thang tuần tự (một sắc xanh, nhạt -> đậm) cho bản đồ nhiệt
TUAN_TU = ["#cde2fb", "#9ec5f4", "#6da7ec", "#3987e5", "#256abf", "#184f95", "#0d366b"]
# Trạng thái tuyển sinh (khớp ui.STATUS)
TRANG_THAI_MAU = {"Tư vấn": "#2a78d6", "Nộp hồ sơ": "#eda100", "Nhập học": "#1baf7a",
                  "Rút hồ sơ": "#9a9890"}
# Mức đánh giá nội trú
MUC_MAU = {"Tốt": "#1baf7a", "Khá": "#2a78d6", "Trung bình": "#eda100", "Chưa tốt": "#e34948"}

MUC_TIEN = ("tiền", "thanh toán", "còn lại", "đã thu", "(đ)")


def toi() -> bool:
    try:
        return st.context.theme.type == "dark"
    except Exception:
        return False


def cat() -> list[str]:
    return CAT_TOI if toi() else CAT_SANG


def _muc() -> dict:
    """Màu mực / nền của biểu đồ theo giao diện sáng / tối."""
    if toi():
        return {"nen": "#1C1C1E", "chu": "#f0efec", "phu": "#c3c2b7", "mo": "#898781",
                "luoi": "#2c2c2a", "truc": "#383835"}
    return {"nen": "#FFFFFF", "chu": "#1D1D1F", "phu": "#52514e", "mo": "#898781",
            "luoi": "#ECEBE6", "truc": "#c3c2b7"}


def cau_hinh(c, height: int, gon: bool = False):
    """Kiểu chung: chữ hệ thống, trục chìm, lưới mảnh, chú giải trên cùng dạng chấm tròn."""
    m = _muc()
    fs = 11 if gon else 12
    return (c.properties(height=height, background="transparent", padding={"top": 4, "left": 2,
                                                                           "right": 6, "bottom": 2})
            .configure(font="Inter, system-ui, -apple-system, 'Segoe UI', sans-serif")
            .configure_view(strokeWidth=0)
            .configure_axis(labelColor=m["mo"], labelFontSize=fs, titleColor=m["phu"],
                            gridColor=m["luoi"], gridWidth=1, domainColor=m["truc"],
                            tickColor=m["truc"], tickSize=4, labelPadding=6, titleFontWeight=500)
            .configure_axisBand(grid=False, ticks=False)
            .configure_legend(orient="top", direction="horizontal", title=None,
                              labelColor=m["phu"], labelFontSize=fs, symbolType="circle",
                              symbolSize=80, columnPadding=14, padding=0, offset=6)
            .configure_title(color=m["chu"], fontSize=13, anchor="start"))


def _tien(v: float) -> str:
    return f"{v / 1e6:,.1f} tr".replace(",", "#").replace(".", ",").replace("#", ".")


def _so(v) -> str:
    try:
        return f"{float(v):,.0f}".replace(",", ".")
    except (TypeError, ValueError):
        return str(v)


def _mau_nhom(doms: list, ten_mau: dict | None) -> list[str]:
    """Màu theo nhóm: trạng thái / mức có màu riêng; còn lại theo thứ tự cố định."""
    if ten_mau and all(d in ten_mau for d in doms):
        return [ten_mau[d] for d in doms]
    return cat()[:len(doms)] if len(doms) <= 8 else None


def ve(spec: dict, height: int | None = None, gon: bool = False, key: str | None = None):
    """Vẽ một biểu đồ theo `spec` của reports.Result.chart:
    {kind: bar | hbar | stack | stack_cat | group | line | line_cat | area | heat,
     data, x, y, color?, money?, horizontal?, fmt?, pct?}"""
    data = spec.get("data")
    if data is None or len(data) == 0:
        return
    c = bieu_do(spec, height, gon)
    if c is not None:
        st.altair_chart(c, width="stretch", key=key)


def bieu_do(spec: dict, height: int | None = None, gon: bool = False):
    data: pd.DataFrame = spec["data"].copy()
    kind, x, y = spec["kind"], spec["x"], spec["y"]
    color = spec.get("color")
    m = _muc()
    money = spec.get("money") or any(w in str(y).lower() for w in MUC_TIEN)
    pct = spec.get("pct") or "(%)" in str(y)
    vfmt = ",.1f" if pct else ",.0f"
    ten_mau = {**TRANG_THAI_MAU, **MUC_MAU}

    # ---------------------------------------------------------------- đường theo thời gian
    if kind in ("line", "area", "line_cat"):
        thoi_gian = kind != "line_cat"
        fmt = spec.get("fmt") or "%d/%m"
        doms = list(dict.fromkeys(data[color])) if color else []
        xenc = (alt.X(f"{x}:T", title=None, axis=alt.Axis(format=fmt, labelAngle=0,
                                                          tickCount=8, grid=False))
                if thoi_gian else
                alt.X(f"{x}:N", title=None, sort=list(dict.fromkeys(data[x])),
                      axis=alt.Axis(labelAngle=0 if data[x].nunique() <= 14 else -40,
                                    grid=False)))
        yenc = alt.Y(f"{y}:Q", title=None, axis=alt.Axis(format="d" if not pct else ".0f",
                                                         tickCount=5, domain=False, ticks=False))
        cenc = (alt.Color(f"{color}:N", sort=doms,
                          scale=alt.Scale(domain=doms, range=_mau_nhom(doms, ten_mau)))
                if color else alt.value(cat()[0]))
        base = alt.Chart(data).encode(x=xenc, y=yenc, color=cenc)
        lop = []
        cong = "monotone" if data[x].nunique() >= 10 else "linear"  # ít điểm: nối thẳng
        if kind == "area" or (not color or len(doms) == 1):  # một chuỗi: nền nhạt 10%
            lop.append(base.mark_area(opacity=.10, interpolate=cong))
        lop.append(base.mark_line(strokeWidth=2, interpolate=cong, strokeCap="round",
                                  strokeJoin="round"))
        # rê chuột: vạch dọc + điểm + tooltip theo kỳ
        chon = alt.selection_point(fields=[x], nearest=True, on="pointerover", empty=False,
                                   clear="pointerout")
        tip = ([alt.Tooltip(f"{x}:T", title="Kỳ", format=spec.get("tipfmt", "%d/%m/%Y"))]
               if thoi_gian else [alt.Tooltip(f"{x}:N", title=x)])
        if color:
            tip.append(alt.Tooltip(f"{color}:N", title=color))
        tip.append(alt.Tooltip(f"{y}:Q", title=y, format=vfmt))
        lop.append(base.mark_point(size=70, filled=True, stroke=m["nen"], strokeWidth=2,
                                   opacity=1).encode(
            opacity=alt.condition(chon, alt.value(1), alt.value(0 if len(data) > 24 else 1)),
            tooltip=tip).add_params(chon))
        lop.insert(0, alt.Chart(data).mark_rule(color=m["mo"], strokeWidth=1).encode(
            x=alt.X(f"{x}:T") if thoi_gian else alt.X(f"{x}:N",
                                                      sort=list(dict.fromkeys(data[x])))
        ).transform_filter(chon))
        return cau_hinh(alt.layer(*lop), height or 300, gon)

    # ---------------------------------------------------------------- bản đồ nhiệt
    if kind == "heat":
        xs = list(dict.fromkeys(data[x]))
        ys = list(dict.fromkeys(data[color]))
        vmax = max(float(data[y].max() or 0), 1)
        base = alt.Chart(data).encode(
            x=alt.X(f"{x}:N", title=None, sort=xs, axis=alt.Axis(labelAngle=0, orient="top",
                                                                 domain=False, ticks=False)),
            y=alt.Y(f"{color}:N", title=None, sort=ys, axis=alt.Axis(domain=False, ticks=False)))
        o = base.mark_rect(cornerRadius=4, stroke=m["nen"], strokeWidth=2).encode(
            color=alt.Color(f"{y}:Q", legend=None, scale=alt.Scale(range=TUAN_TU,
                                                                   domain=[0, vmax])),
            tooltip=[alt.Tooltip(f"{color}:N"), alt.Tooltip(f"{x}:N"),
                     alt.Tooltip(f"{y}:Q", format=vfmt)])
        so = base.mark_text(fontSize=11 if gon else 12, fontWeight=500).encode(
            text=alt.condition(f"datum['{y}'] > 0", alt.Text(f"{y}:Q", format=vfmt),
                               alt.value("")),
            color=alt.condition(f"datum['{y}'] > {vmax * .45}", alt.value("#FFFFFF"),
                                alt.value("#1D1D1F")))
        return cau_hinh(o + so, height or max(160, 34 * len(ys) + 30), gon)

    # ---------------------------------------------------------------- thanh / cột
    horiz = spec.get("horizontal") or kind == "hbar"
    n = data[x].nunique()
    cat_axis = (alt.Axis(labelLimit=240, labelAngle=0, domain=False, ticks=False, labelPadding=8)
                if horiz else
                alt.Axis(labelAngle=0 if n <= 12 else -40, labelLimit=140, domain=True,
                         ticks=False))
    sort = (alt.EncodingSortField(y, "sum", "descending") if horiz and not spec.get("giu_thu_tu")
            else list(dict.fromkeys(data[x])))
    cenc_cat = (alt.Y(f"{x}:N", title=None, sort=sort, axis=cat_axis) if horiz
                else alt.X(f"{x}:N", title=None, sort=sort, axis=cat_axis))
    vax = (alt.Axis(labelExpr="format(datum.value / 1e6, ',.0f') + ' tr'", tickCount=5,
                    domain=False, ticks=False)
           if money else alt.Axis(format="d" if not pct else ".0f", tickCount=5, domain=False,
                                  ticks=False))
    val = (alt.X(f"{y}:Q", title=None, axis=vax) if horiz
           else alt.Y(f"{y}:Q", title=None, axis=vax))
    data["_lbl"] = [_tien(v) if money else (f"{v:,.1f}%" if pct else _so(v)) for v in data[y]]
    tip = [alt.Tooltip(f"{x}:N", title=x)] + (
        [alt.Tooltip(f"{color}:N", title=color)] if color else []) + [
        alt.Tooltip("_lbl:N", title=y)]
    # bề dày ≤ 24px (cột đứng ít nhóm: cố định 24px; nhiều nhóm: 62% khe)
    if horiz:
        kich = {"size": 18} if n <= 14 else {"height": {"band": .62}}
    else:
        kich = {"size": 24} if n <= 14 else {"width": {"band": .62}}
    enc = {"x": val, "y": cenc_cat} if horiz else {"x": cenc_cat, "y": val}

    if kind in ("stack", "stack_cat"):
        doms = list(dict.fromkeys(data[color]))
        if kind == "stack":
            from .schema import TRANG_THAI
            doms = [s for s in TRANG_THAI if s in set(doms)] + [d for d in doms
                                                                 if d not in TRANG_THAI]
        data["_o"] = data[color].map({d: i for i, d in enumerate(doms)})
        enc["color"] = alt.Color(f"{color}:N", sort=doms, scale=alt.Scale(
            domain=doms, range=_mau_nhom(doms, ten_mau)))
        enc["order"] = alt.Order("_o:Q")
        mark = alt.Chart(data).mark_bar(stroke=m["nen"], strokeWidth=2, **kich)
        c = mark.encode(**enc, tooltip=tip)
        h = height or (max(200, min(620, 30 * n + 40)) if horiz else 300)
        return cau_hinh(c, h, gon)

    if kind == "group":
        doms = list(dict.fromkeys(data[color]))
        enc["color"] = alt.Color(f"{color}:N", sort=doms, scale=alt.Scale(
            domain=doms, range=_mau_nhom(doms, ten_mau)))
        mark = alt.Chart(data).mark_bar(cornerRadiusEnd=4, stroke=m["nen"], strokeWidth=1.5,
                                        size=14 if horiz else max(8, min(22, 64 // len(doms))))
        enc["yOffset" if horiz else "xOffset"] = (alt.YOffset if horiz else alt.XOffset)(
            f"{color}:N", sort=doms, scale=alt.Scale(paddingOuter=.6 if n <= 2 else .2))
        c = mark.encode(**enc, tooltip=tip)
        h = height or (max(220, min(680, 22 * n * len(doms) + 40)) if horiz else 300)
        return cau_hinh(c, h, gon)

    # một chuỗi: một màu; nhãn giá trị ở đầu thanh
    mau = spec.get("mau") or cat()[0]
    mark = alt.Chart(data).mark_bar(cornerRadiusEnd=4, color=mau, **kich)
    if spec.get("mau_theo_nhom"):  # mỗi thanh một màu riêng (vd bước tuyển sinh), không chú giải
        doms = list(dict.fromkeys(data[x]))
        enc["color"] = alt.Color(f"{x}:N", legend=None, scale=alt.Scale(
            domain=doms, range=_mau_nhom(doms, ten_mau)))
    c = mark.encode(**enc, tooltip=tip)
    if n <= 30:
        so = alt.Chart(data).mark_text(
            align="left" if horiz else "center", baseline="middle" if horiz else "bottom",
            dx=6 if horiz else 0, dy=0 if horiz else -5, fontSize=11, color=m["phu"]).encode(
            **({"x": val, "y": cenc_cat} if horiz else {"x": cenc_cat, "y": val}),
            text="_lbl:N")
        c = c + so
    h = height or (max(200, min(640, 28 * n + 30)) if horiz else 300)
    return cau_hinh(c, h, gon)


def phan_doan(phan: list[tuple[str, float]], mau: dict | None = None, height: int = 14,
              key: str | None = None):
    """Thanh phân đoạn (một tổng chia ≤ 6 phần) kèm chú giải số + %: thay cho biểu đồ tròn."""
    tong = sum(v for _, v in phan) or 1
    m = _muc()
    ds = [(t, v, (mau or {}).get(t) or cat()[i]) for i, (t, v) in enumerate(phan[:8])]
    thanh = "".join(
        f'<span title="{t}: {_so(v)}" style="flex:{v};background:{c};min-width:{4 if v else 0}px">'
        f'</span>' for t, v, c in ds if v)
    chu = "".join(
        f'<span class="tp-seg-i"><i style="background:{c}"></i>{t}'
        f'<b>{_so(v)}</b><em>{v / tong:.0%}</em></span>' for t, v, c in ds)
    st.html(f'''<div class="tp-seg" style="--seg-h:{height}px;--seg-gap:{m["nen"]}">
<div class="tp-seg-bar">{thanh}</div><div class="tp-seg-ds">{chu}</div></div>''')
