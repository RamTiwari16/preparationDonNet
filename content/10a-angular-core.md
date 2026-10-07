## Angular Architecture

### Overview: components, standalone, modules, services

**Definition.** Angular is a full, opinionated TypeScript framework (UI + router + forms + HTTP + DI + testing + CLI). The building blocks: **components** (template + class + styles), **directives** and **pipes** (template behaviour/formatting), **services** (logic and data, injected via DI), and **routes** (URL to component). This guide targets Angular 17/18/19; newer releases keep the same concepts, and the direction is signals, zoneless change detection and standalone only (check the current release notes).

**Standalone vs NgModule.** Until v14 every component had to be declared in an `NgModule`. Standalone components (stable v15, **default for new projects from v17**, and `standalone: true` is the implicit default from **v19**) declare their own dependencies in `imports`. NgModules still work and are common in older code bases; interviews ask for both.

| | NgModule (legacy) | Standalone (modern) |
|---|---|---|
| Where dependencies are declared | `declarations` / `imports` of the module | `imports` of each component |
| Bootstrap | `platformBrowserDynamic().bootstrapModule(AppModule)` | `bootstrapApplication(AppComponent, appConfig)` |
| Providers | `providers` in `@NgModule`, `forRoot()` | `ApplicationConfig.providers` with `provideRouter()`, `provideHttpClient()` |
| Lazy loading | `loadChildren: () => import(...).then(m => m.XModule)` | `loadComponent` / `loadChildren` returning routes |
| Boilerplate | more, "which module declares this?" errors | less, self-describing components |

```typescript
// main.ts
import { bootstrapApplication } from '@angular/platform-browser';
bootstrapApplication(AppComponent, appConfig).catch(err => console.error(err));

// app.config.ts
export const appConfig: ApplicationConfig = {
  providers: [
    provideZoneChangeDetection({ eventCoalescing: true }),
    provideRouter(routes, withComponentInputBinding()),       // route params -> inputs
    provideHttpClient(withInterceptors([authInterceptor, errorInterceptor]))
  ]
};

// Legacy equivalent for comparison
@NgModule({
  declarations: [AppComponent, OrderListComponent],
  imports: [BrowserModule, HttpClientModule, FormsModule, AppRoutingModule],
  bootstrap: [AppComponent]
})
export class AppModule {}
```

### Dependency Injection: hierarchy, providedIn, inject()

**Definition.** Angular's DI creates and supplies class instances (services, tokens). A class asks for a dependency; the **injector** finds a provider and returns an instance. Same idea as ASP.NET Core DI; the main difference is a *hierarchy of injectors* that follows the component/route tree.

```typescript
@Injectable({ providedIn: 'root' })              // singleton for the whole app, tree-shakable
export class OrderService {
  private http = inject(HttpClient);             // modern: inject() function
  private apiUrl = inject(API_URL);              // token

  getOrders(page = 1) {
    return this.http.get<Order[]>(`${this.apiUrl}/orders`, { params: { page, pageSize: 20 } });
  }
}
// Older constructor style (still valid): constructor(private http: HttpClient) {}

export const API_URL = new InjectionToken<string>('API_URL', {
  providedIn: 'root', factory: () => 'https://localhost:5001/api'
});
```

**Resolution order (hierarchy).** For a dependency requested by a component, Angular looks: (1) the component's own `providers` / `viewProviders`, (2) parent/ancestor components up the element tree, (3) the **environment injector** (route-level `providers` on a `Route`, lazy route subtree), (4) the root injector (`providedIn: 'root'`, `ApplicationConfig.providers`), (5) the platform injector; otherwise `NullInjectorError: No provider for X`.

| Where provided | Lifetime / scope | .NET analogy |
|---|---|---|
| `providedIn: 'root'` / app config | one instance for the app | `AddSingleton` |
| `providers` on a lazy **Route** | one per lazy route subtree | scoped to a feature |
| `providers` on a **component** | a new instance per component instance (and its children) | `AddScoped`/`AddTransient`-like |

Provider forms: `{ provide: T, useClass: Impl }`, `useValue`, `useFactory` (+ `deps`), `useExisting` (alias), `multi: true` (collects many, e.g. `HTTP_INTERCEPTORS`). `inject()` works only in an *injection context*: constructors, field initialisers, factory functions, functional guards/interceptors/resolvers; not inside a later callback unless you capture it earlier or use `runInInjectionContext`.

:::q Constructor injection vs inject()? Which is preferred now?
`inject()` is the modern style (Angular 14+). It works in field initialisers, allows functional guards/interceptors, avoids long constructors and base-class constructor pass-through, and is easier to compose in reusable functions. Constructor injection is still valid and often seen in older code. Behaviour is the same.
:::

:::q providedIn: 'root' vs providing a service in a component?
`root` creates a single shared instance (and is tree-shaken if unused): use for app-wide services such as API clients and auth. A component-level `providers` entry creates a separate instance for each component instance and its subtree - use it for per-component state (a form wizard store, a list's selection state) that must not leak across instances.
:::

### Component anatomy and data binding

```typescript
@Component({
  selector: 'app-product-card',
  standalone: true,                                  // implicit default from v19
  imports: [CurrencyPipe, RouterLink, FormsModule],
  templateUrl: './product-card.component.html',
  styleUrl: './product-card.component.scss',          // styleUrl (singular) since v17
  changeDetection: ChangeDetectionStrategy.OnPush
})
export class ProductCardComponent {
  @Input({ required: true }) product!: Product;       // parent -> child (signal input() later)
  @Output() added = new EventEmitter<number>();       // child -> parent
  qty = 1;
  add() { this.added.emit(this.product.id); }
}
```

```html
<article class="card" [class.out-of-stock]="product.stock === 0">   <!-- class binding -->
  <h3>{{ product.name | titlecase }}</h3>                           <!-- interpolation -->
  <img [src]="product.imageUrl" [alt]="product.name">                <!-- property binding -->
  <p>{{ product.price | currency:'USD' }}</p>
  <input type="number" [(ngModel)]="qty" min="1">                    <!-- two-way -->
  <button (click)="add()" [disabled]="product.stock === 0">Add</button> <!-- event binding -->
  <a [routerLink]="['/products', product.id]">Details</a>
</article>
<!-- parent -->
<app-product-card [product]="p" (added)="cart.add($event)" />
```

| Syntax | Direction | Example |
|---|---|---|
| `{{ expr }}` | component -> view (string) | `{{ order.total }}` |
| `[prop]="expr"` | component -> DOM **property** | `[disabled]="busy"`, `[src]="url"` |
| `[attr.x]`, `[class.x]`, `[style.width.px]` | attributes/classes/styles | `[attr.aria-label]="label"` |
| `(event)="handler($event)"` | DOM -> component | `(click)="save()"` |
| `[(ngModel)]="v"` | both | sugar for `[ngModel]="v" (ngModelChange)="v = $event"` |
| `#ref` | template reference variable | `<input #q>` then `q.value` |

`[(x)]` ("banana in a box") works for any pair `x` + `xChange`; custom components do this with `model()` (signals file). `ngModel` needs `FormsModule` in `imports`. Property binding sets DOM properties (not HTML attributes), values are sanitised (`[innerHTML]`, URLs) - Angular is XSS-safe by default unless you call `bypassSecurityTrust*`.

### New control flow: @if, @for, @switch, @defer

**Definition.** Angular 17 introduced built-in template control flow with a block syntax. It replaces `*ngIf`, `*ngFor`, `*ngSwitch` (structural directives from `CommonModule`). Benefits: no imports needed, better type narrowing, less runtime code, and **`@for` requires `track`** so DOM reuse is not forgotten. Later versions deprecate the old directives (check the current release notes); a migration schematic exists: `ng generate @angular/core:control-flow`.

```html
@if (orders$ | async; as orders) {
  @for (o of orders; track o.id; let i = $index, last = $last) {
    <li [class.last]="last">{{ i + 1 }}. #{{ o.id }} - {{ o.total | currency }}</li>
  } @empty {
    <li>No orders yet.</li>
  }
} @else {
  <app-spinner />
}

@switch (order.status) {
  @case ('Paid')    { <span class="ok">Paid</span> }
  @case ('Pending') { <span class="warn">Pending</span> }
  @default          { <span>Unknown</span> }
}
```

`@for` context variables: `$index`, `$first`, `$last`, `$even`, `$odd`, `$count`. Old syntax equivalents:

```html
<li *ngFor="let o of orders; trackBy: trackById; let i = index">...</li>
<div *ngIf="loaded; else loading">...</div><ng-template #loading>...</ng-template>
```

#### @defer (deferrable views)

`@defer` lazy-loads a *standalone* component/directive/pipe (and its dependencies) into a separate chunk, triggered by a condition. It is declarative code splitting inside templates.

```html
@defer (on viewport; prefetch on idle) {
  <app-reviews [productId]="product.id" />          <!-- heavy chart/reviews widget -->
} @placeholder (minimum 300ms) {
  <div class="skeleton" style="height: 200px"></div>
} @loading (after 100ms; minimum 500ms) {
  <app-spinner />
} @error {
  <p>Reviews could not be loaded.</p>
}
```

Triggers: `on idle` (default), `on viewport`, `on interaction`, `on hover`, `on immediate`, `on timer(5s)`, `when <boolean expr>`. `prefetch` triggers download the chunk early without rendering it. The deferred component must not be referenced elsewhere in the same file (otherwise it is bundled eagerly). In SSR the placeholder renders on the server.

:::q @for vs *ngFor - what changed and what is `track`?
`@for` is built-in syntax (no `CommonModule` import) and `track` is mandatory: it is the expression that identifies items (like React's `key` or `*ngFor trackBy`) so Angular reuses DOM nodes when the array changes instead of re-creating all of them. It also has `@empty` and is faster in the framework's benchmarks. Use a stable id: `track item.id`; `track $index` only for static lists.
:::

### Directives

**Definition.** A directive adds behaviour to an element/template. Three kinds: **components** (directive with a template), **attribute directives** (change appearance/behaviour of an element: `ngClass`, `ngStyle`, custom), and **structural directives** (change the DOM structure by adding/removing elements: `*ngIf`, `*ngFor`; the `*` is sugar for an `<ng-template>`).

```typescript
// Attribute directive: <p appHighlight="lightblue">
@Directive({ selector: '[appHighlight]', standalone: true })
export class HighlightDirective {
  @Input('appHighlight') color = 'yellow';
  private el = inject<ElementRef<HTMLElement>>(ElementRef);

  @HostListener('mouseenter') onEnter() { this.el.nativeElement.style.background = this.color; }
  @HostListener('mouseleave') onLeave() { this.el.nativeElement.style.background = ''; }
}

// Structural directive: <button *appHasRole="'Admin'">Delete</button>
@Directive({ selector: '[appHasRole]', standalone: true })
export class HasRoleDirective {
  private tpl = inject<TemplateRef<unknown>>(TemplateRef);
  private vcr = inject(ViewContainerRef);
  private auth = inject(AuthService);

  @Input() set appHasRole(role: string) {
    this.vcr.clear();
    if (this.auth.hasRole(role)) this.vcr.createEmbeddedView(this.tpl);
  }
}
```

:::warn Hiding a button is not security
`*appHasRole` only improves UX. The ASP.NET Core endpoint must still be protected with `[Authorize(Roles = "Admin")]` or a policy: a user can call the API directly.
:::

### Pipes

**Definition.** A pipe transforms a value in a template: `{{ value | pipeName:arg }}`. Built-in: `date`, `currency`, `number`, `percent`, `uppercase`, `titlecase`, `slice`, `json`, `keyvalue`, `async`, `i18nPlural`.

| | Pure pipe (default) | Impure pipe (`pure: false`) |
|---|---|---|
| Re-evaluated | only when the **input reference/primitive** changes | on **every** change-detection cycle |
| Cost | negligible | can be expensive |
| Use for | formatting, mapping | rare: needs to react to mutation or time (`async` is impure by design) |
| Gotcha | mutating an array in place does **not** re-run it | sorting/filtering large arrays in an impure pipe tanks performance |

```typescript
@Pipe({ name: 'truncate', standalone: true })          // pure
export class TruncatePipe implements PipeTransform {
  transform(value: string | null | undefined, max = 50, suffix = '...'): string {
    if (!value) return '';
    return value.length <= max ? value : value.slice(0, max).trimEnd() + suffix;
  }
}
// {{ product.description | truncate:80 }}
```

**`async` pipe.** `{{ orders$ | async }}` subscribes to an Observable/Promise, returns the latest value, marks the view for check (works with `OnPush`) and **unsubscribes automatically on destroy**. It is the cleanest way to avoid manual subscriptions and memory leaks. Don't use it twice on the same cold observable in one template (two HTTP calls): bind once with `@if (x$ | async; as x)`.

## Routing

**Definition.** The Angular Router maps URLs to components, supports nested routes (`<router-outlet>`), lazy loading, guards, resolvers and URL parameters.

```typescript
// app.routes.ts
export const routes: Routes = [
  { path: '', pathMatch: 'full', redirectTo: 'products' },
  { path: 'login',
    loadComponent: () => import('./auth/login.component').then(m => m.LoginComponent) },
  { path: 'products',
    loadChildren: () => import('./products/products.routes').then(m => m.PRODUCT_ROUTES) },
  { path: 'orders', canActivate: [authGuard],
    loadChildren: () => import('./orders/orders.routes').then(m => m.ORDER_ROUTES) },
  { path: 'admin', canMatch: [roleGuard('Admin')],       // route is not even matched/loaded
    loadChildren: () => import('./admin/admin.routes').then(m => m.ADMIN_ROUTES) },
  { path: '**', loadComponent: () => import('./not-found.component').then(m => m.NotFoundComponent) }
];

// products/products.routes.ts - child routes of a lazy feature
export const PRODUCT_ROUTES: Routes = [
  { path: '', component: ProductListComponent, title: 'Products' },
  { path: ':id', component: ProductDetailComponent,
    resolve: { product: productResolver },                // data ready before activation
    children: [{ path: 'reviews', component: ReviewsComponent }] }   // rendered in nested outlet
];
```

```typescript
// Functional resolver
export const productResolver: ResolveFn<Product> = route =>
  inject(ProductService).getById(Number(route.paramMap.get('id')));

// Functional guards (v15+). Class-based guards are deprecated.
export const authGuard: CanActivateFn = (route, state) => {
  const auth = inject(AuthService);
  if (auth.isAuthenticated()) return true;                // token present and not expired
  return inject(Router).createUrlTree(['/login'], { queryParams: { returnUrl: state.url } });
};

export const roleGuard = (...roles: string[]): CanActivateFn => () => {
  const auth = inject(AuthService);
  return roles.some(r => auth.hasRole(r)) || inject(Router).createUrlTree(['/forbidden']);
};

export const unsavedChangesGuard: CanDeactivateFn<{ dirty: boolean }> = c =>
  !c.dirty || confirm('Discard unsaved changes?');
```

```typescript
// Reading params - three ways
@Component({ /* ... */ })
export class ProductDetailComponent {
  // 1. With withComponentInputBinding(): route params, query params AND resolver data -> inputs
  @Input() id!: string;
  @Input() product!: Product;                             // from `resolve: { product }`

  // 2. Observable (reacts when :id changes while the component is reused)
  private route = inject(ActivatedRoute);
  id$ = this.route.paramMap.pipe(map(p => p.get('id')));

  // 3. Snapshot (only valid if the component is recreated on every navigation)
  snapshotId = this.route.snapshot.paramMap.get('id');

  private router = inject(Router);
  goBack() { this.router.navigate(['/products'], { queryParams: { page: 2 } }); }
}
```

```html
<nav>
  <a routerLink="/products" routerLinkActive="active">Products</a>
  <a [routerLink]="['/orders', order.id]">Order</a>
</nav>
<router-outlet />
```

**Lazy loading** splits the app into chunks per route, loaded on first navigation: `loadComponent` for a single standalone component, `loadChildren` for a route array (or an NgModule in legacy code). Add `withPreloading(PreloadAllModules)` (or a custom strategy) in `provideRouter` to fetch chunks in the background after the first render.

:::scenario User with an expired token opens a bookmarked /orders URL
`authGuard` runs before activation. If `isAuthenticated()` only checks that a token exists, the page loads and every API call gets 401. Better: check the `exp` claim, and when expired either redirect to `/login?returnUrl=/orders` or try a silent refresh first (guard returns an `Observable<boolean | UrlTree>`). The 401 interceptor is the second line of defence; the API is the authority.
:::

:::q What is the difference between canActivate, canMatch and canLoad?
`canActivate` runs after the route is matched and the chunk may already be downloaded; it decides whether navigation proceeds. `canMatch` (v14.2+) decides whether a route *matches at all*, so a failing guard prevents the lazy chunk from loading and lets another route with the same path match (role-based variants of a route). `canLoad` is the older, deprecated equivalent for lazy modules.
:::
