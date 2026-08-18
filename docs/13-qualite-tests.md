# Qualité et tests

[Sommaire](index.md) · [Convention MISA](14-convention-misa.md) · [Limites](15-limites-evolutions.md)

## Ma démarche

Je vérifie le projet à plusieurs niveaux, car un module peut être correct seul tout en cassant une signature, un import ou un contrat dans un autre fichier.

## Les niveaux de contrôle

| Niveau | Ce que je vérifie |
| --- | --- |
| syntaxe | tous les modules peuvent être compilés |
| formatage | le style reste homogène |
| lint | imports, erreurs simples et conventions |
| typage | cohérence entre les signatures et les bibliothèques |
| unitaire | comportement isolé d’un service ou d’un nœud |
| intégration | collaboration entre FastAPI, LangGraph et les adapters |
| contrat | stabilité des modèles JSON |
| end-to-end | parcours utilisateur complet |

## Les outils observés

Les sorties reçues montrent l’utilisation de Ruff, Vulture et Pyright. Une exécution Pyright a révélé des erreurs dans Milvus et plusieurs nœuds : incompatibilité entre `TypedDict` et les signatures PyMilvus, paramètres génériques manquants et accès possibles à `None`.

Des versions correctives ont ensuite été préparées pour :

- les nœuds A, B, C, E, F, G et H ;
- `milvus_service.py` ;
- les stubs ciblés de validation.

Le dernier état de consolidation déclare que Ruff, Pyright et Pytest passent à
l’échelle du backend et des tests, avec 34 cas de routage LangGraph validés. Les
rapports correspondants ne font pas partie des pièces jointes actuelles. Je
présente donc ce résultat comme **déclaré consolidé** et je demande les sorties
d’exécution pour en faire une preuve archivée.

## Les commandes de référence

À exécuter depuis le dépôt réel avec les scripts définis par le projet :

```bash
uv run ruff check backend
uv run ruff format --check backend
uv run pyright backend
uv run pytest
```

Je n’annonce un résultat propre en soutenance qu’avec la sortie globale, la date,
la version du dépôt et l’environnement de chaque commande.

## Les tests unitaires prioritaires

### Échecs

- FEN valide, invalide et position terminale ;
- conversion UCI/SAN ;
- coup légal et illégal ;
- application d’un coup et FEN résultante.

### Workflow

- validation bloquante ;
- ouverture connue et inconnue ;
- Stockfish disponible, incomplet ou indisponible ;
- contexte Wikichess exact par ECO ;
- repli Wikichess par coups ;
- YouTube sans contexte exploitable ;
- LLM indisponible avec réponse de secours ;
- MongoDB en erreur sans perte de la réponse.

### Adapters

- timeout et nouvelle tentative HTTP ;
- validation d’une réponse JSON incorrecte ;
- dimension d’embedding incohérente ;
- filtre Milvus dangereux ou invalide ;
- score Stockfish en centipions et mat ;
- quota YouTube ;
- retrait des blocs `<think>` d’Ollama.

## Les tests du cycle de vie

- initialisation nominale dans l’ordre ;
- double initialisation idempotente ;
- ressource facultative indisponible ;
- ressource obligatoire en échec ;
- contrôle de santé en échec après initialisation ;
- rollback en ordre inverse ;
- erreur de fermeture isolée ;
- annulation pendant le démarrage ;
- suppression du conteneur avant l’arrêt des dépendances.

## Les tests de contrat

Je dois figer par exemple ou snapshot :

- `AnalysisRequest` et `AnalysisResponse` ;
- `ChessAnalysisState` et `StateUpdate` ;
- les valeurs de `AnalysisStatus` et `WorkflowStep` ;
- l’optionalité des données Stockfish ;
- `ServicesStatus` ;
- l’enveloppe d’erreur ;
- `AnalysisRecord` dans MongoDB ;
- les neuf clés injectées dans `RunnableConfig`.

## Mes critères de livraison

- [ ] Ruff passe sur tout le backend ;
- [ ] Pyright passe sur tout le backend ;
- [ ] les tests unitaires et d’intégration passent ;
- [ ] les contrats JSON sont testés ;
- [ ] aucun secret ou corps rejeté n’apparaît dans les logs ;
- [ ] les types TypeScript sont alignés sur l’API ;
- [ ] la documentation évolue dans le même lot que le code.
