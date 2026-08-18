"""Tests unitaires du nœud d'analyse Stockfish LangGraph."""

from __future__ import annotations

from typing import cast
from unittest.mock import AsyncMock, MagicMock

import chess
import pytest
from app.adapters.stockfish_service import StockfishService
from app.agent.nodes.C_engine_analysis import (
    STOCKFISH_SERVICE_KEY,
    _build_engine_summary,
    _build_error_update,
    _build_missing_service_update,
    _build_principal_variation_summary,
    _build_stockfish_error_update,
    _build_success_update,
    _build_unexpected_error_update,
    _enrich_evaluation,
    _format_score,
    _get_stockfish_service,
    _get_success_status,
    engine_analysis,
)
from app.agent.state import ChessAnalysisState
from app.core.constants import (
    ERROR_CONFIGURATION,
    ERROR_UNEXPECTED,
)
from app.core.exceptions import (
    StockfishError,
)
from app.schemas.analysis.evaluation import (
    EngineAnalysis,
    Evaluation,
    PositionEvaluation,
    PrincipalVariation,
)
from app.schemas.chess.move import BestMove
from app.schemas.chess.position import FenRequest
from app.schemas.common.enums import (
    AnalysisStatus,
    EvaluationType,
    WorkflowStep,
)
from app.schemas.common.error import (
    WorkflowError,
)
from langchain_core.runnables import RunnableConfig

# Configuration

STARTING_FEN = chess.STARTING_FEN


# Construction des données de test

def build_best_move(
    *,
    uci: str = "e2e4",
    san: str = "e4",
    score: float = 30.0,
    evaluation_type: EvaluationType = (
        EvaluationType.CENTIPAWN
    ),
    depth: int = 15,
) -> BestMove:
    """Construit un meilleur coup Stockfish."""

    return BestMove(
        uci=uci,
        san=san,
        from_square=uci[:2],
        to_square=uci[2:4],
        score=score,
        evaluation_type=evaluation_type,
        depth=depth,
        principal_variation=[
            uci,
        ],
    )


def build_evaluation(
    *,
    score: float = 30.0,
    evaluation_type: EvaluationType = (
        EvaluationType.CENTIPAWN
    ),
    depth: int = 15,
    nodes: int | None = 1000,
    time_ms: int | None = 250,
    moves: list[str] | None = None,
    alternatives: list[BestMove] | None = None,
    summary: str | None = None,
) -> PositionEvaluation:
    """Construit une évaluation Stockfish complète."""

    engine_evaluation = Evaluation(
        score=score,
        evaluation_type=evaluation_type,
        depth=depth,
        nodes=nodes,
        time_ms=time_ms,
    )

    principal_variation = PrincipalVariation(
        moves=(
            moves
            if moves is not None
            else [
                "e2e4",
                "e7e5",
                "g1f3",
            ]
        ),
        evaluation=engine_evaluation,
        explanation=None,
    )

    engine = EngineAnalysis(
        best_move=build_best_move(
            score=score,
            evaluation_type=evaluation_type,
            depth=depth,
        ),
        evaluation=engine_evaluation,
        principal_variation=principal_variation,
        alternatives=(
            alternatives
            if alternatives is not None
            else [
                build_best_move(
                    uci="d2d4",
                    san="d4",
                    score=20.0,
                ),
            ]
        ),
    )

    return PositionEvaluation(
        engine=engine,
        summary=summary,
    )


# Fixtures

@pytest.fixture
def state() -> ChessAnalysisState:
    """Construit un état minimal valide."""

    return ChessAnalysisState(
        fen=STARTING_FEN,
    )


@pytest.fixture
def evaluation() -> PositionEvaluation:
    """Construit une évaluation Stockfish complète."""

    return build_evaluation()


# Service

def test_get_stockfish_service_returns_configured_service(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Vérifie la récupération du service Stockfish."""

    service = MagicMock(
        spec=StockfishService,
    )

    configured_service = MagicMock(
        return_value=service,
    )

    monkeypatch.setattr(
        "app.agent.nodes.C_engine_analysis."
        "get_configured_service",
        configured_service,
    )

    config = cast(
        RunnableConfig,
        {},
    )

    result = _get_stockfish_service(
        config
    )

    assert result is service

    configured_service.assert_called_once_with(
        config,
        STOCKFISH_SERVICE_KEY,
        expected_type=StockfishService,
    )


def test_get_stockfish_service_returns_none_when_missing(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Vérifie l'absence du service Stockfish."""

    configured_service = MagicMock(
        return_value=None,
    )

    monkeypatch.setattr(
        "app.agent.nodes.C_engine_analysis."
        "get_configured_service",
        configured_service,
    )

    result = _get_stockfish_service(
        cast(
            RunnableConfig,
            {},
        )
    )

    assert result is None


def test_get_stockfish_service_rejects_invalid_type(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Vérifie le rejet d'un service d'un autre type."""

    configured_service = MagicMock(
        return_value=object(),
    )

    monkeypatch.setattr(
        "app.agent.nodes.C_engine_analysis."
        "get_configured_service",
        configured_service,
    )

    result = _get_stockfish_service(
        cast(
            RunnableConfig,
            {},
        )
    )

    assert result is None


# Statut

@pytest.mark.parametrize(
    ("initial_status", "expected_status"),
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
    initial_status: AnalysisStatus,
    expected_status: AnalysisStatus,
) -> None:
    """Vérifie le statut après une analyse moteur réussie."""

    current_state = state.model_copy(
        update={
            "status": initial_status,
        }
    )

    assert (
        _get_success_status(
            current_state
        )
        == expected_status
    )


# Formatage du score

def test_format_score_centipawn() -> None:
    """Vérifie le format centipion."""

    assert (
        _format_score(
            42.0,
            EvaluationType.CENTIPAWN,
        )
        == "42 centipions"
    )


def test_format_score_centipawn_rounds_value() -> None:
    """Vérifie l'arrondi du score centipion."""

    assert (
        _format_score(
            42.6,
            EvaluationType.CENTIPAWN,
        )
        == "43 centipions"
    )


def test_format_score_mate() -> None:
    """Vérifie le format d'un score de mat."""

    assert (
        _format_score(
            3.0,
            EvaluationType.MATE,
        )
        == "mat en 3"
    )


def test_format_score_negative_mate() -> None:
    """Vérifie un mat défavorable."""

    assert (
        _format_score(
            -2.0,
            EvaluationType.MATE,
        )
        == "mat en -2"
    )


# Résumé moteur

def test_build_engine_summary_contains_main_information(
    evaluation: PositionEvaluation,
) -> None:
    """Vérifie le résumé moteur complet."""

    result = _build_engine_summary(
        evaluation
    )

    assert (
        "Meilleur coup retourné par Stockfish : "
        "e4 (e2e4)."
        in result
    )

    assert (
        "Évaluation retournée : "
        "30 centipions."
        in result
    )

    assert (
        "Profondeur d'analyse : 15."
        in result
    )

    assert (
        "Nœuds analysés : 1000."
        in result
    )

    assert (
        "Temps d'analyse : 250 ms."
        in result
    )

    assert (
        "Variante principale calculée : "
        "e2e4 e7e5 g1f3."
        in result
    )

    assert (
        "Alternatives retournées : "
        "d4 (20 centipions)."
        in result
    )


def test_build_engine_summary_without_optional_values() -> None:
    """Vérifie le résumé sans métriques optionnelles."""

    value = build_evaluation(
        nodes=None,
        time_ms=None,
        moves=[],
        alternatives=[],
    )

    result = _build_engine_summary(
        value
    )

    assert (
        "Évaluation retournée : "
        "30 centipions."
        in result
    )

    assert (
        "Nœuds analysés"
        not in result
    )

    assert (
        "Temps d'analyse"
        not in result
    )

    assert (
        "Variante principale calculée"
        not in result
    )

    assert (
        "Alternatives retournées"
        not in result
    )


def test_build_engine_summary_formats_mate() -> None:
    """Vérifie le format d'un score de mat dans le résumé."""

    value = build_evaluation(
        score=3.0,
        evaluation_type=EvaluationType.MATE,
        alternatives=[],
    )

    result = _build_engine_summary(
        value
    )

    assert "mat en 3" in result


# Variante principale

def test_build_principal_variation_summary(
    evaluation: PositionEvaluation,
) -> None:
    """Vérifie le résumé de la variante principale."""

    result = (
        _build_principal_variation_summary(
            evaluation
        )
    )

    assert result is not None

    assert (
        "Variante principale calculée par Stockfish "
        "à la profondeur 15"
        in result
    )

    assert (
        "e2e4 e7e5 g1f3"
        in result
    )

    assert (
        "Évaluation associée : "
        "30 centipions."
        in result
    )


def test_build_principal_variation_summary_returns_none() -> None:
    """Vérifie l'absence de variante principale."""

    value = build_evaluation(
        moves=[],
        alternatives=[],
    )

    assert (
        _build_principal_variation_summary(
            value
        )
        is None
    )


def test_build_principal_variation_summary_formats_mate() -> None:
    """Vérifie le format du mat dans la variante."""

    value = build_evaluation(
        score=4.0,
        evaluation_type=EvaluationType.MATE,
        alternatives=[],
    )

    result = (
        _build_principal_variation_summary(
            value
        )
    )

    assert result is not None
    assert "mat en 4" in result


# Enrichissement

def test_enrich_evaluation_adds_summary_and_explanation(
    evaluation: PositionEvaluation,
) -> None:
    """Vérifie l'enrichissement de l'évaluation."""

    result = _enrich_evaluation(
        evaluation
    )

    assert result.summary is not None

    assert (
        result
        .engine
        .principal_variation
        .explanation
        is not None
    )

    assert (
        "Meilleur coup retourné par Stockfish"
        in result.summary
    )

    assert (
        "Variante principale calculée par Stockfish"
        in (
            result
            .engine
            .principal_variation
            .explanation
            or ""
        )
    )


def test_enrich_evaluation_does_not_mutate_original(
    evaluation: PositionEvaluation,
) -> None:
    """Vérifie que l'objet original n'est pas modifié."""

    assert evaluation.summary is None

    assert (
        evaluation
        .engine
        .principal_variation
        .explanation
        is None
    )

    result = _enrich_evaluation(
        evaluation
    )

    assert result is not evaluation

    assert evaluation.summary is None

    assert (
        evaluation
        .engine
        .principal_variation
        .explanation
        is None
    )


# Mises à jour

def test_build_error_update_marks_failed(
    state: ChessAnalysisState,
) -> None:
    """Vérifie une mise à jour d'échec."""

    error = WorkflowError(
        step=WorkflowStep.ENGINE_ANALYSIS,
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
        == WorkflowStep.ENGINE_ANALYSIS
    )

    assert result["completed_steps"] == []
    assert result["errors"] == [error]
    assert result["warnings"] == []


def test_build_success_update(
    state: ChessAnalysisState,
    evaluation: PositionEvaluation,
) -> None:
    """Vérifie la mise à jour réussie."""

    enriched = _enrich_evaluation(
        evaluation
    )

    result = _build_success_update(
        state,
        enriched,
    )

    assert (
        result["status"]
        == AnalysisStatus.SUCCESS
    )

    assert (
        result["current_step"]
        == WorkflowStep.ENGINE_ANALYSIS
    )

    assert (
        result["evaluation"]
        == enriched
    )

    assert (
        WorkflowStep.ENGINE_ANALYSIS
        in result["completed_steps"]
    )

    assert (
        result[
            "workflow_context"
        ].engine_context
        == enriched.summary
    )


def test_build_success_update_preserves_partial_status(
    state: ChessAnalysisState,
    evaluation: PositionEvaluation,
) -> None:
    """Vérifie qu'une dégradation antérieure est conservée."""

    partial_state = state.model_copy(
        update={
            "status": AnalysisStatus.PARTIAL_SUCCESS,
        }
    )

    enriched = _enrich_evaluation(
        evaluation
    )

    result = _build_success_update(
        partial_state,
        enriched,
    )

    assert (
        result["status"]
        == AnalysisStatus.PARTIAL_SUCCESS
    )


def test_build_success_update_uses_fallback_context(
    state: ChessAnalysisState,
    evaluation: PositionEvaluation,
) -> None:
    """Vérifie le contexte de repli sans résumé."""

    result = _build_success_update(
        state,
        evaluation,
    )

    assert (
        result[
            "workflow_context"
        ].engine_context
        == "Aucune synthèse moteur n'est disponible."
    )


def test_build_missing_service_update(
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

    assert (
        result["errors"][0].code
        == ERROR_CONFIGURATION
    )

    assert (
        result["errors"][0].recoverable
        is False
    )


def test_build_stockfish_error_update(
    state: ChessAnalysisState,
) -> None:
    """Vérifie la conversion d'une erreur Stockfish."""

    error = StockfishError(
        message="Stockfish indisponible.",
    )

    result = _build_stockfish_error_update(
        state,
        error,
    )

    assert (
        result["status"]
        == AnalysisStatus.FAILED
    )

    assert (
        result["errors"][0].code
        == error.code
    )

    assert (
        result["errors"][0].recoverable
        == error.retryable
    )

    assert (
        result["errors"][0].message
        == str(error)
    )


def test_build_unexpected_error_update(
    state: ChessAnalysisState,
) -> None:
    """Vérifie l'erreur inattendue."""

    result = _build_unexpected_error_update(
        state
    )

    assert (
        result["status"]
        == AnalysisStatus.FAILED
    )

    assert (
        result["errors"][0].code
        == ERROR_UNEXPECTED
    )

    assert (
        result["errors"][0].recoverable
        is False
    )


# API publique

@pytest.mark.asyncio
async def test_engine_analysis_success(
    state: ChessAnalysisState,
    evaluation: PositionEvaluation,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Vérifie une analyse Stockfish réussie."""

    analyze_position = AsyncMock(
        return_value=evaluation,
    )

    service = MagicMock(
        spec=StockfishService,
    )

    service.analyze_position = analyze_position

    get_service = MagicMock(
        return_value=service,
    )

    emit_progress = MagicMock()

    monkeypatch.setattr(
        "app.agent.nodes.C_engine_analysis."
        "_get_stockfish_service",
        get_service,
    )

    monkeypatch.setattr(
        "app.agent.nodes.C_engine_analysis."
        "emit_progress",
        emit_progress,
    )

    result = await engine_analysis(
        state,
        cast(
            RunnableConfig,
            {},
        ),
    )

    assert (
        result["status"]
        == AnalysisStatus.SUCCESS
    )

    assert (
        result["current_step"]
        == WorkflowStep.ENGINE_ANALYSIS
    )

    assert (
        WorkflowStep.ENGINE_ANALYSIS
        in result["completed_steps"]
    )

    returned_evaluation = result[
        "evaluation"
    ]

    assert returned_evaluation.summary is not None

    assert (
        returned_evaluation
        .engine
        .principal_variation
        .explanation
        is not None
    )

    analyze_position.assert_awaited_once()

    request = (
        analyze_position
        .call_args
        .args[0]
    )

    assert isinstance(
        request,
        FenRequest,
    )

    assert request.fen == STARTING_FEN

    assert emit_progress.call_count == 2


@pytest.mark.asyncio
async def test_engine_analysis_missing_service(
    state: ChessAnalysisState,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Vérifie l'absence de StockfishService."""

    get_service = MagicMock(
        return_value=None,
    )

    emit_progress = MagicMock()

    monkeypatch.setattr(
        "app.agent.nodes.C_engine_analysis."
        "_get_stockfish_service",
        get_service,
    )

    monkeypatch.setattr(
        "app.agent.nodes.C_engine_analysis."
        "emit_progress",
        emit_progress,
    )

    result = await engine_analysis(
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
async def test_engine_analysis_handles_stockfish_error(
    state: ChessAnalysisState,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Vérifie une erreur métier Stockfish."""

    stockfish_error = StockfishError(
        message="Stockfish indisponible.",
    )

    analyze_position = AsyncMock(
        side_effect=stockfish_error,
    )

    service = MagicMock(
        spec=StockfishService,
    )

    service.analyze_position = analyze_position

    emit_progress = MagicMock()

    monkeypatch.setattr(
        "app.agent.nodes.C_engine_analysis."
        "_get_stockfish_service",
        MagicMock(
            return_value=service,
        ),
    )

    monkeypatch.setattr(
        "app.agent.nodes.C_engine_analysis."
        "emit_progress",
        emit_progress,
    )

    result = await engine_analysis(
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
        == stockfish_error.code
    )

    assert (
        result["errors"][0].recoverable
        == stockfish_error.retryable
    )

    assert (
        WorkflowStep.ENGINE_ANALYSIS
        not in result["completed_steps"]
    )

    assert emit_progress.call_count == 2


@pytest.mark.asyncio
async def test_engine_analysis_handles_unexpected_error(
    state: ChessAnalysisState,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Vérifie une erreur inattendue."""

    analyze_position = AsyncMock(
        side_effect=RuntimeError(
            "unexpected failure"
        ),
    )

    service = MagicMock(
        spec=StockfishService,
    )

    service.analyze_position = analyze_position

    emit_progress = MagicMock()

    monkeypatch.setattr(
        "app.agent.nodes.C_engine_analysis."
        "_get_stockfish_service",
        MagicMock(
            return_value=service,
        ),
    )

    monkeypatch.setattr(
        "app.agent.nodes.C_engine_analysis."
        "emit_progress",
        emit_progress,
    )

    result = await engine_analysis(
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

    assert (
        WorkflowStep.ENGINE_ANALYSIS
        not in result["completed_steps"]
    )

    assert emit_progress.call_count == 2