"""Schémas représentant les coups d'échecs.

Ce module centralise les modèles décrivant les différents types de coups
manipulés par le projet.

Les modèles sont utilisés par FastAPI, LangGraph, Stockfish, Lichess et
le frontend Angular.
"""

from __future__ import annotations

from pydantic import BaseModel, ConfigDict, Field

from app.schemas.enums import EvaluationType


# Coup

class Move(BaseModel):
    """Représente un coup d'échecs."""

    model_config = ConfigDict(
        extra="forbid",
        frozen=True
    )

    uci: str = Field(
        ...,
        min_length=4,
        max_length=5,
        description="Notation UCI."
    )

    san: str = Field(
        ...,
        description="Notation SAN."
    )

    from_square: str = Field(
        ...,
        min_length=2,
        max_length=2,
        description="Case de départ."
    )

    to_square: str = Field(
        ...,
        min_length=2,
        max_length=2,
        description="Case d'arrivée."
    )


# Coup légal

class LegalMove(Move):
    """Coup légal disponible."""

    is_capture: bool = Field(
        default=False,
        description="Indique si le coup capture une pièce."
    )

    is_check: bool = Field(
        default=False,
        description="Indique si le coup met le roi en échec."
    )

    is_checkmate: bool = Field(
        default=False,
        description="Indique si le coup termine la partie."
    )

    is_castling: bool = Field(
        default=False,
        description="Indique un roque."
    )

    is_promotion: bool = Field(
        default=False,
        description="Indique une promotion."
    )

    promotion_piece: str | None = Field(
        default=None,
        description="Pièce de promotion."
    )


# Coup joué

class PlayedMove(Move):
    """Coup effectivement joué."""

    before_fen: str = Field(
        ...,
        description="Position avant le coup."
    )

    after_fen: str = Field(
        ...,
        description="Position après le coup."
    )

    move_number: int = Field(
        ...,
        ge=1,
        description="Numéro du coup."
    )


# Coup recommandé

class BestMove(Move):
    """Meilleur coup proposé par le moteur."""

    score: float = Field(
        ...,
        description="Score retourné par le moteur."
    )

    evaluation_type: EvaluationType = Field(
        ...,
        description="Type d'évaluation."
    )

    depth: int = Field(
        ...,
        ge=1,
        description="Profondeur d'analyse."
    )

    principal_variation: list[str] = Field(
        default_factory=list,
        description="Suite de coups principale."
    )


# Recommandation

class MoveSuggestion(BaseModel):
    """Recommandation d'un coup."""

    model_config = ConfigDict(
        extra="forbid"
    )

    move: BestMove

    explanation: str = Field(
        ...,
        description="Explication générée par le LLM."
    )

    advantages: list[str] = Field(
        default_factory=list,
        description="Points positifs."
    )

    risks: list[str] = Field(
        default_factory=list,
        description="Risques éventuels."
    )


# Statistiques

class MoveStatistics(BaseModel):
    """Statistiques associées à un coup."""

    model_config = ConfigDict(
        extra="forbid",
        frozen=True
    )

    games: int = Field(
        default=0,
        ge=0,
        description="Nombre de parties."
    )

    white_win_rate: float = Field(
        default=0.0,
        ge=0.0,
        le=100.0,
        description="Pourcentage de victoires des Blancs."
    )

    black_win_rate: float = Field(
        default=0.0,
        ge=0.0,
        le=100.0,
        description="Pourcentage de victoires des Noirs."
    )

    draw_rate: float = Field(
        default=0.0,
        ge=0.0,
        le=100.0,
        description="Pourcentage de nulles."
    )

    average_rating: int | None = Field(
        default=None,
        ge=0,
        description="Classement Elo moyen."
    )