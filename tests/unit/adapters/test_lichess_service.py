"""Tests unitaires du service Lichess de Chess Agent."""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock

import httpx
import pytest
from app.adapters.lichess_service import (
    RETRYABLE_STATUS_CODES,
    LichessPayload,
    LichessService,
)
from app.core.constants import (
    DEFAULT_STARTING_FEN,
    MASTER_DATABASE_ENDPOINT,
    UNKNOWN_OPENING,
    USER_DATABASE_ENDPOINT,
)
from app.core.exceptions import (
    LichessError,
    LichessResponseError,
    LichessTimeoutError,
    OpeningNotFoundError,
)
from app.schemas.chess.position import FenRequest
from pydantic import SecretStr

# Constantes

VALID_FEN = "r1bqkbnr/pppp1ppp/2n5/1B2p3/4P3/5N2/PPPP1PPP/RNBQK2R b KQkq - 3 3"

VALID_PAYLOAD: LichessPayload = {
    "white": 40,
    "draws": 20,
    "black": 40,
    "opening": {
        "eco": "C60",
        "name": "Ruy Lopez",
    },
}

EMPTY_OPENING_PAYLOAD: LichessPayload = {
    "white": 0,
    "draws": 0,
    "black": 0,
    "opening": {},
}


# Fixtures


@pytest.fixture
def service() -> LichessService:
    """Construit un service Lichess."""

    return LichessService()


@pytest.fixture
def response() -> MagicMock:
    """Construit une réponse HTTP simulée."""

    mocked_response = MagicMock(spec=httpx.Response)

    mocked_response.status_code = 200
    mocked_response.content = (
        b'{"white":40,"draws":20,"black":40,"opening":{"eco":"C60","name":"Ruy Lopez"}}'
    )

    mocked_response.raise_for_status.return_value = None

    return mocked_response


# Construction


def test_service_is_ready_after_creation(
    service: LichessService,
) -> None:
    """Vérifie que le client HTTP est disponible après construction."""

    assert service.is_ready() is True
    assert service.is_closed() is False


def test_get_token_returns_none_when_token_is_missing(
    service: LichessService,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Vérifie l'absence de token Lichess."""

    test_settings = service._settings.model_copy(
        update={
            "lichess_token": None,
        }
    )

    monkeypatch.setattr(
        service,
        "_settings",
        test_settings,
    )

    assert service._get_token() is None


def test_get_token_returns_secret_value(
    service: LichessService,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Vérifie la récupération d'un token configuré."""

    test_settings = service._settings.model_copy(
        update={
            "lichess_token": SecretStr("token-value"),
        }
    )

    monkeypatch.setattr(
        service,
        "_settings",
        test_settings,
    )

    assert service._get_token() == "token-value"


def test_get_token_returns_none_for_empty_secret(
    service: LichessService,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Vérifie qu'un token vide est ignoré."""

    test_settings = service._settings.model_copy(
        update={
            "lichess_token": SecretStr("   "),
        }
    )

    monkeypatch.setattr(
        service,
        "_settings",
        test_settings,
    )

    assert service._get_token() is None


# Cycle de vie


@pytest.mark.asyncio
async def test_close_closes_http_client(
    service: LichessService,
) -> None:
    """Vérifie que le client HTTP est fermé."""

    service._client.aclose = AsyncMock()

    await service.close()

    service._client.aclose.assert_awaited_once()


@pytest.mark.asyncio
async def test_close_does_nothing_when_client_is_closed(
    service: LichessService,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Vérifie qu'un client déjà fermé n'est pas refermé."""

    client = MagicMock()
    client.is_closed = True
    client.aclose = AsyncMock()

    monkeypatch.setattr(
        service,
        "_client",
        client,
    )

    await service.close()

    client.aclose.assert_not_awaited()


@pytest.mark.asyncio
async def test_close_ignores_closing_error(
    service: LichessService,
) -> None:
    """Vérifie qu'une erreur de fermeture n'est pas propagée."""

    service._client.aclose = AsyncMock(side_effect=RuntimeError("close failure"))

    await service.close()


# Requête générique


@pytest.mark.asyncio
async def test_request_returns_parsed_payload(
    service: LichessService,
    response: MagicMock,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Vérifie qu'une requête retourne le payload validé."""

    execute_request = AsyncMock(return_value=response)

    monkeypatch.setattr(
        service,
        "_execute_request",
        execute_request,
    )

    payload = await service._request(
        MASTER_DATABASE_ENDPOINT,
        params={
            "fen": VALID_FEN,
        },
    )

    assert payload["white"] == 40
    assert payload["black"] == 40

    execute_request.assert_awaited_once()


# Parsing


def test_parse_response_payload_returns_json_object(
    service: LichessService,
    response: MagicMock,
) -> None:
    """Vérifie le parsing d'une réponse JSON valide."""

    payload = service._parse_response_payload(response)

    assert payload["white"] == 40
    assert payload["draws"] == 20
    assert payload["black"] == 40


def test_parse_response_payload_rejects_empty_response(
    service: LichessService,
    response: MagicMock,
) -> None:
    """Vérifie qu'une réponse vide est refusée."""

    response.content = b""

    with pytest.raises(LichessResponseError):
        service._parse_response_payload(response)


def test_parse_response_payload_rejects_invalid_json(
    service: LichessService,
    response: MagicMock,
) -> None:
    """Vérifie qu'un JSON invalide est refusé."""

    response.content = b"not-json"

    with pytest.raises(LichessResponseError):
        service._parse_response_payload(response)


def test_parse_response_payload_rejects_non_object_json(
    service: LichessService,
    response: MagicMock,
) -> None:
    """Vérifie que le JSON doit représenter un objet."""

    response.content = b'["not", "an", "object"]'

    with pytest.raises(LichessResponseError):
        service._parse_response_payload(response)


# Retry


@pytest.mark.parametrize(
    "status_code",
    sorted(RETRYABLE_STATUS_CODES),
)
def test_should_retry_status_accepts_retryable_status(
    service: LichessService,
    status_code: int,
) -> None:
    """Vérifie les statuts HTTP temporaires."""

    assert (
        service._should_retry_status(
            status_code=status_code,
            attempt=1,
            total_attempts=2,
        )
        is True
    )


def test_should_retry_status_rejects_non_retryable_status(
    service: LichessService,
) -> None:
    """Vérifie qu'un statut permanent n'est pas retenté."""

    assert (
        service._should_retry_status(
            status_code=404,
            attempt=1,
            total_attempts=2,
        )
        is False
    )


def test_should_retry_status_stops_on_last_attempt(
    service: LichessService,
) -> None:
    """Vérifie qu'aucun retry n'est réalisé après la dernière tentative."""

    assert (
        service._should_retry_status(
            status_code=503,
            attempt=2,
            total_attempts=2,
        )
        is False
    )


@pytest.mark.asyncio
async def test_wait_before_retry_uses_exponential_delay(
    service: LichessService,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Vérifie le calcul du délai exponentiel."""

    sleep = AsyncMock()

    monkeypatch.setattr(
        "app.adapters.lichess_service.asyncio.sleep",
        sleep,
    )

    test_settings = service._settings.model_copy(
        update={
            "http_retry_delay_seconds": 2.0,
        }
    )

    monkeypatch.setattr(
        service,
        "_settings",
        test_settings,
    )

    await service._wait_before_retry(
        attempt=3,
        endpoint=MASTER_DATABASE_ENDPOINT,
        status_code=503,
    )

    sleep.assert_awaited_once_with(8.0)


# Exécution HTTP


@pytest.mark.asyncio
async def test_execute_request_returns_successful_response(
    service: LichessService,
    response: MagicMock,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Vérifie une requête HTTP réussie."""

    client = MagicMock()
    client.get = AsyncMock(return_value=response)

    monkeypatch.setattr(
        service,
        "_client",
        client,
    )

    result = await service._execute_request(
        MASTER_DATABASE_ENDPOINT,
        params=None,
    )

    assert result is response

    response.raise_for_status.assert_called_once()


@pytest.mark.asyncio
async def test_execute_request_retries_retryable_status(
    service: LichessService,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Vérifie une nouvelle tentative après une erreur temporaire."""

    first_response = MagicMock(spec=httpx.Response)
    first_response.status_code = 503
    first_response.raise_for_status.return_value = None

    second_response = MagicMock(spec=httpx.Response)
    second_response.status_code = 200
    second_response.raise_for_status.return_value = None

    client = MagicMock()
    client.get = AsyncMock(
        side_effect=[
            first_response,
            second_response,
        ]
    )

    monkeypatch.setattr(
        service,
        "_client",
        client,
    )

    test_settings = service._settings.model_copy(
        update={
            "http_max_retry_attempts": 1,
        }
    )

    monkeypatch.setattr(
        service,
        "_settings",
        test_settings,
    )

    wait = AsyncMock()

    monkeypatch.setattr(
        service,
        "_wait_before_retry",
        wait,
    )

    result = await service._execute_request(
        MASTER_DATABASE_ENDPOINT,
        params=None,
    )

    assert result is second_response
    assert client.get.await_count == 2
    wait.assert_awaited_once()


@pytest.mark.asyncio
async def test_execute_request_raises_timeout_after_last_attempt(
    service: LichessService,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Vérifie la traduction d'un timeout définitif."""

    request = httpx.Request(
        "GET",
        "https://example.test",
    )

    timeout_error = httpx.TimeoutException(
        "timeout",
        request=request,
    )

    client = MagicMock()
    client.get = AsyncMock(side_effect=timeout_error)

    monkeypatch.setattr(
        service,
        "_client",
        client,
    )

    test_settings = service._settings.model_copy(
        update={
            "http_max_retry_attempts": 0,
        }
    )

    monkeypatch.setattr(
        service,
        "_settings",
        test_settings,
    )

    with pytest.raises(LichessTimeoutError):
        await service._execute_request(
            MASTER_DATABASE_ENDPOINT,
            params=None,
        )


@pytest.mark.asyncio
async def test_execute_request_retries_timeout(
    service: LichessService,
    response: MagicMock,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Vérifie un retry après timeout."""

    request = httpx.Request(
        "GET",
        "https://example.test",
    )

    timeout_error = httpx.TimeoutException(
        "timeout",
        request=request,
    )

    client = MagicMock()
    client.get = AsyncMock(
        side_effect=[
            timeout_error,
            response,
        ]
    )

    monkeypatch.setattr(
        service,
        "_client",
        client,
    )

    test_settings = service._settings.model_copy(
        update={
            "http_max_retry_attempts": 1,
        }
    )

    monkeypatch.setattr(
        service,
        "_settings",
        test_settings,
    )

    wait = AsyncMock()

    monkeypatch.setattr(
        service,
        "_wait_before_retry",
        wait,
    )

    result = await service._execute_request(
        MASTER_DATABASE_ENDPOINT,
        params=None,
    )

    assert result is response
    assert client.get.await_count == 2
    wait.assert_awaited_once()


@pytest.mark.asyncio
async def test_execute_request_translates_http_status_error(
    service: LichessService,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Vérifie la traduction d'une erreur HTTP."""

    request = httpx.Request(
        "GET",
        "https://example.test",
    )

    response = httpx.Response(
        404,
        request=request,
    )

    client = MagicMock()
    client.get = AsyncMock(return_value=response)

    monkeypatch.setattr(
        service,
        "_client",
        client,
    )

    with pytest.raises(LichessError):
        await service._execute_request(
            MASTER_DATABASE_ENDPOINT,
            params=None,
        )


@pytest.mark.asyncio
async def test_execute_request_translates_network_error(
    service: LichessService,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Vérifie la traduction d'une erreur réseau."""

    request = httpx.Request(
        "GET",
        "https://example.test",
    )

    error = httpx.ConnectError(
        "network error",
        request=request,
    )

    client = MagicMock()
    client.get = AsyncMock(side_effect=error)

    monkeypatch.setattr(
        service,
        "_client",
        client,
    )

    test_settings = service._settings.model_copy(
        update={
            "http_max_retry_attempts": 0,
        }
    )

    monkeypatch.setattr(
        service,
        "_settings",
        test_settings,
    )

    with pytest.raises(LichessError):
        await service._execute_request(
            MASTER_DATABASE_ENDPOINT,
            params=None,
        )


# Accès aux bases Lichess


@pytest.mark.asyncio
async def test_get_master_database_uses_expected_parameters(
    service: LichessService,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Vérifie l'appel à la base maîtres."""

    request = AsyncMock(return_value=VALID_PAYLOAD)

    monkeypatch.setattr(
        service,
        "_request",
        request,
    )

    result = await service._get_master_database(fen=VALID_FEN)

    assert result == VALID_PAYLOAD

    request.assert_awaited_once_with(
        MASTER_DATABASE_ENDPOINT,
        params={
            "fen": VALID_FEN,
            "moves": service._settings.lichess_max_moves,
        },
    )


@pytest.mark.asyncio
async def test_get_user_database_uses_optional_filters(
    service: LichessService,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Vérifie l'appel à la base joueurs."""

    request = AsyncMock(return_value=VALID_PAYLOAD)

    monkeypatch.setattr(
        service,
        "_request",
        request,
    )

    result = await service._get_user_database(
        fen=VALID_FEN,
        speeds="rapid",
        ratings="2000",
    )

    assert result == VALID_PAYLOAD

    request.assert_awaited_once_with(
        USER_DATABASE_ENDPOINT,
        params={
            "fen": VALID_FEN,
            "moves": service._settings.lichess_max_moves,
            "speeds": "rapid",
            "ratings": "2000",
        },
    )


# Détection d'ouverture


@pytest.mark.asyncio
async def test_detect_opening_returns_opening_details(
    service: LichessService,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Vérifie la détection d'une ouverture connue."""

    get_master_database = AsyncMock(return_value=VALID_PAYLOAD)

    monkeypatch.setattr(
        service,
        "_get_master_database",
        get_master_database,
    )

    result = await service.detect_opening(FenRequest(fen=VALID_FEN))

    assert result.opening.eco == "C60"
    assert result.opening.name == "Ruy Lopez"
    assert result.opening.final_fen == VALID_FEN

    assert result.statistics is not None
    assert result.statistics.games == 100
    assert result.statistics.white_win_rate == pytest.approx(40.0)
    assert result.statistics.black_win_rate == pytest.approx(40.0)
    assert result.statistics.draw_rate == pytest.approx(20.0)


@pytest.mark.asyncio
async def test_detect_opening_raises_when_opening_is_missing(
    service: LichessService,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Vérifie l'absence d'ouverture."""

    get_master_database = AsyncMock(return_value=EMPTY_OPENING_PAYLOAD)

    monkeypatch.setattr(
        service,
        "_get_master_database",
        get_master_database,
    )

    with pytest.raises(OpeningNotFoundError):
        await service.detect_opening(FenRequest(fen=VALID_FEN))


# Construction d'ouverture


def test_build_opening_returns_expected_model(
    service: LichessService,
) -> None:
    """Vérifie la conversion du payload vers Opening."""

    opening = service._build_opening(
        VALID_PAYLOAD,
        fen=VALID_FEN,
    )

    assert opening.eco == "C60"
    assert opening.name == "Ruy Lopez"
    assert opening.moves == []
    assert opening.final_fen == VALID_FEN
    assert opening.description is None


def test_build_opening_uses_unknown_name_when_missing(
    service: LichessService,
) -> None:
    """Vérifie le nom d'ouverture par défaut."""

    payload: LichessPayload = {
        "opening": {
            "eco": "C60",
        },
    }

    opening = service._build_opening(
        payload,
        fen=VALID_FEN,
    )

    assert opening.name == UNKNOWN_OPENING


# Statistiques


def test_build_statistics_returns_expected_rates(
    service: LichessService,
) -> None:
    """Vérifie le calcul des statistiques."""

    statistics = service._build_statistics(VALID_PAYLOAD)

    assert statistics.games == 100
    assert statistics.white_win_rate == pytest.approx(40.0)
    assert statistics.black_win_rate == pytest.approx(40.0)
    assert statistics.draw_rate == pytest.approx(20.0)


def test_build_statistics_returns_empty_statistics_when_no_games(
    service: LichessService,
) -> None:
    """Vérifie le cas sans partie."""

    statistics = service._build_statistics(
        {
            "white": 0,
            "black": 0,
            "draws": 0,
        }
    )

    assert statistics.games == 0
    assert statistics.white_win_rate == 0.0
    assert statistics.black_win_rate == 0.0
    assert statistics.draw_rate == 0.0


# Présence d'ouverture


def test_has_opening_returns_true_with_name(
    service: LichessService,
) -> None:
    """Vérifie la détection par nom."""

    assert (
        service._has_opening(
            {
                "opening": {
                    "name": "Ruy Lopez",
                },
            }
        )
        is True
    )


def test_has_opening_returns_true_with_eco(
    service: LichessService,
) -> None:
    """Vérifie la détection par ECO."""

    assert (
        service._has_opening(
            {
                "opening": {
                    "eco": "C60",
                },
            }
        )
        is True
    )


def test_has_opening_returns_false_without_opening(
    service: LichessService,
) -> None:
    """Vérifie l'absence d'ouverture."""

    assert (
        service._has_opening(
            {
                "opening": {},
            }
        )
        is False
    )


# Helpers JSON


def test_get_object_returns_nested_object(
    service: LichessService,
) -> None:
    """Vérifie l'extraction d'un objet JSON."""

    result = service._get_object(
        VALID_PAYLOAD,
        "opening",
    )

    assert result == {
        "eco": "C60",
        "name": "Ruy Lopez",
    }


def test_get_object_returns_empty_dict_for_invalid_value(
    service: LichessService,
) -> None:
    """Vérifie le repli pour une valeur non objet."""

    result = service._get_object(
        {
            "opening": "Ruy Lopez",
        },
        "opening",
    )

    assert result == {}


def test_get_string_returns_trimmed_value(
    service: LichessService,
) -> None:
    """Vérifie le nettoyage d'une chaîne."""

    result = service._get_string(
        {
            "name": "  Ruy Lopez  ",
        },
        "name",
    )

    assert result == "Ruy Lopez"


def test_get_string_returns_default_for_invalid_value(
    service: LichessService,
) -> None:
    """Vérifie la valeur par défaut."""

    result = service._get_string(
        {
            "name": 42,
        },
        "name",
        "Unknown",
    )

    assert result == "Unknown"


# Conversion des entiers


@pytest.mark.parametrize(
    ("value", "expected"),
    [
        (10, 10),
        (10.0, 10),
        ("10", 10),
        (" 10 ", 10),
        (0, 0),
    ],
)
def test_parse_integer_accepts_valid_values(
    service: LichessService,
    value: object,
    expected: int,
) -> None:
    """Vérifie les représentations numériques valides."""

    assert (
        service._parse_integer(
            value  # type: ignore[arg-type]
        )
        == expected
    )


@pytest.mark.parametrize(
    "value",
    [
        None,
        True,
        False,
        -1,
        -1.0,
        1.5,
        "abc",
        "-1",
        [],
        {},
    ],
)
def test_parse_integer_rejects_invalid_values(
    service: LichessService,
    value: object,
) -> None:
    """Vérifie les représentations numériques invalides."""

    assert (
        service._parse_integer(
            value  # type: ignore[arg-type]
        )
        is None
    )


def test_get_integer_returns_zero_for_invalid_value(
    service: LichessService,
) -> None:
    """Vérifie le repli vers zéro."""

    result = service._get_integer(
        {
            "white": "invalid",
        },
        "white",
    )

    assert result == 0


# Santé


@pytest.mark.asyncio
async def test_ping_returns_true_when_lichess_responds(
    service: LichessService,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Vérifie un ping réussi."""

    get_master_database = AsyncMock(return_value=VALID_PAYLOAD)

    monkeypatch.setattr(
        service,
        "_get_master_database",
        get_master_database,
    )

    assert await service.ping() is True

    get_master_database.assert_awaited_once_with(fen=DEFAULT_STARTING_FEN)


@pytest.mark.asyncio
async def test_ping_returns_false_when_client_is_closed(
    service: LichessService,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Vérifie le ping avec client fermé."""

    client = MagicMock()
    client.is_closed = True

    monkeypatch.setattr(
        service,
        "_client",
        client,
    )

    assert await service.ping() is False


@pytest.mark.asyncio
async def test_ping_returns_false_on_lichess_error(
    service: LichessService,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Vérifie le ping lorsque Lichess échoue."""

    get_master_database = AsyncMock(side_effect=LichessError(message="failure"))

    monkeypatch.setattr(
        service,
        "_get_master_database",
        get_master_database,
    )

    assert await service.ping() is False


@pytest.mark.asyncio
async def test_ping_returns_false_on_unexpected_error(
    service: LichessService,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Vérifie la protection contre une erreur inattendue."""

    get_master_database = AsyncMock(side_effect=RuntimeError("unexpected"))

    monkeypatch.setattr(
        service,
        "_get_master_database",
        get_master_database,
    )

    assert await service.ping() is False


@pytest.mark.asyncio
async def test_health_returns_service_status(
    service: LichessService,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Vérifie l'état de santé détaillé."""

    ping = AsyncMock(return_value=True)

    monkeypatch.setattr(
        service,
        "ping",
        ping,
    )

    status = await service.health()

    assert status["service"] == "lichess"
    assert status["is_ready"] is True
    assert status["is_closed"] is False
    assert status["available"] is True

    assert status["base_url"] == str(service._client.base_url)

    assert status["endpoint"] == (MASTER_DATABASE_ENDPOINT)

    assert status["timeout_seconds"] == (service._settings.lichess_timeout_seconds)

    assert status["max_moves"] == (service._settings.lichess_max_moves)

    assert status["max_retry_attempts"] == (service._settings.http_max_retry_attempts)

    assert status["retry_delay_seconds"] == (service._settings.http_retry_delay_seconds)

    assert status["max_connections"] == (service._settings.http_max_connections)

    assert status["user_agent"] == (service._settings.http_user_agent)
