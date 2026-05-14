# Tranquilytics

Stress-free stock analysis with transparent reasoning.

## Single repo App

- `backend/`: Python fastAPI (yfinance-first), report generation, SQLite DB, scikit for ML
- `frontend/`: React + Tailwind dashboard UI, Node.js
- `docs/`: project research PDFs and notes

## Local development

### Backend

```powershell
cd backend
python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -r requirements.txt
uvicorn app.main:app --reload --port 8000
```

API will be available at `http://127.0.0.1:8000` and docs at `http://127.0.0.1:8000/docs`.

### Frontend

```powershell
cd frontend
npm install
npm run dev
```

The UI will run at the URL printed by Vite (usually `http://127.0.0.1:5173`).

Keep the backend running on **port 8000** while developing the UI; Vite proxies requests from `/api/*` to `http://127.0.0.1:8000` (see `frontend/vite.config.ts`). If you deploy the frontend separately, set `VITE_API_BASE` to your API origin (no trailing slash).

Optional env for the dashboard **watchlist** (SQLite, separate from the TTL cache): set `TRANQUILYTICS_STATE_DB` to an absolute path if you want the DB file outside `backend/app/`. Rows are keyed by `user_id` (`local` by default, or `X-User-Id` for early multi-profile testing) so a hosted build can swap storage without changing the HTTP contract.

## Notes

- v1 uses **yfinance** for market data and recent **headlines** (when available).
- Headline polarity uses **VADER** (`vaderSentiment`) on text from **two lanes**: ticker news surfaced by **yfinance** plus **Google News RSS** queries for `{SYMBOL} stock` (distinct outlets, pooled so one pathway cannot dominate silently). Results are fused before the **synthesizer** blends headline probability with the technical stream.

- Alpha Vantage or other APIs can supplement or replace headline sources as a fallback later.

- **Daily movers dropdown** (`GET /market/daily-leaders`): ranks symbols by yesterday→latest daily % move within a **curated large-cap universe** (~30 liquid US names—not the full exchange). Profiles use `longBusinessSummary` from yfinance when available.

- The app avoids imperative language and includes a “not financial advice” disclaimer in UI/report output.
