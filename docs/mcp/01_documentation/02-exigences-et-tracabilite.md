# Exigences et traçabilité

## Règle de preuve

Une exigence n'est considérée couverte que si les six colonnes sont renseignées : phase, fichier cible, méthode, test, preuve et statut. Les preuves indiquées ci-dessous sont **attendues** sauf lorsque le statut mentionne explicitement un élément déjà présent.

## A. Exigences mission

| ID | Exigence | Phase | Fichiers/composants cibles | Méthode | Test/vérification | Preuve soutenable | Statut |
| --- | --- | --- | --- | --- | --- | --- | --- |
| MIS-01 | Stocker les vidéos à analyser | 0, 3 | ingestion, stockage objet, `VideoAsset` | n'accepter que fichiers autorisés, hash et provenance | upload, doublon, retrait, rétention | métadonnées + preuve de licence + journal de purge | À concevoir |
| MIS-02 | Extraire les frames | 3 | worker vidéo | échantillonnage adaptatif et keyframes | vidéo courte/longue, cadence variable | rapport nombre de frames et durées | À concevoir |
| MIS-03 | Détecter l'échiquier | 3 | modèle CV | détection, coins, rectification | corpus annoté multi-layout | précision/rappel par version de modèle | À expérimenter |
| MIS-04 | Détecter les pièces | 3 | classifieur 64 cases | classification + confiance | matrice de confusion par pièce/case | rapport métriques + exemples d'échec | À expérimenter |
| MIS-05 | Convertir en position/FEN | 3 | reconstructeur temporel | légalité + suivi séquentiel | séquences avec coups, roque, promotion | taux placement exact et FEN complète | Contrat manquant |
| MIS-06 | Gérer l'incertitude FEN | 3 | schémas vidéo | `partial`/`complete`, champs inconnus | image isolée sans historique | réponse explicite sans FEN inventée | Recommandé |
| MIS-07 | Indexer position et timestamp | 3 | MongoDB/index exact | segments temporels et clé de position | même position répétée, plans coupés | requête DB + timeline attendue | Contrat manquant |
| MIS-08 | Rechercher une vidéo par FEN | 3 | service recherche, MCP | exact puis proximité contrôlée | FEN présente, absente, partielle | résultat classé avec confiance | À concevoir |
| MIS-09 | Retourner un lien YouTube horodaté | 3 | service lien | identifiant + seconde de début | URL, arrondi et offset | ouverture au passage attendu | Contrat manquant |
| MIS-10 | Fournir bénéfices et limites | Documentation | étude | analyse multicritère | revue par commanditaire | sections 2, 8 et 9 de l'étude | Couvert dossier |
| MIS-11 | Fournir architecture MCP | 2 | doc architecture, diagrammes | tools/resources/prompts, transports | revue + validation catalogue | diagrammes et YAML | Couvert conception |
| MIS-12 | Chiffrer build et OPEX | 0, 4 | plan budget | charges bottom-up et scénarios | revue hypothèses | tableau charges + sensibilités | Couvert estimation |
| MIS-13 | Décrire risques et alternatives | Toutes | registre risques | probabilité, impact, mitigation | revue portes Go/No-Go | registre versionné | Couvert dossier |
| MIS-14 | Décrire les étapes | Toutes | roadmap | phases, dépendances, livrables | jalons d'acceptation | planning et checklist | Couvert dossier |

## B. Exigences produit

| ID | Exigence | Phase | Fichiers/composants cibles | Méthode | Test/vérification | Preuve soutenable | Statut |
| --- | --- | --- | --- | --- | --- | --- | --- |
| APP-01 | Recevoir une FEN | 1 | `AnalysisRequest`, `FenRequest` | modèle unique + normalisation | FEN valide/invalide/espaces | tests Pydantic + python-chess | Partiel existant |
| APP-02 | Identifier ouverture/variante ECO | 1 | service opening, `OpeningDetails` | base ECO et transpositions | corpus positions connues | taux d'identification | Schémas présents |
| APP-03 | Proposer théorie Lichess | 1 | client Lichess | cache, sérialisation, timeout | réponses vide/429/5xx | tests mock + métriques | À développer |
| APP-04 | Repli Stockfish | 1 | worker moteur | temps maximal et MultiPV | théorie absente, moteur indisponible | ligne légale + temps borné | Schémas présents |
| APP-05 | Enrichir par RAG Milvus | 2 | ingestion/retrieval | chunks sourcés, seuil de similarité | jeu de questions annoté | Recall@5/NDCG + citations | Schémas présents |
| APP-06 | Recommander des vidéos | 2, 3 | service YouTube, `VideoCollection` | requête, cache, pertinence | quota, aucun résultat | raison + score + source | Schémas partiels |
| APP-07 | Générer explication pédagogique | 2 | agent/LangGraph | LLM contraint par données structurées | coup illégal, source absente | validation de légalité et citation | À développer |
| APP-08 | Interface échiquier Angular | 4 | Angular/ngx-chessboard | saisie FEN et affichage variantes | E2E clavier/mobile/erreurs | vidéo de recette + tests | À développer |
| APP-09 | Gérer préférences utilisateur | 4 | `UserProfile` | langue, difficulté, ouvertures | lecture/édition/effacement | tests API + audit RGPD | Schémas présents |
| APP-10 | Réponse dégradée | 1, 2 | LangGraph, erreurs | repli par dépendance | LLM/Mongo/Milvus/API indisponibles | réponse partielle typée | À concevoir |
| APP-11 | Idempotence | 1, 3 | analyses/jobs MongoDB | `request_id`, `job_id`, index unique | répétition/reprise | un seul résultat logique | Absent fichiers reçus |

## C. Choix d'ingénierie

Ces éléments ne sont pas des exigences métier immuables ; ils sont retenus par les discussions et doivent être revalidés si une contrainte change.

| ID | Choix | Phase | Fichier/composant | Justification | Test | Preuve | Statut |
| --- | --- | --- | --- | --- | --- | --- | --- |
| ENG-01 | FastAPI | 1 | API | cohérence Pydantic/Python | OpenAPI et tests contrat | schéma généré | Décidé |
| ENG-02 | LangGraph | 1, 2 | orchestration | replis et étapes explicites | transitions, reprise, timeouts | traces de graphe | Décidé |
| ENG-03 | MongoDB | 1 | persistance | documents et jobs | index, reprise, sauvegarde | plan de restauration | Décidé |
| ENG-04 | Milvus | 2 | vector store | RAG et montée en charge | qualité/latence | benchmark | Décidé |
| ENG-05 | Stockfish | 1 | moteur UCI | référence déterministe | légalité, timebox | rapport moteur | Décidé |
| ENG-06 | Angular/ngx-chessboard | 4 | frontend | échiquier interactif | test compatibilité versions | build reproductible | Décidé |
| ENG-07 | Docker Compose | 1 | dev/POC | environnement reproductible | démarrage propre | logs + healthchecks | Décidé POC |
| ENG-08 | MCP SDK Python v2 | 2 | serveur MCP | protocole 2026-07-28 | conformance + clients cibles | rapport Inspector/suite | Recommandé |
| ENG-09 | Stdio local, HTTP distant | 2 | transports | simplicité locale, accès distant | tests sur deux transports | rapports contrats | Recommandé |
| ENG-10 | Jobs explicites | 3 | MongoDB + queue | MCP stateless, longues vidéos | reprise et polling | historique d'état | Recommandé |

## D. Qualité, sécurité et conformité

| ID | Exigence | Phase | Fichier/composant | Méthode | Test | Preuve | Statut |
| --- | --- | --- | --- | --- | --- | --- | --- |
| QUA-01 | Convention MISA | Toutes | tout Python | lint, review, typage | Ruff/Pyright | rapports CI | Convention fournie |
| QUA-02 | Validation stricte | 1 | schémas | `extra=forbid`, validateurs métier | fuzz FEN/UCI/URL | tests unitaires | Inégal aujourd'hui |
| QUA-03 | Contrats cohérents | 1 | schemas/API/MCP | enums uniques, erreurs standard | snapshot schemas | diff approuvé | Écarts relevés |
| QUA-04 | Tests bout en bout | 4 | stack | cas nominaux et dégradés | campagne recette | dossier de preuves | À produire |
| SEC-01 | Authentification/autorisation | 2, 4 | passerelle/MCP | OAuth/OIDC, scopes | token expiré, mauvais scope | rapport sécurité | Absent |
| SEC-02 | Secrets | 1 | configuration | coffre/env, jamais dépôt/logs | scan secret | rapport CI | Absent |
| SEC-03 | Protection SSRF/fichiers | 3 | ingestion | allowlist, taille, MIME, sandbox | URL interne, zip bomb, faux MIME | tests sécurité | Absent |
| SEC-04 | RGPD | 0, 4 | comptes/données | minimisation, rétention, droits | effacement/export | registre + preuve | À valider |
| LEG-01 | Droits vidéo | 0, 3 | ingestion | provenance/licence obligatoire | actif sans licence | rejet + journal | Bloquant |
| OPS-01 | Observabilité | 1-4 | tous services | logs structurés, métriques, traces | incident simulé | tableau de bord | À produire |
| OPS-02 | Sauvegarde/reprise | 4 | Mongo/objets | RPO/RTO, test restauration | perte simulée | PV de restauration | À produire |

## Couverture actuelle des fichiers fournis

| Domaine | Contrats présents | Implémentation présente | Tests présents | Conclusion |
| --- | --- | --- | --- | --- |
| FEN/position | Oui, partiels | Non | Non | non prouvé |
| Ouvertures/coups | Oui | Non | Non | non prouvé |
| Stockfish | Réponses seulement | Non | Non | non prouvé |
| RAG | Documents/résultats | Non | Non | non prouvé |
| Vidéos | Métadonnées/recommandation | Non | Non | timestamp absent |
| Utilisateurs | Oui | Non | Non | RGPD à cadrer |
| FastAPI | Modèles de requête/réponse | Routes absentes | Non | surface incomplète |
| LangGraph | Non | Non | Non | absent du lot |
| MCP | Non | Non | Non | absent du lot |

## Définition de « couvert » pour la soutenance

- **Couvert dossier** : conception écrite et traçable, sans prétention d'exécution.
- **Partiel existant** : un contrat est présent mais la logique ou la validation métier manque.
- **Prouvé** : test exécuté, résultat archivé et version identifiée.
- **Bloquant** : aucune mise en production avant résolution.
