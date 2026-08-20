"""Ingestion des contenus pédagogiques Wikichess dans Milvus.

Ce module prépare et charge le corpus pédagogique Wikichess utilisé
par le moteur RAG de Chess Agent.

Chaque fichier JSON représente une ouverture et contient notamment :

- ses métadonnées documentaires ;
- sa séquence de coups ;
- son marqueur position_after ;
- son contenu pédagogique intégral ;
- les coups suivants disponibles depuis la position.

Un fichier JSON produit exactement un document vectoriel.

Le module :

- découvre les fichiers JSON Wikichess ;
- valide leur contenu ;
- construit un document pédagogique par ouverture ;
- conserve les branches suivantes comme métadonnées de navigation ;
- construit un texte enrichi uniquement pour l'embedding ;
- génère les embeddings par lots ;
- vérifie la dimension vectorielle ;
- construit les documents Milvus ;
- remplace éventuellement les anciens documents Wikichess ;
- insère les nouveaux documents ;
- exporte les documents préparés ;
- affiche un bilan d'ingestion.

Le contenu pédagogique n'est ni tronqué ni découpé.

Les champs moves, position_after et les informations d'identité de
l'ouverture enrichissent le texte utilisé pour l'embedding.

Le champ next_moves n'est pas intégré au texte d'embedding et n'est
pas ajouté au contenu pédagogique destiné au LLM. Il reste une donnée
de navigation permettant de représenter les branches Wikichess.

La génération des embeddings reste déléguée à EmbeddingService.

La gestion de la collection et des insertions reste déléguée à
MilvusService.
"""

from __future__ import annotations

import asyncio
import hashlib
import json
import sys
from collections.abc import Iterable, Mapping, Sequence
from dataclasses import asdict
from pathlib import Path
from time import perf_counter
from typing import Any

# Chemins

BACKEND_DIRECTORY = Path(__file__).resolve().parents[1]

if str(BACKEND_DIRECTORY) not in sys.path:
    sys.path.insert(0, str(BACKEND_DIRECTORY))


# Imports applicatifs

from app.adapters.embedding_service import EmbeddingService
from app.adapters.milvus_service import MilvusService, VectorDocument
from app.core.config import settings
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

from scripts.config.constants_scripts import (
    CHUNK_HASH_LENGTH,
    CHUNK_ID_PREFIX,
    CHUNK_INDEX_WIDTH,
    DEFAULT_ENCODING,
    MANIFEST_FILE,
    METADATA_ARTICLE_SLUG_KEY,
    METADATA_ARTICLE_TITLE_KEY,
    METADATA_CHUNK_COUNT_KEY,
    METADATA_CHUNK_INDEX_KEY,
    METADATA_CONTRIBUTORS_KEY,
    METADATA_DATASET_KEY,
    METADATA_ECO_KEY,
    METADATA_LANGUAGE_KEY,
    METADATA_MOVES_KEY,
    METADATA_MOVES_PATH_KEY,
    METADATA_NEXT_MOVES_KEY,
    METADATA_POSITION_AFTER_KEY,
    METADATA_RETRIEVED_AT_KEY,
    METADATA_SOURCE_PATH_KEY,
    METADATA_SOURCE_URL_KEY,
    METADATA_WIKICHESS_TITLE_KEY,
    PROCESSED_DIRECTORY,
    PROCESSED_FILE,
    PROJECT_DIRECTORY,
    WIKICHESS_DIRECTORY,
    WIKICHESS_FILTER,
    WIKICHESS_SOURCE,
)
from scripts.config.settings_scripts import wikichess_script_settings
from scripts.schemas.wikichess_script import (
    IngestionReport,
    WikichessArticle,
    WikichessChunk,
    WikichessNextMove,
)

logger = get_logger(__name__)


# Types

Metadata = dict[str, Any]

JsonPayload = dict[str, Any]

NextMoves = tuple[WikichessNextMove, ...]


# Validation


def validate_configuration() -> None:
    """Valide la configuration locale d'ingestion."""

    if not WIKICHESS_DIRECTORY.is_dir():
        raise ConfigurationError(
            message=(f"Le répertoire Wikichess est introuvable : {WIKICHESS_DIRECTORY}")
        )

    if not WIKICHESS_SOURCE.strip():
        raise ConfigurationError(message=("La source Wikichess ne peut pas être vide."))

    if not WIKICHESS_FILTER.strip():
        raise ConfigurationError(
            message=("Le filtre Milvus Wikichess ne peut pas être vide.")
        )

    if CHUNK_HASH_LENGTH < 1:
        raise ConfigurationError(
            message=("La longueur du hash des documents doit être supérieure à zéro.")
        )

    if CHUNK_INDEX_WIDTH < 1:
        raise ConfigurationError(
            message=("La largeur de l'index des documents doit être supérieure à zéro.")
        )


def validate_vector_dimension(dimension: int, *, source: str) -> int:
    """Valide une dimension vectorielle."""

    if isinstance(dimension, bool) or not isinstance(dimension, int) or dimension < 1:
        raise ConfigurationError(
            message=(
                f"La dimension vectorielle fournie par {source} "
                "doit être un entier supérieur à zéro."
            )
        )

    return dimension


def validate_vector_dimensions(
    embedding_service: EmbeddingService, milvus_service: MilvusService
) -> int:
    """Vérifie la cohérence des dimensions vectorielles."""

    embedding_dimension = validate_vector_dimension(
        embedding_service.get_dimension(), source="EmbeddingService"
    )

    milvus_dimension = validate_vector_dimension(
        milvus_service.get_vector_dimension(), source="MilvusService"
    )

    if embedding_dimension != milvus_dimension:
        raise ConfigurationError(
            message=(
                "La dimension du modèle d'embedding "
                "ne correspond pas à celle attendue par Milvus : "
                f"{embedding_dimension} contre "
                f"{milvus_dimension}."
            )
        )

    return embedding_dimension


# Normalisation


def normalize_text(value: Any) -> str:
    """Normalise une valeur textuelle."""

    if not isinstance(value, str):
        return ""

    return (
        value.replace("\u00a0", " ")
        .replace("\r\n", "\n")
        .replace("\r", "\n")
        .replace("’", "'")
        .replace("“", '"')
        .replace("”", '"')
        .replace("–", "-")
        .replace("—", "-")
        .replace("\ufffd", "-")
        .strip()
    )


def normalize_contributors(value: Any) -> tuple[str, ...]:
    """Normalise la liste des contributeurs."""

    if not isinstance(value, list):
        return ()

    contributors = [
        normalize_text(contributor)
        for contributor in value
        if isinstance(contributor, str)
    ]

    return tuple(
        dict.fromkeys(contributor for contributor in contributors if contributor)
    )


def normalize_moves(value: Any) -> tuple[str, ...]:
    """Normalise la séquence de coups d'une ouverture."""

    if not isinstance(value, list):
        return ()

    moves = [normalize_text(move) for move in value if isinstance(move, str)]

    return tuple(move for move in moves if move)


def normalize_next_moves(value: Any) -> NextMoves:
    """Normalise les branches suivantes d'une position Wikichess."""

    if not isinstance(value, list):
        return ()

    next_moves: list[WikichessNextMove] = []

    seen_moves: set[str] = set()

    for item in value:
        if not isinstance(item, Mapping):
            continue

        move = normalize_text(item.get("move"))

        source_url = normalize_text(item.get("source_url"))

        if not move or not source_url:
            continue

        comparable_move = move.casefold()

        if comparable_move in seen_moves:
            continue

        seen_moves.add(comparable_move)

        next_moves.append(WikichessNextMove(move=move, source_url=source_url))

    return tuple(next_moves)


# JSON


def read_json_file(path: Path) -> JsonPayload:
    """Lit et valide la racine d'un fichier JSON."""

    try:
        raw_content = path.read_text(encoding=DEFAULT_ENCODING)

    except OSError as error:
        raise ValueError(f"Impossible de lire {path}.") from error

    try:
        payload = json.loads(raw_content)

    except json.JSONDecodeError as error:
        raise ValueError(f"JSON invalide dans {path}.") from error

    if not isinstance(payload, dict):
        raise ValueError(f"La racine JSON de {path} doit être un objet.")

    return payload


def get_required_text(payload: JsonPayload, key: str, *, path: Path) -> str:
    """Retourne un champ textuel obligatoire."""

    value = normalize_text(payload.get(key))

    if not value:
        raise ValueError(f"Le champ '{key}' est absent ou vide dans {path}.")

    return value


def get_optional_text(payload: JsonPayload, key: str) -> str:
    """Retourne un champ textuel facultatif."""

    return normalize_text(payload.get(key))


# Découverte


def discover_wikichess_files() -> list[Path]:
    """Retourne les documents JSON Wikichess."""

    files = [
        path
        for path in WIKICHESS_DIRECTORY.rglob("*.json")
        if (path.is_file() and path.resolve() != MANIFEST_FILE.resolve())
    ]

    return sorted(files)


# Lecture


def load_article(path: Path) -> WikichessArticle | None:
    """Charge un contenu pédagogique Wikichess depuis un JSON."""

    try:
        payload = read_json_file(path)

        slug = get_required_text(payload, "slug", path=path)

        title = get_required_text(payload, "title", path=path)

        content = get_optional_text(payload, "content")

    except ValueError as error:
        logger.warning("Document Wikichess ignoré : %s", error)

        return None

    wikichess_title = get_optional_text(payload, "wikichess_title")

    eco = get_optional_text(payload, "eco")

    moves = normalize_moves(payload.get("moves"))

    position_after = get_optional_text(payload, "position_after")

    source_url = get_optional_text(payload, "source_url")

    language = (
        get_optional_text(payload, "language")
        or wikichess_script_settings.default_language
    )

    retrieved_at = get_optional_text(payload, "retrieved_at")

    contributors = normalize_contributors(payload.get("contributors"))

    next_moves = normalize_next_moves(payload.get("next_moves"))

    relative_path = path.relative_to(PROJECT_DIRECTORY)

    return WikichessArticle(
        slug=slug,
        title=title,
        content=content,
        source_path=relative_path.as_posix(),
        language=language,
        eco=eco,
        moves=moves,
        position_after=position_after,
        source_url=source_url,
        wikichess_title=wikichess_title,
        contributors=contributors,
        next_moves=next_moves,
        retrieved_at=retrieved_at,
    )


def load_articles() -> list[WikichessArticle]:
    """Charge tous les contenus pédagogiques Wikichess."""

    paths = discover_wikichess_files()

    if not paths:
        raise ConfigurationError(
            message=(
                "Aucun document JSON Wikichess n'a été trouvé dans "
                f"{WIKICHESS_DIRECTORY}."
            )
        )

    articles: list[WikichessArticle] = []

    seen_slugs: set[str] = set()

    for path in paths:
        article = load_article(path)

        if article is None:
            continue

        if article.slug in seen_slugs:
            raise ValueError(
                f"Deux documents Wikichess utilisent le même slug : {article.slug}."
            )

        seen_slugs.add(article.slug)

        articles.append(article)

    if not articles:
        raise ConfigurationError(
            message=("Aucun contenu pédagogique Wikichess exploitable n'a été chargé.")
        )

    logger.info("%s document(s) Wikichess chargé(s).", len(articles))

    return articles


# Identifiants


def build_chunk_identifier(article_slug: str, chunk_index: int, content: str) -> str:
    """Construit un identifiant stable pour un document."""

    digest = hashlib.sha256(content.encode(DEFAULT_ENCODING)).hexdigest()[
        :CHUNK_HASH_LENGTH
    ]

    formatted_index = str(chunk_index).zfill(CHUNK_INDEX_WIDTH)

    return f"{CHUNK_ID_PREFIX}-{article_slug}-{formatted_index}-{digest}"


# Documents


def build_chunk(article: WikichessArticle) -> WikichessChunk:
    """Construit le document unique associé à un article."""

    return WikichessChunk(
        id=build_chunk_identifier(article.slug, 0, article.content),
        article_slug=article.slug,
        article_title=article.title,
        content=article.content,
        chunk_index=0,
        chunk_count=1,
        source_path=article.source_path,
        language=article.language,
        eco=article.eco,
        moves=article.moves,
        position_after=article.position_after,
        source_url=article.source_url,
        wikichess_title=article.wikichess_title,
        contributors=article.contributors,
        next_moves=article.next_moves,
        retrieved_at=article.retrieved_at,
    )


def build_chunks(articles: Sequence[WikichessArticle]) -> list[WikichessChunk]:
    """Construit un document vectoriel par article Wikichess."""

    chunks = [build_chunk(article) for article in articles]

    if not chunks:
        raise ConfigurationError(
            message=("Aucun document Wikichess n'a été construit.")
        )

    logger.info("%s document(s) Wikichess construit(s).", len(chunks))

    return chunks


# Contexte vectoriel


def get_opening_name(chunk: WikichessChunk) -> str:
    """Retourne le nom d'ouverture associé au document."""

    return (
        normalize_text(chunk.wikichess_title)
        or normalize_text(chunk.article_title)
        or normalize_text(chunk.article_slug)
    )


def build_vector_content(chunk: WikichessChunk) -> str:
    """Construit le texte enrichi utilisé pour l'embedding."""

    sections = ["Type : présentation", f"Ouverture : {get_opening_name(chunk)}"]

    if chunk.eco:
        sections.append(f"Code ECO : {chunk.eco}")

    if chunk.moves:
        sections.append("Coups : " + " ".join(chunk.moves))

    if chunk.position_after:
        sections.append(f"Position après : {chunk.position_after}")

    if chunk.content:
        sections.extend(["", chunk.content])

    return "\n".join(sections).strip()


# Lots


def iter_batches(values: Sequence[Any], batch_size: int) -> Iterable[Sequence[Any]]:
    """Découpe une séquence en lots."""

    if batch_size < 1:
        raise ValueError("La taille d'un lot doit être supérieure à zéro.")

    for start in range(0, len(values), batch_size):
        yield values[start : start + batch_size]


# Export


def chunk_to_dict(chunk: WikichessChunk) -> dict[str, Any]:
    """Convertit un document préparé en dictionnaire."""

    payload = asdict(chunk)

    payload["vector_content"] = build_vector_content(chunk)

    return payload


def export_chunks(chunks: Sequence[WikichessChunk]) -> bool:
    """Exporte les documents préparés."""

    if not wikichess_script_settings.export_prepared_chunks:
        logger.info("Export local des documents Wikichess désactivé.")

        return False

    PROCESSED_DIRECTORY.mkdir(parents=True, exist_ok=True)

    payload = [chunk_to_dict(chunk) for chunk in chunks]

    PROCESSED_FILE.write_text(
        json.dumps(payload, ensure_ascii=False, indent=2), encoding=DEFAULT_ENCODING
    )

    logger.info("Documents Wikichess exportés dans %s.", PROCESSED_FILE)

    return True


# Métadonnées


def build_metadata(chunk: WikichessChunk) -> Metadata:
    """Construit les métadonnées Milvus."""

    metadata: Metadata = {
        METADATA_DATASET_KEY: WIKICHESS_SOURCE,
        METADATA_ARTICLE_SLUG_KEY: chunk.article_slug,
        METADATA_ARTICLE_TITLE_KEY: chunk.article_title,
        METADATA_CHUNK_INDEX_KEY: chunk.chunk_index,
        METADATA_CHUNK_COUNT_KEY: chunk.chunk_count,
        METADATA_SOURCE_PATH_KEY: chunk.source_path,
        METADATA_LANGUAGE_KEY: chunk.language,
    }

    if chunk.eco:
        metadata[METADATA_ECO_KEY] = chunk.eco

    if chunk.moves:
        metadata[METADATA_MOVES_KEY] = list(chunk.moves)

        metadata[METADATA_MOVES_PATH_KEY] = " ".join(chunk.moves)

    if chunk.position_after:
        metadata[METADATA_POSITION_AFTER_KEY] = chunk.position_after

    if chunk.source_url:
        metadata[METADATA_SOURCE_URL_KEY] = chunk.source_url

    if chunk.wikichess_title:
        metadata[METADATA_WIKICHESS_TITLE_KEY] = chunk.wikichess_title

    if chunk.contributors:
        metadata[METADATA_CONTRIBUTORS_KEY] = list(chunk.contributors)

    if chunk.next_moves:
        metadata[METADATA_NEXT_MOVES_KEY] = [
            asdict(next_move) for next_move in chunk.next_moves
        ]

    if chunk.retrieved_at:
        metadata[METADATA_RETRIEVED_AT_KEY] = chunk.retrieved_at

    return metadata


# Vectorisation


async def vectorize_chunks(
    chunks: Sequence[WikichessChunk], embedding_service: EmbeddingService
) -> list[VectorDocument]:
    """Génère les documents vectoriels Wikichess."""

    documents: list[VectorDocument] = []

    embedding_batch_size = settings.embedding_max_batch_size

    for chunk_batch in iter_batches(chunks, embedding_batch_size):
        vector_contents = [build_vector_content(chunk) for chunk in chunk_batch]

        embeddings = await embedding_service.generate_embeddings(vector_contents)

        if len(embeddings) != len(chunk_batch):
            raise EmbeddingGenerationError(
                message=(
                    "Le nombre d'embeddings ne correspond pas "
                    "au nombre de documents Wikichess."
                )
            )

        for chunk, embedding in zip(chunk_batch, embeddings, strict=True):
            documents.append(
                VectorDocument(
                    id=chunk.id,
                    vector=embedding,
                    content=chunk.content,
                    source=WIKICHESS_SOURCE,
                    metadata=build_metadata(chunk),
                )
            )

        logger.info(
            "%s/%s document(s) Wikichess vectorisé(s).", len(documents), len(chunks)
        )

    return documents


# Nettoyage


async def clear_existing_documents(milvus_service: MilvusService) -> bool:
    """Supprime les anciens documents Wikichess."""

    if not wikichess_script_settings.replace_existing_documents:
        logger.info("Conservation des documents Wikichess existants.")

        return False

    logger.info("Suppression des anciens documents Wikichess.")

    await milvus_service.delete_by_filter(WIKICHESS_FILTER)

    return True


# Insertion


async def insert_documents(
    documents: Sequence[VectorDocument], milvus_service: MilvusService
) -> list[str]:
    """Insère les documents Wikichess dans Milvus."""

    inserted_identifiers: list[str] = []

    insert_batch_size = wikichess_script_settings.milvus_insert_batch_size

    for document_batch in iter_batches(documents, insert_batch_size):
        identifiers = await milvus_service.insert_documents(document_batch)

        inserted_identifiers.extend(identifiers)

        logger.info(
            "%s/%s document(s) inséré(s) dans Milvus.",
            len(inserted_identifiers),
            len(documents),
        )

    return inserted_identifiers


# Ingestion


async def ingest_wikichess() -> IngestionReport:
    """Ingère les contenus pédagogiques Wikichess dans Milvus."""

    validate_configuration()

    started_at = perf_counter()

    embedding_service = EmbeddingService()

    milvus_service: MilvusService | None = None

    try:
        # Embeddings

        await embedding_service.start()

        embedding_dimension = validate_vector_dimension(
            embedding_service.get_dimension(), source="EmbeddingService"
        )

        # Milvus

        milvus_service = MilvusService(vector_dimension=embedding_dimension)

        await milvus_service.start()

        validated_dimension = validate_vector_dimensions(
            embedding_service, milvus_service
        )

        logger.info(
            "Services vectoriels prêts avec une dimension de %s.", validated_dimension
        )

        # Chargement

        articles = load_articles()

        chunks = build_chunks(articles)

        # Export

        exported_chunks = export_chunks(chunks)

        # Vectorisation

        documents = await vectorize_chunks(chunks, embedding_service)

        # Remplacement

        replaced_existing_documents = await clear_existing_documents(milvus_service)

        # Insertion

        inserted_identifiers = await insert_documents(documents, milvus_service)

        # Rapport

        duration_ms = round((perf_counter() - started_at) * 1_000, 2)

        report = IngestionReport(
            article_count=len(articles),
            chunk_count=len(chunks),
            inserted_count=len(inserted_identifiers),
            embedding_dimension=validated_dimension,
            duration_ms=duration_ms,
            exported_chunks=exported_chunks,
            replaced_existing_documents=(replaced_existing_documents),
        )

        logger.info(
            "Ingestion Wikichess terminée : "
            "%s document(s) source, "
            "%s document(s) vectoriel(s), "
            "%s insertion(s).",
            report.article_count,
            report.chunk_count,
            report.inserted_count,
        )

        return report

    finally:
        if milvus_service is not None:
            await milvus_service.close()

        await embedding_service.close()


# Affichage


def display_report(report: IngestionReport) -> None:
    """Affiche le bilan d'ingestion."""

    print()
    print("Ingestion Wikichess terminée.")
    print()

    print(f"Documents sources lus : {report.article_count}")

    print(f"Documents vectoriels produits : {report.chunk_count}")

    print(f"Documents insérés : {report.inserted_count}")

    print(f"Dimension des embeddings : {report.embedding_dimension}")

    print(f"Durée : {report.duration_ms:.2f} ms")

    print(f"Collection : {settings.milvus_collection_name}")

    print(
        "Documents existants remplacés : "
        f"{'oui' if report.replaced_existing_documents else 'non'}"
    )

    print(f"Documents exportés : {'oui' if report.exported_chunks else 'non'}")

    if report.exported_chunks:
        print(f"Export : {PROCESSED_FILE}")


# Exécution


async def main() -> int:
    """Exécute l'ingestion Wikichess."""

    try:
        report = await ingest_wikichess()

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
        ValueError,
    ) as error:
        logger.exception("Ingestion Wikichess impossible.")

        print()
        print(f"Erreur : {error}")

        return 1

    except Exception as error:
        logger.exception("Erreur inattendue pendant l'ingestion Wikichess.")

        print()
        print(f"Erreur inattendue : {error}")

        return 1

    display_report(report)

    return 0


# Entrée

if __name__ == "__main__":
    raise SystemExit(asyncio.run(main()))
