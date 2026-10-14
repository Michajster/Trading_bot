"""Bot Claude – codzienne decyzje według stałych reguł na danych ze Stocklake.

Użycie:
    python3 claude_bot/strategy.py PLIK_Z_DANYMI.json [PLIK2.json ...]

Każdy plik to odpowiedź narzędzia Stocklake get_stocks ({"symbols": {...}}) albo sam słownik
{symbol: dane}. Skrypt łączy pliki, zapisuje surowy zrzut do claude_bot/snapshots/RRRR-MM-DD.json,
aktualizuje stan portfela w data/claude_bot.json i nic poza tym nie robi.

Reguły (zawsze te same, bez ręcznych wyjątków):
  1. Spółka może trafić do portfela, gdy:
     - cena jest powyżej średniej z 200 dni (trend wzrostowy),
     - prognozowany wskaźnik C/Z jest między 0 a 35 (firma zarabia i nie jest skrajnie droga),
     - średnia ocena analityków to co najmniej „kupuj” (wynik 2,5 lub mniej w skali 1–5),
     - przychody rosną rok do roku, a marża zysku jest dodatnia.
  2. Spełniające warunki spółki dostają cztery miejsca w rankingu:
     potencjał do celu analityków, wzrost zysków, taniość (niskie C/Z), marża zysku.
     Wynik to średnia z czterech miejsc w skali 0–100.
  3. Portfel ma 10 spółek. Spółka zostaje, dopóki jest w czołowej 15 i spełnia warunki
     (bufor ogranicza zbędne transakcje). Wolne miejsca zajmują najlepsze spółki spoza portfela,
     każda za równą część wolnej gotówki.
  4. Prowizja 0,1% od każdej transakcji. Start: 100 $ wirtualnych. Porównanie z funduszem SPY (S&P 500).
"""
import json
import os
import sys
from datetime import datetime, timezone

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
STATE = os.path.join(ROOT, "data", "claude_bot.json")
SNAPS = os.path.join(ROOT, "claude_bot", "snapshots")
UNIVERSE = os.path.join(ROOT, "claude_bot", "universe.json")
FEE, CAPITAL, SLOTS, KEEP = 0.001, 100.0, 10, 15
BENCH = "SPY"


def load_snapshot(paths):
    merged = {}
    for p in paths:
        with open(p) as f:
            j = json.load(f)
        merged.update(j.get("symbols", j))
    return merged


def eligible(d):
    ind = d.get("indicators") or {}
    price, sma200, pe = d.get("price"), ind.get("sma200"), d.get("pe_forward")
    an, rg, pm = d.get("analyst_rating_score"), d.get("revenue_growth"), d.get("profit_margins")
    reasons = []
    if not price or not sma200 or price <= sma200:
        reasons.append("cena pod średnią 200 dni")
    if not pe or pe <= 0 or pe > 35:
        reasons.append("C/Z poza zakresem 0–35")
    if an is None or an > 2.5:
        reasons.append("analitycy nie mówią „kupuj”")
    if rg is None or rg <= 0:
        reasons.append("przychody nie rosną")
    if pm is None or pm <= 0:
        reasons.append("brak zysku")
    return reasons


def pct_rank(values):
    """Higher value -> higher score, 0..100."""
    order = sorted(range(len(values)), key=lambda i: values[i])
    out = [0.0] * len(values)
    n = len(values)
    for r, i in enumerate(order):
        out[i] = 100.0 * r / (n - 1) if n > 1 else 100.0
    return out


def rank(snapshot, universe):
    rows, rejected = [], []
    for s in universe:
        d = snapshot.get(s)
        if not d:
            continue
        why = eligible(d)
        if why:
            rejected.append({"sym": s, "why": why})
            continue
        price = d["price"]
        rows.append({
            "sym": s, "name": d.get("name") or s, "sector": d.get("sector") or "",
            "price": price,
            "upside": (d.get("analyst_target") or price) / price - 1,
            "growth": max(-1.0, min(3.0, d.get("earnings_growth") or 0.0)),
            "value": 1.0 / d["pe_forward"], "pe": d["pe_forward"],
            "margin": d.get("profit_margins") or 0.0,
        })
    if rows:
        f = {k: pct_rank([r[k] for r in rows]) for k in ("upside", "growth", "value", "margin")}
        for i, r in enumerate(rows):
            r["parts"] = {k: round(f[k][i]) for k in f}
            r["score"] = round(sum(f[k][i] for k in f) / 4, 1)
    rows.sort(key=lambda r: -r["score"])
    return rows, rejected


def main(paths):
    snap = load_snapshot(paths)
    with open(UNIVERSE) as f:
        universe = json.load(f)["symbols"]
    stamps = [d.get("updated_at") for d in snap.values() if d.get("updated_at")]
    asof = max(stamps) if stamps else datetime.now(timezone.utc).isoformat()
    day = asof[:10]

    os.makedirs(SNAPS, exist_ok=True)
    keep = ("name", "sector", "price", "prev_close", "pe_forward", "pe_trailing", "analyst_rating_score", "analyst_target",
            "analyst_count", "revenue_growth", "earnings_growth", "profit_margins", "debt_to_equity", "market_cap_usd",
            "earnings_date", "updated_at")
    slim = {s: {k: d.get(k) for k in keep} | {"sma200": (d.get("indicators") or {}).get("sma200"),
                                              "rsi": (d.get("indicators") or {}).get("rsi")} for s, d in snap.items()}
    with open(os.path.join(SNAPS, day + ".json"), "w") as f:
        json.dump(slim, f, separators=(",", ":"))

    if os.path.exists(STATE):
        with open(STATE) as f:
            st = json.load(f)
    else:
        st = None
    # A second run on the same day replaces that day's decisions.
    if st and st.get("day") == day:
        st = st.get("before")  # may be None on the very first day
    core = ("start", "cash", "pos", "history", "trades", "bench_start", "day")
    before = {k: st[k] for k in core if k in st} if st else None
    before = json.loads(json.dumps(before)) if before else None
    if not st:
        st = {"start": day, "cash": CAPITAL, "pos": {}, "history": [], "trades": [], "bench_start": None}

    prices = {s: d["price"] for s, d in snap.items() if d.get("price")}
    bench = prices.get(BENCH)
    if bench and not st.get("bench_start"):
        st["bench_start"] = bench

    ranked, rejected = rank(snap, universe)
    place = {r["sym"]: i for i, r in enumerate(ranked)}
    top = [r["sym"] for r in ranked]
    trades = []

    def sell(sym, why):
        p = st["pos"][sym]
        px = prices.get(sym, p["last"])
        gross = p["qty"] * px
        fee = gross * FEE
        st["cash"] += gross - fee
        trades.append({"date": day, "sym": sym, "side": "sell", "qty": p["qty"], "price": px,
                       "usd": round(gross - fee, 4), "pl": round(gross - fee - p["cost"], 4), "why": why})
        del st["pos"][sym]

    for sym in list(st["pos"]):
        if sym not in prices:
            continue  # no data today: keep holding, decide tomorrow
        if sym not in place:
            sell(sym, "przestała spełniać warunki")
        elif place[sym] >= KEEP:
            sell(sym, f"spadła na {place[sym] + 1}. miejsce w rankingu")

    free = SLOTS - len(st["pos"])
    picks = [s for s in top if s not in st["pos"]][:max(0, free)]
    if picks:
        part = st["cash"] / len(picks)
        for sym in picks:
            px = prices[sym]
            fee = part * FEE
            qty = (part - fee) / px
            st["cash"] -= part
            st["pos"][sym] = {"qty": qty, "cost": part, "since": day, "last": px}
            trades.append({"date": day, "sym": sym, "side": "buy", "qty": qty, "price": px,
                           "usd": round(part, 4), "why": f"{place[sym] + 1}. miejsce w rankingu"})
    st["cash"] = max(0.0, st["cash"])

    for sym, p in st["pos"].items():
        if sym in prices:
            p["last"] = prices[sym]
    value = st["cash"] + sum(p["qty"] * p["last"] for p in st["pos"].values())
    bench_value = CAPITAL * bench / st["bench_start"] if bench and st.get("bench_start") else None
    st["history"] = [h for h in st["history"] if h["date"] != day]
    st["history"].append({"date": day, "value": round(value, 4), "spy": round(bench_value, 4) if bench_value else None})
    st["trades"] = (trades + st["trades"])[:400]

    st.update({
        "day": day, "asof": asof, "value": round(value, 4), "spy_value": bench_value,
        "positions": [{"sym": s, "name": (snap.get(s) or {}).get("name") or s, "qty": p["qty"], "cost": p["cost"],
                       "price": p["last"], "value": round(p["qty"] * p["last"], 4), "since": p["since"],
                       "rank": place.get(s, -1) + 1 if s in place else None} for s, p in sorted(
                           st["pos"].items(), key=lambda kv: place.get(kv[0], 999))],
        "ranking": [{k: r[k] for k in ("sym", "name", "sector", "price", "score", "parts", "pe")} |
                    {"upside": round(r["upside"] * 100, 1), "growth": round(r["growth"] * 100, 1), "margin": round(r["margin"] * 100, 1)}
                    for r in ranked[:20]],
        "rejected": rejected, "universe_size": len(universe), "eligible": len(ranked),
        "before": before,
    })
    os.makedirs(os.path.dirname(STATE), exist_ok=True)
    with open(STATE, "w") as f:
        json.dump(st, f, ensure_ascii=False, separators=(",", ":"))
    buys = sum(1 for t in trades if t["side"] == "buy")
    print(f"{day}: wartość {value:.2f} $, SPY {bench_value or 0:.2f} $, kupno {buys}, sprzedaż {len(trades) - buys}, "
          f"spełnia warunki {len(ranked)}/{len(universe)}")


if __name__ == "__main__":
    if len(sys.argv) < 2:
        sys.exit(__doc__)
    main(sys.argv[1:])
