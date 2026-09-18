"""Cross-platform market matching: pairs up Kalshi and Polymarket markets that
are almost certainly asking the same real-world question, using normalized
token-overlap similarity on the title/question text plus a loose close-date
sanity check. No ML, no external service -- just deterministic text matching
so this stays free and dependency-light.
"""
import re
from datetime import datetime, timezone

STOPWORDS = {
    "will", "the", "a", "an", "by", "in", "of", "on", "to", "for", "be",
    "is", "are", "at", "before", "after", "than", "or", "and", "than",
    "win", "get", "does", "do", "than", "2025", "2026", "2027", "2028",
    "market", "yes", "no",
}


def _tokens(text):
    text = (text or "").lower()
    text = re.sub(r"[^a-z0-9%$.\s]", " ", text)
    words = [w for w in text.split() if w and w not in STOPWORDS]
    return set(words)


def _jaccard(a, b):
    if not a or not b:
        return 0.0
    inter = len(a & b)
    union = len(a | b)
    return inter / union if union else 0.0


def _parse_dt(s):
    if not s:
        return None
    try:
        return datetime.fromisoformat(str(s).replace("Z", "+00:00"))
    except ValueError:
        return None


def find_matches(kalshi_rows, poly_rows, min_similarity=0.32, max_date_gap_days=60,
                  min_poly_liquidity=300.0):
    """Greedy best-first matching. Returns a list of match dicts with both
    sides' info plus the computed similarity and price gap.

    Kalshi and Polymarket's "liquidity"-ish fields are on completely different
    scales (contract counts vs. dollars), so we filter each platform on its
    own terms: Kalshi markets need SOME observed activity (open interest or
    24h volume above zero), Polymarket markets need a modest dollar-liquidity
    floor to exclude dead listings.
    """
    k_rows = [r for r in kalshi_rows if r["liquidity"] > 0 or r["volume_24h"] > 0]
    p_rows = [r for r in poly_rows if r["liquidity"] >= min_poly_liquidity]

    k_tok = [(_tokens(r["title"]), r) for r in k_rows]
    p_tok = [(_tokens(r["title"]), r) for r in p_rows]

    candidates = []
    for kt, k in k_tok:
        kd = _parse_dt(k.get("close_time"))
        for pt, p in p_tok:
            sim = _jaccard(kt, pt)
            if sim < min_similarity:
                continue
            pd = _parse_dt(p.get("close_time"))
            if kd and pd:
                gap_days = abs((kd - pd).total_seconds()) / 86400
                if gap_days > max_date_gap_days:
                    continue
            candidates.append((sim, k, p))

    candidates.sort(key=lambda c: c[0], reverse=True)
    used_k, used_p, matches = set(), set(), []
    for sim, k, p in candidates:
        kk = (k["platform"], k.get("ticker"))
        pk = (p["platform"], p.get("id"))
        if kk in used_k or pk in used_p:
            continue
        used_k.add(kk)
        used_p.add(pk)
        gap = abs(k["price"] - p["price"])
        matches.append({
            "similarity": round(sim, 3),
            "gap": round(gap, 4),
            "kalshi": k,
            "polymarket": p,
        })

    matches.sort(key=lambda m: m["gap"], reverse=True)
    return matches


def debug_top_candidates(kalshi_rows, poly_rows, max_date_gap_days=60, top_n=20):
    """Diagnostic helper: ignores the similarity threshold entirely and returns
    the highest-similarity pairs found (after the same liquidity/activity
    filters as find_matches), so we can see what's *almost* matching."""
    k_rows = [r for r in kalshi_rows if r["liquidity"] > 0 or r["volume_24h"] > 0]
    p_rows = [r for r in poly_rows if r["liquidity"] >= 300.0]

    k_tok = [(_tokens(r["title"]), r) for r in k_rows]
    p_tok = [(_tokens(r["title"]), r) for r in p_rows]

    scored = []
    for kt, k in k_tok:
        kd = _parse_dt(k.get("close_time"))
        for pt, p in p_tok:
            sim = _jaccard(kt, pt)
            if sim <= 0:
                continue
            pd = _parse_dt(p.get("close_time"))
            date_gap = None
            if kd and pd:
                date_gap = abs((kd - pd).total_seconds()) / 86400
            scored.append((sim, date_gap, k, p))
    scored.sort(key=lambda c: c[0], reverse=True)
    return scored[:top_n]
