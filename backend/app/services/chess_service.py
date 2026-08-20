"""Service métier dédié à la manipulation des positions d'échecs.

Ce service centralise les opérations métier reposant sur python-chess :

- création et lecture d'une position ;
- récupération des coups légaux ;
- validation des coups ;
- conversion SAN / UCI ;
- conversion d'un historique UCI vers SAN ;
- application d'un coup.

Les opérations techniques communes restent déléguées à chess_utils.
"""

from __future__ import annotations

from typing import Any

import chess

from app.core.exceptions import InvalidMoveError
from app.core.logging import get_logger
from app.schemas.chess.move import LegalMove, PlayedMove
from app.schemas.chess.position import BoardPosition, FenRequest, PositionContext
from app.schemas.common.enums import ChessColor, MoveNotation
from app.utils.chess_utils import (
    create_board,
    normalize_move,
    normalize_notation,
    validate_board,
    validate_chess_move,
)

logger = get_logger(__name__)


# Types

ChessServiceStatus = dict[str, Any]


# Service


class ChessService:
    """Service métier de manipulation des positions."""

    # Construction

    def _create_board(self, fen: str) -> chess.Board:
        """Construit un échiquier à partir d'une FEN."""

        return create_board(fen)

    # Position

    def get_position(self, request: FenRequest) -> BoardPosition:
        """Construit une position depuis une FEN."""

        board = self._create_board(request.fen)

        return self.build_position(board)

    def build_position(self, board: chess.Board) -> BoardPosition:
        """Construit un schéma BoardPosition."""

        validate_board(board)

        return BoardPosition(
            fen=board.fen(),
            active_color=self._get_board_color(board),
            fullmove_number=board.fullmove_number,
            halfmove_clock=board.halfmove_clock,
            castling_rights=(board.castling_xfen() if board.castling_rights else "-"),
            en_passant_square=(
                chess.square_name(board.ep_square)
                if board.ep_square is not None
                else None
            ),
            is_check=board.is_check(),
            is_checkmate=board.is_checkmate(),
            is_stalemate=board.is_stalemate(),
            is_game_over=board.is_game_over(claim_draw=True),
        )

    def get_active_color(self, fen: str) -> ChessColor:
        """Retourne le joueur ayant le trait."""

        board = self._create_board(fen)

        return self._get_board_color(board)

    def _get_board_color(self, board: chess.Board) -> ChessColor:
        """Retourne la couleur ayant le trait."""

        validate_board(board)

        if board.turn == chess.WHITE:
            return ChessColor.WHITE

        return ChessColor.BLACK

    def get_context(self, request: FenRequest) -> PositionContext:
        """Construit le contexte complet d'une position."""

        board = self._create_board(request.fen)

        return PositionContext(
            board=self.build_position(board),
            legal_moves=self._build_legal_moves(board),
            last_move=None,
            is_draw=self._is_draw(board),
        )

    def _is_draw(self, board: chess.Board) -> bool:
        """Indique si une position est une nulle."""

        validate_board(board)

        return (
            board.is_stalemate()
            or board.is_insufficient_material()
            or board.is_seventyfive_moves()
            or board.is_fivefold_repetition()
            or board.can_claim_draw()
        )

    # Coups légaux

    def _build_legal_moves(self, board: chess.Board) -> list[LegalMove]:
        """Construit les coups légaux d'un échiquier."""

        validate_board(board)

        return [self.build_move(board, move) for move in board.legal_moves]

    def get_legal_moves(self, request: FenRequest) -> list[LegalMove]:
        """Retourne les coups légaux d'une position."""

        board = self._create_board(request.fen)

        return self._build_legal_moves(board)

    def is_legal_move(self, fen: str, move: str) -> bool:
        """Indique si un coup est légal."""

        board = self._create_board(fen)

        try:
            self.parse_move(board, move)

        except InvalidMoveError:
            return False

        return True

    def _ensure_legal_move(self, board: chess.Board, move: chess.Move) -> None:
        """Vérifie qu'un coup est légal dans la position."""

        validate_board(board)

        validate_chess_move(move)

        if move not in board.legal_moves:
            raise InvalidMoveError(
                message=("Le coup fourni n'est pas légal dans cette position.")
            )

    def build_move(self, board: chess.Board, move: chess.Move) -> LegalMove:
        """Construit un schéma représentant un coup légal."""

        self._ensure_legal_move(board, move)

        san = board.san(move)

        resulting_board = board.copy(stack=False)

        resulting_board.push(move)

        return LegalMove(
            uci=move.uci(),
            san=san,
            from_square=chess.square_name(move.from_square),
            to_square=chess.square_name(move.to_square),
            is_capture=board.is_capture(move),
            is_check=resulting_board.is_check(),
            is_checkmate=resulting_board.is_checkmate(),
            is_castling=board.is_castling(move),
            is_promotion=(move.promotion is not None),
            promotion_piece=(
                chess.piece_name(move.promotion) if move.promotion is not None else None
            ),
        )

    # Analyse des notations

    def parse_move(self, board: chess.Board, move: str) -> chess.Move:
        """Analyse automatiquement une notation SAN ou UCI."""

        validate_board(board)

        normalized_move = normalize_move(move)

        try:
            return self.parse_uci_move(board, normalized_move)

        except InvalidMoveError:
            return self.parse_san_move(board, normalized_move)

    def parse_uci_move(self, board: chess.Board, move: str) -> chess.Move:
        """Analyse un coup UCI."""

        validate_board(board)

        normalized_move = normalize_move(move)

        try:
            parsed_move = chess.Move.from_uci(normalized_move)

        except ValueError as error:
            raise InvalidMoveError(
                message=("Le coup fourni n'est pas une notation UCI valide.")
            ) from error

        self._ensure_legal_move(board, parsed_move)

        return parsed_move

    def parse_san_move(self, board: chess.Board, move: str) -> chess.Move:
        """Analyse un coup SAN."""

        validate_board(board)

        normalized_move = normalize_move(move)

        try:
            parsed_move = board.parse_san(normalized_move)

        except (
            chess.AmbiguousMoveError,
            chess.IllegalMoveError,
            chess.InvalidMoveError,
            ValueError,
        ) as error:
            raise InvalidMoveError(
                message=("Le coup fourni n'est pas une notation SAN valide ou légale.")
            ) from error

        validate_chess_move(parsed_move)

        return parsed_move

    # Conversion

    def convert_move(
        self, fen: str, move: str, source: MoveNotation, target: MoveNotation
    ) -> str:
        """Convertit un coup entre deux notations."""

        board = self._create_board(fen)

        source_notation = normalize_notation(source, required=True)

        target_notation = normalize_notation(target, required=True)

        if source_notation is MoveNotation.UCI:
            parsed_move = self.parse_uci_move(board, move)

        else:
            parsed_move = self.parse_san_move(board, move)

        if target_notation is MoveNotation.SAN:
            return board.san(parsed_move)

        return parsed_move.uci()

    def convert_to_san(self, fen: str, move: str) -> str:
        """Convertit un coup UCI vers la notation SAN."""

        return self.convert_move(
            fen=fen, move=move, source=MoveNotation.UCI, target=MoveNotation.SAN
        )

    def convert_to_uci(self, fen: str, move: str) -> str:
        """Convertit un coup SAN vers la notation UCI."""

        return self.convert_move(
            fen=fen, move=move, source=MoveNotation.SAN, target=MoveNotation.UCI
        )

    def convert_uci_history_to_san(self, moves: list[str]) -> list[str]:
        """Convertit un historique UCI complet vers la notation SAN."""

        board = chess.Board()

        san_moves: list[str] = []

        for move in moves:
            parsed_move = self.parse_uci_move(board, move)

            san_moves.append(board.san(parsed_move))

            board.push(parsed_move)

        return san_moves

    # Application

    def apply_move(self, fen: str, move: str) -> PlayedMove:
        """Applique un coup sur une position."""

        board = self._create_board(fen)

        before_fen = board.fen()

        move_number = board.fullmove_number

        parsed_move = self.parse_move(board, move)

        legal_move = self.build_move(board, parsed_move)

        board.push(parsed_move)

        return PlayedMove(
            uci=legal_move.uci,
            san=legal_move.san,
            from_square=legal_move.from_square,
            to_square=legal_move.to_square,
            before_fen=before_fen,
            after_fen=board.fen(),
            move_number=move_number,
        )

    def get_resulting_fen(self, fen: str, move: str) -> str:
        """Retourne la FEN obtenue après un coup."""

        board = self._create_board(fen)

        parsed_move = self.parse_move(board, move)

        board.push(parsed_move)

        return board.fen()

    # Informations

    def is_ready(self) -> bool:
        """Indique si python-chess est opérationnel."""

        return self.ping()

    # Santé

    def ping(self) -> bool:
        """Vérifie que python-chess est opérationnel."""

        try:
            board = chess.Board()

            validate_board(board)

            next(iter(board.legal_moves), None)

        except Exception:
            logger.exception("La bibliothèque python-chess est indisponible.")

            return False

        return True

    def health(self) -> ChessServiceStatus:
        """Retourne l'état de santé du service."""

        available = self.ping()

        return {
            "service": "chess",
            "is_ready": available,
            "available": available,
            "library": "python-chess",
            "version": chess.__version__,
        }
