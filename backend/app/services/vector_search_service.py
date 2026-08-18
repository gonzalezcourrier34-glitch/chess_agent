"""Service applicatif de recherche vectorielle.

Ce service orchestre les recherches dans les documents indexés
dans Milvus.

Il prend en charge deux usages distincts :

- la recherche sémantique générale ;
- la recherche structurelle filtrée par métadonnées.

La recherche Wikichess par séquence de coups repose sur une
correspondance exacte du champ moves_path.

Dans ce cas :

- moves_path identifie la position documentaire ;
- le filtre Milvus limite strictement les candidats ;
- l'embedding classe uniquement les documents compatibles ;
- aucune ouverture n'est déduite depuis une similarité sémantique.

La génération des embeddings reste déléguée à EmbeddingService.

La gestion de la collection, des index et des recherches vectorielles
reste déléguée à MilvusService.

Ce service est responsable de :

- valider les requêtes ;
- normaliser les limites ;
- normaliser les séquences de coups ;
- construire les filtres documentaires ;
- générer l'embedding d'une requête ;
- interroger Milvus ;
- normaliser les résultats ;
- vérifier les correspondances structurelles ;
- construire les schémas exposés à l'application ;
- maintenir les statistiques techniques ;
- vérifier la disponibilité de la chaîne RAG.

Ce service ne dépend ni de FastAPI ni de LangGraph.
"""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from time import perf_counter
from typing import Any

from app.adapters.embedding_service import EmbeddingService
from app.adapters.milvus_service import MilvusService
from app.core.config import settings
from app.core.exceptions import (
    EmbeddingGenerationError,
    EmbeddingModelUnavailableError,
    ErrorContext,
    MilvusConnectionError,
    MilvusError,
    MilvusSearchError,
    RetrievalError,
)
from app.core.logging import get_logger
from app.schemas.analysis.search import (
    VectorSearchRequest,
    VectorSearchResponse,
    VectorSearchResult,
)

logger = get_logger(__name__)


# Types

MilvusSearchResult = Mapping[str, Any]

VectorSearchServiceStatus = dict[str, Any]


# Configuration

RESULT_ID_FIELD = "id"

RESULT_CONTENT_FIELD = "content"

RESULT_SOURCE_FIELD = "source"

RESULT_METADATA_FIELD = "metadata"

RESULT_SIMILARITY_FIELD = "similarity"


# Métadonnées

METADATA_ECO_KEY = "eco"

METADATA_MOVES_PATH_KEY = "moves_path"


# Service


class VectorSearchService:
    """Service applicatif de recherche vectorielle."""

    # Construction

    def __init__(
        self, embedding_service: EmbeddingService, milvus_service: MilvusService
    ) -> None:
        """Initialise le service."""

        self._embedding_service = embedding_service

        self._milvus_service = milvus_service

        self._search_count = 0

        self._result_count = 0

        self._last_search_duration_ms: float | None = None

    # Validation

    def _normalize_query(self, query: str) -> str:
        """Valide et normalise une requête textuelle."""

            
        normalized_query = " ".join(
            query.split()
        )

        if not normalized_query:
            raise RetrievalError(
                context=ErrorContext(
                    service="vector_search", operation="_normalize_query"
                ),
                message=("La recherche vectorielle ne peut pas être vide.")
            )

        return normalized_query

    def _normalize_limit(self, limit: int | None) -> int:
        """Valide le nombre maximal de résultats."""

        normalized_limit = limit if limit is not None else settings.rag_search_top_k

        if isinstance(normalized_limit, bool) or not isinstance(normalized_limit, int):
            raise RetrievalError(
                context=ErrorContext(
                    service="vector_search", operation="_normalize_limit"
                ),
                message=("Le nombre maximal de résultats " "doit être un entier.")
            )

        if normalized_limit < 1:
            raise RetrievalError(
                context=ErrorContext(
                    service="vector_search", operation="_normalize_limit"
                ),
                message=(
                    "Le nombre maximal de résultats " "doit être supérieur ou égal à 1."
                )
            )

        return min(normalized_limit, settings.milvus_search_limit)

    def _normalize_moves(self, moves: Sequence[str]) -> tuple[str, ...]:
        """Valide et normalise une séquence de coups."""

        if isinstance(moves, str):
            raise RetrievalError(
                context=ErrorContext(
                    service="vector_search", operation="_normalize_moves"
                ),
                message=(
                    "La séquence de coups doit être " "une collection de chaînes."
                )
            )

        normalized_moves = [
            move.strip() for move in moves if isinstance(move, str) and move.strip()
        ]

        if not normalized_moves:
            raise RetrievalError(
                context=ErrorContext(
                    service="vector_search", operation="_normalize_moves"
                ),
                message=("La recherche par coups nécessite " "au moins un coup.")
            )

        if len(normalized_moves) != len(moves):
            raise RetrievalError(
                context=ErrorContext(
                    service="vector_search", operation="_normalize_moves"
                ),
                message=("La séquence de coups contient " "une valeur invalide.")
            )

        return tuple(normalized_moves)

    def _normalize_eco(self, eco: str) -> str:
        """Valide et normalise un code ECO."""

        if not isinstance(eco, str):
            raise RetrievalError(
                context=ErrorContext(
                    service="vector_search", operation="_normalize_eco"
                ),
                message=("Le code ECO doit être " "une chaîne de caractères.")
            )

        normalized_eco = eco.strip().upper()

        if not normalized_eco:
            raise RetrievalError(
                context=ErrorContext(
                    service="vector_search", operation="_normalize_eco"
                ),
                message=("Le code ECO ne peut pas être vide.")
            )

        return normalized_eco

    def _normalize_filter_expression(self, filter_expression: str) -> str:
        """Valide et normalise une expression de filtrage."""

        if not isinstance(filter_expression, str):
            raise RetrievalError(
                context=ErrorContext(
                    service="vector_search", operation="_normalize_filter_expression"
                ),
                message=(
                    "Le filtre documentaire doit être " "une chaîne de caractères."
                )
            )

        normalized_expression = filter_expression.strip()

        if not normalized_expression:
            raise RetrievalError(
                context=ErrorContext(
                    service="vector_search", operation="_normalize_filter_expression"
                ),
                message=("Le filtre documentaire ne peut pas être vide.")
            )

        return normalized_expression

    # Filtres

    def _escape_filter_value(self, value: str) -> str:
        """Échappe une valeur intégrée dans un filtre Milvus."""

        return value.replace("\\", "\\\\").replace('"', '\\"')

    def _build_metadata_equals_filter(self, *, key: str, value: str) -> str:
        """Construit un filtre d'égalité sur une métadonnée."""

        escaped_key = self._escape_filter_value(key)

        escaped_value = self._escape_filter_value(value)

        return f'metadata["{escaped_key}"] ' f'== "{escaped_value}"'

    def _build_moves_path(self, moves: Sequence[str]) -> str:
        """Construit le chemin canonique d'une séquence de coups."""

        return " ".join(moves)

    def _build_eco_filter(self, eco: str) -> str:
        """Construit le filtre exact d'un code ECO."""

        return self._build_metadata_equals_filter(key=METADATA_ECO_KEY, value=eco)

    def _build_moves_filter(self, moves_path: str) -> str:
        """Construit le filtre exact d'un chemin de coups."""

        return self._build_metadata_equals_filter(
            key=METADATA_MOVES_PATH_KEY, value=moves_path
        )

    # Conversion

    def _get_text(self, value: Any) -> str:
        """Retourne une chaîne nettoyée."""

        if not isinstance(value, str):
            return ""

        return " ".join(value.split())

    def _get_identifier(self, result: MilvusSearchResult) -> str | None:
        """Retourne l'identifiant d'un résultat Milvus."""

        identifier = result.get(RESULT_ID_FIELD)

        if identifier is None:
            return None

        normalized_identifier = str(identifier).strip()

        return normalized_identifier if normalized_identifier else None

    def _get_content(self, result: MilvusSearchResult) -> str | None:
        """Retourne le contenu textuel d'un résultat."""

        value = result.get(RESULT_CONTENT_FIELD)

        if not isinstance(value, str):
            return None

        return value.strip()

    def _get_similarity(
        self,
        result: MilvusSearchResult
    ) -> float | None:
        """Retourne le score de similarité normalisé."""

        value = result.get(RESULT_SIMILARITY_FIELD)

        if value is None or isinstance(value, bool):
            return None

        try:
            similarity = float(value)
        except (TypeError, ValueError):
            return None

        return min(
            max(similarity, 0.0),
            1.0
        )

    def _get_metadata(self, result: MilvusSearchResult) -> dict[str, Any]:
        """Retourne les métadonnées d'un résultat."""

        metadata = result.get(RESULT_METADATA_FIELD)

        normalized_metadata = dict(metadata) if isinstance(metadata, Mapping) else {}

        source = self._get_text(result.get(RESULT_SOURCE_FIELD))

        if source and RESULT_SOURCE_FIELD not in normalized_metadata:
            normalized_metadata[RESULT_SOURCE_FIELD] = source

        return normalized_metadata

    def _build_result(self, result: MilvusSearchResult) -> VectorSearchResult | None:
        """Construit un résultat de recherche vectorielle."""

        identifier = self._get_identifier(result)

        content = self._get_content(result)

        similarity = self._get_similarity(result)

        if identifier is None or content is None or similarity is None:
            logger.warning("Résultat Milvus incomplet ignoré.")

            return None

        return VectorSearchResult(
            id=identifier,
            content=content,
            similarity=similarity,
            metadata=self._get_metadata(result)
        )

    def _build_results(
        self, results: Sequence[MilvusSearchResult]
    ) -> list[VectorSearchResult]:
        """Construit les résultats exposés par l'application."""

        normalized_results: list[VectorSearchResult] = []

        seen_identifiers: set[str] = set()

        for result in results:
            normalized_result = self._build_result(result)

            if normalized_result is None:
                continue

            if normalized_result.id in seen_identifiers:
                continue

            seen_identifiers.add(normalized_result.id)

            normalized_results.append(normalized_result)

        return normalized_results

    # Vérification structurelle

    def _get_result_eco(self, result: VectorSearchResult) -> str | None:
        """Retourne le code ECO d'un résultat."""

        metadata = result.metadata

        if not isinstance(metadata, Mapping):
            return None

        value = metadata.get(METADATA_ECO_KEY)

        if not isinstance(value, str):
            return None

        normalized_value = value.strip().upper()

        return normalized_value or None

    def _get_result_moves_path(self, result: VectorSearchResult) -> str | None:
        """Retourne le chemin de coups d'un résultat."""

        metadata = result.metadata

        if not isinstance(metadata, Mapping):
            return None

        value = metadata.get(METADATA_MOVES_PATH_KEY)

        if not isinstance(value, str):
            return None

        normalized_value = " ".join(value.split())

        return normalized_value if normalized_value else None

    def _keep_exact_eco(
        self, results: Sequence[VectorSearchResult], *, eco: str
    ) -> list[VectorSearchResult]:
        """Conserve uniquement les résultats du code ECO demandé."""

        verified_results: list[VectorSearchResult] = []

        for result in results:
            result_eco = self._get_result_eco(result)

            if result_eco != eco:
                logger.warning(
                    "Résultat Wikichess écarté : " "eco attendu=%r, reçu=%r, id=%r.",
                    eco,
                    result_eco,
                    result.id
                )

                continue

            verified_results.append(result)

        return verified_results

    def _keep_exact_moves_path(
        self, results: Sequence[VectorSearchResult], *, moves_path: str
    ) -> list[VectorSearchResult]:
        """Conserve uniquement les résultats au chemin exact."""

        verified_results: list[VectorSearchResult] = []

        for result in results:
            result_moves_path = self._get_result_moves_path(result)

            if result_moves_path != moves_path:
                logger.warning(
                    "Résultat Wikichess écarté : "
                    "moves_path attendu=%r, reçu=%r, id=%r.",
                    moves_path,
                    result_moves_path,
                    result.id
                )

                continue

            verified_results.append(result)

        return verified_results

    # Statistiques

    def _register_search(self, *, result_count: int, duration_ms: float) -> None:
        """Enregistre les statistiques d'une recherche."""

        self._search_count += 1

        self._result_count += result_count

        self._last_search_duration_ms = duration_ms

    # Recherche interne

    async def _execute_search(
        self,
        *,
        query: str,
        limit: int | None,
        filter_expression: str | None = None,
        operation: str
    ) -> list[VectorSearchResult]:
        """Exécute une recherche vectorielle éventuellement filtrée."""

        normalized_query = self._normalize_query(query)

        normalized_limit = self._normalize_limit(limit)

        normalized_filter = (
            self._normalize_filter_expression(filter_expression)
            if filter_expression is not None
            else None
        )

        logger.debug(
            "Recherche vectorielle : " "operation=%s, query=%r, limit=%s, filter=%r.",
            operation,
            normalized_query,
            normalized_limit,
            normalized_filter
        )

        started_at = perf_counter()

        try:
            # L'embedding classe les documents après application
            # éventuelle du filtre structurel.
            query_vector = await self._embedding_service.generate_embedding(
                normalized_query
            )

            raw_results = await self._milvus_service.search(
                query_vector,
                limit=normalized_limit,
                filter_expression=normalized_filter
            )

        except (EmbeddingModelUnavailableError, EmbeddingGenerationError) as error:
            logger.warning(
                "Impossible de générer l'embedding " "de la recherche : %s", error
            )

            raise RetrievalError(
                context=ErrorContext(
                    service="vector_search",
                    operation=operation,
                    metadata={
                        "query": normalized_query,
                        "limit": normalized_limit,
                        "filter_expression": normalized_filter,
                    }
                ),
                message=(
                    "Impossible de transformer la requête " "en vecteur de recherche."
                ),
                cause=error
            ) from error

        except (MilvusConnectionError, MilvusSearchError, MilvusError) as error:
            logger.warning("Recherche Milvus impossible : %s", error)

            raise RetrievalError(
                context=ErrorContext(
                    service="vector_search",
                    operation=operation,
                    metadata={
                        "query": normalized_query,
                        "limit": normalized_limit,
                        "filter_expression": normalized_filter,
                    }
                ),
                message=(
                    "Impossible d'effectuer la recherche " "dans la base vectorielle."
                ),
                cause=error
            ) from error

        except Exception as error:
            logger.exception("Erreur inattendue durant la recherche vectorielle.")

            raise RetrievalError(
                context=ErrorContext(
                    service="vector_search",
                    operation=operation,
                    metadata={
                        "query": normalized_query,
                        "limit": normalized_limit,
                        "filter_expression": normalized_filter,
                    }
                ),
                message=("La recherche vectorielle a échoué."),
                cause=error
            ) from error

        duration_ms = round((perf_counter() - started_at) * 1_000, 2)

        results = self._build_results(raw_results)

        self._register_search(result_count=len(results), duration_ms=duration_ms)

        logger.info(
            "Recherche vectorielle %s : " "%s résultat(s) en %.2f ms.",
            operation,
            len(results),
            duration_ms
        )

        return results

    # Recherche sémantique

    async def search(self, request: VectorSearchRequest) -> VectorSearchResponse:
        """Recherche des documents par similarité sémantique."""

        normalized_query = self._normalize_query(request.query)

        results = await self._execute_search(
            query=normalized_query, limit=request.limit, operation="search"
        )

        return VectorSearchResponse(query=normalized_query, results=results)

    # Recherche filtrée

    async def search_with_filter(
        self, *, query: str, filter_expression: str, limit: int | None = None
    ) -> list[VectorSearchResult]:
        """Recherche des documents dans un sous-ensemble filtré."""

        return await self._execute_search(
            query=query,
            limit=limit,
            filter_expression=filter_expression,
            operation="search_with_filter"
        )

    # Recherche Wikichess

    async def search_wikichess(
        self,
        *,
        query: str,
        eco: str | None = None,
        moves: Sequence[str] | None = None,
        limit: int | None = None
    ) -> list[VectorSearchResult]:
        """Recherche un document Wikichess selon le contexte disponible.

        Le code ECO constitue la stratégie prioritaire lorsqu'il est
        disponible.

        Lorsque cette recherche ne retourne aucun document, la séquence
        de coups est utilisée comme stratégie de repli lorsqu'elle est
        disponible.
        """

        # Recherche ECO

        if eco:
            eco_results = await self.search_by_eco(eco=eco, query=query, limit=limit)

            if eco_results:
                return eco_results

            logger.info(
                "Aucun document Wikichess trouvé pour eco=%r. "
                "Recherche par coups tentée en repli.",
                eco
            )

        # Recherche par coups

        if moves:
            return await self.search_by_moves(moves=moves, query=query, limit=limit)

        # Aucun contexte exploitable

        raise RetrievalError(
            context=ErrorContext(service="vector_search", operation="search_wikichess"),
            message=(
                "La recherche Wikichess nécessite "
                "un code ECO ou un historique de coups."
            )
        )

    async def search_by_eco(
        self, *, eco: str, query: str, limit: int | None = None
    ) -> list[VectorSearchResult]:
        """Recherche les documents Wikichess d'un code ECO.

        Le code ECO constitue le filtre structurel principal.

        L'embedding est ensuite utilisé uniquement pour classer les
        documents appartenant au même code ECO.
        """

        normalized_eco = self._normalize_eco(eco)

        filter_expression = self._build_eco_filter(normalized_eco)

        logger.info("Recherche Wikichess par ECO : eco=%r.", normalized_eco)

        results = await self._execute_search(
            query=query,
            limit=limit,
            filter_expression=filter_expression,
            operation="search_by_eco"
        )

        verified_results = self._keep_exact_eco(results, eco=normalized_eco)

        if len(verified_results) != len(results):
            logger.warning(
                "Recherche Wikichess par ECO : "
                "%s résultat(s) écarté(s) après "
                "vérification du code ECO.",
                (len(results) - len(verified_results))
            )

        logger.info(
            "Recherche Wikichess par ECO terminée : " "eco=%r, résultats=%s.",
            normalized_eco,
            len(verified_results)
        )

        return verified_results

    async def search_by_moves(
        self, *, moves: Sequence[str], query: str, limit: int | None = None
    ) -> list[VectorSearchResult]:
        """Recherche les documents correspondant exactement aux coups.

        La séquence est convertie dans le même format que le champ
        moves_path enregistré lors de l'ingestion Wikichess.

        Le filtre Milvus constitue la première protection.

        Les résultats sont ensuite contrôlés une seconde fois côté
        application afin qu'un document dont moves_path diffère de la
        séquence demandée ne puisse jamais être retourné au workflow.
        """

        normalized_moves = self._normalize_moves(moves)

        moves_path = self._build_moves_path(normalized_moves)

        filter_expression = self._build_moves_filter(moves_path)

        logger.info("Recherche Wikichess exacte : moves_path=%r.", moves_path)

        results = await self._execute_search(
            query=query,
            limit=limit,
            filter_expression=filter_expression,
            operation="search_by_moves"
        )

        verified_results = self._keep_exact_moves_path(results, moves_path=moves_path)

        if len(verified_results) != len(results):
            logger.warning(
                "Recherche Wikichess : "
                "%s résultat(s) écarté(s) après "
                "vérification du moves_path.",
                (len(results) - len(verified_results))
            )

        logger.info(
            "Recherche Wikichess exacte terminée : " "moves_path=%r, résultats=%s.",
            moves_path,
            len(verified_results)
        )

        return verified_results

    # Informations

    def get_search_count(self) -> int:
        """Retourne le nombre de recherches effectuées."""

        return self._search_count

    def get_result_count(self) -> int:
        """Retourne le nombre total de résultats retournés."""

        return self._result_count

    def get_last_search_duration_ms(self) -> float | None:
        """Retourne la durée de la dernière recherche."""

        return self._last_search_duration_ms

    def is_ready(self) -> bool:
        """Indique si les dépendances semblent initialisées."""

        return self._embedding_service.is_ready() and self._milvus_service.is_ready()

    # Santé

    async def ping(self) -> bool:
        """Vérifie la disponibilité de la chaîne RAG."""

        try:
            embedding_available = await self._embedding_service.ping()

            milvus_available = await self._milvus_service.ping()

        except Exception:
            logger.exception(
                "Erreur inattendue lors du test " "du service de recherche vectorielle."
            )

            return False

        return embedding_available and milvus_available

    async def health(self) -> VectorSearchServiceStatus:
        """Retourne l'état de santé du service."""

        embedding_available = False

        milvus_available = False

        try:
            embedding_available = await self._embedding_service.ping()

        except Exception:
            logger.exception("État du service d'embedding indisponible.")

        try:
            milvus_available = await self._milvus_service.ping()

        except Exception:
            logger.exception("État du service Milvus indisponible.")

        available = embedding_available and milvus_available

        return {
            "service": "vector_search",
            "is_ready": self.is_ready(),
            "available": available,
            "embedding_available": embedding_available,
            "milvus_available": milvus_available,
            "embedding_model": settings.embedding_model,
            "collection": settings.milvus_collection_name,
            "default_limit": settings.rag_search_top_k,
            "maximum_limit": settings.milvus_search_limit,
            "search_count": self.get_search_count(),
            "result_count": self.get_result_count(),
            "last_search_duration_ms": (self.get_last_search_duration_ms()),
        }