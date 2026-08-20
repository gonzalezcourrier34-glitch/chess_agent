"""Routes d'évaluation moteur.

Ce module expose les endpoints permettant d'évaluer une position
directement avec Stockfish.

Il ne contient aucune logique métier.

L'analyse est entièrement déléguée au StockfishService.

Ces routes permettent d'obtenir une évaluation technique indépendante
du workflow LangGraph. Elles sont principalement destinées aux outils,
aux tests et aux diagnostics.
"""

from __future__ import annotations

from fastapi import APIRouter, status

from app.api.responses import STOCKFISH_ERROR_RESPONSES
from app.api.v1.dependencies.services import StockfishServiceDependency
from app.schemas.analysis.evaluation import PositionEvaluation
from app.schemas.chess.position import FenRequest

# Routeur


router = APIRouter()


# Évaluation


@router.post(
    "/evaluate",
    response_model=PositionEvaluation,
    status_code=status.HTTP_200_OK,
    summary="Évaluer une position",
    description=(
        "Analyse une position FEN avec Stockfish et retourne "
        "l'évaluation complète du moteur, comprenant le score, "
        "la profondeur atteinte, la variante principale et les "
        "meilleurs coups proposés."
    ),
    response_description="Évaluation technique de la position.",
    responses=STOCKFISH_ERROR_RESPONSES,
)
async def evaluate_position(
    payload: FenRequest, service: StockfishServiceDependency
) -> PositionEvaluation:
    """Évalue une position avec Stockfish.

    Cette route exécute uniquement le moteur d'analyse. Elle ne réalise
    ni détection d'ouverture, ni recherche documentaire, ni génération
    d'explication par l'agent.

    Args:
        payload: Position FEN à analyser.
        service: Service d'analyse Stockfish.

    Returns:
        Évaluation technique produite par le moteur.
    """

    return await service.analyze_position(payload)
