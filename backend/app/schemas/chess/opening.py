"""Schémas représentant les ouvertures d'échecs.

Ce module regroupe les modèles décrivant :

- une ouverture ;
- ses variantes ;
- ses statistiques globales ;
- les coups statistiques retournés par Lichess ;
- son contenu pédagogique.

Ces modèles sont utilisés par les services d'analyse, le moteur RAG,
MongoDB, LangGraph et les réponses de l'API.
"""

from __future__ import annotations

from pydantic import BaseModel, ConfigDict, Field

from app.schemas.common.enums import DifficultyLevel

# Ouverture


class Opening(BaseModel):
    """Représente une ouverture."""

    model_config = ConfigDict(
        extra="forbid",
        frozen=True
    )

    # Informations générales permettant d'identifier une ouverture.
    eco: str
    name: str

    variation: str | None = None
    family: str | None = None

    # Suite principale de coups menant à cette ouverture.
    moves: list[str] = Field(
        default_factory=list
    )

    # Positions de début et de fin de la variante lorsqu'elles sont
    # disponibles.
    starting_fen: str | None = None
    final_fen: str | None = None

    # Informations complémentaires destinées à l'utilisateur.
    description: str | None = None

    difficulty: DifficultyLevel = (
        DifficultyLevel.INTERMEDIATE
    )


# Variante


class OpeningVariation(BaseModel):
    """Représente une variante complète d'ouverture."""

    model_config = ConfigDict(
        extra="forbid",
        frozen=True
    )

    # Une variante possède son propre nom, son code ECO et la suite
    # de coups permettant de l'atteindre.
    name: str
    eco: str

    moves: list[str] = Field(
        default_factory=list
    )

    final_fen: str

    description: str | None = None


# Statistiques globales


class OpeningStatistics(BaseModel):
    """Statistiques globales d'une ouverture ou d'une position."""

    model_config = ConfigDict(
        extra="forbid",
        frozen=True
    )

    # Ces données proviennent d'une base de parties lorsqu'elles sont
    # disponibles.
    games: int = Field(
        default=0,
        ge=0
    )

    white_win_rate: float = Field(
        default=0.0,
        ge=0.0,
        le=100.0
    )

    black_win_rate: float = Field(
        default=0.0,
        ge=0.0,
        le=100.0
    )

    draw_rate: float = Field(
        default=0.0,
        ge=0.0,
        le=100.0
    )

    average_rating: int | None = Field(
        default=None,
        ge=0
    )


# Réponse Lichess


class OpeningMoveStatistics(BaseModel):
    """Statistiques d'un coup retourné par Lichess."""

    model_config = ConfigDict(
        extra="forbid",
        frozen=True
    )

    # Le coup est conservé dans les deux notations retournées par
    # Lichess afin d'être exploitable par le backend et le frontend.
    uci: str = Field(
        ...,
        min_length=4,
        max_length=5
    )

    san: str = Field(
        ...,
        min_length=1
    )

    # Nombre total de parties ayant suivi ce coup.
    games: int = Field(
        default=0,
        ge=0
    )

    white_win_rate: float = Field(
        default=0.0,
        ge=0.0,
        le=100.0
    )

    black_win_rate: float = Field(
        default=0.0,
        ge=0.0,
        le=100.0
    )

    draw_rate: float = Field(
        default=0.0,
        ge=0.0,
        le=100.0
    )

    average_rating: int | None = Field(
        default=None,
        ge=0
    )


# Théorie


class OpeningTheory(BaseModel):
    """Représente le contenu pédagogique d'une ouverture."""

    model_config = ConfigDict(
        extra="forbid"
    )

    # Cette partie rassemble les connaissances utiles pour comprendre
    # et apprendre l'ouverture.
    overview: str

    strategic_ideas: list[str] = Field(
        default_factory=list
    )

    tactical_patterns: list[str] = Field(
        default_factory=list
    )

    typical_plans_white: list[str] = Field(
        default_factory=list
    )

    typical_plans_black: list[str] = Field(
        default_factory=list
    )

    common_mistakes: list[str] = Field(
        default_factory=list
    )


# Résultat


class OpeningDetails(BaseModel):
    """Regroupe les informations disponibles sur une ouverture."""

    model_config = ConfigDict(
        extra="forbid"
    )

    opening: Opening

    statistics: OpeningStatistics | None = None

    # Les réponses correspondent aux coups disponibles depuis la
    # position analysée et à leurs statistiques Lichess.
    responses: list[OpeningMoveStatistics] = Field(
        default_factory=list
    )

    theory: OpeningTheory | None = None

    variations: list[OpeningVariation] = Field(
        default_factory=list
    )