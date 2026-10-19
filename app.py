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

# --- 2. CSS PRE KRAJŠÍ DIZAJN A ROZLOŽENIE ---
st.markdown("""
    <style>
    /* ODSTRÁNENIE MEDZIER A SKRYTIE FOOTERA */
    .block-container { padding-top: 1.5rem !important; padding-bottom: 0rem !important; }
    footer {visibility: hidden;}
    
    /* 1. VÝRAZNEJŠÍ POSUVNÍK (SCROLLBAR) */
    ::-webkit-scrollbar {
        width: 16px !important;
        height: 16px !important;
    }
    ::-webkit-scrollbar-track {
        background: #e9ecef !important; 
        border-radius: 8px !important;
        border: 1px solid #dee2e6 !important;
    }
    ::-webkit-scrollbar-thumb {
        background: #6c757d !important; 
        border-radius: 8px !important;
        border: 3px solid #e9ecef !important;
    }
    ::-webkit-scrollbar-thumb:hover {
        background: #495057 !important; 
    }

    /* 6. ELEGANTNEJŠÍ DIZAJN KNIHY (Pätkové písmo, tieňovanie) */
    .book-title {
        font-family: 'Georgia', serif;
        color: #2c3e50;
        border-bottom: 2px solid #e9ecef;
        padding-bottom: 10px;
        margin-bottom: 20px;
    }
    
    /* Úprava tlačidiel v ĽAVOM stĺpci (maskovanie za text knihy) */
    [data-testid="column"]:nth-of-type(1) button {
        white-space: normal !important;
        text-align: left !important;
        height: auto !important;
        padding: 10px 15px !important;
        display: block !important;
        width: 100% !important;
        border: none !important;
        background: transparent !important;
        box-shadow: none !important;
        color: #1a1a1a !important;
        transition: background-color 0.2s;
        border-radius: 5px !important;
        margin-bottom: 5px !important;
    }
    [data-testid="column"]:nth-of-type(1) button p {
        white-space: normal !important;
        font-family: 'Georgia', serif !important;
        font-size: 19px !important;
        line-height: 1.8 !important;
        margin: 0 !important;
    }
    [data-testid="column"]:nth-of-type(1) button:hover {
        background-color: #f8f9fa !important;
        border-left: 4px solid #ced4da !important;
    }
    
    /* Zvýraznený odsek po kliknutí (krajšia žltá knižná farba) */
    .highlighted-text {
        background-color: #fff3cd;
        color: #212529;
        padding: 15px;
        border-radius: 5px;
        border-left: 5px solid #ffc107;
        margin-bottom: 10px;
        font-family: 'Georgia', serif;
        font-size: 19px;
        line-height: 1.8;
        box-shadow: 0 2px 4px rgba(0,0,0,0.05);
    }

    /* 2. ZAMRAZENIE PRAVÉHO PANELU (Sticky stĺpec) */
    [data-testid="column"]:nth-of-type(2) {
        position: sticky !important;
        top: 2rem !important;
        height: max-content;
        align-self: flex-start;
        background-color: #ffffff;
        padding: 15px;
        border-radius: 10px;
        box-shadow: 0 4px 6px rgba(0,0,0,0.05);
        border: 1px solid #f1f3f5;
    }
    
    /* Zabezpečenie rolovania vo vnútri ľavého stĺpca */
    div[data-testid="column"]:nth-of-type(1) div[data-testid="stVerticalBlock"]:first-of-type {
        height: 88vh !important;
        overflow-y: auto !important;
        padding-right: 15px !important;
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

if "selected_paragraph" not in st.session_state:
    st.session_state.selected_paragraph = None
if "explanation" not in st.session_state:
    st.session_state.explanation = ""
if "messages" not in st.session_state:
    st.session_state.messages = []
if "prompt_count" not in st.session_state:
    st.session_state.prompt_count = 0
if "chat_locked" not in st.session_state:
    st.session_state.chat_locked = False
if "show_explanation" not in st.session_state:
    st.session_state.show_explanation = False

# Inicializácia modelu (Chat)
if "chat_session" not in st.session_state or st.session_state.chat_session is None:
    system_instruction = """
    Si sokratovský tútor vyučujúci analytickú filozofiu, konkrétne Wittgensteinov Tractatus Logico-Philosophicus. 
    Tvojou úlohou je pomáhať študentovi porozumieť textu, ale NIKDY mu nedáš priamu a úplnú odpoveď.
    Veď s ním kritický dialóg, pýtaj sa analytické otázky a naviguj ho k tomu, aby na filozofické dôsledky prišiel sám.
    Ak sa študent spýta na niečo mimo filozofie alebo textu, zdvorilo ho vráť k danej téme.
    """
    model = genai.GenerativeModel(
        model_name="gemini-3.8-flash",
        system_instruction=system_instruction
    )
    st.session_state.chat_session = model.start_chat(history=[])

# --- 4. FUNKCIA NA GENERÁCIU PASÍVNEHO VYSVETLENIA ---
@st.cache_data(show_spinner=False, ttl=86400)
def generate_explanation(para_text):
    model = genai.GenerativeModel("gemini-3.8-flash")
    prompt = f"Vysvetli odborne, jasne a zrozumiteľne pre vysokoškolského študenta hlavnú myšlienku tohto odseku z Wittgensteinovho Tractatus Logico-Philosophicus. Buď vecný a nezačínaj dialóg:\n\n'{para_text}'"
    try:
        return model.generate_content(prompt).text
    except Exception as e:
        if "ResourceExhausted" in str(e) or "429" in str(e):
            return "⏳ **Tútor je momentálne preťažený.** Počkajte 30 sekúnd a skúste odsek vybrať znova."
        return f"❌ Neočakávaná chyba: {e}"

# --- 5. HLAVNÉ ROZLOŽENIE STRÁNKY ---
col1, col2 = st.columns([2.2, 1])

# ĽAVÝ STĹPEC: TEXT KNIHY
with col1:
    st.markdown("<h2 class='book-title'>📖 Tractatus Logico-Philosophicus</h2>", unsafe_allow_html=True)
    
    book_container = st.container(border=False)
    with book_container:
        for para in st.session_state.text_data:
            para_display = f"<b>{para['id']}</b> &nbsp; {para['text']}"
            
            if st.session_state.selected_paragraph == para['id']:
                st.markdown(f"<div class='highlighted-text'>{para_display}</div>", unsafe_allow_html=True)
            else:
                if st.button(para_display, key=f"btn_{para['id']}", use_container_width=True):
                    st.session_state.selected_paragraph = para['id']
                    # 5. Keď sa klikne na text, zapne sa zobrazenie vysvetlenia (bez zrušenia chatu)
                    st.session_state.show_explanation = True 
                    with st.spinner("Tútor pripravuje výklad k tomuto odseku..."):
                        st.session_state.explanation = generate_explanation(para['text'])
                    st.rerun()

# PRAVÝ STĹPEC: VYSVETLENIE A DISKUSIA
with col2:
    # 3. FUNKCIA VYNULOVANIA
    col_title, col_btn = st.columns([2, 1])
    with col_title:
        st.markdown(f"### 💬 Diskusia ({st.session_state.prompt_count} / 20)")
    with col_btn:
        if st.button("🔄 Vynulovať", help="Zmaže aktuálnu diskusiu a začne odznova", use_container_width=True):
            st.session_state.messages = []
            st.session_state.prompt_count = 0
            st.session_state.chat_locked = False
            st.session_state.chat_session = model.start_chat(history=[])
            st.rerun()
            
    st.markdown("<hr style='margin: 5px 0 15px 0;'>", unsafe_allow_html=True)

    # 5. ZOBRAZENIE VYSVETLENIA (Len ak je aktívne show_explanation)
    if st.session_state.selected_paragraph and st.session_state.show_explanation:
        st.markdown(f"**💡 Výklad (Odsek {st.session_state.selected_paragraph})**")
        if "preťažený" in st.session_state.explanation:
            st.warning(st.session_state.explanation)
        else:
            st.info(st.session_state.explanation)
        st.markdown("<br>", unsafe_allow_html=True)
    
    # Výška chatu dynamicky podľa toho, či svieti vysvetlenie
    chat_height_css = "30vh" if (st.session_state.selected_paragraph and st.session_state.show_explanation) else "65vh"
    
    st.markdown(f"""
        <style>
        div[data-testid="column"]:nth-of-type(2) div[data-testid="stVerticalBlock"]:nth-of-type(2) {{
            height: {chat_height_css} !important;
            overflow-y: auto !important;
            padding: 10px;
        }}
        </style>
    """, unsafe_allow_html=True)