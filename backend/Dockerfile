FROM python:3.12-slim

# Environnement

ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1
ENV UV_LINK_MODE=copy
ENV PATH="/app/.venv/bin:$PATH"

WORKDIR /app


# Dépendances système

RUN apt-get update \
    && apt-get install -y --no-install-recommends \
        build-essential \
        curl \
        stockfish \
    && rm -rf /var/lib/apt/lists/*


# Gestionnaire Python

RUN pip install \
    --no-cache-dir \
    --root-user-action=ignore \
    uv


# Dépendances Python

COPY pyproject.toml uv.lock ./

RUN uv sync \
    --frozen \
    --no-dev \
    --no-install-project


# Backend

COPY backend ./backend


# Données

RUN mkdir -p \
    /app/data/raw/wikichess \
    /app/data/processed/chunks


# API

EXPOSE 8000

CMD ["uvicorn", "app.main:app", "--app-dir", "backend", "--host", "0.0.0.0", "--port", "8000"]