"""Tests unitaires du conteneur applicatif Chess Agent."""

from __future__ import annotations

from typing import Any, cast
from unittest.mock import AsyncMock, MagicMock

import pytest

from app.adapters.embedding_service import EmbeddingService
from app.adapters.lichess_service import LichessService
from app.adapters.llm_service import LLMService
from app.adapters.milvus_service import MilvusService
from app.adapters.mongodb_service import MongoDBService
from app.adapters.stockfish_service import StockfishService
from app.adapters.youtube_service import YoutubeService
from app.agent.graph import GraphDependencies
from app.core.container import (
    ApplicationContainer,
    _ping_service,
    create_application_container,
)
from app.services.analysis_service import AnalysisService
from app.services.chess_service import ChessService
from app.services.healthcheck_service import HealthcheckService
from app.services.vector_search_service import VectorSearchService


# Helpers


def build_container() -> ApplicationContainer:
    """Construit un conteneur avec des dépendances simulées."""

    return ApplicationContainer(
        chess=cast(
            ChessService,
            MagicMock(spec=ChessService),
        ),
        vector_search=cast(
            VectorSearchService,
            MagicMock(spec=VectorSearchService),
        ),
        stockfish=cast(
            StockfishService,
            MagicMock(spec=StockfishService),
        ),
        lichess=cast(
            LichessService,
            MagicMock(spec=LichessService),
        ),
        embedding=cast(
            EmbeddingService,
            MagicMock(spec=EmbeddingService),
        ),
        milvus=cast(
            MilvusService,
            MagicMock(spec=MilvusService),
        ),
        mongodb=cast(
            MongoDBService,
            MagicMock(spec=MongoDBService),
        ),
        llm=cast(
            LLMService,
            MagicMock(spec=LLMService),
        ),
        youtube=cast(
            YoutubeService,
            MagicMock(spec=YoutubeService),
        ),
    )


def configure_ping(
    service: Any,
    *,
    result: bool = True,
) -> AsyncMock:
    """Configure le ping asynchrone d'un service simulé."""

    ping = AsyncMock(
        return_value=result,
    )

    service.ping = ping

    return ping


# _ping_service


@pytest.mark.asyncio
async def test_ping_service_returns_service_status() -> None:
    """Vérifie la remontée du résultat d'un ping."""

    service = MagicMock()

    service.ping = AsyncMock(
        return_value=True,
    )

    result = await _ping_service(
        "test",
        service,
    )

    assert result == (
        "test",
        True,
    )

    service.ping.assert_awaited_once_with()


@pytest.mark.asyncio
async def test_ping_service_returns_false() -> None:
    """Vérifie un service indisponible."""

    service = MagicMock()

    service.ping = AsyncMock(
        return_value=False,
    )

    result = await _ping_service(
        "test",
        service,
    )

    assert result == (
        "test",
        False,
    )


@pytest.mark.asyncio
async def test_ping_service_handles_exception() -> None:
    """Vérifie qu'une exception de ping n'interrompt pas le contrôle."""

    service = MagicMock()

    service.ping = AsyncMock(
        side_effect=RuntimeError(
            "ping failure"
        ),
    )

    result = await _ping_service(
        "test",
        service,
    )

    assert result == (
        "test",
        False,
    )


# Dépendances LangGraph


def test_to_graph_dependencies() -> None:
    """Vérifie la construction des dépendances du graphe."""

    container = build_container()

    dependencies = (
        container.to_graph_dependencies()
    )

    assert isinstance(
        dependencies,
        GraphDependencies,
    )

    assert (
        dependencies.chess_service
        is container.chess
    )

    assert (
        dependencies.stockfish_service
        is container.stockfish
    )

    assert (
        dependencies.lichess_service
        is container.lichess
    )

    assert (
        dependencies.embedding_service
        is container.embedding
    )

    assert (
        dependencies.milvus_service
        is container.milvus
    )

    assert (
        dependencies.vector_search_service
        is container.vector_search
    )

    assert (
        dependencies.llm_service
        is container.llm
    )

    assert (
        dependencies.youtube_service
        is container.youtube
    )

    assert (
        dependencies.mongodb_service
        is container.mongodb
    )


# Construction du workflow


def test_build_graph(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Vérifie la construction complète du workflow."""

    container = build_container()

    graph = MagicMock()

    analysis = MagicMock(
        spec=AnalysisService,
    )

    healthcheck = MagicMock(
        spec=HealthcheckService,
    )

    build_agent_graph = MagicMock(
        return_value=graph,
    )

    analysis_class = MagicMock(
        return_value=analysis,
    )

    healthcheck_class = MagicMock(
        return_value=healthcheck,
    )

    monkeypatch.setattr(
        "app.core.container."
        "build_agent_graph",
        build_agent_graph,
    )

    monkeypatch.setattr(
        "app.core.container."
        "AnalysisService",
        analysis_class,
    )

    monkeypatch.setattr(
        "app.core.container."
        "HealthcheckService",
        healthcheck_class,
    )

    container.build_graph()

    assert container.agent_graph is graph
    assert container.analysis is analysis
    assert container.healthcheck is healthcheck

    build_agent_graph.assert_called_once_with()

    analysis_class.assert_called_once()

    analysis_call = (
        analysis_class.call_args
    )

    assert (
        analysis_call.kwargs["graph"]
        is graph
    )

    assert isinstance(
        analysis_call.kwargs["dependencies"],
        GraphDependencies,
    )

    healthcheck_class.assert_called_once_with(
        mongodb_service=container.mongodb,
        milvus_service=container.milvus,
        embedding_service=container.embedding,
        stockfish_service=container.stockfish,
        lichess_service=container.lichess,
        youtube_service=container.youtube,
        llm_service=container.llm,
        analysis_service=analysis,
    )


def test_build_graph_returns_when_already_ready(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Vérifie qu'un conteneur prêt n'est pas reconstruit."""

    container = build_container()

    container.agent_graph = MagicMock()
    container.analysis = MagicMock(
        spec=AnalysisService,
    )
    container.healthcheck = MagicMock(
        spec=HealthcheckService,
    )

    build_agent_graph = MagicMock()

    monkeypatch.setattr(
        "app.core.container."
        "build_agent_graph",
        build_agent_graph,
    )

    container.build_graph()

    build_agent_graph.assert_not_called()


def test_build_graph_replaces_partial_state(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Vérifie la reconstruction depuis un état partiel."""

    container = build_container()

    old_graph = MagicMock()

    container.agent_graph = old_graph
    container.analysis = None
    container.healthcheck = None

    new_graph = MagicMock()
    analysis = MagicMock(
        spec=AnalysisService,
    )
    healthcheck = MagicMock(
        spec=HealthcheckService,
    )

    monkeypatch.setattr(
        "app.core.container."
        "build_agent_graph",
        MagicMock(
            return_value=new_graph,
        ),
    )

    monkeypatch.setattr(
        "app.core.container."
        "AnalysisService",
        MagicMock(
            return_value=analysis,
        ),
    )

    monkeypatch.setattr(
        "app.core.container."
        "HealthcheckService",
        MagicMock(
            return_value=healthcheck,
        ),
    )

    container.build_graph()

    assert (
        container.agent_graph
        is new_graph
    )

    assert (
        container.analysis
        is analysis
    )

    assert (
        container.healthcheck
        is healthcheck
    )


def test_build_graph_is_atomic_when_graph_creation_fails(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Vérifie qu'une erreur ne publie aucun composant partiel."""

    container = build_container()

    monkeypatch.setattr(
        "app.core.container."
        "build_agent_graph",
        MagicMock(
            side_effect=RuntimeError(
                "graph failure"
            ),
        ),
    )

    with pytest.raises(
        RuntimeError,
        match="graph failure",
    ):
        container.build_graph()

    assert container.agent_graph is None
    assert container.analysis is None
    assert container.healthcheck is None


def test_build_graph_is_atomic_when_analysis_creation_fails(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Vérifie l'atomicité si AnalysisService échoue."""

    container = build_container()

    graph = MagicMock()

    monkeypatch.setattr(
        "app.core.container."
        "build_agent_graph",
        MagicMock(
            return_value=graph,
        ),
    )

    monkeypatch.setattr(
        "app.core.container."
        "AnalysisService",
        MagicMock(
            side_effect=RuntimeError(
                "analysis failure"
            ),
        ),
    )

    with pytest.raises(
        RuntimeError,
        match="analysis failure",
    ):
        container.build_graph()

    assert container.agent_graph is None
    assert container.analysis is None
    assert container.healthcheck is None


def test_build_graph_is_atomic_when_healthcheck_creation_fails(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Vérifie l'atomicité si HealthcheckService échoue."""

    container = build_container()

    graph = MagicMock()

    analysis = MagicMock(
        spec=AnalysisService,
    )

    monkeypatch.setattr(
        "app.core.container."
        "build_agent_graph",
        MagicMock(
            return_value=graph,
        ),
    )

    monkeypatch.setattr(
        "app.core.container."
        "AnalysisService",
        MagicMock(
            return_value=analysis,
        ),
    )

    monkeypatch.setattr(
        "app.core.container."
        "HealthcheckService",
        MagicMock(
            side_effect=RuntimeError(
                "healthcheck failure"
            ),
        ),
    )

    with pytest.raises(
        RuntimeError,
        match="healthcheck failure",
    ):
        container.build_graph()

    assert container.agent_graph is None
    assert container.analysis is None
    assert container.healthcheck is None


# Destruction


def test_destroy_graph() -> None:
    """Vérifie la libération des composants du workflow."""

    container = build_container()

    container.agent_graph = MagicMock()
    container.analysis = MagicMock(
        spec=AnalysisService,
    )
    container.healthcheck = MagicMock(
        spec=HealthcheckService,
    )

    container.destroy_graph()

    assert container.agent_graph is None
    assert container.analysis is None
    assert container.healthcheck is None


def test_destroy_graph_is_idempotent() -> None:
    """Vérifie que la destruction peut être répétée."""

    container = build_container()

    container.destroy_graph()
    container.destroy_graph()

    assert container.agent_graph is None
    assert container.analysis is None
    assert container.healthcheck is None


# État du workflow


def test_is_graph_ready_false() -> None:
    """Vérifie l'absence du graphe."""

    container = build_container()

    assert (
        container.is_graph_ready()
        is False
    )


def test_is_graph_ready_true() -> None:
    """Vérifie un graphe présent."""

    container = build_container()

    container.agent_graph = MagicMock()

    assert (
        container.is_graph_ready()
        is True
    )


def test_is_analysis_ready_false() -> None:
    """Vérifie l'absence du service d'analyse."""

    container = build_container()

    assert (
        container.is_analysis_ready()
        is False
    )


def test_is_analysis_ready_true() -> None:
    """Vérifie le service d'analyse présent."""

    container = build_container()

    container.analysis = MagicMock(
        spec=AnalysisService,
    )

    assert (
        container.is_analysis_ready()
        is True
    )


def test_is_healthcheck_ready_false() -> None:
    """Vérifie l'absence du healthcheck."""

    container = build_container()

    assert (
        container.is_healthcheck_ready()
        is False
    )


def test_is_healthcheck_ready_true() -> None:
    """Vérifie le healthcheck présent."""

    container = build_container()

    container.healthcheck = MagicMock(
        spec=HealthcheckService,
    )

    assert (
        container.is_healthcheck_ready()
        is True
    )


def test_is_ready_false() -> None:
    """Vérifie un conteneur incomplet."""

    container = build_container()

    assert container.is_ready() is False


def test_is_ready_true() -> None:
    """Vérifie un conteneur complètement prêt."""

    container = build_container()

    container.agent_graph = MagicMock()

    container.analysis = MagicMock(
        spec=AnalysisService,
    )

    container.healthcheck = MagicMock(
        spec=HealthcheckService,
    )

    assert container.is_ready() is True


def test_is_ready_false_when_only_graph_exists() -> None:
    """Vérifie qu'un seul composant ne suffit pas."""

    container = build_container()

    container.agent_graph = MagicMock()

    assert container.is_ready() is False


# Santé


@pytest.mark.asyncio
async def test_health_with_all_services_available() -> None:
    """Vérifie l'état complet lorsque tous les services répondent."""

    container = build_container()

    for service in (
        container.mongodb,
        container.milvus,
        container.embedding,
        container.vector_search,
        container.stockfish,
        container.lichess,
        container.youtube,
        container.llm,
    ):
        configure_ping(
            service,
            result=True,
        )

    container.agent_graph = MagicMock()
    container.analysis = MagicMock(
        spec=AnalysisService,
    )
    container.healthcheck = MagicMock(
        spec=HealthcheckService,
    )

    result = await container.health()

    assert result == {
        "mongodb": True,
        "milvus": True,
        "embedding": True,
        "vector_search": True,
        "stockfish": True,
        "lichess": True,
        "youtube": True,
        "llm": True,
        "graph": True,
        "analysis": True,
        "healthcheck": True,
    }


@pytest.mark.asyncio
async def test_health_with_services_unavailable() -> None:
    """Vérifie les indisponibilités techniques."""

    container = build_container()

    configure_ping(
        container.mongodb,
        result=False,
    )

    configure_ping(
        container.milvus,
        result=True,
    )

    configure_ping(
        container.embedding,
        result=False,
    )

    configure_ping(
        container.vector_search,
        result=True,
    )

    configure_ping(
        container.stockfish,
        result=True,
    )

    configure_ping(
        container.lichess,
        result=False,
    )

    configure_ping(
        container.youtube,
        result=True,
    )

    configure_ping(
        container.llm,
        result=False,
    )

    result = await container.health()

    assert result == {
        "mongodb": False,
        "milvus": True,
        "embedding": False,
        "vector_search": True,
        "stockfish": True,
        "lichess": False,
        "youtube": True,
        "llm": False,
        "graph": False,
        "analysis": False,
        "healthcheck": False,
    }


@pytest.mark.asyncio
async def test_health_handles_ping_exception() -> None:
    """Vérifie qu'une exception d'un service reste localisée."""

    container = build_container()

    for service in (
        container.mongodb,
        container.milvus,
        container.embedding,
        container.vector_search,
        container.stockfish,
        container.lichess,
        container.youtube,
        container.llm,
    ):
        configure_ping(
            service,
            result=True,
        )

    container.mongodb.ping = AsyncMock(
        side_effect=RuntimeError(
            "mongodb failure"
        ),
    )

    result = await container.health()

    assert result["mongodb"] is False

    assert result["milvus"] is True
    assert result["embedding"] is True
    assert result["vector_search"] is True
    assert result["stockfish"] is True
    assert result["lichess"] is True
    assert result["youtube"] is True
    assert result["llm"] is True


# Construction publique


def test_create_application_container(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Vérifie l'assemblage du conteneur applicatif."""

    chess = MagicMock(
        spec=ChessService,
    )

    stockfish = MagicMock(
        spec=StockfishService,
    )

    lichess = MagicMock(
        spec=LichessService,
    )

    embedding = MagicMock(
        spec=EmbeddingService,
    )

    milvus = MagicMock(
        spec=MilvusService,
    )

    vector_search = MagicMock(
        spec=VectorSearchService,
    )

    llm = MagicMock(
        spec=LLMService,
    )

    youtube = MagicMock(
        spec=YoutubeService,
    )

    mongodb = MagicMock(
        spec=MongoDBService,
    )

    chess_class = MagicMock(
        return_value=chess,
    )

    stockfish_class = MagicMock(
        return_value=stockfish,
    )

    lichess_class = MagicMock(
        return_value=lichess,
    )

    embedding_class = MagicMock(
        return_value=embedding,
    )

    milvus_class = MagicMock(
        return_value=milvus,
    )

    vector_search_class = MagicMock(
        return_value=vector_search,
    )

    llm_class = MagicMock(
        return_value=llm,
    )

    youtube_class = MagicMock(
        return_value=youtube,
    )

    mongodb_class = MagicMock(
        return_value=mongodb,
    )

    monkeypatch.setattr(
        "app.core.container.ChessService",
        chess_class,
    )

    monkeypatch.setattr(
        "app.core.container.StockfishService",
        stockfish_class,
    )

    monkeypatch.setattr(
        "app.core.container.LichessService",
        lichess_class,
    )

    monkeypatch.setattr(
        "app.core.container.EmbeddingService",
        embedding_class,
    )

    monkeypatch.setattr(
        "app.core.container.MilvusService",
        milvus_class,
    )

    monkeypatch.setattr(
        "app.core.container.VectorSearchService",
        vector_search_class,
    )

    monkeypatch.setattr(
        "app.core.container.LLMService",
        llm_class,
    )

    monkeypatch.setattr(
        "app.core.container.YoutubeService",
        youtube_class,
    )

    monkeypatch.setattr(
        "app.core.container.MongoDBService",
        mongodb_class,
    )

    container = (
        create_application_container()
    )

    assert isinstance(
        container,
        ApplicationContainer,
    )

    assert container.chess is chess
    assert container.stockfish is stockfish
    assert container.lichess is lichess
    assert container.embedding is embedding
    assert container.milvus is milvus
    assert container.vector_search is vector_search
    assert container.llm is llm
    assert container.youtube is youtube
    assert container.mongodb is mongodb

    assert container.agent_graph is None
    assert container.analysis is None
    assert container.healthcheck is None
    assert container.resource_manager is None

    chess_class.assert_called_once_with()
    stockfish_class.assert_called_once_with()
    lichess_class.assert_called_once_with()
    embedding_class.assert_called_once_with()
    milvus_class.assert_called_once_with()
    llm_class.assert_called_once_with()
    youtube_class.assert_called_once_with()
    mongodb_class.assert_called_once_with()

    vector_search_class.assert_called_once_with(
        embedding_service=embedding,
        milvus_service=milvus,
    )