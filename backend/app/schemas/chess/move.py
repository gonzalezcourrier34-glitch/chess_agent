"""Schémas représentant les coups d'échecs.

Ce module centralise les modèles décrivant les différents types de coups
manipulés par le projet.

Les modèles sont utilisés par FastAPI, LangGraph, Stockfish, Lichess et
le frontend Angular.
"""

from __future__ import annotations

from pydantic import BaseModel, ConfigDict, Field

from app.schemas.common.enums import EvaluationType

# Coup


class Move(BaseModel):
    """Représente un coup d'échecs."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    # Informations communes à tous les coups manipulés
    # par l'application.
    uci: str = Field(..., min_length=4, max_length=5)

    san: str

    from_square: str = Field(..., min_length=2, max_length=2)

    to_square: str = Field(..., min_length=2, max_length=2)


# Coup légal


class LegalMove(Move):
    """Coup légal."""

    # Ces indicateurs décrivent les propriétés du coup afin
    # de faciliter les analyses et l'affichage.
    is_capture: bool = False
    is_check: bool = False
    is_checkmate: bool = False
    is_castling: bool = False
    is_promotion: bool = False

    promotion_piece: str | None = None


# Coup joué


class PlayedMove(Move):
    """Coup joué."""

    # Conservation de la position avant et après le coup
    # pour faciliter les analyses et la navigation.
    before_fen: str

    after_fen: str

    move_number: int = Field(..., ge=1)


# Coup recommandé


class BestMove(Move):
    """Meilleur coup proposé."""

    # Informations issues du moteur d'analyse.
    score: float

    evaluation_type: EvaluationType

    depth: int = Field(..., ge=1)

    principal_variation: list[str] = Field(default_factory=list)


# Recommandation


class MoveSuggestion(BaseModel):
    """Recommandation d'un coup."""

    model_config = ConfigDict(extra="forbid")

    # Ce modèle regroupe le meilleur coup proposé
    # ainsi que son explication pédagogique.
    move: BestMove

    explanation: str

    advantages: list[str] = Field(default_factory=list)

    risks: list[str] = Field(default_factory=list)


# Statistiques


class MoveStatistics(BaseModel):
    """Statistiques d'un coup."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    # Ces statistiques proviennent d'une base de parties
    # lorsqu'elles sont disponibles.
    games: int = Field(default=0, ge=0)

    white_win_rate: float = Field(default=0.0, ge=0, le=100)

    black_win_rate: float = Field(default=0.0, ge=0, le=100)

    draw_rate: float = Field(default=0.0, ge=0, le=100)

    average_rating: int | None = Field(default=None, ge=0)
