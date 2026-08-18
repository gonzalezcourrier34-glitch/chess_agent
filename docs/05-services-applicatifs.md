# Services applicatifs

[Sommaire](index.md) · [Architecture](02-architecture-technique.md) · [Adapters](06-adapters-infrastructure.md)

## Le rôle de mes services

Mes services portent les cas d’usage de l’application. Ils ne connaissent pas le protocole HTTP de FastAPI et s’appuient sur des schémas métier. Cette séparation me permet de les tester sans démarrer un serveur web.

**Statut : Confirmé.**

## `AnalysisService`

`AnalysisService` est le point d’entrée de l’analyse complète. Quand j’appelle `analyze(request)`, le service :

1. crée un `request_id` UUID ;
2. normalise la question, la langue et l’historique de coups ;
3. construit les `AnalysisOptions` internes ;
4. construit `ChessAnalysisState` avec le statut initial ;
5. prépare le `RunnableConfig` et son `thread_id` ;
6. exécute le graphe compilé ;
7. valide l’état final renvoyé par LangGraph ;
8. complète les métadonnées de durée et de modèles ;
9. construit `AnalysisResponse`.

Sa réponse expose le statut, la FEN, l’ouverture, l’évaluation, les documents,
les vidéos, l’explication, l’identifiant de sauvegarde et le premier message
d’erreur utile. Le mode d’analyse n’appartient plus au contrat récent, car il ne
pilotait aucune branche effective.

Le service suit aussi le nombre d’analyses et la durée de la dernière exécution.

## `ChessService`

`ChessService` encapsule la manipulation métier de l’échiquier avec `python-chess`. Il fournit notamment :

- la création et la validation d’une position ;
- la couleur active ;
- le contexte de la position : échec, mat, pat, partie terminée et nulle ;
- la liste des coups légaux ;
- la vérification d’un coup ;
- la construction d’un coup enrichi ;
- l’analyse de notations UCI et SAN ;
- la conversion UCI ↔ SAN ;
- la conversion d’un historique UCI vers SAN ;
- l’application d’un coup et la FEN résultante.

Ce service ne lance pas Stockfish. Il vérifie la légalité et la représentation des positions et des coups.

## `VectorSearchService`

`VectorSearchService` coordonne `EmbeddingService` et `MilvusService`. Il :

- normalise la requête et la limite ;
- génère le vecteur de requête ;
- construit les filtres Milvus ;
- exécute la recherche ;
- transforme les résultats techniques en `VectorSearchResult` ;
- contrôle les correspondances exactes par code ECO ou `moves_path` ;
- mesure le nombre de recherches, le nombre de résultats et la dernière durée.

Ses opérations publiques principales sont :

| Méthode | Usage |
| --- | --- |
| `search()` | recherche sémantique générale |
| `search_with_filter()` | recherche dans un sous-ensemble Milvus |
| `search_wikichess()` | stratégie ECO puis coups en repli |
| `search_by_eco()` | filtre exact sur le code ECO |
| `search_by_moves()` | filtre et vérification exacte de la séquence |

## `HealthcheckService`

`HealthcheckService` exécute en parallèle les contrôles de MongoDB, Milvus, embeddings, Stockfish, Lichess, YouTube et LangGraph. Une exception sur un service ne bloque pas les autres vérifications.

Pour l’état global, je considère actuellement comme requis :

- MongoDB ;
- Milvus ;
- le service d’embedding ;
- Stockfish ;
- le LLM ;
- LangGraph.

Lichess et YouTube peuvent être indisponibles sans empêcher l’application de
démarrer. Le service construit ensuite un `HealthcheckResponse` avec le nom, la
version, l’environnement, le modèle d’embedding, la collection Milvus et les
états détaillés.

## Les contrôles communs

Mes services exposent, selon leur nature :

- `is_ready()` pour vérifier l’état local ;
- `ping()` pour effectuer un contrôle léger ;
- `health()` pour retourner un diagnostic détaillé.

Je distingue ces trois niveaux afin qu’un objet construit ne soit pas automatiquement considéré comme joignable.
