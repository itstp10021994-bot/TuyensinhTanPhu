"""Giấy tờ cần thu: bộ phận Tuyển sinh cấu hình loại giấy tờ mỗi khối phải nộp khi nhập học."""
from tuyensinh import ui, ui_giay_to

ui.page_header("Giấy tờ cần thu", "Loại giấy tờ học sinh mới mỗi khối phải nộp khi nhập học — "
               "dùng cho Thu hồ sơ, tiến độ giấy tờ trên thẻ và báo cáo", eyebrow="Tuyển sinh")
ui_giay_to.render(ui.storage())
