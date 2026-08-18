"""Tests de disponibilité du frontend Chess Agent."""

from __future__ import annotations

import httpx
import pytest


# Tests

@pytest.mark.deployment
def test_frontend_is_available(
    frontend_url: str,
) -> None:
    """Vérifie que le frontend Angular répond."""

    response = httpx.get(
        frontend_url,
        timeout=10.0,
        follow_redirects=True,
    )

    assert response.status_code == 200


@pytest.mark.deployment
def test_frontend_returns_html(
    frontend_url: str,
) -> None:
    """Vérifie que le frontend retourne un document HTML."""

    response = httpx.get(
        frontend_url,
        timeout=10.0,
        follow_redirects=True,
    )

    content_type = response.headers.get(
        "content-type",
        "",
    )

    assert "text/html" in content_type.lower()