"""Schémas représentant les documents du moteur RAG.

Ce module centralise les modèles utilisés pour manipuler les documents
stockés dans Milvus ou MongoDB.

Les documents représentent les connaissances exploitées par l'agent IA
pour enrichir une analyse d'échecs.

Les métadonnées documentaires conservent également les informations
structurelles du corpus Wikichess lorsqu'elles sont disponibles :

- le code ECO ;
- la séquence de coups ;
- le chemin de coups utilisé pour la recherche ;
- le dernier coup de la position Wikichess ;
- le titre Wikichess ;
- les continuations disponibles depuis la position.

Ces informations restent facultatives afin que les schémas RAG puissent
également représenter des documents provenant d'autres sources.
"""

from __future__ import annotations

from pydantic import BaseModel, ConfigDict, Field

from app.schemas.common.enums import DocumentType

# Navigation Wikichess

class DocumentNextMove(BaseModel):
    """Continuation documentaire disponible depuis une position."""

    model_config = ConfigDict(
        extra="forbid",
        frozen=True
    )

    move: str = Field(
        ...,
        min_length=1,
        description=(
            "Coup permettant d'accéder à une continuation "
            "documentaire."
        )
    )

    source_url: str = Field(
        ...,
        min_length=1,
        description=(
            "URL du document correspondant à la continuation."
        )
    )


# Métadonnées

class DocumentMetadata(BaseModel):
    """Métadonnées associées à un document RAG."""

    model_config = ConfigDict(
        extra="forbid",
        frozen=True
    )

    # Provenance

    source: str = Field(
        ...,
        min_length=1,
        description="Source documentaire."
    )

    language: str = Field(
        default="en",
        min_length=2,
        description="Langue du document."
    )

    author: str | None = Field(
        default=None,
        description="Auteur du document."
    )

    url: str | None = Field(
        default=None,
        description="URL du document source."
    )

    publication_date: str | None = Field(
        default=None,
        description="Date de publication du document."
    )

    # Wikichess

    eco: str | None = Field(
        default=None,
        description="Code ECO associé au document Wikichess."
    )

    moves: tuple[str, ...] = Field(
        default_factory=tuple,
        description=(
            "Séquence de coups conduisant au document Wikichess."
        )
    )

    moves_path: str | None = Field(
        default=None,
        description=(
            "Représentation textuelle normalisée de la séquence "
            "de coups utilisée pour les recherches structurelles."
        )
    )

    position_after: str | None = Field(
        default=None,
        description=(
            "Dernier coup indiqué par le marqueur Position after "
            "de Wikichess."
        )
    )

    wikichess_title: str | None = Field(
        default=None,
        description="Titre original fourni par Wikichess."
    )

    next_moves: tuple[
        DocumentNextMove,
        ...
    ] = Field(
        default_factory=tuple,
        description=(
            "Continuations Wikichess disponibles depuis "
            "la position documentaire."
        )
    )


# Document

class Document(BaseModel):
    """Document indexé dans le moteur RAG."""

    model_config = ConfigDict(
        extra="forbid",
        frozen=True
    )

    id: str = Field(
        ...,
        min_length=1,
        description="Identifiant unique du document."
    )

    type: DocumentType = Field(
        ...,
        description="Nature du document."
    )

    title: str = Field(
        ...,
        min_length=1,
        description="Titre du document."
    )

    content: str = Field(
        ...,
        description="Contenu intégral du document."
    )

    metadata: DocumentMetadata


# Chunk

class DocumentChunk(BaseModel):
    """Fragment d'un document indexé."""

    model_config = ConfigDict(
        extra="forbid",
        frozen=True
    )

    id: str = Field(
        ...,
        min_length=1,
        description="Identifiant unique du fragment."
    )

    document_id: str = Field(
        ...,
        min_length=1,
        description="Identifiant du document parent."
    )

    content: str = Field(
        ...,
        description="Contenu textuel du fragment."
    )

    chunk_index: int = Field(
        ...,
        ge=0,
        description="Position du fragment dans le document."
    )


# Résultat RAG

class RetrievedDocument(BaseModel):
    """Document retrouvé par le moteur RAG."""

    model_config = ConfigDict(
        extra="forbid"
    )

    document: Document

    similarity: float = Field(
        ...,
        ge=0.0,
        le=1.0,
        description="Score de similarité vectorielle."
    )

    chunk: DocumentChunk | None = Field(
        default=None,
        description="Fragment documentaire utilisé."
    )

    excerpt: str | None = Field(
        default=None,
        description="Extrait court du contenu documentaire."
    )


# Contexte

class RetrievalContext(BaseModel):
    """Contexte documentaire utilisé par une analyse."""

    model_config = ConfigDict(
        extra="forbid"
    )

    query: str = Field(
        ...,
        description="Requête utilisée pour récupérer les documents."
    )

    documents: list[RetrievedDocument] = Field(
        default_factory=list,
        description="Documents sélectionnés par le moteur RAG."
    )

    total_results: int = Field(
        default=0,
        ge=0,
        description="Nombre de documents sélectionnés."
    )