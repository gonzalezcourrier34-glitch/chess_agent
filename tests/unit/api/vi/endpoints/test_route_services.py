"""Tests unitaires des routes de supervision des services."""

from __future__ import annotations

from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock

import pytest
from app.api.v1.endpoints.route_services import get_services_status
from app.schemas.common.service import ServicesStatus

# Supervision


@pytest.mark.asyncio
async def test_get_services_status_returns_services_from_healthcheck() -> None:
    """Vérifie que la route retourne l'état des services du diagnostic."""

    expected_services = MagicMock(
        spec=ServicesStatus,
    )

    healthcheck_response = SimpleNamespace(
        services=expected_services,
    )

    healthcheck = MagicMock()
    healthcheck.check = AsyncMock(
        return_value=healthcheck_response,
    )

    result = await get_services_status(
        healthcheck=healthcheck,
    )

    assert result is expected_services

    healthcheck.check.assert_awaited_once_with()


@pytest.mark.asyncio
async def test_get_services_status_propagates_healthcheck_error() -> None:
    """Vérifie que la route ne masque pas une erreur de supervision."""

    healthcheck = MagicMock()
    healthcheck.check = AsyncMock(
        side_effect=RuntimeError(
            "healthcheck failure",
        ),
    )

    with pytest.raises(
        RuntimeError,
        match="healthcheck failure",
    ):
        await get_services_status(
            healthcheck=healthcheck,
        )

    healthcheck.check.assert_awaited_once_with()
