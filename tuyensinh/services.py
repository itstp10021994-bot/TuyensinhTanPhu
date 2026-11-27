"""Nghiệp vụ tuyển sinh — tách khỏi giao diện để dễ kiểm thử."""
from __future__ import annotations

import re
from functools import lru_cache
from datetime import date

import pandas as pd

from .schema import (BOOL, DATE, GIAY_TO_NHAP_HOC, NHAP_HOC, NUMBER, RUT_HO_SO, TUYEN_SINH,
                     ListDef)
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
            df[f.key] = df[f.key].astype(object).fillna(False).astype(bool)
        elif f.type == DATE:
            df[f.key] = pd.to_datetime(df[f.key], errors="coerce").dt.date
        else:
            df[f.key] = df[f.key].astype(object).fillna("").astype(str)
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
        if "CheDo" in clean and old.get("CheDo") != rec.get("CheDo"):
            _che_do_tu_tuyen_sinh(storage, rec)
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
                   ly_do: str | None = None, nguoi: str = "", luu_tru: bool = True) -> dict:
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
    buoc_cu = rec.get("TrangThai")
    rec = storage.update_item(TUYEN_SINH.name, item_id, upd)
    if trang_thai == "Nhập học":
        sync_nhap_hoc(storage, rec)
    if trang_thai == "Rút hồ sơ" and luu_tru and buoc_cu != "Rút hồ sơ":
        _luu_tru_an_toan(storage, ts={**rec, "TrangThai": buoc_cu},
                         nh=nhap_hoc_of(storage, item_id), ly_do=ly_do or "", nguoi=nguoi)
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


# ------------------------------------------------------------------ lên lớp (HS cũ sang năm mới)
# Trường chỉ đúng cho một năm học: không chép sang hồ sơ năm mới
KHONG_CHEP_LEN_LOP = {"id", "Created", "Modified", "TuyenSinhID", "NamHoc", "LopHoc", "Khoi",
                      "TinhTrangHS", "LopCu", "NgayNhanHoSo", "SoTienThanhToan",
                      "SoTienConLai", "TongDaThu", "NgayDongPhi", "KeToanXacNhan",
                      "NguoiNhanHoSo", "NguoiCapNhat", "GhiChu"}
DA_NGHI = ("Rút hồ sơ", "Không học tiếp")


def _khoa_hs(r: dict) -> tuple:
    from .danh_muc import fold
    return (fold(r.get("HoTen")), str(r.get("NgaySinh") or "")[:10])


def lop_goi_y(lop_cu: str, khoi_moi: str) -> str:
    """6A1 -> 7A1 (đổi số khối ở đầu tên lớp); lớp không theo dạng đó thì để trống."""
    m = re.match(r"^(\d{1,2})(.*)$", str(lop_cu or "").strip())
    return f"{khoi_moi}{m.group(2)}" if m and khoi_moi else ""


def ds_len_lop(items: list[dict], nam_cu: str, nam_moi: str, khoi_cuoi: int = 12,
               goi_y_lop: bool = False, rut_ids: set | None = None) -> list[dict]:
    """Học sinh năm cũ sẽ lên lớp sang năm mới (đang học, chưa có hồ sơ năm mới, chưa học
    khối cuối). Mỗi dòng: dữ liệu hồ sơ năm mới + "_ly_do" nếu bị loại."""
    da_co = {_khoa_hs(r) for r in items if r.get("NamHoc") == nam_moi}
    out = []
    for r in items:
        if r.get("NamHoc") != nam_cu:
            continue
        khoi = str(r.get("Khoi") or "").strip()
        ly_do = ""
        if str(r.get("TinhTrangHS") or "") in DA_NGHI:
            ly_do = f"Đã {str(r.get('TinhTrangHS')).lower()}"
        elif rut_ids and str(r.get("TuyenSinhID") or "") in rut_ids:
            ly_do = "Đã rút hồ sơ"
        elif not khoi.isdigit():
            ly_do = "Chưa có khối"
        elif int(khoi) >= khoi_cuoi:
            ly_do = f"Học xong khối {khoi_cuoi}"
        elif _khoa_hs(r) in da_co:
            ly_do = f"Đã có hồ sơ {nam_moi}"
        moi = {k: v for k, v in r.items() if k not in KHONG_CHEP_LEN_LOP and not _empty(v)}
        khoi_moi = str(int(khoi) + 1) if khoi.isdigit() else ""
        moi.update(NamHoc=nam_moi, Khoi=khoi_moi, LopCu=r.get("LopHoc") or "",
                   TinhTrangHS="Học tiếp",
                   LopHoc=lop_goi_y(r.get("LopHoc"), khoi_moi) if goi_y_lop else "")
        moi["_ly_do"] = ly_do
        moi["_khoi_cu"] = khoi
        out.append(moi)
    return out


def tao_len_lop(storage: Storage, rows: list[dict], nam_moi: str, workers: int = 4,
                progress=None) -> int:
    """Tạo hồ sơ năm mới cho các học sinh lên lớp (bỏ qua em đã có hồ sơ năm mới — chạy lại an
    toàn khi bị ngắt giữa chừng)."""
    from concurrent.futures import ThreadPoolExecutor

    da_co = {_khoa_hs(r) for r in storage.list_items(NHAP_HOC.name)
             if r.get("NamHoc") == nam_moi}
    todo = [{k: v for k, v in r.items() if not k.startswith("_")} for r in rows
            if _khoa_hs(r) not in da_co]
    done = 0
    with ThreadPoolExecutor(max_workers=max(1, workers)) as pool:
        for _ in pool.map(lambda d: storage.create_item(NHAP_HOC.name, _clean(NHAP_HOC, d)),
                          todo):
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
        old = storage.get_item(NHAP_HOC.name, item_id) or {}
        rec = storage.update_item(NHAP_HOC.name, item_id, clean)
        _che_do_tu_nhap_hoc(storage, old, rec)
        return rec
    return storage.create_item(NHAP_HOC.name, clean)


def cap_nhat_nhap_hoc(storage: Storage, item_id: str, data: dict) -> dict:
    """Cập nhật một phần hồ sơ (xếp lớp, thu hồ sơ, học phí, xe…) — không kiểm tra bắt buộc."""
    old = (storage.get_item(NHAP_HOC.name, item_id) or {}) if "NoiTruBanTru" in data else {}
    rec = storage.update_item(NHAP_HOC.name, item_id, _clean(NHAP_HOC, data))
    if "NoiTruBanTru" in data:
        _che_do_tu_nhap_hoc(storage, old, rec)
    return rec


# ------------------------------------------------------------------ đồng bộ chế độ nội / bán trú
def _bo_khoi_phong(storage: Storage, nh_id: str) -> None:
    """Em không còn Nội trú: bỏ khỏi phòng nội trú (list phòng chưa tạo thì bỏ qua)."""
    from . import noi_tru as NT
    from .schema import NOI_TRU_PHONG
    try:
        phongs = storage.list_items(NOI_TRU_PHONG.name)
    except Exception:  # noqa: BLE001 — chưa dùng phân hệ nội trú
        return
    NT.bo_khoi_phong(storage, phongs, [str(nh_id)])


def _che_do_tu_nhap_hoc(storage: Storage, old: dict, rec: dict) -> None:
    """Đổi N.trú, B.trú ở hồ sơ nhập học -> Chế độ của liên hệ Data tuyển sinh + phòng nội trú."""
    from . import noi_tru as NT
    cu, moi = NT.nhom_che_do(old.get("NoiTruBanTru")), NT.nhom_che_do(rec.get("NoiTruBanTru"))
    if cu == moi:
        return
    tid = str(rec.get("TuyenSinhID") or "").strip()
    if moi and tid:
        ts = storage.get_item(TUYEN_SINH.name, tid)
        if ts and ts.get("CheDo") != moi:
            storage.update_item(TUYEN_SINH.name, tid, {"CheDo": moi})
    if cu == "Nội trú":
        _bo_khoi_phong(storage, rec["id"])


def _che_do_tu_tuyen_sinh(storage: Storage, ts: dict) -> None:
    """Đổi Chế độ ở Data tuyển sinh -> N.trú, B.trú của hồ sơ nhập học liên kết + phòng."""
    from . import noi_tru as NT
    nh = nhap_hoc_of(storage, ts["id"])
    if nh is None:
        return
    che_do = ts.get("CheDo") or ""
    if che_do not in ("Nội trú", "Bán trú", "Ngoại trú"):
        return
    cu = NT.nhom_che_do(nh.get("NoiTruBanTru"))
    moi = che_do if che_do != "Ngoại trú" else ""
    if cu == moi:
        return
    storage.update_item(NHAP_HOC.name, nh["id"],
                        {"NoiTruBanTru": NT.gia_tri_nh(nh.get("NoiTruBanTru"), moi)})
    if cu == "Nội trú":
        _bo_khoi_phong(storage, nh["id"])


_GIAY_TO_ALIAS = {"phieu dk nhap hoc": "Phiếu đăng ký nhập học",
                  "thoa thuan voi nha truong":
                      "Thỏa thuận của Cha mẹ/Người giám hộ học sinh với nhà trường",
                  "chung nhan tot nghiep thcs tam thoi": "Giấy chứng nhận tốt nghiệp THCS tạm thời",
                  "giay gioi thieu chuyen truong cua phong gd/so gd":
                      "Giấy giới thiệu chuyển trường của UBND/Sở GD&ĐT",
                  "giay gioi thieu chuyen truong cua ubnd/so":
                      "Giấy giới thiệu chuyển trường của UBND/Sở GD&ĐT"}


@lru_cache(maxsize=1)
def giay_to_mac_dinh() -> dict[str, list[str]]:
    """Danh mục mặc định (Book1.xlsx) — dùng khi list DanhMuc_GiayTo chưa có dữ liệu."""
    import json
    from pathlib import Path

    path = Path(__file__).parent / "data" / "giay_to_theo_khoi.json"
    return json.loads(path.read_text(encoding="utf-8"))["theo_khoi"]


_GIAY_TO_HIEN_TAI: dict[str, list[str]] | None = None


def dat_giay_to(bang: dict[str, list[str]] | None):
    """App đặt danh mục đang dùng (đọc từ SharePoint); None = dùng mặc định."""
    global _GIAY_TO_HIEN_TAI
    _GIAY_TO_HIEN_TAI = bang or None


def _giay_to_theo_khoi() -> dict[str, list[str]]:
    return _GIAY_TO_HIEN_TAI or giay_to_mac_dinh()


def giay_to_tu_list(items: list[dict]) -> dict[str, list[str]]:
    """Bản ghi list DanhMuc_GiayTo -> {khối: [giấy tờ theo thứ tự]}."""
    rows = []
    for it in items:
        khoi, ten = str(it.get("Khoi") or "").strip(), str(it.get("TenGiayTo") or "").strip()
        if khoi and ten:
            try:
                tt = float(it.get("ThuTu"))
            except (TypeError, ValueError):
                tt = 999.0
            rows.append((khoi, tt, int(it.get("id") or 0), ten))
    out: dict[str, list[str]] = {}
    for khoi, _, _, ten in sorted(rows):
        if ten not in out.setdefault(khoi, []):
            out[khoi].append(ten)
    return out


def luu_giay_to_khoi(storage: Storage, khoi: str, ds: list[str], items: list[dict]) -> int:
    """Ghi danh sách giấy tờ của 1 khối lên list: sửa/thêm/xóa cho khớp `ds`."""
    from .schema import GIAY_TO

    khoi = khoi.strip()
    cu = sorted([it for it in items if str(it.get("Khoi") or "").strip() == khoi],
                key=lambda it: int(it.get("id") or 0))
    n = 0
    for i, ten in enumerate(ds):
        data = {"Khoi": khoi, "TenGiayTo": ten, "ThuTu": i + 1}
        if i < len(cu):
            it = cu[i]
            if (str(it.get("TenGiayTo")) != ten or str(it.get("ThuTu")).split(".")[0]
                    != str(i + 1)):
                storage.update_item(GIAY_TO.name, it["id"], data)
                n += 1
        else:
            storage.create_item(GIAY_TO.name, data)
            n += 1
    for it in cu[len(ds):]:
        storage.delete_item(GIAY_TO.name, it["id"])
        n += 1
    return n


def giay_to_can_nop(khoi: str | None, phan_he: str | None = None) -> list[str]:
    """Giấy tờ cần nộp khi nhập học theo khối (và phân hệ IEP/ESL).

    Không có đúng "khối-phân hệ" thì lấy "khối", rồi danh sách đầu tiên của khối đó."""
    bang = _giay_to_theo_khoi()
    khoi = str(khoi or "").strip()
    ph = str(phan_he or "").strip().upper()
    for key in (f"{khoi}-{ph}" if ph else None, khoi):
        if key and key in bang:
            return list(bang[key])
    cung_khoi = sorted([k for k in bang if k.split("-")[0] == khoi],
                       key=lambda k: (not k.endswith("-IEP"), k))  # ưu tiên IEP
    return list(bang[cung_khoi[0]]) if cung_khoi else []


# Dòng ghi chú tình trạng bổ sung trong ô "Hồ sơ đã nộp" (không phải tên giấy tờ)
_DONG_BO_SUNG = re.compile(r"^(đã thu đủ|cần bổ sung\s*:|hạn bổ sung)", re.I)


def doc_bo_sung(text: str) -> tuple[str, list[str], date | None]:
    """Tình trạng bổ sung ghi khi thu hồ sơ: ("du" | "bo_sung" | "", giấy tờ cần bổ sung, hạn)."""
    tt, ds, han = "", [], None
    for line in str(text or "").splitlines():
        line = line.strip()
        if re.match(r"^đã thu đủ", line, re.I):
            tt = "du"
        elif re.match(r"^cần bổ sung\s*:", line, re.I):
            tt = "bo_sung"
            ds = [x.strip() for x in line.split(":", 1)[1].split(";") if x.strip()]
        else:
            m = re.match(r"^hạn bổ sung\s+(\d{1,2})/(\d{1,2})/(\d{4})", line, re.I)
            if m:
                d, mth, y = map(int, m.groups())
                try:
                    han = date(y, mth, d)
                except ValueError:
                    pass
    return tt, ds, han


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
        if not line or _DONG_BO_SUNG.match(line):
            continue
        name, _, ban = line.rpartition(" -") if " -" in line else (line, "", "")
        name = name.strip()
        key = danh_muc.fold(name)
        name = known.get(key) or _GIAY_TO_ALIAS.get(key) or name
        docs[name] = ban.strip() or "Bản gốc"
    return ngay, docs


def la_hs_cu(rec: dict) -> bool:
    """Học sinh cũ (lên lớp / có sẵn từ VEMIS): hồ sơ nhập học không liên kết Data tuyển sinh."""
    v = rec.get("TuyenSinhID")
    return v is None or (isinstance(v, float) and v != v) or not str(v).strip()


def giay_to_cua_hs(rec: dict) -> list[str]:
    """Giấy tờ học sinh này cần nộp: học sinh mới theo danh mục của khối; học sinh cũ không
    phải nộp (đã nộp từ các năm trước)."""
    return [] if la_hs_cu(rec) else giay_to_can_nop(rec.get("Khoi"), rec.get("PhanHe"))


def tien_do_giay_to(rec: dict) -> tuple[list[str], dict[str, str], list[str]]:
    """(giấy tờ cần nộp theo khối, giấy tờ đã nộp {tên: bản}, giấy tờ còn thiếu).
    Học sinh cũ: không có giấy tờ cần nộp."""
    can = giay_to_cua_hs(rec)
    da = doc_ho_so(rec.get("HoSoDaNop"))[1]
    tt, bo_sung, _ = doc_bo_sung(rec.get("HoSoDaNop"))
    if tt == "du":  # tuyển sinh xác nhận đã thu đủ
        return can, da, []
    if tt == "bo_sung":  # chỉ những giấy tờ tuyển sinh chọn cần bổ sung
        return can, da, [g for g in bo_sung if g not in da]
    return can, da, [g for g in can if g not in da]


def ghi_ho_so(ngay: date | None, docs: dict[str, str], bo_sung: list[str] | None = None,
              han: date | None = None, du: bool = False) -> str:
    """Nội dung ô "Hồ sơ đã nộp": ngày, từng giấy tờ - bản, rồi tình trạng bổ sung
    ("Đã thu đủ" hoặc "Cần bổ sung: A; B" + "Hạn bổ sung dd/mm/yyyy")."""
    lines = [f"Ngày đã nộp {ngay:%d/%m/%Y}"] if ngay else []
    lines += [f"{g} - {ban}" for g, ban in docs.items()]
    if du:
        lines.append("Đã thu đủ")
    elif bo_sung:
        lines.append("Cần bổ sung: " + "; ".join(bo_sung))
        if han:
            lines.append(f"Hạn bổ sung {han:%d/%m/%Y}")
    return "\n".join(lines)


def rut_ho_so_nhap_hoc(storage: Storage, rec: dict, ly_do: str, nguoi: str = "") -> dict:
    """Rút hồ sơ sau khi đã nhập học: đánh dấu hồ sơ và chuyển Data tuyển sinh sang Rút hồ sơ."""
    note = f"{date.today():%d/%m/%Y} rút hồ sơ" + (f" ({nguoi})" if nguoi else "") + \
        (f": {ly_do}" if ly_do else "")
    out = cap_nhat_nhap_hoc(storage, rec["id"], {
        "TinhTrangHS": "Rút hồ sơ", "GhiChu": f"{rec.get('GhiChu') or ''}\n{note}".strip()})
    if rec.get("TuyenSinhID") and storage.get_item(TUYEN_SINH.name, rec["TuyenSinhID"]):
        ts = storage.get_item(TUYEN_SINH.name, rec["TuyenSinhID"])
        set_trang_thai(storage, rec["TuyenSinhID"], "Rút hồ sơ", ly_do or "rút sau nhập học",
                       nguoi, luu_tru=False)
    else:
        ts = None
    _bo_khoi_phong(storage, rec["id"])  # rút hồ sơ: không còn ở phòng nội trú
    _luu_tru_an_toan(storage, ts=ts, nh=rec, ly_do=ly_do or "", nguoi=nguoi,
                     buoc="Sau nhập học")
    return out


# ------------------------------------------------------------------ Lưu trữ rút hồ sơ
_DONG_RUT = re.compile(r"(\d{1,2}/\d{1,2}/\d{4}) rút hồ sơ(?: \(([^)\n]*)\))?(?:: ?(.*))?")


def dong_rut_ho_so(ts: dict | None = None, nh: dict | None = None, ly_do: str = "",
                   nguoi: str = "", ngay: date | str | None = None,
                   buoc: str | None = None) -> dict:
    """Một dòng lưu trữ rút hồ sơ từ bản ghi Data tuyển sinh (ts) và / hoặc hồ sơ nhập học (nh)."""
    # bản ghi lấy từ bảng có thể chứa NaN / Timestamp: chuẩn hóa trước
    ts = {k: v for k, v in ((k, _gia_tri_luu(v)) for k, v in (ts or {}).items()) if v}
    nh = {k: v for k, v in ((k, _gia_tri_luu(v)) for k, v in (nh or {}).items()) if v}
    khoi = str(nh.get("Khoi") or ts.get("Khoi") or "")
    ph = str(nh.get("PhanHe") or ts.get("PhanHe") or "")
    if ph and ph not in khoi:
        khoi = f"{khoi} {ph}".strip()
    ngay = ngay or date.today()
    return {
        "NamHoc": nh.get("NamHoc") or ts.get("NamHoc") or "",
        "NgayRut": ngay.isoformat() if isinstance(ngay, date) else ngay,
        "HoTen": nh.get("HoTen") or ts.get("HoTenHS") or "",
        "NgaySinh": nh.get("NgaySinh") or ts.get("NgaySinh") or None,
        "Khoi": khoi,
        "LopHoc": nh.get("LopHoc") or "",
        "SDT": ts.get("SDT") or nh.get("DienThoaiSLL") or nh.get("DienThoaiMe")
        or nh.get("DienThoaiBo") or "",
        "CheDo": nh.get("NoiTruBanTru") or ts.get("CheDo") or "",
        "Buoc": buoc or ("Sau nhập học" if nh else ts.get("TrangThai") or ""),
        "LyDo": ly_do or "",
        "NguoiThucHien": nguoi or "",
        "TuyenSinhID": str(ts.get("id") or nh.get("TuyenSinhID") or ""),
        "NhapHocID": str(nh.get("id") or ""),
    }


def _dam_bao_list_rut(storage: Storage) -> None:
    """List LuuTru_RutHoSo chưa có / thiếu cột thì tự tạo (SharePoint); kho cục bộ bỏ qua."""
    if not hasattr(storage, "colmap"):
        return
    try:
        thieu = bool(storage.colmap(RUT_HO_SO.name).missing)
    except Exception:  # noqa: BLE001 — chưa có list
        thieu = True
    if thieu:
        from . import importer  # tránh vòng import

        importer.setup_lists(storage, log=lambda *_: None, lists=[RUT_HO_SO])
        getattr(storage, "_maps", {}).pop(RUT_HO_SO.name, None)


def ghi_rut_ho_so(storage: Storage, dong: dict) -> dict:
    """Ghi một dòng vào Lưu trữ rút hồ sơ."""
    _dam_bao_list_rut(storage)
    return storage.create_item(RUT_HO_SO.name, {k: v for k, v in
                                                ((k, _gia_tri_luu(v)) for k, v in dong.items())
                                                if v not in (None, "")})


def _gia_tri_luu(v):
    """Giá trị lấy từ bảng (Timestamp, NaN, số) → chuỗi ghi được lên list."""
    if v is None:
        return None
    try:
        if pd.isna(v):
            return None
    except (TypeError, ValueError):
        pass
    if hasattr(v, "isoformat"):
        return v.date().isoformat() if hasattr(v, "date") and callable(v.date) else v.isoformat()
    s = str(v).strip()
    return s[:-2] if s.endswith(".0") and s[:-2].isdigit() else s


def _luu_tru_an_toan(storage: Storage, **kw) -> None:
    """Ghi lưu trữ sau khi đã rút: lỗi thì báo rõ (hồ sơ vẫn đã rút, bổ sung lại được)."""
    try:
        ghi_rut_ho_so(storage, dong_rut_ho_so(**kw))
    except Exception as e:  # noqa: BLE001
        raise ValueError(
            "Đã rút hồ sơ nhưng chưa ghi được vào Lưu trữ rút hồ sơ (" + str(e)[:200] + "). "
            "Mở Công cụ → Lưu trữ rút hồ sơ → “Bổ sung hồ sơ đã rút” để ghi lại.") from e


def _tach_ghi_chu(ghi_chu: str) -> tuple[str, str, str]:
    """(ngày dd/mm/yyyy, người, lý do) của lần rút cuối trong ghi chú; không có → ("","","")."""
    m = None
    for m in _DONG_RUT.finditer(str(ghi_chu or "")):
        pass
    if not m:
        return "", "", ""
    return m.group(1), (m.group(2) or "").strip(), (m.group(3) or "").strip()


def _ngay_iso(dmy: str, du_phong) -> str | None:
    try:
        d, mth, y = (int(x) for x in dmy.split("/"))
        return date(y, mth, d).isoformat()
    except (ValueError, AttributeError):
        s = str(du_phong or "")[:10]
        return s or None


def rut_chua_luu_tru(ts_items: list[dict], nh_items: list[dict],
                     da_luu: list[dict]) -> list[dict]:
    """Các hồ sơ đã rút (trước khi có lưu trữ) chưa có dòng lưu trữ, dựng lại từ ghi chú."""
    co_ts = {str(r.get("TuyenSinhID")) for r in da_luu if r.get("TuyenSinhID")}
    co_nh = {str(r.get("NhapHocID")) for r in da_luu if r.get("NhapHocID")}
    nh_theo_ts = {str(r.get("TuyenSinhID")): r for r in nh_items if r.get("TuyenSinhID")}
    out = []

    def them(ts, nh):
        nguon = nh if nh and nh.get("TinhTrangHS") == "Rút hồ sơ" else None
        ngay, nguoi, ly_do = _tach_ghi_chu((nguon or {}).get("GhiChu"))
        if not ngay and ts:
            ngay, nguoi2, ly_do = _tach_ghi_chu(ts.get("GhiChu"))
            nguoi = nguoi or nguoi2
        goc = nguon or ts or nh
        out.append(dong_rut_ho_so(
            ts=ts, nh=nh, ly_do=ly_do, nguoi=nguoi,
            ngay=_ngay_iso(ngay, goc.get("Modified")),
            buoc="Sau nhập học" if nguon else ("Không rõ (bổ sung)" if ts else "Sau nhập học")))

    for ts in ts_items:
        if ts.get("TrangThai") != "Rút hồ sơ" or str(ts.get("id")) in co_ts:
            continue
        nh = nh_theo_ts.get(str(ts.get("id")))
        if nh and str(nh.get("id")) in co_nh:
            continue
        them(ts, nh)
    for nh in nh_items:
        if (nh.get("TinhTrangHS") == "Rút hồ sơ" and str(nh.get("id")) not in co_nh
                and str(nh.get("TuyenSinhID") or "") not in co_ts
                and not (nh.get("TuyenSinhID") and any(
                    str(t.get("id")) == str(nh["TuyenSinhID"]) and t.get("TrangThai") == "Rút hồ sơ"
                    for t in ts_items))):
            them(None, nh)
    return out


def nhap_hoc_df(storage: Storage, nam_hoc: str) -> pd.DataFrame:
    """Hồ sơ nhập học của năm, bỏ các HS đã rút hồ sơ sau khi nhập học."""
    df = load_df(storage, NHAP_HOC, nam_hoc)
    ts = load_df(storage, TUYEN_SINH)
    rut = set(ts.loc[ts["TrangThai"] == "Rút hồ sơ", "id"])
    return df[~df["TuyenSinhID"].isin(rut)].reset_index(drop=True)


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
