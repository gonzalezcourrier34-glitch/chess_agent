"""Service de supervision de Chess Agent.

Ce service centralise la vérification de l'état des principaux
composants de l'application.

Il est responsable de :

- interroger les services applicatifs ;
- agréger leurs états de disponibilité ;
- déterminer l'état global du backend ;
- construire la réponse retournée par l'endpoint de santé.

Le service ne dépend pas de FastAPI.

Il ne démarre, ne ferme et ne recrée aucune ressource.
"""

from __future__ import annotations

import asyncio
from collections.abc import Awaitable, Callable
from typing import Any

from app.adapters.embedding_service import EmbeddingService
from app.adapters.lichess_service import LichessService
from app.adapters.llm_service import LLMService
from app.adapters.milvus_service import MilvusService
from app.adapters.mongodb_service import MongoDBService
from app.adapters.stockfish_service import StockfishService
from app.adapters.youtube_service import YoutubeService
from app.core.config import settings
from app.core.logging import get_logger
from app.schemas.analysis.healthcheck import HealthcheckResponse
from app.schemas.common.enums import ServiceStatus
from app.schemas.common.service import ServiceHealth, ServicesStatus
from app.services.analysis_service import AnalysisService
from app.core.exceptions import ApplicationNotReadyError

logger = get_logger(__name__)


# Types

ServicePingFunction = Callable[[], Awaitable[bool]]

ServiceAvailability = dict[str, bool]

HealthcheckServiceStatus = dict[str, Any]


# Configuration

HEALTHY_STATUS = "healthy"

DEGRADED_STATUS = "degraded"

REQUIRED_SERVICE_NAMES = frozenset({
    "mongodb",
    "milvus",
    "embedding",
    "stockfish",
    "llm",
    "langgraph"
})


# Service

class HealthcheckService:
    """Service de supervision des composants applicatifs."""

    # Construction

    def __init__(
        self,
        *,
        mongodb_service: MongoDBService,
        milvus_service: MilvusService,
        embedding_service: EmbeddingService,
        stockfish_service: StockfishService,
        lichess_service: LichessService,
        youtube_service: YoutubeService,
        llm_service: LLMService,
        analysis_service: AnalysisService
    ) -> None:
        """Initialise le service."""

        self._mongodb_service = mongodb_service
        self._milvus_service = milvus_service
        self._embedding_service = embedding_service
        self._stockfish_service = stockfish_service
        self._lichess_service = lichess_service
        self._youtube_service = youtube_service
        self._llm_service = llm_service
        self._analysis_service = analysis_service

    # Vérification

    async def _check_service(
        self,
        *,
        name: str,
        ping_function: ServicePingFunction
    ) -> bool:
        """Vérifie un service sans interrompre le healthcheck."""

        try:
            return bool(await ping_function())

        except Exception:
            logger.exception(
                "Échec du contrôle du service %s.",
                name
            )

            return False

    async def _check_services(
        self
    ) -> ServiceAvailability:
        """Retourne la disponibilité de tous les services."""

        service_checks = {
            "mongodb": (
                "MongoDB",
                self._mongodb_service.ping
            ),
            "milvus": (
                "Milvus",
                self._milvus_service.ping
            ),
            "embedding": (
                "Embedding",
                self._embedding_service.ping
            ),
            "stockfish": (
                "Stockfish",
                self._stockfish_service.ping
            ),
            "lichess": (
                "Lichess",
                self._lichess_service.ping
            ),
            "youtube": (
                "YouTube",
                self._youtube_service.ping
            ),
            "llm": (
                "LLM",
                self._llm_service.ping
            ),
            "langgraph": (
                "LangGraph",
                self._analysis_service.ping
            )
        }

        service_names = list(service_checks)

        availabilities = await asyncio.gather(
            *(
                self._check_service(
                    name=display_name,
                    ping_function=ping_function
                )
                for display_name, ping_function
                in service_checks.values()
            )
        )

        return dict(
            zip(
                service_names,
                availabilities,
                strict=True
            )
        )

    async def _check_required_services(
        self
    ) -> ServiceAvailability:
        """Retourne la disponibilité des services critiques."""

        service_checks = {
            "mongodb": (
                "MongoDB",
                self._mongodb_service.ping
            ),
            "milvus": (
                "Milvus",
                self._milvus_service.ping
            ),
            "embedding": (
                "Embedding",
                self._embedding_service.ping
            ),
            "stockfish": (
                "Stockfish",
                self._stockfish_service.ping
            ),
            "llm": (
                "LLM",
                self._llm_service.ping
            ),
            "langgraph": (
                "LangGraph",
                self._analysis_service.ping
            )
        }

        service_names = list(
            service_checks
        )

        availabilities = await asyncio.gather(
            *(
                self._check_service(
                    name=display_name,
                    ping_function=ping_function
                )
                for display_name, ping_function
                in service_checks.values()
            )
        )

        return dict(
            zip(
                service_names,
                availabilities,
                strict=True
            )
        )

    async def check_readiness(
        self
    ) -> None:
        """Vérifie que les services critiques sont disponibles."""

        logger.debug(
            "Exécution du contrôle de readiness."
        )

        services = await self._check_required_services()

        unavailable_services = [
            service_name
            for service_name in REQUIRED_SERVICE_NAMES
            if not services.get(
                service_name,
                False
            )
        ]

        if unavailable_services:
            logger.warning(
                "Application non prête. "
                "Services critiques indisponibles : %s.",
                ", ".join(
                    sorted(
                        unavailable_services
                    )
                )
            )

            raise ApplicationNotReadyError(
                unavailable_services=sorted(
                    unavailable_services
                )
            )

        logger.info(
            "Application prête."
        )
    
    # Statuts

    def _get_service_status(
        self,
        available: bool
    ) -> ServiceStatus:
        """Retourne le statut normalisé d'un service."""

        if available:
            return ServiceStatus.AVAILABLE

        return ServiceStatus.UNAVAILABLE

    def _get_application_status(
        self,
        services: ServiceAvailability
    ) -> str:
        """Retourne l'état global de l'application."""

        required_services_available = all(
            services.get(
                service_name,
                False
            )
            for service_name in REQUIRED_SERVICE_NAMES
        )

        if required_services_available:
            return HEALTHY_STATUS

        return DEGRADED_STATUS

    # Construction

    def _build_service_health(
        self,
        available: bool
    ) -> ServiceHealth:
        """Construit l'état normalisé d'un service."""

        status = self._get_service_status(
            available
        )

        message = None

        if not available:
            message = "Service indisponible."

        return ServiceHealth(
            available=available,
            status=status,
            message=message
        )

    def _build_response(
        self,
        services: ServiceAvailability
    ) -> HealthcheckResponse:
        """Construit la réponse complète du healthcheck."""

        return HealthcheckResponse(
            status=self._get_application_status(
                services
            ),
            application=settings.app_name,
            version=settings.app_version,
            environment=settings.app_env,
            embedding_model=settings.embedding_model,
            milvus_collection=settings.milvus_collection_name,
            services=ServicesStatus(
                mongodb=self._build_service_health(
                    services["mongodb"]
                ),
                milvus=self._build_service_health(
                    services["milvus"]
                ),
                embedding=self._build_service_health(
                    services["embedding"]
                ),
                stockfish=self._build_service_health(
                    services["stockfish"]
                ),
                lichess=self._build_service_health(
                    services["lichess"]
                ),
                youtube=self._build_service_health(
                    services["youtube"]
                ),
                llm=self._build_service_health(
                    services["llm"]
                ),
                langgraph=self._build_service_health(
                    services["langgraph"]
                )
            )
        )

    # Supervision

    async def check(
        self
    ) -> HealthcheckResponse:
        """Retourne l'état général de l'application."""

        logger.debug(
            "Exécution du healthcheck applicatif."
        )

        services = await self._check_services()

        response = self._build_response(
            services
        )

        logger.info(
            "Healthcheck terminé avec le statut %s.",
            response.status
        )

        return response

    # Informations

    def is_ready(
        self
    ) -> bool:
        """Indique si le service de supervision est configuré."""

        return all((
            self._mongodb_service is not None,
            self._milvus_service is not None,
            self._embedding_service is not None,
            self._stockfish_service is not None,
            self._lichess_service is not None,
            self._youtube_service is not None,
            self._llm_service is not None,
            self._analysis_service is not None
        ))

    # Santé

    async def ping(
        self
    ) -> bool:
        """Vérifie que le service de supervision est disponible."""

        return self.is_ready()

    async def health(
        self
    ) -> HealthcheckServiceStatus:
        """Retourne l'état de santé du service de supervision."""

        available = await self.ping()

        return {
            "service": "healthcheck",
            "available": available,
            "is_ready": self.is_ready()
        }