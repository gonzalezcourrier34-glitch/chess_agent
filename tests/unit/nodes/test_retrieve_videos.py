"""Tests unitaires du nœud de récupération des vidéos pédagogiques."""

from __future__ import annotations

from types import SimpleNamespace
from typing import cast
from unittest.mock import AsyncMock, MagicMock

import chess
import pytest
from langchain_core.runnables import RunnableConfig

from app.adapters.youtube_service import YoutubeService
from app.agent.nodes.F_retrieve_videos import (
    SEARCH_SOURCE_LICHESS,
    SEARCH_SOURCE_WIKICHESS,
    YOUTUBE_SERVICE_KEY,
    VideoSearchContext,
    _build_completed_update,
    _build_error_update,
    _build_lichess_search_context,
    _build_missing_service_update,
    _build_search_context,
    _build_search_request,
    _build_success_update,
    _build_unexpected_error_update,
    _build_video_summary,
    _build_videos_summary,
    _build_warning_update,
    _build_wikichess_search_context,
    _build_workflow_context,
    _build_youtube_warning_update,
    _get_opening_identity,
    _get_partial_success_status,
    _get_success_status,
    _get_wikichess_identity,
    _get_youtube_service,
    _normalize_text,
    _select_videos,
    retrieve_videos,
)
from app.agent.state import ChessAnalysisState
from app.core.config import settings
from app.core.constants import (
    ERROR_CONFIGURATION,
    ERROR_UNEXPECTED,
    ERROR_YOUTUBE_UNAVAILABLE,
)
from app.core.exceptions import YoutubeError
from app.schemas.chess.opening import (
    Opening,
    OpeningDetails,
)
from app.schemas.common.enums import (
    AnalysisStatus,
    VideoPlatform,
    WorkflowStep,
)
from app.schemas.common.error import (
    WorkflowError,
    WorkflowWarning,
)
from app.schemas.media.video import (
    Video,
    VideoChannel,
    VideoCollection,
    VideoRecommendation,
    VideoSearchRequest,
)
from app.schemas.rag.document import RetrievalContext


# Configuration

STARTING_FEN = chess.STARTING_FEN

VIDEO_ID = "video-1"

VIDEO_URL = (
    "https://www.youtube.com/watch?v=video-1"
)


# Construction des données de test

def build_opening(
    *,
    name: str = "Ruy Lopez",
    eco: str = "C60",
) -> OpeningDetails:
    """Construit une ouverture minimale."""

    return OpeningDetails(
        opening=Opening(
            name=name,
            eco=eco,
            moves=[
                "e4",
                "e5",
                "Nf3",
                "Nc6",
                "Bb5",
            ],
        ),
    )


def build_video(
    *,
    identifier: str = VIDEO_ID,
    title: str = "Ruy Lopez Chess Opening",
) -> Video:
    """Construit une vidéo conforme au schéma métier."""

    return Video(
        id=identifier,
        platform=VideoPlatform.YOUTUBE,
        title=title,
        description="Guide pédagogique.",
        url=(
            "https://www.youtube.com/watch?v="
            f"{identifier}"
        ),
        thumbnail_url=(
            "https://example.test/thumbnail.jpg"
        ),
        duration_seconds=630,
        view_count=1000,
        like_count=100,
        comment_count=10,
        published_at="2026-08-18T10:00:00Z",
        channel=VideoChannel(
            id="channel-1",
            name="Chess Channel",
            url=(
                "https://www.youtube.com/"
                "@chess-channel"
            ),
            subscribers=50000,
        ),
        language="fr",
    )


def build_recommendation(
    *,
    identifier: str = VIDEO_ID,
    score: float = 0.95,
) -> VideoRecommendation:
    """Construit une recommandation vidéo."""

    return VideoRecommendation(
        video=build_video(
            identifier=identifier,
        ),
        relevance_score=score,
        reason="Vidéo pertinente.",
        matching_topics=[
            "Ruy",
            "Lopez",
        ],
    )


def build_collection(
    *,
    recommendations: list[
        VideoRecommendation
    ] | None = None,
) -> VideoCollection:
    """Construit une réponse du YoutubeService."""

    values = (
        recommendations
        if recommendations is not None
        else [
            build_recommendation(),
        ]
    )

    return VideoCollection(
        query="Ruy Lopez C60",
        total_results=len(values),
        videos=values,
    )


def build_wikichess_context(
    *,
    title: str = "Ruy Lopez",
    wikichess_title: str | None = (
        "Ruy Lopez Opening"
    ),
    eco: str | None = "C60",
) -> RetrievalContext:
    """Construit le minimum nécessaire au nœud pour Wikichess.

    Le test cible uniquement la lecture de l'identité documentaire.
    Les sous-objets sont donc construits sans réinventer le reste du
    contrat RAG.
    """

    metadata = SimpleNamespace(
        wikichess_title=wikichess_title,
        eco=eco,
    )

    document = SimpleNamespace(
        title=title,
        metadata=metadata,
    )

    retrieved_document = SimpleNamespace(
        document=document,
    )

    return cast(
        RetrievalContext,
        SimpleNamespace(
            documents=[
                retrieved_document,
            ],
        ),
    )


# Fixtures

@pytest.fixture
def state() -> ChessAnalysisState:
    """Construit un état minimal du workflow."""

    return ChessAnalysisState(
        fen=STARTING_FEN,
    )


@pytest.fixture
def opening_state(
    state: ChessAnalysisState,
) -> ChessAnalysisState:
    """Construit un état avec ouverture Lichess."""

    return state.model_copy(
        update={
            "opening": build_opening(),
        }
    )


@pytest.fixture
def video() -> Video:
    """Construit une vidéo de référence."""

    return build_video()


# Service

def test_get_youtube_service_returns_configured_service(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Vérifie la récupération du YoutubeService."""

    service = MagicMock(
        spec=YoutubeService,
    )

    configured_service = MagicMock(
        return_value=service,
    )

    monkeypatch.setattr(
        "app.agent.nodes.F_retrieve_videos."
        "get_configured_service",
        configured_service,
    )

    config = cast(
        RunnableConfig,
        {},
    )

    result = _get_youtube_service(
        config
    )

    assert result is service

    configured_service.assert_called_once_with(
        config,
        YOUTUBE_SERVICE_KEY,
        expected_type=YoutubeService,
    )


def test_get_youtube_service_returns_none_when_missing(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Vérifie l'absence du service YouTube."""

    monkeypatch.setattr(
        "app.agent.nodes.F_retrieve_videos."
        "get_configured_service",
        MagicMock(
            return_value=None
        ),
    )

    result = _get_youtube_service(
        cast(
            RunnableConfig,
            {},
        )
    )

    assert result is None


def test_get_youtube_service_rejects_invalid_type(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Vérifie le rejet d'un service d'un autre type."""

    monkeypatch.setattr(
        "app.agent.nodes.F_retrieve_videos."
        "get_configured_service",
        MagicMock(
            return_value=object()
        ),
    )

    result = _get_youtube_service(
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
    """Vérifie le statut après une recherche réussie."""

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
    """Vérifie le statut d'une recherche dégradée."""

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
            "  Ruy Lopez  ",
            "Ruy Lopez",
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
        (
            True,
            None,
        ),
    ],
)
def test_normalize_text(
    value: object,
    expected: str | None,
) -> None:
    """Vérifie la normalisation du texte."""

    assert (
        _normalize_text(value)
        == expected
    )


# Identité Lichess

def test_get_opening_identity_without_opening(
    state: ChessAnalysisState,
) -> None:
    """Vérifie l'absence d'ouverture."""

    assert (
        _get_opening_identity(state)
        == (
            None,
            None,
        )
    )


def test_get_opening_identity(
    opening_state: ChessAnalysisState,
) -> None:
    """Vérifie le nom et le code ECO."""

    assert (
        _get_opening_identity(
            opening_state
        )
        == (
            "Ruy Lopez",
            "C60",
        )
    )


# Identité Wikichess

def test_get_wikichess_identity_without_context(
    state: ChessAnalysisState,
) -> None:
    """Vérifie l'absence de document Wikichess."""

    assert (
        _get_wikichess_identity(state)
        == (
            None,
            None,
        )
    )


def test_get_wikichess_identity_with_empty_context(
    state: ChessAnalysisState,
) -> None:
    """Vérifie un contexte sans document."""

    context = cast(
        RetrievalContext,
        SimpleNamespace(
            documents=[],
        ),
    )

    current_state = state.model_copy(
        update={
            "retrieval_context": context,
        }
    )

    assert (
        _get_wikichess_identity(
            current_state
        )
        == (
            None,
            None,
        )
    )


def test_get_wikichess_identity_prefers_wikichess_title(
    state: ChessAnalysisState,
) -> None:
    """Vérifie la priorité du titre Wikichess."""

    context = build_wikichess_context(
        title="Titre générique",
        wikichess_title="Ruy Lopez Wikichess",
        eco="C60",
    )

    current_state = state.model_copy(
        update={
            "retrieval_context": context,
        }
    )

    assert (
        _get_wikichess_identity(
            current_state
        )
        == (
            "Ruy Lopez Wikichess",
            "C60",
        )
    )


def test_get_wikichess_identity_falls_back_to_document_title(
    state: ChessAnalysisState,
) -> None:
    """Vérifie le repli sur le titre du document."""

    context = build_wikichess_context(
        title="Ruy Lopez",
        wikichess_title=None,
        eco=None,
    )

    current_state = state.model_copy(
        update={
            "retrieval_context": context,
        }
    )

    assert (
        _get_wikichess_identity(
            current_state
        )
        == (
            "Ruy Lopez",
            None,
        )
    )


# Contexte Lichess

def test_build_lichess_search_context(
    opening_state: ChessAnalysisState,
) -> None:
    """Vérifie le contexte construit depuis Lichess."""

    context = (
        _build_lichess_search_context(
            opening_state
        )
    )

    assert context is not None

    assert context == VideoSearchContext(
        query="Ruy Lopez C60",
        title="Ruy Lopez",
        eco="C60",
        source=SEARCH_SOURCE_LICHESS,
    )


def test_build_lichess_search_context_without_opening(
    state: ChessAnalysisState,
) -> None:
    """Vérifie l'absence de contexte Lichess."""

    assert (
        _build_lichess_search_context(
            state
        )
        is None
    )


# Contexte Wikichess

def test_build_wikichess_search_context(
    state: ChessAnalysisState,
) -> None:
    """Vérifie le contexte construit depuis Wikichess."""

    current_state = state.model_copy(
        update={
            "retrieval_context": (
                build_wikichess_context()
            ),
        }
    )

    context = (
        _build_wikichess_search_context(
            current_state
        )
    )

    assert context is not None

    assert context.query == (
        "Ruy Lopez Opening C60"
    )

    assert (
        context.title
        == "Ruy Lopez Opening"
    )

    assert context.eco == "C60"

    assert (
        context.source
        == SEARCH_SOURCE_WIKICHESS
    )


def test_build_wikichess_search_context_uses_opening_eco(
    opening_state: ChessAnalysisState,
) -> None:
    """Vérifie le repli ECO sur Lichess."""

    current_state = opening_state.model_copy(
        update={
            "opening": build_opening(
                name="Ruy Lopez",
                eco="C60",
            ),
            "retrieval_context": (
                build_wikichess_context(
                    wikichess_title=(
                        "Ruy Lopez Wikichess"
                    ),
                    eco=None,
                )
            ),
        }
    )

    context = (
        _build_wikichess_search_context(
            current_state
        )
    )

    assert context is not None
    assert context.eco == "C60"

    assert (
        context.query
        == "Ruy Lopez Wikichess C60"
    )


def test_build_wikichess_search_context_without_title(
    state: ChessAnalysisState,
) -> None:
    """Vérifie l'absence de contexte Wikichess exploitable."""

    context = build_wikichess_context(
        title="   ",
        wikichess_title=None,
        eco="C60",
    )

    current_state = state.model_copy(
        update={
            "retrieval_context": context,
        }
    )

    assert (
        _build_wikichess_search_context(
            current_state
        )
        is None
    )


# Choix du contexte

def test_build_search_context_prefers_lichess(
    opening_state: ChessAnalysisState,
) -> None:
    """Vérifie que Lichess reste prioritaire."""

    current_state = opening_state.model_copy(
        update={
            "retrieval_context": (
                build_wikichess_context(
                    wikichess_title=(
                        "Titre Wikichess"
                    ),
                    eco="C61",
                )
            ),
        }
    )

    context = _build_search_context(
        current_state
    )

    assert context is not None

    assert (
        context.source
        == SEARCH_SOURCE_LICHESS
    )

    assert context.title == "Ruy Lopez"
    assert context.eco == "C60"


def test_build_search_context_uses_wikichess_fallback(
    state: ChessAnalysisState,
) -> None:
    """Vérifie le repli sur Wikichess."""

    current_state = state.model_copy(
        update={
            "retrieval_context": (
                build_wikichess_context()
            ),
        }
    )

    context = _build_search_context(
        current_state
    )

    assert context is not None

    assert (
        context.source
        == SEARCH_SOURCE_WIKICHESS
    )


def test_build_search_context_returns_none(
    state: ChessAnalysisState,
) -> None:
    """Vérifie l'absence totale de contexte."""

    assert (
        _build_search_context(state)
        is None
    )


# Requête YouTube

def test_build_search_request() -> None:
    """Vérifie le contrat envoyé au YoutubeService."""

    context = VideoSearchContext(
        query="Ruy Lopez C60",
        title="Ruy Lopez",
        eco="C60",
        source=SEARCH_SOURCE_LICHESS,
    )

    request = _build_search_request(
        context
    )

    assert isinstance(
        request,
        VideoSearchRequest,
    )

    assert (
        request.query
        == "Ruy Lopez C60"
    )

    assert (
        request.max_results
        == settings.youtube_search_max_results
    )

    assert (
        request.language
        == settings.youtube_default_language
    )


# Sélection

def test_select_videos() -> None:
    """Vérifie l'extraction des vidéos des recommandations."""

    recommendations = [
        build_recommendation(
            identifier=f"video-{index}",
            score=0.9,
        )
        for index in range(
            settings.max_selected_videos + 2
        )
    ]

    collection = build_collection(
        recommendations=recommendations,
    )

    videos = _select_videos(
        collection
    )

    assert (
        len(videos)
        == settings.max_selected_videos
    )

    assert all(
        isinstance(video, Video)
        for video in videos
    )

    assert (
        videos[0].id
        == "video-0"
    )


def test_select_videos_returns_empty_list() -> None:
    """Vérifie une collection vide."""

    collection = VideoCollection(
        query="Ruy Lopez",
        total_results=0,
        videos=[],
    )

    assert (
        _select_videos(collection)
        == []
    )


# Résumé vidéo

def test_build_video_summary(
    video: Video,
) -> None:
    """Vérifie le résumé complet d'une vidéo."""

    summary = _build_video_summary(
        video,
        1,
    )

    assert "Vidéo 1 :" in summary

    assert (
        "- Titre : Ruy Lopez Chess Opening"
        in summary
    )

    assert (
        "- Chaîne : Chess Channel"
        in summary
    )

    assert (
        f"- URL : {VIDEO_URL}"
        in summary
    )

    assert "- Miniature :" in summary

    assert (
        "- Publication : "
        "2026-08-18T10:00:00Z"
        in summary
    )

    assert "- Langue : fr" in summary

    assert (
        "- Durée : 630 secondes"
        in summary
    )


def test_build_video_summary_without_optional_values() -> None:
    """Vérifie un résumé sans informations facultatives."""

    video = Video(
        id="video-minimal",
        title="Chess Opening",
        url=(
            "https://www.youtube.com/watch?"
            "v=video-minimal"
        ),
        channel=VideoChannel(
            name="Chess Channel",
        ),
    )

    summary = _build_video_summary(
        video,
        2,
    )

    assert "Vidéo 2 :" in summary
    assert "Miniature" not in summary
    assert "Publication" not in summary
    assert "Langue" not in summary
    assert "Durée" not in summary


def test_build_videos_summary(
    video: Video,
) -> None:
    """Vérifie le résumé de plusieurs vidéos."""

    second_video = build_video(
        identifier="video-2",
        title="Italian Game Guide",
    )

    summary = _build_videos_summary(
        [
            video,
            second_video,
        ]
    )

    assert summary is not None
    assert "Vidéo 1 :" in summary
    assert "Vidéo 2 :" in summary

    assert (
        "Ruy Lopez Chess Opening"
        in summary
    )

    assert (
        "Italian Game Guide"
        in summary
    )


def test_build_videos_summary_returns_none() -> None:
    """Vérifie l'absence de vidéos."""

    assert (
        _build_videos_summary([])
        is None
    )


# Contexte du workflow

def test_build_workflow_context(
    state: ChessAnalysisState,
    video: Video,
) -> None:
    """Vérifie l'enrichissement du WorkflowContext."""

    context = _build_workflow_context(
        state,
        [
            video,
        ],
    )

    assert (
        context.videos_summary
        is not None
    )

    assert (
        "Ruy Lopez Chess Opening"
        in context.videos_summary
    )

    assert (
        state.workflow_context.videos_summary
        is None
    )


def test_build_workflow_context_without_videos(
    state: ChessAnalysisState,
) -> None:
    """Vérifie le contexte sans vidéo."""

    context = _build_workflow_context(
        state,
        (),
    )

    assert (
        context.videos_summary
        is None
    )


# Mises à jour

def test_build_completed_update(
    state: ChessAnalysisState,
    video: Video,
) -> None:
    """Vérifie une étape YouTube terminée."""

    update = _build_completed_update(
        state,
        status=AnalysisStatus.SUCCESS,
        videos=[
            video,
        ],
        warnings=(),
    )

    assert (
        update["status"]
        == AnalysisStatus.SUCCESS
    )

    assert (
        update["current_step"]
        == WorkflowStep.RETRIEVE_VIDEOS
    )

    assert (
        WorkflowStep.RETRIEVE_VIDEOS
        in update["completed_steps"]
    )

    assert update["videos"] == [
        video,
    ]

    assert (
        update[
            "workflow_context"
        ].videos_summary
        is not None
    )

    assert update["errors"] == []
    assert update["warnings"] == []


def test_build_success_update(
    state: ChessAnalysisState,
    video: Video,
) -> None:
    """Vérifie une recherche réussie."""

    update = _build_success_update(
        state,
        [
            video,
        ],
    )

    assert (
        update["status"]
        == AnalysisStatus.SUCCESS
    )

    assert update["videos"] == [
        video,
    ]


def test_build_success_update_preserves_partial_status(
    state: ChessAnalysisState,
) -> None:
    """Vérifie la conservation d'un statut dégradé."""

    current_state = state.model_copy(
        update={
            "status": (
                AnalysisStatus.PARTIAL_SUCCESS
            ),
        }
    )

    update = _build_success_update(
        current_state,
        (),
    )

    assert (
        update["status"]
        == AnalysisStatus.PARTIAL_SUCCESS
    )


def test_build_warning_update(
    state: ChessAnalysisState,
) -> None:
    """Vérifie une indisponibilité récupérable."""

    warning = WorkflowWarning(
        step=WorkflowStep.RETRIEVE_VIDEOS,
        code=ERROR_YOUTUBE_UNAVAILABLE,
        message="YouTube indisponible.",
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
        WorkflowStep.RETRIEVE_VIDEOS
        in update["completed_steps"]
    )

    assert update["videos"] == []

    assert update["warnings"] == [
        warning,
    ]

    assert (
        update[
            "workflow_context"
        ].videos_summary
        is None
    )


def test_build_warning_update_preserves_failed_status(
    state: ChessAnalysisState,
) -> None:
    """Vérifie qu'un échec antérieur reste prioritaire."""

    failed_state = state.model_copy(
        update={
            "status": AnalysisStatus.FAILED,
        }
    )

    warning = WorkflowWarning(
        step=WorkflowStep.RETRIEVE_VIDEOS,
        code=ERROR_YOUTUBE_UNAVAILABLE,
        message="YouTube indisponible.",
    )

    update = _build_warning_update(
        failed_state,
        warning,
    )

    assert (
        update["status"]
        == AnalysisStatus.FAILED
    )


def test_build_error_update(
    state: ChessAnalysisState,
) -> None:
    """Vérifie une erreur bloquante."""

    error = WorkflowError(
        step=WorkflowStep.RETRIEVE_VIDEOS,
        code=ERROR_UNEXPECTED,
        message="Erreur.",
        recoverable=False,
    )

    update = _build_error_update(
        state,
        error,
    )

    assert (
        update["status"]
        == AnalysisStatus.FAILED
    )

    assert (
        update["current_step"]
        == WorkflowStep.RETRIEVE_VIDEOS
    )

    assert (
        WorkflowStep.RETRIEVE_VIDEOS
        not in update["completed_steps"]
    )

    assert update["videos"] == []
    assert update["errors"] == [error]

    assert (
        update[
            "workflow_context"
        ].videos_summary
        is None
    )


def test_build_missing_service_update(
    state: ChessAnalysisState,
) -> None:
    """Vérifie l'erreur de configuration."""

    update = _build_missing_service_update(
        state
    )

    assert (
        update["status"]
        == AnalysisStatus.FAILED
    )

    assert (
        update["errors"][0].code
        == ERROR_CONFIGURATION
    )

    assert (
        update["errors"][0].recoverable
        is False
    )


def test_build_youtube_warning_update(
    state: ChessAnalysisState,
) -> None:
    """Vérifie la conversion d'une erreur YouTube."""

    error = YoutubeError(
        message="Quota YouTube indisponible.",
    )

    update = _build_youtube_warning_update(
        state,
        error,
    )

    assert (
        update["status"]
        == AnalysisStatus.PARTIAL_SUCCESS
    )

    assert (
        update["warnings"][0].code
        == ERROR_YOUTUBE_UNAVAILABLE
    )

    assert (
        update["warnings"][0].message
        == str(error)
    )


def test_build_unexpected_error_update(
    state: ChessAnalysisState,
) -> None:
    """Vérifie une erreur inattendue."""

    update = _build_unexpected_error_update(
        state
    )

    assert (
        update["status"]
        == AnalysisStatus.FAILED
    )

    assert (
        update["errors"][0].code
        == ERROR_UNEXPECTED
    )

    assert (
        update["errors"][0].recoverable
        is False
    )


# Nœud public

@pytest.mark.asyncio
async def test_retrieve_videos_skips_without_context(
    state: ChessAnalysisState,
) -> None:
    """Vérifie que YouTube est ignoré sans contexte."""

    update = await retrieve_videos(
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
        WorkflowStep.RETRIEVE_VIDEOS
        in update["completed_steps"]
    )

    assert update["videos"] == []

    assert (
        update[
            "workflow_context"
        ].videos_summary
        is None
    )


@pytest.mark.asyncio
async def test_retrieve_videos_missing_service(
    opening_state: ChessAnalysisState,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Vérifie l'absence du YoutubeService."""

    get_service = MagicMock(
        return_value=None,
    )

    emit_progress = MagicMock()

    monkeypatch.setattr(
        "app.agent.nodes.F_retrieve_videos."
        "_get_youtube_service",
        get_service,
    )

    monkeypatch.setattr(
        "app.agent.nodes.F_retrieve_videos."
        "emit_progress",
        emit_progress,
    )

    update = await retrieve_videos(
        opening_state,
        cast(
            RunnableConfig,
            {},
        ),
    )

    assert (
        update["status"]
        == AnalysisStatus.FAILED
    )

    assert (
        update["errors"][0].code
        == ERROR_CONFIGURATION
    )

    assert update["videos"] == []

    emit_progress.assert_called_once()


@pytest.mark.asyncio
async def test_retrieve_videos_success(
    opening_state: ChessAnalysisState,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Vérifie une recherche YouTube réussie."""

    collection = build_collection()

    search_videos = AsyncMock(
        return_value=collection,
    )

    service = MagicMock(
        spec=YoutubeService,
    )

    service.search_videos = search_videos

    emit_progress = MagicMock()

    monkeypatch.setattr(
        "app.agent.nodes.F_retrieve_videos."
        "_get_youtube_service",
        MagicMock(
            return_value=service,
        ),
    )

    monkeypatch.setattr(
        "app.agent.nodes.F_retrieve_videos."
        "emit_progress",
        emit_progress,
    )

    update = await retrieve_videos(
        opening_state,
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
        WorkflowStep.RETRIEVE_VIDEOS
        in update["completed_steps"]
    )

    assert len(
        update["videos"]
    ) == 1

    assert (
        update["videos"][0].id
        == VIDEO_ID
    )

    search_videos.assert_awaited_once()

    request = (
        search_videos
        .call_args
        .args[0]
    )

    assert isinstance(
        request,
        VideoSearchRequest,
    )

    assert (
        request.query
        == "Ruy Lopez C60"
    )

    assert (
        request.max_results
        == settings.youtube_search_max_results
    )

    assert (
        request.language
        == settings.youtube_default_language
    )

    assert emit_progress.call_count == 2


@pytest.mark.asyncio
async def test_retrieve_videos_success_with_wikichess_fallback(
    state: ChessAnalysisState,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Vérifie la recherche depuis le contexte Wikichess."""

    current_state = state.model_copy(
        update={
            "retrieval_context": (
                build_wikichess_context(
                    wikichess_title=(
                        "Italian Game Wikichess"
                    ),
                    eco="C50",
                )
            ),
        }
    )

    search_videos = AsyncMock(
        return_value=build_collection(),
    )

    service = MagicMock(
        spec=YoutubeService,
    )

    service.search_videos = search_videos

    monkeypatch.setattr(
        "app.agent.nodes.F_retrieve_videos."
        "_get_youtube_service",
        MagicMock(
            return_value=service,
        ),
    )

    monkeypatch.setattr(
        "app.agent.nodes.F_retrieve_videos."
        "emit_progress",
        MagicMock(),
    )

    update = await retrieve_videos(
        current_state,
        cast(
            RunnableConfig,
            {},
        ),
    )

    assert (
        update["status"]
        == AnalysisStatus.SUCCESS
    )

    request = (
        search_videos
        .call_args
        .args[0]
    )

    assert (
        request.query
        == "Italian Game Wikichess C50"
    )


@pytest.mark.asyncio
async def test_retrieve_videos_handles_youtube_error(
    opening_state: ChessAnalysisState,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Vérifie une indisponibilité connue de YouTube."""

    youtube_error = YoutubeError(
        message="YouTube indisponible.",
    )

    search_videos = AsyncMock(
        side_effect=youtube_error,
    )

    service = MagicMock(
        spec=YoutubeService,
    )

    service.search_videos = search_videos

    emit_progress = MagicMock()

    monkeypatch.setattr(
        "app.agent.nodes.F_retrieve_videos."
        "_get_youtube_service",
        MagicMock(
            return_value=service,
        ),
    )

    monkeypatch.setattr(
        "app.agent.nodes.F_retrieve_videos."
        "emit_progress",
        emit_progress,
    )

    update = await retrieve_videos(
        opening_state,
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
        WorkflowStep.RETRIEVE_VIDEOS
        in update["completed_steps"]
    )

    assert update["videos"] == []

    assert len(
        update["warnings"]
    ) == 1

    assert (
        update["warnings"][0].code
        == ERROR_YOUTUBE_UNAVAILABLE
    )

    assert emit_progress.call_count == 2


@pytest.mark.asyncio
async def test_retrieve_videos_preserves_failed_status_on_youtube_error(
    opening_state: ChessAnalysisState,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Vérifie qu'un échec global antérieur reste prioritaire."""

    failed_state = opening_state.model_copy(
        update={
            "status": AnalysisStatus.FAILED,
        }
    )

    service = MagicMock(
        spec=YoutubeService,
    )

    service.search_videos = AsyncMock(
        side_effect=YoutubeError(
            message="YouTube indisponible.",
        ),
    )

    monkeypatch.setattr(
        "app.agent.nodes.F_retrieve_videos."
        "_get_youtube_service",
        MagicMock(
            return_value=service,
        ),
    )

    monkeypatch.setattr(
        "app.agent.nodes.F_retrieve_videos."
        "emit_progress",
        MagicMock(),
    )

    update = await retrieve_videos(
        failed_state,
        cast(
            RunnableConfig,
            {},
        ),
    )

    assert (
        update["status"]
        == AnalysisStatus.FAILED
    )


@pytest.mark.asyncio
async def test_retrieve_videos_handles_unexpected_error(
    opening_state: ChessAnalysisState,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Vérifie une erreur inattendue."""

    search_videos = AsyncMock(
        side_effect=RuntimeError(
            "unexpected"
        ),
    )

    service = MagicMock(
        spec=YoutubeService,
    )

    service.search_videos = search_videos

    emit_progress = MagicMock()

    monkeypatch.setattr(
        "app.agent.nodes.F_retrieve_videos."
        "_get_youtube_service",
        MagicMock(
            return_value=service,
        ),
    )

    monkeypatch.setattr(
        "app.agent.nodes.F_retrieve_videos."
        "emit_progress",
        emit_progress,
    )

    update = await retrieve_videos(
        opening_state,
        cast(
            RunnableConfig,
            {},
        ),
    )

    assert (
        update["status"]
        == AnalysisStatus.FAILED
    )

    assert (
        update["errors"][0].code
        == ERROR_UNEXPECTED
    )

    assert (
        WorkflowStep.RETRIEVE_VIDEOS
        not in update["completed_steps"]
    )

    assert update["videos"] == []

    assert emit_progress.call_count == 2