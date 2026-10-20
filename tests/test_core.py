import json
from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo
import pytest

from tutor_core import BookError, read_book, choose_passages, context_for_model, api_error_message, format_transcript


def book():
    return [
        {"id": "1", "text": "Svet je všetko, čo je skutočnosťou."},
        {"id": "1.1", "text": "Svet je súhrn faktov, nie vecí."},
        {"id": "2", "text": "Čo je fakt, je existencia stavov vecí."},
        {"id": "2.1", "text": "Robíme si obrazy faktov."},
        {"id": "3", "text": "Logický obraz faktov je myšlienka."},
        {"id": "4", "text": "Myšlienka je zmysluplná veta."},
        {"id": "5", "text": "Veta je pravdivostná funkcia elementárnych viet."},
        {"id": "6", "text": "Všeobecná forma pravdivostnej funkcie je ..."},
        {"id": "7", "text": "O čom nemožno hovoriť, o tom treba mlčať."},
    ]


def test_load_normal_json(tmp_path):
    (tmp_path / "text.json").write_text(json.dumps(book(), ensure_ascii=False), encoding="utf-8")
    assert len(read_book(tmp_path / "text.json")) == 9


def test_load_reject_duplicate(tmp_path):
    (tmp_path / "text.json").write_text(json.dumps([book()[0], book()[0]]), encoding="utf-8")
    with pytest.raises(BookError, match="Duplicitné"):
        read_book(tmp_path / "text.json")


def test_load_missing(tmp_path):
    with pytest.raises(BookError, match="Chýba"):
        read_book(tmp_path / "text.json")


def test_passages_references():
    passages = choose_passages(book(), "Čo znamená téza 2.1 o obrazoch?", "2.1")
    assert "2.1" in {p["id"] for p in passages}
    assert len(passages) <= 14
    assert "[2.1]" in context_for_model(book(), "obraz", "2.1")


def test_error_quota():
    assert "429" in api_error_message(Exception("RESOURCE_EXHAUSTED: 429 too many"))
    assert "limit 0" in api_error_message(Exception("429: limit: 0"))


def test_export():
    out = format_transcript([{"role":"user", "content":"Moja otázka"},
                             {"role":"assistant", "content":"Odpoveď"}],
                            "Jana", 9, "gemini-3.8-flash", "abc",
                            datetime(2026, 10, 19, 12, 0, tzinfo=ZoneInfo("Europe/Bratislava")))
    assert "ŠTUDENT:" in out and "AI TÚTOR:" in out
    assert "1 / 20" in out and "Jana" in out
