"""Nghiệp vụ tuyển sinh — tách khỏi giao diện để dễ kiểm thử."""
from __future__ import annotations

import re
from functools import lru_cache
from datetime import date

import pandas as pd

from .schema import BOOL, DATE, GIAY_TO_NHAP_HOC, NHAP_HOC, NUMBER, TUYEN_SINH, ListDef
from .storage.base import Storage


def today() -> str:
    return date.today().isoformat()


def _empty(v) -> bool:
    return v is None or v is pd.NaT or (isinstance(v, float) and pd.isna(v)) or v == ""


def normalize_phone(v: str | None) -> str:
    digits = re.sub(r"\D", "", str(v or ""))
    if digits.startswith("84") and len(digits) == 11:
        digits = "0" + digits[2:]
    return digits


def phone_query(q: str) -> str:
    """Ô tìm kiếm là SĐT (chỉ số, dấu cách, +, -, .) → SĐT chuẩn hóa; ngược lại "".
    Tránh "Đồng Bộ 772" khớp mọi SĐT có "772"."""
    q = (q or "").strip()
    return normalize_phone(q) if q and re.fullmatch(r"[\d\s+().-]+", q) else ""


def validate(ld: ListDef, data: dict) -> list[str]:
    errors = []
    for f in ld.fields:
        v = data.get(f.key)
        if f.required and (_empty(v) or str(v).strip() == ""):
            errors.append(f"Chưa nhập **{f.label}**")
        elif f.type == NUMBER and not _empty(v):
            try:
                float(v)
            except (TypeError, ValueError):
                errors.append(f"**{f.label}** phải là số")
    if ld is TUYEN_SINH and data.get("SDT"):
        if not re.fullmatch(r"0\d{9,10}", normalize_phone(data["SDT"])):
            errors.append("**SĐT** không hợp lệ (10–11 số, bắt đầu bằng 0)")
    return errors


def to_df(ld: ListDef, items: list[dict]) -> pd.DataFrame:
    cols = ["id"] + ld.keys + ["Created", "Modified"]
    df = pd.DataFrame(items).reindex(columns=cols).copy()
    for f in ld.fields:
        if f.type == NUMBER:  # để trống = NaN (khác 0)
            df[f.key] = pd.to_numeric(df[f.key], errors="coerce")
        elif f.type == BOOL:
            df[f.key] = df[f.key].fillna(False).astype(bool)
        elif f.type == DATE:
            df[f.key] = pd.to_datetime(df[f.key], errors="coerce").dt.date
        else:
            df[f.key] = df[f.key].fillna("").astype(str)
    return df


def load_df(storage: Storage, ld: ListDef, nam_hoc: str | None = None) -> pd.DataFrame:
    df = to_df(ld, storage.list_items(ld.name))
    if nam_hoc:
        df = df[df["NamHoc"] == nam_hoc]
    return df.reset_index(drop=True)


def _clean(ld: ListDef, data: dict) -> dict:
    out = {}
    for f in ld.fields:
        if f.key not in data:
            continue
        v = data[f.key]
        if f.type == DATE:
            if _empty(v):
                v = ""
            else:
                v = v.isoformat()[:10] if isinstance(v, date) else str(v or "")[:10]
        elif f.type == NUMBER:
            v = "" if _empty(v) else float(v)
        elif f.type == BOOL:
            v = bool(v)
        else:
            v = "" if v is None else str(v).strip()
        out[f.key] = v
    return out


# ------------------------------------------------------------------ Tuyển sinh
def find_duplicates(source, data: dict, exclude_id: str | None = None) -> list[dict]:
    """HS trùng SĐT + họ tên trong cùng năm học.

    `source`: Storage hoặc danh sách bản ghi đã tải sẵn (tránh đọc lại cả list)."""
    phone = normalize_phone(data.get("SDT"))
    name = str(data.get("HoTenHS", "")).strip().lower()
    items = source.list_items(TUYEN_SINH.name) if hasattr(source, "list_items") else source
    return [
        it for it in items
        if it.get("NamHoc") == data.get("NamHoc") and it["id"] != exclude_id
        and normalize_phone(it.get("SDT")) == phone
        and str(it.get("HoTenHS", "")).strip().lower() == name
    ]


def save_tuyen_sinh(storage: Storage, data: dict, item_id: str | None = None) -> dict:
    data = dict(data)
    data.setdefault("TrangThai", "Tư vấn")
    if data.get("SDT"):
        data["SDT"] = normalize_phone(data["SDT"])
    errors = validate(TUYEN_SINH, data)
    if errors:
        raise ValueError("\n".join(errors))
    clean = _clean(TUYEN_SINH, data)
    if item_id:
        old = storage.get_item(TUYEN_SINH.name, item_id) or {}
        rec = storage.update_item(TUYEN_SINH.name, item_id, clean)
        if old.get("TrangThai") != rec.get("TrangThai"):
            rec = set_trang_thai(storage, item_id, rec["TrangThai"])
        elif rec.get("TrangThai") == "Nhập học":
            sync_nhap_hoc(storage, rec)
        return rec
    rec = storage.create_item(TUYEN_SINH.name, clean)
    if rec.get("TrangThai") != "Tư vấn":
        rec = set_trang_thai(storage, rec["id"], rec["TrangThai"])
    return rec


def set_trang_thai(storage: Storage, item_id: str, trang_thai: str,
                   ly_do: str | None = None, nguoi: str = "") -> dict:
    """Chuyển "Bước": Tư vấn → Nộp hồ sơ → Nhập học, hoặc Rút hồ sơ.

    Khi chuyển sang "Nhập học" sẽ tạo hồ sơ trong Data_NhapHoc (nếu chưa có).
    Lý do rút hồ sơ được ghi thêm vào "Nội dung đã trao đổi".
    """
    rec = storage.get_item(TUYEN_SINH.name, item_id)
    if rec is None:
        raise KeyError(item_id)
    upd = {"TrangThai": trang_thai}
    if trang_thai == "Nộp hồ sơ" and nguoi and not rec.get("NguoiNhanHoSo"):
        upd["NguoiNhanHoSo"] = nguoi
    if ly_do:
        note = f"{date.today():%d/%m/%Y} rút hồ sơ: {ly_do}"
        upd["GhiChu"] = f"{rec.get('GhiChu') or ''}\n{note}".strip()
    rec = storage.update_item(TUYEN_SINH.name, item_id, upd)
    if trang_thai == "Nhập học":
        sync_nhap_hoc(storage, rec)
    return rec


def nhap_hoc_of(storage: Storage, tuyen_sinh_id: str) -> dict | None:
    for it in storage.list_items(NHAP_HOC.name):
        if str(it.get("TuyenSinhID")) == str(tuyen_sinh_id):
            return it
    return None


def _che_do_to_vemis(che_do: str) -> str:
    return che_do if che_do in ("Nội trú", "Bán trú") else ""


def nhap_hoc_prefill(ts: dict) -> dict:
    """Thông tin hồ sơ nhập học lấy sẵn từ bản ghi tuyển sinh."""
    return {
        "TuyenSinhID": ts["id"],
        "NamHoc": ts.get("NamHoc", ""),
        "LopHoc": ts.get("Khoi", ""),
        "Khoi": ts.get("Khoi", ""),
        "PhanHe": ts.get("PhanHe", ""),
        "TinhTrangHS": "Đang nhập hồ sơ",
        "HoTen": ts.get("HoTenHS", ""),
        "NgaySinh": ts.get("NgaySinh", ""),
        "GioiTinh": ts.get("GioiTinh", ""),
        "NgayVaoTruong": today(),
        "NoiTruBanTru": _che_do_to_vemis(ts.get("CheDo", "")),
        "DienThoaiSLL": ts.get("SDT", ""),
        "TruongCu": ts.get("TruongCu", ""),
        "TruongCu_PhuongXa": ts.get("TruongCu_PhuongXa", ""),
        "TruongCu_Tinh": ts.get("TruongCu_Tinh", ""),
        "QuocTich": "Việt Nam",
        "DanToc": "Kinh",
        "TonGiao": "Không",
        "DienChinhSach": "Không",
    }


def sync_nhap_hoc(storage: Storage, ts: dict) -> dict:
    """Tạo (hoặc bổ sung thông tin còn trống) hồ sơ nhập học từ bản ghi tuyển sinh."""
    prefill = nhap_hoc_prefill(ts)
    cur = nhap_hoc_of(storage, ts["id"])
    if cur is None:
        return storage.create_item(NHAP_HOC.name, _clean(NHAP_HOC, prefill))
    missing = {k: v for k, v in prefill.items() if v and not cur.get(k)}
    return storage.update_item(NHAP_HOC.name, cur["id"], _clean(NHAP_HOC, missing)) if missing else cur


def tao_ho_so_hang_loat(storage: Storage, ts_records: list[dict], workers: int = 4,
                        progress=None) -> int:
    """Tạo hồ sơ nhập học cho nhiều HS: đọc Data_NhapHoc 1 lần, tạo các hồ sơ còn thiếu song song
    (mỗi thao tác là 1 lần gọi flow Power Automate — làm tuần tự sẽ rất chậm)."""
    from concurrent.futures import ThreadPoolExecutor

    co_roi = {str(it.get("TuyenSinhID")) for it in storage.list_items(NHAP_HOC.name)}
    todo = [ts for ts in ts_records if str(ts["id"]) not in co_roi]
    done = 0
    with ThreadPoolExecutor(max_workers=max(1, workers)) as pool:
        for _ in pool.map(lambda ts: storage.create_item(
                NHAP_HOC.name, _clean(NHAP_HOC, nhap_hoc_prefill(ts))), todo):
            done += 1
            if progress:
                progress(done, len(todo))
    return done


def save_nhap_hoc(storage: Storage, data: dict, item_id: str | None = None) -> dict:
    errors = validate(NHAP_HOC, data)
    if errors:
        raise ValueError("\n".join(errors))
    clean = _clean(NHAP_HOC, data)
    if item_id:
        return storage.update_item(NHAP_HOC.name, item_id, clean)
    return storage.create_item(NHAP_HOC.name, clean)


def cap_nhat_nhap_hoc(storage: Storage, item_id: str, data: dict) -> dict:
    """Cập nhật một phần hồ sơ (xếp lớp, thu hồ sơ, học phí, xe…) — không kiểm tra bắt buộc."""
    return storage.update_item(NHAP_HOC.name, item_id, _clean(NHAP_HOC, data))


_GIAY_TO_ALIAS = {"phieu dk nhap hoc": "Phiếu đăng ký nhập học",
                  "thoa thuan voi nha truong":
                      "Thỏa thuận của Cha mẹ/Người giám hộ học sinh với nhà trường",
                  "chung nhan tot nghiep thcs tam thoi": "Giấy chứng nhận tốt nghiệp THCS tạm thời",
                  "giay gioi thieu chuyen truong cua phong gd/so gd":
                      "Giấy giới thiệu chuyển trường của UBND/Sở GD&ĐT",
                  "giay gioi thieu chuyen truong cua ubnd/so":
                      "Giấy giới thiệu chuyển trường của UBND/Sở GD&ĐT"}


@lru_cache(maxsize=1)
def _giay_to_theo_khoi() -> dict[str, list[str]]:
    import json
    from pathlib import Path

    path = Path(__file__).parent / "data" / "giay_to_theo_khoi.json"
    return json.loads(path.read_text(encoding="utf-8"))["theo_khoi"]


def giay_to_can_nop(khoi: str | None, phan_he: str | None = None) -> list[str]:
    """Giấy tờ cần nộp khi nhập học theo khối (và phân hệ IEP/ESL).

    Không có đúng "khối-phân hệ" thì lấy "khối", rồi danh sách đầu tiên của khối đó."""
    bang = _giay_to_theo_khoi()
    khoi = str(khoi or "").strip()
    ph = str(phan_he or "").strip().upper()
    for key in (f"{khoi}-{ph}" if ph else None, khoi):
        if key and key in bang:
            return list(bang[key])
    cung_khoi = [k for k in bang if k.split("-")[0] == khoi]
    return list(bang[cung_khoi[0]]) if cung_khoi else []


def doc_ho_so(text: str) -> tuple[date | None, dict[str, str]]:
    """ "Ngày đã nộp 23/06/2025\nGiấy khai sinh - Bản sao…" -> (ngày, {giấy tờ: bản gốc/sao})."""
    from . import danh_muc

    ngay, docs = None, {}
    known = {danh_muc.fold(g): g for g in GIAY_TO_NHAP_HOC}
    for line in str(text or "").splitlines():
        line = line.strip()
        m = re.match(r"ng[aà]y đã nộp\s+(\d{1,2})/(\d{1,2})/(\d{4})", line, re.I)
        if m:
            d, mth, y = map(int, m.groups())
            try:
                ngay = date(y, mth, d)
            except ValueError:
                pass
            continue
        if not line:
            continue
        name, _, ban = line.rpartition(" -") if " -" in line else (line, "", "")
        name = name.strip()
        key = danh_muc.fold(name)
        name = known.get(key) or _GIAY_TO_ALIAS.get(key) or name
        docs[name] = ban.strip() or "Bản gốc"
    return ngay, docs


def tien_do_giay_to(rec: dict) -> tuple[list[str], dict[str, str], list[str]]:
    """(giấy tờ cần nộp theo khối, giấy tờ đã nộp {tên: bản}, giấy tờ còn thiếu)."""
    can = giay_to_can_nop(rec.get("Khoi"), rec.get("PhanHe"))
    da = doc_ho_so(rec.get("HoSoDaNop"))[1]
    return can, da, [g for g in can if g not in da]


def ghi_ho_so(ngay: date | None, docs: dict[str, str]) -> str:
    lines = [f"Ngày đã nộp {ngay:%d/%m/%Y}"] if ngay else []
    return "\n".join(lines + [f"{g} - {ban}" for g, ban in docs.items()])


def rut_ho_so_nhap_hoc(storage: Storage, rec: dict, ly_do: str, nguoi: str = "") -> dict:
    """Rút hồ sơ sau khi đã nhập học: đánh dấu hồ sơ và chuyển Data tuyển sinh sang Rút hồ sơ."""
    note = f"{date.today():%d/%m/%Y} rút hồ sơ" + (f" ({nguoi})" if nguoi else "") + \
        (f": {ly_do}" if ly_do else "")
    out = cap_nhat_nhap_hoc(storage, rec["id"], {
        "TinhTrangHS": "Rút hồ sơ", "GhiChu": f"{rec.get('GhiChu') or ''}\n{note}".strip()})
    if rec.get("TuyenSinhID") and storage.get_item(TUYEN_SINH.name, rec["TuyenSinhID"]):
        set_trang_thai(storage, rec["TuyenSinhID"], "Rút hồ sơ", ly_do or "rút sau nhập học",
                       nguoi)
    return out


def nhap_hoc_df(storage: Storage, nam_hoc: str) -> pd.DataFrame:
    """Hồ sơ nhập học của năm, bỏ các HS đã rút hồ sơ sau khi nhập học."""
    df = load_df(storage, NHAP_HOC, nam_hoc)
    ts = load_df(storage, TUYEN_SINH)
    rut = set(ts.loc[ts["TrangThai"] == "Rút hồ sơ", "id"])
    return df[~df["TuyenSinhID"].isin(rut)].reset_index(drop=True)


# ------------------------------------------------------------------ Kế toán (giữ chỗ)
def xac_nhan_giu_cho(storage: Storage, item_id: str, so_tien, nguoi: str,
                     tinh_trang: str = "Đã giữ chỗ", **bank) -> dict:
    """Kế toán xác nhận số tiền giữ chỗ (ghi vào các cột có sẵn của Data tuyển sinh)."""
    if tinh_trang == "Đã giữ chỗ" and (_empty(so_tien) or float(so_tien) <= 0):
        raise ValueError("**Số tiền xác nhận** phải lớn hơn 0")
    upd = {"GiuCho": tinh_trang, "NguoiXacNhan": nguoi}
    if not _empty(so_tien):
        upd["SoTienXacNhan"] = float(so_tien)
    upd.update({k: v for k, v in bank.items()
                if k in ("TenChuTaiKhoan", "NganHang", "SoTaiKhoan")})
    return storage.update_item(TUYEN_SINH.name, item_id, _clean(TUYEN_SINH, upd))


def giu_cho_summary(ts: pd.DataFrame) -> pd.DataFrame:
    """Tổng hợp giữ chỗ theo khối: số HS và số tiền theo từng tình trạng."""
    d = ts.assign(GiuCho=ts["GiuCho"].replace("", "Chưa giữ chỗ"),
                  SoTien=ts["SoTienXacNhan"].fillna(0))
    so_hs = pd.crosstab(d["Khoi"], d["GiuCho"])
    tien = d[d["GiuCho"] == "Đã giữ chỗ"].groupby("Khoi")["SoTien"].sum()
    out = so_hs.assign(**{"Tiền đã giữ chỗ": tien}).fillna(0)
    out.index.name = "Khối"
    return out.reset_index()


# ------------------------------------------------------------------ Mức hoàn thiện hồ sơ nhập học
# Các thông tin tối thiểu để nộp dữ liệu lên VEMIS / CSDL ngành
NHAP_HOC_CAN_CO = ["LopHoc", "HoTen", "NgaySinh", "GioiTinh", "DanToc", "QuocTich",
                   "ChoO_Tinh", "ChoO_Xa", "NoiSinh_Tinh", "TenCha", "TenMe", "DienThoaiSLL"]


NHAP_HOC_NHAN_NGAN = {"LopHoc": "Lớp", "HoTen": "Họ tên", "NgaySinh": "Ngày sinh",
                      "GioiTinh": "Giới tính", "DanToc": "Dân tộc", "QuocTich": "Quốc tịch",
                      "ChoO_Tinh": "Tỉnh (chỗ ở)", "ChoO_Xa": "Xã (chỗ ở)",
                      "NoiSinh_Tinh": "Nơi sinh", "TenCha": "Tên cha", "TenMe": "Tên mẹ",
                      "DienThoaiSLL": "SĐT liên lạc"}


def missing_fields(row: dict) -> list[str]:
    return [k for k in NHAP_HOC_CAN_CO if _empty(row.get(k)) or str(row.get(k)).strip() == ""]


def completeness(df: pd.DataFrame) -> pd.Series:
    """Tỷ lệ (0–1) thông tin tối thiểu đã có của từng hồ sơ nhập học."""
    if df.empty:
        return pd.Series(dtype=float)
    return df.apply(lambda r: 1 - len(missing_fields(r)) / len(NHAP_HOC_CAN_CO), axis=1)
