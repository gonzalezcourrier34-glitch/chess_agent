"""Schémas représentant les utilisateurs du projet Chess Agent.

Ce module regroupe les modèles décrivant les utilisateurs, leurs
préférences et leurs informations publiques.

Ces modèles sont utilisés par MongoDB, les services métier et l'API.
"""

from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, ConfigDict, EmailStr, Field

from app.schemas.enums import DifficultyLevel


# Utilisateur

class User(BaseModel):
    """Représente un utilisateur."""

    model_config = ConfigDict(
        extra="forbid",
        frozen=True
    )

    id: str = Field(
        ...,
        description="Identifiant unique."
    )

    username: str = Field(
        ...,
        min_length=3,
        max_length=50,
        description="Nom d'utilisateur."
    )

    email: EmailStr = Field(
        ...,
        description="Adresse électronique."
    )

    created_at: datetime = Field(
        ...,
        description="Date de création du compte."
    )


# Préférences

class UserPreferences(BaseModel):
    """Préférences d'apprentissage."""

    model_config = ConfigDict(
        extra="forbid"
    )

    preferred_color: str | None = Field(
        default=None,
        description="Couleur préférée."
    )

    preferred_openings: list[str] = Field(
        default_factory=list,
        description="Ouvertures favorites."
    )

    difficulty: DifficultyLevel = Field(
        default=DifficultyLevel.INTERMEDIATE,
        description="Niveau souhaité."
    )

    language: str = Field(
        default="fr",
        description="Langue préférée."
    )


# Profil

class UserProfile(BaseModel):
    """Profil complet d'un utilisateur."""

    model_config = ConfigDict(
        extra="forbid"
    )

    user: User

    preferences: UserPreferences | None = Field(
        default=None,
        description="Préférences utilisateur."
    )