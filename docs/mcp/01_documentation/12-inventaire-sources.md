# Inventaire des sources

## 1. Fichiers fournis

| N° | Nom reçu | Copie dans le dossier | Usage |
| ---: | --- | --- | --- |
| 1 | `MISA.txt` | `04_sources_fournies/MISA.txt` | convention Python |
| 2 | `evaluation(1).py` | `04_sources_fournies/evaluation.py` | schémas évaluation |
| 3 | `user(1).py` | `04_sources_fournies/user.py` | schémas utilisateur |
| 4 | `document(1).py` | `04_sources_fournies/document.py` | schémas RAG |
| 5 | `analysis(1).py` | `04_sources_fournies/analysis.py` | requête/réponse analyse |
| 6 | `video(1).py` | `04_sources_fournies/video.py` | vidéos et recommandations |
| 7 | `move(1).py` | `04_sources_fournies/move.py` | coups et statistiques |
| 8 | `error(1).py` | `04_sources_fournies/error.py` | erreurs |
| 9 | `opening(1).py` | `04_sources_fournies/opening.py` | ouvertures |
| 10 | `position(1).py` | `04_sources_fournies/position.py` | position/FEN |
| 11 | `enums(1).py` | `04_sources_fournies/enums.py` | enums communs |

Les copies sont fidèles au contenu reçu ; seul le nom est normalisé pour faciliter la lecture.

## 2. Contexte consolidé des échanges

- mission : concevoir un système de stockage vidéo, extraction de frames, détection d'échiquier, position/FEN et recherche de lien horodaté ;
- stack : FastAPI, LangGraph, Milvus, MongoDB, Stockfish, APIs Lichess/YouTube, Angular/ngx-chessboard, Docker Compose, Git ;
- workflow : FEN -> ouverture -> Lichess -> repli Stockfish -> RAG -> vidéos -> UI ;
- contrainte : couverture à 100 % de l'énoncé avec phase, fichiers, méthode, test et preuve ;
- contrainte : séparer exigences mission et choix d'ingénierie.

## 3. Références officielles consultées

Consultation : 18 août 2026.

### Model Context Protocol

- Spécification 2026-07-28 : https://modelcontextprotocol.io/specification/2026-07-28
- Architecture : https://modelcontextprotocol.io/docs/2026-07-28/learn/architecture
- Tools : https://modelcontextprotocol.io/specification/2026-07-28/server/tools
- Resources : https://modelcontextprotocol.io/specification/2026-07-28/server/resources
- Changelog : https://modelcontextprotocol.io/specification/2026-07-28/changelog
- SDK Python officiel : https://github.com/modelcontextprotocol/python-sdk

Points retenus : coeur sans session, requêtes autonomes, découverte, tools/resources/prompts, transports stdio et Streamable HTTP, durcissement de l'autorisation, SDK Python v2 stable.

### Lichess

- API : https://lichess.org/api
- Conseils API et rate limiting : https://lichess.org/page/api-tips

Points retenus : un seul appel à la fois ; après HTTP 429, attendre une minute complète avant reprise.

### YouTube

- Démarrage API : https://developers.google.com/youtube/v3/getting-started
- Quotas/audits : https://developers.google.com/youtube/v3/guides/quota_and_compliance_audits
- Coût des méthodes : https://developers.google.com/youtube/v3/determine_quota_cost
- Conditions YouTube : https://www.youtube.com/statictemplate=terms

Points retenus : quotas par projet/méthode, audit pour extension, limites d'usage et absence de droit général de télécharger/reproduire les contenus.

### Données et coûts

- MongoDB Atlas : https://www.mongodb.com/pricing
- Zilliz Cloud : https://zilliz.com/pricing
- Guide de prix Zilliz : https://zilliz.com/pricing/pricing-guide

Les prix publics changent ; le budget du dossier utilise des fourchettes et doit être recalculé avec régions, SLA et volumes.

## 4. Sources à ajouter avant développement

- énoncé officiel intégral et critères d'évaluation ;
- licences du corpus documentaire ;
- licences et preuves de droits des vidéos ;
- matrice des clients MCP cibles ;
- versions exactes Python/Angular/ngx-chessboard/LangGraph/Milvus/MongoDB ;
- hypothèses de trafic et SLA ;
- benchmark de vision et vérité terrain ;
- décision fournisseur LLM/embeddings ;
- politique RGPD et sécurité de l'organisation.

## 5. Limites documentaires

Les références de prix et quotas sont datées du jour de consultation. L'étude n'a pas accès à des contrats commerciaux privés, à l'énoncé officiel non fourni ni à des mesures d'exécution d'un dépôt complet. Les chiffres restent des estimations à recalculer après cadrage.
