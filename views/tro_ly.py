"""Trợ lý dữ liệu dạng hộp chat: hỏi bằng tiếng Việt, trả lời từ dữ liệu của app.
Bộ máy trả lời: tuyensinh/tro_ly.py; tùy chọn Gemini (tuyensinh/ai_gemini.py) chỉ để hiểu câu
hỏi — số liệu luôn tính trong app, dữ liệu học sinh không gửi ra ngoài."""
import base64
from datetime import datetime
from zoneinfo import ZoneInfo

import altair as alt
import streamlit as st

from tuyensinh import ai_gemini, tro_ly, ui
from tuyensinh.schema import NHAP_HOC, TUYEN_SINH

# Ảnh đại diện robot AI (đầu robot + ngôi sao AI) — SVG nhúng dạng ảnh vì st.html không
# cho thẻ <svg> trực tiếp
_SVG = ('<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 24 24">'
        '<path d="M12 4.2V6.4" stroke="#FFFFFF" stroke-width="1.3" stroke-linecap="round"/>'
        '<path fill="#FDE047" d="M12 0.7Q12 2.6 13.9 2.6Q12 2.6 12 4.5Q12 2.6 10.1 2.6Q12 2.6 12 0.7Z"/>'
        '<path fill="#FDE047" d="M20.6 2.8Q20.6 4.2 22.0 4.2Q20.6 4.2 20.6 5.6Q20.6 4.2 19.2 4.2Q20.6 4.2 20.6 2.8Z"/>'
        '<rect x="2.3" y="10.2" width="1.8" height="4.2" rx=".9" fill="#FFFFFF"/>'
        '<rect x="19.9" y="10.2" width="1.8" height="4.2" rx=".9" fill="#FFFFFF"/>'
        '<rect x="4.6" y="6.6" width="14.8" height="11.6" rx="3.6" fill="#FFFFFF"/>'
        '<circle cx="9.2" cy="11.6" r="1.7" fill="#4F46E5"/>'
        '<circle cx="14.8" cy="11.6" r="1.7" fill="#4F46E5"/>'
        '<rect x="9.4" y="14.6" width="5.2" height="1.4" rx=".7" fill="#06B6D4"/>'
        '</svg>')
TEN_AI = "Conan Ro"
BOT_SVG = ('<img alt="" src="data:image/svg+xml;base64,'
           + base64.b64encode(_SVG.encode()).decode() + '">')
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
# Bảng màu kiểu Zalo (sáng / tối)
M = dict(nen="#0F141B" if TOI else "#E9EEF5", khung="#161C24" if TOI else "#FFFFFF",
         vien="#2A3340" if TOI else "#DCE3EC", ban="#0068FF", ban_chu="#FFFFFF",
         bot="#1F2733" if TOI else "#FFFFFF", bot_chu="#E6EAF0" if TOI else "#111827",
         phu="#8B95A5", chip="#1A212B" if TOI else "#FFFFFF")
st.html(f"""<style>
.st-key-zl_khung {{background:{M['khung']}; border:1px solid {M['vien']}; border-radius:16px;
  overflow:hidden; gap:0 !important; box-shadow:0 4px 18px rgba(15,23,42,.08);}}
.st-key-zl_dau {{padding:10px 16px; border-bottom:1px solid {M['vien']}; background:{M['khung']};}}
.st-key-zl_dau .zl-ten {{font-weight:700; font-size:1.02rem; line-height:1.2;}}
.st-key-zl_dau .zl-tt {{font-size:.78rem; color:{M['phu']};}}
.st-key-zl_dau .zl-tt b {{color:#16A34A; font-weight:600;}}
.zl-av {{width:40px; height:40px; border-radius:50%;
  background:linear-gradient(135deg,#6D28D9 0%,#2563EB 55%,#06B6D4 100%);
  display:flex; align-items:center; justify-content:center; color:#fff; font-size:20px; flex:none;}}
.zl-av.nho {{width:30px; height:30px; font-size:15px; margin-top:2px;}}
.zl-av img {{width:28px; height:28px;}} .zl-av.nho img {{width:21px; height:21px;}}
/* bong bóng co theo nội dung, tối đa 78% (người hỏi) / phần còn lại sau ảnh đại diện (trợ lý) */
div:has(> [class*="st-key-zl_u_"]) {{flex:0 1 auto !important; max-width:78%; width:auto !important;}}
div:has(> [class*="st-key-zl_b_"]) {{flex:0 1 auto !important; max-width:calc(100% - 40px);
  width:auto !important; min-width:0;}}
[class*="st-key-zl_u_"], [class*="st-key-zl_b_"] {{width:max-content !important;
  max-width:100% !important; min-width:0;}}
.st-key-zl_tin {{background:{M['nen']}; padding:12px 14px 4px;}}
.st-key-zl_tin > div {{gap:.35rem;}}
.zl-ngay {{text-align:center; margin:4px 0 8px;}}
.zl-ngay span {{background:rgba(100,116,139,.18); color:{M['phu']}; font-size:.72rem;
  padding:2px 10px; border-radius:10px;}}
[class*="st-key-zl_u_"] {{background:{M['ban']}; color:{M['ban_chu']}; border-radius:16px 16px 4px 16px;
  padding:8px 12px 4px; box-shadow:0 1px 2px rgba(0,0,0,.08);}}
[class*="st-key-zl_u_"] p {{color:{M['ban_chu']}; margin:0;}}
[class*="st-key-zl_u_"] .zl-gio {{color:rgba(255,255,255,.75); text-align:right;}}
[class*="st-key-zl_b_"] {{background:{M['bot']}; color:{M['bot_chu']}; border-radius:16px 16px 16px 4px;
  padding:8px 12px 4px; border:1px solid {M['vien']};
  box-shadow:0 1px 2px rgba(0,0,0,.05);}}
[class*="st-key-zl_b_"] [data-testid="stCaptionContainer"] p {{font-size:.76rem;}}
.zl-gio {{font-size:.68rem; color:{M['phu']}; margin-top:2px;}}
.zl-go span {{display:inline-block; width:7px; height:7px; margin:0 2px; border-radius:50%;
  background:{M['phu']}; animation:zlgo 1.2s infinite ease-in-out;}}
.zl-go span:nth-child(2) {{animation-delay:.2s;}} .zl-go span:nth-child(3) {{animation-delay:.4s;}}
@keyframes zlgo {{0%,80%,100% {{opacity:.25; transform:translateY(0)}} 40% {{opacity:1; transform:translateY(-3px)}}}}
.st-key-zl_goiy {{padding:8px 12px 0; background:{M['khung']}; border-top:1px solid {M['vien']};}}
.st-key-zl_goiy [data-testid="stPills"] button {{background:{M['chip']}; color:#0068FF;
  border:1px solid #BFD7FF; border-radius:16px; font-size:.8rem;}}
.st-key-zl_nhap {{padding:6px 12px 12px; background:{M['khung']};}}
.st-key-zl_nhap [data-testid="stChatInput"] > div {{border-radius:22px;}}
.st-key-zl_tin {{height:calc(100vh - 330px) !important; min-height:340px;}}
@media (max-width: 640px) {{ .st-key-zl_tin {{height:calc(100vh - 300px) !important;}}
  div:has(> [class*="st-key-zl_u_"]) {{max-width:88%;}} }}
</style>""")

khung = st.container(key="zl_khung")
with khung.container(key="zl_dau", horizontal=True, vertical_alignment="center", gap="small"):
    st.html(f'<div class="zl-av">{BOT_SVG}</div>', width="content")
    st.html(f'<div class="zl-ten">{TEN_AI}</div><div class="zl-tt"><b>●</b> Trợ lý AI tuyển sinh'
            f' · năm học {nam_hoc}</div>', width="stretch")
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


tin.html(f'<div class="zl-ngay"><span>Hôm nay</span></div>')
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
