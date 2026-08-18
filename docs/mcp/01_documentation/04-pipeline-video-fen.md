# Pipeline vidéo vers position et timestamp

## Objectif

Créer un index permettant de retrouver dans une vidéo autorisée les intervalles où une position d'échecs apparaît, puis de produire un lien horodaté vers la plateforme source.

## Entrées

| Champ | Obligatoire | Description |
| --- | --- | --- |
| `asset_id` | oui | identifiant interne stable |
| `source_type` | oui | upload, owned, licensed, partner |
| `source_url` | selon cas | URL d'origine, jamais utilisée pour contourner une restriction |
| `youtube_video_id` | non | identifiant servant au lien horodaté |
| `rights_basis` | oui | propriété, licence, consentement ou contrat |
| `retention_policy` | oui | durée et règle de suppression |
| `expected_layout` | non | aide au POC contrôlé |
| `known_initial_fen` | recommandé | nécessaire à une reconstruction complète fiable |

## Étapes détaillées

### 1. Admission

- authentifier l'émetteur ;
- vérifier taille, MIME réel, codec et durée ;
- refuser URL interne, protocole non autorisé et fichier suspect ;
- exiger provenance et base de droits ;
- calculer SHA-256 et détecter les doublons.

### 2. Décodage

- extraire FPS, résolution, durée et keyframes ;
- limiter CPU, mémoire, durée et espace temporaire ;
- isoler le transcodage dans un worker sans secret.

### 3. Échantillonnage

- cadence basse pendant les plans stables ;
- cadence plus élevée lors d'un changement détecté ;
- éviter de traiter chaque frame d'une vidéo longue ;
- conserver la correspondance exacte PTS -> millisecondes.

### 4. Détection d'échiquier

- boîte/coins et score ;
- suivi entre frames pour limiter les faux négatifs ;
- rectification homographique ;
- rejet si moins de 64 cases cohérentes.

### 5. Orientation

- détecter repères de coordonnées si visibles ;
- comparer légalité et continuité des orientations candidates ;
- indiquer `unknown` si le signal est insuffisant.

### 6. Classification des cases

Classes minimales : vide, roi/dame/tour/fou/cavalier/pion, blanc/noir. Conserver probabilités par case, pas seulement le meilleur label.

### 7. Lissage temporel

- vote glissant ;
- suppression des transitions d'animation ;
- détection d'un changement de une ou quelques cases ;
- pénalisation des apparitions impossibles.

### 8. Validation échiquéenne

- nombre et placement des rois ;
- nombre de pièces plausible ;
- transition compatible avec un coup légal ;
- promotion, roque et prise en passant traités explicitement ;
- aucune correction silencieuse : conserver prédiction brute et correction proposée.

### 9. Construction de position

États :

- `piece_placement_only` : seules les pièces sont connues ;
- `partial_fen` : placement + certains champs ;
- `full_fen` : six champs reconstruits avec preuve suffisante.

Une position complète exige soit une position initiale connue et une séquence légale suivie, soit des métadonnées fiables. Le système ne doit pas remplir arbitrairement `w - - 0 1`.

### 10. Segmentation

Regrouper des observations consécutives de même position :

- `start_ms` : première apparition stable ;
- `end_ms` : dernière apparition stable ;
- `best_frame_ms` : frame de preuve avec meilleur score ;
- `confidence` : confiance calibrée ;
- `evidence_frame_ref` : crop optionnel à rétention courte.

### 11. Indexation

Index exact sur `position_key`. Index secondaires sur ECO, pièces, source, langue, niveau, chaîne et date. Milvus n'est utilisé que pour la proximité lorsque la correspondance exacte échoue et que le produit l'autorise.

### 12. Résultat

Pour YouTube : `https://www.youtube.com/watchv={video_id}&t={seconds}s`. Le système renvoie aussi la plage, la confiance, le type de position et la raison de classement.

## Jeu de vérité terrain

Minimum POC recommandé :

- 20 à 50 vidéos autorisées ;
- 1 000 frames annotées ;
- 200 transitions de coups ;
- au moins 5 layouts ;
- captures avec overlays, thèmes clairs/sombres et animations ;
- cas négatifs sans échiquier.

Réserver les vidéos de test avant l'entraînement pour éviter la fuite de données.

## Métriques

| Niveau | Métrique | Seuil Go POC |
| --- | --- | ---: |
| Détection | rappel échiquier | >= 95 % |
| Géométrie | coins dans tolérance | >= 95 % |
| Cases | exactitude macro par classe | >= 95 % |
| Position | placement exact des 64 cases | >= 90 % |
| Séquence | transitions légales reconstruites | >= 90 % |
| Temps | erreur absolue P90 | <= 2 s |
| Recherche | Recall@5 position vidéo | >= 90 % |
| Calibration | écart confiance/réalité | <= 5 points |

Ces seuils valent pour le corpus cible, pas pour toutes les vidéos publiques.

## Stratégies comparées

| Approche | Avantages | Limites | Recommandation |
| --- | --- | --- | --- |
| Règles CV classiques | rapide, explicable | fragile aux thèmes/overlays | baseline |
| Détecteur + classifieur cases | bon compromis | données annotées nécessaires | POC recommandé |
| OCR notation/PGN visible | précision élevée si présent | dépend de l'interface vidéo | signal auxiliaire |
| Transcription/chapitres | peu coûteux | ne donne pas toujours la position | repli recommandation |
| Modèle multimodal général | mise en route rapide | coût, variabilité, reproductibilité | benchmark, pas source unique |

## Gestion des erreurs

- `NO_BOARD_DETECTED`
- `UNSUPPORTED_LAYOUT`
- `LOW_CONFIDENCE_POSITION`
- `ILLEGAL_TRANSITION`
- `INCOMPLETE_FEN`
- `RIGHTS_NOT_VERIFIED`
- `VIDEO_DECODE_FAILED`
- `RESOURCE_LIMIT_EXCEEDED`
- `INDEX_WRITE_FAILED`

Chaque erreur contient étape, actif, version, caractère relançable et détails non sensibles.

## Coût unitaire à mesurer

Le pilote doit produire : secondes CPU/GPU par minute de vidéo, nombre de frames traitées, Go temporaires, coût cloud estimé, taux de retraitement et coût par position indexée. Sans ces mesures, l'OPEX vidéo reste une fourchette et non un budget.
