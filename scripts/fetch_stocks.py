"""Pobiera ceny akcji (USA i GPW) z Yahoo Finance i zapisuje je do jednego pliku JSON.

Uruchamiane przez GitHub Actions co ~15 minut. Strona czyta wynik z gałęzi `data`.
Format: {"updated": sekundy, "fx": {"USDPLN": kurs},
         "assets": {"AAPL": {"name", "market", "cur", "iv": {"15m": [[czas_otwarcia_s, zamknięcie], ...], "1h": ..., "1d": ...}}}}
"""
import json
import sys
import time

import yfinance as yf

TICKERS = {
    "AAPL": ("Apple", "US"),
    "NVDA": ("Nvidia", "US"),
    "TSLA": ("Tesla", "US"),
    "MSFT": ("Microsoft", "US"),
    "AMZN": ("Amazon", "US"),
    "GOOGL": ("Alphabet", "US"),
    "PKO.WA": ("PKO BP", "PL"),
    "PKN.WA": ("Orlen", "PL"),
    "CDR.WA": ("CD Projekt", "PL"),
    "KGH.WA": ("KGHM", "PL"),
    "PZU.WA": ("PZU", "PL"),
    "ALE.WA": ("Allegro", "PL"),
}
# ile historii pobrać dla każdego interwału (limity Yahoo: 15m do 60 dni, 1h do 730 dni)
INTERVALS = {"15m": "30d", "1h": "180d", "1d": "2y"}


def rnd(x):
    return round(float(x), 4 if x < 100 else 2)


def series(symbol, interval, period):
    h = yf.Ticker(symbol).history(period=period, interval=interval, auto_adjust=False)
    if h is None or h.empty or "Close" not in h:
        return []
    out = []
    for ts, close in zip(h.index, h["Close"]):
        if close != close or close <= 0:  # NaN
            continue
        out.append([int(ts.timestamp()), rnd(close)])
    return out


def main(path):
    assets, errors = {}, []
    for sym, (name, market) in TICKERS.items():
        ivs = {}
        for iv, period in INTERVALS.items():
            try:
                s = series(sym, iv, period)
                if s:
                    ivs[iv] = s
            except Exception as e:  # jeden zły ticker nie psuje reszty
                errors.append(f"{sym} {iv}: {type(e).__name__}: {e}")
            time.sleep(0.3)
        if ivs:
            assets[sym] = {"name": name, "market": market, "cur": "PLN" if market == "PL" else "USD", "iv": ivs}

    fx = {}
    try:
        s = series("USDPLN=X", "1d", "5d")
        if s:
            fx["USDPLN"] = s[-1][1]
    except Exception as e:
        errors.append(f"USDPLN: {e}")

    for e in errors:
        print("UWAGA:", e)
    if not assets:
        print("Brak danych z Yahoo, nie nadpisuję pliku.")
        sys.exit(1)

    with open(path, "w") as f:
        json.dump({"updated": int(time.time()), "fx": fx, "assets": assets}, f, separators=(",", ":"))
    print(f"Zapisano {len(assets)} spółek do {path}")


if __name__ == "__main__":
    main(sys.argv[1] if len(sys.argv) > 1 else "stocks.json")
