"""Téléchargement des contenus pédagogiques Wikichess.

Ce module construit le corpus documentaire utilisé par le moteur RAG
de Chess Agent.

Les ouvertures à parcourir sont chargées depuis un fichier JSON externe.

Pour chaque ouverture configurée, le module :

- parcourt Wikichess jusqu'à la position ciblée ;
- extrait l'intégralité du contenu pédagogique ;
- récupère les métadonnées utiles ;
- récupère les coups suivants et leurs pages Wikichess ;
- structure les branches avec WikichessNextMove ;
- enregistre un document JSON autonome ;
- produit un manifeste global du téléchargement.

Le contenu pédagogique correspond au texte situé après les informations
de position et d'édition, jusqu'au séparateur Wikichess.

Les statistiques détaillées situées après ce séparateur ne sont pas
collectées.

Les fichiers JSON générés sont destinés à être ingérés ensuite dans
Milvus comme documents pédagogiques.
"""

from __future__ import annotations

import asyncio
import json
import re
import sys
from dataclasses import asdict
from datetime import UTC, datetime
from pathlib import Path
from time import perf_counter
from typing import Any
from urllib.parse import urljoin, urlparse
from urllib.robotparser import RobotFileParser

import httpx
from bs4 import BeautifulSoup, Tag

# Chemins

BACKEND_DIRECTORY = Path(
    __file__
).resolve().parents[1]

if str(BACKEND_DIRECTORY) not in sys.path:
    sys.path.insert(
        0,
        str(BACKEND_DIRECTORY)
    )


# Imports applicatifs

from app.core.logging import get_logger

from scripts.config.constants_scripts import (
    ACCEPTED_CONTENT_TYPES,
    ARTICLE_END_PATTERNS,
    ARTICLE_START_PATTERN,
    CONTRIBUTORS_PATTERN,
    DATE_LINE_PATTERN,
    DEFAULT_ENCODING,
    ECO_METADATA_PATTERN,
    ECO_PATTERN,
    EDITOR_PATTERN,
    MANIFEST_FILE,
    MOVE_NUMBER_PATTERN,
    MOVE_SUFFIX_PATTERN,
    MULTIPLE_NEWLINES_PATTERN,
    MULTIPLE_SPACES_PATTERN,
    OPENING_PATTERN,
    OPENINGS_FILE,
    POSITION_MARKER_PATTERN,
    REMOVED_TAGS,
    SEPARATOR_PATTERN,
    USER_AGENT,
    WIKICHESS_BASE_URL,
    WIKICHESS_DIRECTORY,
    WIKICHESS_PAGE_PATTERN,
    WIKICHESS_ROBOTS_URL,
    WIKICHESS_SOURCE,
    WIKICHESS_START_URL,
)
from scripts.config.settings_scripts import wikichess_script_settings
from scripts.schemas.wikichess_script import (
    DownloadFailure,
    OpeningTarget,
    WikichessNextMove,
)

logger = get_logger(__name__)


# Types

ArticlePayload = dict[str, Any]

OpeningTargets = tuple[
    OpeningTarget,
    ...
]

NextMoves = tuple[
    WikichessNextMove,
    ...
]


# Chargement des ouvertures

def load_opening_targets() -> OpeningTargets:
    """Charge les ouvertures configurées depuis le fichier JSON."""

    if not OPENINGS_FILE.is_file():
        raise ValueError(
            "Le fichier des ouvertures est introuvable : "
            f"{OPENINGS_FILE}"
        )

    try:
        payload = json.loads(
            OPENINGS_FILE.read_text(
                encoding=DEFAULT_ENCODING
            )
        )

    except json.JSONDecodeError as error:
        raise ValueError(
            "Le fichier openings.json contient un JSON invalide."
        ) from error

    except OSError as error:
        raise ValueError(
            "Impossible de lire le fichier des ouvertures : "
            f"{OPENINGS_FILE}"
        ) from error

    if not isinstance(payload, list):
        raise ValueError(
            "La racine de openings.json doit être une liste."
        )

    targets: list[OpeningTarget] = []

    for index, item in enumerate(
        payload,
        start=1
    ):
        if not isinstance(item, dict):
            raise ValueError(
                f"L'ouverture #{index} doit être un objet JSON."
            )

        try:
            slug = item["slug"]
            title = item["title"]
            moves = item["moves"]
            eco = item["eco"]

        except KeyError as error:
            raise ValueError(
                "Champ obligatoire absent dans l'ouverture "
                f"#{index} : {error.args[0]}."
            ) from error

        if not isinstance(slug, str):
            raise ValueError(
                f"Le slug de l'ouverture #{index} doit être une chaîne."
            )

        if not isinstance(title, str):
            raise ValueError(
                f"Le titre de l'ouverture #{index} doit être une chaîne."
            )

        if not isinstance(eco, str):
            raise ValueError(
                f"Le code ECO de l'ouverture #{index} doit être une chaîne."
            )

        if not isinstance(moves, list):
            raise ValueError(
                f"Les coups de l'ouverture #{index} doivent être une liste."
            )

        if not all(
            isinstance(move, str)
            for move in moves
        ):
            raise ValueError(
                f"Tous les coups de l'ouverture #{index} "
                "doivent être des chaînes."
            )

        target = OpeningTarget(
            slug=slug.strip(),
            title=title.strip(),
            moves=tuple(
                move.strip()
                for move in moves
            ),
            eco=eco.strip()
        )

        validate_opening_target(
            target
        )

        targets.append(
            target
        )

    if not targets:
        raise ValueError(
            "Aucune ouverture n'est configurée dans openings.json."
        )

    slugs = [
        target.slug
        for target in targets
    ]

    if len(slugs) != len(set(slugs)):
        raise ValueError(
            "Deux ouvertures utilisent le même slug."
        )

    logger.info(
        "%s ouverture(s) chargée(s) depuis %s.",
        len(targets),
        OPENINGS_FILE
    )

    return tuple(
        targets
    )


# Validation

def validate_configuration(
    targets: OpeningTargets
) -> None:
    """Valide la configuration du collecteur Wikichess."""

    if not targets:
        raise ValueError(
            "La liste des ouvertures est vide."
        )

    for target in targets:
        validate_opening_target(
            target
        )


def validate_opening_target(
    target: OpeningTarget
) -> None:
    """Valide une ouverture configurée."""

    if not target.slug.strip():
        raise ValueError(
            "Une ouverture possède un slug vide."
        )

    if not target.title.strip():
        raise ValueError(
            "Une ouverture possède un titre vide."
        )

    if not target.moves:
        raise ValueError(
            f"Aucune ligne définie pour {target.title}."
        )

    if any(
        not move.strip()
        for move in target.moves
    ):
        raise ValueError(
            f"Un coup est vide pour {target.title}."
        )

    if ECO_PATTERN.fullmatch(
        target.eco
    ) is None:
        raise ValueError(
            "Code ECO invalide pour "
            f"{target.title} : {target.eco}."
        )


# Normalisation

def normalize_text(
    value: Any
) -> str:
    """Normalise une valeur textuelle."""

    if not isinstance(value, str):
        return ""

    normalized_value = (
        value
        .replace("\u00a0", " ")
        .replace("\r\n", "\n")
        .replace("\r", "\n")
    )

    lines: list[str] = []

    for raw_line in normalized_value.splitlines():
        line = MULTIPLE_SPACES_PATTERN.sub(
            " ",
            raw_line
        ).strip()

        if line:
            lines.append(
                line
            )

            continue

        if (
            lines
            and lines[-1] != ""
        ):
            lines.append(
                ""
            )

    normalized_value = "\n".join(
        lines
    )

    return MULTIPLE_NEWLINES_PATTERN.sub(
        "\n\n",
        normalized_value
    ).strip()


def normalize_move(
    value: Any
) -> str:
    """Normalise un coup Wikichess."""

    move = normalize_text(
        value
    )

    if not move:
        return ""

    move = MOVE_NUMBER_PATTERN.sub(
        "",
        move
    ).strip()

    move = MOVE_SUFFIX_PATTERN.sub(
        "",
        move
    ).strip()

    return (
        move
        .replace("0-0-0", "O-O-O")
        .replace("0-0", "O-O")
        .replace("×", "x")
        .replace("–", "-")
        .replace("—", "-")
    )


def remove_duplicate_lines(
    content: str
) -> str:
    """Retire les lignes successives identiques."""

    lines: list[str] = []

    previous_line: str | None = None

    for raw_line in content.splitlines():
        line = normalize_text(
            raw_line
        )

        if not line:
            if (
                lines
                and lines[-1] != ""
            ):
                lines.append(
                    ""
                )

            previous_line = None

            continue

        comparable_line = line.casefold()

        if comparable_line == previous_line:
            continue

        lines.append(
            line
        )

        previous_line = comparable_line

    return normalize_text(
        "\n".join(
            lines
        )
    )


def split_contributors(
    value: str
) -> tuple[str, ...]:
    """Découpe et déduplique les contributeurs."""

    contributors = [
        normalize_text(
            contributor
        )
        for contributor in re.split(
            r"[,;]",
            value
        )
    ]

    return tuple(
        dict.fromkeys(
            contributor
            for contributor in contributors
            if contributor
        )
    )


# URL

def is_ficgs_url(
    url: str
) -> bool:
    """Indique si une URL appartient au domaine FICGS."""

    host = urlparse(
        url
    ).netloc.casefold()

    return host in {
        "ficgs.com",
        "www.ficgs.com"
    }


def is_wikichess_page_url(
    url: str
) -> bool:
    """Indique si une URL correspond à une page Wikichess."""

    if not is_ficgs_url(
        url
    ):
        return False

    parsed_url = urlparse(
        url
    )

    return WIKICHESS_PAGE_PATTERN.search(
        parsed_url.path
    ) is not None


# Robots

async def load_robots_parser(
    client: httpx.AsyncClient
) -> RobotFileParser | None:
    """Télécharge et prépare robots.txt."""

    try:
        response = await client.get(
            WIKICHESS_ROBOTS_URL
        )

        if response.status_code == 404:
            logger.info(
                "Aucun fichier robots.txt publié."
            )

            return None

        response.raise_for_status()

    except httpx.HTTPError as error:
        if wikichess_script_settings.strict_robots_policy:
            raise RuntimeError(
                "Impossible de vérifier robots.txt."
            ) from error

        logger.warning(
            "robots.txt indisponible : %s",
            error
        )

        return None

    parser = RobotFileParser()

    parser.set_url(
        WIKICHESS_ROBOTS_URL
    )

    parser.parse(
        response.text.splitlines()
    )

    return parser


def ensure_url_allowed(
    parser: RobotFileParser | None,
    url: str
) -> None:
    """Vérifie qu'une URL est autorisée."""

    if parser is None:
        return

    if parser.can_fetch(
        USER_AGENT,
        url
    ):
        return

    if wikichess_script_settings.strict_robots_policy:
        raise PermissionError(
            "Accès interdit par robots.txt : "
            f"{url}"
        )

    logger.warning(
        "URL non autorisée explicitement par robots.txt : %s.",
        url
    )


# HTTP

def _resolve_response_encoding(
    response: httpx.Response
) -> str:
    """Détermine l'encodage d'une page Wikichess."""

    content_type = response.headers.get(
        "content-type",
        ""
    )

    charset_match = re.search(
        r"charset\s*=\s*[\"']?([^;\"'\s]+)",
        content_type,
        flags=re.IGNORECASE
    )

    if charset_match is not None:
        return charset_match.group(1)

    return DEFAULT_ENCODING

async def fetch_html(
    client: httpx.AsyncClient,
    url: str,
    robots_parser: RobotFileParser | None
) -> str:
    """Télécharge et décode une page HTML Wikichess."""

    ensure_url_allowed(
        robots_parser,
        url
    )

    response = await client.get(
        url
    )

    response.raise_for_status()

    content_type = response.headers.get(
        "content-type",
        ""
    ).casefold()

    if (
        content_type
        and not any(
            accepted_type in content_type
            for accepted_type in ACCEPTED_CONTENT_TYPES
        )
    ):
        raise ValueError(
            "La ressource téléchargée n'est pas une page HTML : "
            f"{url}."
        )

    response.encoding = _resolve_response_encoding(
        response
    )

    html = response.text.strip()

    if not html:
        raise ValueError(
            f"La page téléchargée est vide : {url}."
        )

    return html


# Liens Wikichess

def extract_link_texts(
    link: Tag
) -> set[str]:
    """Retourne les textes pouvant représenter le coup d'un lien."""

    values = {
        normalize_move(
            link.get_text(
                " ",
                strip=True
            )
        ),
        normalize_move(
            link.get(
                "title"
            )
        ),
        normalize_move(
            link.get(
                "aria-label"
            )
        )
    }

    image = link.find(
        "img"
    )

    if isinstance(
        image,
        Tag
    ):
        values.add(
            normalize_move(
                image.get(
                    "alt"
                )
            )
        )

        values.add(
            normalize_move(
                image.get(
                    "title"
                )
            )
        )

    return {
        value
        for value in values
        if value
    }


def extract_link_move(
    link: Tag
) -> str:
    """Extrait le coup représenté par un lien Wikichess."""

    move = normalize_move(
        link.get_text(
            " ",
            strip=True
        )
    )

    if move:
        return move

    title = normalize_text(
        link.get(
            "title"
        )
    )

    if title:
        title_move = title.split(
            ":",
            maxsplit=1
        )[0]

        move = normalize_move(
            title_move
        )

        if move:
            return move

    image = link.find(
        "img"
    )

    if isinstance(
        image,
        Tag
    ):
        move = normalize_move(
            image.get(
                "alt"
            )
        )

        if move:
            return move

    return ""


# Navigation

def find_move_url(
    html: str,
    current_url: str,
    expected_move: str
) -> str:
    """Retourne l'URL correspondant à un coup."""

    soup = BeautifulSoup(
        html,
        "html.parser"
    )

    normalized_expected_move = normalize_move(
        expected_move
    )

    if not normalized_expected_move:
        raise ValueError(
            "Le coup recherché ne peut pas être vide."
        )

    available_moves: list[str] = []

    for link in soup.select(
        "a[href]"
    ):
        href = normalize_text(
            link.get(
                "href"
            )
        )

        if not href:
            continue

        url = urljoin(
            current_url,
            href
        )

        if not is_wikichess_page_url(
            url
        ):
            continue

        link_texts = extract_link_texts(
            link
        )

        available_moves.extend(
            sorted(
                link_texts
            )
        )

        if normalized_expected_move in link_texts:
            return url

    displayed_moves = ", ".join(
        dict.fromkeys(
            available_moves
        )
    )

    if not displayed_moves:
        displayed_moves = "aucun coup détecté"

    raise LookupError(
        f"Le coup {expected_move} est introuvable depuis "
        f"{current_url}. Coups disponibles : {displayed_moves}."
    )


async def resolve_opening_page(
    client: httpx.AsyncClient,
    robots_parser: RobotFileParser | None,
    target: OpeningTarget
) -> tuple[str, str]:
    """Parcourt Wikichess jusqu'à la position ciblée."""

    current_url = WIKICHESS_START_URL

    html = await fetch_html(
        client,
        current_url,
        robots_parser
    )

    for move_index, move in enumerate(
        target.moves,
        start=1
    ):
        next_url = find_move_url(
            html,
            current_url,
            move
        )

        logger.debug(
            "Navigation %s/%s pour %s : %s -> %s",
            move_index,
            len(target.moves),
            target.title,
            move,
            next_url
        )

        current_url = next_url

        html = await fetch_html(
            client,
            current_url,
            robots_parser
        )

        if move_index < len(target.moves):
            await asyncio.sleep(
                wikichess_script_settings.request_delay_seconds
            )

    return (
        current_url,
        html
    )


# Coups suivants

def extract_next_moves(
    html: str,
    current_url: str
) -> NextMoves:
    """Extrait les branches suivantes d'une position Wikichess."""

    soup = BeautifulSoup(
        html,
        "html.parser"
    )

    next_moves: list[WikichessNextMove] = []

    seen_moves: set[str] = set()

    for link in soup.select(
        "a[href]"
    ):
        href = normalize_text(
            link.get(
                "href"
            )
        )

        if not href:
            continue

        source_url = urljoin(
            current_url,
            href
        )

        if not is_wikichess_page_url(
            source_url
        ):
            continue

        move = extract_link_move(
            link
        )

        if not move:
            continue

        if move.casefold() in {
            "back",
            "wikichess"
        }:
            continue

        comparable_move = move.casefold()

        if comparable_move in seen_moves:
            continue

        seen_moves.add(
            comparable_move
        )

        next_moves.append(
            WikichessNextMove(
                move=move,
                source_url=source_url
            )
        )

    return tuple(
        next_moves
    )


# Extraction HTML

def remove_unwanted_elements(
    soup: BeautifulSoup
) -> None:
    """Retire les éléments HTML sans intérêt documentaire."""

    for tag_name in REMOVED_TAGS:
        for element in soup.find_all(
            tag_name
        ):
            element.decompose()


def get_page_text(
    soup: BeautifulSoup
) -> str:
    """Retourne le texte complet de la page."""

    body = soup.body

    if not isinstance(
        body,
        Tag
    ):
        raise ValueError(
            "Le corps HTML de la page Wikichess est introuvable."
        )

    return normalize_text(
        body.get_text(
            "\n",
            strip=True
        )
    )


def find_article_end(
    content: str
) -> int:
    """Retourne la position de fin du contenu Wikichess."""

    ends: list[int] = []

    for pattern in ARTICLE_END_PATTERNS:
        match = pattern.search(
            content
        )

        if match is not None:
            ends.append(
                match.start()
            )

    return (
        min(ends)
        if ends
        else len(content)
    )


def isolate_article_content(
    content: str
) -> str:
    """Isole la partie documentaire d'une page Wikichess."""

    start_match = ARTICLE_START_PATTERN.search(
        content
    )

    if start_match is None:
        logger.warning(
            "Marqueur 'Position after :' absent. "
            "Utilisation du contenu disponible."
        )

        article_content = content

    else:
        article_content = content[
            start_match.start():
        ]

    article_content = article_content[
        :find_article_end(
            article_content
        )
    ]

    return remove_duplicate_lines(
        article_content
    )


# Structure Wikichess

def find_separator_index(
    lines: list[str]
) -> int | None:
    """Retourne la position du séparateur Wikichess."""

    for index, line in enumerate(
        lines
    ):
        if SEPARATOR_PATTERN.fullmatch(
            line
        ) is not None:
            return index

    return None


def extract_position(
    lines: list[str],
    target: OpeningTarget
) -> str:
    """Extrait le marqueur position_after de Wikichess."""

    for index, line in enumerate(
        lines
    ):
        match = POSITION_MARKER_PATTERN.match(
            line
        )

        if match is None:
            continue

        inline_position = normalize_text(
            match.group(1)
        )

        if inline_position:
            return inline_position

        if index + 1 >= len(lines):
            continue

        next_line = normalize_text(
            lines[index + 1]
        )

        if (
            next_line
            and EDITOR_PATTERN.search(
                next_line
            ) is None
        ):
            return next_line

    return target.moves[-1]


def find_content_start(
    lines: list[str]
) -> int:
    """Retourne le début du contenu pédagogique."""

    for index, line in enumerate(
        lines
    ):
        if DATE_LINE_PATTERN.fullmatch(
            line
        ) is not None:
            return index + 1

    for index, line in enumerate(
        lines
    ):
        if EDITOR_PATTERN.search(
            line
        ) is not None:
            return index + 1

    for index, line in enumerate(
        lines
    ):
        if POSITION_MARKER_PATTERN.match(
            line
        ) is not None:
            return index + 1

    return 0


# Contenu pédagogique

def extract_content(
    lines: list[str]
) -> str:
    """Extrait le contenu pédagogique Wikichess disponible."""

    if not lines:
        return ""

    start_index = find_content_start(
        lines
    )

    return normalize_text(
        "\n".join(
            lines[start_index:]
        )
    )


# Métadonnées

def extract_metadata(
    lines: list[str],
    target: OpeningTarget
) -> tuple[
    str,
    str,
    tuple[str, ...]
]:
    """Extrait les métadonnées documentaires utiles."""

    metadata_content = "\n".join(
        lines
    )

    opening_match = OPENING_PATTERN.search(
        metadata_content
    )

    eco_match = ECO_METADATA_PATTERN.search(
        metadata_content
    )

    wikichess_title = (
        normalize_text(
            opening_match.group(1)
        )
        if opening_match is not None
        else target.title
    )

    eco = (
        normalize_text(
            eco_match.group(1)
        )
        if eco_match is not None
        else target.eco
    )

    contributors: tuple[str, ...] = ()

    for line in lines:
        match = CONTRIBUTORS_PATTERN.match(
            line
        )

        if match is None:
            continue

        contributors = split_contributors(
            match.group(1)
        )

        break

    return (
        wikichess_title,
        eco,
        contributors
    )


# Sérialisation

def serialize_next_moves(
    next_moves: NextMoves
) -> list[dict[str, str]]:
    """Convertit les branches Wikichess en structures JSON."""

    return [
        asdict(
            next_move
        )
        for next_move in next_moves
    ]


# Construction

def extract_article_payload(
    html: str,
    target: OpeningTarget,
    source_url: str
) -> ArticlePayload:
    """Construit le document pédagogique depuis une page Wikichess."""

    # Branches

    next_moves = extract_next_moves(
        html,
        source_url
    )

    # Contenu documentaire

    soup = BeautifulSoup(
        html,
        "html.parser"
    )

    remove_unwanted_elements(
        soup
    )

    raw_content = get_page_text(
        soup
    )

    isolated_content = isolate_article_content(
        raw_content
    )

    lines = [
        line
        for line in isolated_content.splitlines()
        if line
    ]

    separator_index = find_separator_index(
        lines
    )

    if separator_index is None:
        content_lines = lines
        metadata_lines: list[str] = []

    else:
        content_lines = lines[
            :separator_index
        ]

        metadata_lines = lines[
            separator_index + 1:
        ]

    # Position

    position_after = extract_position(
        content_lines,
        target
    )

    # Présentation

    content = extract_content(
        content_lines
    )

    # Métadonnées

    (
        wikichess_title,
        eco,
        contributors
    ) = extract_metadata(
        metadata_lines,
        target
    )

    # Document

    return {
        "slug": target.slug,
        "title": target.title,
        "wikichess_title": wikichess_title,
        "eco": eco,
        "moves": list(
            target.moves
        ),
        "position_after": position_after,
        "source_url": source_url,
        "language": (
            wikichess_script_settings
            .default_language
        ),
        "retrieved_at": datetime.now(
            UTC
        ).isoformat(),
        "contributors": list(
            contributors
        ),
        "content": content,
        "next_moves": serialize_next_moves(
            next_moves
        )
    }


# Sauvegarde

def get_article_output_path(
    slug: str
) -> Path:
    """Retourne le chemin JSON d'un document Wikichess."""

    return (
        WIKICHESS_DIRECTORY
        / f"{slug}.json"
    )


def save_article(
    article: ArticlePayload
) -> Path:
    """Enregistre un document pédagogique Wikichess."""

    output_path = get_article_output_path(
        str(
            article["slug"]
        )
    )

    if (
        output_path.exists()
        and not (
            wikichess_script_settings
            .replace_existing_files
        )
    ):
        logger.info(
            "Fichier déjà présent, conservation de %s.",
            output_path
        )

        return output_path

    output_path.parent.mkdir(
        parents=True,
        exist_ok=True
    )

    output_path.write_text(
        json.dumps(
            article,
            ensure_ascii=False,
            indent=2
        ),
        encoding=DEFAULT_ENCODING
    )

    logger.info(
        "Document enregistré : %s",
        output_path
    )

    return output_path


# Manifeste

def build_manifest_article(
    article: ArticlePayload
) -> ArticlePayload:
    """Construit l'entrée manifeste d'un article."""

    return {
        key: value
        for key, value in article.items()
        if key != "content"
    }


def save_manifest(
    *,
    targets: OpeningTargets,
    articles: list[ArticlePayload],
    failures: list[DownloadFailure],
    duration_ms: float
) -> None:
    """Enregistre le manifeste du corpus."""

    payload = {
        "source": WIKICHESS_SOURCE,
        "base_url": WIKICHESS_BASE_URL,
        "start_url": WIKICHESS_START_URL,
        "generated_at": datetime.now(
            UTC
        ).isoformat(),
        "requested_count": len(
            targets
        ),
        "downloaded_count": len(
            articles
        ),
        "failed_count": len(
            failures
        ),
        "duration_ms": duration_ms,
        "articles": [
            build_manifest_article(
                article
            )
            for article in articles
        ],
        "failures": [
            asdict(
                failure
            )
            for failure in failures
        ]
    }

    WIKICHESS_DIRECTORY.mkdir(
        parents=True,
        exist_ok=True
    )

    MANIFEST_FILE.write_text(
        json.dumps(
            payload,
            ensure_ascii=False,
            indent=2
        ),
        encoding=DEFAULT_ENCODING
    )

    logger.info(
        "Manifeste enregistré : %s",
        MANIFEST_FILE
    )


# Téléchargement

async def download_opening(
    client: httpx.AsyncClient,
    robots_parser: RobotFileParser | None,
    target: OpeningTarget
) -> ArticlePayload:
    """Télécharge un document pédagogique Wikichess."""

    source_url, html = await resolve_opening_page(
        client,
        robots_parser,
        target
    )

    logger.info(
        "Extraction de %s depuis %s.",
        target.title,
        source_url
    )

    article = extract_article_payload(
        html,
        target,
        source_url
    )

    logger.debug(
        "%s coup(s) suivant(s) détecté(s) pour %s.",
        len(
            article["next_moves"]
        ),
        target.title
    )

    save_article(
        article
    )

    return article


async def download_wikichess() -> tuple[
    list[ArticlePayload],
    list[DownloadFailure],
    float
]:
    """Télécharge les documents pédagogiques Wikichess."""

    targets = load_opening_targets()

    validate_configuration(
        targets
    )

    WIKICHESS_DIRECTORY.mkdir(
        parents=True,
        exist_ok=True
    )

    started_at = perf_counter()

    articles: list[ArticlePayload] = []

    failures: list[DownloadFailure] = []

    async with httpx.AsyncClient(
        timeout=(
            wikichess_script_settings
            .request_timeout_seconds
        ),
        follow_redirects=True,
        headers={
            "User-Agent": USER_AGENT,
            "Accept": ",".join(
                ACCEPTED_CONTENT_TYPES
            )
        }
    ) as client:
        robots_parser = await load_robots_parser(
            client
        )

        for index, target in enumerate(
            targets
        ):
            try:
                logger.info(
                    "Téléchargement de %s : %s.",
                    target.title,
                    " ".join(
                        target.moves
                    )
                )

                article = await download_opening(
                    client,
                    robots_parser,
                    target
                )

                articles.append(
                    article
                )

            except (
                httpx.HTTPError,
                LookupError,
                OSError,
                PermissionError,
                ValueError
            ) as error:
                logger.warning(
                    "Téléchargement impossible pour %s : %s",
                    target.title,
                    error
                )

                failures.append(
                    DownloadFailure(
                        slug=target.slug,
                        title=target.title,
                        reason=str(error)
                    )
                )

            except Exception as error:
                logger.exception(
                    "Erreur inattendue pour %s.",
                    target.title
                )

                failures.append(
                    DownloadFailure(
                        slug=target.slug,
                        title=target.title,
                        reason=(
                            "Erreur inattendue : "
                            f"{error}"
                        )
                    )
                )

            if index < len(targets) - 1:
                await asyncio.sleep(
                    wikichess_script_settings
                    .request_delay_seconds
                )

    duration_ms = round(
        (
            perf_counter()
            - started_at
        ) * 1_000,
        2
    )

    save_manifest(
        targets=targets,
        articles=articles,
        failures=failures,
        duration_ms=duration_ms
    )

    return (
        articles,
        failures,
        duration_ms
    )


# Affichage

def display_report(
    *,
    articles: list[ArticlePayload],
    failures: list[DownloadFailure],
    duration_ms: float
) -> None:
    """Affiche le bilan du téléchargement."""

    print()
    print("Téléchargement Wikichess terminé.")
    print()

    print(
        "Documents téléchargés : "
        f"{len(articles)}"
    )

    print(
        f"Échecs : {len(failures)}"
    )

    print(
        f"Durée : {duration_ms:.2f} ms"
    )

    print(
        f"Répertoire : {WIKICHESS_DIRECTORY}"
    )

    print(
        f"Manifeste : {MANIFEST_FILE}"
    )

    if articles:
        print()
        print("Documents enregistrés :")

        for article in articles:
            print(
                "- "
                f"{article['title']} : "
                f"{article['slug']}.json "
                f"({len(article['next_moves'])} coup(s) suivant(s))"
            )

    if failures:
        print()
        print("Échecs :")

        for failure in failures:
            print(
                f"- {failure.title} : "
                f"{failure.reason}"
            )


# Exécution

async def main() -> int:
    """Exécute le téléchargement Wikichess."""

    try:
        (
            articles,
            failures,
            duration_ms
        ) = await download_wikichess()

    except (
        httpx.HTTPError,
        OSError,
        PermissionError,
        RuntimeError,
        ValueError
    ) as error:
        logger.exception(
            "Téléchargement Wikichess impossible."
        )

        print()
        print(
            f"Erreur : {error}"
        )

        return 1

    except Exception as error:
        logger.exception(
            "Erreur inattendue pendant le téléchargement."
        )

        print()
        print(
            f"Erreur inattendue : {error}"
        )

        return 1

    display_report(
        articles=articles,
        failures=failures,
        duration_ms=duration_ms
    )

    return (
        0
        if articles
        else 1
    )


# Entrée

if __name__ == "__main__":
    raise SystemExit(
        asyncio.run(
            main()
        )
    )