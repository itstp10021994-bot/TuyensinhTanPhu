"""Trợ lý dữ liệu dạng hộp chat: hỏi bằng tiếng Việt, trả lời từ dữ liệu của app.
Bộ máy trả lời: tuyensinh/tro_ly.py; tùy chọn Gemini (tuyensinh/ai_gemini.py) chỉ để hiểu câu
hỏi — số liệu luôn tính trong app, dữ liệu học sinh không gửi ra ngoài."""
import altair as alt
import streamlit as st

from tuyensinh import ai_gemini, tro_ly, ui
from tuyensinh.schema import NHAP_HOC, TUYEN_SINH

CAT = ["#2a78d6", "#eb6834", "#1baf7a", "#eda100", "#e87ba4", "#008300", "#4a3aa7", "#e34948"]

S = st.session_state
nam_hoc = ui.nam_hoc()
tk = S.get("tk")
ctx = tro_ly.Ctx(ui.df(TUYEN_SINH, nam_hoc), ui.df(NHAP_HOC, nam_hoc), nam_hoc,
                 quyen=set(tk["Quyen"]) if tk else None,
                 ts_all=ui.df(TUYEN_SINH), nh_all=ui.df(NHAP_HOC))

actions = ui.page_header("Trợ lý dữ liệu", f"Hỏi đáp nhanh về dữ liệu năm học {nam_hoc} — "
                         "xử lý ngay trong app, không gửi dữ liệu ra ngoài")
msgs = S.setdefault("tl_msgs", [])
co_ai = ai_gemini.co_khoa()
with actions.container(horizontal=True, horizontal_alignment="right", vertical_alignment="center"):
    dung_ai = st.toggle("AI hiểu câu hỏi", value=co_ai, disabled=not co_ai, key="tl_dung_ai",
                        help="Dùng Google Gemini (miễn phí) để hiểu câu hỏi tự do. Chỉ gửi câu "
                             "hỏi, không gửi dữ liệu học sinh; câu có tên / số điện thoại xử lý "
                             "trong app." if co_ai else
                        "Chưa bật: thêm GEMINI_API_KEY vào Secrets của app (xem Cài đặt → "
                        "Hướng dẫn).")
    if msgs and st.button("Cuộc trò chuyện mới", icon=":material/add_comment:"):
        msgs.clear()
        S.pop("tl_truoc", None)
        S.pop("tl_truoc_goc", None)
        st.rerun()


def _ai(cau_hoi, truoc):
    """Gọi Gemini có lưu đệm trong phiên (cùng câu hỏi + ngữ cảnh không tốn thêm lượt)."""
    cache = S.setdefault("tl_ai_cache", {})
    k = (cau_hoi.strip().lower(), S.get("tl_truoc_goc"))
    if k not in cache:
        kq = ai_gemini.viet_lai(cau_hoi, S.get("tl_truoc_goc"), nam_hoc,
                                f"{ctx.hom_nay:%d/%m/%Y}")
        if kq.loi:  # lỗi (hết lượt...) thì không lưu đệm để lần sau thử lại
            return kq
        cache[k] = kq
    return cache[k]


def _bieu_do_nhom(df):
    x, nhom, y = df.columns[:3]
    doms = list(dict.fromkeys(df[nhom]))
    n = df[x].nunique()
    ngang = n > 8 or df[x].astype(str).str.len().max() > 10
    cat = alt.Y(f"{x}:N", title=None, sort=list(dict.fromkeys(df[x])),
                axis=alt.Axis(labelLimit=260, labelOverlap=False)) if ngang else \
        alt.X(f"{x}:N", title=None, sort=list(dict.fromkeys(df[x])), axis=alt.Axis(labelAngle=0))
    val = alt.X(f"{y}:Q", title=None, axis=alt.Axis(format="d")) if ngang else \
        alt.Y(f"{y}:Q", title=None, axis=alt.Axis(format="d"))
    off = alt.YOffset(f"{nhom}:N") if ngang else alt.XOffset(f"{nhom}:N")
    c = alt.Chart(df.astype({x: str})).mark_bar(cornerRadiusEnd=3).encode(
        **({"x": val, "y": cat, "yOffset": off} if ngang else {"x": cat, "y": val, "xOffset": off}),
        color=alt.Color(f"{nhom}:N", scale=alt.Scale(domain=doms, range=CAT[:len(doms)]),
                        legend=alt.Legend(orient="top", title=None)),
        tooltip=[alt.Tooltip(f"{x}:N"), alt.Tooltip(f"{nhom}:N"), alt.Tooltip(f"{y}:Q", format="d")])
    st.altair_chart(c.properties(height=max(200, 22 * n * len(doms)) if ngang else 260)
                    .configure_view(stroke=None), width="stretch")


def _bieu_do(df):
    if df.shape[1] >= 3:
        return _bieu_do_nhom(df)
    x, y = df.columns[:2]
    n = len(df)
    if n == 0 or n > 25:
        return
    ngang = n > 12 or df[x].astype(str).str.len().max() > 8
    sort = alt.EncodingSortField(y, "sum", "descending") if ngang else list(dict.fromkeys(df[x]))
    cat = alt.Y(f"{x}:N", title=None, sort=sort, axis=alt.Axis(labelLimit=260, labelOverlap=False)) if ngang else \
        alt.X(f"{x}:N", title=None, sort=sort, axis=alt.Axis(labelAngle=0))
    val = alt.X(f"{y}:Q", title=None, axis=alt.Axis(format="d")) if ngang else \
        alt.Y(f"{y}:Q", title=None, axis=alt.Axis(format="d"))
    c = alt.Chart(df.astype({x: str})).mark_bar(
        cornerRadiusEnd=4, color="#2a78d6",
        **({"height": {"band": .7}} if ngang else {"width": {"band": .6}})).encode(
        **({"x": val, "y": cat} if ngang else {"x": cat, "y": val}),
        tooltip=[alt.Tooltip(f"{x}:N"), alt.Tooltip(f"{y}:Q", format="d")])
    st.altair_chart(c.properties(height=max(160, 30 * n) if ngang else 240)
                    .configure_view(stroke=None), width="stretch")


def _hien(m, i):
    with st.chat_message(m["role"], avatar=":material/person:" if m["role"] == "user"
                         else ":material/smart_toy:"):
        r = m.get("tl")
        if r is not None and r.ai_hieu:
            st.caption(f":material/auto_awesome: AI hiểu là: *{r.ai_hieu}*")
        elif r is not None and r.da_ghep:
            st.caption(f":material/link: Hiểu theo ngữ cảnh câu trước: *{r.hieu_la}*")
        if r is not None and r.ai_loi:
            st.caption(f":material/info: {r.ai_loi} — đang dùng cách hiểu thường.")
        st.markdown(m["text"])
        if r is None:
            return
        if r.chart is not None and len(r.chart) > 1:
            _bieu_do(r.chart)
        if r.table is not None and len(r.table):
            st.dataframe(r.table, hide_index=True, width="stretch",
                         height=min(420, 38 + 35 * len(r.table)), key=f"tl_tbl_{i}")
            st.download_button("Tải CSV", r.table.to_csv(index=False).encode("utf-8-sig"),
                               file_name="tro_ly.csv", mime="text/csv", key=f"tl_csv_{i}",
                               icon=":material/download:", type="tertiary")


hoi = None
if not msgs:
    with st.chat_message("assistant", avatar=":material/smart_toy:"):
        st.markdown(tro_ly.huong_dan().text)
for i, m in enumerate(msgs):
    _hien(m, i)

goi_y = (msgs[-1]["tl"].goi_y if msgs and msgs[-1].get("tl") else []) or list(tro_ly.VI_DU)
chon = st.pills("Gợi ý", goi_y, key=f"tl_goi_y_{len(msgs)}", label_visibility="collapsed")
hoi = st.chat_input("Hỏi về dữ liệu tuyển sinh, ví dụ: bao nhiêu HS nhập học khối 10?") or chon

if hoi:
    msgs.append({"role": "user", "text": hoi})
    try:
        tl = tro_ly.tra_loi(hoi, ctx, S.get("tl_truoc"), ai=_ai if dung_ai else None)
    except Exception as e:  # không để lỗi một câu hỏi làm hỏng trang
        tl = tro_ly.TraLoi(f"Xin lỗi, mình gặp lỗi khi trả lời câu này ({e}).")
    S["tl_truoc"] = tl.hieu_la or None
    S["tl_truoc_goc"] = tl.ai_hieu if tl.ai_hieu and not tl.ai_hieu.startswith("(") else hoi
    msgs.append({"role": "assistant", "text": tl.text, "tl": tl})
    del msgs[:-40]  # giữ 20 lượt gần nhất
    st.rerun()
