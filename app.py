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
        font-size: 18px !important; /* Požiadavka č. 1: väčšie písmo */
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
        font-size: 18px; /* Požiadavka č. 1: väčšie písmo */
        line-height: 1.7;
    }

    /* Požiadavka č. 3: Výraznejší posuvník (Scrollbar) PRE ĽAVÝ KONTAJNER */
    [data-testid="stVerticalBlock"] > div > div > div > div > div > div[data-testid="stVerticalBlock"] {
        overflow-y: auto !important;
    }
    ::-webkit-scrollbar {
        width: 14px; /* Širší pásik */
    }
    ::-webkit-scrollbar-track {
        background: #f1f1f1; 
        border-radius: 10px;
    }
    ::-webkit-scrollbar-thumb {
        background: #888; 
        border-radius: 10px;
        border: 3px solid #f1f1f1; /* Efekt odsadenia */
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
# Požiadavka č. 2: Zmena pomeru stĺpcov na cca 2:1 (pomer 2.2 ku 1 pre lepší vizuál knihy)
col1, col2 = st.columns([2.2, 1])

# ĽAVÝ STĹPEC: TEXT KNIHY
with col1:
    st.markdown("### 📖 Tractatus Logico-Philosophicus")
    st.markdown("<hr style='margin-top: 0; margin-bottom: 10px;'>", unsafe_allow_html=True)
    
    # Požiadavka č. 4: Kontajner roztiahnutý na výšku obrazovky (850px pre väčšinu monitorov)
    book_container = st.container(height=850, border=False)
    
    with book_container:
        for para in st.session_state.text_data:
            para_display = f"**{para['id']}** {para['text']}"
            
            # Ak je odsek kliknutý, zobrazí sa ako žltý zvýraznený box
            if st.session_state.selected_paragraph == para['id']:
                st.markdown(f"<div class='highlighted-text'>{para_display}</div>", unsafe_allow_html=True)
            
            # Inak sa zobrazí ako maskované tlačidlo
            else:
                if st.button(para_display, key=f"btn_{para['id']}", use_container_width=True):
                    st.session_state.selected_paragraph = para['id']
                    
                    with st.spinner("Tútor pripravuje výklad k tomuto odseku..."):
                        st.session_state.explanation = generate_explanation(para['text'])
                    st.rerun()

# PRAVÝ STĹPEC: VYSVETLENIE A DISKUSIA
with col2:
    # OKNO 1: PASÍVNE VYSVETLENIE (Zobrazí sa, len ak je niečo vybrané)
    if st.session_state.selected_paragraph:
        st.markdown(f"### 💡 Výklad (Odsek {st.session_state.selected_paragraph})")
        st.info(st.session_state.explanation)
        st.markdown("<br>", unsafe_allow_html=True)
    
    # OKNO 2: SOKRATOVSKÁ DISKUSIA (Požiadavka 5: Je nezávislá a vždy prítomná)
    # Požiadavka č. 6: Počítadlo promptov
    st.markdown(f"### 💬 Diskusia k textu ({st.session_state.prompt_count} / 20)")
    
    # Výška chat okna sa prispôsobí podľa toho, či je zobrazené vysvetlenie
    chat_height = 400 if st.session_state.selected_paragraph else 750
    chat_container = st.container(height=chat_height, border=True)
    
    with chat_container:
        if len(st.session_state.messages) == 0:
            st.write("Tu môžete začať diskusiu kedykoľvek...")
            
        for msg in st.session_state.messages:
            with st.chat_message(msg["role"]):
                st.markdown(msg["content"])
    
    # Vstupné pole pre študenta a logika limitov
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
                        # Odovzdáme kontext o vybranom odseku, ak nejaký existuje
                        context_str = f"[Zameranie na odsek {st.session_state.selected_paragraph}] " if st.session_state.selected_paragraph else ""
                        full_context_msg = f"{context_str}Otázka študenta: {user_msg}"
                        
                        response = st.session_state.chat_session.send_message(full_context_msg)
                        st.markdown(response.text)
            
            st.session_state.messages.append({"role": "assistant", "content": response.text})
            st.rerun()

    # Požiadavka č. 7: Možnosť stiahnuť diskusiu (Zobrazí sa hneď, ako je aspoň 1 správa)
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