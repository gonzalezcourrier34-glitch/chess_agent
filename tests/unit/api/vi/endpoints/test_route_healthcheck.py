"""Tests unitaires des routes de contrôle de santé."""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock

import pytest
from app.api.v1.endpoints.route_healthcheck import healthcheck, live, ready
from app.schemas.analysis.healthcheck import HealthcheckResponse

# Liveness


@pytest.mark.asyncio
async def test_live_returns_alive_status() -> None:
    """Vérifie que la route de liveness répond correctement."""

    result = await live()

    assert result == {
        "status": "alive",
    }


# Readiness


@pytest.mark.asyncio
async def test_ready_delegates_to_healthcheck_service() -> None:
    """Vérifie que la readiness délègue au service de supervision."""

    service = MagicMock()
    service.check_readiness = AsyncMock(
        return_value=None,
    )

    result = await ready(
        healthcheck_service=service,
    )

    assert result == {
        "status": "ready",
    }

    service.check_readiness.assert_awaited_once_with()


@pytest.mark.asyncio
async def test_ready_propagates_service_error() -> None:
    """Vérifie que la route ne masque pas une erreur de readiness."""

    service = MagicMock()
    service.check_readiness = AsyncMock(
        side_effect=RuntimeError(
            "readiness failure",
        ),
    )

    with pytest.raises(
        RuntimeError,
        match="readiness failure",
    ):
        await ready(
            healthcheck_service=service,
        )

    service.check_readiness.assert_awaited_once_with()


# Diagnostic complet


@pytest.mark.asyncio
async def test_healthcheck_delegates_to_healthcheck_service() -> None:
    """Vérifie que le diagnostic complet est délégué au service."""

    expected_response = MagicMock(
        spec=HealthcheckResponse,
    )

    service = MagicMock()
    service.check = AsyncMock(
        return_value=expected_response,
    )

    result = await healthcheck(
        healthcheck_service=service,
    )

    assert result is expected_response

    service.check.assert_awaited_once_with()


@pytest.mark.asyncio
async def test_healthcheck_propagates_service_error() -> None:
    """Vérifie que la route ne masque pas une erreur de diagnostic."""

    service = MagicMock()
    service.check = AsyncMock(
        side_effect=RuntimeError(
            "healthcheck failure",
        ),
    )

    with pytest.raises(
        RuntimeError,
        match="healthcheck failure",
    ):
        await healthcheck(
            healthcheck_service=service,
        )

    service.check.assert_awaited_once_with()
