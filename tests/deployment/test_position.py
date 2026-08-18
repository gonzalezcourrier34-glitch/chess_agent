"""Tests de validation d'une position déployée."""

from __future__ import annotations

import httpx
import pytest

# Constantes

STARTING_FEN = (
    "rnbqkbnr/pppppppp/8/8/8/8/"
    "PPPPPPPP/RNBQKBNR w KQkq - 0 1"
)


# Tests

@pytest.mark.deployment
def test_position_validation_accepts_valid_fen(
    backend_url: str,
) -> None:
    """Vérifie qu'une FEN valide est acceptée."""

    response = httpx.post(
        f"{backend_url}/api/v1/position/validate",
        json={
            "fen": STARTING_FEN,
        },
        timeout=10.0,
    )

    assert response.status_code == 200


@pytest.mark.deployment
def test_position_validation_rejects_invalid_fen(
    backend_url: str,
) -> None:
    """Vérifie qu'une FEN invalide est rejetée."""

    response = httpx.post(
        f"{backend_url}/api/v1/position/validate",
        json={
            "fen": "invalid-fen",
        },
        timeout=10.0,
    )

    assert response.status_code >= 400