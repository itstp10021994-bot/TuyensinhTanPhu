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
    # Tên hiển thị của cột trên list SharePoint có sẵn (mặc định = label)
    sp: str = ""
    # Lựa chọn có gợi ý nhưng vẫn cho gõ giá trị mới (vd tên trường cũ)
    free: bool = False

    @property
    def sp_title(self) -> str:
        return self.sp or self.label


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
# Cột "Bước" trên list: 4 nút trạng thái của app
TRANG_THAI = ("Tư vấn", "Nộp hồ sơ", "Nhập học", "Rút hồ sơ")
# Cột "Tình trạng": mức độ tư vấn (theo dữ liệu thực tế của list cũ)
TINH_TRANG = ("Cần tư vấn thêm", "Cần tham quan tư vấn tại trường", "Đang cân nhắc",
              "Chờ HĐTS duyệt", "Đã cấp giấy tiếp nhận", "Nhập học", "Hủy giữ chỗ", "Hủy")
# Cột "Giữ chỗ" (kế toán)
GIU_CHO = ("Chưa giữ chỗ", "Đã giữ chỗ", "Hủy giữ chỗ", "Đã hoàn phí")
PHAN_HE = ("IEP", "ESL")
KHOI = tuple(str(i) for i in range(1, 13))
CHE_DO = ("Nội trú", "Bán trú", "Ngoại trú")
GIOI_TINH = ("Nam", "Nữ")
# Tình trạng của hồ sơ nhập học (theo list cũ)
TINH_TRANG_HS = ("Đang nhập hồ sơ", "Đang đóng phí", "Đã đóng phí", "Học tiếp",
                 "Không học tiếp", "Rút hồ sơ")
NGUON = ("Ban TS đến trường tư vấn", "Bạn bè - Người thân", "Quảng cáo tự động", "Mạng xã hội",
         "Hotline", "Trực tiếp", "Gần nhà", "Tự tìm hiểu", "PHHS trường giới thiệu",
         "CBNV Trường-IGC", "Giáo viên trường cũ", "Đi trường TS")
HANH_KIEM = ("Tốt", "Khá", "Đạt", "Chưa đạt")
HOC_LUC = ("Xuất sắc", "Giỏi", "Khá", "Đạt", "Chưa đạt", "Hoàn thành xuất sắc", "Hoàn thành tốt",
           "Hoàn thành", "Chưa hoàn thành", "Tốt", "Trung bình")
# Tổ hợp môn lựa chọn (THPT)
TO_HOP_MON = ("Lý-Địa-GDKTPL-Tin học", "Lý-Hóa-Địa-Tin học", "Lý-Hóa-GDKTPL-Tin học",
              "Lý-Hóa-Sinh-Tin học", "Hóa-Địa-GDKTPL-Tin học", "Sinh-Địa-GDKTPL-Tin học",
              "Lý-Sinh-Địa-Tin học", "Hóa-Sinh-GDKTPL-Tin học", "Hóa-Sinh-Địa-Tin học")
# Giấy tờ thu khi nhập học (nút "Thu hồ sơ")
GIAY_TO_NHAP_HOC = (
    "Phiếu đăng ký nhập học", "Thỏa thuận của Cha mẹ/Người giám hộ học sinh với nhà trường",
    "Giấy khai sinh", "Học bạ Tiểu học", "Học bạ THCS", "Học bạ THPT",
    "Hoàn thành chương trình tiểu học", "Đơn xét tuyển 10",
    "Giấy chứng nhận trúng tuyển vào lớp 10", "Giấy chứng nhận tốt nghiệp THCS tạm thời",
    "Bằng tốt nghiệp THCS", "Bảng điểm", "Đơn xin chuyển trường",
    "Giấy giới thiệu chuyển trường của trường nơi chuyển đi",
    "Giấy giới thiệu chuyển trường của UBND/Sở GD&ĐT")
# Môn học ở "Quá trình học tập" (điểm 1, điểm 2 như app cũ)
MON_HOC = (("Toan", "Toán"), ("Van", "Ngữ văn"), ("TV", "Tiếng Việt"), ("Anh", "Tiếng Anh"),
           ("GDCD", "GDCD"), ("LSDL", "LS và ĐL"), ("KHTN", "KHTN"), ("Tin", "Tin học"),
           ("CongNghe", "Công nghệ"), ("Ly", "Vật lý"), ("Hoa", "Hóa học"), ("Sinh", "Sinh học"),
           ("Su", "Lịch sử"), ("Dia", "Địa lý"), ("GDKTPL", "GDKT&PL"))

# ---------------------------------------------------------------- Data tuyển sinh
# Khớp với list "Data tuyển sinh" hiện có trên site tuyensinh2 (sp = tên hiển thị cột).
G_LIENHE, G_HOCSINH, G_TRUONGCU, G_KETOAN = (
    "Liên hệ & tư vấn", "Học sinh", "Trường cũ & kết quả học tập", "Giữ chỗ / kế toán")

TUYEN_SINH = ListDef(
    name="Data_TuyenSinh",
    title="Data tuyển sinh",
    fields=(
        # --- Liên hệ & tư vấn
        Field("NamHoc", "Năm học", CHOICE, "@nam_hoc", required=True, sp="Nam hoc",
              group=G_LIENHE),
        Field("NgayLienHe", "Ngày liên hệ", DATE, required=True, group=G_LIENHE),
        Field("SDT", "SĐT", required=True, group=G_LIENHE),
        Field("Nguon", "Nguồn", CHOICE, NGUON, group=G_LIENHE),
        Field("TenLienHe", "Tên liên hệ (Tài khoản FB)", sp="Tài khoản FB", group=G_LIENHE),
        Field("NguoiGioiThieu", "Người giới thiệu", group=G_LIENHE),
        Field("TrangThai", "Bước", CHOICE, TRANG_THAI, required=True, group=G_LIENHE),
        Field("TinhTrang", "Tình trạng tư vấn", CHOICE, TINH_TRANG, sp="Tình trạng",
              group=G_LIENHE),
        Field("NguoiNhanHoSo", "Người nhận hồ sơ", group=G_LIENHE),
        Field("GhiChu", "Nội dung đã trao đổi", NOTE, group=G_LIENHE),
        # --- Học sinh
        Field("HoTenHS", "Họ tên HS", required=True, group=G_HOCSINH),
        Field("NgaySinh", "Ngày sinh", DATE, group=G_HOCSINH),
        Field("Khoi", "Khối", CHOICE, KHOI, required=True, group=G_HOCSINH),
        Field("PhanHe", "Phân hệ", CHOICE, PHAN_HE, free=True, group=G_HOCSINH),
        Field("GioiTinh", "Giới tính", CHOICE, GIOI_TINH, group=G_HOCSINH),
        Field("CheDo", "Chế độ", CHOICE, CHE_DO, group=G_HOCSINH),
        # --- Trường cũ & kết quả học tập
        # Chọn Tỉnh → Phường/Xã (địa giới mới) → gợi ý trường thuộc phường/xã đó.
        # Cột "Trường cũ_Quận huyện" có sẵn trên list nay lưu Phường/Xã.
        Field("TruongCu_Tinh", "Trường cũ - Tỉnh/Thành phố", CHOICE, "@tinh",
              sp="Trường cũ_tỉnh", group=G_TRUONGCU),
        Field("TruongCu_PhuongXa", "Trường cũ - Phường/Xã", CHOICE, "@xa:TruongCu_Tinh",
              sp="Trường cũ_Quận huyện", group=G_TRUONGCU),
        Field("TruongCu", "Trường cũ", CHOICE, "@truong:TruongCu_Tinh,TruongCu_PhuongXa",
              free=True, group=G_TRUONGCU),
        # Quận/huyện, tỉnh trước sáp nhập (giữ lại từ dữ liệu cũ để tra cứu)
        Field("TruongCu_DiaChiCu", "Trường cũ - Địa chỉ cũ (trước sáp nhập)", group=G_TRUONGCU),
        Field("Toan1", "Toán 1", NUMBER, group=G_TRUONGCU),
        Field("Van1", "Văn 1", NUMBER, group=G_TRUONGCU),
        Field("Anh1", "Anh 1", NUMBER, group=G_TRUONGCU),
        Field("TV1", "TV 1", NUMBER, group=G_TRUONGCU),
        Field("Toan2", "Toán 2", NUMBER, group=G_TRUONGCU),
        Field("Van2", "Văn 2", NUMBER, group=G_TRUONGCU),
        Field("Anh2", "Tiếng Anh 2", NUMBER, group=G_TRUONGCU),
        Field("TV2", "TV 2", NUMBER, group=G_TRUONGCU),
        Field("HanhKiem1", "Hạnh kiểm 1", CHOICE, HANH_KIEM, group=G_TRUONGCU),
        Field("HanhKiem2", "Hạnh kiểm 2", CHOICE, HANH_KIEM, group=G_TRUONGCU),
        # --- Giữ chỗ / kế toán
        Field("GiuCho", "Giữ chỗ", CHOICE, GIU_CHO, group=G_KETOAN),
        Field("SoTienXacNhan", "Số tiền xác nhận", NUMBER, group=G_KETOAN),
        Field("NguoiXacNhan", "Người xác nhận", group=G_KETOAN),
        Field("TenChuTaiKhoan", "Tên chủ tài khoản", group=G_KETOAN),
        Field("NganHang", "Ngân hàng", group=G_KETOAN),
        Field("SoTaiKhoan", "Số tài khoản", group=G_KETOAN),
    ),
)

# ---------------------------------------------------------------- Data nhập học
# Trùng với biểu mẫu "Danh sách học sinh" (import VEMIS / CSDL ngành).
G_CHUNG, G_DIACHI, G_GIAYTO, G_GIADINH, G_LIENLAC = (
    "Thông tin chung", "Địa chỉ", "Giấy tờ & chính sách", "Gia đình", "Liên lạc & khác")
G_HOCTAP, G_KHANCAP, G_NGANHANG, G_MON, G_HOCPHI = (
    "Quá trình học tập", "Liên hệ khẩn cấp", "Tài khoản ngân hàng", "Lựa chọn môn",
    "Hồ sơ & học phí")


def _diem_fields() -> tuple:
    out = []
    for dot in ("1", "2"):
        out.append(Field(f"HocLuc{dot}", f"Học lực {dot}", CHOICE, HOC_LUC, free=True,
                         group=G_HOCTAP))
        out.append(Field(f"HanhKiem{dot}", f"Hạnh kiểm {dot}", CHOICE, HANH_KIEM, free=True,
                         group=G_HOCTAP))
        out += [Field(f"{k}{dot}", f"{ten} {dot}", NUMBER, group=G_HOCTAP) for k, ten in MON_HOC]
    return tuple(out)

NHAP_HOC = ListDef(
    name="Data_NhapHoc",
    title="Hồ sơ nhập học",
    fields=(
        Field("TuyenSinhID", "ID tuyển sinh", group="_"),
        # --- Thông tin chung
        Field("NamHoc", "Năm học", CHOICE, "@nam_hoc", required=True, sp="Nam hoc",
              group=G_CHUNG),
        # Không bắt buộc: HS mới nhập học thường "chưa xếp lớp" (vẫn tính vào mức hoàn thiện)
        Field("LopHoc", "Lớp học", group=G_CHUNG),
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
        # Ngoài biểu mẫu VEMIS (không xuất ra file VEMIS)
        Field("Khoi", "Khối", CHOICE, KHOI, group=G_CHUNG),
        Field("PhanHe", "Phân hệ", CHOICE, PHAN_HE, free=True, group=G_CHUNG),
        Field("TinhTrangHS", "Tình trạng hồ sơ", CHOICE, TINH_TRANG_HS, free=True, group=G_CHUNG),
        Field("LopCu", "Lớp cũ", group=G_CHUNG),
        # Trường cũ: lấy từ Data tuyển sinh (không có trong biểu mẫu VEMIS)
        Field("TruongCu_Tinh", "Trường cũ - Tỉnh/Thành phố", CHOICE, "@tinh", group=G_CHUNG),
        Field("TruongCu_PhuongXa", "Trường cũ - Phường/Xã", CHOICE, "@xa:TruongCu_Tinh",
              group=G_CHUNG),
        Field("TruongCu", "Trường cũ", CHOICE, "@truong:TruongCu_Tinh,TruongCu_PhuongXa",
              free=True, group=G_CHUNG),
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
        Field("MaBHYT", "Mã số BHYT", group=G_GIAYTO),
        Field("HoSoDaNop", "Hồ sơ đã nộp", NOTE, group=G_GIAYTO),
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
        Field("EmailCha", "Email cha", group=G_GIADINH),
        Field("EmailMe", "Email mẹ", group=G_GIADINH),
        Field("NguoiGiamHo", "Người giám hộ", group=G_GIADINH),
        Field("NamSinhNGH", "Năm sinh người giám hộ", group=G_GIADINH),
        Field("NgheNghiepNGH", "Nghề nghiệp người giám hộ", group=G_GIADINH),
        Field("CanCuocNGH", "Căn cước người giám hộ", group=G_GIADINH),
        Field("DienThoaiNGH", "Điện thoại người giám hộ", group=G_GIADINH),
        Field("EmailNGH", "Email người giám hộ", group=G_GIADINH),
        # --- Liên lạc & khác
        Field("DienThoaiSLL", "Điện thoại SLL", group=G_LIENLAC),
        Field("EmailSLL", "Email SLL", group=G_LIENLAC),
        Field("DienThoaiBo", "Điện thoại bố", group=G_LIENLAC),
        Field("DienThoaiMe", "Điện thoại mẹ", group=G_LIENLAC),
        Field("DienThoaiHS", "Điện thoại HS", group=G_LIENLAC),
        Field("KhanCap_Ten", "Liên hệ khẩn cấp - Họ tên", group=G_KHANCAP),
        Field("KhanCap_SDT", "Liên hệ khẩn cấp - SĐT", group=G_KHANCAP),
        Field("KhanCap_QuanHe", "Liên hệ khẩn cấp - Quan hệ", group=G_KHANCAP),
        Field("DangKyXe", "Đăng ký xe đưa đón", group=G_HOCPHI),
        Field("DiemDonTra", "Điểm đón trả", group=G_HOCPHI),
        # --- Quá trình học tập (điểm, học lực, hạnh kiểm ở trường cũ)
        *_diem_fields(),
        # --- Tài khoản ngân hàng (nhận hoàn phí)
        Field("TenChuTaiKhoan", "Tên chủ tài khoản", group=G_NGANHANG),
        Field("NganHang", "Ngân hàng", group=G_NGANHANG),
        Field("SoTaiKhoan", "Số tài khoản", group=G_NGANHANG),
        # --- Lựa chọn môn (tổ hợp môn THPT)
        Field("LuaChon1", "Lựa chọn 1", CHOICE, TO_HOP_MON, free=True, group=G_MON),
        Field("LuaChon2", "Lựa chọn 2", CHOICE, TO_HOP_MON, free=True, group=G_MON),
        Field("LuaChon3", "Lựa chọn 3", CHOICE, TO_HOP_MON, free=True, group=G_MON),
        # --- Hồ sơ & học phí
        Field("NgayNhanHoSo", "Ngày nhận hồ sơ", DATE, group=G_HOCPHI),
        Field("SoTienXacNhan", "Số tiền giữ chỗ", NUMBER, group=G_HOCPHI),
        Field("SoTienThanhToan", "Số tiền PHHS thanh toán", NUMBER, group=G_HOCPHI),
        Field("SoTienConLai", "Số tiền còn lại", NUMBER, group=G_HOCPHI),
        Field("TongDaThu", "Tổng số tiền đã thu", NUMBER, group=G_HOCPHI),
        Field("NgayDongPhi", "Ngày đóng phí", DATE, group=G_HOCPHI),
        Field("KeToanXacNhan", "Kế toán xác nhận", group=G_HOCPHI),
        Field("GhiChu", "Ghi chú", NOTE, group=G_LIENLAC),
    ),
)

# Danh mục giấy tờ cần nộp theo khối (chỉnh ở trang Cài đặt). Mỗi dòng = 1 giấy tờ của 1 khối.
GIAY_TO = ListDef(
    name="DanhMuc_GiayTo",
    title="Danh mục giấy tờ cần nộp theo khối",
    fields=(
        Field("Khoi", "Khối (vd 10-IEP, 7)", required=True),
        Field("TenGiayTo", "Tên giấy tờ", required=True),
        Field("ThuTu", "Thứ tự", NUMBER),
    ),
)

ALL_LISTS = (TUYEN_SINH, NHAP_HOC, GIAY_TO)


# Cột của Data_NhapHoc không có trong biểu mẫu VEMIS (chỉ dùng trong app / SharePoint)
NHAP_HOC_NGOAI_VEMIS = tuple(
    f.key for f in NHAP_HOC.fields
    if f.key in ("TuyenSinhID", "NamHoc", "TruongCu_Tinh", "TruongCu_PhuongXa", "TruongCu",
                 "Khoi", "PhanHe", "TinhTrangHS", "LopCu", "MaBHYT", "HoSoDaNop", "EmailCha",
                 "EmailMe", "NguoiGiamHo", "NamSinhNGH", "NgheNghiepNGH", "CanCuocNGH",
                 "DienThoaiNGH", "EmailNGH")
    or f.group in (G_HOCTAP, G_KHANCAP, G_NGANHANG, G_MON, G_HOCPHI))
