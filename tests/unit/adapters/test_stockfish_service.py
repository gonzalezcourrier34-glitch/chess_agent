"""Tests unitaires du service Stockfish de Chess Agent."""

from __future__ import annotations

import asyncio
from pathlib import Path
from typing import cast
from unittest.mock import AsyncMock, MagicMock

import chess
import chess.engine
import pytest
from app.adapters.stockfish_service import (
    MINIMUM_DEPTH,
    SERVICE_NAME,
    StockfishAnalysis,
    StockfishService,
)
from app.core.exceptions import (
    StockfishAnalysisError,
    StockfishConfigurationError,
    StockfishResponseError,
    StockfishTimeoutError,
    StockfishUnavailableError,
)
from app.schemas.chess.position import FenRequest
from app.schemas.common.enums import EvaluationType

# Configuration

STARTING_FEN = chess.STARTING_FEN

BEST_MOVE = chess.Move.from_uci(
    "e2e4"
)

SECOND_MOVE = chess.Move.from_uci(
    "d2d4"
)


# Helpers

def build_cp_score(
    centipawns: int = 25,
) -> chess.engine.PovScore:
    """Construit un score centipawn du point de vue des Blancs."""

    return chess.engine.PovScore(
        chess.engine.Cp(
            centipawns
        ),
        chess.WHITE,
    )


def build_mate_score(
    moves: int = 3,
) -> chess.engine.PovScore:
    """Construit un score de mat du point de vue des Blancs."""

    return chess.engine.PovScore(
        chess.engine.Mate(
            moves
        ),
        chess.WHITE,
    )


def build_info(
    *,
    move: chess.Move = BEST_MOVE,
    score: chess.engine.PovScore | None = None,
    depth: int = 15,
    nodes: int = 1000,
    engine_time: float = 0.25,
) -> chess.engine.InfoDict:
    """Construit une réponse Stockfish typée."""

    payload: dict[str, object] = {
        "score": (
            score
            if score is not None
            else build_cp_score()
        ),
        "pv": [
            move,
        ],
        "depth": depth,
        "nodes": nodes,
        "time": engine_time,
    }

    return cast(
        chess.engine.InfoDict,
        payload,
    )


# Fixtures

@pytest.fixture
def service() -> StockfishService:
    """Construit un service Stockfish non initialisé."""

    return StockfishService()


@pytest.fixture
def engine() -> MagicMock:
    """Construit un faux moteur Stockfish."""

    mocked_engine = MagicMock(
        spec=chess.engine.SimpleEngine
    )

    mocked_engine.quit = MagicMock()
    mocked_engine.close = MagicMock()
    mocked_engine.configure = MagicMock()
    mocked_engine.analyse = MagicMock()

    return mocked_engine


@pytest.fixture
def board() -> chess.Board:
    """Construit la position initiale."""

    return chess.Board(
        STARTING_FEN
    )


# État initial

def test_service_is_not_ready_after_creation(
    service: StockfishService,
) -> None:
    """Vérifie l'état initial du service."""

    assert service.is_ready() is False
    assert service.get_analyzed_count() == 0
    assert (
        service.get_last_analysis_duration()
        is None
    )


# Moteur

def test_get_engine_rejects_uninitialized_service(
    service: StockfishService,
) -> None:
    """Vérifie l'absence de moteur."""

    with pytest.raises(
        StockfishUnavailableError
    ):
        service._get_engine()


def test_get_engine_returns_initialized_engine(
    service: StockfishService,
    engine: MagicMock,
) -> None:
    """Vérifie la récupération du moteur courant."""

    service._engine = cast(
        chess.engine.SimpleEngine,
        engine,
    )

    assert (
        service._get_engine()
        is engine
    )


@pytest.mark.asyncio
async def test_ensure_engine_returns_started_engine(
    service: StockfishService,
    engine: MagicMock,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Vérifie l'initialisation automatique du moteur."""

    start_engine = AsyncMock(
        return_value=engine
    )

    monkeypatch.setattr(
        service,
        "_start_engine",
        start_engine,
    )

    result = await service._ensure_engine()

    assert result is engine

    start_engine.assert_awaited_once()


# Démarrage

@pytest.mark.asyncio
async def test_start_calls_start_engine(
    service: StockfishService,
    engine: MagicMock,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Vérifie le démarrage public."""

    start_engine = AsyncMock(
        return_value=engine
    )

    monkeypatch.setattr(
        service,
        "_start_engine",
        start_engine,
    )

    await service.start()

    start_engine.assert_awaited_once()


@pytest.mark.asyncio
async def test_start_engine_returns_existing_engine(
    service: StockfishService,
    engine: MagicMock,
) -> None:
    """Vérifie qu'un moteur existant n'est pas redémarré."""

    service._engine = cast(
        chess.engine.SimpleEngine,
        engine,
    )

    result = await service._start_engine()

    assert result is engine


@pytest.mark.asyncio
async def test_start_engine_rejects_missing_executable(
    service: StockfishService,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Vérifie le rejet d'un exécutable inexistant."""

    from app.adapters.stockfish_service import settings

    test_settings = settings.model_copy(
        update={
            "stockfish_path": (
                "missing-stockfish-binary"
            ),
        }
    )

    monkeypatch.setattr(
        "app.adapters.stockfish_service.settings",
        test_settings,
    )

    with pytest.raises(
        StockfishConfigurationError
    ):
        await service._start_engine()


@pytest.mark.asyncio
async def test_start_engine_initializes_and_configures_engine(
    service: StockfishService,
    engine: MagicMock,
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    """Vérifie le lancement et la configuration du moteur."""

    executable = (
        tmp_path
        / "stockfish"
    )

    executable.write_text(
        "fake",
        encoding="utf-8",
    )

    from app.adapters.stockfish_service import settings

    test_settings = settings.model_copy(
        update={
            "stockfish_path": str(
                executable
            ),
            "stockfish_threads": 2,
            "stockfish_hash_mb": 128,
        }
    )

    monkeypatch.setattr(
        "app.adapters.stockfish_service.settings",
        test_settings,
    )

    popen_uci = MagicMock(
        return_value=engine
    )

    monkeypatch.setattr(
        "app.adapters.stockfish_service."
        "chess.engine.SimpleEngine.popen_uci",
        popen_uci,
    )

    result = await service._start_engine()

    assert result is engine
    assert service._engine is engine

    popen_uci.assert_called_once_with(
        str(executable)
    )

    engine.configure.assert_called_once_with(
        {
            "Threads": 2,
            "Hash": 128,
        }
    )


@pytest.mark.asyncio
async def test_start_engine_translates_startup_error(
    service: StockfishService,
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    """Vérifie une erreur pendant le démarrage du moteur."""

    executable = (
        tmp_path
        / "stockfish"
    )

    executable.write_text(
        "fake",
        encoding="utf-8",
    )

    from app.adapters.stockfish_service import settings

    test_settings = settings.model_copy(
        update={
            "stockfish_path": str(
                executable
            ),
        }
    )

    monkeypatch.setattr(
        "app.adapters.stockfish_service.settings",
        test_settings,
    )

    monkeypatch.setattr(
        "app.adapters.stockfish_service."
        "chess.engine.SimpleEngine.popen_uci",
        MagicMock(
            side_effect=RuntimeError(
                "startup failure"
            )
        ),
    )

    with pytest.raises(
        StockfishUnavailableError
    ):
        await service._start_engine()


# Fermeture

@pytest.mark.asyncio
async def test_close_releases_engine(
    service: StockfishService,
    engine: MagicMock,
) -> None:
    """Vérifie la fermeture du moteur."""

    service._engine = cast(
        chess.engine.SimpleEngine,
        engine,
    )

    await service.close()

    assert service._engine is None
    assert service.is_ready() is False

    engine.quit.assert_called_once()


@pytest.mark.asyncio
async def test_close_does_nothing_without_engine(
    service: StockfishService,
) -> None:
    """Vérifie la fermeture sans moteur actif."""

    await service.close()

    assert service._engine is None


@pytest.mark.asyncio
async def test_close_uses_close_when_quit_fails(
    service: StockfishService,
    engine: MagicMock,
) -> None:
    """Vérifie la fermeture forcée après échec de quit."""

    engine.quit.side_effect = RuntimeError(
        "quit failure"
    )

    service._engine = cast(
        chess.engine.SimpleEngine,
        engine,
    )

    await service.close()

    assert service._engine is None

    engine.close.assert_called_once()


@pytest.mark.asyncio
async def test_close_failed_engine_calls_quit(
    service: StockfishService,
    engine: MagicMock,
) -> None:
    """Vérifie la fermeture d'un moteur mal initialisé."""

    await service._close_failed_engine(
        cast(
            chess.engine.SimpleEngine,
            engine,
        )
    )

    engine.quit.assert_called_once()


@pytest.mark.asyncio
async def test_close_failed_engine_uses_close_when_quit_fails(
    service: StockfishService,
    engine: MagicMock,
) -> None:
    """Vérifie la fermeture forcée d'un moteur mal initialisé."""

    engine.quit.side_effect = RuntimeError(
        "quit failure"
    )

    await service._close_failed_engine(
        cast(
            chess.engine.SimpleEngine,
            engine,
        )
    )

    engine.close.assert_called_once()


@pytest.mark.asyncio
async def test_initialize_calls_start(
    service: StockfishService,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Vérifie l'alias initialize."""

    start = AsyncMock()

    monkeypatch.setattr(
        service,
        "start",
        start,
    )

    await service.initialize()

    start.assert_awaited_once()


@pytest.mark.asyncio
async def test_shutdown_calls_close(
    service: StockfishService,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Vérifie l'alias shutdown."""

    close = AsyncMock()

    monkeypatch.setattr(
        service,
        "close",
        close,
    )

    await service.shutdown()

    close.assert_awaited_once()


# Normalisation des analyses

def test_normalize_analysis_wraps_single_info(
    service: StockfishService,
) -> None:
    """Vérifie une réponse Stockfish simple."""

    info = build_info()

    result = service._normalize_analysis(
        info
    )

    assert result == [
        info,
    ]


def test_normalize_analysis_keeps_multipv_list(
    service: StockfishService,
) -> None:
    """Vérifie une réponse MultiPV."""

    first = build_info()
    second = build_info(
        move=SECOND_MOVE,
    )

    raw: StockfishAnalysis = [
        first,
        second,
    ]

    result = service._normalize_analysis(
        raw
    )

    assert result == [
        first,
        second,
    ]


# Variante principale

def test_get_principal_variation_returns_moves(
    service: StockfishService,
) -> None:
    """Vérifie la récupération de la variante principale."""

    info = build_info()

    result = (
        service._get_principal_variation(
            info
        )
    )

    assert result == [
        BEST_MOVE,
    ]


def test_get_principal_variation_returns_empty_list_when_missing(
    service: StockfishService,
) -> None:
    """Vérifie l'absence de variante principale."""

    info = cast(
        chess.engine.InfoDict,
        {},
    )

    assert (
        service._get_principal_variation(
            info
        )
        == []
    )


# Score

def test_get_principal_score_returns_pov_score(
    service: StockfishService,
) -> None:
    """Vérifie la récupération du score principal."""

    score = build_cp_score()

    info: dict[str, object] = {
        "score": score,
    }

    assert (
        service._get_principal_score(
            info
        )
        is score
    )


@pytest.mark.parametrize(
    "value",
    [
        None,
        12,
        "12",
        chess.engine.Cp(12),
    ],
)
def test_get_principal_score_rejects_invalid_value(
    service: StockfishService,
    value: object,
) -> None:
    """Vérifie qu'un PovScore est obligatoire."""

    with pytest.raises(
        StockfishResponseError
    ):
        service._get_principal_score(
            {
                "score": value,
            }
        )


# Nodes

@pytest.mark.parametrize(
    ("value", "expected"),
    [
        (100, 100),
        (0, 0),
        (-1, None),
        (True, None),
        (1.5, None),
        ("100", None),
        (None, None),
    ],
)
def test_get_nodes(
    service: StockfishService,
    value: object,
    expected: int | None,
) -> None:
    """Vérifie la normalisation du nombre de nœuds."""

    assert (
        service._get_nodes(
            {
                "nodes": value,
            }
        )
        == expected
    )


# Temps moteur

@pytest.mark.parametrize(
    ("value", "expected"),
    [
        (0.25, 250),
        (1, 1000),
        (0, 0),
        (-1, None),
        (True, None),
        ("1", None),
        (float("inf"), None),
        (float("nan"), None),
        (None, None),
    ],
)
def test_get_engine_time_ms(
    service: StockfishService,
    value: object,
    expected: int | None,
) -> None:
    """Vérifie la conversion du temps moteur."""

    assert (
        service._get_engine_time_ms(
            {
                "time": value,
            }
        )
        == expected
    )


# Analyse synchrone

def test_run_engine_analysis_calls_python_chess(
    service: StockfishService,
    engine: MagicMock,
    board: chess.Board,
) -> None:
    """Vérifie l'appel synchrone au moteur."""

    expected = build_info()

    engine.analyse.return_value = expected

    result = service._run_engine_analysis(
        cast(
            chess.engine.SimpleEngine,
            engine,
        ),
        board,
    )

    assert result is expected

    engine.analyse.assert_called_once()


# Construction du meilleur coup

def test_build_best_move_returns_expected_move(
    service: StockfishService,
    board: chess.Board,
) -> None:
    """Vérifie la construction d'un meilleur coup."""

    info = build_info(
        move=BEST_MOVE,
        score=build_cp_score(
            35
        ),
        depth=15,
    )

    result = service._build_best_move(
        board=board,
        evaluation=info,
    )

    assert result is not None
    assert result.uci == "e2e4"
    assert result.san == "e4"
    assert result.from_square == "e2"
    assert result.to_square == "e4"
    assert result.score == 35.0
    assert (
        result.evaluation_type
        == EvaluationType.CENTIPAWN
    )
    assert result.depth == 15

    assert result.principal_variation == [
        "e2e4",
    ]


def test_build_best_move_returns_none_without_pv(
    service: StockfishService,
    board: chess.Board,
) -> None:
    """Vérifie l'absence de meilleur coup sans PV."""

    info = cast(
        chess.engine.InfoDict,
        {
            "score": build_cp_score(),
        },
    )

    result = service._build_best_move(
        board=board,
        evaluation=info,
    )

    assert result is None


def test_build_best_move_returns_none_without_valid_score(
    service: StockfishService,
    board: chess.Board,
) -> None:
    """Vérifie l'absence de meilleur coup sans score valide."""

    info = cast(
        chess.engine.InfoDict,
        {
            "pv": [
                BEST_MOVE,
            ],
        },
    )

    result = service._build_best_move(
        board=board,
        evaluation=info,
    )

    assert result is None


def test_build_best_move_uses_uci_when_san_fails(
    service: StockfishService,
    board: chess.Board,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Vérifie le repli UCI si la conversion SAN échoue."""

    info = build_info()

    monkeypatch.setattr(
        board,
        "san",
        MagicMock(
            side_effect=ValueError(
                "invalid SAN"
            )
        ),
    )

    result = service._build_best_move(
        board=board,
        evaluation=info,
    )

    assert result is not None
    assert result.san == "e2e4"


# Conversion du score

def test_convert_score_returns_centipawns(
    service: StockfishService,
) -> None:
    """Vérifie la conversion d'un score centipawn."""

    score = chess.engine.Cp(
        42
    )

    assert (
        service._convert_score(
            score
        )
        == 42
    )


def test_convert_score_returns_mate_distance(
    service: StockfishService,
) -> None:
    """Vérifie la conversion d'un score de mat."""

    score = chess.engine.Mate(
        3
    )

    assert (
        service._convert_score(
            score
        )
        == 3
    )


def test_get_score_type_returns_centipawn(
    service: StockfishService,
) -> None:
    """Vérifie le type centipawn."""

    result = service._get_score_type(
        chess.engine.Cp(
            10
        )
    )

    assert (
        result
        == EvaluationType.CENTIPAWN
    )


def test_get_score_type_returns_mate(
    service: StockfishService,
) -> None:
    """Vérifie le type mat."""

    result = service._get_score_type(
        chess.engine.Mate(
            2
        )
    )

    assert (
        result
        == EvaluationType.MATE
    )


# Profondeur

@pytest.mark.parametrize(
    ("value", "expected"),
    [
        (15, 15),
        (1, 1),
        (0, MINIMUM_DEPTH),
        (-1, MINIMUM_DEPTH),
        (True, MINIMUM_DEPTH),
        (1.5, MINIMUM_DEPTH),
        ("15", MINIMUM_DEPTH),
        (None, MINIMUM_DEPTH),
    ],
)
def test_get_depth(
    service: StockfishService,
    value: object,
    expected: int,
) -> None:
    """Vérifie la profondeur Stockfish."""

    result = service._get_depth(
        {
            "depth": value,
        }
    )

    assert result == expected


# Évaluation complète

def test_build_evaluation_returns_position_evaluation(
    service: StockfishService,
    board: chess.Board,
) -> None:
    """Vérifie la construction de l'évaluation complète."""

    principal = build_info(
        move=BEST_MOVE,
        score=build_cp_score(
            30
        ),
    )

    alternative = build_info(
        move=SECOND_MOVE,
        score=build_cp_score(
            20
        ),
    )

    raw: StockfishAnalysis = [
        principal,
        alternative,
    ]

    result = service._build_evaluation(
        board=board,
        info=raw,
    )

    assert result.engine.best_move.uci == "e2e4"
    assert (
        result.engine.evaluation.score
        == 30.0
    )

    assert (
        result.engine.evaluation.evaluation_type
        == EvaluationType.CENTIPAWN
    )

    assert len(
        result.engine.alternatives
    ) == 1

    assert (
        result.engine.alternatives[0].uci
        == "d2d4"
    )


def test_build_evaluation_rejects_empty_analysis(
    service: StockfishService,
    board: chess.Board,
) -> None:
    """Vérifie le rejet d'une analyse vide."""

    with pytest.raises(
        StockfishResponseError
    ):
        service._build_evaluation(
            board=board,
            info=[],
        )


def test_build_evaluation_rejects_missing_best_move(
    service: StockfishService,
    board: chess.Board,
) -> None:
    """Vérifie qu'un meilleur coup est obligatoire."""

    info = cast(
        chess.engine.InfoDict,
        {
            "score": build_cp_score(),
            "depth": 15,
        },
    )

    with pytest.raises(
        StockfishResponseError
    ):
        service._build_evaluation(
            board=board,
            info=info,
        )


def test_build_evaluation_rejects_missing_score(
    service: StockfishService,
    board: chess.Board,
) -> None:
    """Vérifie qu'un score principal est obligatoire."""

    info = cast(
        chess.engine.InfoDict,
        {
            "pv": [
                BEST_MOVE,
            ],
        },
    )

    with pytest.raises(
        StockfishResponseError
    ):
        service._build_evaluation(
            board=board,
            info=info,
        )


# Analyse publique

@pytest.mark.asyncio
async def test_analyze_position_returns_evaluation_and_counts(
    service: StockfishService,
    engine: MagicMock,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Vérifie une analyse réussie."""

    raw = build_info()

    monkeypatch.setattr(
        service,
        "_start_engine",
        AsyncMock(
            return_value=engine,
        ),
    )

    monkeypatch.setattr(
        service,
        "_analyze_with_timeout",
        AsyncMock(
            return_value=raw,
        ),
    )

    result = await service.analyze_position(
        FenRequest(
            fen=STARTING_FEN
        )
    )

    assert (
        result.engine.best_move.uci
        == "e2e4"
    )

    assert (
        service.get_analyzed_count()
        == 1
    )

    assert (
        service.get_last_analysis_duration()
        is not None
    )


@pytest.mark.asyncio
async def test_analyze_position_does_not_count_when_disabled(
    service: StockfishService,
    engine: MagicMock,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Vérifie l'option count=False."""

    monkeypatch.setattr(
        service,
        "_start_engine",
        AsyncMock(
            return_value=engine,
        ),
    )

    monkeypatch.setattr(
        service,
        "_analyze_with_timeout",
        AsyncMock(
            return_value=build_info(),
        ),
    )

    await service.analyze_position(
        FenRequest(
            fen=STARTING_FEN
        ),
        count=False,
    )

    assert (
        service.get_analyzed_count()
        == 0
    )


@pytest.mark.asyncio
async def test_analyze_position_translates_timeout(
    service: StockfishService,
    engine: MagicMock,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Vérifie la traduction d'un timeout."""

    monkeypatch.setattr(
        service,
        "_start_engine",
        AsyncMock(
            return_value=engine,
        ),
    )

    monkeypatch.setattr(
        service,
        "_analyze_with_timeout",
        AsyncMock(
            side_effect=TimeoutError(),
        ),
    )

    with pytest.raises(
        StockfishTimeoutError
    ):
        await service.analyze_position(
            FenRequest(
                fen=STARTING_FEN
            )
        )


@pytest.mark.asyncio
async def test_analyze_position_translates_unexpected_error(
    service: StockfishService,
    engine: MagicMock,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Vérifie la traduction d'une erreur d'analyse."""

    monkeypatch.setattr(
        service,
        "_start_engine",
        AsyncMock(
            return_value=engine,
        ),
    )

    monkeypatch.setattr(
        service,
        "_analyze_with_timeout",
        AsyncMock(
            side_effect=RuntimeError(
                "analysis failure"
            ),
        ),
    )

    with pytest.raises(
        StockfishAnalysisError
    ):
        await service.analyze_position(
            FenRequest(
                fen=STARTING_FEN
            )
        )


# Abort

@pytest.mark.asyncio
async def test_abort_analysis_releases_engine(
    service: StockfishService,
    engine: MagicMock,
) -> None:
    """Vérifie l'arrêt forcé d'une analyse."""

    typed_engine = cast(
        chess.engine.SimpleEngine,
        engine,
    )

    service._engine = typed_engine

    async def pending_analysis() -> StockfishAnalysis:
        await asyncio.sleep(
            10
        )

        return build_info()

    task = asyncio.create_task(
        pending_analysis()
    )

    await service._abort_analysis(
        typed_engine,
        task,
    )

    assert service._engine is None
    assert task.cancelled()

    engine.close.assert_called_once()


# Santé
@pytest.mark.asyncio
async def test_ping_returns_true_on_success(
    service: StockfishService,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Vérifie un ping réussi."""

    analyze_position = AsyncMock()

    monkeypatch.setattr(
        service,
        "analyze_position",
        analyze_position,
    )

    assert await service.ping() is True

    analyze_position.assert_awaited_once()

@pytest.mark.asyncio
async def test_ping_returns_false_on_stockfish_error(
    service: StockfishService,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Vérifie une indisponibilité Stockfish."""

    monkeypatch.setattr(
        service,
        "analyze_position",
        AsyncMock(
            side_effect=StockfishUnavailableError(
                message="unavailable"
            ),
        ),
    )

    assert await service.ping() is False


@pytest.mark.asyncio
async def test_ping_returns_false_on_unexpected_error(
    service: StockfishService,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Vérifie une erreur inattendue."""

    monkeypatch.setattr(
        service,
        "analyze_position",
        AsyncMock(
            side_effect=RuntimeError(
                "unexpected"
            ),
        ),
    )

    assert await service.ping() is False


@pytest.mark.asyncio
async def test_health_returns_service_status(
    service: StockfishService,
    engine: MagicMock,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Vérifie l'état de santé détaillé."""

    service._engine = cast(
        chess.engine.SimpleEngine,
        engine,
    )

    service._analyzed_positions = 4
    service._last_analysis_duration_ms = 125.5

    monkeypatch.setattr(
        service,
        "ping",
        AsyncMock(
            return_value=True,
        ),
    )

    status = await service.health()

    assert (
        status["service"]
        == SERVICE_NAME
    )

    assert status["is_ready"] is True
    assert status["available"] is True

    assert (
        status["analyzed_positions"]
        == 4
    )

    assert (
        status["last_analysis_duration_ms"]
        == 125.5
    )

    assert status["depth"] >= 1
    assert status["threads"] >= 1
    assert status["hash_mb"] >= 1
    assert status["top_moves"] >= 1