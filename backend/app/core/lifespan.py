"""Gestion du cycle de vie de Chess Agent.

Ce module centralise :

- l'initialisation ordonnée des ressources techniques ;
- le contrôle de leur disponibilité ;
- le rollback en cas d'échec ;
- leur fermeture dans l'ordre inverse ;
- l'exposition du conteneur applicatif à FastAPI.

Il ne contient aucune logique métier.
"""

from __future__ import annotations

from asyncio import CancelledError, Lock, gather
from collections.abc import AsyncIterator, Awaitable, Callable
from contextlib import asynccontextmanager
from dataclasses import dataclass
from time import perf_counter

from fastapi import FastAPI

from app.core.container import ApplicationContainer, create_application_container
from app.core.exceptions import (
    ResourceHealthError,
    ResourceInitializationError,
    ResourceShutdownError,
)
from app.core.logging import get_logger

logger = get_logger(__name__)


# Types

InitializeFunction = Callable[[ApplicationContainer], Awaitable[None]]
ShutdownFunction = Callable[[ApplicationContainer], Awaitable[None]]
HealthFunction = Callable[[ApplicationContainer], Awaitable[bool]]
ResourceHealthStatus = dict[str, bool]


# Ressources


@dataclass(slots=True)
class ManagedResource:
    """Décrit une ressource gérée par le lifespan."""

    name: str
    initialize: InitializeFunction
    shutdown: ShutdownFunction
    health: HealthFunction

    # Une ressource obligatoire bloque le démarrage lorsqu'elle est
    # indisponible. Une ressource facultative autorise un mode dégradé.
    required: bool = True
    initialized: bool = False


# Gestionnaire


class ResourceManager:
    """Gère le cycle de vie des ressources techniques."""

    # Construction

    def __init__(self, container: ApplicationContainer) -> None:
        """Initialise le gestionnaire."""
        self.container = container
        self._resources: list[ManagedResource] = []
        self._lifecycle_lock = Lock()

    # Informations

    @property
    def resources(self) -> tuple[ManagedResource, ...]:
        """Retourne les ressources enregistrées."""
        return tuple(self._resources)

    # Enregistrement

    def register(self, resource: ManagedResource) -> None:
        """Enregistre une ressource dont le nom est unique."""
        if any(current.name == resource.name for current in self._resources):
            raise ValueError(f"La ressource {resource.name!r} est déjà enregistrée.")

        self._resources.append(resource)

    # Initialisation

    async def initialize_resource(self, resource: ManagedResource) -> None:
        """Initialise et contrôle une ressource."""
        async with self._lifecycle_lock:
            await self._initialize_resource(resource)

    async def _initialize_resource(self, resource: ManagedResource) -> None:
        """Initialise une ressource dans la section critique courante."""
        if resource.initialized:
            logger.debug("La ressource %s est déjà initialisée.", resource.name)
            return

        logger.info("Initialisation de %s...", resource.name)
        started_at = perf_counter()

        try:
            await resource.initialize(self.container)
        except CancelledError:
            await self._cleanup_failed_initialization(resource)
            raise
        except Exception as error:
            await self._cleanup_failed_initialization(resource)
            self._handle_initialization_error(resource, error)
            return

        # La ressource doit participer au rollback si son contrôle de santé
        # échoue après une initialisation technique réussie.
        resource.initialized = True
        available = await self._check_initialized_resource(resource)

        if not available and resource.required:
            await self._shutdown_resource(resource, rollback=True)
            raise ResourceHealthError(message=f"{resource.name} est indisponible.")

        if not available:
            logger.warning(
                "%s est indisponible. L'application poursuit son démarrage "
                "en mode dégradé.",
                resource.name,
            )

        logger.info(
            "%s initialisé en %.3f s.", resource.name, perf_counter() - started_at
        )

    def _handle_initialization_error(
        self, resource: ManagedResource, error: Exception
    ) -> None:
        """Traite un échec d'initialisation selon le niveau d'exigence."""
        failure = ResourceInitializationError(
            message=f"Impossible d'initialiser {resource.name}.", cause=error
        )

        if resource.required:
            raise failure from error

        logger.warning(
            "Initialisation facultative de %s impossible : %s", resource.name, error
        )

    async def _check_initialized_resource(self, resource: ManagedResource) -> bool:
        """Contrôle une ressource initialisée avant sa publication."""
        try:
            return await resource.health(self.container)
        except CancelledError:
            await self._shutdown_resource(resource, rollback=True)
            raise
        except Exception as error:
            if not resource.required:
                logger.warning(
                    "Le contrôle de la ressource facultative %s a échoué : %s",
                    resource.name,
                    error,
                )
                return False

            await self._shutdown_resource(resource, rollback=True)
            raise ResourceHealthError(
                message=f"Impossible de contrôler {resource.name}.", cause=error
            ) from error

    async def _cleanup_failed_initialization(self, resource: ManagedResource) -> None:
        """Nettoie une ressource dont l'initialisation a été interrompue."""
        try:
            await resource.shutdown(self.container)
        except Exception as error:
            ResourceShutdownError(
                message=(
                    f"Impossible de nettoyer {resource.name} après un échec "
                    "d'initialisation."
                ),
                cause=error,
            ).log()
        finally:
            resource.initialized = False

    async def initialize_all(self) -> None:
        """Initialise toutes les ressources enregistrées."""
        async with self._lifecycle_lock:
            try:
                for resource in self._resources:
                    await self._initialize_resource(resource)
            except CancelledError:
                await self._rollback()
                raise
            except Exception:
                await self._rollback()
                raise

    # Rollback

    async def rollback(self) -> None:
        """Libère les ressources déjà initialisées."""
        async with self._lifecycle_lock:
            await self._rollback()

    async def _rollback(self) -> None:
        """Exécute le rollback dans la section critique courante."""
        for resource in reversed(self._resources):
            await self._shutdown_resource(resource, rollback=True)

    # Fermeture

    async def shutdown_all(self) -> None:
        """Ferme toutes les ressources initialisées."""
        async with self._lifecycle_lock:
            for resource in reversed(self._resources):
                await self._shutdown_resource(resource, rollback=False)

    async def _shutdown_resource(
        self, resource: ManagedResource, *, rollback: bool
    ) -> None:
        """Ferme une ressource initialisée sans masquer les autres arrêts."""
        if not resource.initialized:
            return

        started_at = perf_counter()

        if rollback:
            logger.warning("Rollback de %s.", resource.name)
        else:
            logger.info("Arrêt de %s...", resource.name)

        try:
            await resource.shutdown(self.container)
        except Exception as error:
            if rollback:
                message = f"Impossible d'arrêter {resource.name} pendant le rollback."
            else:
                message = f"Impossible d'arrêter {resource.name}."

            ResourceShutdownError(message=message, cause=error).log()
            return
        finally:
            # Le gestionnaire est terminal après une tentative de fermeture.
            # Une méthode shutdown doit elle-même garantir son idempotence.
            resource.initialized = False

        if not rollback:
            logger.info(
                "%s arrêté en %.3f s.", resource.name, perf_counter() - started_at
            )

    # Santé

    async def health(self) -> ResourceHealthStatus:
        """Retourne l'état de santé des ressources initialisées."""
        async with self._lifecycle_lock:
            statuses = await gather(
                *(self._get_resource_status(resource) for resource in self._resources)
            )

        return dict(statuses)

    async def _get_resource_status(self, resource: ManagedResource) -> tuple[str, bool]:
        """Retourne le statut isolé d'une ressource."""
        if not resource.initialized:
            return resource.name, False

        try:
            return resource.name, await resource.health(self.container)
        except Exception:
            logger.exception("Échec du contrôle de %s.", resource.name)
            return resource.name, False


# Fonctions neutres


async def no_initialize(container: ApplicationContainer) -> None:
    """Ne réalise aucune opération d'initialisation."""
    del container


async def no_shutdown(container: ApplicationContainer) -> None:
    """Ne réalise aucune opération de fermeture."""
    del container


# MongoDB


async def initialize_mongodb(container: ApplicationContainer) -> None:
    """Initialise le service MongoDB."""
    await container.mongodb.initialize()


async def shutdown_mongodb(container: ApplicationContainer) -> None:
    """Ferme le service MongoDB."""
    await container.mongodb.close()


async def mongodb_health(container: ApplicationContainer) -> bool:
    """Indique si MongoDB est disponible."""
    return await container.mongodb.ping()


# Embeddings


async def initialize_embedding(container: ApplicationContainer) -> None:
    """Initialise le modèle d'embedding."""
    await container.embedding.initialize()


async def shutdown_embedding(container: ApplicationContainer) -> None:
    """Libère le modèle d'embedding."""
    await container.embedding.close()


async def embedding_health(container: ApplicationContainer) -> bool:
    """Indique si le service d'embedding est disponible."""
    return await container.embedding.ping()


# Milvus


async def initialize_milvus(container: ApplicationContainer) -> None:
    """Initialise la connexion à Milvus."""
    await container.milvus.initialize()


async def shutdown_milvus(container: ApplicationContainer) -> None:
    """Ferme la connexion à Milvus."""
    await container.milvus.close()


async def milvus_health(container: ApplicationContainer) -> bool:
    """Indique si Milvus est disponible."""
    return await container.milvus.ping()


# Stockfish


async def initialize_stockfish(container: ApplicationContainer) -> None:
    """Démarre le moteur Stockfish."""
    await container.stockfish.start()


async def shutdown_stockfish(container: ApplicationContainer) -> None:
    """Arrête le moteur Stockfish."""
    await container.stockfish.close()


async def stockfish_health(container: ApplicationContainer) -> bool:
    """Indique si Stockfish est disponible."""
    return await container.stockfish.ping()


# Lichess


async def shutdown_lichess(container: ApplicationContainer) -> None:
    """Ferme le client HTTP Lichess."""
    await container.lichess.close()


async def lichess_health(container: ApplicationContainer) -> bool:
    """Indique si le service Lichess est disponible."""
    return await container.lichess.ping()


# YouTube


async def shutdown_youtube(container: ApplicationContainer) -> None:
    """Ferme le client HTTP YouTube."""
    await container.youtube.close()


async def youtube_health(container: ApplicationContainer) -> bool:
    """Indique si le service YouTube est disponible."""
    return await container.youtube.ping()


# LLM


async def initialize_llm(container: ApplicationContainer) -> None:
    """Initialise le service de génération."""
    await container.llm.initialize()


async def shutdown_llm(container: ApplicationContainer) -> None:
    """Ferme le service de génération."""
    await container.llm.close()


async def llm_health(container: ApplicationContainer) -> bool:
    """Indique si le modèle de langage est disponible."""
    return await container.llm.ping()


# Orchestration


async def initialize_workflow(container: ApplicationContainer) -> None:
    """Construit le workflow et les services d'orchestration."""
    container.build_graph()


async def shutdown_workflow(container: ApplicationContainer) -> None:
    """Libère le workflow et les services d'orchestration."""
    container.destroy_graph()


async def workflow_health(container: ApplicationContainer) -> bool:
    """Indique si le workflow est disponible."""
    return container.is_ready()


# Construction


def create_resource_manager(container: ApplicationContainer) -> ResourceManager:
    """Construit le gestionnaire des ressources."""
    manager = ResourceManager(container)

    # L'ordre d'enregistrement détermine l'ordre d'initialisation. La
    # fermeture est automatiquement exécutée dans l'ordre inverse.
    resources = (
        ManagedResource(
            name="MongoDB",
            initialize=initialize_mongodb,
            shutdown=shutdown_mongodb,
            health=mongodb_health,
        ),
        ManagedResource(
            name="Embedding",
            initialize=initialize_embedding,
            shutdown=shutdown_embedding,
            health=embedding_health,
        ),
        ManagedResource(
            name="Milvus",
            initialize=initialize_milvus,
            shutdown=shutdown_milvus,
            health=milvus_health,
        ),
        ManagedResource(
            name="Stockfish",
            initialize=initialize_stockfish,
            shutdown=shutdown_stockfish,
            health=stockfish_health,
        ),
        # Le nœud de génération possède une réponse de secours lorsque le
        # modèle est indisponible.
        ManagedResource(
            name="LLM",
            initialize=initialize_llm,
            shutdown=shutdown_llm,
            health=llm_health,
        ),
        # Les clients HTTP sont créés par le conteneur. Leur initialisation
        # est neutre, mais ils doivent être contrôlés puis fermés.
        ManagedResource(
            name="Lichess",
            initialize=no_initialize,
            shutdown=shutdown_lichess,
            health=lichess_health,
            required=False,
        ),
        ManagedResource(
            name="YouTube",
            initialize=no_initialize,
            shutdown=shutdown_youtube,
            health=youtube_health,
            required=False,
        ),
        # Le workflow est publié après toutes les dépendances techniques.
        ManagedResource(
            name="Workflow",
            initialize=initialize_workflow,
            shutdown=shutdown_workflow,
            health=workflow_health,
        ),
    )

    for resource in resources:
        manager.register(resource)

    return manager


# Lifespan


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncIterator[None]:
    """Gère le cycle de vie de Chess Agent."""
    logger.info("Démarrage de Chess Agent...")
    started_at = perf_counter()

    container = create_application_container()
    resource_manager = create_resource_manager(container)
    container.resource_manager = resource_manager

    try:
        # Les routes ne reçoivent le conteneur qu'une fois toutes les
        # ressources obligatoires disponibles.
        await resource_manager.initialize_all()
        app.state.container = container

        logger.info("Chess Agent prêt en %.3f s.", perf_counter() - started_at)

        yield
    except Exception:
        logger.exception("Échec de l'exécution de Chess Agent.")
        raise
    finally:
        logger.info("Arrêt de Chess Agent...")
        shutdown_started_at = perf_counter()

        # Le conteneur ne doit plus être visible pendant la fermeture de ses
        # dépendances.
        if getattr(app.state, "container", None) is container:
            del app.state.container

        try:
            await resource_manager.shutdown_all()
        finally:
            container.resource_manager = None

        logger.info(
            "Chess Agent arrêté en %.3f s.", perf_counter() - shutdown_started_at
        )
