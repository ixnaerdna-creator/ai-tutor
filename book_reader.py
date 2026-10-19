"""Súvislá čítačka s vlastným scrollovaním nezávislým od rozmerov Streamlitu."""
import streamlit as st


READER_CSS = r"""
:host { display: block; width: 100%; }
*, *::before, *::after { box-sizing: border-box; }
.tract-shell {
  display: flex; flex-direction: column;
  font-family: Georgia, 'Times New Roman', serif;
  height: 650px; min-height: 650px; max-height: 650px; width: 100%; overflow: hidden;
  color: var(--st-text-color, #222);
}
.tract-toolbar {
  display: flex; flex: 0 0 auto; flex-wrap: wrap; align-items: center;
  gap: 7px; padding: 0 10px 9px 0;
  font-family: system-ui, sans-serif; font-size: 12px;
}
.tract-toolbar input {
  min-width: 135px; flex: 1 1 220px;
  border: 1px solid #bec5cc; border-radius: 7px; padding: 8px 9px;
  font-family: system-ui, sans-serif;
  color: var(--st-text-color, #333);
  background: var(--st-background-color, #fff);
}
.tract-toolbar button {
  cursor: pointer; border: 1px solid #b6bcc4; background: transparent;
  border-radius: 6px; min-height: 34px; padding: 5px 9px;
  color: var(--st-text-color, #333); font: 12px system-ui, sans-serif;
}
.tract-toolbar button:hover { background: #e8e9eb; color: #222; }
.tract-counter { font-size: 12px; white-space: nowrap; color: var(--st-text-color, #333); }
.tract-scroll {
  flex: 1 1 0; min-height: 0; height: auto;
  overflow-y: scroll; overflow-x: hidden;
  padding: 2px 12px 8px 0; scrollbar-gutter: stable;
  overscroll-behavior: contain; scrollbar-width: auto;
  scrollbar-color: #555c65 #e4e7ea;
}
.tract-scroll::-webkit-scrollbar { width: 17px; }
.tract-scroll::-webkit-scrollbar-track { background: #e4e7ea; border-radius: 8px; }
.tract-scroll::-webkit-scrollbar-thumb { background: #555c65; border: 3px solid #e4e7ea; border-radius: 9px; }
.tract-scroll::-webkit-scrollbar-thumb:hover { background: #2c3138; }
.tract-entry {
  display: block; text-align: left; width: 100%;
  padding: 3px 2px 4px; margin: 0 0 3px;
  background: transparent; border: 0; border-radius: 2px;
  box-shadow: none; outline-offset: -2px;
  color: var(--st-text-color, #20262b);
  font: 19px/1.43 Georgia, 'Times New Roman', serif;
  cursor: pointer; white-space: normal; overflow-wrap: break-word;
  word-break: normal; hyphens: auto;
}
.tract-entry:hover { background: #f4edd0; }
.tract-entry:focus-visible { outline: 2px solid #a78319; }
.tract-entry.is-selected { background: #fff0b7; color: #24231b; }
.tract-entry.is-match:not(.is-selected) { background: #f7f3e3; }
.tract-id { font-weight: 700; padding-right: 10px; }
.tract-text { white-space: pre-wrap; }
.tract-end {
  margin-top: 22px; padding: 15px 0 24px;
  border-top: 1px solid #abb2b9;
  color: var(--st-text-color, #4c5661);
  font: 13px system-ui, sans-serif;
}
@media(max-width: 800px) {
  .tract-entry { font-size: 17px; line-height: 1.4; }
  .tract-toolbar button { font-size: 11px; }
}
"""

READER_HTML = """
<div class="tract-shell" lang="sk">
  <div class="tract-toolbar">
    <input type="search" id="tract-find" placeholder="Slovo alebo číslo tézy" aria-label="Hľadať v knihe" />
    <button type="button" id="tract-prev" aria-label="Predchádzajúci výsledok vyhľadávania">↑</button>
    <button type="button" id="tract-next" aria-label="Nasledujúci výsledok vyhľadávania">↓</button>
    <button type="button" id="tract-first">Na začiatok</button>
    <button type="button" id="tract-last">Na koniec</button>
    <span class="tract-counter" id="tract-counter"></span>
  </div>
  <div id="tract-reader" class="tract-scroll" aria-label="Text celej knihy">
    <div id="tract-entries"></div>
    <div id="tract-end" class="tract-end" tabindex="-1"></div>
  </div>
</div>
"""

# Text knihy vkladáme len cez textContent (nie innerHTML).
READER_JS = r"""
export default function({ parentElement, data, setTriggerValue }) {
  const shell = parentElement.querySelector('.tract-shell');
  const scroll = parentElement.querySelector('#tract-reader');
  const area = parentElement.querySelector('#tract-entries');
  const end = parentElement.querySelector('#tract-end');
  const find = parentElement.querySelector('#tract-find');
  const count = parentElement.querySelector('#tract-counter');
  const previous = parentElement.querySelector('#tract-prev');
  const next = parentElement.querySelector('#tract-next');
  const first = parentElement.querySelector('#tract-first');
  const last = parentElement.querySelector('#tract-last');
  const entries = Array.isArray(data?.paragraphs) ? data.paragraphs : [];
  const storedKey = 'tractatus.reader.' + (data?.bookKey ?? 'book');
  // Dôležité: výška vnútorného panelu je pevná v px. Percentá sa pri
  // Streamlit Components v2 môžu vzťahovať na obal bez určenej výšky.
  // Vtedy neexistuje vnútorný posuvník a navigačné tlačidlá nič nerobia.
  const requestedHeight = Number(data?.readerHeight);
  const fixedHeight = Number.isFinite(requestedHeight)
    ? Math.max(420, Math.min(900, requestedHeight)) : 650;
  shell.style.height = `${fixedHeight}px`;
  shell.style.minHeight = `${fixedHeight}px`;
  shell.style.maxHeight = `${fixedHeight}px`;
  let savedScroll = 0;
  let searchValue = '';
  try {
    savedScroll = Number(sessionStorage.getItem(storedKey + '.scroll') || 0);
    searchValue = sessionStorage.getItem(storedKey + '.search') || '';
  } catch (_) {}
  // Pri opätovnom vykreslení sa najprv vytvoria všetky tézy, až potom sa obnoví posun.
  find.value = searchValue;
  area.replaceChildren();
  const nodes = [];
  const normalize = s => String(s ?? '').normalize('NFD').replace(/[\u0300-\u036f]/g, '').toLowerCase();

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
      for (const n of nodes) {
        n.node.classList.toggle('is-selected', n.id === entry.id);
        n.node.setAttribute('aria-pressed', n.id === entry.id ? 'true' : 'false');
      }
      save();
      setTriggerValue('selected', entry.id);
    };
    area.appendChild(b);
    nodes.push({node: b, id: entry.id, content: normalize(entry.id + ' ' + entry.text)});
  }
  end.textContent = 'Koniec textu';

  let matches = [];
  let current = 0;
  function save() {
    try { sessionStorage.setItem(storedKey + '.scroll', String(scroll.scrollTop)); } catch (_) {}
  }
  function scrollToEntry(node) {
    // Posúva sa iba vnútorná čítačka. scrollIntoView by mohol posunúť aj stránku.
    const nodeRect = node.getBoundingClientRect();
    const viewportRect = scroll.getBoundingClientRect();
    const target = scroll.scrollTop + (nodeRect.top - viewportRect.top)
      - Math.max(0, (scroll.clientHeight - nodeRect.height) / 2);
    scroll.scrollTo({top: Math.max(0, target), behavior: 'instant'});
    save();
  }
  function updateCounter() {
    count.textContent = find.value.trim()
      ? (matches.length ? `${current + 1}/${matches.length}` : '0 nálezov')
      : '';
  }
  function goToMatch(step) {
    if (!matches.length) return;
    current = (current + step + matches.length) % matches.length;
    scrollToEntry(nodes[matches[current]].node);
    updateCounter();
  }
  function refreshSearch(shouldJump) {
    const q = normalize(find.value.trim());
    matches = [];
    nodes.forEach((n, i) => {
      const match = q.length > 0 && n.content.includes(q);
      n.node.classList.toggle('is-match', match);
      if (match) matches.push(i);
    });
    current = 0;
    updateCounter();
    try { sessionStorage.setItem(storedKey + '.search', find.value); } catch (_) {}
    if (shouldJump && matches.length) scrollToEntry(nodes[matches[0]].node);
  }
  find.oninput = () => refreshSearch(true);
  previous.onclick = () => goToMatch(-1);
  next.onclick = () => goToMatch(1);
  function jump(toEnd) {
    // Nepoužívame scrollIntoView(): ten by posúval aj CELÚ Streamlit stránku.
    // scrollTop funguje aj tam, kde scrollTo(..., behavior:'instant') nie.
    const apply = () => {
      const maximum = Math.max(0, scroll.scrollHeight - scroll.clientHeight);
      scroll.scrollTop = toEnd ? maximum : 0;
      save();
    };
    apply();
    // Streamlit môže pri novom zobrazení ešte dokončovať rozloženie.
    requestAnimationFrame(apply);
  }
  first.onclick = () => jump(false);
  last.onclick = () => jump(true);
  refreshSearch(false);
  // Obnovenie polohy pri ďalšom zobrazení komponentu (napr. po odpovedi AI).
  const restore = () => { scroll.scrollTop = Math.min(savedScroll, Math.max(0, scroll.scrollHeight - scroll.clientHeight)); };
  restore();
  requestAnimationFrame(restore);
  const onScroll = () => save();
  scroll.addEventListener('scroll', onScroll, {passive: true});
  return () => scroll.removeEventListener('scroll', onScroll);
}
"""

book_reader = st.components.v2.component(
    name="tractatus_continuous_book_reader_v4_fixedheight",
    html=READER_HTML,
    css=READER_CSS,
    js=READER_JS,
    isolate_styles=True,
)
