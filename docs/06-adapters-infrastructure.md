# Adapters et infrastructure

[Sommaire](index.md) · [Services](05-services-applicatifs.md) · [Cycle de vie](11-cycle-vie-configuration-supervision.md)

## Pourquoi j’utilise des adapters

J’encapsule chaque technologie externe dans un adapter. Mon workflow manipule ainsi des modèles du projet et des exceptions cohérentes, sans dépendre directement des formats HTTP, UCI, Milvus ou MongoDB.

**Statut : Confirmé.**

## Catalogue

| Adapter | Technologie | Opérations principales |
| --- | --- | --- |
| `EmbeddingService` | Sentence Transformers | démarrer, encoder un texte ou un lot, obtenir la dimension |
| `LichessService` | Lichess Explorer HTTP | détecter une ouverture et ses statistiques |
| `StockfishService` | moteur UCI | analyser une position en MultiPV |
| `MilvusService` | PyMilvus | créer la collection, insérer, upsert, rechercher, lire, supprimer |
| `LLMService` | Ollama HTTP | vérifier le modèle et générer un texte |
| `YoutubeService` | API YouTube Data | rechercher, enrichir et classer des vidéos |
| `MongoDBService` | PyMongo/MongoDB | enregistrer, lire, lister et supprimer des analyses |

## Embeddings

`EmbeddingService` charge le modèle configuré de manière protégée par un verrou. Il distingue l’encodage d’une requête de celui d’un lot de documents, normalise les textes, impose une taille maximale de lot et vérifie que chaque vecteur respecte la dimension annoncée.

Il expose des métriques simples : dimension et nombre de vecteurs générés.

## Lichess

`LichessService` interroge les bases Explorer. Il gère :

- un client HTTP asynchrone ;
- un jeton facultatif ;
- des délais configurables ;
- des nouvelles tentatives exponentielles sur les statuts transitoires ;
- la validation du JSON ;
- la construction de l’ouverture, des statistiques et des variantes.

Une absence d’ouverture devient `OpeningNotFoundError`. Une panne réseau ou une réponse invalide devient une exception Lichess spécialisée.

## Stockfish

`StockfishService` démarre un moteur UCI avec le chemin, les threads et la mémoire configurés. Pour chaque analyse, il :

- applique une profondeur et un nombre de coups candidats ;
- lance le calcul hors de la boucle asynchrone ;
- impose un timeout ;
- interrompt réellement le moteur si le calcul bloque ;
- convertit le score en centipions ou mat ;
- construit le meilleur coup, la variante principale et les alternatives ;
- suit le nombre d’analyses et la dernière durée.

## Milvus

`MilvusService` crée le client, la collection et l’index en fonction de la dimension réelle du service d’embedding. Il supporte `COSINE`, `IP` ou `L2` et les index `HNSW`, `IVF_FLAT` ou `AUTOINDEX`.

Avant chaque écriture, il valide l’identifiant, le contenu, la source, le vecteur, les métadonnées et l’horodatage. Après une recherche, il transforme la distance en similarité normalisée et rend les métadonnées compatibles JSON.

## Ollama

`LLMService` vérifie le fournisseur, l’URL et le nom du modèle. Au démarrage, il consulte `/api/tags` pour confirmer que le modèle est disponible. Pour la génération, il envoie un payload à `/api/chat`, sérialise les appels par verrou, impose un timeout et vérifie la réponse.

Il retire également les balises ou blocs `<think>` afin de ne pas renvoyer le raisonnement interne. Il suit le nombre de générations, les échecs et la durée moyenne.

## YouTube

`YoutubeService` recherche des vidéos, récupère leur durée, construit les URLs, extrait les miniatures et calcule un score de pertinence. Il filtre les contenus qui ne possèdent pas les marqueurs échiquéens attendus et conserve les résultats les plus pédagogiques.

Il traite séparément les erreurs de configuration, de quota, de timeout, d’indisponibilité et de réponse. Les statuts transitoires peuvent déclencher une nouvelle tentative.

## MongoDB

`MongoDBService` prépare les index, sérialise `AnalysisRecord`, garantit l’idempotence par `request_id`, reconstruit les modèles Pydantic à la lecture et fournit un historique paginé. Le détail se trouve dans [10 — Persistance MongoDB](10-persistance-mongodb.md).

## Stratégie de dégradation

| Adapter | Exigence au démarrage | Repli fonctionnel |
| --- | --- | --- |
| MongoDB | obligatoire | aucun au démarrage |
| embeddings | obligatoire | aucun |
| Milvus | obligatoire | aucun |
| Stockfish | obligatoire | aucun |
| Ollama | obligatoire au démarrage | réponse de secours si un appel échoue après le démarrage |
| Lichess | facultatif | analyse sans théorie distante |
| YouTube | facultatif | réponse sans vidéo |
