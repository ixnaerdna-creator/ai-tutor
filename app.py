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

# --- 2. CSS PRE KRAJŠÍ DIZAJN (OPRAVENÉ SCROLLOVANIE) ---
st.markdown("""
    <style>
    /* Skrytie hornej lišty a zbytočných medzier */
    header {visibility: hidden !important;}
    .block-container { padding-top: 1rem !important; padding-bottom: 0rem !important; }
    
    /* SCROLLBAR PRE CHROME, EDGE, SAFARI */
    ::-webkit-scrollbar {
        width: 16px !important;
    }
    ::-webkit-scrollbar-track {
        background: #e0e0e0 !important; 
        border-radius: 8px !important;
    }
    ::-webkit-scrollbar-thumb {
        background-color: #4a4a4a !important; 
        border-radius: 8px !important;
        border: 3px solid #e0e0e0 !important;
    }
    ::-webkit-scrollbar-thumb:hover {
        background-color: #2b2b2b !important; 
    }
    
    /* SCROLLBAR PRE FIREFOX (Univerzálne riešenie) */
    * {
        scrollbar-width: auto;
        scrollbar-color: #4a4a4a #e0e0e0;
    }

    /* ĽAVÝ STĹPEC BUDE ROLOVATEĽNÝ CELÝ (Najúčinnejšie riešenie pre Streamlit) */
    div[data-testid="column"]:nth-of-type(1) {
        height: 85vh !important;
        overflow-y: auto !important;
        padding-right: 15px !important;
    }

    /* ELEGANTNÝ DIZAJN TEXTU */
    .book-title {
        color: #2c3e50;
        border-bottom: 2px solid #e9ecef;
        padding-bottom: 10px;
        margin-bottom: 10px;
    }
    
    /* Úprava tlačidiel textu */
    [data-testid="column"]:nth-of-type(1) button {
        white-space: normal !important;
        text-align: left !important;
        height: auto !important;
        padding: 10px 15px !important;
        display: block !important;
        width: 100% !important;
        border: none !important;
        background: transparent !important;
        color: #1a1a1a !important;
        border-radius: 5px !important;
        margin-bottom: 2px !important;
    }
    [data-testid="column"]:nth-of-type(1) button p {
        white-space: normal !important;
        font-size: 18px !important;
        line-height: 1.7 !important;
        margin: 0 !important;
    }
    [data-testid="column"]:nth-of-type(1) button:hover {
        background-color: #f8f9fa !important;
    }
    
    /* Zvýraznený odsek po kliknutí */
    .highlighted-text {
        background-color: #fff3cd;
        color: #212529;
        padding: 15px;
        border-radius: 5px;
        border-left: 5px solid #ffc107;
        margin-bottom: 10px;
        font-size: 18px;
        line-height: 1.7;
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
    st.markdown("<h3 class='book-title'>📖 Tractatus Logico-Philosophicus</h3>", unsafe_allow_html=True)
    st.info("👈 **Kliknutím na text dostaneš vysvetlenie danej pasáže.**")
    
    # Texty sa generujú priamo do rolovacieho stĺpca (bez zbytočných vnútorných okien)
    for para in st.session_state.text_data:
        
        if st.session_state.selected_paragraph == para['id']:
            st.markdown(f"<div class='highlighted-text'><b>{para['id']}</b> &nbsp; {para['text']}</div>", unsafe_allow_html=True)
        else:
            para_display = f"**{para['id']}** {para['text']}"
            if st.button(para_display, key=f"btn_{para['id']}", use_container_width=True):
                st.session_state.selected_paragraph = para['id']
                st.session_state.show_explanation = True 
                with st.spinner("Tútor pripravuje výklad k tomuto odseku..."):
                    st.session_state.explanation = generate_explanation(para['text'])
                st.rerun()

# PRAVÝ STĹPEC: VYSVETLENIE A DISKUSIA
with col2:
    # TLAČIDLO NA VYNULOVANIE
    col_title, col_btn = st.columns([1.5, 1])
    with col_title:
        st.markdown(f"### 💬 Diskusia ({st.session_state.prompt_count} / 20)")
    with col_btn:
        if st.button("🔄 Vynuluj diskusiu", use_container_width=True):
            st.session_state.messages = []
            st.session_state.prompt_count = 0
            st.session_state.chat_locked = False
            st.session_state.chat_session = model.start_chat(history=[])
            st.rerun()
            
    st.markdown("<hr style='margin: 0px 0 10px 0;'>", unsafe_allow_html=True)

    # ZOBRAZENIE VYSVETLENIA
    if st.session_state.selected_paragraph and st.session_state.show_explanation:
        st.markdown(f"**💡 Výklad (Odsek {st.session_state.selected_paragraph})**")
        if "preťažený" in st.session_state.explanation:
            st.warning(st.session_state.explanation)
        else:
            st.info(st.session_state.explanation)
        st.markdown("<br>", unsafe_allow_html=True)
    
    # DISKUSNÉ OKNO
    chat_height = 250 if (st.session_state.selected_paragraph and st.session_state.show_explanation) else 450
    chat_container = st.container(height=chat_height, border=True)
    
    with chat_container:
        if len(st.session_state.messages) == 0:
            st.write("Tu môžete začať diskusiu kedykoľvek...")
            
        for msg in st.session_state.messages:
            with st.chat_message(msg["role"]):
                st.markdown(msg["content"])
    
    # POLÍČKO NA PÍSANIE
    if st.session_state.chat_locked:
        st.error("Dosiahli ste limit 20 správ.")
    else:
        user_msg = st.chat_input("Položte otázku alebo napíšte svoju úvahu...")
        if user_msg:
            st.session_state.show_explanation = False 
            st.session_state.prompt_count += 1
            st.session_state.messages.append({"role": "user", "content": user_msg})
            
            if st.session_state.prompt_count >= 20:
                st.session_state.chat_locked = True
                
            with chat_container:
                with st.chat_message("user"):
                    st.markdown(user_msg)
                
                with st.chat_message("assistant"):
                    with st.spinner("Tútor premýšľa..."):
                        selected_text_raw = next((p['text'] for p in st.session_state.text_data if p['id'] == st.session_state.selected_paragraph), "") if st.session_state.selected_paragraph else ""
                        context_str = f"[Tichý kontext: Študent sa zameriava na odsek {st.session_state.selected_paragraph}: '{selected_text_raw}']\n\n" if selected_text_raw else ""
                        full_context_msg = f"{context_str}Otázka študenta: {user_msg}"
                        
                        try:
                            response = st.session_state.chat_session.send_message(full_context_msg)
                            response_text = response.text
                        except Exception as e:
                            if "ResourceExhausted" in str(e) or "429" in str(e):
                                response_text = "⏳ **Tútor je preťažený.** (Limit bol vyčerpaný). Zopakujte prosím otázku o pol minúty."
                            else:
                                 response_text = f"❌ Chyba: {e}"
                            
                            # NEVYMAŽEME históriu, takže odpoveď zostane na obrazovke. 
                            # Iba študentovi znížime počítadlo, aby nebol o túto otázku ukrátený.
                            st.session_state.prompt_count -= 1 
                                 
                        st.markdown(response_text)
            
            # Zapísanie asistenta do pamäte obrazovky
            st.session_state.messages.append({"role": "assistant", "content": response_text})
            st.rerun()

    # --- 6. SŤAHOVANIE PREPISU ---
    if len(st.session_state.messages) > 0:
        chat_history_text = "Tractatus Logico-Philosophicus - Prepis diskusie\n"
        chat_history_text += "="*50 + "\n\n"
        for msg in st.session_state.messages:
            role_name = "ŠTUDENT" if msg["role"] == "user" else "TÚTOR"
            chat_history_text += f"{role_name}:\n{msg['content']}\n\n"
            
        st.download_button("📥 Stiahnuť prepis (TXT)", data=chat_history_text, file_name="wittgenstein_diskusia.txt", mime="text/plain", use_container_width=True)