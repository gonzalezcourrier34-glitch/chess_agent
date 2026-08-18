"""Énumérations communes du projet Chess Agent.

Ce module centralise les différentes valeurs utilisées par les schémas
et les services du projet afin d'éviter les chaînes de caractères
littérales dispersées dans le code.

Toutes les énumérations héritent de StrEnum afin de faciliter leur
sérialisation dans les réponses JSON.
"""

from __future__ import annotations

from enum import StrEnum

# Analyse

class AnalysisMode(StrEnum):
    """Mode d'analyse utilisé."""

    THEORY = "theory"
    ENGINE = "engine"


class AnalysisStatus(StrEnum):
    """Statut d'une analyse."""

    SUCCESS = "success"
    ERROR = "error"
    RUNNING = "running"


# Couleur

class PieceColor(StrEnum):
    """Couleur du joueur."""

    WHITE = "white"
    BLACK = "black"


class ChessColor(StrEnum):
    """Couleur du joueur."""

    WHITE = "white"
    BLACK = "black"


class MoveNotation(StrEnum):
    """Notation d'un coup."""

    UCI = "uci"
    SAN = "san"


# Evaluation

class EvaluationType(StrEnum):
    """Type d'évaluation retournée par le moteur."""

    CENTIPAWN = "centipawn"
    MATE = "mate"


# Services

class ServiceStatus(StrEnum):
    """État d'un service externe."""

    AVAILABLE = "available"
    UNAVAILABLE = "unavailable"
    DEGRADED = "degraded"


# Recherche

class SearchSource(StrEnum):
    """Origine d'un résultat de recherche."""

    MILVUS = "milvus"
    LICHESS = "lichess"
    STOCKFISH = "stockfish"
    YOUTUBE = "youtube"


# Documents

class DocumentType(StrEnum):
    """Nature d'un document retourné."""

    OPENING = "opening"
    GAME = "game"
    ARTICLE = "article"


# Vidéos

class VideoPlatform(StrEnum):
    """Plateforme vidéo."""

    YOUTUBE = "youtube"


# Difficulté

class DifficultyLevel(StrEnum):
    """Niveau de difficulté d'une ouverture."""

    BEGINNER = "beginner"
    INTERMEDIATE = "intermediate"
    ADVANCED = "advanced"
    MASTER = "master"