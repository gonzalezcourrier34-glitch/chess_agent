"""Initialisation de la collection vectorielle Milvus.

Ce script prépare l'infrastructure vectorielle utilisée par le moteur
RAG de Chess Agent.

Il permet notamment :

- de charger le modèle d'embedding ;
- de récupérer la dimension réelle des vecteurs ;
- d'initialiser le client Milvus ;
- de recréer la collection lorsque cette option est activée ;
- de créer et charger l'index vectoriel ;
- de vérifier la disponibilité des services ;
- d'afficher un bilan d'initialisation.

La création du schéma, de la collection et de l'index reste entièrement
déléguée au MilvusService.

Le script ne charge aucun document Wikichess.
"""

from __future__ import annotations

import asyncio
import sys
from pathlib import Path
from typing import Any

# Chemins

# Le dossier backend doit être disponible dans sys.path lorsque le
# script est exécuté directement depuis la racine du projet.
BACKEND_DIRECTORY = Path(__file__).resolve().parents[1]

if str(BACKEND_DIRECTORY) not in sys.path:
    sys.path.insert(0, str(BACKEND_DIRECTORY))


from app.adapters.embedding_service import EmbeddingService
from app.adapters.milvus_service import MilvusService
from app.core.config import settings
from app.core.exceptions import (
    ConfigurationError,
    EmbeddingModelUnavailableError,
    MilvusConnectionError,
    MilvusIndexError,
    MilvusOperationError,
)
from app.core.logging import get_logger

logger = get_logger(__name__)


# Types

InitializationStatus = dict[str, Any]


# Validation


def validate_vector_dimension(dimension: int) -> int:
    """Valide une dimension vectorielle."""

    # Les booléens héritent de int en Python, mais ne représentent pas
    # une dimension vectorielle exploitable.
    if isinstance(dimension, bool) or not isinstance(dimension, int) or dimension < 1:
        raise ConfigurationError(
            message=(
                "La dimension du modèle d'embedding "
                "doit être un entier supérieur à zéro."
            )
        )

    return dimension


def validate_dimensions(embedding_dimension: int, milvus_dimension: int) -> None:
    """Vérifie la cohérence des dimensions vectorielles."""

    if embedding_dimension == milvus_dimension:
        return

    raise ConfigurationError(
        message=(
            "La dimension du modèle d'embedding "
            "ne correspond pas à celle de Milvus : "
            f"{embedding_dimension} contre "
            f"{milvus_dimension}."
        )
    )


# Collection


async def recreate_collection(milvus_service: MilvusService) -> None:
    """Recrée la collection Milvus lorsque cette option est activée."""

    if not settings.milvus_recreate_collection:
        return

    logger.warning(
        "Recréation demandée pour la collection Milvus %s.",
        milvus_service.collection_name,
    )

    await milvus_service.drop_collection()

    # drop_collection() marque la collection comme non prête.
    # Un nouveau démarrage recrée alors la collection avec la dimension
    # actuelle du modèle d'embedding.
    await milvus_service.start()

    logger.info(
        "Collection Milvus %s recréée avec une dimension de %s.",
        milvus_service.collection_name,
        milvus_service.get_vector_dimension(),
    )


# Construction


async def create_services() -> tuple[EmbeddingService, MilvusService]:
    """Construit et initialise les services vectoriels."""

    embedding_service = EmbeddingService()
    milvus_service: MilvusService | None = None

    try:
        # Le modèle doit être chargé avant Milvus afin de récupérer la
        # dimension réelle des embeddings.
        await embedding_service.start()

        vector_dimension = validate_vector_dimension(embedding_service.get_dimension())

        # Milvus utilise exactement la dimension exposée par le modèle.
        milvus_service = MilvusService(vector_dimension=vector_dimension)

        await milvus_service.start()

        await recreate_collection(milvus_service)

    except Exception:
        if milvus_service is not None:
            await milvus_service.close()

        await embedding_service.close()

        raise

    return (embedding_service, milvus_service)


# Vérification


async def build_initialization_status(
    embedding_service: EmbeddingService, milvus_service: MilvusService
) -> InitializationStatus:
    """Construit le bilan d'initialisation."""

    embedding_health = await embedding_service.health()

    milvus_health = await milvus_service.health()

    embedding_dimension = validate_vector_dimension(embedding_service.get_dimension())

    milvus_dimension = validate_vector_dimension(milvus_service.get_vector_dimension())

    validate_dimensions(embedding_dimension, milvus_dimension)

    available = bool(embedding_health.get("available")) and bool(
        milvus_health.get("available")
    )

    return {
        "available": available,
        "recreated": settings.milvus_recreate_collection,
        "embedding": embedding_health,
        "milvus": milvus_health,
        "embedding_dimension": embedding_dimension,
        "milvus_dimension": milvus_dimension,
        "collection": milvus_service.collection_name,
        "metric_type": milvus_service.metric_type,
        "index_type": milvus_service.index_type,
    }


def display_status(initialization_status: InitializationStatus) -> None:
    """Affiche le bilan d'initialisation."""

    embedding_status = initialization_status.get("embedding", {})

    milvus_status = initialization_status.get("milvus", {})

    print()
    print("Initialisation Milvus terminée.")
    print()
    print(
        "État global : "
        f"{'disponible' if initialization_status['available'] else 'indisponible'}"
    )
    print(f"Modèle d'embedding : {embedding_status.get('model')}")
    print(f"Dimension des embeddings : {initialization_status['embedding_dimension']}")
    print(f"Dimension Milvus : {initialization_status['milvus_dimension']}")
    print(f"Collection Milvus : {initialization_status['collection']}")
    print(f"Collection recréée : {initialization_status['recreated']}")
    print(f"Métrique : {initialization_status['metric_type']}")
    print(f"Type d'index : {initialization_status['index_type']}")
    print(f"Milvus disponible : {milvus_status.get('available', False)}")
    print(f"Milvus prêt : {milvus_status.get('is_ready', False)}")


# Initialisation


async def initialize_milvus() -> InitializationStatus:
    """Initialise la collection vectorielle Milvus."""

    logger.info("Démarrage de l'initialisation Milvus.")

    embedding_service: EmbeddingService | None = None
    milvus_service: MilvusService | None = None

    try:
        (embedding_service, milvus_service) = await create_services()

        initialization_status = await build_initialization_status(
            embedding_service, milvus_service
        )

        if not initialization_status["available"]:
            raise MilvusConnectionError(
                message=("La chaîne vectorielle n'est pas entièrement disponible.")
            )

        logger.info(
            "Collection Milvus %s initialisée avec une dimension de %s.",
            milvus_service.collection_name,
            milvus_service.get_vector_dimension(),
        )

        return initialization_status

    finally:
        # Le script possède les instances créées. Elles sont toujours
        # fermées à la fin de l'exécution.
        if milvus_service is not None:
            await milvus_service.close()

        if embedding_service is not None:
            await embedding_service.close()


# Exécution


async def main() -> int:
    """Exécute le script et retourne son code de sortie."""

    try:
        initialization_status = await initialize_milvus()

    except (
        ConfigurationError,
        EmbeddingModelUnavailableError,
        MilvusConnectionError,
        MilvusIndexError,
        MilvusOperationError,
    ) as error:
        logger.exception("Initialisation Milvus impossible.")

        print()
        print(f"Erreur : {error}")

        return 1

    except Exception as error:
        logger.exception("Erreur inattendue pendant l'initialisation Milvus.")

        print()
        print(f"Erreur inattendue : {error}")

        return 1

    display_status(initialization_status)

    return 0


# Entrée


if __name__ == "__main__":
    raise SystemExit(asyncio.run(main()))
