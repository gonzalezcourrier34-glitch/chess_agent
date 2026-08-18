"""Tests unitaires du service LLM Ollama de Chess Agent."""

from __future__ import annotations

from typing import cast
from unittest.mock import AsyncMock, MagicMock

import httpx
import pytest

from app.adapters.llm_service import (
    JsonObject,
    LLMService,
    OLLAMA_PROVIDER,
    OllamaChatPayload,
)
from app.core.constants import (
    LLM_CHAT_ENDPOINT,
    LLM_TAGS_ENDPOINT,
)
from app.core.exceptions import (
    ConfigurationError,
    ErrorContext,
    InvalidLLMResponseError,
    LLMGenerationError,
    OllamaConnectionError,
    OllamaModelUnavailableError,
    OllamaResponseError,
    OllamaTimeoutError,
)


# Configuration

MODEL_NAME = "qwen2.5:7b-instruct"
BASE_URL = "http://localhost:11434"

VALID_MODELS_PAYLOAD: JsonObject = {
    "models": [
        {
            "name": MODEL_NAME,
        },
    ],
}

VALID_CHAT_PAYLOAD: JsonObject = {
    "message": {
        "content": "La position est équilibrée.",
    },
}


# Exceptions de test

def build_ollama_timeout_error() -> OllamaTimeoutError:
    """Construit une erreur de timeout valide."""

    return OllamaTimeoutError(
        context=ErrorContext(
            service="llm",
            operation="test",
        ),
        message="Timeout Ollama simulé.",
    )


def build_ollama_connection_error() -> OllamaConnectionError:
    """Construit une erreur de connexion valide."""

    return OllamaConnectionError(
        context=ErrorContext(
            service="llm",
            operation="test",
        ),
        message="Erreur de connexion Ollama simulée.",
    )


def build_ollama_model_unavailable_error(
) -> OllamaModelUnavailableError:
    """Construit une erreur de modèle indisponible valide."""

    return OllamaModelUnavailableError(
        context=ErrorContext(
            service="llm",
            operation="test",
        ),
        message="Modèle Ollama indisponible.",
    )


# Fixtures

@pytest.fixture
def service() -> LLMService:
    """Construit un service LLM non initialisé."""

    return LLMService()


@pytest.fixture
def configured_service(
    service: LLMService,
    monkeypatch: pytest.MonkeyPatch,
) -> LLMService:
    """Retourne un service utilisant une configuration de test."""

    test_settings = service._settings.model_copy(
        update={
            "llm_provider": OLLAMA_PROVIDER,
            "llm_base_url": BASE_URL,
            "llm_model": MODEL_NAME,
            "llm_temperature": 0.2,
            "llm_num_predict": 512,
            "llm_timeout_seconds": 15.0,
        }
    )

    monkeypatch.setattr(
        service,
        "_settings",
        test_settings,
    )

    return service


@pytest.fixture
def mock_client() -> MagicMock:
    """Construit un faux client HTTP Ollama."""

    client = MagicMock(
        spec=httpx.AsyncClient,
    )

    client.aclose = AsyncMock()
    client.get = AsyncMock()
    client.post = AsyncMock()

    return client


# État initial

def test_service_is_not_ready_after_creation(
    service: LLMService,
) -> None:
    """Vérifie l'état initial du service."""

    assert service.is_ready() is False
    assert service.get_generated_count() == 0
    assert service.get_failed_count() == 0
    assert service.get_average_duration_ms() == 0.0


# Configuration

def test_validate_provider_accepts_ollama(
    configured_service: LLMService,
) -> None:
    """Vérifie que le fournisseur Ollama est accepté."""

    configured_service._validate_provider()


def test_validate_provider_rejects_other_provider(
    service: LLMService,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Vérifie le rejet d'un fournisseur différent."""

    test_settings = service._settings.model_copy(
        update={
            "llm_provider": "openai",
        }
    )

    monkeypatch.setattr(
        service,
        "_settings",
        test_settings,
    )

    with pytest.raises(ConfigurationError):
        service._validate_provider()


def test_get_base_url_returns_normalized_url(
    configured_service: LLMService,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Vérifie la normalisation de l'URL Ollama."""

    test_settings = configured_service._settings.model_copy(
        update={
            "llm_base_url": f"{BASE_URL}/",
        }
    )

    monkeypatch.setattr(
        configured_service,
        "_settings",
        test_settings,
    )

    assert configured_service._get_base_url() == BASE_URL


def test_get_base_url_rejects_empty_value(
    service: LLMService,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Vérifie qu'une URL vide est rejetée."""

    test_settings = service._settings.model_copy(
        update={
            "llm_base_url": "   ",
        }
    )

    monkeypatch.setattr(
        service,
        "_settings",
        test_settings,
    )

    with pytest.raises(ConfigurationError):
        service._get_base_url()


def test_get_model_name_returns_normalized_name(
    configured_service: LLMService,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Vérifie la normalisation du nom du modèle."""

    test_settings = configured_service._settings.model_copy(
        update={
            "llm_model": f"  {MODEL_NAME}  ",
        }
    )

    monkeypatch.setattr(
        configured_service,
        "_settings",
        test_settings,
    )

    assert configured_service._get_model_name() == MODEL_NAME


def test_get_model_name_rejects_empty_value(
    service: LLMService,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Vérifie qu'un nom de modèle vide est rejeté."""

    test_settings = service._settings.model_copy(
        update={
            "llm_model": "   ",
        }
    )

    monkeypatch.setattr(
        service,
        "_settings",
        test_settings,
    )

    with pytest.raises(ConfigurationError):
        service._get_model_name()


# Normalisation

def test_normalize_required_text_strips_spaces(
    service: LLMService,
) -> None:
    """Vérifie la normalisation d'un texte obligatoire."""

    result = service._normalize_required_text(
        "  Analyse cette position  ",
        field_name="Le prompt",
        operation="generate",
    )

    assert result == "Analyse cette position"


def test_normalize_required_text_rejects_non_string(
    service: LLMService,
) -> None:
    """Vérifie le rejet d'une valeur non textuelle."""

    with pytest.raises(LLMGenerationError):
        service._normalize_required_text(
            42,
            field_name="Le prompt",
            operation="generate",
        )


def test_normalize_required_text_rejects_empty_string(
    service: LLMService,
) -> None:
    """Vérifie le rejet d'un texte vide."""

    with pytest.raises(LLMGenerationError):
        service._normalize_required_text(
            "   ",
            field_name="Le prompt",
            operation="generate",
        )


# Nettoyage du raisonnement interne

@pytest.mark.parametrize(
    ("raw", "expected"),
    [
        (
            "<think>raisonnement</think>Réponse finale",
            "Réponse finale",
        ),
        (
            "texte interne</think>Réponse finale",
            "Réponse finale",
        ),
        (
            "<think>raisonnement non fermé",
            "",
        ),
        (
            "Réponse <think>interne</think> finale",
            "Réponse  finale",
        ),
        (
            "Réponse simple",
            "Réponse simple",
        ),
    ],
)
def test_remove_thinking_blocks(
    service: LLMService,
    raw: str,
    expected: str,
) -> None:
    """Vérifie le nettoyage des balises think."""

    assert service._remove_thinking_blocks(
        raw
    ) == expected


# Client

def test_get_client_rejects_uninitialized_service(
    service: LLMService,
) -> None:
    """Vérifie l'absence de client initialisé."""

    with pytest.raises(ConfigurationError):
        service._get_client()


def test_get_client_returns_initialized_client(
    service: LLMService,
    mock_client: MagicMock,
) -> None:
    """Vérifie le retour du client initialisé."""

    service._client = cast(
        httpx.AsyncClient,
        mock_client,
    )

    assert service._get_client() is mock_client


@pytest.mark.asyncio
async def test_ensure_client_starts_service_if_needed(
    service: LLMService,
    mock_client: MagicMock,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Vérifie l'initialisation automatique du client."""

    async def fake_start() -> None:
        service._client = cast(
            httpx.AsyncClient,
            mock_client,
        )

    monkeypatch.setattr(
        service,
        "start",
        fake_start,
    )

    client = await service._ensure_client()

    assert client is mock_client


# Cycle de vie

@pytest.mark.asyncio
async def test_start_initializes_client(
    configured_service: LLMService,
    mock_client: MagicMock,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Vérifie l'initialisation du service."""

    create_client = MagicMock(
        return_value=mock_client,
    )

    ensure_model_available = AsyncMock()

    monkeypatch.setattr(
        configured_service,
        "_create_client",
        create_client,
    )

    monkeypatch.setattr(
        configured_service,
        "_ensure_model_available",
        ensure_model_available,
    )

    await configured_service.start()

    assert configured_service.is_ready() is True
    assert configured_service._client is mock_client

    create_client.assert_called_once_with(
        BASE_URL
    )

    ensure_model_available.assert_awaited_once_with(
        mock_client
    )


@pytest.mark.asyncio
async def test_start_is_idempotent(
    configured_service: LLMService,
    mock_client: MagicMock,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Vérifie qu'un second démarrage ne recrée pas le client."""

    configured_service._client = cast(
        httpx.AsyncClient,
        mock_client,
    )

    create_client = MagicMock()

    monkeypatch.setattr(
        configured_service,
        "_create_client",
        create_client,
    )

    await configured_service.start()

    create_client.assert_not_called()


@pytest.mark.asyncio
async def test_start_closes_client_when_model_check_fails(
    configured_service: LLMService,
    mock_client: MagicMock,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Vérifie le nettoyage après un échec d'initialisation."""

    monkeypatch.setattr(
        configured_service,
        "_create_client",
        MagicMock(
            return_value=mock_client,
        ),
    )

    monkeypatch.setattr(
        configured_service,
        "_ensure_model_available",
        AsyncMock(
            side_effect=build_ollama_model_unavailable_error(),
        ),
    )

    close_client = AsyncMock()

    monkeypatch.setattr(
        configured_service,
        "_close_client",
        close_client,
    )

    with pytest.raises(
        OllamaModelUnavailableError
    ):
        await configured_service.start()

    close_client.assert_awaited_once()


@pytest.mark.asyncio
async def test_close_releases_client(
    service: LLMService,
    mock_client: MagicMock,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Vérifie la fermeture du client."""

    service._client = cast(
        httpx.AsyncClient,
        mock_client,
    )

    close_client = AsyncMock()

    monkeypatch.setattr(
        service,
        "_close_client",
        close_client,
    )

    await service.close()

    assert service._client is None
    assert service.is_ready() is False

    close_client.assert_awaited_once_with(
        mock_client,
        error_message=(
            "Erreur lors de la fermeture du client Ollama."
        ),
    )


@pytest.mark.asyncio
async def test_close_does_nothing_without_client(
    service: LLMService,
) -> None:
    """Vérifie la fermeture d'un service non initialisé."""

    await service.close()

    assert service._client is None


@pytest.mark.asyncio
async def test_initialize_calls_start(
    service: LLMService,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Vérifie l'alias initialize."""

    start = AsyncMock()

    monkeypatch.setattr(
        service,
        "start",
        start,
    )

    await service.initialize()

    start.assert_awaited_once()


@pytest.mark.asyncio
async def test_shutdown_calls_close(
    service: LLMService,
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
async def test_close_client_calls_aclose(
    service: LLMService,
    mock_client: MagicMock,
) -> None:
    """Vérifie la fermeture bas niveau du client HTTP."""

    await service._close_client(
        cast(
            httpx.AsyncClient,
            mock_client,
        ),
        error_message="test",
    )

    mock_client.aclose.assert_awaited_once()


@pytest.mark.asyncio
async def test_close_client_ignores_closing_error(
    service: LLMService,
    mock_client: MagicMock,
) -> None:
    """Vérifie qu'une erreur de fermeture n'est pas propagée."""

    mock_client.aclose = AsyncMock(
        side_effect=RuntimeError(
            "close failure"
        )
    )

    await service._close_client(
        cast(
            httpx.AsyncClient,
            mock_client,
        ),
        error_message="test",
    )


# Catalogue Ollama

def test_extract_model_names_returns_expected_models(
    service: LLMService,
) -> None:
    """Vérifie l'extraction des noms de modèles."""

    payload: JsonObject = {
        "models": [
            {
                "name": "model-a",
            },
            {
                "model": "model-b",
            },
            {
                "name": "   ",
            },
            "invalid",
        ],
    }

    result = service._extract_model_names(
        payload
    )

    assert result == {
        "model-a",
        "model-b",
    }


def test_extract_model_names_rejects_invalid_models_field(
    service: LLMService,
) -> None:
    """Vérifie le rejet d'un catalogue invalide."""

    payload: JsonObject = {
        "models": "invalid",
    }

    with pytest.raises(OllamaResponseError):
        service._extract_model_names(
            payload
        )


@pytest.mark.asyncio
async def test_get_available_models_returns_names(
    service: LLMService,
    mock_client: MagicMock,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Vérifie la lecture du catalogue Ollama."""

    response = httpx.Response(
        200,
        request=httpx.Request(
            "GET",
            f"{BASE_URL}{LLM_TAGS_ENDPOINT}",
        ),
        json=VALID_MODELS_PAYLOAD,
    )

    monkeypatch.setattr(
        service,
        "_request_available_models",
        AsyncMock(
            return_value=response,
        ),
    )

    result = await service._get_available_models(
        cast(
            httpx.AsyncClient,
            mock_client,
        )
    )

    assert result == {
        MODEL_NAME,
    }


@pytest.mark.asyncio
async def test_ensure_model_available_accepts_installed_model(
    configured_service: LLMService,
    mock_client: MagicMock,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Vérifie qu'un modèle installé est accepté."""

    monkeypatch.setattr(
        configured_service,
        "_get_available_models",
        AsyncMock(
            return_value={
                MODEL_NAME,
            }
        ),
    )

    await configured_service._ensure_model_available(
        cast(
            httpx.AsyncClient,
            mock_client,
        )
    )


@pytest.mark.asyncio
async def test_ensure_model_available_rejects_missing_model(
    configured_service: LLMService,
    mock_client: MagicMock,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Vérifie le rejet d'un modèle absent."""

    monkeypatch.setattr(
        configured_service,
        "_get_available_models",
        AsyncMock(
            return_value={
                "other-model",
            }
        ),
    )

    with pytest.raises(
        OllamaModelUnavailableError
    ):
        await configured_service._ensure_model_available(
            cast(
                httpx.AsyncClient,
                mock_client,
            )
        )


# Requête catalogue

@pytest.mark.asyncio
async def test_request_available_models_returns_response(
    service: LLMService,
    mock_client: MagicMock,
) -> None:
    """Vérifie une requête catalogue réussie."""

    response = httpx.Response(
        200,
        request=httpx.Request(
            "GET",
            f"{BASE_URL}{LLM_TAGS_ENDPOINT}",
        ),
        json=VALID_MODELS_PAYLOAD,
    )

    mock_client.get = AsyncMock(
        return_value=response,
    )

    result = await service._request_available_models(
        cast(
            httpx.AsyncClient,
            mock_client,
        )
    )

    assert result is response


@pytest.mark.asyncio
async def test_request_available_models_translates_timeout(
    service: LLMService,
    mock_client: MagicMock,
) -> None:
    """Vérifie la traduction d'un timeout."""

    request = httpx.Request(
        "GET",
        f"{BASE_URL}{LLM_TAGS_ENDPOINT}",
    )

    mock_client.get = AsyncMock(
        side_effect=httpx.TimeoutException(
            "timeout",
            request=request,
        )
    )

    with pytest.raises(OllamaTimeoutError):
        await service._request_available_models(
            cast(
                httpx.AsyncClient,
                mock_client,
            )
        )


@pytest.mark.asyncio
async def test_request_available_models_translates_http_error(
    service: LLMService,
    mock_client: MagicMock,
) -> None:
    """Vérifie la traduction d'une erreur HTTP."""

    request = httpx.Request(
        "GET",
        f"{BASE_URL}{LLM_TAGS_ENDPOINT}",
    )

    response = httpx.Response(
        500,
        request=request,
    )

    mock_client.get = AsyncMock(
        return_value=response,
    )

    with pytest.raises(OllamaResponseError):
        await service._request_available_models(
            cast(
                httpx.AsyncClient,
                mock_client,
            )
        )


@pytest.mark.asyncio
async def test_request_available_models_translates_network_error(
    service: LLMService,
    mock_client: MagicMock,
) -> None:
    """Vérifie la traduction d'une erreur réseau."""

    request = httpx.Request(
        "GET",
        f"{BASE_URL}{LLM_TAGS_ENDPOINT}",
    )

    mock_client.get = AsyncMock(
        side_effect=httpx.ConnectError(
            "network failure",
            request=request,
        )
    )

    with pytest.raises(
        OllamaConnectionError
    ):
        await service._request_available_models(
            cast(
                httpx.AsyncClient,
                mock_client,
            )
        )


# Payload de génération

def test_build_chat_payload_returns_expected_structure(
    configured_service: LLMService,
) -> None:
    """Vérifie le payload transmis à Ollama."""

    payload = configured_service._build_chat_payload(
        prompt="Analyse la position."
    )

    assert payload["model"] == MODEL_NAME

    assert payload["messages"] == [
        {
            "role": "user",
            "content": "Analyse la position.",
        }
    ]

    assert payload["stream"] is False

    assert (
        payload["options"]["temperature"]
        == 0.2
    )

    assert (
        payload["options"]["num_predict"]
        == 512
    )


# Requête de génération

@pytest.mark.asyncio
async def test_send_chat_request_returns_response(
    configured_service: LLMService,
    mock_client: MagicMock,
) -> None:
    """Vérifie une requête de génération réussie."""

    response = httpx.Response(
        200,
        request=httpx.Request(
            "POST",
            f"{BASE_URL}{LLM_CHAT_ENDPOINT}",
        ),
        json=VALID_CHAT_PAYLOAD,
    )

    mock_client.post = AsyncMock(
        return_value=response,
    )

    payload: OllamaChatPayload = (
        configured_service._build_chat_payload(
            prompt="Analyse."
        )
    )

    result = (
        await configured_service._send_chat_request(
            client=cast(
                httpx.AsyncClient,
                mock_client,
            ),
            payload=payload,
            model_name=MODEL_NAME,
        )
    )

    assert result is response


@pytest.mark.asyncio
async def test_send_chat_request_translates_timeout(
    configured_service: LLMService,
    mock_client: MagicMock,
) -> None:
    """Vérifie la traduction d'un timeout."""

    request = httpx.Request(
        "POST",
        f"{BASE_URL}{LLM_CHAT_ENDPOINT}",
    )

    mock_client.post = AsyncMock(
        side_effect=httpx.TimeoutException(
            "timeout",
            request=request,
        )
    )

    payload = (
        configured_service._build_chat_payload(
            prompt="Analyse."
        )
    )

    with pytest.raises(OllamaTimeoutError):
        await configured_service._send_chat_request(
            client=cast(
                httpx.AsyncClient,
                mock_client,
            ),
            payload=payload,
            model_name=MODEL_NAME,
        )


@pytest.mark.asyncio
async def test_send_chat_request_translates_connect_error(
    configured_service: LLMService,
    mock_client: MagicMock,
) -> None:
    """Vérifie la traduction d'une erreur de connexion."""

    request = httpx.Request(
        "POST",
        f"{BASE_URL}{LLM_CHAT_ENDPOINT}",
    )

    mock_client.post = AsyncMock(
        side_effect=httpx.ConnectError(
            "connection failure",
            request=request,
        )
    )

    payload = (
        configured_service._build_chat_payload(
            prompt="Analyse."
        )
    )

    with pytest.raises(
        OllamaConnectionError
    ):
        await configured_service._send_chat_request(
            client=cast(
                httpx.AsyncClient,
                mock_client,
            ),
            payload=payload,
            model_name=MODEL_NAME,
        )


@pytest.mark.asyncio
async def test_send_chat_request_translates_http_status_error(
    configured_service: LLMService,
    mock_client: MagicMock,
) -> None:
    """Vérifie la traduction d'une erreur HTTP."""

    request = httpx.Request(
        "POST",
        f"{BASE_URL}{LLM_CHAT_ENDPOINT}",
    )

    response = httpx.Response(
        500,
        request=request,
    )

    mock_client.post = AsyncMock(
        return_value=response,
    )

    payload = (
        configured_service._build_chat_payload(
            prompt="Analyse."
        )
    )

    with pytest.raises(OllamaResponseError):
        await configured_service._send_chat_request(
            client=cast(
                httpx.AsyncClient,
                mock_client,
            ),
            payload=payload,
            model_name=MODEL_NAME,
        )


@pytest.mark.asyncio
async def test_send_chat_request_translates_generic_http_error(
    configured_service: LLMService,
    mock_client: MagicMock,
) -> None:
    """Vérifie une erreur HTTP générique."""

    request = httpx.Request(
        "POST",
        f"{BASE_URL}{LLM_CHAT_ENDPOINT}",
    )

    mock_client.post = AsyncMock(
        side_effect=httpx.ReadError(
            "read failure",
            request=request,
        )
    )

    payload = (
        configured_service._build_chat_payload(
            prompt="Analyse."
        )
    )

    with pytest.raises(
        OllamaConnectionError
    ):
        await configured_service._send_chat_request(
            client=cast(
                httpx.AsyncClient,
                mock_client,
            ),
            payload=payload,
            model_name=MODEL_NAME,
        )


@pytest.mark.asyncio
async def test_send_chat_request_translates_unexpected_error(
    configured_service: LLMService,
    mock_client: MagicMock,
) -> None:
    """Vérifie une erreur inattendue."""

    mock_client.post = AsyncMock(
        side_effect=RuntimeError(
            "unexpected"
        )
    )

    payload = (
        configured_service._build_chat_payload(
            prompt="Analyse."
        )
    )

    with pytest.raises(LLMGenerationError):
        await configured_service._send_chat_request(
            client=cast(
                httpx.AsyncClient,
                mock_client,
            ),
            payload=payload,
            model_name=MODEL_NAME,
        )


# Validation JSON

def test_extract_json_mapping_returns_valid_mapping(
    service: LLMService,
) -> None:
    """Vérifie l'extraction d'un JSON valide."""

    response = httpx.Response(
        200,
        request=httpx.Request(
            "GET",
            BASE_URL,
        ),
        json={
            "models": [],
        },
    )

    result = service._extract_json_mapping(
        response
    )

    assert result == {
        "models": [],
    }


def test_extract_json_mapping_rejects_empty_response(
    service: LLMService,
) -> None:
    """Vérifie le rejet d'une réponse vide."""

    response = httpx.Response(
        200,
        request=httpx.Request(
            "GET",
            BASE_URL,
        ),
        content=b"",
    )

    with pytest.raises(OllamaResponseError):
        service._extract_json_mapping(
            response
        )


def test_extract_json_mapping_rejects_invalid_json(
    service: LLMService,
) -> None:
    """Vérifie le rejet d'un JSON invalide."""

    response = httpx.Response(
        200,
        request=httpx.Request(
            "GET",
            BASE_URL,
        ),
        content=b"invalid-json",
    )

    with pytest.raises(OllamaResponseError):
        service._extract_json_mapping(
            response
        )


# Extraction du texte

def test_extract_response_text_returns_clean_text(
    service: LLMService,
) -> None:
    """Vérifie l'extraction du texte généré."""

    result = service._extract_response_text(
        VALID_CHAT_PAYLOAD
    )

    assert result == (
        "La position est équilibrée."
    )


def test_extract_response_text_removes_thinking_block(
    service: LLMService,
) -> None:
    """Vérifie la suppression du raisonnement interne."""

    payload: JsonObject = {
        "message": {
            "content": (
                "<think>raisonnement interne</think>"
                "Réponse finale"
            ),
        },
    }

    result = service._extract_response_text(
        payload
    )

    assert result == "Réponse finale"


def test_extract_response_text_rejects_missing_message(
    service: LLMService,
) -> None:
    """Vérifie le rejet d'une réponse sans message."""

    payload: JsonObject = {}

    with pytest.raises(
        InvalidLLMResponseError
    ):
        service._extract_response_text(
            payload
        )


def test_extract_response_text_rejects_non_string_content(
    service: LLMService,
) -> None:
    """Vérifie le rejet d'un contenu non textuel."""

    payload: JsonObject = {
        "message": {
            "content": 42,
        },
    }

    with pytest.raises(
        InvalidLLMResponseError
    ):
        service._extract_response_text(
            payload
        )


def test_extract_response_text_rejects_empty_content(
    service: LLMService,
) -> None:
    """Vérifie le rejet d'une réponse vide après nettoyage."""

    payload: JsonObject = {
        "message": {
            "content": (
                "<think>interne</think>"
            ),
        },
    }

    with pytest.raises(
        InvalidLLMResponseError
    ):
        service._extract_response_text(
            payload
        )


# Génération

@pytest.mark.asyncio
async def test_generate_returns_generated_text(
    configured_service: LLMService,
    mock_client: MagicMock,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Vérifie une génération réussie."""

    configured_service._client = cast(
        httpx.AsyncClient,
        mock_client,
    )

    response = httpx.Response(
        200,
        request=httpx.Request(
            "POST",
            f"{BASE_URL}{LLM_CHAT_ENDPOINT}",
        ),
        json=VALID_CHAT_PAYLOAD,
    )

    monkeypatch.setattr(
        configured_service,
        "_send_chat_request",
        AsyncMock(
            return_value=response,
        ),
    )

    result = await configured_service.generate(
        prompt="Analyse cette position."
    )

    assert result == (
        "La position est équilibrée."
    )

    assert (
        configured_service.get_generated_count()
        == 1
    )

    assert (
        configured_service.get_failed_count()
        == 0
    )

    assert (
        configured_service.get_average_duration_ms()
        >= 0.0
    )


@pytest.mark.asyncio
async def test_generate_increments_failed_counter(
    configured_service: LLMService,
    mock_client: MagicMock,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Vérifie le compteur de générations échouées."""

    configured_service._client = cast(
        httpx.AsyncClient,
        mock_client,
    )

    monkeypatch.setattr(
        configured_service,
        "_send_chat_request",
        AsyncMock(
            side_effect=(
                build_ollama_timeout_error()
            ),
        ),
    )

    with pytest.raises(OllamaTimeoutError):
        await configured_service.generate(
            prompt="Analyse cette position."
        )

    assert (
        configured_service.get_generated_count()
        == 0
    )

    assert (
        configured_service.get_failed_count()
        == 1
    )


@pytest.mark.asyncio
async def test_generate_rejects_empty_prompt(
    configured_service: LLMService,
) -> None:
    """Vérifie le rejet d'un prompt vide."""

    with pytest.raises(
        LLMGenerationError
    ):
        await configured_service.generate(
            prompt="   "
        )


# Métriques

def test_get_average_duration_returns_zero_without_generation(
    service: LLMService,
) -> None:
    """Vérifie la moyenne avant génération."""

    assert (
        service.get_average_duration_ms()
        == 0.0
    )


def test_get_average_duration_returns_average(
    service: LLMService,
) -> None:
    """Vérifie le calcul de la durée moyenne."""

    service._generated_responses = 2
    service._total_generation_duration_ms = 30.0

    assert (
        service.get_average_duration_ms()
        == 15.0
    )


# Santé

@pytest.mark.asyncio
async def test_ping_returns_true_when_model_is_available(
    configured_service: LLMService,
    mock_client: MagicMock,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Vérifie un ping réussi."""

    configured_service._client = cast(
        httpx.AsyncClient,
        mock_client,
    )

    monkeypatch.setattr(
        configured_service,
        "_get_available_models",
        AsyncMock(
            return_value={
                MODEL_NAME,
            }
        ),
    )

    assert (
        await configured_service.ping()
        is True
    )


@pytest.mark.asyncio
async def test_ping_returns_false_when_model_is_missing(
    configured_service: LLMService,
    mock_client: MagicMock,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Vérifie le cas d'un modèle absent."""

    configured_service._client = cast(
        httpx.AsyncClient,
        mock_client,
    )

    monkeypatch.setattr(
        configured_service,
        "_get_available_models",
        AsyncMock(
            return_value={
                "other-model",
            }
        ),
    )

    assert (
        await configured_service.ping()
        is False
    )


@pytest.mark.asyncio
async def test_ping_returns_false_on_ollama_error(
    configured_service: LLMService,
    mock_client: MagicMock,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Vérifie une erreur Ollama."""

    configured_service._client = cast(
        httpx.AsyncClient,
        mock_client,
    )

    monkeypatch.setattr(
        configured_service,
        "_get_available_models",
        AsyncMock(
            side_effect=(
                build_ollama_connection_error()
            ),
        ),
    )

    assert (
        await configured_service.ping()
        is False
    )


@pytest.mark.asyncio
async def test_ping_returns_false_on_unexpected_error(
    configured_service: LLMService,
    mock_client: MagicMock,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Vérifie une erreur inattendue."""

    configured_service._client = cast(
        httpx.AsyncClient,
        mock_client,
    )

    monkeypatch.setattr(
        configured_service,
        "_get_available_models",
        AsyncMock(
            side_effect=RuntimeError(
                "unexpected"
            ),
        ),
    )

    assert (
        await configured_service.ping()
        is False
    )


@pytest.mark.asyncio
async def test_health_returns_service_status(
    configured_service: LLMService,
    mock_client: MagicMock,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Vérifie l'état de santé détaillé."""

    configured_service._client = cast(
        httpx.AsyncClient,
        mock_client,
    )

    configured_service._generated_responses = 4
    configured_service._failed_generations = 2
    configured_service._total_generation_duration_ms = 40.0

    monkeypatch.setattr(
        configured_service,
        "ping",
        AsyncMock(
            return_value=True,
        ),
    )

    status = await configured_service.health()

    assert status["service"] == "llm"
    assert status["provider"] == OLLAMA_PROVIDER
    assert status["is_ready"] is True
    assert status["available"] is True
    assert status["model"] == MODEL_NAME
    assert status["base_url"] == BASE_URL
    assert status["temperature"] == 0.2
    assert status["timeout_seconds"] == 15.0
    assert status["generated_responses"] == 4
    assert status["failed_generations"] == 2

    assert (
        status["average_generation_duration_ms"]
        == 10.0
    )