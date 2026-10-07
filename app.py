import os
import html
import requests
import streamlit as st

st.set_page_config(page_title="بياع AI", page_icon="🛒", layout="centered")

# ================== CONFIG (from secrets, nothing hardcoded) ==================
def get_secret(name, default=None):
    try:
        return st.secrets[name]                    # .streamlit/secrets.toml locally, or the Secrets box on Streamlit Cloud
    except Exception:
        return os.environ.get(name, default)       # fallback: environment variables

API_URL = get_secret("API_URL")
API_KEY = get_secret("API_KEY")
REQUEST_TIMEOUT = 300                              # seconds (4 chained LLM calls are slow)

if not API_URL or not API_KEY:
    st.error("API_URL و API_KEY مش متظبطين. ضيفهم في ملف secrets.toml (محلياً) أو في Secrets (على Streamlit Cloud).")
    st.stop()

INTENT_AR = {
    "product_search": "بحث عن منتج",
    "price_inquiry": "استفسار عن السعر",
    "availability_check": "استفسار عن التوفر",
    "comparison": "مقارنة منتجات",
    "policy_or_faq": "سياسات وأسئلة شائعة",
    "order_issue": "مشكلة في طلب",
    "ready_to_buy": "جاهز للشراء",
    "other": "أخرى",
}
ACTION_AR = {
    "send_reply": "إرسال الرد",
    "ask_clarifying_question": "طلب توضيح من العميل",
    "offer_substitute": "اقتراح بديل",
    "confirm_order": "تأكيد الطلب",
    "escalate_to_human": "تحويل لموظف",
    "follow_up_later": "المتابعة لاحقاً",
}
QUICK_QUESTIONS = [
    "عايز لبن بدون لاكتوز",
    "عايز أرز للمحشي وميزانيتي ١٠٠ جنيه",
    "الحد الأدنى للطلب كام؟",
    "بتوصلوا إسكندرية؟",
    "الطلب اتأخر بقاله يومين وده مش مقبول!",
]

# ================== STYLE ==================
st.markdown("""
<style>
@import url('https://fonts.googleapis.com/css2?family=Cairo:wght@400;600;800&display=swap');

.stApp, .stApp p, .stApp li, .stApp h1, .stApp h2, .stApp h3, .stApp label,
.stApp textarea, .stApp button { font-family: 'Cairo', sans-serif; }

.stApp { direction: rtl; text-align: right; background: #FFF8EE; }
section[data-testid="stSidebar"] { direction: rtl; background: #FFFFFF; border-left: 1px solid #F0E3CC; }
#MainMenu, footer, header[data-testid="stHeader"] { visibility: hidden; }
.block-container { padding-top: 0 !important; max-width: 820px; }

/* storefront awning */
.awning {
    height: 26px; margin: 0 -1rem 14px -1rem;
    background: repeating-linear-gradient(90deg, #1B7F4B 0 34px, #FFFFFF 34px 68px);
    border-radius: 0 0 22px 22px; box-shadow: 0 4px 10px rgba(0,0,0,.12);
}
/* shop sign */
.hero {
    display: flex; align-items: center; gap: 16px;
    background: linear-gradient(135deg, #1B7F4B, #14613A);
    border: 4px solid #F2B84B; border-radius: 20px;
    padding: 16px 22px; margin-bottom: 18px; color: #fff;
    box-shadow: 0 6px 16px rgba(27,127,75,.3);
}
.hero-logo { font-size: 46px; background: #fff; border-radius: 50%; width: 76px; height: 76px;
             display: flex; align-items: center; justify-content: center; }
.hero-title { font-size: 40px; font-weight: 800; line-height: 1.1; }
.hero-title span { background: #F28C28; color: #fff; padding: 0 10px; border-radius: 10px; margin-right: 6px; }
.hero-sub { font-size: 15px; opacity: .92; margin-top: 4px; }

/* chat bubbles */
[data-testid="stChatMessage"] {
    background: #FFFFFF; border: 1px solid #F0E3CC; border-radius: 18px;
    padding: 12px 16px; box-shadow: 0 2px 6px rgba(0,0,0,.04);
}

/* product card = shelf label */
.product { border: 2px dashed #F2B84B; background: #FFFDF5; border-radius: 16px;
           padding: 12px 16px; margin: 10px 0; }
.p-top { display: flex; justify-content: space-between; align-items: center; font-size: 13px; color: #8A6D3B; }
.p-name { font-size: 20px; font-weight: 800; color: #2B2B2B; margin: 6px 0; }
.p-price { display: inline-block; background: #FFE14D; color: #C62828; font-size: 26px; font-weight: 800;
           padding: 2px 16px; border-radius: 10px; transform: rotate(-1.5deg); }
.p-price small { font-size: 14px; }
.p-id { font-size: 12px; color: #999; margin-top: 6px; }
.stock { padding: 2px 12px; border-radius: 999px; font-weight: 600; font-size: 13px; }
.stock.ok { background: #E3F4EA; color: #1B7F4B; }
.stock.no { background: #FDE5E5; color: #C62828; }

/* badges + reason */
.badges { display: flex; flex-wrap: wrap; gap: 8px; margin: 8px 0; }
.badge { padding: 4px 12px; border-radius: 999px; font-size: 13px; font-weight: 600; }
.badge.intent { background: #E8F1FF; color: #1D4ED8; }
.badge.action { background: #FFF0DC; color: #C2560C; }
.reason { background: #F7F4EE; border-right: 4px solid #1B7F4B; border-radius: 8px;
          padding: 8px 12px; font-size: 14px; color: #444; margin-top: 6px; }

/* buttons */
.stButton > button { width: 100%; border-radius: 12px; border: 1px solid #F2B84B; background: #FFFDF5;
                     color: #2B2B2B; font-weight: 600; text-align: right; }
.stButton > button:hover { background: #F2B84B; color: #fff; border-color: #F2B84B; }

/* force dark text everywhere (even if the browser is in dark mode) */
.stApp { color: #2B2B2B !important; }
[data-testid="stMarkdownContainer"] p,
[data-testid="stMarkdownContainer"] li,
[data-testid="stMarkdownContainer"] h1,
[data-testid="stMarkdownContainer"] h2,
[data-testid="stMarkdownContainer"] h3,
[data-testid="stMarkdownContainer"] h4,
[data-testid="stMarkdownContainer"] strong { color: #2B2B2B !important; }
[data-testid="stCaptionContainer"],
[data-testid="stSpinner"] * { color: #555 !important; }
[data-testid="stChatInput"] textarea { color: #2B2B2B !important; background: #FFFFFF !important; }
[data-testid="stChatInput"] textarea::placeholder { color: #888 !important; }
.hero .hero-title, .hero .hero-sub { color: #FFFFFF !important; }
.stButton > button:hover { color: #2B2B2B !important; }
</style>
""", unsafe_allow_html=True)

# ================== BACKEND CALL ==================
def ask_backend(prompt: str) -> dict:
    base = API_URL.strip().rstrip("/")
    if base.endswith("/answer"):                   # in case /answer was pasted into the URL by mistake
        base = base[: -len("/answer")]

    r = requests.post(
        f"{base}/answer",
        headers={"Authorization": f"Bearer {API_KEY}", "ngrok-skip-browser-warning": "true"},
        data={"prompt": prompt},
        timeout=REQUEST_TIMEOUT,
    )
    if r.status_code == 401:
        raise RuntimeError("مفتاح الـ API غير صحيح.")
    if r.status_code == 404:
        if "ngrok" in r.text.lower():
            raise RuntimeError("الـ ngrok tunnel مش شغال أو الرابط قديم. شغّل الـ backend تاني وحدّث API_URL في الـ Secrets.")
        raise RuntimeError("السيرفر شغال بس مفيهوش /answer. أعد تشغيل خلية الـ API وبعدها خلية الـ ngrok.")
    if not r.ok:
        try:
            detail = r.json().get("detail", r.text)
        except Exception:
            detail = r.text
        raise RuntimeError(f"خطأ من السيرفر ({r.status_code}): {detail}")
    return r.json()

# ================== RENDERING ==================
def render_assistant(data: dict):
    st.markdown(data.get("suggested_reply", ""))

    product = data.get("recommended_product")
    if product:
        in_stock = product.get("in_stock", False)
        stock_cls, stock_txt = ("ok", "متوفر") if in_stock else ("no", "غير متوفر")
        st.markdown(f"""
<div class="product">
  <div class="p-top"><span>🏷️ المنتج المقترح</span><span class="stock {stock_cls}">{stock_txt}</span></div>
  <div class="p-name">{html.escape(str(product.get("name", "")))}</div>
  <div class="p-price">{float(product.get("price_egp", 0)):g} <small>جنيه</small></div>
  <div class="p-id">كود المنتج: {html.escape(str(product.get("product_id", "")))}</div>
</div>""", unsafe_allow_html=True)

    intent = INTENT_AR.get(data.get("customer_intent"), data.get("customer_intent", ""))
    action = ACTION_AR.get(data.get("next_action"), data.get("next_action", ""))
    st.markdown(f"""
<div class="badges">
  <span class="badge intent">🎯 نية العميل: {html.escape(str(intent))}</span>
  <span class="badge action">➡️ الإجراء التالي: {html.escape(str(action))}</span>
</div>
<div class="reason"><b>سبب الاختيار:</b> {html.escape(str(data.get("reason", "")))}</div>
""", unsafe_allow_html=True)

# ================== PAGE ==================
st.markdown("""
<div class="awning"></div>
<div class="hero">
  <div class="hero-logo">🛒</div>
  <div>
    <div class="hero-title">بياع <span>AI</span></div>
    <div class="hero-sub">مساعد المبيعات الذكي · اكتب رسالة العميل وهنجهزلك الرد المناسب</div>
  </div>
</div>
""", unsafe_allow_html=True)

with st.sidebar:
    st.markdown("### 🛍️ أسئلة سريعة")
    for q in QUICK_QUESTIONS:
        if st.button(q, key=f"quick_{q}"):
            st.session_state.queued = q
    st.markdown("---")
    if st.button("🗑️ مسح المحادثة"):
        st.session_state.messages = []
        st.rerun()
    st.caption("بياع AI · مساعد المبيعات الذكي")

if "messages" not in st.session_state:
    st.session_state.messages = []

if not st.session_state.messages:
    with st.chat_message("assistant", avatar="🛒"):
        st.markdown("أهلاً بيك في **بياع AI** 👋  \nاكتب رسالة العميل وأنا هحدد نيته، أرشحله المنتج المناسب، وأجهزلك الرد.")

for m in st.session_state.messages:
    if m["role"] == "user":
        with st.chat_message("user", avatar="🙋"):
            st.markdown(m["content"])
    else:
        with st.chat_message("assistant", avatar="🛒"):
            if "error" in m:
                st.error(m["error"])
            else:
                render_assistant(m["data"])

prompt = st.chat_input("اكتب رسالة العميل هنا...") or st.session_state.pop("queued", None)

if prompt:
    st.session_state.messages.append({"role": "user", "content": prompt})
    with st.chat_message("user", avatar="🙋"):
        st.markdown(prompt)

    with st.chat_message("assistant", avatar="🛒"):
        try:
            with st.spinner("بياع AI بيجهز الرد..."):
                data = ask_backend(prompt)
            render_assistant(data)
            st.session_state.messages.append({"role": "assistant", "data": data})
        except requests.exceptions.Timeout:
            err = "السيرفر أخد وقت طويل. جرّب تاني."
        except requests.exceptions.ConnectionError:
            err = "مش قادر أوصل للسيرفر. اتأكد إن الـ ngrok شغال وإن الرابط في الـ Secrets هو الرابط الحالي."
        except Exception as e:
            err = str(e)
        else:
            err = None
        if err:
            st.error(err)
            st.session_state.messages.append({"role": "assistant", "error": err})