"""Routes de recherche vectorielle.

Ce module expose les endpoints permettant de rechercher des documents
dans la base vectorielle Milvus.

Il ne contient aucune logique métier.

La génération de l'embedding de la requête, l'interrogation de Milvus,
le classement des résultats et la construction de la réponse sont
délégués au VectorSearchService.

La route publique /vector réalise une recherche sémantique depuis une
requête textuelle.

Les recherches structurelles spécifiques au corpus Wikichess, notamment
la recherche par séquence de coups, restent utilisées en interne par le
workflow et ne sont pas exposées par cette route.
"""

from __future__ import annotations

from fastapi import APIRouter, status

from app.api.responses import VECTOR_SEARCH_ERROR_RESPONSES
from app.api.v1.dependencies.services import VectorSearchServiceDependency
from app.schemas.analysis.search import (
    VectorSearchRequest,
    VectorSearchResponse,
)

# Routeur


router = APIRouter()


# Recherche vectorielle


@router.post(
    "/vector",
    response_model=VectorSearchResponse,
    status_code=status.HTTP_200_OK,
    summary="Rechercher des documents",
    description=(
        "Recherche les documents les plus proches d'une requête "
        "textuelle dans la base vectorielle Milvus. "
        "La requête est convertie en embedding puis comparée "
        "aux documents indexés."
    ),
    response_description="Documents classés par similarité.",
    responses=VECTOR_SEARCH_ERROR_RESPONSES,
)
async def search_documents(
    payload: VectorSearchRequest,
    service: VectorSearchServiceDependency,
) -> VectorSearchResponse:
    """Recherche des documents par similarité vectorielle.

    Args:
        payload: Requête textuelle et paramètres de recherche.
        service: Service de recherche vectorielle.

    Returns:
        Résultats documentaires classés par similarité.
    """

    return await service.search(
        payload
    )