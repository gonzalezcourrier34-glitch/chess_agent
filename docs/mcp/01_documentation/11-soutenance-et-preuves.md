# Soutenance et dossier de preuves

## 1. Trame de présentation, 15 minutes

| Temps | Sujet | Message clé | Preuve montrée |
| ---: | --- | --- | --- |
| 1 min | problème | retrouver l'explication et le bon passage vidéo | parcours utilisateur |
| 2 min | périmètre | coeur échecs + MCP + vidéo contrôlée | matrice exigences |
| 2 min | architecture | mêmes services via API et MCP | diagramme logique |
| 3 min | démonstration | FEN -> ouverture -> coups -> sources -> timestamp | journal E2E |
| 2 min | difficulté vidéo | position partielle et reconstruction temporelle | exemples annotés |
| 2 min | faisabilité | score, budget, planning | tableaux synthèse |
| 2 min | risques | droits vidéo et métriques Go/No-Go | registre risques |
| 1 min | décision | Go conditionnel par paliers | portes G0-G5 |

## 2. Démonstration idéale

1. Démarrer un environnement propre.
2. Afficher les versions et healthchecks.
3. Soumettre une FEN connue via client MCP.
4. Montrer identification ECO et source de théorie.
5. Soumettre une position hors théorie et montrer le repli Stockfish.
6. Afficher un document RAG avec source.
7. Rechercher la position dans une vidéo autorisée.
8. Ouvrir le lien au timestamp calculé.
9. Répéter le même `request_id` et prouver l'idempotence.
10. Simuler un 429 Lichess ou un service indisponible et montrer la réponse dégradée.

## 3. Dossier de preuve par exigence

Arborescence recommandée :

```text
preuves/
  MIS-01/
    README.md
    input.json
    result.json
    logs.txt
    capture.png
  APP-03/
  SEC-01/
  ...
```

Chaque `README.md` précise version Git, environnement, commande, attendu, obtenu, date et responsable.

## 4. Questions probables et réponses

### Pourquoi MCP en plus de FastAPI 

FastAPI sert le frontend et les intégrations HTTP classiques. MCP rend les mêmes capacités découvrables et appelables de manière structurée par des hôtes IA, avec tools, resources et prompts. La logique métier n'est pas dupliquée.

### Peut-on réellement produire une FEN depuis une image 

On peut reconnaître la disposition des pièces. Les autres champs FEN ne sont pas toujours visibles. Le système les reconstruit seulement grâce à la séquence et à un état initial fiable ; sinon il annonce une position partielle.

### Pourquoi ne pas télécharger toutes les vidéos YouTube 

Parce que l'accès au lecteur ou aux métadonnées n'accorde pas automatiquement le droit de télécharger et d'analyser les octets. Le MVP utilise des vidéos détenues/licenciées et renvoie un lien YouTube horodaté.

### Pourquoi Lichess puis Stockfish 

La théorie et les statistiques sont plus pédagogiques dans les positions connues. Stockfish fournit un repli déterministe hors base, sous budget de calcul.

### Pourquoi Milvus si MongoDB existe 

MongoDB gère documents et état applicatif ; Milvus sert la similarité vectorielle. Pour un très petit corpus, une alternative plus simple doit être benchmarkée.

### Comment évitez-vous les hallucinations 

Les coups sont validés/rejoués avec `python-chess`, les évaluations viennent de Stockfish/Lichess et les explications citent les chunks retrouvés. Le LLM présente, il ne décide pas de la légalité.

## 5. Captures/rapports indispensables

- matrice de tests avec statuts ;
- rapport Pyright/Ruff ;
- tests unitaires et couverture ;
- contrats OpenAPI/MCP ;
- trace LangGraph nominale et dégradée ;
- rapport qualité RAG ;
- rapport CV par sous-groupe ;
- mesure timestamp ;
- test rate limit Lichess ;
- test auth/scopes ;
- scan secrets/vulnérabilités ;
- test de restauration ;
- preuve de droits du corpus, expurgée si confidentielle.

## 6. Checklist avant soutenance

- [ ] aucune affirmation « développé » sans preuve exécutable ;
- [ ] version et date sur tous les rapports ;
- [ ] démonstration enregistrée en secours ;
- [ ] corpus test distinct de l'entraînement ;
- [ ] deux cas d'échec expliqués ;
- [ ] budget relié aux hypothèses ;
- [ ] décisions et hypothèses clairement séparées ;
- [ ] tous les IDs d'exigence ont une preuve ou un statut à faire ;
- [ ] lien horodaté testé ;
- [ ] droits du média de démonstration confirmés.

## 7. Formulation de conclusion

« Le coeur Chess Agent et son exposition MCP sont techniquement faisables. La valeur différenciante, la recherche d'une position dans une vidéo, est faisable sur corpus contrôlé mais reste conditionnée par les droits et par des seuils mesurés de vision et de timestamp. Nous proposons un investissement progressif, avec une porte de décision après trois semaines de réduction des risques. »
