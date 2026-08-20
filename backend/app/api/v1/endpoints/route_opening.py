"""Routes d'accès aux données d'ouverture Lichess.

Ce module expose les endpoints permettant de détecter une ouverture
associée à une position d'échecs.

Il ne contient aucune logique métier.

La détection de l'ouverture, la récupération des statistiques et la
normalisation des réponses principales sont déléguées au
LichessService.
"""

from __future__ import annotations

from fastapi import APIRouter, status

from app.api.responses import LICHESS_ERROR_RESPONSES
from app.api.v1.dependencies.services import LichessServiceDependency
from app.schemas.chess.opening import OpeningDetails
from app.schemas.chess.position import FenRequest

# Routeur


router = APIRouter()


# Ouverture


@router.post(
    "",
    response_model=OpeningDetails,
    status_code=status.HTTP_200_OK,
    summary="Détecter une ouverture",
    description=(
        "Détecte l'ouverture correspondant à une position FEN et "
        "retourne les informations disponibles dans Lichess, notamment "
        "le nom, le code ECO, les statistiques globales et les réponses "
        "principales jouées depuis la position."
    ),
    response_description=("Informations disponibles sur l'ouverture détectée."),
    responses=LICHESS_ERROR_RESPONSES,
)
async def detect_opening(
    payload: FenRequest,
    service: LichessServiceDependency,
) -> OpeningDetails:
    """Détecte une ouverture depuis une position FEN.

    Args:
        payload: Position FEN à analyser.
        service: Service d'accès aux données Lichess.

    Returns:
        Ouverture détectée, statistiques globales et réponses
        principales disponibles.
    """

    return await service.detect_opening(payload)
