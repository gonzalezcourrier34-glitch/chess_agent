"""Schémas représentant les utilisateurs du projet Chess Agent.

Ce module regroupe les modèles décrivant les utilisateurs, leurs
préférences et leurs informations publiques.

Ces modèles sont utilisés par MongoDB, les services métier et l'API.
"""

from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, ConfigDict, EmailStr, Field

from app.schemas.common.enums import DifficultyLevel

# Utilisateur


class User(BaseModel):
    """Représente un utilisateur."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    # Informations d'identification de l'utilisateur.
    id: str

    username: str = Field(..., min_length=3, max_length=50)

    email: EmailStr

    created_at: datetime


# Préférences


class UserPreferences(BaseModel):
    """Préférences d'apprentissage."""

    model_config = ConfigDict(extra="forbid")

    # Ces préférences permettent d'adapter les analyses
    # et les recommandations proposées à l'utilisateur.
    preferred_color: str | None = None

    preferred_openings: list[str] = Field(default_factory=list)

    difficulty: DifficultyLevel = DifficultyLevel.INTERMEDIATE

    language: str = "fr"


# Profil


class UserProfile(BaseModel):
    """Profil complet d'un utilisateur."""

    model_config = ConfigDict(extra="forbid")

    # Ce modèle rassemble les informations du compte
    # et les préférences d'apprentissage dans une seule réponse.
    user: User

    preferences: UserPreferences | None = None
