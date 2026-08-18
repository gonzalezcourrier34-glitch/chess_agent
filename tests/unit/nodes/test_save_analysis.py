"""Tests unitaires du nœud de sauvegarde finale LangGraph."""

from __future__ import annotations

from datetime import UTC, datetime
from typing import cast
from unittest.mock import AsyncMock, MagicMock

import chess
import pytest
from langchain_core.runnables import RunnableConfig
from pydantic import BaseModel, ConfigDict

from app.adapters.mongodb_service import MongoDBService
from app.agent.nodes.H_save_analysis import (
    ANALYSIS_IDENTIFIER_NAMESPACE,
    MONGODB_SERVICE_KEY,
    UNEXPECTED_SAVE_MESSAGE,
    _build_analysis_id,
    _build_analysis_record,
    _build_configuration_warning_update,
    _build_database_warning_update,
    _build_missing_request_id_update,
    _build_missing_service_update,
    _build_success_update,
    _build_unexpected_warning_update,
    _build_warning_update,
    _get_created_at,
    _get_mongodb_service,
    _get_partial_success_status,
    _get_request_id,
    _get_success_status,
    _normalize_optional_text,
    _serialize_json_object,
    _serialize_model,
    save_analysis,
)
from app.agent.state import (
    ChessAnalysisState,
    WorkflowMetadata,
)
from app.core.constants import (
    ERROR_CONFIGURATION,
    ERROR_UNEXPECTED,
)
from app.core.exceptions import DatabaseError
from app.schemas.analysis.analysis import AnalysisSaveResult
from app.schemas.common.enums import (
    AnalysisStatus,
    WorkflowStep,
)
from app.schemas.common.error import WorkflowWarning


# Configuration

STARTING_FEN = chess.STARTING_FEN

REQUEST_ID = "request-123"


# Modèle de test

class SerializableModel(BaseModel):
    """Petit modèle Pydantic utilisé pour tester la sérialisation."""

    model_config = ConfigDict(
        extra="forbid"
    )

    name: str
    value: int


# Fixtures

@pytest.fixture
def state() -> ChessAnalysisState:
    """Construit un état minimal avec request_id."""

    metadata = WorkflowMetadata(
        request_id=REQUEST_ID,
    )

    return ChessAnalysisState(
        fen=STARTING_FEN,
        metadata=metadata,
    )


@pytest.fixture
def save_result() -> AnalysisSaveResult:
    """Construit un résultat de sauvegarde."""

    return AnalysisSaveResult(
        analysis_id="analysis-123",
        request_id=REQUEST_ID,
        created=True,
        saved_at=datetime(
            2026,
            8,
            18,
            11,
            0,
            tzinfo=UTC,
        ),
    )


# Service

def test_get_mongodb_service_returns_configured_service(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Vérifie la récupération du MongoDBService."""

    service = MagicMock(
        spec=MongoDBService,
    )

    configured_service = MagicMock(
        return_value=service,
    )

    monkeypatch.setattr(
        "app.agent.nodes.H_save_analysis."
        "get_configured_service",
        configured_service,
    )

    config = cast(
        RunnableConfig,
        {},
    )

    result = _get_mongodb_service(
        config
    )

    assert result is service

    configured_service.assert_called_once_with(
        config,
        MONGODB_SERVICE_KEY,
        expected_type=MongoDBService,
    )


def test_get_mongodb_service_returns_none_when_missing(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Vérifie l'absence du service MongoDB."""

    monkeypatch.setattr(
        "app.agent.nodes.H_save_analysis."
        "get_configured_service",
        MagicMock(
            return_value=None,
        ),
    )

    result = _get_mongodb_service(
        cast(
            RunnableConfig,
            {},
        )
    )

    assert result is None


def test_get_mongodb_service_rejects_invalid_type(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Vérifie le rejet d'un service d'un autre type."""

    monkeypatch.setattr(
        "app.agent.nodes.H_save_analysis."
        "get_configured_service",
        MagicMock(
            return_value=object(),
        ),
    )

    result = _get_mongodb_service(
        cast(
            RunnableConfig,
            {},
        )
    )

    assert result is None


# Statuts

@pytest.mark.parametrize(
    ("initial", "expected"),
    [
        (
            AnalysisStatus.PENDING,
            AnalysisStatus.SUCCESS,
        ),
        (
            AnalysisStatus.SUCCESS,
            AnalysisStatus.SUCCESS,
        ),
        (
            AnalysisStatus.PARTIAL_SUCCESS,
            AnalysisStatus.PARTIAL_SUCCESS,
        ),
        (
            AnalysisStatus.FAILED,
            AnalysisStatus.FAILED,
        ),
    ],
)
def test_get_success_status(
    state: ChessAnalysisState,
    initial: AnalysisStatus,
    expected: AnalysisStatus,
) -> None:
    """Vérifie le statut final après sauvegarde."""

    current_state = state.model_copy(
        update={
            "status": initial,
        }
    )

    assert (
        _get_success_status(
            current_state
        )
        == expected
    )


@pytest.mark.parametrize(
    ("initial", "expected"),
    [
        (
            AnalysisStatus.PENDING,
            AnalysisStatus.PARTIAL_SUCCESS,
        ),
        (
            AnalysisStatus.SUCCESS,
            AnalysisStatus.PARTIAL_SUCCESS,
        ),
        (
            AnalysisStatus.PARTIAL_SUCCESS,
            AnalysisStatus.PARTIAL_SUCCESS,
        ),
        (
            AnalysisStatus.FAILED,
            AnalysisStatus.FAILED,
        ),
    ],
)
def test_get_partial_success_status(
    state: ChessAnalysisState,
    initial: AnalysisStatus,
    expected: AnalysisStatus,
) -> None:
    """Vérifie le statut final dégradé."""

    current_state = state.model_copy(
        update={
            "status": initial,
        }
    )

    assert (
        _get_partial_success_status(
            current_state
        )
        == expected
    )


# Normalisation

@pytest.mark.parametrize(
    ("value", "expected"),
    [
        (
            None,
            None,
        ),
        (
            "",
            None,
        ),
        (
            "   ",
            None,
        ),
        (
            "  hello   world  ",
            "hello world",
        ),
        (
            "texte",
            "texte",
        ),
    ],
)
def test_normalize_optional_text(
    value: str | None,
    expected: str | None,
) -> None:
    """Vérifie la normalisation d'un texte facultatif."""

    assert (
        _normalize_optional_text(value)
        == expected
    )


def test_get_request_id(
    state: ChessAnalysisState,
) -> None:
    """Vérifie la récupération du request_id."""

    assert (
        _get_request_id(state)
        == REQUEST_ID
    )


def test_get_request_id_normalizes_value(
    state: ChessAnalysisState,
) -> None:
    """Vérifie la normalisation du request_id."""

    metadata = state.metadata.model_copy(
        update={
            "request_id": "  request   123  ",
        }
    )

    current_state = state.model_copy(
        update={
            "metadata": metadata,
        }
    )

    assert (
        _get_request_id(
            current_state
        )
        == "request 123"
    )


def test_get_request_id_returns_none(
    state: ChessAnalysisState,
) -> None:
    """Vérifie l'absence du request_id."""

    metadata = state.metadata.model_copy(
        update={
            "request_id": None,
        }
    )

    current_state = state.model_copy(
        update={
            "metadata": metadata,
        }
    )

    assert (
        _get_request_id(
            current_state
        )
        is None
    )


# Identifiants

def test_build_analysis_id_is_deterministic() -> None:
    """Vérifie l'idempotence de l'identifiant d'analyse."""

    first = _build_analysis_id(
        REQUEST_ID
    )

    second = _build_analysis_id(
        REQUEST_ID
    )

    assert first == second
    assert first


def test_build_analysis_id_changes_with_request_id() -> None:
    """Vérifie qu'un autre request_id produit un autre identifiant."""

    first = _build_analysis_id(
        "request-a"
    )

    second = _build_analysis_id(
        "request-b"
    )

    assert first != second


def test_analysis_identifier_namespace_is_stable() -> None:
    """Vérifie le namespace utilisé par la génération UUID."""

    assert (
        ANALYSIS_IDENTIFIER_NAMESPACE
        == "chess-agent-analysis"
    )


# Dates

def test_get_created_at_uses_started_at(
    state: ChessAnalysisState,
) -> None:
    """Vérifie la date de démarrage comme date de création."""

    started_at = datetime(
        2026,
        8,
        18,
        10,
        0,
        tzinfo=UTC,
    )

    metadata = state.metadata.model_copy(
        update={
            "started_at": started_at,
        }
    )

    current_state = state.model_copy(
        update={
            "metadata": metadata,
        }
    )

    default = datetime(
        2026,
        8,
        18,
        11,
        0,
        tzinfo=UTC,
    )

    assert (
        _get_created_at(
            current_state,
            default=default,
        )
        == started_at
    )


def test_get_created_at_uses_default(
    state: ChessAnalysisState,
) -> None:
    """Vérifie la date de repli."""

    default = datetime(
        2026,
        8,
        18,
        11,
        0,
        tzinfo=UTC,
    )

    assert (
        _get_created_at(
            state,
            default=default,
        )
        == default
    )


def test_get_created_at_supports_legacy_created_at(
    state: ChessAnalysisState,
) -> None:
    """Vérifie la compatibilité avec created_at."""

    created_at = datetime(
        2026,
        8,
        17,
        8,
        0,
        tzinfo=UTC,
    )

    metadata = MagicMock()
    metadata.created_at = created_at
    metadata.started_at = None
    metadata.requested_at = None

    current_state = state.model_copy(
        update={
            "metadata": metadata,
        }
    )

    assert (
        _get_created_at(
            current_state,
            default=datetime.now(UTC),
        )
        == created_at
    )


# Sérialisation JSON

def test_serialize_json_object_from_pydantic_model() -> None:
    """Vérifie la sérialisation d'un BaseModel."""

    model = SerializableModel(
        name="test",
        value=42,
    )

    result = _serialize_json_object(
        model
    )

    assert result == {
        "name": "test",
        "value": 42,
    }


def test_serialize_json_object_from_mapping() -> None:
    """Vérifie la sérialisation d'un mapping."""

    result = _serialize_json_object(
        {
            "name": "test",
            "value": 42,
        }
    )

    assert result == {
        "name": "test",
        "value": 42,
    }


@pytest.mark.parametrize(
    "value",
    [
        None,
        "text",
        42,
        True,
        [],
    ],
)
def test_serialize_json_object_rejects_non_object(
    value: object,
) -> None:
    """Vérifie les types non pris en charge."""

    assert (
        _serialize_json_object(value)
        is None
    )


def test_serialize_json_object_rejects_invalid_json_mapping() -> None:
    """Vérifie une valeur non sérialisable en JSON."""

    result = _serialize_json_object(
        {
            "invalid": object(),
        }
    )

    assert result is None


def test_serialize_model_returns_none() -> None:
    """Vérifie un modèle absent."""

    assert (
        _serialize_model(None)
        is None
    )


def test_serialize_model_returns_json_object() -> None:
    """Vérifie un modèle Pydantic."""

    model = SerializableModel(
        name="test",
        value=42,
    )

    assert (
        _serialize_model(model)
        == {
            "name": "test",
            "value": 42,
        }
    )


# Construction du record

def test_build_analysis_record(
    state: ChessAnalysisState,
) -> None:
    """Vérifie la construction du document MongoDB."""

    current_state = state.model_copy(
        update={
            "moves": [
                "e2e4",
                "e7e5",
            ],
            "question": "  Que jouer ?  ",
            "response": "  Réponse finale.  ",
        }
    )

    record = _build_analysis_record(
        current_state,
        REQUEST_ID,
    )

    assert (
        record.id
        == _build_analysis_id(REQUEST_ID)
    )

    assert record.request_id == REQUEST_ID
    assert record.fen == STARTING_FEN

    assert record.moves == [
        "e2e4",
        "e7e5",
    ]

    assert record.question == "Que jouer ?"

    assert (
        record.response
        == "Réponse finale."
    )

    assert (
        record.response_language
        == current_state.options.response_language
    )

    assert (
        record.status
        == AnalysisStatus.SUCCESS
    )

    assert (
        record.current_step
        == WorkflowStep.SAVE_ANALYSIS
    )

    assert (
        WorkflowStep.SAVE_ANALYSIS
        in record.completed_steps
    )

    assert record.saved_at.tzinfo is not None


def test_build_analysis_record_preserves_partial_status(
    state: ChessAnalysisState,
) -> None:
    """Vérifie la conservation d'une réussite partielle."""

    current_state = state.model_copy(
        update={
            "status": (
                AnalysisStatus.PARTIAL_SUCCESS
            ),
        }
    )

    record = _build_analysis_record(
        current_state,
        REQUEST_ID,
    )

    assert (
        record.status
        == AnalysisStatus.PARTIAL_SUCCESS
    )


def test_build_analysis_record_uses_started_at(
    state: ChessAnalysisState,
) -> None:
    """Vérifie la date de création enregistrée."""

    started_at = datetime(
        2026,
        8,
        18,
        9,
        30,
        tzinfo=UTC,
    )

    metadata = state.metadata.model_copy(
        update={
            "started_at": started_at,
        }
    )

    current_state = state.model_copy(
        update={
            "metadata": metadata,
        }
    )

    record = _build_analysis_record(
        current_state,
        REQUEST_ID,
    )

    assert (
        record.created_at
        == started_at
    )


# Mises à jour

def test_build_success_update(
    state: ChessAnalysisState,
    save_result: AnalysisSaveResult,
) -> None:
    """Vérifie une sauvegarde réussie."""

    update = _build_success_update(
        state,
        save_result,
    )

    assert (
        update["status"]
        == AnalysisStatus.SUCCESS
    )

    assert (
        update["current_step"]
        == WorkflowStep.SAVE_ANALYSIS
    )

    assert (
        WorkflowStep.SAVE_ANALYSIS
        in update["completed_steps"]
    )

    assert (
        update["analysis_id"]
        == save_result.analysis_id
    )

    assert update["errors"] == []
    assert update["warnings"] == []


def test_build_warning_update(
    state: ChessAnalysisState,
) -> None:
    """Vérifie une sauvegarde dégradée."""

    warning = WorkflowWarning(
        step=WorkflowStep.SAVE_ANALYSIS,
        code=ERROR_UNEXPECTED,
        message="Erreur de sauvegarde.",
    )

    update = _build_warning_update(
        state,
        warning,
    )

    assert (
        update["status"]
        == AnalysisStatus.PARTIAL_SUCCESS
    )

    assert (
        update["current_step"]
        == WorkflowStep.SAVE_ANALYSIS
    )

    assert (
        WorkflowStep.SAVE_ANALYSIS
        in update["completed_steps"]
    )

    assert update["analysis_id"] is None

    assert update["warnings"] == [
        warning,
    ]


def test_build_warning_update_preserves_failed_status(
    state: ChessAnalysisState,
) -> None:
    """Vérifie qu'un échec précédent reste prioritaire."""

    failed_state = state.model_copy(
        update={
            "status": AnalysisStatus.FAILED,
        }
    )

    warning = WorkflowWarning(
        step=WorkflowStep.SAVE_ANALYSIS,
        code=ERROR_UNEXPECTED,
        message="Erreur.",
    )

    update = _build_warning_update(
        failed_state,
        warning,
    )

    assert (
        update["status"]
        == AnalysisStatus.FAILED
    )


def test_build_configuration_warning_update(
    state: ChessAnalysisState,
) -> None:
    """Vérifie une erreur de configuration."""

    update = _build_configuration_warning_update(
        state,
        "Configuration invalide.",
    )

    assert (
        update["status"]
        == AnalysisStatus.PARTIAL_SUCCESS
    )

    assert (
        update["warnings"][-1].code
        == ERROR_CONFIGURATION
    )

    assert (
        update["warnings"][-1].message
        == "Configuration invalide."
    )


def test_build_missing_service_update(
    state: ChessAnalysisState,
) -> None:
    """Vérifie l'absence du MongoDBService."""

    update = _build_missing_service_update(
        state
    )

    assert (
        update["warnings"][-1].code
        == ERROR_CONFIGURATION
    )

    assert (
        "MongoDBService"
        in update["warnings"][-1].message
    )

    assert update["analysis_id"] is None


def test_build_missing_request_id_update(
    state: ChessAnalysisState,
) -> None:
    """Vérifie l'absence du request_id."""

    update = _build_missing_request_id_update(
        state
    )

    assert (
        update["warnings"][-1].code
        == ERROR_CONFIGURATION
    )

    assert (
        "request_id"
        in update["warnings"][-1].message
    )

    assert update["analysis_id"] is None


def test_build_database_warning_update(
    state: ChessAnalysisState,
) -> None:
    """Vérifie une erreur MongoDB connue."""

    error = DatabaseError(
        message="MongoDB indisponible.",
    )

    update = _build_database_warning_update(
        state,
        error,
    )

    assert (
        update["warnings"][-1].code
        == error.code
    )

    assert (
        update["warnings"][-1].message
        == str(error)
    )

    assert (
        update["status"]
        == AnalysisStatus.PARTIAL_SUCCESS
    )


def test_build_unexpected_warning_update(
    state: ChessAnalysisState,
) -> None:
    """Vérifie une erreur inattendue."""

    update = _build_unexpected_warning_update(
        state
    )

    assert (
        update["warnings"][-1].code
        == ERROR_UNEXPECTED
    )

    assert (
        update["warnings"][-1].message
        == UNEXPECTED_SAVE_MESSAGE
    )

    assert (
        update["status"]
        == AnalysisStatus.PARTIAL_SUCCESS
    )


# API publique

@pytest.mark.asyncio
async def test_save_analysis_without_request_id(
    state: ChessAnalysisState,
) -> None:
    """Vérifie la sauvegarde ignorée sans request_id."""

    metadata = state.metadata.model_copy(
        update={
            "request_id": None,
        }
    )

    current_state = state.model_copy(
        update={
            "metadata": metadata,
        }
    )

    update = await save_analysis(
        current_state,
        cast(
            RunnableConfig,
            {},
        ),
    )

    assert (
        update["status"]
        == AnalysisStatus.PARTIAL_SUCCESS
    )

    assert update["analysis_id"] is None

    assert (
        update["warnings"][-1].code
        == ERROR_CONFIGURATION
    )


@pytest.mark.asyncio
async def test_save_analysis_missing_service(
    state: ChessAnalysisState,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Vérifie l'absence du MongoDBService."""

    emit_progress = MagicMock()

    monkeypatch.setattr(
        "app.agent.nodes.H_save_analysis."
        "_get_mongodb_service",
        MagicMock(
            return_value=None,
        ),
    )

    monkeypatch.setattr(
        "app.agent.nodes.H_save_analysis."
        "emit_progress",
        emit_progress,
    )

    update = await save_analysis(
        state,
        cast(
            RunnableConfig,
            {},
        ),
    )

    assert (
        update["status"]
        == AnalysisStatus.PARTIAL_SUCCESS
    )

    assert update["analysis_id"] is None

    assert (
        update["warnings"][-1].code
        == ERROR_CONFIGURATION
    )

    emit_progress.assert_called_once()


@pytest.mark.asyncio
async def test_save_analysis_success(
    state: ChessAnalysisState,
    save_result: AnalysisSaveResult,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Vérifie une sauvegarde MongoDB réussie."""

    save = AsyncMock(
        return_value=save_result,
    )

    service = MagicMock(
        spec=MongoDBService,
    )

    service.save_analysis = save

    emit_progress = MagicMock()

    monkeypatch.setattr(
        "app.agent.nodes.H_save_analysis."
        "_get_mongodb_service",
        MagicMock(
            return_value=service,
        ),
    )

    monkeypatch.setattr(
        "app.agent.nodes.H_save_analysis."
        "emit_progress",
        emit_progress,
    )

    update = await save_analysis(
        state,
        cast(
            RunnableConfig,
            {},
        ),
    )

    assert (
        update["status"]
        == AnalysisStatus.SUCCESS
    )

    assert (
        update["analysis_id"]
        == save_result.analysis_id
    )

    assert (
        WorkflowStep.SAVE_ANALYSIS
        in update["completed_steps"]
    )

    save.assert_awaited_once()

    analysis = save.call_args.args[0]

    assert analysis.request_id == REQUEST_ID

    assert (
        analysis.id
        == _build_analysis_id(REQUEST_ID)
    )

    assert emit_progress.call_count == 2


@pytest.mark.asyncio
async def test_save_analysis_handles_database_error(
    state: ChessAnalysisState,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Vérifie une erreur MongoDB connue."""

    database_error = DatabaseError(
        message="MongoDB indisponible.",
    )

    save = AsyncMock(
        side_effect=database_error,
    )

    service = MagicMock(
        spec=MongoDBService,
    )

    service.save_analysis = save

    emit_progress = MagicMock()

    monkeypatch.setattr(
        "app.agent.nodes.H_save_analysis."
        "_get_mongodb_service",
        MagicMock(
            return_value=service,
        ),
    )

    monkeypatch.setattr(
        "app.agent.nodes.H_save_analysis."
        "emit_progress",
        emit_progress,
    )

    update = await save_analysis(
        state,
        cast(
            RunnableConfig,
            {},
        ),
    )

    assert (
        update["status"]
        == AnalysisStatus.PARTIAL_SUCCESS
    )

    assert update["analysis_id"] is None

    assert (
        update["warnings"][-1].code
        == database_error.code
    )

    assert (
        update["warnings"][-1].message
        == str(database_error)
    )

    assert emit_progress.call_count == 2


@pytest.mark.asyncio
async def test_save_analysis_handles_unexpected_error(
    state: ChessAnalysisState,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Vérifie une erreur inattendue pendant la persistance."""

    save = AsyncMock(
        side_effect=RuntimeError(
            "unexpected"
        ),
    )

    service = MagicMock(
        spec=MongoDBService,
    )

    service.save_analysis = save

    emit_progress = MagicMock()

    monkeypatch.setattr(
        "app.agent.nodes.H_save_analysis."
        "_get_mongodb_service",
        MagicMock(
            return_value=service,
        ),
    )

    monkeypatch.setattr(
        "app.agent.nodes.H_save_analysis."
        "emit_progress",
        emit_progress,
    )

    update = await save_analysis(
        state,
        cast(
            RunnableConfig,
            {},
        ),
    )

    assert (
        update["status"]
        == AnalysisStatus.PARTIAL_SUCCESS
    )

    assert update["analysis_id"] is None

    assert (
        update["warnings"][-1].code
        == ERROR_UNEXPECTED
    )

    assert (
        update["warnings"][-1].message
        == UNEXPECTED_SAVE_MESSAGE
    )

    assert (
        WorkflowStep.SAVE_ANALYSIS
        in update["completed_steps"]
    )

    assert emit_progress.call_count == 2


@pytest.mark.asyncio
async def test_save_analysis_preserves_partial_status(
    state: ChessAnalysisState,
    save_result: AnalysisSaveResult,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Vérifie la conservation d'un statut dégradé."""

    partial_state = state.model_copy(
        update={
            "status": (
                AnalysisStatus.PARTIAL_SUCCESS
            ),
        }
    )

    save = AsyncMock(
        return_value=save_result,
    )

    service = MagicMock(
        spec=MongoDBService,
    )

    service.save_analysis = save

    monkeypatch.setattr(
        "app.agent.nodes.H_save_analysis."
        "_get_mongodb_service",
        MagicMock(
            return_value=service,
        ),
    )

    monkeypatch.setattr(
        "app.agent.nodes.H_save_analysis."
        "emit_progress",
        MagicMock(),
    )

    update = await save_analysis(
        partial_state,
        cast(
            RunnableConfig,
            {},
        ),
    )

    assert (
        update["status"]
        == AnalysisStatus.PARTIAL_SUCCESS
    )