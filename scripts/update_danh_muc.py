"""Cập nhật danh mục Tỉnh → Phường/Xã theo địa giới hành chính mới nhất.

Nguồn: github.com/ThangLeQuoc/vietnamese-provinces-database (dữ liệu API của Tổng cục
Thống kê, cập nhật theo từng nghị quyết). Tên giữ cách viết của danh mục VEMIS khi chỉ khác
kiểu đặt dấu ("Hòa"/"Hoà") để file xuất vẫn import được vào VEMIS.

    python scripts/update_danh_muc.py            # tải bản mới nhất
    python scripts/update_danh_muc.py file.json  # dùng file đã tải
"""
import json
import re
import sys
import unicodedata
import urllib.request
from datetime import date

import _common

URL = ("https://raw.githubusercontent.com/ThangLeQuoc/vietnamese-provinces-database/master/"
       "json/vn_only_simplified_json_generated_data_vn_units.json")
META = ("https://raw.githubusercontent.com/ThangLeQuoc/vietnamese-provinces-database/master/"
        "json/vn_provinces_metadata.json")
OUT = _common.ROOT / "tuyensinh" / "data" / "danh_muc.json"


def key(s: str) -> str:
    """So khớp không phân biệt dấu, hoa/thường, khoảng trắng, kiểu nháy."""
    s = unicodedata.normalize("NFD", s.replace("’", "'").replace("''", "'").strip().lower())
    s = "".join(c for c in s if unicodedata.category(c) != "Mn").replace("đ", "d")
    return re.sub(r"\s+", " ", s).strip("'")


def clean(s: str) -> str:
    s = re.sub(r"\s+", " ", s.replace("’", "'").replace("''", "'")).strip().strip("'")
    return s[0].upper() + s[1:] if s else s


def prov_key(s: str) -> str:
    return key(re.sub(r"^(Tỉnh|Thành phố)\s+", "", s.strip()))


def main():
    if len(sys.argv) > 1:
        data = json.load(open(sys.argv[1], encoding="utf-8"))
        meta = {}
    else:
        with urllib.request.urlopen(URL, timeout=120) as r:
            data = json.load(r)
        try:
            with urllib.request.urlopen(META, timeout=30) as r:
                meta = json.load(r)
                meta = meta[0] if isinstance(meta, list) else meta
        except Exception:
            meta = {}

    dm = json.loads(OUT.read_text(encoding="utf-8"))
    old_xa = dm["xa_theo_tinh"]
    old_by_key = {prov_key(t): t for t in old_xa}
    alias = dict(dm.get("tinh_cu", {}))

    xa_theo_tinh, tinh = {}, []
    for p in data:
        name = clean(p["FullName"])
        old_name = old_by_key.get(prov_key(name))
        # Giữ cách viết VEMIS nếu chỉ khác dấu; đổi tên thật (vd Tỉnh → Thành phố) thì dùng tên mới
        if old_name and key(old_name) == key(name):
            name = old_name
        elif old_name:
            alias[old_name] = name
        spelled = {key(x): x.strip() for x in old_xa.get(old_name, [])}
        wards = []
        for w in p["Wards"]:
            n = clean(w["FullName"])
            wards.append(spelled.get(key(n), n))
        tinh.append(name)
        xa_theo_tinh[name] = wards

    changed_prov = sorted(set(tinh) ^ set(old_xa))
    n_old = sum(len(v) for v in old_xa.values())
    n_new = sum(len(v) for v in xa_theo_tinh.values())
    dm.update(tinh=tinh, xa_theo_tinh=xa_theo_tinh, tinh_cu=alias,
              nguon_dia_gioi={"nguon": "Tổng cục Thống kê qua thanglequoc/vietnamese-provinces-database",
                              "phien_ban": meta.get("DatasetVersion", ""),
                              "nghi_quyet": meta.get("LatestDecree", ""),
                              "cap_nhat": date.today().isoformat()})
    OUT.write_text(json.dumps(dm, ensure_ascii=False, indent=1), encoding="utf-8")
    print(f"{len(tinh)} tỉnh/thành, {n_new} phường/xã (trước: {len(old_xa)} / {n_old})")
    print("Tên tỉnh thay đổi:", changed_prov or "không")
    print("Phiên bản:", dm["nguon_dia_gioi"])


if __name__ == "__main__":
    main()
