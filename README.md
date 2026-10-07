# Bot na 100 $

Strona do nauki tradingu na wirtualnych pieniądzach: https://michajster.github.io/Trading_bot/

**Boty** – dowolnie wiele botów naraz, każdy z własnym wirtualnym kapitałem, na krypto (BTC, ETH, SOL), akcjach z USA i z GPW, z interwałem od 5 minut do 1 dnia. Cztery strategie: Siatka (grid), DCA, Trend (przecięcie średnich) i RSI. Opcjonalny stop loss i take profit. Przed startem podgląd na historii, potem lista botów z wynikiem, wykresem i historią transakcji.

**Giełda** – ręczny handel za wirtualne 100 $: kupno i sprzedaż akcji USA, GPW i krypto, portfel z zyskiem lub stratą, zlecenia stop loss i take profit dla każdej pozycji, historia zleceń. Akcje kupisz tylko w godzinach sesji.

## Skąd są ceny

- Krypto: publiczne API Binance, na żywo w przeglądarce.
- Akcje: Yahoo Finance. Workflow `.github/workflows/stocks.yml` co ~15 minut w dni robocze uruchamia `scripts/fetch_stocks.py` i zapisuje `stocks.json` na gałęzi `data`. Ceny są więc opóźnione o kilkanaście minut.

Prowizja w symulacji: 0,1% od transakcji. Projekt edukacyjny, nie porada inwestycyjna.
