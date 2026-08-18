"""Dépendances de pagination de l'API.

Ce module centralise :

- la validation du nombre maximal de résultats ;
- la validation du décalage ;
- la construction des paramètres de pagination.

Il ne contient aucune logique métier.

La validation des paramètres HTTP est déléguée à FastAPI.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Annotated

from fastapi import Depends, Query

from app.core.config import settings

# Modèle

@dataclass(
    frozen=True,
    slots=True
)
class Pagination:
    """Paramètres normalisés de pagination."""

    limit: int

    offset: int


# Paramètres

LimitParameter = Annotated[
    int,
    Query(
        ge=1,
        le=settings.mongodb_history_max_limit,
        description=(
            "Nombre maximal de résultats retournés."
        )
    )
]

OffsetParameter = Annotated[
    int,
    Query(
        ge=0,
        description=(
            "Nombre de résultats ignorés."
        )
    )
]


# Construction

def get_pagination(
    limit: LimitParameter = settings.mongodb_history_default_limit,
    offset: OffsetParameter = 0
) -> Pagination:
    """Construit les paramètres de pagination."""

    return Pagination(
        limit=limit,
        offset=offset
    )


# Dépendance typée

PaginationDependency = Annotated[
    Pagination,
    Depends(get_pagination)
]