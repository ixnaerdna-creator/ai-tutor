import streamlit as st
import datetime
import google.generativeai as genai
import json # <-- Toto je nový riadok, ktorý musíte pridať

# 1. Konfigurácia stránky
st.set_page_config(page_title="Analytický Tútor", layout="wide")

# --- CSS ÚPRAVA PRE KLIKACÍ TEXT ---
st.markdown("""
    <style>
    /* Agresívnejšie CSS pre zalomenie textu a prispôsobenie výšky tlačidla */
    [data-testid="column"]:nth-of-type(1) div.stButton > button {
        white-space: normal !important;
        text-align: left !important;
        height: auto !important;
        min-height: 40px !important;
        display: block !important;
        padding: 15px 10px !important;
        line-height: 1.5 !important;
    }
    
    /* Vynútenie zalomenia aj pre vnútorné elementy (odseky) v Streamlit tlačidle */
    [data-testid="column"]:nth-of-type(1) div.stButton > button * {
        white-space: normal !important;
    }
    </style>
""", unsafe_allow_html=True)

# --- BOČNÝ PANEL PRE API KĽÚČ ---
with st.sidebar:
    st.title("Nastavenia")
    api_key = st.text_input("Vložte svoj Gemini API Kľúč", type="password")
    st.markdown("[Získať API kľúč zadarmo (Google AI Studio)](https://aistudio.google.com/app/apikey)")
    st.markdown("---")
    st.info("Na to, aby agent odpovedal, je potrebný API kľúč.")

# 2. Inicializácia pamäte (Session State)
if "messages" not in st.session_state:
    st.session_state.messages = []
if "prompt_count" not in st.session_state:
    st.session_state.prompt_count = 0
if "chat_locked" not in st.session_state:
    st.session_state.chat_locked = False
if "chat_session" not in st.session_state:
    st.session_state.chat_session = None

# Načítanie textu z externého súboru text.json
if "text_data" not in st.session_state:
    try:
        with open("text.json", "r", encoding="utf-8") as file:
            st.session_state.text_data = json.load(file)
    except FileNotFoundError:
        st.error("Nepodarilo sa načítať text. Súbor 'text.json' sa v priečinku nenašiel.")
        st.session_state.text_data = []

# 3. Inicializácia modelu Gemini (ak je zadaný kľúč)
if api_key and st.session_state.chat_session is None:
    genai.configure(api_key=api_key)
    
    system_instruction = """
    Rola: Si prísne analytický Sokratovský tútor filozofie. Tvojou absolútnou a jedinou vedomostnou bázou je text, ktorý ti študent poskytne.
    Pravidlo 1: Nesmieš používať žiadne externé vedomosti, interpretácie z webu ani sekundárnu literatúru. Ak otázka presahuje rámec textu, odpovedz: "Na túto otázku text nedáva odpoveď."
    Pravidlo 2: Ak študent označí konkrétny odsek, tvojou úlohou je vysvetliť, ako tento odsek súvisí s celkovou štruktúrou textu.
    Pravidlo 3: Každú svoju odpoveď musíš zakončiť JEDNOU analytickou otázkou na študenta, aby si ho prinútil premýšľať nad logickými dôsledkami. Neponúkaj mu hotové riešenia.
    Pravidlo 4: Odpovedaj profesionálne, akademicky a výlučne v slovenskom jazyku.
    """
    
    model = genai.GenerativeModel(
        model_name="gemini-3.8-flash",
        system_instruction=system_instruction
    )
    
    st.session_state.chat_session = model.start_chat(history=[])

# --- HLAVNÉ ROZHRANIE ---
if not api_key:
    st.warning("👈 Pre spustenie aplikácie najprv vložte Gemini API kľúč do bočného panelu naľavo.")
else:
    # Rozdelenie obrazovky (Ľavý stĺpec 40%, Pravý 60%)
    col1, col2 = st.columns([4, 6])

    # 4. Ľavý stĺpec: Čítačka textu s vyhľadávaním
    with col1:
        st.header("📖 Zdrojový text (Wittgenstein)")
        
        # Vyhľadávacie pole
        search_query = st.text_input("🔍 Vyhľadať v texte (číslo odseku alebo slovo):", "")
        st.markdown("---")
        
        # Filtrovanie zobrazeného textu na základe vyhľadávania
        filtered_data = []
        for para in st.session_state.text_data:
            if search_query.lower() in para['id'].lower() or search_query.lower() in para['text'].lower():
                filtered_data.append(para)
                
        if not filtered_data:
            st.info("Nenašli sa žiadne zhody v texte.")

        # Vykreslenie odsekov (klikací text)
        for para in filtered_data:
            # Zistíme, či je tento odsek práve vybratý na analýzu
            is_selected = st.session_state.get("selected_paragraph") == para['id']
            
            if is_selected:
                # Zvýraznený text so žltým podfarbením a čiernym písmom pre dobrú čitateľnosť
                st.markdown(
                    f"<div style='background-color: #fff3cd; color: black; padding: 15px; border-radius: 8px; border-left: 5px solid #ffc107; margin-bottom: 10px;'>"
                    f"<b>{para['id']}</b> {para['text']}</div>", 
                    unsafe_allow_html=True
                )
            else:
                # Vytvoríme "neviditeľné" tlačidlo, ktoré vyzerá ako obyčajný text
                if st.button(f"**{para['id']}** {para['text']}", key=f"btn_{para['id']}", disabled=st.session_state.chat_locked, type="tertiary", use_container_width=True):
                    st.session_state.selected_paragraph = para['id']
                    
                    if st.session_state.prompt_count < 20:
                        user_msg = f"Zameral som sa na odsek {para['id']}: '{para['text']}'. Vysvetli jeho hlavnú myšlienku podľa tvojich inštrukcií a polož mi analytickú otázku."
                        
                        st.session_state.messages.append({"role": "user", "content": f"*(Študent si vybral na analýzu odsek {para['id']})*"})
                        st.session_state.prompt_count += 1
                        
                        with st.spinner("Tútor analyzuje text..."):
                            response = st.session_state.chat_session.send_message(user_msg)
                        
                        st.session_state.messages.append({"role": "assistant", "content": response.text})
                        st.rerun()

    # 5. Pravý stĺpec: Chatové rozhranie
    with col2:
        st.header("🤖 Analytický dialóg")
        
        # Počítadlo promptov
        st.progress(st.session_state.prompt_count / 20)
        st.write(f"**Krok: {st.session_state.prompt_count} / 20**")
        
        # Zobrazenie doterajšej komunikácie
        for msg in st.session_state.messages:
            with st.chat_message(msg["role"]):
                st.markdown(msg["content"])
                
        # Zámok konverzácie po 20. prompte
        if st.session_state.prompt_count >= 20 and not st.session_state.chat_locked:
            st.session_state.chat_locked = True
            
            final_instruction = "Toto bol 20. krok. Ukonči dialóg. Napíš teraz záverečnú, komplexnú analýzu toho, ako študent chápal text a ako sa jeho argumentácia počas dialógu vyvíjala. Na záver mu nedávaj už žiadnu otázku."
            
            with st.spinner("Tútor pripravuje záverečné zhodnotenie..."):
                final_response = st.session_state.chat_session.send_message(final_instruction)
            
            st.session_state.messages.append({"role": "assistant", "content": final_response.text})
            st.rerun()

        # Vstupné pole pre študenta
        if prompt := st.chat_input("Zadajte svoju odpoveď alebo otázku...", disabled=st.session_state.chat_locked):
            st.session_state.messages.append({"role": "user", "content": prompt})
            st.session_state.prompt_count += 1
            
            with st.spinner("Tútor premýšľa..."):
                response = st.session_state.chat_session.send_message(prompt)
            
            st.session_state.messages.append({"role": "assistant", "content": response.text})
            st.rerun()
            
        # Tlačidlo pre stiahnutie dialógu (Zobrazí sa až po uzamknutí chatu)
        if st.session_state.chat_locked:
            st.success("Konverzácia bola ukončená.")
            
            export_text = "--- LOG ANALYTICKEJ KONVERZÁCIE ---\n\n"
            for m in st.session_state.messages:
                role_name = "ŠTUDENT" if m['role'] == 'user' else "TÚTOR"
                export_text += f"[{role_name}]: {m['content']}\n\n"
            
            st.download_button(
                label="📥 Stiahnuť analýzu (TXT)",
                data=export_text,
                file_name=f"analyticky_dialog_{datetime.datetime.now().strftime('%Y%m%d_%H%M')}.txt",
                mime="text/plain"
            )