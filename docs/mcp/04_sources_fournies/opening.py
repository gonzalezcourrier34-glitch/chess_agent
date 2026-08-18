"""Schémas représentant les ouvertures d'échecs.

Ce module regroupe les modèles décrivant une ouverture, ses variantes et
les statistiques associées.

Ces modèles sont utilisés par les services d'analyse, le moteur RAG,
MongoDB et les réponses de l'API.
"""

from __future__ import annotations

from app.schemas.enums import DifficultyLevel
from pydantic import BaseModel, ConfigDict, Field

# Ouverture

class Opening(BaseModel):
    """Représente une ouverture d'échecs."""

    model_config = ConfigDict(
        extra="forbid",
        frozen=True
    )

    eco: str = Field(
        ...,
        description="Code ECO de l'ouverture."
    )

    name: str = Field(
        ...,
        description="Nom de l'ouverture."
    )

    variation: str | None = Field(
        default=None,
        description="Nom de la variante."
    )

    family: str | None = Field(
        default=None,
        description="Famille de l'ouverture."
    )

    moves: list[str] = Field(
        default_factory=list,
        description="Suite principale de coups."
    )

    starting_fen: str | None = Field(
        default=None,
        description="Position de départ."
    )

    final_fen: str | None = Field(
        default=None,
        description="Position finale de la variante."
    )

    description: str | None = Field(
        default=None,
        description="Description de l'ouverture."
    )

    difficulty: DifficultyLevel = Field(
        default=DifficultyLevel.INTERMEDIATE,
        description="Niveau conseillé."
    )


# Variante

class OpeningVariation(BaseModel):
    """Décrit une variante d'ouverture."""

    model_config = ConfigDict(
        extra="forbid",
        frozen=True
    )

    name: str = Field(
        ...,
        description="Nom de la variante."
    )

    eco: str = Field(
        ...,
        description="Code ECO."
    )

    moves: list[str] = Field(
        default_factory=list,
        description="Suite des coups."
    )

    final_fen: str = Field(
        ...,
        description="Position atteinte."
    )

    description: str | None = Field(
        default=None,
        description="Présentation de la variante."
    )


# Statistiques

class OpeningStatistics(BaseModel):
    """Statistiques d'une ouverture."""

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
        ge=0,
        le=100,
        description="Victoires des Blancs."
    )

    black_win_rate: float = Field(
        default=0.0,
        ge=0,
        le=100,
        description="Victoires des Noirs."
    )

    draw_rate: float = Field(
        default=0.0,
        ge=0,
        le=100,
        description="Parties nulles."
    )

    average_rating: int | None = Field(
        default=None,
        ge=0,
        description="Classement Elo moyen."
    )


# Théorie

class OpeningTheory(BaseModel):
    """Contenu pédagogique d'une ouverture."""

    model_config = ConfigDict(
        extra="forbid"
    )

    overview: str = Field(
        ...,
        description="Présentation générale."
    )

    strategic_ideas: list[str] = Field(
        default_factory=list,
        description="Idées stratégiques."
    )

    tactical_patterns: list[str] = Field(
        default_factory=list,
        description="Motifs tactiques."
    )

    typical_plans_white: list[str] = Field(
        default_factory=list,
        description="Plans des Blancs."
    )

    typical_plans_black: list[str] = Field(
        default_factory=list,
        description="Plans des Noirs."
    )

    common_mistakes: list[str] = Field(
        default_factory=list,
        description="Erreurs fréquentes."
    )


# Résultat complet

class OpeningDetails(BaseModel):
    """Informations complètes d'une ouverture."""

    model_config = ConfigDict(
        extra="forbid"
    )

    opening: Opening

    statistics: OpeningStatistics | None = Field(
        default=None,
        description="Statistiques disponibles."
    )

    theory: OpeningTheory | None = Field(
        default=None,
        description="Informations théoriques."
    )

    variations: list[OpeningVariation] = Field(
        default_factory=list,
        description="Variantes connues."
    )