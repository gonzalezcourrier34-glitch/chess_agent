"""Tests unitaires des routes d'accès aux ouvertures Lichess."""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock

import pytest
from app.api.v1.endpoints.route_opening import detect_opening
from app.schemas.chess.opening import OpeningDetails
from app.schemas.chess.position import FenRequest

# Configuration

FEN = "rnbqkbnr/pppppppp/8/8/8/8/PPPPPPPP/RNBQKBNR w KQkq - 0 1"


# Helpers


def build_fen_request() -> FenRequest:
    """Construit une requête FEN valide."""

    return FenRequest(
        fen=FEN,
    )


# Détection d'ouverture


@pytest.mark.asyncio
async def test_detect_opening_delegates_to_lichess_service() -> None:
    """Vérifie que la route délègue la détection au service Lichess."""

    payload = build_fen_request()

    expected_response = MagicMock(
        spec=OpeningDetails,
    )

    service = MagicMock()
    service.detect_opening = AsyncMock(
        return_value=expected_response,
    )

    result = await detect_opening(
        payload=payload,
        service=service,
    )

    assert result is expected_response

    service.detect_opening.assert_awaited_once_with(
        payload,
    )


@pytest.mark.asyncio
async def test_detect_opening_propagates_service_error() -> None:
    """Vérifie que la route ne masque pas une erreur du service Lichess."""

    payload = build_fen_request()

    service = MagicMock()
    service.detect_opening = AsyncMock(
        side_effect=RuntimeError(
            "lichess failure",
        ),
    )

    with pytest.raises(
        RuntimeError,
        match="lichess failure",
    ):
        await detect_opening(
            payload=payload,
            service=service,
        )

    service.detect_opening.assert_awaited_once_with(
        payload,
    )
