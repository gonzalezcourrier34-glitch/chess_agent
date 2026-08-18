"""Service de recherche de vidéos pédagogiques sur YouTube.

Ce module centralise :

- les appels à l'API YouTube Data ;
- les nouvelles tentatives après une erreur temporaire ;
- la validation et la normalisation des réponses JSON ;
- la récupération des métadonnées complémentaires des vidéos ;
- la construction et le filtrage des recommandations ;
- l'exposition de l'état de santé du service.

Il ne localise pas une position précise dans une vidéo et ne contient
aucune logique propre au workflow LangGraph.
"""

from __future__ import annotations

import asyncio
import re
from collections.abc import AsyncGenerator, Mapping, Sequence
from contextlib import asynccontextmanager
from typing import TypedDict

import httpx
from pydantic import TypeAdapter, ValidationError

from app.core.config import settings
from app.core.constants import (
    YOUTUBE_CHANNEL_URL_TEMPLATE,
    YOUTUBE_QUOTA_ERROR_MARKERS,
    YOUTUBE_RETRYABLE_STATUS_CODES,
    YOUTUBE_SEARCH_ENDPOINT,
    YOUTUBE_SEARCH_ORDER,
    YOUTUBE_SEARCH_PART,
    YOUTUBE_SEARCH_SAFE_SEARCH,
    YOUTUBE_SEARCH_TYPE,
    YOUTUBE_SEARCH_VIDEO_DURATION,
    YOUTUBE_VIDEO_DETAILS_PART,
    YOUTUBE_VIDEO_URL_TEMPLATE,
    YOUTUBE_VIDEOS_ENDPOINT,
)
from app.core.exceptions import (
    ErrorContext,
    InvalidRequestError,
    YoutubeConfigurationError,
    YoutubeError,
    YoutubeQuotaError,
    YoutubeResponseError,
    YoutubeTimeoutError,
    YoutubeUnavailableError,
)
from app.core.logging import get_logger
from app.schemas.common.enums import VideoPlatform
from app.schemas.media.video import (
    Video,
    VideoChannel,
    VideoCollection,
    VideoRecommendation,
    VideoSearchRequest,
)

logger = get_logger(__name__)


# Types

type JsonScalar = None | bool | int | float | str
type JsonValue = JsonScalar | list[JsonValue] | dict[str, JsonValue]
type YoutubePayload = dict[str, JsonValue]
type YoutubeParam = str | int
type YoutubeParams = dict[str, YoutubeParam]


class YoutubeServiceStatus(TypedDict):
    """État de santé exposé par le service YouTube."""

    service: str
    is_ready: bool
    is_closed: bool
    available: bool
    base_url: str
    search_endpoint: str
    videos_endpoint: str
    region_code: str
    default_language: str
    query_suffix: str
    max_results: int
    timeout_seconds: float
    max_retry_attempts: int
    retry_delay_seconds: float
    max_connections: int
    user_agent: str


class YoutubeVideoDetails(TypedDict):
    """Métadonnées complémentaires d'une vidéo YouTube."""

    duration_seconds: int | None
    view_count: int | None
    like_count: int | None
    comment_count: int | None


# Configuration

SERVICE_NAME = "youtube"

MIN_SEARCH_RESULTS = 1
MAX_SEARCH_RESULTS = 20

MIN_LANGUAGE_LENGTH = 2
MAX_LANGUAGE_LENGTH = 10

MIN_TOPIC_LENGTH = 3

SECONDS_PER_DAY = 86_400
SECONDS_PER_HOUR = 3_600
SECONDS_PER_MINUTE = 60

MIN_RELEVANCE_SCORE = 0.2
RANK_SCORE_DECREMENT = 0.08
TOPIC_SCORE_INCREMENT = 0.03
MAX_TOPIC_SCORE = 0.15


YOUTUBE_PAYLOAD_ADAPTER: TypeAdapter[YoutubePayload] = TypeAdapter(
    YoutubePayload
)


# Ces termes éliminent les résultats manifestement sans rapport avec
# les échecs. La correspondance avec le nom de l'ouverture est ensuite
# vérifiée séparément.
REQUIRED_CHESS_TERMS = frozenset(
    {
        "chess",
        "échecs",
        "opening",
        "ouverture",
        "gambit",
        "defense",
        "défense",
        "variation",
    }
)


# Les durées retournées par YouTube utilisent le format ISO 8601.
DURATION_PATTERN = re.compile(
    r"^P"
    r"(?:(?P<days>\d+)D)?"
    r"(?:T"
    r"(?:(?P<hours>\d+)H)?"
    r"(?:(?P<minutes>\d+)M)?"
    r"(?:(?P<seconds>\d+)S)?"
    r")?$"
)


# Service


class YoutubeService:
    """Service de recherche de vidéos pédagogiques YouTube."""

    # Construction

    def __init__(self) -> None:
        """Initialise le client HTTP du service."""
        self._settings = settings

        limits = httpx.Limits(
            max_connections=self._settings.http_max_connections,
            max_keepalive_connections=(
                self._settings.http_max_connections
            ),
        )

        self._client = httpx.AsyncClient(
            base_url=self._settings.youtube_api_url,
            timeout=self._settings.youtube_timeout_seconds,
            headers={
                "User-Agent": self._settings.http_user_agent
            },
            limits=limits,
            follow_redirects=True,
        )

        # Plusieurs recherches peuvent s'exécuter en parallèle.
        # La condition permet toutefois à ``close`` d'attendre leur fin
        # avant de fermer le transport HTTP.
        self._operation_condition = asyncio.Condition()
        self._active_operations = 0
        self._closing = False

    # Cycle de vie

    async def initialize(self) -> None:
        """Initialise le service."""
        logger.info(
            "Initialisation du client YouTube."
        )

    async def shutdown(self) -> None:
        """Libère les ressources du service."""
        await self.close()

    async def close(self) -> None:
        """Ferme la session HTTP après les opérations actives."""
        async with self._operation_condition:
            if self._client.is_closed:
                return

            self._closing = True

            try:
                await self._operation_condition.wait_for(
                    lambda: self._active_operations == 0
                )

                logger.info(
                    "Fermeture du client HTTP YouTube."
                )

                await self._client.aclose()

            except Exception:
                # Une erreur de fermeture ne doit pas masquer
                # l'arrêt de l'application.
                logger.exception(
                    "Erreur lors de la fermeture du client YouTube."
                )

            finally:
                self._closing = False
                self._operation_condition.notify_all()

    @asynccontextmanager
    async def _operation(
        self,
        name: str,
    ) -> AsyncGenerator[None, None]:
        """Protège une opération contre une fermeture concurrente."""
        async with self._operation_condition:
            if self._closing or self._client.is_closed:
                raise YoutubeUnavailableError(
                    context=ErrorContext(
                        service=SERVICE_NAME,
                        operation=name,
                    ),
                    message=(
                        "Le client HTTP YouTube est fermé."
                    ),
                )

            self._active_operations += 1

        try:
            yield

        finally:
            async with self._operation_condition:
                self._active_operations -= 1
                self._operation_condition.notify_all()

    # Configuration

    def _get_api_key(self) -> str:
        """Retourne la clé API YouTube configurée."""
        api_key = self._settings.youtube_api_key

        if api_key is None:
            raise YoutubeConfigurationError(
                context=ErrorContext(
                    service=SERVICE_NAME,
                    operation="_get_api_key",
                ),
                message=(
                    "La clé API YouTube n'est pas configurée."
                ),
            )

        normalized_api_key = (
            api_key
            .get_secret_value()
            .strip()
        )

        if not normalized_api_key:
            raise YoutubeConfigurationError(
                context=ErrorContext(
                    service=SERVICE_NAME,
                    operation="_get_api_key",
                ),
                message=(
                    "La clé API YouTube est vide."
                ),
            )

        return normalized_api_key

    # HTTP

    async def _request(
        self,
        endpoint: str,
        *,
        params: YoutubeParams,
    ) -> YoutubePayload:
        """Exécute une requête et retourne son JSON validé."""
        request_params: YoutubeParams = {
            **params,
            "key": self._get_api_key(),
        }

        logger.debug(
            "Interrogation YouTube : %s",
            endpoint,
        )

        response = await self._execute_request(
            endpoint=endpoint,
            params=request_params,
        )

        return self._parse_response_payload(
            response
        )

    async def _execute_request(
        self,
        *,
        endpoint: str,
        params: YoutubeParams,
    ) -> httpx.Response:
        """Exécute une requête HTTP avec nouvelles tentatives."""
        total_attempts = (
            self._settings.http_max_retry_attempts
            + 1
        )

        for attempt in range(
            1,
            total_attempts + 1,
        ):
            try:
                response = await self._client.get(
                    endpoint,
                    params=params,
                )
                
                if self._should_retry_status(
                    endpoint=endpoint,
                    status_code=response.status_code,
                    attempt=attempt,
                    total_attempts=total_attempts,
                ):
                    await self._wait_before_retry(
                        attempt=attempt,
                        endpoint=endpoint,
                        status_code=response.status_code,
                    )
                    continue

                if response.is_error:
                    self._raise_response_error(
                        response
                    )

                logger.debug(
                    "Réponse YouTube reçue : %s.",
                    response.status_code,
                )

                return response

            except httpx.TimeoutException as error:
                if attempt < total_attempts:
                    await self._wait_before_retry(
                        attempt=attempt,
                        endpoint=endpoint,
                    )
                    continue

                logger.exception(
                    "Timeout lors de l'appel à YouTube."
                )

                raise YoutubeTimeoutError(
                    context=ErrorContext(
                        service=SERVICE_NAME,
                        operation=endpoint,
                    ),
                    message=(
                        "Le service YouTube ne répond pas "
                        "dans le délai configuré."
                    ),
                    cause=error,
                ) from error

            except YoutubeError:
                raise

            except httpx.HTTPError as error:
                if attempt < total_attempts:
                    await self._wait_before_retry(
                        attempt=attempt,
                        endpoint=endpoint,
                    )
                    continue

                logger.exception(
                    "Erreur réseau lors de l'appel à YouTube."
                )

                raise YoutubeUnavailableError(
                    context=ErrorContext(
                        service=SERVICE_NAME,
                        operation=endpoint,
                    ),
                    message=(
                        "Impossible de contacter le service YouTube."
                    ),
                    cause=error,
                ) from error

        raise YoutubeUnavailableError(
            context=ErrorContext(
                service=SERVICE_NAME,
                operation=endpoint,
            ),
            message=(
                "La requête YouTube n'a pas pu être exécutée."
            ),
        )

    def _parse_response_payload(
        self,
        response: httpx.Response,
    ) -> YoutubePayload:
        """Valide et retourne le contenu JSON d'une réponse."""
        if not response.content:
            raise YoutubeResponseError(
                context=ErrorContext(
                    service=SERVICE_NAME,
                    operation="_parse_response_payload",
                ),
                message=(
                    "Réponse vide retournée par YouTube."
                ),
            )

        try:
            return YOUTUBE_PAYLOAD_ADAPTER.validate_json(
                response.content
            )

        except ValidationError as error:
            logger.warning(
                "Réponse JSON invalide retournée par YouTube."
            )

            raise YoutubeResponseError(
                context=ErrorContext(
                    service=SERVICE_NAME,
                    operation="_parse_response_payload",
                ),
                message=(
                    "La réponse retournée par YouTube "
                    "n'est pas un objet JSON valide."
                ),
                cause=error,
            ) from error

    def _raise_response_error(
        self,
        response: httpx.Response,
    ) -> None:
        """Transforme une réponse HTTP en exception métier."""
        status_code = response.status_code

        error_reason = self._extract_error_reason(
            response
        )

        normalized_reason = (
            error_reason.casefold()
        )

        error_context = ErrorContext(
            service=SERVICE_NAME,
            operation="_raise_response_error",
            metadata={
                "status_code": status_code,
                "reason": error_reason,
            },
        )

        if (
            status_code in {
                403,
                429,
            }
            and any(
                marker.casefold()
                in normalized_reason
                for marker
                in YOUTUBE_QUOTA_ERROR_MARKERS
            )
        ):
            raise YoutubeQuotaError(
                context=error_context,
                message=(
                    "Le quota de l'API YouTube est dépassé."
                ),
            )

        if status_code in {
            400,
            401,
            403,
        }:
            raise YoutubeConfigurationError(
                context=error_context,
                message=(
                    "La clé API YouTube est invalide, "
                    "mal configurée ou non autorisée."
                ),
            )

        if status_code in {
            408,
            504,
        }:
            raise YoutubeTimeoutError(
                context=error_context,
                message=(
                    "Le délai d'attente de l'API "
                    "YouTube est dépassé."
                ),
            )

        if (
            status_code == 429
            or status_code >= 500
        ):
            raise YoutubeUnavailableError(
                context=error_context,
                message=(
                    "L'API YouTube est temporairement "
                    "indisponible."
                ),
            )

        raise YoutubeResponseError(
            context=error_context,
            message=(
                "L'API YouTube a retourné une erreur."
            ),
        )

    def _extract_error_reason(
        self,
        response: httpx.Response,
    ) -> str:
        """Retourne la raison structurée d'une erreur YouTube."""
        try:
            payload = (
                YOUTUBE_PAYLOAD_ADAPTER.validate_json(
                    response.content
                )
            )

        except ValidationError:
            return response.text.strip()

        error_payload = payload.get(
            "error"
        )

        if not isinstance(
            error_payload,
            dict,
        ):
            return response.text.strip()

        errors = error_payload.get(
            "errors"
        )

        if isinstance(errors, list):
            for error in errors:
                if not isinstance(
                    error,
                    dict,
                ):
                    continue

                reason = self._get_text(
                    error.get("reason")
                )

                if reason:
                    return reason

        message = self._get_text(
            error_payload.get("message")
        )

        return (
            message
            or response.text.strip()
        )

    def _should_retry_status(
        self,
        *,
        endpoint: str,
        status_code: int,
        attempt: int,
        total_attempts: int,
    ) -> bool:
        """Indique si une requête peut être retentée."""

        if endpoint == YOUTUBE_SEARCH_ENDPOINT:
            return False

        return (
            status_code in YOUTUBE_RETRYABLE_STATUS_CODES
            and attempt < total_attempts
        )

    async def _wait_before_retry(
        self,
        *,
        attempt: int,
        endpoint: str,
        status_code: int | None = None,
    ) -> None:
        """Attend avant une nouvelle tentative HTTP."""
        delay = (
            self._settings.http_retry_delay_seconds
            * 2 ** (attempt - 1)
        )

        status_message = (
            f" après le statut HTTP {status_code}"
            if status_code is not None
            else ""
        )

        logger.warning(
            "Nouvelle tentative YouTube dans %.2f "
            "seconde(s) pour %s après la tentative "
            "%s%s.",
            delay,
            endpoint,
            attempt,
            status_message,
        )

        await asyncio.sleep(
            delay
        )

    # Recherche

    async def search_videos(
        self,
        request: VideoSearchRequest,
    ) -> VideoCollection:
        """Recherche des vidéos pédagogiques."""
        async with self._operation(
            "search_videos"
        ):
            normalized_query = (
                self._normalize_query(
                    request.query
                )
            )

            normalized_limit = (
                self._normalize_max_results(
                    request.max_results
                )
            )

            normalized_language = (
                self._normalize_language(
                    request.language
                )
            )

            search_query = (
                self._build_search_query(
                    normalized_query
                )
            )

            logger.info(
                "Recherche de vidéos YouTube pour : %s",
                normalized_query,
            )

            search_payload = await self._request(
                YOUTUBE_SEARCH_ENDPOINT,
                params={
                    "part": YOUTUBE_SEARCH_PART,
                    "q": search_query,
                    "type": YOUTUBE_SEARCH_TYPE,
                    "order": YOUTUBE_SEARCH_ORDER,
                    "safeSearch": (
                        YOUTUBE_SEARCH_SAFE_SEARCH
                    ),
                    "videoDuration": (
                        YOUTUBE_SEARCH_VIDEO_DURATION
                    ),
                    "relevanceLanguage": (
                        normalized_language
                    ),
                    "regionCode": (
                        self._settings.youtube_region_code
                    ),
                    "maxResults": normalized_limit,
                },
            )

            video_ids = self._extract_video_ids(
                search_payload
            )

            details = await self._get_video_details(
                video_ids
            )

            recommendations = (
                self._build_recommendations(
                    search_payload,
                    details=details,
                    query=normalized_query,
                )
            )

            logger.info(
                "%s vidéo(s) YouTube conservée(s) "
                "pour %s.",
                len(recommendations),
                normalized_query,
            )

            return VideoCollection(
                query=normalized_query,
                total_results=len(
                    recommendations
                ),
                videos=recommendations,
            )

    async def _get_video_details(
        self,
        video_ids: Sequence[str],
    ) -> dict[str, YoutubeVideoDetails]:
        """Récupère les métadonnées complémentaires."""
        if not video_ids:
            return {}

        payload = await self._request(
            YOUTUBE_VIDEOS_ENDPOINT,
            params={
                "part": (
                    YOUTUBE_VIDEO_DETAILS_PART
                ),
                "id": ",".join(
                    video_ids
                ),
            },
        )

        return self._extract_video_details(
            payload
        )

    # Normalisation

    def _normalize_query(
        self,
        query: object,
    ) -> str:
        """Valide et normalise une recherche."""
        if not isinstance(
            query,
            str,
        ):
            raise InvalidRequestError(
                context=ErrorContext(
                    service=SERVICE_NAME,
                    operation="_normalize_query",
                ),
                message=(
                    "La recherche YouTube doit être "
                    "une chaîne de caractères."
                ),
            )

        normalized_query = " ".join(
            query.split()
        )

        if not normalized_query:
            raise InvalidRequestError(
                context=ErrorContext(
                    service=SERVICE_NAME,
                    operation="_normalize_query",
                ),
                message=(
                    "La recherche YouTube ne peut "
                    "pas être vide."
                ),
            )

        return normalized_query

    def _normalize_max_results(
        self,
        max_results: object | None,
    ) -> int:
        """Valide le nombre maximal de résultats."""
        normalized_limit = (
            max_results
            if max_results is not None
            else self._settings.youtube_search_max_results
        )

        if (
            isinstance(
                normalized_limit,
                bool,
            )
            or not isinstance(
                normalized_limit,
                int,
            )
        ):
            raise InvalidRequestError(
                context=ErrorContext(
                    service=SERVICE_NAME,
                    operation="_normalize_max_results",
                ),
                message=(
                    "Le nombre maximal de vidéos "
                    "doit être un entier."
                ),
            )

        if not (
            MIN_SEARCH_RESULTS
            <= normalized_limit
            <= MAX_SEARCH_RESULTS
        ):
            raise InvalidRequestError(
                context=ErrorContext(
                    service=SERVICE_NAME,
                    operation="_normalize_max_results",
                ),
                message=(
                    "Le nombre maximal de vidéos "
                    "doit être compris entre "
                    f"{MIN_SEARCH_RESULTS} et "
                    f"{MAX_SEARCH_RESULTS}."
                ),
            )

        return normalized_limit

    def _normalize_language(
        self,
        language: object | None,
    ) -> str:
        """Valide et normalise la langue de recherche."""
        normalized_language = (
            language
            if language is not None
            else self._settings.youtube_default_language
        )

        if not isinstance(
            normalized_language,
            str,
        ):
            raise InvalidRequestError(
                context=ErrorContext(
                    service=SERVICE_NAME,
                    operation="_normalize_language",
                ),
                message=(
                    "La langue YouTube doit être "
                    "une chaîne de caractères."
                ),
            )

        normalized_language = (
            normalized_language
            .strip()
            .lower()
        )

        if not (
            MIN_LANGUAGE_LENGTH
            <= len(normalized_language)
            <= MAX_LANGUAGE_LENGTH
        ):
            raise InvalidRequestError(
                context=ErrorContext(
                    service=SERVICE_NAME,
                    operation="_normalize_language",
                ),
                message=(
                    "La langue YouTube doit contenir "
                    f"entre {MIN_LANGUAGE_LENGTH} et "
                    f"{MAX_LANGUAGE_LENGTH} caractères."
                ),
            )

        return normalized_language

    def _build_search_query(
        self,
        query: str,
    ) -> str:
        """Construit une recherche pédagogique."""
        return (
            f"{query} "
            f"{self._settings.youtube_query_suffix}"
        )

    # Extraction

    def _extract_video_ids(
        self,
        payload: YoutubePayload,
    ) -> list[str]:
        """Extrait les identifiants uniques des vidéos."""
        items = payload.get(
            "items"
        )

        if not isinstance(
            items,
            list,
        ):
            return []

        video_ids: list[str] = []

        seen_video_ids: set[str] = set()

        for item in items:
            if not isinstance(
                item,
                dict,
            ):
                continue

            identifier = item.get(
                "id"
            )

            if not isinstance(
                identifier,
                dict,
            ):
                continue

            video_id = self._get_text(
                identifier.get(
                    "videoId"
                )
            )

            if (
                not video_id
                or video_id in seen_video_ids
            ):
                continue

            seen_video_ids.add(
                video_id
            )

            video_ids.append(
                video_id
            )

        return video_ids

    def _extract_video_details(
        self,
        payload: YoutubePayload,
    ) -> dict[str, YoutubeVideoDetails]:
        """Extrait les métadonnées complémentaires."""
        items = payload.get(
            "items"
        )

        if not isinstance(
            items,
            list,
        ):
            return {}

        details: dict[
            str,
            YoutubeVideoDetails
        ] = {}

        for item in items:
            if not isinstance(
                item,
                dict,
            ):
                continue

            video_id = self._get_text(
                item.get("id")
            )

            if not video_id:
                continue

            content_details = item.get(
                "contentDetails"
            )

            statistics = item.get(
                "statistics"
            )

            duration_seconds: int | None = None
            view_count: int | None = None
            like_count: int | None = None
            comment_count: int | None = None

            if isinstance(
                content_details,
                dict,
            ):
                duration_seconds = (
                    self._parse_duration(
                        content_details.get(
                            "duration"
                        )
                    )
                )

            if isinstance(
                statistics,
                dict,
            ):
                view_count = (
                    self._parse_optional_int(
                        statistics.get(
                            "viewCount"
                        )
                    )
                )

                like_count = (
                    self._parse_optional_int(
                        statistics.get(
                            "likeCount"
                        )
                    )
                )

                comment_count = (
                    self._parse_optional_int(
                        statistics.get(
                            "commentCount"
                        )
                    )
                )

            details[video_id] = {
                "duration_seconds": (
                    duration_seconds
                ),
                "view_count": (
                    view_count
                ),
                "like_count": (
                    like_count
                ),
                "comment_count": (
                    comment_count
                ),
            }

        return details

    # Construction

    def _build_recommendations(
        self,
        payload: YoutubePayload,
        *,
        details: Mapping[
            str,
            YoutubeVideoDetails,
        ],
        query: str,
    ) -> list[VideoRecommendation]:
        """Construit les recommandations vidéo uniques."""
        items = payload.get(
            "items"
        )

        if not isinstance(
            items,
            list,
        ):
            return []

        recommendations: list[
            VideoRecommendation
        ] = []

        seen_video_ids: set[str] = set()

        for rank, item in enumerate(
            items,
            start=1,
        ):
            recommendation = (
                self._build_recommendation(
                    item,
                    details=details,
                    query=query,
                    rank=rank,
                )
            )

            if recommendation is None:
                continue

            video_id = (
                recommendation.video.id
            )

            if video_id in seen_video_ids:
                continue

            seen_video_ids.add(
                video_id
            )

            recommendations.append(
                recommendation
            )

        return recommendations

    def _build_recommendation(
        self,
        item: JsonValue,
        *,
        details: Mapping[
            str,
            YoutubeVideoDetails,
        ],
        query: str,
        rank: int,
    ) -> VideoRecommendation | None:
        """Construit une recommandation YouTube."""
        if not isinstance(
            item,
            dict,
        ):
            return None

        identifier = item.get(
            "id"
        )

        snippet = item.get(
            "snippet"
        )

        if (
            not isinstance(identifier, dict)
            or not isinstance(snippet, dict)
        ):
            return None

        video_id = self._get_text(
            identifier.get(
                "videoId"
            )
        )

        title = self._get_text(
            snippet.get(
                "title"
            )
        )

        channel_name = self._get_text(
            snippet.get(
                "channelTitle"
            )
        )

        if (
            not video_id
            or not title
            or not channel_name
        ):
            return None

        description = (
            self._get_optional_text(
                snippet.get(
                    "description"
                )
            )
        )

        if not self._is_relevant_video(
            title=title,
            description=description,
            channel_name=channel_name,
            query=query,
        ):
            return None

        channel_id = (
            self._get_optional_text(
                snippet.get(
                    "channelId"
                )
            )
        )

        matching_topics = (
            self._get_matching_topics(
                title=title,
                description=description,
                query=query,
            )
        )

        video_details = details.get(
            video_id
        )

        video = Video(
            id=video_id,
            platform=VideoPlatform.YOUTUBE,
            title=title,
            description=description,
            url=(
                YOUTUBE_VIDEO_URL_TEMPLATE.format(
                    video_id=video_id
                )
            ),
            thumbnail_url=(
                self._get_thumbnail_url(
                    snippet.get(
                        "thumbnails"
                    )
                )
            ),
            duration_seconds=(
                video_details[
                    "duration_seconds"
                ]
                if video_details is not None
                else None
            ),
            view_count=(
                video_details[
                    "view_count"
                ]
                if video_details is not None
                else None
            ),
            like_count=(
                video_details[
                    "like_count"
                ]
                if video_details is not None
                else None
            ),
            comment_count=(
                video_details[
                    "comment_count"
                ]
                if video_details is not None
                else None
            ),
            published_at=(
                self._get_optional_text(
                    snippet.get(
                        "publishedAt"
                    )
                )
            ),
            channel=VideoChannel(
                id=channel_id,
                name=channel_name,
                url=(
                    YOUTUBE_CHANNEL_URL_TEMPLATE.format(
                        channel_id=channel_id
                    )
                    if channel_id is not None
                    else None
                ),
                subscribers=None,
            ),
            language=(
                self._get_optional_text(
                    snippet.get(
                        "defaultLanguage"
                    )
                )
            ),
        )

        return VideoRecommendation(
            video=video,
            relevance_score=(
                self._calculate_relevance_score(
                    rank=rank,
                    matching_topics=matching_topics,
                )
            ),
            reason=(
                "Vidéo pédagogique correspondant "
                "à l'ouverture analysée."
            ),
            matching_topics=matching_topics,
        )

    # Pertinence

    def _is_relevant_video(
        self,
        *,
        title: str,
        description: str | None,
        channel_name: str,
        query: str,
    ) -> bool:
        """Vérifie qu'une vidéo concerne les échecs et la recherche."""
        searchable_text = " ".join(
            (
                title,
                description or "",
                channel_name,
            )
        ).casefold()

        has_chess_context = any(
            term in searchable_text
            for term in REQUIRED_CHESS_TERMS
        )

        if not has_chess_context:
            return False

        query_terms = {
            word
            for word in query.casefold().split()
            if len(word) >= MIN_TOPIC_LENGTH
        }

        if not query_terms:
            return True

        return any(
            term in searchable_text
            for term in query_terms
        )

    def _get_matching_topics(
        self,
        *,
        title: str,
        description: str | None,
        query: str,
    ) -> list[str]:
        """Retourne les thèmes correspondant à la recherche."""
        searchable_text = (
            f"{title} {description or ''}"
            .casefold()
        )

        topics = [
            word
            for word
            in query.casefold().split()
            if (
                len(word) >= MIN_TOPIC_LENGTH
                and word in searchable_text
            )
        ]

        return list(
            dict.fromkeys(
                topics
            )
        )

    def _calculate_relevance_score(
        self,
        *,
        rank: int,
        matching_topics: Sequence[str],
    ) -> float:
        """Calcule un score simple de pertinence."""
        rank_score = max(
            1.0
            - (rank - 1)
            * RANK_SCORE_DECREMENT,
            MIN_RELEVANCE_SCORE,
        )

        topic_bonus = min(
            len(matching_topics)
            * TOPIC_SCORE_INCREMENT,
            MAX_TOPIC_SCORE,
        )

        return min(
            rank_score + topic_bonus,
            1.0,
        )

    # Conversion

    def _get_thumbnail_url(
        self,
        thumbnails: JsonValue | None,
    ) -> str | None:
        """Retourne la meilleure miniature disponible."""
        if not isinstance(
            thumbnails,
            dict,
        ):
            return None

        for quality in (
            "maxres",
            "standard",
            "high",
            "medium",
            "default",
        ):
            thumbnail = thumbnails.get(
                quality
            )

            if not isinstance(
                thumbnail,
                dict,
            ):
                continue

            url = self._get_optional_text(
                thumbnail.get(
                    "url"
                )
            )

            if url:
                return url

        return None

    def _parse_duration(
        self,
        value: JsonValue | None,
    ) -> int | None:
        """Convertit une durée ISO 8601 en secondes."""
        normalized_value = (
            self._get_text(
                value
            )
        )

        if not normalized_value:
            return None

        match = DURATION_PATTERN.fullmatch(
            normalized_value
        )

        if match is None:
            logger.debug(
                "Durée YouTube invalide : %s",
                normalized_value,
            )
            return None

        days = int(
            match.group("days")
            or 0
        )

        hours = int(
            match.group("hours")
            or 0
        )

        minutes = int(
            match.group("minutes")
            or 0
        )

        seconds = int(
            match.group("seconds")
            or 0
        )

        return (
            days * SECONDS_PER_DAY
            + hours * SECONDS_PER_HOUR
            + minutes * SECONDS_PER_MINUTE
            + seconds
        )

    def _parse_optional_int(
        self,
        value: JsonValue | None,
    ) -> int | None:
        """Convertit un compteur YouTube en entier."""
        normalized_value = (
            self._get_text(
                value
            )
        )

        if not normalized_value:
            return None

        try:
            return int(
                normalized_value
            )

        except ValueError:
            logger.debug(
                "Valeur numérique YouTube invalide : %s",
                normalized_value,
            )
            return None

    def _get_text(
        self,
        value: JsonValue | None,
    ) -> str:
        """Retourne une chaîne nettoyée."""
        if not isinstance(
            value,
            str,
        ):
            return ""

        return " ".join(
            value.split()
        )

    def _get_optional_text(
        self,
        value: JsonValue | None,
    ) -> str | None:
        """Retourne une chaîne nettoyée ou ``None``."""
        return (
            self._get_text(value)
            or None
        )

    # Informations

    def is_closed(self) -> bool:
        """Indique si le client HTTP est fermé."""
        return self._client.is_closed

    def is_ready(self) -> bool:
        """Indique si le service peut être utilisé."""
        if (
            self._closing
            or self._client.is_closed
        ):
            return False

        try:
            self._get_api_key()

        except YoutubeConfigurationError:
            return False

        return True

    # Santé

    async def ping(self) -> bool:
        """Vérifie que le service YouTube est prêt à être utilisé."""
        if (
            self._closing
            or self._client.is_closed
        ):
            logger.error(
                "Le client HTTP YouTube est fermé."
            )
            return False

        try:
            self._get_api_key()

        except YoutubeConfigurationError:
            logger.info(
                "Aucune clé API YouTube configurée. "
                "Le service est désactivé."
            )
            return False

        return True

    async def health(
        self,
    ) -> YoutubeServiceStatus:
        """Retourne l'état de santé détaillé du service."""
        available = await self.ping()

        return {
            "service": SERVICE_NAME,
            "is_ready": self.is_ready(),
            "is_closed": self.is_closed(),
            "available": available,
            "base_url": str(
                self._client.base_url
            ),
            "search_endpoint": (
                YOUTUBE_SEARCH_ENDPOINT
            ),
            "videos_endpoint": (
                YOUTUBE_VIDEOS_ENDPOINT
            ),
            "region_code": (
                self._settings.youtube_region_code
            ),
            "default_language": (
                self._settings.youtube_default_language
            ),
            "query_suffix": (
                self._settings.youtube_query_suffix
            ),
            "max_results": (
                self._settings.youtube_search_max_results
            ),
            "timeout_seconds": (
                self._settings.youtube_timeout_seconds
            ),
            "max_retry_attempts": (
                self._settings.http_max_retry_attempts
            ),
            "retry_delay_seconds": (
                self._settings.http_retry_delay_seconds
            ),
            "max_connections": (
                self._settings.http_max_connections
            ),
            "user_agent": (
                self._settings.http_user_agent
            ),
        }