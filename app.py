import streamlit as st
import google.generativeai as genai
import json

# --- KONFIGURÁCIA STRÁNKY ---
st.set_page_config(page_title="Sokratovský Tútor", layout="wide")

# --- CSS PRE KLIKACÍ TEXT A ROZLOŽENIE ---
st.markdown("""
    <style>
    /* Úprava tlačidiel v ĽAVOM stĺpci, aby vyzerali presne ako bežný text knihy */
    [data-testid="column"]:nth-of-type(1) button {
        white-space: normal !important;
        text-align: left !important;
        height: auto !important;
        padding: 8px 10px !important;
        display: block !important;
        width: 100% !important;
        border: none !important;
        background: transparent !important;
        font-size: 16px !important;
        line-height: 1.6 !important;
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
        font-size: 16px;
        line-height: 1.6;
    }
    </style>
""", unsafe_allow_html=True)

# --- INICIALIZÁCIA SESSION STATE ---
if "api_key" not in st.session_state:
    st.session_state.api_key = ""
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
if "chat_session" not in st.session_state:
    st.session_state.chat_session = None

# --- BOČNÝ PANEL PRE API KĽÚČ ---
with st.sidebar:
    st.title("⚙️ Nastavenia")
    api_key_input = st.text_input("Vložte váš Gemini API kľúč:", type="password", value=st.session_state.api_key)
    if api_key_input:
        st.session_state.api_key = api_key_input
        genai.configure(api_key=st.session_state.api_key)
        
        # Inicializácia modelu pre Sokratovskú DISKUSIU
        if st.session_state.chat_session is None:
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
            
    if "prompt_count" in st.session_state:
        st.info(f"Počet otázok v diskusii: {st.session_state.prompt_count} / 20")

# Ak nie je kľúč, zastavíme vykresľovanie stránky a čakáme na používateľa
if not st.session_state.api_key:
    st.warning("Pre začatie práce s aplikáciou vložte svoj Gemini API kľúč do bočného panelu naľavo.")
    st.stop()

# --- FUNKCIA NA GENERÁCIU PASÍVNEHO VYSVETLENIA (Mimo Sokratovského dialógu) ---
def generate_explanation(para_text):
    model = genai.GenerativeModel("gemini-3.8-flash")
    prompt = f"Vysvetli odborne, jasne a zrozumiteľne pre vysokoškolského študenta hlavnú myšlienku tohto odseku z Wittgensteinovho Tractatus Logico-Philosophicus. Buď vecný a nezačínaj dialóg:\n\n'{para_text}'"
    response = model.generate_content(prompt)
    return response.text

# --- HLAVNÉ ROZLOŽENIE STRÁNKY ---
col1, col2 = st.columns([1.2, 1]) # Ľavý stĺpec s textom je mierne širší

# ĽAVÝ STĹPEC: TEXT KNIHY
with col1:
    st.markdown("### 📖 Tractatus Logico-Philosophicus")
    st.markdown("<hr style='margin-top: 0; margin-bottom: 10px;'>", unsafe_allow_html=True)
    
    # Špeciálny kontajner, ktorý zabezpečí, že sa roluje len text a stránka neskáče
    book_container = st.container(height=750, border=False)
    
    with book_container:
        for para in st.session_state.text_data:
            para_display = f"**{para['id']}** {para['text']}"
            
            # Ak je odsek kliknutý, zobrazí sa ako žltý zvýraznený box
            if st.session_state.selected_paragraph == para['id']:
                st.markdown(f"<div class='highlighted-text'>{para_display}</div>", unsafe_allow_html=True)
            
            # Inak sa zobrazí ako maskované tlačidlo (vyzerá ako bežný text)
            else:
                if st.button(para_display, key=f"btn_{para['id']}", use_container_width=True):
                    st.session_state.selected_paragraph = para['id']
                    
                    # Vygenerovanie vysvetlenia na pozadí (nepripočíta sa k limitu promptov)
                    with st.spinner("Tútor pripravuje výklad k tomuto odseku..."):
                        st.session_state.explanation = generate_explanation(para['text'])
                    st.rerun()

# PRAVÝ STĹPEC: VYSVETLENIE A DISKUSIA
with col2:
    if st.session_state.selected_paragraph:
        
        # 1. OKNO: PASÍVNE VYSVETLENIE (Nezávislé od limitu)
        st.markdown(f"### 💡 Výklad (Odsek {st.session_state.selected_paragraph})")
        st.info(st.session_state.explanation)
        
        st.markdown("<br>", unsafe_allow_html=True)
        
        # 2. OKNO: SOKRATOVSKÁ DISKUSIA (Aktívne rozhranie s limitom 20)
        st.markdown("### 💬 Diskusia k textu")
        
        chat_container = st.container(height=400, border=True)
        
        # Zobrazenie predošlej histórie chatu
        with chat_container:
            for msg in st.session_state.messages:
                with st.chat_message(msg["role"]):
                    st.markdown(msg["content"])
        
        # Reakcia na zamknutie pri dosiahnutí limitu
        if st.session_state.chat_locked:
            st.error("Dosiahli ste limit 20 správ pre túto reláciu.")
            chat_history = "\n\n".join([f"{msg['role'].upper()}: {msg['content']}" for msg in st.session_state.messages])
            st.download_button("Stiahnuť prepis diskusie (TXT)", chat_history, file_name="wittgenstein_diskusia.txt")
        
        # Vstupné pole pre študenta (začína dialóg a pripočíta prompt)
        else:
            user_msg = st.chat_input("Položte otázku k odseku alebo napíšte svoju úvahu...")
            if user_msg:
                # Pripočítanie promptu a uloženie otázky
                st.session_state.prompt_count += 1
                st.session_state.messages.append({"role": "user", "content": user_msg})
                
                if st.session_state.prompt_count >= 20:
                    st.session_state.chat_locked = True
                    
                with chat_container:
                    with st.chat_message("user"):
                        st.markdown(user_msg)
                    
                    with st.chat_message("assistant"):
                        with st.spinner("Tútor premýšľa..."):
                            # Model dostane okrem otázky aj tichý kontext o tom, na ktorý odsek sa študent práve pozerá
                            full_context_msg = f"[Tichý systémový kontext: Študent sa momentálne pozerá na odsek {st.session_state.selected_paragraph}. Jeho vygenerované vysvetlenie bolo: '{st.session_state.explanation}']\n\nOtázka študenta: {user_msg}"
                            
                            response = st.session_state.chat_session.send_message(full_context_msg)
                            st.markdown(response.text)
                
                st.session_state.messages.append({"role": "assistant", "content": response.text})
                st.rerun()
    
    # Úvodná obrazovka pravého stĺpca (kým nie je zakliknutý žiadny odsek)
    else:
        st.info("👈 Pre začatie práce si prečítajte text knihy a kliknite na odsek, ktorý chcete s tútorom analyzovať.")