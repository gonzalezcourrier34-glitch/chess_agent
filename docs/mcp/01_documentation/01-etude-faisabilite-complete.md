# Étude de faisabilité complète

## 1. Cadre de l'étude

### 1.1 Besoin consolidé

Le projet Chess Agent / AgentIA vise un assistant pédagogique capable de :

1. recevoir une position d'échecs au format FEN ;
2. reconnaître une ouverture et sa variante ;
3. interroger Lichess pour la théorie et les statistiques ;
4. utiliser Stockfish lorsque la position n'est pas couverte par la théorie ;
5. enrichir l'analyse avec des documents retrouvés dans Milvus ;
6. recommander des vidéos YouTube ;
7. retrouver, dans des vidéos indexées, le passage où apparaît une position et fournir un lien horodaté ;
8. orchestrer le parcours avec LangGraph ;
9. exposer les capacités par FastAPI, MCP et une interface Angular/ngx-chessboard ;
10. conserver les données métier et l'historique utile dans MongoDB.

La mission est une **conception prouvable**, pas la prétention que tous ces éléments sont déjà développés. Les onze fichiers fournis constituent une base de contrats Pydantic et une convention MISA, mais pas un produit exécutable.

### 1.2 Sources analysées

- Convention MISA v2.0.
- Schémas : evaluation, user, document, analysis, video, move, error, opening, position, enums.
- Discussions antérieures : stack imposée, workflow FEN -> Lichess -> Stockfish -> RAG -> YouTube, pipeline vidéo et obligation de couverture exhaustive.
- Références officielles listées dans `12-inventaire-sources.md`.

### 1.3 Méthode

L'étude sépare :

- les **exigences mission**, qui décrivent le résultat attendu ;
- les **choix d'ingénierie**, qui peuvent évoluer sans changer la mission ;
- les **preuves existantes**, limitées aux fichiers réellement reçus ;
- les **hypothèses de chiffrage**, à confirmer pendant le cadrage.

## 2. Faisabilité fonctionnelle

### 2.1 Parcours principal

Le parcours nominal est cohérent :

1. l'utilisateur saisit ou construit une FEN ;
2. le backend la valide avec `python-chess` ;
3. le système normalise la position et calcule une clé stable ;
4. une base d'ouvertures/ECO tente l'identification ;
5. Lichess fournit coups et statistiques lorsque disponibles ;
6. Stockfish prend le relais selon une limite de temps déterministe ;
7. Milvus retrouve explications et documents ;
8. l'agent compose une réponse pédagogique avec traçabilité des sources ;
9. l'index vidéo recherche la position ou ses positions voisines ;
10. l'API renvoie l'analyse, les recommandations et les liens horodatés.

Ce parcours est fonctionnellement réalisable. Le principal point d'incertitude est la qualité du passage vidéo -> position, non le traitement échiquéen.

### 2.2 Utilisateurs cibles

À valider avec le commanditaire :

- joueurs débutants et intermédiaires apprenant des ouvertures ;
- entraîneurs préparant des supports ;
- clubs ou plateformes pédagogiques ;
- utilisateurs d'un agent IA compatible MCP.

Le modèle `UserPreferences` montre déjà une personnalisation par couleur, ouvertures, difficulté et langue. L'usage de comptes crée toutefois des obligations RGPD absentes des fichiers transmis.

### 2.3 Hors périmètre initial recommandé

- analyse temps réel d'un flux live ;
- indexation sans autorisation de l'ensemble de YouTube ;
- garantie de FEN complète depuis une image isolée ;
- jeu automatisé sur une plateforme ;
- entraînement d'un modèle de vision généraliste sur tout style d'échiquier ;
- conseil échiquéen compétitif sans indication d'incertitude.

## 3. Faisabilité technique

### 3.1 Compatibilité de la stack

| Composant | Rôle | Avis |
| --- | --- | --- |
| FastAPI | API interne, health checks, surface HTTP | Adapté aux schémas Pydantic existants. |
| LangGraph | Orchestration des étapes et replis | Adapté, mais l'état doit rester métier et testable. |
| MongoDB | utilisateurs, jobs, métadonnées, résultats | Adapté ; indexation et rétention à définir. |
| Milvus | recherche vectorielle | Adapté au RAG ; surdimensionné si le corpus reste très petit. |
| Stockfish | analyse hors théorie | Très adapté ; encadrer temps, profondeur et concurrence. |
| Lichess API | théorie/statistiques | Adapté sous respect strict du rate limiting. |
| YouTube Data API | découverte et métadonnées | Adapté ; ne fournit pas un droit général de télécharger les vidéos. |
| Angular/ngx-chessboard | interface interactive | Adapté ; vérifier compatibilité de version au démarrage. |
| MCP Python SDK v2 | exposition à des hôtes IA | Adapté à Python et au protocole 2026-07-28. |
| Docker Compose | environnement local/POC | Adapté ; la production demandera orchestration, sauvegardes et secrets. |

### 3.2 Architecture MCP

Le protocole MCP 2026-07-28 est sans session au niveau protocolaire. Chaque requête doit être autonome. Les traitements longs utilisent donc un `job_id` explicite, enregistré dans MongoDB, plutôt qu'un état caché dans la connexion.

Le serveur expose :

- des **tools** pour valider/analyser/rechercher ;
- des **resources** pour lire les ouvertures, positions et timelines ;
- des **prompts** pour structurer les explications pédagogiques ;
- le transport `stdio` en local et `Streamable HTTP` en environnement distant.

Le catalogue détaillé est dans `02_contrats/mcp-catalogue.yaml`. Pour éviter une dépendance prématurée à l'extension MCP Tasks, le MVP utilise `video.start_indexing` puis `video.get_indexing_status`. Cette décision pourra être revue lorsque l'extension et son support SDK seront validés par tests de conformité.

### 3.3 Faisabilité du pipeline vidéo

#### Entrée autorisée

Le pipeline accepte :

- un fichier détenu par l'organisation ;
- un fichier téléversé par un utilisateur attestant disposer des droits ;
- un flux ou objet fourni contractuellement par un créateur ;
- un corpus open data dont la licence autorise le traitement.

Il n'est pas recommandé de télécharger automatiquement des contenus YouTube tiers. Pour une vidéo YouTube, la couche de recommandation utilise l'API officielle et le lecteur intégré ; l'analyse des octets exige une autorisation distincte.

#### Étapes

1. Ingestion et empreinte du fichier.
2. Échantillonnage adaptatif des frames.
3. Détection de la zone d'échiquier.
4. Rectification de perspective et orientation.
5. Classification des 64 cases.
6. Lissage temporel entre frames.
7. Validation de légalité avec `python-chess`.
8. Reconstruction de la séquence de coups si l'état initial est connu.
9. Production d'une position normalisée avec score de confiance.
10. Indexation de la position, de la plage temporelle et de la source.

#### Limite FEN fondamentale

Une image isolée révèle principalement la disposition des pièces. Elle ne permet généralement pas de déduire avec certitude :

- le joueur au trait ;
- les droits de roque ;
- la case de prise en passant ;
- les compteurs de demi-coups et de coups.

La sortie de vision doit donc distinguer `piece_placement` de `full_fen`. Une FEN complète n'est déclarée que si la séquence antérieure ou une métadonnée fiable permet de reconstruire les champs manquants. Sinon, le résultat porte un état `partial` et des valeurs inconnues explicites.

### 3.4 Performance

Objectifs initiaux à confirmer :

| Opération | Objectif P95 |
| --- | ---: |
| Validation FEN | 100 ms |
| Identification ouverture locale | 300 ms |
| Réponse théorie avec cache | 2 s |
| Analyse Stockfish | 3 à 8 s selon budget moteur |
| Recherche RAG | 1,5 s |
| Recherche position vidéo pré-indexée | 1 s |
| Démarrage d'un job vidéo | 500 ms, traitement asynchrone |

La latence globale doit être bornée par étape. LangGraph ne doit pas masquer les timeouts ni lancer des appels externes non bornés.

### 3.5 Données et modèles

MongoDB conserve les objets transactionnels : utilisateurs, préférences, jobs, vidéos, timelines, analyses et erreurs. Milvus conserve les embeddings de documents et éventuellement des représentations de positions. Les positions exactes doivent d'abord être recherchées par clé déterministe ; le vectoriel sert à la proximité sémantique ou positionnelle, pas à remplacer une égalité exacte.

Une clé de position peut reposer sur :

- FEN normalisée pour une position complète ;
- placement des pièces + trait lorsque disponible ;
- hachage stable documenté ;
- version du détecteur et niveau de confiance.

## 4. Faisabilité opérationnelle

### 4.1 Déploiement

Le POC peut fonctionner avec Docker Compose. Le MVP distant sépare au minimum :

- API/MCP stateless ;
- workers Stockfish ;
- workers vidéo CPU/GPU ;
- MongoDB ;
- Milvus ou service managé ;
- stockage objet ;
- file de travaux ;
- collecte de logs, métriques et traces.

Les workers vidéo sont extensibles horizontalement. Les appels Lichess sont sérialisés par une passerelle avec cache et backoff. Les liens YouTube sont calculés à partir d'un timestamp stocké, sans répliquer la vidéo.

### 4.2 Exploitabilité

Chaque analyse reçoit un `request_id`; chaque ingestion un `job_id`. Les appels sont idempotents. Les traces contiennent les durées, statuts et versions de modèles, jamais les secrets ni le contenu personnel inutile.

SLO MVP proposés : disponibilité 99,5 %, taux d'erreur interne inférieur à 1 %, reprise d'un job interrompu sans doublon, sauvegarde quotidienne des métadonnées et RPO de 24 h.

### 4.3 Dépendances externes

- Lichess demande un seul appel simultané et une pause complète d'une minute après HTTP 429.
- YouTube applique des quotas et peut exiger un audit pour une extension.
- Les SDK, modèles de vision et bibliothèques doivent être verrouillés et scannés.
- Une indisponibilité externe ne doit pas empêcher une réponse dégradée locale.

## 5. Faisabilité juridique et conformité

### 5.1 Vidéos

Le stockage et l'analyse d'une vidéo sont distincts du droit d'afficher un lecteur YouTube. Les conditions YouTube restreignent notamment le téléchargement et l'usage automatisé non autorisé. Le MVP doit donc conserver une preuve de provenance/licence pour chaque fichier analysé.

Décision d'architecture :

- vidéo autorisée : stockage objet chiffré, durée de rétention définie ;
- vidéo YouTube tierce non autorisée : métadonnées API, identifiant, miniature permise, positions provenant seulement d'une source autorisée, lien `https://www.youtube.com/watchv=...&t=...s` ;
- retrait source : désindexation et purge traçable.

### 5.2 Données personnelles

Les modèles `User`, `UserProfile` et `UserPreferences` impliquent identifiant, pseudo, email et préférences. Avant production : registre de traitement, finalités, base légale, minimisation, durée de conservation, droits d'accès/effacement, export, sécurité et contrats de sous-traitance.

### 5.3 Propriété intellectuelle et modèles

Chaque document RAG doit stocker source, URL, auteur, date, licence et règle de citation. Les réponses générées doivent indiquer les sources utilisées et éviter de reproduire de longs passages protégés.

## 6. Faisabilité économique

### 6.1 Investissement

Trois niveaux sont proposés :

| Niveau | Contenu | Charge | Coût estimatif |
| --- | --- | ---: | ---: |
| POC | coeur FEN, MCP, petit RAG, 20-50 vidéos contrôlées, UI minimale | 45-65 j.h | 30-45 kEUR |
| MVP | comptes, pipeline asynchrone, sécurité, corpus annoté, CI/CD | 115-165 j.h | 75-115 kEUR |
| Bêta production | haute disponibilité, observabilité, corpus élargi, conformité | 210-310 j.h | 145-220 kEUR |

Les montants reposent sur 550 à 750 EUR/jour. Ils excluent licences de contenus, acquisition de données, audit juridique externe, support 24/7 et TVA.

### 6.2 OPEX mensuel

| Poste | Démo | MVP | Petite production |
| --- | ---: | ---: | ---: |
| API et workers CPU | 0-50 EUR | 80-350 EUR | 600-2 000 EUR |
| MongoDB | 0-30 EUR | 30-150 EUR | 100-600 EUR |
| Milvus/Zilliz | 0-50 EUR | 50-350 EUR | 200-1 200 EUR |
| Stockage et trafic | 0-20 EUR | 20-150 EUR | 100-800 EUR |
| GPU vidéo batch | 0-80 EUR | 100-600 EUR | 500-2 500 EUR |
| LLM/embeddings | 0-50 EUR | 50-500 EUR | 300-2 000 EUR |
| Logs, sauvegardes, sécurité | 0-20 EUR | 20-200 EUR | 200-800 EUR |
| **Total** | **0-250 EUR** | **350-1 800 EUR** | **2 000-7 500 EUR** |

Le stockage des frames est à éviter : conserver la vidéo autorisée, les timestamps, crops de preuve limités et artefacts nécessaires. La suppression des frames intermédiaires réduit fortement le coût et le risque.

### 6.3 Valeur attendue

- accès direct au bon passage pédagogique ;
- réduction du temps de recherche d'une explication ;
- parcours personnalisé ;
- réutilisation des mêmes capacités dans plusieurs hôtes grâce à MCP ;
- corpus et métriques capitalisables.

Le modèle économique n'a pas été décidé. Options à évaluer ultérieurement : outil interne de club/formation, abonnement B2C, licence B2B pour entraîneurs ou API. Aucun revenu n'est intégré au verdict de faisabilité.

## 7. Qualité et preuves

### 7.1 Seuils POC

- 100 % des FEN invalides du jeu de test sont rejetées proprement ;
- 100 % des coups proposés sont légaux dans la position ;
- aucun appel Lichess concurrent ;
- récupération après 429 conforme au délai ;
- exactitude du placement des pièces >= 90 % sur le corpus contrôlé ;
- rappel de détection d'échiquier >= 95 % ;
- erreur de timestamp P90 <= 2 s ;
- Recall@5 RAG >= 0,80 sur les questions annotées ;
- aucun secret dans le dépôt ou les logs ;
- contrats MCP et OpenAPI validés automatiquement.

### 7.2 Preuve soutenable

Pour chaque exigence, conserver : cas de test, entrée, résultat attendu, résultat réel, version de code/modèle, journal horodaté et capture ou rapport. La matrice `02-exigences-et-tracabilite.md` est la source de vérité de la couverture.

## 8. Risques déterminants

1. **Droits vidéo** : peut interdire le scénario d'ingestion choisi.
2. **FEN impossible depuis une frame seule** : nécessite reconstruction temporelle et statut partiel.
3. **Variabilité visuelle** : échiquiers 2D/3D, overlays, transitions, caméra, compression.
4. **Quotas externes** : Lichess/YouTube imposent cache, limitation et modes dégradés.
5. **Contrats incomplets** : timestamp, job, confiance et provenance absents des schémas actuels.
6. **Coût GPU/LLM** : dérive si les vidéos sont retraitées ou si le cache est insuffisant.
7. **Explications non fiables** : le LLM doit décrire des sorties structurées et sourcées, pas inventer des variantes.

## 9. Alternatives

### A. Métadonnées seulement

Recherche vidéo par titre, description et chapitres, sans analyser les images. Coût et risque faibles, précision positionnelle faible. Adapté comme repli légal.

### B. Corpus éditorialisé

Créateurs partenaires fournissant vidéos et PGN/timelines. Meilleure qualité et conformité. Recommandation prioritaire pour le MVP.

### C. Vision contrôlée

Analyse limitée à un ou deux layouts d'échiquier. Bon compromis pour prouver la chaîne technique.

### D. Vision généraliste

Tout type de vidéo et de perspective. Coût élevé, besoin de données important, non recommandé avant preuve du MVP.

## 10. Plan de mise en oeuvre

### Phase 0 - Réduction des risques, 3 semaines

- définir les droits et le corpus ;
- annoter un échantillon ;
- benchmarker deux approches de vision ;
- figer les contrats MCP et vidéo ;
- établir les budgets de temps Stockfish, quotas et cache.

### Phase 1 - Coeur déterministe, 3 à 4 semaines

- validation FEN ;
- ouverture/ECO ;
- Lichess et Stockfish ;
- API, erreurs, idempotence ;
- tests et métriques.

### Phase 2 - RAG et MCP, 3 à 4 semaines

- ingestion documentée ;
- recherche Milvus ;
- outils/ressources/prompts MCP ;
- auth locale/distance ;
- conformité protocolaire.

### Phase 3 - Vidéo contrôlée, 5 à 8 semaines

- ingestion autorisée ;
- détection et reconstruction ;
- timeline indexée ;
- recherche FEN -> timestamp ;
- évaluation sur vérité terrain.

### Phase 4 - Frontend, durcissement et pilote, 4 à 6 semaines

- expérience Angular ;
- comptes/préférences ;
- observabilité, sauvegarde, sécurité ;
- recette et pilote utilisateurs.

## 11. Critères Go/No-Go

| Porte | Go | No-Go / pivot |
| --- | --- | --- |
| Juridique | droits documentés pour tout fichier analysé | provenance ou licence absente |
| Vision | >= 90 % de placements exacts sur corpus cible | < 80 % après deux itérations |
| Timestamp | P90 <= 2 s | P90 > 5 s |
| Coût | coût/heure vidéo compatible avec budget | retraitements GPU non maîtrisés |
| MCP | catalogue stable, auth et contrats validés | dépendance à état de session caché |
| Pédagogie | réponses légales, sourcées, utiles | hallucinations de coups ou sources |

Entre les seuils Go et No-Go, une itération corrective time-boxée est autorisée. Le pivot privilégié est un corpus éditorialisé avec PGN/timelines fournis.

## 12. Conclusion

Le projet est techniquement cohérent et présente une valeur pédagogique claire. Sa réussite dépend d'une stratégie par paliers : coeur échiquéen déterministe, MCP standardisé, RAG mesuré, puis vision sur corpus légalement et visuellement contrôlé. Le dossier recommande un Go conditionnel, précédé d'un lot court de réduction des risques et suivi de portes de décision quantitatives.
