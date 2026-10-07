### Overview: components, standalone, modules, services

**In simple words:** Angular is a full framework written in TypeScript. It gives you components (screen parts), services (shared logic and data), routing, forms, HTTP and testing in one package. In older Angular, every component had to belong to an *NgModule* (a group that lists components). Modern Angular uses *standalone* components, which list their own dependencies in `imports`.

**Real-life example:** NgModules are like a hospital where every doctor must belong to a department before they can work. Standalone components are like independent clinics, each with its own list of equipment.

**Interview question:** What is a standalone component and how is it different from an NgModule?

**Simple answer:** A standalone component declares what it needs in its own `imports` array, so no NgModule is required. It is the default since Angular 17. The app starts with `bootstrapApplication`, and global providers like the router and HttpClient go in the app config. NgModules still work and are common in older projects.

```typescript
bootstrapApplication(AppComponent, {
  providers: [provideRouter(routes), provideHttpClient()]
});
```

### Dependency Injection: hierarchy, providedIn, inject()

**In simple words:** *Dependency Injection* (DI) means Angular creates objects like services and gives them to the classes that need them. It works like DI in ASP.NET Core. Angular has a tree of *injectors* (object suppliers): component level, route level and root level. `providedIn: 'root'` creates one shared instance for the whole app.

**Real-life example:** If you need a stapler, you first check your desk, then your team's cupboard, then the office store room. You take the first one you find.

**Interview question:** What is the difference between `providedIn: 'root'` and providing a service in a component?

**Simple answer:** `providedIn: 'root'` gives one shared instance for the whole app, like `AddSingleton`, and it is removed from the bundle if unused. Adding a service to a component's `providers` creates a new instance for each component instance and its children. Today I usually use the `inject()` function instead of constructor injection.

```typescript
@Injectable({ providedIn: 'root' })
export class OrderService {
  private http = inject(HttpClient);
}
```

### Component anatomy and data binding

**In simple words:** A component has a TypeScript class, an HTML template and styles. *Data binding* connects the class and the template. `{{ }}` shows a value, `[prop]` sets an element property, `(event)` listens to events, and `[(ngModel)]` does both directions. `@Input` passes data into a child; `@Output` sends events up to the parent.

**Real-life example:** It is like a shop display. The price tag shows the price from the system (`{{ }}`), and when a customer presses the "buy" button, the system is told (`(click)`).

**Interview question:** What types of data binding does Angular have?

**Simple answer:** Interpolation `{{ value }}` and property binding `[prop]` go from component to view. Event binding `(event)` goes from view to component. Two-way binding `[(ngModel)]` combines both. Angular also sanitises bound values, so it is safe from script injection by default.

```text
<h3>{{ product.name }}</h3>
<button (click)="add()" [disabled]="product.stock === 0">Add</button>
<input [(ngModel)]="qty">
```

### New control flow: @if, @for, @switch, @defer

**In simple words:** Angular 17 added built-in template blocks: `@if`, `@for`, `@switch` and `@defer`. They replace the older `*ngIf`, `*ngFor` and `*ngSwitch`. `@for` must have `track`, which tells Angular how to identify each item. `@defer` loads a heavy part of the page later, for example when it scrolls into view.

**Real-life example:** `@defer` is like a restaurant that brings dessert only when you ask for it, so your main course arrives faster.

**Interview question:** What is `track` in `@for`, and what does `@defer` do?

**Simple answer:** `track` gives each item an identity, like a key in React, so Angular can reuse DOM rows when the list changes. I use a stable id like `track o.id`. `@defer` lazy-loads a component into a separate file, with triggers like `on viewport` or `on idle`, and shows a placeholder until it loads.

```text
@for (o of orders; track o.id) {
  <li>#{{ o.id }}</li>
} @empty { <li>No orders yet.</li> }

@defer (on viewport) { <app-reviews /> } @placeholder { <p>...</p> }
```

### Directives

**In simple words:** A *directive* adds behaviour to an element in the template. There are three kinds. Components are directives with a template. *Attribute directives* change how an element looks or behaves, like `ngClass`. *Structural directives* add or remove elements, like the old `*ngIf`.

**Real-life example:** An attribute directive is like a highlighter pen — the text stays, but it looks different. A structural directive is like scissors — it decides if a part of the page is there at all.

**Interview question:** What is the difference between an attribute directive and a structural directive?

**Simple answer:** An attribute directive changes the appearance or behaviour of an existing element. A structural directive changes the DOM structure by adding or removing elements using a template. Note that hiding a button with a role directive is only for the user experience; the API must still check permissions.

```typescript
@Directive({ selector: '[appHighlight]', standalone: true })
export class HighlightDirective {
  private el = inject(ElementRef);
  @HostListener('mouseenter') on() { this.el.nativeElement.style.background = 'yellow'; }
}
```

### Pipes

**In simple words:** A *pipe* formats a value in the template, like `{{ price | currency }}` or `{{ date | date:'short' }}`. *Pure* pipes (the default) run again only when the input value or reference changes, so they are fast. The `async` pipe subscribes to an Observable, shows its latest value, and unsubscribes automatically.

**Real-life example:** A pipe is like a currency converter at an airport. You give it a number and it gives you the same amount in a nicer format.

**Interview question:** What is the difference between a pure and an impure pipe?

**Simple answer:** A pure pipe runs only when its input changes by reference or value, so it is cheap. An impure pipe runs on every change detection cycle and can be slow. Because pure pipes check the reference, changing an array in place will not update them; you need a new array.

```typescript
@Pipe({ name: 'truncate', standalone: true })
export class TruncatePipe implements PipeTransform {
  transform(v: string, max = 50) { return v.length <= max ? v : v.slice(0, max) + '...'; }
}
```

### HttpClient basics against an ASP.NET Core API

**In simple words:** `HttpClient` is Angular's service for calling APIs. Each call returns a *cold Observable*: nothing is sent until someone subscribes. Each subscription sends a new request. It reads JSON automatically and throws an `HttpErrorResponse` for non-2xx status codes, unlike `fetch`.

**Real-life example:** It is like a pizza order form you fill in but have not sent. Nothing happens until you press "Order" (subscribe). Press it twice and you get two pizzas.

**Interview question:** Why does my HttpClient call not send any request?

**Simple answer:** HttpClient returns a cold Observable, so the request only goes out when you subscribe, or when the `async` pipe subscribes. Also, subscribing twice sends two requests. If several places need the same result, I use `shareReplay(1)` or bind it once in the template.

```typescript
getOrders(page = 1) {
  return this.http.get<Order[]>(`${this.base}/orders`, { params: { page } });
}
// this.orderService.getOrders().subscribe(o => this.orders = o);
```

### Functional interceptors: JWT, refresh-on-401, global errors

**In simple words:** An *interceptor* is code that runs on every HTTP request and response. It can add the JWT header, refresh an expired token and retry, or show a global error message. Modern Angular writes interceptors as simple functions and registers them with `withInterceptors([...])`. Requests pass through them in order, and responses come back in reverse order.

**Real-life example:** It is like the mail room of an office. Every outgoing letter gets a company stamp, and every returned letter is checked before it reaches your desk.

**Interview question:** How do you attach a JWT and handle token expiry in Angular?

**Simple answer:** A functional interceptor clones the request and adds `Authorization: Bearer <token>`. On a 401, it calls the refresh endpoint once. Other failed requests wait, then are replayed with the new token. If refresh fails, the user is logged out.

```typescript
export const authInterceptor: HttpInterceptorFn = (req, next) => {
  const token = inject(AuthService).accessToken();
  return next(token
    ? req.clone({ setHeaders: { Authorization: `Bearer ${token}` } })
    : req);
};
```

### Template-driven vs reactive

**In simple words:** Angular has two ways to build forms. *Template-driven* forms keep the form model in the HTML using `ngModel`. *Reactive* forms build the model in the TypeScript class with `FormGroup` and `FormControl`. Reactive forms are typed, easier to test, and better for dynamic fields and complex validation.

**Real-life example:** A template-driven form is like a quick paper note. A reactive form is like a bank's official form with clear rules for each box, checked by a system.

**Interview question:** Template-driven or reactive forms — which do you choose?

**Simple answer:** I choose reactive forms for anything beyond a tiny form. The model is in code and strongly typed, validators are simple testable functions, and `FormArray` makes dynamic rows easy. Template-driven forms are fine for something small like a two-field login.

### Reactive form: typed, validators, async validator, FormArray

**In simple words:** In a reactive form you create a typed `FormGroup` in code. *Validators* are functions that check a value, like `Validators.required`. An *async validator* checks with the server, for example "is this email already used?". A `FormArray` holds a list of controls, so the user can add or remove rows like order lines.

**Real-life example:** A loan form has fixed boxes (FormGroup), rules for each box (validators), a phone call to verify your employer (async validator), and a list where you can add more family members (FormArray).

**Interview question:** How do you write an async validator that does not spam the server?

**Simple answer:** I return an Observable from an `AsyncValidatorFn`. I add a short `timer` delay with `switchMap`, so old checks are cancelled when the user types again. I set `updateOn: 'blur'` to check less often, and use `catchError` so an API failure does not block the form.

```typescript
form = this.fb.group({
  email: ['', [Validators.required, Validators.email]],
  lines: this.fb.array([this.newLine()])
});
addLine() { this.form.controls.lines.push(this.newLine()); }
```

### Observables: cold vs hot, Observable vs Promise

**In simple words:** An *Observable* is a stream that can send zero, one or many values over time. It is lazy: nothing runs until you subscribe, and you can unsubscribe to cancel. A *cold* Observable starts fresh for each subscriber, like an HTTP call. A *hot* Observable is already running and is shared, like mouse clicks.

**Real-life example:** A cold Observable is like a recorded movie — each viewer starts from the beginning. A hot Observable is like live TV — if you join late, you miss what already happened.

**Interview question:** What is the difference between an Observable and a Promise?

**Simple answer:** A Promise starts right away, gives exactly one result and cannot be cancelled. An Observable is lazy, can give many values, can be cancelled by unsubscribing, and has many operators like `map` and `switchMap`. Angular's HttpClient returns cold Observables.

### Subjects

**In simple words:** A *Subject* is an Observable that you can also push values into with `.next()`. Many subscribers receive the same values. A `BehaviorSubject` needs a start value and always gives the latest value to new subscribers. A `ReplaySubject` replays the last few values to late subscribers.

**Real-life example:** A `Subject` is like a radio announcement — you only hear it if you are listening now. A `BehaviorSubject` is like a notice board — anyone who comes later still sees the latest notice.

**Interview question:** What is the difference between `Subject`, `BehaviorSubject` and `ReplaySubject`?

**Simple answer:** `Subject` has no memory, so late subscribers only see future values. `BehaviorSubject` holds a current value, gives it to new subscribers, and has `.value`, so it suits state like the cart. `ReplaySubject(n)` replays the last n values. I expose them with `asObservable()` so other code cannot call `next()`.

```typescript
private readonly _lines$ = new BehaviorSubject<CartLine[]>([]);
readonly lines$ = this._lines$.asObservable();
add(l: CartLine) { this._lines$.next([...this._lines$.value, l]); }
```

### Core operators

**In simple words:** *Operators* are functions you chain in `pipe()` to change a stream. `map` changes values, `filter` drops some, `debounceTime` waits for a pause. The four "flattening" operators start an inner call, like HTTP, for each value. They differ in what happens when a new value arrives while the last call is still running.

**Real-life example:** `switchMap` is like changing your taxi destination — the old trip is cancelled. `concatMap` is a queue at a counter. `mergeMap` is many counters at once. `exhaustMap` ignores new people until the current one is done.

**Interview question:** What is the difference between `switchMap`, `mergeMap`, `concatMap` and `exhaustMap`?

**Simple answer:** `switchMap` cancels the previous call, so the latest wins — good for search. `mergeMap` runs calls in parallel. `concatMap` runs them one by one, in order — good for saves. `exhaustMap` ignores new triggers while busy — good for a submit button. I put `catchError` inside the inner call so one error does not kill the whole stream.

```typescript
results$ = this.term.valueChanges.pipe(
  debounceTime(300),
  distinctUntilChanged(),
  switchMap(t => this.api.search(t).pipe(catchError(() => of([]))))
);
```

### Unsubscribing and memory leaks

**In simple words:** If you subscribe to a stream that never ends, like `interval`, a `Subject` or form `valueChanges`, the subscription keeps running after the component is destroyed. This keeps the component in memory and causes strange updates. HTTP calls finish by themselves, so they are safe.

**Real-life example:** It is like a newspaper subscription you forgot to cancel after moving house. Papers keep arriving at an empty home.

**Interview question:** How do you prevent memory leaks from subscriptions in Angular?

**Simple answer:** I avoid manual subscriptions by using the `async` pipe or `toSignal`, which unsubscribe for me. When I must subscribe, I use `takeUntilDestroyed()`. In older code I use `takeUntil(destroy$)` as the last operator. For one value only, `take(1)` is enough.

```typescript
constructor() {
  this.ws.orders$.pipe(takeUntilDestroyed())
    .subscribe(o => this.latest.set(o));
}
```

### Change detection: Default vs OnPush, zone.js, zoneless

**In simple words:** *Change detection* is how Angular updates the screen when data changes. Classic Angular uses *zone.js*, which watches browser events and timers, then checks the components. With the *Default* strategy, every component is checked each time. With *OnPush*, a component is checked only when its inputs get a new reference, an event happens inside it, or a signal it reads changes. *Zoneless* apps drop zone.js and rely on signals.

**Real-life example:** Default is like a teacher checking every student's homework every day. OnPush is like checking only the students who raised their hand.

**Interview question:** What does OnPush do, and what triggers a check?

**Simple answer:** OnPush skips the component unless an input gets a new reference, a DOM event fires inside it, an `async` pipe emits, a signal it reads changes, or `markForCheck()` is called. So you must update data immutably, creating new objects instead of changing old ones. It is one of the biggest performance wins.

```typescript
// Wrong with OnPush: same reference
this.order.total = 99;
// Right: new reference
this.orders = this.orders.map(o => o.id === id ? { ...o, total: 99 } : o);
```

### Signals: signal, computed, effect

**In simple words:** A *signal* is a value that tells Angular when it changes. You read it by calling it, like `count()`, and change it with `set` or `update`. `computed` makes a read-only value from other signals and recalculates only when needed. `effect` runs side-effect code, like saving to `localStorage`, when signals it reads change.

**Real-life example:** A signal is like a shared spreadsheet cell. A `computed` cell is a formula that updates when its input cells change. An `effect` is an email alert sent when a cell changes.

**Interview question:** What are signals and why did Angular add them?

**Simple answer:** Signals are reactive values that Angular tracks exactly, so it knows which views to update. This gives faster, more precise change detection and allows apps without zone.js. I use `computed` for derived values and `effect` only for side effects, not for copying state.

```typescript
lines = signal<CartLine[]>([]);
total = computed(() => this.lines().reduce((s, l) => s + l.qty * l.price, 0));
add(l: CartLine) { this.lines.update(ls => [...ls, l]); }
```

### Signal inputs, outputs, model and queries

**In simple words:** Modern Angular has signal versions of component inputs and outputs. `input()` creates a read-only signal input. `output()` replaces `@Output` with `EventEmitter`. `model()` creates a two-way binding, used as `[(qty)]`. `viewChild()` and `contentChildren()` find child elements and return signals.

**Real-life example:** An `input()` is like a menu the customer gives the chef — the chef reads it but cannot change it. `model()` is like a shared order sheet that both the waiter and the customer can edit.

**Interview question:** What are the benefits of signal inputs over `@Input`?

**Simple answer:** Signal inputs are read-only inside the component, so you cannot change them by mistake. They work directly with `computed`, so you rarely need `ngOnChanges`. `model()` makes two-way binding for custom components easy.

```typescript
productId = input.required<number>();
max = input(10);
qty = model(1);
limitReached = output<number>();
```

### Interop: toSignal and toObservable

**In simple words:** Signals and RxJS work together. `toSignal` turns an Observable into a signal and unsubscribes automatically when the component is destroyed. `toObservable` turns a signal into an Observable, so you can use RxJS operators like `switchMap` on it.

**Real-life example:** It is like a currency exchange counter. You can change dollars into rupees and back, depending on which shop you want to use.

**Interview question:** When do you use signals and when do you use RxJS?

**Simple answer:** They complement each other. I use signals for component state and values the template reads. I use RxJS for async streams where timing matters, like debounce, cancel and retry. Then I convert the result to a signal with `toSignal` so the template stays simple.

```typescript
page = signal(1);
result = toSignal(
  toObservable(this.page).pipe(switchMap(p => this.orders.list(p)))
);
```

### Options in increasing order of ceremony

**In simple words:** There are several ways to manage state in Angular, from simple to heavy. Start with state inside the component. Next is a service that holds state in a `BehaviorSubject` or signals. Then NgRx SignalStore for more structure. NgRx Store, the Redux pattern, is the most structured and needs the most code.

**Real-life example:** It is like storing money: a wallet (component), a home safe (service), a small bank account (SignalStore), or a full bank with audits (NgRx Store).

**Interview question:** When would you use NgRx instead of a service with signals or `BehaviorSubject`?

**Simple answer:** I use NgRx Store when many features share and change the same state, when I need devtools and a history of every change, or when a large team needs one strict pattern. For most CRUD apps, a signal-based service or NgRx SignalStore is enough with much less code.

```typescript
@Injectable({ providedIn: 'root' })
export class CartService {
  private readonly _lines = signal<CartLine[]>([]);
  readonly lines = this._lines.asReadonly();
}
```

### NgRx Store overview

**In simple words:** NgRx Store is the Redux pattern for Angular. Components *dispatch* actions. Pure *reducers* create the new state. *Selectors* read parts of the state. *Effects* handle side effects like HTTP calls and then dispatch success or failure actions. All state lives in one store.

**Real-life example:** It is like a restaurant kitchen. The waiter hands in an order slip (action). The head chef follows fixed recipes to update the dishes (reducer). A runner fetches ingredients from the store room (effect).

**Interview question:** What are actions, reducers, selectors and effects in NgRx?

**Simple answer:** Actions describe what happened, like "Load Orders". Reducers are pure functions that make a new state from the old state and an action. Selectors read and derive data from the state. Effects listen for actions, call APIs and dispatch new actions with the result, keeping side effects out of reducers.

```typescript
export const ordersReducer = createReducer(initialState,
  on(OrdersActions.load, s => ({ ...s, loading: true })),
  on(OrdersActions.loadSuccess, (s, { orders }) => ({ ...s, orders, loading: false }))
);
```

### NgRx SignalStore (mention)

**In simple words:** NgRx SignalStore is a newer, lighter store built on signals. You build it from small pieces: `withState` for data, `withComputed` for derived values and `withMethods` for actions. It has much less code than classic NgRx Store, but still gives a clear structure.

**Real-life example:** If NgRx Store is a full bank branch, SignalStore is a modern banking app — the same safe rules, but with fewer forms to fill in.

**Interview question:** What is NgRx SignalStore and when would you use it?

**Simple answer:** It is a signal-based store from NgRx with very little code. I use it in medium or large apps when I want structure for shared state without the actions, reducers and effects of the full Redux pattern. Components read its signals directly in the template.

```typescript
export const CartStore = signalStore(
  { providedIn: 'root' },
  withState({ lines: [] as CartLine[] }),
  withMethods(store => ({ clear() { patchState(store, { lines: [] }); } }))
);
```

### JWT login flow end-to-end with ASP.NET Core

**In simple words:** The user logs in once. The ASP.NET Core API returns a short-lived *access token* (a JWT) and a long-lived *refresh token* in an HttpOnly cookie (JavaScript cannot read it). Angular keeps the access token in memory and an interceptor adds it to every API call. When it expires, the app uses the refresh cookie to get a new one.

**Real-life example:** At a concert, you show your ticket once and get a wristband for the day (access token). If the wristband expires, you show your ticket again at the desk (refresh token) to get a new one.

**Interview question:** Where should you store the JWT in an Angular app, and who checks it?

**Simple answer:** I keep the access token in memory and the refresh token in an HttpOnly, Secure cookie, because `localStorage` can be stolen by an XSS attack. Decoding the token in the browser is only for showing the name or roles. The API checks the signature, issuer, audience and expiry on every request.

```typescript
login(email: string, password: string) {
  return this.http.post<{ accessToken: string }>('/api/auth/login',
    { email, password }, { withCredentials: true })
    .pipe(tap(r => this._token.set(r.accessToken)));
}
```

### MSAL / SSO with Microsoft Entra ID

**In simple words:** For company apps, users sign in with their Microsoft work account. This is *SSO* (single sign-on: one login for many apps). The Angular app never sees the password; it redirects to *Microsoft Entra ID* (formerly Azure AD). The MSAL library gets tokens for specific *scopes* (permissions). `MsalGuard` protects routes, and `MsalInterceptor` adds the right token to API calls.

**Real-life example:** It is like a company ID card issued by the main office. You show it at every building, and no building needs to store your password.

**Interview question:** How does MSAL Angular protect routes and API calls?

**Simple answer:** `MsalGuard` sends the user to the Entra ID login if they are not signed in. `MsalInterceptor` checks the request URL in its map, gets a token for the right scope, silently when possible, and adds the Bearer header. The ASP.NET Core API validates the token with Microsoft.Identity.Web and checks the scope or roles.
