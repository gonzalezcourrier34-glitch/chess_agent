"""Tests unitaires du service d'embeddings Chess Agent."""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock

import pytest
from app.adapters.embedding_service import (
    EmbeddingService,
)
from app.core.exceptions import (
    ConfigurationError,
    EmbeddingGenerationError,
    EmbeddingModelUnavailableError,
)

# Constantes

EMBEDDING_DIMENSION = 3

VALID_VECTOR = [
    0.1,
    0.2,
    0.3,
]

VALID_DOCUMENT_VECTORS = [
    [0.1, 0.2, 0.3],
    [0.4, 0.5, 0.6],
]


# Fixtures


@pytest.fixture
def service() -> EmbeddingService:
    """Construit un service non initialisé."""

    return EmbeddingService()


@pytest.fixture
def model() -> MagicMock:
    """Construit un faux modèle SentenceTransformer."""

    mocked_model = MagicMock()

    mocked_model.get_embedding_dimension.return_value = EMBEDDING_DIMENSION

    mocked_model.encode_query.return_value = VALID_VECTOR

    mocked_model.encode_document.return_value = VALID_DOCUMENT_VECTORS

    return mocked_model


# Construction


def test_service_is_not_ready_after_creation(
    service: EmbeddingService,
) -> None:
    """Vérifie l'état initial du service."""

    assert service.is_ready() is False
    assert service.get_generated_count() == 0


def test_get_dimension_fails_before_initialization(
    service: EmbeddingService,
) -> None:
    """Vérifie qu'aucune dimension n'existe avant le chargement."""

    with pytest.raises(ConfigurationError):
        service.get_dimension()


# Cycle de vie


@pytest.mark.asyncio
async def test_start_loads_model(
    service: EmbeddingService,
    model: MagicMock,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Vérifie que le démarrage charge le modèle."""

    monkeypatch.setattr(
        "app.adapters.embedding_service.SentenceTransformer",
        lambda *args, **kwargs: model,
    )

    await service.start()

    assert service.is_ready() is True
    assert service.get_dimension() == EMBEDDING_DIMENSION


@pytest.mark.asyncio
async def test_start_is_idempotent(
    service: EmbeddingService,
    model: MagicMock,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Vérifie qu'un second démarrage ne recharge pas le modèle."""

    constructor = MagicMock(
        return_value=model,
    )

    monkeypatch.setattr(
        "app.adapters.embedding_service.SentenceTransformer",
        constructor,
    )

    await service.start()
    await service.start()

    assert constructor.call_count == 1


@pytest.mark.asyncio
async def test_start_fails_when_model_has_no_dimension(
    service: EmbeddingService,
    model: MagicMock,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Vérifie le rejet d'un modèle sans dimension valide."""

    model.get_embedding_dimension.return_value = None

    monkeypatch.setattr(
        "app.adapters.embedding_service.SentenceTransformer",
        lambda *args, **kwargs: model,
    )

    with pytest.raises(EmbeddingModelUnavailableError):
        await service.start()


@pytest.mark.asyncio
async def test_start_fails_when_model_loading_fails(
    service: EmbeddingService,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Vérifie la traduction d'une erreur de chargement."""

    def raise_error(
        *args: object,
        **kwargs: object,
    ) -> None:
        raise RuntimeError("model unavailable")

    monkeypatch.setattr(
        "app.adapters.embedding_service.SentenceTransformer",
        raise_error,
    )

    with pytest.raises(EmbeddingModelUnavailableError):
        await service.start()


@pytest.mark.asyncio
async def test_close_releases_model(
    service: EmbeddingService,
    model: MagicMock,
) -> None:
    """Vérifie que close remet le service à l'état non prêt."""

    service._model = model
    service._dimension = EMBEDDING_DIMENSION

    await service.close()

    assert service.is_ready() is False

    with pytest.raises(ConfigurationError):
        service.get_dimension()


@pytest.mark.asyncio
async def test_initialize_calls_start(
    service: EmbeddingService,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Vérifie l'alias initialize."""

    start = AsyncMock()

    monkeypatch.setattr(
        service,
        "start",
        start,
    )

    await service.initialize()

    start.assert_awaited_once()


@pytest.mark.asyncio
async def test_shutdown_calls_close(
    service: EmbeddingService,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Vérifie l'alias shutdown."""

    close = AsyncMock()

    monkeypatch.setattr(
        service,
        "close",
        close,
    )

    await service.shutdown()

    close.assert_awaited_once()


# Accès au modèle


def test_get_model_fails_when_service_is_not_started(
    service: EmbeddingService,
) -> None:
    """Vérifie qu'un modèle non chargé ne peut pas être récupéré."""

    with pytest.raises(ConfigurationError):
        service._get_model()


def test_get_model_returns_loaded_model(
    service: EmbeddingService,
    model: MagicMock,
) -> None:
    """Vérifie la récupération d'un modèle chargé."""

    service._model = model

    assert service._get_model() is model


# Normalisation


def test_normalize_text_strips_spaces(
    service: EmbeddingService,
) -> None:
    """Vérifie la normalisation des espaces."""

    result = service._normalize_text(
        "   Ruy Lopez   ",
        operation="test",
    )

    assert result == "Ruy Lopez"


def test_normalize_text_rejects_empty_text(
    service: EmbeddingService,
) -> None:
    """Vérifie qu'un texte vide est refusé."""

    with pytest.raises(EmbeddingGenerationError):
        service._normalize_text(
            "   ",
            operation="test",
        )


def test_normalize_text_rejects_non_string(
    service: EmbeddingService,
) -> None:
    """Vérifie qu'une entrée non textuelle est refusée."""

    with pytest.raises(EmbeddingGenerationError):
        service._normalize_text(
            42,  # type: ignore[arg-type]
            operation="test",
        )


def test_normalize_text_rejects_text_too_long(
    service: EmbeddingService,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Vérifie la limite de longueur."""

    from app.adapters.embedding_service import settings

    test_settings = settings.model_copy(
        update={
            "embedding_max_text_length": 5,
        }
    )

    monkeypatch.setattr(
        "app.adapters.embedding_service.settings",
        test_settings,
    )

    with pytest.raises(EmbeddingGenerationError):
        service._normalize_text(
            "123456",
            operation="test",
        )


def test_normalize_texts_returns_normalized_list(
    service: EmbeddingService,
) -> None:
    """Vérifie la normalisation d'un lot."""

    result = service._normalize_texts(
        [
            "  one  ",
            " two ",
        ]
    )

    assert result == [
        "one",
        "two",
    ]


def test_normalize_texts_reports_invalid_index(
    service: EmbeddingService,
) -> None:
    """Vérifie le rejet d'un élément invalide dans un lot."""

    with pytest.raises(EmbeddingGenerationError):
        service._normalize_texts(
            [
                "valid",
                "   ",
            ]
        )


# Validation des lots


def test_validate_batch_accepts_valid_batch(
    service: EmbeddingService,
) -> None:
    """Vérifie qu'un lot valide est accepté."""

    service._validate_batch(
        [
            "one",
            "two",
        ]
    )


def test_validate_batch_rejects_string(
    service: EmbeddingService,
) -> None:
    """Vérifie qu'une chaîne seule n'est pas un lot."""

    with pytest.raises(EmbeddingGenerationError):
        service._validate_batch(
            "not-a-batch"  # type: ignore[arg-type]
        )


def test_validate_batch_rejects_oversized_batch(
    service: EmbeddingService,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Vérifie la taille maximale d'un lot."""

    from app.adapters.embedding_service import settings

    test_settings = settings.model_copy(
        update={
            "embedding_max_batch_size": 1,
        }
    )

    monkeypatch.setattr(
        "app.adapters.embedding_service.settings",
        test_settings,
    )

    with pytest.raises(EmbeddingGenerationError):
        service._validate_batch(
            [
                "one",
                "two",
            ]
        )


# Conversion


def test_convert_number_accepts_numeric_value(
    service: EmbeddingService,
) -> None:
    """Vérifie la conversion d'une valeur numérique."""

    result = service._convert_number(
        1,
        operation="test",
    )

    assert result == 1.0


def test_convert_number_rejects_boolean(
    service: EmbeddingService,
) -> None:
    """Vérifie qu'un booléen n'est pas accepté comme composante."""

    with pytest.raises(EmbeddingGenerationError):
        service._convert_number(
            True,
            operation="test",
        )


def test_convert_number_rejects_non_numeric_value(
    service: EmbeddingService,
) -> None:
    """Vérifie le rejet d'une valeur non numérique."""

    with pytest.raises(EmbeddingGenerationError):
        service._convert_number(
            "abc",
            operation="test",
        )


def test_convert_number_rejects_non_finite_value(
    service: EmbeddingService,
) -> None:
    """Vérifie le rejet d'une valeur infinie."""

    with pytest.raises(EmbeddingGenerationError):
        service._convert_number(
            float("inf"),
            operation="test",
        )


def test_convert_embedding_returns_float_list(
    service: EmbeddingService,
) -> None:
    """Vérifie la conversion d'un embedding."""

    result = service._convert_embedding(
        [
            1,
            2.5,
            3,
        ],
        operation="test",
    )

    assert result == [
        1.0,
        2.5,
        3.0,
    ]


def test_convert_embedding_rejects_mapping(
    service: EmbeddingService,
) -> None:
    """Vérifie qu'un mapping n'est pas un embedding valide."""

    with pytest.raises(EmbeddingGenerationError):
        service._convert_embedding(
            {
                "value": 1,
            },
            operation="test",
        )


def test_convert_embeddings_returns_batch(
    service: EmbeddingService,
) -> None:
    """Vérifie la conversion d'un lot d'embeddings."""

    result = service._convert_embeddings(
        [
            [1, 2],
            [3, 4],
        ],
        operation="test",
    )

    assert result == [
        [1.0, 2.0],
        [3.0, 4.0],
    ]


# Dimensions


def test_validate_embedding_dimension_accepts_valid_dimension(
    service: EmbeddingService,
) -> None:
    """Vérifie une dimension valide."""

    service._dimension = 3

    service._validate_embedding_dimension(
        [0.1, 0.2, 0.3],
        operation="test",
    )


def test_validate_embedding_dimension_rejects_invalid_dimension(
    service: EmbeddingService,
) -> None:
    """Vérifie le rejet d'une dimension incorrecte."""

    service._dimension = 3

    with pytest.raises(EmbeddingGenerationError):
        service._validate_embedding_dimension(
            [0.1, 0.2],
            operation="test",
        )


def test_validate_embeddings_rejects_invalid_count(
    service: EmbeddingService,
) -> None:
    """Vérifie le nombre d'embeddings retournés."""

    service._dimension = 3

    with pytest.raises(EmbeddingGenerationError):
        service._validate_embeddings(
            [
                [0.1, 0.2, 0.3],
            ],
            expected_count=2,
            operation="test",
        )


# Génération d'un embedding


@pytest.mark.asyncio
async def test_generate_embedding_returns_vector(
    service: EmbeddingService,
    model: MagicMock,
) -> None:
    """Vérifie la génération d'un embedding de requête."""

    service._model = model
    service._dimension = EMBEDDING_DIMENSION

    result = await service.generate_embedding("Ruy Lopez")

    assert result == VALID_VECTOR
    assert service.get_generated_count() == 1

    model.encode_query.assert_called_once()


@pytest.mark.asyncio
async def test_generate_embedding_without_count_does_not_increment_counter(
    service: EmbeddingService,
    model: MagicMock,
) -> None:
    """Vérifie l'option count=False."""

    service._model = model
    service._dimension = EMBEDDING_DIMENSION

    result = await service.generate_embedding(
        "Ruy Lopez",
        count=False,
    )

    assert result == VALID_VECTOR
    assert service.get_generated_count() == 0


@pytest.mark.asyncio
async def test_generate_embedding_translates_model_error(
    service: EmbeddingService,
    model: MagicMock,
) -> None:
    """Vérifie la traduction d'une erreur du modèle."""

    model.encode_query.side_effect = RuntimeError("encoding failure")

    service._model = model
    service._dimension = EMBEDDING_DIMENSION

    with pytest.raises(EmbeddingGenerationError):
        await service.generate_embedding("Ruy Lopez")


# Génération de documents


@pytest.mark.asyncio
async def test_generate_embeddings_returns_vectors(
    service: EmbeddingService,
    model: MagicMock,
) -> None:
    """Vérifie la génération d'un lot d'embeddings."""

    service._model = model
    service._dimension = EMBEDDING_DIMENSION

    result = await service.generate_embeddings(
        [
            "Ruy Lopez",
            "Sicilian Defence",
        ]
    )

    assert result == VALID_DOCUMENT_VECTORS
    assert service.get_generated_count() == 2

    model.encode_document.assert_called_once()


@pytest.mark.asyncio
async def test_generate_embeddings_returns_empty_list_for_empty_batch(
    service: EmbeddingService,
) -> None:
    """Vérifie qu'un lot vide ne déclenche aucun chargement."""

    result = await service.generate_embeddings([])

    assert result == []
    assert service.get_generated_count() == 0


@pytest.mark.asyncio
async def test_generate_embeddings_rejects_wrong_embedding_count(
    service: EmbeddingService,
    model: MagicMock,
) -> None:
    """Vérifie le nombre de vecteurs générés."""

    model.encode_document.return_value = [
        VALID_VECTOR,
    ]

    service._model = model
    service._dimension = EMBEDDING_DIMENSION

    with pytest.raises(EmbeddingGenerationError):
        await service.generate_embeddings(
            [
                "one",
                "two",
            ]
        )


@pytest.mark.asyncio
async def test_generate_embeddings_rejects_wrong_dimension(
    service: EmbeddingService,
    model: MagicMock,
) -> None:
    """Vérifie les dimensions du lot généré."""

    model.encode_document.return_value = [
        [0.1, 0.2],
    ]

    service._model = model
    service._dimension = EMBEDDING_DIMENSION

    with pytest.raises(EmbeddingGenerationError):
        await service.generate_embeddings(
            [
                "one",
            ]
        )


# Informations


def test_get_generated_count_returns_current_value(
    service: EmbeddingService,
) -> None:
    """Vérifie le compteur d'embeddings."""

    service._generated_embeddings = 12

    assert service.get_generated_count() == 12


def test_is_ready_returns_true_when_model_and_dimension_exist(
    service: EmbeddingService,
    model: MagicMock,
) -> None:
    """Vérifie l'état prêt."""

    service._model = model
    service._dimension = EMBEDDING_DIMENSION

    assert service.is_ready() is True


# Santé


@pytest.mark.asyncio
async def test_ping_returns_true_when_embedding_is_valid(
    service: EmbeddingService,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Vérifie un healthcheck réussi."""

    service._dimension = EMBEDDING_DIMENSION

    generate_embedding = AsyncMock(return_value=VALID_VECTOR)

    monkeypatch.setattr(
        service,
        "generate_embedding",
        generate_embedding,
    )

    assert await service.ping() is True

    generate_embedding.assert_awaited_once_with(
        "chess",
        count=False,
    )


@pytest.mark.asyncio
async def test_ping_returns_false_on_embedding_error(
    service: EmbeddingService,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Vérifie un healthcheck en erreur."""

    generate_embedding = AsyncMock(side_effect=EmbeddingGenerationError())

    monkeypatch.setattr(
        service,
        "generate_embedding",
        generate_embedding,
    )

    assert await service.ping() is False


@pytest.mark.asyncio
async def test_ping_returns_false_for_wrong_dimension(
    service: EmbeddingService,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Vérifie le rejet d'un embedding de mauvaise dimension."""

    service._dimension = EMBEDDING_DIMENSION

    generate_embedding = AsyncMock(
        return_value=[
            0.1,
            0.2,
        ]
    )

    monkeypatch.setattr(
        service,
        "generate_embedding",
        generate_embedding,
    )

    assert await service.ping() is False


@pytest.mark.asyncio
async def test_health_returns_service_status(
    service: EmbeddingService,
    model: MagicMock,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Vérifie la structure de l'état de santé."""

    service._model = model
    service._dimension = EMBEDDING_DIMENSION
    service._generated_embeddings = 4

    ping = AsyncMock(return_value=True)

    monkeypatch.setattr(
        service,
        "ping",
        ping,
    )

    status = await service.health()

    assert status["service"] == "embedding"
    assert status["is_ready"] is True
    assert status["available"] is True
    assert status["dimension"] == EMBEDDING_DIMENSION
    assert status["generated_embeddings"] == 4
