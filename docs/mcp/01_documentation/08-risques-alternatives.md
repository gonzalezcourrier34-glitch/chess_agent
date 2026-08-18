# Registre des risques et alternatives

Échelle : probabilité P et impact I de 1 à 5 ; criticité = P x I.

| ID | Risque | P | I | Score | Prévention / réduction | Déclencheur | Propriétaire |
| --- | --- | ---: | ---: | ---: | --- | --- | --- |
| R01 | droits vidéo insuffisants | 4 | 5 | 20 | corpus détenu/licencié, preuve obligatoire | actif sans preuve | produit/juridique |
| R02 | FEN complète inférable d'une frame | 5 | 4 | 20 | état partiel, suivi temporel, FEN initiale | champs inventés ou incohérents | ML/backend |
| R03 | généralisation vision faible | 4 | 4 | corpus contrôlé, benchmark, métriques par layout | placement exact < 90 % | ML/CV |
| R04 | quota/rate limit Lichess | 3 | 4 | sérialisation, cache, pause 60 s après 429 | 429 ou latence élevée | backend |
| R05 | quota YouTube | 3 | 3 | cache, budget, audit si extension | consommation > 80 % | backend/ops |
| R06 | hallucination de coups/sources | 3 | 5 | légalité déterministe, sorties structurées, citations | coup illégal ou source absente | IA/QA |
| R07 | coût GPU excessif | 4 | 4 | échantillonnage adaptatif, budget, corpus PGN | coût/heure > seuil | ML/ops |
| R08 | divergence API/MCP | 3 | 3 | mêmes services, contrats et tests snapshot | réponses sémantiques différentes | architecte |
| R09 | contrats Pydantic incohérents | 4 | 3 | enums uniques, revue migration, version API | échec sérialisation | backend |
| R10 | traitement vidéo hostile | 3 | 5 | sandbox, limites, antivirus, codecs contrôlés | crash/épuisement | sécurité |
| R11 | fuite de données utilisateur | 2 | 5 | tenant checks, chiffrement, tests horizontaux | accès croisé | sécurité |
| R12 | dépendance service externe | 4 | 3 | timeouts, circuit breaker, mode dégradé | 5xx/timeout | backend/ops |
| R13 | Milvus surdimensionné | 3 | 2 | benchmark vs alternative simple | faible corpus/coût élevé | architecte |
| R14 | extension MCP non supportée | 3 | 3 | jobs métier, compatibilité client, pin versions | test client échoue | MCP |
| R15 | manque de vérité terrain | 4 | 4 | annotation avant modèle, split propre | métriques non crédibles | produit/ML |
| R16 | versioning modèle/index | 3 | 4 | model_version, index_version, réindexation | résultats incompatibles | ML/data |
| R17 | performance Stockfish | 3 | 3 | timebox, pool workers, cache | file d'attente | backend/ops |
| R18 | non-conformité RGPD | 3 | 5 | registre, rétention, droits, minimisation | demande d'effacement impossible | produit/sécu |

## Matrice de traitement

- score 15-25 : blocage ou réduction avant pilote ;
- score 8-14 : plan obligatoire et suivi hebdomadaire ;
- score 1-7 : accepter ou surveiller.

## Alternatives de périmètre

| Option | Description | Coût | Risque | Valeur | Avis |
| --- | --- | ---: | ---: | ---: | --- |
| O1 Core sans vision | FEN, théorie, moteur, RAG, vidéos par métadonnées | faible | faible | moyenne | repli sûr |
| O2 Corpus partenaire | vidéos + PGN/timelines fournis | moyen | faible | élevée | meilleure option MVP |
| O3 Vision contrôlée | 1-5 layouts autorisés | moyen | moyen | élevée | POC recommandé |
| O4 Vision généraliste | toute vidéo publique | très élevé | très élevé | potentiellement élevée | No-Go initial |
| O5 Base vectorielle managée | Zilliz/Milvus géré | moyen OPEX | faible ops | élevée | si petite équipe |
| O6 Milvus auto-hébergé | contrôle total | ops élevé | moyen | élevée | si compétence infra |
| O7 Recherche exacte d'abord | hash position + Mongo | faible | faible | élevée | obligatoire |
| O8 Tout vectoriel | proximité comme mécanisme principal | moyen | moyen | moyenne | déconseillé pour exactitude |

## Plans de contingence

### Vision sous les seuils

Limiter aux layouts performants, exiger PGN ou overlay lisible, offrir recherche par ouverture/chapitre et conserver la position manuelle.

### Droits non obtenus

Supprimer ingestion vidéo tierce ; ne garder que liens et métadonnées officielles ou vidéos propres. Le coeur Chess Agent reste viable.

### Coûts trop élevés

Traitement différé, cadence réduite, cache, modèles CPU, suppression des artefacts intermédiaires, quotas par compte et corpus éditorialisé.

### MCP client incompatible

Geler la version SDK, réduire aux primitives communes, utiliser l'API FastAPI pour le frontend et maintenir des tests par client cible.

## Revue

Le registre est revu à chaque porte G0-G5. Toute criticité >= 15 possède un responsable, une date et une preuve de réduction avant passage de porte.
