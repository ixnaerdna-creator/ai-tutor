import streamlit as st
import google.generativeai as genai
import json

# --- 1. KONFIGURÁCIA STRÁNKY ---
st.set_page_config(page_title="Tractatus - Sokratovský Tútor", layout="wide")

try:
    api_key = st.secrets["GEMINI_API_KEY"]
    genai.configure(api_key=api_key)
except KeyError:
    st.error("Chyba: API kľúč nie je nastavený v Streamlit Secrets.")
    st.stop()

# --- 2. CSS PRE DIZAJN A PROPORCIE ---
st.markdown("""
    <style>
    header {visibility: hidden !important;}
    .block-container { padding-top: 1rem !important; padding-bottom: 0rem !important; }

    /* POSUVNÍKY */
    ::-webkit-scrollbar { width: 14px !important; }
    ::-webkit-scrollbar-track { background: #f1f1f1 !important; border-radius: 8px !important; border-left: 1px solid #cccccc; }
    ::-webkit-scrollbar-thumb { background-color: #666666 !important; border-radius: 8px !important; border: 2px solid #f1f1f1 !important; }
    ::-webkit-scrollbar-thumb:hover { background-color: #333333 !important; }
    * { scrollbar-width: thin; scrollbar-color: #666666 #f1f1f1; }

    .book-title { color: #2c3e50; border-bottom: 2px solid #e9ecef; padding-bottom: 10px; margin-bottom: 10px; }

    /* KOĽAJNICA PRE POSUVNÍK VĽAVO */
    div[data-testid="column"]:nth-of-type(1) div[data-testid="stVerticalBlock"] > div.element-container {
        padding-right: 40px !important; 
    }

    /* ZÁKLADNÉ TLAČIDLO KNIHY (Zamerané len na ľavý stĺpec) */
    div[data-testid="column"]:nth-of-type(1) div[data-testid="stButton"] > button {
        text-align: left !important;
        height: auto !important;
        padding: 15px !important;
        border: none !important;
        background: transparent !important;
        display: block !important;
        width: 100% !important;
    }
    div[data-testid="column"]:nth-of-type(1) div[data-testid="stButton"] > button:hover {
        background-color: #f8f9fa !important;
    }
    
    /* ZLATÁ STREDNÁ CESTA PRE PÍSMO: 18px */
    div[data-testid="column"]:nth-of-type(1) div[data-testid="stButton"] p {
        font-size: 18px !important; 
        line-height: 1.6 !important;
        color: #1a1a1a !important;
        margin: 0 !important;
    }

    /* VYSVIETENÝ TEXT (Zladený na 18px) */
    .highlighted-text {
        background-color: #fff3cd;
        color: #212529;
        padding: 15px; 
        border-radius: 5px;
        border-left: 5px solid #ffc107;
        margin-bottom: 10px;
        font-size: 18px !important;
        line-height: 1.6 !important;
    }
    .highlighted-text b { font-size: 18px !important; }
    
    /* ZMENŠENIE TLAČIDLA VYNULUJ DISKUSIU V PRAVOM STĹPCI */
    div[data-testid="column"]:nth-of-type(2) div[data-testid="stButton"] p {
        font-size: 14px !important;
    }
    </style>
""", unsafe_allow_html=True)

# --- 3. INICIALIZÁCIA SESSION STATE ---
if "text_data" not in st.session_state:
    try:
        with open("text.json", "r", encoding="utf-8") as file:
            st.session_state.text_data = json.load(file)
    except FileNotFoundError:
        st.error("Chyba: Súbor 'text.json' sa nenašiel.")
        st.session_state.text_data = []

if "selected_paragraph" not in st.session_state: st.session_state.selected_paragraph = None
if "explanation" not in st.session_state: st.session_state.explanation = ""
if "messages" not in st.session_state: st.session_state.messages = []
if "prompt_count" not in st.session_state: st.session_state.prompt_count = 0
if "chat_locked" not in st.session_state: st.session_state.chat_locked = False
if "show_explanation" not in st.session_state: st.session_state.show_explanation = False

# --- 4. INICIALIZÁCIA MODELU ---
system_instruction = """
Si sokratovský tútor vyučujúci analytickú filozofiu, konkrétne Wittgensteinov Tractatus Logico-Philosophicus.
Tvojou úlohou je pomáhať študentovi porozumieť textu, ale NIKDY mu nedáš priamu a úplnú odpoveď.
Veď s ním kritický dialóg, pýtaj sa analytické otázky a naviguj ho k tomu, aby na filozofické dôsledky prišiel sám.
Ak sa študent spýta na niečo mimo filozofie alebo textu, zdvorilo ho vráť k danej téme.
"""
if "chat_session" not in st.session_state or st.session_state.chat_session is None:
    model = genai.GenerativeModel(model_name="gemini-3.8-flash", system_instruction=system_instruction)
    st.session_state.chat_session = model.start_chat(history=[])

# --- 5. FUNKCIA GENERÁCIE VYSVETLENIA ---
@st.cache_data(show_spinner=False, ttl=86400)
def generate_explanation(para_text):
    model_exp = genai.GenerativeModel("gemini-3.8-flash")
    prompt = f"Vysvetli odborne, jasne a zrozumiteľne pre vysokoškolského študenta hlavnú myšlienku tohto odseku z Wittgensteinovho Tractatus Logico-Philosophicus. Buď vecný a nezačínaj dialóg:\n\n'{para_text}'"
    try:
        return model_exp.generate_content(prompt).text
    except Exception as e:
        error_msg = str(e)
        if "ResourceExhausted" in error_msg or "429" in error_msg:
            return "⏳ **Tútor je preťažený (Bol dosiahnutý denný alebo minútový limit pre bezplatný API kľúč).**"
        return f"❌ Chyba modelu: {error_msg}"

# --- 6. HLAVNÉ ROZLOŽENIE STRÁNKY ---
col1, col2 = st.columns([2.2, 1])

# ĽAVÝ STĹPEC: TEXT KNIHY
with col1:
    st.markdown("<h3 class='book-title'>📖 Tractatus Logico-Philosophicus</h3>", unsafe_allow_html=True)
    st.info("👈 **Kliknutím na text dostaneš vysvetlenie danej pasáže.**")

    # ZNÍŽENIE VÝŠKY OKNA (Z 650 na 550), ABY NEZASAHovalo DO WINDOWS LIŠTY
    book_container = st.container(height=550, border=False)
    with book_container:
        for para in st.session_state.text_data:
            if st.session_state.selected_paragraph == para['id']:
                st.markdown(f"<div class='highlighted-text'><b>{para['id']}</b> &nbsp; {para['text']}</div>", unsafe_allow_html=True)
            else:
                if st.button(f"**{para['id']}** {para['text']}", key=f"btn_{para['id']}", use_container_width=True):
                    st.session_state.selected_paragraph = para['id']
                    st.session_state.show_explanation = True
                    with st.spinner("Tútor pripravuje výklad k tomuto odseku..."):
                        st.session_state.explanation = generate_explanation(para['text'])
                    st.rerun()
        
        # Zarážka na úplnom spodku
        st.markdown("<div style='height: 150px; width: 100%;'></div>", unsafe_allow_html=True)

# PRAVÝ STĹPEC: VYSVETLENIE A DISKUSIA
with col2:
    col_title, col_btn = st.columns([1.5, 1])
    with col_title:
        # ZMENŠENÝ NADPIS (zo 3 krížikov ### na 4 ####)
        st.markdown(f"#### 💬 Diskusia ({st.session_state.prompt_count} / 20)")
    with col_btn:
        if st.button("🔄 Vynuluj diskusiu", use_container_width=True):
            st.session_state.messages = []
            st.session_state.prompt_count = 0
            st.session_state.chat_locked = False
            model_new = genai.GenerativeModel(model_name="gemini-3.8-flash", system_instruction=system_instruction)
            st.session_state.chat_session = model_new.start_chat(history=[])
            st.rerun()

    st.markdown("<hr style='margin: 0px 0 10px 0;'>", unsafe_allow_html=True)

    if st.session_state.selected_paragraph and st.session_state.show_explanation:
        st.markdown(f"**💡 Výklad (Odsek {st.session_state.selected_paragraph})**")
        if "preťažený" in st.session_state.explanation or "❌" in st.session_state.explanation:
            st.error(st.session_state.explanation)
        else:
            st.info(st.session_state.explanation)
        st.markdown("<br>", unsafe_allow_html=True)

    # ZNÍŽENÁ VÝŠKA AJ PRE CHAT
    chat_height = 200 if (st.session_state.selected_paragraph and st.session_state.show_explanation) else 420
    chat_container = st.container(height=chat_height, border=True)

    with chat_container:
        if len(st.session_state.messages) == 0:
            st.write("Tu môžete začať diskusiu kedykoľvek...")

        for msg in st.session_state.messages:
            with st.chat_message(msg["role"]):
                st.markdown(msg["content"])
        
        st.markdown("<div style='height: 50px;'></div>", unsafe_allow_html=True)

    if st.session_state.chat_locked:
        st.error("Dosiahli ste limit 20 správ.")
    else:
        user_msg = st.chat_input("Položte otázku alebo napíšte svoju úvahu...")
        if user_msg:
            st.session_state.show_explanation = False
            st.session_state.prompt_count += 1
            st.session_state.messages.append({"role": "user", "content": user_msg})

            with chat_container:
                with st.chat_message("user"):
                    st.markdown(user_msg)

                with st.chat_message("assistant"):
                    with st.spinner("Tútor premýšľa..."):
                        selected_text_raw = next((p['text'] for p in st.session_state.text_data if p['id'] == st.session_state.selected_paragraph), "") if st.session_state.selected_paragraph else ""
                        context_str = f"[Zameranie na odsek {st.session_state.selected_paragraph}: '{selected_text_raw}']\n\n" if selected_text_raw else ""
                        full_context_msg = f"{context_str}Otázka študenta: {user_msg}"

                        try:
                            response = st.session_state.chat_session.send_message(full_context_msg)
                            response_text = response.text
                        except Exception as e:
                            error_msg = str(e)
                            if "ResourceExhausted" in error_msg or "429" in error_msg:
                                response_text = "⏳ **Tútor je preťažený.** (Denný alebo minútový limit Googlu bol vyčerpaný)."
                            else:
                                 response_text = f"❌ Chyba modelu: {error_msg}"
                            
                            st.session_state.prompt_count -= 1
                            
                        st.markdown(response_text)

            st.session_state.messages.append({"role": "assistant", "content": response_text})
            st.rerun()

    if len(st.session_state.messages) > 0:
        chat_history_text = "Tractatus Logico-Philosophicus - Prepis diskusie\n" + "="*50 + "\n\n"
        for msg in st.session_state.messages:
            role_name = "ŠTUDENT" if msg["role"] == "user" else "TÚTOR"
            chat_history_text += f"{role_name}:\n{msg['content']}\n\n"

        st.download_button("📥 Stiahnuť prepis (TXT)", data=chat_history_text, file_name="wittgenstein_diskusia.txt", mime="text/plain", use_container_width=True)