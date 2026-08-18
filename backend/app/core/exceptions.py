"""Exceptions centralisées du projet Chess Agent.

Ce module constitue le point d'entrée unique de toutes les exceptions
utilisées dans l'application.

L'objectif est de fournir une architecture d'erreurs homogène,
indépendante de FastAPI et réutilisable dans tous les composants du
backend.

Les exceptions peuvent être utilisées par :

- les services ;
- les repositories ;
- les nœuds LangGraph ;
- les endpoints FastAPI ;
- les tâches asynchrones ;
- les scripts ;
- les tests unitaires.

Chaque exception possède une définition immuable décrivant son identité
fonctionnelle (code, message, statut HTTP, niveau de log, possibilité de
réessai...).

Les instances transportent ensuite les informations spécifiques à
l'erreur rencontrée :

- détails fonctionnels ;
- contexte d'exécution ;
- exception d'origine ;
- informations destinées au frontend.

Toutes les exceptions peuvent être :

- journalisées de manière uniforme ;
- converties en schémas Pydantic ;
- propagées sans dépendre du framework HTTP.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from typing import Any

from app.core.logging import get_logger
from app.schemas.common.error import ApiError

logger = get_logger(__name__)


# Définition des erreurs

# Les définitions sont immuables.
#
# Elles décrivent une famille d'erreurs indépendamment de son
# occurrence.
#
# Toutes les instances d'une même exception partagent donc exactement
# la même définition.


@dataclass(frozen=True, slots=True)
class ErrorDefinition:
    """Définition statique d'une erreur."""

    code: str

    message: str

    status_code: int

    retryable: bool = False

    log_level: int = logging.ERROR


# Contexte d'exécution

# Contrairement à ErrorDefinition, ce contexte est propre à chaque
# occurrence d'une erreur.
#
# Il est principalement utilisé pour enrichir les logs sans exposer
# nécessairement ces informations au frontend.


@dataclass(slots=True)
class ErrorContext:
    """Informations de contexte liées à une erreur."""

    workflow: str | None = None

    node: str | None = None

    service: str | None = None

    operation: str | None = None

    request_id: str | None = None

    metadata: dict[str, Any] = field(
        default_factory=dict
    )


# Exception de base

# Toutes les exceptions du projet héritent de cette classe.
#
# Elle fournit :
#
# - une définition commune ;
# - un contexte d'exécution ;
# - une sérialisation Pydantic ;
# - une représentation lisible ;
# - une journalisation centralisée.
#
# Les classes filles n'ont généralement qu'à redéfinir la variable
# "definition".


class ChessAgentError(Exception):
    """Exception de base du projet."""

    definition = ErrorDefinition(
        code="CHESS_AGENT_ERROR",
        message="Une erreur Chess Agent est survenue.",
        status_code=500
    )

    def __init__(
        self,
        *,
        message: str | None = None,
        details: dict[str, Any] | None = None,
        context: ErrorContext | None = None,
        cause: Exception | None = None
    ) -> None:
        """Initialise une exception métier."""

        self.message = (
            message
            or self.definition.message
        )

        self.details = details or {}

        self.context = (
            context
            or ErrorContext()
        )

        self.cause = cause

        super().__init__(self.message)

    @property
    def code(self) -> str:
        """Retourne le code fonctionnel."""

        return self.definition.code

    @property
    def status_code(self) -> int:
        """Retourne le statut HTTP."""

        return self.definition.status_code

    @property
    def retryable(self) -> bool:
        """Indique si l'opération peut être retentée."""

        return self.definition.retryable

    @property
    def is_client_error(self) -> bool:
        """Indique s'il s'agit d'une erreur 4xx."""

        return 400 <= self.status_code < 500

    @property
    def is_server_error(self) -> bool:
        """Indique s'il s'agit d'une erreur 5xx."""

        return self.status_code >= 500

    @property
    def log_level(self) -> int:
        """Retourne le niveau de journalisation."""

        return self.definition.log_level

    def to_schema(self) -> ApiError:
        """Construit le schéma Pydantic."""

        return ApiError(
            code=self.code,
            message=self.message,
            status_code=self.status_code
        )

    def log(self) -> None:
        """Journalise l'exception.

        Toutes les exceptions du projet utilisent cette méthode afin de
        garantir une structure de log identique.
        """

        payload = {
            "code": self.code,
            "status_code": self.status_code,
            "retryable": self.retryable,
            "details": self.details,
            "workflow": self.context.workflow,
            "node": self.context.node,
            "service": self.context.service,
            "operation": self.context.operation,
            "request_id": self.context.request_id,
            "metadata": self.context.metadata
        }

        if self.cause is not None:

            logger.log(
                self.log_level,
                self.message,
                extra=payload,
                exc_info=self.cause
            )

            return

        logger.log(
            self.log_level,
            self.message,
            extra=payload
        )

    def __str__(self) -> str:
        """Retourne le message utilisateur."""

        return self.message

    def __repr__(self) -> str:
        """Retourne une représentation compacte de l'exception."""

        return (
            f"{self.__class__.__name__}("
            f"code={self.code!r}, "
            f"message={self.message!r})"
        )

# Exceptions liées aux requêtes

# Ces exceptions représentent les erreurs provoquées directement par une
# requête cliente.
#
# Elles correspondent généralement aux codes HTTP 4xx et indiquent que
# le serveur a correctement reçu la requête mais ne peut pas la traiter.


class InvalidRequestError(ChessAgentError):
    """La requête reçue est invalide."""

    definition = ErrorDefinition(
        code="INVALID_REQUEST",
        message="La requête est invalide.",
        status_code=400,
        log_level=logging.WARNING
    )


class AuthenticationError(ChessAgentError):
    """Authentification requise."""

    definition = ErrorDefinition(
        code="AUTHENTICATION_ERROR",
        message="Authentification requise.",
        status_code=401,
        log_level=logging.WARNING
    )


class AuthorizationError(ChessAgentError):
    """L'utilisateur ne possède pas les droits nécessaires."""

    definition = ErrorDefinition(
        code="AUTHORIZATION_ERROR",
        message="Accès refusé.",
        status_code=403,
        log_level=logging.WARNING
    )


class RateLimitExceededError(ChessAgentError):
    """Trop de requêtes ont été envoyées."""

    definition = ErrorDefinition(
        code="RATE_LIMIT_EXCEEDED",
        message="La limite de requêtes est atteinte.",
        status_code=429,
        retryable=True,
        log_level=logging.INFO
    )


# Ressources

# Cette famille concerne les ressources manipulées par l'application.
#
# Une ressource peut être :
#
# - une analyse ;
# - une ouverture ;
# - une vidéo ;
# - un utilisateur ;
# - un document ;
# - un élément de base de données.
#
# Ces erreurs indiquent principalement qu'une ressource est absente,
# déjà existante ou dans un état incompatible.


class ResourceNotFoundError(ChessAgentError):
    """La ressource demandée est introuvable."""

    definition = ErrorDefinition(
        code="RESOURCE_NOT_FOUND",
        message="La ressource demandée est introuvable.",
        status_code=404,
        log_level=logging.INFO
    )


class ResourceConflictError(ChessAgentError):
    """Une ressource existe déjà."""

    definition = ErrorDefinition(
        code="RESOURCE_CONFLICT",
        message="La ressource existe déjà.",
        status_code=409,
        log_level=logging.WARNING
    )


class ResourceLockedError(ChessAgentError):
    """La ressource est momentanément verrouillée."""

    definition = ErrorDefinition(
        code="RESOURCE_LOCKED",
        message="La ressource est actuellement verrouillée.",
        status_code=423,
        retryable=True
    )


# Moteur d'échecs

# Les exceptions suivantes représentent toutes les erreurs provenant de
# python-chess ainsi que des services manipulant un échiquier.
#
# Elles décrivent uniquement des problèmes métier liés au jeu d'échecs.
#
# Les problèmes provenant de Stockfish seront traités plus loin dans la
# partie Infrastructure.


class ChessServiceError(ChessAgentError):
    """Erreur générale du moteur d'échecs."""

    definition = ErrorDefinition(
        code="CHESS_SERVICE_ERROR",
        message="Une erreur est survenue dans le moteur d'échecs.",
        status_code=500
    )


class InvalidFenError(ChessServiceError):
    """La position FEN est invalide."""

    definition = ErrorDefinition(
        code="INVALID_FEN",
        message="La position FEN est invalide.",
        status_code=400,
        log_level=logging.WARNING
    )


class InvalidMoveError(ChessServiceError):
    """Le coup fourni est invalide."""

    definition = ErrorDefinition(
        code="INVALID_MOVE",
        message="Le coup fourni est invalide.",
        status_code=400,
        log_level=logging.WARNING
    )


class IllegalMoveError(ChessServiceError):
    """Le coup n'est pas légal."""

    definition = ErrorDefinition(
        code="ILLEGAL_MOVE",
        message="Le coup n'est pas légal dans cette position.",
        status_code=400,
        log_level=logging.WARNING
    )


class InvalidNotationError(ChessServiceError):
    """Notation SAN ou UCI invalide."""

    definition = ErrorDefinition(
        code="INVALID_NOTATION",
        message="La notation du coup est invalide.",
        status_code=400,
        log_level=logging.WARNING
    )


class InvalidBoardStateError(ChessServiceError):
    """État interne du plateau invalide."""

    definition = ErrorDefinition(
        code="INVALID_BOARD_STATE",
        message="L'état du plateau est invalide.",
        status_code=400,
        log_level=logging.WARNING
    )

# Analyse

# Cette famille regroupe toutes les erreurs produites pendant
# l'analyse d'une position.
#
# Une analyse peut échouer pour plusieurs raisons :
#
# - le moteur d'analyse est indisponible ;
# - le calcul dépasse le temps autorisé ;
# - l'analyse est annulée ;
# - aucune ouverture correspondante n'a été trouvée.
#
# Ces exceptions sont principalement utilisées par les nœuds
# LangGraph responsables de l'analyse d'une partie.


class AnalysisError(ChessAgentError):
    """Erreur générale d'analyse."""

    definition = ErrorDefinition(
        code="ANALYSIS_ERROR",
        message="Une erreur est survenue durant l'analyse.",
        status_code=500
    )

class AnalysisCancelledError(AnalysisError):
    """Analyse interrompue."""

    definition = ErrorDefinition(
        code="ANALYSIS_CANCELLED",
        message="L'analyse a été interrompue.",
        status_code=409,
        log_level=logging.INFO
    )


class OpeningNotFoundError(AnalysisError):
    """Aucune ouverture n'a été trouvée."""

    definition = ErrorDefinition(
        code="OPENING_NOT_FOUND",
        message="Aucune ouverture correspondante n'a été trouvée.",
        status_code=404,
        log_level=logging.INFO
    )


# Recherche vectorielle

# Les exceptions suivantes concernent le moteur RAG.
#
# Elles sont principalement utilisées par les services de recherche
# documentaire et les nœuds LangGraph responsables de récupérer
# le contexte d'une position.
#
# Cette famille couvre notamment :
#
# - la génération des embeddings ;
# - la recherche Milvus ;
# - les dépassements de délai ;
# - l'absence de résultats pertinents.
#
# Les erreurs propres à Milvus seront spécialisées plus loin dans
# la section Infrastructure.


class RetrievalError(ChessAgentError):
    """Erreur générale de recherche documentaire."""

    definition = ErrorDefinition(
        code="RETRIEVAL_ERROR",
        message="La recherche documentaire a échoué.",
        status_code=500
    )


class RetrievalTimeoutError(RetrievalError):
    """Recherche trop longue."""

    definition = ErrorDefinition(
        code="RETRIEVAL_TIMEOUT",
        message="La recherche documentaire a dépassé le délai autorisé.",
        status_code=504,
        retryable=True
    )


class RetrievalEmptyError(RetrievalError):
    """Aucun document pertinent."""

    definition = ErrorDefinition(
        code="RETRIEVAL_EMPTY",
        message="Aucun document pertinent n'a été trouvé.",
        status_code=404,
        log_level=logging.INFO
    )


class EmbeddingError(RetrievalError):
    """Erreur générale liée aux embeddings."""

    definition = ErrorDefinition(
        code="EMBEDDING_ERROR",
        message="Impossible de générer les embeddings.",
        status_code=500
    )


class EmbeddingModelUnavailableError(EmbeddingError):
    """Le modèle d'embedding est indisponible."""

    definition = ErrorDefinition(
        code="EMBEDDING_MODEL_UNAVAILABLE",
        message="Le modèle d'embedding est indisponible.",
        status_code=503,
        retryable=True
    )


class EmbeddingGenerationError(EmbeddingError):
    """La génération des embeddings échoue."""

    definition = ErrorDefinition(
        code="EMBEDDING_GENERATION_ERROR",
        message="La génération des embeddings a échoué.",
        status_code=500
    )


class EmbeddingDimensionError(EmbeddingError):
    """Dimension inattendue des embeddings."""

    definition = ErrorDefinition(
        code="EMBEDDING_DIMENSION_ERROR",
        message="La dimension des embeddings est invalide.",
        status_code=500
    )


class ContextConstructionError(RetrievalError):
    """Impossible de construire le contexte RAG."""

    definition = ErrorDefinition(
        code="CONTEXT_CONSTRUCTION_ERROR",
        message="Impossible de construire le contexte documentaire.",
        status_code=500
    )
    
# Intelligence artificielle

# Cette famille regroupe les erreurs produites par le moteur
# d'orchestration de l'agent.
#
# Contrairement aux erreurs d'analyse, elles concernent le déroulement
# du workflow lui-même :
#
# - construction du prompt ;
# - exécution des nœuds LangGraph ;
# - génération LLM ;
# - traitement des réponses.
#
# Elles représentent donc les erreurs "fonctionnelles" de l'agent.


class AgentExecutionError(ChessAgentError):
    """Erreur générale d'exécution de l'agent."""

    definition = ErrorDefinition(
        code="AGENT_EXECUTION_ERROR",
        message="L'agent n'a pas pu terminer son exécution.",
        status_code=500
    )


class WorkflowStateError(AgentExecutionError):
    """État du workflow incohérent."""

    definition = ErrorDefinition(
        code="WORKFLOW_STATE_ERROR",
        message="L'état du workflow est incohérent.",
        status_code=500
    )
    
class WorkflowConfigurationError(
    AgentExecutionError
):
    """Configuration du workflow invalide."""

    definition = ErrorDefinition(
        code="WORKFLOW_CONFIGURATION_ERROR",
        message="La configuration du workflow est invalide.",
        status_code=500
    )

class WorkflowRoutingError(
    AgentExecutionError
):
    """Erreur de routage du workflow."""

    definition = ErrorDefinition(
        code="WORKFLOW_ROUTING_ERROR",
        message="Impossible de déterminer la prochaine étape du workflow.",
        status_code=500
    )

class WorkflowExecutionError(AgentExecutionError):
    """Le workflow n'a pas pu terminer son exécution."""

    definition = ErrorDefinition(
        code="WORKFLOW_EXECUTION_ERROR",
        message="Le workflow n'a pas pu terminer son exécution.",
        status_code=500
    )
    
    
class PromptConstructionError(AgentExecutionError):
    """Erreur lors de la construction du prompt."""

    definition = ErrorDefinition(
        code="PROMPT_CONSTRUCTION_ERROR",
        message="Impossible de construire le prompt.",
        status_code=500
    )


class LLMGenerationError(AgentExecutionError):
    """Le modèle de langage n'a pas pu générer de réponse."""

    definition = ErrorDefinition(
        code="LLM_GENERATION_ERROR",
        message="La génération de la réponse a échoué.",
        status_code=500
    )


class InvalidLLMResponseError(AgentExecutionError):
    """Réponse LLM invalide."""

    definition = ErrorDefinition(
        code="INVALID_LLM_RESPONSE",
        message="Le modèle a retourné une réponse invalide.",
        status_code=500
    )

        
class AgentInterruptedError(AgentExecutionError):
    """Le workflow est interrompu."""

    definition = ErrorDefinition(
        code="AGENT_INTERRUPTED",
        message="Le workflow a été interrompu.",
        status_code=409,
        log_level=logging.INFO
    )


class AgentIterationLimitError(AgentExecutionError):
    """Le nombre maximal d'itérations est atteint."""

    definition = ErrorDefinition(
        code="AGENT_ITERATION_LIMIT",
        message="Le nombre maximal d'itérations est atteint.",
        status_code=500
    )


# Configuration

# Cette famille regroupe les erreurs liées à la configuration de
# l'application.
#
# Elles indiquent qu'un composant ne peut pas fonctionner correctement
# en raison d'une configuration absente, invalide ou incohérente.
#
# Elles correspondent généralement à des erreurs de démarrage ou
# d'initialisation plutôt qu'à des erreurs provoquées par une requête
# utilisateur.


class ConfigurationError(ChessAgentError):
    """La configuration de l'application est invalide."""

    definition = ErrorDefinition(
        code="CONFIGURATION_ERROR",
        message="La configuration de l'application est invalide.",
        status_code=500
    )

# Infrastructure

# Cette famille regroupe toutes les erreurs provenant des composants
# techniques de l'application.
#
# Contrairement aux erreurs métier, elles indiquent qu'un service
# externe ou une dépendance n'a pas pu fonctionner correctement.
#
# Elles servent notamment à distinguer :
#
# - une erreur de logique métier ;
# - une indisponibilité d'infrastructure ;
# - un problème réseau ;
# - une panne d'un service externe.
#
# Les handlers FastAPI pourront ainsi renvoyer automatiquement un
# statut HTTP 503 lorsque cela est pertinent.


class InfrastructureError(ChessAgentError):
    """Erreur générale d'infrastructure."""

    definition = ErrorDefinition(
        code="INFRASTRUCTURE_ERROR",
        message="Une erreur d'infrastructure est survenue.",
        status_code=500
    )


class ExternalServiceError(InfrastructureError):
    """Erreur provenant d'un service externe."""

    definition = ErrorDefinition(
        code="EXTERNAL_SERVICE_ERROR",
        message="Le service externe est indisponible.",
        status_code=503,
        retryable=True
    )


class ServiceUnavailableError(InfrastructureError):
    """Service momentanément indisponible."""

    definition = ErrorDefinition(
        code="SERVICE_UNAVAILABLE",
        message="Le service est momentanément indisponible.",
        status_code=503,
        retryable=True
    )

class ApplicationNotReadyError(
    InfrastructureError
):
    """L'application n'est pas prête à recevoir du trafic."""

    definition = ErrorDefinition(
        code="APPLICATION_NOT_READY",
        message="L'application n'est pas prête à recevoir du trafic.",
        status_code=503,
        retryable=True,
        log_level=logging.WARNING
    )

    def __init__(
        self,
        *,
        unavailable_services: list[str]
    ) -> None:
        """Initialise l'erreur de readiness."""

        self.unavailable_services = (
            unavailable_services
        )

        super().__init__(
            details={
                "unavailable_services": (
                    unavailable_services
                )
            }
        )
        
class ServiceTimeoutError(InfrastructureError):
    """Temps d'attente dépassé."""

    definition = ErrorDefinition(
        code="SERVICE_TIMEOUT",
        message="Le délai d'attente du service est dépassé.",
        status_code=504,
        retryable=True
    )

class ResourceInitializationError(
    InfrastructureError
):
    """La ressource n'a pas pu être initialisée."""

    definition = ErrorDefinition(
        code="RESOURCE_INITIALIZATION_ERROR",
        message="La ressource n'a pas pu être initialisée.",
        status_code=503,
        retryable=True
    )

class ResourceHealthError(
    InfrastructureError
):
    """La ressource n'est pas disponible."""

    definition = ErrorDefinition(
        code="RESOURCE_HEALTH_ERROR",
        message="La ressource n'est pas disponible.",
        status_code=503,
        retryable=True
    )

class ResourceShutdownError(
    InfrastructureError
):
    """Impossible d'arrêter correctement la ressource."""

    definition = ErrorDefinition(
        code="RESOURCE_SHUTDOWN_ERROR",
        message="Impossible d'arrêter la ressource.",
        status_code=500
    )

class ResourceRollbackError(
    InfrastructureError
):
    """Le rollback de la ressource a échoué."""

    definition = ErrorDefinition(
        code="RESOURCE_ROLLBACK_ERROR",
        message="Le rollback de la ressource a échoué.",
        status_code=500
    )
    
# Base de données

# Cette famille couvre toutes les erreurs liées aux systèmes de
# persistance.
#
# Les implémentations concrètes (MongoDB aujourd'hui, éventuellement
# PostgreSQL demain) héritent toutes de cette classe afin de conserver
# une hiérarchie homogène.


class DatabaseError(InfrastructureError):
    """Erreur générale de base de données."""

    definition = ErrorDefinition(
        code="DATABASE_ERROR",
        message="Une erreur de base de données est survenue.",
        status_code=500
    )


class DatabaseConnectionError(DatabaseError):
    """Connexion impossible."""

    definition = ErrorDefinition(
        code="DATABASE_CONNECTION_ERROR",
        message="Impossible de se connecter à la base de données.",
        status_code=503,
        retryable=True
    )


class DatabaseOperationError(DatabaseError):
    """Erreur lors d'une requête."""

    definition = ErrorDefinition(
        code="DATABASE_QUERY_ERROR",
        message="La requête vers la base de données a échoué.",
        status_code=500
    )


class MongoDBError(DatabaseError):
    """Erreur MongoDB."""

    definition = ErrorDefinition(
        code="MONGODB_ERROR",
        message="Une erreur MongoDB est survenue.",
        status_code=500
    )


# Base vectorielle

# Milvus constitue la couche de stockage vectoriel utilisée par le
# moteur RAG.
#
# Les erreurs ci-dessous permettent de distinguer une indisponibilité
# du serveur, un problème d'indexation ou une erreur de recherche.

class MilvusError(InfrastructureError):
    """Erreur générale liée à Milvus."""

    definition = ErrorDefinition(
        code="MILVUS_ERROR",
        message="Une erreur Milvus est survenue.",
        status_code=500
    )


class MilvusConnectionError(MilvusError):
    """Connexion Milvus impossible."""

    definition = ErrorDefinition(
        code="MILVUS_CONNECTION_ERROR",
        message="Impossible de se connecter à Milvus.",
        status_code=503,
        retryable=True
    )


class MilvusValidationError(MilvusError):
    """Donnée destinée à Milvus invalide."""

    definition = ErrorDefinition(
        code="MILVUS_VALIDATION_ERROR",
        message="Les données destinées à Milvus sont invalides.",
        status_code=400,
        log_level=logging.WARNING
    )


class MilvusIndexError(MilvusError):
    """Erreur de collection ou d'index vectoriel."""

    definition = ErrorDefinition(
        code="MILVUS_INDEX_ERROR",
        message=(
            "Impossible de préparer ou d'utiliser "
            "l'index vectoriel."
        ),
        status_code=500
    )


class MilvusOperationError(MilvusError):
    """Erreur générale lors d'une opération Milvus."""

    definition = ErrorDefinition(
        code="MILVUS_OPERATION_ERROR",
        message="Une opération Milvus a échoué.",
        status_code=500
    )


class MilvusInsertionError(MilvusOperationError):
    """Erreur d'insertion vectorielle."""

    definition = ErrorDefinition(
        code="MILVUS_INSERTION_ERROR",
        message="L'insertion dans Milvus a échoué.",
        status_code=500
    )


class MilvusSearchError(MilvusOperationError):
    """Erreur de recherche ou de lecture vectorielle."""

    definition = ErrorDefinition(
        code="MILVUS_SEARCH_ERROR",
        message="La recherche vectorielle a échoué.",
        status_code=500
    )


class MilvusDeletionError(MilvusOperationError):
    """Erreur de suppression vectorielle."""

    definition = ErrorDefinition(
        code="MILVUS_DELETION_ERROR",
        message="La suppression dans Milvus a échoué.",
        status_code=500
    )

# Services IA

# Les services suivants sont volontairement séparés afin de permettre
# aux handlers et aux métriques de distinguer précisément la source
# d'une défaillance.

# Lichess
class LichessError(InfrastructureError):
    """Erreur Lichess."""

    definition = ErrorDefinition(
        code="LICHESS_ERROR",
        message="Impossible de communiquer avec Lichess.",
        status_code=503,
        retryable=True
    )

class LichessUnavailableError(LichessError):
    """Le service Lichess est momentanément indisponible."""

    definition = ErrorDefinition(
        code="LICHESS_UNAVAILABLE",
        message="Le service Lichess est momentanément indisponible.",
        status_code=503,
        retryable=True
    )


class LichessTimeoutError(LichessError):
    """Le délai d'attente de Lichess est dépassé."""

    definition = ErrorDefinition(
        code="LICHESS_TIMEOUT",
        message="Le délai d'attente de Lichess est dépassé.",
        status_code=504,
        retryable=True
    )


class LichessResponseError(LichessError):
    """La réponse retournée par Lichess est invalide."""

    definition = ErrorDefinition(
        code="LICHESS_RESPONSE_ERROR",
        message="La réponse retournée par Lichess est invalide.",
        status_code=502
    )

# Youtube

class YoutubeError(InfrastructureError):
    """Erreur YouTube."""

    definition = ErrorDefinition(
        code="YOUTUBE_ERROR",
        message="Impossible de récupérer les vidéos.",
        status_code=503,
        retryable=True
    )

class YoutubeConfigurationError(YoutubeError):
    """Configuration YouTube absente ou invalide."""

    definition = ErrorDefinition(
        code="YOUTUBE_CONFIGURATION_ERROR",
        message="La configuration YouTube est invalide.",
        status_code=503
    )


class YoutubeQuotaError(YoutubeError):
    """Quota de l'API YouTube dépassé."""

    definition = ErrorDefinition(
        code="YOUTUBE_QUOTA_ERROR",
        message="Le quota de l'API YouTube est dépassé.",
        status_code=429,
        retryable=True,
        log_level=logging.WARNING
    )


class YoutubeTimeoutError(YoutubeError):
    """Délai d'attente YouTube dépassé."""

    definition = ErrorDefinition(
        code="YOUTUBE_TIMEOUT_ERROR",
        message="Le délai d'attente de YouTube est dépassé.",
        status_code=504,
        retryable=True
    )


class YoutubeUnavailableError(YoutubeError):
    """API YouTube temporairement indisponible."""

    definition = ErrorDefinition(
        code="YOUTUBE_UNAVAILABLE_ERROR",
        message="Le service YouTube est indisponible.",
        status_code=503,
        retryable=True
    )


class YoutubeResponseError(YoutubeError):
    """Réponse YouTube invalide."""

    definition = ErrorDefinition(
        code="YOUTUBE_RESPONSE_ERROR",
        message="La réponse retournée par YouTube est invalide.",
        status_code=502
    )


# Ollama

class OllamaError(InfrastructureError):
    """Erreur générale liée au serveur Ollama."""

    definition = ErrorDefinition(
        code="OLLAMA_ERROR",
        message="Une erreur Ollama est survenue.",
        status_code=503,
        retryable=True
    )


class OllamaConnectionError(OllamaError):
    """Connexion au serveur Ollama impossible."""

    definition = ErrorDefinition(
        code="OLLAMA_CONNECTION_ERROR",
        message="Impossible de contacter le serveur Ollama.",
        status_code=503,
        retryable=True
    )


class OllamaTimeoutError(OllamaError):
    """Le délai d'attente d'Ollama est dépassé."""

    definition = ErrorDefinition(
        code="OLLAMA_TIMEOUT",
        message="Le délai d'attente d'Ollama est dépassé.",
        status_code=504,
        retryable=True
    )


class OllamaModelUnavailableError(OllamaError):
    """Le modèle Ollama configuré est indisponible."""

    definition = ErrorDefinition(
        code="OLLAMA_MODEL_UNAVAILABLE",
        message="Le modèle Ollama configuré est indisponible.",
        status_code=503,
        retryable=True
    )


class OllamaResponseError(OllamaError):
    """La réponse retournée par Ollama est invalide."""

    definition = ErrorDefinition(
        code="OLLAMA_RESPONSE_ERROR",
        message="La réponse retournée par Ollama est invalide.",
        status_code=502
    )
    
# Stockfish

class StockfishError(InfrastructureError):
    """Erreur générale liée à Stockfish."""

    definition = ErrorDefinition(
        code="STOCKFISH_ERROR",
        message="Une erreur Stockfish est survenue.",
        status_code=503,
        retryable=True
    )


class StockfishConfigurationError(StockfishError):
    """Configuration Stockfish invalide."""

    definition = ErrorDefinition(
        code="STOCKFISH_CONFIGURATION_ERROR",
        message="La configuration de Stockfish est invalide.",
        status_code=500
    )


class StockfishUnavailableError(StockfishError):
    """Le moteur Stockfish est indisponible."""

    definition = ErrorDefinition(
        code="STOCKFISH_UNAVAILABLE",
        message="Le moteur Stockfish est indisponible.",
        status_code=503,
        retryable=True
    )


class StockfishTimeoutError(StockfishError):
    """L'analyse Stockfish a dépassé son délai."""

    definition = ErrorDefinition(
        code="STOCKFISH_TIMEOUT",
        message="L'analyse Stockfish a dépassé le délai autorisé.",
        status_code=504,
        retryable=True
    )


class StockfishAnalysisError(StockfishError):
    """L'analyse Stockfish a échoué."""

    definition = ErrorDefinition(
        code="STOCKFISH_ANALYSIS_ERROR",
        message="L'analyse Stockfish a échoué.",
        status_code=500
    )


class StockfishResponseError(StockfishError):
    """La réponse produite par Stockfish est inexploitable."""

    definition = ErrorDefinition(
        code="STOCKFISH_RESPONSE_ERROR",
        message="La réponse produite par Stockfish est invalide.",
        status_code=502
    )
