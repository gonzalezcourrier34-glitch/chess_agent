# Guide de présentation du projet

[Sommaire](index.md) · [Présentation](01-presentation-projet.md) · [Limites](15-limites-evolutions.md)

## Mon résumé en une phrase

J’ai conçu Chess Agent comme un backend d’analyse échiquéenne capable de valider une position, de croiser Lichess, Stockfish et Wikichess, puis de produire et conserver une explication pédagogique.

## Mon pitch de deux minutes

> Mon projet s’appelle Chess Agent. L’objectif est de transformer une position d’échecs en une explication plus riche qu’un simple score moteur. L’utilisateur fournit une FEN, éventuellement l’historique des coups et une question. Mon backend FastAPI délègue l’analyse à un service qui exécute un workflow LangGraph composé de huit nœuds.
>
> Je commence par valider la position avec python-chess. Je peux ensuite reconnaître l’ouverture avec Lichess, analyser la position avec Stockfish, retrouver un document Wikichess grâce aux embeddings et à Milvus, puis proposer des vidéos YouTube. Ollama rassemble uniquement les informations disponibles dans une réponse finale. Si le LLM est indisponible, je conserve une réponse de secours. Enfin, MongoDB sauvegarde l’analyse de manière idempotente grâce au request_id.
>
> J’ai séparé les responsabilités entre l’API, les services, le workflow, les adapters et les schémas Pydantic. Le cycle de vie démarre les ressources obligatoires dans un ordre précis. Lichess et YouTube peuvent fonctionner en mode dégradé ; le LLM est requis au démarrage, mais une erreur de génération ultérieure produit une réponse de secours. J’applique aussi la convention MISA pour garder un code lisible, typé et homogène.

## Mon plan de présentation en dix minutes

| Temps | Sujet | Message principal |
| --- | --- | --- |
| 0:00–1:00 | besoin | une analyse utile doit expliquer, pas seulement noter |
| 1:00–2:00 | architecture | chaque couche possède une responsabilité |
| 2:00–5:00 | workflow | huit nœuds enrichissent progressivement le même état |
| 5:00–6:30 | sources | Lichess, Stockfish et Wikichess ont des rôles différents |
| 6:30–7:30 | robustesse | timeouts, erreurs structurées, repli et rollback |
| 7:30–8:30 | persistance | sauvegarde idempotente et historique MongoDB |
| 8:30–9:15 | qualité | MISA, Ruff, Pyright et tests de contrat |
| 9:15–10:00 | limites | preuves à archiver, frontend et déploiement |

## La démonstration que je peux préparer

1. je montre une FEN valide et l’historique des coups ;
2. j’explique la construction de l’état initial ;
3. je suis les étapes terminées dans le workflow ;
4. je compare la donnée Lichess au résultat Stockfish ;
5. je montre le document Wikichess retenu et son filtre ECO ou coups ;
6. j’affiche la réponse finale ;
7. je retrouve l’`analysis_id` enregistré ;
8. je termine par l’état des services.

Si l’interface Angular réelle n’est pas disponible, je peux démontrer le backend avec la documentation OpenAPI ou un client HTTP, sans prétendre montrer un frontend finalisé.

## Les questions probables

### Pourquoi LangGraph plutôt qu’une seule fonction ?

J’ai plusieurs étapes facultatives, des états intermédiaires et des replis. LangGraph rend le parcours explicite, testable nœud par nœud et adaptable selon les options.

### Pourquoi utiliser Stockfish et un LLM ?

Stockfish calcule. Le LLM explique. Je ne demande pas au modèle de langage d’inventer un score ou un meilleur coup.

### Pourquoi Lichess et Wikichess ?

Lichess apporte des statistiques issues de parties. Wikichess apporte un contenu pédagogique documentaire. Leurs informations sont complémentaires.

### Comment éviter un mauvais document RAG ?

Je filtre d’abord par code ECO ou séquence exacte de coups, puis je vérifie de nouveau le résultat dans l’application. La similarité vectorielle sert au classement dans ce sous-ensemble.

### Que se passe-t-il si Ollama ne répond pas ?

Le LLM est requis au démarrage dans l’état consolidé. Si un appel échoue après
que l’application est devenue prête, le nœud génère une réponse de secours à
partir des données déjà disponibles et ajoute un avertissement.

### Que se passe-t-il si MongoDB échoue ?

Je conserve l’analyse produite, j’ajoute un avertissement et je renvoie `analysis_id = None`. La persistance ne détruit pas le résultat métier.

### Comment le démarrage reste-t-il sûr ?

Le gestionnaire initialise les ressources obligatoires dans l’ordre, les contrôle et exécute un rollback inverse si l’une d’elles échoue. Le conteneur FastAPI n’est publié qu’après ce processus.

### Le projet est-il totalement terminé ?

Je réponds avec précision : le backend principal est déclaré consolidé, y
compris les contrats, les routes, le routage et les validations globales. Je dois
encore archiver les preuves correspondantes dans ce dossier, vérifier le
frontend réel et documenter le déploiement complet.

## Ce que je dois éviter de dire

- « le LLM analyse la position » : c’est Stockfish qui calcule ;
- « Lichess donne le meilleur coup » : il fournit surtout ouverture et statistiques ;
- « le RAG cherche partout » : il cible Wikichess avec ECO ou coups ;
- « tous les tests passent » sans sortie globale ;
- « l’endpoint est `/api/analyze` » sans route confirmée ;
- « le frontend est terminé » sans sources Angular réelles.
