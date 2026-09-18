"""Thin client for Polymarket's public Gamma API (no auth required for reading
market listings and prices)."""
import json
import time
import requests

BASE = "https://gamma-api.polymarket.com"
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
    return []


# Polymarket doesn't expose a clean "category" filter on this endpoint that
# matches Kalshi's, so we pull the highest-liquidity active binary markets
# (which skews toward politics/econ/current-events -- exactly the overlap
# we want with Kalshi) and let the text matcher in match.py do the rest.
def collect_top_markets(pages=6, page_size=100):
    out = []
    for offset in range(0, pages * page_size, page_size):
        data = _get("/markets", params={
            "limit": page_size,
            "offset": offset,
            "active": "true",
            "closed": "false",
            "order": "liquidity",
            "ascending": "false",
        })
        if not data:
            break
        for m in data:
            row = _normalize(m)
            if row:
                out.append(row)
        if len(data) < page_size:
            break
    return out


def _normalize(m):
    try:
        outcomes = json.loads(m.get("outcomes") or "[]")
        prices = json.loads(m.get("outcomePrices") or "[]")
    except (json.JSONDecodeError, TypeError):
        return None
    if len(outcomes) != 2 or len(prices) != 2:
        return None
    # Find the "Yes" (or first) outcome's implied probability
    yes_idx = 0
    for i, o in enumerate(outcomes):
        if str(o).strip().lower() == "yes":
            yes_idx = i
            break
    try:
        price = float(prices[yes_idx])
    except (TypeError, ValueError, IndexError):
        return None
    slug = m.get("slug") or ""
    return {
        "platform": "polymarket",
        "title": m.get("question") or "",
        "id": m.get("id"),
        "url": f"https://polymarket.com/event/{slug}" if slug else "https://polymarket.com",
        "price": price,
        "close_time": m.get("endDate"),
        "liquidity": _safe_float(m.get("liquidity")),
        "volume_24h": _safe_float(m.get("volume24hr") or m.get("volume")),
    }


def _safe_float(v):
    try:
        return float(v) if v not in (None, "") else 0.0
    except (TypeError, ValueError):
        return 0.0
