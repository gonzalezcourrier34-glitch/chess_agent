"""Routeur principal de l'API version 1.

Ce module centralise :

- l'enregistrement des routeurs spécialisés ;
- la définition des préfixes fonctionnels ;
- l'organisation des tags de la documentation Swagger.

Il ne contient aucune logique métier.

Chaque routeur spécialisé reste responsable de la définition de ses
endpoints, de ses modèles de réponse et de sa documentation OpenAPI.
"""

from __future__ import annotations

from fastapi import APIRouter

from app.api.v1.endpoints.route_analysis import router as analysis_router
from app.api.v1.endpoints.route_engine import router as engine_router
from app.api.v1.endpoints.route_healthcheck import router as healthcheck_router
from app.api.v1.endpoints.route_history import router as history_router
from app.api.v1.endpoints.route_opening import router as opening_router
from app.api.v1.endpoints.route_position import router as position_router
from app.api.v1.endpoints.route_search_videos import router as search_videos_router
from app.api.v1.endpoints.route_services import router as services_router
from app.api.v1.endpoints.route_vector_search import router as search_documents_router

# Tags

ANALYSIS_TAG = "Analysis"
ENGINE_TAG = "Engine"
HEALTHCHECK_TAG = "Healthcheck"
HISTORY_TAG = "History"
OPENING_TAG = "Opening"
POSITION_TAG = "Position"
SEARCH_TAG = "Search"
SERVICES_TAG = "Services"


# Routeur
api_router = APIRouter(prefix="/v1")


# Analyse

api_router.include_router(analysis_router, prefix="/analysis", tags=[ANALYSIS_TAG])


# Moteur

api_router.include_router(engine_router, prefix="/engine", tags=[ENGINE_TAG])


# Supervision

api_router.include_router(healthcheck_router, prefix="", tags=[HEALTHCHECK_TAG])


# Historique

api_router.include_router(history_router, prefix="/history", tags=[HISTORY_TAG])


# Ouvertures

api_router.include_router(opening_router, prefix="/openings", tags=[OPENING_TAG])


# Position

api_router.include_router(position_router, prefix="/position", tags=[POSITION_TAG])


# Recherche documentaire

api_router.include_router(search_documents_router, prefix="/search", tags=[SEARCH_TAG])


# Recherche vidéo

api_router.include_router(search_videos_router, prefix="/search", tags=[SEARCH_TAG])


# Services

api_router.include_router(services_router, prefix="/services", tags=[SERVICES_TAG])
