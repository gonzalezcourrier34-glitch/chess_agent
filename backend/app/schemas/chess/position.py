"""Schémas représentant une position d'échecs.

Ce module centralise les modèles décrivant l'état d'une position
d'échecs.

Les modèles restent indépendants de python-chess afin de faciliter les
échanges entre FastAPI, LangGraph, les services et le frontend Angular.
"""

from __future__ import annotations

from pydantic import BaseModel, ConfigDict, Field

from app.schemas.chess.move import LegalMove, PlayedMove
from app.schemas.common.enums import ChessColor

# Requête

class FenRequest(BaseModel):
    """Requête contenant une position FEN."""

    model_config = ConfigDict(
        extra="forbid",
        frozen=True,
        str_strip_whitespace=True
    )

    # Le FEN est le point d'entrée principal de l'analyse.
    # Une longueur minimale permet d'écarter les valeurs
    # manifestement invalides avant d'appeler les services.
    fen: str = Field(
        ...,
        min_length=10
    )


# Position

class BoardPosition(BaseModel):
    """État d'un échiquier."""

    model_config = ConfigDict(
        extra="forbid",
        frozen=True
    )

    # Position complète au format FEN.
    # Elle constitue la source de vérité de l'échiquier.
    fen: str

    # Joueur ayant le trait.
    active_color: ChessColor

    # Informations extraites du FEN pour éviter au frontend
    # et aux autres composants de devoir le parser.
    fullmove_number: int = Field(
        ...,
        ge=1
    )

    halfmove_clock: int = Field(
        ...,
        ge=0
    )

    castling_rights: str = "-"

    en_passant_square: str | None = None

    # État actuel de la partie.
    # Ces indicateurs simplifient l'affichage et les décisions
    # prises par les différents services.
    is_check: bool = False

    is_checkmate: bool = False

    is_stalemate: bool = False

    is_game_over: bool = False


# Contexte

class PositionContext(BaseModel):
    """Contexte d'une position analysée."""

    model_config = ConfigDict(
        extra="forbid"
    )

    # Position complète analysée.
    board: BoardPosition

    # Liste des coups légaux calculés à partir de la position.
    legal_moves: list[LegalMove] = Field(
        default_factory=list
    )

    # Dernier coup joué lorsqu'il est connu.
    last_move: PlayedMove | None = None

    # Indique si la position est considérée comme une nulle.
    is_draw: bool = False