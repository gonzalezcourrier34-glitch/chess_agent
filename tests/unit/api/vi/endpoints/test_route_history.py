"""Tests unitaires des routes de gestion de l'historique."""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock

import pytest
from app.api.v1.dependencies.pagination import Pagination
from app.api.v1.endpoints.route_history import (
    delete_history,
    get_history,
    list_history,
)
from app.schemas.analysis.analysis import (
    AnalysisRecord,
    AnalysisSummary,
)
from fastapi import status

# Configuration

ANALYSIS_ID = "analysis-test-id"
LIMIT = 20
OFFSET = 10


# Historique


@pytest.mark.asyncio
async def test_list_history_delegates_to_mongodb_service() -> None:
    """Vérifie que la liste est déléguée au service MongoDB."""

    pagination = Pagination(
        limit=LIMIT,
        offset=OFFSET,
    )

    expected_response = [
        MagicMock(spec=AnalysisSummary),
        MagicMock(spec=AnalysisSummary),
    ]

    service = MagicMock()
    service.list_recent_analyses = AsyncMock(
        return_value=expected_response,
    )

    result = await list_history(
        pagination=pagination,
        service=service,
    )

    assert result is expected_response

    service.list_recent_analyses.assert_awaited_once_with(
        limit=LIMIT,
        offset=OFFSET,
    )


@pytest.mark.asyncio
async def test_list_history_returns_empty_list() -> None:
    """Vérifie qu'un historique vide est retourné tel quel."""

    pagination = Pagination(
        limit=LIMIT,
        offset=OFFSET,
    )

    service = MagicMock()
    service.list_recent_analyses = AsyncMock(
        return_value=[],
    )

    result = await list_history(
        pagination=pagination,
        service=service,
    )

    assert result == []

    service.list_recent_analyses.assert_awaited_once_with(
        limit=LIMIT,
        offset=OFFSET,
    )


@pytest.mark.asyncio
async def test_list_history_propagates_service_error() -> None:
    """Vérifie que la route ne masque pas une erreur MongoDB."""

    pagination = Pagination(
        limit=LIMIT,
        offset=OFFSET,
    )

    service = MagicMock()
    service.list_recent_analyses = AsyncMock(
        side_effect=RuntimeError(
            "database failure",
        ),
    )

    with pytest.raises(
        RuntimeError,
        match="database failure",
    ):
        await list_history(
            pagination=pagination,
            service=service,
        )

    service.list_recent_analyses.assert_awaited_once_with(
        limit=LIMIT,
        offset=OFFSET,
    )


# Lecture


@pytest.mark.asyncio
async def test_get_history_delegates_to_mongodb_service() -> None:
    """Vérifie que la lecture est déléguée au service MongoDB."""

    expected_response = MagicMock(
        spec=AnalysisRecord,
    )

    service = MagicMock()
    service.get_required_analysis = AsyncMock(
        return_value=expected_response,
    )

    result = await get_history(
        analysis_id=ANALYSIS_ID,
        service=service,
    )

    assert result is expected_response

    service.get_required_analysis.assert_awaited_once_with(
        ANALYSIS_ID,
    )


@pytest.mark.asyncio
async def test_get_history_propagates_service_error() -> None:
    """Vérifie que la route ne masque pas une erreur de lecture."""

    service = MagicMock()
    service.get_required_analysis = AsyncMock(
        side_effect=RuntimeError(
            "analysis not found",
        ),
    )

    with pytest.raises(
        RuntimeError,
        match="analysis not found",
    ):
        await get_history(
            analysis_id=ANALYSIS_ID,
            service=service,
        )

    service.get_required_analysis.assert_awaited_once_with(
        ANALYSIS_ID,
    )


# Suppression


@pytest.mark.asyncio
async def test_delete_history_delegates_to_mongodb_service() -> None:
    """Vérifie que la suppression est déléguée au service MongoDB."""

    service = MagicMock()
    service.delete_required_analysis = AsyncMock(
        return_value=None,
    )

    response = await delete_history(
        analysis_id=ANALYSIS_ID,
        service=service,
    )

    service.delete_required_analysis.assert_awaited_once_with(
        ANALYSIS_ID,
    )

    assert response.status_code == status.HTTP_204_NO_CONTENT
    assert response.body == b""


@pytest.mark.asyncio
async def test_delete_history_propagates_service_error() -> None:
    """Vérifie que la route ne confirme pas une suppression en erreur."""

    service = MagicMock()
    service.delete_required_analysis = AsyncMock(
        side_effect=RuntimeError(
            "delete failure",
        ),
    )

    with pytest.raises(
        RuntimeError,
        match="delete failure",
    ):
        await delete_history(
            analysis_id=ANALYSIS_ID,
            service=service,
        )

    service.delete_required_analysis.assert_awaited_once_with(
        ANALYSIS_ID,
    )
