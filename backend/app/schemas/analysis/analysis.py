"""Schémas d'analyse du backend Chess Agent.

Ce module centralise les modèles utilisés pour :

- recevoir une demande d'analyse ;
- transporter l'historique réel des coups joués ;
- retourner le résultat complet d'une analyse ;
- enregistrer une analyse dans MongoDB ;
- représenter le résultat d'une sauvegarde ;
- afficher un résumé dans l'historique des analyses.

Les modèles métier spécialisés restent définis dans leurs modules
respectifs :

- ouvertures ;
- positions ;
- évaluations ;
- documents ;
- vidéos.

L'historique des coups constitue une donnée explicite de la requête.

Il ne doit jamais être reconstruit depuis :

- le FEN ;
- le nom d'une ouverture ;
- un code ECO.

Les données internes du workflow qui ne possèdent pas de contrat métier
stable sont conservées sous forme de snapshots JSON.
"""

from __future__ import annotations

from datetime import datetime
from typing import Any

from pydantic import BaseModel, ConfigDict, Field, field_validator

from app.schemas.analysis.evaluation import PositionEvaluation
from app.schemas.chess.opening import OpeningDetails
from app.schemas.chess.position import BoardPosition
from app.schemas.common.enums import AnalysisStatus, WorkflowStep
from app.schemas.common.error import WorkflowError, WorkflowWarning
from app.schemas.media.video import Video
from app.schemas.rag.document import Document, RetrievalContext

# Types

JsonObject = dict[str, Any]

# Requête

class AnalysisRequest(BaseModel):
    """Requête d'analyse d'une position."""

    model_config = ConfigDict(
        extra="forbid",
        str_strip_whitespace=True
    )

    # Position

    fen: str = Field(
        ...,
        min_length=10,
        description="Position à analyser au format FEN."
    )

    # Historique

    moves: list[str] = Field(
        default_factory=list,
        description="Historique des coups au format UCI."
    )

    # Demande utilisateur

    question: str | None = Field(
        default=None,
        description="Question facultative posée par l'utilisateur."
    )

    response_language: str = Field(
        default="fr",
        min_length=2,
        max_length=10,
        description="Langue souhaitée pour la réponse."
    )

    # Validation

    @field_validator(
        "moves"
    )
    @classmethod
    def validate_moves(
        cls,
        moves: list[str]
    ) -> list[str]:
        """Valide et normalise l'historique des coups."""

        normalized_moves: list[str] = []

        for index, move in enumerate(
            moves
        ):
            if not isinstance(
                move,
                str
            ):
                raise ValueError(
                    f"Le coup situé à l'index {index} "
                    "doit être une chaîne."
                )

            normalized_move = move.strip()

            if not normalized_move:
                raise ValueError(
                    f"Le coup situé à l'index {index} "
                    "ne peut pas être vide."
                )

            normalized_moves.append(
                normalized_move
            )

        return normalized_moves


# Réponse

class AnalysisResponse(BaseModel):
    """Résultat complet d'une analyse."""

    model_config = ConfigDict(
        extra="forbid"
    )

    # Informations générales

    status: AnalysisStatus

    fen: str

    # Résultats métier

    opening: OpeningDetails | None = None

    evaluation: PositionEvaluation | None = None

    documents: list[Document] = Field(
        default_factory=list,
        description="Documents pédagogiques sélectionnés par le RAG."
    )

    videos: list[Video] = Field(
        default_factory=list,
        description="Vidéos pédagogiques sélectionnées."
    )

    # Réponse

    explanation: str | None = Field(
        default=None,
        description="Réponse pédagogique générée."
    )

    analysis_id: str | None = Field(
        default=None,
        description="Identifiant de l'analyse persistée."
    )

    error: str | None = Field(
        default=None,
        description=(
            "Dernier message d'erreur produit par le workflow "
            "lorsqu'une analyse échoue ou se termine partiellement."
        )
    )

# Persistance

class AnalysisRecord(BaseModel):
    """Analyse complète persistée dans MongoDB."""

    model_config = ConfigDict(
        extra="forbid",
        frozen=True
    )

    # Identifiants

    id: str = Field(
        ...,
        min_length=1,
        description="Identifiant unique de l'analyse."
    )

    request_id: str = Field(
        ...,
        min_length=1,
        description="Identifiant de la requête d'origine."
    )

    document_version: int = Field(
        default=1,
        ge=1,
        description="Version du format du document MongoDB."
    )

    # Requête

    fen: str = Field(
        ...,
        min_length=10,
        description="Position analysée au format FEN."
    )

    moves: list[str] = Field(
        default_factory=list,
        description=(
            "Historique réel des coups ayant conduit "
            "à la position analysée."
        )
    )

    question: str | None = Field(
        default=None,
        description="Question formulée par l'utilisateur."
    )

    response_language: str = Field(
        default="fr",
        min_length=2,
        max_length=10,
        description="Langue utilisée pour la réponse."
    )

    # Résultats métier

    status: AnalysisStatus = Field(
        ...,
        description="Statut de l'analyse au moment de la sauvegarde."
    )

    position: BoardPosition | None = Field(
        default=None,
        description="Position structurée validée."
    )

    opening: OpeningDetails | None = Field(
        default=None,
        description="Ouverture éventuellement détectée."
    )

    evaluation: PositionEvaluation | None = Field(
        default=None,
        description="Évaluation produite par Stockfish."
    )

    retrieval_context: RetrievalContext | None = Field(
        default=None,
        description=(
            "Contexte documentaire complet récupéré "
            "par le moteur RAG."
        )
    )

    videos: list[Video] = Field(
        default_factory=list,
        description="Vidéos pédagogiques sélectionnées."
    )

    response: str | None = Field(
        default=None,
        description="Réponse finale produite par le workflow."
    )

    # Snapshots internes

    options: JsonObject = Field(
        default_factory=dict,
        description="Snapshot des options d'analyse."
    )

    engine_analysis: JsonObject | None = Field(
        default=None,
        description="Snapshot détaillé du résultat Stockfish."
    )

    workflow_context: JsonObject = Field(
        default_factory=dict,
        description="Snapshot du contexte consolidé du workflow."
    )

    metadata: JsonObject = Field(
        default_factory=dict,
        description="Métadonnées techniques de l'exécution."
    )

    # Suivi du workflow

    current_step: WorkflowStep = Field(
        ...,
        description="Dernière étape exécutée."
    )

    completed_steps: list[WorkflowStep] = Field(
        default_factory=list,
        description="Étapes terminées du workflow."
    )

    warnings: list[WorkflowWarning] = Field(
        default_factory=list,
        description="Avertissements produits pendant l'analyse."
    )

    errors: list[WorkflowError] = Field(
        default_factory=list,
        description="Erreurs produites pendant l'analyse."
    )

    # Dates

    created_at: datetime = Field(
        ...,
        description="Date de création initiale de l'analyse."
    )

    saved_at: datetime = Field(
        ...,
        description="Date de la dernière sauvegarde."
    )


# Résultat de sauvegarde

class AnalysisSaveResult(BaseModel):
    """Résultat retourné après une sauvegarde MongoDB."""

    model_config = ConfigDict(
        extra="forbid",
        frozen=True
    )

    analysis_id: str = Field(
        ...,
        min_length=1,
        description="Identifiant de l'analyse sauvegardée."
    )

    request_id: str = Field(
        ...,
        min_length=1,
        description="Identifiant de la requête associée."
    )

    saved_at: datetime = Field(
        ...,
        description="Date effective de la sauvegarde."
    )

    created: bool = Field(
        ...,
        description=(
            "Indique si le document a été créé "
            "plutôt que mis à jour."
        )
    )


# Historique

class AnalysisSummary(BaseModel):
    """Résumé d'une analyse affichée dans un historique."""

    model_config = ConfigDict(
        extra="forbid",
        frozen=True
    )

    # Identifiants

    id: str = Field(
        ...,
        min_length=1,
        description="Identifiant unique de l'analyse."
    )

    request_id: str = Field(
        ...,
        min_length=1,
        description="Identifiant de la requête associée."
    )

    # Analyse

    fen: str = Field(
        ...,
        min_length=10,
        description="Position analysée."
    )

    status: AnalysisStatus = Field(
        ...,
        description="Statut final de l'analyse."
    )


    opening_name: str | None = Field(
        default=None,
        description="Nom de l'ouverture éventuellement détectée."
    )

    response_preview: str | None = Field(
        default=None,
        description="Extrait de la réponse générée."
    )

    # Diagnostics

    warning_count: int = Field(
        default=0,
        ge=0,
        description="Nombre d'avertissements."
    )

    error_count: int = Field(
        default=0,
        ge=0,
        description="Nombre d'erreurs."
    )

    # Dates

    created_at: datetime = Field(
        ...,
        description="Date de création de l'analyse."
    )

    saved_at: datetime = Field(
        ...,
        description="Date de la dernière sauvegarde."
    )