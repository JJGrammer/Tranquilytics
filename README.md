# Tranquilytics

Stress-free stock analysis with transparent reasoning.

## Monorepo layout

- `backend/`: Python API (yfinance-first), report generation, caching
- `frontend/`: React + Tailwind dashboard UI
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

## Notes

- v1 uses **yfinance** for market data. Alpha Vantage can be added as a secondary fallback later.
- The app avoids imperative language and includes a “not financial advice” disclaimer in UI/report output.

