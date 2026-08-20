"""Schémas représentant les évaluations d'une position.

Ce module regroupe les modèles utilisés pour représenter les analyses
produites par Stockfish ainsi que les évaluations enrichies générées par
l'agent IA.

Les modèles sont indépendants du moteur UCI et servent également aux
réponses FastAPI.
"""

from __future__ import annotations

from pydantic import BaseModel, ConfigDict, Field

from app.schemas.chess.move import BestMove
from app.schemas.common.enums import EvaluationType

# Évaluation


class Evaluation(BaseModel):
    """Évaluation d'une position."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    # Informations directement retournées par Stockfish.
    score: float

    evaluation_type: EvaluationType

    depth: int = Field(..., ge=1)

    nodes: int | None = Field(default=None, ge=0)

    time_ms: int | None = Field(default=None, ge=0)


# Ligne principale


class PrincipalVariation(BaseModel):
    """Variante principale calculée par le moteur."""

    model_config = ConfigDict(extra="forbid")

    # Cette variante correspond à la meilleure suite de coups
    # trouvée par le moteur lors de l'analyse.
    moves: list[str] = Field(default_factory=list)

    evaluation: Evaluation

    explanation: str | None = None


# Analyse moteur


class EngineAnalysis(BaseModel):
    """Analyse complète d'une position."""

    model_config = ConfigDict(extra="forbid")

    # Ce modèle rassemble les principaux résultats produits
    # par Stockfish pour une position donnée.
    best_move: BestMove

    evaluation: Evaluation

    principal_variation: PrincipalVariation

    alternatives: list[BestMove] = Field(default_factory=list)


# Analyse enrichie


class PositionEvaluation(BaseModel):
    """Évaluation enrichie destinée au frontend."""

    model_config = ConfigDict(extra="forbid")

    # L'analyse du moteur est enrichie par l'agent IA afin de
    # produire une explication plus pédagogique.
    engine: EngineAnalysis

    positional_themes: list[str] = Field(default_factory=list)

    tactical_themes: list[str] = Field(default_factory=list)

    strengths: list[str] = Field(default_factory=list)

    weaknesses: list[str] = Field(default_factory=list)

    recommendations: list[str] = Field(default_factory=list)

    summary: str | None = None
