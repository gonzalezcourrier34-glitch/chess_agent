"""Routes de supervision des services.

Ce module expose l'endpoint permettant de vérifier l'état des services
utilisés par Chess Agent.

Il ne contient aucune logique métier. La vérification de disponibilité
est déléguée au service de supervision.
"""

from __future__ import annotations

from fastapi import APIRouter, status

from app.api.v1.dependencies.services import HealthcheckServiceDependency
from app.api.responses import SERVER_ERROR_RESPONSES
from app.schemas.common.service import ServicesStatus

# Routeur


router = APIRouter()


# Supervision


@router.get(
    "",
    response_model=ServicesStatus,
    status_code=status.HTTP_200_OK,
    summary="Consulter l'état des services",
    description=(
        "Retourne l'état de fonctionnement des services utilisés par "
        "Chess Agent. Cet endpoint permet de vérifier rapidement la "
        "disponibilité de l'infrastructure."
    ),
    response_description="État des services.",
    responses=SERVER_ERROR_RESPONSES,
)
async def get_services_status(
    healthcheck: HealthcheckServiceDependency,
) -> ServicesStatus:
    """Retourne l'état des services de l'application."""

    response = await healthcheck.check()

    return response.services