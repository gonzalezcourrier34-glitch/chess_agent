"""Schémas du point de santé de Chess Agent.

Ce module définit la réponse globale retournée par l'endpoint de santé
de l'application.

Le détail des composants supervisés est représenté par ServicesStatus.
"""

from __future__ import annotations

from pydantic import BaseModel, ConfigDict

from app.schemas.common.service import ServicesStatus

# Réponse


class HealthcheckResponse(BaseModel):
    """État général de l'application."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    status: str

    application: str

    version: str

    environment: str

    embedding_model: str

    milvus_collection: str

    services: ServicesStatus
