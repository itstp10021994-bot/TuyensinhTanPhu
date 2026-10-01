"""Hệ thống thiết kế + thành phần giao diện dùng chung.

Nguyên tắc:
- Một màu chính (xanh #1D4ED8), nền trung tính; màu chỉ dùng để truyền đạt trạng thái.
- Trạng thái luôn có chữ đi kèm (không dựa vào màu), nhất quán giữa bảng, badge và biểu đồ.
- Mỗi trang: tiêu đề + mô tả ngắn + vùng hành động bên phải; nội dung chia thành các khối.
- Danh sách → chọn dòng → trang chi tiết (drill-in) cho bản ghi dài; biểu mẫu ngắn mở dạng hộp thoại.
"""
from __future__ import annotations

import hashlib
import io
import threading
import time
import traceback
from concurrent.futures import ThreadPoolExecutor
from contextlib import contextmanager
from datetime import date, datetime
from html import escape

import pandas as pd
import streamlit as st

from . import config, danh_muc, services
from .schema import BOOL, CHOICE, DATE, GIU_CHO, NOTE, NUMBER, TRANG_THAI, Field, ListDef
from .storage import Storage, create_storage

# ---------------------------------------------------------------- tokens
# Màu trạng thái: tên màu theme của Streamlit (tự đổi theo sáng/tối) + mã hex cho biểu đồ.
STATUS = {
    "Tư vấn": {"color": "blue", "hex": "#2563EB", "icon": ":material/forum:"},
    "Nộp hồ sơ": {"color": "orange", "hex": "#D97706", "icon": ":material/description:"},
    "Nhập học": {"color": "green", "hex": "#059669", "icon": ":material/school:"},
    "Rút hồ sơ": {"color": "gray", "hex": "#6B7280", "icon": ":material/block:"},
}
GIU_CHO_COLOR = {
    "Chưa giữ chỗ": "gray",
    "Đã giữ chỗ": "green",
    "Hủy giữ chỗ": "red",
    "Đã hoàn phí": "violet",
}
STEPS = ("Tư vấn", "Nộp hồ sơ", "Nhập học")  # luồng chính; "Rút hồ sơ" là nhánh thoát
XLSX = "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"

CSS = """
<style>
/* ---- khung trang ---- */
/* chừa chỗ cho thanh header của Streamlit (cao hơn khi chạy trên Streamlit Cloud) */
.block-container {padding-top: 4.25rem; padding-bottom: 3rem; max-width: 1480px;}
/* logo trường (nền trắng để rõ cả khi giao diện tối) */
[data-testid="stHeaderLogo"], [data-testid="stSidebarLogo"] {background: #fff; border-radius: 6px;
  padding: 2px 6px; height: 2.4rem !important; max-width: 11rem;}
/* thanh công cụ (năm học, người thao tác) nằm trên thanh menu ngang */
.st-key-tp_toolbar {position: fixed; top: .55rem; right: 4.5rem; z-index: 999991;
  width: auto !important; background: transparent;}
.st-key-tp_toolbar [data-testid="stSelectbox"] {min-width: 140px;}
/* danh sách thẻ (bố cục như app cũ: danh sách trái, chi tiết phải) */
[class*="st-key-cards_"] [data-testid="stVerticalBlockBorderWrapper"] {padding: 2px 0;}
[class*="st-key-cards_"] button {min-height: 30px; padding: 2px 10px; font-size: .78rem;}
[class*="st-key-cards_"] [class*="st-key-name_"] button {border: 0; background: none; padding: 0;
  min-height: 0; font-size: 1rem; font-weight: 600; color: #1D4ED8;
  text-align: left; justify-content: flex-start;}
[class*="st-key-cards_"] [class*="st-key-name_"] button p {text-align: left;}
[class*="st-key-cards_"] [class*="st-key-card_sel"] {border-left: 4px solid #1D4ED8;
  background: rgba(37, 99, 235, .06); border-radius: 8px;}
[class*="st-key-cards_"] [class*="st-key-xoa_"] button {background: #DC2626;
  border-color: #DC2626; color: #fff;}
[class*="st-key-cards_"] [class*="st-key-rut_"] button {color: #DC2626;}
.tp-card {font-size: .86rem; line-height: 1.55; margin: 0;}
.tp-card b {font-weight: 600;} .tp-card .k {opacity: .7;} .tp-card .red {color: #DC2626;}
.tp-tag {font-size: .75rem; font-weight: 600; margin: 0; align-self: center;}
/* thanh tiêu đề khung chi tiết */
[class*="st-key-head_"] {background: #EA580C; border-radius: 8px; padding: 8px 14px;}
[class*="st-key-head_"] h3 {color: #fff !important; margin: 0; font-size: 1.05rem;}
[class*="st-key-head_"] button {background: #fff; color: #1D4ED8; border: 0; font-weight: 600;}
h1, h2, h3 {letter-spacing: -0.01em;}
[data-testid="stSidebarNav"] {padding-top: .25rem;}
[data-testid="stSidebarNavSeparator"] {margin: .25rem 0;}
/* tiêu đề trang */
.tp-eyebrow {font-size: .8125rem; font-weight: 500; opacity: .65; margin: 0 0 .15rem 0;}
.tp-title {font-size: 1.625rem; font-weight: 700; line-height: 1.25; margin: 0;}
.tp-sub {font-size: .9375rem; opacity: .7; margin: .25rem 0 0 0;}
/* KPI */
[data-testid="stMetric"] {padding: .85rem 1rem;}
[data-testid="stMetricLabel"] p {font-size: .8125rem; font-weight: 500; opacity: .75;}
/* trạng thái trống */
.tp-empty {text-align: center; padding: 2.5rem 1rem 1rem;}
.tp-empty .ico {font-family: "Material Symbols Rounded"; font-size: 2.5rem; line-height: 1;
  opacity: .45; font-feature-settings: "liga"; -webkit-font-feature-settings: "liga";}
.tp-empty h4 {margin: .5rem 0 .25rem; font-size: 1.0625rem; font-weight: 600;}
.tp-empty p {opacity: .7; margin: 0 auto; max-width: 30rem; font-size: .9375rem;}
/* stepper quy trình */
.tp-steps {display: flex; gap: .5rem; list-style: none; padding: 0 !important;
  margin: .25rem 0 0 0 !important;}
.tp-steps li {margin: 0 !important;}
.tp-steps li {flex: 1; display: flex; align-items: center; gap: .5rem; font-size: .875rem;
  padding: .5rem .75rem; border-radius: .5rem; border: 1px solid rgba(128,128,128,.25);}
.tp-steps .n {display: inline-flex; width: 1.4rem; height: 1.4rem; border-radius: 50%;
  align-items: center; justify-content: center; font-size: .75rem; font-weight: 600;
  border: 1.5px solid currentColor; flex: none;}
.tp-steps .done {color: #047857; border-color: rgba(5,150,105,.35);}
.tp-steps .done .n {background: #059669; border-color: #059669; color: #fff;}
.tp-steps .cur {border-color: #1D4ED8; box-shadow: inset 0 0 0 1px #1D4ED8; font-weight: 600;}
.tp-steps .cur .n {background: #1D4ED8; border-color: #1D4ED8; color: #fff;}
.tp-steps .todo {opacity: .6;}
.tp-steps.off li {opacity: .45;}
/* danh sách key-value trong thẻ phụ */
.tp-kv {display: grid; grid-template-columns: auto 1fr; gap: .35rem 1rem; font-size: .875rem;
  margin: .25rem 0 0 0 !important; padding: 0 !important;}
.tp-kv dt {opacity: .65;} .tp-kv dd {margin: 0; font-weight: 500; text-align: right;}
/* danh sách việc cần làm */
.tp-muted {opacity: .7; font-size: .875rem;}
/* mobile */
@media (max-width: 640px) {
  .block-container {padding: 4.25rem .9rem 2.5rem;}
  .st-key-tp_toolbar {position: static; justify-content: flex-start !important;
    flex-wrap: nowrap !important;}
  .st-key-tp_toolbar [data-testid="stSelectbox"] {min-width: 110px; flex: 1;}
  .st-key-tp_toolbar [data-testid="stCaptionContainer"], .st-key-tp_refresh {display: none;}
  /* KPI: 2 thẻ mỗi hàng thay vì xếp dọc từng thẻ */
  [class*="st-key-kpis"] [data-testid="stHorizontalBlock"] {flex-wrap: wrap; gap: .5rem;}
  [class*="st-key-kpis"] [data-testid="stColumn"] {flex: 1 1 calc(50% - .5rem) !important;
    min-width: calc(50% - .5rem) !important; width: auto !important;}
  .tp-title {font-size: 1.3rem;}
  .tp-steps {flex-direction: column; gap: .35rem;}
  [data-testid="stMetric"] {padding: .6rem .75rem;}
  [data-testid="stMetricValue"] {font-size: 1.3rem;}
}
@media (prefers-reduced-motion: reduce) { * {transition: none !important; animation: none !important;} }
</style>
"""


# ---------------------------------------------------------------- dữ liệu
@st.cache_resource
def _base_storage() -> Storage:
    return create_storage()


class _UserStorage:
    """Kho dữ liệu của phiên làm việc: mỗi lần ghi Data tuyển sinh / Hồ sơ nhập học tự lưu
    tên người thao tác (tài khoản Microsoft 365 đăng nhập) vào cột Người cập nhật."""

    def __init__(self, base: Storage, user: str):
        self._base, self._user = base, user

    def __getattr__(self, name):
        return getattr(self._base, name)

    def _stamp(self, list_name: str, data: dict) -> dict:
        from .schema import NHAP_HOC, TUYEN_SINH

        if self._user and list_name in (TUYEN_SINH.name, NHAP_HOC.name) and data:
            data = {**data, "NguoiCapNhat": self._user}
        return data

    def create_item(self, list_name, data):
        return self._base.create_item(list_name, self._stamp(list_name, data))

    def update_item(self, list_name, item_id, data):
        return self._base.update_item(list_name, item_id, self._stamp(list_name, data))


def storage() -> Storage:
    return _UserStorage(_base_storage(), current_user())


TTL = 600  # giây: dữ liệu sửa thẳng trên SharePoint hiện lên app sau tối đa 10 phút


@st.cache_resource
def _data_store() -> dict:
    """Bộ nhớ đệm dùng chung mọi người dùng: bản ghi + DataFrame đã chuyển đổi của từng list."""
    return {"lock": threading.Lock(), "lists": {}}


def _entry(name: str) -> dict:
    store = _data_store()
    with store["lock"]:
        return store["lists"].setdefault(name, {"lock": threading.Lock()})


def _fresh(e: dict, version: int) -> bool:
    return e.get("version") == version and time.monotonic() - e.get("at", -1e9) < TTL


def _fetch(st_obj: Storage, name: str, version: int, optional: bool = False) -> dict:
    e = _entry(name)
    with e["lock"]:  # nhiều người mở cùng lúc: chỉ tải 1 lần
        if not _fresh(e, version):
            err = ""
            try:
                items = st_obj.list_items(name)
            except Exception as ex:  # list tùy chọn (vd danh mục) chưa có: không chặn app
                if not optional:
                    raise
                items, err = [], str(ex)
            e.update(version=version, at=time.monotonic(), items=items, frames={}, memo={},
                     error=err)
    return e


def preload(*lds: ListDef, optional: tuple = ()):
    """Tải các list trang cần — song song — vào bộ nhớ đệm (nếu chưa có / đã cũ).

    `optional`: list không bắt buộc (lỗi -> coi như rỗng, ghi lại lỗi để trang Cài đặt báo)."""
    v = data_version()
    opt = {ld.name for ld in optional}
    need = [ld.name for ld in lds if not _fresh(_entry(ld.name), v)]
    if not need:
        return
    s = storage()
    with st.spinner("Đang tải dữ liệu từ SharePoint…"):
        if len(need) == 1:
            _fetch(s, need[0], v, need[0] in opt)
        else:
            with ThreadPoolExecutor(max_workers=len(need)) as pool:
                list(pool.map(lambda n: _fetch(s, n, v, n in opt), need))


def list_error(ld: ListDef) -> str:
    """Lỗi lần tải gần nhất của list tùy chọn ("" nếu tải được)."""
    return _entry(ld.name).get("error", "")


def apply_giay_to():
    """Danh mục giấy tờ theo khối: lấy từ list DanhMuc_GiayTo, chưa có thì dùng mặc định."""
    from .schema import GIAY_TO

    preload(GIAY_TO, optional=(GIAY_TO,))
    services.dat_giay_to(memo(GIAY_TO, "bang", lambda: services.giay_to_tu_list(
        _entry(GIAY_TO.name)["items"])))


@st.cache_resource
def _shared_state() -> dict:
    """Bộ đếm phiên bản dữ liệu dùng chung cho mọi người dùng của server."""
    return {"version": 0, "loaded_at": datetime.now()}


def data_version() -> int:
    return _shared_state()["version"]


def invalidate():
    """Gọi sau mỗi lần ghi: mọi phiên làm việc đều đọc lại dữ liệu mới."""
    state = _shared_state()
    state["version"] += 1
    state["loaded_at"] = datetime.now()


def refresh():
    store = _data_store()
    with store["lock"]:
        store["lists"].clear()
    invalidate()


def loaded_at() -> datetime:
    return _shared_state()["loaded_at"]


def records(ld: ListDef, optional: bool = False) -> list[dict]:
    """Bản ghi của list (dùng chung bộ nhớ đệm với df())."""
    preload(ld, optional=(ld,) if optional else ())
    return _entry(ld.name)["items"]


def df(ld: ListDef, nam_hoc: str | None = None) -> pd.DataFrame:
    """DataFrame của list (đã chuyển đổi sẵn, lưu đệm theo năm học). Trả về bản sao."""
    preload(ld)
    e = _entry(ld.name)
    with e["lock"]:
        frames = e["frames"]
        if None not in frames:
            frames[None] = services.to_df(ld, e["items"])
        if nam_hoc not in frames:
            base = frames[None]
            frames[nam_hoc] = base[base["NamHoc"] == nam_hoc].reset_index(drop=True)
        return frames[nam_hoc].copy()


def memo(ld: ListDef, key, fn):
    """Lưu đệm kết quả tính toán nặng trên dữ liệu của list (tự xóa khi dữ liệu đổi)."""
    if not _fresh(_entry(ld.name), data_version()):
        preload(ld)
    e = _entry(ld.name)
    key = (key, data_version())
    if key not in e["memo"]:
        e["memo"][key] = fn()
    return e["memo"][key]


def nam_hoc() -> str:
    return st.session_state.get("nam_hoc", config.default_year())


def logged_in() -> bool:
    """Đã đăng nhập (Microsoft 365 hoặc tài khoản của app)."""
    if st.session_state.get("tk"):
        return True
    try:
        return bool(st.user.is_logged_in)
    except Exception:
        return False


def current_user() -> str:
    tk = st.session_state.get("tk")
    if tk:
        return tk.get("HoTen") or tk.get("TenDangNhap") or ""
    try:
        if st.user.is_logged_in:
            return st.user.get("name") or st.user.get("email") or ""
    except Exception:
        pass
    return st.session_state.get("nguoi_dung", "")


def cookie_secret() -> str:
    """Khóa ký cookie ghi nhớ đăng nhập (COOKIE_SECRET, hoặc mật khẩu quản trị / key flow)."""
    pa = config.section("powerautomate")
    return str(config.get("COOKIE_SECRET") or config.get("ADMIN_PASSWORD") or pa.get("key")
               or config.get("PA_KEY") or "tuyen-sinh-tan-phu")


def set_cookie(name: str, value: str, days: int = 30):
    """Ghi cookie lên trình duyệt (days < 0: xóa)."""
    import json

    import streamlit.components.v1 as components

    components.html(
        "<script>(function(){var d=window.parent.document;"
        f"var s={json.dumps(name)}+'='+encodeURIComponent({json.dumps(value)})"
        f"+'; path=/; max-age={max(days, 0) * 86400}; SameSite=Lax';"
        "if(window.parent.location.protocol==='https:'){s+='; Secure';}"
        "d.cookie=s;})();</script>", height=0)


def is_admin() -> bool:
    tk = st.session_state.get("tk")
    return bool(tk and tk.get("VaiTro") == "Quản trị")


def mutate(fn, *args, success: str | None = None, **kwargs):
    """Chạy thao tác ghi, hiển thị lỗi thân thiện. Trả về kết quả hoặc None nếu lỗi."""
    try:
        with st.spinner("Đang lưu…"):
            res = fn(*args, **kwargs)
    except ValueError as e:  # lỗi kiểm tra dữ liệu
        st.error(str(e), icon=":material/error:")
        return None
    except Exception as e:  # lỗi kết nối SharePoint / Power Automate
        error_state(e, compact=True)
        return None
    invalidate()
    if success:
        st.toast(success, icon=":material/check_circle:")
    return res


# ---------------------------------------------------------------- danh sách thẻ + chi tiết
def card_list(view: pd.DataFrame, key: str, render_card, selected: str | None,
              filter_state=None, page_size: int = 20, height: int = 760):
    """Danh sách thẻ có phân trang (về trang 1 khi bộ lọc đổi)."""
    S = st.session_state
    pages = max(1, -(-len(view) // page_size))
    fkey = hash(repr(filter_state))
    if S.get(f"_{key}_fkey") != fkey:
        S[f"_{key}_fkey"], S[f"{key}_page"] = fkey, 1
    page = min(S.get(f"{key}_page", 1), pages)
    with st.container(height=height, border=True, key=f"cards_{key}"):
        if view.empty:
            empty_state("search_off", "Không có học sinh phù hợp", "Thử từ khóa hoặc bộ lọc khác.")
        for _, r in view.iloc[(page - 1) * page_size: page * page_size].iterrows():
            render_card(r.to_dict(), r["id"] == selected)
    nav = st.container(horizontal=True, vertical_alignment="center")
    nav.button("", icon=":material/chevron_left:", key=f"{key}_prev", disabled=page <= 1,
               on_click=lambda: S.update({f"{key}_page": page - 1}))
    nav.caption(f"Trang **{page}/{pages}** · {len(view)} học sinh")
    nav.button("", icon=":material/chevron_right:", key=f"{key}_next", disabled=page >= pages,
               on_click=lambda: S.update({f"{key}_page": page + 1}))


def card_box(rid: str, selected: bool):
    return st.container(border=True, key=f"card_sel_{rid}" if selected else f"card_{rid}")


def detail_head(title: str, key: str):
    """Thanh tiêu đề màu cam của khung chi tiết; trả về cột bên phải để đặt nút."""
    with st.container(key=f"head_{key}"):
        h1, h2 = st.columns([4, 1.2], vertical_alignment="center")
        h1.markdown(f"### {escape(title)}")
    return h2


# ---------------------------------------------------------------- khung trang
def inject_css():
    st.html(CSS)


def page_header(title: str, subtitle: str | None = None, eyebrow: str | None = None):
    """Tiêu đề trang; trả về container bên phải để đặt nút hành động."""
    left, right = st.columns([3, 2], vertical_alignment="bottom", gap="medium")
    html = ""
    if eyebrow:
        html += f'<p class="tp-eyebrow">{escape(eyebrow)}</p>'
    html += f'<h1 class="tp-title">{escape(title)}</h1>'
    if subtitle:
        html += f'<p class="tp-sub">{escape(subtitle)}</p>'
    left.html(html)
    actions = right.container(horizontal=True, horizontal_alignment="right", gap="small")
    st.space("small")
    return actions


@contextmanager
def section(title: str | None = None, caption: str | None = None, border: bool = True):
    with st.container(border=border):
        if title:
            st.markdown(f"#### {title}")
        if caption:
            st.caption(caption)
        yield


def empty_state(icon: str, title: str, body: str = ""):
    st.html(f'<div class="tp-empty" role="status"><span class="ico" '
            f'aria-hidden="true">{icon}</span><h4>{escape(title)}</h4>'
            f'<p>{escape(body)}</p></div>')


def _is_connection_error(err: Exception) -> bool:
    import requests

    msg = str(err)
    return isinstance(err, (requests.RequestException, ConnectionError, TimeoutError)) or any(
        k in msg for k in ("Graph ", "Power Automate", "token", "Thiếu cấu hình"))


def _sp_message(msg: str) -> str:
    """Lấy câu báo lỗi gốc của SharePoint trong phản hồi của flow."""
    import re

    m = re.search(r'\\*"value\\*"\s*:\s*\\*"(.+?)\\*"', msg)
    return m.group(1).replace("\\'", "'") if m else ""


def error_state(err: Exception, compact: bool = False):
    msg = str(err)
    if not _is_connection_error(err):
        friendly = "Đã xảy ra lỗi không mong muốn. Thử tải lại trang; nếu vẫn lỗi, gửi phần " \
                   "chi tiết kỹ thuật bên dưới cho người quản trị."
    elif "Thiếu cấu hình" in msg:
        friendly = msg
    elif "quá thời gian chờ" in msg or "timed out" in msg.lower():
        friendly = ("Power Automate phản hồi quá chậm (quá 2 phút). Thường do flow đang bị giới "
                    "hạn tốc độ sau nhiều thao tác liên tiếp — chờ 1–2 phút rồi bấm **Thử lại**. "
                    "Xem Lịch sử chạy của flow để biết bước nào chậm.")
    elif "does not exist at site" in msg or ("404" in msg and "List '" in msg):
        friendly = ("Chưa có list trên SharePoint (flow đã kết nối được). Vào **Hệ thống → Cài đặt "
                    "& đồng bộ** và bấm **Tạo list / thêm cột**.")
    elif "404" in msg:
        friendly = "Không tìm thấy list hoặc bản ghi trên SharePoint. Có thể đã bị xóa hoặc đổi tên."
    elif "401" in msg or "403" in msg:
        friendly = "Không có quyền truy cập SharePoint. Kiểm tra key / quyền của tài khoản chạy flow."
    else:
        friendly = "Không kết nối được tới SharePoint. Kiểm tra mạng hoặc cấu hình flow rồi thử lại."
    sp = _sp_message(msg)
    if sp and "Cài đặt" not in friendly:
        friendly += f"\n\nSharePoint báo: *{sp}*"
    icon = ":material/cloud_off:" if _is_connection_error(err) else ":material/error:"
    if not compact:
        st.markdown("### Không tải được trang")
    st.error(friendly, icon=icon)
    with st.expander("Chi tiết kỹ thuật"):
        st.code(msg if compact else traceback.format_exc(), language=None)
    if "Cài đặt" in friendly:
        st.page_link("views/cai_dat.py", label="Mở Cài đặt & đồng bộ", icon=":material/settings:")
    if not compact:
        st.button("Thử lại", icon=":material/refresh:", on_click=refresh, type="primary")


def status_badge(status: str, container=st):
    s = STATUS.get(status)
    if s:
        container.badge(status, color=s["color"], icon=s["icon"])
    elif status:
        container.badge(status, color="gray")


def giu_cho_badge(tinh_trang: str, container=st):
    tinh_trang = tinh_trang or "Chưa giữ chỗ"
    container.badge(tinh_trang, color=GIU_CHO_COLOR.get(tinh_trang, "gray"),
                    icon=":material/payments:")


def stepper(current: str):
    withdrawn = current == "Rút hồ sơ"
    idx = STEPS.index(current) if current in STEPS else -1
    items = []
    for i, step in enumerate(STEPS):
        cls = "done" if i < idx else "cur" if i == idx else "todo"
        mark = "✓" if cls == "done" else str(i + 1)
        aria = ' aria-current="step"' if cls == "cur" else ""
        items.append(f'<li class="{cls}"{aria}><span class="n">{mark}</span>{step}</li>')
    st.html(f'<ol class="tp-steps{" off" if withdrawn else ""}" aria-label="Quy trình tuyển sinh">'
            + "".join(items) + "</ol>")


def next_step(current: str) -> str | None:
    if current in STEPS and current != STEPS[-1]:
        return STEPS[STEPS.index(current) + 1]
    return None


def kv(rows: list[tuple[str, str]]):
    body = "".join(f"<dt>{escape(k)}</dt><dd>{escape(str(v) if v not in (None, '') else '—')}</dd>"
                   for k, v in rows)
    st.html(f'<dl class="tp-kv">{body}</dl>')


def kpi_row(n: int, key: str = "kpis"):
    """Hàng thẻ chỉ số; trên mobile hiển thị 2 thẻ mỗi hàng."""
    return st.container(key=key).columns(n)


def kpi(container, label: str, value, note: str | None = None, help: str | None = None):
    """Thẻ chỉ số thống nhất: cùng chiều cao, ghi chú trung tính (không mũi tên)."""
    container.metric(label, value, note or None, delta_color="off", delta_arrow="off",
                     border=True, height="stretch", help=help)


# ---------------------------------------------------------------- định dạng
def money(v) -> str:
    try:
        if v is None or pd.isna(v):
            return "—"
        return f"{float(v):,.0f} đ".replace(",", ".")
    except (TypeError, ValueError):
        return "—"


def fmt_date(v) -> str:
    d = _to_date(v)
    return d.strftime("%d/%m/%Y") if d else "—"


def ago(ts) -> str:
    if not ts:
        return ""
    return ts.strftime("%H:%M")


# ---------------------------------------------------------------- bảng
def tag_col(values: pd.Series) -> pd.Series:
    """Chuyển giá trị thành list 1 phần tử để hiển thị dạng pill màu trong bảng."""
    return values.map(lambda v: [v] if v else [])


def status_column(label: str = "Bước"):
    return st.column_config.MultiselectColumn(
        label, options=list(TRANG_THAI), color=[STATUS[s]["color"] for s in TRANG_THAI],
        width="small")


def giu_cho_column(label: str = "Giữ chỗ"):
    return st.column_config.MultiselectColumn(
        label, options=list(GIU_CHO), color=[GIU_CHO_COLOR[s] for s in GIU_CHO])


def table_height(n: int, max_h: int = 560) -> int:
    return min(max_h, 38 + 35 * max(n, 1) + 2)


DATE_COL = {"format": "DD/MM/YYYY"}


# ---------------------------------------------------------------- form
def _to_date(v) -> date | None:
    if v is None or v is pd.NaT or v == "" or (isinstance(v, float) and pd.isna(v)):
        return None
    if isinstance(v, date):
        return v
    try:
        return pd.to_datetime(v).date()
    except (ValueError, TypeError):
        return None


def field_input(f: Field, record: dict, prefix: str, container=st, label: str | None = None):
    """Vẽ ô nhập cho trường `f`; giá trị lấy từ `record`. Trả về giá trị mới."""
    key = f"{prefix}_{f.key}"
    label = (label or f.label) + (" *" if f.required else "")
    v = record.get(f.key)
    if f.type == DATE:
        return container.date_input(label, value=_to_date(v), key=key, format="DD/MM/YYYY",
                                    min_value=date(1940, 1, 1), max_value=date(2100, 12, 31))
    if f.type == NUMBER:
        empty = v is None or v == "" or (isinstance(v, float) and pd.isna(v))
        is_money = f.key.startswith("SoTien")
        return container.number_input(
            label, value=None if empty else float(v), key=key, min_value=0.0,
            max_value=None if is_money or (not empty and float(v) > 10) else 10.0, step=100000.0 if is_money else 0.25,
            format="%.0f" if is_money else "%.2f", placeholder="—")
    if f.type == BOOL:
        return container.checkbox(label, value=bool(v), key=key)
    if f.type == NOTE:
        return container.text_area(label, value=str(v or ""), key=key, height=96)
    if f.type == CHOICE:
        return _choice_input(f, record, prefix, container, label, key, v)
    return container.text_input(label, value=str(v or ""), key=key)


@st.cache_data(show_spinner=False)
def _learned_schools(version: int) -> dict:
    """Tên trường đã nhập trong dữ liệu, theo (tỉnh, xã) và theo tỉnh — dùng làm gợi ý."""
    from .schema import NHAP_HOC, TUYEN_SINH

    idx: dict[tuple[str, str], dict[str, int]] = {}
    for ld in (TUYEN_SINH, NHAP_HOC):
        for r in _fetch(storage(), ld.name, version)["items"]:
            ten = str(r.get("TruongCu") or "").strip()
            if not ten:
                continue
            t = danh_muc.fold(danh_muc.normalize_tinh(str(r.get("TruongCu_Tinh") or "")))
            x = danh_muc.fold(r.get("TruongCu_PhuongXa") or "")
            for k in ((t, x), (t, "")):
                idx.setdefault(k, {})
                idx[k][ten] = idx[k].get(ten, 0) + 1
    # sắp theo số lần xuất hiện
    return {k: [n for n, _ in sorted(v.items(), key=lambda kv: (-kv[1], kv[0]))]
            for k, v in idx.items()}


def school_suggestions(tinh: str, xa: str, khoi: str = "") -> list[str]:
    """Danh mục trường (truong_hoc.csv) trước, rồi các trường đã từng nhập ở phường/xã đó.

    Nếu biết khối đăng ký, trường đúng cấp học (vd THCS với khối 10) và liên cấp lên đầu.
    """
    out = danh_muc.truong_hoc(tinh, xa)
    want = danh_muc.cap_truoc_khoi(khoi)
    if want:
        rank = {c: 0 for c in want} | {"Liên cấp": 1}
        out.sort(key=lambda n: rank.get(danh_muc.cap_hoc(n, tinh, xa), 2))
    try:
        learned = _learned_schools(data_version()).get(
            (danh_muc.fold(danh_muc.normalize_tinh(tinh)), danh_muc.fold(xa)), [])
    except Exception:  # không đọc được dữ liệu -> chỉ dùng danh mục
        learned = []
    seen = {danh_muc.fold(x) for x in out}
    out += [x for x in learned if danh_muc.fold(x) not in seen]
    return out


def _choice_input(f: Field, record: dict, prefix: str, container, label: str, key: str, v):
    """Ô chọn; hỗ trợ chuỗi phụ thuộc Tỉnh → Phường/Xã → Trường.

    Giá trị của ô cha lấy từ lần vẽ hiện tại (lưu trong `_fv`), nên khi đổi Tỉnh thì
    danh sách Phường/Xã và gợi ý trường thay đổi ngay; ô con có key gồm giá trị ô cha để
    tự xóa lựa chọn cũ không còn hợp lệ.
    """
    cur = st.session_state.setdefault("_fv", {}).setdefault(prefix, {})
    parent_keys = danh_muc.parents(f)
    ctx = dict(record)
    changed = False
    for pk in parent_keys:
        ctx[pk] = cur.get(pk, record.get(pk)) or ""
        if danh_muc.fold(danh_muc.normalize_tinh(ctx[pk])) != danh_muc.fold(
                danh_muc.normalize_tinh(record.get(pk) or "")):
            changed = True
    if isinstance(f.options, str) and f.options == "@tinh":
        v = danh_muc.normalize_tinh(v)
    is_school = isinstance(f.options, str) and f.options.startswith("@truong:")
    if is_school:
        khoi = cur.get("Khoi", record.get("Khoi")) or record.get("LopHoc", "")
        opts = school_suggestions(ctx[parent_keys[0]], ctx[parent_keys[1]], khoi)
    else:
        opts = danh_muc.options_for(f, ctx)
    if changed:  # ô cha vừa đổi: bỏ giá trị cũ
        v = None
    elif v and v not in opts:
        opts = [v] + opts  # giữ giá trị cũ (vd tên theo địa giới trước sáp nhập)
    if parent_keys:
        key = f"{key}__{abs(hash(tuple(ctx[pk] for pk in parent_keys))) % 10**8}"
    if f.free:
        ph = ("Chọn trong gợi ý hoặc gõ tên trường…" if opts else "Gõ tên trường…") \
            if is_school else "Chọn hoặc gõ giá trị khác…"
        tinh_ctx = ctx.get(parent_keys[0], "") if is_school else ""
        xa_ctx = ctx.get(parent_keys[1], "") if is_school else ""

        def _fmt(name):
            cap = danh_muc.cap_hoc(name, tinh_ctx, xa_ctx) if is_school else ""
            return f"{name}  ·  {cap}" if cap else name

        val = container.selectbox(label, opts, index=opts.index(v) if v in opts else None,
                                  key=key, placeholder=ph, accept_new_options=True,
                                  format_func=_fmt,
                                  help="Gợi ý theo Phường/Xã đã chọn. Có thể gõ tên trường "
                                       "chưa có trong danh sách." if is_school else None)
    else:
        waiting = parent_keys and not opts
        ph = "Chọn Tỉnh/Thành phố trước" if waiting else "Chọn…"
        val = container.selectbox(label, opts, index=opts.index(v) if v in opts else None,
                                  key=key, placeholder=ph, disabled=bool(waiting))
    cur[f.key] = val or ""
    return val


def record_form(fields: list[Field], record: dict, prefix: str, ncols: int = 3,
                labels: dict[str, str] | None = None) -> dict:
    """Lưới ô nhập; ô ghi chú nhiều dòng chiếm trọn chiều ngang."""
    labels = labels or {}
    out = {}
    cols = st.columns(ncols)
    i = 0
    for f in fields:
        if f.type == NOTE:
            out[f.key] = field_input(f, record, prefix, label=labels.get(f.key))
            cols, i = st.columns(ncols), 0
            continue
        out[f.key] = field_input(f, record, prefix, cols[i % ncols], labels.get(f.key))
        i += 1
    return out


def required_hint():
    st.caption("Các trường có dấu * là bắt buộc.")


# ---------------------------------------------------------------- xuất file
def excel_bytes(frames: dict[str, pd.DataFrame]) -> bytes:
    buf = io.BytesIO()
    with pd.ExcelWriter(buf, engine="openpyxl") as xw:
        for sheet, data in frames.items():
            data.to_excel(xw, index=False, sheet_name=sheet[:31])
    return buf.getvalue()


def download_excel(label: str, frames: dict[str, pd.DataFrame] | pd.DataFrame, file_name: str,
                   container=st, primary: bool = False, key: str | None = None):
    """Nút tải Excel; file chỉ được tạo khi người dùng bấm."""
    if isinstance(frames, pd.DataFrame):
        frames = {"Data": frames}
    container.download_button(label, lambda: excel_bytes(frames), file_name=file_name,
                              mime=XLSX, icon=":material/download:", key=key,
                              type="primary" if primary else "secondary", on_click="ignore")


def table_key(prefix: str, ids) -> str:
    """Key cho bảng có chọn dòng: đổi khi tập dòng hiển thị đổi (lọc, tìm kiếm, dữ liệu mới)
    để lựa chọn cũ — lưu theo vị trí dòng — không trỏ nhầm sang học sinh khác."""
    h = hashlib.md5(",".join(map(str, ids)).encode()).hexdigest()[:10]
    return f"{prefix}_{h}"
