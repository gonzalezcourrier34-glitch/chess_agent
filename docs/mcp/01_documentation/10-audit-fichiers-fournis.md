# Audit des fichiers fournis

## 1. Inventaire

| Fichier reçu | Rôle observé | Points utiles | Limites majeures |
| --- | --- | --- | --- |
| `MISA.txt` | convention Python | structure, typage, lisibilité, responsabilité | pas de règles tests/sécurité/async spécifiques |
| `evaluation(1).py` | évaluations Stockfish/IA | score, type, profondeur, PV | cohérence PV et score à préciser |
| `user(1).py` | utilisateurs/préférences | personnalisation | RGPD/auth/persistance absents |
| `document(1).py` | documents RAG | metadata, chunks, similarité | licence, embedding/version absents |
| `analysis(1).py` | requête/réponse agrégée | contrat produit principal | enums dupliqués, idempotence absente |
| `video(1).py` | vidéos/recommandations | plateforme indépendante | aucun timestamp, segment, provenance ou job |
| `move(1).py` | coups/statistiques | UCI/SAN, légalité décrite | validation seulement syntaxique par longueur |
| `error(1).py` | erreurs | code/message/HTTP | intégration incohérente avec AnalysisResponse |
| `opening(1).py` | ouverture/théorie | ECO, variantes, plans | validation ECO et sources absentes |
| `position(1).py` | FEN/position | champs principaux | FEN faiblement validée |
| `enums(1).py` | valeurs communes | centralisation | doublons et non-utilisation dans analysis |

## 2. Résultat global

Les modules constituent une base lisible de DTO Pydantic. Ils montrent le domaine envisagé, mais ne prouvent pas :

- une route FastAPI ;
- un service métier ;
- un graphe LangGraph ;
- un client Lichess/YouTube ;
- Stockfish lancé via UCI ;
- MongoDB ou Milvus configurés ;
- un pipeline vidéo ;
- un serveur MCP ;
- des tests ;
- un déploiement Docker.

Le statut correct est donc **conception partielle des contrats**.

## 3. Écarts transverses

### 3.1 Enums dupliqués

`analysis(1).py` définit `AnalysisMode` et `AnalysisStatus` sous forme de `Literal`, alors que `enums(1).py` fournit des `StrEnum`. Les deux ne sont pas équivalents : l'enum inclut `RUNNING`, le Literal non. Il faut une source unique.

`PieceColor` et `ChessColor` portent les mêmes valeurs et descriptions. Conserver un seul type sauf différence métier documentée.

### 3.2 Validation métier insuffisante

- `FenRequest.fen` vérifie seulement une longueur minimale ;
- `Move.uci` vérifie une longueur 4-5 sans pattern ni légalité ;
- `from_square`/`to_square` acceptent n'importe quels deux caractères ;
- `eco` n'est pas contraint par un pattern A00-E99 ;
- URLs et emails sont inégalement typés ;
- dates vidéo/document sont des chaînes libres ;
- taux de résultats ne sont pas contrôlés comme ensemble.

La validation Pydantic doit être complétée par `python-chess` et des validateurs contextuels.

### 3.3 Configuration Pydantic inégale

Certains modèles interdisent les champs supplémentaires et/ou sont figés ; d'autres non. Les entrées externes doivent refuser les champs inconnus. La mutabilité doit refléter le rôle, pas varier sans justification.

### 3.4 Erreurs incohérentes

`ErrorResponse` définit une enveloppe structurée, mais `AnalysisResponse.error` est une simple chaîne. Choisir un modèle d'erreur unique pour FastAPI et mapper proprement vers les erreurs MCP.

### 3.5 Idempotence et traçabilité absentes

`AnalysisRequest` ne contient ni `request_id`, ni utilisateur, langue, difficulté, budget moteur ou options. Les discussions antérieures évoquaient une sauvegarde idempotente ; elle n'est pas visible dans les fichiers reçus.

### 3.6 Sources et versions absentes

Une réponse pédagogique doit indiquer : provenance Lichess/Stockfish/RAG/YouTube, timestamp d'accès, version moteur, profondeur/temps, document/chunk et score. Les contrats ne couvrent pas entièrement cette traçabilité.

## 4. Écarts par fichier

### `evaluation(1).py`

- `Evaluation.score: float` ne précise pas l'unité selon `CENTIPAWN` ou `MATE` ; un entier ou union discriminée serait plus sûr.
- `PrincipalVariation` embarque une `Evaluation`, et `EngineAnalysis` en embarque une autre ; définir si elles doivent être identiques.
- `BestMove` contient déjà `principal_variation`, créant une autre duplication.
- limites maximales de profondeur, noeuds et temps non définies.

### `user(1).py`

- identifiant format libre ;
- `preferred_color` est une chaîne au lieu de `ChessColor` ;
- langue libre au lieu d'un code validé ;
- email personnel sans politique de rétention ;
- absence de consentements/rôles/tenant si nécessaires.

### `document(1).py`

- `publication_date` devrait être un type date/temps ;
- `url` devrait être validée ;
- licence, droits, hash, version d'embedding et modèle manquent ;
- `Document.content` intégral dans chaque résultat peut gonfler les réponses ;
- `RetrievedDocument` devrait privilégier le chunk/extrait sourcé.

### `analysis(1).py`

- duplication de modes/statuts ;
- `AnalysisRequest` trop minimal ;
- pas de `request_id`, `created_at`, `sources`, `warnings`, `partial` ;
- listes `Document` et `Video` perdent similarité/raison de recommandation ;
- réponse success/error non discriminée, ce qui autorise des combinaisons incohérentes ;
- erreurs standard non réutilisées.

### `video(1).py`

Écart critique par rapport à la mission : aucun champ `timestamp`, `start_ms`, `end_ms`, `position_key`, `fen`, `confidence`, `rights_basis`, `asset_id`, `job_id` ou `index_version`. Il faut ajouter des contrats dédiés sans surcharger `Video`.

`published_at` devrait être temporel ; URLs validées ; la dépendance au nombre d'abonnés est volatile et peut être absente.

### `move(1).py`

- cohérence UCI/SAN/cases non vérifiée ;
- promotion non discriminée ;
- `score` et type d'évaluation dupliquent `Evaluation` ;
- taux peuvent totaliser autre chose que 100 ;
- aucune source/période pour les statistiques.

### `error(1).py`

- nom `Error` très générique ;
- absence de `correlation_id`, `retryable`, `details` structurés et dépendance ;
- `status_code` HTTP ne s'applique pas directement au transport MCP ; séparer erreur métier et mapping transport.

### `opening(1).py`

- ECO et FEN non validés ;
- coups sans type notation ;
- statistiques dupliquées avec celles des coups ;
- théorie sans sources ;
- difficulté par défaut peut être arbitraire.

### `position(1).py`

- validation FEN faible ;
- `active_color` blanc/noir nécessite un mapping vers `w/b` ;
- castling rights chaîne libre ;
- en passant chaîne libre ;
- état nul/game over peut être incohérent sans calcul `python-chess` ;
- import multi-ligne inutilement développé au regard de deux symboles, point mineur de style.

### `enums(1).py`

- `PieceColor`/`ChessColor` dupliqués ;
- `SearchSource` mélange base, APIs et moteur, utiles mais de natures différentes ;
- types vidéo/états de job/position partielle absents ;
- ligne vide après les commentaires de section à homogénéiser selon MISA.

## 5. Schémas à ajouter

- `AnalysisOptions`, `AnalysisSource`, `AnalysisWarning` ;
- `VideoAsset`, `RightsMetadata` ;
- `VideoIndexJob`, `VideoIndexStatus` ;
- `BoardObservation`, `DetectedPosition` ;
- `VideoPositionSegment`, `VideoPositionMatch` ;
- `ModelProvenance`, `IndexProvenance` ;
- `ServiceError` séparé du mapping HTTP/MCP ;
- unions discriminées success/error et partial/full position.

Un exemple JSON contractuel figure dans `02_contrats/schemas-video-index.json`.

## 6. Priorités de correction

| Priorité | Action | Motif |
| --- | --- | --- |
| P0 | unifier enums et erreurs | évite divergence de contrat |
| P0 | ajouter provenance/droits/timestamps/jobs | indispensable à la mission vidéo |
| P0 | valider FEN/coups par python-chess | sûreté fonctionnelle |
| P1 | ajouter request_id, sources, warnings | idempotence et preuve |
| P1 | unions discriminées de réponses | états impossibles éliminés |
| P1 | types URL/date/langue/IDs | validation externe |
| P2 | réduire duplications statistiques/PV | maintenabilité |
| P2 | homogénéiser frozen/extra | cohérence MISA |

## 7. Conclusion d'audit

La base est exploitable pour démarrer une refonte de contrats, pas pour affirmer la faisabilité déjà démontrée. Le premier sprint technique doit corriger les P0 avant d'exposer une API ou un serveur MCP stable.
