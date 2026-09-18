"""Renders the daily gap-scan results into a static index.html (GitHub Pages)."""
from datetime import datetime, timezone
from xml.sax.saxutils import escape

PAGE_TITLE = "Predict Gap Scanner"
PAGE_DESC = ("Kalshi vs Polymarket -- same real-world question, different price. "
             "Refreshed automatically every few hours from each platform's public API.")


def render(matches, generated_at=None):
    generated_at = generated_at or datetime.now(timezone.utc)
    rows = []
    for m in matches:
        k, p = m["kalshi"], m["polymarket"]
        gap_pct = f"{m['gap'] * 100:.1f}pts"
        sim_pct = f"{m['similarity'] * 100:.0f}%"
        rows.append(f"""
    <tr>
      <td class="gap">{gap_pct}</td>
      <td>
        <div class="q">{escape(k['title'])}</div>
        <div class="sub">
          <a href="{escape(k['url'])}" target="_blank" rel="noopener">Kalshi: {k['price']*100:.1f}%</a>
          &nbsp;vs&nbsp;
          <a href="{escape(p['url'])}" target="_blank" rel="noopener">Polymarket: {p['price']*100:.1f}%</a>
        </div>
      </td>
      <td class="sim">{sim_pct} match</td>
    </tr>""")

    rows_html = "".join(rows) if rows else (
        '<tr><td colspan="3" class="empty">No high-confidence matches with a '
        "meaningful price gap this run -- markets are efficient right now, or "
        "nothing overlapped closely enough between the two platforms.</td></tr>")

    return f"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>{PAGE_TITLE}</title>
<meta name="description" content="{PAGE_DESC}">
<style>
  :root {{ color-scheme: dark; }}
  body {{ background:#0b0f14; color:#e6edf3; font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Helvetica, Arial, sans-serif; margin:0; padding:0 16px 60px; }}
  .wrap {{ max-width: 880px; margin: 0 auto; }}
  h1 {{ font-size: 1.6rem; margin-top: 2rem; margin-bottom: 0.25rem; }}
  p.desc {{ color:#9aa7b2; margin-top:0; }}
  .meta {{ color:#6c7681; font-size: 0.85rem; margin-bottom: 1.5rem; }}
  table {{ width:100%; border-collapse: collapse; }}
  td {{ padding: 14px 10px; border-bottom: 1px solid #1c2530; vertical-align: top; }}
  td.gap {{ font-weight:700; font-size:1.1rem; color:#7ee787; white-space:nowrap; width:70px; }}
  td.sim {{ color:#6c7681; font-size:0.8rem; white-space:nowrap; width:90px; text-align:right; }}
  .q {{ font-size:1rem; margin-bottom:4px; }}
  .sub {{ font-size:0.85rem; color:#9aa7b2; }}
  a {{ color:#79c0ff; text-decoration:none; }}
  a:hover {{ text-decoration:underline; }}
  .empty {{ color:#6c7681; text-align:center; padding: 40px 0; }}
  footer {{ color:#6c7681; font-size:0.8rem; margin-top:2rem; }}
</style>
</head>
<body>
<div class="wrap">
  <h1>{PAGE_TITLE}</h1>
  <p class="desc">{PAGE_DESC}</p>
  <div class="meta">Last updated: {generated_at.strftime('%Y-%m-%d %H:%M UTC')} &middot; {len(matches)} matched markets shown</div>
  <table>
    <tbody>
      {rows_html}
    </tbody>
  </table>
  <footer>
    Sourced live from Kalshi's and Polymarket's public market-data APIs. Prices shown are the most
    recent snapshot at generation time and move constantly -- this is informational, not a trade
    recommendation, and nothing here is an offer to buy or sell any contract. Verify current prices
    on each platform before acting.
  </footer>
</div>
</body>
</html>
"""
