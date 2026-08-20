"""Tests unitaires des routes de recherche de vidéos."""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock

import pytest
from app.api.v1.endpoints.route_search_videos import (
    search_videos,
    search_videos_by_opening,
)
from app.schemas.media.video import (
    VideoCollection,
    VideoSearchRequest,
)

# Configuration

OPENING = "Sicilian Defense"


# Recherche par ouverture


@pytest.mark.asyncio
async def test_search_videos_by_opening_builds_request_and_delegates() -> None:
    """Vérifie la construction de la requête depuis le nom d'ouverture."""

    expected_response = MagicMock(
        spec=VideoCollection,
    )

    service = MagicMock()
    service.search_videos = AsyncMock(
        return_value=expected_response,
    )

    result = await search_videos_by_opening(
        service=service,
        opening=OPENING,
    )

    assert result is expected_response

    service.search_videos.assert_awaited_once()

    request = service.search_videos.await_args.args[0]

    assert isinstance(
        request,
        VideoSearchRequest,
    )
    assert request.query == OPENING


@pytest.mark.asyncio
async def test_search_videos_by_opening_propagates_service_error() -> None:
    """Vérifie que la route ne masque pas une erreur YouTube."""

    service = MagicMock()
    service.search_videos = AsyncMock(
        side_effect=RuntimeError(
            "youtube failure",
        ),
    )

    with pytest.raises(
        RuntimeError,
        match="youtube failure",
    ):
        await search_videos_by_opening(
            service=service,
            opening=OPENING,
        )

    service.search_videos.assert_awaited_once()


# Recherche avancée


@pytest.mark.asyncio
async def test_search_videos_delegates_payload_to_youtube_service() -> None:
    """Vérifie que la requête avancée est transmise au service YouTube."""

    payload = VideoSearchRequest(
        query=OPENING,
    )

    expected_response = MagicMock(
        spec=VideoCollection,
    )

    service = MagicMock()
    service.search_videos = AsyncMock(
        return_value=expected_response,
    )

    result = await search_videos(
        payload=payload,
        service=service,
    )

    assert result is expected_response

    service.search_videos.assert_awaited_once_with(
        payload,
    )


@pytest.mark.asyncio
async def test_search_videos_propagates_service_error() -> None:
    """Vérifie que la route ne masque pas une erreur du service YouTube."""

    payload = VideoSearchRequest(
        query=OPENING,
    )

    service = MagicMock()
    service.search_videos = AsyncMock(
        side_effect=RuntimeError(
            "youtube failure",
        ),
    )

    with pytest.raises(
        RuntimeError,
        match="youtube failure",
    ):
        await search_videos(
            payload=payload,
            service=service,
        )

    service.search_videos.assert_awaited_once_with(
        payload,
    )
