# Qualité, tests et recette

## 1. Stratégie

La qualité est organisée en pyramide : validation statique, tests unitaires, contrats, intégrations isolées, bout en bout, sécurité, charge et évaluation ML. Aucun score global unique ne remplace les seuils bloquants.

## 2. Chaîne CI proposée

1. format/lint ;
2. typage statique ;
3. tests unitaires avec couverture ;
4. validation JSON Schema/OpenAPI/YAML ;
5. tests contrats FastAPI/MCP ;
6. tests intégration avec services simulés ;
7. scans secrets, dépendances et images ;
8. build Docker reproductible ;
9. tests E2E sur environnement éphémère ;
10. publication des rapports de preuve.

Outils possibles : Ruff, Pyright, pytest, Hypothesis, Schemathesis, MCP Inspector/suite de conformité, Playwright, pip-audit, Trivy. Ils sont des choix d'implémentation, pas des exigences mission.

## 3. Tests statiques et schémas

- Python conforme à MISA ;
- Python cible explicitée, au minimum 3.11 recommandé pour `StrEnum` natif ;
- imports internes résolus ;
- aucune duplication de types sémantiques ;
- `extra="forbid"` homogène sur les entrées API ;
- champs temporels et URLs typés ;
- exemples OpenAPI/MCP validés ;
- compatibilité Pydantic verrouillée.

## 4. Tests domaine échecs

| Cas | Attendu |
| --- | --- |
| FEN standard valide | normalisée sans changement sémantique |
| rang trop long, roi absent, symbole invalide | erreur structurée |
| coup UCI syntaxiquement correct mais illégal | rejet métier |
| roque sans droit | rejet |
| promotion valide/invalide | validation contextuelle |
| position issue d'une transposition | ouverture identifiée selon politique |
| statistiques | taux bornés et somme tolérée/validée |
| Stockfish timeout | réponse dégradée, worker libéré |
| PV | tous les coups rejouables légalement |

Utiliser des tests de propriété pour générer des positions légales et vérifier que normalisation, sérialisation et rejeu préservent l'état.

## 5. Tests workflow

Branches minimales :

- cache hit ;
- théorie Lichess trouvée ;
- théorie absente -> Stockfish ;
- Lichess 429 -> pause/circuit/cache ;
- Stockfish indisponible ;
- Milvus indisponible ;
- LLM indisponible ;
- MongoDB indisponible avant/après calcul ;
- YouTube quota épuisé ;
- aucun document ou aucune vidéo ;
- répétition du même `request_id` ;
- annulation/reprise d'un job vidéo.

Chaque noeud LangGraph doit être testable indépendamment. Les transitions sont vérifiées par snapshot de trace, sans dépendre du texte exact du LLM.

## 6. Tests MCP

- découverte des primitives ;
- schémas d'entrée et de sortie ;
- champ manquant, supplémentaire ou trop grand ;
- outil inconnu ;
- resource inconnue ;
- cache metadata des listes/ressources ;
- `stdio` et Streamable HTTP ;
- version protocolaire supportée et refus propre d'une version incompatible ;
- absence d'état implicite entre deux instances ;
- scopes corrects/incorrects ;
- propagation des correlation IDs ;
- outil d'écriture soumis à autorisation et audit.

## 7. Tests FastAPI

- génération OpenAPI ;
- cohérence codes HTTP et modèle `ErrorResponse` ;
- idempotence ;
- limites de taille ;
- timeouts ;
- CORS limité ;
- auth ;
- health/readiness distingués ;
- même réponse métier via API et MCP, hors enveloppe de transport.

## 8. Évaluation RAG

Construire 50 à 100 questions annotées avec documents attendus. Mesurer Recall@5, MRR/NDCG, taux de réponse sourcée, fidélité au contexte et abstention lorsque le corpus ne répond pas.

Seuils POC : Recall@5 >= 0,80, sources correctes >= 90 %, aucune citation inventée dans le jeu de recette.

## 9. Évaluation vidéo

Séparer entraînement, validation et test par vidéo/chaîne/layout, pas par frames aléatoires. Rapporter par sous-groupe : 2D/3D, thème, résolution, overlays, animation, orientation.

Seuils bloquants : rappel échiquier >= 95 %, placement exact >= 90 %, Recall@5 vidéo >= 90 %, erreur timestamp P90 <= 2 s. Présenter aussi les intervalles de confiance et le nombre d'exemples.

## 10. Performance et charge

Scénarios : 10/50/200 analyses concurrentes, pool Stockfish saturé, 10 jobs vidéo, cache froid/chaud, dépendance lente. Mesurer P50/P95/P99, débit, mémoire, CPU/GPU, files d'attente et taux d'erreur.

Les appels Lichess restent sérialisés indépendamment de la charge interne. Un test spécifique confirme l'attente d'une minute après 429.

## 11. Sécurité

- contrôle d'accès horizontal ;
- injection dans prompts/documents ;
- SSRF ;
- traversée de chemin ;
- fichier vidéo hostile ;
- épuisement ressources ;
- secrets ;
- dépendances ;
- journalisation de données personnelles ;
- consentement pour annulation/purge.

## 12. Matrice de recette

Le CSV `05_preuves/matrice-recette.csv` sert au suivi. Colonnes obligatoires : identifiant, exigence, cas, précondition, entrée, attendu, obtenu, statut, version, preuve, date, responsable.

## 13. Définition de Done

Une fonctionnalité est terminée lorsque :

- code et contrats sont relus ;
- tests requis passent ;
- métriques sont sous les seuils ;
- logs/erreurs sont exploitables ;
- sécurité et droits sont respectés ;
- documentation est mise à jour ;
- preuve est liée à l'exigence ;
- démonstration peut être reproduite depuis un environnement propre.

## 14. Preuves à ne pas surévaluer

- compilation seule ;
- capture d'écran sans entrée/version ;
- exemple unique réussi ;
- métrique d'entraînement ;
- réponse LLM jugée « plausible » ;
- schéma Pydantic sans route ni test ;
- fichier déclaré mais absent du lot.
