"""Tests unitaires du cycle de vie applicatif."""

from __future__ import annotations

from asyncio import CancelledError
from typing import Any, cast
from unittest.mock import AsyncMock, MagicMock

import pytest
from app.core.container import ApplicationContainer
from app.core.exceptions import (
    ResourceHealthError,
    ResourceInitializationError,
)
from app.core.lifespan import (
    ManagedResource,
    ResourceManager,
    create_resource_manager,
    embedding_health,
    initialize_embedding,
    initialize_llm,
    initialize_milvus,
    initialize_mongodb,
    initialize_stockfish,
    initialize_workflow,
    lichess_health,
    lifespan,
    llm_health,
    milvus_health,
    mongodb_health,
    no_initialize,
    no_shutdown,
    shutdown_embedding,
    shutdown_lichess,
    shutdown_llm,
    shutdown_milvus,
    shutdown_mongodb,
    shutdown_stockfish,
    shutdown_workflow,
    shutdown_youtube,
    stockfish_health,
    workflow_health,
    youtube_health,
)
from fastapi import FastAPI

# Helpers


def build_container() -> ApplicationContainer:
    """Construit un conteneur simulé."""

    container = MagicMock(
        spec=ApplicationContainer,
    )

    container.mongodb = MagicMock()
    container.embedding = MagicMock()
    container.milvus = MagicMock()
    container.stockfish = MagicMock()
    container.lichess = MagicMock()
    container.youtube = MagicMock()
    container.llm = MagicMock()

    container.build_graph = MagicMock()
    container.destroy_graph = MagicMock()
    container.is_ready = MagicMock(
        return_value=True,
    )

    container.resource_manager = None

    return cast(
        ApplicationContainer,
        container,
    )


def build_resource(
    *,
    name: str = "Test",
    required: bool = True,
    initialize_result: None = None,
    health_result: bool = True,
) -> ManagedResource:
    """Construit une ressource simulée."""

    initialize = AsyncMock(
        return_value=initialize_result,
    )

    shutdown = AsyncMock()

    health = AsyncMock(
        return_value=health_result,
    )

    return ManagedResource(
        name=name,
        initialize=initialize,
        shutdown=shutdown,
        health=health,
        required=required,
    )


# ManagedResource


def test_managed_resource_defaults() -> None:
    """Vérifie les valeurs par défaut."""

    resource = build_resource()

    assert resource.required is True
    assert resource.initialized is False


# ResourceManager construction


def test_resource_manager_starts_empty() -> None:
    """Vérifie un gestionnaire sans ressource."""

    manager = ResourceManager(build_container())

    assert manager.resources == ()


def test_register_resource() -> None:
    """Vérifie l'enregistrement d'une ressource."""

    manager = ResourceManager(build_container())

    resource = build_resource()

    manager.register(resource)

    assert manager.resources == (resource,)


def test_register_rejects_duplicate_name() -> None:
    """Vérifie l'unicité du nom des ressources."""

    manager = ResourceManager(build_container())

    manager.register(
        build_resource(
            name="MongoDB",
        )
    )

    with pytest.raises(
        ValueError,
        match="déjà enregistrée",
    ):
        manager.register(
            build_resource(
                name="MongoDB",
            )
        )


# Initialisation d'une ressource


@pytest.mark.asyncio
async def test_initialize_resource_success() -> None:
    """Vérifie une initialisation réussie."""

    container = build_container()

    manager = ResourceManager(container)

    resource = build_resource(
        health_result=True,
    )

    await manager.initialize_resource(resource)

    assert resource.initialized is True

    cast(
        AsyncMock,
        resource.initialize,
    ).assert_awaited_once_with(container)

    cast(
        AsyncMock,
        resource.health,
    ).assert_awaited_once_with(container)


@pytest.mark.asyncio
async def test_initialize_resource_is_idempotent() -> None:
    """Vérifie qu'une ressource initialisée n'est pas recréée."""

    container = build_container()

    manager = ResourceManager(container)

    resource = build_resource()

    resource.initialized = True

    await manager.initialize_resource(resource)

    cast(
        AsyncMock,
        resource.initialize,
    ).assert_not_awaited()


@pytest.mark.asyncio
async def test_initialize_required_resource_fails_on_initialization_error() -> None:
    """Vérifie une erreur d'initialisation bloquante."""

    container = build_container()

    manager = ResourceManager(container)

    resource = build_resource(
        required=True,
    )

    cast(
        AsyncMock,
        resource.initialize,
    ).side_effect = RuntimeError("initialization failure")

    with pytest.raises(ResourceInitializationError):
        await manager.initialize_resource(resource)

    assert resource.initialized is False

    cast(
        AsyncMock,
        resource.shutdown,
    ).assert_awaited_once_with(container)


@pytest.mark.asyncio
async def test_initialize_optional_resource_ignores_initialization_error() -> None:
    """Vérifie une ressource facultative en échec."""

    container = build_container()

    manager = ResourceManager(container)

    resource = build_resource(
        required=False,
    )

    cast(
        AsyncMock,
        resource.initialize,
    ).side_effect = RuntimeError("optional failure")

    await manager.initialize_resource(resource)

    assert resource.initialized is False

    cast(
        AsyncMock,
        resource.shutdown,
    ).assert_awaited_once_with(container)


@pytest.mark.asyncio
async def test_initialize_required_resource_fails_on_unhealthy_resource() -> None:
    """Vérifie une ressource critique indisponible après initialisation."""

    container = build_container()

    manager = ResourceManager(container)

    resource = build_resource(
        required=True,
        health_result=False,
    )

    with pytest.raises(ResourceHealthError):
        await manager.initialize_resource(resource)

    assert resource.initialized is False

    cast(
        AsyncMock,
        resource.shutdown,
    ).assert_awaited_once_with(container)


@pytest.mark.asyncio
async def test_initialize_optional_resource_accepts_unhealthy_resource() -> None:
    """Vérifie le mode dégradé pour une ressource facultative."""

    manager = ResourceManager(build_container())

    resource = build_resource(
        required=False,
        health_result=False,
    )

    await manager.initialize_resource(resource)

    assert resource.initialized is True


@pytest.mark.asyncio
async def test_initialize_resource_propagates_cancelled_error() -> None:
    """Vérifie l'annulation pendant l'initialisation."""

    container = build_container()

    manager = ResourceManager(container)

    resource = build_resource()

    cast(
        AsyncMock,
        resource.initialize,
    ).side_effect = CancelledError()

    with pytest.raises(CancelledError):
        await manager.initialize_resource(resource)

    assert resource.initialized is False

    cast(
        AsyncMock,
        resource.shutdown,
    ).assert_awaited_once_with(container)


# Health post-initialisation


@pytest.mark.asyncio
async def test_check_initialized_resource_success() -> None:
    """Vérifie un contrôle de santé réussi."""

    manager = ResourceManager(build_container())

    resource = build_resource(
        health_result=True,
    )

    result = await manager._check_initialized_resource(resource)

    assert result is True


@pytest.mark.asyncio
async def test_check_initialized_optional_resource_handles_exception() -> None:
    """Vérifie une exception de santé sur ressource facultative."""

    manager = ResourceManager(build_container())

    resource = build_resource(
        required=False,
    )

    cast(
        AsyncMock,
        resource.health,
    ).side_effect = RuntimeError("health failure")

    result = await manager._check_initialized_resource(resource)

    assert result is False


@pytest.mark.asyncio
async def test_check_initialized_required_resource_handles_exception() -> None:
    """Vérifie une exception de santé sur ressource obligatoire."""

    container = build_container()

    manager = ResourceManager(container)

    resource = build_resource(
        required=True,
    )

    resource.initialized = True

    cast(
        AsyncMock,
        resource.health,
    ).side_effect = RuntimeError("health failure")

    with pytest.raises(ResourceHealthError):
        await manager._check_initialized_resource(resource)

    assert resource.initialized is False


@pytest.mark.asyncio
async def test_check_initialized_resource_propagates_cancelled_error() -> None:
    """Vérifie l'annulation pendant le contrôle de santé."""

    container = build_container()

    manager = ResourceManager(container)

    resource = build_resource()

    resource.initialized = True

    cast(
        AsyncMock,
        resource.health,
    ).side_effect = CancelledError()

    with pytest.raises(CancelledError):
        await manager._check_initialized_resource(resource)

    assert resource.initialized is False


# Nettoyage d'initialisation


@pytest.mark.asyncio
async def test_cleanup_failed_initialization() -> None:
    """Vérifie le nettoyage après échec."""

    container = build_container()

    manager = ResourceManager(container)

    resource = build_resource()

    resource.initialized = True

    await manager._cleanup_failed_initialization(resource)

    assert resource.initialized is False

    cast(
        AsyncMock,
        resource.shutdown,
    ).assert_awaited_once_with(container)


@pytest.mark.asyncio
async def test_cleanup_failed_initialization_handles_shutdown_error() -> None:
    """Vérifie une erreur pendant le nettoyage."""

    manager = ResourceManager(build_container())

    resource = build_resource()

    resource.initialized = True

    cast(
        AsyncMock,
        resource.shutdown,
    ).side_effect = RuntimeError("shutdown failure")

    await manager._cleanup_failed_initialization(resource)

    assert resource.initialized is False


# initialize_all


@pytest.mark.asyncio
async def test_initialize_all() -> None:
    """Vérifie l'initialisation ordonnée de toutes les ressources."""

    manager = ResourceManager(build_container())

    first = build_resource(name="First")
    second = build_resource(name="Second")

    manager.register(first)
    manager.register(second)

    await manager.initialize_all()

    assert first.initialized is True
    assert second.initialized is True


@pytest.mark.asyncio
async def test_initialize_all_rolls_back_on_error() -> None:
    """Vérifie le rollback global en cas d'échec."""

    manager = ResourceManager(build_container())

    first = build_resource(name="First")

    second = build_resource(name="Second")

    cast(
        AsyncMock,
        second.initialize,
    ).side_effect = RuntimeError("failure")

    manager.register(first)
    manager.register(second)

    with pytest.raises(ResourceInitializationError):
        await manager.initialize_all()

    assert first.initialized is False
    assert second.initialized is False


# Rollback


@pytest.mark.asyncio
async def test_rollback_uses_reverse_order() -> None:
    """Vérifie l'ordre inverse du rollback."""

    container = build_container()

    manager = ResourceManager(container)

    calls: list[str] = []

    async def shutdown_first(
        current_container: ApplicationContainer,
    ) -> None:
        del current_container
        calls.append("first")

    async def shutdown_second(
        current_container: ApplicationContainer,
    ) -> None:
        del current_container
        calls.append("second")

    first = ManagedResource(
        name="First",
        initialize=AsyncMock(),
        shutdown=shutdown_first,
        health=AsyncMock(return_value=True),
        initialized=True,
    )

    second = ManagedResource(
        name="Second",
        initialize=AsyncMock(),
        shutdown=shutdown_second,
        health=AsyncMock(return_value=True),
        initialized=True,
    )

    manager.register(first)
    manager.register(second)

    await manager.rollback()

    assert calls == [
        "second",
        "first",
    ]


# Shutdown


@pytest.mark.asyncio
async def test_shutdown_all() -> None:
    """Vérifie la fermeture de toutes les ressources."""

    manager = ResourceManager(build_container())

    first = build_resource(name="First")
    second = build_resource(name="Second")

    first.initialized = True
    second.initialized = True

    manager.register(first)
    manager.register(second)

    await manager.shutdown_all()

    assert first.initialized is False
    assert second.initialized is False


@pytest.mark.asyncio
async def test_shutdown_resource_ignores_uninitialized_resource() -> None:
    """Vérifie qu'une ressource inactive n'est pas fermée."""

    manager = ResourceManager(build_container())

    resource = build_resource()

    await manager._shutdown_resource(
        resource,
        rollback=False,
    )

    cast(
        AsyncMock,
        resource.shutdown,
    ).assert_not_awaited()


@pytest.mark.asyncio
async def test_shutdown_resource_handles_exception() -> None:
    """Vérifie une erreur de fermeture."""

    manager = ResourceManager(build_container())

    resource = build_resource()

    resource.initialized = True

    cast(
        AsyncMock,
        resource.shutdown,
    ).side_effect = RuntimeError("shutdown failure")

    await manager._shutdown_resource(
        resource,
        rollback=False,
    )

    assert resource.initialized is False


@pytest.mark.asyncio
async def test_shutdown_resource_handles_rollback_exception() -> None:
    """Vérifie une erreur de fermeture pendant rollback."""

    manager = ResourceManager(build_container())

    resource = build_resource()

    resource.initialized = True

    cast(
        AsyncMock,
        resource.shutdown,
    ).side_effect = RuntimeError("rollback shutdown failure")

    await manager._shutdown_resource(
        resource,
        rollback=True,
    )

    assert resource.initialized is False


# Santé du manager


@pytest.mark.asyncio
async def test_get_resource_status_false_when_not_initialized() -> None:
    """Vérifie une ressource non initialisée."""

    manager = ResourceManager(build_container())

    resource = build_resource()

    result = await manager._get_resource_status(resource)

    assert result == (
        "Test",
        False,
    )


@pytest.mark.asyncio
async def test_get_resource_status_success() -> None:
    """Vérifie une ressource initialisée et saine."""

    manager = ResourceManager(build_container())

    resource = build_resource(
        health_result=True,
    )

    resource.initialized = True

    result = await manager._get_resource_status(resource)

    assert result == (
        "Test",
        True,
    )


@pytest.mark.asyncio
async def test_get_resource_status_handles_exception() -> None:
    """Vérifie une erreur lors du healthcheck."""

    manager = ResourceManager(build_container())

    resource = build_resource()

    resource.initialized = True

    cast(
        AsyncMock,
        resource.health,
    ).side_effect = RuntimeError("health failure")

    result = await manager._get_resource_status(resource)

    assert result == (
        "Test",
        False,
    )


@pytest.mark.asyncio
async def test_health() -> None:
    """Vérifie le healthcheck global du gestionnaire."""

    manager = ResourceManager(build_container())

    healthy = build_resource(
        name="Healthy",
        health_result=True,
    )

    unavailable = build_resource(
        name="Unavailable",
        health_result=False,
    )

    healthy.initialized = True
    unavailable.initialized = True

    manager.register(healthy)
    manager.register(unavailable)

    result = await manager.health()

    assert result == {
        "Healthy": True,
        "Unavailable": False,
    }


# Fonctions neutres


@pytest.mark.asyncio
async def test_no_initialize() -> None:
    """Vérifie l'initialisation neutre."""

    await no_initialize(build_container())


@pytest.mark.asyncio
async def test_no_shutdown() -> None:
    """Vérifie la fermeture neutre."""

    await no_shutdown(build_container())


# Fonctions de ressources


@pytest.mark.asyncio
@pytest.mark.parametrize(
    (
        "function",
        "attribute",
        "method_name",
    ),
    [
        (
            initialize_mongodb,
            "mongodb",
            "initialize",
        ),
        (
            shutdown_mongodb,
            "mongodb",
            "close",
        ),
        (
            mongodb_health,
            "mongodb",
            "ping",
        ),
        (
            initialize_embedding,
            "embedding",
            "initialize",
        ),
        (
            shutdown_embedding,
            "embedding",
            "close",
        ),
        (
            embedding_health,
            "embedding",
            "ping",
        ),
        (
            initialize_milvus,
            "milvus",
            "initialize",
        ),
        (
            shutdown_milvus,
            "milvus",
            "close",
        ),
        (
            milvus_health,
            "milvus",
            "ping",
        ),
        (
            initialize_stockfish,
            "stockfish",
            "start",
        ),
        (
            shutdown_stockfish,
            "stockfish",
            "close",
        ),
        (
            stockfish_health,
            "stockfish",
            "ping",
        ),
        (
            shutdown_lichess,
            "lichess",
            "close",
        ),
        (
            lichess_health,
            "lichess",
            "ping",
        ),
        (
            shutdown_youtube,
            "youtube",
            "close",
        ),
        (
            youtube_health,
            "youtube",
            "ping",
        ),
        (
            initialize_llm,
            "llm",
            "initialize",
        ),
        (
            shutdown_llm,
            "llm",
            "close",
        ),
        (
            llm_health,
            "llm",
            "ping",
        ),
    ],
)
async def test_resource_adapter_functions(
    function: Any,
    attribute: str,
    method_name: str,
) -> None:
    """Vérifie les fonctions simples du lifespan."""

    container = build_container()

    dependency = getattr(
        container,
        attribute,
    )

    method = AsyncMock(
        return_value=True,
    )

    setattr(
        dependency,
        method_name,
        method,
    )

    result = await function(container)

    method.assert_awaited_once_with()

    if method_name == "ping":
        assert result is True


# Workflow


@pytest.mark.asyncio
async def test_initialize_workflow() -> None:
    """Vérifie la construction du workflow."""

    container = build_container()

    await initialize_workflow(container)

    cast(
        Any,
        container.build_graph,
    ).assert_called_once_with()


@pytest.mark.asyncio
async def test_shutdown_workflow() -> None:
    """Vérifie la destruction du workflow."""

    container = build_container()

    await shutdown_workflow(container)

    cast(
        Any,
        container.destroy_graph,
    ).assert_called_once_with()


@pytest.mark.asyncio
async def test_workflow_health() -> None:
    """Vérifie la santé du workflow."""

    container = build_container()

    cast(
        Any,
        container.is_ready,
    ).return_value = True

    assert await workflow_health(container) is True


# Construction du ResourceManager


def test_create_resource_manager() -> None:
    """Vérifie l'ordre et les propriétés des ressources."""

    container = build_container()

    manager = create_resource_manager(container)

    names = [resource.name for resource in manager.resources]

    assert names == [
        "MongoDB",
        "Embedding",
        "Milvus",
        "Stockfish",
        "LLM",
        "Lichess",
        "YouTube",
        "Workflow",
    ]

    required_by_name = {
        resource.name: resource.required for resource in manager.resources
    }

    assert required_by_name == {
        "MongoDB": True,
        "Embedding": True,
        "Milvus": True,
        "Stockfish": True,
        "LLM": True,
        "Lichess": False,
        "YouTube": False,
        "Workflow": True,
    }


# Lifespan FastAPI


@pytest.mark.asyncio
async def test_lifespan_success(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Vérifie un cycle de vie FastAPI complet."""

    app = FastAPI()

    container = build_container()

    manager = MagicMock(
        spec=ResourceManager,
    )

    manager.initialize_all = AsyncMock()
    manager.shutdown_all = AsyncMock()

    monkeypatch.setattr(
        "app.core.lifespan.create_application_container",
        MagicMock(
            return_value=container,
        ),
    )

    monkeypatch.setattr(
        "app.core.lifespan.create_resource_manager",
        MagicMock(
            return_value=manager,
        ),
    )

    async with lifespan(app):
        assert app.state.container is container

        assert container.resource_manager is manager

    manager.initialize_all.assert_awaited_once_with()
    manager.shutdown_all.assert_awaited_once_with()

    assert (
        getattr(
            app.state,
            "container",
            None,
        )
        is None
    )

    assert container.resource_manager is None


@pytest.mark.asyncio
async def test_lifespan_rolls_back_visibility_when_initialization_fails(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Vérifie l'échec au démarrage du lifespan."""

    app = FastAPI()

    container = build_container()

    manager = MagicMock(
        spec=ResourceManager,
    )

    manager.initialize_all = AsyncMock(side_effect=RuntimeError("startup failure"))

    manager.shutdown_all = AsyncMock()

    monkeypatch.setattr(
        "app.core.lifespan.create_application_container",
        MagicMock(
            return_value=container,
        ),
    )

    monkeypatch.setattr(
        "app.core.lifespan.create_resource_manager",
        MagicMock(
            return_value=manager,
        ),
    )

    with pytest.raises(
        RuntimeError,
        match="startup failure",
    ):
        async with lifespan(app):
            pass

    assert (
        getattr(
            app.state,
            "container",
            None,
        )
        is None
    )

    manager.shutdown_all.assert_awaited_once_with()

    assert container.resource_manager is None


@pytest.mark.asyncio
async def test_lifespan_shutdown_runs_when_application_body_fails(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Vérifie la fermeture si l'application lève une exception."""

    app = FastAPI()

    container = build_container()

    manager = MagicMock(
        spec=ResourceManager,
    )

    manager.initialize_all = AsyncMock()
    manager.shutdown_all = AsyncMock()

    monkeypatch.setattr(
        "app.core.lifespan.create_application_container",
        MagicMock(
            return_value=container,
        ),
    )

    monkeypatch.setattr(
        "app.core.lifespan.create_resource_manager",
        MagicMock(
            return_value=manager,
        ),
    )

    with pytest.raises(
        RuntimeError,
        match="application failure",
    ):
        async with lifespan(app):
            raise RuntimeError("application failure")

    manager.shutdown_all.assert_awaited_once_with()

    assert container.resource_manager is None
