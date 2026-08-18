"""Schémas représentant les ressources vidéo.

Ce module regroupe les modèles utilisés pour représenter les vidéos
proposées à l'utilisateur lors d'une analyse.

Les modèles restent indépendants de l'API YouTube afin de faciliter
l'évolution du projet vers d'autres plateformes.
"""

from __future__ import annotations

from app.schemas.enums import VideoPlatform
from pydantic import BaseModel, ConfigDict, Field

# Chaîne

class VideoChannel(BaseModel):
    """Chaîne publiant une vidéo."""

    model_config = ConfigDict(
        extra="forbid",
        frozen=True
    )

    id: str | None = Field(
        default=None,
        description="Identifiant de la chaîne."
    )

    name: str = Field(
        ...,
        description="Nom de la chaîne."
    )

    url: str | None = Field(
        default=None,
        description="Lien vers la chaîne."
    )

    subscribers: int | None = Field(
        default=None,
        ge=0,
        description="Nombre d'abonnés."
    )


# Vidéo

class Video(BaseModel):
    """Vidéo pédagogique."""

    model_config = ConfigDict(
        extra="forbid",
        frozen=True
    )

    id: str = Field(
        ...,
        description="Identifiant de la vidéo."
    )

    platform: VideoPlatform = Field(
        default=VideoPlatform.YOUTUBE,
        description="Plateforme d'hébergement."
    )

    title: str = Field(
        ...,
        description="Titre."
    )

    description: str | None = Field(
        default=None,
        description="Description."
    )

    url: str = Field(
        ...,
        description="Lien vers la vidéo."
    )

    thumbnail_url: str | None = Field(
        default=None,
        description="Miniature."
    )

    duration_seconds: int | None = Field(
        default=None,
        ge=0,
        description="Durée."
    )

    published_at: str | None = Field(
        default=None,
        description="Date de publication."
    )

    channel: VideoChannel

    language: str | None = Field(
        default=None,
        description="Langue."
    )


# Pertinence

class VideoRecommendation(BaseModel):
    """Vidéo recommandée."""

    model_config = ConfigDict(
        extra="forbid"
    )

    video: Video

    relevance_score: float = Field(
        ...,
        ge=0.0,
        le=1.0,
        description="Pertinence calculée."
    )

    reason: str | None = Field(
        default=None,
        description="Justification de la recommandation."
    )

    matching_topics: list[str] = Field(
        default_factory=list,
        description="Thèmes correspondants."
    )


# Collection

class VideoCollection(BaseModel):
    """Ensemble de vidéos."""

    model_config = ConfigDict(
        extra="forbid"
    )

    query: str = Field(
        ...,
        description="Recherche utilisée."
    )

    total_results: int = Field(
        default=0,
        ge=0,
        description="Nombre de vidéos."
    )

    videos: list[VideoRecommendation] = Field(
        default_factory=list,
        description="Vidéos proposées."
    )