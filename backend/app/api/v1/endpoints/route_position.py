"""Routes de gestion des positions d'échecs.

Ce module expose les endpoints techniques permettant de :

- valider une position au format FEN ;
- obtenir sa représentation structurée ;
- récupérer les coups légaux disponibles ;
- lancer directement une évaluation Stockfish.

Il ne contient aucune logique métier.

La validation et la manipulation des positions sont déléguées au
ChessService.

L'analyse technique est déléguée au StockfishService.

La route d'évaluation moteur constitue un point d'accès interne destiné
aux tests, au diagnostic et aux outils techniques. Elle reste exclue de
la documentation OpenAPI publique, car l'analyse complète doit passer
par le workflow de l'agent.
"""

from __future__ import annotations

from fastapi import APIRouter, status

from app.api.responses import CHESS_ERROR_RESPONSES
from app.api.v1.dependencies.services import (
    ChessServiceDependency,
    StockfishServiceDependency,
)
from app.schemas.analysis.evaluation import PositionEvaluation
from app.schemas.chess.move import LegalMove
from app.schemas.chess.position import BoardPosition, FenRequest

# Routeur


router = APIRouter()


# Validation


@router.post(
    "/validate",
    response_model=BoardPosition,
    status_code=status.HTTP_200_OK,
    summary="Valider une position FEN",
    description=(
        "Vérifie qu'une position FEN est valide puis retourne sa "
        "représentation structurée, notamment le joueur ayant le trait, "
        "les droits de roque et l'état de la partie."
    ),
    response_description="Position validée et structurée.",
    responses=CHESS_ERROR_RESPONSES,
)
async def validate_position(
    payload: FenRequest,
    service: ChessServiceDependency,
) -> BoardPosition:
    """Valide et structure une position d'échecs.

    Args:
        payload: Position FEN à valider.
        service: Service de manipulation des positions.

    Returns:
        Représentation structurée de la position.
    """

    return service.get_position(
        payload
    )


# Coups légaux


@router.post(
    "/legal-moves",
    response_model=list[LegalMove],
    status_code=status.HTTP_200_OK,
    summary="Lister les coups légaux",
    description=(
        "Valide la position FEN puis retourne tous les coups légaux "
        "disponibles pour le joueur ayant le trait."
    ),
    response_description="Liste des coups légaux disponibles.",
    responses=CHESS_ERROR_RESPONSES,
)
async def get_legal_moves(
    payload: FenRequest,
    service: ChessServiceDependency,
) -> list[LegalMove]:
    """Retourne les coups légaux d'une position.

    Args:
        payload: Position FEN utilisée pour calculer les coups.
        service: Service de manipulation des positions.

    Returns:
        Liste structurée des coups légaux disponibles.
    """

    return service.get_legal_moves(
        payload
    )


# Évaluation interne


@router.post(
    "/evaluate",
    response_model=PositionEvaluation,
    status_code=status.HTTP_200_OK,
    summary="Évaluer techniquement une position",
    description=(
        "Lance une analyse directe de la position avec Stockfish. "
        "Cette route est réservée aux tests et aux outils internes."
    ),
    response_description="Évaluation technique de la position.",
    include_in_schema=False,
)
async def evaluate_position(
    payload: FenRequest,
    service: StockfishServiceDependency,
) -> PositionEvaluation:
    """Évalue directement une position avec Stockfish.

    Cette route contourne volontairement le workflow LangGraph. Elle ne
    produit donc pas nécessairement les enrichissements documentaires,
    théoriques, vidéo ou génératifs disponibles dans l'analyse complète.

    Args:
        payload: Position FEN à analyser.
        service: Service d'analyse Stockfish.

    Returns:
        Évaluation technique produite par le moteur.
    """

    return await service.analyze_position(
        payload
    )