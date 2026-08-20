"""Tests unitaires du service applicatif de recherche vectorielle."""

from __future__ import annotations

from typing import Any, cast
from unittest.mock import AsyncMock, MagicMock

import pytest
from app.adapters.embedding_service import EmbeddingService
from app.adapters.milvus_service import MilvusService
from app.core.config import settings
from app.core.exceptions import (
    EmbeddingGenerationError,
    EmbeddingModelUnavailableError,
    ErrorContext,
    MilvusConnectionError,
    MilvusError,
    MilvusSearchError,
    RetrievalError,
)
from app.schemas.analysis.search import (
    VectorSearchRequest,
    VectorSearchResult,
)
from app.services.vector_search_service import (
    METADATA_ECO_KEY,
    METADATA_MOVES_PATH_KEY,
    RESULT_CONTENT_FIELD,
    RESULT_ID_FIELD,
    RESULT_METADATA_FIELD,
    RESULT_SIMILARITY_FIELD,
    RESULT_SOURCE_FIELD,
    VectorSearchService,
)

# Helpers


def build_service(
    *,
    embedding_service: EmbeddingService | None = None,
    milvus_service: MilvusService | None = None,
) -> VectorSearchService:
    """Construit le service sans infrastructure réelle."""

    if embedding_service is None:
        embedding_service = cast(
            EmbeddingService,
            MagicMock(
                spec=EmbeddingService,
            ),
        )

    if milvus_service is None:
        milvus_service = cast(
            MilvusService,
            MagicMock(
                spec=MilvusService,
            ),
        )

    return VectorSearchService(
        embedding_service=embedding_service,
        milvus_service=milvus_service,
    )


def build_result(
    *,
    identifier: str = "doc-1",
    content: str = "Présentation Wikichess.",
    similarity: float = 0.95,
    eco: str = "C60",
    moves_path: str = "e4 e5 Nf3 Nc6 Bb5",
) -> VectorSearchResult:
    """Construit un résultat vectoriel conforme au schéma actuel."""

    return VectorSearchResult(
        id=identifier,
        content=content,
        similarity=similarity,
        metadata={
            METADATA_ECO_KEY: eco,
            METADATA_MOVES_PATH_KEY: moves_path,
            RESULT_SOURCE_FIELD: "wikichess",
        },
    )


def build_raw_result(
    *,
    identifier: object = "doc-1",
    content: object = "Présentation Wikichess.",
    similarity: object = 0.95,
    source: object = "wikichess",
    metadata: object | None = None,
) -> dict[str, Any]:
    """Construit un résultat brut retourné par Milvus."""

    if metadata is None:
        metadata = {
            METADATA_ECO_KEY: "C60",
            METADATA_MOVES_PATH_KEY: ("e4 e5 Nf3 Nc6 Bb5"),
        }

    return {
        RESULT_ID_FIELD: identifier,
        RESULT_CONTENT_FIELD: content,
        RESULT_SIMILARITY_FIELD: similarity,
        RESULT_SOURCE_FIELD: source,
        RESULT_METADATA_FIELD: metadata,
    }


# Construction


def test_initial_statistics_are_zero() -> None:
    """Vérifie les statistiques initiales."""

    service = build_service()

    assert service.get_search_count() == 0
    assert service.get_result_count() == 0

    assert service.get_last_search_duration_ms() is None


# Requête


def test_normalize_query() -> None:
    """Vérifie la normalisation d'une requête."""

    service = build_service()

    assert service._normalize_query("  Ruy   Lopez   opening ") == "Ruy Lopez opening"


@pytest.mark.parametrize(
    "query",
    [
        "",
        "   ",
        "\n\t",
    ],
)
def test_normalize_query_rejects_empty_query(
    query: str,
) -> None:
    """Vérifie le rejet d'une requête vide."""

    service = build_service()

    with pytest.raises(RetrievalError):
        service._normalize_query(query)


# Limite


def test_normalize_limit_uses_requested_limit() -> None:
    """Vérifie une limite explicite."""

    service = build_service()

    assert service._normalize_limit(3) == 3


def test_normalize_limit_uses_default() -> None:
    """Vérifie la limite par défaut."""

    service = build_service()

    assert service._normalize_limit(None) == min(
        settings.rag_search_top_k,
        settings.milvus_search_limit,
    )


def test_normalize_limit_caps_maximum() -> None:
    """Vérifie le plafonnement Milvus."""

    service = build_service()

    result = service._normalize_limit(settings.milvus_search_limit + 100)

    assert result == settings.milvus_search_limit


@pytest.mark.parametrize(
    "value",
    [
        0,
        -1,
    ],
)
def test_normalize_limit_rejects_non_positive(
    value: int,
) -> None:
    """Vérifie les limites invalides."""

    service = build_service()

    with pytest.raises(RetrievalError):
        service._normalize_limit(value)


def test_normalize_limit_rejects_boolean() -> None:
    """Vérifie qu'un booléen n'est pas accepté comme entier."""

    service = build_service()

    with pytest.raises(RetrievalError):
        service._normalize_limit(True)


def test_normalize_limit_rejects_non_integer() -> None:
    """Vérifie une limite d'un autre type."""

    service = build_service()

    with pytest.raises(RetrievalError):
        service._normalize_limit(
            cast(
                int,
                "5",
            )
        )


# Coups


def test_normalize_moves() -> None:
    """Vérifie la normalisation des coups."""

    service = build_service()

    result = service._normalize_moves(
        [
            " e4 ",
            " e5 ",
            " Nf3 ",
        ]
    )

    assert result == (
        "e4",
        "e5",
        "Nf3",
    )


def test_normalize_moves_rejects_string() -> None:
    """Vérifie qu'une chaîne seule n'est pas une séquence valide."""

    service = build_service()

    with pytest.raises(RetrievalError):
        service._normalize_moves(
            cast(
                list[str],
                "e4 e5",
            )
        )


@pytest.mark.parametrize(
    "moves",
    [
        [],
        [""],
        ["   "],
    ],
)
def test_normalize_moves_rejects_empty_values(
    moves: list[str],
) -> None:
    """Vérifie l'absence de coup exploitable."""

    service = build_service()

    with pytest.raises(RetrievalError):
        service._normalize_moves(moves)


def test_normalize_moves_rejects_invalid_member() -> None:
    """Vérifie une valeur invalide dans la séquence."""

    service = build_service()

    with pytest.raises(RetrievalError):
        service._normalize_moves(
            cast(
                list[str],
                [
                    "e4",
                    42,
                ],
            )
        )


# ECO


def test_normalize_eco() -> None:
    """Vérifie la normalisation ECO."""

    service = build_service()

    assert service._normalize_eco(" c60 ") == "C60"


def test_normalize_eco_rejects_empty() -> None:
    """Vérifie un ECO vide."""

    service = build_service()

    with pytest.raises(RetrievalError):
        service._normalize_eco("   ")


def test_normalize_eco_rejects_non_string() -> None:
    """Vérifie un ECO d'un type invalide."""

    service = build_service()

    with pytest.raises(RetrievalError):
        service._normalize_eco(
            cast(
                str,
                60,
            )
        )


# Filtre


def test_normalize_filter_expression() -> None:
    """Vérifie le nettoyage du filtre."""

    service = build_service()

    assert (
        service._normalize_filter_expression('  metadata["eco"] == "C60"  ')
        == 'metadata["eco"] == "C60"'
    )


def test_normalize_filter_expression_rejects_empty() -> None:
    """Vérifie un filtre vide."""

    service = build_service()

    with pytest.raises(RetrievalError):
        service._normalize_filter_expression("   ")


def test_normalize_filter_expression_rejects_non_string() -> None:
    """Vérifie un filtre d'un autre type."""

    service = build_service()

    with pytest.raises(RetrievalError):
        service._normalize_filter_expression(
            cast(
                str,
                42,
            )
        )


# Échappement


def test_escape_filter_value() -> None:
    """Vérifie l'échappement pour Milvus."""

    service = build_service()

    result = service._escape_filter_value('a\\b"c')

    assert result == ('a\\\\b\\"c')


def test_build_metadata_equals_filter() -> None:
    """Vérifie le filtre d'égalité."""

    service = build_service()

    result = service._build_metadata_equals_filter(
        key="eco",
        value="C60",
    )

    assert result == ('metadata["eco"] == "C60"')


def test_build_metadata_equals_filter_escapes_values() -> None:
    """Vérifie l'échappement des clés et valeurs."""

    service = build_service()

    result = service._build_metadata_equals_filter(
        key='a"b',
        value='c"d',
    )

    assert result == 'metadata["a\\"b"] == "c\\"d"'


# Chemins


def test_build_moves_path() -> None:
    """Vérifie le chemin canonique."""

    service = build_service()

    assert (
        service._build_moves_path(
            (
                "e4",
                "e5",
                "Nf3",
            )
        )
        == "e4 e5 Nf3"
    )


def test_build_eco_filter() -> None:
    """Vérifie le filtre ECO."""

    service = build_service()

    assert service._build_eco_filter("C60") == 'metadata["eco"] == "C60"'


def test_build_moves_filter() -> None:
    """Vérifie le filtre moves_path."""

    service = build_service()

    assert service._build_moves_filter("e4 e5 Nf3") == (
        'metadata["moves_path"] == "e4 e5 Nf3"'
    )


# Texte


@pytest.mark.parametrize(
    ("value", "expected"),
    [
        (
            "  Wikichess   Ruy Lopez ",
            "Wikichess Ruy Lopez",
        ),
        (
            "",
            "",
        ),
        (
            None,
            "",
        ),
        (
            42,
            "",
        ),
    ],
)
def test_get_text(
    value: object,
    expected: str,
) -> None:
    """Vérifie la récupération textuelle."""

    service = build_service()

    assert service._get_text(value) == expected


# Identifiant


@pytest.mark.parametrize(
    ("value", "expected"),
    [
        (
            " doc-1 ",
            "doc-1",
        ),
        (
            123,
            "123",
        ),
        (
            "",
            None,
        ),
        (
            "   ",
            None,
        ),
        (
            None,
            None,
        ),
    ],
)
def test_get_identifier(
    value: object,
    expected: str | None,
) -> None:
    """Vérifie l'identifiant Milvus."""

    service = build_service()

    result = service._get_identifier(
        {
            RESULT_ID_FIELD: value,
        }
    )

    assert result == expected


# Contenu


@pytest.mark.parametrize(
    ("value", "expected"),
    [
        (
            " texte ",
            "texte",
        ),
        (
            "",
            "",
        ),
        (
            None,
            None,
        ),
        (
            42,
            None,
        ),
    ],
)
def test_get_content(
    value: object,
    expected: str | None,
) -> None:
    """Vérifie le contenu."""

    service = build_service()

    result = service._get_content(
        {
            RESULT_CONTENT_FIELD: value,
        }
    )

    assert result == expected


# Similarité


@pytest.mark.parametrize(
    ("value", "expected"),
    [
        (
            0.8,
            0.8,
        ),
        (
            "0.5",
            0.5,
        ),
        (
            -1.0,
            0.0,
        ),
        (
            4.0,
            1.0,
        ),
        (
            None,
            None,
        ),
        (
            True,
            None,
        ),
        (
            "invalid",
            None,
        ),
    ],
)
def test_get_similarity(
    value: object,
    expected: float | None,
) -> None:
    """Vérifie la normalisation de similarité."""

    service = build_service()

    result = service._get_similarity(
        {
            RESULT_SIMILARITY_FIELD: value,
        }
    )

    assert result == expected


# Métadonnées


def test_get_metadata() -> None:
    """Vérifie les métadonnées."""

    service = build_service()

    result = service._get_metadata(
        {
            RESULT_METADATA_FIELD: {
                "eco": "C60",
            },
            RESULT_SOURCE_FIELD: ("wikichess"),
        }
    )

    assert result == {
        "eco": "C60",
        "source": "wikichess",
    }


def test_get_metadata_preserves_existing_source() -> None:
    """Vérifie qu'une source existante n'est pas remplacée."""

    service = build_service()

    result = service._get_metadata(
        {
            RESULT_METADATA_FIELD: {
                "source": "dataset",
            },
            RESULT_SOURCE_FIELD: ("wikichess"),
        }
    )

    assert result["source"] == "dataset"


def test_get_metadata_rejects_invalid_metadata() -> None:
    """Vérifie le repli sur des métadonnées invalides."""

    service = build_service()

    result = service._get_metadata(
        {
            RESULT_METADATA_FIELD: "invalid",
        }
    )

    assert result == {}


# Résultat métier


def test_build_result() -> None:
    """Vérifie la conversion d'un résultat Milvus."""

    service = build_service()

    result = service._build_result(build_raw_result())

    assert result is not None
    assert result.id == "doc-1"
    assert result.content == ("Présentation Wikichess.")
    assert result.similarity == 0.95

    assert result.metadata["eco"] == "C60"


@pytest.mark.parametrize(
    "raw_result",
    [
        {
            RESULT_CONTENT_FIELD: "test",
            RESULT_SIMILARITY_FIELD: 0.5,
        },
        {
            RESULT_ID_FIELD: "id",
            RESULT_SIMILARITY_FIELD: 0.5,
        },
        {
            RESULT_ID_FIELD: "id",
            RESULT_CONTENT_FIELD: "test",
        },
    ],
)
def test_build_result_rejects_incomplete_result(
    raw_result: dict[str, Any],
) -> None:
    """Vérifie qu'un résultat incomplet est ignoré."""

    service = build_service()

    assert service._build_result(raw_result) is None


def test_build_results_filters_invalid_and_duplicates() -> None:
    """Vérifie filtrage et déduplication."""

    service = build_service()

    raw_results = [
        build_raw_result(
            identifier="doc-1",
        ),
        build_raw_result(
            identifier="doc-1",
        ),
        build_raw_result(
            identifier=None,
        ),
        build_raw_result(
            identifier="doc-2",
        ),
    ]

    results = service._build_results(raw_results)

    assert [result.id for result in results] == [
        "doc-1",
        "doc-2",
    ]


# Métadonnées structurelles


def test_get_result_eco() -> None:
    """Vérifie la lecture de l'ECO."""

    service = build_service()

    assert (
        service._get_result_eco(
            build_result(
                eco=" c60 ",
            )
        )
        == "C60"
    )


def test_get_result_eco_returns_none_without_eco() -> None:
    """Vérifie l'absence d'ECO."""

    service = build_service()

    result = build_result().model_copy(
        update={
            "metadata": {},
        }
    )

    assert service._get_result_eco(result) is None


def test_get_result_eco_rejects_non_string() -> None:
    """Vérifie une métadonnée ECO invalide."""

    service = build_service()

    result = build_result().model_copy(
        update={
            "metadata": {
                METADATA_ECO_KEY: 60,
            },
        }
    )

    assert service._get_result_eco(result) is None


def test_get_result_moves_path() -> None:
    """Vérifie la lecture de moves_path."""

    service = build_service()

    result = build_result(moves_path=" e4   e5  Nf3 ")

    assert service._get_result_moves_path(result) == "e4 e5 Nf3"


def test_get_result_moves_path_returns_none() -> None:
    """Vérifie l'absence de moves_path."""

    service = build_service()

    result = build_result().model_copy(
        update={
            "metadata": {},
        }
    )

    assert service._get_result_moves_path(result) is None


# Vérification ECO


def test_keep_exact_eco() -> None:
    """Vérifie la sélection exacte ECO."""

    service = build_service()

    results = [
        build_result(
            identifier="c60",
            eco="C60",
        ),
        build_result(
            identifier="c61",
            eco="C61",
        ),
    ]

    verified = service._keep_exact_eco(
        results,
        eco="C60",
    )

    assert [result.id for result in verified] == [
        "c60",
    ]


# Vérification moves_path


def test_keep_exact_moves_path() -> None:
    """Vérifie la sélection exacte du chemin."""

    service = build_service()

    results = [
        build_result(
            identifier="match",
            moves_path="e4 e5",
        ),
        build_result(
            identifier="other",
            moves_path="d4 d5",
        ),
    ]

    verified = service._keep_exact_moves_path(
        results,
        moves_path="e4 e5",
    )

    assert [result.id for result in verified] == [
        "match",
    ]


# Statistiques


def test_register_search() -> None:
    """Vérifie l'enregistrement des statistiques."""

    service = build_service()

    service._register_search(
        result_count=3,
        duration_ms=12.5,
    )

    assert service.get_search_count() == 1
    assert service.get_result_count() == 3

    assert service.get_last_search_duration_ms() == 12.5

    service._register_search(
        result_count=2,
        duration_ms=8.0,
    )

    assert service.get_search_count() == 2
    assert service.get_result_count() == 5


# Recherche interne


@pytest.mark.asyncio
async def test_execute_search_success() -> None:
    """Vérifie une recherche nominale."""

    embedding_service = cast(
        EmbeddingService,
        MagicMock(
            spec=EmbeddingService,
        ),
    )

    embedding_service.generate_embedding = AsyncMock(
        return_value=[
            0.1,
            0.2,
        ],
    )

    milvus_service = cast(
        MilvusService,
        MagicMock(
            spec=MilvusService,
        ),
    )

    milvus_service.search = AsyncMock(
        return_value=[
            build_raw_result(),
        ]
    )

    service = build_service(
        embedding_service=embedding_service,
        milvus_service=milvus_service,
    )

    results = await service._execute_search(
        query="  Ruy   Lopez ",
        limit=3,
        operation="test",
    )

    assert len(results) == 1
    assert results[0].id == "doc-1"

    embedding_service.generate_embedding.assert_awaited_once_with("Ruy Lopez")

    milvus_service.search.assert_awaited_once_with(
        [
            0.1,
            0.2,
        ],
        limit=3,
        filter_expression=None,
    )

    assert service.get_search_count() == 1
    assert service.get_result_count() == 1

    assert service.get_last_search_duration_ms() is not None


@pytest.mark.asyncio
async def test_execute_search_with_filter() -> None:
    """Vérifie la transmission d'un filtre."""

    embedding_service = cast(
        EmbeddingService,
        MagicMock(
            spec=EmbeddingService,
        ),
    )

    embedding_service.generate_embedding = AsyncMock(
        return_value=[
            0.1,
        ],
    )

    milvus_service = cast(
        MilvusService,
        MagicMock(
            spec=MilvusService,
        ),
    )

    milvus_service.search = AsyncMock(return_value=[])

    service = build_service(
        embedding_service=embedding_service,
        milvus_service=milvus_service,
    )

    await service._execute_search(
        query="test",
        limit=None,
        filter_expression=(' metadata["eco"] == "C60" '),
        operation="filtered",
    )

    milvus_service.search.assert_awaited_once_with(
        [
            0.1,
        ],
        limit=min(
            settings.rag_search_top_k,
            settings.milvus_search_limit,
        ),
        filter_expression=('metadata["eco"] == "C60"'),
    )


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "exception_class",
    [
        EmbeddingModelUnavailableError,
        EmbeddingGenerationError,
    ],
)
async def test_execute_search_translates_embedding_errors(
    exception_class: type[EmbeddingModelUnavailableError | EmbeddingGenerationError],
) -> None:
    """Vérifie la traduction des erreurs d'embedding."""

    embedding_service = cast(
        EmbeddingService,
        MagicMock(
            spec=EmbeddingService,
        ),
    )

    error = exception_class(
        context=ErrorContext(
            service="embedding",
            operation="generate_embedding",
        ),
        message="Embedding indisponible.",
    )

    embedding_service.generate_embedding = AsyncMock(
        side_effect=error,
    )

    service = build_service(
        embedding_service=embedding_service,
    )

    with pytest.raises(RetrievalError) as caught:
        await service._execute_search(
            query="test",
            limit=3,
            operation="test",
        )

    assert "transformer la requête" in str(caught.value)


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "exception_class",
    [
        MilvusConnectionError,
        MilvusSearchError,
        MilvusError,
    ],
)
async def test_execute_search_translates_milvus_errors(
    exception_class: type[MilvusConnectionError | MilvusSearchError | MilvusError],
) -> None:
    """Vérifie la traduction des erreurs Milvus."""

    embedding_service = cast(
        EmbeddingService,
        MagicMock(
            spec=EmbeddingService,
        ),
    )

    embedding_service.generate_embedding = AsyncMock(
        return_value=[
            0.1,
        ],
    )

    milvus_service = cast(
        MilvusService,
        MagicMock(
            spec=MilvusService,
        ),
    )

    error = exception_class(
        context=ErrorContext(
            service="milvus",
            operation="search",
        ),
        message="Milvus indisponible.",
    )

    milvus_service.search = AsyncMock(
        side_effect=error,
    )

    service = build_service(
        embedding_service=embedding_service,
        milvus_service=milvus_service,
    )

    with pytest.raises(RetrievalError) as caught:
        await service._execute_search(
            query="test",
            limit=3,
            operation="test",
        )

    assert "base vectorielle" in str(caught.value)


@pytest.mark.asyncio
async def test_execute_search_translates_unexpected_error() -> None:
    """Vérifie une erreur inattendue."""

    embedding_service = cast(
        EmbeddingService,
        MagicMock(
            spec=EmbeddingService,
        ),
    )

    embedding_service.generate_embedding = AsyncMock(
        side_effect=RuntimeError("unexpected"),
    )

    service = build_service(
        embedding_service=embedding_service,
    )

    with pytest.raises(RetrievalError) as caught:
        await service._execute_search(
            query="test",
            limit=3,
            operation="test",
        )

    assert "recherche vectorielle a échoué" in str(caught.value)


# Recherche sémantique


@pytest.mark.asyncio
async def test_search() -> None:
    """Vérifie la recherche sémantique publique."""

    service = build_service()

    expected_results = [
        build_result(),
    ]

    execute_search = AsyncMock(
        return_value=expected_results,
    )

    service._execute_search = execute_search  # type: ignore[method-assign]

    request = VectorSearchRequest.model_construct(
        query="  Ruy   Lopez ",
        limit=4,
    )

    response = await service.search(request)

    assert response.query == "Ruy Lopez"
    assert response.results == expected_results

    execute_search.assert_awaited_once_with(
        query="Ruy Lopez",
        limit=4,
        operation="search",
    )


# Recherche filtrée


@pytest.mark.asyncio
async def test_search_with_filter() -> None:
    """Vérifie l'API de recherche filtrée."""

    service = build_service()

    expected = [
        build_result(),
    ]

    execute_search = AsyncMock(
        return_value=expected,
    )

    service._execute_search = execute_search  # type: ignore[method-assign]

    result = await service.search_with_filter(
        query="Ruy Lopez",
        filter_expression=('metadata["eco"] == "C60"'),
        limit=2,
    )

    assert result == expected

    execute_search.assert_awaited_once_with(
        query="Ruy Lopez",
        limit=2,
        filter_expression=('metadata["eco"] == "C60"'),
        operation="search_with_filter",
    )


# Wikichess


@pytest.mark.asyncio
async def test_search_wikichess_prefers_eco() -> None:
    """Vérifie la priorité de l'ECO."""

    service = build_service()

    eco_results = [
        build_result(),
    ]

    service.search_by_eco = AsyncMock(  # type: ignore[method-assign]
        return_value=eco_results
    )

    service.search_by_moves = AsyncMock()  # type: ignore[method-assign]

    result = await service.search_wikichess(
        query="Ruy Lopez",
        eco="C60",
        moves=[
            "e4",
            "e5",
        ],
        limit=3,
    )

    assert result == eco_results

    service.search_by_eco.assert_awaited_once_with(
        eco="C60",
        query="Ruy Lopez",
        limit=3,
    )

    service.search_by_moves.assert_not_awaited()


@pytest.mark.asyncio
async def test_search_wikichess_falls_back_to_moves() -> None:
    """Vérifie le repli ECO -> coups."""

    service = build_service()

    service.search_by_eco = AsyncMock(  # type: ignore[method-assign]
        return_value=[]
    )

    move_results = [
        build_result(),
    ]

    service.search_by_moves = AsyncMock(  # type: ignore[method-assign]
        return_value=move_results
    )

    result = await service.search_wikichess(
        query="Ruy Lopez",
        eco="C60",
        moves=[
            "e4",
            "e5",
        ],
        limit=3,
    )

    assert result == move_results

    service.search_by_moves.assert_awaited_once_with(
        moves=[
            "e4",
            "e5",
        ],
        query="Ruy Lopez",
        limit=3,
    )


@pytest.mark.asyncio
async def test_search_wikichess_uses_moves_without_eco() -> None:
    """Vérifie une recherche uniquement par coups."""

    service = build_service()

    expected = [
        build_result(),
    ]

    service.search_by_moves = AsyncMock(  # type: ignore[method-assign]
        return_value=expected
    )

    result = await service.search_wikichess(
        query="position",
        moves=[
            "e4",
            "e5",
        ],
    )

    assert result == expected


@pytest.mark.asyncio
async def test_search_wikichess_requires_context() -> None:
    """Vérifie qu'ECO ou coups sont nécessaires."""

    service = build_service()

    with pytest.raises(RetrievalError):
        await service.search_wikichess(
            query="test",
        )


# Recherche ECO


@pytest.mark.asyncio
async def test_search_by_eco() -> None:
    """Vérifie une recherche ECO complète."""

    service = build_service()

    results = [
        build_result(
            identifier="keep",
            eco="C60",
        ),
        build_result(
            identifier="reject",
            eco="C61",
        ),
    ]

    execute_search = AsyncMock(
        return_value=results,
    )

    service._execute_search = execute_search  # type: ignore[method-assign]

    result = await service.search_by_eco(
        eco=" c60 ",
        query="Ruy Lopez",
        limit=5,
    )

    assert [item.id for item in result] == [
        "keep",
    ]

    execute_search.assert_awaited_once_with(
        query="Ruy Lopez",
        limit=5,
        filter_expression=('metadata["eco"] == "C60"'),
        operation="search_by_eco",
    )


# Recherche coups


@pytest.mark.asyncio
async def test_search_by_moves() -> None:
    """Vérifie une recherche exacte par coups."""

    service = build_service()

    results = [
        build_result(
            identifier="keep",
            moves_path="e4 e5 Nf3",
        ),
        build_result(
            identifier="reject",
            moves_path="d4 d5",
        ),
    ]

    execute_search = AsyncMock(
        return_value=results,
    )

    service._execute_search = execute_search  # type: ignore[method-assign]

    result = await service.search_by_moves(
        moves=[
            " e4 ",
            " e5 ",
            " Nf3 ",
        ],
        query="position",
        limit=4,
    )

    assert [item.id for item in result] == [
        "keep",
    ]

    execute_search.assert_awaited_once_with(
        query="position",
        limit=4,
        filter_expression=('metadata["moves_path"] == "e4 e5 Nf3"'),
        operation="search_by_moves",
    )


# Disponibilité


def test_is_ready_true() -> None:
    """Vérifie un service prêt."""

    embedding_service = cast(
        EmbeddingService,
        MagicMock(
            spec=EmbeddingService,
        ),
    )

    cast(
        Any,
        embedding_service.is_ready,
    ).return_value = True

    milvus_service = cast(
        MilvusService,
        MagicMock(
            spec=MilvusService,
        ),
    )

    cast(
        Any,
        milvus_service.is_ready,
    ).return_value = True

    service = build_service(
        embedding_service=embedding_service,
        milvus_service=milvus_service,
    )

    assert service.is_ready() is True


def test_is_ready_false_if_embedding_not_ready() -> None:
    """Vérifie une dépendance embedding non prête."""

    embedding_service = cast(
        EmbeddingService,
        MagicMock(
            spec=EmbeddingService,
        ),
    )

    cast(
        Any,
        embedding_service.is_ready,
    ).return_value = False

    milvus_service = cast(
        MilvusService,
        MagicMock(
            spec=MilvusService,
        ),
    )

    cast(
        Any,
        milvus_service.is_ready,
    ).return_value = True

    service = build_service(
        embedding_service=embedding_service,
        milvus_service=milvus_service,
    )

    assert service.is_ready() is False


# Ping


@pytest.mark.asyncio
async def test_ping_true() -> None:
    """Vérifie un ping nominal."""

    embedding_service = cast(
        EmbeddingService,
        MagicMock(
            spec=EmbeddingService,
        ),
    )

    embedding_service.ping = AsyncMock(return_value=True)

    milvus_service = cast(
        MilvusService,
        MagicMock(
            spec=MilvusService,
        ),
    )

    milvus_service.ping = AsyncMock(return_value=True)

    service = build_service(
        embedding_service=embedding_service,
        milvus_service=milvus_service,
    )

    assert await service.ping() is True


@pytest.mark.asyncio
async def test_ping_false_when_dependency_unavailable() -> None:
    """Vérifie un ping partiellement indisponible."""

    embedding_service = cast(
        EmbeddingService,
        MagicMock(
            spec=EmbeddingService,
        ),
    )

    embedding_service.ping = AsyncMock(return_value=True)

    milvus_service = cast(
        MilvusService,
        MagicMock(
            spec=MilvusService,
        ),
    )

    milvus_service.ping = AsyncMock(return_value=False)

    service = build_service(
        embedding_service=embedding_service,
        milvus_service=milvus_service,
    )

    assert await service.ping() is False


@pytest.mark.asyncio
async def test_ping_false_on_exception() -> None:
    """Vérifie une erreur inattendue pendant le ping."""

    embedding_service = cast(
        EmbeddingService,
        MagicMock(
            spec=EmbeddingService,
        ),
    )

    embedding_service.ping = AsyncMock(side_effect=RuntimeError("failure"))

    service = build_service(
        embedding_service=embedding_service,
    )

    assert await service.ping() is False


# Santé


@pytest.mark.asyncio
async def test_health() -> None:
    """Vérifie le rapport de santé complet."""

    embedding_service = cast(
        EmbeddingService,
        MagicMock(
            spec=EmbeddingService,
        ),
    )

    embedding_service.ping = AsyncMock(return_value=True)

    cast(
        Any,
        embedding_service.is_ready,
    ).return_value = True

    milvus_service = cast(
        MilvusService,
        MagicMock(
            spec=MilvusService,
        ),
    )

    milvus_service.ping = AsyncMock(return_value=True)

    cast(
        Any,
        milvus_service.is_ready,
    ).return_value = True

    service = build_service(
        embedding_service=embedding_service,
        milvus_service=milvus_service,
    )

    service._register_search(
        result_count=2,
        duration_ms=12.34,
    )

    result = await service.health()

    assert result["service"] == "vector_search"
    assert result["is_ready"] is True
    assert result["available"] is True

    assert result["embedding_available"] is True

    assert result["milvus_available"] is True

    assert result["embedding_model"] == settings.embedding_model

    assert result["collection"] == settings.milvus_collection_name

    assert result["default_limit"] == settings.rag_search_top_k

    assert result["maximum_limit"] == settings.milvus_search_limit

    assert result["search_count"] == 1
    assert result["result_count"] == 2

    assert result["last_search_duration_ms"] == 12.34


@pytest.mark.asyncio
async def test_health_handles_embedding_exception() -> None:
    """Vérifie une erreur du healthcheck embedding."""

    embedding_service = cast(
        EmbeddingService,
        MagicMock(
            spec=EmbeddingService,
        ),
    )

    embedding_service.ping = AsyncMock(side_effect=RuntimeError("embedding failure"))

    cast(
        Any,
        embedding_service.is_ready,
    ).return_value = True

    milvus_service = cast(
        MilvusService,
        MagicMock(
            spec=MilvusService,
        ),
    )

    milvus_service.ping = AsyncMock(return_value=True)

    cast(
        Any,
        milvus_service.is_ready,
    ).return_value = True

    service = build_service(
        embedding_service=embedding_service,
        milvus_service=milvus_service,
    )

    result = await service.health()

    assert result["embedding_available"] is False

    assert result["milvus_available"] is True

    assert result["available"] is False


@pytest.mark.asyncio
async def test_health_handles_milvus_exception() -> None:
    """Vérifie une erreur du healthcheck Milvus."""

    embedding_service = cast(
        EmbeddingService,
        MagicMock(
            spec=EmbeddingService,
        ),
    )

    embedding_service.ping = AsyncMock(return_value=True)

    cast(
        Any,
        embedding_service.is_ready,
    ).return_value = True

    milvus_service = cast(
        MilvusService,
        MagicMock(
            spec=MilvusService,
        ),
    )

    milvus_service.ping = AsyncMock(side_effect=RuntimeError("milvus failure"))

    cast(
        Any,
        milvus_service.is_ready,
    ).return_value = True

    service = build_service(
        embedding_service=embedding_service,
        milvus_service=milvus_service,
    )

    result = await service.health()

    assert result["embedding_available"] is True

    assert result["milvus_available"] is False

    assert result["available"] is False
