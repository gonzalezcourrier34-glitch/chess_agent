"""Tests unitaires du nœud de détection d'ouverture LangGraph."""

from __future__ import annotations

from typing import cast
from unittest.mock import AsyncMock, MagicMock

import chess
import pytest
from app.adapters.lichess_service import LichessService
from app.agent.nodes.B_detect_theory import (
    LICHESS_SERVICE_KEY,
    MAX_CONTEXT_VARIATIONS,
    _build_error_update,
    _build_missing_service_update,
    _build_opening_context,
    _build_opening_summary,
    _build_statistics_context,
    _build_success_update,
    _build_theory_context,
    _build_unexpected_error_update,
    _build_variations_context,
    _build_warning_update,
    _get_lichess_service,
    _get_partial_success_status,
    detect_theory,
)
from app.agent.state import ChessAnalysisState
from app.core.constants import (
    ERROR_CONFIGURATION,
    ERROR_LICHESS_UNAVAILABLE,
    ERROR_OPENING_NOT_FOUND,
    ERROR_UNEXPECTED,
)
from app.core.exceptions import (
    LichessError,
    OpeningNotFoundError,
)
from app.schemas.chess.opening import (
    Opening,
    OpeningDetails,
    OpeningStatistics,
    OpeningTheory,
    OpeningVariation,
)
from app.schemas.chess.position import FenRequest
from app.schemas.common.enums import (
    AnalysisStatus,
    WorkflowStep,
)
from app.schemas.common.error import (
    WorkflowError,
    WorkflowWarning,
)
from langchain_core.runnables import RunnableConfig

# Configuration

STARTING_FEN = chess.STARTING_FEN

GIUOCO_PIANO_FEN = (
    "r1bqk1nr/pppp1ppp/2n5/2b1p3/"
    "2B1P3/5N2/PPPP1PPP/RNBQK2R "
    "w KQkq - 4 4"
)


# Fixtures

@pytest.fixture
def state() -> ChessAnalysisState:
    """Construit un état minimal valide."""

    return ChessAnalysisState(
        fen=STARTING_FEN,
    )


@pytest.fixture
def opening() -> OpeningDetails:
    """Construit une ouverture complète pour les tests."""

    return OpeningDetails(
        opening=Opening(
            name="Italian Game",
            eco="C50",
            variation="Classical Variation",
            family="King's Pawn Game",
            moves=[
                "e4",
                "e5",
                "Nf3",
                "Nc6",
                "Bc4",
            ],
            description="Ouverture classique.",
        ),
        statistics=OpeningStatistics(
            games=1000,
            white_win_rate=40.0,
            draw_rate=30.0,
            black_win_rate=30.0,
        ),
        theory=OpeningTheory(
            overview="Développement rapide des pièces.",
            strategic_ideas=[
                "Contrôler le centre",
            ],
            tactical_patterns=[
                "Pression sur f7",
            ],
            typical_plans_white=[
                "Développer rapidement",
            ],
            typical_plans_black=[
                "Contester le centre",
            ],
            common_mistakes=[
                "Sortir la dame trop tôt",
            ],
        ),
        variations=[
            OpeningVariation(
                name="Giuoco Piano",
                eco="C50",
                moves=[
                    "e4",
                    "e5",
                    "Nf3",
                    "Nc6",
                    "Bc4",
                    "Bc5",
                ],
                final_fen=GIUOCO_PIANO_FEN,
            ),
        ],
    )


# Services

def test_get_lichess_service_returns_configured_service(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Vérifie la récupération du service Lichess configuré."""

    service = MagicMock(
        spec=LichessService,
    )

    configured_service = MagicMock(
        return_value=service,
    )

    monkeypatch.setattr(
        "app.agent.nodes.B_detect_theory."
        "get_configured_service",
        configured_service,
    )

    config = cast(
        RunnableConfig,
        {},
    )

    result = _get_lichess_service(
        config
    )

    assert result is service

    configured_service.assert_called_once_with(
        config,
        LICHESS_SERVICE_KEY,
        expected_type=LichessService,
    )


def test_get_lichess_service_returns_none_when_missing(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Vérifie l'absence du service Lichess."""

    configured_service = MagicMock(
        return_value=None,
    )

    monkeypatch.setattr(
        "app.agent.nodes.B_detect_theory."
        "get_configured_service",
        configured_service,
    )

    result = _get_lichess_service(
        cast(
            RunnableConfig,
            {},
        )
    )

    assert result is None


def test_get_lichess_service_rejects_invalid_type(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Vérifie le rejet d'un service d'un autre type."""

    configured_service = MagicMock(
        return_value=object(),
    )

    monkeypatch.setattr(
        "app.agent.nodes.B_detect_theory."
        "get_configured_service",
        configured_service,
    )

    result = _get_lichess_service(
        cast(
            RunnableConfig,
            {},
        )
    )

    assert result is None


# Statuts

@pytest.mark.parametrize(
    ("initial_status", "expected_status"),
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
    initial_status: AnalysisStatus,
    expected_status: AnalysisStatus,
) -> None:
    """Vérifie le calcul du statut dégradé."""

    current_state = state.model_copy(
        update={
            "status": initial_status,
        }
    )

    result = _get_partial_success_status(
        current_state
    )

    assert result == expected_status


# Résumés

def test_build_opening_summary(
    opening: OpeningDetails,
) -> None:
    """Vérifie le résumé d'une ouverture complète."""

    result = _build_opening_summary(
        opening
    )

    assert "Italian Game" in result
    assert "C50" in result
    assert "Classical Variation" in result
    assert "Variantes connues disponibles : 1." in result


def test_build_opening_summary_without_optional_information() -> None:
    """Vérifie un résumé sans variante complémentaire."""

    details = OpeningDetails(
        opening=Opening(
            name="Italian Game",
            eco="C50",
            moves=[],
        ),
        statistics=None,
        theory=None,
        variations=[],
    )

    result = _build_opening_summary(
        details
    )

    assert result == (
        "Ouverture : Italian Game. "
        "Code ECO : C50."
    )


# Statistiques

def test_build_statistics_context_returns_none() -> None:
    """Vérifie l'absence de statistiques."""

    assert (
        _build_statistics_context(
            None
        )
        is None
    )


def test_build_statistics_context() -> None:
    """Vérifie la construction du contexte statistique."""

    statistics = OpeningStatistics(
        games=1000,
        white_win_rate=40.0,
        draw_rate=30.0,
        black_win_rate=30.0,
    )

    result = _build_statistics_context(
        statistics
    )

    assert result is not None
    assert "1000 parties" in result
    assert "40.0% de victoires blanches" in result
    assert "30.0% de nulles" in result
    assert "30.0% de victoires noires" in result


# Théorie

def test_build_theory_context_returns_none() -> None:
    """Vérifie l'absence de théorie."""

    assert (
        _build_theory_context(
            None
        )
        is None
    )


def test_build_theory_context() -> None:
    """Vérifie la construction du contexte théorique."""

    theory = OpeningTheory(
        overview="Présentation.",
        strategic_ideas=[
            "Contrôler le centre",
        ],
        tactical_patterns=[
            "Attaque sur f7",
        ],
        typical_plans_white=[
            "Développer les pièces",
        ],
        typical_plans_black=[
            "Contester le centre",
        ],
        common_mistakes=[
            "Sortir la dame trop tôt",
        ],
    )

    result = _build_theory_context(
        theory
    )

    assert result is not None
    assert "Présentation théorique : Présentation." in result
    assert "Contrôler le centre" in result
    assert "Attaque sur f7" in result
    assert "Développer les pièces" in result
    assert "Contester le centre" in result
    assert "Sortir la dame trop tôt" in result


# Variantes

def test_build_variations_context_returns_none() -> None:
    """Vérifie l'absence de variantes."""

    assert (
        _build_variations_context(
            []
        )
        is None
    )


def test_build_variations_context() -> None:
    """Vérifie la construction du contexte des variantes."""

    variations = [
        OpeningVariation(
            name="Giuoco Piano",
            eco="C50",
            moves=[
                "e4",
                "e5",
                "Nf3",
            ],
            final_fen=STARTING_FEN,
        ),
    ]

    result = _build_variations_context(
        variations
    )

    assert result is not None
    assert "Giuoco Piano" in result
    assert "C50" in result
    assert "e4 e5 Nf3" in result


def test_build_variations_context_without_moves() -> None:
    """Vérifie le repli lorsqu'aucun coup n'est disponible."""

    variations = [
        OpeningVariation(
            name="Variation vide",
            eco="C50",
            moves=[],
            final_fen=STARTING_FEN,
        ),
    ]

    result = _build_variations_context(
        variations
    )

    assert result is not None
    assert "suite non précisée" in result


def test_build_variations_context_limits_results() -> None:
    """Vérifie la limite du nombre de variantes."""

    variations = [
        OpeningVariation(
            name=f"Variation {index}",
            eco="C50",
            moves=[
                "e4",
            ],
            final_fen=STARTING_FEN,
        )
        for index in range(
            MAX_CONTEXT_VARIATIONS + 2
        )
    ]

    result = _build_variations_context(
        variations
    )

    assert result is not None

    assert (
        f"Variation {MAX_CONTEXT_VARIATIONS - 1}"
        in result
    )

    assert (
        f"Variation {MAX_CONTEXT_VARIATIONS}"
        not in result
    )


# Contexte complet

def test_build_opening_context(
    opening: OpeningDetails,
) -> None:
    """Vérifie le contexte complet d'une ouverture."""

    result = _build_opening_context(
        opening
    )

    assert "Italian Game" in result
    assert "C50" in result
    assert "Classical Variation" in result
    assert "King's Pawn Game" in result
    assert "e4 e5 Nf3 Nc6 Bc4" in result
    assert "Ouverture classique." in result
    assert "Statistiques globales" in result
    assert "Présentation théorique" in result
    assert "Variantes principales" in result


def test_build_opening_context_without_theory_or_variations() -> None:
    """Vérifie les messages de repli du contexte."""

    details = OpeningDetails(
        opening=Opening(
            name="Italian Game",
            eco="C50",
            moves=[],
        ),
        statistics=None,
        theory=None,
        variations=[],
    )

    result = _build_opening_context(
        details
    )

    assert (
        "Aucune théorie pédagogique détaillée "
        "n'est disponible."
        in result
    )

    assert (
        "Aucune variante complète n'est disponible."
        in result
    )


# Mises à jour

def test_build_success_update(
    state: ChessAnalysisState,
    opening: OpeningDetails,
) -> None:
    """Vérifie la mise à jour après détection."""

    result = _build_success_update(
        state,
        opening,
    )

    assert result["status"] == state.status

    assert (
        result["current_step"]
        == WorkflowStep.DETECT_THEORY
    )

    assert result["opening"] == opening

    assert (
        WorkflowStep.DETECT_THEORY
        in result["completed_steps"]
    )

    context = result[
        "workflow_context"
    ]

    assert context.opening_summary is not None
    assert context.opening_context is not None


def test_build_warning_update(
    state: ChessAnalysisState,
) -> None:
    """Vérifie une mise à jour contenant un avertissement."""

    warning = WorkflowWarning(
        step=WorkflowStep.DETECT_THEORY,
        code=ERROR_OPENING_NOT_FOUND,
        message="Ouverture inconnue.",
    )

    result = _build_warning_update(
        state,
        warning,
    )

    assert result["status"] == state.status
    assert result["opening"] is None

    assert (
        WorkflowStep.DETECT_THEORY
        in result["completed_steps"]
    )

    assert result["warnings"] == [
        warning,
    ]

    context = result[
        "workflow_context"
    ]

    assert context.opening_summary is None
    assert context.opening_context is None


def test_build_warning_update_can_override_status(
    state: ChessAnalysisState,
) -> None:
    """Vérifie la surcharge explicite du statut."""

    warning = WorkflowWarning(
        step=WorkflowStep.DETECT_THEORY,
        code=ERROR_LICHESS_UNAVAILABLE,
        message="Lichess indisponible.",
    )

    result = _build_warning_update(
        state,
        warning,
        status=AnalysisStatus.PARTIAL_SUCCESS,
    )

    assert (
        result["status"]
        == AnalysisStatus.PARTIAL_SUCCESS
    )


def test_build_error_update(
    state: ChessAnalysisState,
) -> None:
    """Vérifie une mise à jour d'échec."""

    error = WorkflowError(
        step=WorkflowStep.DETECT_THEORY,
        code=ERROR_UNEXPECTED,
        message="Erreur.",
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
        == WorkflowStep.DETECT_THEORY
    )

    assert result["opening"] is None
    assert result["errors"] == [error]

    assert (
        WorkflowStep.DETECT_THEORY
        not in result["completed_steps"]
    )

    context = result[
        "workflow_context"
    ]

    assert context.opening_summary is None
    assert context.opening_context is None


def test_build_missing_service_update(
    state: ChessAnalysisState,
) -> None:
    """Vérifie l'erreur de configuration du service."""

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


def test_build_unexpected_error_update(
    state: ChessAnalysisState,
) -> None:
    """Vérifie la construction de l'erreur inattendue."""

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


# API publique

@pytest.mark.asyncio
async def test_detect_theory_success(
    state: ChessAnalysisState,
    opening: OpeningDetails,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Vérifie la détection réussie d'une ouverture."""

    detect_opening = AsyncMock(
        return_value=opening,
    )

    service = MagicMock(
        spec=LichessService,
    )

    service.detect_opening = detect_opening

    get_service = MagicMock(
        return_value=service,
    )

    emit_progress = MagicMock()

    monkeypatch.setattr(
        "app.agent.nodes.B_detect_theory."
        "_get_lichess_service",
        get_service,
    )

    monkeypatch.setattr(
        "app.agent.nodes.B_detect_theory."
        "emit_progress",
        emit_progress,
    )

    result = await detect_theory(
        state,
        cast(
            RunnableConfig,
            {},
        ),
    )

    assert result["opening"] == opening
    assert result["status"] == state.status

    assert (
        WorkflowStep.DETECT_THEORY
        in result["completed_steps"]
    )

    detect_opening.assert_awaited_once()

    request = (
        detect_opening
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
async def test_detect_theory_missing_service(
    state: ChessAnalysisState,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Vérifie l'absence du service Lichess."""

    get_service = MagicMock(
        return_value=None,
    )

    emit_progress = MagicMock()

    monkeypatch.setattr(
        "app.agent.nodes.B_detect_theory."
        "_get_lichess_service",
        get_service,
    )

    monkeypatch.setattr(
        "app.agent.nodes.B_detect_theory."
        "emit_progress",
        emit_progress,
    )

    result = await detect_theory(
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

    assert result["opening"] is None
    assert result["completed_steps"] == []

    emit_progress.assert_called_once()


@pytest.mark.asyncio
async def test_detect_theory_opening_not_found(
    state: ChessAnalysisState,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Vérifie le cas d'une ouverture inconnue."""

    detect_opening = AsyncMock(
        side_effect=OpeningNotFoundError(
            message="Ouverture inconnue.",
        ),
    )

    service = MagicMock(
        spec=LichessService,
    )

    service.detect_opening = detect_opening

    monkeypatch.setattr(
        "app.agent.nodes.B_detect_theory."
        "_get_lichess_service",
        MagicMock(
            return_value=service,
        ),
    )

    emit_progress = MagicMock()

    monkeypatch.setattr(
        "app.agent.nodes.B_detect_theory."
        "emit_progress",
        emit_progress,
    )

    result = await detect_theory(
        state,
        cast(
            RunnableConfig,
            {},
        ),
    )

    assert result["opening"] is None

    assert (
        result["warnings"][0].code
        == ERROR_OPENING_NOT_FOUND
    )

    assert (
        WorkflowStep.DETECT_THEORY
        in result["completed_steps"]
    )

    assert emit_progress.call_count == 2


@pytest.mark.asyncio
async def test_detect_theory_lichess_error(
    state: ChessAnalysisState,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Vérifie une indisponibilité de Lichess."""

    detect_opening = AsyncMock(
        side_effect=LichessError(
            message="Lichess indisponible.",
        ),
    )

    service = MagicMock(
        spec=LichessService,
    )

    service.detect_opening = detect_opening

    monkeypatch.setattr(
        "app.agent.nodes.B_detect_theory."
        "_get_lichess_service",
        MagicMock(
            return_value=service,
        ),
    )

    emit_progress = MagicMock()

    monkeypatch.setattr(
        "app.agent.nodes.B_detect_theory."
        "emit_progress",
        emit_progress,
    )

    result = await detect_theory(
        state,
        cast(
            RunnableConfig,
            {},
        ),
    )

    assert (
        result["status"]
        == AnalysisStatus.PARTIAL_SUCCESS
    )

    assert result["opening"] is None

    assert (
        result["warnings"][0].code
        == ERROR_LICHESS_UNAVAILABLE
    )

    assert (
        WorkflowStep.DETECT_THEORY
        in result["completed_steps"]
    )

    assert emit_progress.call_count == 2


@pytest.mark.asyncio
async def test_detect_theory_lichess_error_preserves_failed_status(
    state: ChessAnalysisState,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Vérifie qu'un workflow déjà échoué reste en échec."""

    failed_state = state.model_copy(
        update={
            "status": AnalysisStatus.FAILED,
        }
    )

    detect_opening = AsyncMock(
        side_effect=LichessError(
            message="Lichess indisponible.",
        ),
    )

    service = MagicMock(
        spec=LichessService,
    )

    service.detect_opening = detect_opening

    monkeypatch.setattr(
        "app.agent.nodes.B_detect_theory."
        "_get_lichess_service",
        MagicMock(
            return_value=service,
        ),
    )

    monkeypatch.setattr(
        "app.agent.nodes.B_detect_theory."
        "emit_progress",
        MagicMock(),
    )

    result = await detect_theory(
        failed_state,
        cast(
            RunnableConfig,
            {},
        ),
    )

    assert (
        result["status"]
        == AnalysisStatus.FAILED
    )


@pytest.mark.asyncio
async def test_detect_theory_unexpected_error(
    state: ChessAnalysisState,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Vérifie une erreur inattendue."""

    detect_opening = AsyncMock(
        side_effect=RuntimeError(
            "Unexpected failure"
        ),
    )

    service = MagicMock(
        spec=LichessService,
    )

    service.detect_opening = detect_opening

    monkeypatch.setattr(
        "app.agent.nodes.B_detect_theory."
        "_get_lichess_service",
        MagicMock(
            return_value=service,
        ),
    )

    emit_progress = MagicMock()

    monkeypatch.setattr(
        "app.agent.nodes.B_detect_theory."
        "emit_progress",
        emit_progress,
    )

    result = await detect_theory(
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

    assert result["opening"] is None

    assert (
        WorkflowStep.DETECT_THEORY
        not in result["completed_steps"]
    )

    assert emit_progress.call_count == 2