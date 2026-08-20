"""Connexion MongoDB du projet Chess Agent.

Ce module centralise :

- la création du client MongoDB ;
- l'initialisation de la connexion ;
- l'accès à la base de données ;
- l'accès aux collections ;
- la vérification de l'état de MongoDB ;
- la fermeture du client.

Aucune logique métier ne doit être implémentée dans ce module.

Le cycle de vie de la connexion est géré par le module ``lifespan``.
"""

from __future__ import annotations

from threading import Lock
from time import perf_counter
from typing import Any

from pymongo import AsyncMongoClient
from pymongo.asynchronous.collection import AsyncCollection
from pymongo.asynchronous.database import AsyncDatabase
from pymongo.errors import PyMongoError

# Les paramètres sont centralisés dans app.core.config.Settings.
#
# mongodb_uri                          URI de connexion à MongoDB.
# mongodb_database                     Nom de la base de données.
# mongodb_server_selection_timeout_ms  Timeout de sélection du serveur.
# mongodb_max_pool_size                Taille maximale du pool.
from app.core.config import settings
from app.core.constants import (
    ANALYSES_COLLECTION,
    CACHE_COLLECTION,
    DOCUMENTS_COLLECTION,
    FAVORITES_COLLECTION,
    INVALID_COLLECTION_CHARACTER,
    MONGODB_PING_COMMAND,
    OPENING_THEORIES_COLLECTION,
    OPENINGS_COLLECTION,
    POSITIONS_COLLECTION,
    SETTINGS_COLLECTION,
    USER_HISTORIES_COLLECTION,
    USERS_COLLECTION,
    VIDEOS_COLLECTION,
)
from app.core.exceptions import ConfigurationError, DatabaseConnectionError
from app.core.logging import get_logger

logger = get_logger(__name__)


# Types

MongoDocument = dict[str, Any]

MongoClient = AsyncMongoClient

MongoDatabase = AsyncDatabase

MongoCollection = AsyncCollection

MongoHealthStatus = dict[str, Any]


# Collections

# Ces alias regroupent les collections utilisées par le projet.
#
# Les valeurs réelles restent centralisées dans constants.py afin
# d'éviter toute divergence entre MongoDB, les repositories et les
# services métier.
MONGO_COLLECTIONS = frozenset(
    {
        OPENINGS_COLLECTION,
        OPENING_THEORIES_COLLECTION,
        POSITIONS_COLLECTION,
        ANALYSES_COLLECTION,
        DOCUMENTS_COLLECTION,
        VIDEOS_COLLECTION,
        USERS_COLLECTION,
        USER_HISTORIES_COLLECTION,
        FAVORITES_COLLECTION,
        CACHE_COLLECTION,
        SETTINGS_COLLECTION,
    }
)


# État

# Le client MongoDB est partagé par l'ensemble de l'application.
#
# Il est créé une seule fois puis réutilisé jusqu'à l'arrêt de
# l'application.
_client: MongoClient | None = None

# Le verrou protège uniquement la création et le remplacement de la
# référence globale. Les opérations MongoDB restent asynchrones.
_client_lock = Lock()


# Validation


def get_required_setting(value: str | None, setting_name: str) -> str:
    """Retourne une configuration obligatoire nettoyée."""

    # Cette validation fournit une erreur de configuration explicite
    # avant toute tentative de connexion.
    normalized_value = str(value or "").strip()

    if not normalized_value:
        raise ConfigurationError(
            message=(f"La configuration MongoDB '{setting_name}' est obligatoire.")
        )

    return normalized_value


def normalize_collection_name(name: str) -> str:
    """Valide et normalise un nom de collection MongoDB."""

    # Une validation explicite évite de transmettre à PyMongo une valeur
    # absente ou d'un type inattendu.
    if not isinstance(name, str):
        raise ValueError(
            "Le nom de la collection MongoDB doit être une chaîne de caractères."
        )

    collection_name = name.strip()

    if not collection_name:
        raise ValueError("Le nom de la collection MongoDB est obligatoire.")

    # MongoDB interdit le caractère nul dans les noms de collections.
    if INVALID_COLLECTION_CHARACTER in collection_name:
        raise ValueError(
            "Le nom de la collection MongoDB contient un caractère interdit."
        )

    return collection_name


# Connexion


def connect() -> MongoClient:
    """Retourne le client MongoDB partagé."""

    global _client

    # Le client existant est retourné immédiatement sans reprendre le
    # verrou.
    if _client is not None:
        return _client

    with _client_lock:
        # Un second contrôle est nécessaire, car un autre thread peut
        # avoir créé le client pendant l'attente du verrou.
        if _client is not None:
            return _client

        mongodb_uri = get_required_setting(settings.mongodb_uri, "mongodb_uri")

        # AsyncMongoClient établit les connexions réelles à la demande.
        # La commande ping d'initialize() déclenchera la vérification du
        # serveur.
        _client = AsyncMongoClient(
            mongodb_uri,
            serverSelectionTimeoutMS=(settings.mongodb_server_selection_timeout_ms),
            maxPoolSize=settings.mongodb_max_pool_size,
        )

    return _client


async def initialize() -> MongoClient:
    """Initialise et vérifie la connexion MongoDB."""

    global _client

    client = connect()

    try:
        # La commande ping force la sélection d'un serveur et vérifie
        # immédiatement que MongoDB est joignable.
        await client.admin.command(MONGODB_PING_COMMAND)

    except (ConfigurationError, PyMongoError) as error:
        # La référence globale est supprimée afin qu'une prochaine
        # tentative reparte d'un client neuf.
        with _client_lock:
            if _client is client:
                _client = None

        try:
            await client.close()

        except Exception:
            # Une erreur de fermeture ne doit pas masquer la cause
            # initiale de l'échec de connexion.
            logger.exception(
                "Erreur lors de la fermeture du client MongoDB "
                "après un échec d'initialisation."
            )

        logger.exception("Impossible d'initialiser la connexion MongoDB.")

        raise DatabaseConnectionError(
            message="Impossible d'initialiser MongoDB."
        ) from error

    logger.info("Connexion MongoDB initialisée.")

    return client


async def disconnect() -> None:
    """Ferme le client MongoDB partagé."""

    global _client

    # La référence est retirée sous verrou avant la fermeture réelle.
    # Une future demande pourra ainsi créer un nouveau client.
    with _client_lock:
        client = _client
        _client = None

    if client is None:
        return

    try:
        await client.close()

    except PyMongoError as error:
        logger.exception("Erreur lors de la fermeture du client MongoDB.")

        raise DatabaseConnectionError(
            message=("Impossible de fermer proprement le client MongoDB.")
        ) from error

    logger.info("Client MongoDB fermé.")


# Accès aux données


def get_database() -> MongoDatabase:
    """Retourne la base MongoDB configurée."""

    database_name = get_required_setting(settings.mongodb_database, "mongodb_database")

    # L'accès par crochets ne déclenche pas immédiatement une opération
    # réseau. Il retourne un objet représentant la base.
    return connect()[database_name]


def get_collection(name: str) -> MongoCollection:
    """Retourne une collection MongoDB."""

    collection_name = normalize_collection_name(name)

    # L'accès par crochets retourne un objet collection réutilisable par
    # les repositories et les services de persistance.
    return get_database()[collection_name]


async def collection_exists(name: str) -> bool:
    """Indique si une collection existe."""

    collection_name = normalize_collection_name(name)

    try:
        collection_names = await get_database().list_collection_names()

    except PyMongoError as error:
        logger.exception("Impossible de récupérer les collections MongoDB.")

        raise DatabaseConnectionError(
            message=("Impossible de vérifier l'existence de la collection MongoDB.")
        ) from error

    return collection_name in collection_names


# Informations


def is_initialized() -> bool:
    """Indique si un client MongoDB a été créé."""

    return _client is not None


# Santé


async def ping() -> bool:
    """Teste la disponibilité de MongoDB."""

    try:
        # Si aucun client n'existe, connect() le crée à la demande.
        # La commande ping réalise ensuite la vérification réseau réelle.
        client = connect()

        await client.admin.command(MONGODB_PING_COMMAND)

    except (ConfigurationError, PyMongoError):
        logger.exception("MongoDB est indisponible.")

        return False

    except Exception:
        logger.exception("Erreur inattendue lors du test MongoDB.")

        return False

    return True


async def health() -> MongoHealthStatus:
    """Retourne l'état de santé de MongoDB."""

    started_at = perf_counter()

    available = await ping()

    latency_ms = round((perf_counter() - started_at) * 1_000, 2)

    database_name: str | None = None

    try:
        database_name = get_required_setting(
            settings.mongodb_database, "mongodb_database"
        )

    except ConfigurationError:
        # Une configuration absente est reflétée dans le diagnostic sans
        # provoquer l'échec de l'endpoint de supervision.
        logger.exception("Nom de base MongoDB non configuré.")

    return {
        "service": "mongodb",
        "is_initialized": is_initialized(),
        "available": available,
        "database": database_name,
        "latency_ms": latency_ms,
        "server_selection_timeout_ms": (settings.mongodb_server_selection_timeout_ms),
        "max_pool_size": settings.mongodb_max_pool_size,
    }
