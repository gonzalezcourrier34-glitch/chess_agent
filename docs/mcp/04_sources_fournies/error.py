"""Schémas représentant les erreurs du projet Chess Agent.

Ce module regroupe les modèles utilisés pour représenter les erreurs
retournées par les services métier et l'API.

Ces modèles sont indépendants des exceptions Python.
"""

from __future__ import annotations

from pydantic import BaseModel, ConfigDict, Field


# Erreur

class Error(BaseModel):
    """Représente une erreur."""

    model_config = ConfigDict(
        extra="forbid",
        frozen=True
    )

    code: str = Field(
        ...,
        description="Code métier de l'erreur."
    )

    message: str = Field(
        ...,
        description="Description de l'erreur."
    )

    status_code: int = Field(
        ...,
        ge=100,
        le=599,
        description="Code HTTP associé."
    )


# Erreur de validation

class ValidationError(Error):
    """Erreur de validation."""

    details: list[str] = Field(
        default_factory=list,
        description="Liste des erreurs détectées."
    )


# Réponse d'erreur

class ErrorResponse(BaseModel):
    """Réponse standardisée contenant une erreur."""

    model_config = ConfigDict(
        extra="forbid"
    )

    error: Error