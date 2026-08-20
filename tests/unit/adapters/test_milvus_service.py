"""Tests unitaires du service Milvus de Chess Agent."""

from __future__ import annotations

from datetime import UTC, datetime
from typing import cast
from unittest.mock import AsyncMock, MagicMock

import pytest
from app.adapters.milvus_service import (
    JsonObject,
    MilvusService,
    NormalizedVectorDocument,
    VectorDocument,
)
from app.core.constants import (
    MILVUS_CONTENT_FIELD,
    MILVUS_CREATED_AT_FIELD,
    MILVUS_ID_FIELD,
    MILVUS_MAX_IDENTIFIER_LENGTH,
    MILVUS_MAX_SEARCH_LIMIT,
    MILVUS_MAX_SOURCE_LENGTH,
    MILVUS_METADATA_FIELD,
    MILVUS_SOURCE_FIELD,
)
from app.core.exceptions import (
    ConfigurationError,
    ErrorContext,
    MilvusConnectionError,
    MilvusDeletionError,
    MilvusInsertionError,
    MilvusOperationError,
    MilvusSearchError,
    MilvusValidationError,
)
from pymilvus import MilvusClient

# Configuration

VECTOR_DIMENSION = 3

VALID_VECTOR = [
    0.1,
    0.2,
    0.3,
]

VALID_DOCUMENT_ID = "document-1"

VALID_DOCUMENT: VectorDocument = {
    "id": VALID_DOCUMENT_ID,
    "vector": VALID_VECTOR,
    "content": "Ruy Lopez opening",
    "source": "wikichess",
    "metadata": {
        "eco": "C60",
    },
    "created_at": 1_700_000_000_000,
}


# Exceptions de test


def build_operation_error(
    operation: str = "test",
) -> MilvusOperationError:
    """Construit une erreur Milvus valide pour les mocks."""

    return MilvusOperationError(
        context=ErrorContext(
            service="milvus",
            operation=operation,
        ),
        message="Erreur Milvus simulée.",
    )


# Fixtures


@pytest.fixture
def service() -> MilvusService:
    """Construit un service Milvus avec une petite dimension."""

    return MilvusService(vector_dimension=VECTOR_DIMENSION)


@pytest.fixture
def client() -> MagicMock:
    """Construit un faux client PyMilvus."""

    mocked_client = MagicMock(spec=MilvusClient)

    return mocked_client


# Construction


def test_service_is_not_ready_after_creation(
    service: MilvusService,
) -> None:
    """Vérifie l'état initial du service."""

    assert service.is_ready() is False
    assert service.get_vector_dimension() == VECTOR_DIMENSION


@pytest.mark.parametrize(
    "dimension",
    [
        0,
        -1,
        True,
        False,
        1.5,
        "3",
    ],
)
def test_constructor_rejects_invalid_vector_dimension(
    dimension: object,
) -> None:
    """Vérifie le rejet d'une dimension invalide."""

    with pytest.raises(ConfigurationError):
        MilvusService(
            vector_dimension=dimension  # type: ignore[arg-type]
        )


def test_constructor_accepts_positive_dimension() -> None:
    """Vérifie l'acceptation d'une dimension positive."""

    service = MilvusService(vector_dimension=128)

    assert service.get_vector_dimension() == 128


# Informations


def test_collection_name_returns_configured_name(
    service: MilvusService,
) -> None:
    """Vérifie l'accès au nom de collection."""

    assert isinstance(
        service.collection_name,
        str,
    )

    assert service.collection_name


def test_metric_type_returns_configured_metric(
    service: MilvusService,
) -> None:
    """Vérifie l'accès à la métrique."""

    assert isinstance(
        service.metric_type,
        str,
    )

    assert service.metric_type


def test_index_type_returns_configured_index(
    service: MilvusService,
) -> None:
    """Vérifie l'accès au type d'index."""

    assert isinstance(
        service.index_type,
        str,
    )

    assert service.index_type


def test_is_ready_requires_client_and_collection(
    service: MilvusService,
    client: MagicMock,
) -> None:
    """Vérifie les deux conditions de disponibilité."""

    service._client = cast(
        MilvusClient,
        client,
    )

    assert service.is_ready() is False

    service._collection_ready = True

    assert service.is_ready() is True


# Cycle de vie


@pytest.mark.asyncio
async def test_start_initializes_client_and_collection(
    service: MilvusService,
    client: MagicMock,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Vérifie l'initialisation du service."""

    monkeypatch.setattr(
        service,
        "_create_client",
        MagicMock(return_value=client),
    )

    ensure_collection = AsyncMock()

    monkeypatch.setattr(
        service,
        "_ensure_collection",
        ensure_collection,
    )

    await service.start()

    assert service._client is client

    ensure_collection.assert_awaited_once()


@pytest.mark.asyncio
async def test_start_is_idempotent(
    service: MilvusService,
    client: MagicMock,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Vérifie qu'un service prêt n'est pas réinitialisé."""

    service._client = cast(
        MilvusClient,
        client,
    )
    service._collection_ready = True

    create_client = MagicMock()

    monkeypatch.setattr(
        service,
        "_create_client",
        create_client,
    )

    await service.start()

    create_client.assert_not_called()


@pytest.mark.asyncio
async def test_start_resets_state_on_unexpected_error(
    service: MilvusService,
    client: MagicMock,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Vérifie le nettoyage après une erreur inattendue."""

    monkeypatch.setattr(
        service,
        "_create_client",
        MagicMock(return_value=client),
    )

    monkeypatch.setattr(
        service,
        "_ensure_collection",
        AsyncMock(side_effect=RuntimeError("initialization failure")),
    )

    close_after_failure = AsyncMock()

    monkeypatch.setattr(
        service,
        "_close_client_after_failure",
        close_after_failure,
    )

    with pytest.raises(MilvusConnectionError):
        await service.start()

    assert service._client is None
    assert service._collection_ready is False

    close_after_failure.assert_awaited_once_with(client)


@pytest.mark.asyncio
async def test_close_releases_client(
    service: MilvusService,
    client: MagicMock,
) -> None:
    """Vérifie la fermeture du client Milvus."""

    service._client = cast(
        MilvusClient,
        client,
    )
    service._collection_ready = True

    await service.close()

    assert service._client is None
    assert service._collection_ready is False

    client.close.assert_called_once()


@pytest.mark.asyncio
async def test_close_does_nothing_without_client(
    service: MilvusService,
) -> None:
    """Vérifie la fermeture d'un service non initialisé."""

    await service.close()

    assert service._client is None


@pytest.mark.asyncio
async def test_close_ignores_client_closing_error(
    service: MilvusService,
    client: MagicMock,
) -> None:
    """Vérifie qu'une erreur de fermeture n'est pas propagée."""

    client.close.side_effect = RuntimeError("close failure")

    service._client = cast(
        MilvusClient,
        client,
    )
    service._collection_ready = True

    await service.close()

    assert service._client is None
    assert service._collection_ready is False


@pytest.mark.asyncio
async def test_initialize_calls_start(
    service: MilvusService,
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
    service: MilvusService,
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
async def test_close_client_after_failure_does_nothing_without_client(
    service: MilvusService,
) -> None:
    """Vérifie l'absence de fermeture sans client."""

    await service._close_client_after_failure(None)


@pytest.mark.asyncio
async def test_close_client_after_failure_closes_client(
    service: MilvusService,
    client: MagicMock,
) -> None:
    """Vérifie la fermeture après un échec d'initialisation."""

    await service._close_client_after_failure(
        cast(
            MilvusClient,
            client,
        )
    )

    client.close.assert_called_once()


# Client


def test_get_client_rejects_uninitialized_service(
    service: MilvusService,
) -> None:
    """Vérifie l'absence de client."""

    with pytest.raises(MilvusConnectionError):
        service._get_client()


def test_get_client_returns_current_client(
    service: MilvusService,
    client: MagicMock,
) -> None:
    """Vérifie la récupération du client courant."""

    service._client = cast(
        MilvusClient,
        client,
    )

    assert service._get_client() is client


@pytest.mark.asyncio
async def test_ensure_client_starts_service_if_needed(
    service: MilvusService,
    client: MagicMock,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Vérifie l'initialisation automatique."""

    async def fake_start() -> None:
        service._client = cast(
            MilvusClient,
            client,
        )
        service._collection_ready = True

    monkeypatch.setattr(
        service,
        "start",
        fake_start,
    )

    result = await service._ensure_client()

    assert result is client


# Exécution


@pytest.mark.asyncio
async def test_execute_returns_operation_result(
    service: MilvusService,
    client: MagicMock,
) -> None:
    """Vérifie une opération Milvus réussie."""

    service._client = cast(
        MilvusClient,
        client,
    )
    service._collection_ready = True

    result = await service._execute(
        "test",
        lambda current_client: "ok" if current_client is client else "invalid",
    )

    assert result == "ok"


@pytest.mark.asyncio
async def test_execute_preserves_milvus_operation_error(
    service: MilvusService,
    client: MagicMock,
) -> None:
    """Vérifie qu'une erreur Milvus explicite n'est pas retraduite."""

    service._client = cast(
        MilvusClient,
        client,
    )
    service._collection_ready = True

    error = build_operation_error()

    def failing_operation(
        _: MilvusClient,
    ) -> object:
        raise error

    with pytest.raises(MilvusOperationError) as raised:
        await service._execute(
            "test",
            failing_operation,
        )

    assert raised.value is error


@pytest.mark.asyncio
async def test_execute_translates_unexpected_error(
    service: MilvusService,
    client: MagicMock,
) -> None:
    """Vérifie la traduction d'une erreur inattendue."""

    service._client = cast(
        MilvusClient,
        client,
    )
    service._collection_ready = True

    def failing_operation(
        _: MilvusClient,
    ) -> object:
        raise RuntimeError("failure")

    with pytest.raises(MilvusOperationError):
        await service._execute(
            "test",
            failing_operation,
        )


# Paramètres d'index


def test_get_index_parameters_returns_dict(
    service: MilvusService,
) -> None:
    """Vérifie la structure des paramètres d'index."""

    parameters = service._get_index_parameters()

    assert isinstance(
        parameters,
        dict,
    )


def test_get_search_parameters_returns_dict(
    service: MilvusService,
) -> None:
    """Vérifie la structure des paramètres de recherche."""

    parameters = service._get_search_parameters()

    assert isinstance(
        parameters,
        dict,
    )


# Validation de dimension


@pytest.mark.parametrize(
    "dimension",
    [
        0,
        -1,
        True,
        False,
        1.5,
        "3",
        None,
    ],
)
def test_normalize_vector_dimension_rejects_invalid_value(
    service: MilvusService,
    dimension: object,
) -> None:
    """Vérifie le rejet d'une dimension invalide."""

    with pytest.raises(ConfigurationError):
        service._normalize_vector_dimension(dimension)


def test_normalize_vector_dimension_accepts_positive_integer(
    service: MilvusService,
) -> None:
    """Vérifie une dimension valide."""

    assert service._normalize_vector_dimension(3) == 3


# Validation vectorielle


def test_normalize_vector_returns_float_values(
    service: MilvusService,
) -> None:
    """Vérifie la normalisation d'un vecteur."""

    result = service._normalize_vector(
        [
            1,
            2.5,
            3,
        ]
    )

    assert result == [
        1.0,
        2.5,
        3.0,
    ]


@pytest.mark.parametrize(
    "value",
    [
        None,
        "abc",
        1,
        {},
    ],
)
def test_normalize_vector_rejects_non_sequence(
    service: MilvusService,
    value: object,
) -> None:
    """Vérifie qu'un vecteur doit être une séquence."""

    with pytest.raises(MilvusValidationError):
        service._normalize_vector(value)


def test_normalize_vector_rejects_wrong_dimension(
    service: MilvusService,
) -> None:
    """Vérifie la dimension du vecteur."""

    with pytest.raises(MilvusValidationError):
        service._normalize_vector(
            [
                0.1,
                0.2,
            ]
        )


@pytest.mark.parametrize(
    "value",
    [
        True,
        "0.2",
        None,
    ],
)
def test_normalize_vector_rejects_non_numeric_component(
    service: MilvusService,
    value: object,
) -> None:
    """Vérifie le rejet d'une composante non numérique."""

    vector = [
        0.1,
        value,
        0.3,
    ]

    with pytest.raises(MilvusValidationError):
        service._normalize_vector(vector)


@pytest.mark.parametrize(
    "value",
    [
        float("inf"),
        float("-inf"),
        float("nan"),
    ],
)
def test_normalize_vector_rejects_non_finite_component(
    service: MilvusService,
    value: float,
) -> None:
    """Vérifie le rejet d'une composante non finie."""

    with pytest.raises(MilvusValidationError):
        service._normalize_vector(
            [
                0.1,
                value,
                0.3,
            ]
        )


# Identifiants


def test_normalize_identifier_strips_spaces(
    service: MilvusService,
) -> None:
    """Vérifie la normalisation d'un identifiant."""

    assert service._normalize_identifier("  document-1  ") == "document-1"


@pytest.mark.parametrize(
    "value",
    [
        None,
        42,
        True,
        [],
    ],
)
def test_normalize_identifier_rejects_non_string(
    service: MilvusService,
    value: object,
) -> None:
    """Vérifie qu'un identifiant doit être textuel."""

    with pytest.raises(MilvusValidationError):
        service._normalize_identifier(value)


def test_normalize_identifier_rejects_empty_value(
    service: MilvusService,
) -> None:
    """Vérifie le rejet d'un identifiant vide."""

    with pytest.raises(MilvusValidationError):
        service._normalize_identifier("   ")


def test_normalize_identifier_rejects_long_value(
    service: MilvusService,
) -> None:
    """Vérifie la longueur maximale d'un identifiant."""

    value = "x" * (MILVUS_MAX_IDENTIFIER_LENGTH + 1)

    with pytest.raises(MilvusValidationError):
        service._normalize_identifier(value)


# Contenu


def test_normalize_content_strips_spaces(
    service: MilvusService,
) -> None:
    """Vérifie la normalisation du contenu."""

    assert service._normalize_content("  Ruy Lopez  ") == "Ruy Lopez"


@pytest.mark.parametrize(
    "value",
    [
        None,
        42,
        True,
        [],
    ],
)
def test_normalize_content_rejects_non_string(
    service: MilvusService,
    value: object,
) -> None:
    """Vérifie le type du contenu."""

    with pytest.raises(MilvusValidationError):
        service._normalize_content(value)


# Source


def test_normalize_source_returns_empty_string_for_none(
    service: MilvusService,
) -> None:
    """Vérifie la source absente."""

    assert service._normalize_source(None) == ""


def test_normalize_source_strips_spaces(
    service: MilvusService,
) -> None:
    """Vérifie la normalisation de la source."""

    assert service._normalize_source("  wikichess  ") == "wikichess"


def test_normalize_source_rejects_non_string(
    service: MilvusService,
) -> None:
    """Vérifie le type de la source."""

    with pytest.raises(MilvusValidationError):
        service._normalize_source(42)


def test_normalize_source_rejects_long_value(
    service: MilvusService,
) -> None:
    """Vérifie la longueur maximale de la source."""

    value = "x" * (MILVUS_MAX_SOURCE_LENGTH + 1)

    with pytest.raises(MilvusValidationError):
        service._normalize_source(value)


# Métadonnées


def test_normalize_metadata_returns_empty_dict_for_none(
    service: MilvusService,
) -> None:
    """Vérifie les métadonnées absentes."""

    assert service._normalize_metadata(None) == {}


def test_normalize_metadata_returns_json_safe_mapping(
    service: MilvusService,
) -> None:
    """Vérifie la conversion JSON des métadonnées."""

    metadata = service._normalize_metadata(
        {
            "eco": "C60",
            "depth": 15,
            "active": True,
        }
    )

    expected: JsonObject = {
        "eco": "C60",
        "depth": 15,
        "active": True,
    }

    assert metadata == expected


def test_normalize_metadata_rejects_non_mapping(
    service: MilvusService,
) -> None:
    """Vérifie que les métadonnées doivent être un mapping."""

    with pytest.raises(MilvusValidationError):
        service._normalize_metadata(
            [
                "invalid",
            ]
        )


# Timestamp


def test_normalize_timestamp_returns_existing_integer(
    service: MilvusService,
) -> None:
    """Vérifie un timestamp déjà normalisé."""

    assert service._normalize_timestamp(123456) == 123456


def test_normalize_timestamp_converts_datetime(
    service: MilvusService,
) -> None:
    """Vérifie la conversion d'une date UTC."""

    value = datetime(
        2026,
        8,
        18,
        10,
        0,
        tzinfo=UTC,
    )

    result = service._normalize_timestamp(value)

    assert isinstance(
        result,
        int,
    )

    assert result > 0


def test_normalize_timestamp_generates_current_time_for_none(
    service: MilvusService,
) -> None:
    """Vérifie la génération automatique du timestamp."""

    result = service._normalize_timestamp(None)

    assert isinstance(
        result,
        int,
    )

    assert result > 0


@pytest.mark.parametrize(
    "value",
    [
        True,
        False,
        -1,
        1.5,
        "123",
    ],
)
def test_normalize_timestamp_rejects_invalid_value(
    service: MilvusService,
    value: object,
) -> None:
    """Vérifie le rejet d'un timestamp invalide."""

    with pytest.raises(MilvusValidationError):
        service._normalize_timestamp(value)


# Limite


def test_normalize_limit_accepts_valid_value(
    service: MilvusService,
) -> None:
    """Vérifie une limite valide."""

    assert service._normalize_limit(5) == 5


@pytest.mark.parametrize(
    "value",
    [
        0,
        -1,
        True,
        False,
        1.5,
        "5",
        MILVUS_MAX_SEARCH_LIMIT + 1,
    ],
)
def test_normalize_limit_rejects_invalid_value(
    service: MilvusService,
    value: object,
) -> None:
    """Vérifie le rejet d'une limite invalide."""

    with pytest.raises(MilvusValidationError):
        service._normalize_limit(value)


# Filtre


def test_normalize_filter_returns_none_for_none(
    service: MilvusService,
) -> None:
    """Vérifie un filtre facultatif absent."""

    assert service._normalize_filter(None) is None


def test_normalize_filter_returns_none_for_empty_string(
    service: MilvusService,
) -> None:
    """Vérifie un filtre facultatif vide."""

    assert service._normalize_filter("   ") is None


def test_normalize_filter_strips_spaces(
    service: MilvusService,
) -> None:
    """Vérifie la normalisation du filtre."""

    assert (
        service._normalize_filter("  source == 'wikichess'  ")
        == "source == 'wikichess'"
    )


@pytest.mark.parametrize(
    "value",
    [
        "source == 'x'; drop",
        "source == 'x'\n",
        "source == 'x'\r",
        "source == 'x'\x00",
    ],
)
def test_normalize_filter_rejects_forbidden_characters(
    service: MilvusService,
    value: str,
) -> None:
    """Vérifie le rejet de caractères interdits."""

    with pytest.raises(MilvusValidationError):
        service._normalize_filter(value)


def test_normalize_filter_rejects_missing_required_filter(
    service: MilvusService,
) -> None:
    """Vérifie qu'un filtre obligatoire doit être renseigné."""

    with pytest.raises(MilvusValidationError):
        service._normalize_filter(
            None,
            required=True,
        )


# Documents


def test_normalize_document_returns_typed_document(
    service: MilvusService,
) -> None:
    """Vérifie la normalisation complète d'un document."""

    normalized = service._normalize_document(VALID_DOCUMENT)

    assert normalized["id"] == VALID_DOCUMENT_ID
    assert normalized["vector"] == VALID_VECTOR
    assert normalized["content"] == "Ruy Lopez opening"
    assert normalized["source"] == "wikichess"
    assert normalized["metadata"]["eco"] == "C60"
    assert normalized["created_at"] == 1_700_000_000_000


def test_normalize_document_generates_identifier(
    service: MilvusService,
) -> None:
    """Vérifie la génération automatique d'un identifiant."""

    document: VectorDocument = {
        "vector": VALID_VECTOR,
        "content": "Ruy Lopez",
    }

    normalized = service._normalize_document(document)

    assert normalized["id"]


def test_normalize_document_requires_identifier_for_upsert(
    service: MilvusService,
) -> None:
    """Vérifie l'obligation d'un identifiant pour un upsert."""

    document: VectorDocument = {
        "vector": VALID_VECTOR,
        "content": "Ruy Lopez",
    }

    with pytest.raises(MilvusValidationError):
        service._normalize_document(
            document,
            require_identifier=True,
        )


def test_to_client_document_returns_dictionary(
    service: MilvusService,
) -> None:
    """Vérifie la conversion pour PyMilvus."""

    document: NormalizedVectorDocument = {
        "id": VALID_DOCUMENT_ID,
        "vector": VALID_VECTOR,
        "content": "Ruy Lopez",
        "source": "wikichess",
        "metadata": {
            "eco": "C60",
        },
        "created_at": 123456,
    }

    result = service._to_client_document(document)

    assert isinstance(
        result,
        dict,
    )

    assert result["id"] == VALID_DOCUMENT_ID


# Écriture


@pytest.mark.asyncio
async def test_insert_document_returns_identifier(
    service: MilvusService,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Vérifie l'insertion d'un document."""

    execute = AsyncMock(return_value=None)

    monkeypatch.setattr(
        service,
        "_execute",
        execute,
    )

    identifier = await service.insert_document(
        document_id=VALID_DOCUMENT_ID,
        vector=VALID_VECTOR,
        content="Ruy Lopez",
        source="wikichess",
        metadata={
            "eco": "C60",
        },
    )

    assert identifier == VALID_DOCUMENT_ID

    execute.assert_awaited_once()


@pytest.mark.asyncio
async def test_insert_document_translates_operation_error(
    service: MilvusService,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Vérifie la traduction d'une erreur d'insertion."""

    monkeypatch.setattr(
        service,
        "_execute",
        AsyncMock(side_effect=build_operation_error("insert")),
    )

    with pytest.raises(MilvusInsertionError):
        await service.insert_document(
            document_id=VALID_DOCUMENT_ID,
            vector=VALID_VECTOR,
            content="Ruy Lopez",
        )


@pytest.mark.asyncio
async def test_insert_documents_returns_empty_list_for_empty_batch(
    service: MilvusService,
) -> None:
    """Vérifie l'insertion d'un lot vide."""

    result = await service.insert_documents([])

    assert result == []


@pytest.mark.asyncio
async def test_insert_documents_returns_identifiers(
    service: MilvusService,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Vérifie l'insertion d'un lot."""

    execute = AsyncMock(return_value=None)

    monkeypatch.setattr(
        service,
        "_execute",
        execute,
    )

    documents: list[VectorDocument] = [
        {
            "id": "doc-1",
            "vector": VALID_VECTOR,
            "content": "Document 1",
        },
        {
            "id": "doc-2",
            "vector": VALID_VECTOR,
            "content": "Document 2",
        },
    ]

    identifiers = await service.insert_documents(documents)

    assert identifiers == [
        "doc-1",
        "doc-2",
    ]


@pytest.mark.asyncio
async def test_upsert_document_returns_identifier(
    service: MilvusService,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Vérifie la mise à jour d'un document."""

    monkeypatch.setattr(
        service,
        "_execute",
        AsyncMock(return_value=None),
    )

    identifier = await service.upsert_document(
        document_id=VALID_DOCUMENT_ID,
        vector=VALID_VECTOR,
        content="Updated",
    )

    assert identifier == VALID_DOCUMENT_ID


# Recherche


def test_normalize_search_results_returns_empty_for_invalid_value(
    service: MilvusService,
) -> None:
    """Vérifie un résultat PyMilvus invalide."""

    assert service._normalize_search_results(None) == []


def test_normalize_search_results_returns_normalized_result(
    service: MilvusService,
) -> None:
    """Vérifie la conversion d'un résultat PyMilvus."""

    raw_results = [
        [
            {
                "id": VALID_DOCUMENT_ID,
                "distance": 0.9,
                "entity": {
                    MILVUS_CONTENT_FIELD: "Ruy Lopez",
                    MILVUS_SOURCE_FIELD: "wikichess",
                    MILVUS_METADATA_FIELD: {
                        "eco": "C60",
                    },
                    MILVUS_CREATED_AT_FIELD: 123456,
                },
            }
        ]
    ]

    results = service._normalize_search_results(raw_results)

    assert len(results) == 1

    result = results[0]

    assert result["id"] == VALID_DOCUMENT_ID
    assert result["distance"] == 0.9
    assert result["content"] == "Ruy Lopez"
    assert result["source"] == "wikichess"
    assert result["metadata"]["eco"] == "C60"
    assert result["created_at"] == 123456


@pytest.mark.asyncio
async def test_search_returns_normalized_results(
    service: MilvusService,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Vérifie une recherche vectorielle."""

    raw_results = [
        [
            {
                "id": VALID_DOCUMENT_ID,
                "distance": 0.8,
                "entity": {
                    MILVUS_CONTENT_FIELD: "Ruy Lopez",
                    MILVUS_SOURCE_FIELD: "wikichess",
                    MILVUS_METADATA_FIELD: {},
                    MILVUS_CREATED_AT_FIELD: 123,
                },
            }
        ]
    ]

    monkeypatch.setattr(
        service,
        "_execute",
        AsyncMock(return_value=raw_results),
    )

    results = await service.search(
        VALID_VECTOR,
        limit=1,
    )

    assert len(results) == 1
    assert results[0]["id"] == VALID_DOCUMENT_ID


@pytest.mark.asyncio
async def test_search_translates_operation_error(
    service: MilvusService,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Vérifie la traduction d'une erreur de recherche."""

    monkeypatch.setattr(
        service,
        "_execute",
        AsyncMock(side_effect=build_operation_error("search")),
    )

    with pytest.raises(MilvusSearchError):
        await service.search(
            VALID_VECTOR,
            limit=1,
        )


# Similarité


def test_distance_to_similarity_returns_metric_value_for_cosine(
    service: MilvusService,
) -> None:
    """Vérifie COSINE ou IP."""

    if service.metric_type in {
        "COSINE",
        "IP",
    }:
        assert service._distance_to_similarity(0.8) == 0.8


def test_distance_to_similarity_is_non_negative(
    service: MilvusService,
) -> None:
    """Vérifie que la similarité retournée est numérique."""

    result = service._distance_to_similarity(0.5)

    assert isinstance(
        result,
        float,
    )


# Lecture


@pytest.mark.asyncio
async def test_get_document_returns_none_when_not_found(
    service: MilvusService,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Vérifie un document absent."""

    monkeypatch.setattr(
        service,
        "_execute",
        AsyncMock(return_value=[]),
    )

    result = await service.get_document(VALID_DOCUMENT_ID)

    assert result is None


@pytest.mark.asyncio
async def test_get_document_returns_json_object(
    service: MilvusService,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Vérifie la récupération d'un document."""

    monkeypatch.setattr(
        service,
        "_execute",
        AsyncMock(
            return_value=[
                {
                    MILVUS_ID_FIELD: VALID_DOCUMENT_ID,
                    MILVUS_CONTENT_FIELD: "Ruy Lopez",
                }
            ]
        ),
    )

    result = await service.get_document(VALID_DOCUMENT_ID)

    assert result is not None
    assert result[MILVUS_ID_FIELD] == VALID_DOCUMENT_ID


@pytest.mark.asyncio
async def test_get_document_translates_operation_error(
    service: MilvusService,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Vérifie la traduction d'une erreur de lecture."""

    monkeypatch.setattr(
        service,
        "_execute",
        AsyncMock(side_effect=build_operation_error("get")),
    )

    with pytest.raises(MilvusSearchError):
        await service.get_document(VALID_DOCUMENT_ID)


# Suppression


@pytest.mark.asyncio
async def test_delete_document_returns_true(
    service: MilvusService,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Vérifie la suppression par identifiant."""

    monkeypatch.setattr(
        service,
        "_execute",
        AsyncMock(return_value=None),
    )

    assert await service.delete_document(VALID_DOCUMENT_ID) is True


@pytest.mark.asyncio
async def test_delete_document_translates_operation_error(
    service: MilvusService,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Vérifie la traduction d'une erreur de suppression."""

    monkeypatch.setattr(
        service,
        "_execute",
        AsyncMock(side_effect=build_operation_error("delete")),
    )

    with pytest.raises(MilvusDeletionError):
        await service.delete_document(VALID_DOCUMENT_ID)


@pytest.mark.asyncio
async def test_delete_by_filter_returns_true(
    service: MilvusService,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Vérifie la suppression filtrée."""

    monkeypatch.setattr(
        service,
        "_execute",
        AsyncMock(return_value=None),
    )

    assert await service.delete_by_filter("source == 'wikichess'") is True


@pytest.mark.asyncio
async def test_delete_by_filter_rejects_empty_filter(
    service: MilvusService,
) -> None:
    """Vérifie qu'un filtre est obligatoire."""

    with pytest.raises(MilvusValidationError):
        await service.delete_by_filter("   ")


# Conversion JSON


def test_make_json_safe_keeps_json_scalar(
    service: MilvusService,
) -> None:
    """Vérifie les valeurs JSON natives."""

    assert service._make_json_safe("text") == "text"

    assert service._make_json_safe(12) == 12

    assert service._make_json_safe(True) is True

    assert service._make_json_safe(None) is None


def test_make_json_safe_converts_datetime(
    service: MilvusService,
) -> None:
    """Vérifie la conversion d'une date."""

    value = datetime(
        2026,
        8,
        18,
        10,
        0,
        tzinfo=UTC,
    )

    result = service._make_json_safe(value)

    assert isinstance(
        result,
        str,
    )

    assert "2026-08-18" in result


def test_make_json_safe_converts_mapping(
    service: MilvusService,
) -> None:
    """Vérifie la conversion récursive d'un mapping."""

    result = service._make_json_safe(
        {
            "eco": "C60",
            "depth": 15,
        }
    )

    expected: JsonObject = {
        "eco": "C60",
        "depth": 15,
    }

    assert result == expected


def test_make_json_safe_converts_sequence(
    service: MilvusService,
) -> None:
    """Vérifie la conversion d'une séquence."""

    result = service._make_json_safe(
        [
            "a",
            1,
            True,
        ]
    )

    assert result == [
        "a",
        1,
        True,
    ]


# Helpers


def test_get_result_text_returns_text(
    service: MilvusService,
) -> None:
    """Vérifie l'extraction d'un texte."""

    assert (
        service._get_result_text(
            {
                "content": "Ruy Lopez",
            },
            "content",
        )
        == "Ruy Lopez"
    )


def test_get_result_text_returns_empty_string_for_invalid_value(
    service: MilvusService,
) -> None:
    """Vérifie le repli d'un champ non textuel."""

    assert (
        service._get_result_text(
            {
                "content": 42,
            },
            "content",
        )
        == ""
    )


@pytest.mark.parametrize(
    ("value", "expected"),
    [
        (12, 12),
        (12.0, 12),
        ("12", 12),
        ("invalid", 0),
        (True, 0),
        (None, 0),
    ],
)
def test_get_integer(
    service: MilvusService,
    value: object,
    expected: int,
) -> None:
    """Vérifie la conversion entière."""

    assert service._get_integer(value) == expected


@pytest.mark.parametrize(
    ("value", "expected"),
    [
        (12, 12.0),
        (12.5, 12.5),
        ("12.5", 12.5),
        ("invalid", None),
        (True, None),
        (None, None),
        (float("inf"), None),
    ],
)
def test_get_float(
    service: MilvusService,
    value: object,
    expected: float | None,
) -> None:
    """Vérifie la conversion flottante."""

    assert service._get_float(value) == expected


# Santé


@pytest.mark.asyncio
async def test_ping_returns_true_on_success(
    service: MilvusService,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Vérifie un ping réussi."""

    monkeypatch.setattr(
        service,
        "_execute",
        AsyncMock(return_value=[]),
    )

    assert await service.ping() is True


@pytest.mark.asyncio
async def test_ping_returns_false_on_milvus_error(
    service: MilvusService,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Vérifie une indisponibilité Milvus."""

    monkeypatch.setattr(
        service,
        "_execute",
        AsyncMock(side_effect=build_operation_error("list_collections")),
    )

    assert await service.ping() is False


@pytest.mark.asyncio
async def test_ping_returns_false_on_unexpected_error(
    service: MilvusService,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Vérifie une erreur inattendue."""

    monkeypatch.setattr(
        service,
        "_execute",
        AsyncMock(side_effect=RuntimeError("unexpected")),
    )

    assert await service.ping() is False


@pytest.mark.asyncio
async def test_health_returns_service_status(
    service: MilvusService,
    client: MagicMock,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Vérifie l'état de santé détaillé."""

    service._client = cast(
        MilvusClient,
        client,
    )
    service._collection_ready = True

    monkeypatch.setattr(
        service,
        "ping",
        AsyncMock(return_value=True),
    )

    monkeypatch.setattr(
        service,
        "_execute",
        AsyncMock(return_value=True),
    )

    status = await service.health()

    assert status["service"] == "milvus"
    assert status["is_ready"] is True
    assert status["available"] is True
    assert status["collection_exists"] is True
    assert status["vector_dimension"] == VECTOR_DIMENSION
    assert status["collection"] == service.collection_name
    assert status["metric_type"] == service.metric_type
    assert status["index_type"] == service.index_type
