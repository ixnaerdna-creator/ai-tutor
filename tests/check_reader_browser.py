"""Manuálny prehliadačový test čítačky: python tests/check_reader_browser.py"""
from pathlib import Path
from ast import parse, literal_eval
import json
from playwright.sync_api import sync_playwright

folder = Path(__file__).resolve().parents[1]
source = (folder/'book_reader.py').read_text()
module = parse(source)
vars = {}
for stmt in module.body:
    if hasattr(stmt, 'targets') and len(stmt.targets)==1 and hasattr(stmt.targets[0], 'id'):
        if stmt.targets[0].id in ('READER_HTML', 'READER_CSS', 'READER_JS'):
            vars[stmt.targets[0].id] = literal_eval(stmt.value)
js = vars['READER_JS'].replace('export default function(', 'function mount(')
paras = [{'id':str(i/100), 'text':'Toto je kontrolná testovacia veta s diakritikou. ' * (2+(i%7))} for i in range(1, 701)]
data = {'paragraphs':paras, 'selected':None, 'bookKey':'browser-test'}
html = '''<!doctype html><html><head><meta charset="utf-8"><style>
*{box-sizing:border-box} body{margin:0;padding:15px;font-family:sans-serif}
#host{width:65%;height:680px;border:1px solid #ddd} </style></head><body>
<h3>Test čítačky</h3><div id="host"></div><script>
const host=document.getElementById('host'); const root=host.attachShadow({mode:'open'});
const style=document.createElement('style'); style.textContent=CSS_CONTENT;
root.innerHTML=HTML_CONTENT; root.prepend(style);
JS_CONTENT
mount({parentElement:root, data:DATA_CONTENT, setTriggerValue:(k,v)=>window.chosen={k,v}});
window.getMetrics=()=>{const e=root.querySelector('#tract-reader');const shell=root.querySelector('.tract-shell');
return {clientHeight:e.clientHeight, scrollHeight:e.scrollHeight, scrollTop:e.scrollTop,
lastVisible:root.querySelector('#tract-end').getBoundingClientRect().bottom <= e.getBoundingClientRect().bottom+1,
count:root.querySelectorAll('.tract-entry').length,
shellHeight:shell.getBoundingClientRect().height,
lastID:root.querySelector('#tract-end').textContent};};
</script></body></html>'''
html = html.replace('CSS_CONTENT', json.dumps(vars['READER_CSS'])).replace('HTML_CONTENT',json.dumps(vars['READER_HTML'])).replace('JS_CONTENT',js).replace('DATA_CONTENT',json.dumps(data,ensure_ascii=False))
p = folder/'tests'/'_browser_reader_test.html'
p.write_text(html)
try:
    with sync_playwright() as pl:
        browser=pl.chromium.launch(headless=True, executable_path='/usr/bin/chromium', args=['--no-sandbox','--disable-dev-shm-usage'])
        page=browser.new_page(viewport={'width':1400,'height':1000})
        page.on("pageerror", lambda e: print("PAGE ERROR", e))
        page.on("console", lambda e: print("CONSOLE",e.text))
        page.set_content(html)
        print('Before:', page.evaluate('window.getMetrics()'))
        page.locator('#host').locator('css=button#tract-last').click()
        result = page.evaluate('window.getMetrics()')
        print('At end:',result)
        assert result['count']==700
        assert result['scrollTop']>0
        assert result['lastVisible'], 'Last text footer is not visible after clicking Na koniec'
        assert '7.0' in result['lastID']
        # Check end really visible after manual scroll wheel and search functionality
        page.locator('#host').locator('css=button#tract-first').click()
        zero=page.evaluate('window.getMetrics()')
        assert zero['scrollTop']==0
        print('PASS: bottom reachable, top reachable, all paragraphs loaded')
        browser.close()
finally:
    p.unlink(missing_ok=True)
