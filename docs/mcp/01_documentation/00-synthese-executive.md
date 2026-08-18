# Synthèse exécutive

## Objet

Concevoir un assistant pédagogique d'ouvertures d'échecs qui reçoit une position FEN, identifie l'ouverture, propose des coups issus de la théorie ou de Stockfish, enrichit la réponse par RAG et retrouve une vidéo pertinente à un timestamp précis. Les capacités sont exposées à un agent IA via MCP et à une interface Angular via FastAPI.

## Verdict

**Go conditionnel pour un POC puis un MVP sur corpus contrôlé.**

- **Go** : validation FEN, identification ECO, statistiques/théorie Lichess, repli Stockfish, RAG Milvus, persistance MongoDB, API FastAPI, interface Angular et serveur MCP.
- **Go sous expérimentation** : détection de l'échiquier et des pièces dans des vidéos hétérogènes, reconstruction temporelle de la position et précision du timestamp.
- **No-Go en l'état** : téléchargement et stockage automatisés de vidéos YouTube tierces sans autorisation. Le système doit indexer des vidéos détenues/licenciées ou téléversées par un utilisateur autorisé ; pour YouTube, il conserve de préférence identifiant, métadonnées, positions dérivées autorisées et lien horodaté.

## Score de faisabilité

| Dimension | Poids | Note / 5 | Commentaire |
| --- | ---: | ---: | --- |
| Coeur échiquéen et API | 25 % | 4,5 | Bibliothèques et services matures ; intégration à réaliser. |
| MCP et agent orchestration | 15 % | 4,0 | SDK Python v2 stable ; protocole 2026-07-28 sans session. |
| RAG et données | 15 % | 3,5 | Faisable, sous réserve de corpus et d'évaluation de pertinence. |
| Vision vidéo -> position | 20 % | 2,8 | Faisable sur corpus contrôlé ; généralisation non prouvée. |
| Sécurité, conformité, droits | 15 % | 2,5 | Bloquant tant que les droits vidéo et la base RGPD ne sont pas cadrés. |
| Exploitation et coûts | 10 % | 3,5 | Coûts maîtrisables avec traitement batch et quotas. |
| **Total pondéré** | **100 %** | **3,5 / 5** | **Faisable sous conditions et par paliers.** |

## Périmètre recommandé

### POC démontrable

- entrée FEN validée ;
- identification d'ouverture et variante ;
- coups Lichess puis Stockfish si la théorie est absente ;
- récupération RAG sur un petit corpus ;
- recherche dans 20 à 50 vidéos autorisées pré-indexées ;
- six outils MCP principaux ;
- interface Angular minimale ;
- mesures de qualité et preuves reproductibles.

### MVP

- gestion de comptes et préférences ;
- pipeline asynchrone d'indexation vidéo ;
- observabilité, contrôle d'accès et reprise sur erreur ;
- corpus élargi et jeu de vérité terrain ;
- critères de qualité bloquants ;
- déploiement Streamable HTTP sécurisé.

## Ordres de grandeur

Hypothèses : équipe mixte, tarifs moyens de 550 à 750 EUR par jour, hors taxes, hors achat de données et hors marge contractuelle.

| Niveau | Charge | Délai calendaire | Investissement estimatif |
| --- | ---: | ---: | ---: |
| Démonstrateur POC | 45 à 65 j.h | 8 à 12 semaines | 30 kEUR à 45 kEUR |
| MVP corpus contrôlé | 115 à 165 j.h | 4 à 6 mois | 75 kEUR à 115 kEUR |
| Bêta production | 210 à 310 j.h | 7 à 10 mois | 145 kEUR à 220 kEUR |

OPEX mensuel indicatif : 50 à 250 EUR pour une démonstration locale/cloud légère, 350 à 1 800 EUR pour un MVP, 2 000 à 7 500 EUR pour une petite production. La vision GPU, le volume vidéo et les appels LLM sont les principaux facteurs de variation.

## Conditions de Go

1. Les vidéos du pilote sont détenues, téléversées avec autorisation ou couvertes par une licence exploitable.
2. Un jeu de vérité terrain d'au moins 1 000 frames et 200 séquences est annoté.
3. Le POC atteint au minimum 90 % de positions de pièces exactes sur le corpus contrôlé et une erreur de timestamp P90 inférieure ou égale à 2 secondes.
4. Les appels Lichess respectent la sérialisation et le délai après HTTP 429.
5. Les secrets, journaux, comptes et données personnelles sont cadrés.
6. Le serveur MCP passe les tests de contrats, d'autorisation et de non-régression.

## Décision proposée

Lancer un **lot de réduction des risques de trois semaines** avant le MVP : droits vidéo, benchmark vision, validation du catalogue MCP et mesure des quotas. À son issue, le comité décide de poursuivre le pipeline vidéo, de le limiter aux vidéos maîtrisées ou de conserver uniquement la recommandation par métadonnées.
