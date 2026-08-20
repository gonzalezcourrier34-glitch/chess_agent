"""Tests unitaires du nœud de récupération du contexte RAG."""

from __future__ import annotations

from typing import cast
from unittest.mock import AsyncMock, MagicMock

import chess
import pytest
from app.agent.nodes.E_retrieve_context import (
    CHESS_SERVICE_KEY,
    DEFAULT_DOCUMENT_SOURCE,
    EXCERPT_MAX_LENGTH,
    METADATA_ARTICLE_SLUG_KEY,
    METADATA_ARTICLE_TITLE_KEY,
    METADATA_DATASET_KEY,
    METADATA_ECO_KEY,
    METADATA_LANGUAGE_KEY,
    METADATA_MOVES_KEY,
    METADATA_MOVES_PATH_KEY,
    METADATA_NEXT_MOVES_KEY,
    METADATA_POSITION_AFTER_KEY,
    METADATA_SOURCE_KEY,
    METADATA_SOURCE_URL_KEY,
    METADATA_TYPE_KEY,
    METADATA_WIKICHESS_TITLE_KEY,
    NEXT_MOVE_KEY,
    NEXT_MOVE_SOURCE_URL_KEY,
    SELECTED_DOCUMENT_LIMIT,
    VECTOR_SEARCH_SERVICE_KEY,
    _build_documents_summary,
    _build_empty_retrieval_context,
    _build_excerpt,
    _build_next_move,
    _build_retrieval_context,
    _build_search_query,
    _build_success_update,
    _build_warning_update,
    _convert_moves_to_san,
    _format_moves_path,
    _get_chess_service,
    _get_document_type,
    _get_metadata_moves,
    _get_metadata_next_moves,
    _get_opening_identity,
    _get_partial_success_status,
    _get_result_similarity,
    _get_result_source,
    _get_state_moves,
    _get_success_status,
    _get_vector_search_service,
    _normalize_moves,
    _normalize_similarity,
    _normalize_text,
    _search_documents,
    _select_results,
    retrieve_context,
)
from app.agent.state import ChessAnalysisState
from app.core.constants import (
    ERROR_CONFIGURATION,
    ERROR_MILVUS_UNAVAILABLE,
    ERROR_UNEXPECTED,
)
from app.core.exceptions import RetrievalError
from app.schemas.analysis.search import VectorSearchResult
from app.schemas.chess.opening import (
    Opening,
    OpeningDetails,
)
from app.schemas.common.enums import (
    AnalysisStatus,
    DocumentType,
    WorkflowStep,
)
from app.schemas.common.error import WorkflowWarning
from app.services.chess_service import ChessService
from app.services.vector_search_service import VectorSearchService
from langchain_core.runnables import RunnableConfig

# Configuration

STARTING_FEN = chess.STARTING_FEN

UCI_MOVES = [
    "e2e4",
    "e7e5",
    "g1f3",
]

SAN_MOVES = (
    "e4",
    "e5",
    "Nf3",
)


# Construction


def build_opening() -> OpeningDetails:
    """Construit une ouverture minimale."""

    return OpeningDetails(
        opening=Opening(
            name="Ruy Lopez",
            eco="C60",
            moves=[
                "e4",
                "e5",
                "Nf3",
                "Nc6",
                "Bb5",
            ],
        ),
    )


def build_result(
    *,
    identifier: str = "ruy-lopez-1",
    similarity: float = 0.92,
    content: str = "Présentation pédagogique de la Ruy Lopez.",
) -> VectorSearchResult:
    """Construit un résultat vectoriel conforme au schéma actuel."""

    return VectorSearchResult(
        id=identifier,
        similarity=similarity,
        content=content,
        metadata={
            METADATA_ARTICLE_SLUG_KEY: "ruy-lopez",
            METADATA_ARTICLE_TITLE_KEY: "Ruy Lopez",
            METADATA_WIKICHESS_TITLE_KEY: ("Chess Opening Theory/1. e4/1... e5"),
            METADATA_ECO_KEY: "C60",
            METADATA_LANGUAGE_KEY: "fr",
            METADATA_MOVES_KEY: [
                "e4",
                "e5",
                "Nf3",
            ],
            METADATA_MOVES_PATH_KEY: "e4 e5 Nf3",
            METADATA_POSITION_AFTER_KEY: STARTING_FEN,
            METADATA_SOURCE_KEY: "wikichess",
            METADATA_SOURCE_URL_KEY: ("https://example.test/ruy-lopez"),
            METADATA_TYPE_KEY: DocumentType.ARTICLE.value,
            METADATA_NEXT_MOVES_KEY: [
                {
                    NEXT_MOVE_KEY: "Nc6",
                    NEXT_MOVE_SOURCE_URL_KEY: ("https://example.test/nc6"),
                },
            ],
        },
    )


# Fixtures


@pytest.fixture
def state() -> ChessAnalysisState:
    """Construit un état minimal."""

    return ChessAnalysisState(
        fen=STARTING_FEN,
    )


@pytest.fixture
def opening_state(
    state: ChessAnalysisState,
) -> ChessAnalysisState:
    """Construit un état avec une ouverture."""

    return state.model_copy(
        update={
            "opening": build_opening(),
        }
    )


@pytest.fixture
def result() -> VectorSearchResult:
    """Construit un résultat Wikichess."""

    return build_result()


# Services


def test_get_chess_service_returns_service(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Vérifie la récupération de ChessService."""

    service = ChessService()

    configured = MagicMock(
        return_value=service,
    )

    monkeypatch.setattr(
        "app.agent.nodes.E_retrieve_context.get_configured_service",
        configured,
    )

    config = cast(
        RunnableConfig,
        {},
    )

    assert _get_chess_service(config) is service

    configured.assert_called_once_with(
        config,
        CHESS_SERVICE_KEY,
        expected_type=ChessService,
    )


def test_get_chess_service_returns_none(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Vérifie l'absence de ChessService."""

    monkeypatch.setattr(
        "app.agent.nodes.E_retrieve_context.get_configured_service",
        MagicMock(return_value=None),
    )

    assert _get_chess_service(cast(RunnableConfig, {})) is None


def test_get_chess_service_rejects_invalid_type(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Vérifie un type de service invalide."""

    monkeypatch.setattr(
        "app.agent.nodes.E_retrieve_context.get_configured_service",
        MagicMock(return_value=object()),
    )

    assert _get_chess_service(cast(RunnableConfig, {})) is None


def test_get_vector_search_service_returns_service(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Vérifie la récupération du service vectoriel."""

    service = MagicMock(
        spec=VectorSearchService,
    )

    configured = MagicMock(
        return_value=service,
    )

    monkeypatch.setattr(
        "app.agent.nodes.E_retrieve_context.get_configured_service",
        configured,
    )

    config = cast(
        RunnableConfig,
        {},
    )

    assert _get_vector_search_service(config) is service

    configured.assert_called_once_with(
        config,
        VECTOR_SEARCH_SERVICE_KEY,
        expected_type=VectorSearchService,
    )


def test_get_vector_search_service_returns_none(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Vérifie l'absence du service vectoriel."""

    monkeypatch.setattr(
        "app.agent.nodes.E_retrieve_context.get_configured_service",
        MagicMock(return_value=None),
    )

    assert _get_vector_search_service(cast(RunnableConfig, {})) is None


# Statuts


@pytest.mark.parametrize(
    ("status", "expected"),
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
    status: AnalysisStatus,
    expected: AnalysisStatus,
) -> None:
    """Vérifie le statut d'une recherche réussie."""

    current_state = state.model_copy(
        update={
            "status": status,
        }
    )

    assert _get_success_status(current_state) == expected


@pytest.mark.parametrize(
    ("status", "expected"),
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
    status: AnalysisStatus,
    expected: AnalysisStatus,
) -> None:
    """Vérifie le statut d'une recherche dégradée."""

    current_state = state.model_copy(
        update={
            "status": status,
        }
    )

    assert _get_partial_success_status(current_state) == expected


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
    """Vérifie le nettoyage des chaînes."""

    assert _normalize_text(value) == expected


def test_normalize_moves() -> None:
    """Vérifie le nettoyage d'une suite de coups."""

    result = _normalize_moves(
        [
            " e4 ",
            "",
            " e5 ",
            42,
            " Nf3 ",
        ]
    )

    assert result == (
        "e4",
        "e5",
        "Nf3",
    )


@pytest.mark.parametrize(
    "value",
    [
        "e4 e5",
        b"e4",
        None,
        42,
    ],
)
def test_normalize_moves_rejects_invalid_sequence(
    value: object,
) -> None:
    """Vérifie les valeurs non séquentielles."""

    assert _normalize_moves(value) == ()


def test_get_state_moves(
    state: ChessAnalysisState,
) -> None:
    """Vérifie les coups transmis au workflow."""

    current_state = state.model_copy(
        update={
            "moves": UCI_MOVES,
        }
    )

    assert _get_state_moves(current_state) == tuple(UCI_MOVES)


def test_format_moves_path() -> None:
    """Vérifie le format du chemin de coups."""

    assert _format_moves_path(SAN_MOVES) == "e4 e5 Nf3"


# Conversion UCI vers SAN


def test_convert_moves_to_san(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Vérifie la conversion des coups."""

    service = ChessService()

    converter = MagicMock(
        return_value=[
            "e4",
            "e5",
            "Nf3",
        ],
    )

    monkeypatch.setattr(
        service,
        "convert_uci_history_to_san",
        converter,
    )

    result = _convert_moves_to_san(
        service,
        UCI_MOVES,
    )

    assert result == SAN_MOVES

    converter.assert_called_once_with(UCI_MOVES)


def test_convert_moves_to_san_rejects_empty_conversion(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Vérifie une conversion incohérente."""

    service = ChessService()

    monkeypatch.setattr(
        service,
        "convert_uci_history_to_san",
        MagicMock(return_value=[]),
    )

    with pytest.raises(
        ValueError,
        match="aucun coup",
    ):
        _convert_moves_to_san(
            service,
            UCI_MOVES,
        )


# Ouverture


def test_get_opening_identity_without_opening(
    state: ChessAnalysisState,
) -> None:
    """Vérifie l'absence d'ouverture."""

    assert _get_opening_identity(state) == (
        None,
        None,
    )


def test_get_opening_identity(
    opening_state: ChessAnalysisState,
) -> None:
    """Vérifie l'identité de l'ouverture."""

    assert _get_opening_identity(opening_state) == (
        "Ruy Lopez",
        "C60",
    )


# Requête


def test_build_search_query_with_opening_and_moves(
    opening_state: ChessAnalysisState,
) -> None:
    """Vérifie la requête documentaire complète."""

    query = _build_search_query(
        opening_state,
        SAN_MOVES,
    )

    assert "Type : présentation Wikichess" in query
    assert "Coups : e4 e5 Nf3" in query
    assert "Ouverture Lichess : Ruy Lopez" in query
    assert "Code ECO Lichess : C60" in query


def test_build_search_query_without_context(
    state: ChessAnalysisState,
) -> None:
    """Vérifie la requête minimale."""

    assert (
        _build_search_query(
            state,
            (),
        )
        == "Type : présentation Wikichess"
    )


# Métadonnées


def test_get_metadata_moves() -> None:
    """Vérifie les coups Wikichess."""

    metadata: dict[str, object] = {
        METADATA_MOVES_KEY: [
            " e4 ",
            "e5",
            "",
        ],
    }

    assert _get_metadata_moves(metadata) == (
        "e4",
        "e5",
    )


def test_build_next_move() -> None:
    """Vérifie une continuation valide."""

    result = _build_next_move(
        {
            NEXT_MOVE_KEY: "Nc6",
            NEXT_MOVE_SOURCE_URL_KEY: ("https://example.test/nc6"),
        }
    )

    assert result is not None
    assert result.move == "Nc6"

    assert result.source_url == "https://example.test/nc6"


@pytest.mark.parametrize(
    "value",
    [
        None,
        "invalid",
        {},
        {
            NEXT_MOVE_KEY: "Nc6",
        },
        {
            NEXT_MOVE_SOURCE_URL_KEY: ("https://example.test"),
        },
    ],
)
def test_build_next_move_rejects_invalid_value(
    value: object,
) -> None:
    """Vérifie les continuations invalides."""

    assert _build_next_move(value) is None


def test_get_metadata_next_moves() -> None:
    """Vérifie le filtrage des continuations."""

    metadata: dict[str, object] = {
        METADATA_NEXT_MOVES_KEY: [
            {
                NEXT_MOVE_KEY: "Nc6",
                NEXT_MOVE_SOURCE_URL_KEY: "https://example.test/nc6",
            },
            {
                NEXT_MOVE_KEY: "",
                NEXT_MOVE_SOURCE_URL_KEY: "https://example.test",
            },
            "invalid",
        ],
    }

    result = _get_metadata_next_moves(metadata)

    assert len(result) == 1
    assert result[0].move == "Nc6"


# Similarité


@pytest.mark.parametrize(
    ("value", "expected"),
    [
        (
            -1.0,
            0.0,
        ),
        (
            0.5,
            0.5,
        ),
        (
            2.0,
            1.0,
        ),
        (
            float("inf"),
            0.0,
        ),
    ],
)
def test_normalize_similarity(
    value: float,
    expected: float,
) -> None:
    """Vérifie l'encadrement de la similarité."""

    assert _normalize_similarity(value) == expected


def test_get_result_similarity(
    result: VectorSearchResult,
) -> None:
    """Vérifie la lecture de la similarité."""

    assert _get_result_similarity(result) == 0.92


# Source


def test_get_result_source(
    result: VectorSearchResult,
) -> None:
    """Vérifie la source documentaire."""

    assert _get_result_source(result) == "wikichess"


def test_get_result_source_uses_dataset() -> None:
    """Vérifie le repli sur le dataset."""

    result = build_result()

    result = result.model_copy(
        update={
            "metadata": {
                METADATA_DATASET_KEY: "wikichess-dataset",
            },
        }
    )

    assert _get_result_source(result) == "wikichess-dataset"


def test_get_result_source_uses_default() -> None:
    """Vérifie la source par défaut."""

    result = build_result()

    result = result.model_copy(
        update={
            "metadata": {},
        }
    )

    assert _get_result_source(result) == DEFAULT_DOCUMENT_SOURCE


# Type documentaire


def test_get_document_type_from_enum() -> None:
    """Vérifie un type déjà normalisé."""

    metadata: dict[str, object] = {
        METADATA_TYPE_KEY: DocumentType.ARTICLE,
    }

    assert _get_document_type(metadata) == DocumentType.ARTICLE


def test_get_document_type_from_string() -> None:
    """Vérifie un type textuel."""

    metadata: dict[str, object] = {
        METADATA_TYPE_KEY: "article",
    }

    assert _get_document_type(metadata) == DocumentType.ARTICLE


def test_get_document_type_falls_back_on_unknown() -> None:
    """Vérifie un type inconnu."""

    assert (
        _get_document_type(
            {
                METADATA_TYPE_KEY: "inconnu",
            }
        )
        == DocumentType.ARTICLE
    )


# Extrait


def test_build_excerpt_returns_none_for_empty_content() -> None:
    """Vérifie l'absence d'extrait."""

    assert _build_excerpt("   ") is None


def test_build_excerpt_returns_content() -> None:
    """Vérifie un contenu court."""

    assert _build_excerpt("Texte pédagogique.") == "Texte pédagogique."


def test_build_excerpt_truncates_long_content() -> None:
    """Vérifie la troncature."""

    content = "x" * (EXCERPT_MAX_LENGTH + 20)

    result = _build_excerpt(content)

    assert result is not None
    assert result.endswith("...")
    assert len(result) == EXCERPT_MAX_LENGTH + 3


# Sélection


def test_select_results_keeps_best_result() -> None:
    """Vérifie le tri par similarité."""

    results = [
        build_result(
            identifier="low",
            similarity=0.40,
        ),
        build_result(
            identifier="high",
            similarity=0.95,
        ),
    ]

    selected = _select_results(results)

    assert len(selected) == SELECTED_DOCUMENT_LIMIT

    assert selected[0].id == "high"


# Contexte RAG


def test_build_retrieval_context(
    result: VectorSearchResult,
) -> None:
    """Vérifie la conversion d'un résultat vectoriel."""

    context = _build_retrieval_context(
        "query",
        [
            result,
        ],
    )

    assert context.query == "query"
    assert context.total_results == 1
    assert len(context.documents) == 1

    retrieved = context.documents[0]

    assert retrieved.document.id == "ruy-lopez"

    assert retrieved.document.title == "Ruy Lopez"

    assert retrieved.similarity == 0.92

    assert retrieved.document.metadata.eco == "C60"

    assert retrieved.document.metadata.moves == (
        "e4",
        "e5",
        "Nf3",
    )

    assert retrieved.document.metadata.next_moves[0].move == "Nc6"


def test_build_empty_retrieval_context() -> None:
    """Vérifie un contexte vide."""

    context = _build_empty_retrieval_context("query")

    assert context.query == "query"
    assert context.documents == []
    assert context.total_results == 0


# Résumé documentaire


def test_build_documents_summary(
    result: VectorSearchResult,
) -> None:
    """Vérifie le résumé du document retenu."""

    context = _build_retrieval_context(
        "query",
        [
            result,
        ],
    )

    summary = _build_documents_summary(context)

    assert summary is not None
    assert "Titre : Ruy Lopez" in summary
    assert "Code ECO : C60" in summary
    assert "Coups : e4 e5 Nf3" in summary
    assert "Présentation Wikichess" in summary
    assert "Continuations Wikichess : Nc6" in summary


def test_build_documents_summary_returns_none() -> None:
    """Vérifie l'absence de documents."""

    context = _build_empty_retrieval_context("query")

    assert _build_documents_summary(context) is None


# Recherche interne


@pytest.mark.asyncio
async def test_search_documents_returns_empty_without_context(
    state: ChessAnalysisState,
) -> None:
    """Vérifie l'absence de recherche sans ECO ni coups."""

    service = MagicMock(
        spec=VectorSearchService,
    )

    context = await _search_documents(
        state=state,
        moves=(),
        service=service,
    )

    assert context.total_results == 0


@pytest.mark.asyncio
async def test_search_documents_returns_result(
    opening_state: ChessAnalysisState,
    result: VectorSearchResult,
) -> None:
    """Vérifie une recherche Wikichess réussie."""

    search = AsyncMock(
        return_value=[
            result,
        ]
    )

    service = MagicMock(
        spec=VectorSearchService,
    )
    service.search_wikichess = search

    context = await _search_documents(
        state=opening_state,
        moves=SAN_MOVES,
        service=service,
    )

    assert context.total_results == 1

    search.assert_awaited_once_with(
        query=_build_search_query(
            opening_state,
            SAN_MOVES,
        ),
        eco="C60",
        moves=SAN_MOVES,
        limit=SELECTED_DOCUMENT_LIMIT,
    )


@pytest.mark.asyncio
async def test_search_documents_returns_empty_when_no_result(
    opening_state: ChessAnalysisState,
) -> None:
    """Vérifie une recherche sans résultat."""

    search = AsyncMock(return_value=[])

    service = MagicMock(
        spec=VectorSearchService,
    )
    service.search_wikichess = search

    context = await _search_documents(
        state=opening_state,
        moves=SAN_MOVES,
        service=service,
    )

    assert context.total_results == 0


# Mises à jour


def test_build_success_update(
    state: ChessAnalysisState,
    result: VectorSearchResult,
) -> None:
    """Vérifie une recherche réussie."""

    context = _build_retrieval_context(
        "query",
        [
            result,
        ],
    )

    update = _build_success_update(
        state,
        context,
    )

    assert update["status"] == AnalysisStatus.SUCCESS

    assert update["current_step"] == WorkflowStep.RETRIEVE_CONTEXT

    assert WorkflowStep.RETRIEVE_CONTEXT in update["completed_steps"]

    assert update["retrieval_context"] == context

    assert update["workflow_context"].documents_summary is not None


def test_build_warning_update(
    state: ChessAnalysisState,
) -> None:
    """Vérifie une recherche dégradée."""

    warning = WorkflowWarning(
        step=WorkflowStep.RETRIEVE_CONTEXT,
        code=ERROR_MILVUS_UNAVAILABLE,
        message="Recherche indisponible.",
    )

    update = _build_warning_update(
        state,
        warning,
        query="query",
    )

    assert update["status"] == AnalysisStatus.PARTIAL_SUCCESS

    assert WorkflowStep.RETRIEVE_CONTEXT in update["completed_steps"]

    assert update["retrieval_context"].total_results == 0

    assert update["warnings"] == [
        warning,
    ]


# Nœud


@pytest.mark.asyncio
async def test_retrieve_context_skips_search_without_eco_or_moves(
    state: ChessAnalysisState,
) -> None:
    """Vérifie le chemin sans critère de recherche."""

    result = await retrieve_context(
        state,
        cast(
            RunnableConfig,
            {},
        ),
    )

    assert result["status"] == AnalysisStatus.SUCCESS

    assert result["retrieval_context"].total_results == 0

    assert WorkflowStep.RETRIEVE_CONTEXT in result["completed_steps"]


@pytest.mark.asyncio
async def test_retrieve_context_missing_vector_service(
    opening_state: ChessAnalysisState,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Vérifie l'absence de VectorSearchService."""

    emit_progress = MagicMock()

    monkeypatch.setattr(
        "app.agent.nodes.E_retrieve_context._get_vector_search_service",
        MagicMock(return_value=None),
    )

    monkeypatch.setattr(
        "app.agent.nodes.E_retrieve_context.emit_progress",
        emit_progress,
    )

    result = await retrieve_context(
        opening_state,
        cast(
            RunnableConfig,
            {},
        ),
    )

    assert result["status"] == AnalysisStatus.FAILED

    assert result["errors"][0].code == ERROR_CONFIGURATION

    emit_progress.assert_called_once()


@pytest.mark.asyncio
async def test_retrieve_context_missing_chess_service(
    state: ChessAnalysisState,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Vérifie l'absence de ChessService lors de la conversion."""

    current_state = state.model_copy(
        update={
            "moves": UCI_MOVES,
        }
    )

    vector_service = MagicMock(
        spec=VectorSearchService,
    )

    monkeypatch.setattr(
        "app.agent.nodes.E_retrieve_context._get_vector_search_service",
        MagicMock(return_value=vector_service),
    )

    monkeypatch.setattr(
        "app.agent.nodes.E_retrieve_context._get_chess_service",
        MagicMock(return_value=None),
    )

    emit_progress = MagicMock()

    monkeypatch.setattr(
        "app.agent.nodes.E_retrieve_context.emit_progress",
        emit_progress,
    )

    result = await retrieve_context(
        current_state,
        cast(
            RunnableConfig,
            {},
        ),
    )

    assert result["status"] == AnalysisStatus.FAILED

    assert result["errors"][0].code == ERROR_CONFIGURATION

    emit_progress.assert_called_once()


@pytest.mark.asyncio
async def test_retrieve_context_conversion_error(
    state: ChessAnalysisState,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Vérifie une erreur de conversion UCI vers SAN."""

    current_state = state.model_copy(
        update={
            "moves": UCI_MOVES,
        }
    )

    vector_service = MagicMock(
        spec=VectorSearchService,
    )

    chess_service = ChessService()

    monkeypatch.setattr(
        "app.agent.nodes.E_retrieve_context._get_vector_search_service",
        MagicMock(return_value=vector_service),
    )

    monkeypatch.setattr(
        "app.agent.nodes.E_retrieve_context._get_chess_service",
        MagicMock(return_value=chess_service),
    )

    monkeypatch.setattr(
        "app.agent.nodes.E_retrieve_context._convert_moves_to_san",
        MagicMock(side_effect=RuntimeError("conversion failure")),
    )

    emit_progress = MagicMock()

    monkeypatch.setattr(
        "app.agent.nodes.E_retrieve_context.emit_progress",
        emit_progress,
    )

    result = await retrieve_context(
        current_state,
        cast(
            RunnableConfig,
            {},
        ),
    )

    assert result["status"] == AnalysisStatus.FAILED

    assert result["errors"][0].code == ERROR_UNEXPECTED

    assert emit_progress.call_count == 2


@pytest.mark.asyncio
async def test_retrieve_context_success(
    state: ChessAnalysisState,
    result: VectorSearchResult,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Vérifie le chemin complet UCI → SAN → Wikichess."""

    current_state = state.model_copy(
        update={
            "moves": UCI_MOVES,
        }
    )

    chess_service = ChessService()

    vector_service = MagicMock(
        spec=VectorSearchService,
    )

    search = AsyncMock(
        return_value=[
            result,
        ]
    )

    vector_service.search_wikichess = search

    monkeypatch.setattr(
        "app.agent.nodes.E_retrieve_context._get_vector_search_service",
        MagicMock(return_value=vector_service),
    )

    monkeypatch.setattr(
        "app.agent.nodes.E_retrieve_context._get_chess_service",
        MagicMock(return_value=chess_service),
    )

    monkeypatch.setattr(
        "app.agent.nodes.E_retrieve_context._convert_moves_to_san",
        MagicMock(return_value=SAN_MOVES),
    )

    emit_progress = MagicMock()

    monkeypatch.setattr(
        "app.agent.nodes.E_retrieve_context.emit_progress",
        emit_progress,
    )

    update = await retrieve_context(
        current_state,
        cast(
            RunnableConfig,
            {},
        ),
    )

    assert update["status"] == AnalysisStatus.SUCCESS

    assert update["retrieval_context"].total_results == 1

    assert WorkflowStep.RETRIEVE_CONTEXT in update["completed_steps"]

    assert emit_progress.call_count == 4


@pytest.mark.asyncio
async def test_retrieve_context_handles_retrieval_error(
    opening_state: ChessAnalysisState,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Vérifie une indisponibilité connue du RAG."""

    vector_service = MagicMock(
        spec=VectorSearchService,
    )

    search_documents = AsyncMock(
        side_effect=RetrievalError(
            message="Milvus indisponible.",
        )
    )

    monkeypatch.setattr(
        "app.agent.nodes.E_retrieve_context._get_vector_search_service",
        MagicMock(return_value=vector_service),
    )

    monkeypatch.setattr(
        "app.agent.nodes.E_retrieve_context._search_documents",
        search_documents,
    )

    emit_progress = MagicMock()

    monkeypatch.setattr(
        "app.agent.nodes.E_retrieve_context.emit_progress",
        emit_progress,
    )

    update = await retrieve_context(
        opening_state,
        cast(
            RunnableConfig,
            {},
        ),
    )

    assert update["status"] == AnalysisStatus.PARTIAL_SUCCESS

    assert update["retrieval_context"].total_results == 0

    assert len(update["warnings"]) == 1

    assert WorkflowStep.RETRIEVE_CONTEXT in update["completed_steps"]

    assert emit_progress.call_count == 2


@pytest.mark.asyncio
async def test_retrieve_context_handles_unexpected_search_error(
    opening_state: ChessAnalysisState,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Vérifie une erreur inattendue de recherche."""

    vector_service = MagicMock(
        spec=VectorSearchService,
    )

    monkeypatch.setattr(
        "app.agent.nodes.E_retrieve_context._get_vector_search_service",
        MagicMock(return_value=vector_service),
    )

    monkeypatch.setattr(
        "app.agent.nodes.E_retrieve_context._search_documents",
        AsyncMock(side_effect=RuntimeError("unexpected")),
    )

    emit_progress = MagicMock()

    monkeypatch.setattr(
        "app.agent.nodes.E_retrieve_context.emit_progress",
        emit_progress,
    )

    update = await retrieve_context(
        opening_state,
        cast(
            RunnableConfig,
            {},
        ),
    )

    assert update["status"] == AnalysisStatus.FAILED

    assert update["errors"][0].code == ERROR_UNEXPECTED

    assert WorkflowStep.RETRIEVE_CONTEXT not in update["completed_steps"]

    assert emit_progress.call_count == 2
