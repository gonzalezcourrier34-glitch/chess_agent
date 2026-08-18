"""Analyse des positions d'échecs avec Stockfish.

Ce module centralise :

- le cycle de vie du processus UCI ;
- l'analyse MultiPV des positions FEN ;
- la conversion des résultats vers les schémas métier ;
- le suivi des métriques et de l'état de santé du service.

Il ne contient aucune logique propre au workflow LangGraph.
"""

from __future__ import annotations

import asyncio
from collections.abc import Mapping
from contextlib import suppress
from math import isfinite
from pathlib import Path
from time import perf_counter
from typing import Literal, TypedDict

import chess
import chess.engine

from app.core.config import settings
from app.core.exceptions import (
    StockfishAnalysisError,
    StockfishConfigurationError,
    StockfishError,
    StockfishResponseError,
    StockfishTimeoutError,
    StockfishUnavailableError,
)
from app.core.logging import get_logger
from app.schemas.analysis.evaluation import (
    EngineAnalysis,
    Evaluation,
    PositionEvaluation,
    PrincipalVariation,
)
from app.schemas.chess.move import BestMove
from app.schemas.chess.position import FenRequest
from app.schemas.common.enums import EvaluationType
from app.utils.chess_utils import create_board

logger = get_logger(__name__)


# Types

type StockfishAnalysis = chess.engine.InfoDict | list[chess.engine.InfoDict]


class StockfishServiceStatus(TypedDict):
    """État de santé exposé par le service Stockfish."""

    service: Literal["stockfish"]
    is_ready: bool
    available: bool
    engine: str
    depth: int
    threads: int
    hash_mb: int
    timeout_seconds: float
    top_moves: int
    analyzed_positions: int
    last_analysis_duration_ms: float | None


# Configuration

SERVICE_NAME: Literal["stockfish"] = "stockfish"
MILLISECONDS_PER_SECOND = 1_000
MINIMUM_DEPTH = 1


# Service


class StockfishService:
    """Service d'analyse des positions avec Stockfish."""

    # Construction

    def __init__(self) -> None:
        """Initialise le service sans démarrer immédiatement Stockfish."""
        self._engine: chess.engine.SimpleEngine | None = None
        self._analyzed_positions = 0
        self._last_analysis_duration_ms: float | None = None

        # Un moteur UCI ne doit jamais être démarré, interrogé ou fermé par
        # deux opérations simultanées. Un verrou unique évite aussi les courses
        # entre une analyse et la fermeture du processus.
        self._engine_lock = asyncio.Lock()

    # Cycle de vie

    async def start(self) -> None:
        """Démarre et configure le moteur Stockfish."""
        async with self._engine_lock:
            await self._start_engine()

    async def _start_engine(self) -> chess.engine.SimpleEngine:
        """Démarre Stockfish pendant que le verrou du moteur est détenu."""
        if self._engine is not None:
            return self._engine

        engine_path = Path(settings.stockfish_path)

        if not engine_path.is_file():
            raise StockfishConfigurationError(
                message=f"Exécutable Stockfish introuvable : {engine_path}."
            )

        logger.info("Initialisation de Stockfish.")
        engine: chess.engine.SimpleEngine | None = None

        try:
            # Le lancement et la configuration UCI sont synchrones dans
            # python-chess et doivent rester hors de la boucle événementielle.
            started_engine = await asyncio.to_thread(
                chess.engine.SimpleEngine.popen_uci,
                str(engine_path)
            )
            engine = started_engine
            await asyncio.to_thread(
                started_engine.configure,
                {
                    "Threads": settings.stockfish_threads,
                    "Hash": settings.stockfish_hash_mb,
                }
            )
        except Exception as error:
            logger.exception("Impossible de démarrer Stockfish.")

            if engine is not None:
                await self._close_failed_engine(engine)

            raise StockfishUnavailableError(
                message="Le moteur Stockfish ne peut pas être démarré.",
                cause=error
            ) from error

        self._engine = started_engine
        logger.info("Stockfish est initialisé.")
        return started_engine

    async def _close_failed_engine(
        self,
        engine: chess.engine.SimpleEngine
    ) -> None:
        """Ferme un moteur dont l'initialisation n'a pas abouti."""
        try:
            await asyncio.to_thread(engine.quit)
        except Exception:
            logger.exception(
                "Impossible de fermer Stockfish après l'échec de son "
                "initialisation."
            )

            try:
                await asyncio.to_thread(engine.close)
            except Exception:
                logger.exception(
                    "Impossible de forcer la fermeture de Stockfish."
                )

    async def close(self) -> None:
        """Ferme proprement le moteur Stockfish."""
        async with self._engine_lock:
            engine = self._engine

            if engine is None:
                return

            # La référence est retirée avant l'arrêt afin qu'un moteur en cours
            # de fermeture ne puisse plus être publié par le service.
            self._engine = None
            logger.info("Arrêt de Stockfish.")

            try:
                await asyncio.to_thread(engine.quit)
            except Exception:
                logger.exception("Erreur lors de l'arrêt de Stockfish.")

                try:
                    await asyncio.to_thread(engine.close)
                except Exception:
                    logger.exception(
                        "Impossible de forcer la fermeture de Stockfish."
                    )

    async def initialize(self) -> None:
        """Initialise le service pour les gestionnaires de cycle de vie."""
        await self.start()

    async def shutdown(self) -> None:
        """Arrête le service pour les gestionnaires de cycle de vie."""
        await self.close()

    # Validation

    def _get_engine(self) -> chess.engine.SimpleEngine:
        """Retourne le moteur initialisé."""
        if self._engine is None:
            raise StockfishUnavailableError(
                message="Stockfish n'est pas initialisé."
            )

        return self._engine

    async def _ensure_engine(self) -> chess.engine.SimpleEngine:
        """Retourne un moteur initialisé."""
        async with self._engine_lock:
            return await self._start_engine()

    def _normalize_analysis(
        self,
        analysis: StockfishAnalysis
    ) -> list[chess.engine.InfoDict]:
        """Normalise les réponses simple et MultiPV de python-chess."""
        if isinstance(analysis, list):
            return analysis

        return [analysis]

    def _get_principal_variation(
        self,
        evaluation: chess.engine.InfoDict
    ) -> list[chess.Move]:
        """Retourne la variante principale fournie par Stockfish."""
        moves = evaluation.get("pv")

        if moves is None:
            return []

        return list(moves)

    def _get_principal_score(
        self,
        evaluation: Mapping[str, object]
    ) -> chess.engine.PovScore:
        """Retourne le score obligatoire de l'évaluation principale."""
        score = evaluation.get("score")

        if not isinstance(score, chess.engine.PovScore):
            raise StockfishResponseError(
                message="Stockfish n'a retourné aucun score valide."
            )

        return score

    def _get_nodes(
        self,
        evaluation: Mapping[str, object]
    ) -> int | None:
        """Retourne un nombre de nœuds valide lorsqu'il est disponible."""
        nodes = evaluation.get("nodes")

        if (
            isinstance(nodes, bool)
            or not isinstance(nodes, int)
            or nodes < 0
        ):
            return None

        return nodes

    def _get_engine_time_ms(
        self,
        evaluation: Mapping[str, object]
    ) -> int | None:
        """Retourne le temps moteur en millisecondes."""
        engine_time = evaluation.get("time")

        if (
            isinstance(engine_time, bool)
            or not isinstance(engine_time, (int, float))
            or not isfinite(engine_time)
            or engine_time < 0
        ):
            return None

        return int(engine_time * MILLISECONDS_PER_SECOND)

    # Analyse

    async def analyze_position(
        self,
        request: FenRequest,
        *,
        count: bool = True
    ) -> PositionEvaluation:
        """Analyse une position avec Stockfish."""
        logger.debug("Analyse Stockfish de la position : %s", request.fen)
        board = create_board(request.fen)
        started_at = perf_counter()

        # Le verrou reste détenu jusqu'à la conversion du résultat. Une
        # fermeture ne peut donc pas invalider le moteur pendant l'analyse.
        async with self._engine_lock:
            engine = await self._start_engine()

            try:
                raw_analysis = await self._analyze_with_timeout(engine, board)
            except TimeoutError as error:
                logger.exception("Timeout durant l'analyse Stockfish.")
                raise StockfishTimeoutError(
                    message=(
                        "L'analyse Stockfish a dépassé le temps maximal "
                        "autorisé."
                    ),
                    cause=error
                ) from error
            except asyncio.CancelledError:
                raise
            except Exception as error:
                logger.exception("Erreur durant l'analyse Stockfish.")
                raise StockfishAnalysisError(
                    message="Impossible d'analyser la position.",
                    cause=error
                ) from error

            position_evaluation = self._build_evaluation(
                board=board,
                info=raw_analysis
            )

            if count:
                self._analyzed_positions += 1

            duration_ms = (
                perf_counter() - started_at
            ) * MILLISECONDS_PER_SECOND
            self._last_analysis_duration_ms = duration_ms

        logger.info(
            "Analyse Stockfish terminée en %.2f ms.",
            duration_ms
        )
        return position_evaluation

    async def _analyze_with_timeout(
        self,
        engine: chess.engine.SimpleEngine,
        board: chess.Board
    ) -> StockfishAnalysis:
        """Exécute l'analyse bloquante avec un délai maximal sûr."""
        analysis_task = asyncio.create_task(
            asyncio.to_thread(self._run_engine_analysis, engine, board)
        )

        try:
            return await asyncio.wait_for(
                asyncio.shield(analysis_task),
                timeout=settings.stockfish_timeout_seconds
            )
        except TimeoutError:
            await self._abort_analysis(engine, analysis_task)
            raise
        except asyncio.CancelledError:
            await self._abort_analysis(engine, analysis_task)
            raise

    def _run_engine_analysis(
        self,
        engine: chess.engine.SimpleEngine,
        board: chess.Board
    ) -> StockfishAnalysis:
        """Exécute l'appel synchrone à python-chess."""
        return engine.analyse(
            board,
            chess.engine.Limit(depth=settings.stockfish_depth),
            multipv=settings.top_moves
        )

    async def _abort_analysis(
        self,
        engine: chess.engine.SimpleEngine,
        analysis_task: asyncio.Task[StockfishAnalysis]
    ) -> None:
        """Interrompt un moteur après un timeout ou une annulation."""
        if self._engine is engine:
            self._engine = None

        try:
            # Annuler seulement la coroutine ``to_thread`` laisserait son thread
            # actif. Fermer le transport interrompt réellement la commande UCI.
            await asyncio.to_thread(engine.close)
        except Exception:
            logger.exception(
                "Impossible de forcer l'arrêt d'une analyse Stockfish."
            )

        analysis_task.cancel()

        with suppress(asyncio.CancelledError, Exception):
            await analysis_task

    # Construction

    def _build_evaluation(
        self,
        *,
        board: chess.Board,
        info: StockfishAnalysis
    ) -> PositionEvaluation:
        """Construit une évaluation complète."""
        evaluations = self._normalize_analysis(info)

        if not evaluations:
            raise StockfishResponseError(
                message="Stockfish n'a retourné aucune évaluation."
            )

        principal = evaluations[0]
        relative_score = self._get_principal_score(principal).relative
        best_move = self._build_best_move(
            board=board,
            evaluation=principal
        )

        # Le schéma EngineAnalysis impose un meilleur coup. Une position sans
        # coup exploitable produit donc une erreur métier explicite.
        if best_move is None:
            raise StockfishResponseError(
                message="Stockfish n'a retourné aucun coup exploitable."
            )

        alternatives = [
            alternative
            for evaluation in evaluations[1:]
            if (
                alternative := self._build_best_move(
                    board=board,
                    evaluation=evaluation
                )
            )
            is not None
        ]
        evaluation = Evaluation(
            score=float(self._convert_score(relative_score)),
            evaluation_type=self._get_score_type(relative_score),
            depth=self._get_depth(principal),
            nodes=self._get_nodes(principal),
            time_ms=self._get_engine_time_ms(principal)
        )
        principal_variation = PrincipalVariation(
            moves=[
                move.uci()
                for move in self._get_principal_variation(principal)
            ],
            evaluation=evaluation
        )
        engine_analysis = EngineAnalysis(
            best_move=best_move,
            evaluation=evaluation,
            principal_variation=principal_variation,
            alternatives=alternatives
        )

        return PositionEvaluation(engine=engine_analysis)

    def _build_best_move(
        self,
        *,
        board: chess.Board,
        evaluation: chess.engine.InfoDict
    ) -> BestMove | None:
        """Construit un meilleur coup depuis une évaluation."""
        principal_variation = self._get_principal_variation(evaluation)

        if not principal_variation:
            return None

        score = evaluation.get("score")

        if not isinstance(score, chess.engine.PovScore):
            return None

        move = principal_variation[0]
        relative_score = score.relative

        try:
            san = board.san(move)
        except (AssertionError, ValueError):
            # L'UCI reste un repli exploitable si une réponse moteur inattendue
            # ne peut pas être convertie en notation SAN.
            logger.warning(
                "Impossible de convertir le coup %s en SAN.",
                move.uci()
            )
            san = move.uci()

        return BestMove(
            uci=move.uci(),
            san=san,
            from_square=chess.square_name(move.from_square),
            to_square=chess.square_name(move.to_square),
            score=float(self._convert_score(relative_score)),
            evaluation_type=self._get_score_type(relative_score),
            depth=self._get_depth(evaluation),
            principal_variation=[
                variation_move.uci()
                for variation_move in principal_variation
            ]
        )

    def _convert_score(self, score: chess.engine.Score) -> int:
        """Convertit un score Stockfish en valeur métier."""
        if score.is_mate():
            mate = score.mate()
            return mate if mate is not None else 0

        centipawns = score.score()
        return centipawns if centipawns is not None else 0

    def _get_score_type(
        self,
        score: chess.engine.Score
    ) -> EvaluationType:
        """Retourne le type d'évaluation."""
        if score.is_mate():
            return EvaluationType.MATE

        return EvaluationType.CENTIPAWN

    def _get_depth(self, evaluation: Mapping[str, object]) -> int:
        """Retourne la profondeur réellement atteinte."""
        depth = evaluation.get("depth")

        if isinstance(depth, bool) or not isinstance(depth, int):
            return MINIMUM_DEPTH

        return max(depth, MINIMUM_DEPTH)

    # Informations

    def is_ready(self) -> bool:
        """Indique si le moteur Stockfish est démarré."""
        return self._engine is not None

    def get_analyzed_count(self) -> int:
        """Retourne le nombre de positions analysées."""
        return self._analyzed_positions

    def get_last_analysis_duration(self) -> float | None:
        """Retourne la durée de la dernière analyse."""
        return self._last_analysis_duration_ms

    # Santé

    async def ping(self) -> bool:
        """Vérifie que le moteur Stockfish peut analyser une position."""
        try:
            await self.analyze_position(
                FenRequest(fen=chess.STARTING_FEN),
                count=False
            )
        except StockfishError:
            logger.exception("Le moteur Stockfish est indisponible.")
            return False
        except Exception:
            logger.exception("Erreur inattendue lors du test Stockfish.")
            return False

        return True

    async def health(self) -> StockfishServiceStatus:
        """Retourne l'état de santé du service."""
        available = await self.ping()

        return {
            "service": SERVICE_NAME,
            "is_ready": self.is_ready(),
            "available": available,
            "engine": Path(settings.stockfish_path).name,
            "depth": settings.stockfish_depth,
            "threads": settings.stockfish_threads,
            "hash_mb": settings.stockfish_hash_mb,
            "timeout_seconds": float(settings.stockfish_timeout_seconds),
            "top_moves": settings.top_moves,
            "analyzed_positions": self.get_analyzed_count(),
            "last_analysis_duration_ms": (
                self.get_last_analysis_duration()
            ),
        }