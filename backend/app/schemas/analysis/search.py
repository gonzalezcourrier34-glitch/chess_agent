"""Schémas de recherche vectorielle.

Ce module définit les modèles utilisés par l'API pour :

- recevoir une requête de recherche sémantique ;
- retourner les documents retrouvés dans Milvus ;
- exposer le score de similarité et les métadonnées associées.

Les opérations de génération d'embeddings et de recherche vectorielle
restent déléguées aux services spécialisés.
"""

from __future__ import annotations

from typing import Any

from pydantic import BaseModel, ConfigDict, Field

# Requête


class VectorSearchRequest(BaseModel):
    """Requête de recherche vectorielle."""

    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)

    # La requête peut être le nom d'une ouverture ou une question
    # formulée librement par l'utilisateur.
    query: str = Field(..., min_length=2, max_length=500)

    # Le nombre de résultats peut être ajusté pour une recherche
    # ponctuelle sans dépasser la limite prévue par l'API.
    limit: int = Field(default=5, ge=1, le=20)


# Résultat


class VectorSearchResult(BaseModel):
    """Document retrouvé dans Milvus."""

    model_config = ConfigDict(extra="forbid")

    # Identifiant technique du document ou du chunk.
    id: str

    # Contenu textuel retourné par la recherche.
    content: str

    # Score normalisé de similarité avec la requête.
    similarity: float = Field(..., ge=0, le=1)

    # Métadonnées associées au document, par exemple l'ouverture,
    # la source ou l'index du chunk.
    metadata: dict[str, Any] = Field(default_factory=dict)


# Réponse


class VectorSearchResponse(BaseModel):
    """Résultat complet d'une recherche vectorielle."""

    model_config = ConfigDict(extra="forbid")

    # Requête originale transmise par le client.
    query: str

    # Résultats ordonnés du plus pertinent au moins pertinent.
    results: list[VectorSearchResult] = Field(default_factory=list)
