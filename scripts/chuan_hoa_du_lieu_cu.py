"""Chuẩn hóa dữ liệu "Data tuyển sinh" cũ (xuất từ SharePoint) để tạo list mới.

- Tên cột → tên nội bộ không dấu (khớp tuyensinh/schema.py)
- Tỉnh cũ (63 tỉnh) → tỉnh/thành mới (34); quận/huyện cũ được nhận diện và giữ lại ở
  cột TruongCu_DiaChiCu; Trường cũ đối chiếu danh mục trường (truong_hoc.csv) trong đúng
  tỉnh và quận/huyện cũ → tên trường chuẩn + Phường/Xã mới
- Khối "10-IEP" → Khối 10 + Phân hệ IEP; Nguồn, Tình trạng, Ngân hàng, SĐT, họ tên chuẩn hóa
- Thêm cột Giữ chỗ (tách khỏi Tình trạng tư vấn)

    python scripts/chuan_hoa_du_lieu_cu.py data_tuyensinh.xlsx -o Data_TuyenSinh_chuan_hoa.xlsx
"""
import argparse
import difflib
import json
import re
import urllib.request
from collections import Counter, defaultdict
from datetime import date

import _common
import pandas as pd

from tuyensinh import danh_muc, services
from tuyensinh.schema import (GIU_CHO, NGUON, PHAN_HE, TINH_TRANG, TRANG_THAI, TUYEN_SINH,
                              DATE, NUMBER)

OLD_UNITS_URL = ("https://raw.githubusercontent.com/ThangLeQuoc/vietnamese-provinces-database/"
                 "v2.4.1/json/simplified_json_generated_data_vn_units.json")
fold = danh_muc.fold

# Cột trong file xuất từ list cũ → key trong app
OLD_COLS = {
    "Ngày liên hệ": "NgayLienHe", "SĐT": "SDT", "Nguồn": "Nguon", "Tài khoản FB": "TenLienHe",
    "Người giới thiệu": "NguoiGioiThieu", "Họ tên HS": "HoTenHS", "Khối": "Khoi",
    "Giới tính": "GioiTinh", "Chế độ": "CheDo", "Trường cũ": "TruongCu",
    "Trường cũ_Quận huyện": "_HuyenCu", "Trường cũ_tỉnh": "_TinhCu",
    "Tình trạng": "TinhTrang", "Nội dung đã trao đổi": "GhiChu", "Bước": "TrangThai",
    "Phân hệ": "PhanHe", "Người nhận hồ sơ": "NguoiNhanHoSo",
    "Số tiền xác nhận": "SoTienXacNhan", "Người xác nhận": "NguoiXacNhan",
    "Tên chủ tài khoản": "TenChuTaiKhoan", "Ngân hàng": "NganHang", "Số tài khoản": "SoTaiKhoan",
    "Toán 1": "Toan1", "Văn 1": "Van1", "Anh 1": "Anh1", "TV 1": "TV1", "Toán 2": "Toan2",
    "Văn 2": "Van2", "Tiếng Anh 2": "Anh2", "TV 2": "TV2", "Hạnh kiểm 1": "HanhKiem1",
    "Hạnh kiểm 2": "HanhKiem2", "Ngày sinh": "NgaySinh", "Nam hoc": "NamHoc",
}

BANKS = [  # (mẫu trên chuỗi không dấu, tên chuẩn)
    (r"vietcom|vcb|vietcm", "Vietcombank"), (r"techcom|techcomank|ky thuong", "Techcombank"),
    (r"vietin|viettin", "VietinBank"), (r"sac+ombank|sacom", "Sacombank"), (r"\bacb\b|a chau", "ACB"),
    (r"\bmb\b|mbbank|mb bank|quan doi", "MB Bank"), (r"vp ?bank", "VPBank"),
    (r"bidv", "BIDV"), (r"tp ?bank|tien phong", "TPBank"), (r"agri|agibank|aribank", "Agribank"),
    (r"msb|hang hai", "MSB"), (r"shinhan", "Shinhan Bank"), (r"hd ?bank", "HDBank"),
    (r"ocb|phuong dong", "OCB"), (r"vib\b|quoc te", "VIB"), (r"scb", "SCB"),
    (r"lpbank|lien viet|lpb", "LPBank"), (r"sea ?bank", "SeABank"), (r"shb", "SHB"),
    (r"eximbank", "Eximbank"), (r"nam a", "Nam A Bank"), (r"bac a", "Bac A Bank"),
    (r"kien ?long", "KienlongBank"), (r"cake", "Cake by VPBank"), (r"timo", "Timo"),
    (r"pvcom", "PVcomBank"), (r"abbank|an binh", "ABBank"), (r"vietbank", "Vietbank"),
    (r"bao viet", "BaoViet Bank"), (r"uob", "UOB"), (r"hsbc", "HSBC"),
    (r"standard", "Standard Chartered"), (r"woori", "Woori Bank"),
]
SUFFIX_NGUOI = re.compile(r"\s*_\s*TH\s*-\s*THCS\s*-\s*THPT.*$", re.I)


# ------------------------------------------------------------------ danh mục cũ / mới
def load_old_units(path: str | None):
    if path:
        return json.load(open(path, encoding="utf-8"))
    with urllib.request.urlopen(OLD_UNITS_URL, timeout=120) as r:
        return json.load(r)


def strip_prefix(s: str) -> str:
    return re.sub(r"^(tinh|thanh pho|tp\.?|thu do|quan|huyen|thi xa|thi tran|phuong|xa|"
                  r"q\.?|h\.?|tx\.?)\s+", "", fold(s)).strip()


class Geo:
    """Tra cứu tỉnh/quận huyện cũ và quy đổi sang địa giới mới."""

    def __init__(self, old_units):
        new = danh_muc.load()
        self.ma_xa = new["ma_xa"]  # mã phường/xã mới -> [tỉnh, xã]
        self.old_prov = {}  # code -> tên
        self.old_prov_by_key = {}
        self.districts = defaultdict(list)  # key tên -> [(prov_code, tên huyện, code)]
        self.old_wards = defaultdict(list)  # key tên -> [(prov_code, huyện)]
        prov_new_votes = defaultdict(Counter)
        self.wards_of_district = defaultdict(set)  # (prov, huyện) -> {(tỉnh mới, xã mới)}
        for p in old_units:
            self.old_prov[p["Code"]] = p["FullName"]
            self.old_prov_by_key[strip_prefix(p["FullName"])] = p["Code"]
            for d in p["District"]:
                self.districts[strip_prefix(d["FullName"])].append((p["Code"], d["FullName"]))
                for w in d.get("Ward") or []:
                    self.old_wards[strip_prefix(w["FullName"])].append((p["Code"], d["FullName"]))
                    hit = self.ma_xa.get(w["Code"])
                    if hit:
                        prov_new_votes[p["Code"]][hit[0]] += 1
                        self.wards_of_district[(p["Code"], d["FullName"])].add(tuple(hit))
        self.old_to_new = {c: v.most_common(1)[0][0] for c, v in prov_new_votes.items()}
        self.new_tinh = {fold(re.sub(r"^(Tỉnh|Thành phố)\s+", "", t)): t for t in new["tinh"]}

    def tinh(self, raw: str) -> tuple[str, str | None]:
        """→ (tỉnh mới, mã tỉnh cũ) từ chuỗi tự do."""
        s = fold(raw)
        s = re.sub(r"^(tp\.?\s*|thanh pho\s+)", "", s).strip(" .-")
        if not s or len(s) < 3:
            return "", None
        if s in ("hcm", "tphcm", "tp hcm", "sai gon", "ho chi minh", "hochiminh"):
            s = "ho chi minh"
        if s in ("vung tau", "ba ria vung tau", "brvt"):
            s = "ba ria - vung tau"
        code = self.old_prov_by_key.get(s) or self.old_prov_by_key.get(s.replace("-", " - "))
        if code:
            return self.old_to_new.get(code, ""), code
        if s in self.new_tinh:
            return self.new_tinh[s], None
        return "", None

    def huyen(self, raw: str, prov_code: str | None, new_tinh: str = ""):
        """→ (mã tỉnh cũ, tên quận/huyện cũ) từ chuỗi tự do; None nếu không chắc."""
        s = fold(raw).strip(" .,-")
        if not s:
            return None
        m = re.fullmatch(r"(?:q\.?|quan)?\s*(\d{1,2})", s)
        if m:  # "11", "Q11", "Quận 11" -> Quận 11 (TP.HCM)
            s = f"quan {int(m.group(1))}"
            key = str(int(m.group(1)))
        else:
            s = re.sub(r"^(tp\.?|thanh pho|tx\.?|thi xa)\s+", "", s)
            key = strip_prefix(s)
        cands = self.districts.get(key, [])
        if prov_code:
            cands = [c for c in cands if c[0] == prov_code]
        elif new_tinh:
            cands = [c for c in cands if self.old_to_new.get(c[0]) == new_tinh]
        if len(cands) == 1:
            return cands[0]
        if not cands:  # có thể là tên phường/xã cũ (vd "Phú Thọ Hòa")
            ws = self.old_wards.get(key, [])
            if prov_code:
                ws = [w for w in ws if w[0] == prov_code]
            elif new_tinh:
                ws = [w for w in ws if self.old_to_new.get(w[0]) == new_tinh]
            if len({w for w in ws}) == 1:
                return ws[0]
        return None


# ------------------------------------------------------------------ trường học
LEVEL = [(r"\btrung hoc co so\b|\bthcs\b", "thcs"), (r"\btrung hoc pho thong\b|\bthpt\b", "thpt"),
         (r"\btieu hoc\b|\btih\b|\bth\b", "th"), (r"\bmam non\b|\bmn\b|\bmau giao\b|\bmg\b", "mn")]


def school_key(name: str) -> tuple[str, frozenset]:
    """(tên riêng đã chuẩn hóa, tập cấp học) — "THCS TT Tân Châu" ≈ "Trường THCS Thị trấn Tân Châu"."""
    s = fold(name)
    s = re.sub(r"[^\w\s]", " ", s)
    levels = set()
    for pat, lv in LEVEL:
        if re.search(pat, s):
            levels.add(lv)
            s = re.sub(pat, " ", s)
    s = re.sub(r"\bthi tran\b", "tt", s)
    s = re.sub(r"\b(truong|cong lap|school|cap|co so \d+|cs\d*)\b", " ", s)
    return re.sub(r"\s+", " ", s).strip(), frozenset(levels)


class Schools:
    def __init__(self):
        df = pd.read_csv(danh_muc.TRUONG_CSV, dtype=str).fillna("")
        self.rows = []
        for r in df.itertuples(index=False):
            k, lv = school_key(r[2])
            self.rows.append({"tinh": r[0], "xa": r[1], "ten": r[2], "key": k, "lv": lv})

    def match(self, raw: str, tinh: str, wards: set | None, khoi: str,
              region: set | None = None):
        """Trả về dòng danh mục khớp duy nhất, hoặc None.

        Không rõ tỉnh: chỉ tìm trong `region` (các tỉnh trường thường tuyển sinh)."""
        k, lv = school_key(raw)
        if not k:
            return None, ""
        if tinh:
            pool = [r for r in self.rows if r["tinh"] == tinh]
        elif region:
            pool = [r for r in self.rows if r["tinh"] in region]
        else:
            return None, ""
        want = {"Mầm non": "mn", "Tiểu học": "th", "THCS": "thcs", "THPT": "thpt"}
        by_khoi = {want[c] for c in danh_muc.cap_truoc_khoi(khoi)}

        def pick(cands):
            if not cands:
                return None
            if lv:  # tên có ghi cấp học: phải khớp cấp
                cands = [c for c in cands if not c["lv"] or lv & c["lv"]]
            elif by_khoi and len(cands) > 1:
                pref = [c for c in cands if c["lv"] & by_khoi]
                cands = pref or cands
            if wards:  # biết quận/huyện cũ: trường phải nằm trong đó
                cands = [c for c in cands if (c["tinh"], c["xa"]) in wards]
            uniq = {(c["tinh"], c["xa"], c["ten"]) for c in cands}
            return cands[0] if len(uniq) == 1 else None

        exact = pick([r for r in pool if r["key"] == k])
        if exact or not tinh:
            return (exact, "exact") if exact else (None, "")
        # Gần đúng chỉ để sửa lỗi chính tả: cùng chữ số, cùng từ đầu, tên đủ dài
        digits = re.findall(r"\d+", k)
        scored = [(difflib.SequenceMatcher(None, k, r["key"]).ratio(), r) for r in pool
                  if abs(len(r["key"]) - len(k)) <= 3 and min(len(k), len(r["key"])) >= 10
                  and re.findall(r"\d+", r["key"]) == digits
                  and r["key"].split()[:1] == k.split()[:1]]
        close = pick([r for sc, r in scored if sc >= 0.9])
        return (close, "fuzzy") if close else (None, "")


# ------------------------------------------------------------------ giá trị
def canon(value: str, choices, extra: dict | None = None) -> str:
    v = re.sub(r"\s+", " ", str(value or "")).strip()
    if not v:
        return ""
    for c in choices:
        if fold(c) == fold(v):
            return c
    return (extra or {}).get(fold(v), v)


def bank(v: str) -> str:
    s = fold(v)
    if not s:
        return ""
    for pat, name in BANKS:
        if re.search(pat, s):
            return name
    return re.sub(r"\s+", " ", v).strip()


def person(v: str) -> str:
    v = re.sub(r"\s+", " ", SUFFIX_NGUOI.sub("", str(v or ""))).strip()
    if v and (v.isupper() or v.islower()):
        v = v.title()
    return v


ABBR = [(r"^(TH\s*,?\s*[-–&]?\s*THCS\s*[-–&]?\s*THPT)\b", "Tiểu học - Trung học cơ sở - Trung học phổ thông"),
        (r"^(TH\s*,?\s*[-–&]\s*THCS|TH\s*,\s*THCS)\b", "Tiểu học - Trung học cơ sở"),
        (r"^(THCS\s*[-–&,]\s*THPT)\b", "Trung học cơ sở - Trung học phổ thông"),
        (r"^THCS\b", "Trung học cơ sở"), (r"^THPT\b", "Trung học phổ thông"),
        (r"^(TiH|TH)\b", "Tiểu học"), (r"^(MN|Mầm non)\b", "Mầm non")]


def full_school_name(v: str) -> str:
    """ "THCS TT Long Thành" -> "Trường Trung học cơ sở Thị trấn Long Thành" (tên chưa có trong danh mục)."""
    if not v:
        return v
    v = re.sub(r"^Trường\s+", "", v, flags=re.I)
    for pat, full in ABBR:
        if re.match(pat, v, flags=re.I):
            v = re.sub(pat, full, v, count=1, flags=re.I)
            v = re.sub(r"\bTT\b", "Thị trấn", v)
            return "Trường " + v
    return v if re.match(r"^Trường\b", v, re.I) else v


def clean_school(v: str) -> str:
    v = re.sub(r"\s+", " ", str(v or "")).strip(" .,-")
    if fold(v) in ("trong", "khong", "khong co", "chua co", "-", "x", "0"):
        return ""
    v = re.sub(r"^TiH\b", "TH", v)
    return v


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("file")
    ap.add_argument("-o", "--out", default="Data_TuyenSinh_chuan_hoa.xlsx")
    ap.add_argument("--old-units", help="JSON danh mục hành chính trước sáp nhập (v2.4.1)")
    args = ap.parse_args()

    geo = Geo(load_old_units(args.old_units))
    schools = Schools()
    raw = pd.read_excel(args.file, dtype=str).fillna("")
    raw = raw.rename(columns={c.strip(): c.strip() for c in raw.columns})
    missing = [c for c in OLD_COLS if c not in raw.columns]
    if missing:
        raise SystemExit(f"File thiếu cột: {missing}")

    # Lượt 1: các tỉnh xuất hiện >= 5 lần = vùng tuyển sinh (dùng khi dòng không ghi tỉnh)
    tinh_count = Counter(geo.tinh(t)[0] for t in raw["Trường cũ_tỉnh"])
    region = {t for t, n in tinh_count.items() if t and n >= 5}
    print("Vùng tuyển sinh:", sorted(region))

    out, report = [], []
    stats = Counter()
    for i, r in raw.iterrows():
        o = {k: str(r[c]).strip() for c, k in OLD_COLS.items()}
        rec = {}
        # --- thông tin chung
        rec["HoTenHS"] = person(o["HoTenHS"])
        # Title là cột bắt buộc mặc định của SharePoint
        rec["Title"] = rec["HoTenHS"] or f"(Chưa có tên) {o['SDT']}".strip()
        rec["NamHoc"] = o["NamHoc"]
        m = re.match(r"\s*(\d{1,2})\s*[-–_ ]?\s*([A-Za-z]*)", o["Khoi"])
        rec["Khoi"] = str(int(m.group(1))) if m else o["Khoi"]
        rec["PhanHe"] = canon((m.group(2) if m and m.group(2) else o["PhanHe"]).upper(), PHAN_HE)
        rec["GioiTinh"] = canon(o["GioiTinh"], ("Nam", "Nữ"))
        rec["CheDo"] = canon(o["CheDo"], ("Nội trú", "Bán trú", "Ngoại trú"))
        phone = services.normalize_phone(o["SDT"])
        rec["SDT"] = phone if re.fullmatch(r"0\d{9,10}", phone) else o["SDT"]
        if rec["SDT"] != phone:
            stats["SĐT không hợp lệ (giữ nguyên)"] += 1
        rec["TenLienHe"] = person(o["TenLienHe"])
        rec["NguoiGioiThieu"] = person(o["NguoiGioiThieu"])
        rec["Nguon"] = canon(o["Nguon"], NGUON)
        rec["TrangThai"] = canon(o["TrangThai"], TRANG_THAI) or "Tư vấn"
        rec["TinhTrang"] = canon(o["TinhTrang"], TINH_TRANG)
        rec["GhiChu"] = o["GhiChu"]
        rec["NguoiNhanHoSo"] = person(o["NguoiNhanHoSo"])
        # --- ngày, điểm
        for k in ("NgayLienHe", "NgaySinh"):
            d = pd.to_datetime(o[k], errors="coerce")
            rec[k] = d.date() if pd.notna(d) else None
        for k in ("Toan1", "Van1", "Anh1", "TV1", "Toan2", "Van2", "Anh2", "TV2"):
            rec[k] = pd.to_numeric(o[k].replace(",", "."), errors="coerce")
        rec["HanhKiem1"], rec["HanhKiem2"] = o["HanhKiem1"], o["HanhKiem2"]
        # --- giữ chỗ / kế toán
        tien = pd.to_numeric(o["SoTienXacNhan"], errors="coerce")
        rec["SoTienXacNhan"] = tien if pd.notna(tien) and tien > 0 else None
        if rec["TinhTrang"] == "Hủy giữ chỗ":
            rec["GiuCho"] = "Hủy giữ chỗ"
        elif rec["SoTienXacNhan"]:
            rec["GiuCho"] = "Đã giữ chỗ"
        else:
            rec["GiuCho"] = "Chưa giữ chỗ"
        rec["NguoiXacNhan"] = person(o["NguoiXacNhan"])
        rec["TenChuTaiKhoan"] = person(o["TenChuTaiKhoan"])
        rec["NganHang"] = bank(o["NganHang"])
        rec["SoTaiKhoan"] = re.sub(r"\s+", "", o["SoTaiKhoan"])

        # --- trường cũ: tỉnh → quận/huyện cũ → trường → phường/xã mới
        tinh_raw, huyen_raw = o["_TinhCu"], o["_HuyenCu"]
        if " - " in tinh_raw and not huyen_raw:  # "Tây Ninh - Bến Cầu", "Cẩm My - Đồng Nai"
            a, b = [x.strip() for x in tinh_raw.split(" - ", 1)]
            if geo.tinh(a)[0]:
                tinh_raw, huyen_raw = a, b
            elif geo.tinh(b)[0]:
                tinh_raw, huyen_raw = b, a
        tinh, prov_code = geo.tinh(tinh_raw)
        dist = geo.huyen(huyen_raw, prov_code, tinh) if huyen_raw else None
        if dist and not tinh:  # suy ra tỉnh từ quận/huyện
            prov_code = dist[0]
            tinh = geo.old_to_new.get(prov_code, "")
        wards = geo.wards_of_district.get(dist) if dist else None
        ten_raw = clean_school(o["TruongCu"])
        hit, how = schools.match(ten_raw, tinh, wards, rec["Khoi"], region) if ten_raw \
            else (None, "")
        rec["TruongCu"] = hit["ten"] if hit else full_school_name(ten_raw)
        rec["TruongCu_Tinh"] = hit["tinh"] if hit else tinh
        rec["TruongCu_PhuongXa"] = hit["xa"] if hit else ""
        dia_chi_cu = ", ".join(x for x in [
            dist[1] if dist else huyen_raw,
            geo.old_prov.get(prov_code, tinh_raw) if (prov_code or tinh_raw) else ""] if x)
        rec["TruongCu_DiaChiCu"] = dia_chi_cu
        status = ("khớp danh mục" if how == "exact" else
                  "khớp gần đúng — nên kiểm tra" if how == "fuzzy" else
                  "không có tên trường" if not ten_raw else "chưa khớp — kiểm tra tay")
        stats[status] += 1
        stats["Có Tỉnh/Thành (mới)" if rec["TruongCu_Tinh"] else "Không xác định được tỉnh"] += 1
        if dist:
            stats["Nhận diện được quận/huyện cũ"] += 1
        elif huyen_raw:
            stats["Quận/huyện ghi không rõ"] += 1
        report.append({"Dòng": i + 2, "Họ tên HS": rec["HoTenHS"],
                       "Trường cũ (gốc)": o["TruongCu"], "Quận huyện (gốc)": huyen_raw,
                       "Tỉnh (gốc)": o["_TinhCu"], "Trường cũ (chuẩn)": rec["TruongCu"],
                       "Phường/Xã mới": rec["TruongCu_PhuongXa"],
                       "Tỉnh/Thành mới": rec["TruongCu_Tinh"],
                       "Quận/huyện, tỉnh cũ": dia_chi_cu, "Kết quả": status,
                       "Khối (gốc)": o["Khoi"], "Khối": rec["Khoi"], "Phân hệ": rec["PhanHe"],
                       "Ngân hàng (gốc)": o["NganHang"], "Ngân hàng": rec["NganHang"]})
        out.append(rec)

    write_workbook(args.out, out, report, stats)
    print(f"Đã ghi {args.out}: {len(out)} dòng")
    print(dict(stats))


# ------------------------------------------------------------------ xuất Excel
def columns():
    """Thứ tự cột của list mới: (tên nội bộ, tên hiển thị, kiểu SharePoint, lựa chọn, bắt buộc)."""
    type_name = {DATE: "Ngày (Date only)", NUMBER: "Số", "note": "Nhiều dòng văn bản",
                 "choice": "Lựa chọn (cho phép nhập giá trị khác)", "text": "Một dòng văn bản",
                 "bool": "Có/Không"}
    cols = [("Title", "Tiêu đề (Họ tên HS)", "Một dòng văn bản", "", "Có")]
    for f in TUYEN_SINH.fields:
        if isinstance(f.options, tuple):
            choices = ", ".join(f.options)
        elif f.options == "@nam_hoc":
            from tuyensinh import config

            choices = ", ".join(config.school_years())
        else:
            choices = "Theo danh mục địa giới / trường học" if f.options else ""
        kind = type_name.get(f.type, "Một dòng văn bản")
        if f.type == "choice" and not isinstance(f.options, tuple):
            kind = "Một dòng văn bản"  # danh mục lớn (tỉnh, xã, trường) lưu dạng văn bản
        cols.append((f.key, f.label, kind, choices, "Có" if f.required else ""))
    return cols


def write_workbook(path, rows, report, stats):
    from openpyxl.utils import get_column_letter
    from openpyxl.worksheet.table import Table, TableStyleInfo

    cols = columns()
    keys = [c[0] for c in cols]
    df = pd.DataFrame(rows)[keys]
    old_by_key = {v: k for k, v in OLD_COLS.items()}
    with pd.ExcelWriter(path, engine="openpyxl") as xw:
        pd.DataFrame({"Hướng dẫn": HUONG_DAN}).to_excel(xw, sheet_name="Huong_dan", index=False)
        df.to_excel(xw, sheet_name="Data_TuyenSinh", index=False)
        pd.DataFrame(cols, columns=["Tên cột (nội bộ)", "Tên hiển thị", "Kiểu cột",
                                    "Lựa chọn", "Bắt buộc"]).assign(
            **{"Cột cũ": [old_by_key.get(k, "Trường cũ_Quận huyện" if k == "TruongCu_PhuongXa"
                                          else "") for k in keys]}
        ).to_excel(xw, sheet_name="Cau_truc_cot", index=False)
        pd.DataFrame(report).to_excel(xw, sheet_name="Bao_cao_chuan_hoa", index=False)
        pd.DataFrame([{"Chỉ số": k, "Số dòng": v} for k, v in stats.items() if k]).to_excel(
            xw, sheet_name="Thong_ke", index=False)

        ws = xw.sheets["Data_TuyenSinh"]
        n = len(df) + 1
        tab = Table(displayName="Data_TuyenSinh", ref=f"A1:{get_column_letter(len(keys))}{n}")
        tab.tableStyleInfo = TableStyleInfo(name="TableStyleMedium2", showRowStripes=True)
        ws.add_table(tab)
        ws.freeze_panes = "C2"
        for j, k in enumerate(keys, start=1):
            letter = get_column_letter(j)
            ws.column_dimensions[letter].width = 26 if k in ("HoTenHS", "TruongCu", "GhiChu",
                                                              "TruongCu_DiaChiCu") else 15
            kind = TUYEN_SINH.get(k).type if k in TUYEN_SINH.keys else "text"
            for cell in ws[letter][1:]:
                if kind == DATE:
                    cell.number_format = "DD/MM/YYYY"
                elif kind == NUMBER:
                    cell.number_format = "#,##0.##"
                else:
                    cell.number_format = "@"  # giữ số 0 đầu SĐT, số tài khoản
        for name in ("Cau_truc_cot", "Bao_cao_chuan_hoa", "Huong_dan", "Thong_ke"):
            s = xw.sheets[name]
            for col in s.columns:
                s.column_dimensions[col[0].column_letter].width = 30 if name != "Huong_dan" else 120
            s.freeze_panes = "A2"


HUONG_DAN = [
    f"File chuẩn hóa ngày {date.today():%d/%m/%Y} từ dữ liệu Data tuyển sinh cũ.",
    "",
    "CÁCH 1 (khuyên dùng) — tạo list bằng app, đúng kiểu cột và tên hiển thị:",
    "  1. Trong .streamlit/secrets.toml đặt SP_LIST_Data_TuyenSinh = \"Data_TuyenSinh\" (tên list mới).",
    "  2. python scripts/setup_sharepoint.py        → tạo list Data_TuyenSinh + Data_NhapHoc.",
    "  3. python scripts/import_excel.py tuyensinh Data_TuyenSinh_chuan_hoa.xlsx --nam-hoc 2026-2027",
    "     (cột Năm học trong file được giữ nguyên; --nam-hoc chỉ dùng cho dòng trống).",
    "",
    "CÁCH 2 — tạo list trực tiếp trên SharePoint từ Excel:",
    "  1. Mở site tuyensinh2 → Mới → Danh sách → Từ Excel → tải file này lên.",
    "  2. Chọn bảng \"Data_TuyenSinh\". Kiểm tra kiểu cột theo sheet Cau_truc_cot:",
    "     NgayLienHe, NgaySinh = Ngày; SoTienXacNhan và điểm = Số; còn lại = Một dòng văn bản",
    "     (GhiChu = Nhiều dòng văn bản). SĐT, Số tài khoản PHẢI là văn bản để giữ số 0 đầu.",
    "  3. Đặt tên list: Data_TuyenSinh → Tạo.",
    "  4. (Tùy chọn) Đổi tên hiển thị cột theo cột \"Tên hiển thị\" — tên nội bộ không đổi nên",
    "     app vẫn nhận đúng. Không đổi tên cột trong Excel trước khi tạo list.",
    "",
    "Sheet Bao_cao_chuan_hoa: so sánh giá trị gốc và giá trị chuẩn hóa từng dòng.",
    "  Lọc cột Kết quả = \"chưa khớp — kiểm tra tay\" để rà các trường chưa tìm thấy trong danh mục.",
    "  Cột TruongCu_DiaChiCu giữ quận/huyện, tỉnh cũ (trước sáp nhập) để tra cứu.",
    "",
    "Thay đổi so với list cũ:",
    "  - Khối \"10-IEP\" tách thành Khoi = 10 và PhanHe = IEP.",
    "  - Tình trạng giữ nguyên ý nghĩa tư vấn; thêm cột GiuCho (Chưa giữ chỗ / Đã giữ chỗ /",
    "    Hủy giữ chỗ / Đã hoàn phí) suy ra từ Số tiền xác nhận và Tình trạng.",
    "  - Trường cũ_Quận huyện → TruongCu_PhuongXa (Phường/Xã mới) + TruongCu_DiaChiCu.",
    "  - Tỉnh cũ → tỉnh/thành mới (34 đơn vị). Ngân hàng, Nguồn, SĐT, họ tên được chuẩn hóa.",
]


if __name__ == "__main__":
    main()
