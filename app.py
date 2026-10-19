import streamlit as st
from google import genai
from google.genai import types
import json

# --- 1. KONFIGURÁCIA STRÁNKY ---
st.set_page_config(page_title="Tractatus - Sokratovský Tútor", layout="wide")

try:
    api_key = st.secrets["GEMINI_API_KEY"]
except KeyError:
    st.error("Chyba: API kľúč nie je nastavený v Streamlit Secrets.")
    st.stop()

@st.cache_resource
def get_client():
    return genai.Client(api_key=api_key)

client = get_client()

# Rozšírená kaskáda modelov z vášho zoznamu: pri chybe 429, 503 alebo 500 okamžite zaskočí ďalší
MODEL_CASCADE = [
    "gemini-3.5-flash-lite",
    "gemini-3.7-flash",
    "gemini-3.6-flash",
    "gemini-3.5-flash",
    "gemini-3.8-flash",
    "gemini-3.1-flash-lite",
    "gemini-2.5-flash-lite",
    "gemini-flash-lite-latest",
    "gemini-flash-latest"
]

# --- 2. CSS PRE DIZAJN, BEZ RÁMČEKOV A S MINIMÁLNYMI ROZOSTUPMI ---
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

    /* STIAHNUTIE MEDZIER MEDZI ODSTAVCAMI NA MINIMUM */
    div[data-testid="stVerticalBlock"] {
        gap: 0.1rem !important;
    }
    div.element-container {
        margin-bottom: 0px !important;
    }

    /* ÚPLNÉ ZRUŠENIE VŠETKÝCH RÁMČEKOV, OBRYSOV A POZADÍ PRE ODSTAVCE */
    div.stButton > button[kind="tertiary"],
    div[data-testid="stButton"] > button {
        border: none !important;
        outline: none !important;
        box-shadow: none !important;
        background: transparent !important;
        background-color: transparent !important;
        padding: 3px 25px 3px 6px !important;
        margin: 0px !important;
        text-align: left !important;
        justify-content: flex-start !important;
        width: 100% !important;
        min-height: 0px !important;
        height: auto !important;
    }

    div.stButton > button[kind="tertiary"]:hover,
    div.stButton > button[kind="tertiary"]:focus,
    div.stButton > button[kind="tertiary"]:active,
    div[data-testid="stButton"] > button:hover,
    div[data-testid="stButton"] > button:focus,
    div[data-testid="stButton"] > button:active {
        border: none !important;
        outline: none !important;
        box-shadow: none !important;
        background: transparent !important;
        background-color: transparent !important;
    }

    div[data-testid="stButton"] > button:hover p,
    div[data-testid="stButton"] > button:hover span {
        color: #0056b3 !important;
    }

    /* PÍSMO PRED VYSVIETENÍM (19px) */
    div[data-testid="stButton"] button p,
    div[data-testid="stButton"] button span,
    div[data-testid="stButton"] button div {
        font-size: 19px !important;
        line-height: 1.45 !important;
        color: #1a1a1a !important;
        margin: 0px !important;
        padding: 0px !important;
        white-space: normal !important;
        text-align: left !important;
    }

    /* VYSVIETENÝ TEXT PO KLIKNUTÍ (20px) */
    .highlighted-text {
        background-color: #fff3cd;
        color: #212529;
        padding: 6px 25px 6px 10px;
        border-radius: 4px;
        border-left: 4px solid #ffc107;
        margin: 2px 0px;
        font-size: 20px !important;
        line-height: 1.45 !important;
    }
    .highlighted-text b {
        font-size: 20px !important;
    }

    /* Tlačidlo Vynuluj diskusiu */
    div[data-testid="stButton"] > button[kind="secondary"] {
        border: 1px solid #ced4da !important;
        background-color: #f8f9fa !important;
        padding: 4px 10px !important;
        justify-content: center !important;
        text-align: center !important;
        border-radius: 5px !important;
    }
    div[data-testid="stButton"] > button[kind="secondary"] p {
        font-size: 14px !important;
        text-align: center !important;
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

# --- 4. SYSTÉMOVÉ INŠTRUKCIE A NEPRIESTRELNÉ KASKÁDOVÉ VOLANIE API ---
system_instruction = """
Si sokratovský tútor vyučujúci analytickú filozofiu, konkrétne Wittgensteinov Tractatus Logico-Philosophicus.
Tvojou úlohou je pomáhať študentovi porozumieť textu, ale NIKDY mu nedáš priamu a úplnú odpoveď.
Veď s ním kritický dialóg, pýtaj sa analytické otázky a naviguj ho k tomu, aby na filozofické dôsledky prišiel sám.
Ak sa študent spýta na niečo mimo filozofie alebo textu, zdvorilo ho vráť k danej téme.
"""

def generate_explanation(para_text):
    # Cache ukladáme manuálne do session_state len pre úspešné odpovede (aby sa nezacachovala chybová hláška)
    if "exp_cache" not in st.session_state:
        st.session_state.exp_cache = {}
    if para_text in st.session_state.exp_cache:
        return st.session_state.exp_cache[para_text]

    prompt = f"Vysvetli odborne, jasne a zrozumiteľne pre vysokoškolského študenta hlavnú myšlienku tohto odseku z Wittgensteinovho Tractatus Logico-Philosophicus. Buď vecný a nezačínaj dialóg:\n\n'{para_text}'"
    last_error = ""
    for model_name in MODEL_CASCADE:
        try:
            response = client.models.generate_content(
                model=model_name,
                contents=prompt
            )
            if response and response.text:
                st.session_state.exp_cache[para_text] = response.text
                return response.text
        except Exception as e:
            last_error = f"({model_name}): {str(e)}"
            # Pri AKEJKOĽVEK chybe (429, 503, 500, 404) okamžite skúšame ďalší model v poradí
            continue
    return f"⏳ **Všetky záložné modely sú momentálne vyťažené.** Posledná správa: {last_error}"

def send_chat_with_fallback(messages_history, current_context_msg):
    contents = []
    for m in messages_history[:-1]:
        role = "user" if m["role"] == "user" else "model"
        contents.append(types.Content(role=role, parts=[types.Part.from_text(text=m["content"])]))
    
    contents.append(types.Content(role="user", parts=[types.Part.from_text(text=current_context_msg)]))
    
    config = types.GenerateContentConfig(
        system_instruction=system_instruction,
        temperature=0.7
    )
    
    last_error = ""
    for model_name in MODEL_CASCADE:
        try:
            response = client.models.generate_content(
                model=model_name,
                contents=contents,
                config=config
            )
            if response and response.text:
                return response.text, True
        except Exception as e:
            last_error = f"({model_name}): {str(e)}"
            continue
    return f"⏳ **Tútor je preťažený.** Všetky modely v kaskáde sú dočasne obsadené ({last_error}). Skúste otázku zopakovať o malú chvíľu.", False

# --- 5. HLAVNÉ ROZLOŽENIE STRÁNKY ---
col1, col2 = st.columns([2.2, 1])

# ĽAVÝ STĹPEC: TEXT KNIHY
with col1:
    st.markdown("<h3 class='book-title'>📖 Tractatus Logico-Philosophicus</h3>", unsafe_allow_html=True)
    st.info("👈 **Kliknutím na text dostaneš vysvetlenie danej pasáže.**")

    book_container = st.container(height=550, border=False)
    with book_container:
        for para in st.session_state.text_data:
            if st.session_state.selected_paragraph == para['id']:
                st.markdown(f"<div class='highlighted-text'><b>{para['id']}</b> &nbsp; {para['text']}</div>", unsafe_allow_html=True)
            else:
                try:
                    clicked = st.button(f"**{para['id']}** {para['text']}", key=f"btn_{para['id']}", type="tertiary", use_container_width=True)
                except TypeError:
                    clicked = st.button(f"**{para['id']}** {para['text']}", key=f"btn_{para['id']}", use_container_width=True)
                
                if clicked:
                    st.session_state.selected_paragraph = para['id']
                    st.session_state.show_explanation = True
                    with st.spinner("Tútor pripravuje výklad k tomuto odseku..."):
                        st.session_state.explanation = generate_explanation(para['text'])
                    st.rerun()
        
        st.markdown("<div style='height: 150px; width: 100%;'></div>", unsafe_allow_html=True)

# PRAVÝ STĹPEC: VYSVETLENIE A DISKUSIA
with col2:
    col_title, col_btn = st.columns([1.5, 1])
    with col_title:
        st.markdown(f"#### 💬 Diskusia ({st.session_state.prompt_count} / 20)")
    with col_btn:
        if st.button("🔄 Vynuluj diskusiu", type="secondary", use_container_width=True):
            st.session_state.messages = []
            st.session_state.prompt_count = 0
            st.session_state.chat_locked = False
            st.rerun()

    st.markdown("<hr style='margin: 0px 0 10px 0;'>", unsafe_allow_html=True)

    if st.session_state.selected_paragraph and st.session_state.show_explanation:
        st.markdown(f"**💡 Výklad (Odsek {st.session_state.selected_paragraph})**")
        if "vyťažené" in st.session_state.explanation or "❌" in st.session_state.explanation:
            st.error(st.session_state.explanation)
        else:
            st.info(st.session_state.explanation)
        st.markdown("<br>", unsafe_allow_html=True)

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

                        response_text, success = send_chat_with_fallback(st.session_state.messages, full_context_msg)
                        if not success:
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