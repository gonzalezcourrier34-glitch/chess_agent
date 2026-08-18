"""Service de génération d'embeddings du projet Chess Agent.

Ce module encapsule SentenceTransformer afin de produire les vecteurs
nécessaires à la recherche sémantique dans Milvus.

Il prend en charge :

- le chargement et la libération du modèle ;
- l'encodage distinct des requêtes et des documents ;
- la normalisation et la validation des entrées ;
- la conversion et la validation des vecteurs générés ;
- l'exposition des informations techniques et de santé du service.

Il ne contient aucune logique de recherche vectorielle ni d'accès à Milvus.
"""

from __future__ import annotations

import asyncio
from collections.abc import Iterable, Mapping, Sequence
from math import isfinite
from time import perf_counter
from typing import Protocol, SupportsFloat, TypedDict, runtime_checkable

from sentence_transformers import SentenceTransformer

from app.core.config import settings
from app.core.exceptions import (
    ConfigurationError,
    EmbeddingGenerationError,
    EmbeddingModelUnavailableError,
    ErrorContext,
)
from app.core.logging import get_logger

logger = get_logger(__name__)


# Types

Embedding = list[float]
EmbeddingBatch = list[Embedding]


class EmbeddingServiceStatus(TypedDict):
    """État de santé exposé par le service d'embedding."""

    service: str
    is_ready: bool
    available: bool
    provider: str
    model: str
    device: str
    dimension: int | None
    max_batch_size: int
    max_text_length: int
    generated_embeddings: int


@runtime_checkable
class SupportsToList(Protocol):
    """Objet convertible en collection Python par ``tolist``."""

    def tolist(self) -> object:
        """Retourne la représentation Python de l'objet."""
        ...


# Configuration

SERVICE_NAME = "embedding"
HEALTHCHECK_TEXT = "chess"
MILLISECONDS_PER_SECOND = 1_000


# Service


class EmbeddingService:
    """Service de génération d'embeddings."""

    # Construction

    def __init__(self) -> None:
        """Initialise le service sans charger immédiatement le modèle."""
        self._model: SentenceTransformer | None = None
        self._dimension: int | None = None
        self._generated_embeddings = 0

        # Le cycle de vie et les inférences sont protégés séparément pour
        # éviter les changements d'état et les encodages concurrents.
        self._model_lock = asyncio.Lock()
        self._encode_lock = asyncio.Lock()

    # Cycle de vie

    async def start(self) -> None:
        """Charge le modèle d'embedding s'il ne l'est pas déjà."""
        async with self._model_lock:
            if self._model is not None:
                return

            model_name = settings.embedding_model.strip()

            if not model_name:
                raise ConfigurationError(
                    context=ErrorContext(service=SERVICE_NAME, operation="start"),
                    message="Le nom du modèle d'embedding n'est pas configuré."
                )

            logger.info(
               "Chargement du modèle d'embedding %s sur %s.",
                model_name,
                settings.embedding_device
            )

            try:
                model = await asyncio.to_thread(
                    SentenceTransformer,
                    model_name,
                    device=settings.embedding_device
                    )
                
            except Exception as error:
                logger.exception("Impossible de charger le modèle d'embedding.")
                raise EmbeddingModelUnavailableError(
                    context=ErrorContext(service=SERVICE_NAME, operation="start"),
                    cause=error
                ) from error

            dimension = model.get_embedding_dimension()

            if dimension is None or dimension <= 0:
                raise EmbeddingModelUnavailableError(
                    context=ErrorContext(service=SERVICE_NAME, operation="start"),
                    message=(
                        "Le modèle chargé ne fournit pas de dimension "
                        "d'embedding valide."
                    )
                )

            self._model = model
            self._dimension = int(dimension)

            logger.info(
                "Modèle d'embedding %s chargé avec une dimension de %s.",
                model_name,
                self._dimension
            )

    async def close(self) -> None:
        """Libère les références vers le modèle chargé."""
        async with self._model_lock:
            if self._model is None:
                return

            async with self._encode_lock:
                logger.info("Libération du modèle d'embedding.")
                self._model = None
                self._dimension = None

    async def initialize(self) -> None:
        """Initialise le service."""
        await self.start()

    async def shutdown(self) -> None:
        """Libère les ressources du service."""
        await self.close()

    # Accès au modèle

    def _get_model(self) -> SentenceTransformer:
        """Retourne le modèle chargé."""
        if self._model is None:
            raise ConfigurationError(
                context=ErrorContext(
                    service=SERVICE_NAME,
                    operation="_get_model"
                ),
                message="Le modèle d'embedding n'est pas initialisé."
            )

        return self._model

    async def _ensure_model(self) -> SentenceTransformer:
        """Retourne le modèle après l'avoir initialisé si nécessaire."""
        if self._model is None:
            await self.start()

        return self._get_model()

    # Normalisation

    def _normalize_text(self, text: str, *, operation: str) -> str:
        """Valide et normalise un texte à encoder."""
        if not isinstance(text, str):
            raise EmbeddingGenerationError(
                context=ErrorContext(service=SERVICE_NAME, operation=operation),
                message="Le contenu à encoder doit être une chaîne de caractères."
            )

        normalized_text = text.strip()

        if not normalized_text:
            raise EmbeddingGenerationError(
                context=ErrorContext(service=SERVICE_NAME, operation=operation),
                message=(
                    "Impossible de générer un embedding à partir d'un texte vide."
                )
            )

        maximum_length = settings.embedding_max_text_length

        if len(normalized_text) > maximum_length:
            raise EmbeddingGenerationError(
                context=ErrorContext(service=SERVICE_NAME, operation=operation),
                message=(
                    "Le texte dépasse la longueur maximale autorisée pour les "
                    f"embeddings : {len(normalized_text)} caractères reçus pour "
                    f"{maximum_length} maximum."
                )
            )

        return normalized_text

    def _normalize_texts(self, texts: Sequence[str]) -> list[str]:
        """Valide et normalise un lot de textes."""
        operation = "generate_embeddings"
        normalized_texts: list[str] = []

        for index, text in enumerate(texts):
            try:
                normalized_text = self._normalize_text(text, operation=operation)
            except EmbeddingGenerationError as error:
                raise EmbeddingGenerationError(
                    context=ErrorContext(service=SERVICE_NAME, operation=operation),
                    message=f"Le texte situé à l'index {index} est invalide.",
                    cause=error
                ) from error

            normalized_texts.append(normalized_text)

        return normalized_texts

    def _validate_batch(self, texts: Sequence[str]) -> None:
        """Vérifie la structure et la taille d'un lot de documents."""
        operation = "generate_embeddings"

        if isinstance(texts, str):
            raise EmbeddingGenerationError(
                context=ErrorContext(service=SERVICE_NAME, operation=operation),
                message="Les documents à encoder doivent former une collection."
            )

        maximum_size = settings.embedding_max_batch_size

        if len(texts) > maximum_size:
            raise EmbeddingGenerationError(
                context=ErrorContext(service=SERVICE_NAME, operation=operation),
                message=(
                    f"Le lot contient trop de textes : {len(texts)} reçus pour "
                    f"{maximum_size} maximum."
                )
            )

    # Conversion

    def _get_iterable(
        self,
        value: object,
        *,
        operation: str,
        message: str
    ) -> Iterable[object]:
        """Retourne une vue itérable sûre d'un résultat d'encodage."""
        candidate = value.tolist() if isinstance(value, SupportsToList) else value

        if isinstance(candidate, (str, bytes, bytearray, Mapping)):
            raise EmbeddingGenerationError(
                context=ErrorContext(service=SERVICE_NAME, operation=operation),
                message=message
            )

        if not isinstance(candidate, Iterable):
            raise EmbeddingGenerationError(
                context=ErrorContext(service=SERVICE_NAME, operation=operation),
                message=message
            )

        return candidate

    def _convert_number(self, value: object, *, operation: str) -> float:
        """Convertit une composante numérique finie en nombre flottant."""
        if isinstance(value, bool) or not isinstance(value, SupportsFloat):
            raise EmbeddingGenerationError(
                context=ErrorContext(service=SERVICE_NAME, operation=operation),
                message=(
                    "L'embedding généré ne contient pas uniquement des valeurs "
                    "numériques."
                )
            )

        try:
            converted_value = float(value)
        except (TypeError, ValueError, OverflowError) as error:
            raise EmbeddingGenerationError(
                context=ErrorContext(service=SERVICE_NAME, operation=operation),
                message="Une composante de l'embedding ne peut pas être convertie.",
                cause=error
            ) from error

        if not isfinite(converted_value):
            raise EmbeddingGenerationError(
                context=ErrorContext(service=SERVICE_NAME, operation=operation),
                message="L'embedding généré contient une valeur non finie."
            )

        return converted_value

    def _convert_embedding(
        self,
        embedding: object,
        *,
        operation: str,
        index: int | None = None
    ) -> Embedding:
        """Convertit un embedding en liste de nombres flottants."""
        location = "" if index is None else f" situé à l'index {index}"
        values = self._get_iterable(
            embedding,
            operation=operation,
            message=f"Le résultat{location} n'est pas un embedding valide."
        )

        return [
            self._convert_number(value, operation=operation) for value in values
        ]

    def _convert_embeddings(
        self,
        embeddings: object,
        *,
        operation: str
    ) -> EmbeddingBatch:
        """Convertit un lot d'embeddings en listes de nombres flottants."""
        values = self._get_iterable(
            embeddings,
            operation=operation,
            message="Le résultat généré n'est pas un lot d'embeddings valide."
        )

        return [
            self._convert_embedding(value, operation=operation, index=index)
            for index, value in enumerate(values)
        ]

    # Validation

    def _validate_embedding_dimension(
        self,
        embedding: Embedding,
        *,
        operation: str,
        index: int | None = None
    ) -> None:
        """Vérifie la dimension d'un embedding."""
        expected_dimension = self.get_dimension()

        if len(embedding) == expected_dimension:
            return

        if index is None:
            message = (
                "La dimension de l'embedding généré est invalide : "
                f"{len(embedding)} au lieu de {expected_dimension}."
            )
        else:
            message = (
                f"La dimension de l'embedding situé à l'index {index} est "
                f"invalide : {len(embedding)} au lieu de {expected_dimension}."
            )

        raise EmbeddingGenerationError(
            context=ErrorContext(service=SERVICE_NAME, operation=operation),
            message=message
        )

    def _validate_embeddings(
        self,
        embeddings: EmbeddingBatch,
        *,
        expected_count: int,
        operation: str
    ) -> None:
        """Vérifie le nombre et la dimension des embeddings d'un lot."""
        if len(embeddings) != expected_count:
            raise EmbeddingGenerationError(
                context=ErrorContext(service=SERVICE_NAME, operation=operation),
                message=(
                    "Le nombre d'embeddings générés est invalide : "
                    f"{len(embeddings)} au lieu de {expected_count}."
                )
            )

        for index, embedding in enumerate(embeddings):
            self._validate_embedding_dimension(
                embedding,
                operation=operation,
                index=index
            )

    # Requêtes

    async def generate_embedding(
        self,
        text: str,
        *,
        count: bool = True
    ) -> Embedding:
        """Génère l'embedding d'une requête sémantique."""
        operation = "generate_embedding"
        normalized_text = self._normalize_text(text, operation=operation)
        model = await self._ensure_model()

        logger.debug("Génération d'un embedding de requête.")

        try:
            async with self._encode_lock:
                started_at = perf_counter()
                raw_embedding = await asyncio.to_thread(
                    model.encode_query,
                    normalized_text,
                    convert_to_numpy=True,
                    normalize_embeddings=True
                )
        except Exception as error:
            exception = EmbeddingGenerationError(
                context=ErrorContext(service=SERVICE_NAME, operation=operation),
                cause=error
            )
            exception.log()
            raise exception from error

        duration_ms = (perf_counter() - started_at) * MILLISECONDS_PER_SECOND
        embedding = self._convert_embedding(
            raw_embedding,
            operation=operation
        )
        self._validate_embedding_dimension(embedding, operation=operation)

        if count:
            self._generated_embeddings += 1

        logger.debug("Embedding de requête généré en %.2f ms.", duration_ms)
        return embedding

    # Documents

    async def generate_embeddings(self, texts: Sequence[str]) -> EmbeddingBatch:
        """Génère les embeddings d'un lot de documents."""
        operation = "generate_embeddings"
        self._validate_batch(texts)

        if not texts:
            return []

        normalized_texts = self._normalize_texts(texts)
        model = await self._ensure_model()

        logger.debug(
            "Génération de %s embedding(s) de document.",
            len(normalized_texts)
        )

        try:
            async with self._encode_lock:
                started_at = perf_counter()
                raw_embeddings = await asyncio.to_thread(
                    model.encode_document,
                    normalized_texts,
                    convert_to_numpy=True,
                    normalize_embeddings=True
                )
        except Exception as error:
            exception = EmbeddingGenerationError(
                context=ErrorContext(service=SERVICE_NAME, operation=operation),
                cause=error
            )
            exception.log()
            raise exception from error

        duration_ms = (perf_counter() - started_at) * MILLISECONDS_PER_SECOND
        embeddings = self._convert_embeddings(
            raw_embeddings,
            operation=operation
        )
        self._validate_embeddings(
            embeddings,
            expected_count=len(normalized_texts),
            operation=operation
        )
        self._generated_embeddings += len(embeddings)

        logger.debug(
            "%s embedding(s) de document généré(s) en %.2f ms.",
            len(embeddings),
            duration_ms
        )
        return embeddings

    # Informations

    def get_dimension(self) -> int:
        """Retourne la dimension des embeddings."""
        if self._dimension is None:
            raise ConfigurationError(
                context=ErrorContext(
                    service=SERVICE_NAME,
                    operation="get_dimension"
                ),
                message="La dimension du modèle d'embedding n'est pas disponible."
            )

        return self._dimension

    def get_generated_count(self) -> int:
        """Retourne le nombre d'embeddings générés."""
        return self._generated_embeddings

    def is_ready(self) -> bool:
        """Indique si le modèle et sa dimension sont disponibles."""
        return self._model is not None and self._dimension is not None

    # Santé

    async def ping(self) -> bool:
        """Vérifie que le modèle peut produire un embedding valide."""
        try:
            embedding = await self.generate_embedding(
                HEALTHCHECK_TEXT,
                count=False
            )
            dimension = self.get_dimension()
        except (
            ConfigurationError,
            EmbeddingGenerationError,
            EmbeddingModelUnavailableError
        ):
            logger.exception("Le modèle d'embedding est indisponible.")
            return False
        except Exception:
            logger.exception(
                "Erreur inattendue lors du test du modèle d'embedding."
            )
            return False

        if len(embedding) != dimension:
            logger.error(
                "Dimension d'embedding invalide : %s au lieu de %s.",
                len(embedding),
                dimension
            )
            return False

        return True

    async def health(self) -> EmbeddingServiceStatus:
        """Retourne l'état de santé détaillé du service."""
        available = await self.ping()
        dimension = self.get_dimension() if available else None

        return {
            "service": SERVICE_NAME,
            "is_ready": self.is_ready(),
            "available": available,
            "provider": settings.embedding_provider,
            "model": settings.embedding_model,
            "device": settings.embedding_device,
            "dimension": dimension,
            "max_batch_size": settings.embedding_max_batch_size,
            "max_text_length": settings.embedding_max_text_length,
            "generated_embeddings": self.get_generated_count(),
        }