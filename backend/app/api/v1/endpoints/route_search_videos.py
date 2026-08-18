"""Routes de recherche de vidéos.

Ce module expose les endpoints permettant de rechercher des vidéos
pédagogiques adaptées à une analyse échiquéenne.

Il ne contient aucune logique métier.

La validation de la requête, la résolution des paramètres par défaut,
l'appel à l'API YouTube, la normalisation des résultats et la
construction des recommandations sont délégués au YoutubeService.
"""

from __future__ import annotations

from fastapi import APIRouter, Path, status

from app.api.responses import YOUTUBE_ERROR_RESPONSES
from app.api.v1.dependencies.services import YoutubeServiceDependency
from app.schemas.media.video import (
    VideoCollection,
    VideoSearchRequest,
)


# Routeur

router = APIRouter()


# Recherche par ouverture

@router.get(
    "/videos/{opening}",
    response_model=VideoCollection,
    status_code=status.HTTP_200_OK,
    summary="Rechercher des vidéos pour une ouverture",
    description=(
        "Recherche des vidéos pédagogiques YouTube pertinentes "
        "pour une ouverture d'échecs donnée."
    ),
    response_description="Collection de vidéos pédagogiques recommandées.",
    responses=YOUTUBE_ERROR_RESPONSES,
)
async def search_videos_by_opening(
    service: YoutubeServiceDependency,
    opening: str = Path(
        ...,
        min_length=1,
        description="Nom de l'ouverture d'échecs à rechercher.",
        examples=["Sicilian Defense"],
    ),
) -> VideoCollection:
    """Recherche des vidéos pédagogiques pour une ouverture."""
    request = VideoSearchRequest(
        query=opening,
    )

    return await service.search_videos(
        request
    )


# Recherche avancée

@router.post(
    "/videos",
    response_model=VideoCollection,
    status_code=status.HTTP_200_OK,
    summary="Rechercher des vidéos pédagogiques",
    description=(
        "Recherche des vidéos pédagogiques sur YouTube à partir d'une "
        "requête échiquéenne. Les résultats sont normalisés, classés "
        "et accompagnés de leurs informations de pertinence."
    ),
    response_description="Collection de vidéos pédagogiques recommandées.",
    responses=YOUTUBE_ERROR_RESPONSES,
)
async def search_videos(
    payload: VideoSearchRequest,
    service: YoutubeServiceDependency,
) -> VideoCollection:
    """Recherche des vidéos pédagogiques."""
    return await service.search_videos(
        payload
    )