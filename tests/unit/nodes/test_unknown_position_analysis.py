"""Tests unitaires du nœud d'analyse pédagogique d'une position inconnue."""

from __future__ import annotations

from typing import cast

import chess
import pytest
from langchain_core.runnables import RunnableConfig

from app.agent.nodes.D_unknown_position_analysis import (
    _append_alternatives,
    _append_best_move,
    _append_evaluation,
    _append_principal_variation,
    _append_summary,
    _build_success_update,
    _build_unknown_position_context,
    _build_workflow_context,
    _format_moves,
    _format_score,
    _get_success_status,
    unknown_position_analysis,
)
from app.agent.state import ChessAnalysisState
from app.schemas.analysis.evaluation import (
    EngineAnalysis,
    Evaluation,
    PositionEvaluation,
    PrincipalVariation,
)
from app.schemas.chess.move import BestMove
from app.schemas.common.enums import (
    AnalysisStatus,
    EvaluationType,
    WorkflowStep,
)


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
    principal_variation: list[str] | None = None,
) -> BestMove:
    """Construit un coup évalué par Stockfish."""

    return BestMove(
        uci=uci,
        san=san,
        from_square=uci[:2],
        to_square=uci[2:4],
        score=score,
        evaluation_type=evaluation_type,
        depth=depth,
        principal_variation=(
            principal_variation
            if principal_variation is not None
            else [
                uci,
            ]
        ),
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
    principal_moves: list[str] | None = None,
    principal_explanation: str | None = (
        "Développement central."
    ),
    alternatives: list[BestMove] | None = None,
    summary: str | None = (
        "Stockfish préfère e4."
    ),
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
            principal_moves
            if principal_moves is not None
            else [
                "e2e4",
                "e7e5",
                "g1f3",
            ]
        ),
        evaluation=engine_evaluation,
        explanation=principal_explanation,
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
                    principal_variation=[
                        "d2d4",
                        "d7d5",
                    ],
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
    """Construit un état minimal sans ouverture."""

    return ChessAnalysisState(
        fen=STARTING_FEN,
    )


@pytest.fixture
def evaluation() -> PositionEvaluation:
    """Construit une évaluation Stockfish complète."""

    return build_evaluation()


# Statuts

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
    """Vérifie le statut après une préparation réussie."""

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


# Formatage des scores

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


# Formatage des coups

def test_format_moves_returns_normalized_moves() -> None:
    """Vérifie la normalisation d'une suite de coups."""

    result = _format_moves(
        [
            " e2e4 ",
            "",
            "   ",
            "e7e5",
            " g1f3 ",
        ]
    )

    assert result == "e2e4 e7e5 g1f3"


def test_format_moves_returns_none_for_empty_values() -> None:
    """Vérifie l'absence de coups exploitables."""

    assert (
        _format_moves(
            [
                "",
                "   ",
            ]
        )
        is None
    )


def test_format_moves_returns_none_for_empty_list() -> None:
    """Vérifie une liste vide."""

    assert (
        _format_moves([])
        is None
    )


# Meilleur coup

def test_append_best_move(
    evaluation: PositionEvaluation,
) -> None:
    """Vérifie l'ajout du meilleur coup."""

    sections: list[str] = []

    _append_best_move(
        sections,
        evaluation,
    )

    assert len(sections) == 1

    assert (
        "Meilleur coup calculé par Stockfish"
        in sections[0]
    )

    assert "- SAN : e4" in sections[0]
    assert "- UCI : e2e4" in sections[0]
    assert "- Score : 30 centipions" in sections[0]
    assert "- Profondeur : 15" in sections[0]


def test_append_best_move_without_best_move() -> None:
    """Vérifie le cas d'un meilleur coup absent."""

    evaluation = build_evaluation()

    engine = evaluation.engine.model_copy(
        update={
            "best_move": None,
        }
    )

    evaluation = evaluation.model_copy(
        update={
            "engine": engine,
        }
    )

    sections: list[str] = []

    _append_best_move(
        sections,
        evaluation,
    )

    assert sections == [
        (
            "Meilleur coup calculé par Stockfish :\n"
            "- Non disponible."
        )
    ]


def test_append_best_move_formats_mate() -> None:
    """Vérifie un meilleur coup avec score de mat."""

    evaluation = build_evaluation(
        score=3.0,
        evaluation_type=EvaluationType.MATE,
    )

    sections: list[str] = []

    _append_best_move(
        sections,
        evaluation,
    )

    assert "mat en 3" in sections[0]


# Évaluation moteur

def test_append_evaluation(
    evaluation: PositionEvaluation,
) -> None:
    """Vérifie l'ajout de l'évaluation globale."""

    sections: list[str] = []

    _append_evaluation(
        sections,
        evaluation,
    )

    assert len(sections) == 1
    assert "Évaluation moteur" in sections[0]
    assert "- Score : 30 centipions" in sections[0]
    assert "- Profondeur : 15" in sections[0]
    assert "- Nœuds analysés : 1000" in sections[0]
    assert "- Temps d'analyse : 250 ms" in sections[0]


def test_append_evaluation_without_optional_metrics() -> None:
    """Vérifie l'évaluation sans nœuds ni durée."""

    evaluation = build_evaluation(
        nodes=None,
        time_ms=None,
    )

    sections: list[str] = []

    _append_evaluation(
        sections,
        evaluation,
    )

    assert "- Score : 30 centipions" in sections[0]
    assert "- Profondeur : 15" in sections[0]

    assert (
        "Nœuds analysés"
        not in sections[0]
    )

    assert (
        "Temps d'analyse"
        not in sections[0]
    )


def test_append_evaluation_without_engine_evaluation() -> None:
    """Vérifie le repli lorsqu'aucune évaluation globale n'est disponible."""

    evaluation = build_evaluation()

    engine = evaluation.engine.model_copy(
        update={
            "evaluation": None,
        }
    )

    evaluation = evaluation.model_copy(
        update={
            "engine": engine,
        }
    )

    sections: list[str] = []

    _append_evaluation(
        sections,
        evaluation,
    )

    assert sections == [
        "Évaluation moteur :\n- Non disponible."
    ]


# Variante principale

def test_append_principal_variation(
    evaluation: PositionEvaluation,
) -> None:
    """Vérifie l'ajout de la variante principale."""

    sections: list[str] = []

    _append_principal_variation(
        sections,
        evaluation,
    )

    assert len(sections) == 1
    assert "Variante principale" in sections[0]
    assert "- Coups : e2e4 e7e5 g1f3" in sections[0]
    assert "- Score : 30 centipions" in sections[0]
    assert "- Profondeur : 15" in sections[0]

    assert (
        "- Description : Développement central."
        in sections[0]
    )


def test_append_principal_variation_without_moves() -> None:
    """Vérifie l'absence de variante principale exploitable."""

    evaluation = build_evaluation(
        principal_moves=[],
    )

    sections: list[str] = []

    _append_principal_variation(
        sections,
        evaluation,
    )

    assert sections == []


def test_append_principal_variation_without_explanation() -> None:
    """Vérifie une variante sans description."""

    evaluation = build_evaluation(
        principal_explanation=None,
    )

    sections: list[str] = []

    _append_principal_variation(
        sections,
        evaluation,
    )

    assert len(sections) == 1

    assert (
        "Description"
        not in sections[0]
    )


# Alternatives

def test_append_alternatives(
    evaluation: PositionEvaluation,
) -> None:
    """Vérifie l'ajout des alternatives."""

    sections: list[str] = []

    _append_alternatives(
        sections,
        evaluation,
    )

    assert len(sections) == 1

    assert (
        "Alternatives calculées"
        in sections[0]
    )

    assert (
        "- d4 (d2d4)"
        in sections[0]
    )

    assert (
        "Score : 20 centipions"
        in sections[0]
    )

    assert (
        "Profondeur : 15"
        in sections[0]
    )

    assert (
        "Variante : d2d4 d7d5"
        in sections[0]
    )


def test_append_alternatives_without_alternatives() -> None:
    """Vérifie l'absence d'alternatives."""

    evaluation = build_evaluation(
        alternatives=[],
    )

    sections: list[str] = []

    _append_alternatives(
        sections,
        evaluation,
    )

    assert sections == []


def test_append_alternatives_without_principal_variation() -> None:
    """Vérifie une alternative sans variante associée."""

    alternative = build_best_move(
        uci="d2d4",
        san="d4",
        score=20.0,
        principal_variation=[],
    )

    evaluation = build_evaluation(
        alternatives=[
            alternative,
        ]
    )

    sections: list[str] = []

    _append_alternatives(
        sections,
        evaluation,
    )

    assert len(sections) == 1

    assert (
        "Variante :"
        not in sections[0]
    )


def test_append_alternatives_formats_mate() -> None:
    """Vérifie une alternative avec score de mat."""

    alternative = build_best_move(
        uci="d2d4",
        san="d4",
        score=4.0,
        evaluation_type=EvaluationType.MATE,
    )

    evaluation = build_evaluation(
        alternatives=[
            alternative,
        ]
    )

    sections: list[str] = []

    _append_alternatives(
        sections,
        evaluation,
    )

    assert "mat en 4" in sections[0]


# Synthèse

def test_append_summary(
    evaluation: PositionEvaluation,
) -> None:
    """Vérifie l'ajout de la synthèse moteur."""

    sections: list[str] = []

    _append_summary(
        sections,
        evaluation,
    )

    assert sections == [
        (
            "Synthèse moteur :\n"
            "Stockfish préfère e4."
        )
    ]


def test_append_summary_without_summary() -> None:
    """Vérifie l'absence de synthèse."""

    evaluation = build_evaluation(
        summary=None,
    )

    sections: list[str] = []

    _append_summary(
        sections,
        evaluation,
    )

    assert sections == []


# Contexte complet

def test_build_unknown_position_context(
    evaluation: PositionEvaluation,
) -> None:
    """Vérifie la construction du contexte pédagogique complet."""

    result = _build_unknown_position_context(
        evaluation
    )

    assert (
        "La position ne correspond à aucune ouverture "
        "connue retournée par Lichess."
        in result
    )

    assert (
        "Meilleur coup calculé par Stockfish"
        in result
    )

    assert "Évaluation moteur" in result
    assert "Variante principale" in result
    assert "Alternatives calculées" in result
    assert "Synthèse moteur" in result


# Contexte du workflow

def test_build_workflow_context(
    state: ChessAnalysisState,
) -> None:
    """Vérifie l'ajout du contexte de position inconnue."""

    context = _build_workflow_context(
        state,
        "Contexte inconnu.",
    )

    assert (
        context.unknown_position_context
        == "Contexte inconnu."
    )

    assert (
        state
        .workflow_context
        .unknown_position_context
        is None
    )


# Mise à jour réussie

def test_build_success_update(
    state: ChessAnalysisState,
) -> None:
    """Vérifie la mise à jour après préparation."""

    result = _build_success_update(
        state,
        "Contexte inconnu.",
    )

    assert (
        result["status"]
        == AnalysisStatus.SUCCESS
    )

    assert (
        result["current_step"]
        == WorkflowStep.UNKNOWN_POSITION_ANALYSIS
    )

    assert (
        WorkflowStep.UNKNOWN_POSITION_ANALYSIS
        in result["completed_steps"]
    )

    assert (
        result[
            "workflow_context"
        ].unknown_position_context
        == "Contexte inconnu."
    )

    assert result["errors"] == []
    assert result["warnings"] == []


def test_build_success_update_preserves_partial_success(
    state: ChessAnalysisState,
) -> None:
    """Vérifie la conservation d'un statut dégradé."""

    partial_state = state.model_copy(
        update={
            "status": AnalysisStatus.PARTIAL_SUCCESS,
        }
    )

    result = _build_success_update(
        partial_state,
        "Contexte.",
    )

    assert (
        result["status"]
        == AnalysisStatus.PARTIAL_SUCCESS
    )


def test_build_success_update_preserves_failed_status(
    state: ChessAnalysisState,
) -> None:
    """Vérifie la conservation d'un statut d'échec."""

    failed_state = state.model_copy(
        update={
            "status": AnalysisStatus.FAILED,
        }
    )

    result = _build_success_update(
        failed_state,
        "Contexte.",
    )

    assert (
        result["status"]
        == AnalysisStatus.FAILED
    )


# API publique

@pytest.mark.asyncio
async def test_unknown_position_analysis_success(
    state: ChessAnalysisState,
    evaluation: PositionEvaluation,
) -> None:
    """Vérifie le chemin nominal du nœud."""

    current_state = state.model_copy(
        update={
            "evaluation": evaluation,
            "opening": None,
        }
    )

    result = await unknown_position_analysis(
        current_state,
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
        == WorkflowStep.UNKNOWN_POSITION_ANALYSIS
    )

    assert (
        WorkflowStep.UNKNOWN_POSITION_ANALYSIS
        in result["completed_steps"]
    )

    context = result[
        "workflow_context"
    ]

    assert (
        context.unknown_position_context
        is not None
    )

    assert (
        "La position ne correspond à aucune ouverture "
        "connue retournée par Lichess."
        in context.unknown_position_context
    )


@pytest.mark.asyncio
async def test_unknown_position_analysis_rejects_known_opening(
    state: ChessAnalysisState,
) -> None:
    """Vérifie le garde-fou sur une ouverture déjà détectée."""

    current_state = state.model_copy(
        update={
            "opening": cast(
                object,
                object(),
            ),
        }
    )

    with pytest.raises(
        RuntimeError,
        match=(
            "uniquement lorsqu'aucune ouverture "
            "n'a été détectée"
        ),
    ):
        await unknown_position_analysis(
            current_state,
            cast(
                RunnableConfig,
                {},
            ),
        )


@pytest.mark.asyncio
async def test_unknown_position_analysis_requires_evaluation(
    state: ChessAnalysisState,
) -> None:
    """Vérifie le garde-fou sur l'évaluation Stockfish."""

    current_state = state.model_copy(
        update={
            "opening": None,
            "evaluation": None,
        }
    )

    with pytest.raises(
        RuntimeError,
        match=(
            "nécessite une évaluation Stockfish"
        ),
    ):
        await unknown_position_analysis(
            current_state,
            cast(
                RunnableConfig,
                {},
            ),
        )