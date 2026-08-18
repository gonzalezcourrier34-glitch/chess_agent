"""Schémas représentant une position d'échecs.

Ce module centralise les modèles décrivant l'état d'une position
d'échecs.

Les modèles restent indépendants de python-chess afin de faciliter les
échanges entre FastAPI, LangGraph, les services et le frontend Angular.
"""

from __future__ import annotations

from pydantic import BaseModel, ConfigDict, Field

from app.schemas.enums import ChessColor
from app.schemas.move import (
    LegalMove,
    PlayedMove
)


# Requête

class FenRequest(BaseModel):
    """Requête contenant une position FEN."""

    model_config = ConfigDict(
        extra="forbid",
        frozen=True,
        str_strip_whitespace=True
    )

    fen: str = Field(
        ...,
        min_length=10,
        description="Position au format FEN."
    )


# Position

class BoardPosition(BaseModel):
    """Représente l'état courant d'un échiquier."""

    model_config = ConfigDict(
        extra="forbid",
        frozen=True
    )

    fen: str = Field(
        ...,
        description="Position complète au format FEN."
    )

    active_color: ChessColor = Field(
        ...,
        description="Couleur du joueur ayant le trait."
    )

    fullmove_number: int = Field(
        ...,
        ge=1,
        description="Numéro du coup."
    )

    halfmove_clock: int = Field(
        ...,
        ge=0,
        description="Compteur des demi-coups."
    )

    castling_rights: str = Field(
        default="-",
        description="Droits de roque."
    )

    en_passant_square: str | None = Field(
        default=None,
        description="Case de prise en passant."
    )

    is_check: bool = Field(
        default=False,
        description="Le roi est en échec."
    )

    is_checkmate: bool = Field(
        default=False,
        description="La partie est terminée par échec et mat."
    )

    is_stalemate: bool = Field(
        default=False,
        description="La partie est terminée par pat."
    )

    is_game_over: bool = Field(
        default=False,
        description="La partie est terminée."
    )


# Contexte

class PositionContext(BaseModel):
    """Contexte complet d'une position analysée."""

    model_config = ConfigDict(
        extra="forbid"
    )

    board: BoardPosition = Field(
        ...,
        description="Position analysée."
    )

    legal_moves: list[LegalMove] = Field(
        default_factory=list,
        description="Coups légaux disponibles."
    )

    last_move: PlayedMove | None = Field(
        default=None,
        description="Dernier coup joué."
    )

    is_draw: bool = Field(
        default=False,
        description="La position est une nulle."
    )