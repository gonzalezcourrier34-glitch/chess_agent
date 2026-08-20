"""Initialisation des données de démonstration MongoDB.

Ce script ajoute un petit jeu de données consacré aux ouvertures
d'échecs dans MongoDB.

Il permet notamment :

- d'initialiser les ouvertures de démonstration ;
- d'ajouter leur contenu théorique ;
- d'éviter les doublons grâce aux opérations upsert ;
- de vérifier les données insérées ;
- d'afficher un bilan d'exécution.

Le script réutilise exclusivement le module de connexion MongoDB du
projet.

Il ne contient aucune logique utilisée directement par l'application.
"""

from __future__ import annotations

import asyncio
import sys
from collections.abc import Mapping, Sequence
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from pymongo import ASCENDING
from pymongo.errors import PyMongoError
from pymongo.operations import UpdateOne

# Le dossier backend doit être accessible lorsque le script est lancé
# directement depuis la racine du projet.
BACKEND_DIRECTORY = Path(__file__).resolve().parents[1]

if str(BACKEND_DIRECTORY) not in sys.path:
    sys.path.insert(0, str(BACKEND_DIRECTORY))

from app.core.constants import OPENING_THEORIES_COLLECTION, OPENINGS_COLLECTION
from app.core.exceptions import DatabaseOperationError
from app.core.logging import get_logger
from app.database.mongodb import MongoCollection, disconnect, get_collection, initialize

logger = get_logger(__name__)


# Types

MongoDocument = dict[str, Any]

SeedResult = dict[str, int]


# Configuration

# La version permet d'identifier le jeu de données ayant produit les
# documents présents dans MongoDB.
SEED_VERSION = "1.0.0"

SEED_SOURCE = "chess_agent_seed"

# Les insertions sont regroupées afin de limiter les allers-retours avec
# MongoDB.
ORDERED_BULK_OPERATIONS = False


# Données

# Les ouvertures suivantes couvrent plusieurs familles importantes :
#
# - jeu ouvert ;
# - défense semi-ouverte ;
# - défense fermée ;
# - ouverture de pion dame ;
# - système positionnel.
#
# Elles pourront ensuite être enrichies depuis Wikichess ou une autre
# source documentaire.

OPENINGS: tuple[MongoDocument, ...] = (
    {
        "slug": "italian-game",
        "eco": "C50",
        "name": "Italian Game",
        "variation": None,
        "family": "Open Game",
        "moves": ["e4", "e5", "Nf3", "Nc6", "Bc4"],
        "starting_fen": (
            "r1bqkbnr/pppp1ppp/2n5/4p3/2B1P3/5N2/PPPP1PPP/RNBQK2R b KQkq - 3 3"
        ),
        "difficulty": "beginner",
        "description": (
            "Ouverture classique fondée sur un développement rapide, "
            "le contrôle du centre et une pression précoce sur f7."
        ),
        "tags": ["open-game", "development", "f7", "beginner"],
    },
    {
        "slug": "ruy-lopez",
        "eco": "C60",
        "name": "Ruy Lopez",
        "variation": None,
        "family": "Open Game",
        "moves": ["e4", "e5", "Nf3", "Nc6", "Bb5"],
        "starting_fen": (
            "r1bqkbnr/pppp1ppp/2n5/1B2p3/4P3/5N2/PPPP1PPP/RNBQK2R b KQkq - 3 3"
        ),
        "difficulty": "intermediate",
        "description": (
            "Ouverture stratégique dans laquelle les Blancs mettent "
            "la pression sur le défenseur du pion e5."
        ),
        "tags": ["open-game", "strategy", "center", "intermediate"],
    },
    {
        "slug": "sicilian-defense",
        "eco": "B20",
        "name": "Sicilian Defense",
        "variation": None,
        "family": "Sicilian Defense",
        "moves": ["e4", "c5"],
        "starting_fen": (
            "rnbqkbnr/pp1ppppp/8/2p5/4P3/8/PPPP1PPP/RNBQKBNR w KQkq - 0 2"
        ),
        "difficulty": "advanced",
        "description": (
            "Défense asymétrique dans laquelle les Noirs contestent "
            "le centre et recherchent un contre-jeu actif."
        ),
        "tags": ["semi-open-game", "counterplay", "asymmetry", "advanced"],
    },
    {
        "slug": "french-defense",
        "eco": "C00",
        "name": "French Defense",
        "variation": None,
        "family": "French Defense",
        "moves": ["e4", "e6"],
        "starting_fen": (
            "rnbqkbnr/pppp1ppp/4p3/8/4P3/8/PPPP1PPP/RNBQKBNR w KQkq - 0 2"
        ),
        "difficulty": "intermediate",
        "description": (
            "Défense solide préparant d5, avec une structure centrale "
            "fermée et un contre-jeu fréquent sur l'aile dame."
        ),
        "tags": ["semi-open-game", "pawn-chain", "counterplay", "intermediate"],
    },
    {
        "slug": "queens-gambit",
        "eco": "D06",
        "name": "Queen's Gambit",
        "variation": None,
        "family": "Queen's Pawn Game",
        "moves": ["d4", "d5", "c4"],
        "starting_fen": (
            "rnbqkbnr/ppp1pppp/8/3p4/2PP4/8/PP2PPPP/RNBQKBNR b KQkq - 0 2"
        ),
        "difficulty": "intermediate",
        "description": (
            "Ouverture de pion dame dans laquelle les Blancs proposent "
            "le pion c4 afin de détourner le pion d5."
        ),
        "tags": ["closed-game", "queens-pawn", "center", "intermediate"],
    },
    {
        "slug": "kings-indian-defense",
        "eco": "E60",
        "name": "King's Indian Defense",
        "variation": None,
        "family": "Indian Defense",
        "moves": ["d4", "Nf6", "c4", "g6"],
        "starting_fen": (
            "rnbqkb1r/pppppp1p/5np1/8/2PP4/8/PP2PPPP/RNBQKBNR w KQkq - 0 3"
        ),
        "difficulty": "advanced",
        "description": (
            "Défense hypermoderne dans laquelle les Noirs autorisent "
            "un large centre blanc avant de le contre-attaquer."
        ),
        "tags": ["closed-game", "hypermodern", "kingside", "advanced"],
    },
)


OPENING_THEORIES: tuple[MongoDocument, ...] = (
    {
        "opening_slug": "italian-game",
        "overview": (
            "L'Italienne développe rapidement le fou en c4 et vise "
            "la case f7, souvent fragile au début de la partie."
        ),
        "strategic_ideas": [
            "Développer rapidement les pièces mineures.",
            "Roquer tôt afin de sécuriser le roi.",
            "Préparer la poussée d4 avec c3.",
            "Maintenir une pression sur f7.",
        ],
        "tactical_patterns": [
            "Attaque sur f7.",
            "Sacrifice temporaire en e5.",
            "Clouage du cavalier f6.",
            "Ouverture de la colonne e.",
        ],
        "typical_plans_white": [
            "Jouer c3 puis d4.",
            "Développer le fou dame en g5 ou e3.",
            "Placer une tour sur e1.",
        ],
        "typical_plans_black": [
            "Développer le cavalier en f6.",
            "Jouer Bc5 ou Be7.",
            "Contester le centre avec d5.",
        ],
        "common_mistakes": [
            "Attaquer f7 sans développement suffisant.",
            "Retarder inutilement le roque.",
            "Jouer d4 sans préparation.",
        ],
    },
    {
        "opening_slug": "ruy-lopez",
        "overview": (
            "L'Espagnole exerce une pression durable sur le cavalier "
            "c6 et sur le pion e5."
        ),
        "strategic_ideas": [
            "Augmenter progressivement la pression sur e5.",
            "Préserver le fou de cases blanches.",
            "Préparer c3 et d4.",
            "Exploiter l'espace au centre.",
        ],
        "tactical_patterns": [
            "Prise en c6 suivie de Nxe5.",
            "Clouage du cavalier c6.",
            "Attaque sur la colonne e.",
            "Sacrifices sur f7.",
        ],
        "typical_plans_white": [
            "Roquer rapidement.",
            "Jouer Re1, c3 et d4.",
            "Replier le fou en a4 puis b3.",
        ],
        "typical_plans_black": [
            "Jouer a6 et b5.",
            "Développer le fou en e7.",
            "Préparer d5 ou f5.",
        ],
        "common_mistakes": [
            "Prendre en c6 sans comprendre la structure obtenue.",
            "Négliger la défense du pion e5.",
            "Déplacer plusieurs fois le fou sans nécessité.",
        ],
    },
    {
        "opening_slug": "sicilian-defense",
        "overview": (
            "La Sicilienne crée immédiatement une structure "
            "asymétrique et un jeu riche en possibilités tactiques."
        ),
        "strategic_ideas": [
            "Contester d4 avec le pion c.",
            "Créer un contre-jeu sur la colonne c.",
            "Utiliser la majorité de pions à l'aile dame.",
            "Accepter un développement parfois plus lent.",
        ],
        "tactical_patterns": [
            "Sacrifice sur e6.",
            "Attaque opposée sur les deux ailes.",
            "Pression sur la colonne c.",
            "Rupture d5.",
        ],
        "typical_plans_white": [
            "Jouer d4 et ouvrir le centre.",
            "Développer rapidement les pièces.",
            "Lancer une attaque à l'aile roi.",
        ],
        "typical_plans_black": [
            "Développer avec d6, Nf6 et Nc6.",
            "Créer du contre-jeu sur la colonne c.",
            "Préparer d5 ou b5.",
        ],
        "common_mistakes": [
            "Jouer passivement sans contre-jeu.",
            "Retarder le développement du roi.",
            "Pousser les pions d'aile trop tôt.",
        ],
    },
    {
        "opening_slug": "french-defense",
        "overview": (
            "La Française construit une chaîne de pions solide mais "
            "enferme temporairement le fou de cases blanches."
        ),
        "strategic_ideas": [
            "Attaquer la base de la chaîne blanche.",
            "Préparer les ruptures c5 et f6.",
            "Accepter un espace réduit temporaire.",
            "Réactiver le fou c8.",
        ],
        "tactical_patterns": [
            "Rupture f6.",
            "Pression sur d4.",
            "Sacrifice sur e6.",
            "Attaque du roi resté au centre.",
        ],
        "typical_plans_white": [
            "Gagner de l'espace avec e5.",
            "Soutenir le centre avec c3.",
            "Attaquer à l'aile roi.",
        ],
        "typical_plans_black": [
            "Jouer c5 rapidement.",
            "Attaquer d4.",
            "Développer le fou par d7 ou b7.",
        ],
        "common_mistakes": [
            "Bloquer définitivement le fou c8.",
            "Oublier la rupture c5.",
            "Échanger le mauvais pion central.",
        ],
    },
    {
        "opening_slug": "queens-gambit",
        "overview": (
            "Le Gambit Dame vise à affaiblir le contrôle noir du centre "
            "plutôt qu'à sacrifier réellement un pion."
        ),
        "strategic_ideas": [
            "Attaquer le point d5.",
            "Développer naturellement les pièces.",
            "Créer une majorité centrale.",
            "Exploiter la colonne c.",
        ],
        "tactical_patterns": [
            "Récupération du pion c4.",
            "Pression sur c7.",
            "Rupture e4.",
            "Clouage du cavalier f6.",
        ],
        "typical_plans_white": [
            "Développer Nc3 et Nf3.",
            "Jouer e3 puis Bxc4.",
            "Occuper la colonne c.",
        ],
        "typical_plans_black": [
            "Soutenir d5 avec e6.",
            "Contester le centre avec c5.",
            "Développer le fou de cases blanches.",
        ],
        "common_mistakes": [
            "Tenter de conserver le pion c4 à tout prix.",
            "Retarder le développement.",
            "Créer un pion dame isolé sans compensation.",
        ],
    },
    {
        "opening_slug": "kings-indian-defense",
        "overview": (
            "L'Est-Indienne autorise les Blancs à construire un centre "
            "large avant de le cibler avec des ruptures de pions."
        ),
        "strategic_ideas": [
            "Contrôler le centre à distance.",
            "Préparer e5 ou c5.",
            "Créer une attaque à l'aile roi.",
            "Exploiter les cases noires.",
        ],
        "tactical_patterns": [
            "Rupture f5.",
            "Sacrifice sur g3.",
            "Attaque sur la colonne f.",
            "Contre-jeu central avec c6.",
        ],
        "typical_plans_white": [
            "Occuper le centre avec e4.",
            "Gagner de l'espace à l'aile dame.",
            "Ouvrir les colonnes c et b.",
        ],
        "typical_plans_black": [
            "Roquer rapidement.",
            "Préparer e5 puis f5.",
            "Lancer une attaque contre le roi blanc.",
        ],
        "common_mistakes": [
            "Attaquer avant d'avoir fermé le centre.",
            "Négliger le contre-jeu blanc à l'aile dame.",
            "Jouer f5 sans préparation.",
        ],
    },
)


# Dates


def utc_now() -> datetime:
    """Retourne la date courante en UTC."""

    return datetime.now(UTC)


# Normalisation


def normalize_required_text(value: Any, field_name: str) -> str:
    """Valide et normalise un texte obligatoire."""

    if not isinstance(value, str):
        raise ValueError(f"Le champ '{field_name}' doit être une chaîne.")

    normalized_value = " ".join(value.split())

    if not normalized_value:
        raise ValueError(f"Le champ '{field_name}' ne peut pas être vide.")

    return normalized_value


def normalize_document(
    document: Mapping[str, Any], *, identifier_field: str
) -> MongoDocument:
    """Normalise un document avant son insertion."""

    if not isinstance(document, Mapping):
        raise ValueError("Chaque document de seed doit être un mapping.")

    normalized_document = dict(document)

    normalized_document[identifier_field] = normalize_required_text(
        normalized_document.get(identifier_field), identifier_field
    )

    now = utc_now()

    # Les informations de seed permettent d'identifier clairement
    # l'origine et la version des données de démonstration.
    normalized_document.update(
        {"seed_source": SEED_SOURCE, "seed_version": SEED_VERSION, "updated_at": now}
    )

    return normalized_document


def normalize_documents(
    documents: Sequence[Mapping[str, Any]], *, identifier_field: str
) -> list[MongoDocument]:
    """Normalise un ensemble de documents."""

    normalized_documents: list[MongoDocument] = []

    seen_identifiers: set[str] = set()

    for document in documents:
        normalized_document = normalize_document(
            document, identifier_field=identifier_field
        )

        identifier = normalized_document[identifier_field]

        if identifier in seen_identifiers:
            raise ValueError(
                f"Identifiant dupliqué dans le jeu de données : {identifier}."
            )

        seen_identifiers.add(identifier)

        normalized_documents.append(normalized_document)

    return normalized_documents


# Indexes


async def create_indexes(
    openings_collection: MongoCollection, theories_collection: MongoCollection
) -> None:
    """Crée les indexes nécessaires aux données de référence."""

    # Le slug constitue l'identifiant métier stable d'une ouverture.
    await openings_collection.create_index(
        [("slug", ASCENDING)], unique=True, name="openings_slug_unique"
    )

    # Le code ECO est souvent utilisé pour filtrer les ouvertures.
    await openings_collection.create_index([("eco", ASCENDING)], name="openings_eco")

    # Une seule fiche théorique est conservée par ouverture.
    await theories_collection.create_index(
        [("opening_slug", ASCENDING)], unique=True, name="opening_theories_slug_unique"
    )

    logger.info("Indexes MongoDB vérifiés.")


# Opérations


def build_upsert_operations(
    documents: Sequence[Mapping[str, Any]], *, identifier_field: str
) -> list[UpdateOne]:
    """Construit les opérations upsert MongoDB."""

    operations: list[UpdateOne] = []

    for document in documents:
        identifier = document[identifier_field]

        # created_at est renseigné uniquement lors de la première
        # insertion. Les exécutions suivantes mettent à jour le contenu
        # sans perdre la date d'origine.
        update_document = {
            "$set": dict(document),
            "$setOnInsert": {"created_at": utc_now()},
        }

        operations.append(
            UpdateOne({identifier_field: identifier}, update_document, upsert=True)
        )

    return operations


async def upsert_documents(
    collection: MongoCollection,
    documents: Sequence[Mapping[str, Any]],
    *,
    identifier_field: str,
) -> SeedResult:
    """Insère ou met à jour des documents."""

    if not documents:
        return {"matched": 0, "modified": 0, "upserted": 0}

    operations = build_upsert_operations(documents, identifier_field=identifier_field)

    try:
        result = await collection.bulk_write(
            operations, ordered=ORDERED_BULK_OPERATIONS
        )

    except PyMongoError as error:
        logger.exception("Échec de l'écriture des données MongoDB.")

        raise DatabaseOperationError(
            message=(
                "Impossible d'enregistrer les données de démonstration dans MongoDB."
            ),
            cause=error,
        ) from error

    return {
        "matched": result.matched_count,
        "modified": result.modified_count,
        "upserted": result.upserted_count,
    }


# Vérification


async def count_seeded_documents(collection: MongoCollection) -> int:
    """Compte les documents produits par ce script."""

    try:
        return await collection.count_documents({"seed_source": SEED_SOURCE})

    except PyMongoError as error:
        logger.exception("Impossible de compter les documents MongoDB.")

        raise DatabaseOperationError(
            message=("Impossible de vérifier les données de démonstration."),
            cause=error,
        ) from error


# Exécution


async def seed_mongodb() -> None:
    """Initialise les données de démonstration MongoDB."""

    logger.info("Démarrage de l'initialisation des données MongoDB.")

    await initialize()

    openings_collection = get_collection(OPENINGS_COLLECTION)

    theories_collection = get_collection(OPENING_THEORIES_COLLECTION)

    try:
        # Les documents sont entièrement validés avant la première
        # écriture afin d'éviter une initialisation partielle due à une
        # erreur présente dans le jeu de données.
        openings = normalize_documents(OPENINGS, identifier_field="slug")

        theories = normalize_documents(
            OPENING_THEORIES, identifier_field="opening_slug"
        )

        await create_indexes(openings_collection, theories_collection)

        openings_result = await upsert_documents(
            openings_collection, openings, identifier_field="slug"
        )

        theories_result = await upsert_documents(
            theories_collection, theories, identifier_field="opening_slug"
        )

        openings_count = await count_seeded_documents(openings_collection)

        theories_count = await count_seeded_documents(theories_collection)

        logger.info(
            "Initialisation MongoDB terminée : "
            "%s ouverture(s), %s fiche(s) théorique(s).",
            openings_count,
            theories_count,
        )

        print()
        print("Initialisation MongoDB terminée.")
        print(f"Collection : {OPENINGS_COLLECTION}")
        print(f"Documents présents : {openings_count}")
        print(f"Insertions : {openings_result['upserted']}")
        print(f"Mises à jour : {openings_result['modified']}")
        print()
        print(f"Collection : {OPENING_THEORIES_COLLECTION}")
        print(f"Documents présents : {theories_count}")
        print(f"Insertions : {theories_result['upserted']}")
        print(f"Mises à jour : {theories_result['modified']}")

    finally:
        # Le script possède le client créé pour son exécution. Il doit
        # donc toujours le fermer, même après une erreur.
        await disconnect()


async def main() -> int:
    """Exécute le script et retourne son code de sortie."""

    try:
        await seed_mongodb()

    except (DatabaseOperationError, PyMongoError, ValueError) as error:
        logger.exception("Initialisation MongoDB impossible.")

        print(f"Erreur : {error}")

        return 1

    except Exception as error:
        logger.exception("Erreur inattendue pendant l'initialisation MongoDB.")

        print(f"Erreur inattendue : {error}")

        return 1

    return 0


# Entrée

if __name__ == "__main__":
    raise SystemExit(asyncio.run(main()))
