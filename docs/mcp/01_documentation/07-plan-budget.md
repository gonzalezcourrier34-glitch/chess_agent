# Plan, charges et budget

## 1. Hypothèses

- jour homme de 7 heures ;
- taux indicatifs HT : backend/MCP 700 EUR, ML/CV 750 EUR, frontend 600 EUR, DevOps/sécurité 700 EUR, QA 550 EUR, produit/UX 600 EUR ;
- équipe disponible en parallèle ;
- corpus vidéo pilote fourni légalement ;
- pas de refonte majeure de la stack ;
- pas de support 24/7 ;
- fourchettes incluant revue et documentation, avec aléa technique selon niveau.

## 2. Lots MVP détaillés

| Lot | Livrables | Charge basse | Charge haute | Dépendances |
| --- | --- | ---: | ---: | --- |
| L0 Cadrage/droits | périmètre, corpus, DPIA screening, critères | 8 j | 12 j | aucune |
| L1 Architecture/contrats | ADR, schémas, OpenAPI, catalogue MCP | 8 j | 12 j | L0 |
| L2 Coeur échecs | FEN, ECO, Lichess, Stockfish, erreurs/cache | 18 j | 26 j | L1 |
| L3 Orchestration/API | LangGraph, FastAPI, idempotence | 12 j | 18 j | L2 |
| L4 RAG | ingestion, Milvus, évaluation, citations | 12 j | 18 j | L1 |
| L5 Serveur MCP | tools/resources/prompts, transports, auth | 10 j | 15 j | L2-L4 |
| L6 Vidéo POC | ingestion, CV, reconstruction, index | 28 j | 42 j | L0-L1 |
| L7 Frontend | échiquier, résultats, jobs, erreurs | 14 j | 20 j | L3/L5 |
| L8 DevOps/observabilité | Compose, CI/CD, logs, backups | 10 j | 15 j | transversal |
| L9 Sécurité/conformité | auth, scans, rétention, retrait | 7 j | 12 j | L0 |
| L10 QA/recette/pilote | campagnes, charge, preuves, soutenance | 12 j | 18 j | tous |
| **Total brut** |  | **139 j** | **208 j** |  |

Ce total correspond à un MVP ambitieux avec pipeline vidéo. L'objectif budgétaire de 115 à 165 j.h suppose réemploi de composants, corpus contrôlé et limitation du frontend. Un arbitrage de périmètre est donc nécessaire pour tenir la borne basse.

## 3. Scénarios d'investissement

### Scénario POC - 30 à 45 kEUR

- FEN/opening/Lichess/Stockfish ;
- RAG réduit ;
- serveur MCP local + HTTP de test ;
- 20 à 50 vidéos pré-autorisées ;
- un à deux layouts ;
- UI minimale ;
- preuves des principaux critères.

### Scénario MVP - 75 à 115 kEUR

- comptes/préférences ;
- traitement asynchrone ;
- auth et observabilité ;
- 5 layouts et corpus annoté ;
- déploiement pilote ;
- procédures de retrait et restauration.

### Scénario bêta - 145 à 220 kEUR

- résilience et scalabilité ;
- corpus élargi ;
- sécurité renforcée ;
- compatibilité clients MCP ciblés ;
- supervision, runbooks et pilote multi-utilisateurs.

## 4. Planning indicatif MVP

| Période | Travaux | Jalon |
| --- | --- | --- |
| Semaines 1-3 | cadrage droits, données, benchmark vision, contrats | Porte G0 : corpus et architecture |
| Semaines 4-7 | coeur échecs, API, cache, erreurs | Porte G1 : analyse déterministe |
| Semaines 6-9 | RAG, MCP, contrats et auth | Porte G2 : client MCP E2E |
| Semaines 8-15 | pipeline vidéo contrôlé | Porte G3 : seuils vision/timestamp |
| Semaines 12-17 | frontend, comptes, observabilité | Porte G4 : pilote intégré |
| Semaines 18-20 | sécurité, charge, recette, preuves | Porte G5 : Go pilote |

Délai réaliste : 4 à 6 mois avec 3 à 4 personnes équivalent temps plein. Une personne seule doit raisonner en charge et non en calendrier : environ 7 à 10 mois pour un périmètre réduit.

## 5. RACI minimal

| Activité | Produit | Architecte/backend | ML/CV | Frontend | DevOps/sécu | QA |
| --- | --- | --- | --- | --- | --- | --- |
| exigences et Go/No-Go | A/R | C | C | C | C | C |
| contrats MCP/API | C | A/R | C | C | C | C |
| coeur échecs | C | A/R | I | C | C | C |
| pipeline vidéo | C | C | A/R | I | C | C |
| sécurité/conformité | C | C | C | I | A/R | C |
| recette et preuves | A | R | R | R | R | R |

A = accountable, R = responsible, C = consulted, I = informed.

## 6. OPEX et facteurs

| Facteur | Formule de pilotage |
| --- | --- |
| CPU API | requêtes x durée CPU x tarif instance |
| Stockfish | analyses x secondes moteur x coeurs |
| Vidéo GPU | heures vidéo x frames/min x coût GPU/frame |
| Stockage | Go source autorisée + preuves + sauvegardes |
| Milvus | nombre de vecteurs x dimension x réplication |
| LLM | tokens entrée/sortie par analyse |
| Trafic | réponses, miniatures, téléchargements autorisés |

Mettre des budgets/quotas par utilisateur et alerter à 50/80/100 %.

## 7. Sensibilités

| Variation | Effet probable |
| --- | --- |
| durée vidéo x10 | coût GPU et stockage presque linéaires sans échantillonnage |
| layouts de 2 à 20 | annotation et généralisation fortement accrues |
| analyse Stockfish 2 s -> 10 s | capacité moteur divisée approximativement par 5 |
| cache hit 20 % -> 80 % | forte réduction APIs/LLM/Stockfish |
| conservation de toutes les frames | hausse majeure stockage et risque juridique |
| corpus partenaire avec PGN | baisse forte du coût vision et hausse précision |

## 8. Réserves

Ajouter 15 à 25 % de contingence au budget validé tant que le benchmark vision et les droits du corpus ne sont pas clos. Toute estimation ferme doit partir du volume : heures vidéo/mois, analyses/jour, utilisateurs actifs, clients MCP, régions et SLA.
