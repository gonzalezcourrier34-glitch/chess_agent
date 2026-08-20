"""Routes de gestion de l'historique des analyses.

Ce module expose les endpoints permettant de :

- consulter les analyses enregistrées ;
- parcourir l'historique avec pagination ;
- récupérer une analyse précise ;
- supprimer une analyse enregistrée.

Il ne contient aucune logique métier.

La validation des paramètres de pagination est déléguée aux dépendances
FastAPI.

La lecture, la recherche et la suppression des analyses sont entièrement
déléguées au MongoDBService.
"""

from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Path, Response, status

from app.api.responses import (
    DATABASE_ERROR_RESPONSES,
    DATABASE_RESOURCE_ERROR_RESPONSES,
)
from app.api.v1.dependencies.pagination import PaginationDependency
from app.api.v1.dependencies.services import MongoDBServiceDependency
from app.schemas.analysis.analysis import (
    AnalysisRecord,
    AnalysisSummary,
)

# Routeur


router = APIRouter()


# Historique


@router.get(
    "",
    response_model=list[AnalysisSummary],
    status_code=status.HTTP_200_OK,
    summary="Consulter l'historique des analyses",
    description=(
        "Retourne les analyses enregistrées les plus récentes. "
        "Les résultats sont paginés à partir des paramètres limit "
        "et offset."
    ),
    response_description="Liste paginée des analyses enregistrées.",
    responses=DATABASE_ERROR_RESPONSES,
)
async def list_history(
    pagination: PaginationDependency,
    service: MongoDBServiceDependency,
) -> list[AnalysisSummary]:
    """Retourne les analyses enregistrées.

    Args:
        pagination: Paramètres de pagination validés.
        service: Service d'accès aux analyses enregistrées.

    Returns:
        Liste des analyses correspondant à la page demandée.
    """

    return await service.list_recent_analyses(
        limit=pagination.limit,
        offset=pagination.offset,
    )


# Lecture


@router.get(
    "/{analysis_id}",
    response_model=AnalysisRecord,
    status_code=status.HTTP_200_OK,
    summary="Consulter une analyse",
    description=(
        "Retourne le contenu complet d'une analyse enregistrée "
        "à partir de son identifiant unique."
    ),
    response_description="Analyse enregistrée.",
    responses=DATABASE_RESOURCE_ERROR_RESPONSES,
)
async def get_history(
    analysis_id: Annotated[
        str,
        Path(
            min_length=1,
            description="Identifiant unique de l'analyse.",
        ),
    ],
    service: MongoDBServiceDependency,
) -> AnalysisRecord:
    """Retourne une analyse enregistrée.

    Args:
        analysis_id: Identifiant de l'analyse recherchée.
        service: Service d'accès aux analyses enregistrées.

    Returns:
        Analyse correspondant à l'identifiant fourni.
    """

    return await service.get_required_analysis(analysis_id)


# Suppression


@router.delete(
    "/{analysis_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Supprimer une analyse",
    description=(
        "Supprime définitivement une analyse enregistrée à partir "
        "de son identifiant unique."
    ),
    response_description="Analyse supprimée.",
    responses=DATABASE_RESOURCE_ERROR_RESPONSES,
)
async def delete_history(
    analysis_id: Annotated[
        str,
        Path(
            min_length=1,
            description="Identifiant unique de l'analyse.",
        ),
    ],
    service: MongoDBServiceDependency,
) -> Response:
    """Supprime une analyse enregistrée.

    Args:
        analysis_id: Identifiant de l'analyse à supprimer.
        service: Service d'accès aux analyses enregistrées.

    Returns:
        Réponse HTTP vide confirmant la suppression.
    """

    await service.delete_required_analysis(analysis_id)

    return Response(status_code=status.HTTP_204_NO_CONTENT)
