"""Constantes structurelles des scripts Wikichess.

Ce module centralise les valeurs utilisées pour :

- parcourir les pages Wikichess ;
- identifier les contenus utiles ;
- charger le catalogue des ouvertures ;
- enregistrer les présentations JSON ;
- préparer les documents vectoriels ;
- construire les métadonnées Milvus.

Les paramètres ajustables restent définis dans
settings_scripts.py.
"""

from __future__ import annotations

import re
from pathlib import Path
from urllib.parse import urljoin

# Chemins

BACKEND_DIRECTORY = Path(
    __file__
).resolve().parents[2]

PROJECT_DIRECTORY = (
    BACKEND_DIRECTORY.parent
)

WIKICHESS_DIRECTORY = (
    PROJECT_DIRECTORY
    / "data"
    / "raw"
    / "wikichess"
)

OPENINGS_FILE = (
    Path(__file__)
    .resolve()
    .parent
    / "openings.json"
)

MANIFEST_FILE = (
    WIKICHESS_DIRECTORY
    / "manifest.json"
)

PROCESSED_DIRECTORY = (
    PROJECT_DIRECTORY
    / "data"
    / "processed"
    / "chunks"
)

PROCESSED_FILE = (
    PROCESSED_DIRECTORY
    / "wikichess_chunks.json"
)


# Wikichess

WIKICHESS_BASE_URL = (
    "https://ficgs.com/"
)

WIKICHESS_START_URL = urljoin(
    WIKICHESS_BASE_URL,
    "wikichess.html"
)

WIKICHESS_ROBOTS_URL = urljoin(
    WIKICHESS_BASE_URL,
    "robots.txt"
)

WIKICHESS_SOURCE = "wikichess"

WIKICHESS_FILTER = (
    'source == "wikichess"'
)


# HTTP

USER_AGENT = (
    "ChessAgentWikichessCollector/1.0 "
    "(educational RAG dataset)"
)

ACCEPTED_CONTENT_TYPES = (
    "text/html",
    "application/xhtml+xml"
)


# Fichiers

DEFAULT_ENCODING = "utf-8"

JSON_EXTENSION = ".json"


# Nettoyage HTML

REMOVED_TAGS = (
    "script",
    "style",
    "noscript",
    "svg",
    "canvas",
    "iframe",
    "form",
    "button"
)


# Expressions communes

MULTIPLE_SPACES_PATTERN = re.compile(
    r"[ \t\u00a0]+"
)

MULTIPLE_NEWLINES_PATTERN = re.compile(
    r"\n{3,}"
)

ECO_PATTERN = re.compile(
    r"\b[A-E][0-9]{2}\b"
)


# Expressions Wikichess

SEPARATOR_PATTERN = re.compile(
    r"^=+$"
)

OPENING_PATTERN = re.compile(
    r'\[Opening\s+"([^"]+)"\]',
    flags=re.IGNORECASE
)

ECO_METADATA_PATTERN = re.compile(
    r'\[ECO\s+"([^"]+)"\]',
    flags=re.IGNORECASE
)

CONTRIBUTORS_PATTERN = re.compile(
    r"^Contributors?\s*:\s*(.+)$",
    flags=re.IGNORECASE
)

POSITION_MARKER_PATTERN = re.compile(
    r"^Position\s+after\s*:\s*(.*)$",
    flags=re.IGNORECASE
)

EDITOR_PATTERN = re.compile(
    r"last\s+edited\s+by",
    flags=re.IGNORECASE
)

DATE_LINE_PATTERN = re.compile(
    r"^\[[^\]]+\]$"
)

ARTICLE_START_PATTERN = re.compile(
    r"Position\s+after\s*:",
    flags=re.IGNORECASE
)

ARTICLE_END_PATTERNS = (
    re.compile(
        (
            r"See\s+this\s+chess\s+line\s+with\s+the\s+"
            r"javascript\s+viewer"
        ),
        flags=re.IGNORECASE
    ),
    re.compile(
        r"Play\s+this\s+chess\s+position",
        flags=re.IGNORECASE
    ),
    re.compile(
        r"Back\s+to\s+Wikichess",
        flags=re.IGNORECASE
    )
)

WIKICHESS_PAGE_PATTERN = re.compile(
    r"/wikichess(?:_\d+)?\.html(?:\?.*)?$",
    flags=re.IGNORECASE
)

MOVE_NUMBER_PATTERN = re.compile(
    r"^\d+\.(?:\.\.)?"
)

MOVE_SUFFIX_PATTERN = re.compile(
    r"[?!+#]+$"
)


# Identifiants vectoriels

CHUNK_ID_PREFIX = "wikichess"

CHUNK_HASH_LENGTH = 12

CHUNK_INDEX_WIDTH = 4

# Métadonnées Milvus

METADATA_DATASET_KEY = "dataset"

METADATA_ARTICLE_SLUG_KEY = "article_slug"

METADATA_ARTICLE_TITLE_KEY = "article_title"

METADATA_CHUNK_INDEX_KEY = "chunk_index"

METADATA_CHUNK_COUNT_KEY = "chunk_count"

METADATA_SOURCE_PATH_KEY = "source_path"

METADATA_LANGUAGE_KEY = "language"

METADATA_ECO_KEY = "eco"

METADATA_MOVES_KEY = "moves"

METADATA_MOVES_PATH_KEY = "moves_path"

METADATA_POSITION_AFTER_KEY = "position_after"

METADATA_NEXT_MOVES_KEY = "next_moves"

METADATA_SOURCE_URL_KEY = "source_url"

METADATA_WIKICHESS_TITLE_KEY = "wikichess_title"

METADATA_CONTRIBUTORS_KEY = "contributors"

METADATA_RETRIEVED_AT_KEY = "retrieved_at"