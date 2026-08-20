"""Schémas représentant l'état des services.

Ce module définit les modèles utilisés par les endpoints de supervision
de Chess Agent.
"""

from __future__ import annotations

from app.schemas.common.enums import ServiceStatus
from pydantic import BaseModel, ConfigDict

# Service


class ServiceHealth(BaseModel):
    """État d'un service applicatif."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    available: bool

    status: ServiceStatus

    message: str | None = None


# Services


class ServicesStatus(BaseModel):
    """État des services de l'application."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    mongodb: ServiceHealth

    milvus: ServiceHealth

    embedding: ServiceHealth

    stockfish: ServiceHealth

    lichess: ServiceHealth

    youtube: ServiceHealth

    llm: ServiceHealth

    langgraph: ServiceHealth
