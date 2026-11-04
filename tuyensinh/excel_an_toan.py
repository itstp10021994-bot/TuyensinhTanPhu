"""Xuất Excel an toàn: dữ liệu người dùng nhập bắt đầu bằng "=" (vd ghi chú "=HYPERLINK(...)")
được openpyxl ghi thành CÔNG THỨC và chạy khi mở file (CSV/formula injection). Các hàm này ghi lại
những ô đó thành chữ thường, giữ nguyên nội dung."""
from __future__ import annotations


def chan_cong_thuc_ws(ws) -> int:
    n = 0
    for row in ws.iter_rows():
        for c in row:
            if c.data_type == "f" and isinstance(c.value, str):
                c.data_type = "s"
                n += 1
    return n


def chan_cong_thuc(wb) -> int:
    return sum(chan_cong_thuc_ws(ws) for ws in wb.worksheets)
