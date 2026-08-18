"""Dépendances d'authentification de l'API.

Ce module centralise :

- la récupération du jeton Bearer ;
- la validation de sa présence ;
- la préparation du jeton transmis aux services applicatifs.

Il ne valide pas encore l'identité de l'utilisateur.

La vérification cryptographique du jeton et la récupération de
l'utilisateur authentifié seront ajoutées dans une étape ultérieure.
"""

from __future__ import annotations

from typing import Annotated

from fastapi import Depends
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer

from app.core.exceptions import AuthenticationError

# Sécurité

bearer_scheme = HTTPBearer(
    auto_error=False
)


# Types

BearerCredentials = Annotated[
    HTTPAuthorizationCredentials | None,
    Depends(bearer_scheme)
]


# Dépendances

def get_access_token(
    credentials: BearerCredentials
) -> str:
    """Retourne le jeton Bearer transmis par le client."""

    if credentials is None:
        raise AuthenticationError(
            message=(
                "Jeton d'authentification manquant."
            )
        )

    token = credentials.credentials.strip()

    if not token:
        raise AuthenticationError(
            message=(
                "Jeton d'authentification vide."
            )
        )

    return token


# Dépendance typée

AccessTokenDependency = Annotated[
    str,
    Depends(get_access_token)
]