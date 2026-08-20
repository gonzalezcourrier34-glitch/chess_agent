"""Constantes communes du projet Chess Agent.

Ce module centralise les valeurs stables partagées par plusieurs
composants de l'application.

Les paramètres pouvant varier selon l'environnement restent définis
dans app.core.config.Settings.
"""

from __future__ import annotations

# Projet

PROJECT_NAME = "Chess Agent"

PROJECT_LOGGER_NAME = "chess_agent"

DEFAULT_ENCODING = "utf-8"


# API

API_PREFIX = "/api"

HEALTH_ENDPOINT = "/health"

ANALYSIS_ENDPOINT = "/analysis"

SERVICES_ENDPOINT = "/services"

VECTOR_SEARCH_ENDPOINT = "/vector-search"


# Journalisation

LOG_FORMAT = "%(asctime)s | %(levelname)s | %(name)s | %(message)s"

LOG_DATE_FORMAT = "%Y-%m-%d %H:%M:%S"


# MongoDB

MONGODB_PING_COMMAND = "ping"

INVALID_COLLECTION_CHARACTER = "\x00"

REQUEST_ID_FIELD = "request_id"

CREATED_AT_FIELD = "created_at"

SAVED_AT_FIELD = "saved_at"

DOCUMENT_VERSION_FIELD = "document_version"

# Collections MongoDB

OPENINGS_COLLECTION = "openings"

OPENING_THEORIES_COLLECTION = "opening_theories"

POSITIONS_COLLECTION = "positions"

ANALYSES_COLLECTION = "analyses"

DOCUMENTS_COLLECTION = "documents"

VIDEOS_COLLECTION = "videos"

USERS_COLLECTION = "users"

USER_HISTORIES_COLLECTION = "user_histories"

FAVORITES_COLLECTION = "favorites"

CACHE_COLLECTION = "cache"

SETTINGS_COLLECTION = "settings"


# Milvus

# Champs communs du schéma Milvus.
MILVUS_ID_FIELD = "id"

MILVUS_VECTOR_FIELD = "vector"

MILVUS_CONTENT_FIELD = "content"

MILVUS_SOURCE_FIELD = "source"

MILVUS_METADATA_FIELD = "metadata"

MILVUS_CREATED_AT_FIELD = "created_at"

# Valeurs techniques utilisées pour construire les collections et les
# index lorsqu'aucune configuration spécifique n'est fournie.
#
# Cette dimension reste uniquement une valeur de secours. La dimension
# réelle doit être récupérée depuis EmbeddingService avant la création
# d'une collection.
MILVUS_DEFAULT_VECTOR_DIMENSION = 1024

MILVUS_MAX_SEARCH_LIMIT = 100

MILVUS_MAX_IDENTIFIER_LENGTH = 100

MILVUS_MAX_SOURCE_LENGTH = 500

# Configuration

MILVUS_RECREATE_COLLECTION = True

# Modèle de langage

# Endpoints Ollama.

LLM_CHAT_ENDPOINT = "/api/chat"

LLM_TAGS_ENDPOINT = "/api/tags"


# Génération de réponse

DEFAULT_RESPONSE_LANGUAGE = "fr"

# DEFAULT_GENERATION_QUESTION = (
#     "Réponds à la question en exploitant toutes les sections pertinentes du contexte."
# )

# Documents

DEFAULT_DOCUMENT_TITLE = "Document d'échecs"

DEFAULT_DOCUMENT_LANGUAGE = "en"

# Lichess

MASTER_DATABASE_ENDPOINT = "/masters"

USER_DATABASE_ENDPOINT = "/lichess"

DEFAULT_STARTING_FEN = "rnbqkbnr/pppppppp/8/8/8/8/PPPPPPPP/RNBQKBNR w KQkq - 0 1"

UNKNOWN_OPENING = "Unknown opening"


# YouTube

YOUTUBE_SEARCH_ENDPOINT = "/search"

YOUTUBE_VIDEOS_ENDPOINT = "/videos"

YOUTUBE_VIDEO_URL_TEMPLATE = "https://www.youtube.com/watch?v={video_id}"

YOUTUBE_EMBED_URL_TEMPLATE = "https://www.youtube.com/embed/{video_id}"

YOUTUBE_CHANNEL_URL_TEMPLATE = "https://www.youtube.com/channel/{channel_id}"

YOUTUBE_SEARCH_PART = "snippet"

YOUTUBE_VIDEO_DETAILS_PART = "contentDetails,statistics,status"

YOUTUBE_SEARCH_TYPE = "video"

YOUTUBE_SEARCH_ORDER = "relevance"

YOUTUBE_SEARCH_SAFE_SEARCH = "strict"

YOUTUBE_SEARCH_VIDEO_DURATION = "medium"

YOUTUBE_RETRYABLE_STATUS_CODES = frozenset(
    {
        408,
        425,
        500,
        502,
        503,
        504,
    }
)

YOUTUBE_QUOTA_ERROR_MARKERS = frozenset(
    {
        "quotaexceeded",
        "dailylimitexceeded",
        "ratelimitexceeded",
        "userratelimitexceeded",
    }
)


# Échecs

WHITE = "white"

BLACK = "black"


# Erreurs

ERROR_INVALID_FEN = "invalid_fen"

ERROR_OPENING_NOT_FOUND = "opening_not_found"

ERROR_LICHESS_UNAVAILABLE = "lichess_unavailable"

ERROR_STOCKFISH_UNAVAILABLE = "stockfish_unavailable"

ERROR_MILVUS_UNAVAILABLE = "milvus_unavailable"

ERROR_YOUTUBE_UNAVAILABLE = "youtube_unavailable"

ERROR_CONFIGURATION = "configuration_error"

ERROR_TIMEOUT = "timeout"

ERROR_UNEXPECTED = "unexpected_error"
