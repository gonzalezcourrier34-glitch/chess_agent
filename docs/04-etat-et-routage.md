# État partagé et routage

[Sommaire](index.md) · [Workflow](03-workflow-langgraph.md) · [Modèles](09-modeles-donnees.md)

## Pourquoi j’utilise un état partagé

`ChessAnalysisState` est le contrat commun de mon workflow. Je regroupe dans un seul modèle validé les entrées, les options, l’avancement, les résultats intermédiaires et les métadonnées techniques. Chaque nœud lit uniquement les champs utiles et retourne un dictionnaire de mise à jour.

Les services ne sont jamais stockés dans l’état : je les injecte par `RunnableConfig`. Je garde ainsi un état sérialisable et indépendant des clients techniques.

**Statut : Confirmé.**

## Les entrées

| Champ | Type | Valeur initiale | Utilisation |
| --- | --- | --- | --- |
| `fen` | `str` | obligatoire | position à analyser |
| `moves` | `list[str]` | liste vide | historique réel des coups |
| `question` | `str` | chaîne vide | demande facultative de l’utilisateur |
| `options` | `AnalysisOptions` | options par défaut | branches à exécuter |

## Les options

| Option | Défaut | Effet attendu |
| --- | --- | --- |
| `include_stockfish` | `true` | active l’analyse moteur |
| `include_opening` | `true` | active Lichess |
| `include_context` | `true` | active le RAG documentaire |
| `include_videos` | `true` | active YouTube |
| `generate_response` | `true` | active la génération finale |
| `response_language` | `fr` | choisit la langue de réponse |
| `save_analysis` | `true` | active MongoDB |

Dans `AnalysisService`, je construis actuellement ces options avec tous les
enrichissements activés. La requête pilote directement la langue, mais pas les
six booléens. `AnalysisMode` a été retiré du contrat récent parce qu’il ne
modifiait aucune branche réelle. Je considère l’ouverture future des options à
l’API comme une évolution, pas comme un contrat déjà exposé.

## L’avancement

| Champ | Rôle |
| --- | --- |
| `status` | statut global de l’analyse |
| `current_step` | dernière étape commencée ou exécutée |
| `completed_steps` | étapes terminées sans boucle |
| `warnings` | problèmes récupérables |
| `errors` | problèmes bloquants ou structurés |

Les versions récentes utilisent les membres `PENDING`, `SUCCESS`,
`PARTIAL_SUCCESS` et `FAILED`. La consolidation du backend déclare une seule
énumération canonique. Le fichier d’énumérations joint plus ancien expose encore
`SUCCESS`, `ERROR` et `RUNNING` : il reste utile pour l’historique, mais ne doit
plus piloter le contrat public.

## Les résultats métier

| Domaine | Champs |
| --- | --- |
| position | `position` |
| ouverture | `opening` |
| moteur | `engine_analysis`, `evaluation` |
| RAG | `retrieval_context` |
| vidéo | `videos` |
| génération | `workflow_context`, `response` |
| persistance | `analysis_id` |
| diagnostic | `metadata` |

## Le contexte de génération

`WorkflowContext` contient des résumés préparés progressivement :

- `position_summary` ;
- `opening_summary` et `opening_context` ;
- `engine_context` ;
- `unknown_position_context` ;
- `documents_summary` ;
- `videos_summary` ;
- `final_summary`.

Cette structure évite de reconstruire toute l’information au dernier moment. Le nœud de génération assemble les sections disponibles et applique des règles différentes à Wikichess, Lichess, Stockfish et aux positions inconnues.

## Les métadonnées

`WorkflowMetadata` suit :

- le `request_id` ;
- les dates de début et de fin ;
- la durée en millisecondes ;
- le fournisseur, le modèle et la dimension d’embedding ;
- le fournisseur et le modèle LLM ;
- la profondeur Stockfish ;
- le `top_k` RAG et le nombre de documents récupérés.

## Les destinations enregistrées

| Après | Destinations autorisées par `graph.py` |
| --- | --- |
| validation | théorie, moteur, contexte, vidéos, réponse, sauvegarde, fin |
| théorie | moteur, contexte, vidéos, réponse, sauvegarde, fin |
| moteur | position inconnue, contexte, vidéos, réponse, sauvegarde, fin |
| position inconnue | réponse, sauvegarde, fin |
| contexte | vidéos, réponse, sauvegarde, fin |
| vidéos | réponse, sauvegarde, fin |
| réponse | sauvegarde, fin |
| sauvegarde | fin |

## Ce que je peux affirmer sur le routage

Les règles de routage tiennent compte de l’échec de l’état, des options d’exécution, de la présence d’une ouverture et des options de réponse ou de sauvegarde. Je peux confirmer les destinations ci-dessus grâce à `graph.py`.

Je ne recopie pas les conditions `if` détaillées des sept fonctions : le contenu intégral de `routing.py` n’est pas présent dans le lot final consultable, même s’il a été signalé comme reçu pendant la collecte. J’évite donc d’inventer leur ordre de priorité.
