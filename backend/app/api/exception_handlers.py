"""Handlers d'exceptions FastAPI du projet Chess Agent.

Ce module centralise :

- la traduction des exceptions métiers en réponses HTTP ;
- le traitement homogène des erreurs de validation ;
- le traitement des erreurs inattendues ;
- l'enregistrement des handlers sur l'application.

Il ne définit aucune exception métier."""


from __future__ import annotations

from fastapi import FastAPI, Request, status
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse

from app.core.exceptions import ChessAgentError
from app.core.logging import get_logger
from app.schemas.common.error import (
    ApiError,
    ApiValidationError,
    ErrorResponse,
    ValidationErrorResponse,
    ValidationIssue,
)

logger = get_logger(__name__)


# Constantes


VALIDATION_ERROR_CODE = "VALIDATION_ERROR"

VALIDATION_ERROR_MESSAGE = (
    "Les données de la requête sont invalides."
)

INTERNAL_ERROR_CODE = "INTERNAL_SERVER_ERROR"

INTERNAL_ERROR_MESSAGE = (
    "Une erreur interne est survenue."
)


# Construction


def _get_request_id(
    request: Request
) -> str | None:
    """Récupère l'identifiant de corrélation de la requête."""

    request_id = getattr(
        request.state,
        "request_id",
        None
    )

    if not isinstance(
        request_id,
        str
    ):
        return None

    normalized_request_id = request_id.strip()

    return normalized_request_id or None


def build_error_response(
    *,
    status_code: int,
    error_code: str,
    message: str,
    request_id: str | None = None
) -> JSONResponse:
    """Construit une réponse d'erreur homogène."""

    response = ErrorResponse(
        error=ApiError(
            code=error_code,
            message=message,
            status_code=status_code
        ),
        request_id=request_id
    )

    return JSONResponse(
        status_code=status_code,
        content=response.model_dump(
            mode="json"
        )
    )


def _build_validation_details(
    exception: RequestValidationError
) -> list[ValidationIssue]:
    """Extrait les détails utiles sans exposer les entrées rejetées."""

    details: list[ValidationIssue] = []

    for error in exception.errors():
        details.append(
            ValidationIssue(
                loc=list(
                    error["loc"]
                ),
                msg=error["msg"],
                type=error["type"]
            )
        )

    return details


def _build_validation_response(
    details: list[ValidationIssue],
    request_id: str | None = None
) -> JSONResponse:
    """Construit une réponse pour une requête invalide."""

    status_code = (
        status.HTTP_422_UNPROCESSABLE_ENTITY
    )

    response = ValidationErrorResponse(
        error=ApiValidationError(
            code=VALIDATION_ERROR_CODE,
            message=VALIDATION_ERROR_MESSAGE,
            status_code=status_code,
            details=details
        ),
        request_id=request_id
    )

    return JSONResponse(
        status_code=status_code,
        content=response.model_dump(
            mode="json"
        )
    )


# Exceptions métiers


async def chess_agent_exception_handler(
    request: Request,
    exception: Exception
) -> JSONResponse:
    """Traduit une exception métier en réponse HTTP."""

    if not isinstance(
        exception,
        ChessAgentError
    ):
        raise exception

    request_id = _get_request_id(
        request
    )

    logger.warning(
        "%s %s | Erreur métier %s | request_id=%s.",
        request.method,
        request.url.path,
        exception.code,
        request_id
    )

    return build_error_response(
        status_code=exception.status_code,
        error_code=exception.code,
        message=exception.message,
        request_id=request_id
    )


# Validation


async def validation_exception_handler(
    request: Request,
    exception: Exception
) -> JSONResponse:
    """Traduit une erreur de validation FastAPI en réponse HTTP."""

    if not isinstance(
        exception,
        RequestValidationError
    ):
        raise exception

    request_id = _get_request_id(
        request
    )

    details = _build_validation_details(
        exception
    )

    logger.warning(
        "%s %s | Requête invalide (%d erreur(s)) | request_id=%s.",
        request.method,
        request.url.path,
        len(details),
        request_id
    )

    return _build_validation_response(
        details,
        request_id=request_id
    )


# Erreurs inattendues


async def unexpected_exception_handler(
    request: Request,
    exception: Exception
) -> JSONResponse:
    """Masque une erreur inattendue et conserve sa trace en interne."""

    request_id = _get_request_id(
        request
    )

    logger.error(
        "%s %s | Erreur inattendue : %s | request_id=%s.",
        request.method,
        request.url.path,
        type(exception).__name__,
        request_id,
        exc_info=(
            type(exception),
            exception,
            exception.__traceback__
        )
    )

    return build_error_response(
        status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
        error_code=INTERNAL_ERROR_CODE,
        message=INTERNAL_ERROR_MESSAGE,
        request_id=request_id
    )


# Configuration


def register_exception_handlers(
    app: FastAPI
) -> None:
    """Enregistre les handlers d'exceptions sur l'application."""

    app.add_exception_handler(
        ChessAgentError,
        chess_agent_exception_handler
    )

    app.add_exception_handler(
        RequestValidationError,
        validation_exception_handler
    )

    app.add_exception_handler(
        Exception,
        unexpected_exception_handler
    )