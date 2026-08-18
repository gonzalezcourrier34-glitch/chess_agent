"""Tests unitaires du service de supervision."""

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
from app.core.config import settings
from app.core.exceptions import ApplicationNotReadyError
from app.schemas.common.enums import ServiceStatus
from app.services.analysis_service import AnalysisService
from app.services.healthcheck_service import (
    DEGRADED_STATUS,
    HEALTHY_STATUS,
    HealthcheckService,
)

# Types


ServiceMocks = dict[str, Any]


# Construction


@pytest.fixture
def service_mocks() -> ServiceMocks:
    """Construit les dépendances simulées du service."""

    return {
        "mongodb_service": cast(
            MongoDBService,
            MagicMock(spec=MongoDBService),
        ),
        "milvus_service": cast(
            MilvusService,
            MagicMock(spec=MilvusService),
        ),
        "embedding_service": cast(
            EmbeddingService,
            MagicMock(spec=EmbeddingService),
        ),
        "stockfish_service": cast(
            StockfishService,
            MagicMock(spec=StockfishService),
        ),
        "lichess_service": cast(
            LichessService,
            MagicMock(spec=LichessService),
        ),
        "youtube_service": cast(
            YoutubeService,
            MagicMock(spec=YoutubeService),
        ),
        "llm_service": cast(
            LLMService,
            MagicMock(spec=LLMService),
        ),
        "analysis_service": cast(
            AnalysisService,
            MagicMock(spec=AnalysisService),
        ),
    }


@pytest.fixture
def service(
    service_mocks: ServiceMocks,
) -> HealthcheckService:
    """Construit le service testé."""

    return HealthcheckService(
        mongodb_service=service_mocks["mongodb_service"],
        milvus_service=service_mocks["milvus_service"],
        embedding_service=service_mocks["embedding_service"],
        stockfish_service=service_mocks["stockfish_service"],
        lichess_service=service_mocks["lichess_service"],
        youtube_service=service_mocks["youtube_service"],
        llm_service=service_mocks["llm_service"],
        analysis_service=service_mocks["analysis_service"],
    )


def configure_ping(
    dependency: Any,
    *,
    result: bool = True,
) -> AsyncMock:
    """Configure le ping asynchrone d'une dépendance."""

    ping_mock = AsyncMock(
        return_value=result,
    )

    dependency.ping = ping_mock

    return ping_mock


def configure_all_pings(
    service_mocks: ServiceMocks,
    *,
    result: bool = True,
) -> dict[str, AsyncMock]:
    """Configure tous les contrôles de disponibilité."""

    return {
        name: configure_ping(
            dependency,
            result=result,
        )
        for name, dependency in service_mocks.items()
    }


# Vérification individuelle


@pytest.mark.asyncio
async def test_check_service_returns_true(
    service: HealthcheckService,
) -> None:
    """Vérifie un service disponible."""

    ping = AsyncMock(
        return_value=True,
    )

    result = await service._check_service(
        name="Test",
        ping_function=ping,
    )

    assert result is True

    ping.assert_awaited_once_with()


@pytest.mark.asyncio
async def test_check_service_returns_false(
    service: HealthcheckService,
) -> None:
    """Vérifie un service indisponible."""

    ping = AsyncMock(
        return_value=False,
    )

    result = await service._check_service(
        name="Test",
        ping_function=ping,
    )

    assert result is False

    ping.assert_awaited_once_with()


@pytest.mark.asyncio
async def test_check_service_converts_truthy_value(
    service: HealthcheckService,
) -> None:
    """Vérifie la normalisation booléenne du résultat."""

    ping = AsyncMock(
        return_value=1,
    )

    result = await service._check_service(
        name="Test",
        ping_function=ping,
    )

    assert result is True


@pytest.mark.asyncio
async def test_check_service_handles_exception(
    service: HealthcheckService,
) -> None:
    """Vérifie qu'une exception devient une indisponibilité."""

    ping = AsyncMock(
        side_effect=RuntimeError(
            "Service indisponible."
        ),
    )

    result = await service._check_service(
        name="Test",
        ping_function=ping,
    )

    assert result is False


# Vérification globale


@pytest.mark.asyncio
async def test_check_services_returns_all_services(
    service: HealthcheckService,
    service_mocks: ServiceMocks,
) -> None:
    """Vérifie le contrôle de tous les services."""

    configure_all_pings(
        service_mocks,
    )

    result = await service._check_services()

    assert result == {
        "mongodb": True,
        "milvus": True,
        "embedding": True,
        "stockfish": True,
        "lichess": True,
        "youtube": True,
        "llm": True,
        "langgraph": True,
    }


@pytest.mark.asyncio
async def test_check_services_preserves_unavailable_service(
    service: HealthcheckService,
    service_mocks: ServiceMocks,
) -> None:
    """Vérifie la présence d'un service indisponible."""

    configure_all_pings(
        service_mocks,
    )

    configure_ping(
        service_mocks["youtube_service"],
        result=False,
    )

    result = await service._check_services()

    assert result["youtube"] is False

    assert result["mongodb"] is True
    assert result["milvus"] is True
    assert result["embedding"] is True
    assert result["stockfish"] is True
    assert result["lichess"] is True
    assert result["llm"] is True
    assert result["langgraph"] is True


# Services critiques


@pytest.mark.asyncio
async def test_check_required_services_returns_required_services_only(
    service: HealthcheckService,
    service_mocks: ServiceMocks,
) -> None:
    """Vérifie le contrôle des seuls services critiques."""

    configure_all_pings(
        service_mocks,
    )

    result = await service._check_required_services()

    assert result == {
        "mongodb": True,
        "milvus": True,
        "embedding": True,
        "stockfish": True,
        "llm": True,
        "langgraph": True,
    }

    cast(
        AsyncMock,
        service_mocks["lichess_service"].ping,
    ).assert_not_awaited()

    cast(
        AsyncMock,
        service_mocks["youtube_service"].ping,
    ).assert_not_awaited()


@pytest.mark.asyncio
async def test_check_readiness_succeeds(
    service: HealthcheckService,
    service_mocks: ServiceMocks,
) -> None:
    """Vérifie une application prête."""

    configure_all_pings(
        service_mocks,
    )

    result = await service.check_readiness()

    assert result is None


@pytest.mark.asyncio
async def test_check_readiness_raises_when_required_service_is_unavailable(
    service: HealthcheckService,
    service_mocks: ServiceMocks,
) -> None:
    """Vérifie le refus de readiness si un service critique échoue."""

    configure_all_pings(
        service_mocks,
    )

    configure_ping(
        service_mocks["mongodb_service"],
        result=False,
    )

    with pytest.raises(
        ApplicationNotReadyError
    ):
        await service.check_readiness()


@pytest.mark.asyncio
async def test_check_readiness_accepts_optional_service_failure(
    service: HealthcheckService,
    service_mocks: ServiceMocks,
) -> None:
    """Vérifie qu'un service facultatif n'affecte pas la readiness."""

    configure_all_pings(
        service_mocks,
    )

    configure_ping(
        service_mocks["youtube_service"],
        result=False,
    )

    configure_ping(
        service_mocks["lichess_service"],
        result=False,
    )

    result = await service.check_readiness()

    assert result is None


# Statuts


@pytest.mark.parametrize(
    ("available", "expected"),
    [
        (
            True,
            ServiceStatus.AVAILABLE,
        ),
        (
            False,
            ServiceStatus.UNAVAILABLE,
        ),
    ],
)
def test_get_service_status(
    service: HealthcheckService,
    available: bool,
    expected: ServiceStatus,
) -> None:
    """Vérifie la conversion vers ServiceStatus."""

    assert (
        service._get_service_status(
            available
        )
        is expected
    )


def test_get_application_status_returns_healthy(
    service: HealthcheckService,
) -> None:
    """Vérifie le statut global sain."""

    services = {
        "mongodb": True,
        "milvus": True,
        "embedding": True,
        "stockfish": True,
        "lichess": False,
        "youtube": False,
        "llm": True,
        "langgraph": True,
    }

    result = service._get_application_status(
        services
    )

    assert result == HEALTHY_STATUS


@pytest.mark.parametrize(
    "failed_service",
    [
        "mongodb",
        "milvus",
        "embedding",
        "stockfish",
        "llm",
        "langgraph",
    ],
)
def test_get_application_status_returns_degraded(
    service: HealthcheckService,
    failed_service: str,
) -> None:
    """Vérifie la dégradation d'un service critique."""

    services = {
        "mongodb": True,
        "milvus": True,
        "embedding": True,
        "stockfish": True,
        "lichess": True,
        "youtube": True,
        "llm": True,
        "langgraph": True,
    }

    services[failed_service] = False

    result = service._get_application_status(
        services
    )

    assert result == DEGRADED_STATUS


def test_get_application_status_returns_degraded_if_required_key_missing(
    service: HealthcheckService,
) -> None:
    """Vérifie qu'un service critique absent est indisponible."""

    services = {
        "mongodb": True,
        "milvus": True,
        "embedding": True,
        "stockfish": True,
        "lichess": True,
        "youtube": True,
        "llm": True,
    }

    result = service._get_application_status(
        services
    )

    assert result == DEGRADED_STATUS


# Construction


def test_build_service_health_available(
    service: HealthcheckService,
) -> None:
    """Vérifie la santé d'un service disponible."""

    result = service._build_service_health(
        True
    )

    assert result.available is True
    assert result.status is ServiceStatus.AVAILABLE
    assert result.message is None


def test_build_service_health_unavailable(
    service: HealthcheckService,
) -> None:
    """Vérifie la santé d'un service indisponible."""

    result = service._build_service_health(
        False
    )

    assert result.available is False
    assert result.status is ServiceStatus.UNAVAILABLE
    assert result.message == "Service indisponible."


def test_build_response(
    service: HealthcheckService,
) -> None:
    """Vérifie la construction de la réponse complète."""

    services = {
        "mongodb": True,
        "milvus": True,
        "embedding": True,
        "stockfish": True,
        "lichess": False,
        "youtube": False,
        "llm": True,
        "langgraph": True,
    }

    result = service._build_response(
        services
    )

    assert result.status == HEALTHY_STATUS
    assert result.application == settings.app_name
    assert result.version == settings.app_version
    assert result.environment == settings.app_env
    assert result.embedding_model == settings.embedding_model
    assert (
        result.milvus_collection
        == settings.milvus_collection_name
    )

    assert result.services.mongodb.available is True
    assert result.services.milvus.available is True
    assert result.services.embedding.available is True
    assert result.services.stockfish.available is True
    assert result.services.lichess.available is False
    assert result.services.youtube.available is False
    assert result.services.llm.available is True
    assert result.services.langgraph.available is True


# Supervision


@pytest.mark.asyncio
async def test_check_returns_healthy_response(
    service: HealthcheckService,
    service_mocks: ServiceMocks,
) -> None:
    """Vérifie un healthcheck global sain."""

    configure_all_pings(
        service_mocks,
    )

    result = await service.check()

    assert result.status == HEALTHY_STATUS

    assert result.services.mongodb.available is True
    assert result.services.milvus.available is True
    assert result.services.embedding.available is True
    assert result.services.stockfish.available is True
    assert result.services.lichess.available is True
    assert result.services.youtube.available is True
    assert result.services.llm.available is True
    assert result.services.langgraph.available is True


@pytest.mark.asyncio
async def test_check_returns_healthy_with_optional_service_unavailable(
    service: HealthcheckService,
    service_mocks: ServiceMocks,
) -> None:
    """Vérifie qu'un service facultatif ne dégrade pas l'application."""

    configure_all_pings(
        service_mocks,
    )

    configure_ping(
        service_mocks["youtube_service"],
        result=False,
    )

    result = await service.check()

    assert result.status == HEALTHY_STATUS
    assert result.services.youtube.available is False


@pytest.mark.asyncio
async def test_check_returns_degraded_response(
    service: HealthcheckService,
    service_mocks: ServiceMocks,
) -> None:
    """Vérifie un healthcheck global dégradé."""

    configure_all_pings(
        service_mocks,
    )

    configure_ping(
        service_mocks["milvus_service"],
        result=False,
    )

    result = await service.check()

    assert result.status == DEGRADED_STATUS
    assert result.services.milvus.available is False


@pytest.mark.asyncio
async def test_check_handles_ping_exception(
    service: HealthcheckService,
    service_mocks: ServiceMocks,
) -> None:
    """Vérifie qu'une exception de ping n'interrompt pas le healthcheck."""

    configure_all_pings(
        service_mocks,
    )

    service_mocks["stockfish_service"].ping = AsyncMock(
        side_effect=RuntimeError(
            "Stockfish indisponible."
        ),
    )

    result = await service.check()

    assert result.status == DEGRADED_STATUS
    assert result.services.stockfish.available is False


# Disponibilité


def test_is_ready_returns_true(
    service: HealthcheckService,
) -> None:
    """Vérifie que le service est correctement configuré."""

    assert service.is_ready() is True


def test_is_ready_returns_false_with_missing_dependency(
    service_mocks: ServiceMocks,
) -> None:
    """Vérifie une configuration incomplète."""

    service = HealthcheckService(
        mongodb_service=service_mocks["mongodb_service"],
        milvus_service=service_mocks["milvus_service"],
        embedding_service=service_mocks["embedding_service"],
        stockfish_service=service_mocks["stockfish_service"],
        lichess_service=service_mocks["lichess_service"],
        youtube_service=service_mocks["youtube_service"],
        llm_service=service_mocks["llm_service"],
        analysis_service=cast(
            AnalysisService,
            None,
        ),
    )

    assert service.is_ready() is False


# Santé


@pytest.mark.asyncio
async def test_ping_returns_true(
    service: HealthcheckService,
) -> None:
    """Vérifie le ping du service."""

    assert await service.ping() is True


@pytest.mark.asyncio
async def test_health_returns_service_status(
    service: HealthcheckService,
) -> None:
    """Vérifie les informations de santé du service."""

    result = await service.health()

    assert result == {
        "service": "healthcheck",
        "available": True,
        "is_ready": True,
    }