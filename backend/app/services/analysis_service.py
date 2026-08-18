"""Service d'orchestration des analyses échiquéennes.

Ce service constitue le point d'entrée applicatif pour l'exécution
complète d'une analyse.

Il est responsable de :

- construire l'état initial du workflow ;
- transmettre la position et l'historique des coups au workflow ;
- préparer la configuration LangGraph ;
- exécuter le graphe compilé ;
- valider l'état final ;
- construire la réponse destinée à l'API ;
- mesurer et journaliser l'exécution.

Toute la logique spécialisée reste déléguée aux nœuds LangGraph
et aux services injectés dans le workflow.

Le service ne dépend pas de FastAPI.

Il ne réalise aucun appel direct à :

- Stockfish ;
- Lichess ;
- Milvus ;
- YouTube ;
- MongoDB ;
- un modèle d'embedding ;
- un modèle de langage.

L'historique des coups est transporté sans interprétation afin que
les nœuds spécialisés puissent notamment l'utiliser pour la recherche
documentaire Wikichess.
"""

from __future__ import annotations

from collections.abc import AsyncIterator
from datetime import UTC, datetime
from time import perf_counter
from typing import Any
from uuid import uuid4

from langchain_core.runnables import RunnableConfig

from app.agent.graph import (
    ChessAnalysisGraph,
    GraphDependencies,
    build_graph_config,
)
from app.agent.state import (
    AnalysisOptions,
    ChessAnalysisState,
    WorkflowMetadata,
)
from app.core.config import settings
from app.core.exceptions import (
    ErrorContext,
    WorkflowConfigurationError,
    WorkflowExecutionError,
    WorkflowStateError,
)
from app.core.logging import get_logger
from app.schemas.analysis.analysis import (
    AnalysisRequest,
    AnalysisResponse,
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

logger = get_logger(__name__)


# Types

GraphResult = ChessAnalysisState | dict[str, Any]

type GraphStreamPart = dict[str, Any]

AnalysisStreamEvent = (
    AnalysisProgressEvent
    | AnalysisCompletedEvent
)


# Service

class AnalysisService:
    """Service d'orchestration du workflow d'analyse."""

    # Construction

    def __init__(
        self,
        *,
        graph: ChessAnalysisGraph,
        dependencies: GraphDependencies
    ) -> None:
        """Initialise le service."""

        self._graph = graph

        self._dependencies = dependencies

        self._analysis_count = 0

        self._last_analysis_duration_ms: float | None = None

    # Validation

    def _get_graph(
        self
    ) -> ChessAnalysisGraph:
        """Retourne le graphe compilé."""

        if self._graph is None:
            raise WorkflowConfigurationError(
                context=ErrorContext(
                    workflow="chess_analysis",
                    service="analysis",
                    operation="get_graph"
                ),
                message=(
                    "Le workflow LangGraph "
                    "n'est pas initialisé."
                )
            )

        return self._graph

    # Normalisation

    def _normalize_question(
        self,
        question: str | None
    ) -> str:
        """Retourne une question utilisateur normalisée."""

        if question is None:
            return ""

        return " ".join(
            question.split()
        )

    def _normalize_language(
        self,
        language: str
    ) -> str:
        """Retourne une langue de réponse normalisée."""

        normalized_language = (
            language
            .strip()
            .lower()
        )

        return (
            normalized_language
            or "fr"
        )

    def _normalize_moves(
        self,
        moves: list[str]
    ) -> list[str]:
        """Retourne l'historique des coups normalisé."""

        normalized_moves: list[str] = []

        for move in moves:

            normalized_move = (
                move
                .strip()
            )

            if not normalized_move:
                continue

            normalized_moves.append(
                normalized_move
            )

        return normalized_moves

    # Options

    def _build_options(
        self,
        request: AnalysisRequest
    ) -> AnalysisOptions:
        """Construit les options d'exécution du workflow."""

        return AnalysisOptions(
            # Les enrichissements restent activés par défaut.
            # Le routage choisit uniquement les étapes nécessaires.
            include_stockfish=True,
            include_opening=True,
            include_context=True,
            include_videos=True,
            generate_response=True,
            save_analysis=True,
            response_language=self._normalize_language(
                request.response_language
            )
        )

    # Métadonnées

    def _build_metadata(
        self,
        *,
        request_id: str,
        started_at: datetime
    ) -> WorkflowMetadata:
        """Construit les métadonnées initiales du workflow."""

        return WorkflowMetadata(
            request_id=request_id,
            started_at=started_at
        )

    def _complete_metadata(
        self,
        state: ChessAnalysisState,
        *,
        finished_at: datetime,
        duration_ms: float
    ) -> WorkflowMetadata:
        """Complète les métadonnées après l'exécution."""

        embedding_service = (
            self._dependencies
            .embedding_service
        )

        embedding_dimension = (
            embedding_service.get_dimension()
            if embedding_service.is_ready()
            else None
        )

        stockfish_depth = (
            state
            .evaluation
            .engine
            .evaluation
            .depth
            if state.evaluation is not None
            else None
        )

        retrieved_document_count = (
            state
            .retrieval_context
            .total_results
            if state.retrieval_context is not None
            else None
        )

        return state.metadata.model_copy(
            update={
                "finished_at": finished_at,
                "duration_ms": duration_ms,
                "embedding_model": settings.embedding_model,
                "embedding_provider": settings.embedding_provider,
                "embedding_dimension": embedding_dimension,
                "llm_model": settings.llm_model,
                "llm_provider": settings.llm_provider,
                "stockfish_depth": stockfish_depth,
                "rag_top_k": settings.rag_search_top_k,
                "retrieved_document_count": (
                    retrieved_document_count
                )
            }
        )

    # État initial

    def _build_initial_state(
        self,
        request: AnalysisRequest,
        *,
        request_id: str,
        started_at: datetime
    ) -> ChessAnalysisState:
        """Construit l'état initial du workflow."""

        return ChessAnalysisState(
            fen=request.fen,

            # L'historique est transmis tel qu'il a été fourni par
            # l'appelant. Il n'est jamais reconstruit depuis le FEN,
            # le nom de l'ouverture ou le code ECO.
            moves=self._normalize_moves(
                request.moves
            ),

            question=self._normalize_question(
                request.question
            ),

            options=self._build_options(
                request
            ),

            status=AnalysisStatus.PENDING,

            metadata=self._build_metadata(
                request_id=request_id,
                started_at=started_at
            )
        )

    # État final

    def _normalize_graph_result(
        self,
        result: GraphResult
    ) -> ChessAnalysisState:
        """Convertit le résultat LangGraph en état validé."""

        if isinstance(
            result,
            ChessAnalysisState
        ):
            return result

        try:
            return ChessAnalysisState.model_validate(
                result
            )

        except Exception as error:
            logger.exception(
                "L'état final retourné par LangGraph "
                "est invalide."
            )

            raise WorkflowStateError(
                context=ErrorContext(
                    workflow="chess_analysis",
                    service="analysis",
                    operation="normalize_graph_result",
                    metadata={
                        "received_type": type(
                            result
                        ).__name__
                    }
                ),
                message=(
                    "L'état final du workflow "
                    "ne respecte pas son schéma."
                ),
                cause=error
            ) from error

    # Configuration

    def _build_config(
        self,
        *,
        thread_id: str
    ) -> RunnableConfig:
        """Construit la configuration d'exécution LangGraph."""

        config = build_graph_config(
            self._dependencies
        )

        configurable = config.setdefault(
            "configurable",
            {}
        )

        configurable[
            "thread_id"
        ] = thread_id

        config[
            "recursion_limit"
        ] = settings.max_agent_iterations

        return config

    # Exécution

    async def _run_graph(
        self,
        state: ChessAnalysisState,
        config: RunnableConfig
    ) -> ChessAnalysisState:
        """Exécute le workflow LangGraph."""

        graph = self._get_graph()

        try:
            result = await graph.ainvoke(
                state,
                config=config
            )

        except WorkflowExecutionError:
            raise

        except Exception as error:
            logger.exception(
                "Échec de l'exécution du workflow LangGraph."
            )

            raise WorkflowExecutionError(
                context=ErrorContext(
                    workflow="chess_analysis",
                    service="analysis",
                    operation="run_graph",
                    request_id=state.metadata.request_id
                ),
                message=(
                    "Le workflow d'analyse "
                    "n'a pas pu terminer son exécution."
                ),
                cause=error
            ) from error

        return self._normalize_graph_result(
            result
        )

    async def _stream_graph(
        self,
        state: ChessAnalysisState,
        config: RunnableConfig
    ) -> AsyncIterator[GraphStreamPart]:
        """Exécute le workflow en diffusant ses événements."""

        graph = self._get_graph()

        try:
            async for part in graph.astream(
                state,
                config=config,
                stream_mode=[
                    "updates",
                    "custom",
                    "values"
                ],
                version="v2"
            ):
                if not isinstance(
                    part,
                    dict
                ):
                    continue

                yield dict(
                    part
                )

        except WorkflowExecutionError:
            raise

        except Exception as error:
            logger.exception(
                "Échec du streaming du workflow LangGraph."
            )

            raise WorkflowExecutionError(
                context=ErrorContext(
                    workflow="chess_analysis",
                    service="analysis",
                    operation="stream_graph",
                    request_id=state.metadata.request_id
                ),
                message=(
                    "Le workflow d'analyse "
                    "n'a pas pu terminer son exécution."
                ),
                cause=error
            ) from error

    # Progression

    def _extract_step_progress_event(
        self,
        update: dict[str, Any],
        *,
        request_id: str
    ) -> AnalysisProgressEvent | None:
        """Construit un événement depuis une mise à jour LangGraph."""

        current_step = update.get(
            "current_step"
        )

        if current_step is None:
            return None

        try:
            step = WorkflowStep(
                current_step
            )

        except ValueError:
            logger.warning(
                "Étape inconnue reçue pendant l'analyse %s : %s.",
                request_id,
                current_step
            )

            return None

        raw_completed_steps = update.get(
            "completed_steps",
            []
        )

        completed_steps: list[
            WorkflowStep
        ] = []

        for completed_step in raw_completed_steps:

            try:
                normalized_step = WorkflowStep(
                    completed_step
                )

            except ValueError:
                continue

            if (
                normalized_step
                not in completed_steps
            ):
                completed_steps.append(
                    normalized_step
                )

        return AnalysisProgressEvent(
            request_id=request_id,
            step=step,
            status=WorkflowStepStatus.COMPLETED,
            completed_steps=completed_steps
        )

    def _extract_service_progress_event(
        self,
        data: dict[str, Any],
        *,
        request_id: str,
        completed_steps: list[WorkflowStep]
    ) -> AnalysisProgressEvent | None:
        """Construit un événement depuis une progression de service."""

        try:
            step = WorkflowStep(
                data["step"]
            )

            status = WorkflowStepStatus(
                data["status"]
            )

            raw_service = data.get(
                "service"
            )

            service = (
                ServiceType(
                    raw_service
                )
                if raw_service is not None
                else None
            )

        except (
            KeyError,
            TypeError,
            ValueError
        ):
            logger.warning(
                "Événement de progression invalide "
                "reçu pendant l'analyse %s.",
                request_id
            )

            return None

        message = data.get(
            "message"
        )

        return AnalysisProgressEvent(
            request_id=request_id,
            step=step,
            service=service,
            status=status,
            completed_steps=list(
                completed_steps
            ),
            message=(
                message
                if isinstance(
                    message,
                    str
                )
                else None
            )
        )

    def _extract_node_updates(
        self,
        part: GraphStreamPart
    ) -> list[dict[str, Any]]:
        """Extrait les mises à jour de nœuds d'un événement LangGraph."""

        if (
            part.get("type")
            != "updates"
        ):
            return []

        data = part.get(
            "data"
        )

        if not isinstance(
            data,
            dict
        ):
            return []

        return [
            node_update
            for node_update
            in data.values()
            if isinstance(
                node_update,
                dict
            )
        ]

    def _extract_state_value(
        self,
        part: GraphStreamPart
    ) -> ChessAnalysisState | None:
        """Extrait un état complet diffusé par LangGraph."""

        if (
            part.get("type")
            != "values"
        ):
            return None

        data = part.get(
            "data"
        )

        logger.debug(
            "État LangGraph reçu via values : type=%s.",
            type(data).__name__
        )

        if isinstance(
            data,
            ChessAnalysisState
        ):
            return data

        if not isinstance(
            data,
            dict
        ):
            logger.warning(
                "État LangGraph ignoré : type inattendu %s.",
                type(data).__name__
            )

            return None

        try:
            return ChessAnalysisState.model_validate(
                data
            )

        except Exception:
            logger.exception(
                "État LangGraph invalide reçu via values."
            )

            return None

    # Erreurs

    def _extract_error_message(
        self,
        state: ChessAnalysisState
    ) -> str | None:
        """Retourne le dernier message d'erreur du workflow."""

        if not state.errors:
            return None

        return state.errors[
            -1
        ].message

    # Documents

    def _extract_documents(
        self,
        state: ChessAnalysisState
    ) -> list:
        """Retourne les documents récupérés par le workflow."""

        retrieval_context = (
            state.retrieval_context
        )

        if retrieval_context is None:
            return []

        return [
            retrieved_document.document
            for retrieved_document
            in retrieval_context.documents
        ]

    # Réponse

    def _build_response(
        self,
        state: ChessAnalysisState
    ) -> AnalysisResponse:
        """Construit la réponse API depuis l'état final."""

        return AnalysisResponse(
            status=state.status,
            fen=state.fen,
            opening=state.opening,
            evaluation=state.evaluation,
            documents=self._extract_documents(
                state
            ),
            videos=list(
                state.videos
            ),
            explanation=state.response,
            analysis_id=state.analysis_id,
            error=self._extract_error_message(
                state
            )
        )

    # Analyse

    async def analyze(
        self,
        request: AnalysisRequest,
        *,
        request_id: str | None = None
    ) -> AnalysisResponse:
        """Exécute une analyse échiquéenne complète."""

        effective_request_id = (
            request_id
            if request_id is not None
            else str(
                uuid4()
            )
        )

        started_at = datetime.now(
            UTC
        )

        started_counter = perf_counter()

        logger.info(
            "Démarrage de l'analyse %s.",
            effective_request_id
        )

        logger.debug(
            "Analyse %s : %s coup(s) transmis au workflow.",
            effective_request_id,
            len(
                request.moves
            )
        )

        # État initial

        initial_state = self._build_initial_state(
            request,
            request_id=effective_request_id,
            started_at=started_at
        )

        # Configuration

        config = self._build_config(
            thread_id=effective_request_id
        )

        # Workflow

        final_state = await self._run_graph(
            initial_state,
            config
        )

        # Métadonnées finales

        finished_at = datetime.now(
            UTC
        )

        duration_ms = round(
            (
                perf_counter()
                - started_counter
            ) * 1_000,
            2
        )

        final_state = final_state.model_copy(
            update={
                "metadata": self._complete_metadata(
                    final_state,
                    finished_at=finished_at,
                    duration_ms=duration_ms
                )
            }
        )

        # Diagnostic

        logger.debug(
            (
                "Analyse %s : état final "
                "status=%s, opening=%s, "
                "evaluation=%s, documents=%d, videos=%d, "
                "warnings=%d, errors=%d."
            ),
            effective_request_id,
            final_state.status.value,
            final_state.opening is not None,
            final_state.evaluation is not None,
            (
                len(
                    final_state
                    .retrieval_context
                    .documents
                )
                if final_state.retrieval_context
                is not None
                else 0
            ),
            len(
                final_state.videos
            ),
            len(
                final_state.warnings
            ),
            len(
                final_state.errors
            )
        )

        # Statistiques

        self._analysis_count += 1

        self._last_analysis_duration_ms = (
            duration_ms
        )

        logger.info(
            "Analyse %s terminée en %.2f ms "
            "avec le statut %s.",
            effective_request_id,
            duration_ms,
            final_state.status.value
        )

        # Réponse

        return self._build_response(
            final_state
        )

    async def stream_analysis(
        self,
        request: AnalysisRequest,
        *,
        request_id: str | None = None
    ) -> AsyncIterator[AnalysisStreamEvent]:
        """Exécute une analyse en diffusant sa progression."""

        effective_request_id = (
            request_id
            if request_id is not None
            else str(
                uuid4()
            )
        )

        started_at = datetime.now(
            UTC
        )

        started_counter = perf_counter()

        logger.info(
            "Démarrage du streaming de l'analyse %s.",
            effective_request_id
        )

        initial_state = self._build_initial_state(
            request,
            request_id=effective_request_id,
            started_at=started_at
        )

        config = self._build_config(
            thread_id=effective_request_id
        )

        completed_steps: list[
            WorkflowStep
        ] = []

        latest_state: ChessAnalysisState | None = None

        async for part in self._stream_graph(
            initial_state,
            config
        ):
            part_type = part.get(
                "type"
            )

            # État complet

            if (
                part_type
                == "values"
            ):
                state_value = (
                    self._extract_state_value(
                        part
                    )
                )

                if (
                    state_value
                    is not None
                ):
                    latest_state = (
                        state_value
                    )

                continue

            # Progression d'un service

            if (
                part_type
                == "custom"
            ):
                data = part.get(
                    "data"
                )

                if not isinstance(
                    data,
                    dict
                ):
                    continue

                event = (
                    self._extract_service_progress_event(
                        data,
                        request_id=effective_request_id,
                        completed_steps=completed_steps
                    )
                )

                if event is None:
                    continue

                logger.debug(
                    (
                        "Analyse %s : service=%s "
                        "step=%s status=%s."
                    ),
                    effective_request_id,
                    (
                        event.service.value
                        if event.service
                        is not None
                        else None
                    ),
                    event.step.value,
                    event.status.value
                )

                yield event

                continue

            # Progression du workflow

            if (
                part_type
                != "updates"
            ):
                continue

            for update in (
                self._extract_node_updates(
                    part
                )
            ):
                event = (
                    self._extract_step_progress_event(
                        update,
                        request_id=effective_request_id
                    )
                )

                if event is None:
                    continue

                completed_steps = list(
                    event.completed_steps
                )

                logger.debug(
                    (
                        "Analyse %s : étape=%s "
                        "status=%s."
                    ),
                    effective_request_id,
                    event.step.value,
                    event.status.value
                )

                yield event

        # Validation de l'état final

        if latest_state is None:
            raise WorkflowStateError(
                context=ErrorContext(
                    workflow="chess_analysis",
                    service="analysis",
                    operation="stream_analysis",
                    request_id=effective_request_id
                ),
                message=(
                    "Le streaming s'est terminé sans "
                    "état final exploitable."
                )
            )

        # Métadonnées finales

        finished_at = datetime.now(
            UTC
        )

        duration_ms = round(
            (
                perf_counter()
                - started_counter
            ) * 1_000,
            2
        )

        final_state = latest_state.model_copy(
            update={
                "metadata": self._complete_metadata(
                    latest_state,
                    finished_at=finished_at,
                    duration_ms=duration_ms
                )
            }
        )

        # Diagnostic

        logger.debug(
            (
                "Streaming %s : état final "
                "status=%s, opening=%s, "
                "evaluation=%s, documents=%d, videos=%d, "
                "warnings=%d, errors=%d."
            ),
            effective_request_id,
            final_state.status.value,
            final_state.opening is not None,
            final_state.evaluation is not None,
            (
                len(
                    final_state
                    .retrieval_context
                    .documents
                )
                if final_state.retrieval_context
                is not None
                else 0
            ),
            len(
                final_state.videos
            ),
            len(
                final_state.warnings
            ),
            len(
                final_state.errors
            )
        )

        # Statistiques

        self._analysis_count += 1

        self._last_analysis_duration_ms = (
            duration_ms
        )

        logger.info(
            "Streaming de l'analyse %s terminé "
            "en %.2f ms avec le statut %s.",
            effective_request_id,
            duration_ms,
            final_state.status.value
        )

        # Résultat final

        yield AnalysisCompletedEvent(
            request_id=effective_request_id,
            analysis=self._build_response(
                final_state
            )
        )

    # État

    def is_ready(
        self
    ) -> bool:
        """Indique si le service peut exécuter le workflow."""

        return (
            self._graph
            is not None
        )

    def get_analysis_count(
        self
    ) -> int:
        """Retourne le nombre d'analyses exécutées."""

        return self._analysis_count

    def get_last_analysis_duration(
        self
    ) -> float | None:
        """Retourne la durée de la dernière analyse."""

        return (
            self._last_analysis_duration_ms
        )

    # Santé

    async def ping(
        self
    ) -> bool:
        """Vérifie que le service d'analyse est disponible."""

        return self.is_ready()

    async def health(
        self
    ) -> dict[str, Any]:
        """Retourne l'état de santé du service."""

        available = await self.ping()

        return {
            "service": "analysis",
            "available": available,
            "is_ready": self.is_ready(),
            "analysis_count": self.get_analysis_count(),
            "last_analysis_duration_ms": (
                self.get_last_analysis_duration()
            )
        }