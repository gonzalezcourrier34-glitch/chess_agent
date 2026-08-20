"""Fonctions utilitaires liées aux positions d'échecs.

Ce module regroupe les opérations techniques communes autour de
python-chess :

- création d'un échiquier ;
- validation des objets python-chess ;
- normalisation des entrées utilisateur.

Il ne dépend d'aucun service métier.
"""

from __future__ import annotations

from typing import Literal, overload

import chess
from app.core.exceptions import (
    InvalidBoardStateError,
    InvalidFenError,
    InvalidMoveError,
    InvalidNotationError,
)
from app.schemas.common.enums import MoveNotation

# Configuration

# Les notations explicitement prises en charge par le projet.
#
# Cette constante protège le contrat du module si MoveNotation est
# enrichi ultérieurement avec d'autres valeurs.
SUPPORTED_NOTATIONS = frozenset({MoveNotation.UCI, MoveNotation.SAN})


# Normalisation


def normalize_fen(fen: str) -> str:
    """Nettoie et valide une position FEN."""

    # Une validation explicite produit une erreur métier plus claire
    # qu'une erreur technique levée directement par python-chess.
    if not isinstance(fen, str):
        raise InvalidFenError(
            message=("La position FEN doit être une chaîne de caractères.")
        )

    # Les espaces multiples, tabulations et retours à la ligne sont
    # remplacés par un unique espace entre les champs du FEN.
    normalized_fen = " ".join(fen.split())

    if not normalized_fen:
        raise InvalidFenError(message=("La position FEN ne peut pas être vide."))

    return normalized_fen


def normalize_move(move: str) -> str:
    """Nettoie et valide un coup."""

    # Les coups sont reçus depuis l'API ou le workflow sous forme de
    # chaînes SAN ou UCI.
    if not isinstance(move, str):
        raise InvalidMoveError(message=("Le coup doit être une chaîne de caractères."))

    normalized_move = move.strip()

    if not normalized_move:
        raise InvalidMoveError(message=("Le coup ne peut pas être vide."))

    return normalized_move


@overload
def normalize_notation(
    notation: MoveNotation | str, *, required: Literal[True]
) -> MoveNotation: ...


@overload
def normalize_notation(
    notation: MoveNotation | str | None, *, required: Literal[False] = False
) -> MoveNotation | None: ...


def normalize_notation(
    notation: MoveNotation | str | None, *, required: bool = False
) -> MoveNotation | None:
    """Normalise une notation de coup."""

    # Une notation facultative peut rester absente.
    # Lorsqu'elle est exigée par l'appelant, une erreur métier est
    # produite immédiatement.
    if notation is None:
        if required:
            raise InvalidNotationError(message=("La notation du coup est obligatoire."))

        return None

    # Une valeur déjà normalisée peut être retournée directement.
    if isinstance(notation, MoveNotation):
        if notation not in SUPPORTED_NOTATIONS:
            raise InvalidNotationError(
                message=("La notation fournie n'est pas prise en charge.")
            )

        return notation

    if not isinstance(notation, str):
        raise InvalidNotationError(
            message=("La notation du coup doit être une chaîne.")
        )

    normalized_notation = notation.strip().lower()

    if not normalized_notation:
        raise InvalidNotationError(
            message=("La notation du coup ne peut pas être vide.")
        )

    try:
        parsed_notation = MoveNotation(normalized_notation)

    except ValueError as error:
        raise InvalidNotationError(
            message=("La notation doit être 'uci' ou 'san'.")
        ) from error

    # Cette vérification protège le module si MoveNotation accueille
    # ultérieurement d'autres systèmes de notation.
    if parsed_notation not in SUPPORTED_NOTATIONS:
        raise InvalidNotationError(
            message=("La notation fournie n'est pas prise en charge.")
        )

    return parsed_notation


# Validation


def validate_board(board: chess.Board) -> None:
    """Vérifie qu'un échiquier est valide."""

    # Les services métier doivent toujours recevoir un objet
    # python-chess correctement construit.
    if not isinstance(board, chess.Board):
        raise InvalidBoardStateError(
            message=("L'échiquier doit être une instance de chess.Board.")
        )

    # python-chess peut représenter certaines positions techniquement
    # construites mais incohérentes selon les règles des échecs.
    if not board.is_valid():
        raise InvalidBoardStateError(message=("La position d'échecs est invalide."))


def validate_chess_move(move: chess.Move) -> None:
    """Vérifie qu'un coup python-chess est valide."""

    if not isinstance(move, chess.Move):
        raise InvalidMoveError(
            message=("Le coup doit être une instance de chess.Move.")
        )

    # Le coup nul appartient au protocole UCI, mais il ne représente
    # pas un coup jouable par l'utilisateur dans Chess Agent.
    if move == chess.Move.null():
        raise InvalidMoveError(message=("Le coup nul n'est pas autorisé."))


# Construction


def create_board(fen: str) -> chess.Board:
    """Construit un échiquier depuis une position FEN."""

    normalized_fen = normalize_fen(fen)

    try:
        # La construction est confiée à python-chess après la
        # normalisation de l'entrée.
        board = chess.Board(normalized_fen)

    except ValueError as error:
        raise InvalidFenError(
            message=("La position FEN fournie est invalide.")
        ) from error

    # Une seconde validation est nécessaire, car certaines positions
    # peuvent être construites tout en restant structurellement
    # incohérentes.
    validate_board(board)

    return board


# Vérification


def validate_fen(fen: str) -> bool:
    """Indique si une position FEN est exploitable."""

    try:
        create_board(fen)

    except InvalidFenError:
        return False

    return True
