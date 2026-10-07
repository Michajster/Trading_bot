# Bot na 100 $

Strona do nauki tradingu na wirtualnych pieniądzach: https://michajster.github.io/Trading_bot/

**Bot** – strategia przecięcia dwóch średnich kroczących na krypto (BTC, ETH, SOL), akcjach z USA i z GPW. Interwał od 5 minut do 1 dnia. Backtest, test uczciwości (trening na 2/3 danych, sprawdzian na 1/3) i bot na żywo z wirtualnymi 100 $.

**Giełda** – ręczny handel za wirtualne 100 $: kupno i sprzedaż akcji USA, GPW i krypto, portfel z zyskiem lub stratą, historia zleceń. Akcje kupisz tylko w godzinach sesji.

## Skąd są ceny

- Krypto: publiczne API Binance, na żywo w przeglądarce.
- Akcje: Yahoo Finance. Workflow `.github/workflows/stocks.yml` co ~15 minut w dni robocze uruchamia `scripts/fetch_stocks.py` i zapisuje `stocks.json` na gałęzi `data`. Ceny są więc opóźnione o kilkanaście minut.

Prowizja w symulacji: 0,1% od transakcji. Projekt edukacyjny, nie porada inwestycyjna.
