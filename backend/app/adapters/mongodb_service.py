"""Persistance MongoDB des analyses du projet Chess Agent.

Ce service centralise :

- la préparation de la collection et de ses index ;
- la création, la lecture et la suppression des analyses ;
- la construction de l'historique récent ;
- la vérification de la disponibilité de MongoDB.

La gestion du client et de la base reste dans ``app.database.mongodb``.
Le module ne dépend ni de FastAPI ni de LangGraph.
"""

from __future__ import annotations

import asyncio
from typing import Literal, TypedDict

from pydantic import ValidationError as PydanticValidationError
from pymongo import ASCENDING, DESCENDING
from pymongo.errors import PyMongoError

from app.core.config import settings
from app.core.constants import (
    ANALYSES_COLLECTION,
    CREATED_AT_FIELD,
    REQUEST_ID_FIELD,
    SAVED_AT_FIELD,
)
from app.core.exceptions import DatabaseConnectionError, DatabaseOperationError
from app.core.logging import get_logger
from app.database.mongodb import MongoCollection, MongoDocument, get_collection
from app.database.mongodb import ping as ping_mongodb
from app.schemas.analysis.analysis import (
    AnalysisRecord,
    AnalysisSaveResult,
    AnalysisSummary,
)

logger = get_logger(__name__)


# Types

type AnalysisCollection = MongoCollection


class ServiceHealth(TypedDict):
    """État de santé public du service MongoDB."""

    service: Literal["mongodb"]
    available: bool
    initialized: bool
    collection: str
    analysis_count: int | None


# Service


class MongoDBService:
    """Service de persistance des analyses dans MongoDB."""

    # Construction

    def __init__(self, collection: MongoCollection | None = None) -> None:
        """Initialise le service avec une collection facultative."""
        # La collection peut être injectée pendant les tests. En production,
        # elle est obtenue à la demande depuis le gestionnaire commun.
        self._collection = collection
        self._initialized = False

        # Le même verrou protège l'initialisation et la fermeture afin que
        # ``close()`` ne puisse pas invalider une préparation en cours.
        self._lifecycle_lock = asyncio.Lock()

    # Cycle de vie

    async def close(self) -> None:
        """Libère les références détenues par le service."""
        async with self._lifecycle_lock:
            self._collection = None
            self._initialized = False

        logger.info("Service MongoDB fermé.")

    # Collection

    def _get_collection(self) -> AnalysisCollection:
        """Retourne la collection des analyses."""
        if self._collection is None:
            self._collection = get_collection(ANALYSES_COLLECTION)

        return self._collection

    # Initialisation

    async def initialize(self) -> None:
        """Prépare les index nécessaires aux analyses."""
        if self._initialized:
            return

        async with self._lifecycle_lock:
            if self._initialized:
                return

            collection = self._get_collection()

            try:
                # Une requête LangGraph ne doit produire qu'un document,
                # même lorsque son nœud de sauvegarde est rejoué.
                await collection.create_index(
                    [(REQUEST_ID_FIELD, ASCENDING)],
                    unique=True,
                    name="analyses_request_id_unique"
                )

                # Cet index accélère l'affichage de l'historique récent.
                await collection.create_index(
                    [(SAVED_AT_FIELD, DESCENDING)],
                    name="analyses_saved_at_desc"
                )
            except PyMongoError as error:
                logger.exception("Impossible de préparer la collection des analyses.")
                raise DatabaseOperationError(
                    message=(
                        "Impossible de préparer la collection MongoDB des analyses."
                    ),
                    cause=error
                ) from error

            self._initialized = True

        logger.info("Collection MongoDB des analyses préparée.")

    # Validation

    def _normalize_identifier(self, value: str, field_name: str) -> str:
        """Retourne un identifiant non vide et normalisé."""
        normalized_value = str(value or "").strip()

        if not normalized_value:
            raise ValueError(f"Le champ '{field_name}' est obligatoire.")

        return normalized_value

    def _normalize_history_limit(self, value: int) -> int:
        """Retourne une limite d'historique valide."""
        if isinstance(value, bool) or not isinstance(value, int):
            raise TypeError("La limite de l'historique doit être un entier.")

        if value < 1:
            raise ValueError("La limite de l'historique doit être positive.")

        return min(value, settings.mongodb_history_max_limit)

    def _normalize_history_offset(self, value: int) -> int:
        """Retourne un décalage d'historique valide."""
        if isinstance(value, bool) or not isinstance(value, int):
            raise TypeError("Le décalage de l'historique doit être un entier.")

        if value < 0:
            raise ValueError("Le décalage de l'historique ne peut pas être négatif.")

        return value

    def _normalize_preview_length(self, value: int) -> int:
        """Retourne une longueur d'extrait strictement positive."""
        if isinstance(value, bool) or not isinstance(value, int):
            raise TypeError("La longueur maximale de l'extrait doit être un entier.")

        if value < 1:
            raise ValueError("La longueur maximale de l'extrait doit être positive.")

        return value

    # Sérialisation

    def _analysis_to_document(self, analysis: AnalysisRecord) -> MongoDocument:
        """Convertit une analyse en document MongoDB."""
        document = analysis.model_dump(mode="python")

        # MongoDB utilise ``_id`` comme identifiant principal tandis que le
        # schéma métier conserve un champ ``id`` indépendant de la base.
        document["_id"] = document.pop("id")
        return document

    def _document_to_analysis(
        self,
        document: MongoDocument
    ) -> AnalysisRecord:
        """Convertit un document MongoDB en analyse validée."""
        payload = dict(document)
        identifier = payload.pop("_id", None)

        if identifier is None:
            raise DatabaseOperationError(
                message=("Le document MongoDB ne contient aucun identifiant d'analyse.")
            )

        payload["id"] = str(identifier)

        try:
            return AnalysisRecord.model_validate(payload)
        except PydanticValidationError as error:
            logger.exception("Le document MongoDB de l'analyse est invalide.")
            raise DatabaseOperationError(
                message=("Le document MongoDB ne respecte pas le schéma d'analyse."),
                cause=error
            ) from error

    # Construction

    def _build_response_preview(
        self,
        response: str | None,
        *,
        max_length: int | None = None
    ) -> str | None:
        """Construit un extrait normalisé de la réponse."""
        if response is None:
            return None

        configured_length = settings.mongodb_response_preview_length
        preview_length = configured_length if max_length is None else max_length
        normalized_length = self._normalize_preview_length(preview_length)
        normalized_response = " ".join(response.split())

        if not normalized_response:
            return None

        if len(normalized_response) <= normalized_length:
            return normalized_response

        return f"{normalized_response[:normalized_length].rstrip()}..."

    def _extract_opening_name(
        self,
        analysis: AnalysisRecord
    ) -> str | None:
        """Retourne le nom normalisé de l'ouverture détectée."""
        if analysis.opening is None:
            return None

        opening_name = analysis.opening.opening.name.strip()
        return opening_name or None

    def _build_summary(self, analysis: AnalysisRecord) -> AnalysisSummary:
        """Construit le résumé d'une analyse."""
        return AnalysisSummary(
            id=analysis.id,
            request_id=analysis.request_id,
            fen=analysis.fen,
            status=analysis.status,
            opening_name=self._extract_opening_name(analysis),
            response_preview=self._build_response_preview(analysis.response),
            warning_count=len(analysis.warnings),
            error_count=len(analysis.errors),
            created_at=analysis.created_at,
            saved_at=analysis.saved_at
        )

    # Sauvegarde

    async def save_analysis(
        self,
        analysis: AnalysisRecord
    ) -> AnalysisSaveResult:
        """Crée ou met à jour une analyse de manière idempotente."""
        await self.initialize()

        analysis_id = self._normalize_identifier(analysis.id, "analysis_id")
        request_id = self._normalize_identifier(
            analysis.request_id,
            REQUEST_ID_FIELD
        )
        normalized_analysis = analysis.model_copy(
            update={"id": analysis_id, "request_id": request_id}
        )
        document = self._analysis_to_document(normalized_analysis)
        mongo_identifier = document.pop("_id")
        created_at = document.pop(CREATED_AT_FIELD)

        try:
            result = await self._get_collection().update_one(
                {REQUEST_ID_FIELD: request_id},
                {
                    "$set": document,
                    "$setOnInsert": {
                        "_id": mongo_identifier,
                        CREATED_AT_FIELD: created_at,
                    },
                },
                upsert=True
            )
        except PyMongoError as error:
            logger.exception(
                "Impossible d'enregistrer l'analyse %s.",
                request_id
            )
            raise DatabaseOperationError(
                message="Impossible d'enregistrer l'analyse dans MongoDB.",
                cause=error
            ) from error

        stored_analysis = await self.get_analysis_by_request_id(request_id)

        if stored_analysis is None:
            raise DatabaseOperationError(
                message=("L'analyse enregistrée ne peut pas être relue depuis MongoDB.")
            )

        created = result.upserted_id is not None
        action = "créée" if created else "mise à jour"
        logger.info("Analyse %s %s dans MongoDB.", stored_analysis.id, action)

        return AnalysisSaveResult(
            analysis_id=stored_analysis.id,
            request_id=stored_analysis.request_id,
            saved_at=stored_analysis.saved_at,
            created=created
        )

    # Lecture

    async def get_analysis(self, analysis_id: str) -> AnalysisRecord | None:
        """Retourne une analyse par son identifiant."""
        await self.initialize()
        normalized_id = self._normalize_identifier(analysis_id, "analysis_id")

        try:
            document = await self._get_collection().find_one({"_id": normalized_id})
        except PyMongoError as error:
            logger.exception(
                "Impossible de récupérer l'analyse %s.",
                normalized_id
            )
            raise DatabaseOperationError(
                message="Impossible de récupérer l'analyse depuis MongoDB.",
                cause=error
            ) from error

        if document is None:
            return None

        return self._document_to_analysis(document)

    async def get_required_analysis(self, analysis_id: str) -> AnalysisRecord:
        """Retourne une analyse ou signale son absence."""
        analysis = await self.get_analysis(analysis_id)

        if analysis is None:
            raise DatabaseOperationError(message="L'analyse demandée est introuvable.")

        return analysis

    async def get_analysis_by_request_id(
        self,
        request_id: str
    ) -> AnalysisRecord | None:
        """Retourne une analyse par son identifiant de requête."""
        await self.initialize()
        normalized_request_id = self._normalize_identifier(
            request_id,
            REQUEST_ID_FIELD
        )

        try:
            document = await self._get_collection().find_one(
                {REQUEST_ID_FIELD: normalized_request_id}
            )
        except PyMongoError as error:
            logger.exception(
                "Impossible de récupérer l'analyse de la requête %s.",
                normalized_request_id
            )
            raise DatabaseOperationError(
                message=("Impossible de récupérer l'analyse associée à la requête."),
                cause=error
            ) from error

        if document is None:
            return None

        return self._document_to_analysis(document)

    async def list_recent_analyses(
        self,
        *,
        limit: int | None = None,
        offset: int = 0
    ) -> list[AnalysisSummary]:
        """Retourne les analyses les plus récentes."""
        await self.initialize()

        configured_limit = settings.mongodb_history_default_limit
        effective_limit = configured_limit if limit is None else limit
        normalized_limit = self._normalize_history_limit(effective_limit)
        normalized_offset = self._normalize_history_offset(offset)
        summaries: list[AnalysisSummary] = []

        try:
            cursor = (
                self._get_collection()
                .find({})
                .sort(SAVED_AT_FIELD, DESCENDING)
                .skip(normalized_offset)
                .limit(normalized_limit)
            )

            async for document in cursor:
                analysis = self._document_to_analysis(document)
                summaries.append(self._build_summary(analysis))
        except DatabaseOperationError:
            raise
        except PyMongoError as error:
            logger.exception("Impossible de récupérer l'historique des analyses.")
            raise DatabaseOperationError(
                message=("Impossible de récupérer l'historique des analyses."),
                cause=error
            ) from error

        return summaries

    # Suppression

    async def delete_analysis(self, analysis_id: str) -> bool:
        """Supprime une analyse par son identifiant."""
        await self.initialize()
        normalized_id = self._normalize_identifier(analysis_id, "analysis_id")

        try:
            result = await self._get_collection().delete_one({"_id": normalized_id})
        except PyMongoError as error:
            logger.exception(
                "Impossible de supprimer l'analyse %s.",
                normalized_id
            )
            raise DatabaseOperationError(
                message="Impossible de supprimer l'analyse dans MongoDB.",
                cause=error
            ) from error

        deleted = result.deleted_count > 0

        if deleted:
            logger.info("Analyse %s supprimée.", normalized_id)

        return deleted

    async def delete_required_analysis(self, analysis_id: str) -> None:
        """Supprime une analyse ou signale son absence."""
        deleted = await self.delete_analysis(analysis_id)

        if not deleted:
            raise DatabaseOperationError(message="L'analyse demandée est introuvable.")

    # Informations

    def is_initialized(self) -> bool:
        """Indique si le service a préparé ses index."""
        return self._initialized

    # Santé

    async def ping(self) -> bool:
        """Vérifie la disponibilité de MongoDB."""
        try:
            return await ping_mongodb()
        except Exception:
            logger.exception("Erreur inattendue lors du test MongoDBService.")
            return False

    async def health(self) -> ServiceHealth:
        """Retourne l'état de santé du service."""
        available = await self.ping()
        analysis_count: int | None = None

        if available:
            try:
                await self.initialize()
                analysis_count = await self._get_collection().count_documents({})
            except (
                DatabaseConnectionError,
                DatabaseOperationError,
                PyMongoError
            ):
                logger.exception("Impossible de compter les analyses MongoDB.")
            except Exception:
                # Un healthcheck ne doit pas faire échouer l'agrégateur de
                # santé lorsqu'un pilote renvoie une erreur non normalisée.
                logger.exception("Erreur inattendue pendant le healthcheck MongoDB.")

        return {
            "service": "mongodb",
            "available": available,
            "initialized": self.is_initialized(),
            "collection": ANALYSES_COLLECTION,
            "analysis_count": analysis_count,
        }