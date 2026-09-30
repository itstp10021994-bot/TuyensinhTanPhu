"""Tạo dữ liệu mẫu để chạy thử (chỉ dùng với BACKEND=local)."""
import random
from datetime import date, timedelta

import _common  # noqa: F401

from tuyensinh import config, services
from tuyensinh.schema import CHE_DO, NGUON
from tuyensinh.storage import create_storage

assert config.backend() == "local", "Chỉ tạo dữ liệu mẫu cho BACKEND=local"
random.seed(1)
HO = ["Nguyễn", "Trần", "Lê", "Phạm", "Huỳnh", "Võ", "Đặng", "Bùi", "Lâm"]
DEM = ["Văn", "Thị", "Hữu", "Minh", "Gia", "Ngọc", "Tuấn", "Phương", "Khánh"]
TEN = ["Long", "Thiên", "Thành", "Thư", "Oanh", "Huy", "Minh", "An", "Bảo", "Châu", "Duy"]
storage = create_storage()
nam = config.default_year()
for i in range(60):
    gt = random.choice(["Nam", "Nữ"])
    rec = services.save_tuyen_sinh(storage, {
        "NamHoc": nam,
        "NgayLienHe": date(2026, 3, 1) + timedelta(days=random.randint(0, 150)),
        "SDT": "09" + "".join(random.choices("0123456789", k=8)),
        "Nguon": random.choice(NGUON), "TenLienHe": "PH " + random.choice(HO),
        "TruongCu": "THCS " + random.choice(TEN), "Toan2": round(random.uniform(5, 10), 1),
        "Van2": round(random.uniform(5, 10), 1), "HanhKiem2": "Tốt",
        "HoTenHS": f"{random.choice(HO)} {random.choice(DEM)} {random.choice(TEN)}",
        "NgaySinh": date(2010, 1, 1) + timedelta(days=random.randint(0, 3000)),
        "Khoi": random.choice(["6", "8", "10", "10", "10", "11"]), "GioiTinh": gt,
        "CheDo": random.choice(CHE_DO[:2]),
    })
    tt = random.choices(["Tư vấn", "Nộp hồ sơ", "Nhập học", "Rút hồ sơ"], [4, 3, 4, 1])[0]
    if tt != "Tư vấn":
        services.set_trang_thai(storage, rec["id"], tt, "Chuyển trường khác" if tt == "Rút hồ sơ" else None)
    if tt in ("Nộp hồ sơ", "Nhập học"):
        services.xac_nhan_giu_cho(storage, rec["id"], 2000000, "Kế toán")
    elif tt == "Rút hồ sơ" and random.random() < .5:
        services.xac_nhan_giu_cho(storage, rec["id"], 2000000, "Kế toán", "Hủy giữ chỗ",
                                  TenChuTaiKhoan="PH", NganHang="Vietcombank",
                                  SoTaiKhoan="0071000000000")
print("Đã tạo dữ liệu mẫu.")
