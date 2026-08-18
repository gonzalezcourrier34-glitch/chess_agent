"""Schémas représentant les évaluations d'une position.

Ce module regroupe les modèles utilisés pour représenter les analyses
produites par Stockfish ainsi que les évaluations enrichies générées par
l'agent IA.

Les modèles sont indépendants du moteur UCI et servent également aux
réponses FastAPI.
"""

from __future__ import annotations

from app.schemas.enums import EvaluationType
from app.schemas.move import BestMove
from pydantic import BaseModel, ConfigDict, Field

# Evaluation

class Evaluation(BaseModel):
    """Évaluation d'une position."""

    model_config = ConfigDict(
        extra="forbid",
        frozen=True
    )

    score: float = Field(
        ...,
        description="Score retourné par le moteur."
    )

    evaluation_type: EvaluationType = Field(
        ...,
        description="Nature du score."
    )

    depth: int = Field(
        ...,
        ge=1,
        description="Profondeur atteinte."
    )

    nodes: int | None = Field(
        default=None,
        ge=0,
        description="Nombre de nœuds explorés."
    )

    time_ms: int | None = Field(
        default=None,
        ge=0,
        description="Temps d'analyse."
    )


# Ligne principale

class PrincipalVariation(BaseModel):
    """Variante principale calculée par le moteur."""

    model_config = ConfigDict(
        extra="forbid"
    )

    moves: list[str] = Field(
        default_factory=list,
        description="Suite de coups en notation UCI."
    )

    evaluation: Evaluation

    explanation: str | None = Field(
        default=None,
        description="Résumé généré par le LLM."
    )


# Analyse moteur

class EngineAnalysis(BaseModel):
    """Analyse complète d'une position."""

    model_config = ConfigDict(
        extra="forbid"
    )

    best_move: BestMove

    evaluation: Evaluation

    principal_variation: PrincipalVariation

    alternatives: list[BestMove] = Field(
        default_factory=list,
        description="Autres coups recommandés."
    )


# Analyse enrichie

class PositionEvaluation(BaseModel):
    """Évaluation enrichie destinée au frontend."""

    model_config = ConfigDict(
        extra="forbid"
    )

    engine: EngineAnalysis

    positional_themes: list[str] = Field(
        default_factory=list,
        description="Thèmes positionnels."
    )

    tactical_themes: list[str] = Field(
        default_factory=list,
        description="Motifs tactiques."
    )

    strengths: list[str] = Field(
        default_factory=list,
        description="Points forts."
    )

    weaknesses: list[str] = Field(
        default_factory=list,
        description="Faiblesses."
    )

    recommendations: list[str] = Field(
        default_factory=list,
        description="Conseils de jeu."
    )

    summary: str | None = Field(
        default=None,
        description="Résumé produit par le LLM."
    )