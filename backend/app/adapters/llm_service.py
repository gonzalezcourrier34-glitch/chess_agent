"""Service de génération textuelle fondé sur Ollama.

Ce module centralise :

- le cycle de vie du client HTTP ;
- la vérification du fournisseur et du modèle configurés ;
- l'envoi des requêtes de génération ;
- la validation et la normalisation des réponses Ollama ;
- le suivi des métriques et de l'état de santé du service.

Il ne construit aucun prompt métier et n'interprète pas les réponses générées.
"""

from __future__ import annotations

import asyncio
import re
from time import perf_counter
from typing import TypedDict

import httpx
from pydantic import TypeAdapter, ValidationError

from app.core.config import settings
from app.core.constants import LLM_CHAT_ENDPOINT, LLM_TAGS_ENDPOINT
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
from app.core.logging import get_logger

logger = get_logger(__name__)


# Types

type JsonScalar = None | bool | int | float | str
type JsonValue = JsonScalar | list[JsonValue] | dict[str, JsonValue]
type JsonObject = dict[str, JsonValue]


class OllamaChatMessage(TypedDict):
    """Message envoyé à l'API de chat Ollama."""

    role: str
    content: str


class OllamaChatOptions(TypedDict):
    """Options de génération transmises à Ollama."""

    temperature: float
    num_predict: int


class OllamaChatPayload(TypedDict):
    """Corps d'une requête de génération Ollama."""

    model: str
    messages: list[OllamaChatMessage]
    stream: bool
    options: OllamaChatOptions


class LLMServiceStatus(TypedDict):
    """État de santé exposé par le service LLM."""

    service: str
    provider: str
    is_ready: bool
    available: bool
    model: str
    base_url: str
    temperature: float
    timeout_seconds: float
    generated_responses: int
    failed_generations: int
    average_generation_duration_ms: float


# Configuration

SERVICE_NAME = "llm"
OLLAMA_PROVIDER = "ollama"
MILLISECONDS_PER_SECOND = 1_000

JSON_OBJECT_ADAPTER: TypeAdapter[JsonObject] = TypeAdapter(JsonObject)


# Expressions régulières

THINK_BLOCK_PATTERN = re.compile(
    r"<think\b[^>]*>.*?</think\s*>",
    flags=re.IGNORECASE | re.DOTALL
)
THINK_PREFIX_PATTERN = re.compile(
    r"\A.*?</think\s*>",
    flags=re.IGNORECASE | re.DOTALL
)
THINK_SUFFIX_PATTERN = re.compile(
    r"<think\b[^>]*>.*\Z",
    flags=re.IGNORECASE | re.DOTALL
)
THINK_TAG_PATTERN = re.compile(r"</?think\b[^>]*>", flags=re.IGNORECASE)


# Service


class LLMService:
    """Service générique de génération avec Ollama."""

    # Construction

    def __init__(self) -> None:
        """Initialise le service sans ouvrir immédiatement de connexion."""
        self._settings = settings
        self._client: httpx.AsyncClient | None = None

        self._generated_responses = 0
        self._failed_generations = 0
        self._total_generation_duration_ms = 0.0

        # Le cycle de vie et les générations sont protégés séparément. La
        # fermeture acquiert les deux verrous pour ne pas interrompre un appel.
        self._client_lock = asyncio.Lock()
        self._generation_lock = asyncio.Lock()

    # Cycle de vie

    async def start(self) -> None:
        """Initialise le client Ollama et vérifie le modèle configuré."""
        async with self._client_lock:
            if self._client is not None:
                return

            self._validate_provider()
            base_url = self._get_base_url()
            model_name = self._get_model_name()

            logger.info(
                "Initialisation du service LLM Ollama avec le modèle %s.",
                model_name
            )

            client = self._create_client(base_url)

            try:
                await self._ensure_model_available(client)
            except Exception:
                await self._close_client(
                    client,
                    error_message=(
                        "Erreur lors de la fermeture du client Ollama après "
                        "un échec d'initialisation."
                    )
                )
                raise

            self._client = client
            logger.info(
                "Service LLM Ollama initialisé avec le modèle %s.",
                model_name
            )

    async def close(self) -> None:
        """Ferme proprement le client HTTP Ollama."""
        # L'ordre génération puis client est partagé avec ``generate`` afin
        # d'éviter qu'une fermeture ne coupe une requête déjà préparée.
        async with self._generation_lock:
            async with self._client_lock:
                client = self._client

                if client is None:
                    return

                # Les nouvelles générations recréeront un client si elles sont
                # encore nécessaires après la fermeture.
                self._client = None

                logger.info("Fermeture du client Ollama.")
                await self._close_client(
                    client,
                    error_message="Erreur lors de la fermeture du client Ollama."
                )

    async def initialize(self) -> None:
        """Initialise le service LLM."""
        await self.start()

    async def shutdown(self) -> None:
        """Libère les ressources du service."""
        await self.close()

    async def _close_client(
        self,
        client: httpx.AsyncClient,
        *,
        error_message: str
    ) -> None:
        """Ferme un client sans masquer l'arrêt ou l'erreur d'origine."""
        try:
            await client.aclose()
        except Exception:
            logger.exception(error_message)

    # Configuration

    def _validate_provider(self) -> None:
        """Vérifie que le fournisseur configuré est Ollama."""
        provider = self._settings.llm_provider.strip().casefold()

        if provider == OLLAMA_PROVIDER:
            return

        raise ConfigurationError(
            context=ErrorContext(
                service=SERVICE_NAME,
                operation="_validate_provider",
                metadata={"provider": provider}
            ),
            message="LLMService nécessite le fournisseur 'ollama'."
        )

    def _get_base_url(self) -> str:
        """Retourne l'URL normalisée du serveur Ollama."""
        base_url = self._settings.llm_base_url.strip()

        if not base_url:
            raise ConfigurationError(
                context=ErrorContext(
                    service=SERVICE_NAME,
                    operation="_get_base_url"
                ),
                message="L'URL du serveur Ollama n'est pas configurée."
            )

        return base_url.rstrip("/")

    def _get_model_name(self) -> str:
        """Retourne le nom normalisé du modèle configuré."""
        model_name = self._settings.llm_model.strip()

        if not model_name:
            raise ConfigurationError(
                context=ErrorContext(
                    service=SERVICE_NAME,
                    operation="_get_model_name"
                ),
                message="Le modèle Ollama n'est pas configuré."
            )

        return model_name

    # Client HTTP

    def _create_client(self, base_url: str) -> httpx.AsyncClient:
        """Construit le client HTTP Ollama."""
        try:
            maximum_connections = self._settings.http_max_connections
            return httpx.AsyncClient(
                base_url=base_url,
                timeout=httpx.Timeout(self._settings.llm_timeout_seconds),
                limits=httpx.Limits(
                    max_connections=maximum_connections,
                    max_keepalive_connections=maximum_connections
                ),
                headers={
                    "Accept": "application/json",
                    "Content-Type": "application/json",
                    "User-Agent": self._settings.http_user_agent,
                },
                follow_redirects=True
            )
        except Exception as error:
            logger.exception("Impossible d'initialiser le client Ollama.")
            raise OllamaConnectionError(
                context=ErrorContext(
                    service=SERVICE_NAME,
                    operation="_create_client",
                    metadata={"base_url": base_url}
                ),
                message="Impossible d'initialiser le client Ollama.",
                cause=error
            ) from error

    def _get_client(self) -> httpx.AsyncClient:
        """Retourne le client Ollama initialisé."""
        if self._client is None:
            raise ConfigurationError(
                context=ErrorContext(
                    service=SERVICE_NAME,
                    operation="_get_client"
                ),
                message="Le client Ollama n'est pas initialisé."
            )

        return self._client

    async def _ensure_client(self) -> httpx.AsyncClient:
        """Retourne un client Ollama initialisé."""
        if self._client is None:
            await self.start()

        return self._get_client()

    # Normalisation

    def _normalize_required_text(
        self,
        value: object,
        *,
        field_name: str,
        operation: str
    ) -> str:
        """Valide et normalise une valeur textuelle obligatoire."""
        if not isinstance(value, str):
            raise LLMGenerationError(
                context=ErrorContext(
                    service=SERVICE_NAME,
                    operation=operation,
                    metadata={"field": field_name}
                ),
                message=f"{field_name} doit être une chaîne de caractères."
            )

        normalized_value = value.strip()

        if not normalized_value:
            raise LLMGenerationError(
                context=ErrorContext(
                    service=SERVICE_NAME,
                    operation=operation,
                    metadata={"field": field_name}
                ),
                message=f"{field_name} ne peut pas être vide."
            )

        return normalized_value

    def _remove_thinking_blocks(self, value: str) -> str:
        """Supprime le raisonnement interne éventuellement produit."""
        normalized_value = value.strip()

        # Ollama peut renvoyer un bloc complet, une fermeture sans ouverture
        # ou une ouverture non refermée selon le modèle utilisé.
        normalized_value = THINK_BLOCK_PATTERN.sub("", normalized_value)
        normalized_value = THINK_PREFIX_PATTERN.sub("", normalized_value)
        normalized_value = THINK_SUFFIX_PATTERN.sub("", normalized_value)
        normalized_value = THINK_TAG_PATTERN.sub("", normalized_value)

        return normalized_value.strip()

    # Modèles Ollama

    async def _request_available_models(
        self,
        client: httpx.AsyncClient
    ) -> httpx.Response:
        """Interroge le catalogue des modèles Ollama."""
        try:
            response = await client.get(LLM_TAGS_ENDPOINT)
            response.raise_for_status()
            return response
        except httpx.TimeoutException as error:
            raise OllamaTimeoutError(
                context=ErrorContext(
                    service=SERVICE_NAME,
                    operation="_get_available_models"
                ),
                cause=error
            ) from error
        except httpx.HTTPStatusError as error:
            raise OllamaResponseError(
                context=ErrorContext(
                    service=SERVICE_NAME,
                    operation="_get_available_models",
                    metadata={"status_code": error.response.status_code}
                ),
                message=(
                    "Ollama a retourné une erreur pendant la récupération "
                    "des modèles."
                ),
                cause=error
            ) from error
        except httpx.HTTPError as error:
            raise OllamaConnectionError(
                context=ErrorContext(
                    service=SERVICE_NAME,
                    operation="_get_available_models"
                ),
                cause=error
            ) from error

    def _extract_model_names(self, payload: JsonObject) -> set[str]:
        """Extrait les noms de modèles d'un catalogue Ollama validé."""
        models = payload.get("models")

        if not isinstance(models, list):
            raise OllamaResponseError(
                context=ErrorContext(
                    service=SERVICE_NAME,
                    operation="_get_available_models"
                ),
                message="Ollama a retourné une liste de modèles invalide."
            )

        available_models: set[str] = set()

        for item in models:
            if not isinstance(item, dict):
                continue

            for key in ("name", "model"):
                model_name = item.get(key)

                if isinstance(model_name, str) and model_name.strip():
                    available_models.add(model_name.strip())

        return available_models

    async def _get_available_models(
        self,
        client: httpx.AsyncClient
    ) -> set[str]:
        """Retourne les modèles installés dans Ollama."""
        response = await self._request_available_models(client)
        payload = self._extract_json_mapping(response)
        return self._extract_model_names(payload)

    async def _ensure_model_available(
        self,
        client: httpx.AsyncClient
    ) -> None:
        """Vérifie que le modèle configuré est installé."""
        model_name = self._get_model_name()
        available_models = await self._get_available_models(client)

        logger.debug("Modèles Ollama disponibles : %s.", sorted(available_models))

        if model_name in available_models:
            return

        raise OllamaModelUnavailableError(
            context=ErrorContext(
                service=SERVICE_NAME,
                operation="_ensure_model_available",
                metadata={
                    "model": model_name,
                    "available_models": sorted(available_models),
                }
            ),
            message=(
                "Le modèle Ollama configuré n'est pas installé : "
                f"{model_name}."
            )
        )

    # Requête de génération

    def _build_chat_payload(self, *, prompt: str) -> OllamaChatPayload:
        """Construit la requête de génération envoyée à Ollama."""
        return {
            "model": self._get_model_name(),
            "messages": [{"role": "user", "content": prompt}],
            "stream": False,
            "options": {
                "temperature": self._settings.llm_temperature,
                "num_predict": self._settings.llm_num_predict,
            },
        }

    async def _send_chat_request(
        self,
        *,
        client: httpx.AsyncClient,
        payload: OllamaChatPayload,
        model_name: str
    ) -> httpx.Response:
        """Envoie une requête de génération et traduit les erreurs HTTP."""
        try:
            response = await client.post(LLM_CHAT_ENDPOINT, json=payload)
            response.raise_for_status()
            return response
        except httpx.TimeoutException as error:
            logger.warning("Timeout durant la génération Ollama.")
            raise OllamaTimeoutError(
                context=ErrorContext(
                    service=SERVICE_NAME,
                    operation="generate",
                    metadata={"model": model_name}
                ),
                cause=error
            ) from error
        except httpx.ConnectError as error:
            logger.warning("Connexion au serveur Ollama impossible.")
            raise OllamaConnectionError(
                context=ErrorContext(
                    service=SERVICE_NAME,
                    operation="generate",
                    metadata={"base_url": self._get_base_url()}
                ),
                cause=error
            ) from error
        except httpx.HTTPStatusError as error:
            logger.warning(
                "Erreur HTTP %s retournée par Ollama.",
                error.response.status_code
            )
            raise OllamaResponseError(
                context=ErrorContext(
                    service=SERVICE_NAME,
                    operation="generate",
                    metadata={
                        "status_code": error.response.status_code,
                        "model": model_name,
                    }
                ),
                message="Ollama a retourné une erreur HTTP.",
                cause=error
            ) from error
        except httpx.HTTPError as error:
            logger.exception("Erreur HTTP durant la génération Ollama.")
            raise OllamaConnectionError(
                context=ErrorContext(
                    service=SERVICE_NAME,
                    operation="generate"
                ),
                cause=error
            ) from error
        except Exception as error:
            logger.exception("Erreur inattendue durant la génération LLM.")
            raise LLMGenerationError(
                context=ErrorContext(
                    service=SERVICE_NAME,
                    operation="generate"
                ),
                cause=error
            ) from error

    # Validation des réponses

    def _extract_json_mapping(self, response: httpx.Response) -> JsonObject:
        """Valide et retourne l'objet JSON contenu dans une réponse."""
        if not response.content:
            raise OllamaResponseError(
                context=ErrorContext(
                    service=SERVICE_NAME,
                    operation="_extract_json_mapping"
                ),
                message="Ollama a retourné une réponse vide."
            )

        try:
            return JSON_OBJECT_ADAPTER.validate_json(response.content)
        except ValidationError as error:
            raise OllamaResponseError(
                context=ErrorContext(
                    service=SERVICE_NAME,
                    operation="_extract_json_mapping"
                ),
                message="Ollama a retourné une réponse JSON invalide.",
                cause=error
            ) from error

    def _extract_response_text(self, payload: JsonObject) -> str:
        """Valide, nettoie et retourne le texte généré."""
        message = payload.get("message")

        if not isinstance(message, dict):
            raise InvalidLLMResponseError(
                context=ErrorContext(
                    service=SERVICE_NAME,
                    operation="_extract_response_text"
                ),
                message="Ollama n'a pas retourné de message exploitable."
            )

        output_text = message.get("content")

        if not isinstance(output_text, str):
            raise InvalidLLMResponseError(
                context=ErrorContext(
                    service=SERVICE_NAME,
                    operation="_extract_response_text"
                ),
                message="Ollama n'a pas retourné de contenu textuel."
            )

        normalized_text = self._remove_thinking_blocks(output_text)

        if not normalized_text:
            raise InvalidLLMResponseError(
                context=ErrorContext(
                    service=SERVICE_NAME,
                    operation="_extract_response_text"
                ),
                message=(
                    "Ollama a retourné une réponse vide après normalisation."
                )
            )

        return normalized_text

    # API de génération

    async def generate(self, *, prompt: str) -> str:
        """Génère un contenu textuel depuis un prompt complet."""
        normalized_prompt = self._normalize_required_text(
            prompt,
            field_name="Le prompt",
            operation="generate"
        )

        async with self._generation_lock:
            client = await self._ensure_client()
            payload = self._build_chat_payload(prompt=normalized_prompt)
            model_name = self._get_model_name()

            logger.debug(
                "Génération avec le modèle %s : prompt=%d caractères.",
                model_name,
                len(normalized_prompt)
            )

            started_at = perf_counter()

            try:
                response = await self._send_chat_request(
                    client=client,
                    payload=payload,
                    model_name=model_name
                )
                response_payload = self._extract_json_mapping(response)
                generated_text = self._extract_response_text(response_payload)
            except (
                InvalidLLMResponseError,
                LLMGenerationError,
                OllamaConnectionError,
                OllamaResponseError,
                OllamaTimeoutError
            ):
                self._failed_generations += 1
                raise

            duration_ms = (
                perf_counter() - started_at
            ) * MILLISECONDS_PER_SECOND
            self._generated_responses += 1
            self._total_generation_duration_ms += duration_ms

        logger.info("Contenu LLM généré avec Ollama en %.2f ms.", duration_ms)
        return generated_text

    # Informations

    def is_ready(self) -> bool:
        """Indique si le service peut être utilisé."""
        return self._client is not None

    def get_generated_count(self) -> int:
        """Retourne le nombre de générations réussies."""
        return self._generated_responses

    def get_failed_count(self) -> int:
        """Retourne le nombre de générations échouées."""
        return self._failed_generations

    def get_average_duration_ms(self) -> float:
        """Retourne la durée moyenne d'une génération réussie."""
        if self._generated_responses < 1:
            return 0.0

        return self._total_generation_duration_ms / self._generated_responses

    # Santé

    async def ping(self) -> bool:
        """Vérifie la disponibilité d'Ollama et du modèle."""
        try:
            async with self._generation_lock:
                client = await self._ensure_client()
                available_models = await self._get_available_models(client)
                return self._get_model_name() in available_models
        except (
            ConfigurationError,
            OllamaConnectionError,
            OllamaModelUnavailableError,
            OllamaResponseError,
            OllamaTimeoutError
        ):
            logger.exception("Le service Ollama est indisponible.")
            return False
        except Exception:
            logger.exception("Erreur inattendue lors du test Ollama.")
            return False

    async def health(self) -> LLMServiceStatus:
        """Retourne l'état de santé du service."""
        available = await self.ping()

        return {
            "service": SERVICE_NAME,
            "provider": self._settings.llm_provider,
            "is_ready": self.is_ready(),
            "available": available,
            "model": self._settings.llm_model,
            "base_url": self._settings.llm_base_url,
            "temperature": self._settings.llm_temperature,
            "timeout_seconds": self._settings.llm_timeout_seconds,
            "generated_responses": self.get_generated_count(),
            "failed_generations": self.get_failed_count(),
            "average_generation_duration_ms": round(
                self.get_average_duration_ms(),
                2
            ),
        }