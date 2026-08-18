"""Tests unitaires du nœud de génération de la réponse finale."""

from __future__ import annotations

from types import SimpleNamespace
from typing import cast
from unittest.mock import AsyncMock, MagicMock

import chess
import pytest
from app.adapters.llm_service import LLMService
from app.agent.nodes.G_generate_response import (
    GENERAL_RULES,
    LICHESS_RULES,
    LLM_CONFIGURATION_MESSAGE,
    LLM_GENERATION_ERROR_MESSAGE,
    LLM_SERVICE_KEY,
    RESPONSE_RULES,
    STOCKFISH_RULES,
    UNKNOWN_POSITION_RULES,
    VECTOR_CONTENT_PREFIXES,
    WIKICHESS_RULES,
    _append_alternatives,
    _append_best_move,
    _append_position_status,
    _append_prompt_section,
    _append_wikichess_matches,
    _build_document_section,
    _build_documents_context,
    _build_engine_context,
    _build_fallback_response,
    _build_fallback_update,
    _build_opening_context,
    _build_success_update,
    _build_system_prompt,
    _build_updated_workflow_context,
    _build_warning_update,
    _extract_best_move,
    _extract_document_content,
    _extract_opening_name,
    _format_percentage,
    _format_value,
    _generate_llm_response,
    _get_document_eco,
    _get_engine,
    _get_llm_service,
    _get_partial_success_status,
    _get_retrieved_document_count,
    _get_success_status,
    _get_unknown_position_context,
    _get_wikichess_continuations,
    _is_vector_metadata_line,
    _normalize_language,
    _normalize_text,
    _strip_vector_content_header,
    generate_response,
)
from app.agent.state import (
    AnalysisOptions,
    ChessAnalysisState,
)
from app.core.constants import (
    DEFAULT_RESPONSE_LANGUAGE,
    ERROR_CONFIGURATION,
    ERROR_UNEXPECTED,
)
from app.schemas.analysis.evaluation import EngineAnalysis
from app.schemas.chess.opening import (
    Opening,
    OpeningDetails,
    OpeningStatistics,
)
from app.schemas.common.enums import (
    AnalysisStatus,
    WorkflowStep,
)
from app.schemas.common.error import WorkflowWarning
from app.schemas.rag.document import (
    RetrievalContext,
    RetrievedDocument,
)
from langchain_core.runnables import RunnableConfig

# Configuration

STARTING_FEN = chess.STARTING_FEN


# Construction

def build_engine(
    *,
    best_move_san: str | None = "e4",
    best_move_uci: str = "e2e4",
    alternatives: list[object] | None = None,
) -> EngineAnalysis:
    """Construit le minimum nécessaire au nœud pour Stockfish."""

    best_move = None

    if best_move_san is not None:
        best_move = SimpleNamespace(
            san=best_move_san,
            uci=best_move_uci,
        )

    evaluation = SimpleNamespace(
        score=30.0,
        depth=15,
    )

    if alternatives is None:
        alternatives = [
            SimpleNamespace(
                san="d4",
                score=20.0,
            ),
        ]

    return EngineAnalysis.model_construct(
        best_move=best_move,
        evaluation=evaluation,
        principal_variation=None,
        alternatives=alternatives,
    )


def build_opening() -> OpeningDetails:
    """Construit une ouverture Lichess complète."""

    return OpeningDetails(
        opening=Opening(
            eco="C60",
            name="Ruy Lopez",
            moves=[
                "e4",
                "e5",
                "Nf3",
                "Nc6",
                "Bb5",
            ],
        ),
        statistics=OpeningStatistics(
            games=1000,
            white_win_rate=40.0,
            draw_rate=30.0,
            black_win_rate=30.0,
        ),
    )


def build_retrieved_document(
    *,
    title: str = "Ruy Lopez",
    eco: str | None = "C60",
    content: str = (
        "Type : article\n"
        "Ouverture : Ruy Lopez\n"
        "Titre : Ruy Lopez\n"
        "Code ECO : C60\n"
        "\n"
        "Développer les pièces et contrôler le centre."
    ),
    next_moves: tuple[object, ...] = (),
) -> RetrievedDocument:
    """Construit le document minimal réellement lu par ce nœud."""

    metadata = SimpleNamespace(
        eco=eco,
        next_moves=next_moves,
    )

    document = SimpleNamespace(
        title=title,
        content=content,
        metadata=metadata,
    )

    return cast(
        RetrievedDocument,
        SimpleNamespace(
            document=document,
            similarity=0.9,
            chunk=None,
            excerpt=None,
        ),
    )


def build_retrieval_context(
    *,
    documents: list[RetrievedDocument] | None = None,
    total_results: int | None = None,
) -> RetrievalContext:
    """Construit le contexte RAG minimal."""

    values = (
        documents
        if documents is not None
        else [
            build_retrieved_document(),
        ]
    )

    return cast(
        RetrievalContext,
        SimpleNamespace(
            query="Ruy Lopez",
            documents=values,
            total_results=(
                len(values)
                if total_results is None
                else total_results
            ),
        ),
    )


# Fixtures

@pytest.fixture
def state() -> ChessAnalysisState:
    """Construit un état minimal."""

    return ChessAnalysisState(
        fen=STARTING_FEN,
    )


@pytest.fixture
def complete_state(
    state: ChessAnalysisState,
) -> ChessAnalysisState:
    """Construit un état contenant les informations principales."""

    return state.model_copy(
        update={
            "opening": build_opening(),
            "engine_analysis": build_engine(),
            "retrieval_context": (
                build_retrieval_context()
            ),
        }
    )


# Service

def test_get_llm_service_returns_service(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Vérifie la récupération du LLMService."""

    service = MagicMock(
        spec=LLMService,
    )

    configured_service = MagicMock(
        return_value=service,
    )

    monkeypatch.setattr(
        "app.agent.nodes.G_generate_response."
        "get_configured_service",
        configured_service,
    )

    config = cast(
        RunnableConfig,
        {},
    )

    result = _get_llm_service(
        config
    )

    assert result is service

    configured_service.assert_called_once_with(
        config,
        LLM_SERVICE_KEY,
        expected_type=LLMService,
    )


def test_get_llm_service_returns_none_when_missing(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Vérifie l'absence du LLMService."""

    monkeypatch.setattr(
        "app.agent.nodes.G_generate_response."
        "get_configured_service",
        MagicMock(
            return_value=None,
        ),
    )

    assert (
        _get_llm_service(
            cast(
                RunnableConfig,
                {},
            )
        )
        is None
    )


def test_get_llm_service_rejects_invalid_type(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Vérifie le rejet d'un service incorrect."""

    monkeypatch.setattr(
        "app.agent.nodes.G_generate_response."
        "get_configured_service",
        MagicMock(
            return_value=object(),
        ),
    )

    assert (
        _get_llm_service(
            cast(
                RunnableConfig,
                {},
            )
        )
        is None
    )


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
    """Vérifie le statut après génération."""

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
    """Vérifie le statut dégradé."""

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
            "  texte  ",
            "texte",
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
            None,
            None,
        ),
        (
            42,
            None,
        ),
    ],
)
def test_normalize_text(
    value: object,
    expected: str | None,
) -> None:
    """Vérifie la normalisation textuelle."""

    assert (
        _normalize_text(value)
        == expected
    )


@pytest.mark.parametrize(
    ("value", "expected"),
    [
        (
            " FR ",
            "fr",
        ),
        (
            "EN",
            "en",
        ),
        (
            None,
            DEFAULT_RESPONSE_LANGUAGE,
        ),
        (
            "   ",
            DEFAULT_RESPONSE_LANGUAGE,
        ),
    ],
)
def test_normalize_language(
    value: str | None,
    expected: str,
) -> None:
    """Vérifie la langue de réponse."""

    assert (
        _normalize_language(value)
        == expected
    )


@pytest.mark.parametrize(
    ("value", "expected"),
    [
        (
            None,
            "non disponible",
        ),
        (
            None,
            "absent",
        ),
        (
            True,
            "oui",
        ),
        (
            False,
            "non",
        ),
        (
            42,
            "42",
        ),
        (
            "texte",
            "texte",
        ),
    ],
)
def test_format_value(
    value: object,
    expected: str,
) -> None:
    """Vérifie le formatage générique."""

    default = (
        "absent"
        if value is None
        and expected == "absent"
        else "non disponible"
    )

    assert (
        _format_value(
            value,
            default=default,
        )
        == expected
    )


@pytest.mark.parametrize(
    ("value", "expected"),
    [
        (
            None,
            "non disponible",
        ),
        (
            40,
            "40.0 %",
        ),
        (
            33.333,
            "33.3 %",
        ),
    ],
)
def test_format_percentage(
    value: float | int | None,
    expected: str,
) -> None:
    """Vérifie le format des statistiques."""

    assert (
        _format_percentage(value)
        == expected
    )


# Préambule vectoriel

@pytest.mark.parametrize(
    "prefix",
    VECTOR_CONTENT_PREFIXES,
)
def test_is_vector_metadata_line(
    prefix: str,
) -> None:
    """Vérifie les préfixes techniques."""

    assert (
        _is_vector_metadata_line(
            f"{prefix} valeur"
        )
        is True
    )


def test_is_vector_metadata_line_returns_false() -> None:
    """Vérifie une ligne pédagogique."""

    assert (
        _is_vector_metadata_line(
            "Contrôler le centre."
        )
        is False
    )


def test_strip_vector_content_header() -> None:
    """Vérifie la suppression du préambule vectoriel."""

    content = (
        "Type : article\n"
        "Ouverture : Ruy Lopez\n"
        "Titre : Ruy Lopez\n"
        "Code ECO : C60\n"
        "\n"
        "Développer les pièces."
    )

    assert (
        _strip_vector_content_header(
            content
        )
        == "Développer les pièces."
    )


def test_strip_vector_content_header_without_header() -> None:
    """Vérifie un texte pédagogique direct."""

    assert (
        _strip_vector_content_header(
            "  Développer les pièces.  "
        )
        == "Développer les pièces."
    )


def test_strip_vector_content_header_returns_none_without_body() -> None:
    """Vérifie un préambule sans présentation."""

    content = (
        "Type : article\n"
        "Ouverture : Ruy Lopez\n"
        "Code ECO : C60"
    )

    assert (
        _strip_vector_content_header(
            content
        )
        is None
    )


def test_strip_vector_content_header_empty_string() -> None:
    """Vérifie un contenu vide."""

    assert (
        _strip_vector_content_header("")
        is None
    )


# Documents

def test_extract_document_content() -> None:
    """Vérifie l'extraction pédagogique."""

    document = build_retrieved_document()

    result = _extract_document_content(
        document
    )

    assert result == (
        "Développer les pièces "
        "et contrôler le centre."
    )


def test_extract_document_content_returns_none() -> None:
    """Vérifie un document sans contenu."""

    document = build_retrieved_document(
        content="   ",
    )

    assert (
        _extract_document_content(
            document
        )
        is None
    )


def test_get_document_eco() -> None:
    """Vérifie la récupération du code ECO."""

    assert (
        _get_document_eco(
            build_retrieved_document()
        )
        == "C60"
    )


def test_get_document_eco_returns_none() -> None:
    """Vérifie l'absence de code ECO."""

    assert (
        _get_document_eco(
            build_retrieved_document(
                eco=None,
            )
        )
        is None
    )


def test_build_document_section() -> None:
    """Vérifie le contexte Wikichess."""

    section = _build_document_section(
        build_retrieved_document()
    )

    assert "Titre : Ruy Lopez" in section
    assert "Code ECO : C60" in section

    assert (
        "Présentation pédagogique :"
        in section
    )

    assert (
        "Développer les pièces "
        "et contrôler le centre."
        in section
    )


def test_build_document_section_without_content() -> None:
    """Vérifie le repli sans présentation."""

    section = _build_document_section(
        build_retrieved_document(
            content="",
        )
    )

    assert (
        "Aucune présentation pédagogique "
        "disponible."
        in section
    )


def test_build_documents_context_without_context(
    state: ChessAnalysisState,
) -> None:
    """Vérifie l'absence de RAG."""

    assert (
        _build_documents_context(
            state
        )
        is None
    )


def test_build_documents_context_without_documents(
    state: ChessAnalysisState,
) -> None:
    """Vérifie un RAG sans résultat."""

    current_state = state.model_copy(
        update={
            "retrieval_context": (
                build_retrieval_context(
                    documents=[],
                    total_results=0,
                )
            ),
        }
    )

    assert (
        _build_documents_context(
            current_state
        )
        == (
            "Aucune présentation pédagogique "
            "Wikichess n'a été trouvée."
        )
    )


def test_build_documents_context_with_document(
    state: ChessAnalysisState,
) -> None:
    """Vérifie un contexte Wikichess disponible."""

    current_state = state.model_copy(
        update={
            "retrieval_context": (
                build_retrieval_context()
            ),
        }
    )

    result = _build_documents_context(
        current_state
    )

    assert result is not None
    assert "Titre : Ruy Lopez" in result
    assert "Code ECO : C60" in result


# Continuations Wikichess

def test_get_wikichess_continuations_without_context(
    state: ChessAnalysisState,
) -> None:
    """Vérifie l'absence de continuations."""

    assert (
        _get_wikichess_continuations(
            state
        )
        == frozenset()
    )


def test_get_wikichess_continuations(
    state: ChessAnalysisState,
) -> None:
    """Vérifie l'extraction des continuations."""

    next_moves = (
        SimpleNamespace(
            move="e4",
        ),
        SimpleNamespace(
            move="d4",
        ),
        SimpleNamespace(
            move=" ",
        ),
    )

    document = build_retrieved_document(
        next_moves=next_moves,
    )

    current_state = state.model_copy(
        update={
            "retrieval_context": (
                build_retrieval_context(
                    documents=[
                        document,
                    ]
                )
            ),
        }
    )

    assert (
        _get_wikichess_continuations(
            current_state
        )
        == frozenset(
            {
                "e4",
                "d4",
            }
        )
    )


def test_get_wikichess_continuations_ignores_string(
    state: ChessAnalysisState,
) -> None:
    """Vérifie qu'une chaîne n'est pas traitée comme une séquence."""

    metadata = SimpleNamespace(
        eco="C60",
        next_moves="e4",
    )

    raw_document = SimpleNamespace(
        title="Ruy Lopez",
        content="Présentation pédagogique.",
        metadata=metadata,
    )

    retrieved_document = cast(
        RetrievedDocument,
        SimpleNamespace(
            document=raw_document,
            similarity=0.9,
            chunk=None,
            excerpt=None,
        ),
    )

    retrieval_context = cast(
        RetrievalContext,
        SimpleNamespace(
            query="Ruy Lopez",
            documents=[
                retrieved_document,
            ],
            total_results=1,
        ),
    )

    current_state = state.model_copy(
        update={
            "retrieval_context": retrieval_context,
        }
    )

    assert (
        _get_wikichess_continuations(
            current_state
        )
        == frozenset()
    )


# Lichess

def test_build_opening_context_without_opening(
    state: ChessAnalysisState,
) -> None:
    """Vérifie l'absence d'ouverture."""

    assert (
        _build_opening_context(
            state
        )
        is None
    )


def test_build_opening_context(
    state: ChessAnalysisState,
) -> None:
    """Vérifie les statistiques Lichess."""

    current_state = state.model_copy(
        update={
            "opening": build_opening(),
        }
    )

    result = _build_opening_context(
        current_state
    )

    assert result is not None
    assert "Parties : 1000" in result

    assert (
        "Victoires blanches : 40.0 %"
        in result
    )

    assert (
        "Parties nulles : 30.0 %"
        in result
    )

    assert (
        "Victoires noires : 30.0 %"
        in result
    )


# Stockfish

def test_get_engine_from_evaluation(
    state: ChessAnalysisState,
) -> None:
    """Vérifie la priorité de PositionEvaluation."""

    engine = build_engine()

    evaluation = SimpleNamespace(
        engine=engine,
    )

    current_state = state.model_copy(
        update={
            "evaluation": evaluation,
            "engine_analysis": None,
        }
    )

    assert (
        _get_engine(
            current_state
        )
        is engine
    )


def test_get_engine_from_engine_analysis(
    state: ChessAnalysisState,
) -> None:
    """Vérifie le repli sur engine_analysis."""

    engine = build_engine()

    current_state = state.model_copy(
        update={
            "engine_analysis": engine,
        }
    )

    assert (
        _get_engine(
            current_state
        )
        is engine
    )


def test_get_engine_returns_none(
    state: ChessAnalysisState,
) -> None:
    """Vérifie l'absence d'analyse Stockfish."""

    assert (
        _get_engine(state)
        is None
    )


def test_get_engine_rejects_invalid_value(
    state: ChessAnalysisState,
) -> None:
    """Vérifie le rejet d'un mauvais type."""

    current_state = state.model_copy(
        update={
            "engine_analysis": object(),
        }
    )

    assert (
        _get_engine(
            current_state
        )
        is None
    )


def test_append_best_move() -> None:
    """Vérifie les informations Stockfish principales."""

    lines: list[str] = []

    _append_best_move(
        lines,
        build_engine(),
    )

    assert "Meilleur coup : e4" in lines
    assert "Score : 30.0" in lines
    assert "Profondeur : 15" in lines


def test_append_alternatives() -> None:
    """Vérifie les alternatives Stockfish."""

    lines: list[str] = []

    _append_alternatives(
        lines,
        build_engine(),
    )

    assert "Alternatives :" in lines
    assert "- d4 : 20.0" in lines


def test_append_alternatives_without_values() -> None:
    """Vérifie l'absence d'alternatives."""

    lines: list[str] = []

    _append_alternatives(
        lines,
        build_engine(
            alternatives=[],
        ),
    )

    assert lines == []


def test_append_wikichess_matches(
    state: ChessAnalysisState,
) -> None:
    """Vérifie la comparaison factuelle des coups."""

    document = build_retrieved_document(
        next_moves=(
            SimpleNamespace(
                move="e4",
            ),
        ),
    )

    current_state = state.model_copy(
        update={
            "retrieval_context": (
                build_retrieval_context(
                    documents=[
                        document,
                    ]
                )
            ),
        }
    )

    lines: list[str] = []

    _append_wikichess_matches(
        lines,
        current_state,
        build_engine(),
    )

    assert (
        "Correspondances Wikichess :"
        in lines
    )

    assert "- e4 : oui" in lines
    assert "- d4 : non" in lines


def test_build_engine_context(
    state: ChessAnalysisState,
) -> None:
    """Vérifie le contexte moteur."""

    current_state = state.model_copy(
        update={
            "opening": build_opening(),
            "engine_analysis": build_engine(),
        }
    )

    result = _build_engine_context(
        current_state
    )

    assert result is not None
    assert "Meilleur coup : e4" in result
    assert "Score : 30.0" in result
    assert "Alternatives :" in result


def test_build_engine_context_ignored_for_unknown_position(
    state: ChessAnalysisState,
) -> None:
    """Vérifie que le contexte inconnu remplace le contexte moteur."""

    workflow_context = (
        state.workflow_context.model_copy(
            update={
                "unknown_position_context": (
                    "Contexte position inconnue."
                ),
            }
        )
    )

    current_state = state.model_copy(
        update={
            "opening": None,
            "engine_analysis": build_engine(),
            "workflow_context": workflow_context,
        }
    )

    assert (
        _build_engine_context(
            current_state
        )
        is None
    )


# Position inconnue

def test_get_unknown_position_context_returns_none_with_opening(
    state: ChessAnalysisState,
) -> None:
    """Vérifie qu'une ouverture connue désactive ce contexte."""

    workflow_context = (
        state.workflow_context.model_copy(
            update={
                "unknown_position_context": (
                    "Contexte inconnu."
                ),
            }
        )
    )

    current_state = state.model_copy(
        update={
            "opening": build_opening(),
            "workflow_context": workflow_context,
        }
    )

    assert (
        _get_unknown_position_context(
            current_state
        )
        is None
    )


def test_get_unknown_position_context(
    state: ChessAnalysisState,
) -> None:
    """Vérifie le contexte de position inconnue."""

    workflow_context = (
        state.workflow_context.model_copy(
            update={
                "unknown_position_context": (
                    "  Contexte inconnu.  "
                ),
            }
        )
    )

    current_state = state.model_copy(
        update={
            "workflow_context": workflow_context,
        }
    )

    assert (
        _get_unknown_position_context(
            current_state
        )
        == "Contexte inconnu."
    )


# Prompt

def test_append_prompt_section() -> None:
    """Vérifie l'ajout d'une section."""

    sections: list[str] = []

    _append_prompt_section(
        sections,
        "Test",
        "Contenu",
        "Règles",
    )

    assert sections == [
        (
            "# Test\n\n"
            "Contenu\n\n"
            "Règles"
        )
    ]


def test_append_prompt_section_skips_empty_content() -> None:
    """Vérifie qu'une section vide est ignorée."""

    sections: list[str] = []

    _append_prompt_section(
        sections,
        "Test",
        None,
    )

    assert sections == []


def test_build_system_prompt(
    complete_state: ChessAnalysisState,
) -> None:
    """Vérifie le prompt complet transmis au modèle."""

    prompt = _build_system_prompt(
        complete_state
    )

    assert GENERAL_RULES in prompt
    assert "# Wikichess" in prompt
    assert WIKICHESS_RULES in prompt
    assert "# Lichess" in prompt
    assert LICHESS_RULES in prompt
    assert "# Stockfish" in prompt
    assert STOCKFISH_RULES in prompt

    assert (
        RESPONSE_RULES.format(
            language="fr"
        )
        in prompt
    )


def test_build_system_prompt_unknown_position(
    state: ChessAnalysisState,
) -> None:
    """Vérifie le prompt pour une position inconnue."""

    workflow_context = (
        state.workflow_context.model_copy(
            update={
                "unknown_position_context": (
                    "Contexte Stockfish préparé."
                ),
            }
        )
    )

    current_state = state.model_copy(
        update={
            "workflow_context": workflow_context,
        }
    )

    prompt = _build_system_prompt(
        current_state
    )

    assert "# Position inconnue" in prompt

    assert (
        UNKNOWN_POSITION_RULES
        in prompt
    )

    assert (
        "Contexte Stockfish préparé."
        in prompt
    )


def test_build_system_prompt_uses_requested_language(
    state: ChessAnalysisState,
) -> None:
    """Vérifie la langue configurée."""

    options = AnalysisOptions(
        response_language="EN",
    )

    current_state = state.model_copy(
        update={
            "options": options,
        }
    )

    prompt = _build_system_prompt(
        current_state
    )

    assert (
        RESPONSE_RULES.format(
            language="en"
        )
        in prompt
    )


# Extraction

def test_extract_opening_name(
    state: ChessAnalysisState,
) -> None:
    """Vérifie le nom de l'ouverture."""

    current_state = state.model_copy(
        update={
            "opening": build_opening(),
        }
    )

    assert (
        _extract_opening_name(
            current_state
        )
        == "Ruy Lopez"
    )


def test_extract_opening_name_returns_none(
    state: ChessAnalysisState,
) -> None:
    """Vérifie l'absence d'ouverture."""

    assert (
        _extract_opening_name(state)
        is None
    )


def test_extract_best_move(
    state: ChessAnalysisState,
) -> None:
    """Vérifie le meilleur coup Stockfish."""

    current_state = state.model_copy(
        update={
            "engine_analysis": build_engine(),
        }
    )

    assert (
        _extract_best_move(
            current_state
        )
        == "e4"
    )


def test_extract_best_move_uses_uci_fallback(
    state: ChessAnalysisState,
) -> None:
    """Vérifie le repli UCI."""

    engine = build_engine()

    engine.best_move.san = "   "

    current_state = state.model_copy(
        update={
            "engine_analysis": engine,
        }
    )

    assert (
        _extract_best_move(
            current_state
        )
        == "e2e4"
    )


def test_extract_best_move_returns_none(
    state: ChessAnalysisState,
) -> None:
    """Vérifie l'absence de moteur."""

    assert (
        _extract_best_move(state)
        is None
    )


def test_get_retrieved_document_count_without_context(
    state: ChessAnalysisState,
) -> None:
    """Vérifie l'absence de documents."""

    assert (
        _get_retrieved_document_count(
            state
        )
        == 0
    )


def test_get_retrieved_document_count(
    state: ChessAnalysisState,
) -> None:
    """Vérifie le nombre de résultats RAG."""

    current_state = state.model_copy(
        update={
            "retrieval_context": (
                build_retrieval_context(
                    total_results=3,
                )
            ),
        }
    )

    assert (
        _get_retrieved_document_count(
            current_state
        )
        == 3
    )


# Réponse de secours

def test_append_position_status_checkmate(
    state: ChessAnalysisState,
) -> None:
    """Vérifie le statut échec et mat."""

    current_state = state.model_copy(
        update={
            "position": SimpleNamespace(
                is_checkmate=True,
                is_stalemate=False,
                is_check=True,
            ),
        }
    )

    sections: list[str] = []

    _append_position_status(
        sections,
        current_state,
    )

    assert sections == [
        (
            "La position est indiquée "
            "comme un échec et mat."
        )
    ]


def test_append_position_status_stalemate(
    state: ChessAnalysisState,
) -> None:
    """Vérifie le statut de pat."""

    current_state = state.model_copy(
        update={
            "position": SimpleNamespace(
                is_checkmate=False,
                is_stalemate=True,
                is_check=False,
            ),
        }
    )

    sections: list[str] = []

    _append_position_status(
        sections,
        current_state,
    )

    assert sections == [
        "La position est indiquée comme un pat."
    ]


def test_append_position_status_check(
    state: ChessAnalysisState,
) -> None:
    """Vérifie le joueur en échec."""

    current_state = state.model_copy(
        update={
            "position": SimpleNamespace(
                is_checkmate=False,
                is_stalemate=False,
                is_check=True,
            ),
        }
    )

    sections: list[str] = []

    _append_position_status(
        sections,
        current_state,
    )

    assert sections == [
        (
            "Le joueur au trait est indiqué "
            "comme étant en échec."
        )
    ]


def test_build_fallback_response(
    state: ChessAnalysisState,
) -> None:
    """Vérifie la réponse de secours minimale."""

    response = _build_fallback_response(
        state
    )

    assert (
        "La génération de la réponse pédagogique "
        "par le modèle de langage n'est pas disponible."
        in response
    )

    assert (
        f"Position FEN analysée : {STARTING_FEN}."
        in response
    )

    assert (
        "Aucune ouverture connue n'a été détectée."
        in response
    )

    assert (
        "Les résultats détaillés restent disponibles"
        in response
    )


def test_build_fallback_response_with_all_data(
    state: ChessAnalysisState,
) -> None:
    """Vérifie une réponse de secours enrichie."""

    video = SimpleNamespace()

    current_state = state.model_copy(
        update={
            "opening": build_opening(),
            "engine_analysis": build_engine(),
            "retrieval_context": (
                build_retrieval_context(
                    total_results=2,
                )
            ),
            "videos": [
                video,
            ],
        }
    )

    response = _build_fallback_response(
        current_state
    )

    assert (
        "Ouverture détectée : Ruy Lopez."
        in response
    )

    assert (
        "Meilleur coup retourné "
        "par Stockfish : e4."
        in response
    )

    assert (
        "2 document(s) Wikichess "
        "ont été retrouvés."
        in response
    )

    assert (
        "1 vidéo(s) pédagogique(s) "
        "ont été sélectionnée(s)."
        in response
    )


# WorkflowContext

def test_build_updated_workflow_context(
    state: ChessAnalysisState,
) -> None:
    """Vérifie l'enregistrement du résumé final."""

    context = (
        _build_updated_workflow_context(
            state,
            "Réponse finale.",
        )
    )

    assert (
        context.final_summary
        == "Réponse finale."
    )

    assert (
        state.workflow_context.final_summary
        is None
    )


# Updates

def test_build_success_update(
    state: ChessAnalysisState,
) -> None:
    """Vérifie une génération réussie."""

    context = (
        _build_updated_workflow_context(
            state,
            "Réponse.",
        )
    )

    update = _build_success_update(
        state,
        "Réponse.",
        context,
    )

    assert (
        update["status"]
        == AnalysisStatus.SUCCESS
    )

    assert (
        update["current_step"]
        == WorkflowStep.GENERATE_RESPONSE
    )

    assert (
        WorkflowStep.GENERATE_RESPONSE
        in update["completed_steps"]
    )

    assert (
        update["response"]
        == "Réponse."
    )

    assert (
        update[
            "workflow_context"
        ].final_summary
        == "Réponse."
    )


def test_build_warning_update(
    state: ChessAnalysisState,
) -> None:
    """Vérifie une génération dégradée."""

    warning = WorkflowWarning(
        step=WorkflowStep.GENERATE_RESPONSE,
        code=ERROR_UNEXPECTED,
        message="LLM indisponible.",
    )

    context = (
        _build_updated_workflow_context(
            state,
            "Secours.",
        )
    )

    update = _build_warning_update(
        state,
        warning,
        "Secours.",
        context,
    )

    assert (
        update["status"]
        == AnalysisStatus.PARTIAL_SUCCESS
    )

    assert (
        WorkflowStep.GENERATE_RESPONSE
        in update["completed_steps"]
    )

    assert (
        update["response"]
        == "Secours."
    )

    assert update["warnings"] == [
        warning,
    ]


def test_build_fallback_update(
    state: ChessAnalysisState,
) -> None:
    """Vérifie la construction complète du repli."""

    update = _build_fallback_update(
        state,
        ERROR_CONFIGURATION,
        LLM_CONFIGURATION_MESSAGE,
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
        == LLM_CONFIGURATION_MESSAGE
    )

    assert update["response"]

    assert (
        update[
            "workflow_context"
        ].final_summary
        == update["response"]
    )


# Génération LLM

@pytest.mark.asyncio
async def test_generate_llm_response(
    state: ChessAnalysisState,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Vérifie la génération d'une réponse non vide."""

    generate = AsyncMock(
        return_value="  Réponse générée.  ",
    )

    service = MagicMock(
        spec=LLMService,
    )

    service.generate = generate

    build_prompt = MagicMock(
        return_value="PROMPT",
    )

    monkeypatch.setattr(
        "app.agent.nodes.G_generate_response."
        "_build_system_prompt",
        build_prompt,
    )

    response = await _generate_llm_response(
        service,
        state,
    )

    assert response == "Réponse générée."

    generate.assert_awaited_once_with(
        prompt="PROMPT",
    )


@pytest.mark.asyncio
async def test_generate_llm_response_rejects_empty_response(
    state: ChessAnalysisState,
) -> None:
    """Vérifie le rejet d'une réponse vide."""

    generate = AsyncMock(
        return_value="   ",
    )

    service = MagicMock(
        spec=LLMService,
    )

    service.generate = generate

    with pytest.raises(
        ValueError,
        match="réponse vide",
    ):
        await _generate_llm_response(
            service,
            state,
        )


# API publique

@pytest.mark.asyncio
async def test_generate_response_success(
    state: ChessAnalysisState,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Vérifie une génération LLM réussie."""

    service = MagicMock(
        spec=LLMService,
    )

    get_service = MagicMock(
        return_value=service,
    )

    generate_llm = AsyncMock(
        return_value="Réponse pédagogique.",
    )

    emit_progress = MagicMock()

    monkeypatch.setattr(
        "app.agent.nodes.G_generate_response."
        "_get_llm_service",
        get_service,
    )

    monkeypatch.setattr(
        "app.agent.nodes.G_generate_response."
        "_generate_llm_response",
        generate_llm,
    )

    monkeypatch.setattr(
        "app.agent.nodes.G_generate_response."
        "emit_progress",
        emit_progress,
    )

    update = await generate_response(
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
        update["response"]
        == "Réponse pédagogique."
    )

    assert (
        update[
            "workflow_context"
        ].final_summary
        == "Réponse pédagogique."
    )

    assert (
        WorkflowStep.GENERATE_RESPONSE
        in update["completed_steps"]
    )

    generate_llm.assert_awaited_once_with(
        service,
        state,
    )

    assert emit_progress.call_count == 2


@pytest.mark.asyncio
async def test_generate_response_missing_service(
    state: ChessAnalysisState,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Vérifie le repli lorsque LLMService manque."""

    emit_progress = MagicMock()

    monkeypatch.setattr(
        "app.agent.nodes.G_generate_response."
        "_get_llm_service",
        MagicMock(
            return_value=None,
        ),
    )

    monkeypatch.setattr(
        "app.agent.nodes.G_generate_response."
        "emit_progress",
        emit_progress,
    )

    update = await generate_response(
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

    assert (
        update["warnings"][-1].code
        == ERROR_CONFIGURATION
    )

    assert (
        update["warnings"][-1].message
        == LLM_CONFIGURATION_MESSAGE
    )

    assert update["response"]

    emit_progress.assert_called_once()


@pytest.mark.asyncio
async def test_generate_response_handles_generation_error(
    state: ChessAnalysisState,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Vérifie le repli après erreur du LLM."""

    service = MagicMock(
        spec=LLMService,
    )

    generate_llm = AsyncMock(
        side_effect=RuntimeError(
            "LLM failure"
        ),
    )

    emit_progress = MagicMock()

    monkeypatch.setattr(
        "app.agent.nodes.G_generate_response."
        "_get_llm_service",
        MagicMock(
            return_value=service,
        ),
    )

    monkeypatch.setattr(
        "app.agent.nodes.G_generate_response."
        "_generate_llm_response",
        generate_llm,
    )

    monkeypatch.setattr(
        "app.agent.nodes.G_generate_response."
        "emit_progress",
        emit_progress,
    )

    update = await generate_response(
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

    assert (
        update["warnings"][-1].code
        == ERROR_UNEXPECTED
    )

    assert (
        update["warnings"][-1].message
        == LLM_GENERATION_ERROR_MESSAGE
    )

    assert update["response"]

    assert (
        WorkflowStep.GENERATE_RESPONSE
        in update["completed_steps"]
    )

    assert emit_progress.call_count == 2


@pytest.mark.asyncio
async def test_generate_response_preserves_partial_status(
    state: ChessAnalysisState,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Vérifie qu'une dégradation antérieure est conservée."""

    partial_state = state.model_copy(
        update={
            "status": (
                AnalysisStatus.PARTIAL_SUCCESS
            ),
        }
    )

    service = MagicMock(
        spec=LLMService,
    )

    monkeypatch.setattr(
        "app.agent.nodes.G_generate_response."
        "_get_llm_service",
        MagicMock(
            return_value=service,
        ),
    )

    monkeypatch.setattr(
        "app.agent.nodes.G_generate_response."
        "_generate_llm_response",
        AsyncMock(
            return_value="Réponse.",
        ),
    )

    monkeypatch.setattr(
        "app.agent.nodes.G_generate_response."
        "emit_progress",
        MagicMock(),
    )

    update = await generate_response(
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