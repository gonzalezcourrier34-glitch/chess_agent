"""Schémas de progression du workflow d'analyse.

Ce module définit les données exposées par l'API pendant
l'exécution d'une analyse Chess Agent.

Ces schémas constituent le contrat entre l'API FastAPI
et le frontend pour le suivi en temps réel du workflow.
"""

from __future__ import annotations

from typing import Literal

from pydantic import (
    BaseModel,
    ConfigDict,
    Field,
)

from app.schemas.analysis.analysis import AnalysisResponse
from app.schemas.common.enums import (
    ServiceType,
    WorkflowStep,
    WorkflowStepStatus,
)


class AnalysisProgressEvent(BaseModel):
    """Événement de progression d'une analyse."""

    model_config = ConfigDict(
        extra="forbid"
    )

    event: Literal["progress"] = "progress"

    request_id: str

    step: WorkflowStep

    service: ServiceType | None = None

    status: WorkflowStepStatus

    completed_steps: list[WorkflowStep] = Field(
        default_factory=list
    )

    message: str | None = None


class AnalysisCompletedEvent(BaseModel):
    """Événement final d'une analyse."""

    model_config = ConfigDict(
        extra="forbid"
    )

    event: Literal["completed"] = "completed"

    request_id: str

    analysis: AnalysisResponse