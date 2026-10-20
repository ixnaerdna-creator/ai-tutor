from pathlib import Path
from ast import parse, literal_eval


def test_scroll_component_size_and_footer():
    folder = Path(__file__).resolve().parents[1]
    app = (folder / 'app.py').read_text()
    reader = (folder / 'book_reader.py').read_text()
    assert 'height=680' in app
    assert 'KONIEC NAČÍTANÉHO TEXTU' in reader
    assert "#tract-last" in reader
    assert 'min-height: 0' in reader


def test_zero_quota_detection():
    from tutor_core import api_error_message
    msg = api_error_message(Exception('429 RESOURCE_EXHAUSTED; limit: 0'), 'gemini-3.8-flash')
    assert 'nulovú kvótu' in msg
    assert 'gemini-3.8-flash' in msg
