"""Tests unitaires des routes d'évaluation moteur."""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock

import pytest
from app.api.v1.endpoints.route_engine import evaluate_position
from app.schemas.analysis.evaluation import PositionEvaluation
from app.schemas.chess.position import FenRequest

# Configuration

FEN = "rnbqkbnr/pppppppp/8/8/8/8/PPPPPPPP/RNBQKBNR w KQkq - 0 1"


# Helpers


def build_fen_request() -> FenRequest:
    """Construit une requête FEN valide."""

    return FenRequest(
        fen=FEN,
    )


# Évaluation


@pytest.mark.asyncio
async def test_evaluate_position_delegates_to_stockfish_service() -> None:
    """Vérifie que la route délègue l'analyse au service Stockfish."""

    payload = build_fen_request()

    expected_response = MagicMock(
        spec=PositionEvaluation,
    )

    service = MagicMock()
    service.analyze_position = AsyncMock(
        return_value=expected_response,
    )

    result = await evaluate_position(
        payload=payload,
        service=service,
    )

    assert result is expected_response

    service.analyze_position.assert_awaited_once_with(
        payload,
    )


@pytest.mark.asyncio
async def test_evaluate_position_propagates_service_error() -> None:
    """Vérifie que la route ne masque pas les erreurs du service."""

    payload = build_fen_request()

    service = MagicMock()
    service.analyze_position = AsyncMock(
        side_effect=RuntimeError(
            "stockfish failure",
        ),
    )

    with pytest.raises(
        RuntimeError,
        match="stockfish failure",
    ):
        await evaluate_position(
            payload=payload,
            service=service,
        )

    service.analyze_position.assert_awaited_once_with(
        payload,
    )
