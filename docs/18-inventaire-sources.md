# Inventaire des sources utilisées

[Sommaire](index.md) · [Limites](15-limites-evolutions.md)

## Pourquoi je conserve cet inventaire

Je relie chaque partie de la documentation aux sources disponibles afin de savoir ce que je peux confirmer et ce que je dois encore vérifier dans le dépôt canonique.

## Convention et documentation

| Source | Usage |
| --- | --- |
| `MISA.txt` | règles de développement MISA v2.0 |
| document de fonctionnement Angular | explication conceptuelle du frontend standalone |
| sorties Ruff/Vulture | problèmes de style et imports observés |
| sortie Pyright | erreurs de typage observées avant correctifs |
| dossier de correctifs Pyright | versions corrigées de plusieurs nœuds et de Milvus |
| état de consolidation du backend | décisions récentes sur contrats, routes, LLM, Milvus et tests |

## Core et API

| Module logique | Couverture |
| --- | --- |
| `app/core/config.py` | configuration Pydantic complète |
| `app/core/constants.py` | constantes API, MongoDB, Milvus, LLM, Lichess, YouTube et erreurs |
| `app/core/container.py` | composition des dépendances |
| `app/core/lifespan.py` | démarrage, santé, rollback et arrêt |
| `app/core/exceptions.py` | hiérarchie des erreurs |
| handlers FastAPI | enveloppes et traduction HTTP |
| route des services | endpoint local de supervision |

Le dernier état de consolidation déclare le routeur et les routes publiques
vérifiés sous `/api`. Leurs fichiers ne figurent pas dans les pièces jointes de
cette revue : le chemin exact doit être confirmé dans le dépôt canonique ou
l’OpenAPI générée.

## Services

| Module | Responsabilité |
| --- | --- |
| `analysis_service.py` | orchestration du graphe et réponse applicative |
| `chess_service.py` | positions, coups, notations et légalité |
| `vector_search_service.py` | recherche sémantique et Wikichess |
| `healthcheck_service.py` | agrégation de la disponibilité |

## Adapters

| Module | Intégration |
| --- | --- |
| `embedding_service.py` | Sentence Transformers |
| `lichess_service.py` | Lichess Explorer |
| `llm_service.py` | Ollama |
| `milvus_service.py` | Milvus |
| `mongodb_service.py` | MongoDB |
| `stockfish_service.py` | moteur UCI Stockfish |
| `youtube_service.py` | YouTube Data API |

## Agent LangGraph

| Module | Couverture |
| --- | --- |
| `graph.py` | nœuds, transitions et injection |
| `state.py` | options, contexte, état et métadonnées |
| `routing.py` | déclaré couvert par 34 tests ; corps et rapport non joints à cette revue |
| `A_validate_position.py` | validation FEN |
| `B_detect_theory.py` | ouverture Lichess |
| `C_engine_analysis.py` | analyse Stockfish |
| `D_unknown_position_analysis.py` | position inconnue |
| `E_retrieve_context.py` | contexte Wikichess |
| `F_retrieve_videos.py` | vidéos YouTube |
| `G_generate_response.py` | réponse LLM ou secours |
| `H_save_analysis.py` | sauvegarde MongoDB |

## Schémas joints

| Domaine | Modèles reçus |
| --- | --- |
| analyse | requête et réponse |
| évaluation | moteur, variante et enrichissement |
| position | FEN, échiquier et contexte |
| coups | coup, légal, joué, meilleur et statistiques |
| ouverture | identité, variantes, statistiques, théorie et détails |
| documents | document, chunk, résultat et contexte RAG |
| vidéos | chaîne, vidéo, recommandation et collection |
| utilisateur | utilisateur, préférences et profil |
| erreurs | erreur, validation et enveloppe |
| énumérations | modes, statuts, couleurs, notations et sources |

Ces schémas utilisent une organisation plus ancienne que les imports récents. Je les exploite pour comprendre le domaine, mais je signale les contrats qui ne correspondent plus exactement au backend.

## Date de référence

Mon état documentaire correspond aux fichiers disponibles le **18 août 2026**.
Une version ultérieure du dépôt doit être comparée à cet inventaire avant de
considérer la documentation comme normative.
