"""Tests unitaires du service YouTube de Chess Agent."""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock

import httpx
import pytest
from app.adapters.youtube_service import (
    MAX_SEARCH_RESULTS,
    MIN_SEARCH_RESULTS,
    SERVICE_NAME,
    YoutubeParams,
    YoutubePayload,
    YoutubeService,
)
from app.core.constants import (
    YOUTUBE_SEARCH_ENDPOINT,
    YOUTUBE_VIDEOS_ENDPOINT,
)
from app.core.exceptions import (
    ErrorContext,
    InvalidRequestError,
    YoutubeConfigurationError,
    YoutubeQuotaError,
    YoutubeResponseError,
    YoutubeTimeoutError,
    YoutubeUnavailableError,
)
from app.schemas.media.video import VideoSearchRequest
from pydantic import SecretStr

# Configuration

BASE_URL = "https://www.googleapis.com/youtube/v3"
API_KEY = "test-api-key"

QUERY = "Ruy Lopez"
LANGUAGE = "fr"

VIDEO_ID = "video-1"
CHANNEL_ID = "channel-1"


SEARCH_PAYLOAD: YoutubePayload = {
    "items": [
        {
            "id": {
                "videoId": VIDEO_ID,
            },
            "snippet": {
                "title": "Ruy Lopez Chess Opening Guide",
                "description": ("Learn the Ruy Lopez opening."),
                "channelId": CHANNEL_ID,
                "channelTitle": "Chess Channel",
                "publishedAt": ("2026-08-18T10:00:00Z"),
                "defaultLanguage": "en",
                "thumbnails": {
                    "high": {
                        "url": ("https://example.test/thumbnail.jpg"),
                    },
                },
            },
        },
    ],
}


DETAILS_PAYLOAD: YoutubePayload = {
    "items": [
        {
            "id": VIDEO_ID,
            "contentDetails": {
                "duration": "PT10M30S",
            },
            "statistics": {
                "viewCount": "1234",
                "likeCount": "120",
                "commentCount": "15",
            },
        },
    ],
}


# Helpers


def build_youtube_error() -> YoutubeUnavailableError:
    """Construit une erreur YouTube valide."""

    return YoutubeUnavailableError(
        context=ErrorContext(
            service=SERVICE_NAME,
            operation="test",
        ),
        message="YouTube indisponible.",
    )


def build_request(
    *,
    query: str = QUERY,
    max_results: int = 5,
    language: str = LANGUAGE,
) -> VideoSearchRequest:
    """Construit une requête vidéo sans dépendre du validateur complet."""

    return VideoSearchRequest.model_construct(
        query=query,
        max_results=max_results,
        language=language,
    )


def build_response(
    *,
    status_code: int = 200,
    payload: YoutubePayload | None = None,
    content: bytes | None = None,
) -> httpx.Response:
    """Construit une réponse HTTP réaliste."""

    request = httpx.Request(
        "GET",
        f"{BASE_URL}/test",
    )

    if content is not None:
        return httpx.Response(
            status_code,
            request=request,
            content=content,
        )

    return httpx.Response(
        status_code,
        request=request,
        json=(payload if payload is not None else {}),
    )


# Fixtures


@pytest.fixture
def service(
    monkeypatch: pytest.MonkeyPatch,
) -> YoutubeService:
    """Construit un service YouTube configuré pour les tests."""

    youtube_service = YoutubeService()

    test_settings = youtube_service._settings.model_copy(
        update={
            "youtube_api_key": SecretStr(API_KEY),
            "youtube_api_url": BASE_URL,
            "youtube_default_language": (LANGUAGE),
            "youtube_region_code": "FR",
            "youtube_query_suffix": ("chess opening"),
            "youtube_search_max_results": 5,
            "youtube_timeout_seconds": 15.0,
            "http_max_retry_attempts": 1,
            "http_retry_delay_seconds": 0.01,
        }
    )

    monkeypatch.setattr(
        youtube_service,
        "_settings",
        test_settings,
    )

    return youtube_service


# Construction


def test_service_is_ready_with_api_key(
    service: YoutubeService,
) -> None:
    """Vérifie l'état initial du service."""

    assert service.is_closed() is False
    assert service.is_ready() is True


# Cycle de vie


@pytest.mark.asyncio
async def test_initialize_does_not_close_client(
    service: YoutubeService,
) -> None:
    """Vérifie l'initialisation légère du service."""

    await service.initialize()

    assert service.is_closed() is False


@pytest.mark.asyncio
async def test_shutdown_calls_close(
    service: YoutubeService,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Vérifie l'alias shutdown."""

    close = AsyncMock()

    monkeypatch.setattr(
        service,
        "close",
        close,
    )

    await service.shutdown()

    close.assert_awaited_once()


@pytest.mark.asyncio
async def test_close_closes_http_client(
    service: YoutubeService,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Vérifie la fermeture du client HTTP."""

    client = MagicMock(spec=httpx.AsyncClient)

    client.is_closed = False
    client.aclose = AsyncMock()

    monkeypatch.setattr(
        service,
        "_client",
        client,
    )

    await service.close()

    client.aclose.assert_awaited_once()


@pytest.mark.asyncio
async def test_close_does_nothing_when_client_is_closed(
    service: YoutubeService,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Vérifie l'idempotence de la fermeture."""

    client = MagicMock(spec=httpx.AsyncClient)

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
async def test_operation_increments_and_decrements_counter(
    service: YoutubeService,
) -> None:
    """Vérifie la protection d'une opération."""

    assert service._active_operations == 0

    async with service._operation("test"):
        assert service._active_operations == 1

    assert service._active_operations == 0


@pytest.mark.asyncio
async def test_operation_rejects_closing_service(
    service: YoutubeService,
) -> None:
    """Vérifie qu'aucune opération ne démarre pendant la fermeture."""

    service._closing = True

    with pytest.raises(YoutubeUnavailableError):
        async with service._operation("test"):
            pass


# Clé API


def test_get_api_key_returns_secret_value(
    service: YoutubeService,
) -> None:
    """Vérifie la récupération de la clé API."""

    assert service._get_api_key() == API_KEY


def test_get_api_key_rejects_missing_key(
    service: YoutubeService,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Vérifie l'absence de clé API."""

    test_settings = service._settings.model_copy(
        update={
            "youtube_api_key": None,
        }
    )

    monkeypatch.setattr(
        service,
        "_settings",
        test_settings,
    )

    with pytest.raises(YoutubeConfigurationError):
        service._get_api_key()


def test_get_api_key_rejects_empty_key(
    service: YoutubeService,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Vérifie une clé API vide."""

    test_settings = service._settings.model_copy(
        update={
            "youtube_api_key": SecretStr("   "),
        }
    )

    monkeypatch.setattr(
        service,
        "_settings",
        test_settings,
    )

    with pytest.raises(YoutubeConfigurationError):
        service._get_api_key()


# Requête générique


@pytest.mark.asyncio
async def test_request_adds_api_key(
    service: YoutubeService,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Vérifie l'ajout automatique de la clé API."""

    response = build_response(payload=SEARCH_PAYLOAD)

    execute_request = AsyncMock(return_value=response)

    monkeypatch.setattr(
        service,
        "_execute_request",
        execute_request,
    )

    params: YoutubeParams = {
        "part": "snippet",
    }

    result = await service._request(
        YOUTUBE_SEARCH_ENDPOINT,
        params=params,
    )

    assert result == SEARCH_PAYLOAD

    execute_request.assert_awaited_once_with(
        endpoint=YOUTUBE_SEARCH_ENDPOINT,
        params={
            "part": "snippet",
            "key": API_KEY,
        },
    )


# Parsing JSON


def test_parse_response_payload_returns_payload(
    service: YoutubeService,
) -> None:
    """Vérifie le parsing d'un JSON valide."""

    response = build_response(payload=SEARCH_PAYLOAD)

    result = service._parse_response_payload(response)

    assert result == SEARCH_PAYLOAD


def test_parse_response_payload_rejects_empty_response(
    service: YoutubeService,
) -> None:
    """Vérifie le rejet d'une réponse vide."""

    response = build_response(content=b"")

    with pytest.raises(YoutubeResponseError):
        service._parse_response_payload(response)


def test_parse_response_payload_rejects_invalid_json(
    service: YoutubeService,
) -> None:
    """Vérifie le rejet d'un JSON invalide."""

    response = build_response(content=b"not-json")

    with pytest.raises(YoutubeResponseError):
        service._parse_response_payload(response)


# Retry


@pytest.mark.parametrize(
    "status_code",
    [
        408,
        425,
        500,
        502,
        503,
        504,
    ],
)
def test_should_retry_status_accepts_retryable_status(
    service: YoutubeService,
    status_code: int,
) -> None:
    """Vérifie les statuts temporaires hors endpoint de recherche."""

    assert (
        service._should_retry_status(
            endpoint=YOUTUBE_VIDEOS_ENDPOINT,
            status_code=status_code,
            attempt=1,
            total_attempts=2,
        )
        is True
    )


def test_should_retry_status_rejects_last_attempt(
    service: YoutubeService,
) -> None:
    """Vérifie l'arrêt des retries après la dernière tentative."""

    assert (
        service._should_retry_status(
            endpoint=YOUTUBE_VIDEOS_ENDPOINT,
            status_code=503,
            attempt=2,
            total_attempts=2,
        )
        is False
    )


@pytest.mark.parametrize(
    "status_code",
    [
        408,
        425,
        429,
        500,
        502,
        503,
        504,
    ],
)
def test_should_retry_status_rejects_search_endpoint(
    service: YoutubeService,
    status_code: int,
) -> None:
    """Vérifie qu'une recherche YouTube n'est jamais retentée."""

    assert (
        service._should_retry_status(
            endpoint=YOUTUBE_SEARCH_ENDPOINT,
            status_code=status_code,
            attempt=1,
            total_attempts=2,
        )
        is False
    )


def test_should_retry_status_rejects_non_retryable_status(
    service: YoutubeService,
) -> None:
    """Vérifie le rejet d'un statut non temporaire."""

    assert (
        service._should_retry_status(
            endpoint=YOUTUBE_VIDEOS_ENDPOINT,
            status_code=404,
            attempt=1,
            total_attempts=2,
        )
        is False
    )


@pytest.mark.asyncio
async def test_wait_before_retry_uses_exponential_delay(
    service: YoutubeService,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Vérifie le délai exponentiel."""

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

    sleep = AsyncMock()

    monkeypatch.setattr(
        "app.adapters.youtube_service.asyncio.sleep",
        sleep,
    )

    await service._wait_before_retry(
        attempt=3,
        endpoint=YOUTUBE_SEARCH_ENDPOINT,
    )

    sleep.assert_awaited_once_with(8.0)


# Erreurs HTTP


def test_raise_response_error_detects_quota(
    service: YoutubeService,
) -> None:
    """Vérifie une erreur de quota."""

    payload: YoutubePayload = {
        "error": {
            "errors": [
                {
                    "reason": "quotaExceeded",
                },
            ],
        },
    }

    response = build_response(
        status_code=403,
        payload=payload,
    )

    with pytest.raises(YoutubeQuotaError):
        service._raise_response_error(response)


@pytest.mark.parametrize(
    "status_code",
    [
        400,
        401,
        403,
    ],
)
def test_raise_response_error_detects_configuration_error(
    service: YoutubeService,
    status_code: int,
) -> None:
    """Vérifie les erreurs de configuration."""

    payload: YoutubePayload = {
        "error": {
            "message": "forbidden",
        },
    }

    response = build_response(
        status_code=status_code,
        payload=payload,
    )

    with pytest.raises(YoutubeConfigurationError):
        service._raise_response_error(response)


@pytest.mark.parametrize(
    "status_code",
    [
        408,
        504,
    ],
)
def test_raise_response_error_detects_timeout(
    service: YoutubeService,
    status_code: int,
) -> None:
    """Vérifie les erreurs de timeout HTTP."""

    response = build_response(
        status_code=status_code,
        payload={
            "error": {
                "message": "timeout",
            },
        },
    )

    with pytest.raises(YoutubeTimeoutError):
        service._raise_response_error(response)


@pytest.mark.parametrize(
    "status_code",
    [
        429,
        500,
        503,
    ],
)
def test_raise_response_error_detects_unavailable_service(
    service: YoutubeService,
    status_code: int,
) -> None:
    """Vérifie une indisponibilité temporaire."""

    response = build_response(
        status_code=status_code,
        payload={
            "error": {
                "message": "temporary failure",
            },
        },
    )

    with pytest.raises(YoutubeUnavailableError):
        service._raise_response_error(response)


def test_raise_response_error_falls_back_to_response_error(
    service: YoutubeService,
) -> None:
    """Vérifie une erreur HTTP générique."""

    response = build_response(
        status_code=404,
        payload={
            "error": {
                "message": "not found",
            },
        },
    )

    with pytest.raises(YoutubeResponseError):
        service._raise_response_error(response)


# Extraction de la raison


def test_extract_error_reason_returns_reason(
    service: YoutubeService,
) -> None:
    """Vérifie la raison structurée."""

    payload: YoutubePayload = {
        "error": {
            "errors": [
                {
                    "reason": "quotaExceeded",
                },
            ],
        },
    }

    response = build_response(
        status_code=403,
        payload=payload,
    )

    assert service._extract_error_reason(response) == "quotaExceeded"


def test_extract_error_reason_returns_message(
    service: YoutubeService,
) -> None:
    """Vérifie le message d'erreur de repli."""

    payload: YoutubePayload = {
        "error": {
            "message": "API failure",
        },
    }

    response = build_response(
        status_code=400,
        payload=payload,
    )

    assert service._extract_error_reason(response) == "API failure"


# Normalisation de requête


def test_normalize_query_normalizes_spaces(
    service: YoutubeService,
) -> None:
    """Vérifie la normalisation d'une requête."""

    assert service._normalize_query("  Ruy   Lopez  ") == "Ruy Lopez"


@pytest.mark.parametrize(
    "value",
    [
        None,
        42,
        True,
        [],
    ],
)
def test_normalize_query_rejects_non_string(
    service: YoutubeService,
    value: object,
) -> None:
    """Vérifie le type de la requête."""

    with pytest.raises(InvalidRequestError):
        service._normalize_query(value)


def test_normalize_query_rejects_empty_query(
    service: YoutubeService,
) -> None:
    """Vérifie le rejet d'une requête vide."""

    with pytest.raises(InvalidRequestError):
        service._normalize_query("   ")


# Nombre de résultats


def test_normalize_max_results_accepts_valid_value(
    service: YoutubeService,
) -> None:
    """Vérifie une limite valide."""

    assert service._normalize_max_results(5) == 5


@pytest.mark.parametrize(
    "value",
    [
        True,
        False,
        "5",
        1.5,
    ],
)
def test_normalize_max_results_rejects_non_integer(
    service: YoutubeService,
    value: object,
) -> None:
    """Vérifie le type de la limite."""

    with pytest.raises(InvalidRequestError):
        service._normalize_max_results(value)


@pytest.mark.parametrize(
    "value",
    [
        MIN_SEARCH_RESULTS - 1,
        MAX_SEARCH_RESULTS + 1,
    ],
)
def test_normalize_max_results_rejects_out_of_range(
    service: YoutubeService,
    value: int,
) -> None:
    """Vérifie les bornes de résultats."""

    with pytest.raises(InvalidRequestError):
        service._normalize_max_results(value)


# Langue


def test_normalize_language_returns_lowercase(
    service: YoutubeService,
) -> None:
    """Vérifie la normalisation de la langue."""

    assert service._normalize_language(" FR ") == "fr"


def test_normalize_language_uses_default(
    service: YoutubeService,
) -> None:
    """Vérifie la langue par défaut."""

    assert service._normalize_language(None) == LANGUAGE


@pytest.mark.parametrize(
    "value",
    [
        42,
        True,
        [],
    ],
)
def test_normalize_language_rejects_non_string(
    service: YoutubeService,
    value: object,
) -> None:
    """Vérifie le type de la langue."""

    with pytest.raises(InvalidRequestError):
        service._normalize_language(value)


@pytest.mark.parametrize(
    "value",
    [
        "f",
        "abcdefghijk",
    ],
)
def test_normalize_language_rejects_invalid_length(
    service: YoutubeService,
    value: str,
) -> None:
    """Vérifie la longueur de langue."""

    with pytest.raises(InvalidRequestError):
        service._normalize_language(value)


# Construction de recherche


def test_build_search_query_appends_suffix(
    service: YoutubeService,
) -> None:
    """Vérifie le suffixe pédagogique."""

    assert service._build_search_query(QUERY) == f"{QUERY} chess opening"


# Extraction des IDs vidéo


def test_extract_video_ids_returns_unique_ids(
    service: YoutubeService,
) -> None:
    """Vérifie l'extraction et la déduplication."""

    payload: YoutubePayload = {
        "items": [
            {
                "id": {
                    "videoId": "a",
                },
            },
            {
                "id": {
                    "videoId": "a",
                },
            },
            {
                "id": {
                    "videoId": "b",
                },
            },
        ],
    }

    assert service._extract_video_ids(payload) == [
        "a",
        "b",
    ]


def test_extract_video_ids_returns_empty_for_invalid_items(
    service: YoutubeService,
) -> None:
    """Vérifie un payload invalide."""

    payload: YoutubePayload = {
        "items": "invalid",
    }

    assert service._extract_video_ids(payload) == []


# Détails vidéo


def test_extract_video_details_returns_metadata(
    service: YoutubeService,
) -> None:
    """Vérifie l'extraction des statistiques vidéo."""

    details = service._extract_video_details(DETAILS_PAYLOAD)

    assert VIDEO_ID in details

    assert details[VIDEO_ID]["duration_seconds"] == 630

    assert details[VIDEO_ID]["view_count"] == 1234

    assert details[VIDEO_ID]["like_count"] == 120

    assert details[VIDEO_ID]["comment_count"] == 15


@pytest.mark.asyncio
async def test_get_video_details_returns_empty_without_ids(
    service: YoutubeService,
) -> None:
    """Vérifie qu'aucun appel HTTP n'est réalisé sans ID."""

    assert await service._get_video_details([]) == {}


@pytest.mark.asyncio
async def test_get_video_details_calls_videos_endpoint(
    service: YoutubeService,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Vérifie l'appel à l'endpoint de détails."""

    from app.core.constants import (
        YOUTUBE_VIDEO_DETAILS_PART,
    )

    request = AsyncMock(return_value=DETAILS_PAYLOAD)

    monkeypatch.setattr(
        service,
        "_request",
        request,
    )

    details = await service._get_video_details(
        [
            VIDEO_ID,
        ]
    )

    assert VIDEO_ID in details

    request.assert_awaited_once_with(
        YOUTUBE_VIDEOS_ENDPOINT,
        params={
            "part": YOUTUBE_VIDEO_DETAILS_PART,
            "id": VIDEO_ID,
        },
    )
