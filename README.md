# Tranquilytics

Stress-free stock analysis with transparent reasoning.

## Overview

Single-repository full stack:

| Area | Stack | Path |
|------|--------|------|
| API | Python 3.12+ (recommended), **FastAPI**, **uvicorn**, **Pydantic** | `backend/` |
| UI | **React 19**, **Vite**, **Tailwind CSS** (Node.js for tooling) | `frontend/` |
| Docs | Report drafts, figures for write-ups | `docs/` |

Market data and ticker news use **yfinance** (unofficial Yahoo source). Headlines also use **Google News RSS** (`httpx`). Sentiment uses **VADER**. A lightweight **scikit-learn** pipeline scores technical “probability up” per horizon; results are **blended with headline probabilities** and mapped to five **non-imperative** tones via a **policy layer** (not trading advice).

---

## Prerequisites

- **Python** 3.12 (matches CI in `.github/workflows/ci.yml`; 3.10+ may work if dependencies install).
- **Node.js** 20 LTS or newer and **npm** (ships with Node).
- **Windows** PowerShell commands below; macOS/Linux: use `source .venv/bin/activate` instead of `Activate.ps1`.

---

## Quick start (local)

Run **backend** and **frontend** in **two terminals**. The UI proxies `/api/*` to `http://127.0.0.1:8000` (see `frontend/vite.config.ts`).

### 1. Backend API

```powershell
cd backend
python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -r requirements.txt
python run.py --reload --port 8000
```

(`python run.py` runs single-process uvicorn without uvicorn’s multiprocessing `--reload` worker, which on Python 3.14 can emit `RuntimeWarning: coroutine 'Server.serve' was never awaited` after Ctrl+C. For a one-shot server with no file watching: `python run.py --port 8000`.)

- JSON API root: `http://127.0.0.1:8000/`
- Interactive docs: `http://127.0.0.1:8000/docs`
- Health: `http://127.0.0.1:8000/health`

### 2. Frontend dashboard

```powershell
cd frontend
npm install
npm run dev
```

Open the URL Vite prints (usually `http://127.0.0.1:5173`). Keep the backend on **port 8000** so lookups and reports succeed.

### 3. Optional: isolated API base

If you serve the API elsewhere, build or run the frontend with:

```powershell
$env:VITE_API_BASE="https://your-api.example.com"
npm run dev
```

(No trailing slash on `VITE_API_BASE`.)

---

## Environment variables

| Variable | Where | Purpose |
|----------|--------|---------|
| `TRANQUILYTICS_STATE_DB` | Backend | Absolute path to SQLite file for **watchlist** state (default: under `backend/app/`). |
| `VITE_API_BASE` | Frontend (build/dev) | API origin when not using the Vite dev proxy (empty/unset → `/api`). |

### Performance note (screens & time complexity)

- The slow part is usually **HTTP calls** to Yahoo (and optional RSS), not in-memory ML. Work per symbol scales with history length **T** in a simple way (**O(T)** for rolling features—not the bottleneck vs network latency).
- **Per-symbol preview cache** (~20 minutes, SQLite) avoids redoing a full preview when the same ticker is requested again (including overlapping bulk scans).
- The **S&P / curated screener** calls preview in **`screen_mode`**: it **skips Google RSS and company blurbs** to reduce requests; headline sentiment uses **Yahoo ticker news only**, so results may **differ slightly** from the main dashboard preview.
- **`refresh=1`** on `/market/daily-picks` forces a fresh run and bypasses per-symbol preview cache for that scan.

---

## How to run tests

**Backend** (from `backend/`, with `app` on `PYTHONPATH`; PowerShell):

```powershell
$env:PYTHONPATH = "."
python -m pytest -q
```

**Frontend**:

```powershell
cd frontend
npm run test:unit
npm run lint
```

**E2E** (Playwright; ensure app or mocks as your project expects):

```powershell
cd frontend
npm run test:e2e
```

---

## UI: confidence bar and synthesizer explanations

After a successful ticker lookup, each **confidence** bar has a **?** control. After **Generate Analysis**, each **Technical + sentiment synthesizer** panel has a **How it works** link. They open the same explanatory copy used in code:

- **Frontend (source of truth for display):** `frontend/src/analysisExplanations.ts` — sections list formulas aligned with `advice_policy.py` (confidence) and `synthesizer.py` (blend weights and return nudge).
- **Backend (short summaries for docs/tests):** `backend/app/services/analysis_explanations.py` — keep in sync when policies change.

---

## Operational notes

- **Yahoo / yfinance rate limits:** Burst traffic can trigger `YFRateLimitError`. The API may respond with **503** and a JSON `detail` instead of misclassifying symbols. Wait and retry; avoid hammering **Daily picks** over huge universes during demos.
- **Watchlist** stores rows in SQLite keyed by `user_id` (default **`local`**; header `X-User-Id` for early multi-profile tests).
- **Daily movers** (`GET /market/daily-leaders`) rank a **curated** large-cap list, not the entire exchange.

---

## Report write-up (`docs/`)

- `docs/FINAL_REPORT.md` — structured report source for coursework.
- `docs/figures/` — optional screenshots referenced from the report.

---

## Repository layout (concise)

```
backend/app/           FastAPI routers, services (market, ML, sentiment, report)
backend/tests/         pytest
frontend/src/          App, API client, explanation modals
docs/                  PDFs, FINAL_REPORT.md, figures
```

---

## Disclaimer

This software is for **education and research**. It is **not** financial advice. Headlines and scraped data can be incomplete, biased, or delayed.
