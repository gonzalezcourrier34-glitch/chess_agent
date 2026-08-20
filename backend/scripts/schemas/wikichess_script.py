"""Schémas des scripts Wikichess.

Ce module regroupe les structures de données utilisées pour :

- définir les ouvertures à télécharger ;
- représenter les coups suivants disponibles depuis une position ;
- représenter les échecs de téléchargement ;
- représenter les présentations chargées depuis le disque ;
- construire les documents destinés aux embeddings ;
- produire le rapport d'ingestion.

Ces modèles restent indépendants de FastAPI, des services métier
et de Milvus.
"""

from __future__ import annotations

from dataclasses import dataclass

# Téléchargement


@dataclass(frozen=True, slots=True)
class OpeningTarget:
    """Ouverture à récupérer depuis Wikichess."""

    slug: str

    title: str

    moves: tuple[str, ...]

    eco: str


@dataclass(frozen=True, slots=True)
class WikichessNextMove:
    """Coup suivant disponible depuis une position Wikichess."""

    move: str

    source_url: str


@dataclass(frozen=True, slots=True)
class DownloadFailure:
    """Échec rencontré pendant un téléchargement."""

    slug: str

    title: str

    reason: str


# Ingestion


@dataclass(frozen=True, slots=True)
class WikichessArticle:
    """Article Wikichess chargé depuis le disque."""

    slug: str

    title: str

    content: str

    source_path: str

    language: str

    eco: str = ""

    moves: tuple[str, ...] = ()

    position_after: str = ""

    source_url: str = ""

    wikichess_title: str = ""

    contributors: tuple[str, ...] = ()

    next_moves: tuple[WikichessNextMove, ...] = ()

    retrieved_at: str = ""


@dataclass(frozen=True, slots=True)
class WikichessChunk:
    """Document textuel prêt à être vectorisé."""

    id: str

    article_slug: str

    article_title: str

    content: str

    chunk_index: int

    chunk_count: int

    source_path: str

    language: str

    eco: str = ""

    moves: tuple[str, ...] = ()

    position_after: str = ""

    source_url: str = ""

    wikichess_title: str = ""

    contributors: tuple[str, ...] = ()

    next_moves: tuple[WikichessNextMove, ...] = ()

    retrieved_at: str = ""


# Rapports


@dataclass(frozen=True, slots=True)
class IngestionReport:
    """Bilan de l'ingestion Wikichess."""

    article_count: int

    chunk_count: int

    inserted_count: int

    embedding_dimension: int

    duration_ms: float

    exported_chunks: bool = False

    replaced_existing_documents: bool = False
