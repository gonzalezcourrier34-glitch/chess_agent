"""Tests unitaires des handlers d'exceptions FastAPI."""

from __future__ import annotations

import json
from types import SimpleNamespace
from unittest.mock import MagicMock

import pytest
from app.api.exception_handlers import (
    INTERNAL_ERROR_CODE,
    INTERNAL_ERROR_MESSAGE,
    VALIDATION_ERROR_CODE,
    VALIDATION_ERROR_MESSAGE,
    _build_validation_details,
    _build_validation_response,
    _get_request_id,
    build_error_response,
    chess_agent_exception_handler,
    register_exception_handlers,
    unexpected_exception_handler,
    validation_exception_handler,
)
from app.core.exceptions import (
    ChessAgentError,
    ErrorContext,
    InvalidRequestError,
)
from fastapi import FastAPI, Request, status
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse

# Helpers


def build_request(
    *,
    request_id: object | None = "request-test-id",
    method: str = "POST",
    path: str = "/api/test",
) -> Request:
    """Construit une requête FastAPI minimale pour les tests."""

    request = MagicMock(
        spec=Request,
    )

    request.state = SimpleNamespace(
        request_id=request_id,
    )

    request.method = method
    request.url.path = path

    return request


def parse_json_response(
    response: JSONResponse,
) -> dict[str, object]:
    """Décode le contenu JSON d'une réponse FastAPI."""

    body = bytes(
        response.body,
    )

    payload = json.loads(
        body.decode("utf-8"),
    )

    assert isinstance(
        payload,
        dict,
    )

    return payload


# Request ID


@pytest.mark.parametrize(
    ("raw_request_id", "expected"),
    [
        ("request-123", "request-123"),
        ("  request-123  ", "request-123"),
        ("", None),
        ("   ", None),
        (None, None),
        (123, None),
    ],
)
def test_get_request_id_normalizes_value(
    raw_request_id: object | None,
    expected: str | None,
) -> None:
    """Vérifie la normalisation de l'identifiant de corrélation."""

    request = build_request(
        request_id=raw_request_id,
    )

    assert (
        _get_request_id(
            request,
        )
        == expected
    )


# Construction de réponse


def test_build_error_response_returns_standard_error_payload() -> None:
    """Vérifie le contrat JSON d'une erreur standard."""

    response = build_error_response(
        status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
        error_code="SERVICE_UNAVAILABLE",
        message="Service indisponible.",
        request_id="request-123",
    )

    payload = parse_json_response(
        response,
    )

    assert response.status_code == status.HTTP_503_SERVICE_UNAVAILABLE

    assert payload == {
        "error": {
            "code": "SERVICE_UNAVAILABLE",
            "message": "Service indisponible.",
            "status_code": status.HTTP_503_SERVICE_UNAVAILABLE,
        },
        "request_id": "request-123",
    }


def test_build_error_response_accepts_missing_request_id() -> None:
    """Vérifie qu'une erreur peut être construite sans request ID."""

    response = build_error_response(
        status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
        error_code="ERROR",
        message="Erreur.",
    )

    payload = parse_json_response(
        response,
    )

    assert payload["request_id"] is None


# Validation


def test_build_validation_details_extracts_safe_information() -> None:
    """Vérifie l'extraction des informations utiles de validation."""

    exception = RequestValidationError(
        [
            {
                "type": "string_too_short",
                "loc": (
                    "body",
                    "fen",
                ),
                "msg": "String should have at least 10 characters",
                "input": "bad",
                "ctx": {
                    "min_length": 10,
                },
            },
        ],
    )

    details = _build_validation_details(
        exception,
    )

    assert len(details) == 1

    issue = details[0]

    assert issue.loc == [
        "body",
        "fen",
    ]
    assert issue.msg == "String should have at least 10 characters"
    assert issue.type == "string_too_short"


def test_build_validation_response_returns_standard_payload() -> None:
    """Vérifie le contrat JSON d'une erreur de validation."""

    exception = RequestValidationError(
        [
            {
                "type": "missing",
                "loc": (
                    "body",
                    "fen",
                ),
                "msg": "Field required",
                "input": {},
            },
        ],
    )

    details = _build_validation_details(
        exception,
    )

    response = _build_validation_response(
        details,
        request_id="request-123",
    )

    payload = parse_json_response(
        response,
    )

    assert response.status_code == status.HTTP_422_UNPROCESSABLE_CONTENT

    assert payload["request_id"] == "request-123"

    error = payload["error"]

    assert isinstance(
        error,
        dict,
    )

    assert error["code"] == VALIDATION_ERROR_CODE
    assert error["message"] == VALIDATION_ERROR_MESSAGE
    assert error["status_code"] == status.HTTP_422_UNPROCESSABLE_CONTENT

    validation_details = error["details"]

    assert isinstance(
        validation_details,
        list,
    )
    assert len(validation_details) == 1


# Exception métier


@pytest.mark.asyncio
async def test_chess_agent_exception_handler_returns_business_error() -> None:
    """Vérifie la traduction d'une exception métier."""

    request = build_request()

    exception = InvalidRequestError(
        context=ErrorContext(
            service="test",
            operation="test",
        ),
        message="Erreur métier.",
    )

    response = await chess_agent_exception_handler(
        request,
        exception,
    )

    payload = parse_json_response(
        response,
    )

    assert response.status_code == exception.status_code

    assert payload == {
        "error": {
            "code": exception.code,
            "message": "Erreur métier.",
            "status_code": exception.status_code,
        },
        "request_id": "request-test-id",
    }


@pytest.mark.asyncio
async def test_chess_agent_exception_handler_rejects_unexpected_exception() -> None:
    """Vérifie qu'une exception non métier n'est pas interceptée."""

    request = build_request()

    exception = RuntimeError(
        "unexpected failure",
    )

    with pytest.raises(
        RuntimeError,
        match="unexpected failure",
    ):
        await chess_agent_exception_handler(
            request,
            exception,
        )


# Validation FastAPI


@pytest.mark.asyncio
async def test_validation_exception_handler_returns_validation_error() -> None:
    """Vérifie la traduction d'une erreur de validation FastAPI."""

    request = build_request()

    exception = RequestValidationError(
        [
            {
                "type": "missing",
                "loc": (
                    "body",
                    "fen",
                ),
                "msg": "Field required",
                "input": {},
            },
        ],
    )

    response = await validation_exception_handler(
        request,
        exception,
    )

    payload = parse_json_response(
        response,
    )

    assert response.status_code == status.HTTP_422_UNPROCESSABLE_CONTENT

    assert payload["request_id"] == "request-test-id"

    error = payload["error"]

    assert isinstance(
        error,
        dict,
    )

    assert error["code"] == VALIDATION_ERROR_CODE
    assert error["message"] == VALIDATION_ERROR_MESSAGE
    assert error["status_code"] == status.HTTP_422_UNPROCESSABLE_CONTENT


@pytest.mark.asyncio
async def test_validation_exception_handler_rejects_unexpected_exception() -> None:
    """Vérifie qu'une exception non liée à la validation est propagée."""

    request = build_request()

    exception = RuntimeError(
        "unexpected validation failure",
    )

    with pytest.raises(
        RuntimeError,
        match="unexpected validation failure",
    ):
        await validation_exception_handler(
            request,
            exception,
        )


# Erreur inattendue


@pytest.mark.asyncio
async def test_unexpected_exception_handler_masks_internal_error() -> None:
    """Vérifie qu'une erreur interne n'est pas exposée au client."""

    request = build_request()

    exception = RuntimeError(
        "sensitive internal failure",
    )

    response = await unexpected_exception_handler(
        request,
        exception,
    )

    payload = parse_json_response(
        response,
    )

    assert response.status_code == status.HTTP_500_INTERNAL_SERVER_ERROR

    assert payload == {
        "error": {
            "code": INTERNAL_ERROR_CODE,
            "message": INTERNAL_ERROR_MESSAGE,
            "status_code": status.HTTP_500_INTERNAL_SERVER_ERROR,
        },
        "request_id": "request-test-id",
    }

    body = bytes(
        response.body,
    ).decode("utf-8")

    assert "sensitive internal failure" not in body


# Enregistrement


def test_register_exception_handlers_registers_expected_handlers() -> None:
    """Vérifie l'enregistrement des handlers sur FastAPI."""

    app = FastAPI()

    register_exception_handlers(
        app,
    )

    assert app.exception_handlers[ChessAgentError] is chess_agent_exception_handler
    assert (
        app.exception_handlers[RequestValidationError] is validation_exception_handler
    )
    assert app.exception_handlers[Exception] is unexpected_exception_handler
