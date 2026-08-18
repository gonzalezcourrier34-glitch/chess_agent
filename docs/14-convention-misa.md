# Convention MISA v2.0

[Sommaire](index.md) · [Architecture](02-architecture-technique.md) · [Qualité](13-qualite-tests.md)

## Pourquoi je l’utilise

J’applique MISA pour donner l’impression que le projet a été pensé et écrit de manière cohérente du premier au dernier fichier. Mes priorités sont : lisibilité, cohérence, simplicité, robustesse, puis compacité raisonnable.

**Statut : Confirmé à partir de `MISA.txt`.**

## L’ordre d’un module Python

1. docstring du module ;
2. `from __future__ import annotations` ;
3. imports de la bibliothèque standard ;
4. imports externes ;
5. imports internes ;
6. constantes ;
7. configuration ;
8. fonctions utilitaires privées ;
9. classes ;
10. fonctions publiques.

Je peux adapter cet ordre si le rôle du fichier le justifie, mais je conserve la même logique dans les fichiers comparables.

## La docstring de module

Chaque fichier explique :

- son rôle ;
- ses responsabilités ;
- ce qu’il ne fait pas.

## Les sections

J’utilise des titres simples :

```python
# Configuration

# Validation

# Utilitaires

# API publique
```

Je n’utilise pas de séparateurs décoratifs composés de dizaines de caractères.

## Les fonctions

- une fonction possède une responsabilité principale ;
- ses paramètres et son retour sont typés ;
- sa docstring reste concise ;
- 20 à 50 lignes constituent une taille habituelle ;
- au-delà d’environ 70 lignes, j’étudie une extraction sans découpage artificiel ;
- je préfère les retours anticipés aux imbrications profondes.

## Le typage

Je préfère :

```python
list[str]
dict[str, object]
str | None
```

aux anciennes notations. Je type en priorité les frontières publiques, les objets partagés et les retours de services. J’accepte un type générique uniquement quand un contrat métier plus précis n’est pas raisonnable.

## Le nommage et les constantes

Je choisis des noms explicites comme `opening_name`, `recommended_move` et `legal_moves`. Je réserve les abréviations aux usages universels tels que FEN, UCI, SAN et ECO.

J’extrais les valeurs métier répétées en constantes et j’évite les nombres magiques.

## Les commentaires

Mes commentaires expliquent une raison, une contrainte ou un cas particulier. Ils ne paraphrasent pas l’instruction Python suivante.

## Les exceptions et les logs

- je ne capture jamais une exception avec `except:` seul ;
- je cible les exceptions utiles ;
- je conserve la cause avec `raise ... from error` lorsque cela aide le diagnostic ;
- j’utilise le logger du projet et pas `print()` ;
- je ne journalise pas de secret ni d’entrée sensible rejetée.

## La séparation des responsabilités

| Élément | Ce que je n’y place pas |
| --- | --- |
| endpoint | logique métier et transformations complexes |
| service | logique HTTP FastAPI |
| schéma | traitement métier |
| adapter | décision de routage du workflow |

## Ma checklist MISA

- [ ] docstring complète ;
- [ ] imports regroupés ;
- [ ] sections simples ;
- [ ] API publique typée ;
- [ ] noms explicites ;
- [ ] commentaires orientés vers le pourquoi ;
- [ ] exceptions ciblées ;
- [ ] aucune duplication inutile ;
- [ ] une responsabilité principale par fichier ;
- [ ] fichier complet fourni lors d’une correction.

