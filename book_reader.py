"""Bezokrajová interaktívna čítačka celej knihy – komponent Streamlit V2."""
import streamlit as st


READER_CSS = r"""
:host { display: block; color: var(--st-text-color, #222); }
.tract-shell { font-family: Georgia, 'Times New Roman', serif; width: 100%; }
.tract-toolbar { display: flex; align-items: center; gap: 7px; padding: 0 14px 8px 0;
  font-family: system-ui, sans-serif; font-size: 12px; }
.tract-toolbar input { min-width: 0; flex: 1; border: 1px solid #bec5cc; border-radius: 7px;
  padding: 7px 9px; font-family: system-ui, sans-serif; color: var(--st-text-color, #333);
  background: var(--st-background-color, #fff); }
.tract-toolbar button { cursor: pointer; border: 1px solid #b6bcc4; background: transparent;
  border-radius: 6px; min-width: 30px; min-height: 31px; color: var(--st-text-color, #333); }
.tract-counter { font-size: 11px; min-width: 60px; text-align: center; color: var(--st-text-color, #333); }
.tract-scroll {
  overflow-y: auto; overflow-x: hidden;
  height: min(780px, calc(100dvh - 206px)); min-height: 370px;
  padding: 1px 17px 44px 0;
  scrollbar-gutter: stable;
  overscroll-behavior: contain;
  scrollbar-width: auto;
  scrollbar-color: #555c65 #e4e7ea;
}
.tract-scroll::-webkit-scrollbar { width: 17px; }
.tract-scroll::-webkit-scrollbar-track { background: #e4e7ea; border-radius: 8px; }
.tract-scroll::-webkit-scrollbar-thumb { background: #555c65; border: 3px solid #e4e7ea; border-radius: 9px; }
.tract-scroll::-webkit-scrollbar-thumb:hover { background: #2c3138; }
.tract-entry { display: block; text-align: left; width: 100%; box-sizing: border-box;
  padding: 3px 2px 4px; margin: 0 0 3px;
  background: transparent; border: 0; border-radius: 2px; box-shadow: none; outline-offset: -2px;
  color: var(--st-text-color, #20262b); font-family: Georgia, 'Times New Roman', serif;
  font-size: 19px; line-height: 1.43; cursor: pointer; white-space: normal; overflow-wrap: break-word;
  word-break: normal; hyphens: auto; }
.tract-entry:hover { background: color-mix(in srgb, #e8dba3 27%, transparent); }
.tract-entry:focus-visible { outline: 2px solid #a78319; }
.tract-entry.is-selected { background: #fff0b7; color: #24231b; }
.tract-entry.is-match:not(.is-selected) { background: #f7f3e3; }
.tract-id { font-weight: 700; padding-right: 10px; }
.tract-text { white-space: pre-wrap; }
.tract-search-empty { font-family: system-ui, sans-serif; font-size: 12px; color: #8a4f3f; }
@media(max-width: 800px) {
  .tract-entry { font-size: 17px; line-height: 1.4; }
  .tract-scroll { min-height: 320px; height: 55dvh; }
  .tract-toolbar { flex-wrap: wrap; }
}
"""

READER_HTML = """
<div class="tract-shell" lang="sk">
  <div class="tract-toolbar">
    <input type="search" id="tract-find" placeholder="Hľadať slovo alebo číslo tézy" aria-label="Hľadať v knihe" />
    <button type="button" id="tract-prev" aria-label="Predchádzajúci výsledok">↑</button>
    <button type="button" id="tract-next" aria-label="Nasledujúci výsledok">↓</button>
    <span class="tract-counter" id="tract-counter"></span>
  </div>
  <div id="tract-reader" class="tract-scroll" aria-label="Text celej knihy"><div id="tract-entries"></div></div>
</div>
"""

# Dynamické texty vkladáme VÝHRADNE cez textContent, nikdy cez innerHTML.
READER_JS = r"""
export default function({ parentElement, data, setTriggerValue }) {
  const scroll = parentElement.querySelector('#tract-reader');
  const area = parentElement.querySelector('#tract-entries');
  const find = parentElement.querySelector('#tract-find');
  const count = parentElement.querySelector('#tract-counter');
  const previous = parentElement.querySelector('#tract-prev');
  const next = parentElement.querySelector('#tract-next');
  const storedKey = 'tractatus.reader.' + (data?.bookKey ?? 'book');
  let scrollSaved = 0;
  try { scrollSaved = Number(sessionStorage.getItem(storedKey + '.scroll') || 0); } catch (_) {}
  const oldScroll = scroll.scrollTop || scrollSaved;
  let searchValue = '';
  try { searchValue = sessionStorage.getItem(storedKey + '.search') || ''; } catch (_) {}
  find.value = searchValue;
  area.replaceChildren();
  const nodes = [];
  const normalize = s => String(s ?? '').normalize('NFD').replace(/[\u0300-\u036f]/g, '').toLowerCase();
  const entries = Array.isArray(data?.paragraphs) ? data.paragraphs : [];
  for (const entry of entries) {
    const b = document.createElement('button');
    b.className = 'tract-entry' + (entry.id === data?.selected ? ' is-selected' : '');
    b.type = 'button';
    b.setAttribute('aria-label', 'Vysvetliť tézu ' + entry.id);
    b.setAttribute('aria-pressed', entry.id === data?.selected ? 'true' : 'false');
    const id = document.createElement('span');
    id.className = 'tract-id';
    id.textContent = entry.id;
    const tx = document.createElement('span');
    tx.className = 'tract-text';
    tx.textContent = entry.text;
    b.append(id, tx);
    b.onclick = () => {
      for (const n of nodes) { n.node.classList.toggle('is-selected', n.id === entry.id); }
      try { sessionStorage.setItem(storedKey + '.scroll', String(scroll.scrollTop)); } catch (_) {}
      setTriggerValue('selected', entry.id);
    };
    area.appendChild(b);
    nodes.push({node: b, id: entry.id, content: normalize(entry.id + ' ' + entry.text)});
  }
  let matches = [];
  let current = 0;
  function updateCounter() { count.textContent = find.value.trim() ?
      (matches.length ? `${current + 1}/${matches.length}` : '0 nálezov') : `${nodes.length} téz`; }
  function goToMatch(step) {
    if (!matches.length) return;
    current = (current + step + matches.length) % matches.length;
    nodes[matches[current]].node.scrollIntoView({block:'center', behavior:'smooth'});
    updateCounter();
  }
  function refreshSearch(shouldJump) {
    const q = normalize(find.value.trim());
    matches = [];
    nodes.forEach((n,i) => {
      const match = q.length > 0 && n.content.includes(q);
      n.node.classList.toggle('is-match', match);
      if (match) matches.push(i);
    });
    current = 0;
    updateCounter();
    try { sessionStorage.setItem(storedKey + '.search', find.value); } catch (_) {}
    if (shouldJump && matches.length) goToMatch(0);
  }
  find.oninput = () => refreshSearch(true);
  previous.onclick = () => goToMatch(-1);
  next.onclick = () => goToMatch(1);
  scroll.scrollTop = oldScroll;
  refreshSearch(false);
  const save = () => {try { sessionStorage.setItem(storedKey + '.scroll', String(scroll.scrollTop)); } catch (_) {}};
  scroll.addEventListener('scroll', save, {passive: true});
  return () => scroll.removeEventListener('scroll', save);
}
"""

book_reader = st.components.v2.component(
    name="tractatus_continuous_book_reader_v2",
    html=READER_HTML,
    css=READER_CSS,
    js=READER_JS,
    isolate_styles=True,
)
