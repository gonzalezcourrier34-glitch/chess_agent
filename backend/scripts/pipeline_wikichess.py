"""Pipeline complet de préparation du corpus Wikichess.

Ce module orchestre les trois étapes principales du corpus RAG :

- le téléchargement des présentations Wikichess ;
- l'initialisation de la collection vectorielle Milvus ;
- l'ingestion des présentations préparées dans Milvus.

Il ne contient aucune logique de téléchargement, d'embedding,
de création de collection ou d'insertion.

Chaque responsabilité reste déléguée aux scripts spécialisés :

- download_wikichess.py ;
- initialize_milvus.py ;
- ingest_wikichess.py.
"""

from __future__ import annotations

import asyncio
import sys
from pathlib import Path
from time import perf_counter

# Chemins

BACKEND_DIRECTORY = Path(__file__).resolve().parents[1]

if str(BACKEND_DIRECTORY) not in sys.path:
    sys.path.insert(0, str(BACKEND_DIRECTORY))


# Imports applicatifs

from app.core.exceptions import (
    ConfigurationError,
    EmbeddingGenerationError,
    EmbeddingModelUnavailableError,
    MilvusConnectionError,
    MilvusIndexError,
    MilvusInsertionError,
    MilvusOperationError,
    MilvusValidationError,
)
from app.core.logging import get_logger

from scripts.download_wikichess import ArticlePayload, download_wikichess
from scripts.download_wikichess import display_report as display_download_report
from scripts.ingest_wikichess import display_report as display_ingestion_report
from scripts.ingest_wikichess import ingest_wikichess
from scripts.initialize_milvus import InitializationStatus, initialize_milvus
from scripts.initialize_milvus import display_status as display_initialization_status
from scripts.schemas.wikichess_script import DownloadFailure, IngestionReport

logger = get_logger(__name__)


# Types

PipelineDownloadResult = tuple[list[ArticlePayload], list[DownloadFailure], float]

PipelineResult = tuple[PipelineDownloadResult, InitializationStatus, IngestionReport]


# Pipeline


async def run_wikichess_pipeline() -> PipelineResult:
    """Exécute le pipeline complet du corpus Wikichess."""

    started_at = perf_counter()

    logger.info("Démarrage du pipeline Wikichess.")

    # Téléchargement

    logger.info("Étape 1/3 : téléchargement des présentations Wikichess.")

    (articles, failures, download_duration_ms) = await download_wikichess()

    display_download_report(
        articles=articles, failures=failures, duration_ms=download_duration_ms
    )

    # Vérification du corpus

    if not articles:
        raise RuntimeError(
            "Le pipeline est interrompu car aucune présentation "
            "Wikichess n'a été téléchargée."
        )

    if failures:
        logger.warning(
            "Le corpus Wikichess est partiel : %s téléchargement(s) en échec.",
            len(failures),
        )

    # Initialisation Milvus

    logger.info("Étape 2/3 : initialisation de la collection Milvus.")

    initialization_status = await initialize_milvus()

    display_initialization_status(initialization_status)

    if not initialization_status.get("available", False):
        raise MilvusConnectionError(
            message=(
                "L'ingestion est interrompue car la chaîne "
                "vectorielle n'est pas disponible."
            )
        )

    # Ingestion

    logger.info("Étape 3/3 : ingestion des présentations dans Milvus.")

    ingestion_report = await ingest_wikichess()

    display_ingestion_report(ingestion_report)

    # Bilan

    duration_ms = round((perf_counter() - started_at) * 1_000, 2)

    logger.info(
        "Pipeline Wikichess terminé en %.2f ms : "
        "%s présentation(s), "
        "%s document(s), "
        "%s insertion(s).",
        duration_ms,
        ingestion_report.article_count,
        ingestion_report.chunk_count,
        ingestion_report.inserted_count,
    )

    return (
        (articles, failures, download_duration_ms),
        initialization_status,
        ingestion_report,
    )


# Affichage


def display_pipeline_summary(
    download_result: PipelineDownloadResult,
    initialization_status: InitializationStatus,
    ingestion_report: IngestionReport,
) -> None:
    """Affiche le bilan global du pipeline."""

    (articles, failures, download_duration_ms) = download_result

    print()
    print("Pipeline Wikichess terminé.")
    print()

    # Téléchargement

    print(f"Présentations téléchargées : {len(articles)}")

    print(f"Téléchargements échoués : {len(failures)}")

    print(f"Durée du téléchargement : {download_duration_ms:.2f} ms")

    # Milvus

    milvus_available = initialization_status.get("available", False)

    collection_recreated = initialization_status.get("recreated", False)

    print(f"Milvus disponible : {'oui' if milvus_available else 'non'}")

    print(f"Collection Milvus : {initialization_status['collection']}")

    print(f"Collection recréée : {'oui' if collection_recreated else 'non'}")

    print(f"Dimension Milvus : {initialization_status['milvus_dimension']}")

    print(f"Métrique vectorielle : {initialization_status['metric_type']}")

    print(f"Type d'index : {initialization_status['index_type']}")

    # Ingestion

    print(f"Présentations ingérées : {ingestion_report.article_count}")

    print(f"Documents produits : {ingestion_report.chunk_count}")

    print(f"Documents insérés dans Milvus : {ingestion_report.inserted_count}")

    print(f"Dimension des embeddings : {ingestion_report.embedding_dimension}")

    print(
        "Documents existants remplacés : "
        f"{'oui' if ingestion_report.replaced_existing_documents else 'non'}"
    )

    print(
        f"Documents exportés : {'oui' if ingestion_report.exported_chunks else 'non'}"
    )

    # Bilan des branches

    next_moves_count = sum(len(article.get("next_moves", [])) for article in articles)

    print(f"Branches Wikichess récupérées : {next_moves_count}")


# Exécution


async def main() -> int:
    """Exécute le pipeline et retourne son code de sortie."""

    try:
        (
            download_result,
            initialization_status,
            ingestion_report,
        ) = await run_wikichess_pipeline()

    except (
        ConfigurationError,
        EmbeddingGenerationError,
        EmbeddingModelUnavailableError,
        MilvusConnectionError,
        MilvusIndexError,
        MilvusInsertionError,
        MilvusOperationError,
        MilvusValidationError,
        OSError,
        PermissionError,
        RuntimeError,
        ValueError,
    ) as error:
        logger.exception("Pipeline Wikichess impossible.")

        print()
        print(f"Erreur : {error}")

        return 1

    except Exception as error:
        logger.exception("Erreur inattendue pendant le pipeline Wikichess.")

        print()
        print(f"Erreur inattendue : {error}")

        return 1

    display_pipeline_summary(download_result, initialization_status, ingestion_report)

    return 0


# Entrée

if __name__ == "__main__":
    raise SystemExit(asyncio.run(main()))
