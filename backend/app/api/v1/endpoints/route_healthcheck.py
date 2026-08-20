"""Routes de contrôle de santé de Chess Agent.

Ce module expose trois niveaux de contrôle :

- liveness : vérifie que l'API est active ;
- readiness : vérifie que les dépendances critiques sont disponibles ;
- diagnostic : retourne l'état complet des services.

Il ne contient aucune logique métier.
"""

from __future__ import annotations

from fastapi import APIRouter, status

from app.api.v1.dependencies.services import (
    HealthcheckServiceDependency,
)
from app.schemas.analysis.healthcheck import (
    HealthcheckResponse,
)

# Routeur

router = APIRouter()


# Liveness


@router.get(
    "/health/live",
    status_code=status.HTTP_200_OK,
    summary="Vérifier que l'API est active",
    description=(
        "Retourne un statut simple permettant de vérifier que "
        "le processus FastAPI est actif et capable de répondre."
    ),
)
async def live() -> dict[str, str]:
    """Retourne l'état de vie du backend."""

    return {"status": "alive"}


# Readiness


@router.get(
    "/health/ready",
    status_code=status.HTTP_200_OK,
    summary="Vérifier que l'application est prête",
    description=(
        "Vérifie les dépendances critiques nécessaires au "
        "fonctionnement principal de Chess Agent."
    ),
)
async def ready(
    healthcheck_service: HealthcheckServiceDependency,
) -> dict[str, str]:
    """Vérifie que les dépendances critiques sont disponibles."""

    await healthcheck_service.check_readiness()

    return {"status": "ready"}


# Diagnostic complet


@router.get(
    "/healthcheck",
    response_model=HealthcheckResponse,
    status_code=status.HTTP_200_OK,
    summary="Vérifier l'état complet des services",
    description=(
        "Retourne le diagnostic détaillé des services internes "
        "et externes utilisés par Chess Agent."
    ),
)
async def healthcheck(
    healthcheck_service: HealthcheckServiceDependency,
) -> HealthcheckResponse:
    """Retourne le diagnostic complet des services."""

    return await healthcheck_service.check()
