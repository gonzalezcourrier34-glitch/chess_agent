"""Conteneur des dépendances de Chess Agent.

Ce module centralise :

- la création des services applicatifs ;
- le partage des dépendances communes ;
- la préparation des dépendances utilisées par LangGraph ;
- la construction des services d'orchestration ;
- le stockage des ressources partagées.

Le conteneur constitue le point d'entrée unique des dépendances techniques de
l'application. Le cycle de vie des ressources reste géré par
``app.core.lifespan``.
"""

from __future__ import annotations

import asyncio
from dataclasses import dataclass
from typing import Protocol, TypedDict

from langgraph.graph.state import CompiledStateGraph

from app.adapters.embedding_service import EmbeddingService
from app.adapters.lichess_service import LichessService
from app.adapters.llm_service import LLMService
from app.adapters.milvus_service import MilvusService
from app.adapters.mongodb_service import MongoDBService
from app.adapters.stockfish_service import StockfishService
from app.adapters.youtube_service import YoutubeService
from app.agent.graph import GraphDependencies
from app.agent.graph import build_graph as build_agent_graph
from app.core.logging import get_logger
from app.services.analysis_service import AnalysisService
from app.services.chess_service import ChessService
from app.services.healthcheck_service import HealthcheckService
from app.services.vector_search_service import VectorSearchService

logger = get_logger(__name__)


# Types


class PingableService(Protocol):
    """Décrit un service dont la disponibilité peut être vérifiée."""

    async def ping(self) -> bool:
        """Retourne si le service est disponible."""
        ...


class ContainerHealthStatus(TypedDict):
    """Décrit l'état des dépendances du conteneur."""

    mongodb: bool
    milvus: bool
    embedding: bool
    vector_search: bool
    stockfish: bool
    lichess: bool
    youtube: bool
    llm: bool
    graph: bool
    analysis: bool
    healthcheck: bool


# Santé


async def _ping_service(
    service_name: str,
    service: PingableService
) -> tuple[str, bool]:
    """Vérifie un service sans interrompre les autres contrôles."""
    try:
        available = await service.ping()
    except Exception:
        logger.exception(
            "État indisponible pour le service %s.",
            service_name
        )
        available = False

    return service_name, available


# Conteneur


@dataclass(slots=True, kw_only=True)
class ApplicationContainer:
    """Regroupe les dépendances partagées par l'application."""

    # Services métier

    chess: ChessService
    vector_search: VectorSearchService

    # Adapters

    stockfish: StockfishService
    lichess: LichessService
    embedding: EmbeddingService
    milvus: MilvusService
    mongodb: MongoDBService
    llm: LLMService
    youtube: YoutubeService

    # Workflow

    agent_graph: CompiledStateGraph | None = None
    analysis: AnalysisService | None = None
    healthcheck: HealthcheckService | None = None

    # Infrastructure

    # Le conteneur conserve uniquement cette référence. Le type concret et son
    # cycle de vie appartiennent à app.core.lifespan.
    resource_manager: object | None = None

    # LangGraph

    def to_graph_dependencies(self) -> GraphDependencies:
        """Construit les dépendances nécessaires au workflow."""
        return GraphDependencies(
            chess_service=self.chess,
            stockfish_service=self.stockfish,
            lichess_service=self.lichess,
            embedding_service=self.embedding,
            milvus_service=self.milvus,
            vector_search_service=self.vector_search,
            llm_service=self.llm,
            youtube_service=self.youtube,
            mongodb_service=self.mongodb
        )

    # Construction

    def build_graph(self) -> None:
        """Construit atomiquement le workflow et les services associés."""
        if self.is_ready():
            logger.debug("Le workflow LangGraph est déjà initialisé.")
            return

        if any(
            component is not None
            for component in (
                self.agent_graph,
                self.analysis,
                self.healthcheck
            )
        ):
            logger.warning(
                "État partiel détecté durant la construction du workflow."
            )

        logger.debug("Construction du workflow LangGraph.")

        # Les composants ne sont publiés qu'après leur construction complète.
        # Une exception ne laisse donc pas le conteneur dans un état
        # partiellement opérationnel.
        graph = build_agent_graph()
        analysis = AnalysisService(
            graph=graph,
            dependencies=self.to_graph_dependencies()
        )
        
        healthcheck = HealthcheckService(
            mongodb_service=self.mongodb,
            milvus_service=self.milvus,
            embedding_service=self.embedding,
            stockfish_service=self.stockfish,
            lichess_service=self.lichess,
            youtube_service=self.youtube,
            llm_service=self.llm,
            analysis_service=analysis
        )
        
        self.agent_graph = graph
        self.analysis = analysis
        self.healthcheck = healthcheck

        logger.info("Workflow LangGraph initialisé.")

    def destroy_graph(self) -> None:
        """Libère les composants construits autour du workflow."""
        self.healthcheck = None
        self.analysis = None
        self.agent_graph = None

        logger.info("Workflow LangGraph libéré.")

    # Informations

    def is_graph_ready(self) -> bool:
        """Indique si le workflow LangGraph est disponible."""
        return self.agent_graph is not None

    def is_analysis_ready(self) -> bool:
        """Indique si le service d'analyse est disponible."""
        return self.analysis is not None

    def is_healthcheck_ready(self) -> bool:
        """Indique si le service de supervision est disponible."""
        return self.healthcheck is not None

    def is_ready(self) -> bool:
        """Indique si le conteneur est entièrement opérationnel."""
        return (
            self.is_graph_ready()
            and self.is_analysis_ready()
            and self.is_healthcheck_ready()
        )

    # Santé

    async def health(self) -> ContainerHealthStatus:
        """Retourne l'état des dépendances du conteneur."""
        services: tuple[tuple[str, PingableService], ...] = (
            ("mongodb", self.mongodb),
            ("milvus", self.milvus),
            ("embedding", self.embedding),
            ("vector_search", self.vector_search),
            ("stockfish", self.stockfish),
            ("lichess", self.lichess),
            ("youtube", self.youtube),
            ("llm", self.llm)
        )
        service_statuses = dict(
            await asyncio.gather(
                *(
                    _ping_service(service_name, service)
                    for service_name, service in services
                )
            )
        )

        return {
            "mongodb": service_statuses["mongodb"],
            "milvus": service_statuses["milvus"],
            "embedding": service_statuses["embedding"],
            "vector_search": service_statuses["vector_search"],
            "stockfish": service_statuses["stockfish"],
            "lichess": service_statuses["lichess"],
            "youtube": service_statuses["youtube"],
            "llm": service_statuses["llm"],
            "graph": self.is_graph_ready(),
            "analysis": self.is_analysis_ready(),
            "healthcheck": self.is_healthcheck_ready()
        }


# Construction


def create_application_container() -> ApplicationContainer:
    """Construit le conteneur applicatif."""
    chess_service = ChessService()

    stockfish_service = StockfishService()
    lichess_service = LichessService()

    embedding_service = EmbeddingService()
    milvus_service = MilvusService()
    vector_search_service = VectorSearchService(
        embedding_service=embedding_service,
        milvus_service=milvus_service
    )

    llm_service = LLMService()
    youtube_service = YoutubeService()
    mongodb_service = MongoDBService()

    return ApplicationContainer(
        chess=chess_service,
        vector_search=vector_search_service,
        stockfish=stockfish_service,
        lichess=lichess_service,
        embedding=embedding_service,
        milvus=milvus_service,
        llm=llm_service,
        youtube=youtube_service,
        mongodb=mongodb_service
    )