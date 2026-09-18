"""Thin client for Kalshi's public read-only market data API (no auth required
for market/series listing -- these are public GET endpoints)."""
import time
import requests

BASE = "https://api.elections.kalshi.com/trade-api/v2"

CATEGORIES = [
    "Politics", "Economics", "Financials", "World", "Climate and Weather",
    "Science and Technology", "Health",
]

HEADERS = {"User-Agent": "predict-gap-scanner/1.0 (contact: mr.nickchilds@gmail.com)"}


def _get(path, params=None, retries=3):
    url = f"{BASE}{path}"
    for attempt in range(retries):
        try:
            r = requests.get(url, params=params, headers=HEADERS, timeout=20)
            if r.status_code == 200:
                return r.json()
            if r.status_code in (429, 500, 502, 503):
                time.sleep(2 * (attempt + 1))
                continue
            r.raise_for_status()
        except requests.RequestException:
            if attempt == retries - 1:
                raise
            time.sleep(2 * (attempt + 1))
    return {}


def get_series_by_category():
    """Returns {series_ticker: series_dict} across our watched categories."""
    out = {}
    for cat in CATEGORIES:
        data = _get("/series", params={"category": cat})
        for s in data.get("series", []) or []:
            out[s["ticker"]] = s
    return out


def get_open_markets_for_series(series_ticker, limit=50):
    data = _get("/markets", params={"series_ticker": series_ticker, "status": "open", "limit": limit})
    return data.get("markets", []) or []


def market_mid_price(m):
    """Return the mid (implied yes probability, 0-1) for a Kalshi market dict,
    preferring bid/ask midpoint and falling back to last price."""
    bid = m.get("yes_bid_dollars")
    ask = m.get("yes_ask_dollars")
    try:
        bid = float(bid) if bid not in (None, "") else None
        ask = float(ask) if ask not in (None, "") else None
    except (TypeError, ValueError):
        bid = ask = None
    if bid is not None and ask is not None and (bid > 0 or ask > 0):
        return (bid + ask) / 2
    last = m.get("last_price_dollars")
    try:
        return float(last) if last not in (None, "") else None
    except (TypeError, ValueError):
        return None


def collect_watchlist(max_series=200, max_markets_per_series=10):
    """Walk our watched categories' series and pull their open markets, returning
    a flat list of normalized dicts: {title, ticker, url, price, close_time, liquidity, volume}.

    Note: Kalshi's per-market "liquidity" field reads 0 on this endpoint in
    practice, so we use open_interest (contracts outstanding) as the real
    activity signal instead, alongside 24h volume.
    """
    series_map = get_series_by_category()
    out = []
    for i, (ticker, s) in enumerate(series_map.items()):
        if i >= max_series:
            break
        markets = get_open_markets_for_series(ticker, limit=max_markets_per_series)
        for m in markets:
            price = market_mid_price(m)
            if price is None:
                continue
            title = m.get("title") or s.get("title") or ticker
            sub = m.get("yes_sub_title")
            full_title = f"{title} — {sub}" if sub and sub not in title else title
            open_interest = _safe_float(m.get("open_interest_fp") or m.get("open_interest"))
            volume = _safe_float(m.get("volume_24h_fp") or m.get("volume_24h"))
            out.append({
                "platform": "kalshi",
                "title": full_title,
                "ticker": m.get("ticker"),
                "series_ticker": ticker,
                "url": f"https://kalshi.com/markets/{ticker.lower()}",
                "price": price,
                "close_time": m.get("close_time"),
                "liquidity": max(open_interest, _safe_float(m.get("liquidity"))),
                "volume_24h": volume,
            })
    return out


def _safe_float(v):
    try:
        return float(v) if v not in (None, "") else 0.0
    except (TypeError, ValueError):
        return 0.0
