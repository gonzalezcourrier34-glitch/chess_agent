# Décisions, hypothèses et questions

## Décisions issues des échanges

| ID | Décision | Conséquence |
| --- | --- | --- |
| D01 | projet orienté assistant d'ouvertures d'échecs | priorité au parcours FEN et pédagogie |
| D02 | stack FastAPI, LangGraph, Milvus, MongoDB, Stockfish, Lichess/YouTube, Angular/ngx-chessboard | architecture et compétences alignées |
| D03 | théorie Lichess puis repli Stockfish | branche explicite et testée |
| D04 | RAG pour enrichir les explications | corpus, embeddings et métriques nécessaires |
| D05 | pipeline vidéo frames -> échiquier -> position -> timestamp | lot ML/CV distinct et mesuré |
| D06 | exposition par serveur MCP | catalogue tools/resources/prompts |
| D07 | Docker Compose et dépôt Git pour le POC | reproductibilité locale |
| D08 | couvrir 100 % de l'énoncé avec traçabilité et preuve | matrice obligatoire |
| D09 | distinguer exigences mission et choix d'ingénierie | documents séparés et IDs distincts |
| D10 | respecter la convention MISA dans tout Python | CI et revue style |

## Recommandations de cette étude

| ID | Recommandation | Motif |
| --- | --- | --- |
| R-A01 | cible MCP 2026-07-28 et SDK Python v2 | version stable courante au 18 août 2026 |
| R-A02 | stdio local, Streamable HTTP distant | simplicité et conformité |
| R-A03 | jobs vidéo par `job_id` explicite | protocole sans session et traitement long |
| R-A04 | recherche exacte avant vectorielle | exactitude d'une position déterministe |
| R-A05 | corpus détenu/licencié/partenaire | droits et qualité |
| R-A06 | représenter position partielle | impossibilité d'inférer une FEN complète d'une image seule |
| R-A07 | séparer workers Stockfish et vidéo | profils CPU/GPU différents |
| R-A08 | même couche applicative pour API et MCP | éviter divergence métier |
| R-A09 | ne pas dépendre de MCP Tasks au MVP | compatibilité et maturité à valider |
| R-A10 | portes Go/No-Go quantitatives | limiter le risque avant investissement |

## Hypothèses de chiffrage

| ID | Hypothèse | Sensibilité |
| --- | --- | --- |
| H01 | 20 à 50 vidéos POC autorisées | forte sur annotation/vision |
| H02 | 1 à 5 layouts cibles | très forte sur qualité |
| H03 | 45 à 65 j.h pour le POC | forte selon réemploi réel |
| H04 | 550 à 750 EUR/jour | linéaire sur investissement |
| H05 | traitement batch, pas live | forte sur infra |
| H06 | petit trafic pilote | forte sur OPEX |
| H07 | disponibilité 99,5 % MVP | moyenne sur ops |
| H08 | vidéos conservées seulement si autorisées | réduit coût/risque |
| H09 | LLM et embeddings interchangeables | dépend des contrats/qualité |
| H10 | corpus documentaire licencié | bloquant pour RAG public |

## Questions à arbitrer

| Priorité | Question | Décideur | Échéance |
| --- | --- | --- | --- |
| Bloquante | quelles vidéos et quels droits exacts  | produit/juridique | G0 |
| Bloquante | la mission exige-t-elle une FEN complète ou le placement suffit-il  | commanditaire | G0 |
| Bloquante | quels clients MCP doivent être compatibles  | architecte/produit | G0 |
| Haute | quel volume vidéo/mois et analyses/jour  | produit | G0 |
| Haute | quels SLO, régions et contraintes d'hébergement  | produit/ops | G0 |
| Haute | quels layouts et langues prioritaires  | produit/ML | G0 |
| Haute | quel fournisseur LLM ou mode local  | architecte | G1 |
| Haute | authentification interne ou utilisateurs externes  | produit/sécu | G1 |
| Moyenne | Milvus managé ou auto-hébergé  | ops/finance | G1 |
| Moyenne | durée de conservation comptes/vidéos/logs  | juridique/produit | G1 |
| Moyenne | modèle économique et niveau gratuit  | direction | après POC |
| Moyenne | faut-il expliquer les coups en français uniquement  | produit | G1 |

## ADR à créer pendant le projet

- ADR-001 version MCP et matrice clients ;
- ADR-002 sémantique de position partielle ;
- ADR-003 stratégie vidéo et droits ;
- ADR-004 orchestration LangGraph ;
- ADR-005 stockage exact/vectoriel ;
- ADR-006 timeouts, cache et replis ;
- ADR-007 auth et multi-tenant ;
- ADR-008 versioning des modèles et index ;
- ADR-009 politique de rétention ;
- ADR-010 hébergement et observabilité.
