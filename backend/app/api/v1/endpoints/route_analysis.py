"""Routes d'analyse échiquéenne.

Ce module expose les endpoints permettant d'analyser une position
avec le workflow LangGraph.

Il ne contient aucune logique métier.

La validation de la position, l'exécution du workflow,
les analyses théorique et moteur, la recherche documentaire,
la sélection de vidéos, la génération de la réponse et la persistance
sont déléguées à AnalysisService.
"""

from __future__ import annotations

from collections.abc import AsyncIterator

from fastapi import APIRouter, Request, status
from fastapi.responses import StreamingResponse

from app.api.responses import COMMON_ERROR_RESPONSES
from app.api.sse import format_sse_event
from app.api.v1.dependencies.services import AnalysisServiceDependency
from app.schemas.analysis.analysis import AnalysisRequest, AnalysisResponse
from app.schemas.analysis.progress import AnalysisCompletedEvent, AnalysisProgressEvent

# Routeur

router = APIRouter()


# Analyse


@router.post(
    "/position",
    response_model=AnalysisResponse,
    status_code=status.HTTP_200_OK,
    summary="Analyser une position",
    description=(
        "Analyse une position FEN avec le workflow LangGraph et retourne "
        "les résultats théoriques, moteur, documentaires et pédagogiques."
    ),
    response_description="Résultat complet de l'analyse de la position.",
    responses=COMMON_ERROR_RESPONSES
)
async def analyze_position(
    request: Request,
    payload: AnalysisRequest,
    service: AnalysisServiceDependency
) -> AnalysisResponse:
    """Analyse une position avec le workflow de l'agent."""
    request_id = request.state.request_id

    return await service.analyze(
        payload,
        request_id=request_id
    )


@router.post(
    "/stream",
    status_code=status.HTTP_200_OK,
    summary="Analyser une position avec progression",
    description=(
        "Exécute le workflow d'analyse et diffuse sa progression "
        "en temps réel via Server-Sent Events."
    ),
    response_description="Flux SSE de progression de l'analyse.",
    responses=COMMON_ERROR_RESPONSES,
)
async def stream_analysis(
    request: Request,
    payload: AnalysisRequest,
    service: AnalysisServiceDependency
) -> StreamingResponse:
    """Diffuse la progression et le résultat final d'une analyse."""
    request_id = request.state.request_id

    async def event_generator() -> AsyncIterator[str]:
        async for event in service.stream_analysis(
            payload,
            request_id=request_id
        ):
            if isinstance(
                event,
                AnalysisProgressEvent
            ):
                yield format_sse_event(
                    event="progress",
                    data=event.model_dump_json()
                )
                continue

            if isinstance(
                event,
                AnalysisCompletedEvent
            ):
                yield format_sse_event(
                    event="completed",
                    data=event.model_dump_json()
                )

    return StreamingResponse(
        event_generator(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no"
        }
    )