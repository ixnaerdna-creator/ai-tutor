# Oprava čítačky – verzia 3

V GitHub repozitári, ktorý používa existujúca stránka `ai-tutor-tractatus.streamlit.app`, nahraďte **iba** `app.py` a `book_reader.py` súbormi z tohto balíka. Pôvodný `text.json`, `tutor_core.py`, `requirements.txt` a Streamlit Secrets zachovajte.

Po úspešnom nasadení obnovte stránku klávesmi Ctrl+F5. Oprava používa novú identitu komponentu (`v5`), aby sa nenačítala stará podoba.

## Zmeny
- Čítačka má jeden posuvný kontajner s pevným rozmerom riadeným cez `app.py` (720 px); posuvník aj tlačidlá pracujú s tým istým elementom.
- Odstránené druhé plánované obnovovanie starej polohy, ktoré mohlo prebíjať kliknutia na začiatok/koniec.
- Vyhľadávanie zvýrazňuje **len jeden aktívny nález**; čítačka uvádza „Nález X z Y · téza N“.
- Šípky ↑ ↓ a klávesy ↑ ↓ v poli vyhľadávania prechádzajú medzi nálezmi; Enter ide na ďalší nález.
- Výklad a diskusná logika sa nemenia.

## Overenie
1. Stlačte „Na koniec“: mala by byť viditeľná posledná téza `7` a „Koniec textu“.
2. Stlačte „Na začiatok“: prvá téza by mala byť viditeľná.
3. Vyhľadajte „svet“: jedna téza je žltá a zobrazí sa jej poradové číslo medzi výsledkami. Pomocou ↓ / ↑ prechádzajte nálezy.
4. Prejdite posuvníkom na úplný koniec. Otestujte tiež kliknutie na tézu a vytvorenie výkladu.

Test prehliadača s 524 syntetickými tézami potvrdil funkčnosť navigačných tlačidiel a zvýraznenia jedného výsledku; **skutočná nasadená stránka ešte otestovaná nebola**. Ak sa na nej správanie líši, potrebujeme snímku celej obrazovky a prípadné chyby z vývojárskej konzoly (F12 → Console); prípadne prístup ku GitHub repozitáru na kontrolu odlišností v produkčnom kóde.
