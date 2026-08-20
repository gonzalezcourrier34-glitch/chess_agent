"""Tests unitaires des routes de recherche vectorielle."""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock

import pytest
from app.api.v1.endpoints.route_vector_search import search_documents
from app.schemas.analysis.search import (
    VectorSearchRequest,
    VectorSearchResponse,
)

# Configuration

QUERY = "Ruy Lopez strategic ideas"


# Helpers


def build_search_request() -> VectorSearchRequest:
    """Construit une requête de recherche vectorielle valide."""

    return VectorSearchRequest(
        query=QUERY,
    )


# Recherche vectorielle


@pytest.mark.asyncio
async def test_search_documents_delegates_to_vector_search_service() -> None:
    """Vérifie que la route délègue la recherche au service vectoriel."""

    payload = build_search_request()

    expected_response = MagicMock(
        spec=VectorSearchResponse,
    )

    service = MagicMock()
    service.search = AsyncMock(
        return_value=expected_response,
    )

    result = await search_documents(
        payload=payload,
        service=service,
    )

    assert result is expected_response

    service.search.assert_awaited_once_with(
        payload,
    )


@pytest.mark.asyncio
async def test_search_documents_propagates_service_error() -> None:
    """Vérifie que la route ne masque pas une erreur de recherche."""

    payload = build_search_request()

    service = MagicMock()
    service.search = AsyncMock(
        side_effect=RuntimeError(
            "vector search failure",
        ),
    )

    with pytest.raises(
        RuntimeError,
        match="vector search failure",
    ):
        await search_documents(
            payload=payload,
            service=service,
        )

    service.search.assert_awaited_once_with(
        payload,
    )
