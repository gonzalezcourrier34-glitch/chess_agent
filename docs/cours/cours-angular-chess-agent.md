# Cours Angular appliqué à mon projet Chess Agent

## De zéro à mon frontend Angular connecté à FastAPI

> \*\*\*\*Fil rouge : mon projet Chess Agent\*\*\*\*

> Dans ce cours, je présente Angular à travers l'application que j'ai

> réellement construite. Mon objectif n'est pas seulement de définir les

> notions Angular, mais de comprendre comment je les utilise dans Chess

> Agent, pourquoi je les utilise et comment elles s'intègrent à mon

> backend FastAPI.

  -----------------
  \> La navigation
  dans ce cours est
  générée
  automatiquement
  par MkDocs à
  partir des titres
  de sections.

  -----------------

# 1. Angular dans mon projet

Dans Chess Agent, j'utilise \*\*\*\*Angular\*\*\*\* pour construire
l'interface

utilisateur.

Mon backend FastAPI prend en charge la logique applicative et déclenche

les différents traitements : validation de la position, détection de

l'ouverture, analyse Stockfish, récupération du contexte Wikichess,

recherche de vidéos et génération de la réponse.

Angular ne réalise pas ces calculs. Son rôle est de permettre à

l'utilisateur de manipuler l'échiquier, lancer une analyse et afficher

les résultats.

``` text

Utilisateur

    ↓

Frontend Angular

    ↓ HTTP

API FastAPI

    ↓

Workflow LangGraph

    ├── python-chess

    ├── Lichess

    ├── Stockfish

    ├── Milvus / Wikichess

    ├── YouTube

    └── LLM

    ↓

Réponse JSON

    ↓

Angular
```

Dans mon projet, je peux résumer les responsabilités ainsi :

  Technologie   Rôle dans Chess Agent

  ------------- --------------------------------

  Angular       interface utilisateur

  TypeScript    logique du frontend

  HTML          structure de l'interface

  SCSS          présentation visuelle

  FastAPI       API backend

  JSON          format d'échange

  HTTP          communication frontend/backend

Je retiens donc qu'Angular et FastAPI ne se remplacent pas. Ils

constituent deux couches différentes de mon application.

  ------------------------------------
  \# 2. Architecture de mon frontend
  Mon frontend reste volontairement
  simple car Chess Agent est un POC
  avec
  ------------------------------------
  \# 3. Les fichiers principaux
  **\##** `main.ts`

  `main.ts` est le point d'entrée de
  mon application Angular.

  Il lance le composant racine avec la
  configuration Angular.

  \`\`\`ts

  bootstrapApplication(AppComponent,
  appConfig)

      .catch((err) =\>
  console.error(err));

  \`\`\`

  Je peux le voir comme le bouton
  d'allumage de mon frontend.

  **\##** `app.component.ts`

  C'est le cerveau de ma page
  principale.

  J'y conserve notamment :

  \-   la FEN courante ;

  \-   la référence à l'échiquier ;

  \-   l'analyse reçue ;

  \-   l'état de chargement ;

  \-   les erreurs éventuelles ;

  \-   les méthodes déclenchées par
  l'utilisateur.

  Exemple simplifié :

  \`\`\`ts

  export class AppComponent {

      fen = '';

      loading = false;

      analysis: AnalysisResponse \|
  null = null;

      analyze(): void {

          this.loading = true;

      }

  }

  \`\`\`

  **\##** `app.component.html`

  C'est la structure visible de mon
  interface.

  Il relie les éléments graphiques aux
  données et méthodes de

  `AppComponent`.

  \`\`\`html

  \<button

      \[disabled\]="loading"

      (click)="analyze()"\>

      Analyser

  \</button\>

  \`\`\`

  **\##** `app.component.scss`

  J'y définis l'apparence de ma page :
  grille, panneaux, boutons,

  espacements, responsive et
  présentation de l'échiquier.

  **\##** `analysis.service.ts`

  Je l'utilise pour isoler la
  communication HTTP avec FastAPI.

  Ainsi, mon composant ne contient pas
  directement toute la logique

  réseau.
  ------------------------------------

# 4. TypeScript : les bases dont j'ai besoin

Angular utilise TypeScript. TypeScript ajoute notamment un typage

statique à JavaScript.

## Variables typées

``` ts

fen: string = '';

loading: boolean = false;

depth: number = 15;

moves: string[] = [];
```

Je peux aussi laisser TypeScript inférer certains types :

``` ts

loading = false;
```

**\##** `const` **et** `let`

J'utilise `const` lorsqu'une référence ne doit pas être réassignée :

``` ts

const apiUrl = '/api/analysis';
```

J'utilise `let` lorsqu'une variable doit pouvoir changer :

``` ts

let counter = 0;
```

## Méthodes

Dans mon composant :

``` ts

analyze(): void {

    this.loading = true;

}
```

`void` indique que ma méthode ne retourne pas de valeur utile.

## Union de types

``` ts

analysis: AnalysisResponse | null = null;
```

Cela signifie que, tant qu'aucune analyse n'a été reçue, `analysis` vaut

`null`. Après une réponse du backend, elle peut contenir un

`AnalysisResponse`.

## Accès optionnel

``` ts

this.analysis.opening
```

J'utilise `.` lorsqu'une donnée peut être absente.

## Valeur de secours

``` ts

const name = this.analysis.opening.opening.name  'Ouverture inconnue';
```

`` me permet de fournir une valeur si l'expression précédente vaut

`null` ou `undefined`.

  -------------------------
  \# 5. Mon composant
  Angular Le composant est
  une brique fondamentale
  d'Angular.
  -------------------------
  \# 6. Les décorateurs que
  j'utilise Un décorateur
  Angular commence par `@`.

  Dans mon projet, je
  rencontre principalement
  :

  \`\`\`ts

  @Component(...)

  @Injectable(...)

  @ViewChild(...)

  \`\`\`

  **\##** `@Component`

  Il indique à Angular
  qu'une classe est un
  composant et fournit ses

  métadonnées.

  \`\`\`ts

  @Component({

      selector: 'app-root',

      imports: \[

          CommonModule,

          FormsModule,

         
  NgxChessBoardModule

      \],

      templateUrl:
  './app.component.html',

      styleUrl:
  './app.component.scss'

  })

  \`\`\`

  **\###** `selector`

  \`\`\`ts

  selector: 'app-root'

  \`\`\`

  Il identifie la balise
  correspondant à mon
  composant racine.

  **\###** `imports`

  Dans mon composant
  standalone, j'y déclare
  les fonctionnalités dont
  mon

  template a besoin.

  **\###** `templateUrl`

  Il relie mon composant à
  son fichier HTML.

  **\###** `styleUrl`

  Il relie mon composant à
  son fichier SCSS.

  **\##** `@Injectable`

  Je l'utilise sur mon
  service :

  \`\`\`ts

  @Injectable({

      providedIn: 'root'

  })

  export class
  AnalysisService {

  }

  \`\`\`

  Cela permet à Angular de
  gérer le service par
  injection de dépendances.

  **\##** `@ViewChild`

  Je l'utilise pour accéder
  à mon échiquier depuis
  `AppComponent`.

  \`\`\`ts

  @ViewChild('board')

  board!:
  NgxChessBoardView;

  \`\`\`
  -------------------------

# 7. Mon template HTML

Mon template Angular n'est pas du HTML statique.

Il peut lire l'état de mon composant et déclencher ses méthodes.

``` html

\<button

    [disabled]="loading"

    (click)="analyze()">

    Analyser

\</button>
```

Ici :

-     `[disabled]` reçoit une valeur TypeScript ;

-     `(click)` déclenche une méthode TypeScript.

Le template devient donc la projection visuelle de l'état de mon

composant.

  ------------------------------
  \# 8. Le data binding Le
  \*\*\*\*data binding\*\*\*\*
  relie mon TypeScript et mon
  HTML.
  ------------------------------
  \# 9. Les événements
  utilisateur Les événements me
  permettent de transformer une
  action utilisateur en

  appel TypeScript.

  Le cas central de Chess Agent
  est :

  \`\`\`html

  \<button (click)="analyze()"\>

      Analyser

  \</button\>

  \`\`\`

  Le clic déclenche :

  \`\`\`ts

  analyze(): void {

      // lancement de l'analyse

  }

  \`\`\`

  Je peux également récupérer un
  événement avec `$event` :

  \`\`\`html

  \<input
  (input)="onInput(\$event)"\>

  \`\`\`

  Dans mon application, cette
  mécanique relie directement
  les interactions

  de l'utilisateur à l'état du
  composant.
  ------------------------------

# 10. Le contrôle du template

Angular moderne propose notamment `@if` et `@for`.

**\##** `@if`

Je peux afficher un bloc seulement pendant une analyse :

``` html

@if (loading) {

    \<p>Analyse en cours...\</p>

}
```

Ou gérer plusieurs états :

``` html

@if (loading) {

    \<p>Analyse en cours...\</p>

} @else {

    \<p>Prêt.\</p>

}
```

**\##** `@for`

Je peux afficher les vidéos reçues :

``` html

@for (video of videos; track video.id) {

    \<p>{{ video.title }}\</p>

}
```

Le `track` aide Angular à suivre les éléments du DOM de manière

efficace.

  ---------------------
  **\# 11. Le
  formulaire FEN et**
  `ngModel`
  ---------------------
  \# 12. Mon service
  Angular Je ne veux
  pas transformer
  `AppComponent` en
  tiroir où tout finit

  empilé.

  Je sépare donc la
  communication avec
  FastAPI dans
  `AnalysisService`.

  \`\`\`text

  AppComponent

      ↓

  AnalysisService

      ↓

  FastAPI

  \`\`\`

  Mon composant gère
  principalement :

  \-   l'état de
  l'interface ;

  \-   les interactions
  utilisateur ;

  \-   l'affichage des
  résultats.

  Mon service gère :

  \-   la construction
  des appels HTTP ;

  \-   l'envoi des
  requêtes ;

  \-   le typage des
  réponses ;

  \-   le streaming
  d'analyse lorsque je
  l'utilise.

  Exemple :

  \`\`\`ts

  @Injectable({

      providedIn:
  'root'

  })

  export class
  AnalysisService {

      private readonly
  http =
  inject(HttpClient);

  }

  \`\`\`
  ---------------------

# 13. L'injection de dépendances

Angular possède son propre système d'injection de dépendances.

Au lieu de créer mon service manuellement :

``` ts

const service = new AnalysisService(...);
```

je demande à Angular de me le fournir :

``` ts

private readonly analysisService = inject(

    AnalysisService

);
```

Je peux ensuite écrire :

``` ts

this.analysisService.analyze(...);
```

Cette approche améliore :

-     le découplage ;

-     la réutilisation ;

-     les tests ;

-     la gestion des dépendances.

Je retrouve ici une idée proche de celle utilisée dans mon backend : une

classe doit utiliser ses dépendances sans nécessairement être

responsable de leur construction.

  --------------------------------
  \# 14. HttpClient et mon API
  FastAPI `HttpClient` est le pont
  HTTP entre mon frontend et mon
  backend.
  --------------------------------
  \# 15. Observable et RxJS Les
  appels HTTP sont asynchrones.

  Lorsque je demande une analyse,
  Stockfish, Lichess, Milvus,
  YouTube et

  le reste du workflow peuvent
  prendre du temps. Mon navigateur
  ne doit

  pas se figer pendant cette
  attente.

  Angular utilise les
  \*\*\*\*Observable\*\*\*\* de
  RxJS pour représenter ce type de

  flux.

  Mon service peut retourner :

  \`\`\`ts

  Observable\<AnalysisResponse\>

  \`\`\`

  Cela ne signifie pas que je
  possède déjà la réponse. Cela
  signifie que

  je possède un flux auquel je
  peux réagir lorsqu'une réponse
  arrivera.

  Dans mon composant :

  \`\`\`ts

  this.analysisService.analyze(

      this.fen,

      this.moves

  ).subscribe({

      next: (response) =\> {

          this.analysis =
  response;

      },

      error: () =\> {

          this.error = 'Impossible
  d'analyser la position.';

      }

  });

  \`\`\`

  Je retiens :

  \-   `next` : une valeur est
  reçue ;

  \-   `error` : le flux échoue ;

  \-   `complete` : le flux se
  termine, lorsqu'il est pertinent
  de le

      traiter.

  Pour mon analyse en streaming,
  cette notion devient encore plus

  importante puisque plusieurs
  événements de progression
  peuvent arriver

  avant le résultat final.
  --------------------------------

# 16. Mes modèles TypeScript

Je type les données échangées avec FastAPI.

Exemple simplifié :

``` ts

export interface AnalysisRequest {

    fen: string;

    moves: string[];

}
```

Et :

``` ts

export interface AnalysisResponse {

    status: AnalysisStatus;

    fen: string;

    explanation: string | null;

}
```

Mes modèles peuvent être imbriqués afin de représenter :

-     l'ouverture ;

-     les statistiques Lichess ;

-     l'évaluation Stockfish ;

-     les meilleurs coups ;

-     les documents ;

-     les vidéos ;

-     la réponse générée.

Le typage m'apporte :

-     l'autocomplétion ;

-     une meilleure lisibilité ;

-     la détection d'incohérences ;

-     un contrat frontend/backend explicite.

Je dois être particulièrement vigilant aux noms JSON. Si FastAPI

retourne :

``` json

{

    "white_win_rate": 42

}
```

mon frontend doit connaître `white_win_rate`, sauf si je mets en place

une transformation explicite.

  ----------------------------------------------------------
  \# 17.\*\* `ViewChild` \*\*et mon échiquier Mon échiquier
  est un composant enfant.
  ----------------------------------------------------------
  \# 18. SCSS et mise en page Mon interface Chess Agent est
  organisée en trois zones principales :

  \`\`\`text

  ┌────────────────┬────────────────────┬────────────────┐

  │ Lichess        │                    │ Réponse LLM    │

  │                │     Échiquier      │                │

  │ Stockfish      │                    │ Vidéos         │

  └────────────────┴────────────────────┴────────────────┘

  \`\`\`

  CSS Grid convient bien à cette structure :

  \`\`\`scss

  .dashboard {

      display: grid;

      grid-template-columns: 1fr 2fr 1fr;

      gap: 20px;

  }

  \`\`\`

  Pour aligner des éléments internes, je peux utiliser
  Flexbox :

  \`\`\`scss

  .actions {

      display: flex;

      gap: 12px;

      align-items: center;

  }

  \`\`\`

  Pour les écrans plus étroits :

  \`\`\`scss

  @media (max-width: 900px) {

      .dashboard {

          grid-template-columns: 1fr;

      }

  }

  \`\`\`

  Je retiens que le SCSS ne porte pas la logique métier. Il
  organise et

  habille l'interface.
  ----------------------------------------------------------

# 19. Les états de mon interface

Mon interface doit représenter l'état réel de l'application.

Je peux avoir :

``` ts

loading = false;

analysis: AnalysisResponse | null = null;

error: string | null = null;
```

Au lancement :

``` ts

this.loading = true;

this.error = null;
```

En cas de succès :

``` ts

next: (response) => {

    this.analysis = response;

    this.loading = false;

}
```

En cas d'erreur :

``` ts

error: () => {

    this.error = 'Impossible d’analyser la position.';

    this.loading = false;

}
```

Je peux donc considérer mon interface comme une petite machine à états :

``` text

PRÊT

  ↓ clic

ANALYSE EN COURS

  ↓

  ├── SUCCÈS

  ├── SUCCÈS PARTIEL

  └── ÉCHEC
```

Dans mon projet, l'écran de progression peut aller plus loin en

affichant les étapes réelles du workflow reçues par streaming.

  --------------------------------------
  \# 20. Le cycle complet d'une analyse
  Chess Agent C'est la chaîne la plus
  importante à savoir expliquer.
  --------------------------------------
  \# 21. Les erreurs que je dois éviter
  **\## Mettre toute la logique dans**
  `AppComponent`

  Je dois conserver une séparation
  claire :

  \`\`\`text

  Component

      ↓

  Service

      ↓

  API

  \`\`\`

  **\## Oublier** `FormsModule`

  Si j'utilise :

  \`\`\`html

  \[(ngModel)\]

  \`\`\`

  je dois importer `FormsModule`.

  \## Traiter un Observable comme une
  réponse immédiate Ceci est
  conceptuellement incorrect :

  \`\`\`ts

  const result =
  this.analysisService.analyze(...);

  console.log(result.explanation);

  \`\`\`

  `result` est un Observable, pas
  directement un `AnalysisResponse`.

  \## Accéder sans garde à une donnée
  facultative À éviter si `opening` peut
  être absente :

  \`\`\`ts

  this.analysis.opening.opening.name

  \`\`\`

  Je préfère :

  \`\`\`ts

  this.analysis.opening.opening.name

  \`\`\`

  \## Désynchroniser Angular et FastAPI
  Mes interfaces TypeScript doivent
  suivre les contrats réellement

  retournés par mon API.

  C'est l'un des points les plus
  importants de mon architecture.
  --------------------------------------

# 22. Organisation professionnelle de mon frontend

Comme mon POC reste volontairement simple, je ne veux pas créer une

architecture inutilement lourde.

Une organisation compacte peut suffire :

``` text

src/app/

├── app.component.ts

├── app.component.html

├── app.component.scss

├── analysis.model.ts

├── analysis-progress.model.ts

└── analysis.service.ts
```

Si Chess Agent devient un produit plus important, je pourrai évoluer

vers :

``` text

src/app/

├── core/

├── shared/

├── features/

│   └── analysis/

│       ├── components/

│       ├── models/

│       └── services/

└── app.component.ts
```

Je retiens qu'une architecture professionnelle n'est pas celle qui

possède le plus de dossiers. C'est celle dont la complexité reste

proportionnée au besoin.

  ------------------------------------------
  \# 23. Ce que je dois savoir expliquer en
  soutenance \## Pourquoi ai-je utilisé
  Angular  \> J'utilise Angular pour
  construire l'interface de Chess Agent. Il
  me
  ------------------------------------------
  \# 24. Exercices appliqués à Chess Agent
  \## Exercice 1 Que produit :

  \`\`\`ts

  title = 'Chess Agent';

  \`\`\`

  avec :

  \`\`\`html

  \<h1\>{{ title }}\</h1\>

  \`\`\`

  \*\*\*\*Réponse :\*\*\*\*

  \`\`\`html

  \<h1\>Chess Agent\</h1\>

  \`\`\`

  \## Exercice 2 Que se passe-t-il avec :

  \`\`\`html

  \<button
  (click)="analyze()"\>Analyser\</button\>

  \`\`\`

  \*\*\*\*Réponse :\*\*\*\*

  Quand l'utilisateur clique, Angular
  appelle la méthode `analyze()` de

  mon composant.

  \## Exercice 3 Que fait :

  \`\`\`html

  \<button \[disabled\]="loading"\>

  \`\`\`

  \*\*\*\*Réponse :\*\*\*\*

  Le bouton est désactivé lorsque ma
  propriété `loading` vaut `true`.

  \## Exercice 4 Que signifie :

  \`\`\`ts

  analysis: AnalysisResponse \| null = null;

  \`\`\`

  \*\*\*\*Réponse :\*\*\*\*

  Avant toute analyse, je n'ai aucun
  résultat et la valeur est `null`.

  Après une réponse valide, elle peut
  contenir un objet

  `AnalysisResponse`.

  \## Exercice 5 Que signifie :

  \`\`\`ts

  private readonly analysisService = inject(

      AnalysisService

  );

  \`\`\`

  \*\*\*\*Réponse :\*\*\*\*

  Je demande à Angular de m'injecter
  `AnalysisService`. `private` limite

  son accès à ma classe et `readonly`
  m'empêche de réassigner cette

  référence.

  \## Exercice 6 Je dois être capable
  d'expliquer sans notes :

  \`\`\`text

  (click)

     ↓

  analyze()

     ↓

  AnalysisService

     ↓

  HttpClient

     ↓

  FastAPI

     ↓

  LangGraph

     ↓

  réponse

     ↓

  Observable

     ↓

  AppComponent

     ↓

  HTML

  \`\`\`

  Si je maîtrise cette chaîne, je comprends
  le cœur du fonctionnement de

  mon frontend Chess Agent.
  ------------------------------------------

# 25. Fiche mémo

## Les syntaxes Angular que je dois reconnaître

  Syntaxe             Ce qu'elle signifie

  ------------------- ------------------------------------

  `{{ value }}`       interpolation

  `[property]`        TypeScript → propriété

  `(event)`           événement → TypeScript

  `[(ngModel)]`       liaison bidirectionnelle

  `@if`               affichage conditionnel

  `@for`              répétition

  `@Component`        déclaration d'un composant

  `@Injectable`       classe injectable

  `@ViewChild`        référence vers la vue ou un enfant

  `inject(Service)`   injection de dépendance

  `Observable\<T>`     flux asynchrone typé

  `.subscribe()`      abonnement à un Observable

  `.`                accès optionnel

  ``                valeur de secours

## Les fichiers que je dois comprendre en priorité

``` text

app.component.ts

        │

        ├── état et logique de l'interface

        ↓

app.component.html

        │

        └── affichage et événements

app.component.scss

        │

        └── apparence et mise en page

analysis.service.ts

        │

        └── communication avec FastAPI

analysis.model.ts

        │

        └── contrats TypeScript
```

## Mes cinq questions quand je lis mon code Angular

1\.  \*\*\*\*Quelle donnée mon composant possède-t-il \*\*\*\*

2\.  \*\*\*\*Comment mon HTML affiche-t-il cette donnée \*\*\*\*

3\.  \*\*\*\*Quel événement utilisateur déclenche l'action \*\*\*\*

4\.  \*\*\*\*Quel service mon composant appelle-t-il \*\*\*\*

5\.  \*\*\*\*Comment la réponse modifie-t-elle l'état puis l'écran
\*\*\*\*

------------------------------------------------------------------------

# Conclusion

Dans Chess Agent, Angular constitue la couche d'interaction entre

l'utilisateur et mon backend.

Je peux résumer son fonctionnement ainsi :

``` text

Échiquier / FEN

      ↓

app.component.html

      ↓ événements et bindings

app.component.ts

      ↓

analysis.service.ts

      ↓ HttpClient

FastAPI

      ↓

Workflow LangGraph

      ↓

Réponse JSON / progression

      ↓

Observable

      ↓

app.component.ts

      ↓

mise à jour de l'état

      ↓

app.component.html

      ↓

Résultat affiché
```

Je ne dois donc pas apprendre séparément les composants, les services,

les Observables, les décorateurs et les bindings.

Dans mon projet, ils appartiennent tous à la même chaîne :

\*\*l'utilisateur agit, mon composant réagit, mon service communique
avec

FastAPI, le backend effectue l'analyse, Angular reçoit le résultat et

mon template l'affiche.\*\*

C'est cette mécanique complète que je dois être capable de comprendre,

de maintenir et d'expliquer.
