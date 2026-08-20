"""Énumérations communes du projet Chess Agent.

Ce module centralise les différentes valeurs utilisées par :

- les schémas Pydantic ;
- les services applicatifs ;
- le workflow LangGraph ;
- les composants de recherche ;
- les réponses de l'API.

Toutes les énumérations héritent de StrEnum afin de faciliter leur
sérialisation en JSON.
"""

from __future__ import annotations

from enum import StrEnum

# Analyse


class AnalysisStatus(StrEnum):
    """État global d'une analyse."""

    PENDING = "pending"
    SUCCESS = "success"
    PARTIAL_SUCCESS = "partial_success"
    FAILED = "failed"


# Workflow


class WorkflowStep(StrEnum):
    """Étapes exécutables du workflow LangGraph."""

    VALIDATE_POSITION = "validate_position"

    DETECT_THEORY = "detect_theory"

    ENGINE_ANALYSIS = "engine_analysis"

    UNKNOWN_POSITION_ANALYSIS = "unknown_position_analysis"

    RETRIEVE_CONTEXT = "retrieve_context"

    RETRIEVE_VIDEOS = "retrieve_videos"

    GENERATE_RESPONSE = "generate_response"

    SAVE_ANALYSIS = "save_analysis"


# Progression


class WorkflowStepStatus(StrEnum):
    """État d'exécution d'une étape du workflow."""

    PENDING = "pending"
    RUNNING = "running"
    COMPLETED = "completed"
    WARNING = "warning"
    FAILED = "failed"


# Échecs


class ChessColor(StrEnum):
    """Couleur d'un joueur."""

    WHITE = "white"
    BLACK = "black"


class MoveNotation(StrEnum):
    """Notation utilisée pour représenter un coup."""

    UCI = "uci"
    SAN = "san"


# Évaluation


class EvaluationType(StrEnum):
    """Nature d'une évaluation Stockfish."""

    CENTIPAWN = "centipawn"
    MATE = "mate"


# Services


class ServiceType(StrEnum):
    """Services métier et d'infrastructure de l'application."""

    CHESS = "chess"
    STOCKFISH = "stockfish"
    LICHESS = "lichess"

    VECTOR_SEARCH = "vector_search"
    EMBEDDING = "embedding"
    MILVUS = "milvus"

    LLM = "llm"
    YOUTUBE = "youtube"
    MONGODB = "mongodb"
    LANGGRAPH = "langgraph"


class ServiceStatus(StrEnum):
    """État de disponibilité d'un service."""

    AVAILABLE = "available"
    DEGRADED = "degraded"
    UNAVAILABLE = "unavailable"


# Documents


class DocumentType(StrEnum):
    """Nature d'un document manipulé par le moteur RAG."""

    OPENING = "opening"
    GAME = "game"
    ARTICLE = "article"
    CHUNK = "chunk"


# Vidéos


class VideoPlatform(StrEnum):
    """Plateforme vidéo supportée."""

    YOUTUBE = "youtube"


# Difficulté


class DifficultyLevel(StrEnum):
    """Niveau de difficulté d'un contenu pédagogique."""

    BEGINNER = "beginner"
    INTERMEDIATE = "intermediate"
    ADVANCED = "advanced"
    MASTER = "master"
