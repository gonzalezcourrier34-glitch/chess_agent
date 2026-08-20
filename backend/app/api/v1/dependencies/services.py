"""Dépendances d'injection des services applicatifs.

Ce module centralise :

- l'accès au conteneur stocké dans FastAPI ;
- la récupération typée des services ;
- la vérification de l'initialisation applicative.

Il ne crée aucun service.

Les services sont construits une seule fois par le conteneur applicatif,
puis injectés dans les endpoints FastAPI avec Depends.
"""

from __future__ import annotations

from typing import Annotated

from fastapi import Depends, Request

from app.adapters.embedding_service import EmbeddingService
from app.adapters.lichess_service import LichessService
from app.adapters.llm_service import LLMService
from app.adapters.milvus_service import MilvusService
from app.adapters.mongodb_service import MongoDBService
from app.adapters.stockfish_service import StockfishService
from app.adapters.youtube_service import YoutubeService
from app.core.container import ApplicationContainer
from app.core.exceptions import ConfigurationError
from app.services.analysis_service import AnalysisService
from app.services.chess_service import ChessService
from app.services.healthcheck_service import HealthcheckService
from app.services.vector_search_service import VectorSearchService

# Conteneur


def get_application_container(request: Request) -> ApplicationContainer:
    """Retourne le conteneur applicatif initialisé."""

    container = getattr(request.app.state, "container", None)

    if not isinstance(container, ApplicationContainer):
        raise ConfigurationError(
            message=("Le conteneur applicatif n'est pas initialisé.")
        )

    return container


# Dépendance du conteneur

ApplicationContainerDependency = Annotated[
    ApplicationContainer, Depends(get_application_container)
]


# Services d'orchestration


def get_analysis_service(container: ApplicationContainerDependency) -> AnalysisService:
    """Retourne le service d'analyse."""

    service = container.analysis

    if service is None:
        raise ConfigurationError(message=("Le service d'analyse n'est pas initialisé."))

    return service


# Services métier


def get_chess_service(container: ApplicationContainerDependency) -> ChessService:
    """Retourne le service échiquéen."""

    return container.chess


def get_stockfish_service(
    container: ApplicationContainerDependency,
) -> StockfishService:
    """Retourne le service Stockfish."""

    return container.stockfish


# Services d'ouverture


def get_lichess_service(container: ApplicationContainerDependency) -> LichessService:
    """Retourne le service Lichess."""

    return container.lichess


# Services RAG


def get_embedding_service(
    container: ApplicationContainerDependency,
) -> EmbeddingService:
    """Retourne le service de génération d'embeddings."""

    return container.embedding


def get_milvus_service(container: ApplicationContainerDependency) -> MilvusService:
    """Retourne le service Milvus."""

    return container.milvus


def get_vector_search_service(
    container: ApplicationContainerDependency,
) -> VectorSearchService:
    """Retourne le service de recherche vectorielle."""

    return container.vector_search


# Services de génération


def get_llm_service(container: ApplicationContainerDependency) -> LLMService:
    """Retourne le service LLM."""

    return container.llm


# Services multimédias


def get_youtube_service(container: ApplicationContainerDependency) -> YoutubeService:
    """Retourne le service YouTube."""

    return container.youtube


# Services de persistance


def get_mongodb_service(container: ApplicationContainerDependency) -> MongoDBService:
    """Retourne le service MongoDB."""

    return container.mongodb


# Services de supervision


def get_healthcheck_service(
    container: ApplicationContainerDependency,
) -> HealthcheckService:
    """Retourne le service de supervision."""

    service = container.healthcheck

    if service is None:
        raise ConfigurationError(
            message=("Le service de supervision n'est pas initialisé.")
        )

    return service


# Dépendances typées

AnalysisServiceDependency = Annotated[AnalysisService, Depends(get_analysis_service)]

ChessServiceDependency = Annotated[ChessService, Depends(get_chess_service)]

StockfishServiceDependency = Annotated[StockfishService, Depends(get_stockfish_service)]

LichessServiceDependency = Annotated[LichessService, Depends(get_lichess_service)]

EmbeddingServiceDependency = Annotated[EmbeddingService, Depends(get_embedding_service)]

MilvusServiceDependency = Annotated[MilvusService, Depends(get_milvus_service)]

VectorSearchServiceDependency = Annotated[
    VectorSearchService, Depends(get_vector_search_service)
]

LLMServiceDependency = Annotated[LLMService, Depends(get_llm_service)]

YoutubeServiceDependency = Annotated[YoutubeService, Depends(get_youtube_service)]

MongoDBServiceDependency = Annotated[MongoDBService, Depends(get_mongodb_service)]

HealthcheckServiceDependency = Annotated[
    HealthcheckService, Depends(get_healthcheck_service)
]
