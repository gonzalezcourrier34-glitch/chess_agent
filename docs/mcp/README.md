# Dossier MCP - Chess Agent / AgentIA

Version 1.0 - 18 août 2026

Ce dossier consolide les échanges précédents, les onze fichiers fournis et une étude de faisabilité complète pour un assistant d'ouvertures d'échecs exposé par Model Context Protocol (MCP).

## Conclusion en une phrase

Le projet est **faisable sous conditions** : le coeur FEN -> ouverture -> théorie Lichess -> repli Stockfish -> RAG -> recommandation vidéo est réalisable avec la stack retenue, tandis que l'analyse automatique de vidéos doit être limitée à des contenus détenus, téléversés ou explicitement licenciés et validée sur un corpus contrôlé avant toute généralisation.

## Contenu

- `01_documentation/00-synthese-executive.md` : décision Go/No-Go et chiffres clés.
- `01_documentation/01-etude-faisabilite-complete.md` : étude complète.
- `01_documentation/02-exigences-et-tracabilite.md` : couverture exigence -> phase -> fichier -> méthode -> test -> preuve.
- `01_documentation/03-architecture-mcp.md` : architecture cible, outils, ressources et prompts MCP.
- `01_documentation/04-pipeline-video-fen.md` : chaîne vidéo -> frames -> position -> timestamp.
- `01_documentation/05-securite-conformite.md` : sécurité, RGPD, droits vidéo et garde-fous.
- `01_documentation/06-qualite-tests-recette.md` : stratégie de tests et seuils d'acceptation.
- `01_documentation/07-plan-budget.md` : lots, planning, charges, investissement et OPEX.
- `01_documentation/08-risques-alternatives.md` : registre des risques et scénarios alternatifs.
- `01_documentation/09-decisions-hypotheses-questions.md` : décisions, hypothèses et points à arbitrer.
- `01_documentation/10-audit-fichiers-fournis.md` : audit des schémas Pydantic transmis.
- `01_documentation/11-soutenance-et-preuves.md` : démonstration et preuves attendues.
- `01_documentation/12-inventaire-sources.md` : inventaire et références externes.
- `02_contrats/mcp-catalogue.yaml` : catalogue contractuel des primitives MCP.
- `02_contrats/openapi.yaml` : surface HTTP interne minimale.
- `02_contrats/schemas-video-index.json` : contrat des positions vidéo indexées.
- `03_diagrammes/*.mmd` : diagrammes Mermaid réutilisables.
- `04_sources_fournies/` : copie fidèle des onze fichiers reçus.
- `05_preuves/matrice-recette.csv` : grille de recette exploitable.
- `07_pdf/Dossier_MCP_Chess_Agent.pdf` : version prête à présenter.

## Statut des éléments

| Marqueur | Sens |
| --- | --- |
| Décidé | Élément explicitement retenu dans les échanges ou imposé par les fichiers. |
| Recommandé | Choix d'architecture proposé dans cette étude. |
| Hypothèse | Base de chiffrage à confirmer. |
| À valider | Décision métier, juridique ou technique encore ouverte. |

## Lecture rapide

1. Lire la synthèse exécutive.
2. Vérifier la matrice de traçabilité.
3. Examiner les critères Go/No-Go et le budget.
4. Utiliser le document de soutenance pour préparer la démonstration.

## Limite de l'audit

Les fichiers reçus sont une convention de développement et dix modules de schémas. Ils ne contiennent ni routes FastAPI, ni graphe LangGraph, ni services Lichess/Stockfish/YouTube, ni pipeline de vision, ni serveur MCP, ni tests. L'étude ne confond donc pas contrats déclarés et fonctionnalités effectivement prouvées.
