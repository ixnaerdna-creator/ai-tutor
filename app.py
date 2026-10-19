"""Traktát – sokratovský AI tútor pre vysoké školy.

Vyžaduje plný a autorizovaný text diela v lokálnom text.json vedľa app.py.
Gemini API kľúč patrí IBA do Streamlit Secrets, nie do GitHubu.
"""
from __future__ import annotations

import hashlib
import json
from pathlib import Path
from uuid import uuid4
import os
import streamlit as st
from google import genai
from google.genai import types

from book_reader import book_reader
from tutor_core import (
    MAX_TURNS, BookError, api_error_message, context_for_model,
    format_transcript, read_book,
)

st.set_page_config(page_title="Traktát | Filozofický AI tútor", page_icon="📖", layout="wide")
BASE = Path(__file__).resolve().parent
MODEL = "gemini-3.8-flash"  # Nastavte dostupný model cez GEMINI_MODEL v Secrets.
THINKING = "low"  # Náročnejšie úlohy: medium; pre Flash-Lite možno použiť minimal.

st.markdown("""
<style>
  .block-container { padding-top: 1.3rem; max-width: 98rem; }
  h1, h2, h3 { font-family: Georgia, serif; }
  .st-key-chat_reset button { font-size: .82rem; }
  @media(max-width: 800px) { .block-container { padding-top: .75rem; } }
</style>
""", unsafe_allow_html=True)


def secret(name: str, default=None):
    try:
        return st.secrets.get(name, os.environ.get(name, default))
    except Exception:
        return os.environ.get(name, default)


API_KEY = secret("GEMINI_API_KEY")
MODEL = str(secret("GEMINI_MODEL", MODEL))
THINKING = str(secret("GEMINI_THINKING_LEVEL", THINKING)).lower()
if THINKING not in {"minimal", "low", "medium", "high"}:
    THINKING = "low"
if MODEL == "gemini-3.8-flash" and THINKING == "minimal":
    THINKING = "low"  # Gemini 3.8 Flash nepodporuje minimal.

try:
    book = read_book(BASE / "text.json")
except BookError as exc:
    st.error(str(exc))
    st.info("Priložte svoj pôvodný súbor `text.json` do rovnakého priečinka ako `app.py`. ")
    st.stop()

if not API_KEY:
    st.error("V aplikácii chýba GEMINI_API_KEY. Nastavte ho v Streamlit Community Cloud → Settings → Secrets.")
    st.stop()


@st.cache_resource(show_spinner=False)
def get_client(api_key: str):
    return genai.Client(
        api_key=api_key,
        http_options=types.HttpOptions(timeout=35000, retry_options=types.HttpRetryOptions(attempts=1)),
    )


client = get_client(API_KEY)


def call_gemini(system: str, text: str, final: bool = False) -> str:
    # Žiadne nástroje pre vyhľadávanie na webe, žiadne ďalšie súbory či sekundárna literatúra.
    result = client.models.generate_content(
        model=MODEL,
        contents=text,
        config=types.GenerateContentConfig(
            system_instruction=system,
            thinking_config=types.ThinkingConfig(thinking_level=THINKING),
            max_output_tokens=(3300 if final else 2400),  # Menej výstupných tokenov = šetrnejšia prevádzka.
        ),
    )
    response = (result.text or "").strip()
    if not response:
        raise RuntimeError("Model vrátil prázdnu odpoveď.")
    return response


EXPLANATION_RULES = """Si vysokoškolský vyučujúci analytickej filozofie. Vysvetľuješ
výhradne Wittgensteinov Tractatus logico-philosophicus podľa doložených pasáží.
Zdrojom nesmú byť iné knihy, komentáre, web ani všeobecné vedomosti modelu.
Rozlišuj medzi explicitnou tézou a interpretatívnou rekonštrukciou ('Z textu možno usudzovať...').
Odvolávaj sa na skutočné čísla téz z kontextu v hranatých zátvorkách [napr. 2.01].
Neuvádzaj čísla téz, ku ktorým nemáš doslovnú pasáž v podkladoch.
Píš po slovensky, vecne a odborne, no zrozumiteľne; rozsah približne 130–240 slov.
Uveď (1) význam tvrdenia, (2) filozofické väzby, (3) medze výkladu.
Neklaď otázku a nepokračuj v diskusii. Ak podklady nestačia, povedz to.
"""

DIALOGUE_RULES = """Si sokratovský tútor analytickej filozofie. Študent číta
Wittgensteinov Tractatus logico-philosophicus. Jediným autorizovaným
filozofickým zdrojom sú pasáže z text.json uvedené v aktuálnej požiadavke.
Zákaz: vonkajšie filozofické interpretácie, iné diela a web. Podklady neprikrášľuj.
Snaž sa korektne argumentovať, rekonštruovať implikácie, identifikovať
predpoklady a prípadné napätia medzi tézami; používaj aj protipríklady,
ak ich možno podať ako analytické hypotézy (označ ich za hypotézy).
Odlišuj, čo autor priamo tvrdí, od toho, čo z tvrdení môže vyplývať.
Nevkladaj študentovi do úst názory. Odpovedz na skutočný obsah jeho otázky,
nie na posledné automatické vysvetlenie odseku – to NIE JE súčasť rozhovoru.
Odpovedaj po slovensky, približne 100–220 slov; odkazuj na dokladované [čísla téz].
Spravidla odpoveď ukonči jednou presnou analytickou otázkou študentovi.
Ak podklady na otázku nestačia, priznaj limit a navrhni konkrétny textový krok.
Pri záverečnom 20. kroku sa riad osobitnou inštrukciou v požiadavke:
po odpovedi pridaj záverečné kritické zhodnotenie (silné stránky, slabiny,
posun porozumenia, otvorené otázky), už nekladúc ďalšiu otázku.
"""


def initialize_state():
    defaults = {
        "selected_id": None,
        "explanation": "",
        "explanation_error": "",
        "show_explanation": False,
        "explanation_cache": {},
        "messages": [],
        "count": 0,
        "pending": None,
        "pending_failed": False,
        "pending_error": "",
        "session_id": str(uuid4())[:12],
        "student_name": "",
    }
    for key, default in defaults.items():
        if key not in st.session_state:
            st.session_state[key] = default


initialize_state()
book_by_id = {entry["id"]: entry for entry in book}
BOOK_DIGEST = hashlib.sha256(json.dumps(book, ensure_ascii=False, sort_keys=True).encode("utf-8")).hexdigest()


def reset_dialogue():
    st.session_state.messages = []
    st.session_state.count = 0
    st.session_state.pending = None
    st.session_state.pending_failed = False
    st.session_state.pending_error = ""
    st.session_state.show_explanation = False
    st.session_state.session_id = str(uuid4())[:12]


@st.cache_data(show_spinner=False, ttl=604800, max_entries=1200)
def get_shared_explanation(identifier: str, book_digest: str, model_name: str, thinking: str):
    """Bez osobných údajov: opakovane použiteľné výklady pre všetkých študentov."""
    paragraph = book_by_id[identifier]
    sources = context_for_model(book, paragraph["text"], identifier)
    prompt = f"VYBRANÁ TÉZA: [{identifier}] {paragraph['text']}\n\n{sources}\n\nVysvetli vybranú tézu."
    return call_gemini(EXPLANATION_RULES, prompt)


def generate_explanation(identifier: str):
    if identifier in st.session_state.explanation_cache:
        st.session_state.explanation = st.session_state.explanation_cache[identifier]
        st.session_state.explanation_error = ""
        st.session_state.show_explanation = True
        return
    try:
        with st.spinner("Pripravujem výklad odseku…"):
            explanation = get_shared_explanation(identifier, BOOK_DIGEST, MODEL, THINKING)
    except Exception as exc:
        st.session_state.explanation = ""
        st.session_state.explanation_error = api_error_message(exc, MODEL)
        st.session_state.show_explanation = False
        # Chyba sa nekeshuje – ďalší výber/klik môže opakovať požiadavku.
        print(f"[explanation error] {type(exc).__name__}: {exc}")
    else:
        st.session_state.explanation_cache[identifier] = explanation
        st.session_state.explanation = explanation
        st.session_state.explanation_error = ""
        st.session_state.show_explanation = True


def process_pending():
    pending = st.session_state.pending
    if not pending or st.session_state.count >= MAX_TURNS:
        return
    query = pending["text"]
    # Výber pasáží zo SKUTOČNEJ knihy. Nie z vopred naučených interpretácií modelu.
    recent = " ".join(m["content"] for m in st.session_state.messages if m["role"] == "user")[-3000:]
    # Diskusia je obsahovo nezávislá od kliknutého odseku; ten sa používa iba vo výklade.
    excerpts = context_for_model(book, f"{query}\n{recent}", None, 16)
    history = "\n\n".join(
        f"{'ŠTUDENT' if item['role'] == 'user' else 'TÚTOR'}: {item['content']}"
        for item in st.session_state.messages
    )[-30000:]
    last = st.session_state.count == MAX_TURNS - 1
    closing = (
        "\n\nTOTO JE 20. A POSLEDNÝ ŠTUDENTSKÝ VSTUP. Odpovedz na otázku a pridaj "
        "samostatné ZÁVEREČNÉ HODNOTENIE celej diskusie. Nerob ďalší krok "
        "a nepýtaj sa ďalšiu otázku. Nepredstieraj, že vieš, čo sa študent naučil "
        "mimo viditeľného prepisu."
        if last else "\n\nToto nie je posledný krok, ukonči odpoveď jednou analytickou otázkou."
    )
    input_text = (
        f"ZDROJOVÝ PODKLAD:\n{excerpts}\n\n"
        f"DOSLOVNÁ HISTÓRIA DIALÓGU (bez automatických výkladov):\n{history or '(začiatok)'}\n\n"
        f"AKTUÁLNY VSTUP ŠTUDENTA (krok {st.session_state.count + 1} z 20):\n{query}{closing}"
    )
    try:
        with st.spinner("Tútor pripravuje odpoveď…"):
            reply = call_gemini(DIALOGUE_RULES, input_text, final=last)
    except Exception as exc:
        st.session_state.pending_error = api_error_message(exc, MODEL)
        st.session_state.pending_failed = True
        print(f"[dialogue error] {type(exc).__name__}: {exc}")
    else:
        st.session_state.messages.extend([
            {"role": "user", "content": query},
            {"role": "assistant", "content": reply},
        ])
        st.session_state.count += 1
        st.session_state.pending = None
        st.session_state.pending_failed = False
        st.session_state.pending_error = ""


# Znovupokúšanie nikdy neprebieha automaticky. Pri chybe API sa zachová obsah vstupu.
if st.session_state.pending is not None and not st.session_state.pending_failed:
    process_pending()

st.title("Traktát · Filozofický AI tútor")
st.caption("Čítanie a analytický výklad pôvodného textu | samostatný 20-krokový sokratovský dialóg")
left, right = st.columns([2, 1], gap="large", vertical_alignment="top")

with left:
    st.markdown("#### Ludwig Wittgenstein · Tractatus logico-philosophicus")
    st.caption(f"Načítaných {len(book)} téz (posledná: {book[-1]['id']}). Kliknutie otvorí výklad bez spotrebovania diskusného kroku.")
    reader_event = book_reader(
        data={"paragraphs": book, "selected": st.session_state.selected_id,
              "bookKey": f"tractatus-{len(book)}"},
        key="tractatus_main_reader",
        width="stretch",
        height=680,  # Veľkosť obalu Streamlitu; vnútorná čítačka zaberá zvyšnú výšku.
        on_selected_change=lambda: None,
    )
    selected = reader_event.selected
    if selected and selected in book_by_id:
        st.session_state.selected_id = selected
        generate_explanation(selected)
        st.rerun()

with right:
    htitle, hreset = st.columns([1.45, 1], vertical_alignment="center")
    with htitle:
        st.markdown(f"#### Diskusia · {st.session_state.count}/{MAX_TURNS}")
    with hreset:
        if st.button("Vynulovať diskusiu", key="chat_reset", width="stretch"):
            reset_dialogue()
            st.rerun()
    st.progress(st.session_state.count / MAX_TURNS)

    if st.session_state.explanation_error and st.session_state.selected_id:
        st.error(st.session_state.explanation_error)
        if "429" in st.session_state.explanation_error:
            st.markdown("[Skontrolovať kvóty Gemini v Google AI Studio](https://aistudio.google.com/rate-limit)")
        if st.button("Skúsiť výklad znova", key="retry_explanation", width="stretch"):
            generate_explanation(st.session_state.selected_id)
            st.rerun()

    if st.session_state.show_explanation and st.session_state.selected_id:
        st.markdown(f"**Výklad tézy {st.session_state.selected_id}**")
        with st.container(height=180, border=False):
            st.markdown(st.session_state.explanation)
        if st.button("Zavrieť výklad", key="close_expl", width="stretch"):
            st.session_state.show_explanation = False
            st.rerun()
    else:
        st.caption("Výklad je nezávislý od dialógu. Môžete začať otázkou aj bez kliknutia na text.")

    st.markdown("**Sokratovský dialóg**")
    chat_h = 270 if st.session_state.show_explanation else 455
    with st.container(height=chat_h, border=True, autoscroll=True):
        if not st.session_state.messages:
            st.caption("Začnite vlastnou otázkou, námietkou alebo pokusom o rekonštrukciu argumentu.")
        for msg in st.session_state.messages:
            with st.chat_message(msg["role"]):
                st.markdown(msg["content"])

    if st.session_state.pending_failed:
        st.error(st.session_state.pending_error)
        if "429" in st.session_state.pending_error:
            st.markdown("[Skontrolovať kvóty Gemini v Google AI Studio](https://aistudio.google.com/rate-limit)")
        st.info("Vaša otázka zostala uložená. Nezapočítala sa do limitu.")
        r1, r2 = st.columns(2)
        with r1:
            if st.button("Skúsiť znova", key="tryagain"):
                st.session_state.pending_failed = False
                st.rerun()
        with r2:
            if st.button("Zrušiť otázku", key="cancelpending"):
                st.session_state.pending = None
                st.session_state.pending_failed = False
                st.session_state.pending_error = ""
                st.rerun()

    elif st.session_state.count < MAX_TURNS:
        with st.form("ask_question", clear_on_submit=True, border=False):
            question = st.text_area("Vaša otázka alebo argument", height=74, max_chars=3000,
                                    placeholder="Čo podľa Traktátu znamená…?", label_visibility="collapsed")
            submitted = st.form_submit_button("Odoslať tútorovi", type="primary", width="stretch")
        if submitted:
            if question.strip():
                st.session_state.pending = {"text": question.strip()}
                st.session_state.show_explanation = False  # Na začiatku diskusie ukryť starý výklad.
                st.session_state.pending_failed = False
                st.rerun()
            else:
                st.warning("Najprv napíšte otázku alebo argument.")
    else:
        st.success("Dokončili ste 20 krokov. Dialóg je uzavretý; môžete ho exportovať.")

    if st.session_state.messages:
        st.session_state.student_name = st.text_input("Meno študenta/študentky (voliteľné)",
                                                       value=st.session_state.student_name,
                                                       placeholder="Na účely odovzdania v Moodle")
        transcript = format_transcript(st.session_state.messages, st.session_state.student_name,
                                       len(book), MODEL, st.session_state.session_id)
        st.download_button(
            "Stiahnuť celý prepis (TXT)", data=transcript.encode("utf-8-sig"),
            file_name=f"tractatus_dialog_{st.session_state.session_id}.txt", mime="text/plain",
            width="stretch",
        )

st.caption(f"Aktívny model: {MODEL} (myslenie: {THINKING}). "
           "Ak nastane chyba 429, ďalší model vyberte v Streamlit Secrets až po kontrole kvót projektu. "
           "AI sa opiera o vyhľadané časti poskytnutého textu, nie o externé vyhľadávanie. "
           "Jej interpretácie a odkazy na tézy treba pri akademickej práci overovať. "
           "Konverzácia sa neprenáša medzi zariadeniami; prepis si priebežne sťahujte.")
