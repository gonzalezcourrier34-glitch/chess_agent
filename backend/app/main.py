"""Point d'entrée de l'application Chess Agent.

Ce module initialise :

- l'application FastAPI ;
- la configuration globale ;
- la journalisation ;
- le middleware CORS ;
- les routeurs de l'API ;
- la redirection vers la documentation.
"""

from __future__ import annotations

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import RedirectResponse

from app.api.exception_handlers import register_exception_handlers
from app.api.middleware import RequestIdMiddleware
from app.api.v1.router import api_router
from app.core.config import settings
from app.core.constants import API_PREFIX
from app.core.lifespan import lifespan
from app.core.logging import configure_logging

# Configuration

configure_logging()


# Application

app = FastAPI(
    title=settings.app_name,
    version=settings.app_version,
    debug=settings.app_debug,
    lifespan=lifespan,
    docs_url=(
        "/docs"
        if settings.api_docs_enabled
        else None
    ),
    redoc_url=(
        "/redoc"
        if settings.api_docs_enabled
        else None
    ),
    openapi_url=(
        "/openapi.json"
        if settings.api_docs_enabled
        else None
    )
)


# CORS

app.add_middleware(
    RequestIdMiddleware
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://localhost:4200"
    ],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"]
)


# Exceptions

register_exception_handlers(
    app
)


# Routes

app.include_router(
    api_router,
    prefix=API_PREFIX
)


# Racine

@app.get(
    "/",
    include_in_schema=False
)
async def root() -> RedirectResponse:
    """Redirige vers la documentation de l'API."""

    if settings.api_docs_enabled:
        return RedirectResponse(
            url="/docs",
            status_code=307
        )

    return RedirectResponse(
        url="/redoc",
        status_code=307
    )