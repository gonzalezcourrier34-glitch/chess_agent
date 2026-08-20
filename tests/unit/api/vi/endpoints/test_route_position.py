"""Tests unitaires des routes de gestion des positions d'échecs."""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock

import pytest
from app.api.v1.endpoints.route_position import (
    evaluate_position,
    get_legal_moves,
    validate_position,
)
from app.schemas.analysis.evaluation import PositionEvaluation
from app.schemas.chess.move import LegalMove
from app.schemas.chess.position import BoardPosition, FenRequest

# Configuration

FEN = "rnbqkbnr/pppppppp/8/8/8/8/PPPPPPPP/RNBQKBNR w KQkq - 0 1"


# Helpers


def build_fen_request() -> FenRequest:
    """Construit une requête FEN valide."""

    return FenRequest(
        fen=FEN,
    )


# Validation


@pytest.mark.asyncio
async def test_validate_position_delegates_to_chess_service() -> None:
    """Vérifie que la validation est déléguée au service d'échecs."""

    payload = build_fen_request()

    expected_response = MagicMock(
        spec=BoardPosition,
    )

    service = MagicMock()
    service.get_position = MagicMock(
        return_value=expected_response,
    )

    result = await validate_position(
        payload=payload,
        service=service,
    )

    assert result is expected_response

    service.get_position.assert_called_once_with(
        payload,
    )


@pytest.mark.asyncio
async def test_validate_position_propagates_service_error() -> None:
    """Vérifie que la route ne masque pas une erreur de validation."""

    payload = build_fen_request()

    service = MagicMock()
    service.get_position = MagicMock(
        side_effect=RuntimeError(
            "invalid position",
        ),
    )

    with pytest.raises(
        RuntimeError,
        match="invalid position",
    ):
        await validate_position(
            payload=payload,
            service=service,
        )

    service.get_position.assert_called_once_with(
        payload,
    )


# Coups légaux


@pytest.mark.asyncio
async def test_get_legal_moves_delegates_to_chess_service() -> None:
    """Vérifie que les coups légaux sont délégués au service d'échecs."""

    payload = build_fen_request()

    expected_response = [
        MagicMock(spec=LegalMove),
        MagicMock(spec=LegalMove),
    ]

    service = MagicMock()
    service.get_legal_moves = MagicMock(
        return_value=expected_response,
    )

    result = await get_legal_moves(
        payload=payload,
        service=service,
    )

    assert result is expected_response

    service.get_legal_moves.assert_called_once_with(
        payload,
    )


@pytest.mark.asyncio
async def test_get_legal_moves_returns_empty_list() -> None:
    """Vérifie qu'une liste vide de coups légaux est retournée telle quelle."""

    payload = build_fen_request()

    service = MagicMock()
    service.get_legal_moves = MagicMock(
        return_value=[],
    )

    result = await get_legal_moves(
        payload=payload,
        service=service,
    )

    assert result == []

    service.get_legal_moves.assert_called_once_with(
        payload,
    )


@pytest.mark.asyncio
async def test_get_legal_moves_propagates_service_error() -> None:
    """Vérifie que la route ne masque pas une erreur du service d'échecs."""

    payload = build_fen_request()

    service = MagicMock()
    service.get_legal_moves = MagicMock(
        side_effect=RuntimeError(
            "legal moves failure",
        ),
    )

    with pytest.raises(
        RuntimeError,
        match="legal moves failure",
    ):
        await get_legal_moves(
            payload=payload,
            service=service,
        )

    service.get_legal_moves.assert_called_once_with(
        payload,
    )


# Évaluation interne


@pytest.mark.asyncio
async def test_evaluate_position_delegates_to_stockfish_service() -> None:
    """Vérifie que l'évaluation interne est déléguée à Stockfish."""

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
    """Vérifie que la route ne masque pas une erreur Stockfish."""

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
