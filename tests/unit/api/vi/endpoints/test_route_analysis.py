"""Tests unitaires des routes d'analyse échiquéenne."""

from __future__ import annotations

from collections.abc import AsyncIterator
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock

import pytest
from app.api.v1.endpoints.route_analysis import analyze_position, stream_analysis
from app.schemas.analysis.analysis import AnalysisRequest, AnalysisResponse
from app.schemas.analysis.progress import AnalysisCompletedEvent, AnalysisProgressEvent
from fastapi import Request
from fastapi.responses import StreamingResponse

# Configuration

REQUEST_ID = "test-request-id"


# Helpers


def build_request() -> Request:
    """Construit une requête HTTP contenant un identifiant de requête."""

    request = MagicMock(spec=Request)
    request.state = SimpleNamespace(
        request_id=REQUEST_ID,
    )

    return request


def build_analysis_request() -> AnalysisRequest:
    """Construit une requête d'analyse minimale pour les tests."""

    return AnalysisRequest.model_construct(
        fen="rnbqkbnr/pppppppp/8/8/8/8/PPPPPPPP/RNBQKBNR w KQkq - 0 1",
        moves=[],
    )


# Analyse classique


@pytest.mark.asyncio
async def test_analyze_position_delegates_to_analysis_service() -> None:
    """Vérifie que la route délègue l'analyse au service métier."""

    request = build_request()
    payload = build_analysis_request()

    expected_response = MagicMock(
        spec=AnalysisResponse,
    )

    service = MagicMock()
    service.analyze = AsyncMock(
        return_value=expected_response,
    )

    result = await analyze_position(
        request=request,
        payload=payload,
        service=service,
    )

    assert result is expected_response

    service.analyze.assert_awaited_once_with(
        payload,
        request_id=REQUEST_ID,
    )


@pytest.mark.asyncio
async def test_analyze_position_propagates_service_error() -> None:
    """Vérifie que la route ne masque pas les erreurs du service métier."""

    request = build_request()
    payload = build_analysis_request()

    service = MagicMock()
    service.analyze = AsyncMock(
        side_effect=RuntimeError(
            "analysis failure",
        ),
    )

    with pytest.raises(
        RuntimeError,
        match="analysis failure",
    ):
        await analyze_position(
            request=request,
            payload=payload,
            service=service,
        )

    service.analyze.assert_awaited_once_with(
        payload,
        request_id=REQUEST_ID,
    )


# Analyse en streaming


@pytest.mark.asyncio
async def test_stream_analysis_returns_streaming_response() -> None:
    """Vérifie que la route retourne une réponse SSE."""

    request = build_request()
    payload = build_analysis_request()

    async def stream() -> AsyncIterator[object]:
        if False:
            yield None

    service = MagicMock()
    service.stream_analysis = MagicMock(
        return_value=stream(),
    )

    response = await stream_analysis(
        request=request,
        payload=payload,
        service=service,
    )

    assert isinstance(
        response,
        StreamingResponse,
    )

    assert response.media_type == "text/event-stream"

    assert response.headers["cache-control"] == "no-cache"
    assert response.headers["connection"] == "keep-alive"
    assert response.headers["x-accel-buffering"] == "no"

    chunks = [chunk async for chunk in response.body_iterator]

    assert chunks == []

    service.stream_analysis.assert_called_once_with(
        payload,
        request_id=REQUEST_ID,
    )


@pytest.mark.asyncio
async def test_stream_analysis_emits_progress_event(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Vérifie la transformation d'un événement de progression en SSE."""

    request = build_request()
    payload = build_analysis_request()

    progress_event = MagicMock(
        spec=AnalysisProgressEvent,
    )
    progress_event.model_dump_json.return_value = '{"type":"progress"}'

    async def stream() -> AsyncIterator[object]:
        yield progress_event

    service = MagicMock()
    service.stream_analysis = MagicMock(
        return_value=stream(),
    )

    format_sse_event = MagicMock(
        return_value="progress-sse\n\n",
    )

    monkeypatch.setattr(
        "app.api.v1.endpoints.route_analysis.format_sse_event",
        format_sse_event,
    )

    response = await stream_analysis(
        request=request,
        payload=payload,
        service=service,
    )

    chunks = [chunk async for chunk in response.body_iterator]

    assert chunks == [
        "progress-sse\n\n",
    ]

    progress_event.model_dump_json.assert_called_once_with()

    format_sse_event.assert_called_once_with(
        event="progress",
        data='{"type":"progress"}',
    )


@pytest.mark.asyncio
async def test_stream_analysis_emits_completed_event(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Vérifie la transformation de l'événement final en SSE."""

    request = build_request()
    payload = build_analysis_request()

    completed_event = MagicMock(
        spec=AnalysisCompletedEvent,
    )
    completed_event.model_dump_json.return_value = '{"type":"completed"}'

    async def stream() -> AsyncIterator[object]:
        yield completed_event

    service = MagicMock()
    service.stream_analysis = MagicMock(
        return_value=stream(),
    )

    format_sse_event = MagicMock(
        return_value="completed-sse\n\n",
    )

    monkeypatch.setattr(
        "app.api.v1.endpoints.route_analysis.format_sse_event",
        format_sse_event,
    )

    response = await stream_analysis(
        request=request,
        payload=payload,
        service=service,
    )

    chunks = [chunk async for chunk in response.body_iterator]

    assert chunks == [
        "completed-sse\n\n",
    ]

    completed_event.model_dump_json.assert_called_once_with()

    format_sse_event.assert_called_once_with(
        event="completed",
        data='{"type":"completed"}',
    )


@pytest.mark.asyncio
async def test_stream_analysis_ignores_unknown_event() -> None:
    """Vérifie qu'un type d'événement inconnu n'est pas envoyé au client."""

    request = build_request()
    payload = build_analysis_request()

    unknown_event = object()

    async def stream() -> AsyncIterator[object]:
        yield unknown_event

    service = MagicMock()
    service.stream_analysis = MagicMock(
        return_value=stream(),
    )

    response = await stream_analysis(
        request=request,
        payload=payload,
        service=service,
    )

    chunks = [chunk async for chunk in response.body_iterator]

    assert chunks == []
