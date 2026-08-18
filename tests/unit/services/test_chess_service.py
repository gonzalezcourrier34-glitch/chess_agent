"""Tests unitaires du service métier ChessService."""

from __future__ import annotations

import chess
import pytest

from app.core.exceptions import InvalidMoveError
from app.schemas.chess.position import FenRequest
from app.schemas.common.enums import (
    ChessColor,
    MoveNotation,
)
from app.services.chess_service import ChessService


# Configuration

STARTING_FEN = chess.STARTING_FEN

BLACK_TO_MOVE_FEN = (
    "rnbqkbnr/pppppppp/8/8/8/8/"
    "PPPPPPPP/RNBQKBNR b KQkq - 0 1"
)

EN_PASSANT_FEN = (
    "rnbqkbnr/ppp1p1pp/8/3pPp2/8/8/"
    "PPPP1PPP/RNBQKBNR w KQkq f6 0 3"
)

CASTLING_FEN = (
    "r3k2r/8/8/8/8/8/8/R3K2R "
    "w KQkq - 0 1"
)

PROMOTION_FEN = (
    "7k/P7/8/8/8/8/8/7K "
    "w - - 0 1"
)

STALEMATE_FEN = (
    "7k/5Q2/6K1/8/8/8/8/8 "
    "b - - 0 1"
)

CHECKMATE_FEN = (
    "7k/6Q1/6K1/8/8/8/8/8 "
    "b - - 0 1"
)

INSUFFICIENT_MATERIAL_FEN = (
    "7k/8/8/8/8/8/8/K7 "
    "w - - 0 1"
)


# Fixtures

@pytest.fixture
def service() -> ChessService:
    """Construit le service testé."""

    return ChessService()


# Construction de l'échiquier

def test_create_board(
    service: ChessService,
) -> None:
    """Vérifie la création d'un échiquier depuis une FEN."""

    board = service._create_board(
        STARTING_FEN
    )

    assert isinstance(
        board,
        chess.Board,
    )

    assert board.fen() == STARTING_FEN


# Position

def test_get_position(
    service: ChessService,
) -> None:
    """Vérifie la construction d'une position."""

    request = FenRequest(
        fen=STARTING_FEN,
    )

    result = service.get_position(
        request
    )

    assert result.fen == STARTING_FEN

    assert (
        result.active_color
        is ChessColor.WHITE
    )

    assert result.fullmove_number == 1
    assert result.halfmove_clock == 0
    assert result.castling_rights == "KQkq"
    assert result.en_passant_square is None
    assert result.is_check is False
    assert result.is_checkmate is False
    assert result.is_stalemate is False
    assert result.is_game_over is False


def test_build_position(
    service: ChessService,
) -> None:
    """Vérifie la conversion d'un board en BoardPosition."""

    board = chess.Board(
        BLACK_TO_MOVE_FEN
    )

    result = service.build_position(
        board
    )

    assert result.fen == BLACK_TO_MOVE_FEN

    assert (
        result.active_color
        is ChessColor.BLACK
    )


def test_build_position_with_en_passant(
    service: ChessService,
) -> None:
    """Vérifie l'exposition de la case en passant."""

    board = chess.Board()

    board.push_uci("e2e4")
    board.push_uci("d7d5")
    board.push_uci("e4e5")
    board.push_uci("f7f5")

    result = service.build_position(
        board
    )

    assert (
        result.en_passant_square
        == "f6"
    )

def test_build_position_without_castling_rights(
    service: ChessService,
) -> None:
    """Vérifie l'absence de droits de roque."""

    board = chess.Board(
        INSUFFICIENT_MATERIAL_FEN
    )

    result = service.build_position(
        board
    )

    assert result.castling_rights == "-"


def test_build_position_checkmate(
    service: ChessService,
) -> None:
    """Vérifie une position d'échec et mat."""

    result = service.build_position(
        chess.Board(
            CHECKMATE_FEN
        )
    )

    assert result.is_check is True
    assert result.is_checkmate is True
    assert result.is_game_over is True


def test_build_position_stalemate(
    service: ChessService,
) -> None:
    """Vérifie une position de pat."""

    result = service.build_position(
        chess.Board(
            STALEMATE_FEN
        )
    )

    assert result.is_stalemate is True
    assert result.is_game_over is True


# Couleur

def test_get_active_color_white(
    service: ChessService,
) -> None:
    """Vérifie le trait aux blancs."""

    assert (
        service.get_active_color(
            STARTING_FEN
        )
        is ChessColor.WHITE
    )


def test_get_active_color_black(
    service: ChessService,
) -> None:
    """Vérifie le trait aux noirs."""

    assert (
        service.get_active_color(
            BLACK_TO_MOVE_FEN
        )
        is ChessColor.BLACK
    )


def test_get_board_color_white(
    service: ChessService,
) -> None:
    """Vérifie la conversion interne du trait blanc."""

    board = chess.Board(
        STARTING_FEN
    )

    assert (
        service._get_board_color(
            board
        )
        is ChessColor.WHITE
    )


def test_get_board_color_black(
    service: ChessService,
) -> None:
    """Vérifie la conversion interne du trait noir."""

    board = chess.Board(
        BLACK_TO_MOVE_FEN
    )

    assert (
        service._get_board_color(
            board
        )
        is ChessColor.BLACK
    )


# Contexte

def test_get_context(
    service: ChessService,
) -> None:
    """Vérifie le contexte complet d'une position."""

    request = FenRequest(
        fen=STARTING_FEN,
    )

    context = service.get_context(
        request
    )

    assert context.board.fen == STARTING_FEN
    assert len(context.legal_moves) == 20
    assert context.last_move is None
    assert context.is_draw is False


# Nulle

def test_is_draw_false(
    service: ChessService,
) -> None:
    """Vérifie une position non nulle."""

    board = chess.Board()

    assert (
        service._is_draw(board)
        is False
    )


def test_is_draw_for_insufficient_material(
    service: ChessService,
) -> None:
    """Vérifie une nulle par matériel insuffisant."""

    board = chess.Board(
        INSUFFICIENT_MATERIAL_FEN
    )

    assert (
        service._is_draw(board)
        is True
    )


def test_is_draw_for_stalemate(
    service: ChessService,
) -> None:
    """Vérifie une nulle par pat."""

    board = chess.Board(
        STALEMATE_FEN
    )

    assert (
        service._is_draw(board)
        is True
    )


# Coups légaux

def test_build_legal_moves(
    service: ChessService,
) -> None:
    """Vérifie la construction des coups légaux."""

    board = chess.Board()

    moves = service._build_legal_moves(
        board
    )

    assert len(moves) == 20

    assert any(
        move.uci == "e2e4"
        for move in moves
    )

    assert any(
        move.san == "e4"
        for move in moves
    )


def test_get_legal_moves(
    service: ChessService,
) -> None:
    """Vérifie l'API publique des coups légaux."""

    request = FenRequest(
        fen=STARTING_FEN,
    )

    moves = service.get_legal_moves(
        request
    )

    assert len(moves) == 20


def test_is_legal_move_with_uci(
    service: ChessService,
) -> None:
    """Vérifie un coup UCI légal."""

    assert (
        service.is_legal_move(
            STARTING_FEN,
            "e2e4",
        )
        is True
    )


def test_is_legal_move_with_san(
    service: ChessService,
) -> None:
    """Vérifie un coup SAN légal."""

    assert (
        service.is_legal_move(
            STARTING_FEN,
            "e4",
        )
        is True
    )


def test_is_legal_move_returns_false(
    service: ChessService,
) -> None:
    """Vérifie un coup illégal."""

    assert (
        service.is_legal_move(
            STARTING_FEN,
            "e2e5",
        )
        is False
    )


# Validation du coup

def test_ensure_legal_move_accepts_legal_move(
    service: ChessService,
) -> None:
    """Vérifie un coup réellement légal."""

    board = chess.Board()

    move = chess.Move.from_uci(
        "e2e4"
    )

    result = service._ensure_legal_move(
        board,
        move,
    )

    assert result is None


def test_ensure_legal_move_rejects_illegal_move(
    service: ChessService,
) -> None:
    """Vérifie un coup syntaxiquement valide mais illégal."""

    board = chess.Board()

    move = chess.Move.from_uci(
        "e2e5"
    )

    with pytest.raises(
        InvalidMoveError,
        match="n'est pas légal",
    ):
        service._ensure_legal_move(
            board,
            move,
        )


# Construction d'un coup

def test_build_move(
    service: ChessService,
) -> None:
    """Vérifie un coup classique."""

    board = chess.Board()

    move = chess.Move.from_uci(
        "e2e4"
    )

    result = service.build_move(
        board,
        move,
    )

    assert result.uci == "e2e4"
    assert result.san == "e4"
    assert result.from_square == "e2"
    assert result.to_square == "e4"
    assert result.is_capture is False
    assert result.is_check is False
    assert result.is_checkmate is False
    assert result.is_castling is False
    assert result.is_promotion is False
    assert result.promotion_piece is None


def test_build_move_capture(
    service: ChessService,
) -> None:
    """Vérifie la détection d'une capture."""

    board = chess.Board()

    board.push_uci("e2e4")
    board.push_uci("d7d5")

    move = chess.Move.from_uci(
        "e4d5"
    )

    result = service.build_move(
        board,
        move,
    )

    assert result.is_capture is True
    assert result.san == "exd5"


def test_build_move_castling(
    service: ChessService,
) -> None:
    """Vérifie la détection du roque."""

    board = chess.Board(
        CASTLING_FEN
    )

    move = chess.Move.from_uci(
        "e1g1"
    )

    result = service.build_move(
        board,
        move,
    )

    assert result.is_castling is True
    assert result.san == "O-O"


def test_build_move_promotion(
    service: ChessService,
) -> None:
    """Vérifie la promotion."""

    board = chess.Board(
        PROMOTION_FEN
    )

    move = chess.Move.from_uci(
        "a7a8q"
    )

    result = service.build_move(
        board,
        move,
    )

    assert result.is_promotion is True

    assert (
        result.promotion_piece
        == "queen"
    )


# Analyse automatique SAN / UCI

def test_parse_move_uci(
    service: ChessService,
) -> None:
    """Vérifie la détection automatique d'un coup UCI."""

    board = chess.Board()

    move = service.parse_move(
        board,
        "e2e4",
    )

    assert move.uci() == "e2e4"


def test_parse_move_san(
    service: ChessService,
) -> None:
    """Vérifie le repli automatique sur SAN."""

    board = chess.Board()

    move = service.parse_move(
        board,
        "e4",
    )

    assert move.uci() == "e2e4"


def test_parse_move_rejects_invalid_move(
    service: ChessService,
) -> None:
    """Vérifie une notation totalement invalide."""

    board = chess.Board()

    with pytest.raises(
        InvalidMoveError
    ):
        service.parse_move(
            board,
            "not-a-move",
        )


# UCI

def test_parse_uci_move(
    service: ChessService,
) -> None:
    """Vérifie un coup UCI."""

    board = chess.Board()

    move = service.parse_uci_move(
        board,
        " e2e4 ",
    )

    assert move.uci() == "e2e4"


def test_parse_uci_move_rejects_invalid_notation(
    service: ChessService,
) -> None:
    """Vérifie une notation UCI invalide."""

    board = chess.Board()

    with pytest.raises(
        InvalidMoveError,
        match="notation UCI valide",
    ):
        service.parse_uci_move(
            board,
            "hello",
        )


def test_parse_uci_move_rejects_illegal_move(
    service: ChessService,
) -> None:
    """Vérifie un coup UCI valide mais illégal."""

    board = chess.Board()

    with pytest.raises(
        InvalidMoveError,
        match="n'est pas légal",
    ):
        service.parse_uci_move(
            board,
            "e2e5",
        )


# SAN

def test_parse_san_move(
    service: ChessService,
) -> None:
    """Vérifie un coup SAN."""

    board = chess.Board()

    move = service.parse_san_move(
        board,
        " e4 ",
    )

    assert move.uci() == "e2e4"


@pytest.mark.parametrize(
    "move",
    [
        "invalid",
        "Qa9",
        "e5",
    ],
)
def test_parse_san_move_rejects_invalid_move(
    service: ChessService,
    move: str,
) -> None:
    """Vérifie une notation SAN invalide ou illégale."""

    board = chess.Board()

    with pytest.raises(
        InvalidMoveError,
        match="SAN valide ou légale",
    ):
        service.parse_san_move(
            board,
            move,
        )


# Conversion

def test_convert_move_uci_to_san(
    service: ChessService,
) -> None:
    """Vérifie la conversion UCI vers SAN."""

    result = service.convert_move(
        fen=STARTING_FEN,
        move="e2e4",
        source=MoveNotation.UCI,
        target=MoveNotation.SAN,
    )

    assert result == "e4"


def test_convert_move_san_to_uci(
    service: ChessService,
) -> None:
    """Vérifie la conversion SAN vers UCI."""

    result = service.convert_move(
        fen=STARTING_FEN,
        move="e4",
        source=MoveNotation.SAN,
        target=MoveNotation.UCI,
    )

    assert result == "e2e4"


def test_convert_move_uci_to_uci(
    service: ChessService,
) -> None:
    """Vérifie une conversion conservant UCI."""

    result = service.convert_move(
        fen=STARTING_FEN,
        move="e2e4",
        source=MoveNotation.UCI,
        target=MoveNotation.UCI,
    )

    assert result == "e2e4"


def test_convert_move_san_to_san(
    service: ChessService,
) -> None:
    """Vérifie une conversion conservant SAN."""

    result = service.convert_move(
        fen=STARTING_FEN,
        move="e4",
        source=MoveNotation.SAN,
        target=MoveNotation.SAN,
    )

    assert result == "e4"


def test_convert_to_san(
    service: ChessService,
) -> None:
    """Vérifie le raccourci UCI vers SAN."""

    assert (
        service.convert_to_san(
            STARTING_FEN,
            "e2e4",
        )
        == "e4"
    )


def test_convert_to_uci(
    service: ChessService,
) -> None:
    """Vérifie le raccourci SAN vers UCI."""

    assert (
        service.convert_to_uci(
            STARTING_FEN,
            "e4",
        )
        == "e2e4"
    )


# Historique

def test_convert_uci_history_to_san(
    service: ChessService,
) -> None:
    """Vérifie la conversion d'un historique complet."""

    result = (
        service
        .convert_uci_history_to_san(
            [
                "e2e4",
                "e7e5",
                "g1f3",
                "b8c6",
                "f1b5",
            ]
        )
    )

    assert result == [
        "e4",
        "e5",
        "Nf3",
        "Nc6",
        "Bb5",
    ]


def test_convert_uci_history_to_san_empty(
    service: ChessService,
) -> None:
    """Vérifie un historique vide."""

    assert (
        service
        .convert_uci_history_to_san([])
        == []
    )


def test_convert_uci_history_to_san_rejects_invalid_sequence(
    service: ChessService,
) -> None:
    """Vérifie un historique incohérent."""

    with pytest.raises(
        InvalidMoveError
    ):
        service.convert_uci_history_to_san(
            [
                "e2e4",
                "e2e3",
            ]
        )


# Application

def test_apply_move_uci(
    service: ChessService,
) -> None:
    """Vérifie l'application d'un coup UCI."""

    result = service.apply_move(
        STARTING_FEN,
        "e2e4",
    )

    assert result.uci == "e2e4"
    assert result.san == "e4"
    assert result.from_square == "e2"
    assert result.to_square == "e4"
    assert result.before_fen == STARTING_FEN
    assert result.after_fen != STARTING_FEN
    assert result.move_number == 1


def test_apply_move_san(
    service: ChessService,
) -> None:
    """Vérifie l'application d'un coup SAN."""

    result = service.apply_move(
        STARTING_FEN,
        "e4",
    )

    assert result.uci == "e2e4"
    assert result.san == "e4"


def test_apply_move_resulting_fen(
    service: ChessService,
) -> None:
    """Vérifie précisément la FEN après e4."""

    result = service.apply_move(
        STARTING_FEN,
        "e2e4",
    )

    board = chess.Board()

    board.push_uci(
        "e2e4"
    )

    assert (
        result.after_fen
        == board.fen()
    )


# FEN résultante

def test_get_resulting_fen_uci(
    service: ChessService,
) -> None:
    """Vérifie la FEN résultant d'un coup UCI."""

    result = service.get_resulting_fen(
        STARTING_FEN,
        "e2e4",
    )

    board = chess.Board()

    board.push_uci(
        "e2e4"
    )

    assert result == board.fen()


def test_get_resulting_fen_san(
    service: ChessService,
) -> None:
    """Vérifie la FEN résultant d'un coup SAN."""

    result = service.get_resulting_fen(
        STARTING_FEN,
        "e4",
    )

    board = chess.Board()

    board.push_san(
        "e4"
    )

    assert result == board.fen()


# Disponibilité

def test_ping_returns_true(
    service: ChessService,
) -> None:
    """Vérifie que python-chess répond."""

    assert service.ping() is True


def test_is_ready_returns_ping(
    service: ChessService,
) -> None:
    """Vérifie la disponibilité du service."""

    assert service.is_ready() is True


def test_ping_returns_false_on_exception(
    service: ChessService,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Vérifie une erreur inattendue de python-chess."""

    def fail_validation(
        board: chess.Board,
    ) -> None:
        del board

        raise RuntimeError(
            "python-chess failure"
        )

    monkeypatch.setattr(
        "app.services.chess_service."
        "validate_board",
        fail_validation,
    )

    assert service.ping() is False


# Santé

def test_health(
    service: ChessService,
) -> None:
    """Vérifie le rapport de santé."""

    result = service.health()

    assert result == {
        "service": "chess",
        "is_ready": True,
        "available": True,
        "library": "python-chess",
        "version": chess.__version__,
    }


def test_health_when_ping_fails(
    service: ChessService,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Vérifie le rapport lorsque python-chess échoue."""

    monkeypatch.setattr(
        service,
        "ping",
        lambda: False,
    )

    result = service.health()

    assert result["service"] == "chess"
    assert result["is_ready"] is False
    assert result["available"] is False
    assert result["library"] == "python-chess"

    assert (
        result["version"]
        == chess.__version__
    )