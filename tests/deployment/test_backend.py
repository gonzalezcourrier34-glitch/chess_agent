"""Tests de disponibilité du backend Chess Agent."""

from __future__ import annotations

import httpx
import pytest


# Tests

@pytest.mark.deployment
def test_backend_is_available(
    backend_url: str,
) -> None:
    """Vérifie que le backend FastAPI répond."""

    response = httpx.get(
        f"{backend_url}/",
        timeout=10.0,
        follow_redirects=True,
    )

    assert response.status_code == 200


@pytest.mark.deployment
def test_openapi_is_available(
    backend_url: str,
) -> None:
    """Vérifie que le schéma OpenAPI est disponible."""

    response = httpx.get(
        f"{backend_url}/openapi.json",
        timeout=10.0,
    )

    assert response.status_code == 200

    payload = response.json()

    assert isinstance(payload, dict)
    assert "openapi" in payload
    assert "paths" in payload