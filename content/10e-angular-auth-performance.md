## Authentication

### JWT login flow end-to-end with ASP.NET Core

**Definition.** The SPA sends credentials to the API once, receives a short-lived **access token** (JWT) and a long-lived **refresh token**, attaches the access token as `Authorization: Bearer` on every API call, and refreshes it on expiry. The API validates the signature, issuer, audience and expiry on every request.

```text
1. LoginComponent  --POST /api/auth/login {email, password}-->  AuthController
2. API validates, returns { accessToken (15 min) }  + Set-Cookie: refresh=...; HttpOnly; Secure
3. AuthService stores accessToken in memory (signal); decodes claims for UI (name, roles)
4. authInterceptor adds Authorization: Bearer <accessToken> to API calls
5. API: UseAuthentication -> JwtBearer validates -> [Authorize(Roles="Admin")] -> 200 / 401 / 403
6. 401 -> interceptor calls POST /api/auth/refresh (cookie) -> new access token -> replay request
7. Refresh fails -> logout -> /login?returnUrl=...
8. Guards (authGuard, roleGuard) use AuthService to control navigation (UX only)
```

```csharp
// ASP.NET Core side (abbreviated)
builder.Services.AddAuthentication(JwtBearerDefaults.AuthenticationScheme)
    .AddJwtBearer(o => o.TokenValidationParameters = new TokenValidationParameters
    {
        ValidIssuer = "https://shop.contoso.com", ValidAudience = "shop-spa",
        IssuerSigningKey = new SymmetricSecurityKey(Encoding.UTF8.GetBytes(jwtKey)),
        ValidateIssuer = true, ValidateAudience = true, ValidateLifetime = true,
        ClockSkew = TimeSpan.FromSeconds(30)
    });
// POST /api/auth/login  -> { accessToken }   and Response.Cookies.Append("refresh", ..., HttpOnly)
// POST /api/auth/refresh -> rotate refresh token, return a new access token
```

```typescript
// auth.service.ts
type JwtClaims = { sub: string; name: string; email: string; role?: string | string[]; exp: number };

@Injectable({ providedIn: 'root' })
export class AuthService {
  private http = inject(HttpClient);
  private router = inject(Router);
  private api = inject(API_URL);

  private readonly _token = signal<string | null>(null);              // memory only
  readonly accessToken = this._token.asReadonly();
  readonly claims = computed(() => decodeJwt(this._token()));
  readonly user = computed(() => this.claims() && { name: this.claims()!.name, roles: rolesOf(this.claims()!) });

  login(email: string, password: string) {
    return this.http.post<{ accessToken: string }>(`${this.api}/auth/login`,
      { email, password }, { withCredentials: true })
      .pipe(tap(r => this._token.set(r.accessToken)));
  }
  refresh() {                                                          // used by the interceptor
    return this.http.post<{ accessToken: string }>(`${this.api}/auth/refresh`, null,
      { withCredentials: true })
      .pipe(map(r => r.accessToken), tap(t => this._token.set(t)));
  }
  logout() {
    this._token.set(null);
    this.http.post(`${this.api}/auth/logout`, null, { withCredentials: true }).subscribe();
    this.router.navigate(['/login']);
  }
  isAuthenticated() {
    const c = this.claims();
    return !!c && c.exp * 1000 > Date.now();                           // check expiry, not just presence
  }
  hasRole(role: string) { return this.user()?.roles.includes(role) ?? false; }
}

function decodeJwt(token: string | null): JwtClaims | null {
  if (!token) return null;
  try {
    const payload = token.split('.')[1].replace(/-/g, '+').replace(/_/g, '/');
    return JSON.parse(atob(payload));             // decoding is NOT validation - the API validates
  } catch { return null; }
}
const ROLE_URI = 'http://schemas.microsoft.com/ws/2008/06/identity/claims/role';
function rolesOf(c: JwtClaims & Record<string, unknown>): string[] {
  const r = c.role ?? (c[ROLE_URI] as string | string[] | undefined);  // .NET may emit the long URI
  return r ? (Array.isArray(r) ? r : [r]) : [];
}
```

The guard (`authGuard`, `roleGuard`) is in the Routing section and the interceptor with refresh queue in the HttpClient section. On app start, call `refresh()` once (e.g. via `provideAppInitializer` in v19+, or `APP_INITIALIZER`) so a page reload restores the session from the HttpOnly cookie.

| Storage for tokens | XSS can steal? | CSRF risk | Survives reload |
|---|---|---|---|
| Memory (signal/variable) | hard (only while running) | no | **no** - needs refresh-cookie bootstrap |
| `localStorage` | **yes** | no | yes |
| `sessionStorage` | **yes** | no | per tab |
| HttpOnly Secure SameSite cookie | **no** | yes - mitigate with SameSite + anti-forgery | yes |

:::warn Decoding a JWT in the browser is not verifying it
Anyone can edit a token's payload in the browser; the signature is checked only by the API. Use decoded claims for display and navigation only. Every authorization decision is made again on the server with `[Authorize]` and policies.
:::

### MSAL / SSO with Microsoft Entra ID

**Definition.** For corporate SSO the SPA doesn't handle passwords at all: it redirects the user to **Microsoft Entra ID** (formerly Azure AD) with the **authorization code flow + PKCE**, receives an ID token (who the user is) and access tokens for specific **scopes** (what the app may call). `@azure/msal-angular` wraps `@azure/msal-browser` with Angular services: `MsalService`, `MsalGuard` (route protection), `MsalInterceptor` (attaches the right token per URL), `MsalBroadcastService` (login events).

Setup in Entra ID: register **two apps** - the API (expose a scope such as `api://<api-client-id>/access_as_user`) and the SPA (platform type *Single-page application*, redirect URI `http://localhost:4200`, granted permission to that scope).

```typescript
// app.config.ts - standalone setup (msal-angular v3/v4 style; check the docs for your version)
export function msalInstanceFactory(): IPublicClientApplication {
  return new PublicClientApplication({
    auth: {
      clientId: '<spa-client-id>',
      authority: 'https://login.microsoftonline.com/<tenant-id>',
      redirectUri: 'http://localhost:4200',
      postLogoutRedirectUri: 'http://localhost:4200'
    },
    cache: { cacheLocation: BrowserCacheLocation.SessionStorage }
  });
}

export function msalGuardConfigFactory(): MsalGuardConfiguration {
  return { interactionType: InteractionType.Redirect,
           authRequest: { scopes: ['api://<api-client-id>/access_as_user'] },
           loginFailedRoute: '/login-failed' };
}

export function msalInterceptorConfigFactory(): MsalInterceptorConfiguration {
  const protectedResourceMap = new Map<string, Array<string>>([
    ['https://localhost:5001/api/', ['api://<api-client-id>/access_as_user']],  // our API
    ['https://graph.microsoft.com/v1.0/me', ['user.read']]                      // Graph
  ]);
  return { interactionType: InteractionType.Redirect, protectedResourceMap };
}

export const appConfig: ApplicationConfig = {
  providers: [
    provideRouter(routes),
    provideHttpClient(withInterceptorsFromDi()),       // MsalInterceptor is class-based
    { provide: HTTP_INTERCEPTORS, useClass: MsalInterceptor, multi: true },
    { provide: MSAL_INSTANCE, useFactory: msalInstanceFactory },
    { provide: MSAL_GUARD_CONFIG, useFactory: msalGuardConfigFactory },
    { provide: MSAL_INTERCEPTOR_CONFIG, useFactory: msalInterceptorConfigFactory },
    MsalService, MsalGuard, MsalBroadcastService
  ]
};

// routes: { path: 'orders', canActivate: [MsalGuard], loadComponent: ... }
// AppComponent: handle the redirect response once on startup, e.g.
//   this.msal.handleRedirectObservable().subscribe();   (or bootstrap MsalRedirectComponent)
```

```csharp
// ASP.NET Core API validating Entra ID tokens (Microsoft.Identity.Web)
builder.Services.AddAuthentication(JwtBearerDefaults.AuthenticationScheme)
    .AddMicrosoftIdentityWebApi(builder.Configuration.GetSection("AzureAd"));
// appsettings: "AzureAd": { "Instance": "https://login.microsoftonline.com/",
//                           "TenantId": "<tenant-id>", "ClientId": "<api-client-id>" }

[Authorize]
[RequiredScope("access_as_user")]
[ApiController, Route("api/orders")]
public class OrdersController : ControllerBase { /* ... */ }
```

Key concepts to say: MSAL caches tokens and uses `acquireTokenSilent` (refresh token in the background) before falling back to interactive login; each API gets its own **audience**, so the token for Graph cannot call your API; app roles defined in the API registration arrive in the `roles` claim; never request scopes the SPA doesn't need. msal-browser v3+ requires the instance to be initialised before use (msal-angular handles it in its services) - verify initialisation steps for the exact library version.

:::q Custom JWT vs MSAL/Entra ID - when do you use which?
Custom JWT (ASP.NET Core Identity issuing tokens) suits public consumer apps with their own user store. Entra ID with MSAL suits enterprise/employee apps: SSO with Microsoft 365 accounts, MFA and conditional access managed centrally, no passwords in our system, and tokens scoped per API. In both cases the Angular side is the same shape: guard for routes, interceptor for tokens, API validates.
:::

## Angular Performance

| Technique | What it does |
|---|---|
| `OnPush` + immutable data / signals | skip checking unchanged subtrees |
| `track` in `@for` (`trackBy` in `*ngFor`) | reuse DOM rows instead of re-creating them |
| Lazy routes (`loadComponent`/`loadChildren`) + preloading | smaller initial bundle |
| `@defer` blocks | lazy-load heavy widgets on viewport/interaction/idle |
| Pure pipes / `computed` instead of method calls in templates | template functions run on every CD cycle |
| CDK virtual scroll (`cdk-virtual-scroll-viewport`) | render only visible rows of long lists |
| `NgOptimizedImage` (`ngSrc`) | lazy loading, priority hints, correct sizes |
| `runOutsideAngular` | high-frequency events without triggering CD |
| SSR + hydration (`ng add @angular/ssr`, `provideClientHydration()`) | fast first paint, SEO; hydration reuses server DOM instead of re-rendering; incremental hydration and event replay in newer versions |
| Bundle budgets + analysis | fail the build when bundles grow; inspect with `source-map-explorer` / esbuild stats |
| Unsubscribe / `async` pipe | avoid leaks that slow the app over time |

```json
"budgets": [
  { "type": "initial", "maximumWarning": "500kB", "maximumError": "1MB" },
  { "type": "anyComponentStyle", "maximumWarning": "4kB", "maximumError": "8kB" }
]
```

```html
<!-- calls total() on every change detection: avoid for anything non-trivial -->
<td>{{ calculateTotal(order) }}</td>
<!-- better: a pure pipe or a computed signal -->
<td>{{ order | orderTotal }}</td>
```

:::scenario The orders grid (2,000 rows) freezes when a WebSocket pushes price updates
Profile with Angular DevTools: every push triggers app-wide CD and every row is re-checked; `*ngFor` without `trackBy` re-creates all rows on each new array. Fix: `OnPush` on grid and rows, `@for ... track row.id`, update only the changed row immutably (or hold rows in signals), throttle/buffer the socket stream (`bufferTime(250)`), run the socket listener outside Angular's zone, and virtual-scroll the grid. Consider server-side paging for the initial load.
:::

## Testing Basics

**TestBed** creates a testing module/injector; with standalone components you `imports: [TheComponent]`. Use `provideHttpClientTesting()` + **`HttpTestingController`** to assert and answer HTTP calls without a server. The default runner was Karma + Jasmine (Karma is deprecated); newer projects use Jest or Vitest (Vitest is the default in recent CLI versions - verify).

```typescript
describe('OrderService', () => {
  let service: OrderService;
  let http: HttpTestingController;

  beforeEach(() => {
    TestBed.configureTestingModule({ providers: [provideHttpClient(), provideHttpClientTesting()] });
    service = TestBed.inject(OrderService);
    http = TestBed.inject(HttpTestingController);
  });
  afterEach(() => http.verify());                       // no unexpected/outstanding requests

  it('loads an order by id', () => {
    let result: Order | undefined;
    service.get(7).subscribe(o => (result = o));

    const req = http.expectOne('https://localhost:5001/api/orders/7');
    expect(req.request.method).toBe('GET');
    req.flush({ id: 7, total: 120, status: 'Paid' });   // respond
    expect(result?.total).toBe(120);
  });

  it('surfaces ProblemDetails on 404', () => {
    service.get(9).subscribe({ error: e => expect(e.status).toBe(404) });
    http.expectOne(r => r.url.endsWith('/orders/9'))
        .flush({ title: 'Not Found' }, { status: 404, statusText: 'Not Found' });
  });
});

describe('ProductCardComponent', () => {
  it('emits the product id when Add is clicked', async () => {
    await TestBed.configureTestingModule({ imports: [ProductCardComponent] }).compileComponents();
    const fixture = TestBed.createComponent(ProductCardComponent);
    fixture.componentRef.setInput('product', { id: 1, name: 'pen', price: 2, stock: 5 });
    let emitted: number | undefined;
    fixture.componentInstance.added.subscribe((id: number) => (emitted = id));
    fixture.detectChanges();

    fixture.nativeElement.querySelector('button').click();
    expect(emitted).toBe(1);
  });
});
```

Also: mock services with `{ provide: OrderService, useValue: jasmine.createSpyObj(...) }` (or `vi.fn()`), test guards/interceptors with `TestBed.runInInjectionContext`, and use `fakeAsync`/`tick` for debounced logic.

## React vs Angular

| | React | Angular |
|---|---|---|
| Type | UI **library**; you pick router, forms, HTTP, state | full **framework**, batteries included |
| Language | JavaScript or TypeScript (JSX/TSX) | TypeScript (first-class) |
| Templates | JSX - JavaScript expressions in markup | HTML templates with Angular syntax (`@if`, bindings, pipes) |
| Data binding | one-way + callbacks | one-way + two-way (`[(ngModel)]`, `model()`) |
| Reactivity / updates | re-render component, virtual DOM diff | change detection (zone.js) moving to **signals** + zoneless |
| DI | none built in (Context as substitute) | hierarchical DI built in |
| State | useState/Context, Redux Toolkit, Zustand, TanStack Query | services + RxJS/signals, NgRx, SignalStore |
| Async | Promises, async/await | **RxJS Observables** throughout (HttpClient, forms, router) |
| Forms | controlled inputs / React Hook Form | template-driven and reactive forms built in |
| Routing | React Router / TanStack Router / framework | `@angular/router` built in |
| Tooling | Vite, Next.js | Angular CLI (esbuild/Vite), schematics, `ng update` |
| Learning curve | gentler start, many choices later | steeper start (RxJS, DI), consistent conventions |
| Typical fit | flexible products, startups, SSR via Next.js | large enterprise apps, many teams, strong conventions |

:::tip How to answer "React or Angular?"
Don't pick a winner. Say: "Angular gives a consistent, opinionated stack - DI, router, forms, HTTP and testing - which pays off in large enterprise teams; it maps nicely to how we structure ASP.NET Core (services, DI, interceptors like middleware). React is a lighter library with a huge ecosystem, so we choose the pieces. I've used both; the core ideas - components, one-way data flow, immutable state, lazy loading - transfer."
:::

## Quick-fire Q&A

:::q What is a standalone component?
A component that declares its own dependencies in `imports` instead of being declared in an NgModule. It is the default for new projects since v17 (implicit `standalone: true` since v19), bootstrapped with `bootstrapApplication`, and lazy-loaded with `loadComponent`.
:::

:::q How does Angular DI resolve a dependency?
It walks the element injector tree (component `providers` up through ancestors), then the environment injectors (route providers, then root), then the platform injector. The first provider found wins; if none, `NullInjectorError`. `providedIn: 'root'` gives an app-wide tree-shakable singleton.
:::

:::q Observable vs Promise?
A Promise is eager, resolves once and can't be cancelled. An Observable is lazy, can emit many values, can be cancelled by unsubscribing, and has rich operators. Angular's HttpClient returns cold Observables: no request until subscribed.
:::

:::q switchMap vs mergeMap vs concatMap vs exhaustMap in one line each?
`switchMap`: cancel previous, latest wins (search). `mergeMap`: run in parallel (independent calls). `concatMap`: queue in order (sequential saves). `exhaustMap`: ignore new triggers while busy (submit button).
:::

:::q How do you implement search-as-you-type?
`control.valueChanges.pipe(debounceTime(300), map(trim), distinctUntilChanged(), switchMap(t => api.search(t).pipe(catchError(() => of([])))))`, rendered with the `async` pipe or `toSignal`. Debounce reduces calls, `distinctUntilChanged` skips repeats, `switchMap` cancels stale requests, and the inner `catchError` keeps the stream alive.
:::

:::q forkJoin vs combineLatest?
`forkJoin` emits once when all sources complete, with each one's last value: parallel HTTP calls. `combineLatest` emits whenever any source emits, with the latest of each: reactive filters.
:::

:::q BehaviorSubject vs Subject?
`BehaviorSubject` needs an initial value, keeps the current value (`.value`) and replays it to new subscribers: use it for state. `Subject` has no current value; late subscribers only see future emissions: use it for events.
:::

:::q How do you avoid memory leaks with subscriptions?
Prefer the `async` pipe or `toSignal`, which unsubscribe automatically. For manual subscriptions use `takeUntilDestroyed()` (or `takeUntil(destroy$)` as the last operator). HTTP observables complete on their own; `interval`, `fromEvent`, Subjects and store selects do not.
:::

:::q What are signals and why did Angular add them?
Signals are reactive values (`signal`, `computed`, `effect`) that Angular tracks precisely, so it knows exactly which views to update. That enables fine-grained change detection, simpler OnPush components, signal inputs/outputs/model, and removing zone.js (zoneless). RxJS remains for async streams; `toSignal`/`toObservable` bridge them.
:::

:::q Default vs OnPush change detection?
Default checks the component on every CD cycle. OnPush checks it only when an input reference changes, an event fires inside it, an `async` pipe emits, a signal it reads changes, or `markForCheck` is called. OnPush requires immutable updates.
:::

:::q Order of lifecycle hooks?
constructor, `ngOnChanges`, `ngOnInit`, `ngDoCheck`, `ngAfterContentInit`, `ngAfterContentChecked`, `ngAfterViewInit`, `ngAfterViewChecked`, then `ngOnDestroy`. `ngOnChanges`/`ngDoCheck` and the two "Checked" hooks repeat on later changes; `afterNextRender` runs browser-only after rendering.
:::

:::q How do you attach a JWT and handle expiry in Angular?
A functional `HttpInterceptorFn` clones the request with `Authorization: Bearer <token>` for API URLs. On 401 it calls the refresh endpoint once, queues other failing requests on a `BehaviorSubject`, replays them with `switchMap` when the new token arrives, and logs out if refresh fails. Route guards (`CanActivateFn` returning `true` or a `UrlTree`) handle navigation; the ASP.NET Core API enforces `[Authorize]`.
:::

:::q How does MSAL Angular protect routes and API calls?
`MsalGuard` on routes triggers Entra ID login (redirect or popup) when no account is signed in. `MsalInterceptor` looks up the request URL in `protectedResourceMap`, acquires a token for the mapped scopes (silently from cache/refresh token when possible) and adds the Bearer header. The API validates it with Microsoft.Identity.Web and checks the scope or app roles.
:::

:::q Template-driven vs reactive forms?
Template-driven keeps the model in the template with `ngModel`: quick for tiny forms. Reactive builds a typed `FormGroup` in code with validator functions, `FormArray` for dynamic rows and observable `valueChanges`: easier to test and scale. I default to reactive.
:::

:::q How would you improve the load time of a large Angular app?
Lazy-load feature routes and preload them, use `@defer` for heavy widgets, keep budgets in `angular.json` and analyse bundles, use `NgOptimizedImage`, enable SSR with hydration for first paint, and remove unused dependencies. At runtime use OnPush/signals, `track` and virtual scrolling.
:::
