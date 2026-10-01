"""Trợ lý dữ liệu dạng hộp chat: hỏi bằng tiếng Việt, trả lời từ dữ liệu của app.
Bộ máy trả lời: tuyensinh/tro_ly.py; tùy chọn Gemini (tuyensinh/ai_gemini.py) chỉ để hiểu câu
hỏi — số liệu luôn tính trong app, dữ liệu học sinh không gửi ra ngoài."""
from datetime import datetime
from zoneinfo import ZoneInfo

import altair as alt
import streamlit as st

from tuyensinh import ai_gemini, tro_ly, ui
from tuyensinh.schema import NHAP_HOC, TUYEN_SINH

TEN_AI = "Conan Ro"
BOT_SVG = f'<img alt="" src="{ui.ROBOT_URI}">'
CAT = ["#2a78d6", "#eb6834", "#1baf7a", "#eda100", "#e87ba4", "#008300", "#4a3aa7", "#e34948"]

S = st.session_state
nam_hoc = ui.nam_hoc()
tk = S.get("tk")
ctx = tro_ly.Ctx(ui.df(TUYEN_SINH, nam_hoc), ui.df(NHAP_HOC, nam_hoc), nam_hoc,
                 quyen=set(tk["Quyen"]) if tk else None,
                 ts_all=ui.df(TUYEN_SINH), nh_all=ui.df(NHAP_HOC))

msgs = S.setdefault("tl_msgs", [])
co_ai = ai_gemini.co_khoa()
TOI = st.context.theme.type == "dark"
# Cửa sổ macOS + bong bóng iMessage (sáng / tối)
M = dict(cua_so="#1E1E1E" if TOI else "#FFFFFF", thanh="#2A2A2C" if TOI else "#F6F6F6",
         vien="rgba(255,255,255,.10)" if TOI else "rgba(0,0,0,.10)", nen="#1E1E1E" if TOI else "#FFFFFF",
         ban="#0A84FF" if TOI else "#007AFF", bot="#3A3A3C" if TOI else "#E9E9EB",
         bot_chu="#F5F5F7" if TOI else "#1D1D1F", phu="#98989D" if TOI else "#8E8E93",
         chip="#2C2C2E" if TOI else "#F2F2F7", o_nhap="#2C2C2E" if TOI else "#FFFFFF")
st.html(f"""<style>
/* trang Trợ lý: khung chat vừa một màn hình, không cuộn trang */
[data-testid="stMain"] {{overflow: hidden !important;}}
.block-container {{padding-top: 4.4rem !important; padding-bottom: .75rem !important;}}
/* cửa sổ: cao vừa màn hình, rộng theo tỷ lệ 16:9 (không quá bề ngang trang) */
.st-key-zl_khung {{flex: 0 0 auto !important; height: calc(100dvh - 6.1rem) !important;
  max-height: none !important;
  width: min(100%, calc((100dvh - 6.1rem) * 16 / 9)) !important; margin: 0 auto; display: flex; flex-direction: column; flex-wrap: nowrap;
  background: {M['cua_so']}; border-radius: 12px; overflow: hidden; gap: 0 !important;
  box-shadow: 0 0 0 .5px {M['vien']}, 0 22px 70px rgba(0,0,0,{'.55' if TOI else '.16'}),
              0 2px 6px rgba(0,0,0,.06);}}
.st-key-zl_khung > * {{flex: none;}}
.st-key-zl_khung > div:has(> .st-key-zl_tin), .st-key-zl_khung > .st-key-zl_tin
  {{flex: 1 1 0 !important; min-height: 0 !important;}}
.st-key-zl_tin {{height: 100% !important; max-height: none !important; background: {M['nen']};
  padding: 14px 18px 6px; border: 0 !important; border-radius: 0 !important;}}
.st-key-zl_tin > div {{gap: .3rem;}}
/* thanh tiêu đề kiểu macOS: 3 nút đỏ-vàng-xanh, tên ở giữa */
.st-key-zl_dau {{padding: 8px 14px; background: {M['thanh']};
  border-bottom: 1px solid {M['vien']}; min-height: 52px;}}
.zl-den {{display: flex; gap: 8px; align-items: center; padding-right: 6px;}}
.zl-den i {{width: 12px; height: 12px; border-radius: 50%; display: block;
  box-shadow: inset 0 0 0 .5px rgba(0,0,0,.18);}}
.zl-den i:nth-child(1) {{background: #FF5F57;}} .zl-den i:nth-child(2) {{background: #FEBC2E;}}
.zl-den i:nth-child(3) {{background: #28C840;}}
.zl-giua {{display: flex; align-items: center; justify-content: center; gap: 10px;}}
.zl-ten {{font-weight: 600; font-size: .95rem; line-height: 1.15;}}
.zl-tt {{font-size: .74rem; color: {M['phu']};}} .zl-tt b {{color: #28C840;}}
.zl-av {{width: 34px; height: 34px; border-radius: 50%; flex: none; display: flex;
  align-items: center; justify-content: center;
  background: linear-gradient(135deg,#6D28D9 0%,#2563EB 55%,#06B6D4 100%);
  box-shadow: 0 2px 6px rgba(79,70,229,.35);}}
.zl-av img {{width: 24px; height: 24px;}}
.zl-av.nho {{width: 28px; height: 28px; margin-top: auto; box-shadow: none;}}
.zl-av.nho img {{width: 20px; height: 20px;}}
/* bong bóng iMessage */
div:has(> [class*="st-key-zl_u_"]) {{flex: 0 1 auto !important; max-width: 72%; width: auto !important;}}
div:has(> [class*="st-key-zl_b_"]) {{flex: 0 1 auto !important; max-width: calc(100% - 40px);
  width: auto !important; min-width: 0;}}
[class*="st-key-zl_u_"], [class*="st-key-zl_b_"] {{width: max-content !important;
  max-width: 100% !important; min-width: 0; padding: 7px 13px 5px; border-radius: 18px;}}
[class*="st-key-zl_u_"] {{background: {M['ban']}; color: #fff; border-bottom-right-radius: 5px;}}
[class*="st-key-zl_u_"] p {{color: #fff; margin: 0;}}
[class*="st-key-zl_u_"] .zl-gio {{color: rgba(255,255,255,.72); text-align: right;}}
[class*="st-key-zl_b_"] {{background: {M['bot']}; color: {M['bot_chu']}; border-bottom-left-radius: 5px;}}
[class*="st-key-zl_b_"] [data-testid="stCaptionContainer"] p {{font-size: .75rem;}}
/* bong bóng có bảng / biểu đồ: nền thẻ sáng cho dễ đọc */
[class*="st-key-zl_b_"]:has([data-testid="stDataFrame"], [data-testid="stVegaLiteChart"],
  [data-testid="stArrowVegaLiteChart"]) {{background: {M['cua_so']}; border: 1px solid {M['vien']};
  border-radius: 14px; padding: 10px 14px 6px;}}
.zl-gio {{font-size: .66rem; color: {M['phu']}; margin-top: 1px;}}
.zl-ngay {{text-align: center; margin: 2px 0 8px; font-size: .72rem; color: {M['phu']};
  font-weight: 500;}}
.zl-go span {{display: inline-block; width: 7px; height: 7px; margin: 0 2px; border-radius: 50%;
  background: {M['phu']}; animation: zlgo 1.2s infinite ease-in-out;}}
.zl-go span:nth-child(2) {{animation-delay: .2s;}} .zl-go span:nth-child(3) {{animation-delay: .4s;}}
@keyframes zlgo {{0%,80%,100% {{opacity: .25; transform: translateY(0)}}
  40% {{opacity: 1; transform: translateY(-3px)}}}}
/* gợi ý + ô nhập */
.st-key-zl_goiy {{padding: 8px 16px 0; background: {M['cua_so']}; border-top: 1px solid {M['vien']};}}
/* gợi ý: một hàng, cuộn ngang */
.st-key-zl_goiy [data-testid="stButtonGroup"] > div {{flex-wrap: nowrap !important;
  overflow-x: auto; scrollbar-width: none; padding-bottom: 2px;}}
.st-key-zl_goiy [data-testid="stButtonGroup"] > div::-webkit-scrollbar {{display: none;}}
.st-key-zl_goiy [data-testid="stButtonGroup"] button {{flex: none; white-space: nowrap;}}
.st-key-zl_goiy [data-testid="stButtonGroup"] button {{background: {M['chip']}; color: {M['ban']};
  border: 0; border-radius: 14px; font-size: .78rem; min-height: 28px;}}
.st-key-zl_nhap {{padding: 6px 16px 12px; background: {M['cua_so']};}}
.st-key-zl_nhap [data-testid="stChatInput"] > div {{border-radius: 20px; background: {M['o_nhap']};}}
@media (max-width: 760px) {{
  .block-container {{padding-top: 4rem !important;}}
  .st-key-zl_khung {{width: 100% !important; height: calc(100dvh - 9.4rem) !important;
    border-radius: 10px;}}
  .st-key-zl_dau {{flex-wrap: nowrap !important; padding: 6px 10px;}}
  .zl-den, .zl-tt {{display: none;}} .zl-giua {{justify-content: flex-start;}}
  .st-key-zl_tin {{padding: 10px 10px 4px;}}
  div:has(> [class*="st-key-zl_u_"]) {{max-width: 86%;}} }}
</style>""")

khung = st.container(key="zl_khung")
with khung.container(key="zl_dau", horizontal=True, vertical_alignment="center", gap="small"):
    st.html('<div class="zl-den"><i></i><i></i><i></i></div>', width="content")
    st.html(f'<div class="zl-giua"><div class="zl-av">{BOT_SVG}</div><div><div class="zl-ten">'
            f'{TEN_AI}</div><div class="zl-tt"><b>●</b> Trợ lý AI tuyển sinh · năm học {nam_hoc}'
            f'</div></div></div>', width="stretch")
    dung_ai = st.toggle("AI", value=co_ai, disabled=not co_ai, key="tl_dung_ai",
                        help="Dùng Google Gemini (miễn phí) để hiểu câu hỏi tự do. Chỉ gửi câu "
                             "hỏi, không gửi dữ liệu học sinh; câu có tên / số điện thoại xử lý "
                             "trong app." if co_ai else
                        "Chưa bật: thêm GEMINI_API_KEY vào Secrets của app.")
    if st.button("", icon=":material/edit_square:", key="tl_moi", type="tertiary",
                 help="Cuộc trò chuyện mới"):
        msgs.clear()
        for k in ("tl_truoc", "tl_truoc_goc"):
            S.pop(k, None)
        st.rerun()
if not co_ai:
    with khung.expander(":material/info: Công tắc AI đang tắt vì chưa tìm thấy GEMINI_API_KEY",
                        expanded=False):
        st.markdown(
            "1. Streamlit Cloud → app → **⋮ → Settings → Secrets**.\n"
            "2. Dán dòng sau lên **đầu** ô Secrets (trước mọi dòng có dạng `[tên_mục]`):\n"
            "   ```toml\n   GEMINI_API_KEY = \"AIza...\"\n   ```\n"
            "3. Bấm **Save**, chờ app khởi động lại (khoảng 1 phút), rồi tải lại trang (F5).\n\n"
            "Lưu ý: key phải nằm trong dấu ngoặc kép, không có khoảng trắng thừa; tên viết đúng "
            "`GEMINI_API_KEY`.")
tin = khung.container(key="zl_tin", height=560, autoscroll=True)


def _ai(cau_hoi, truoc):
    """Gọi Gemini có lưu đệm trong phiên (cùng câu hỏi + ngữ cảnh không tốn thêm lượt)."""
    cache = S.setdefault("tl_ai_cache", {})
    k = (cau_hoi.strip().lower(), S.get("tl_truoc_goc"))
    if k not in cache:
        thu = ("thứ 2", "thứ 3", "thứ 4", "thứ 5", "thứ 6", "thứ 7", "chủ nhật")
        kq = ai_gemini.viet_lai(cau_hoi, S.get("tl_truoc_goc"), nam_hoc,
                                f"{ctx.hom_nay.isoformat()} ({thu[ctx.hom_nay.weekday()]})",
                                cac_nam=ctx.cac_nam())
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


def _gio(m) -> str:
    return f'<div class="zl-gio">{m.get("gio", "")}</div>'


def _bot(key: str):
    """Một dòng tin của trợ lý: ảnh đại diện + bong bóng; trả về bong bóng để ghi nội dung."""
    hang = tin.container(horizontal=True, vertical_alignment="top", gap="small", wrap=False)
    hang.html(f'<div class="zl-av nho">{BOT_SVG}</div>', width="content")
    return hang.container(key=key, width="content")


def _hien(m, i):
    if m["role"] == "user":
        hang = tin.container(horizontal=True, horizontal_alignment="right", wrap=False)
        with hang.container(key=f"zl_u_{i}", width="content"):
            st.markdown(m["text"])
            st.html(_gio(m))
        return
    r = m.get("tl")
    with _bot(f"zl_b_{i}"):
        if r is not None and r.ai_hieu:
            nguon = f" ({r.ai_mo_hinh})" if getattr(r, "ai_mo_hinh", "") else ""
            st.caption(f":material/auto_awesome: AI{nguon} hiểu là: *{r.ai_hieu}*")
        elif r is not None and r.da_ghep:
            st.caption(f":material/link: Hiểu theo ngữ cảnh câu trước: *{r.hieu_la}*")
        if r is not None and r.ai_loi:
            st.caption(f":material/info: {r.ai_loi} — đang dùng cách hiểu thường.")
        st.markdown(m["text"])
        if r is not None:
            if r.chart is not None and len(r.chart) > 1:
                _bieu_do(r.chart)
            if r.table is not None and len(r.table):
                st.dataframe(r.table, hide_index=True, width="stretch",
                             height=min(360, 38 + 35 * len(r.table)), key=f"tl_tbl_{i}")
                st.download_button("Tải CSV", r.table.to_csv(index=False).encode("utf-8-sig"),
                                   file_name="tro_ly.csv", mime="text/csv", key=f"tl_csv_{i}",
                                   icon=":material/download:", type="tertiary")
        st.html(_gio(m))


tin.html(f'<div class="zl-ngay">Hôm nay</div>')
if not msgs:
    with _bot("zl_b_chao"):
        st.markdown(f"Xin chào 👋 Mình là **{TEN_AI}**. " + tro_ly.huong_dan().text)
for i, m in enumerate(msgs):
    _hien(m, i)

goi_y = ((msgs[-1]["tl"].goi_y if msgs and msgs[-1].get("tl") else []) or list(tro_ly.VI_DU))[:6]
with khung.container(key="zl_goiy"):
    chon = st.pills("Gợi ý", goi_y, key=f"tl_goi_y_{len(msgs)}", label_visibility="collapsed")
with khung.container(key="zl_nhap"):
    hoi = st.chat_input(f"Nhắn cho {TEN_AI}…") or chon

if hoi:
    gio = datetime.now(ZoneInfo("Asia/Ho_Chi_Minh")).strftime("%H:%M")
    msgs.append({"role": "user", "text": hoi, "gio": gio})
    _hien(msgs[-1], len(msgs) - 1)
    with _bot("zl_b_go"):  # "đang soạn tin…" trong lúc tính
        st.html('<div class="zl-go"><span></span><span></span><span></span></div>')
    try:
        tl = tro_ly.tra_loi(hoi, ctx, S.get("tl_truoc"), ai=_ai if dung_ai else None)
    except Exception as e:  # không để lỗi một câu hỏi làm hỏng trang
        tl = tro_ly.TraLoi(f"Xin lỗi, mình gặp lỗi khi trả lời câu này ({e}).")
    S["tl_truoc"] = tl.hieu_la or None
    S["tl_truoc_goc"] = tl.ai_hieu if tl.ai_hieu and not tl.ai_hieu.startswith("(") else hoi
    msgs.append({"role": "assistant", "text": tl.text, "tl": tl,
                 "gio": datetime.now(ZoneInfo("Asia/Ho_Chi_Minh")).strftime("%H:%M")})
    del msgs[:-40]  # giữ 20 lượt gần nhất
    st.rerun()
