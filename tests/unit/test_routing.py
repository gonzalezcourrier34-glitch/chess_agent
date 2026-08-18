"""Tests unitaires du routage conditionnel LangGraph.

Ce module vérifie les décisions prises par ``app.agent.routing``.

Les tests portent uniquement sur la logique de routage :

- interruption d'un workflow en échec ;
- activation ou désactivation des différentes étapes ;
- distinction entre ouverture connue et position inconnue ;
- sélection des enrichissements ;
- génération de la réponse ;
- sauvegarde finale.

Les services métier et les nœuds LangGraph ne sont pas exécutés.
"""

from __future__ import annotations

from types import SimpleNamespace
from typing import cast

import pytest
from app.agent.routing import (
    route_after_context,
    route_after_engine_analysis,
    route_after_response,
    route_after_theory_detection,
    route_after_unknown_position_analysis,
    route_after_validation,
    route_after_videos,
)
from app.agent.state import ChessAnalysisState
from app.schemas.common.enums import AnalysisStatus

# Construction


def _build_state(
    *,
    status: AnalysisStatus = AnalysisStatus.SUCCESS,
    include_opening: bool = False,
    include_stockfish: bool = False,
    include_context: bool = False,
    include_videos: bool = False,
    generate_response: bool = False,
    save_analysis: bool = False,
    opening_present: bool = False,
) -> ChessAnalysisState:
    """Construit un état minimal destiné aux tests de routage."""

    options = SimpleNamespace(
        include_opening=include_opening,
        include_stockfish=include_stockfish,
        include_context=include_context,
        include_videos=include_videos,
        generate_response=generate_response,
        save_analysis=save_analysis,
    )

    opening = (
        object()
        if opening_present
        else None
    )

    state = SimpleNamespace(
        status=status,
        options=options,
        opening=opening,
    )

    return cast(
        ChessAnalysisState,
        state,
    )


# Validation


def test_route_after_validation_stops_failed_workflow() -> None:
    """Un workflow en échec doit être interrompu."""

    state = _build_state(
        status=AnalysisStatus.FAILED,
        include_opening=True,
        include_stockfish=True,
        generate_response=True,
        save_analysis=True,
    )

    assert route_after_validation(state) == "end"


def test_route_after_validation_routes_to_theory() -> None:
    """La détection d'ouverture est prioritaire lorsqu'elle est activée."""

    state = _build_state(
        include_opening=True,
        include_stockfish=True,
    )

    assert route_after_validation(state) == "detect_theory"


def test_route_after_validation_routes_to_engine() -> None:
    """Stockfish est exécuté lorsque la théorie est désactivée."""

    state = _build_state(
        include_opening=False,
        include_stockfish=True,
    )

    assert route_after_validation(state) == "engine_analysis"


@pytest.mark.parametrize(
    ("generate_response", "save_analysis", "expected"),
    [
        (
            True,
            True,
            "generate_response",
        ),
        (
            False,
            True,
            "save_analysis",
        ),
        (
            False,
            False,
            "end",
        ),
    ],
)
def test_route_after_validation_routes_to_output(
    generate_response: bool,
    save_analysis: bool,
    expected: str,
) -> None:
    """La validation rejoint directement la sortie sans analyse activée."""

    state = _build_state(
        generate_response=generate_response,
        save_analysis=save_analysis,
    )

    assert route_after_validation(state) == expected


# Détection théorique


def test_route_after_theory_detection_stops_failed_workflow() -> None:
    """Une erreur fatale après détection interrompt le workflow."""

    state = _build_state(
        status=AnalysisStatus.FAILED,
        include_stockfish=True,
        opening_present=True,
    )

    assert route_after_theory_detection(state) == "end"


def test_route_after_theory_detection_routes_to_engine() -> None:
    """L'analyse moteur suit la détection lorsqu'elle est activée."""

    state = _build_state(
        include_stockfish=True,
        opening_present=True,
    )

    assert route_after_theory_detection(state) == "engine_analysis"


def test_route_after_theory_detection_routes_known_opening_to_context() -> None:
    """Une ouverture connue peut être enrichie par le RAG."""

    state = _build_state(
        opening_present=True,
        include_context=True,
        include_videos=True,
    )

    assert route_after_theory_detection(state) == "retrieve_context"


def test_route_after_theory_detection_routes_known_opening_to_videos() -> None:
    """Les vidéos suivent directement si le contexte est désactivé."""

    state = _build_state(
        opening_present=True,
        include_context=False,
        include_videos=True,
    )

    assert route_after_theory_detection(state) == "retrieve_videos"


def test_route_after_theory_detection_routes_known_opening_to_output() -> None:
    """Une ouverture connue sans enrichissement rejoint la sortie."""

    state = _build_state(
        opening_present=True,
        generate_response=True,
    )

    assert route_after_theory_detection(state) == "generate_response"


def test_route_after_theory_detection_routes_unknown_opening_to_output() -> None:
    """Sans Stockfish, une ouverture absente rejoint directement la sortie."""

    state = _build_state(
        opening_present=False,
        include_stockfish=False,
        generate_response=True,
    )

    assert route_after_theory_detection(state) == "generate_response"


# Analyse moteur


def test_route_after_engine_analysis_stops_failed_workflow() -> None:
    """Une erreur fatale du moteur interrompt le workflow."""

    state = _build_state(
        status=AnalysisStatus.FAILED,
        include_opening=True,
    )

    assert route_after_engine_analysis(state) == "end"


def test_route_after_engine_analysis_skips_unknown_position_when_opening_disabled(
) -> None:
    """Une ouverture non recherchée ne doit pas être considérée inconnue."""

    state = _build_state(
        include_opening=False,
        opening_present=False,
        generate_response=True,
    )

    assert route_after_engine_analysis(state) == "generate_response"


def test_route_after_engine_analysis_routes_unknown_position() -> None:
    """Une ouverture recherchée mais absente utilise l'analyse inconnue."""

    state = _build_state(
        include_opening=True,
        opening_present=False,
    )

    assert (
        route_after_engine_analysis(state)
        == "unknown_position_analysis"
    )


def test_route_after_engine_analysis_routes_known_opening_to_context() -> None:
    """Une ouverture connue est enrichie par le contexte si demandé."""

    state = _build_state(
        include_opening=True,
        opening_present=True,
        include_context=True,
        include_videos=True,
    )

    assert route_after_engine_analysis(state) == "retrieve_context"


def test_route_after_engine_analysis_routes_known_opening_to_videos() -> None:
    """Les vidéos sont utilisées si le contexte documentaire est désactivé."""

    state = _build_state(
        include_opening=True,
        opening_present=True,
        include_videos=True,
    )

    assert route_after_engine_analysis(state) == "retrieve_videos"


def test_route_after_engine_analysis_routes_known_opening_to_output() -> None:
    """Une ouverture connue sans enrichissement rejoint la sortie."""

    state = _build_state(
        include_opening=True,
        opening_present=True,
        generate_response=True,
    )

    assert route_after_engine_analysis(state) == "generate_response"


# Position inconnue


def test_route_after_unknown_position_analysis_stops_failed_workflow() -> None:
    """Une erreur fatale de l'analyse inconnue interrompt le workflow."""

    state = _build_state(
        status=AnalysisStatus.FAILED,
        generate_response=True,
    )

    assert route_after_unknown_position_analysis(state) == "end"


@pytest.mark.parametrize(
    ("generate_response", "save_analysis", "expected"),
    [
        (
            True,
            True,
            "generate_response",
        ),
        (
            False,
            True,
            "save_analysis",
        ),
        (
            False,
            False,
            "end",
        ),
    ],
)
def test_route_after_unknown_position_analysis_routes_to_output(
    generate_response: bool,
    save_analysis: bool,
    expected: str,
) -> None:
    """Une analyse de position inconnue rejoint la sortie configurée."""

    state = _build_state(
        generate_response=generate_response,
        save_analysis=save_analysis,
    )

    assert route_after_unknown_position_analysis(state) == expected


# Contexte documentaire


def test_route_after_context_stops_failed_workflow() -> None:
    """Une erreur fatale du RAG interrompt le workflow."""

    state = _build_state(
        status=AnalysisStatus.FAILED,
        include_videos=True,
    )

    assert route_after_context(state) == "end"


def test_route_after_context_routes_to_videos() -> None:
    """Les vidéos suivent la récupération documentaire si activées."""

    state = _build_state(
        include_videos=True,
    )

    assert route_after_context(state) == "retrieve_videos"


@pytest.mark.parametrize(
    ("generate_response", "save_analysis", "expected"),
    [
        (
            True,
            True,
            "generate_response",
        ),
        (
            False,
            True,
            "save_analysis",
        ),
        (
            False,
            False,
            "end",
        ),
    ],
)
def test_route_after_context_routes_to_output(
    generate_response: bool,
    save_analysis: bool,
    expected: str,
) -> None:
    """Sans vidéos, le contexte rejoint directement la sortie."""

    state = _build_state(
        include_videos=False,
        generate_response=generate_response,
        save_analysis=save_analysis,
    )

    assert route_after_context(state) == expected


# Vidéos


def test_route_after_videos_stops_failed_workflow() -> None:
    """Une erreur fatale de récupération vidéo interrompt le workflow."""

    state = _build_state(
        status=AnalysisStatus.FAILED,
        generate_response=True,
    )

    assert route_after_videos(state) == "end"


@pytest.mark.parametrize(
    ("generate_response", "save_analysis", "expected"),
    [
        (
            True,
            True,
            "generate_response",
        ),
        (
            False,
            True,
            "save_analysis",
        ),
        (
            False,
            False,
            "end",
        ),
    ],
)
def test_route_after_videos_routes_to_output(
    generate_response: bool,
    save_analysis: bool,
    expected: str,
) -> None:
    """La récupération vidéo rejoint la sortie configurée."""

    state = _build_state(
        generate_response=generate_response,
        save_analysis=save_analysis,
    )

    assert route_after_videos(state) == expected


# Réponse


def test_route_after_response_stops_failed_workflow() -> None:
    """Une erreur fatale de génération interrompt le workflow."""

    state = _build_state(
        status=AnalysisStatus.FAILED,
        save_analysis=True,
    )

    assert route_after_response(state) == "end"


def test_route_after_response_routes_to_save() -> None:
    """Une analyse est sauvegardée après génération si demandé."""

    state = _build_state(
        save_analysis=True,
    )

    assert route_after_response(state) == "save_analysis"


def test_route_after_response_routes_to_end() -> None:
    """Sans sauvegarde, la génération termine le workflow."""

    state = _build_state(
        save_analysis=False,
    )

    assert route_after_response(state) == "end"