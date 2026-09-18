"""Main entrypoint: pull markets from both platforms, match them, render the
site, and print a summary. Never raises on a partial failure of either source
-- if one platform's API is unreachable this run, we still render whatever we
have (or leave the previous page untouched) rather than crash the workflow.
"""
import json
import os
import sys
from datetime import datetime, timezone

sys.path.insert(0, os.path.dirname(__file__))

import kalshi_client   # noqa: E402
import polymarket_client  # noqa: E402
import match  # noqa: E402
import render_site  # noqa: E402

MIN_GAP = float(os.environ.get("MIN_GAP") or "0.04")  # 4 percentage points default
TOP_N = int(os.environ.get("TOP_N") or "40")
MIN_SIMILARITY = float(os.environ.get("MIN_SIMILARITY") or "0.32")
DEBUG_TITLES = (os.environ.get("DEBUG_TITLES") or "").lower() == "true"


def main():
    kalshi_rows, poly_rows = [], []
    try:
        kalshi_rows = kalshi_client.collect_watchlist()
        print(f"[kalshi] collected {len(kalshi_rows)} open markets")
    except Exception as e:
        print(f"[kalshi] fetch failed (non-fatal): {e}")

    try:
        poly_rows = polymarket_client.collect_top_markets()
        print(f"[polymarket] collected {len(poly_rows)} active markets")
    except Exception as e:
        print(f"[polymarket] fetch failed (non-fatal): {e}")

    if not kalshi_rows or not poly_rows:
        print("[scan] one or both sources empty this run -- skipping site regen "
              "to avoid overwriting a good page with an empty one")
        return

    if DEBUG_TITLES:
        print("[debug] sample kalshi titles:")
        for r in kalshi_rows[:20]:
            print(f"   liq={r['liquidity']:.0f} vol={r['volume_24h']:.0f}  {r['title']!r}")
        print("[debug] sample polymarket titles:")
        for r in poly_rows[:20]:
            print(f"   liq={r['liquidity']:.0f}  {r['title']!r}")

    all_matches = match.find_matches(kalshi_rows, poly_rows, min_similarity=MIN_SIMILARITY)
    if DEBUG_TITLES:
        print(f"[debug] {len(all_matches)} matches at threshold {MIN_SIMILARITY}")
        print("[debug] top candidates regardless of threshold (ignoring min_similarity):")
        top_cands = match.debug_top_candidates(kalshi_rows, poly_rows)
        for sim, date_gap, k, p in top_cands:
            dg = f"{date_gap:.0f}d" if date_gap is not None else "?"
            print(f"   sim={sim:.2f} dategap={dg}  K:{k['title'][:50]!r}  P:{p['title'][:50]!r}")
    flagged = [m for m in all_matches if m["gap"] >= MIN_GAP][:TOP_N]
    print(f"[scan] {len(all_matches)} total matches, {len(flagged)} above "
          f"{MIN_GAP*100:.0f}pt gap threshold")

    now = datetime.now(timezone.utc)
    html = render_site.render(flagged, generated_at=now)

    out_dir = os.path.join(os.path.dirname(__file__), "..", "docs")
    os.makedirs(out_dir, exist_ok=True)
    with open(os.path.join(out_dir, "index.html"), "w") as f:
        f.write(html)

    # Also dump raw data for anyone who wants to build on top of this later
    with open(os.path.join(out_dir, "matches.json"), "w") as f:
        json.dump({
            "generated_at": now.isoformat(),
            "matches": [
                {
                    "similarity": m["similarity"],
                    "gap": m["gap"],
                    "kalshi_title": m["kalshi"]["title"],
                    "kalshi_price": m["kalshi"]["price"],
                    "kalshi_url": m["kalshi"]["url"],
                    "polymarket_title": m["polymarket"]["title"],
                    "polymarket_price": m["polymarket"]["price"],
                    "polymarket_url": m["polymarket"]["url"],
                }
                for m in flagged
            ],
        }, f, indent=1)

    print(f"[scan] wrote docs/index.html with {len(flagged)} rows")
    for m in flagged[:10]:
        print(f"  {m['gap']*100:5.1f}pt  {m['kalshi']['title'][:60]!r}")


if __name__ == "__main__":
    main()
