"""Tests de supervision des services déployés."""

from __future__ import annotations

import httpx
import pytest

# Tests


@pytest.mark.deployment
def test_services_endpoint_is_available(
    backend_url: str,
) -> None:
    """Vérifie que l'endpoint de supervision répond."""

    response = httpx.get(
        f"{backend_url}/api/v1/services",
        timeout=15.0,
    )

    assert response.status_code == 200


@pytest.mark.deployment
def test_services_endpoint_returns_json(
    backend_url: str,
) -> None:
    """Vérifie que la supervision retourne du JSON."""

    response = httpx.get(
        f"{backend_url}/api/v1/services",
        timeout=15.0,
    )

    assert response.status_code == 200

    payload = response.json()

    assert isinstance(
        payload,
        (dict, list),
    )
