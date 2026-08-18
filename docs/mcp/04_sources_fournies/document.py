"""Schémas représentant les documents du moteur RAG.

Ce module centralise les modèles utilisés pour manipuler les documents
stockés dans Milvus ou MongoDB.

Les documents représentent les connaissances exploitées par l'agent IA
pour enrichir une analyse d'échecs.
"""

from __future__ import annotations

from app.schemas.enums import DocumentType
from pydantic import BaseModel, ConfigDict, Field

# Métadonnées

class DocumentMetadata(BaseModel):
    """Métadonnées d'un document."""

    model_config = ConfigDict(
        extra="forbid",
        frozen=True
    )

    source: str = Field(
        ...,
        description="Origine du document."
    )

    language: str = Field(
        default="en",
        description="Langue du document."
    )

    author: str | None = Field(
        default=None,
        description="Auteur."
    )

    url: str | None = Field(
        default=None,
        description="Lien d'origine."
    )

    publication_date: str | None = Field(
        default=None,
        description="Date de publication."
    )


# Document

class Document(BaseModel):
    """Document indexé."""

    model_config = ConfigDict(
        extra="forbid",
        frozen=True
    )

    id: str = Field(
        ...,
        description="Identifiant unique."
    )

    type: DocumentType = Field(
        ...,
        description="Nature du document."
    )

    title: str = Field(
        ...,
        description="Titre."
    )

    content: str = Field(
        ...,
        description="Contenu intégral."
    )

    metadata: DocumentMetadata


# Chunk

class DocumentChunk(BaseModel):
    """Fragment d'un document."""

    model_config = ConfigDict(
        extra="forbid",
        frozen=True
    )

    id: str = Field(
        ...,
        description="Identifiant du fragment."
    )

    document_id: str = Field(
        ...,
        description="Document parent."
    )

    content: str = Field(
        ...,
        description="Texte indexé."
    )

    chunk_index: int = Field(
        ...,
        ge=0,
        description="Position dans le document."
    )


# Résultat RAG

class RetrievedDocument(BaseModel):
    """Document retrouvé par la recherche vectorielle."""

    model_config = ConfigDict(
        extra="forbid"
    )

    document: Document

    similarity: float = Field(
        ...,
        ge=0.0,
        le=1.0,
        description="Score de similarité."
    )

    chunk: DocumentChunk | None = Field(
        default=None,
        description="Fragment utilisé."
    )

    excerpt: str | None = Field(
        default=None,
        description="Extrait transmis au LLM."
    )


# Contexte

class RetrievalContext(BaseModel):
    """Contexte documentaire utilisé par une analyse."""

    model_config = ConfigDict(
        extra="forbid"
    )

    query: str = Field(
        ...,
        description="Requête effectuée."
    )

    documents: list[RetrievedDocument] = Field(
        default_factory=list,
        description="Documents retrouvés."
    )

    total_results: int = Field(
        default=0,
        ge=0,
        description="Nombre de résultats."
    )