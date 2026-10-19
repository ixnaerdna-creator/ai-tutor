"""Čistá aplikačná logika bez Streamlitu a bez volaní modelu."""
from __future__ import annotations

from collections import Counter
from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo
import json
import math
import re
import unicodedata

MAX_TURNS = 20
WORD_RE = re.compile(r"[\w]+(?:[.][0-9]+)*", re.UNICODE)
REF_RE = re.compile(r"(?<![\d.])([1-7](?:\.\d+)?)(?![\d.])")


class BookError(ValueError):
    """Nekorektný obsah text.json."""


def read_book(path: Path) -> list[dict[str, str]]:
    try:
        contents = path.read_text(encoding="utf-8-sig")
        data = json.loads(contents)
    except FileNotFoundError as exc:
        raise BookError(f"Chýba {path.name}. Ponechajte pôvodný úplný text knihy pod týmto názvom.") from exc
    except json.JSONDecodeError as exc:
        raise BookError(f"Súbor {path.name} nie je platný JSON (riadok {exc.lineno}).") from exc
    if isinstance(data, dict) and isinstance(data.get("paragraphs"), list):
        data = data["paragraphs"]
    if not isinstance(data, list) or not data:
        raise BookError("text.json musí byť neprázdne pole objektov s položkami id a text.")

    result: list[dict[str, str]] = []
    seen: set[str] = set()
    for i, row in enumerate(data, start=1):
        if not isinstance(row, dict) or "id" not in row or "text" not in row:
            raise BookError(f"Položka {i} nemá polia id a text.")
        identifier = str(row["id"]).strip()
        content = row["text"]
        if not isinstance(content, str):
            raise BookError(f"Odsek {identifier} nemá text typu reťazec.")
        content = content.strip()
        if not identifier or not content:
            raise BookError(f"Položka {i} má prázdne id alebo text.")
        if identifier in seen:
            raise BookError(f"Duplicitné id: {identifier}.")
        seen.add(identifier)
        result.append({"id": identifier, "text": content})
    return result


def normalize(value: str) -> str:
    decomp = unicodedata.normalize("NFKD", value.casefold())
    return "".join(ch for ch in decomp if not unicodedata.combining(ch))


def terms(value: str) -> list[str]:
    return [x for x in WORD_RE.findall(normalize(value)) if len(x) > 2]


def choose_passages(book: list[dict[str, str]], query: str, selected_id: str | None = None,
                    limit: int = 14) -> list[dict[str, str]]:
    """Lokálne vyhľadanie relevantných odsekov, bez ďalšieho API volania.

    Ide o výber podkladov, NIE dôkaz, že model nikdy nepoužije vlastné znalosti.
    """
    doc_terms = [Counter(terms(row["id"] + " " + row["text"])) for row in book]
    frequency: Counter[str] = Counter()
    for t in doc_terms:
        frequency.update(t.keys())
    query_terms = terms(query)
    # Jednoduché zjednotenie tvarov slovenčiny: päťznakové kmene.
    query_stems = {t[:5] for t in query_terms if len(t) >= 5}
    q_counts = Counter(query_terms)
    N = len(book)
    scores: list[tuple[float, int]] = []
    for i, (row, counts) in enumerate(zip(book, doc_terms)):
        score = 0.0
        for term, n in q_counts.items():
            tf = counts.get(term, 0)
            if tf:
                score += (1.0 + math.log(tf)) * math.log(1.0 + (N + 1) / (frequency[term] + 1))
        for stem in query_stems:
            if any(w.startswith(stem) for w in counts):
                score += 0.25
        if selected_id and row["id"] == selected_id:
            score += 1000
        scores.append((score, i))
    wanted: set[int] = set()
    id_map = {row["id"]: i for i, row in enumerate(book)}
    if selected_id in id_map:
        pos = id_map[selected_id]
        wanted.update(range(max(0, pos - 2), min(N, pos + 3)))
    for identifier in REF_RE.findall(query):
        if identifier in id_map:
            pos = id_map[identifier]
            wanted.update(range(max(0, pos - 1), min(N, pos + 2)))
    for score, i in sorted(scores, reverse=True):
        if len(wanted) >= limit:
            break
        if score > 0:
            wanted.add(i)
    if not wanted:
        wanted.update(range(min(N, min(limit, 6))))
    if len(wanted) > limit:
        core = ([id_map[selected_id]] if selected_id in id_map else [])
        critical = sorted(wanted, key=lambda i: (
            0 if i in core else 1,
            -scores[i][0],
            abs(i - core[0]) if core else i,
        ))
        wanted = set(critical[:limit])
    return [book[i] for i in sorted(wanted)]


def context_for_model(book: list[dict[str, str]], question: str, selected_id: str | None,
                      limit: int = 14) -> str:
    """Zachová číslovanie téz a poskytne aj pôvodný sedembodový rámec knihy."""
    key = {p["id"]: p["text"] for p in book}
    structure = "\n".join(f"[{i}] {key[i]}" for i in map(str, range(1, 8)) if i in key)
    matches = choose_passages(book, question, selected_id, limit)
    sources = "\n\n".join(f"[{p['id']}] {p['text']}" for p in matches)
    return (
        "ZÁKLADNÁ ŠTRUKTÚRA KNIHY (doslovné vybrané tézy):\n"
        + (structure or "Základné tézy nie sú v dodanom súbore samostatne označené.")
        + "\n\nVYHĽADANÉ DOSLOVNÉ PASÁŽE (výhradne z text.json):\n" + sources
        + "\n\nPoznámka: Toto je výber z knihy. Ak z neho odpoveď nevyplýva, priznaj to. "
          "Nevymýšľaj chýbajúce znenie ďalších téz."
    )


def api_error_message(exc: Exception, model: str = "") -> str:
    code = getattr(exc, "code", None)
    message = str(exc)
    lowered = message.lower()
    model_label = f" pre model {model}" if model else ""
    if code == 429 or "429" in message or "RESOURCE_EXHAUSTED" in message.upper():
        if any(word in lowered for word in ("limit: 0", "limit=0", "limit' : 0", "\"limit\": 0", "quota_value: 0")):
            return (f"Gemini API má{model_label} v tomto Google projekte nulovú kvótu (429; limit 0). "
                    "Čakanie nepomôže. V Google AI Studio overte kvótu daného modelu a "
                    "v Streamlit Secrets nastavte GEMINI_MODEL na model s dostupnou kvótou.")
        return (f"Google Gemini API odmietlo požiadavku{model_label} (429). "
                "Možný je denný limit, limit RPM/TPM alebo nulová kapacita. "
                "Skontrolujte presný limit a používanie vo svojom projekte v Google AI Studio. "
                "Ak má iný model voľnú kvótu, zmeňte GEMINI_MODEL v Streamlit Secrets.")
    if code == 404 or "404" in message or "NOT_FOUND" in message.upper():
        return "Zvolený model nie je dostupný pre daný projekt/verziu API (404). Overte názov a zoznam dostupných modelov."
    if code in (401, 403) or "403" in message or "401" in message:
        return "API kľúč nemá potrebné oprávnenia (401/403) alebo nie je platný. Skontrolujte Streamlit Secrets a Google AI Studio."
    if code == 503 or "503" in message:
        return "Služba Gemini je dočasne nedostupná (503). Otázka zostala uložená na opakovanie."
    return f"Požiadavka na AI zlyhala ({type(exc).__name__}). Otázka zostala uložená; detail je dostupný správcovi v logoch."


def format_transcript(messages: list[dict], student: str, book_count: int,
                      model: str, identifier: str, at: datetime | None = None) -> str:
    moment = at or datetime.now(ZoneInfo("Europe/Bratislava"))
    lines = [
        "TRAKTÁT – FILOZOFICKÝ DIALÓG",
        "=" * 40,
        f"Študent/ka: {student or '(neuvedené)'}",
        f"Dátum: {moment:%d. %m. %Y %H:%M %Z}",
        f"Identifikátor relácie: {identifier}",
        f"Zdroj: Tractatus Logico-Philosophicus – {book_count} odsekov",
        f"Model: {model}",
        f"Dokončené študentské vstupy: {sum(x['role'] == 'user' for x in messages)} / {MAX_TURNS}",
        "", "PREPIS", "-" * 40, "",
    ]
    for msg in messages:
        role = "ŠTUDENT" if msg["role"] == "user" else "AI TÚTOR"
        lines.extend([f"{role}:", str(msg["content"]).strip(), ""])
    return "\n".join(lines)
