"""Čítačka Traktátu – jedna posuvná oblasť a jednoznačná navigácia.

Zámer: minimum závislostí od layoutu nadradeného Streamlit komponentu.
Nezahŕňa žiadne volania Gemini; výklad aj dialóg ostávajú v app.py.
"""
import streamlit as st


READER_CSS = r"""
:host { display: block; width: 100%; height: 100%; min-height: 0; }
*, *::before, *::after { box-sizing: border-box; }
.tract-reader {
  display: block; position: relative; box-sizing: border-box;
  height: 575px; min-height: 575px; max-height: 575px; width: 100%;
  overflow-y: auto; overflow-x: hidden;
  overscroll-behavior-y: contain;
  scrollbar-width: auto;
  scrollbar-color: #5b616c #e5e8eb;
  background: var(--st-background-color, #fff);
  color: var(--st-text-color, #222);
}
.tract-reader::-webkit-scrollbar { width: 16px; }
.tract-reader::-webkit-scrollbar-track { background: #e5e8eb; }
.tract-reader::-webkit-scrollbar-thumb {
  background: #5b616c; border-radius: 10px; border: 3px solid #e5e8eb;
}
.tract-reader::-webkit-scrollbar-thumb:hover { background: #343c48; }
.tract-toolbar {
  position: sticky; top: 0; z-index: 10;
  display: flex; align-items: center; flex-wrap: wrap; gap: 7px;
  padding: 7px 9px 8px 0;
  background: var(--st-background-color, #fff);
  border-bottom: 1px solid #dadee2;
  font: 12px/1.3 system-ui, -apple-system, sans-serif;
}
.tract-toolbar input {
  flex: 1 1 180px; min-width: 110px; max-width: 100%;
  border: 1px solid #b9c0ca; border-radius: 6px;
  padding: 8px 9px; min-height: 35px;
  background: var(--st-background-color, #fff);
  color: var(--st-text-color, #222); font: 13px system-ui, sans-serif;
}
.tract-toolbar button {
  cursor: pointer; flex: 0 0 auto;
  border: 1px solid #b7bec9; background: var(--st-background-color, #fff);
  color: var(--st-text-color, #222); border-radius: 6px;
  min-height: 35px; padding: 6px 10px;
  font: 12px system-ui, sans-serif;
}
.tract-toolbar button:hover { background: #e5eaf1; color: #212936; }
.tract-toolbar button:focus-visible { outline: 2px solid #2156b0; outline-offset: 2px; }
.tract-counter {
  flex: 0 0 100%; margin: 1px 0 0;
  font: 12px system-ui, sans-serif;
  color: var(--st-text-color, #333);
}
.tract-book { padding: 8px 12px 4px 0; }
.tract-entry {
  display: block; text-align: left; width: 100%;
  padding: 3px 5px 5px; margin: 0 0 3px;
  border: 0; border-left: 4px solid transparent;
  border-radius: 2px; box-shadow: none;
  outline-offset: 0; background: transparent;
  color: var(--st-text-color, #20262b);
  font: 19px/1.46 Georgia, 'Times New Roman', serif;
  cursor: pointer; white-space: normal;
  overflow-wrap: anywhere; word-break: normal;
}
.tract-entry:hover { background: #f0f3f8; }
.tract-entry:focus-visible { outline: 2px solid #2463ae; }
/* Zvolená téza pre výklad – odlišné označenie od výsledkov vyhľadávania. */
.tract-entry.is-selected { border-left-color: #4878a7; background: #eaf3fc; }
/* IBA aktuálny nález je žltý. Iné nálezy zostávajú bez žltého pozadia. */
.tract-entry.is-current-match {
  border-left-color: #b57903; background: #ffe494; color: #1f2228;
  outline: 2px solid #c48c1c; outline-offset: -2px;
}
.tract-id { font-weight: 700; padding-right: 10px; }
.tract-text { white-space: pre-wrap; }
.tract-end {
  margin-top: 13px; padding: 12px 5px 22px;
  border-top: 1px solid #b7bec9;
  color: var(--st-text-color, #4d5662);
  font: 13px system-ui, sans-serif;
}
@media (max-width: 720px) {
  .tract-entry { font-size: 17px; line-height: 1.43; }
  .tract-toolbar { gap: 5px; }
  .tract-toolbar button { padding: 6px 7px; }
}
"""


READER_HTML = """
<div id="tract-reader" class="tract-reader" lang="sk" tabindex="0" aria-label="Čítačka knihy">
  <div class="tract-toolbar">
    <input id="tract-find" type="search" placeholder="Slovo alebo číslo tézy" autocomplete="off" aria-label="Hľadať v knihe" />
    <button id="tract-prev" type="button" aria-label="Predchádzajúci nález" title="Predchádzajúci nález">↑</button>
    <button id="tract-next" type="button" aria-label="Nasledujúci nález" title="Nasledujúci nález">↓</button>
    <button id="tract-first" type="button">Na začiatok</button>
    <button id="tract-last" type="button">Na koniec</button>
    <span id="tract-counter" class="tract-counter" role="status" aria-live="polite"></span>
  </div>
  <div id="tract-book" class="tract-book"></div>
  <div id="tract-end" class="tract-end">Koniec textu</div>
</div>
"""


READER_JS = r"""
export default function({ parentElement, data, setTriggerValue }) {
  const reader = parentElement.querySelector('#tract-reader');
  const book = parentElement.querySelector('#tract-book');
  const end = parentElement.querySelector('#tract-end');
  const input = parentElement.querySelector('#tract-find');
  const counter = parentElement.querySelector('#tract-counter');
  const prev = parentElement.querySelector('#tract-prev');
  const next = parentElement.querySelector('#tract-next');
  const first = parentElement.querySelector('#tract-first');
  const last = parentElement.querySelector('#tract-last');
  const entries = Array.isArray(data?.paragraphs) ? data.paragraphs : [];
  const storedKey = 'tractatus.reader.v5.' + (data?.bookKey || 'book');
  const normalize = (value) => String(value ?? '').normalize('NFD')
    .replace(/[\u0300-\u036f]/g, '').toLocaleLowerCase('sk');

  // CELY text má len JEDNÉ scrollovateľné miesto: #tract-reader.
  // Výšku určuje Streamlit pri montovaní komponentu.
  // Nemeníme rozmery na základe obsahu, nespúšťame nekonečné prepočty.
  const nodes = [];
  const fragment = document.createDocumentFragment();
  entries.forEach((entry) => {
    const button = document.createElement('button');
    button.type = 'button';
    button.className = 'tract-entry';
    if (entry.id === data?.selected) button.classList.add('is-selected');
    button.setAttribute('aria-label', 'Vysvetliť tézu ' + entry.id);
    const id = document.createElement('span');
    id.className = 'tract-id';
    id.textContent = entry.id;
    const content = document.createElement('span');
    content.className = 'tract-text';
    content.textContent = entry.text;
    button.append(id, content);
    button.addEventListener('click', () => {
      nodes.forEach((n) => n.el.classList.toggle('is-selected', n.id === entry.id));
      saveScroll();
      setTriggerValue('selected', entry.id);
    });
    fragment.appendChild(button);
    nodes.push({id: entry.id, el: button, content: normalize(entry.id + ' ' + entry.text)});
  });
  book.replaceChildren(fragment);
  end.textContent = 'Koniec textu';

  let storedScroll = 0;
  let storedQuery = '';
  try {
    storedScroll = Math.max(0, Number(sessionStorage.getItem(storedKey + '.scroll') || 0));
    storedQuery = sessionStorage.getItem(storedKey + '.query') || '';
  } catch (_) { /* Firefox privacy settings may block storage */ }

  let hits = [];
  let activeIndex = 0;
  let allowSave = false;

  const maximumScroll = () => Math.max(0, reader.scrollHeight - reader.clientHeight);
  const setPosition = (pos) => {
    // ScrollTop sa nastavuje IBA na ten istý element, ktorý má overflow-y:auto.
    const nextPosition = Math.max(0, Math.min(maximumScroll(), pos));
    reader.scrollTop = nextPosition;
    saveScroll();
  };
  function saveScroll() {
    if (!allowSave) return;
    try { sessionStorage.setItem(storedKey + '.scroll', String(reader.scrollTop)); } catch (_) {}
  }
  function jumpToPosition(pos) {
    // Po kliknutí neobnovujeme starú pozíciu pomocou requestAnimationFrame.
    allowSave = true;
    setPosition(pos);
  }
  function jumpToParagraph(element) {
    const toolbar = parentElement.querySelector('.tract-toolbar');
    const toolbarHeight = toolbar?.getBoundingClientRect().height || 0;
    const relTop = element.getBoundingClientRect().top - reader.getBoundingClientRect().top;
    // Vybraná téza sa ukáže tesne pod sticky ovládaním.
    jumpToPosition(reader.scrollTop + relTop - toolbarHeight - 13);
  }
  function drawActive() {
    nodes.forEach((n) => n.el.classList.remove('is-current-match'));
    if (!hits.length) {
      counter.textContent = input.value.trim() ? 'Žiadne výsledky' : '';
      return;
    }
    const node = nodes[hits[activeIndex]];
    node.el.classList.add('is-current-match');
    counter.textContent = `Nález ${activeIndex + 1} z ${hits.length} · téza ${node.id}`;
  }
  function search(jump=true) {
    const q = normalize(input.value.trim());
    hits = q ? nodes.flatMap((n, i) => n.content.includes(q) ? [i] : []) : [];
    activeIndex = 0;
    drawActive();
    try { sessionStorage.setItem(storedKey + '.query', input.value); } catch (_) {}
    if (jump && hits.length) jumpToParagraph(nodes[hits[0]].el);
  }
  function goHit(delta) {
    if (!hits.length) return;
    activeIndex = (activeIndex + delta + hits.length) % hits.length;
    drawActive();
    jumpToParagraph(nodes[hits[activeIndex]].el);
  }

  input.value = storedQuery;
  search(false);
  input.addEventListener('input', () => search(true));
  input.addEventListener('keydown', (event) => {
    if (event.key === 'Enter' || event.key === 'ArrowDown') {
      event.preventDefault();
      goHit(+1);
    } else if (event.key === 'ArrowUp') {
      event.preventDefault();
      goHit(-1);
    }
  });
  prev.addEventListener('click', () => goHit(-1));
  next.addEventListener('click', () => goHit(+1));
  first.addEventListener('click', () => jumpToPosition(0));
  last.addEventListener('click', () => jumpToPosition(reader.scrollHeight));

  // Po vykreslení 524 téz raz obnovíme polohu čítania. Nevkladáme druhý
  // plánovaný rAF, ktorý by spätne prepisoval kliknutie Na koniec/Na začiatok.
  reader.scrollTop = Math.min(maximumScroll(), storedScroll);
  allowSave = true;
  const onScroll = () => saveScroll();
  reader.addEventListener('scroll', onScroll, {passive:true});
  return () => reader.removeEventListener('scroll', onScroll);
}
"""


book_reader = st.components.v2.component(
    name="tractatus_continuous_book_reader_v5_one_scroll_search_active",
    html=READER_HTML,
    css=READER_CSS,
    js=READER_JS,
    isolate_styles=True,
)
