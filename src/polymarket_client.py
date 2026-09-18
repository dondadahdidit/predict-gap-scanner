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
# matches Kalshi's, so we pull the most actively-TRADED active binary markets
# (sorted by real 24h volume, not the "liquidity" field -- which is dominated
# by a handful of novelty/meme mega-series with huge phantom liquidity and
# near-zero real trading) and let the text matcher in match.py do the rest.
def collect_top_markets(pages=15, page_size=100):
    out = []
    for offset in range(0, pages * page_size, page_size):
        data = _get("/markets", params={
            "limit": page_size,
            "offset": offset,
            "active": "true",
            "closed": "false",
            "order": "volume24hr",
            "ascending": "false",
        })
        if not data:
            break
        for m in data:
            row = _normalize(m)
            if row and not _is_noise(row["title"]):
                out.append(row)
        if len(data) < page_size:
            break
    return out


_NOISE_PATTERNS = (
    "democratic presidential nomination",
    "republican presidential nomination",
)


def _is_noise(title):
    t = title.lower()
    return any(p in t for p in _NOISE_PATTERNS)


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
