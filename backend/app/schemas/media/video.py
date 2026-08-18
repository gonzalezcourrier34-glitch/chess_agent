"""Schémas représentant les ressources vidéo.

Ce module regroupe les modèles utilisés pour représenter les vidéos
proposées à l'utilisateur lors d'une analyse.

Les modèles restent indépendants de l'API YouTube afin de faciliter
l'évolution du projet vers d'autres plateformes.
"""

from __future__ import annotations

from pydantic import BaseModel, ConfigDict, Field

from app.schemas.common.enums import VideoPlatform

# Chaîne

class VideoChannel(BaseModel):
    """Chaîne publiant une vidéo."""

    model_config = ConfigDict(
        extra="forbid",
        frozen=True
    )

    # Informations permettant d'identifier le créateur
    # de la vidéo.
    id: str | None = None

    name: str

    url: str | None = None

    subscribers: int | None = Field(
        default=None,
        ge=0
    )


# Vidéo

class Video(BaseModel):
    """Vidéo pédagogique."""

    model_config = ConfigDict(
        extra="forbid",
        frozen=True
    )

    # Représentation d'une vidéo pouvant être proposée
    # à l'utilisateur lors d'une analyse.
    id: str

    platform: VideoPlatform = (
        VideoPlatform.YOUTUBE
    )

    title: str

    description: str | None = None

    url: str

    thumbnail_url: str | None = None

    duration_seconds: int | None = Field(
        default=None,
        ge=0
    )

    view_count: int | None = Field(
        default=None,
        ge=0
    )

    like_count: int | None = Field(
        default=None,
        ge=0
    )

    comment_count: int | None = Field(
        default=None,
        ge=0
    )

    published_at: str | None = None

    channel: VideoChannel

    language: str | None = None

# Recommandation

class VideoRecommendation(BaseModel):
    """Vidéo recommandée."""

    model_config = ConfigDict(
        extra="forbid"
    )

    # Ce modèle associe une vidéo au score calculé
    # par le moteur de recommandation.
    video: Video

    relevance_score: float = Field(
        ...,
        ge=0.0,
        le=1.0
    )

    reason: str | None = None

    matching_topics: list[str] = Field(
        default_factory=list
    )


# Collection

class VideoCollection(BaseModel):
    """Ensemble de vidéos."""

    model_config = ConfigDict(
        extra="forbid"
    )

    # Résultat complet d'une recherche de vidéos.
    query: str

    total_results: int = Field(
        default=0,
        ge=0
    )

    videos: list[VideoRecommendation] = Field(
        default_factory=list
    )
# Requête

class VideoSearchRequest(BaseModel):
    """Requête de recherche de vidéos pédagogiques."""

    model_config = ConfigDict(
        extra="forbid",
        frozen=True,
        str_strip_whitespace=True
    )

    # Sujet utilisé pour rechercher des vidéos.
    query: str = Field(
        ...,
        min_length=1,
        description=(
            "Ouverture, position ou sujet échiquéen "
            "à rechercher."
        )
    )

    # Nombre maximal de vidéos souhaitées.
    # La valeur configurée dans Settings est utilisée lorsque ce champ
    # n'est pas renseigné.
    max_results: int | None = Field(
        default=None,
        ge=1,
        le=50,
        description=(
            "Nombre maximal de vidéos à retourner."
        )
    )

    # Langue privilégiée pour la recherche.
    # La langue configurée dans Settings est utilisée lorsque ce champ
    # n'est pas renseigné.
    language: str | None = Field(
        default=None,
        min_length=2,
        max_length=10,
        description=(
            "Langue privilégiée pour la recherche."
        )
    )