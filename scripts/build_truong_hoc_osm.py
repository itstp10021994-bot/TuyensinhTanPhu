"""Tạo danh mục trường học theo Phường/Xã mới từ OpenStreetMap.

1. Lấy trường mầm non / tiểu học / THCS / THPT ở Việt Nam từ OpenStreetMap (Overpass API).
2. Đối chiếu tọa độ với ranh giới Phường/Xã mới (GeoJSON, sau sáp nhập) để biết trường thuộc
   Phường/Xã nào — không phụ thuộc địa chỉ ghi theo quận/huyện cũ.
3. Ghi tuyensinh/data/truong_hoc.csv (Tỉnh/Thành phố, Phường/Xã, Tên trường, Cấp học).

Chạy tự động bằng GitHub Actions (.github/workflows/cap-nhat-truong-hoc.yml) hoặc tại máy:
    pip install shapely
    python scripts/build_truong_hoc_osm.py                      # tải dữ liệu từ internet
    python scripts/build_truong_hoc_osm.py --osm osm.json --gis part-01.ndjson ...  # file có sẵn

Dữ liệu OpenStreetMap do cộng đồng đóng góp (© OpenStreetMap contributors, ODbL):
có thể thiếu trường; người dùng vẫn gõ được tên trường mới trong app.
"""
import argparse
import csv
import json
import re
import urllib.parse
import urllib.request
from datetime import date

import _common

from tuyensinh import danh_muc

OVERPASS = ["https://overpass-api.de/api/interpreter",
            "https://overpass.kumi.systems/api/interpreter",
            "https://maps.mail.ru/osm/tools/overpass/api/interpreter"]
QUERY = """[out:json][timeout:900];
area["ISO3166-1"="VN"][admin_level=2]->.vn;
(nwr["amenity"~"^(school|kindergarten)$"]["name"](area.vn););
out center tags;"""
GIS_PARTS = [("https://raw.githubusercontent.com/ThangLeQuoc/vietnamese-provinces-database/master/"
              f"elasticsearch/provinces-gis-part-{i:02d}.ndjson") for i in range(1, 6)]
OUT = danh_muc.TRUONG_CSV

CAP = [  # (mẫu trong tên, cấp học)
    (r"mầm non|mẫu giáo|nhà trẻ|kindergarten|preschool", "Mầm non"),
    (r"tiểu học|\bth\b|primary", "Tiểu học"),
    (r"\bthcs\b|trung học cơ sở|secondary school|junior high", "THCS"),
    (r"\bthpt\b|trung học phổ thông|high school", "THPT"),
]
EXCLUDE = re.compile(r"đại học|cao đẳng|trung cấp|university|college|lái xe|trung tâm|"
                     r"anh ngữ|ngoại ngữ|tin học|driving|dạy nghề|học viện|academy", re.I)


def cap_hoc(name: str, amenity: str) -> str:
    """Cấp học suy ra từ tên; tên có từ 2 cấp trở lên (vd "THCS - THPT") là Liên cấp."""
    n = name.lower()
    caps = [cap for pat, cap in CAP if re.search(pat, n)]
    if len(caps) > 1 or re.search(r"liên cấp|nhiều cấp", n):
        return "Liên cấp"
    if caps:
        return caps[0]
    if re.search(r"phổ thông", n):
        return "THPT"
    return "Mầm non" if amenity == "kindergarten" else ""


def fetch(url: str, data: bytes | None = None, timeout: int = 1000) -> bytes:
    req = urllib.request.Request(url, data=data, headers={"User-Agent": "tuyensinh-tanphu/1.0"})
    with urllib.request.urlopen(req, timeout=timeout) as r:
        return r.read()


def load_osm(path: str | None) -> list[dict]:
    if path:
        return json.load(open(path, encoding="utf-8"))["elements"]
    body = urllib.parse.urlencode({"data": QUERY}).encode()
    last = None
    for url in OVERPASS:
        try:
            print("Overpass:", url)
            return json.loads(fetch(url, body))["elements"]
        except Exception as e:  # thử máy chủ khác
            last = e
            print("  lỗi:", e)
    raise SystemExit(f"Không tải được dữ liệu OpenStreetMap: {last}")


def ward_polygons(paths: list[str] | None):
    """[(tỉnh, phường/xã, geometry)] — ranh giới sau sáp nhập, khớp theo mã phường/xã chuẩn."""
    from shapely.geometry import shape

    ma_xa = danh_muc.load()["ma_xa"]
    out, miss = [], []
    for i, url in enumerate(paths or GIS_PARTS):
        text = (open(url, encoding="utf-8").read() if not url.startswith("http")
                else fetch(url, timeout=900).decode("utf-8"))
        print(f"Ranh giới phần {i + 1}: {len(text) // 1_000_000} MB")
        for line in text.splitlines():
            if not line.startswith('{"Code"'):
                continue  # dòng chỉ mục Elasticsearch
            prov = json.loads(line)
            for w in prov.get("Wards", []):
                geom = (w.get("GIS") or {}).get("Geometry")
                names = ma_xa.get(w["Code"])
                if not geom or not names:
                    miss.append(w.get("FullName"))
                    continue
                out.append((names[0], names[1], shape(geom)))
    print(f"Ranh giới: {len(out)} phường/xã; thiếu {len(miss)} {miss[:5]}")
    return out


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--osm", help="file JSON kết quả Overpass (bỏ qua để tải)")
    ap.add_argument("--gis", nargs="*", help="các file provinces-gis-part-*.ndjson (bỏ qua để tải)")
    args = ap.parse_args()

    from shapely.geometry import Point
    from shapely.strtree import STRtree

    wards = ward_polygons(args.gis)
    tree = STRtree([g for _, _, g in wards])
    elements = load_osm(args.osm)
    print(f"OpenStreetMap: {len(elements)} điểm trường")

    rows, seen, skipped = [], set(), 0
    for el in elements:
        tags = el.get("tags", {})
        name = (tags.get("name:vi") or tags.get("name") or "").strip()
        lat = el.get("lat") or el.get("center", {}).get("lat")
        lon = el.get("lon") or el.get("center", {}).get("lon")
        if not name or lat is None or EXCLUDE.search(name):
            skipped += 1
            continue
        cap = cap_hoc(name, tags.get("amenity", ""))
        if not cap and not re.search(r"trường|school", name, re.I):
            skipped += 1
            continue
        pt = Point(lon, lat)
        hit = next((i for i in tree.query(pt) if wards[i][2].covers(pt)), None)
        if hit is None:
            skipped += 1
            continue
        tinh, xa, _ = wards[hit]
        k = (tinh, xa, danh_muc.fold(name))
        if k in seen:
            continue
        seen.add(k)
        rows.append([tinh, xa, name, cap])

    rows.sort(key=lambda r: (r[0], r[1], r[2]))
    with OUT.open("w", encoding="utf-8", newline="") as fh:
        w = csv.writer(fh)
        w.writerow(["Tỉnh/Thành phố", "Phường/Xã", "Tên trường", "Cấp học"])
        w.writerows(rows)
    meta = OUT.with_suffix(".meta.json")
    meta.write_text(json.dumps({
        "nguon": "OpenStreetMap (© OpenStreetMap contributors, ODbL) + ranh giới phường/xã "
                 "thanglequoc/vietnamese-provinces-database",
        "cap_nhat": date.today().isoformat(), "so_truong": len(rows)},
        ensure_ascii=False, indent=1), encoding="utf-8")
    by_cap = {}
    for r in rows:
        by_cap[r[3] or "Chưa rõ"] = by_cap.get(r[3] or "Chưa rõ", 0) + 1
    print(f"Đã ghi {len(rows)} trường vào {OUT} (bỏ qua {skipped}); theo cấp: {by_cap}")


if __name__ == "__main__":
    main()
