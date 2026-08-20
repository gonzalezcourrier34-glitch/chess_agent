"""Configuration centralisée de Chess Agent.

Ce module centralise :

- les paramètres de l'application ;
- les connexions aux services ;
- les options techniques ;
- le chargement des variables d'environnement.

Toute la configuration est externalisée via le fichier .env.
"""

from __future__ import annotations

from functools import lru_cache
from pathlib import Path
from typing import Literal

from pydantic import Field, SecretStr
from pydantic_settings import BaseSettings, SettingsConfigDict

# Chemins

PROJECT_ROOT = Path(__file__).resolve().parents[3]

ENV_FILE = PROJECT_ROOT / ".env"

# Configuration


class Settings(BaseSettings):
    """Paramètres de configuration de l'application."""

    model_config = SettingsConfigDict(
        env_file=ENV_FILE,
        env_file_encoding="utf-8",
        extra="ignore",
        frozen=True,
        str_strip_whitespace=True,
    )

    # Application

    app_name: str = Field(
        default="Chess Agent", min_length=1, description="Nom de l'application."
    )

    app_version: str = Field(
        default="0.1.0", min_length=1, description="Version de l'application."
    )

    app_env: Literal["development", "test", "production"] = Field(
        default="development", description="Environnement d'exécution."
    )

    app_debug: bool = Field(default=False, description="Active le mode debug.")

    app_host: str = Field(
        default="0.0.0.0", min_length=1, description="Adresse d'écoute du serveur."
    )

    app_port: int = Field(
        default=8000, ge=1, le=65_535, description="Port HTTP de l'application."
    )

    log_level: Literal["DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"] = Field(
        default="INFO", description="Niveau de journalisation."
    )

    # Huggingface

    hf_token: SecretStr | None = Field(
        default=None, description="Jeton d'authentification Hugging Face."
    )

    # HTTP

    http_timeout_seconds: int = Field(
        default=10,
        ge=1,
        le=300,
        description="Temps maximal des requêtes HTTP en secondes.",
    )

    http_max_retry_attempts: int = Field(
        default=3,
        ge=0,
        le=10,
        description="Nombre maximal de nouvelles tentatives HTTP.",
    )

    http_retry_delay_seconds: float = Field(
        default=1.0,
        ge=0,
        le=60,
        description="Délai entre deux tentatives HTTP en secondes.",
    )

    http_max_connections: int = Field(
        default=20, ge=1, le=1_000, description="Nombre maximal de connexions HTTP."
    )

    http_user_agent: str = Field(
        default="ChessAgent/1.0",
        min_length=1,
        description="User-Agent utilisé pour les appels HTTP.",
    )

    # MongoDB

    mongodb_uri: str = Field(
        default="mongodb://localhost:27017",
        min_length=1,
        description="URI de connexion à MongoDB.",
    )

    mongodb_database: str = Field(
        default="chess_agent", min_length=1, description="Nom de la base MongoDB."
    )

    mongodb_server_selection_timeout_ms: int = Field(
        default=5_000,
        ge=100,
        le=120_000,
        description=("Temps maximal de sélection du serveur MongoDB en millisecondes."),
    )

    mongodb_max_pool_size: int = Field(
        default=20, ge=1, le=1_000, description="Nombre maximal de connexions MongoDB."
    )

    mongodb_history_default_limit: int = Field(
        default=20,
        ge=1,
        le=1_000,
        description=(
            "Nombre d'analyses retournées par défaut lors "
            "de la consultation de l'historique."
        ),
    )

    mongodb_response_preview_length: int = Field(
        default=200,
        ge=10,
        le=2_000,
        description=(
            "Longueur maximale de l'aperçu d'une réponse "
            "dans l'historique des analyses."
        ),
    )

    mongodb_history_max_limit: int = Field(
        default=100,
        ge=1,
        le=10_000,
        description=(
            "Nombre maximal d'analyses pouvant être retournées lors d'une consultation."
        ),
    )

    # Milvus

    milvus_host: str = Field(
        default="milvus", min_length=1, description="Nom d'hôte du serveur Milvus."
    )

    milvus_port: int = Field(
        default=19_530, ge=1, le=65_535, description="Port du serveur Milvus."
    )

    milvus_timeout_seconds: int = Field(
        default=10,
        ge=1,
        le=300,
        description="Temps maximal d'attente de Milvus en secondes.",
    )

    milvus_collection_name: str = Field(
        default="documents",
        min_length=1,
        max_length=255,
        pattern=r"^[A-Za-z_][A-Za-z0-9_]*$",
        description="Nom de la collection vectorielle utilisée.",
    )

    milvus_metric_type: Literal["COSINE", "IP", "L2"] = Field(
        default="COSINE", description="Métrique utilisée pour la recherche vectorielle."
    )

    milvus_index_type: Literal["HNSW", "IVF_FLAT", "AUTOINDEX"] = Field(
        default="HNSW", description="Type d'index vectoriel utilisé."
    )

    milvus_search_limit: int = Field(
        default=5,
        ge=1,
        le=100,
        description="Nombre maximal de résultats retournés par Milvus.",
    )

    milvus_index_m: int = Field(
        default=16,
        ge=4,
        le=128,
        description=(
            "Nombre maximal de voisins conservés dans le graphe "
            "HNSW. Une valeur élevée améliore la précision mais "
            "augmente la mémoire utilisée."
        ),
    )

    milvus_index_ef_construction: int = Field(
        default=200,
        ge=8,
        le=2_048,
        description=(
            "Nombre de voisins explorés lors de la construction de "
            "l'index HNSW. Une valeur élevée améliore la qualité de "
            "l'index mais augmente le temps de création."
        ),
    )

    milvus_search_ef: int = Field(
        default=64,
        ge=8,
        le=2_048,
        description=(
            "Nombre de voisins explorés lors d'une recherche HNSW. "
            "Une valeur élevée améliore la précision mais augmente le "
            "temps de recherche."
        ),
    )

    milvus_ivf_nlist: int = Field(
        default=1024, ge=1, description="Nombre de clusters de l'index IVF."
    )

    milvus_ivf_nprobe: int = Field(
        default=16,
        ge=1,
        description="Nombre de clusters explorés lors d'une recherche IVF.",
    )

    milvus_recreate_collection: bool = Field(
        default=False,
        description=(
            "Supprime puis recrée automatiquement la collection Milvus "
            "avant son initialisation. Cette option est principalement "
            "destinée aux phases de développement ou de reconstruction "
            "complète du corpus vectoriel."
        ),
    )

    # Embeddings

    embedding_provider: Literal["sentence-transformers"] = Field(
        default="sentence-transformers", description="Fournisseur des embeddings."
    )

    embedding_model: str = Field(
        default="Qwen/Qwen3-Embedding-0.6B",
        min_length=1,
        description="Modèle utilisé pour générer les embeddings.",
    )

    embedding_device: Literal["cpu", "cuda"] = Field(
        default="cpu", description="Périphérique utilisé pour les embeddings."
    )

    embedding_max_batch_size: int = Field(
        default=16, ge=1, le=1_024, description="Nombre maximal de textes par lot."
    )

    embedding_max_text_length: int = Field(
        default=20_000,
        ge=1,
        le=1_000_000,
        description=(
            "Longueur maximale d'un texte en caractères "
            "avant génération de l'embedding."
        ),
    )

    rag_search_top_k: int = Field(
        default=5,
        ge=1,
        le=50,
        description="Nombre maximal de résultats demandés au moteur RAG.",
    )

    # Stockfish

    stockfish_path: str = Field(
        default="/usr/games/stockfish",
        min_length=1,
        description="Chemin vers l'exécutable Stockfish.",
    )

    stockfish_depth: int = Field(
        default=15, ge=1, le=50, description="Profondeur d'analyse de Stockfish."
    )

    stockfish_threads: int = Field(
        default=2, ge=1, le=128, description="Nombre de threads utilisés par Stockfish."
    )

    stockfish_hash_mb: int = Field(
        default=128,
        ge=1,
        le=32_768,
        description="Mémoire de la table de hachage Stockfish en Mo.",
    )

    stockfish_timeout_seconds: int = Field(
        default=30,
        ge=1,
        le=600,
        description="Temps maximal d'une analyse Stockfish en secondes.",
    )

    # Lichess

    lichess_api_url: str = Field(
        default="https://explorer.lichess.ovh",
        min_length=1,
        description="URL de l'API Lichess.",
    )

    lichess_token: SecretStr | None = Field(
        default=None, description="Jeton d'authentification Lichess."
    )

    lichess_timeout_seconds: int = Field(
        default=10,
        ge=1,
        le=300,
        description="Temps maximal des requêtes Lichess en secondes.",
    )

    lichess_max_moves: int = Field(
        default=20, ge=1, le=100, description="Nombre maximal de coups récupérés."
    )

    # YouTube

    youtube_api_key: SecretStr | None = Field(
        default=None, description="Clé de l'API YouTube."
    )

    youtube_api_url: str = Field(
        default="https://www.googleapis.com/youtube/v3",
        min_length=1,
        description="URL de l'API YouTube.",
    )

    youtube_search_max_results: int = Field(
        default=5,
        ge=1,
        le=20,
        description="Nombre maximal de vidéos retournées par la recherche.",
    )

    youtube_region_code: str = Field(
        default="FR",
        min_length=2,
        max_length=2,
        description="Code pays utilisé pour la recherche YouTube.",
    )

    youtube_timeout_seconds: int = Field(
        default=15,
        ge=1,
        le=300,
        description="Temps maximal des requêtes YouTube en secondes.",
    )

    youtube_default_language: str = Field(
        default="fr",
        min_length=2,
        max_length=10,
        description="Langue utilisée par défaut pour les recherches YouTube.",
    )

    youtube_query_suffix: str = Field(
        default="chess opening tutorial explanation",
        min_length=1,
        description="Suffixe ajouté aux recherches pédagogiques YouTube.",
    )

    # LLM

    llm_provider: Literal["ollama"] = Field(
        default="ollama", description="Fournisseur du modèle de langage."
    )

    llm_model: str = Field(
        default="qwen2.5:7b-instruct",
        min_length=1,
        description="Modèle Ollama utilisé pour la génération.",
    )

    llm_base_url: str = Field(
        default="http://ollama:11434",
        min_length=1,
        description="URL du service Ollama.",
    )

    llm_temperature: float = Field(
        default=0.0,
        ge=0.0,
        le=2.0,
        description="Température utilisée pour la génération.",
    )

    llm_timeout_seconds: int = Field(
        default=180,
        ge=1,
        le=600,
        description="Temps maximal d'une génération LLM en secondes.",
    )

    llm_num_predict: int = Field(
        default=1_500,
        ge=1,
        le=8_192,
        description="Nombre maximal de tokens générés par le LLM.",
    )
    # Workflow

    max_agent_iterations: int = Field(
        default=10, ge=1, le=50, description="Nombre maximal d'itérations de l'agent."
    )

    max_selected_videos: int = Field(
        default=5,
        ge=1,
        le=20,
        description="Nombre maximal de vidéos retenues par le workflow.",
    )

    top_moves: int = Field(
        default=3,
        ge=1,
        le=10,
        description="Nombre de meilleurs coups retournés par défaut.",
    )

    llm_max_context_documents: int = Field(
        default=5,
        ge=1,
        le=20,
        description=("Nombre maximal de documents transmis au modèle de langage."),
    )

    # Frontend

    frontend_url: str = Field(
        default="http://localhost:4200", min_length=1, description="URL du frontend."
    )

    cors_origins: list[str] = Field(
        default_factory=lambda: ["http://localhost:4200"],
        min_length=1,
        description="Origines CORS autorisées.",
    )

    api_docs_enabled: bool = Field(
        default=True, description="Active la documentation OpenAPI."
    )


# Accès


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    """Retourne l'unique instance de configuration."""

    return Settings()


settings = get_settings()
