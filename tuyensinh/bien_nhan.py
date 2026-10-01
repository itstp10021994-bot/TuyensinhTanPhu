"""Biểu mẫu in "Bảng ký nhận hồ sơ học sinh" (HTML khổ A4, in bằng trình duyệt).

Thông tin trường đổi được trong Secrets: TRUONG_TEN, TRUONG_DIA_CHI, TRUONG_DIEN_THOAI,
TRUONG_WEBSITE, TRUONG_FACEBOOK. Logo: đặt file static/logo_truong.png (hoặc .jpg/.svg).
"""
from __future__ import annotations

import base64
from datetime import date
from html import escape
from pathlib import Path

from . import config

STATIC = Path(__file__).resolve().parents[1] / "static"


def truong() -> dict:
    return {
        "ten": config.get("TRUONG_TEN", "Trường TH-THCS-THPT Tân Phú"),
        "dia_chi": config.get("TRUONG_DIA_CHI",
                              "57/8 Kênh Tân Hóa, P. Hòa Thạnh, Q. Tân Phú, TP Hồ Chí Minh"),
        "dien_thoai": config.get("TRUONG_DIEN_THOAI", "0911 97 71 71"),
        "website": config.get("TRUONG_WEBSITE", "tanphu.igcschool.edu.vn"),
        "facebook": config.get("TRUONG_FACEBOOK", "fb.com/tanphu.edu"),
    }


def _logo() -> str:
    for name, mime in (("logo_truong.png", "image/png"), ("logo_truong.jpg", "image/jpeg"),
                       ("logo_truong.svg", "image/svg+xml")):
        p = STATIC / name
        if p.exists():
            return f'<img class="logo" src="data:{mime};base64,' \
                   f'{base64.b64encode(p.read_bytes()).decode()}" alt="logo">'
    return ""


def _d(v) -> str:
    if not v:
        return ""
    if isinstance(v, date):
        return f"{v:%d/%m/%Y}"
    s = str(v)[:10]
    return f"{s[8:10]}/{s[5:7]}/{s[:4]}" if len(s) == 10 and s[4] == "-" else s


def phu_huynh(rec: dict) -> tuple[str, str]:
    """(họ tên, SĐT) người nộp: người giám hộ, rồi mẹ, rồi cha."""
    for ten, sdt in (("NguoiGiamHo", "DienThoaiNGH"), ("TenMe", "DienThoaiMe"),
                     ("TenCha", "DienThoaiBo")):
        if str(rec.get(ten) or "").strip():
            return str(rec[ten]), str(rec.get(sdt) or rec.get("DienThoaiSLL") or "")
    return "", str(rec.get("DienThoaiSLL") or "")


def html(rec: dict, da_nhan: dict[str, str], can_bo_sung: list[str], han_bo_sung: date | None,
         nguoi_nhan: str, nam_hoc: str, ngay_nhan: date | None = None) -> str:
    t = truong()
    ph, sdt = phu_huynh(rec)
    khoi = "-".join(x for x in (str(rec.get("Khoi") or ""), str(rec.get("PhanHe") or "")) if x)
    lop = rec.get("LopHoc") or (f"Khối {khoi}" if khoi else "")
    li_nhan = "".join(f"<li>{escape(g)} <span class='ban'>({escape(b)})</span></li>"
                      for g, b in da_nhan.items())
    li_thieu = "".join(f"<li>{escape(g)}</li>" for g in can_bo_sung)
    footer = " &nbsp;·&nbsp; ".join(escape(x) for x in (t["dia_chi"], t["dien_thoai"],
                                                       t["website"], t["facebook"]) if x)
    ngay = ngay_nhan or date.today()
    logo = _logo()  # logo đã có tên trường -> không in lại tên
    return f"""<!doctype html><html lang="vi"><head><meta charset="utf-8">
<title>Bảng ký nhận hồ sơ - {escape(str(rec.get('HoTen') or ''))}</title>
<style>
@page {{ size: A4; margin: 14mm 16mm; }}
* {{ box-sizing: border-box; }}
body {{ font-family: "Times New Roman", Times, serif; color: #111; margin: 0; background: #f1f5f9; }}
.bar {{ position: sticky; top: 0; display: flex; gap: 8px; justify-content: flex-end; padding: 8px;
       background: #f1f5f9; font-family: system-ui, sans-serif; }}
.bar button {{ border: 0; border-radius: 6px; padding: 8px 16px; font-size: 14px; cursor: pointer;
              background: #1D4ED8; color: #fff; font-weight: 600; }}
.page {{ width: 210mm; min-height: 297mm; margin: 0 auto 16px; background: #fff;
        padding: 14mm 16mm; display: flex; flex-direction: column; box-shadow: 0 1px 4px #0002; }}
.head {{ display: flex; align-items: center; gap: 14px; border-bottom: 2px solid #1D4ED8;
        padding-bottom: 8px; }}
.logo {{ height: 62px; }}
.truong {{ font-family: Arial, sans-serif; color: #1D4ED8; font-weight: 700; font-size: 15px;
          text-transform: uppercase; }}
h1 {{ text-align: center; font-size: 20px; margin: 22px 0 2px; letter-spacing: .3px; }}
.nam {{ text-align: center; font-weight: 700; margin-bottom: 18px; }}
h2 {{ font-size: 15px; margin: 16px 0 6px; text-transform: uppercase; }}
.row {{ display: flex; gap: 16px; margin: 4px 0; font-size: 15px; }}
.row > div {{ flex: 1; }} .lbl {{ color: #444; }}
ul {{ margin: 4px 0 0 0; padding-left: 22px; font-size: 15px; }} li {{ margin: 2px 0; }}
.ban {{ color: #555; font-style: italic; }}
.sum {{ font-weight: 700; font-size: 15px; margin-top: 14px; }}
.han {{ color: #B91C1C; font-weight: 700; margin-top: 10px; font-size: 15px; }}
.ky {{ display: flex; justify-content: space-between; margin-top: auto; padding-top: 28px;
      text-align: center; font-size: 15px; }}
.ky > div {{ width: 45%; }} .ky b {{ display: block; }} .ky i {{ display: block; font-size: 13px; color: #444; }}
.ky .ten {{ margin-top: 62px; font-weight: 700; }}
.foot {{ margin-top: 18px; border-top: 1px solid #CBD5E1; padding-top: 6px; font-size: 11.5px;
        color: #334155; text-align: center; font-family: Arial, sans-serif; }}
@media print {{ body {{ background: #fff; }} .bar {{ display: none; }}
  .page {{ box-shadow: none; margin: 0; width: auto; min-height: 268mm; padding: 0; }} }}
</style></head><body>
<div class="bar"><button onclick="window.print()">🖨 In bảng ký nhận</button></div>
<div class="page">
 <div class="head">{logo or f'<div class="truong">{escape(t["ten"])}</div>'}</div>
 <h1>BẢNG KÝ NHẬN HỒ SƠ HỌC SINH</h1>
 <div class="nam">Năm học {escape(nam_hoc)}</div>
 <h2>Thông tin học sinh</h2>
 <div class="row"><div><span class="lbl">Họ tên:</span> <b>{escape(str(rec.get('HoTen') or ''))}</b></div>
   <div><span class="lbl">Ngày sinh:</span> {escape(_d(rec.get('NgaySinh')))}</div></div>
 <div class="row"><div><span class="lbl">Lớp:</span> {escape(str(lop))}</div>
   <div><span class="lbl">Chế độ:</span> {escape(str(rec.get('NoiTruBanTru') or ''))}</div></div>
 <h2>Thông tin cha mẹ học sinh / người giám hộ</h2>
 <div class="row"><div><span class="lbl">Họ tên:</span> {escape(ph)}</div></div>
 <div class="row"><div><span class="lbl">SĐT:</span> {escape(sdt)}</div></div>
 <div class="sum">Hồ sơ đã nhận là: {len(da_nhan)} hồ sơ hợp lệ</div>
 <ul>{li_nhan}</ul>
 <div class="sum">Hồ sơ cần bổ sung là: {len(can_bo_sung)} hồ sơ</div>
 <ul>{li_thieu}</ul>
 {f'<div class="han">Bổ sung trước ngày: {_d(han_bo_sung)}</div>' if can_bo_sung and han_bo_sung else ''}
 <div class="ky">
  <div><i style="visibility:hidden">Ngày</i><b>Phụ huynh nộp hồ sơ</b><i>Ký và ghi rõ họ tên</i>
   <div class="ten">{escape(ph)}</div></div>
  <div><i>Ngày {ngay:%d} tháng {ngay:%m} năm {ngay:%Y}</i><b>Đơn vị nhận hồ sơ</b>
   <i>Ký và ghi rõ họ tên</i><div class="ten">{escape(nguoi_nhan)}</div></div>
 </div>
 <div class="foot">{footer}</div>
</div></body></html>"""
