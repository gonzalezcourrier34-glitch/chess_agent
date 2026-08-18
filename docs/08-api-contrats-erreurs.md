# API, contrats et erreurs

[Sommaire](index.md) · [Modèles](09-modeles-donnees.md) · [Supervision](11-cycle-vie-configuration-supervision.md)

## Ce que je peux confirmer

Le dernier état de consolidation indique que les routes publiques FastAPI et
leur montage sous `/api` ont été vérifiés. Le présent dossier documentaire ne
contient toutefois pas les fichiers du routeur canonique : je distingue donc
ce statut déclaré de la preuve directement relisible ici.

Les sources techniques décrites pendant l’audit contiennent :

- une route FastAPI de supervision des services ;
- les dépendances typées attendues par cette route ;
- les handlers globaux d’exceptions ;
- le service d’analyse et ses modèles importés.

Le chemin exact de la route d’analyse doit être repris du routeur canonique ou
de l’OpenAPI générée, et non déduit d’un exemple ancien.

## La route de supervision

| Élément | Valeur observée |
| --- | --- |
| méthode | `GET` |
| chemin local du routeur | `""` |
| modèle de réponse | `ServicesStatus` |
| code de succès | `200 OK` |
| traitement | `HealthcheckService.check()` puis `response.services` |

Le chemin public dépend du préfixe utilisé lors du `include_router()`. Une constante `SERVICES_ENDPOINT = "/services"` existe, mais le montage du routeur n’est pas fourni. Je ne transforme donc pas cette constante en preuve du chemin final.

## Le contrat applicatif d’analyse

`AnalysisService` consomme un `AnalysisRequest` avec les attributs suivants :

| Attribut utilisé | Rôle |
| --- | --- |
| `fen` | position obligatoire |
| `moves` | historique réel des coups |
| `question` | question facultative |
| `response_language` | langue normalisée, `fr` en repli |

Il construit un `AnalysisResponse` avec :

- `status` ;
- `fen` ;
- `opening` ;
- `evaluation` ;
- `documents` ;
- `videos` ;
- `explanation` ;
- `analysis_id` ;
- `error`.

Le schéma joint plus ancien ne décrit pas `moves`, `question`,
`response_language` ni `analysis_id`, et il conserve un mode désormais retiré.
Il ne doit donc pas être utilisé seul comme source de vérité actuelle.

## L’enveloppe d’erreur FastAPI

Les handlers renvoient une structure homogène :

```json
{
  "success": false,
  "error": {
    "code": "ERROR_CODE",
    "message": "Message public"
  }
}
```

Une erreur de validation ajoute `details` :

```json
{
  "success": false,
  "error": {
    "code": "VALIDATION_ERROR",
    "message": "Les données de la requête sont invalides.",
    "details": [
      {
        "loc": ["body", "fen"],
        "msg": "Field required",
        "type": "missing"
      }
    ]
  }
}
```

Je retire volontairement la valeur rejetée des détails pour ne pas exposer une entrée sensible.

## La traduction des exceptions

| Exception | Réponse | Journalisation |
| --- | --- | --- |
| `ChessAgentError` | statut, code et message de l’exception | avertissement sans données sensibles |
| `RequestValidationError` | 422 et `VALIDATION_ERROR` | chemin et nombre d’erreurs |
| autre `Exception` | 500 et `INTERNAL_SERVER_ERROR` | trace complète côté serveur |

Pour une erreur inattendue, le client reçoit seulement `Une erreur interne est survenue.`

## La hiérarchie métier

`ChessAgentError` centralise le code, le statut HTTP, la possibilité de réessayer, le contexte et la cause. La hiérarchie couvre notamment :

- requête, authentification, autorisation et limite de débit ;
- ressource absente, conflictuelle ou verrouillée ;
- FEN, coup, notation et état d’échiquier invalides ;
- analyse, récupération RAG et workflow ;
- configuration et cycle de vie ;
- MongoDB, Milvus, Lichess, YouTube, Ollama et Stockfish.

## Les points à figer avant une API normative

Je dois encore aligner :

- le schéma `ErrorResponse` joint et l’enveloppe réellement produite par les handlers ;
- la preuve archivée des valeurs publiques de `AnalysisStatus` ;
- le chemin complet de la route d’analyse dans le README et les exemples ;
- le chemin public de supervision dans le README et les exemples ;
- l’authentification, actuellement non démontrée ;
- les exemples OpenAPI construits depuis les modèles canoniques.
