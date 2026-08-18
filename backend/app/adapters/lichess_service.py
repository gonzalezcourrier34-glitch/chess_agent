"""Service d'accès aux bases d'ouvertures de Lichess.

Ce module centralise :

- les appels HTTP vers les bases maîtres et joueurs ;
- les nouvelles tentatives après une erreur temporaire ;
- la validation et la normalisation des réponses JSON ;
- la conversion des données vers les schémas métier du projet ;
- l'exposition de l'état de santé du service.

Il ne produit ni contenu pédagogique ni variante théorique complète, car ces
informations ne sont pas fournies par l'API Explorer de Lichess.
"""

from __future__ import annotations

import asyncio
from typing import TypedDict

import httpx
from pydantic import TypeAdapter, ValidationError

from app.core.config import settings
from app.core.constants import (
    DEFAULT_STARTING_FEN,
    MASTER_DATABASE_ENDPOINT,
    UNKNOWN_OPENING,
    USER_DATABASE_ENDPOINT,
)
from app.core.exceptions import (
    LichessError,
    LichessResponseError,
    LichessTimeoutError,
    OpeningNotFoundError,
)
from app.core.logging import get_logger
from app.schemas.chess.opening import Opening, OpeningDetails, OpeningStatistics
from app.schemas.chess.position import FenRequest

logger = get_logger(__name__)


# Types

type JsonScalar = None | bool | int | float | str
type JsonValue = JsonScalar | list[JsonValue] | dict[str, JsonValue]
type LichessPayload = dict[str, JsonValue]
type LichessParam = str | int
type LichessParams = dict[str, LichessParam]


class LichessServiceStatus(TypedDict):
    """État de santé exposé par le service Lichess."""

    service: str
    is_ready: bool
    is_closed: bool
    available: bool
    base_url: str
    endpoint: str
    timeout_seconds: float
    max_moves: int
    max_retry_attempts: int
    retry_delay_seconds: float
    max_connections: int
    user_agent: str


# Configuration

SERVICE_NAME = "lichess"

# Ces statuts correspondent à des erreurs potentiellement temporaires.
RETRYABLE_STATUS_CODES = frozenset(
    {
        408,
        425,
        429,
        500,
        502,
        503,
        504,
    }
)

LICHESS_PAYLOAD_ADAPTER: TypeAdapter[LichessPayload] = TypeAdapter(
    LichessPayload
)


# Service


class LichessService:
    """Service d'accès à l'API Explorer de Lichess."""

    # Construction

    def __init__(self) -> None:
        """Initialise le client HTTP du service."""
        self._settings = settings
        limits = httpx.Limits(
            max_connections=self._settings.http_max_connections,
            max_keepalive_connections=self._settings.http_max_connections
        )
        headers = {"User-Agent": self._settings.http_user_agent}
        token = self._get_token()

        if token is not None:
            headers["Authorization"] = f"Bearer {token}"

        self._client = httpx.AsyncClient(
            base_url=self._settings.lichess_api_url,
            timeout=self._settings.lichess_timeout_seconds,
            headers=headers,
            limits=limits,
            follow_redirects=True
        )

    def _get_token(self) -> str | None:
        """Retourne le token Lichess configuré."""
        token = self._settings.lichess_token

        if token is None:
            return None

        return token.get_secret_value().strip() or None

    # Cycle de vie

    async def close(self) -> None:
        """Ferme proprement la session HTTP."""
        if self._client.is_closed:
            return

        logger.info("Fermeture du client HTTP Lichess.")

        try:
            await self._client.aclose()
        except Exception:
            # Une erreur de fermeture ne doit pas masquer l'arrêt de
            # l'application.
            logger.exception("Erreur lors de la fermeture du client Lichess.")

    # HTTP

    async def _request(
        self,
        endpoint: str,
        *,
        params: LichessParams | None = None
    ) -> LichessPayload:
        """Exécute une requête et retourne son contenu JSON validé."""
        logger.debug("Interrogation Lichess : %s, paramètres : %s", endpoint, params)
        response = await self._execute_request(endpoint=endpoint, params=params)
        return self._parse_response_payload(response)

    async def _execute_request(
        self,
        endpoint: str,
        *,
        params: LichessParams | None
    ) -> httpx.Response:
        """Exécute une requête HTTP avec nouvelles tentatives."""
        # Une requête initiale est toujours réalisée. La configuration indique
        # uniquement le nombre de nouvelles tentatives autorisées.
        total_attempts = self._settings.http_max_retry_attempts + 1

        for attempt in range(1, total_attempts + 1):
            try:
                response = await self._client.get(endpoint, params=params)

                if self._should_retry_status(
                    status_code=response.status_code,
                    attempt=attempt,
                    total_attempts=total_attempts
                ):
                    await self._wait_before_retry(
                        attempt=attempt,
                        endpoint=endpoint,
                        status_code=response.status_code
                    )
                    continue

                response.raise_for_status()
                logger.debug(
                    "Réponse Lichess reçue : %s.",
                    response.status_code
                )
                return response
            except httpx.TimeoutException as error:
                if attempt < total_attempts:
                    await self._wait_before_retry(
                        attempt=attempt,
                        endpoint=endpoint
                    )
                    continue

                logger.exception("Timeout lors de l'appel à Lichess.")
                raise LichessTimeoutError(
                    message=(
                        "Le service Lichess ne répond pas dans le délai "
                        "configuré."
                    )
                ) from error
            except httpx.HTTPStatusError as error:
                logger.exception(
                    "Erreur HTTP %s retournée par Lichess pour l'endpoint %s.",
                    error.response.status_code,
                    endpoint
                )
                raise LichessError(
                    message="L'API Lichess a retourné une erreur HTTP."
                ) from error
            except httpx.HTTPError as error:
                if attempt < total_attempts:
                    await self._wait_before_retry(
                        attempt=attempt,
                        endpoint=endpoint
                    )
                    continue

                logger.exception("Erreur réseau lors de l'appel à Lichess.")
                raise LichessError(
                    message="Impossible de contacter le service Lichess."
                ) from error

        # Cette protection conserve le contrat de retour si la logique de
        # tentative évolue ultérieurement.
        raise LichessError(
            message="La requête Lichess n'a pas pu être exécutée."
        )

    def _parse_response_payload(
        self,
        response: httpx.Response
    ) -> LichessPayload:
        """Valide et retourne le contenu JSON d'une réponse."""
        if not response.content:
            raise LichessResponseError(
                message="Réponse vide retournée par Lichess."
            )

        try:
            return LICHESS_PAYLOAD_ADAPTER.validate_json(response.content)
        except ValidationError as error:
            logger.warning("Réponse JSON invalide retournée par Lichess.")
            raise LichessResponseError(
                message=(
                    "La réponse retournée par Lichess n'est pas un objet "
                    "JSON valide."
                )
            ) from error

    def _should_retry_status(
        self,
        *,
        status_code: int,
        attempt: int,
        total_attempts: int
    ) -> bool:
        """Indique si le statut autorise une nouvelle tentative."""
        return (
            status_code in RETRYABLE_STATUS_CODES
            and attempt < total_attempts
        )

    async def _wait_before_retry(
        self,
        *,
        attempt: int,
        endpoint: str,
        status_code: int | None = None
    ) -> None:
        """Attend avant une nouvelle tentative HTTP."""
        delay = self._settings.http_retry_delay_seconds * 2 ** (attempt - 1)
        status_message = (
            f" après le statut HTTP {status_code}"
            if status_code is not None
            else ""
        )
        logger.warning(
            "Nouvelle tentative Lichess dans %.2f seconde(s) pour %s "
            "après la tentative %s%s.",
            delay,
            endpoint,
            attempt,
            status_message
        )
        await asyncio.sleep(delay)

    # Ouvertures

    async def detect_opening(self, request: FenRequest) -> OpeningDetails:
        """Retourne les informations disponibles sur une ouverture."""
        logger.debug(
            "Recherche d'une ouverture pour la position : %s",
            request.fen
        )
        payload = await self._get_master_database(fen=request.fen)

        if not self._has_opening(payload):
            raise OpeningNotFoundError(
                message="Aucune ouverture n'a été retournée par Lichess."
            )

        opening_details = self._build_opening_details(
            payload,
            fen=request.fen
        )
        logger.debug(
            "Ouverture Lichess détectée : %s.",
            opening_details.opening.name
        )
        return opening_details

    async def _get_master_database(self, *, fen: str) -> LichessPayload:
        """Interroge la base des parties de maîtres."""
        return await self._request(
            MASTER_DATABASE_ENDPOINT,
            params={
                "fen": fen,
                "moves": self._settings.lichess_max_moves,
            }
        )

    async def _get_user_database(
        self,
        *,
        fen: str,
        speeds: str | None = None,
        ratings: str | None = None
    ) -> LichessPayload:
        """Interroge la base des parties des joueurs."""
        params: LichessParams = {
            "fen": fen,
            "moves": self._settings.lichess_max_moves,
        }

        if speeds is not None:
            params["speeds"] = speeds

        if ratings is not None:
            params["ratings"] = ratings

        return await self._request(USER_DATABASE_ENDPOINT, params=params)

    # Construction

    def _build_opening_details(
        self,
        payload: LichessPayload,
        *,
        fen: str
    ) -> OpeningDetails:
        """Construit les informations complètes d'une ouverture."""
        # Explorer ne fournit ni théorie pédagogique structurée ni variante
        # complète ; les valeurs par défaut du schéma expriment cette absence.
        return OpeningDetails(
            opening=self._build_opening(payload, fen=fen),
            statistics=self._build_statistics(payload)
        )

    def _build_opening(
        self,
        payload: LichessPayload,
        *,
        fen: str
    ) -> Opening:
        """Construit l'identité de l'ouverture détectée."""
        opening_payload = self._get_object(payload, "opening")

        return Opening(
            eco=self._get_string(opening_payload, "eco"),
            name=self._get_string(
                opening_payload,
                "name",
                UNKNOWN_OPENING
            ),
            moves=[],
            final_fen=fen,
            description=None
        )

    def _build_statistics(
        self,
        payload: LichessPayload
    ) -> OpeningStatistics:
        """Construit les statistiques globales de la position."""
        white_wins = self._get_integer(payload, "white")
        black_wins = self._get_integer(payload, "black")
        draws = self._get_integer(payload, "draws")
        games = white_wins + black_wins + draws

        if games == 0:
            return OpeningStatistics()

        return OpeningStatistics(
            games=games,
            white_win_rate=white_wins * 100 / games,
            black_win_rate=black_wins * 100 / games,
            draw_rate=draws * 100 / games
        )

    # Validation

    def _has_opening(self, payload: LichessPayload) -> bool:
        """Indique si une ouverture est présente."""
        opening = self._get_object(payload, "opening")
        return bool(
            self._get_string(opening, "name")
            or self._get_string(opening, "eco")
        )

    # Conversion

    def _get_object(
        self,
        payload: LichessPayload,
        key: str
    ) -> LichessPayload:
        """Retourne un objet JSON imbriqué ou un objet vide."""
        value = payload.get(key)

        if not isinstance(value, dict):
            return {}

        return value

    def _get_string(
        self,
        payload: LichessPayload,
        key: str,
        default: str = ""
    ) -> str:
        """Retourne une chaîne normalisée."""
        value = payload.get(key)

        if not isinstance(value, str):
            return default

        return value.strip() or default

    def _get_integer(
        self,
        payload: LichessPayload,
        key: str
    ) -> int:
        """Retourne un entier positif ou nul."""
        return self._parse_integer(payload.get(key)) or 0

    def _parse_integer(self, value: JsonValue | None) -> int | None:
        """Convertit une valeur JSON en entier positif ou nul."""
        # ``bool`` hérite de ``int``, mais ne représente pas ici une valeur
        # statistique valide.
        if value is None or isinstance(value, bool):
            return None

        if isinstance(value, int):
            parsed_value = value
        elif isinstance(value, float):
            if not value.is_integer():
                return None
            parsed_value = int(value)
        elif isinstance(value, str):
            try:
                parsed_value = int(value.strip())
            except ValueError:
                return None
        else:
            return None

        return parsed_value if parsed_value >= 0 else None

    # Informations

    def is_closed(self) -> bool:
        """Indique si le client HTTP est fermé."""
        return self._client.is_closed

    def is_ready(self) -> bool:
        """Indique si le client HTTP peut être utilisé."""
        return not self._client.is_closed

    # Santé

    async def ping(self) -> bool:
        """Vérifie que l'API Lichess est disponible."""
        if self._client.is_closed:
            logger.error("Le client HTTP Lichess est fermé.")
            return False

        try:
            await self._get_master_database(fen=DEFAULT_STARTING_FEN)
        except LichessError:
            logger.exception("Le service Lichess est indisponible.")
            return False
        except Exception:
            logger.exception("Erreur inattendue lors du test Lichess.")
            return False

        return True

    async def health(self) -> LichessServiceStatus:
        """Retourne l'état de santé détaillé du service."""
        available = await self.ping()

        return {
            "service": SERVICE_NAME,
            "is_ready": self.is_ready(),
            "is_closed": self.is_closed(),
            "available": available,
            "base_url": str(self._client.base_url),
            "endpoint": MASTER_DATABASE_ENDPOINT,
            "timeout_seconds": self._settings.lichess_timeout_seconds,
            "max_moves": self._settings.lichess_max_moves,
            "max_retry_attempts": self._settings.http_max_retry_attempts,
            "retry_delay_seconds": self._settings.http_retry_delay_seconds,
            "max_connections": self._settings.http_max_connections,
            "user_agent": self._settings.http_user_agent,
        }