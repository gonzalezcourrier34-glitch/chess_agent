# Sécurité et conformité

## 1. Périmètre sensible

- comptes, emails et préférences ;
- secrets Lichess/YouTube/LLM et jetons OAuth ;
- fichiers vidéo potentiellement protégés ;
- prompts et documents RAG externes ;
- outils MCP déclenchant calcul ou écriture ;
- artefacts vision et journaux.

## 2. Menaces principales

| Menace | Exemple | Mesure prioritaire |
| --- | --- | --- |
| Accès non autorisé | lancement d'une ingestion coûteuse | OAuth/OIDC, scopes, quotas par identité |
| Injection d'outil | prompt demandant une action hors rôle | descriptions strictes, validation serveur, refus par défaut |
| SSRF | URL pointant vers réseau interne | pas d'URL arbitraire, allowlist, résolution/IP contrôlée |
| Fichier hostile | faux MP4, bombe de décompression | MIME réel, limites, sandbox, antivirus |
| Exfiltration | secret dans log ou réponse MCP | masquage, logs structurés, tests secrets |
| Déni de service | vidéos énormes ou Stockfish illimité | quotas, timeouts, file de jobs, concurrence bornée |
| Empoisonnement RAG | document malveillant | provenance, modération, séparation données/instructions |
| Fuite inter-utilisateur | timeline privée retournée à un autre compte | contrôle propriétaire/tenant à chaque lecture |
| Supply chain | dépendance compromise | lockfiles, SBOM, scans et mises à jour contrôlées |

## 3. Contrôles MCP

- transport distant uniquement en TLS ;
- OAuth recommandé pour Streamable HTTP ;
- validation de l'émetteur et des audiences ;
- scopes par outil ;
- refus des arguments supplémentaires ;
- taille maximale des entrées/sorties ;
- rate limiting sur `Mcp-Method` et `Mcp-Name` ;
- journalisation des appels sensibles ;
- aucun secret dans les resources ou prompts ;
- consentement explicite avant action destructive ou coûteuse.

## 4. Droits vidéo

### Politique d'admission

Un actif n'est analysé que s'il possède : propriétaire ou licencié, source, date, périmètre de licence, preuve, durée de conservation et règle de retrait. L'attestation seule peut suffire pour un pilote interne à faible risque, mais une validation juridique est requise pour un service commercial.

### YouTube

L'API officielle sert à retrouver les vidéos et leurs métadonnées. Les conditions d'utilisation ne constituent pas une autorisation générale de télécharger ou reproduire les contenus. Le produit doit privilégier le lecteur intégré et le lien horodaté. Toute analyse d'octets vidéo provenant de YouTube nécessite une base d'autorisation documentée séparément.

### Retrait

Un retrait doit supprimer ou désactiver : fichier source, crops de preuve, segments d'index, embeddings associés et caches ; conserver seulement le journal minimal nécessaire à la preuve de suppression.

## 5. RGPD

À réaliser avant pilote externe :

1. identifier responsable et sous-traitants ;
2. documenter finalités et bases légales ;
3. limiter les données à l'identifiant, email nécessaire et préférences utiles ;
4. fixer les durées ;
5. permettre accès, rectification, export et effacement ;
6. sécuriser transit, repos et sauvegardes ;
7. encadrer transferts et fournisseurs ;
8. réaliser une AIPD si le contexte ou l'échelle l'exige ;
9. publier information et contact ;
10. tenir un registre des incidents.

Valeurs de départ à valider : analyses anonymisées 90 jours, comptes jusqu'à suppression + délai technique, journaux sécurité 180 jours, frames temporaires 24 heures, crops de preuve 30 jours maximum.

## 6. RAG et propriété intellectuelle

- ne pas indexer un document sans provenance ;
- stocker licence et règles d'usage ;
- limiter les extraits transmis au LLM ;
- afficher les sources ;
- traiter les documents comme données non fiables, jamais comme instructions système ;
- offrir désindexation et correction.

## 7. Secrets et configuration

- secrets injectés au runtime ;
- environnements séparés ;
- rotation et révocation ;
- aucune clé dans Dockerfile, Compose, frontend ou logs ;
- moindre privilège pour MongoDB, Milvus, stockage et API ;
- scan automatique du dépôt et des images.

## 8. Validation des entrées

- FEN validée par parseur métier ;
- UCI/SAN validés dans le contexte de la position ;
- URLs construites côté serveur à partir d'identifiants validés ;
- tailles de listes bornées ;
- langues et niveaux sous forme d'enums ;
- IDs au format documenté ;
- dates en types temporels, pas chaînes libres ;
- rejet des champs inconnus.

## 9. Journalisation et audit

Champs : timestamp UTC, correlation_id, identité pseudonymisée, outil/route, statut, durée, dépendance, quota, modèle/version. Exclure emails, jetons, vidéo brute, prompts privés et FEN si elle est liée à un utilisateur sans nécessité.

## 10. Checklist avant exposition distante

- [ ] OAuth/OIDC et scopes testés.
- [ ] TLS et en-têtes de sécurité configurés.
- [ ] quotas par utilisateur/outil.
- [ ] politiques de droits vidéo actives.
- [ ] export/effacement RGPD testés.
- [ ] secrets scannés et rotation testée.
- [ ] restauration de sauvegarde exécutée.
- [ ] SBOM et scans de vulnérabilités archivés.
- [ ] tests SSRF/fichiers hostiles exécutés.
- [ ] procédure incident et retrait documentée.
- [ ] revue juridique des sources et licences.

## 11. Avis

Cette section constitue une analyse de conception et non un avis juridique. Les droits vidéo, licences de corpus et obligations RGPD doivent être validés par la personne compétente avant mise en service externe.
