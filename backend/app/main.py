from __future__ import annotations

"""
Tranquilytics backend API entrypoint.

Primary goal:
- Provide a thin, stable HTTP layer around report generation so the frontend can remain
  simple and the analysis logic can be refactored safely behind versioned endpoints.

Design intent:
- Keep routing + middleware here; keep business logic in `app/services/*`.
- Prototype-friendly CORS defaults (open) for local development; lock down later.
"""

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from yfinance.exceptions import YFRateLimitError

from app.routers.health import router as health_router
from app.routers.market import router as market_router
from app.routers.report import router as report_router
from app.routers.ticker import router as ticker_router
from app.routers.watchlist import router as watchlist_router


def create_app() -> FastAPI:
    app = FastAPI(
        title="Tranquilytics API",
        version="0.1.0",
        description="Stress-free, explainable stock analysis (prototype).",
    )

    app.add_middleware(
        CORSMiddleware,
        allow_origins=["*"],
        allow_credentials=False,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    app.include_router(health_router)
    app.include_router(ticker_router, prefix="/ticker", tags=["ticker"])
    app.include_router(report_router, prefix="/report", tags=["report"])
    app.include_router(market_router, prefix="/market", tags=["market"])
    app.include_router(watchlist_router, prefix="/watchlist", tags=["watchlist"])

    @app.exception_handler(YFRateLimitError)
    async def yfinance_rate_limited(_: Request, __: YFRateLimitError) -> JSONResponse:
        return JSONResponse(
            status_code=503,
            content={
                "detail": (
                    "Market data is temporarily unavailable because Yahoo Finance "
                    "rate-limited this client. Wait a few minutes and try again, or "
                    "try from another network."
                )
            },
        )

    @app.get("/", include_in_schema=False)
    def root() -> dict[str, str]:
        """8000 hosts the JSON API only; the SPA runs on Vite (typically :5173)."""
        return {
            "service": "Tranquilytics API",
            "docs": "/docs",
            "health": "/health",
            "note": (
                "No UI at /. Use http://localhost:5173 for the dashboard in dev "
                "(Vite proxies /api → this server)."
            ),
        }

    return app


app = create_app()

