"""Schémas d'analyse du backend Chess Agent.

Ce module définit les modèles utilisés par l'API pour :

- recevoir une demande d'analyse ;
- retourner le résultat complet d'une analyse.

Les modèles métier (ouvertures, coups, évaluations, vidéos,
documents...) sont définis dans leurs modules spécialisés.
"""

from __future__ import annotations

from typing import Literal

from app.schemas.document import Document
from app.schemas.evaluation import PositionEvaluation
from app.schemas.move import BestMove
from app.schemas.opening import OpeningDetails
from app.schemas.video import Video
from pydantic import BaseModel, Field

# Types

AnalysisMode = Literal[
    "theory",
    "engine"
]

AnalysisStatus = Literal[
    "success",
    "error"
]


# Requête

class AnalysisRequest(BaseModel):
    """Requête d'analyse d'une position."""

    fen: str = Field(
        ...,
        description="Position au format FEN."
    )


# Réponse

class AnalysisResponse(BaseModel):
    """Résultat complet d'une analyse."""

    status: AnalysisStatus

    mode: AnalysisMode | None = None

    fen: str

    opening: OpeningDetails | None = None

    evaluation: PositionEvaluation | None = None

    best_moves: list[BestMove] = Field(
        default_factory=list,
        description="Meilleurs coups proposés."
    )

    documents: list[Document] = Field(
        default_factory=list,
        description="Documents retrouvés."
    )

    videos: list[Video] = Field(
        default_factory=list,
        description="Vidéos recommandées."
    )

    explanation: str | None = Field(
        default=None,
        description="Explication générée par le LLM."
    )

    error: str | None = Field(
        default=None,
        description="Message d'erreur éventuel."
    )