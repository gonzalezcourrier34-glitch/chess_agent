"""Tests unitaires des dépendances d'injection des services."""

from __future__ import annotations

from types import SimpleNamespace
from unittest.mock import MagicMock

import pytest
from app.adapters.embedding_service import EmbeddingService
from app.adapters.lichess_service import LichessService
from app.adapters.llm_service import LLMService
from app.adapters.milvus_service import MilvusService
from app.adapters.mongodb_service import MongoDBService
from app.adapters.stockfish_service import StockfishService
from app.adapters.youtube_service import YoutubeService
from app.api.v1.dependencies.services import (
    get_analysis_service,
    get_application_container,
    get_chess_service,
    get_embedding_service,
    get_healthcheck_service,
    get_lichess_service,
    get_llm_service,
    get_milvus_service,
    get_mongodb_service,
    get_stockfish_service,
    get_vector_search_service,
    get_youtube_service,
)
from app.core.container import ApplicationContainer
from app.core.exceptions import ConfigurationError
from app.services.analysis_service import AnalysisService
from app.services.chess_service import ChessService
from app.services.healthcheck_service import HealthcheckService
from app.services.vector_search_service import VectorSearchService
from fastapi import Request

# Helpers


def build_container() -> ApplicationContainer:
    """Construit un conteneur minimal sans initialiser ses services."""

    return object.__new__(
        ApplicationContainer,
    )


def build_request(
    container: object | None,
) -> Request:
    """Construit une requête FastAPI contenant un état applicatif."""

    request = MagicMock(
        spec=Request,
    )

    request.app.state = SimpleNamespace(
        container=container,
    )

    return request


# Conteneur


def test_get_application_container_returns_initialized_container() -> None:
    """Vérifie la récupération du conteneur applicatif."""

    container = build_container()
    request = build_request(
        container,
    )

    result = get_application_container(
        request,
    )

    assert result is container


def test_get_application_container_rejects_missing_container() -> None:
    """Vérifie le rejet d'un conteneur absent."""

    request = build_request(
        None,
    )

    with pytest.raises(
        ConfigurationError,
    ):
        get_application_container(
            request,
        )


def test_get_application_container_rejects_invalid_container() -> None:
    """Vérifie le rejet d'un objet qui n'est pas un conteneur."""

    request = build_request(
        object(),
    )

    with pytest.raises(
        ConfigurationError,
    ):
        get_application_container(
            request,
        )


# Service d'analyse


def test_get_analysis_service_returns_service() -> None:
    """Vérifie la récupération du service d'analyse."""

    container = build_container()
    service = MagicMock(
        spec=AnalysisService,
    )

    container.analysis = service

    result = get_analysis_service(
        container,
    )

    assert result is service


def test_get_analysis_service_rejects_uninitialized_service() -> None:
    """Vérifie le rejet d'un service d'analyse absent."""

    container = build_container()
    container.analysis = None

    with pytest.raises(
        ConfigurationError,
    ):
        get_analysis_service(
            container,
        )


# Service échiquéen


def test_get_chess_service_returns_service() -> None:
    """Vérifie la récupération du service échiquéen."""

    container = build_container()
    service = MagicMock(
        spec=ChessService,
    )

    container.chess = service

    result = get_chess_service(
        container,
    )

    assert result is service


# Stockfish


def test_get_stockfish_service_returns_service() -> None:
    """Vérifie la récupération du service Stockfish."""

    container = build_container()
    service = MagicMock(
        spec=StockfishService,
    )

    container.stockfish = service

    result = get_stockfish_service(
        container,
    )

    assert result is service


# Lichess


def test_get_lichess_service_returns_service() -> None:
    """Vérifie la récupération du service Lichess."""

    container = build_container()
    service = MagicMock(
        spec=LichessService,
    )

    container.lichess = service

    result = get_lichess_service(
        container,
    )

    assert result is service


# Embeddings


def test_get_embedding_service_returns_service() -> None:
    """Vérifie la récupération du service d'embeddings."""

    container = build_container()
    service = MagicMock(
        spec=EmbeddingService,
    )

    container.embedding = service

    result = get_embedding_service(
        container,
    )

    assert result is service


# Milvus


def test_get_milvus_service_returns_service() -> None:
    """Vérifie la récupération du service Milvus."""

    container = build_container()
    service = MagicMock(
        spec=MilvusService,
    )

    container.milvus = service

    result = get_milvus_service(
        container,
    )

    assert result is service


# Recherche vectorielle


def test_get_vector_search_service_returns_service() -> None:
    """Vérifie la récupération du service de recherche vectorielle."""

    container = build_container()
    service = MagicMock(
        spec=VectorSearchService,
    )

    container.vector_search = service

    result = get_vector_search_service(
        container,
    )

    assert result is service


# LLM


def test_get_llm_service_returns_service() -> None:
    """Vérifie la récupération du service LLM."""

    container = build_container()
    service = MagicMock(
        spec=LLMService,
    )

    container.llm = service

    result = get_llm_service(
        container,
    )

    assert result is service


# YouTube


def test_get_youtube_service_returns_service() -> None:
    """Vérifie la récupération du service YouTube."""

    container = build_container()
    service = MagicMock(
        spec=YoutubeService,
    )

    container.youtube = service

    result = get_youtube_service(
        container,
    )

    assert result is service


# MongoDB


def test_get_mongodb_service_returns_service() -> None:
    """Vérifie la récupération du service MongoDB."""

    container = build_container()
    service = MagicMock(
        spec=MongoDBService,
    )

    container.mongodb = service

    result = get_mongodb_service(
        container,
    )

    assert result is service


# Supervision


def test_get_healthcheck_service_returns_service() -> None:
    """Vérifie la récupération du service de supervision."""

    container = build_container()
    service = MagicMock(
        spec=HealthcheckService,
    )

    container.healthcheck = service

    result = get_healthcheck_service(
        container,
    )

    assert result is service


def test_get_healthcheck_service_rejects_uninitialized_service() -> None:
    """Vérifie le rejet d'un service de supervision absent."""

    container = build_container()
    container.healthcheck = None

    with pytest.raises(
        ConfigurationError,
    ):
        get_healthcheck_service(
            container,
        )
