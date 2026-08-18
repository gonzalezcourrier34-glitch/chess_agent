# Persistance MongoDB

[Sommaire](index.md) · [Modèles](09-modeles-donnees.md) · [Cycle de vie](11-cycle-vie-configuration-supervision.md)

## Ce que je stocke

Je conserve une analyse complète dans la collection MongoDB `analyses`. Le nœud final transforme l’état LangGraph en `AnalysisRecord` avec :

- un identifiant stable ;
- le `request_id` ;
- la FEN, les coups et la question ;
- la langue ;
- la position, l’ouverture et l’évaluation ;
- le contexte RAG et les vidéos ;
- la réponse finale ;
- les options et métadonnées techniques ;
- les étapes, avertissements et erreurs ;
- les dates de création et de sauvegarde.

**Statut : Confirmé.**

## L’identifiant et l’idempotence

Le nœud `save_analysis` dérive l’identifiant de l’analyse du `request_id` avec `uuid5` et l’espace de nom `chess-agent-analysis`. Le service MongoDB crée en plus un index unique sur `request_id`.

À l’écriture, j’utilise `update_one(..., upsert=True)` :

- la première exécution crée le document ;
- une nouvelle exécution du même nœud met à jour le document existant ;
- `_id` et `created_at` ne sont définis qu’à l’insertion ;
- `saved_at` reflète la dernière sauvegarde.

Cette stratégie évite qu’un rejeu LangGraph crée plusieurs analyses pour une même requête.

## Les index

| Index | But |
| --- | --- |
| `request_id` ascendant et unique | garantir une analyse par requête |
| `saved_at` descendant | accélérer l’historique récent |

## La conversion des données

Le modèle métier utilise `id`, alors que MongoDB utilise `_id`. À l’écriture, je renomme `id` en `_id`. À la lecture, je réalise l’opération inverse puis je valide le document avec `AnalysisRecord`.

Un document MongoDB sans `_id` ou incompatible avec le schéma déclenche une `DatabaseOperationError`.

## Les opérations publiques

| Méthode | Fonction |
| --- | --- |
| `save_analysis()` | créer ou mettre à jour une analyse |
| `get_analysis()` | lire par identifiant |
| `get_required_analysis()` | lire ou lever une erreur |
| `get_analysis_by_request_id()` | lire par requête |
| `list_recent_analyses()` | obtenir un historique paginé |
| `delete_analysis()` | supprimer si présent |
| `delete_required_analysis()` | supprimer ou lever une erreur |

## L’historique

`list_recent_analyses()` trie par `saved_at` décroissant, applique un `offset` positif ou nul et limite le nombre de résultats. La limite par défaut est 20 et la limite maximale configurée est 100.

Chaque `AnalysisSummary` contient notamment la FEN, le statut, le nom
d’ouverture, un aperçu de la réponse, le nombre d’avertissements, le nombre
d’erreurs et les dates. L’aperçu est normalisé sur une ligne et limité à 200
caractères par défaut. Le mode d’analyse a été retiré de la persistance récente.

## L’échec de sauvegarde

La persistance est traitée comme une étape secondaire après la production de la réponse. Si MongoDB échoue :

- le nœud marque l’étape comme terminée pour éviter une boucle ;
- il conserve la réponse déjà calculée ;
- il ajoute un `WorkflowWarning` ;
- il place `analysis_id` à `None` ;
- il transforme le statut en réussite partielle lorsque nécessaire.

L’absence de `request_id` ou du service injecté suit le même principe, avec un avertissement de configuration.

## Ce que la source ne montre pas

Je n’ai pas de route FastAPI confirmée pour consulter ou supprimer ces analyses. Les opérations existent au niveau service, mais leur exposition HTTP reste à documenter après lecture du routeur correspondant.
