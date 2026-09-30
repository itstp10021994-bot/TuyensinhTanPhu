"""Định nghĩa các danh sách (SharePoint List) và trường dữ liệu của ứng dụng.

Mỗi trường có `key` là tên nội bộ (internal name) dùng trên SharePoint, không dấu,
và `label` là tên hiển thị tiếng Việt.
"""
from __future__ import annotations

from dataclasses import dataclass, field

# Kiểu dữ liệu: text, note (nhiều dòng), date, number, choice, bool
TEXT, NOTE, DATE, NUMBER, CHOICE, BOOL = "text", "note", "date", "number", "choice", "bool"


@dataclass(frozen=True)
class Field:
    key: str
    label: str
    type: str = TEXT
    # Danh sách lựa chọn cố định, hoặc tên danh mục trong danh_muc.json (vd "@tinh")
    options: tuple[str, ...] | str = ()
    required: bool = False
    group: str = ""


@dataclass(frozen=True)
class ListDef:
    name: str  # tên list trên SharePoint
    title: str
    fields: tuple[Field, ...] = field(default_factory=tuple)

    def get(self, key: str) -> Field:
        for f in self.fields:
            if f.key == key:
                return f
        raise KeyError(key)

    @property
    def keys(self) -> list[str]:
        return [f.key for f in self.fields]


# ---------------------------------------------------------------- Giá trị chung
TRANG_THAI = ("Tư vấn", "Nộp hồ sơ", "Nhập học", "Rút hồ sơ")
KHOI = tuple(str(i) for i in range(1, 13))
CHE_DO = ("Nội trú", "Bán trú", "Ngoại trú")
GIOI_TINH = ("Nam", "Nữ")
NGUON = ("Facebook", "Website", "Zalo", "Hotline", "Người quen giới thiệu",
         "Phụ huynh cũ", "Tờ rơi / Banner", "Hội thảo tư vấn", "Khác")
LOAI_PHI = ("Phí giữ chỗ", "Phí nhập học", "Học phí", "Phí nội trú / bán trú",
            "Đồng phục", "Khác")
HINH_THUC_TT = ("Chuyển khoản", "Tiền mặt")
XAC_NHAN = ("Chờ xác nhận", "Đã xác nhận", "Hoàn tiền", "Hủy")

# ---------------------------------------------------------------- Data tuyển sinh
TUYEN_SINH = ListDef(
    name="Data_TuyenSinh",
    title="Data tuyển sinh",
    fields=(
        Field("NamHoc", "Năm học", required=True),
        Field("NgayLienHe", "Ngày liên hệ", DATE, required=True),
        Field("SDT", "SĐT", required=True),
        Field("Nguon", "Nguồn", CHOICE, NGUON),
        Field("TenLienHe", "Tên liên hệ (phụ huynh)"),
        Field("HoTenHS", "Họ tên HS", required=True),
        Field("NgaySinh", "Ngày sinh", DATE),
        Field("NguoiGioiThieu", "Người giới thiệu"),
        Field("Khoi", "Khối", CHOICE, KHOI, required=True),
        Field("GioiTinh", "Giới tính", CHOICE, GIOI_TINH),
        Field("CheDo", "Chế độ", CHOICE, CHE_DO),
        Field("TruongCu", "Trường cũ"),
        Field("DiaChi", "Địa chỉ"),
        Field("Email", "Email"),
        Field("TrangThai", "Trạng thái", CHOICE, TRANG_THAI, required=True),
        Field("NgayNopHoSo", "Ngày nộp hồ sơ", DATE),
        Field("NgayNhapHoc", "Ngày nhập học", DATE),
        Field("NgayRutHoSo", "Ngày rút hồ sơ", DATE),
        Field("LyDoRut", "Lý do rút hồ sơ", NOTE),
        Field("NguoiTuVan", "Người tư vấn"),
        Field("GhiChu", "Ghi chú", NOTE),
    ),
)

# ---------------------------------------------------------------- Data nhập học
# Trùng với biểu mẫu "Danh sách học sinh" (import VEMIS / CSDL ngành).
G_CHUNG, G_DIACHI, G_GIAYTO, G_GIADINH, G_LIENLAC = (
    "Thông tin chung", "Địa chỉ", "Giấy tờ & chính sách", "Gia đình", "Liên lạc & khác")

NHAP_HOC = ListDef(
    name="Data_NhapHoc",
    title="Hồ sơ nhập học",
    fields=(
        Field("TuyenSinhID", "ID tuyển sinh", group="_"),
        Field("NamHoc", "Năm học", required=True, group="_"),
        # --- Thông tin chung
        Field("LopHoc", "Lớp học", required=True, group=G_CHUNG),
        Field("MaHocSinh", "Mã học sinh", group=G_CHUNG),
        Field("MaVEMIS", "Mã VEMIS", group=G_CHUNG),
        Field("MaMOET", "Mã MOET", group=G_CHUNG),
        Field("SoDangBo", "Sổ đăng bộ", group=G_CHUNG),
        Field("HoTen", "Họ và tên", required=True, group=G_CHUNG),
        Field("NgaySinh", "Ngày sinh", DATE, required=True, group=G_CHUNG),
        Field("NgayVaoTruong", "Ngày vào trường", DATE, group=G_CHUNG),
        Field("GioiTinh", "Giới tính", CHOICE, GIOI_TINH, group=G_CHUNG),
        Field("QuocTich", "Quốc tịch", CHOICE, "@quoc_tich", group=G_CHUNG),
        Field("DanToc", "Dân tộc", CHOICE, "@dan_toc", group=G_CHUNG),
        Field("TonGiao", "Tôn giáo", CHOICE, "@ton_giao", group=G_CHUNG),
        # --- Địa chỉ
        Field("ChoO_SoNha", "Chỗ ở hiện nay - SN/Xóm", group=G_DIACHI),
        Field("ChoO_KhuDanCu", "Chỗ ở hiện nay - Khu dân cư", group=G_DIACHI),
        Field("ChoO_Tinh", "Chỗ ở hiện nay - Tỉnh/Tp", CHOICE, "@tinh", group=G_DIACHI),
        Field("ChoO_Xa", "Chỗ ở hiện nay - Xã/Phường", CHOICE, "@xa:ChoO_Tinh", group=G_DIACHI),
        Field("HK_SoNha", "Hộ khẩu thường trú - SN/Xóm", group=G_DIACHI),
        Field("HK_KhuDanCu", "Hộ khẩu thường trú - Khu dân cư", group=G_DIACHI),
        Field("HK_Tinh", "Hộ khẩu thường trú - Tỉnh/Tp", CHOICE, "@tinh", group=G_DIACHI),
        Field("HK_Xa", "Hộ khẩu thường trú - Xã/Phường", CHOICE, "@xa:HK_Tinh", group=G_DIACHI),
        Field("NoiSinh_ThongTin", "Nơi sinh - Thông tin nơi sinh", group=G_DIACHI),
        Field("NoiSinh_Tinh", "Nơi sinh - Tỉnh/Tp", CHOICE, "@tinh", group=G_DIACHI),
        Field("NoiSinh_Xa", "Nơi sinh - Xã/Phường", CHOICE, "@xa:NoiSinh_Tinh", group=G_DIACHI),
        Field("QueQuan_ThongTin", "Quê quán - Thông tin quê quán", group=G_DIACHI),
        Field("QueQuan_Tinh", "Quê quán - Tỉnh/Tp", CHOICE, "@tinh", group=G_DIACHI),
        Field("QueQuan_Xa", "Quê quán - Xã/Phường", CHOICE, "@xa:QueQuan_Tinh", group=G_DIACHI),
        Field("NoiKS_Tinh", "Nơi khai sinh - Tỉnh/Tp", CHOICE, "@tinh", group=G_DIACHI),
        Field("NoiKS_Xa", "Nơi khai sinh - Xã/Phường", CHOICE, "@xa:NoiKS_Tinh", group=G_DIACHI),
        # --- Giấy tờ & chính sách
        Field("CanCuoc", "Căn cước", group=G_GIAYTO),
        Field("NgayCapCanCuoc", "Ngày cấp Căn cước", DATE, group=G_GIAYTO),
        Field("NoiCapCanCuoc", "Nơi cấp Căn cước", group=G_GIAYTO),
        Field("DienChinhSach", "Diện chính sách", CHOICE, "@dien_chinh_sach", group=G_GIAYTO),
        Field("CanNgheo", "Cận nghèo", BOOL, group=G_GIAYTO),
        Field("DoanVien", "Đoàn viên", BOOL, group=G_GIAYTO),
        Field("DoiVien", "Đội viên", BOOL, group=G_GIAYTO),
        Field("KhuyetTat", "Khuyết tật", CHOICE, "@khuyet_tat", group=G_GIAYTO),
        Field("NoiTruBanTru", "N.trú, B.trú", CHOICE, "@noi_tru_ban_tru", group=G_GIAYTO),
        # --- Gia đình
        Field("TenCha", "Tên cha", group=G_GIADINH),
        Field("NgheNghiepCha", "Nghề nghiệp cha", group=G_GIADINH),
        Field("NamSinhCha", "Năm sinh cha", group=G_GIADINH),
        Field("CanCuocCha", "Căn cước cha", group=G_GIADINH),
        Field("DonViCongTacCha", "Đơn vị công tác cha", group=G_GIADINH),
        Field("TenMe", "Tên mẹ", group=G_GIADINH),
        Field("NgheNghiepMe", "Nghề nghiệp mẹ", group=G_GIADINH),
        Field("NamSinhMe", "Năm sinh mẹ", group=G_GIADINH),
        Field("CanCuocMe", "Căn cước mẹ", group=G_GIADINH),
        Field("DonViCongTacMe", "Đơn vị công tác mẹ", group=G_GIADINH),
        # --- Liên lạc & khác
        Field("DienThoaiSLL", "Điện thoại SLL", group=G_LIENLAC),
        Field("EmailSLL", "Email SLL", group=G_LIENLAC),
        Field("DienThoaiBo", "Điện thoại bố", group=G_LIENLAC),
        Field("DienThoaiMe", "Điện thoại mẹ", group=G_LIENLAC),
        Field("DienThoaiHS", "Điện thoại HS", group=G_LIENLAC),
        Field("GhiChu", "Ghi chú", NOTE, group=G_LIENLAC),
    ),
)

# ---------------------------------------------------------------- Kế toán (thu phí)
THU_PHI = ListDef(
    name="Data_ThuPhi",
    title="Thu phí",
    fields=(
        Field("TuyenSinhID", "ID tuyển sinh", required=True),
        Field("NamHoc", "Năm học", required=True),
        Field("HoTenHS", "Họ tên HS"),
        Field("Khoi", "Khối"),
        Field("LoaiPhi", "Loại phí", CHOICE, LOAI_PHI, required=True),
        Field("SoTien", "Số tiền", NUMBER, required=True),
        Field("NgayThu", "Ngày thu", DATE, required=True),
        Field("HinhThuc", "Hình thức", CHOICE, HINH_THUC_TT),
        Field("SoPhieu", "Số phiếu / Mã giao dịch"),
        Field("NguoiThu", "Người thu"),
        Field("TrangThaiXN", "Trạng thái xác nhận", CHOICE, XAC_NHAN),
        Field("NguoiXacNhan", "Người xác nhận"),
        Field("NgayXacNhan", "Ngày xác nhận", DATE),
        Field("GhiChu", "Ghi chú", NOTE),
    ),
)

ALL_LISTS = (TUYEN_SINH, NHAP_HOC, THU_PHI)
