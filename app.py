import streamlit as st
import google.generativeai as genai
import json

# --- 1. KONFIGURÁCIA STRÁNKY ---
st.set_page_config(page_title="Tractatus - Sokratovský Tútor", layout="wide")

# Získanie skrytého kľúča priamo zo servera Streamlitu
try:
    api_key = st.secrets["GEMINI_API_KEY"]
    genai.configure(api_key=api_key)
except KeyError:
    st.error("Chyba: API kľúč nie je nastavený v Streamlit Secrets.")
    st.stop()

# --- 2. CSS PRE DIZAJN A ROZLOŽENIE ---
st.markdown("""
    <style>
    /* ODSTRÁNENIE ZBYTOČNÝCH MEDZIER NA STRÁNKE A MAXIMALIZÁCIA VÝŠKY */
    .block-container {
        padding-top: 2rem !important; /* Zmenšená horná medzera */
        padding-bottom: 0rem !important; /* Žiadna dolná medzera */
        margin-bottom: 0rem !important;
    }
    
    /* Skrytie Streamlit footera, aby neuberal miesto dole */
    footer {visibility: hidden;}

    /* Zväčšenie písma pre text knihy a riadkovanie */
    .book-text {
        font-size: 18px !important;
        line-height: 1.7 !important;
    }
    
    /* Úprava tlačidiel v ĽAVOM stĺpci (maskovanie za text) */
    [data-testid="column"]:nth-of-type(1) button {
        white-space: normal !important;
        text-align: left !important;
        height: auto !important;
        padding: 8px 10px !important;
        display: block !important;
        width: 100% !important;
        border: none !important;
        background: transparent !important;
        box-shadow: none !important;
        color: inherit !important;
        transition: background-color 0.2s;
        border-radius: 5px !important;
        margin: 0 !important;
        justify-content: flex-start !important;
    }
    [data-testid="column"]:nth-of-type(1) button p {
        white-space: normal !important;
        margin: 0 !important;
        text-align: left !important;
        font-size: 18px !important;
        line-height: 1.7 !important;
    }
    [data-testid="column"]:nth-of-type(1) button:hover {
        background-color: #f8f9fa !important;
        color: black !important;
    }
    
    /* Zvýraznený odsek po kliknutí */
    .highlighted-text {
        background-color: #fff3cd;
        color: black;
        padding: 12px 10px;
        border-radius: 8px;
        border-left: 5px solid #ffc107;
        margin-bottom: 5px;
        font-size: 18px;
        line-height: 1.7;
    }

    /* Výraznejší posuvník (Scrollbar) PRE ĽAVÝ KONTAJNER */
    [data-testid="stVerticalBlock"] > div > div > div > div > div > div[data-testid="stVerticalBlock"] {
        overflow-y: auto !important;
    }
    ::-webkit-scrollbar {
        width: 14px;
    }
    ::-webkit-scrollbar-track {
        background: #f1f1f1; 
        border-radius: 10px;
    }
    ::-webkit-scrollbar-thumb {
        background: #888; 
        border-radius: 10px;
        border: 3px solid #f1f1f1;
    }
    ::-webkit-scrollbar-thumb:hover {
        background: #555; 
    }
    </style>
""", unsafe_allow_html=True)

# --- 3. INICIALIZÁCIA SESSION STATE ---
if "text_data" not in st.session_state:
    try:
        with open("text.json", "r", encoding="utf-8") as file:
            st.session_state.text_data = json.load(file)
    except FileNotFoundError:
        st.error("Chyba: Nepodarilo sa načítať text. Súbor 'text.json' sa nenašiel.")
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

# Inicializácia modelu pre Sokratovskú DISKUSIU
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
def generate_explanation(para_text):
    model = genai.GenerativeModel("gemini-3.8-flash")
    prompt = f"Vysvetli odborne, jasne a zrozumiteľne pre vysokoškolského študenta hlavnú myšlienku tohto odseku z Wittgensteinovho Tractatus Logico-Philosophicus. Buď vecný a nezačínaj dialóg:\n\n'{para_text}'"
    response = model.generate_content(prompt)
    return response.text

# --- 5. HLAVNÉ ROZLOŽENIE STRÁNKY ---
col1, col2 = st.columns([2.2, 1])

# ĽAVÝ STĹPEC: TEXT KNIHY
with col1:
    st.markdown("### 📖 Tractatus Logico-Philosophicus")
    st.markdown("<hr style='margin-top: 0; margin-bottom: 10px;'>", unsafe_allow_html=True)
    
    # Použitie relatívnej výšky '85vh', čo znamená 85% výšky okna prehliadača,
    # aby sa kontajner prispôsobil a využil maximum priestoru
    book_container = st.container(height=None, border=False)
    
    # Pre vizuálne natiahnutie do výšky ho uzavrieme do bloku, 
    # ktorý si cez CSS vypýta maximálnu dostupnú výšku (tzv. flexbox alebo vh)
    st.markdown("""
        <style>
        /* Kontajner knihy využije 85% výšky obrazovky */
        div[data-testid="stVerticalBlock"] > div > div > div > div > div > div[data-testid="stVerticalBlock"]:nth-of-type(1) {
            height: 85vh !important;
            min-height: 85vh !important;
        }
        </style>
    """, unsafe_allow_html=True)
    
    with book_container:
        for para in st.session_state.text_data:
            para_display = f"**{para['id']}** {para['text']}"
            
            if st.session_state.selected_paragraph == para['id']:
                st.markdown(f"<div class='highlighted-text'>{para_display}</div>", unsafe_allow_html=True)
            else:
                if st.button(para_display, key=f"btn_{para['id']}", use_container_width=True):
                    st.session_state.selected_paragraph = para['id']
                    
                    with st.spinner("Tútor pripravuje výklad k tomuto odseku..."):
                        st.session_state.explanation = generate_explanation(para['text'])
                    st.rerun()

# PRAVÝ STĹPEC: VYSVETLENIE A DISKUSIA
with col2:
    if st.session_state.selected_paragraph:
        st.markdown(f"### 💡 Výklad (Odsek {st.session_state.selected_paragraph})")
        st.info(st.session_state.explanation)
        st.markdown("<br>", unsafe_allow_html=True)
    
    st.markdown(f"### 💬 Diskusia k textu ({st.session_state.prompt_count} / 20)")
    
    # Ak je vybraný odsek a ukazuje sa výklad, chat okno bude menšie, inak zaberie viac miesta (napr. 60vh)
    chat_container_css_height = "35vh" if st.session_state.selected_paragraph else "70vh"
    
    st.markdown(f"""
        <style>
        /* Kontajner chatu v pravej časti */
        div[data-testid="stVerticalBlock"] > div > div > div > div > div > div[data-testid="stVerticalBlock"]:nth-of-type(2) {
            height: {chat_container_css_height} !important;
            overflow-y: auto !important;
            border: 1px solid rgba(49, 51, 63, 0.2);
            border-radius: 0.5rem;
            padding: 1rem;
        }
        </style>
    """, unsafe_allow_html=True)
    
    # Použijeme obyčajný kontajner, o ktorého výšku sa už postará vložené CSS vyššie
    chat_container = st.container()
    
    with chat_container:
        if len(st.session_state.messages) == 0:
            st.write("Tu môžete začať diskusiu kedykoľvek...")
            
        for msg in st.session_state.messages:
            with st.chat_message(msg["role"]):
                st.markdown(msg["content"])
    
    if st.session_state.chat_locked:
        st.error("Dosiahli ste limit 20 správ pre túto diskusiu.")
    else:
        user_msg = st.chat_input("Položte otázku alebo napíšte svoju úvahu...")
        if user_msg:
            st.session_state.prompt_count += 1
            st.session_state.messages.append({"role": "user", "content": user_msg})
            
            if st.session_state.prompt_count >= 20:
                st.session_state.chat_locked = True
                
            with chat_container:
                with st.chat_message("user"):
                    st.markdown(user_msg)
                
                with st.chat_message("assistant"):
                    with st.spinner("Tútor premýšľa..."):
                        context_str = f"[Zameranie na odsek {st.session_state.selected_paragraph}] " if st.session_state.selected_paragraph else ""
                        full_context_msg = f"{context_str}Otázka študenta: {user_msg}"
                        
                        response = st.session_state.chat_session.send_message(full_context_msg)
                        st.markdown(response.text)
            
            st.session_state.messages.append({"role": "assistant", "content": response.text})
            st.rerun()

    if len(st.session_state.messages) > 0:
        st.markdown("<br>", unsafe_allow_html=True)
        chat_history_text = "Tractatus Logico-Philosophicus - Prepis diskusie\n"
        chat_history_text += "="*50 + "\n\n"
        for msg in st.session_state.messages:
            role_name = "ŠTUDENT" if msg["role"] == "user" else "TÚTOR"
            chat_history_text += f"{role_name}:\n{msg['content']}\n\n"
            
        st.download_button(
            label="📥 Stiahnuť prepis diskusie (TXT)",
            data=chat_history_text,
            file_name="wittgenstein_diskusia.txt",
            mime="text/plain",
            use_container_width=True
        )