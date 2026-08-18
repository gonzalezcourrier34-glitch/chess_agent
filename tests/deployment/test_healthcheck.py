"""Tests du healthcheck déployé de Chess Agent."""

from __future__ import annotations

import httpx
import pytest

# Tests

@pytest.mark.deployment
def test_healthcheck_is_available(
    backend_url: str,
) -> None:
    """Vérifie que le healthcheck répond."""

    response = httpx.get(
        f"{backend_url}/api/v1/healthcheck",
        timeout=10.0,
    )

    assert response.status_code == 200


@pytest.mark.deployment
def test_healthcheck_returns_json(
    backend_url: str,
) -> None:
    """Vérifie que le healthcheck retourne un objet JSON."""

    response = httpx.get(
        f"{backend_url}/api/v1/healthcheck",
        timeout=10.0,
    )

    assert response.status_code == 200

    payload = response.json()

    assert isinstance(payload, dict)