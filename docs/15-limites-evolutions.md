# Limites actuelles et évolutions

[Sommaire](index.md) · [Qualité](13-qualite-tests.md) · [Inventaire](18-inventaire-sources.md)

## Pourquoi je rends ces limites visibles

Je préfère expliquer clairement ce qui reste incomplet plutôt que de donner
l’impression que l’ensemble du projet est stabilisé alors que certains éléments
doivent encore être consolidés.

Cette liste constitue mon plan de consolidation technique.

## Niveau de preuve

Les éléments consolidés ci-dessous correspondent au dernier état documentaire
disponible. Le code canonique et les rapports Ruff, Pyright et Pytest ne sont pas
inclus dans les pièces jointes de cette revue. Je distingue donc :

- **consolidé** : déclaré terminé dans l’état le plus récent ;
- **prouvé** : accompagné d’une sortie, d’une version et d’une date archivées ;
- **à vérifier** : dépend du dépôt, du frontend ou du déploiement non fourni.

Cette distinction ne remet pas en cause le travail réalisé ; elle empêche de
transformer un compte rendu en preuve technique sans les artefacts associés.

## Éléments consolidés

La consolidation du backend a permis de stabiliser plusieurs éléments
structurants du projet :

- les contrats publics et les schémas Pydantic ont été harmonisés ;
- les schémas d’erreur et les handlers FastAPI utilisent une enveloppe
  cohérente ;
- les routes publiques FastAPI et leur montage sous `/api` ont été vérifiés ;
- le routage LangGraph est couvert par des tests dédiés ;
- les statuts du workflow utilisent une énumération commune ;
- les modèles d’évaluation Stockfish sont alignés avec les données réellement
  produites par le service ;
- les imports des schémas utilisent l’organisation actuelle par sous-domaines ;
- `llm_num_predict` possède une seule définition canonique ;
- le nom de la collection Milvus est fourni par
  `Settings.milvus_collection_name` ;
- les anciennes constantes de collections Milvus spécialisées non utilisées
  ont été supprimées ;
- `rag_search_top_k` reste la limite par défaut des recherches vectorielles
  générales ;
- le workflow Wikichess sélectionne volontairement un seul document
  correspondant au contexte échiquéen ;
- `rag_max_selected_documents`, qui n’était pas consommé par le workflow,
  a été supprimé ;
- `max_agent_iterations` est transmis à LangGraph par `recursion_limit` ;
- le LLM est supervisé par le healthcheck et considéré comme une dépendance
  requise de l’application ;
- les requêtes HTTP disposent d’un `request_id` utilisé comme identifiant de
  corrélation jusqu’au workflow et à la persistance ;
- la journalisation finale d’une analyse utilise un résumé technique plutôt
  que l’état complet du workflow ;
- la notion d’`AnalysisMode`, qui ne pilotait aucune branche réelle du
  workflow, a été supprimée du contrat, de l’état, des réponses et de la
  persistance ;
- les champs et options liés aux positions similaires, qui n’étaient alimentés
  par aucune étape du workflow, ont été supprimés ;
- les appels de `MilvusService` ont été vérifiés contre les signatures de
  PyMilvus `3.0.0` réellement installé ;
- Ruff, Pyright et Pytest ont été exécutés à l’échelle du backend et des tests
  avec succès ;
- les tests de routage LangGraph couvrent actuellement 34 cas et sont tous
  validés.

## Priorité moyenne : supervision et observabilité

La supervision applicative couvre les principaux services et utilise un
`request_id` pour corréler les traitements d’une analyse.

La journalisation applicative évite également de consigner directement l’état
complet du workflow, la question utilisateur, la réponse générée ou le contenu
des documents récupérés.

Une observabilité plus complète reste cependant à mettre en place :

- définir des métriques applicatives et techniques ;
- mesurer les temps d’exécution des services externes et des étapes LangGraph ;
- centraliser les traces et les logs en environnement de déploiement ;
- définir des seuils et des alertes pour les services requis ;
- documenter le comportement attendu lorsqu’un service facultatif est
  indisponible ;
- définir des objectifs de latence, de disponibilité et de charge.

## Priorité moyenne : frontend Angular

Le frontend Angular doit encore être finalisé et validé avec le backend
stabilisé.

Il reste notamment à :

- aligner les modèles TypeScript avec les contrats API actuels ;
- vérifier l’intégration de l’échiquier `ngx-chessboard` retenu pour le projet ;
- valider la saisie et la transmission des positions FEN ;
- vérifier l’affichage des résultats Stockfish, Wikichess et des vidéos ;
- vérifier l’affichage de la réponse générée par le LLM ;
- tester les états de chargement et les erreurs API ;
- ajouter les tests nécessaires au périmètre pédagogique du frontend.

## Priorité basse : documentation et exploitation

Plusieurs éléments restent à documenter ou à définir avant une exploitation
plus complète du projet :

- documenter l’ingestion du corpus Wikichess et la construction de la
  collection vectorielle ;
- documenter précisément Docker, les réseaux, les volumes et le démarrage des
  services ;
- intégrer réellement les schémas utilisateur ou les retirer du périmètre ;
- définir l’authentification et l’autorisation si elles deviennent nécessaires ;
- définir la politique de conservation et de suppression des analyses ;
- documenter les dépendances externes et leur comportement en cas
  d’indisponibilité ;
- compléter l’observabilité avec des métriques, traces, tableaux de bord et
  alertes.

## Mon ordre de consolidation

1. finaliser et tester le frontend Angular ;
2. documenter l’ingestion du corpus Wikichess ;
3. documenter le déploiement Docker, les réseaux et les volumes ;
4. statuer sur les schémas utilisateur et leur périmètre ;
5. définir les besoins d’authentification, d’autorisation et de rétention ;
6. compléter l’observabilité et définir les objectifs de performance.
