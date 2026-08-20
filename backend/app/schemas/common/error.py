"""Schémas représentant les erreurs du projet Chess Agent.

Ce module centralise les modèles d'erreur utilisés par :

- les services métier ;
- le workflow LangGraph ;
- les gestionnaires d'exceptions ;
- les réponses de l'API.

Ces modèles décrivent des données d'erreur sérialisables.

Ils restent indépendants des exceptions Python et Pydantic."""

from __future__ import annotations

from app.schemas.common.enums import WorkflowStep
from pydantic import BaseModel, ConfigDict, Field

# Erreur API


class ApiError(BaseModel):
    """Erreur métier exposée par l'API."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    code: str = Field(..., min_length=1, description="Code métier unique de l'erreur.")

    message: str = Field(
        ..., min_length=1, description="Description lisible de l'erreur."
    )

    status_code: int = Field(
        ..., ge=100, le=599, description="Code HTTP associé à l'erreur."
    )


# Validation


class ValidationIssue(BaseModel):
    """Erreur élémentaire de validation d'une requête."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    loc: list[str | int] = Field(
        default_factory=list, description="Emplacement du champ invalide."
    )

    msg: str = Field(
        ..., min_length=1, description="Description du problème de validation."
    )

    type: str = Field(..., min_length=1, description="Type d'erreur de validation.")


class ApiValidationError(ApiError):
    """Erreur de validation exposée par l'API."""

    details: list[ValidationIssue] = Field(
        default_factory=list, description="Problèmes détectés pendant la validation."
    )


# Workflow


class WorkflowWarning(BaseModel):
    """Avertissement produit par le workflow."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    step: WorkflowStep = Field(..., description="Étape ayant produit l'avertissement.")

    message: str = Field(
        ..., min_length=1, description="Description de l'avertissement."
    )

    code: str | None = Field(
        default=None, description="Code métier facultatif de l'avertissement."
    )


class WorkflowError(BaseModel):
    """Erreur produite par le workflow."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    step: WorkflowStep = Field(..., description="Étape ayant produit l'erreur.")

    code: str = Field(..., min_length=1, description="Code métier de l'erreur.")

    message: str = Field(..., min_length=1, description="Description de l'erreur.")

    recoverable: bool = Field(
        default=True,
        description=(
            "Indique si le workflow peut poursuivre ou produire un résultat partiel."
        ),
    )


# Réponses API


class ErrorResponse(BaseModel):
    """Réponse d'erreur standardisée de l'API."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    error: ApiError = Field(..., description="Erreur retournée par l'API.")

    request_id: str | None = Field(
        default=None,
        description="Identifiant permettant de retrouver les logs associés.",
    )


class ValidationErrorResponse(BaseModel):
    """Réponse standardisée d'une erreur de validation."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    error: ApiValidationError = Field(
        ..., description="Erreur de validation retournée par l'API."
    )

    request_id: str | None = Field(
        default=None,
        description="Identifiant permettant de retrouver les logs associés.",
    )
