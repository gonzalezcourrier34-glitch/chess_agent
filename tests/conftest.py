"""Configuration des tests de déploiement de Chess Agent."""

from __future__ import annotations

import os

import pytest

# Configuration

DEFAULT_BACKEND_URL = "http://localhost:8000"
DEFAULT_FRONTEND_URL = "http://localhost:4200"


# Fixtures


@pytest.fixture(scope="session")
def backend_url() -> str:
    """Retourne l'URL du backend déployé."""

    return os.getenv(
        "CHESS_AGENT_BACKEND_URL",
        DEFAULT_BACKEND_URL,
    ).rstrip("/")


@pytest.fixture(scope="session")
def frontend_url() -> str:
    """Retourne l'URL du frontend déployé."""

    return os.getenv(
        "CHESS_AGENT_FRONTEND_URL",
        DEFAULT_FRONTEND_URL,
    ).rstrip("/")
