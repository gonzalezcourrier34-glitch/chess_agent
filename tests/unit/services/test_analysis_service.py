"""Tests unitaires du service d'orchestration des analyses."""

from __future__ import annotations

from collections.abc import AsyncIterator
from datetime import UTC, datetime
from types import SimpleNamespace
from typing import Any, cast
from unittest.mock import AsyncMock, MagicMock

import chess
import pytest
from app.agent.graph import (
    ChessAnalysisGraph,
    GraphDependencies,
)
from app.agent.state import (
    ChessAnalysisState,
    WorkflowMetadata,
)
from app.core.config import settings
from app.core.exceptions import (
    WorkflowConfigurationError,
    WorkflowExecutionError,
    WorkflowStateError,
)
from app.schemas.analysis.analysis import (
    AnalysisRequest,
)
from app.schemas.analysis.progress import (
    AnalysisCompletedEvent,
    AnalysisProgressEvent,
)
from app.schemas.common.enums import (
    AnalysisStatus,
    ServiceType,
    WorkflowStep,
    WorkflowStepStatus,
)
from app.schemas.common.error import WorkflowError
from app.services.analysis_service import AnalysisService
from langchain_core.runnables import RunnableConfig

# Configuration

STARTING_FEN = chess.STARTING_FEN

REQUEST_ID = "request-123"

STARTED_AT = datetime(
    2026,
    8,
    18,
    10,
    0,
    tzinfo=UTC,
)

FINISHED_AT = datetime(
    2026,
    8,
    18,
    10,
    0,
    1,
    tzinfo=UTC,
)


# Faux graphe

class FakeStreamingGraph:
    """Graphe minimal produisant des événements LangGraph."""

    def __init__(
        self,
        parts: list[dict[str, Any]],
    ) -> None:
        """Initialise les événements à diffuser."""

        self.parts = parts

        self.calls: list[
            tuple[
                ChessAnalysisState,
                RunnableConfig,
            ]
        ] = []

    async def astream(
        self,
        state: ChessAnalysisState,
        *,
        config: RunnableConfig,
        stream_mode: list[str],
        version: str,
    ) -> AsyncIterator[object]:
        """Diffuse les événements configurés."""

        del stream_mode
        del version

        self.calls.append(
            (
                state,
                config,
            )
        )

        for part in self.parts:
            yield part


class InvalidStreamingGraph:
    """Graphe minimal levant une erreur pendant le streaming."""

    async def astream(
        self,
        state: ChessAnalysisState,
        *,
        config: RunnableConfig,
        stream_mode: list[str],
        version: str,
    ) -> AsyncIterator[object]:
        """Lève une erreur pendant le streaming."""

        del state
        del config
        del stream_mode
        del version

        if False:
            yield {}

        raise RuntimeError(
            "stream failure"
        )


# Helpers

def build_request(
    *,
    fen: str = STARTING_FEN,
    moves: list[str] | None = None,
    question: str | None = None,
    response_language: str = "fr",
) -> AnalysisRequest:
    """Construit une requête conforme aux champs lus par le service."""

    return AnalysisRequest.model_construct(
        fen=fen,
        moves=(
            moves
            if moves is not None
            else []
        ),
        question=question,
        response_language=response_language,
    )


def build_state(
    *,
    status: AnalysisStatus = AnalysisStatus.SUCCESS,
    request_id: str = REQUEST_ID,
    response: str | None = "Réponse pédagogique.",
) -> ChessAnalysisState:
    """Construit un état final minimal."""

    return ChessAnalysisState(
        fen=STARTING_FEN,
        status=status,
        response=response,
        metadata=WorkflowMetadata(
            request_id=request_id,
            started_at=STARTED_AT,
        ),
    )


def build_dependencies(
    *,
    embedding_ready: bool = True,
    embedding_dimension: int = 1024,
) -> GraphDependencies:
    """Construit les dépendances minimales utilisées par AnalysisService."""

    embedding_service = MagicMock()

    embedding_service.is_ready.return_value = (
        embedding_ready
    )

    embedding_service.get_dimension.return_value = (
        embedding_dimension
    )

    dependencies = SimpleNamespace(
        chess_service=MagicMock(),
        stockfish_service=MagicMock(),
        lichess_service=MagicMock(),
        embedding_service=embedding_service,
        milvus_service=MagicMock(),
        vector_search_service=MagicMock(),
        llm_service=MagicMock(),
        youtube_service=MagicMock(),
        mongodb_service=MagicMock(),
    )

    return cast(
        GraphDependencies,
        dependencies,
    )


def build_service(
    *,
    graph: object | None = None,
    dependencies: GraphDependencies | None = None,
) -> AnalysisService:
    """Construit AnalysisService sans infrastructure réelle."""

    if graph is None:
        graph = MagicMock()

    if dependencies is None:
        dependencies = build_dependencies()

    return AnalysisService(
        graph=cast(
            ChessAnalysisGraph,
            graph,
        ),
        dependencies=dependencies,
    )


# Construction

def test_service_starts_with_zero_statistics() -> None:
    """Vérifie les statistiques initiales."""

    service = build_service()

    assert service.get_analysis_count() == 0

    assert (
        service.get_last_analysis_duration()
        is None
    )

    assert service.is_ready() is True


# Graphe

def test_get_graph_returns_graph() -> None:
    """Vérifie la récupération du graphe."""

    graph = MagicMock()

    service = build_service(
        graph=graph,
    )

    assert (
        service._get_graph()
        is graph
    )


def test_get_graph_rejects_missing_graph() -> None:
    """Vérifie l'absence du graphe."""

    service = build_service()

    service._graph = None  # type: ignore[assignment]

    with pytest.raises(
        WorkflowConfigurationError
    ):
        service._get_graph()


# Normalisation de la question

@pytest.mark.parametrize(
    ("value", "expected"),
    [
        (
            None,
            "",
        ),
        (
            "",
            "",
        ),
        (
            "   ",
            "",
        ),
        (
            "  Que   jouer ?  ",
            "Que jouer ?",
        ),
    ],
)
def test_normalize_question(
    value: str | None,
    expected: str,
) -> None:
    """Vérifie la normalisation de la question."""

    service = build_service()

    assert (
        service._normalize_question(value)
        == expected
    )


# Langue

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
            "   ",
            "fr",
        ),
    ],
)
def test_normalize_language(
    value: str,
    expected: str,
) -> None:
    """Vérifie la normalisation de la langue."""

    service = build_service()

    assert (
        service._normalize_language(value)
        == expected
    )


# Coups

def test_normalize_moves() -> None:
    """Vérifie la normalisation des coups."""

    service = build_service()

    assert (
        service._normalize_moves(
            [
                " e2e4 ",
                "",
                "   ",
                "e7e5",
                " g1f3 ",
            ]
        )
        == [
            "e2e4",
            "e7e5",
            "g1f3",
        ]
    )


def test_normalize_moves_empty() -> None:
    """Vérifie une liste vide."""

    service = build_service()

    assert (
        service._normalize_moves([])
        == []
    )


# Options

def test_build_options_enables_workflow_features() -> None:
    """Vérifie les options produites pour le workflow."""

    service = build_service()

    options = service._build_options(
        build_request(
            response_language="EN",
        )
    )

    assert options.include_stockfish is True
    assert options.include_opening is True
    assert options.include_context is True
    assert options.include_videos is True
    assert options.generate_response is True
    assert options.save_analysis is True

    assert (
        options.response_language
        == "en"
    )


# Métadonnées initiales

def test_build_metadata() -> None:
    """Vérifie les métadonnées initiales."""

    service = build_service()

    metadata = service._build_metadata(
        request_id=REQUEST_ID,
        started_at=STARTED_AT,
    )

    assert metadata.request_id == REQUEST_ID

    assert (
        metadata.started_at
        == STARTED_AT
    )


# Métadonnées finales

def test_complete_metadata_with_ready_embedding() -> None:
    """Vérifie l'enrichissement des métadonnées."""

    dependencies = build_dependencies(
        embedding_ready=True,
        embedding_dimension=1024,
    )

    service = build_service(
        dependencies=dependencies,
    )

    state = build_state()

    metadata = service._complete_metadata(
        state,
        finished_at=FINISHED_AT,
        duration_ms=125.5,
    )

    assert (
        metadata.finished_at
        == FINISHED_AT
    )

    assert metadata.duration_ms == 125.5

    assert (
        metadata.embedding_model
        == settings.embedding_model
    )

    assert (
        metadata.embedding_provider
        == settings.embedding_provider
    )

    assert (
        metadata.embedding_dimension
        == 1024
    )

    assert (
        metadata.llm_model
        == settings.llm_model
    )

    assert (
        metadata.llm_provider
        == settings.llm_provider
    )

    assert (
        metadata.rag_top_k
        == settings.rag_search_top_k
    )


def test_complete_metadata_without_ready_embedding() -> None:
    """Vérifie l'absence de dimension lorsque l'embedding n'est pas prêt."""

    dependencies = build_dependencies(
        embedding_ready=False,
    )

    service = build_service(
        dependencies=dependencies,
    )

    state = build_state()

    metadata = service._complete_metadata(
        state,
        finished_at=FINISHED_AT,
        duration_ms=10.0,
    )

    assert (
        metadata.embedding_dimension
        is None
    )


def test_complete_metadata_without_optional_results() -> None:
    """Vérifie les métadonnées sans Stockfish ni RAG."""

    service = build_service()

    state = build_state()

    metadata = service._complete_metadata(
        state,
        finished_at=FINISHED_AT,
        duration_ms=10.0,
    )

    assert metadata.stockfish_depth is None

    assert (
        metadata.retrieved_document_count
        is None
    )


# État initial

def test_build_initial_state() -> None:
    """Vérifie l'état initial transmis à LangGraph."""

    service = build_service()

    request = build_request(
        moves=[
            " e2e4 ",
            "",
            " e7e5 ",
        ],
        question="  Que   jouer ? ",
        response_language="FR",
    )

    state = service._build_initial_state(
        request,
        request_id=REQUEST_ID,
        started_at=STARTED_AT,
    )

    assert state.fen == STARTING_FEN

    assert state.moves == [
        "e2e4",
        "e7e5",
    ]

    assert (
        state.question
        == "Que jouer ?"
    )

    assert (
        state.status
        == AnalysisStatus.PENDING
    )

    assert (
        state.metadata.request_id
        == REQUEST_ID
    )

    assert (
        state.metadata.started_at
        == STARTED_AT
    )

    assert (
        state.options.response_language
        == "fr"
    )


# Résultat du graphe

def test_normalize_graph_result_returns_existing_state() -> None:
    """Vérifie un état déjà validé."""

    service = build_service()

    state = build_state()

    assert (
        service._normalize_graph_result(
            state
        )
        is state
    )


def test_normalize_graph_result_validates_dict() -> None:
    """Vérifie la conversion d'un dictionnaire LangGraph."""

    service = build_service()

    result = service._normalize_graph_result(
        {
            "fen": STARTING_FEN,
            "status": AnalysisStatus.SUCCESS,
        }
    )

    assert isinstance(
        result,
        ChessAnalysisState,
    )

    assert result.fen == STARTING_FEN

    assert (
        result.status
        == AnalysisStatus.SUCCESS
    )


def test_normalize_graph_result_rejects_invalid_dict() -> None:
    """Vérifie un état final invalide."""

    service = build_service()

    with pytest.raises(
        WorkflowStateError
    ):
        service._normalize_graph_result(
            {
                "status": "invalid",
            }
        )


# Configuration LangGraph

def test_build_config(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Vérifie la configuration finale du graphe."""

    dependencies = build_dependencies()

    service = build_service(
        dependencies=dependencies,
    )

    build_config = MagicMock(
        return_value={
            "configurable": {
                "existing": "value",
            },
        }
    )

    monkeypatch.setattr(
        "app.services.analysis_service."
        "build_graph_config",
        build_config,
    )

    config = service._build_config(
        thread_id=REQUEST_ID,
    )

    configurable = config.get(
        "configurable"
    )

    assert configurable is not None

    assert (
        configurable["existing"]
        == "value"
    )

    assert (
        configurable["thread_id"]
        == REQUEST_ID
    )

    recursion_limit = config.get(
        "recursion_limit"
    )

    assert recursion_limit is not None

    assert (
        recursion_limit
        == settings.max_agent_iterations
    )

    build_config.assert_called_once_with(
        dependencies
    )


def test_build_config_creates_configurable_section(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Vérifie la création de configurable si nécessaire."""

    service = build_service()

    monkeypatch.setattr(
        "app.services.analysis_service."
        "build_graph_config",
        MagicMock(
            return_value={},
        ),
    )

    config = service._build_config(
        thread_id=REQUEST_ID,
    )

    configurable = config.get(
        "configurable"
    )

    assert configurable is not None

    assert (
        configurable["thread_id"]
        == REQUEST_ID
    )


# Exécution du graphe

@pytest.mark.asyncio
async def test_run_graph_success() -> None:
    """Vérifie une exécution LangGraph réussie."""

    final_state = build_state()

    graph = MagicMock()

    ainvoke = AsyncMock(
        return_value=final_state,
    )

    graph.ainvoke = ainvoke

    service = build_service(
        graph=graph,
    )

    initial_state = ChessAnalysisState(
        fen=STARTING_FEN,
    )

    config = cast(
        RunnableConfig,
        {
            "configurable": {},
        },
    )

    result = await service._run_graph(
        initial_state,
        config,
    )

    assert result is final_state

    ainvoke.assert_awaited_once_with(
        initial_state,
        config=config,
    )


@pytest.mark.asyncio
async def test_run_graph_normalizes_dict_result() -> None:
    """Vérifie un résultat brut retourné par LangGraph."""

    graph = MagicMock()

    graph.ainvoke = AsyncMock(
        return_value={
            "fen": STARTING_FEN,
            "status": AnalysisStatus.SUCCESS,
        },
    )

    service = build_service(
        graph=graph,
    )

    result = await service._run_graph(
        ChessAnalysisState(
            fen=STARTING_FEN,
        ),
        cast(
            RunnableConfig,
            {},
        ),
    )

    assert isinstance(
        result,
        ChessAnalysisState,
    )

    assert (
        result.status
        == AnalysisStatus.SUCCESS
    )


@pytest.mark.asyncio
async def test_run_graph_wraps_unexpected_exception() -> None:
    """Vérifie la traduction d'une erreur LangGraph."""

    graph = MagicMock()

    graph.ainvoke = AsyncMock(
        side_effect=RuntimeError(
            "graph failure"
        ),
    )

    service = build_service(
        graph=graph,
    )

    state = ChessAnalysisState(
        fen=STARTING_FEN,
        metadata=WorkflowMetadata(
            request_id=REQUEST_ID,
        ),
    )

    with pytest.raises(
        WorkflowExecutionError
    ):
        await service._run_graph(
            state,
            cast(
                RunnableConfig,
                {},
            ),
        )


# Streaming brut

@pytest.mark.asyncio
async def test_stream_graph_returns_only_dict_parts() -> None:
    """Vérifie le filtrage des événements LangGraph."""

    graph = FakeStreamingGraph(
        [
            {
                "type": "custom",
                "data": {},
            },
            "invalid",  # type: ignore[list-item]
            {
                "type": "values",
                "data": {
                    "fen": STARTING_FEN,
                },
            },
        ]
    )

    service = build_service(
        graph=graph,
    )

    parts = [
        part
        async for part
        in service._stream_graph(
            ChessAnalysisState(
                fen=STARTING_FEN,
            ),
            cast(
                RunnableConfig,
                {},
            ),
        )
    ]

    assert len(parts) == 2

    assert (
        parts[0]["type"]
        == "custom"
    )

    assert (
        parts[1]["type"]
        == "values"
    )


@pytest.mark.asyncio
async def test_stream_graph_wraps_unexpected_exception() -> None:
    """Vérifie la traduction des erreurs de streaming."""

    service = build_service(
        graph=InvalidStreamingGraph(),
    )

    with pytest.raises(
        WorkflowExecutionError
    ):
        async for _ in service._stream_graph(
            ChessAnalysisState(
                fen=STARTING_FEN,
                metadata=WorkflowMetadata(
                    request_id=REQUEST_ID,
                ),
            ),
            cast(
                RunnableConfig,
                {},
            ),
        ):
            pass


# Progression d'étape

def test_extract_step_progress_event() -> None:
    """Vérifie la conversion d'une mise à jour de nœud."""

    service = build_service()

    event = (
        service
        ._extract_step_progress_event(
            {
                "current_step": (
                    WorkflowStep.ENGINE_ANALYSIS
                ),
                "completed_steps": [
                    WorkflowStep.VALIDATE_POSITION,
                    WorkflowStep.ENGINE_ANALYSIS,
                ],
            },
            request_id=REQUEST_ID,
        )
    )

    assert event is not None

    assert (
        event.request_id
        == REQUEST_ID
    )

    assert (
        event.step
        == WorkflowStep.ENGINE_ANALYSIS
    )

    assert (
        event.status
        == WorkflowStepStatus.COMPLETED
    )

    assert event.completed_steps == [
        WorkflowStep.VALIDATE_POSITION,
        WorkflowStep.ENGINE_ANALYSIS,
    ]


def test_extract_step_progress_event_returns_none_without_step() -> None:
    """Vérifie une mise à jour sans étape."""

    service = build_service()

    assert (
        service
        ._extract_step_progress_event(
            {},
            request_id=REQUEST_ID,
        )
        is None
    )


def test_extract_step_progress_event_rejects_unknown_step() -> None:
    """Vérifie une étape inconnue."""

    service = build_service()

    assert (
        service
        ._extract_step_progress_event(
            {
                "current_step": (
                    "unknown_step"
                ),
            },
            request_id=REQUEST_ID,
        )
        is None
    )


def test_extract_step_progress_event_filters_invalid_completed_steps() -> None:
    """Vérifie la normalisation des étapes terminées."""

    service = build_service()

    event = (
        service
        ._extract_step_progress_event(
            {
                "current_step": (
                    WorkflowStep.ENGINE_ANALYSIS
                ),
                "completed_steps": [
                    WorkflowStep.VALIDATE_POSITION,
                    "invalid",
                    WorkflowStep.VALIDATE_POSITION,
                ],
            },
            request_id=REQUEST_ID,
        )
    )

    assert event is not None

    assert event.completed_steps == [
        WorkflowStep.VALIDATE_POSITION,
    ]


# Progression de service

def test_extract_service_progress_event() -> None:
    """Vérifie un événement de progression valide."""

    service = build_service()

    event = (
        service
        ._extract_service_progress_event(
            {
                "step": (
                    WorkflowStep.ENGINE_ANALYSIS
                ),
                "status": (
                    WorkflowStepStatus.RUNNING
                ),
                "service": ServiceType.STOCKFISH,
                "message": "Analyse en cours.",
            },
            request_id=REQUEST_ID,
            completed_steps=[
                WorkflowStep.VALIDATE_POSITION,
            ],
        )
    )

    assert event is not None

    assert (
        event.step
        == WorkflowStep.ENGINE_ANALYSIS
    )

    assert (
        event.status
        == WorkflowStepStatus.RUNNING
    )

    assert (
        event.service
        == ServiceType.STOCKFISH
    )

    assert (
        event.message
        == "Analyse en cours."
    )

    assert event.completed_steps == [
        WorkflowStep.VALIDATE_POSITION,
    ]


def test_extract_service_progress_event_without_service() -> None:
    """Vérifie qu'un service est facultatif."""

    service = build_service()

    event = (
        service
        ._extract_service_progress_event(
            {
                "step": (
                    WorkflowStep.GENERATE_RESPONSE
                ),
                "status": (
                    WorkflowStepStatus.RUNNING
                ),
            },
            request_id=REQUEST_ID,
            completed_steps=[],
        )
    )

    assert event is not None
    assert event.service is None


@pytest.mark.parametrize(
    "data",
    [
        {},
        {
            "step": "invalid",
            "status": "running",
        },
        {
            "step": WorkflowStep.ENGINE_ANALYSIS,
        },
        {
            "step": WorkflowStep.ENGINE_ANALYSIS,
            "status": "invalid",
        },
    ],
)
def test_extract_service_progress_event_rejects_invalid_data(
    data: dict[str, Any],
) -> None:
    """Vérifie les événements de service invalides."""

    service = build_service()

    assert (
        service
        ._extract_service_progress_event(
            data,
            request_id=REQUEST_ID,
            completed_steps=[],
        )
        is None
    )


def test_extract_service_progress_event_ignores_non_string_message() -> None:
    """Vérifie la normalisation du message."""

    service = build_service()

    event = (
        service
        ._extract_service_progress_event(
            {
                "step": (
                    WorkflowStep.ENGINE_ANALYSIS
                ),
                "status": (
                    WorkflowStepStatus.RUNNING
                ),
                "message": 42,
            },
            request_id=REQUEST_ID,
            completed_steps=[],
        )
    )

    assert event is not None
    assert event.message is None


# Mises à jour LangGraph

def test_extract_node_updates() -> None:
    """Vérifie l'extraction des mises à jour de nœuds."""

    service = build_service()

    first = {
        "current_step": (
            WorkflowStep.VALIDATE_POSITION
        ),
    }

    second = {
        "current_step": (
            WorkflowStep.ENGINE_ANALYSIS
        ),
    }

    result = service._extract_node_updates(
        {
            "type": "updates",
            "data": {
                "first": first,
                "invalid": "ignored",
                "second": second,
            },
        }
    )

    assert result == [
        first,
        second,
    ]


@pytest.mark.parametrize(
    "part",
    [
        {
            "type": "custom",
            "data": {},
        },
        {
            "type": "updates",
            "data": [],
        },
    ],
)
def test_extract_node_updates_returns_empty(
    part: dict[str, Any],
) -> None:
    """Vérifie les événements sans mises à jour."""

    service = build_service()

    assert (
        service._extract_node_updates(part)
        == []
    )


# État diffusé

def test_extract_state_value_returns_state() -> None:
    """Vérifie un état déjà validé."""

    service = build_service()

    state = build_state()

    assert (
        service._extract_state_value(
            {
                "type": "values",
                "data": state,
            }
        )
        is state
    )


def test_extract_state_value_validates_dict() -> None:
    """Vérifie un état diffusé sous forme de dictionnaire."""

    service = build_service()

    state = service._extract_state_value(
        {
            "type": "values",
            "data": {
                "fen": STARTING_FEN,
                "status": (
                    AnalysisStatus.SUCCESS
                ),
            },
        }
    )

    assert state is not None

    assert (
        state.status
        == AnalysisStatus.SUCCESS
    )


def test_extract_state_value_returns_none_for_wrong_type() -> None:
    """Vérifie un événement non values."""

    service = build_service()

    assert (
        service._extract_state_value(
            {
                "type": "custom",
                "data": {},
            }
        )
        is None
    )


def test_extract_state_value_returns_none_for_invalid_data_type() -> None:
    """Vérifie des données incompatibles."""

    service = build_service()

    assert (
        service._extract_state_value(
            {
                "type": "values",
                "data": "invalid",
            }
        )
        is None
    )


def test_extract_state_value_returns_none_for_invalid_state() -> None:
    """Vérifie un dictionnaire d'état invalide."""

    service = build_service()

    assert (
        service._extract_state_value(
            {
                "type": "values",
                "data": {
                    "status": "invalid",
                },
            }
        )
        is None
    )


# Erreurs

def test_extract_error_message_returns_none() -> None:
    """Vérifie un état sans erreur."""

    service = build_service()

    assert (
        service._extract_error_message(
            build_state()
        )
        is None
    )


def test_extract_error_message_returns_last_error() -> None:
    """Vérifie que la dernière erreur est retournée."""

    service = build_service()

    first = WorkflowError(
        step=WorkflowStep.VALIDATE_POSITION,
        code="FIRST",
        message="Première erreur.",
        recoverable=False,
    )

    second = WorkflowError(
        step=WorkflowStep.ENGINE_ANALYSIS,
        code="SECOND",
        message="Dernière erreur.",
        recoverable=False,
    )

    state = build_state().model_copy(
        update={
            "errors": [
                first,
                second,
            ],
        }
    )

    assert (
        service._extract_error_message(
            state
        )
        == "Dernière erreur."
    )


# Documents

def test_extract_documents_returns_empty() -> None:
    """Vérifie un état sans contexte RAG."""

    service = build_service()

    assert (
        service._extract_documents(
            build_state()
        )
        == []
    )


def test_extract_documents_returns_documents() -> None:
    """Vérifie l'extraction des documents du contexte RAG."""

    service = build_service()

    document_a = SimpleNamespace(
        id="document-a",
        title="Document A",
    )

    document_b = SimpleNamespace(
        id="document-b",
        title="Document B",
    )

    retrieval_context = SimpleNamespace(
        documents=[
            SimpleNamespace(
                document=document_a,
            ),
            SimpleNamespace(
                document=document_b,
            ),
        ],
        total_results=2,
    )

    state = build_state().model_copy(
        update={
            "retrieval_context": retrieval_context,
        }
    )

    assert (
        service._extract_documents(
            state
        )
        == [
            document_a,
            document_b,
        ]
    )


# Réponse API

def test_build_response() -> None:
    """Vérifie la réponse API minimale."""

    service = build_service()

    state = build_state(
        response="Explication finale.",
    )

    state = state.model_copy(
        update={
            "analysis_id": "analysis-123",
        }
    )

    response = service._build_response(
        state
    )

    assert (
        response.status
        == AnalysisStatus.SUCCESS
    )

    assert response.fen == STARTING_FEN

    assert (
        response.explanation
        == "Explication finale."
    )

    assert (
        response.analysis_id
        == "analysis-123"
    )

    assert response.documents == []
    assert response.videos == []
    assert response.error is None


# Analyse complète

@pytest.mark.asyncio
async def test_analyze_success(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Vérifie l'orchestration nominale d'une analyse."""

    service = build_service()

    final_state = build_state()

    run_graph = AsyncMock(
        return_value=final_state,
    )

    build_config = MagicMock(
        return_value=cast(
            RunnableConfig,
            {
                "configurable": {
                    "thread_id": REQUEST_ID,
                },
            },
        ),
    )

    complete_metadata = MagicMock(
        return_value=final_state.metadata,
    )

    monkeypatch.setattr(
        service,
        "_run_graph",
        run_graph,
    )

    monkeypatch.setattr(
        service,
        "_build_config",
        build_config,
    )

    monkeypatch.setattr(
        service,
        "_complete_metadata",
        complete_metadata,
    )

    response = await service.analyze(
        build_request(
            moves=[
                "e2e4",
                "e7e5",
            ],
        ),
        request_id=REQUEST_ID,
    )

    assert (
        response.status
        == AnalysisStatus.SUCCESS
    )

    assert (
        service.get_analysis_count()
        == 1
    )

    assert (
        service.get_last_analysis_duration()
        is not None
    )

    build_config.assert_called_once_with(
        thread_id=REQUEST_ID,
    )

    run_graph.assert_awaited_once()

    initial_state = (
        run_graph
        .call_args
        .args[0]
    )

    assert (
        initial_state
        .metadata
        .request_id
        == REQUEST_ID
    )

    assert initial_state.moves == [
        "e2e4",
        "e7e5",
    ]


@pytest.mark.asyncio
async def test_analyze_generates_request_id(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Vérifie la création automatique du request_id."""

    service = build_service()

    final_state = build_state(
        request_id="generated-id",
    )

    monkeypatch.setattr(
        "app.services.analysis_service."
        "uuid4",
        MagicMock(
            return_value="generated-id",
        ),
    )

    monkeypatch.setattr(
        service,
        "_run_graph",
        AsyncMock(
            return_value=final_state,
        ),
    )

    monkeypatch.setattr(
        service,
        "_complete_metadata",
        MagicMock(
            return_value=final_state.metadata,
        ),
    )

    response = await service.analyze(
        build_request(),
    )

    assert (
        response.status
        == AnalysisStatus.SUCCESS
    )


# Streaming complet

@pytest.mark.asyncio
async def test_stream_analysis_emits_progress_and_completed_event(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Vérifie le streaming nominal."""

    service = build_service()

    final_state = build_state()

    parts = [
        {
            "type": "custom",
            "data": {
                "step": (
                    WorkflowStep.VALIDATE_POSITION
                ),
                "status": (
                    WorkflowStepStatus.RUNNING
                ),
                "service": ServiceType.CHESS,
                "message": "Validation.",
            },
        },
        {
            "type": "updates",
            "data": {
                "validate_position": {
                    "current_step": (
                        WorkflowStep.VALIDATE_POSITION
                    ),
                    "completed_steps": [
                        WorkflowStep.VALIDATE_POSITION,
                    ],
                },
            },
        },
        {
            "type": "values",
            "data": final_state,
        },
    ]

    async def stream_graph(
        state: ChessAnalysisState,
        config: RunnableConfig,
    ) -> AsyncIterator[dict[str, Any]]:
        del state
        del config

        for part in parts:
            yield part

    monkeypatch.setattr(
        service,
        "_stream_graph",
        stream_graph,
    )

    monkeypatch.setattr(
        service,
        "_complete_metadata",
        MagicMock(
            return_value=final_state.metadata,
        ),
    )

    events = [
        event
        async for event
        in service.stream_analysis(
            build_request(),
            request_id=REQUEST_ID,
        )
    ]

    assert len(events) == 3

    assert isinstance(
        events[0],
        AnalysisProgressEvent,
    )

    assert (
        events[0].status
        == WorkflowStepStatus.RUNNING
    )

    assert isinstance(
        events[1],
        AnalysisProgressEvent,
    )

    assert (
        events[1].status
        == WorkflowStepStatus.COMPLETED
    )

    assert isinstance(
        events[2],
        AnalysisCompletedEvent,
    )

    assert (
        events[2].request_id
        == REQUEST_ID
    )

    assert (
        service.get_analysis_count()
        == 1
    )

    assert (
        service.get_last_analysis_duration()
        is not None
    )


@pytest.mark.asyncio
async def test_stream_analysis_rejects_missing_final_state(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Vérifie un streaming sans état final."""

    service = build_service()

    async def stream_graph(
        state: ChessAnalysisState,
        config: RunnableConfig,
    ) -> AsyncIterator[dict[str, Any]]:
        del state
        del config

        yield {
            "type": "custom",
            "data": {
                "step": (
                    WorkflowStep.VALIDATE_POSITION
                ),
                "status": (
                    WorkflowStepStatus.RUNNING
                ),
            },
        }

    monkeypatch.setattr(
        service,
        "_stream_graph",
        stream_graph,
    )

    with pytest.raises(
        WorkflowStateError
    ):
        async for _ in service.stream_analysis(
            build_request(),
            request_id=REQUEST_ID,
        ):
            pass


# État public

@pytest.mark.asyncio
async def test_ping_returns_readiness() -> None:
    """Vérifie le ping."""

    service = build_service()

    assert await service.ping() is True


@pytest.mark.asyncio
async def test_health() -> None:
    """Vérifie l'état de santé du service."""

    service = build_service()

    service._analysis_count = 3
    service._last_analysis_duration_ms = 125.5

    status = await service.health()

    assert (
        status["service"]
        == "analysis"
    )

    assert (
        status["available"]
        is True
    )

    assert (
        status["is_ready"]
        is True
    )

    assert (
        status["analysis_count"]
        == 3
    )

    assert (
        status[
            "last_analysis_duration_ms"
        ]
        == 125.5
    )