"""Tests unitaires du service MongoDB de Chess Agent."""

from __future__ import annotations

from collections.abc import AsyncIterator
from datetime import UTC, datetime
from typing import cast
from unittest.mock import AsyncMock, MagicMock

import pytest
from app.adapters.mongodb_service import (
    AnalysisCollection,
    MongoDBService,
)
from app.core.constants import (
    ANALYSES_COLLECTION,
    REQUEST_ID_FIELD,
    SAVED_AT_FIELD,
)
from app.core.exceptions import (
    DatabaseOperationError,
)
from app.database.mongodb import (
    MongoDocument,
)
from app.schemas.analysis.analysis import (
    AnalysisRecord,
)
from app.schemas.common.enums import (
    AnalysisStatus,
)
from pymongo import ASCENDING, DESCENDING
from pymongo.errors import PyMongoError

# Configuration

ANALYSIS_ID = "analysis-1"
REQUEST_ID = "request-1"

STARTING_FEN = (
    "rnbqkbnr/pppppppp/8/8/8/8/"
    "PPPPPPPP/RNBQKBNR w KQkq - 0 1"
)

CREATED_AT = datetime(
    2026,
    8,
    18,
    10,
    0,
    tzinfo=UTC,
)

SAVED_AT = datetime(
    2026,
    8,
    18,
    10,
    1,
    tzinfo=UTC,
)


# Faux curseur

class FakeCursor:
    """Curseur asynchrone minimal utilisé par les tests."""

    def __init__(
        self,
        documents: list[MongoDocument],
    ) -> None:
        """Initialise le curseur."""

        self._documents = documents
        self.sort_calls: list[
            tuple[str, int]
        ] = []
        self.skip_calls: list[int] = []
        self.limit_calls: list[int] = []

    def sort(
        self,
        field: str,
        direction: int,
    ) -> FakeCursor:
        """Simule sort()."""

        self.sort_calls.append(
            (
                field,
                direction,
            )
        )

        return self

    def skip(
        self,
        value: int,
    ) -> FakeCursor:
        """Simule skip()."""

        self.skip_calls.append(
            value
        )

        return self

    def limit(
        self,
        value: int,
    ) -> FakeCursor:
        """Simule limit()."""

        self.limit_calls.append(
            value
        )

        return self

    def __aiter__(
        self,
    ) -> AsyncIterator[MongoDocument]:
        """Retourne l'itérateur asynchrone."""

        return self._iterate()

    async def _iterate(
        self,
    ) -> AsyncIterator[MongoDocument]:
        """Parcourt les documents."""

        for document in self._documents:
            yield document


# Construction des données de test

def build_analysis_record(
    *,
    analysis_id: str = ANALYSIS_ID,
    request_id: str = REQUEST_ID,
    response: str | None = (
        "La position initiale ne présente "
        "aucun avantage particulier."
    ),
) -> AnalysisRecord:
    """Construit une analyse adaptée aux besoins du service testé."""

    return AnalysisRecord.model_construct(
        id=analysis_id,
        request_id=request_id,
        fen=STARTING_FEN,
        moves=[],
        question=None,
        status=AnalysisStatus.SUCCESS,
        position=None,
        opening=None,
        evaluation=None,
        retrieval_context=None,
        videos=[],
        response=response,
        engine_analysis=None,
        workflow_context={},
        metadata={},
        completed_steps=[],
        warnings=[],
        errors=[],
        created_at=CREATED_AT,
        saved_at=SAVED_AT,
    )


def build_mongo_document(
    analysis: AnalysisRecord,
) -> MongoDocument:
    """Construit un document MongoDB depuis une analyse."""

    document = analysis.model_dump(
        mode="python"
    )

    document["_id"] = document.pop(
        "id"
    )

    return cast(
        MongoDocument,
        document,
    )


# Fixtures

@pytest.fixture
def collection() -> MagicMock:
    """Construit une fausse collection MongoDB."""

    mocked_collection = MagicMock()

    mocked_collection.create_index = (
        AsyncMock()
    )

    mocked_collection.update_one = (
        AsyncMock()
    )

    mocked_collection.find_one = (
        AsyncMock()
    )

    mocked_collection.delete_one = (
        AsyncMock()
    )

    mocked_collection.count_documents = (
        AsyncMock()
    )

    return mocked_collection


@pytest.fixture
def service(
    collection: MagicMock,
) -> MongoDBService:
    """Construit le service avec une collection injectée."""

    return MongoDBService(
        collection=cast(
            AnalysisCollection,
            collection,
        )
    )


@pytest.fixture
def analysis() -> AnalysisRecord:
    """Construit une analyse de référence."""

    return build_analysis_record()


# Construction

def test_service_is_not_initialized_after_creation(
    service: MongoDBService,
) -> None:
    """Vérifie l'état initial du service."""

    assert service.is_initialized() is False


def test_get_collection_returns_injected_collection(
    service: MongoDBService,
    collection: MagicMock,
) -> None:
    """Vérifie la récupération de la collection injectée."""

    assert (
        service._get_collection()
        is collection
    )


def test_get_collection_loads_default_collection(
    monkeypatch: pytest.MonkeyPatch,
    collection: MagicMock,
) -> None:
    """Vérifie la récupération tardive de la collection."""

    get_collection = MagicMock(
        return_value=collection
    )

    monkeypatch.setattr(
        "app.adapters.mongodb_service."
        "get_collection",
        get_collection,
    )

    service = MongoDBService()

    result = service._get_collection()

    assert result is collection

    get_collection.assert_called_once_with(
        ANALYSES_COLLECTION
    )


# Cycle de vie

@pytest.mark.asyncio
async def test_close_resets_service(
    service: MongoDBService,
) -> None:
    """Vérifie la fermeture du service."""

    service._initialized = True

    await service.close()

    assert service._collection is None
    assert service.is_initialized() is False


# Initialisation

@pytest.mark.asyncio
async def test_initialize_creates_required_indexes(
    service: MongoDBService,
    collection: MagicMock,
) -> None:
    """Vérifie la création des deux index MongoDB."""

    await service.initialize()

    assert service.is_initialized() is True

    assert (
        collection.create_index.await_count
        == 2
    )

    collection.create_index.assert_any_await(
        [
            (
                REQUEST_ID_FIELD,
                ASCENDING,
            )
        ],
        unique=True,
        name="analyses_request_id_unique",
    )

    collection.create_index.assert_any_await(
        [
            (
                SAVED_AT_FIELD,
                DESCENDING,
            )
        ],
        name="analyses_saved_at_desc",
    )


@pytest.mark.asyncio
async def test_initialize_is_idempotent(
    service: MongoDBService,
    collection: MagicMock,
) -> None:
    """Vérifie qu'une seconde initialisation ne recrée pas les index."""

    await service.initialize()
    await service.initialize()

    assert (
        collection.create_index.await_count
        == 2
    )


@pytest.mark.asyncio
async def test_initialize_translates_pymongo_error(
    service: MongoDBService,
    collection: MagicMock,
) -> None:
    """Vérifie la traduction d'une erreur d'indexation."""

    collection.create_index.side_effect = (
        PyMongoError(
            "index failure"
        )
    )

    with pytest.raises(
        DatabaseOperationError
    ):
        await service.initialize()

    assert service.is_initialized() is False


# Identifiants

def test_normalize_identifier_strips_spaces(
    service: MongoDBService,
) -> None:
    """Vérifie la normalisation d'un identifiant."""

    result = service._normalize_identifier(
        "  analysis-1  ",
        "analysis_id",
    )

    assert result == "analysis-1"


@pytest.mark.parametrize(
    "value",
    [
        "",
        "   ",
    ],
)
def test_normalize_identifier_rejects_empty_value(
    service: MongoDBService,
    value: str,
) -> None:
    """Vérifie le rejet d'un identifiant vide."""

    with pytest.raises(
        ValueError
    ):
        service._normalize_identifier(
            value,
            "analysis_id",
        )


# Limite d'historique

def test_normalize_history_limit_accepts_positive_value(
    service: MongoDBService,
) -> None:
    """Vérifie une limite valide."""

    result = (
        service._normalize_history_limit(
            5
        )
    )

    assert result >= 1


@pytest.mark.parametrize(
    "value",
    [
        True,
        False,
        1.5,
        "5",
    ],
)
def test_normalize_history_limit_rejects_non_integer(
    service: MongoDBService,
    value: object,
) -> None:
    """Vérifie qu'une limite doit être entière."""

    with pytest.raises(
        TypeError
    ):
        service._normalize_history_limit(
            value  # type: ignore[arg-type]
        )


@pytest.mark.parametrize(
    "value",
    [
        0,
        -1,
    ],
)
def test_normalize_history_limit_rejects_non_positive_value(
    service: MongoDBService,
    value: int,
) -> None:
    """Vérifie qu'une limite doit être positive."""

    with pytest.raises(
        ValueError
    ):
        service._normalize_history_limit(
            value
        )


# Offset

def test_normalize_history_offset_accepts_zero(
    service: MongoDBService,
) -> None:
    """Vérifie l'offset zéro."""

    assert (
        service._normalize_history_offset(
            0
        )
        == 0
    )


def test_normalize_history_offset_accepts_positive_value(
    service: MongoDBService,
) -> None:
    """Vérifie un offset positif."""

    assert (
        service._normalize_history_offset(
            10
        )
        == 10
    )


@pytest.mark.parametrize(
    "value",
    [
        True,
        False,
        1.5,
        "1",
    ],
)
def test_normalize_history_offset_rejects_non_integer(
    service: MongoDBService,
    value: object,
) -> None:
    """Vérifie que l'offset doit être entier."""

    with pytest.raises(
        TypeError
    ):
        service._normalize_history_offset(
            value  # type: ignore[arg-type]
        )


def test_normalize_history_offset_rejects_negative_value(
    service: MongoDBService,
) -> None:
    """Vérifie qu'un offset négatif est refusé."""

    with pytest.raises(
        ValueError
    ):
        service._normalize_history_offset(
            -1
        )


# Longueur d'extrait

def test_normalize_preview_length_accepts_positive_value(
    service: MongoDBService,
) -> None:
    """Vérifie une longueur valide."""

    assert (
        service._normalize_preview_length(
            20
        )
        == 20
    )


@pytest.mark.parametrize(
    "value",
    [
        True,
        False,
        1.5,
        "20",
    ],
)
def test_normalize_preview_length_rejects_non_integer(
    service: MongoDBService,
    value: object,
) -> None:
    """Vérifie le type de la longueur."""

    with pytest.raises(
        TypeError
    ):
        service._normalize_preview_length(
            value  # type: ignore[arg-type]
        )


@pytest.mark.parametrize(
    "value",
    [
        0,
        -1,
    ],
)
def test_normalize_preview_length_rejects_non_positive_value(
    service: MongoDBService,
    value: int,
) -> None:
    """Vérifie une longueur strictement positive."""

    with pytest.raises(
        ValueError
    ):
        service._normalize_preview_length(
            value
        )


# Aperçu de réponse

def test_build_response_preview_returns_none_for_none(
    service: MongoDBService,
) -> None:
    """Vérifie une réponse absente."""

    assert (
        service._build_response_preview(
            None
        )
        is None
    )


def test_build_response_preview_returns_none_for_whitespace(
    service: MongoDBService,
) -> None:
    """Vérifie une réponse vide après normalisation."""

    assert (
        service._build_response_preview(
            "   \n   "
        )
        is None
    )


def test_build_response_preview_normalizes_whitespace(
    service: MongoDBService,
) -> None:
    """Vérifie la normalisation des espaces."""

    result = (
        service._build_response_preview(
            "Une   réponse\navec   espaces.",
            max_length=100,
        )
    )

    assert result == (
        "Une réponse avec espaces."
    )


def test_build_response_preview_truncates_long_response(
    service: MongoDBService,
) -> None:
    """Vérifie la troncature de l'extrait."""

    result = (
        service._build_response_preview(
            "abcdefghij",
            max_length=5,
        )
    )

    assert result == "abcde..."


def test_build_response_preview_rejects_invalid_length(
    service: MongoDBService,
) -> None:
    """Vérifie une longueur d'extrait invalide."""

    with pytest.raises(
        ValueError
    ):
        service._build_response_preview(
            "response",
            max_length=0,
        )


# Sérialisation

def test_analysis_to_document_moves_id_to_mongodb_id(
    service: MongoDBService,
    analysis: AnalysisRecord,
) -> None:
    """Vérifie la conversion vers le format MongoDB."""

    document = service._analysis_to_document(
        analysis
    )

    assert document["_id"] == ANALYSIS_ID
    assert "id" not in document

    assert (
        document[REQUEST_ID_FIELD]
        == REQUEST_ID
    )


def test_document_to_analysis_rejects_missing_identifier(
    service: MongoDBService,
) -> None:
    """Vérifie qu'un document doit posséder _id."""

    document = cast(
        MongoDocument,
        {
            REQUEST_ID_FIELD: REQUEST_ID,
        },
    )

    with pytest.raises(
        DatabaseOperationError
    ):
        service._document_to_analysis(
            document
        )


def test_document_to_analysis_rejects_invalid_document(
    service: MongoDBService,
) -> None:
    """Vérifie la validation Pydantic du document lu."""

    document = cast(
        MongoDocument,
        {
            "_id": ANALYSIS_ID,
            REQUEST_ID_FIELD: REQUEST_ID,
        },
    )

    with pytest.raises(
        DatabaseOperationError
    ):
        service._document_to_analysis(
            document
        )


# Nom d'ouverture

def test_extract_opening_name_returns_none_without_opening(
    service: MongoDBService,
    analysis: AnalysisRecord,
) -> None:
    """Vérifie une analyse sans ouverture."""

    assert (
        service._extract_opening_name(
            analysis
        )
        is None
    )


# Résumé

def test_build_summary_uses_analysis_data(
    service: MongoDBService,
    analysis: AnalysisRecord,
) -> None:
    """Vérifie la construction du résumé d'historique."""

    summary = service._build_summary(
        analysis
    )

    assert summary.id == ANALYSIS_ID

    assert (
        summary.request_id
        == REQUEST_ID
    )

    assert summary.fen == STARTING_FEN

    assert (
        summary.status
        == AnalysisStatus.SUCCESS
    )

    assert summary.opening_name is None

    assert (
        summary.warning_count
        == 0
    )

    assert (
        summary.error_count
        == 0
    )


# Sauvegarde

@pytest.mark.asyncio
async def test_save_analysis_returns_created_result(
    service: MongoDBService,
    collection: MagicMock,
    analysis: AnalysisRecord,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Vérifie la création idempotente d'une analyse."""

    service._initialized = True

    update_result = MagicMock()
    update_result.upserted_id = ANALYSIS_ID

    collection.update_one.return_value = (
        update_result
    )

    monkeypatch.setattr(
        service,
        "get_analysis_by_request_id",
        AsyncMock(
            return_value=analysis
        ),
    )

    result = await service.save_analysis(
        analysis
    )

    assert result.analysis_id == ANALYSIS_ID
    assert result.request_id == REQUEST_ID
    assert result.created is True

    collection.update_one.assert_awaited_once()


@pytest.mark.asyncio
async def test_save_analysis_returns_updated_result(
    service: MongoDBService,
    collection: MagicMock,
    analysis: AnalysisRecord,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Vérifie la mise à jour d'une analyse existante."""

    service._initialized = True

    update_result = MagicMock()
    update_result.upserted_id = None

    collection.update_one.return_value = (
        update_result
    )

    monkeypatch.setattr(
        service,
        "get_analysis_by_request_id",
        AsyncMock(
            return_value=analysis
        ),
    )

    result = await service.save_analysis(
        analysis
    )

    assert result.created is False


@pytest.mark.asyncio
async def test_save_analysis_translates_pymongo_error(
    service: MongoDBService,
    collection: MagicMock,
    analysis: AnalysisRecord,
) -> None:
    """Vérifie une erreur MongoDB pendant l'écriture."""

    service._initialized = True

    collection.update_one.side_effect = (
        PyMongoError(
            "write failure"
        )
    )

    with pytest.raises(
        DatabaseOperationError
    ):
        await service.save_analysis(
            analysis
        )


@pytest.mark.asyncio
async def test_save_analysis_fails_when_document_cannot_be_reloaded(
    service: MongoDBService,
    collection: MagicMock,
    analysis: AnalysisRecord,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Vérifie l'échec de relecture après sauvegarde."""

    service._initialized = True

    update_result = MagicMock()
    update_result.upserted_id = ANALYSIS_ID

    collection.update_one.return_value = (
        update_result
    )

    monkeypatch.setattr(
        service,
        "get_analysis_by_request_id",
        AsyncMock(
            return_value=None
        ),
    )

    with pytest.raises(
        DatabaseOperationError
    ):
        await service.save_analysis(
            analysis
        )


# Lecture par identifiant

@pytest.mark.asyncio
async def test_get_analysis_returns_none_when_missing(
    service: MongoDBService,
    collection: MagicMock,
) -> None:
    """Vérifie une analyse absente."""

    service._initialized = True

    collection.find_one.return_value = None

    result = await service.get_analysis(
        ANALYSIS_ID
    )

    assert result is None

    collection.find_one.assert_awaited_once_with(
        {
            "_id": ANALYSIS_ID,
        }
    )


@pytest.mark.asyncio
async def test_get_analysis_translates_pymongo_error(
    service: MongoDBService,
    collection: MagicMock,
) -> None:
    """Vérifie une erreur de lecture MongoDB."""

    service._initialized = True

    collection.find_one.side_effect = (
        PyMongoError(
            "read failure"
        )
    )

    with pytest.raises(
        DatabaseOperationError
    ):
        await service.get_analysis(
            ANALYSIS_ID
        )


@pytest.mark.asyncio
async def test_get_required_analysis_returns_existing_analysis(
    service: MongoDBService,
    analysis: AnalysisRecord,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Vérifie la lecture obligatoire d'une analyse existante."""

    monkeypatch.setattr(
        service,
        "get_analysis",
        AsyncMock(
            return_value=analysis
        ),
    )

    result = (
        await service.get_required_analysis(
            ANALYSIS_ID
        )
    )

    assert result is analysis


@pytest.mark.asyncio
async def test_get_required_analysis_rejects_missing_analysis(
    service: MongoDBService,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Vérifie une analyse obligatoire absente."""

    monkeypatch.setattr(
        service,
        "get_analysis",
        AsyncMock(
            return_value=None
        ),
    )

    with pytest.raises(
        DatabaseOperationError
    ):
        await service.get_required_analysis(
            ANALYSIS_ID
        )


# Lecture par request_id

@pytest.mark.asyncio
async def test_get_analysis_by_request_id_returns_none_when_missing(
    service: MongoDBService,
    collection: MagicMock,
) -> None:
    """Vérifie une requête non enregistrée."""

    service._initialized = True

    collection.find_one.return_value = None

    result = (
        await service.get_analysis_by_request_id(
            REQUEST_ID
        )
    )

    assert result is None

    collection.find_one.assert_awaited_once_with(
        {
            REQUEST_ID_FIELD: REQUEST_ID,
        }
    )


@pytest.mark.asyncio
async def test_get_analysis_by_request_id_translates_pymongo_error(
    service: MongoDBService,
    collection: MagicMock,
) -> None:
    """Vérifie une erreur MongoDB pendant la recherche."""

    service._initialized = True

    collection.find_one.side_effect = (
        PyMongoError(
            "read failure"
        )
    )

    with pytest.raises(
        DatabaseOperationError
    ):
        await service.get_analysis_by_request_id(
            REQUEST_ID
        )


# Historique

@pytest.mark.asyncio
async def test_list_recent_analyses_returns_empty_list(
    service: MongoDBService,
    collection: MagicMock,
) -> None:
    """Vérifie un historique vide."""

    service._initialized = True

    cursor = FakeCursor(
        []
    )

    collection.find.return_value = cursor

    result = await service.list_recent_analyses(
        limit=5,
        offset=0,
    )

    assert result == []

    assert cursor.sort_calls == [
        (
            SAVED_AT_FIELD,
            DESCENDING,
        )
    ]

    assert cursor.skip_calls == [
        0
    ]

    assert cursor.limit_calls == [
        5
    ]


@pytest.mark.asyncio
async def test_list_recent_analyses_builds_summaries(
    service: MongoDBService,
    collection: MagicMock,
    analysis: AnalysisRecord,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Vérifie la construction de l'historique."""

    service._initialized = True

    document = build_mongo_document(
        analysis
    )

    cursor = FakeCursor(
        [
            document,
        ]
    )

    collection.find.return_value = cursor

    monkeypatch.setattr(
        service,
        "_document_to_analysis",
        MagicMock(
            return_value=analysis
        ),
    )

    result = await service.list_recent_analyses(
        limit=10,
    )

    assert len(result) == 1

    assert result[0].id == ANALYSIS_ID


# Suppression

@pytest.mark.asyncio
async def test_delete_analysis_returns_true_when_deleted(
    service: MongoDBService,
    collection: MagicMock,
) -> None:
    """Vérifie la suppression d'une analyse existante."""

    service._initialized = True

    result = MagicMock()
    result.deleted_count = 1

    collection.delete_one.return_value = result

    deleted = await service.delete_analysis(
        ANALYSIS_ID
    )

    assert deleted is True


@pytest.mark.asyncio
async def test_delete_analysis_returns_false_when_missing(
    service: MongoDBService,
    collection: MagicMock,
) -> None:
    """Vérifie la suppression d'une analyse absente."""

    service._initialized = True

    result = MagicMock()
    result.deleted_count = 0

    collection.delete_one.return_value = result

    deleted = await service.delete_analysis(
        ANALYSIS_ID
    )

    assert deleted is False


@pytest.mark.asyncio
async def test_delete_analysis_translates_pymongo_error(
    service: MongoDBService,
    collection: MagicMock,
) -> None:
    """Vérifie une erreur MongoDB pendant la suppression."""

    service._initialized = True

    collection.delete_one.side_effect = (
        PyMongoError(
            "delete failure"
        )
    )

    with pytest.raises(
        DatabaseOperationError
    ):
        await service.delete_analysis(
            ANALYSIS_ID
        )


@pytest.mark.asyncio
async def test_delete_required_analysis_accepts_deleted_analysis(
    service: MongoDBService,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Vérifie la suppression obligatoire réussie."""

    monkeypatch.setattr(
        service,
        "delete_analysis",
        AsyncMock(
            return_value=True
        ),
    )

    await service.delete_required_analysis(
        ANALYSIS_ID
    )


@pytest.mark.asyncio
async def test_delete_required_analysis_rejects_missing_analysis(
    service: MongoDBService,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Vérifie la suppression obligatoire d'une analyse absente."""

    monkeypatch.setattr(
        service,
        "delete_analysis",
        AsyncMock(
            return_value=False
        ),
    )

    with pytest.raises(
        DatabaseOperationError
    ):
        await service.delete_required_analysis(
            ANALYSIS_ID
        )


# Santé

@pytest.mark.asyncio
async def test_ping_returns_true(
    service: MongoDBService,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Vérifie un ping MongoDB réussi."""

    monkeypatch.setattr(
        "app.adapters.mongodb_service."
        "ping_mongodb",
        AsyncMock(
            return_value=True
        ),
    )

    assert await service.ping() is True


@pytest.mark.asyncio
async def test_ping_returns_false_on_unexpected_error(
    service: MongoDBService,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Vérifie la protection du healthcheck."""

    monkeypatch.setattr(
        "app.adapters.mongodb_service."
        "ping_mongodb",
        AsyncMock(
            side_effect=RuntimeError(
                "unexpected"
            )
        ),
    )

    assert await service.ping() is False


@pytest.mark.asyncio
async def test_health_returns_unavailable_status(
    service: MongoDBService,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Vérifie l'état lorsque MongoDB est indisponible."""

    monkeypatch.setattr(
        service,
        "ping",
        AsyncMock(
            return_value=False
        ),
    )

    status = await service.health()

    assert status["service"] == "mongodb"
    assert status["available"] is False
    assert status["analysis_count"] is None
    assert status["collection"] == ANALYSES_COLLECTION


@pytest.mark.asyncio
async def test_health_returns_analysis_count(
    service: MongoDBService,
    collection: MagicMock,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Vérifie l'état lorsque MongoDB est disponible."""

    service._initialized = True

    monkeypatch.setattr(
        service,
        "ping",
        AsyncMock(
            return_value=True
        ),
    )

    collection.count_documents.return_value = 12

    status = await service.health()

    assert status["service"] == "mongodb"
    assert status["available"] is True
    assert status["initialized"] is True
    assert status["analysis_count"] == 12

    collection.count_documents.assert_awaited_once_with(
        {}
    )