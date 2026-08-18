"""Configuration ajustable des scripts Wikichess.

Ce module centralise les paramètres pouvant varier selon :

- l'environnement d'exécution ;
- la fréquence des requêtes HTTP ;
- le comportement de remplacement des fichiers ;
- la politique robots.txt ;
- les lots d'insertion Milvus ;
- l'export local des documents préparés.

Les valeurs sont chargées automatiquement depuis le fichier .env.

Les constantes structurelles restent définies dans
constants_scripts.py.
"""

from __future__ import annotations

from functools import lru_cache

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict

# Configuration

class WikichessScriptSettings(BaseSettings):
    """Configuration des scripts Wikichess."""

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        env_prefix="WIKICHESS_",
        extra="ignore",
        frozen=True,
        str_strip_whitespace=True
    )

    # Téléchargement

    request_timeout_seconds: float = Field(
        default=30.0,
        gt=0,
        le=300,
        description=(
            "Temps maximal d'attente d'une requête Wikichess "
            "en secondes."
        )
    )

    request_delay_seconds: float = Field(
        default=1.0,
        ge=0,
        le=60,
        description=(
            "Délai entre deux requêtes Wikichess "
            "en secondes."
        )
    )

    default_language: str = Field(
        default="en",
        min_length=2,
        max_length=10,
        description=(
            "Langue utilisée lorsque l'article Wikichess "
            "ne précise aucune langue."
        )
    )

    replace_existing_files: bool = Field(
        default=True,
        description=(
            "Remplace les fichiers JSON Wikichess "
            "déjà présents."
        )
    )

    strict_robots_policy: bool = Field(
        default=False,
        description=(
            "Interrompt le téléchargement lorsqu'une URL "
            "est refusée ou impossible à vérifier dans robots.txt."
        )
    )

    # Ingestion

    replace_existing_documents: bool = Field(
        default=True,
        description=(
            "Supprime les anciens documents Wikichess "
            "avant une nouvelle ingestion."
        )
    )

    milvus_insert_batch_size: int = Field(
        default=100,
        ge=1,
        le=10_000,
        description=(
            "Nombre maximal de documents insérés dans Milvus "
            "par lot."
        )
    )

    export_prepared_chunks: bool = Field(
        default=True,
        description=(
            "Enregistre les documents Wikichess préparés "
            "dans un fichier JSON avant leur insertion dans Milvus."
        )
    )


# Accès

@lru_cache(
    maxsize=1
)
def get_wikichess_script_settings() -> WikichessScriptSettings:
    """Retourne l'unique configuration des scripts Wikichess."""

    return WikichessScriptSettings()


# Instance

wikichess_script_settings = (
    get_wikichess_script_settings()
)