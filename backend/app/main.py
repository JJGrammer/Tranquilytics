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

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.routers.health import router as health_router
from app.routers.report import router as report_router
from app.routers.ticker import router as ticker_router


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

    return app


app = create_app()

