"""Stockage et recherche vectorielle avec Milvus.

Ce module centralise :

- le cycle de vie du client PyMilvus ;
- la création et le chargement de la collection ;
- l'écriture, la recherche et la suppression de documents ;
- la validation des vecteurs et des métadonnées ;
- l'état de santé du service.

Il ne contient aucune logique métier liée aux échecs ou au workflow LangGraph.
Les appels synchrones de PyMilvus sont exécutés dans des threads afin de ne pas
bloquer la boucle asynchrone.
"""

from __future__ import annotations

import asyncio
import math
from collections.abc import Callable, Mapping, Sequence
from datetime import UTC, datetime
from typing import TypedDict, TypeGuard
from uuid import uuid4

from pymilvus import DataType, MilvusClient

from app.core.config import settings
from app.core.constants import (
    MILVUS_CONTENT_FIELD,
    MILVUS_CREATED_AT_FIELD,
    MILVUS_DEFAULT_VECTOR_DIMENSION,
    MILVUS_ID_FIELD,
    MILVUS_MAX_IDENTIFIER_LENGTH,
    MILVUS_MAX_SEARCH_LIMIT,
    MILVUS_MAX_SOURCE_LENGTH,
    MILVUS_METADATA_FIELD,
    MILVUS_SOURCE_FIELD,
    MILVUS_VECTOR_FIELD,
)
from app.core.exceptions import (
    ConfigurationError,
    ErrorContext,
    MilvusConnectionError,
    MilvusDeletionError,
    MilvusIndexError,
    MilvusInsertionError,
    MilvusOperationError,
    MilvusSearchError,
    MilvusValidationError,
)
from app.core.logging import get_logger

logger = get_logger(__name__)


# Types

type JsonScalar = None | bool | int | float | str
type JsonValue = JsonScalar | list[JsonValue] | dict[str, JsonValue]
type JsonObject = dict[str, JsonValue]
type MetricType = str
type IndexType = str
type ClientOperation = Callable[[MilvusClient], object]


class VectorDocument(TypedDict, total=False):
    """Document accepté par le service Milvus."""

    id: str
    vector: Sequence[float]
    content: str
    source: str
    metadata: Mapping[str, object]
    created_at: int | datetime


class NormalizedVectorDocument(TypedDict):
    """Document validé et prêt à être transmis à PyMilvus."""

    id: str
    vector: list[float]
    content: str
    source: str
    metadata: JsonObject
    created_at: int


type MilvusClientDocument = dict[str, object]


class VectorSearchResult(TypedDict):
    """Résultat normalisé d'une recherche vectorielle."""

    id: str
    distance: float
    similarity: float
    content: str
    source: str
    metadata: JsonObject
    created_at: int


class MilvusServiceStatus(TypedDict):
    """État de santé public du service Milvus."""

    service: str
    is_ready: bool
    available: bool
    host: str
    port: int
    collection: str
    collection_exists: bool
    vector_dimension: int
    metric_type: str
    index_type: str
    search_limit: int
    timeout_seconds: float


type MilvusStatus = MilvusServiceStatus


# Configuration

OUTPUT_FIELDS = [
    MILVUS_ID_FIELD,
    MILVUS_CONTENT_FIELD,
    MILVUS_SOURCE_FIELD,
    MILVUS_METADATA_FIELD,
    MILVUS_CREATED_AT_FIELD,
]


# Service


class MilvusService:
    """Service de stockage et de recherche vectorielle."""

    # Construction

    def __init__(
        self, *, vector_dimension: int = MILVUS_DEFAULT_VECTOR_DIMENSION
    ) -> None:
        """Initialise le service sans ouvrir immédiatement de connexion."""
        self._client: MilvusClient | None = None
        self._collection_ready = False
        self._vector_dimension = self._normalize_vector_dimension(vector_dimension)
        self._lifecycle_lock = asyncio.Lock()
        self._operation_lock = asyncio.Lock()

    # Informations

    @property
    def collection_name(self) -> str:
        """Retourne le nom de la collection configurée."""
        return settings.milvus_collection_name

    @property
    def metric_type(self) -> MetricType:
        """Retourne la métrique vectorielle configurée."""
        return settings.milvus_metric_type

    @property
    def index_type(self) -> IndexType:
        """Retourne le type d'index configuré."""
        return settings.milvus_index_type

    def is_ready(self) -> bool:
        """Indique si le client et sa collection sont prêts."""
        return self._client is not None and self._collection_ready

    def get_vector_dimension(self) -> int:
        """Retourne la dimension attendue des vecteurs."""
        return self._vector_dimension

    # Cycle de vie

    async def start(self) -> None:
        """Initialise le client puis prépare sa collection."""
        async with self._lifecycle_lock:
            if self.is_ready():
                return

            logger.info("Initialisation du service Milvus.")
            client: MilvusClient | None = None

            try:
                client = await asyncio.to_thread(self._create_client)
                self._client = client
                await self._ensure_collection()
            except (ConfigurationError, MilvusConnectionError, MilvusIndexError):
                self._client = None
                self._collection_ready = False
                await self._close_client_after_failure(client)
                raise
            except Exception as error:
                self._client = None
                self._collection_ready = False
                await self._close_client_after_failure(client)
                logger.exception("Impossible d'initialiser Milvus.")
                raise MilvusConnectionError(
                    context=ErrorContext(service="milvus", operation="start"),
                    message="Le service Milvus n'a pas pu être initialisé.",
                    cause=error,
                ) from error

            logger.info("Service Milvus initialisé.")

    async def close(self) -> None:
        """Ferme le client après la fin des opérations en cours."""
        async with self._lifecycle_lock:
            client = self._client
            if client is None:
                return

            # Le verrou empêche la fermeture pendant un appel PyMilvus. La
            # référence est ensuite retirée avant close() afin que les appels
            # en attente redémarrent avec un nouveau client.
            async with self._operation_lock:
                self._client = None
                self._collection_ready = False
                logger.info("Fermeture du client Milvus.")

                try:
                    await asyncio.to_thread(client.close)
                except Exception:
                    logger.exception("Erreur lors de la fermeture de Milvus.")

    async def initialize(self) -> None:
        """Initialise le service pour compatibilité avec l'ancien cycle de vie."""
        await self.start()

    async def shutdown(self) -> None:
        """Ferme le service pour compatibilité avec l'ancien cycle de vie."""
        await self.close()

    async def _close_client_after_failure(self, client: MilvusClient | None) -> None:
        """Ferme un client dont l'initialisation a échoué."""
        if client is None:
            return

        try:
            await asyncio.to_thread(client.close)
        except Exception:
            logger.exception(
                "Impossible de fermer le client Milvus après l'échec de "
                "son initialisation."
            )

    def _create_client(self) -> MilvusClient:
        """Construit le client PyMilvus configuré."""
        uri = f"http://{settings.milvus_host}:{settings.milvus_port}"

        try:
            return MilvusClient(uri=uri, timeout=settings.milvus_timeout_seconds)
        except Exception as error:
            raise MilvusConnectionError(
                context=ErrorContext(service="milvus", operation="_create_client"),
                message="Impossible de créer le client Milvus.",
                cause=error,
            ) from error

    def _get_client(self) -> MilvusClient:
        """Retourne le client courant ou signale une mauvaise initialisation."""
        if self._client is None:
            raise MilvusConnectionError(
                context=ErrorContext(service="milvus", operation="_get_client"),
                message="Le client Milvus n'est pas initialisé.",
            )

        return self._client

    async def _ensure_client(self) -> MilvusClient:
        """Retourne un client dont la collection est prête."""
        if not self.is_ready():
            await self.start()

        return self._get_client()

    # Exécution

    async def _execute(self, operation_name: str, operation: ClientOperation) -> object:
        """Exécute une opération PyMilvus sans bloquer la boucle asynchrone."""
        while True:
            client = await self._ensure_client()

            try:
                async with self._operation_lock:
                    # close() peut avoir remplacé le client pendant l'attente
                    # du verrou. L'opération doit alors repartir sur un client
                    # entièrement initialisé.
                    if client is not self._client:
                        continue

                    return await asyncio.to_thread(operation, client)
            except MilvusOperationError:
                raise
            except Exception as error:
                logger.exception("Échec de l'opération Milvus : %s.", operation_name)
                raise MilvusOperationError(
                    context=ErrorContext(service="milvus", operation=operation_name),
                    message="Une opération Milvus a échoué.",
                    cause=error,
                ) from error

    # Collection

    async def drop_collection(self) -> None:
        """Supprime la collection Milvus."""
        await self._execute(
            "drop_collection",
            lambda client: client.drop_collection(collection_name=self.collection_name),
        )
        self._collection_ready = False

    async def _ensure_collection(self) -> None:
        """Crée si nécessaire puis charge la collection vectorielle."""
        client = self._get_client()

        try:
            exists = await asyncio.to_thread(
                client.has_collection, collection_name=self.collection_name
            )

            if not exists:
                await asyncio.to_thread(self._create_collection_sync, client)

            await asyncio.to_thread(
                client.load_collection, collection_name=self.collection_name
            )
        except Exception as error:
            logger.exception(
                "Impossible de préparer la collection Milvus %s.", self.collection_name
            )
            raise MilvusIndexError(
                context=ErrorContext(service="milvus", operation="_ensure_collection"),
                message="Impossible de préparer la collection Milvus.",
                cause=error,
            ) from error

        self._collection_ready = True

    def _create_collection_sync(self, client: MilvusClient) -> None:
        """Crée le schéma, l'index et la collection."""
        schema = client.create_schema(auto_id=False, enable_dynamic_field=False)
        schema.add_field(
            field_name=MILVUS_ID_FIELD,
            datatype=DataType.VARCHAR,
            is_primary=True,
            max_length=MILVUS_MAX_IDENTIFIER_LENGTH,
        )
        schema.add_field(
            field_name=MILVUS_VECTOR_FIELD,
            datatype=DataType.FLOAT_VECTOR,
            dim=self._vector_dimension,
        )
        schema.add_field(
            field_name=MILVUS_CONTENT_FIELD,
            datatype=DataType.VARCHAR,
            max_length=settings.embedding_max_text_length,
        )
        schema.add_field(
            field_name=MILVUS_SOURCE_FIELD,
            datatype=DataType.VARCHAR,
            max_length=MILVUS_MAX_SOURCE_LENGTH,
        )
        schema.add_field(field_name=MILVUS_METADATA_FIELD, datatype=DataType.JSON)
        schema.add_field(field_name=MILVUS_CREATED_AT_FIELD, datatype=DataType.INT64)

        index_parameters = client.prepare_index_params()
        index_parameters.add_index(
            field_name=MILVUS_VECTOR_FIELD,
            index_name=f"{MILVUS_VECTOR_FIELD}_index",
            index_type=self.index_type,
            metric_type=self.metric_type,
            params=self._get_index_parameters(),
        )
        client.create_collection(
            collection_name=self.collection_name,
            schema=schema,
            index_params=index_parameters,
        )

        logger.info(
            "Collection Milvus %s créée avec une dimension de %s.",
            self.collection_name,
            self._vector_dimension,
        )

    def _get_index_parameters(self) -> dict[str, int]:
        """Retourne les paramètres adaptés au type d'index."""
        if self.index_type == "HNSW":
            return {
                "M": settings.milvus_index_m,
                "efConstruction": settings.milvus_index_ef_construction,
            }

        if self.index_type == "IVF_FLAT":
            return {"nlist": settings.milvus_ivf_nlist}

        return {}

    def _get_search_parameters(self) -> dict[str, int]:
        """Retourne les paramètres adaptés à la recherche vectorielle."""
        if self.index_type == "HNSW":
            return {"ef": settings.milvus_search_ef}

        if self.index_type == "IVF_FLAT":
            return {"nprobe": settings.milvus_ivf_nprobe}

        return {}

    # Écriture

    async def insert_document(
        self,
        *,
        vector: Sequence[float],
        content: str,
        document_id: str | None = None,
        source: str | None = None,
        metadata: Mapping[str, object] | None = None,
    ) -> str:
        """Insère un document vectorisé et retourne son identifiant."""
        document = self._normalize_document(
            {
                "id": document_id,
                "vector": vector,
                "content": content,
                "source": source,
                "metadata": metadata,
            }
        )
        client_document = self._to_client_document(document)

        try:
            await self._execute(
                "insert",
                lambda client: client.insert(
                    collection_name=self.collection_name, data=[client_document]
                ),
            )
        except MilvusOperationError as error:
            raise MilvusInsertionError(
                context=ErrorContext(service="milvus", operation="insert_document"),
                message="L'insertion du document dans Milvus a échoué.",
                cause=error,
            ) from error

        identifier = document["id"]
        logger.debug("Document %s inséré dans Milvus.", identifier)
        return identifier

    async def insert_documents(self, documents: Sequence[VectorDocument]) -> list[str]:
        """Insère plusieurs documents vectorisés."""
        if not documents:
            return []

        normalized_documents = [
            self._normalize_document(document) for document in documents
        ]
        client_documents = [
            self._to_client_document(document) for document in normalized_documents
        ]

        try:
            await self._execute(
                "insert",
                lambda client: client.insert(
                    collection_name=self.collection_name, data=client_documents
                ),
            )
        except MilvusOperationError as error:
            raise MilvusInsertionError(
                context=ErrorContext(service="milvus", operation="insert_documents"),
                message="L'insertion des documents dans Milvus a échoué.",
                cause=error,
            ) from error

        identifiers = [document["id"] for document in normalized_documents]
        logger.info("%s document(s) inséré(s) dans Milvus.", len(identifiers))
        return identifiers

    async def upsert_document(
        self,
        *,
        document_id: str,
        vector: Sequence[float],
        content: str,
        source: str | None = None,
        metadata: Mapping[str, object] | None = None,
    ) -> str:
        """Crée ou remplace un document vectorisé."""
        document = self._normalize_document(
            {
                "id": document_id,
                "vector": vector,
                "content": content,
                "source": source,
                "metadata": metadata,
            },
            require_identifier=True,
        )
        client_document = self._to_client_document(document)

        try:
            await self._execute(
                "upsert",
                lambda client: client.upsert(
                    collection_name=self.collection_name, data=[client_document]
                ),
            )
        except MilvusOperationError as error:
            raise MilvusInsertionError(
                context=ErrorContext(service="milvus", operation="upsert_document"),
                message="La mise à jour du document dans Milvus a échoué.",
                cause=error,
            ) from error

        identifier = document["id"]
        logger.debug("Document %s mis à jour dans Milvus.", identifier)
        return identifier

    # Recherche

    async def search(
        self,
        vector: Sequence[float],
        *,
        limit: int | None = None,
        filter_expression: str | None = None,
    ) -> list[VectorSearchResult]:
        """Recherche les documents les plus proches du vecteur fourni."""
        normalized_limit = self._normalize_limit(
            limit if limit is not None else settings.milvus_search_limit
        )
        normalized_vector = self._normalize_vector(vector)
        normalized_filter = self._normalize_filter(filter_expression)

        def execute_search(client: MilvusClient) -> object:
            return client.search(
                collection_name=self.collection_name,
                data=[normalized_vector],
                anns_field=MILVUS_VECTOR_FIELD,
                filter=normalized_filter or "",
                limit=normalized_limit,
                output_fields=OUTPUT_FIELDS,
                search_params={
                    "metric_type": self.metric_type,
                    "params": self._get_search_parameters(),
                },
            )

        try:
            results = await self._execute("search", execute_search)
        except MilvusOperationError as error:
            raise MilvusSearchError(
                context=ErrorContext(service="milvus", operation="search"),
                message="La recherche vectorielle Milvus a échoué.",
                cause=error,
            ) from error

        return self._normalize_search_results(results)

    def _normalize_search_results(self, results: object) -> list[VectorSearchResult]:
        """Normalise les groupes de résultats retournés par PyMilvus."""
        if not self._is_sequence(results) or not results:
            return []

        first_group = results[0]
        if not self._is_sequence(first_group):
            return []

        normalized_results: list[VectorSearchResult] = []

        for result in first_group:
            if not self._is_mapping(result):
                continue

            entity_value = result.get("entity")
            entity: Mapping[object, object]
            entity = entity_value if self._is_mapping(entity_value) else {}
            distance = self._get_float(result.get("distance"))
            identifier = result.get("id") or entity.get(MILVUS_ID_FIELD)

            if identifier is None or distance is None:
                continue

            normalized_results.append(
                VectorSearchResult(
                    id=str(identifier),
                    distance=distance,
                    similarity=self._distance_to_similarity(distance),
                    content=self._get_result_text(entity, MILVUS_CONTENT_FIELD),
                    source=self._get_result_text(entity, MILVUS_SOURCE_FIELD),
                    metadata=self._normalize_result_metadata(
                        entity.get(MILVUS_METADATA_FIELD)
                    ),
                    created_at=self._get_integer(entity.get(MILVUS_CREATED_AT_FIELD)),
                )
            )

        return normalized_results

    def _distance_to_similarity(self, distance: float) -> float:
        """Convertit une distance Milvus en score de similarité."""
        if self.metric_type in {"COSINE", "IP"}:
            return distance

        return 1.0 / (1.0 + max(distance, 0.0))

    # Lecture

    async def get_document(self, document_id: str) -> JsonObject | None:
        """Retourne un document à partir de son identifiant."""
        normalized_identifier = self._normalize_identifier(document_id)

        try:
            results = await self._execute(
                "get",
                lambda client: client.get(
                    collection_name=self.collection_name,
                    ids=[normalized_identifier],
                    output_fields=OUTPUT_FIELDS,
                ),
            )
        except MilvusOperationError as error:
            raise MilvusSearchError(
                context=ErrorContext(service="milvus", operation="get_document"),
                message="La récupération du document Milvus a échoué.",
                cause=error,
            ) from error

        if not self._is_sequence(results) or not results:
            return None

        result = results[0]
        if not self._is_mapping(result):
            return None

        return {str(key): self._make_json_safe(value) for key, value in result.items()}

    # Suppression

    async def delete_document(self, document_id: str) -> bool:
        """Supprime un document à partir de son identifiant."""
        identifier = self._normalize_identifier(document_id)

        try:
            await self._execute(
                "delete",
                lambda client: client.delete(
                    collection_name=self.collection_name, ids=[identifier]
                ),
            )
        except MilvusOperationError as error:
            raise MilvusDeletionError(
                context=ErrorContext(service="milvus", operation="delete_document"),
                message="La suppression du document Milvus a échoué.",
                cause=error,
            ) from error

        logger.debug("Document %s supprimé de Milvus.", identifier)
        return True

    async def delete_by_filter(self, filter_expression: str) -> bool:
        """Supprime les documents correspondant à un filtre."""
        normalized_filter = self._normalize_filter(filter_expression, required=True)
        if normalized_filter is None:
            raise MilvusValidationError(
                context=ErrorContext(service="milvus", operation="delete_by_filter"),
                message="Une expression de filtre Milvus est obligatoire.",
            )

        try:
            await self._execute(
                "delete",
                lambda client: client.delete(
                    collection_name=self.collection_name, filter=normalized_filter
                ),
            )
        except MilvusOperationError as error:
            raise MilvusDeletionError(
                context=ErrorContext(service="milvus", operation="delete_by_filter"),
                message="La suppression filtrée dans Milvus a échoué.",
                cause=error,
            ) from error

        logger.debug(
            "Documents Milvus supprimés avec le filtre : %s", normalized_filter
        )
        return True

    # Validation

    def _normalize_vector_dimension(self, value: object) -> int:
        """Valide la dimension vectorielle configurée."""
        if isinstance(value, bool) or not isinstance(value, int) or value < 1:
            raise ConfigurationError(
                context=ErrorContext(service="milvus", operation="__init__"),
                message=(
                    "La dimension des vecteurs Milvus doit être un entier "
                    "supérieur à zéro."
                ),
            )

        return value

    def _normalize_document(
        self, document: Mapping[str, object], *, require_identifier: bool = False
    ) -> NormalizedVectorDocument:
        """Valide et normalise un document avant sa persistance."""
        identifier_value = document.get(MILVUS_ID_FIELD)

        if identifier_value is None:
            if require_identifier:
                raise MilvusValidationError(
                    context=ErrorContext(
                        service="milvus", operation="_normalize_document"
                    ),
                    message=(
                        "Un identifiant est obligatoire pour mettre à jour un document."
                    ),
                )
            identifier = uuid4().hex
        else:
            identifier = self._normalize_identifier(identifier_value)

        return NormalizedVectorDocument(
            id=identifier,
            vector=self._normalize_vector(document.get(MILVUS_VECTOR_FIELD)),
            content=self._normalize_content(document.get(MILVUS_CONTENT_FIELD)),
            source=self._normalize_source(document.get(MILVUS_SOURCE_FIELD)),
            metadata=self._normalize_metadata(document.get(MILVUS_METADATA_FIELD)),
            created_at=self._normalize_timestamp(document.get(MILVUS_CREATED_AT_FIELD)),
        )

    @staticmethod
    def _to_client_document(document: NormalizedVectorDocument) -> MilvusClientDocument:
        """Convertit un document typé en dictionnaire accepté par PyMilvus."""
        return dict(document)

    def _normalize_vector(self, vector: object) -> list[float]:
        """Valide la dimension et les valeurs d'un vecteur."""
        if not self._is_sequence(vector):
            raise MilvusValidationError(
                context=ErrorContext(service="milvus", operation="_normalize_vector"),
                message="Le vecteur Milvus doit être une séquence numérique.",
            )

        if len(vector) != self._vector_dimension:
            raise MilvusValidationError(
                context=ErrorContext(service="milvus", operation="_normalize_vector"),
                message=(
                    "Le vecteur doit contenir exactement "
                    f"{self._vector_dimension} dimensions."
                ),
            )

        normalized_vector: list[float] = []

        for index, value in enumerate(vector):
            if isinstance(value, bool) or not isinstance(value, int | float):
                raise MilvusValidationError(
                    context=ErrorContext(
                        service="milvus", operation="_normalize_vector"
                    ),
                    message=(f"La dimension {index} du vecteur n'est pas numérique."),
                )

            normalized_value = float(value)
            if not math.isfinite(normalized_value):
                raise MilvusValidationError(
                    context=ErrorContext(
                        service="milvus", operation="_normalize_vector"
                    ),
                    message=f"La dimension {index} du vecteur n'est pas finie.",
                )

            normalized_vector.append(normalized_value)

        return normalized_vector

    def _normalize_content(self, value: object) -> str:
        """Valide et normalise le contenu textuel d'un document."""
        if not isinstance(value, str):
            raise MilvusValidationError(
                context=ErrorContext(service="milvus", operation="_normalize_content"),
                message="Le contenu Milvus doit être une chaîne de caractères.",
            )

        normalized_value = value.strip()
        if len(normalized_value) > settings.embedding_max_text_length:
            raise MilvusValidationError(
                context=ErrorContext(service="milvus", operation="_normalize_content"),
                message=(
                    "Le contenu dépasse la longueur maximale : "
                    f"{len(normalized_value)} caractères reçus pour "
                    f"{settings.embedding_max_text_length} maximum."
                ),
            )

        return normalized_value

    def _normalize_source(self, value: object) -> str:
        """Valide et normalise la source d'un document."""
        if value is None:
            return ""

        if not isinstance(value, str):
            raise MilvusValidationError(
                context=ErrorContext(service="milvus", operation="_normalize_source"),
                message="La source Milvus doit être une chaîne de caractères.",
            )

        normalized_value = value.strip()
        if len(normalized_value) > MILVUS_MAX_SOURCE_LENGTH:
            raise MilvusValidationError(
                context=ErrorContext(service="milvus", operation="_normalize_source"),
                message=(
                    "La source Milvus ne peut pas dépasser "
                    f"{MILVUS_MAX_SOURCE_LENGTH} caractères."
                ),
            )

        return normalized_value

    def _normalize_identifier(self, value: object) -> str:
        """Valide et normalise un identifiant de document."""
        if not isinstance(value, str):
            raise MilvusValidationError(
                context=ErrorContext(
                    service="milvus", operation="_normalize_identifier"
                ),
                message="L'identifiant Milvus doit être une chaîne de caractères.",
            )

        normalized_value = value.strip()
        if not normalized_value:
            raise MilvusValidationError(
                context=ErrorContext(
                    service="milvus", operation="_normalize_identifier"
                ),
                message="L'identifiant Milvus ne peut pas être vide.",
            )

        if len(normalized_value) > MILVUS_MAX_IDENTIFIER_LENGTH:
            raise MilvusValidationError(
                context=ErrorContext(
                    service="milvus", operation="_normalize_identifier"
                ),
                message=(
                    "L'identifiant Milvus ne peut pas dépasser "
                    f"{MILVUS_MAX_IDENTIFIER_LENGTH} caractères."
                ),
            )

        return normalized_value

    def _normalize_metadata(self, value: object) -> JsonObject:
        """Valide et convertit les métadonnées en objet JSON."""
        if value is None:
            return {}

        if not self._is_mapping(value):
            raise MilvusValidationError(
                context=ErrorContext(service="milvus", operation="_normalize_metadata"),
                message="Les métadonnées Milvus doivent être un dictionnaire.",
            )

        return {str(key): self._make_json_safe(item) for key, item in value.items()}

    def _normalize_result_metadata(self, value: object) -> JsonObject:
        """Normalise les métadonnées renvoyées par PyMilvus."""
        if not self._is_mapping(value):
            return {}

        return {str(key): self._make_json_safe(item) for key, item in value.items()}

    def _normalize_timestamp(self, value: object) -> int:
        """Retourne un horodatage Unix en millisecondes."""
        if value is None:
            return int(datetime.now(UTC).timestamp() * 1_000)

        if isinstance(value, datetime):
            normalized_datetime = (
                value if value.tzinfo is not None else value.replace(tzinfo=UTC)
            )
            return int(normalized_datetime.astimezone(UTC).timestamp() * 1_000)

        if isinstance(value, bool) or not isinstance(value, int) or value < 0:
            raise MilvusValidationError(
                context=ErrorContext(
                    service="milvus", operation="_normalize_timestamp"
                ),
                message="L'horodatage Milvus est invalide.",
            )

        return value

    def _normalize_limit(self, limit: object) -> int:
        """Valide le nombre maximal de résultats."""
        if isinstance(limit, bool) or not isinstance(limit, int):
            raise MilvusValidationError(
                context=ErrorContext(service="milvus", operation="_normalize_limit"),
                message="La limite Milvus doit être un entier.",
            )

        if not 1 <= limit <= MILVUS_MAX_SEARCH_LIMIT:
            raise MilvusValidationError(
                context=ErrorContext(service="milvus", operation="_normalize_limit"),
                message=(
                    "La limite Milvus doit être comprise entre 1 et "
                    f"{MILVUS_MAX_SEARCH_LIMIT}."
                ),
            )

        return limit

    def _normalize_filter(self, value: object, *, required: bool = False) -> str | None:
        """Valide une expression de filtre Milvus."""
        if value is None:
            if required:
                raise MilvusValidationError(
                    context=ErrorContext(
                        service="milvus", operation="_normalize_filter"
                    ),
                    message="Une expression de filtre Milvus est obligatoire.",
                )
            return None

        if not isinstance(value, str):
            raise MilvusValidationError(
                context=ErrorContext(service="milvus", operation="_normalize_filter"),
                message="Le filtre Milvus doit être une chaîne de caractères.",
            )

        normalized_value = value.strip()
        if not normalized_value:
            if required:
                raise MilvusValidationError(
                    context=ErrorContext(
                        service="milvus", operation="_normalize_filter"
                    ),
                    message="Une expression de filtre Milvus est obligatoire.",
                )
            return None

        forbidden_characters = {";", "\x00", "\r", "\n"}
        if any(character in value for character in forbidden_characters):
            raise MilvusValidationError(
                context=ErrorContext(service="milvus", operation="_normalize_filter"),
                message="Le filtre Milvus contient des caractères non autorisés.",
            )

        normalized_value = value.strip()

        if not normalized_value:
            if required:
                raise MilvusValidationError(
                    context=ErrorContext(
                        service="milvus", operation="_normalize_filter"
                    ),
                    message="Une expression de filtre Milvus est obligatoire.",
                )

            return None

        return normalized_value

    # Conversion

    def _make_json_safe(self, value: object) -> JsonValue:
        """Convertit récursivement une valeur en représentation JSON."""
        if value is None or isinstance(value, bool | str | int):
            return value

        if isinstance(value, float):
            return value if math.isfinite(value) else str(value)

        if isinstance(value, datetime):
            normalized_datetime = (
                value if value.tzinfo is not None else value.replace(tzinfo=UTC)
            )
            return normalized_datetime.astimezone(UTC).isoformat()

        if self._is_mapping(value):
            return {str(key): self._make_json_safe(item) for key, item in value.items()}

        if self._is_sequence(value):
            return [self._make_json_safe(item) for item in value]

        if self._is_set(value):
            return [self._make_json_safe(item) for item in value]

        return str(value)

    def _get_result_text(self, payload: Mapping[object, object], key: str) -> str:
        """Retourne un champ textuel d'un résultat PyMilvus."""
        value = payload.get(key)
        return value if isinstance(value, str) else ""

    def _get_integer(self, value: object) -> int:
        """Retourne une valeur entière valide ou zéro."""
        if isinstance(value, bool) or not isinstance(value, int | float | str):
            return 0

        try:
            return int(value)
        except (OverflowError, ValueError):
            return 0

    def _get_float(self, value: object) -> float | None:
        """Retourne un nombre flottant fini."""
        if isinstance(value, bool) or not isinstance(value, int | float | str):
            return None

        try:
            normalized_value = float(value)
        except ValueError:
            return None

        return normalized_value if math.isfinite(normalized_value) else None

    def _is_mapping(self, value: object) -> TypeGuard[Mapping[object, object]]:
        """Indique si une valeur est un dictionnaire exploitable."""
        return isinstance(value, Mapping)

    def _is_sequence(self, value: object) -> TypeGuard[Sequence[object]]:
        """Indique si une valeur est une séquence exploitable."""
        return isinstance(value, Sequence) and not isinstance(
            value, str | bytes | bytearray
        )

    def _is_set(self, value: object) -> TypeGuard[set[object] | frozenset[object]]:
        """Indique si une valeur est un ensemble exploitable."""
        return isinstance(value, set | frozenset)

    # Santé

    async def ping(self) -> bool:
        """Vérifie que Milvus répond à une opération légère."""
        try:
            await self._execute(
                "list_collections", lambda client: client.list_collections()
            )
        except MilvusOperationError:
            logger.warning("Le service Milvus est indisponible.")
            return False
        except Exception:
            logger.exception("Erreur inattendue lors du test Milvus.")
            return False

        return True

    async def health(self) -> MilvusStatus:
        """Retourne l'état de santé du service."""
        available = await self.ping()
        collection_exists = False

        if available:
            try:
                collection_exists = bool(
                    await self._execute(
                        "has_collection",
                        lambda client: client.has_collection(
                            collection_name=self.collection_name
                        ),
                    )
                )
            except MilvusOperationError:
                logger.warning("État de la collection Milvus indisponible.")

        return MilvusServiceStatus(
            service="milvus",
            is_ready=self.is_ready(),
            available=available,
            host=str(settings.milvus_host),
            port=settings.milvus_port,
            collection=self.collection_name,
            collection_exists=collection_exists,
            vector_dimension=self._vector_dimension,
            metric_type=self.metric_type,
            index_type=self.index_type,
            search_limit=settings.milvus_search_limit,
            timeout_seconds=float(settings.milvus_timeout_seconds),
        )
