"""Tests unitaires du nœud de validation de position LangGraph."""

from __future__ import annotations

from typing import cast
from unittest.mock import MagicMock, call

import chess
import pytest
from app.agent.nodes.A_validate_position import (
    CHESS_SERVICE_KEY,
    _build_error_update,
    _build_missing_service_update,
    _build_position_summary,
    _build_success_update,
    _build_unexpected_error_update,
    _get_chess_service,
    validate_position,
)
from app.agent.state import ChessAnalysisState
from app.core.constants import (
    ERROR_CONFIGURATION,
    ERROR_INVALID_FEN,
    ERROR_UNEXPECTED,
)
from app.schemas.chess.position import (
    BoardPosition,
    FenRequest,
)
from app.schemas.common.enums import (
    AnalysisStatus,
    ServiceType,
    WorkflowStep,
    WorkflowStepStatus,
)
from app.schemas.common.error import WorkflowError
from app.services.chess_service import ChessService
from langchain_core.runnables import RunnableConfig

# Configuration

STARTING_FEN = chess.STARTING_FEN


# Fixtures

@pytest.fixture
def state() -> ChessAnalysisState:
    """Construit un état minimal valide."""

    return ChessAnalysisState(
        fen=STARTING_FEN,
    )


@pytest.fixture
def chess_service() -> ChessService:
    """Construit le service d'échecs réel."""

    return ChessService()


@pytest.fixture
def position(
    chess_service: ChessService,
) -> BoardPosition:
    """Construit une position réelle depuis la FEN initiale."""

    return chess_service.get_position(
        FenRequest(
            fen=STARTING_FEN,
        )
    )


# Service

def test_get_chess_service_returns_configured_service(
    chess_service: ChessService,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Vérifie la récupération du ChessService configuré."""

    configured_service = MagicMock(
        return_value=chess_service,
    )

    monkeypatch.setattr(
        "app.agent.nodes.A_validate_position."
        "get_configured_service",
        configured_service,
    )

    config = cast(
        RunnableConfig,
        {},
    )

    result = _get_chess_service(
        config
    )

    assert result is chess_service

    configured_service.assert_called_once_with(
        config,
        CHESS_SERVICE_KEY,
        expected_type=ChessService,
    )


def test_get_chess_service_returns_none_when_missing(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Vérifie l'absence du service."""

    configured_service = MagicMock(
        return_value=None,
    )

    monkeypatch.setattr(
        "app.agent.nodes.A_validate_position."
        "get_configured_service",
        configured_service,
    )

    result = _get_chess_service(
        cast(
            RunnableConfig,
            {},
        )
    )

    assert result is None


def test_get_chess_service_returns_none_for_invalid_type(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Vérifie le rejet d'un service d'un autre type."""

    configured_service = MagicMock(
        return_value=object(),
    )

    monkeypatch.setattr(
        "app.agent.nodes.A_validate_position."
        "get_configured_service",
        configured_service,
    )

    result = _get_chess_service(
        cast(
            RunnableConfig,
            {},
        )
    )

    assert result is None


# Résumé

def test_build_position_summary_contains_fullmove_number(
    position: BoardPosition,
) -> None:
    """Vérifie le résumé factuel de la position."""

    result = _build_position_summary(
        position
    )

    assert (
        result
        == (
            "La position FEN est valide au coup "
            f"{position.fullmove_number} "
            "et peut être analysée."
        )
    )


# Mise à jour d'erreur

def test_build_error_update_marks_state_as_failed(
    state: ChessAnalysisState,
) -> None:
    """Vérifie une mise à jour d'échec."""

    error = WorkflowError(
        step=WorkflowStep.VALIDATE_POSITION,
        code=ERROR_UNEXPECTED,
        message="Erreur de test.",
        recoverable=False,
    )

    result = _build_error_update(
        state,
        error,
    )

    assert (
        result["status"]
        == AnalysisStatus.FAILED
    )

    assert (
        result["current_step"]
        == WorkflowStep.VALIDATE_POSITION
    )

    assert result["completed_steps"] == []
    assert result["errors"] == [error]
    assert result["warnings"] == []


def test_build_error_update_preserves_existing_state_data(
    state: ChessAnalysisState,
) -> None:
    """Vérifie la conservation des erreurs précédentes."""

    previous_error = WorkflowError(
        step=WorkflowStep.VALIDATE_POSITION,
        code="PREVIOUS",
        message="Erreur précédente.",
        recoverable=False,
    )

    state = state.model_copy(
        update={
            "errors": [
                previous_error,
            ],
        }
    )

    new_error = WorkflowError(
        step=WorkflowStep.VALIDATE_POSITION,
        code=ERROR_UNEXPECTED,
        message="Nouvelle erreur.",
        recoverable=False,
    )

    result = _build_error_update(
        state,
        new_error,
    )

    assert result["errors"] == [
        previous_error,
        new_error,
    ]


# Mise à jour réussie

def test_build_success_update_returns_position(
    state: ChessAnalysisState,
    position: BoardPosition,
) -> None:
    """Vérifie la mise à jour d'une validation réussie."""

    result = _build_success_update(
        state,
        position,
    )

    assert (
        result["status"]
        == state.status
    )

    assert (
        result["current_step"]
        == WorkflowStep.VALIDATE_POSITION
    )

    assert (
        result["position"]
        == position
    )

    assert (
        WorkflowStep.VALIDATE_POSITION
        in result["completed_steps"]
    )

    workflow_context = result[
        "workflow_context"
    ]

    assert (
        workflow_context.position_summary
        == _build_position_summary(position)
    )


def test_build_success_update_does_not_mutate_original_state(
    state: ChessAnalysisState,
    position: BoardPosition,
) -> None:
    """Vérifie le fonctionnement transformationnel du nœud."""

    original_completed_steps = list(
        state.completed_steps
    )

    original_summary = (
        state
        .workflow_context
        .position_summary
    )

    _build_success_update(
        state,
        position,
    )

    assert (
        state.completed_steps
        == original_completed_steps
    )

    assert (
        state
        .workflow_context
        .position_summary
        == original_summary
    )


# Erreurs spécialisées

def test_build_missing_service_update_uses_configuration_error(
    state: ChessAnalysisState,
) -> None:
    """Vérifie l'erreur de configuration."""

    result = _build_missing_service_update(
        state
    )

    assert (
        result["status"]
        == AnalysisStatus.FAILED
    )

    errors = result["errors"]

    assert len(errors) == 1

    assert (
        errors[0].code
        == ERROR_CONFIGURATION
    )

    assert (
        errors[0].recoverable
        is False
    )


def test_build_unexpected_error_update_uses_unexpected_code(
    state: ChessAnalysisState,
) -> None:
    """Vérifie l'erreur inattendue."""

    result = _build_unexpected_error_update(
        state
    )

    errors = result["errors"]

    assert len(errors) == 1

    assert (
        errors[0].code
        == ERROR_UNEXPECTED
    )

    assert (
        result["status"]
        == AnalysisStatus.FAILED
    )


# Validation publique

@pytest.mark.asyncio
async def test_validate_position_returns_success_update(
    state: ChessAnalysisState,
    chess_service: ChessService,
    position: BoardPosition,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Vérifie une validation FEN réussie."""

    get_position = MagicMock(
        return_value=position,
    )

    monkeypatch.setattr(
        chess_service,
        "get_position",
        get_position,
    )

    get_service = MagicMock(
        return_value=chess_service,
    )

    emit_progress = MagicMock()

    monkeypatch.setattr(
        "app.agent.nodes.A_validate_position."
        "_get_chess_service",
        get_service,
    )

    monkeypatch.setattr(
        "app.agent.nodes.A_validate_position."
        "emit_progress",
        emit_progress,
    )

    result = await validate_position(
        state,
        cast(
            RunnableConfig,
            {},
        ),
    )

    assert (
        result["status"]
        == state.status
    )

    assert (
        result["position"]
        == position
    )

    assert (
        WorkflowStep.VALIDATE_POSITION
        in result["completed_steps"]
    )

    get_position.assert_called_once()

    request = get_position.call_args.args[0]

    assert isinstance(
        request,
        FenRequest,
    )

    assert request.fen == STARTING_FEN

    assert emit_progress.call_count == 2


@pytest.mark.asyncio
async def test_validate_position_fails_when_service_is_missing(
    state: ChessAnalysisState,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Vérifie l'échec lorsque ChessService manque."""

    get_service = MagicMock(
        return_value=None,
    )

    emit_progress = MagicMock()

    monkeypatch.setattr(
        "app.agent.nodes.A_validate_position."
        "_get_chess_service",
        get_service,
    )

    monkeypatch.setattr(
        "app.agent.nodes.A_validate_position."
        "emit_progress",
        emit_progress,
    )

    result = await validate_position(
        state,
        cast(
            RunnableConfig,
            {},
        ),
    )

    assert (
        result["status"]
        == AnalysisStatus.FAILED
    )

    assert (
        result["errors"][0].code
        == ERROR_CONFIGURATION
    )

    assert result["completed_steps"] == []

    emit_progress.assert_called_once()


@pytest.mark.asyncio
async def test_validate_position_handles_pydantic_validation_error(
    state: ChessAnalysisState,
    chess_service: ChessService,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Vérifie une FEN invalide rejetée par FenRequest."""

    invalid_state = state.model_copy(
        update={
            "fen": "",
        }
    )

    get_service = MagicMock(
        return_value=chess_service,
    )

    emit_progress = MagicMock()

    monkeypatch.setattr(
        "app.agent.nodes.A_validate_position."
        "_get_chess_service",
        get_service,
    )

    monkeypatch.setattr(
        "app.agent.nodes.A_validate_position."
        "emit_progress",
        emit_progress,
    )

    result = await validate_position(
        invalid_state,
        cast(
            RunnableConfig,
            {},
        ),
    )

    assert (
        result["status"]
        == AnalysisStatus.FAILED
    )

    assert (
        result["errors"][0].code
        == ERROR_INVALID_FEN
    )

    assert result["completed_steps"] == []

    emit_progress.assert_called_once()


@pytest.mark.asyncio
async def test_validate_position_handles_unexpected_error(
    state: ChessAnalysisState,
    chess_service: ChessService,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Vérifie une erreur inattendue de ChessService."""

    get_position = MagicMock(
        side_effect=RuntimeError(
            "unexpected failure"
        ),
    )

    monkeypatch.setattr(
        chess_service,
        "get_position",
        get_position,
    )

    get_service = MagicMock(
        return_value=chess_service,
    )

    emit_progress = MagicMock()

    monkeypatch.setattr(
        "app.agent.nodes.A_validate_position."
        "_get_chess_service",
        get_service,
    )

    monkeypatch.setattr(
        "app.agent.nodes.A_validate_position."
        "emit_progress",
        emit_progress,
    )

    result = await validate_position(
        state,
        cast(
            RunnableConfig,
            {},
        ),
    )

    assert (
        result["status"]
        == AnalysisStatus.FAILED
    )

    assert (
        result["errors"][0].code
        == ERROR_UNEXPECTED
    )

    assert result["completed_steps"] == []

    emit_progress.assert_has_calls(
        [
            call(
                step=WorkflowStep.VALIDATE_POSITION,
                service=ServiceType.CHESS,
                status=WorkflowStepStatus.RUNNING,
                message="Validation de la position en cours.",
            ),
            call(
                step=WorkflowStep.VALIDATE_POSITION,
                service=ServiceType.CHESS,
                status=WorkflowStepStatus.FAILED,
                message=(
                    "Une erreur inattendue a interrompu "
                    "la validation de la position."
                ),
            ),
        ]
    )

    assert emit_progress.call_count == 2