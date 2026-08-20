"""Réponses OpenAPI communes de l'API Chess Agent.

Ce module centralise les descriptions de réponses d'erreur utilisées
par les routes FastAPI.

Il ne contient aucune logique métier et ne définit aucune exception.
Les exceptions restent centralisées dans ``app.core.exceptions`` et
les schémas JSON dans ``app.schemas.common.error``.
"""

from __future__ import annotations

from typing import Any

from app.schemas.common.error import (
    ErrorResponse,
    ValidationErrorResponse,
)

# Types


OpenApiResponse = dict[str, Any]

OpenApiResponses = dict[int | str, OpenApiResponse]


# Réponses


BAD_REQUEST_ERROR_RESPONSE: OpenApiResponse = {
    "model": ErrorResponse,
    "description": "La requête est invalide.",
}


VALIDATION_ERROR_RESPONSE: OpenApiResponse = {
    "model": ValidationErrorResponse,
    "description": "Les données de la requête sont invalides.",
}


NOT_FOUND_ERROR_RESPONSE: OpenApiResponse = {
    "model": ErrorResponse,
    "description": "La ressource demandée est introuvable.",
}


CONFLICT_ERROR_RESPONSE: OpenApiResponse = {
    "model": ErrorResponse,
    "description": "La requête entre en conflit avec l'état courant.",
}


TOO_MANY_REQUESTS_ERROR_RESPONSE: OpenApiResponse = {
    "model": ErrorResponse,
    "description": "La limite de requêtes a été atteinte.",
}


INTERNAL_ERROR_RESPONSE: OpenApiResponse = {
    "model": ErrorResponse,
    "description": "Une erreur interne est survenue.",
}


BAD_GATEWAY_ERROR_RESPONSE: OpenApiResponse = {
    "model": ErrorResponse,
    "description": "Un service externe a retourné une réponse invalide.",
}


SERVICE_UNAVAILABLE_ERROR_RESPONSE: OpenApiResponse = {
    "model": ErrorResponse,
    "description": "Un service requis est momentanément indisponible.",
}


GATEWAY_TIMEOUT_ERROR_RESPONSE: OpenApiResponse = {
    "model": ErrorResponse,
    "description": "Le délai d'attente d'un service externe a été dépassé.",
}


# Groupes génériques


SERVER_ERROR_RESPONSES: OpenApiResponses = {
    500: INTERNAL_ERROR_RESPONSE,
}


COMMON_ERROR_RESPONSES: OpenApiResponses = {
    422: VALIDATION_ERROR_RESPONSE,
    **SERVER_ERROR_RESPONSES,
}


RESOURCE_ERROR_RESPONSES: OpenApiResponses = {
    **COMMON_ERROR_RESPONSES,
    404: NOT_FOUND_ERROR_RESPONSE,
    409: CONFLICT_ERROR_RESPONSE,
}


# Échecs


CHESS_ERROR_RESPONSES: OpenApiResponses = {
    400: BAD_REQUEST_ERROR_RESPONSE,
    422: VALIDATION_ERROR_RESPONSE,
    500: INTERNAL_ERROR_RESPONSE,
}


# Stockage


DATABASE_ERROR_RESPONSES: OpenApiResponses = {
    422: VALIDATION_ERROR_RESPONSE,
    500: INTERNAL_ERROR_RESPONSE,
    503: SERVICE_UNAVAILABLE_ERROR_RESPONSE,
}


DATABASE_RESOURCE_ERROR_RESPONSES: OpenApiResponses = {
    **DATABASE_ERROR_RESPONSES,
    404: NOT_FOUND_ERROR_RESPONSE,
}


# Lichess


LICHESS_ERROR_RESPONSES: OpenApiResponses = {
    404: NOT_FOUND_ERROR_RESPONSE,
    422: VALIDATION_ERROR_RESPONSE,
    500: INTERNAL_ERROR_RESPONSE,
    502: BAD_GATEWAY_ERROR_RESPONSE,
    503: SERVICE_UNAVAILABLE_ERROR_RESPONSE,
    504: GATEWAY_TIMEOUT_ERROR_RESPONSE,
}


# Recherche vectorielle


VECTOR_SEARCH_ERROR_RESPONSES: OpenApiResponses = {
    422: VALIDATION_ERROR_RESPONSE,
    500: INTERNAL_ERROR_RESPONSE,
    503: SERVICE_UNAVAILABLE_ERROR_RESPONSE,
    504: GATEWAY_TIMEOUT_ERROR_RESPONSE,
}


# YouTube


YOUTUBE_ERROR_RESPONSES: OpenApiResponses = {
    422: VALIDATION_ERROR_RESPONSE,
    429: TOO_MANY_REQUESTS_ERROR_RESPONSE,
    500: INTERNAL_ERROR_RESPONSE,
    502: BAD_GATEWAY_ERROR_RESPONSE,
    503: SERVICE_UNAVAILABLE_ERROR_RESPONSE,
    504: GATEWAY_TIMEOUT_ERROR_RESPONSE,
}


# Stockfish


STOCKFISH_ERROR_RESPONSES: OpenApiResponses = {
    422: VALIDATION_ERROR_RESPONSE,
    500: INTERNAL_ERROR_RESPONSE,
    502: BAD_GATEWAY_ERROR_RESPONSE,
    503: SERVICE_UNAVAILABLE_ERROR_RESPONSE,
    504: GATEWAY_TIMEOUT_ERROR_RESPONSE,
}
