"""Trợ lý dữ liệu dạng hộp chat: hỏi bằng tiếng Việt, trả lời từ dữ liệu của app (miễn phí,
không gửi dữ liệu ra ngoài). Bộ máy trả lời: tuyensinh/tro_ly.py."""
import altair as alt
import streamlit as st

from tuyensinh import tro_ly, ui
from tuyensinh.schema import NHAP_HOC, TUYEN_SINH

S = st.session_state
nam_hoc = ui.nam_hoc()
tk = S.get("tk")
ctx = tro_ly.Ctx(ui.df(TUYEN_SINH, nam_hoc), ui.df(NHAP_HOC, nam_hoc), nam_hoc,
                 quyen=set(tk["Quyen"]) if tk else None)

actions = ui.page_header("Trợ lý dữ liệu", f"Hỏi đáp nhanh về dữ liệu năm học {nam_hoc} — "
                         "xử lý ngay trong app, không gửi dữ liệu ra ngoài")
msgs = S.setdefault("tl_msgs", [])
if msgs and actions.button("Cuộc trò chuyện mới", icon=":material/add_comment:"):
    msgs.clear()
    st.rerun()


def _bieu_do(df):
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
        st.markdown(m["text"])
        r = m.get("tl")
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
        tl = tro_ly.tra_loi(hoi, ctx)
    except Exception as e:  # không để lỗi một câu hỏi làm hỏng trang
        tl = tro_ly.TraLoi(f"Xin lỗi, mình gặp lỗi khi trả lời câu này ({e}).")
    msgs.append({"role": "assistant", "text": tl.text, "tl": tl})
    del msgs[:-40]  # giữ 20 lượt gần nhất
    st.rerun()
