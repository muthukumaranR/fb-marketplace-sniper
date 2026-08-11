# MarketSwipe

Hunts underpriced listings on Facebook Marketplace. For each watched item, it
scrapes FB results, estimates a fair used price (web search + LLM, with an eBay
fallback), scores every listing for relevance against the query, and emails you
when a clear deal shows up.

- **Backend**: FastAPI + Celery/Redis, Playwright scrapers, SQLite, LiteLLM
- **Frontend**: React + Vite + TypeScript + Tailwind
- **Python 3.11+**, uv for env management

## Prerequisites

- **Docker + Docker Compose** (easiest path), or Python 3.11+ and Node 20+ for local dev
- A **Facebook account** (MarketSwipe uses your session — no credentials stored)
- One of:
  - **Gemini API key** (free tier works): https://aistudio.google.com/apikey
  - **Anthropic API key**: https://console.anthropic.com/
- **Gmail account + app password** for deal notifications (optional but recommended):
  https://myaccount.google.com/apppasswords

## Quick start (Docker)

```bash
git clone https://github.com/muthukumaranR/marketswipe.git
cd marketswipe

# 1. Configure environment
cp .env.example .env
# edit .env — at minimum set BLABLADOR_API_KEY (or GEMINI_API_KEY / ANTHROPIC_API_KEY)

# 2. One-time Facebook login (must run on the host, needs a real browser)
uv sync --no-dev
uv run playwright install chromium
uv run python -c "import asyncio; from backend.scraper_fb import init_fb_login; asyncio.run(init_fb_login())"
# A browser opens → log in to Facebook → press Enter in the terminal.
# Session is saved to ~/.config/marketswipe/fb_state.json and mounted into containers.

# 3. Start the stack
docker compose up --build
```

Open http://localhost:8000 — add items to your watchlist, click **Scan Now**,
and watch deals show up.

## Local development (no Docker)

```bash
# Backend
uv sync
uv run playwright install chromium
cp .env.example .env      # fill in LLM + SMTP keys
uv run python -c "import asyncio; from backend.scraper_fb import init_fb_login; asyncio.run(init_fb_login())"

# One-time FB login (see above), then in three terminals:
redis-server                                                   # terminal 1
uv run uvicorn backend.main:app --reload                       # terminal 2 — API on :8000
uv run celery -A backend.celery_app worker --beat -l info      # terminal 3 — scheduled scans

# Frontend dev server (optional, hot reload)
cd frontend && npm install && npm run dev                      # Vite on :5173 → proxies /api to :8000
```

Production build (what Docker serves): `cd frontend && npm run build` — the
FastAPI app serves the built SPA from `frontend/dist`.

## Configuration

All settings live in `.env` (see `.env.example`). Key knobs:

| Variable | Purpose |
|---|---|
| `BLABLADOR_API_KEY` | Blablador (Helmholtz/FZ Jülich) key — the preferred LLM provider when set |
| `BLABLADOR_URL` | Blablador OpenAI-compatible base URL (default `https://api.blablador.fz-juelich.de/v1`) |
| `BLABLADOR_MODEL_ALIAS` | Which Blablador alias to use (default `alias-fast`). See `GET /v1/models` for the list |
| `BLABLADOR_MODEL_LARGE` | Long-context reasoning alias for `llm_call_kwargs(large=True)` (default `alias-kimi-k3-1m`, 1M ctx). Slow — needs `stream=True` |
| `GEMINI_API_KEY` / `ANTHROPIC_API_KEY` | Fallback LLM providers (LiteLLM auto-detects) |
| `LLM_MODEL` | Bypass auto-detection with an explicit LiteLLM model string |
| `SMTP_USER` / `SMTP_PASS` / `NOTIFY_EMAIL` | Gmail SMTP for deal alerts |
| `DEFAULT_LOCATION` / `DEFAULT_RADIUS` | Default search area for new watch items |
| `GREAT_DEAL_THRESHOLD` / `GOOD_DEAL_THRESHOLD` | Price/fair-price ratios that qualify |
| `SCAN_INTERVAL_MINUTES` | How often Celery beat runs a full scan (default 30) |
| `NOTIFY_MIN_RELEVANCE` | Below this relevance score (0–1), skip the email even if the price looks great. Default `0.5` |

## How it finds deals

1. **Scrape** — Playwright (with stealth) pulls marketplace search results for each watch item.
2. **Price** — For each item, pick a fair used price. Chain: cached price → web search grounded LLM estimate → eBay sold-items Playwright scrape. 7-day cache per item.
3. **Facet extraction** — One LLM call per query converts the search term into a structured spec: `{model, storage, color, …}` each with a weight, interchangeable spellings (`PS5` / `PlayStation 5`), and an optional `required` flag — plus `exclude` terms naming accessories and companion items. Cached 30 days.
4. **Read the body** — For listings that are priced like a deal and pass the title gate, the full listing description is fetched (from `og:description`) so `for parts` buried in the body is caught. Bounded to those candidates — one detail page each is a bot-detection risk, so already-seen and already-disqualified listings are skipped.
5. **Score** — Each listing is matched deterministically against the spec (substring, squashed, compacted-unit, and token-set matching). A missing `required` facet scores 0. Accessory exclusions apply to the **title only** — a real console's body says "comes with 2 controllers" — while condition terms (`for parts`, `cracked`) apply to title and body. `relevance_score ∈ [0, 1]`. No network, so it is fully unit-tested.
6. **Rank** — `final_score = relevance × price_score`. A great price on the wrong item zeroes out, so it sinks to the bottom of "Best match" sort.
7. **Notify** — Email fires only for `great`/`good` deal-quality listings whose relevance ≥ `NOTIFY_MIN_RELEVANCE`.

## Tests

```bash
uv run pytest
```

72 tests cover DB, API, pricing, relevance scoring, and the scan pipeline
end-to-end (scraper/pricer/LLM patched).

## Project layout

```
backend/
  main.py             FastAPI app, SPA serving, image proxy
  config.py           Pydantic settings (env-driven)
  db.py               aiosqlite CRUD + schema migrations
  models.py           Pydantic response models
  pricer.py           Fair-price estimator (web search + LLM, eBay fallback)
  relevance.py        Facet extraction + deterministic listing relevance scoring
  scraper_fb.py       Facebook Marketplace scraper (Playwright + stealth)
  scraper_ebay.py     eBay sold-items scraper
  scraper_prices.py   Multi-source web price scraper (curl_cffi, Docker-safe)
  tasks.py            Celery tasks: scan_all, scan_item, refresh_prices
  notifier.py         Gmail SMTP deal emails
  routers/            FastAPI routers: watchlist, listings, scans, prices
frontend/
  src/                React + TS pages, API client, listings table
tests/
  test_api.py         FastAPI endpoints
  test_db.py          DB CRUD
  test_models.py      Pydantic validation
  test_pricer.py      Deal-quality evaluation
  test_relevance.py   Facet extraction + scoring
  test_tasks.py       End-to-end scan pipeline (mocked externals)
```

## Troubleshooting

- **`/api/auth/fb-status` returns `logged_in: false`** — re-run the `init_fb_login` command. If running Docker, the session file lives on the *host* at `~/.config/marketswipe/fb_state.json`; containers mount it read-only.
- **"No LLM API key configured"** — set `BLABLADOR_API_KEY`, `GEMINI_API_KEY`, or `ANTHROPIC_API_KEY` in `.env` and restart the backend/worker.
- **Price estimation times out on Blablador** — the reasoning aliases (`alias-kimi-k3-1m`, `alias-glm-huge`, `alias-deepseek-v4-flash-0731`) spend a long time thinking; a single price call measured ~2.5 min and the endpoint drops non-streamed requests around 50s. Use `BLABLADOR_MODEL_ALIAS=alias-fast` for the scan loop.
- **"Implausible price ... rejecting" in the logs** — a new estimate moved more than 3x from the last one for that item, so it was refused and the next source was tried. If the move is genuine (a new model launched), clear that item's rows from `price_cache` and re-run.
- **eBay scraper returns no prices in Docker** — eBay blocks datacenter IPs. The web-search scraper (`scraper_prices.py`) is the primary path; eBay is a fallback for local runs.
- **Celery worker not picking up tasks** — confirm Redis is running (`docker compose ps redis`) and `REDIS_URL` matches.

## Notes

This project is purely for educational purposes. Scraping Facebook Marketplace may violate their Terms of Service. Use responsibly, rate-limit yourself, and don't run this against accounts you can't afford to lose. DO NOT use this for commercial purposes or to gain an unfair advantage over other users. The author is not responsible for any consequences arising from the use of this software.