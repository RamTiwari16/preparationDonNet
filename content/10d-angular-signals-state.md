## Change Detection and Signals

### Change detection: Default vs OnPush, zone.js, zoneless

**Definition.** *Change detection (CD)* is how Angular keeps the DOM in sync with component data: it walks the component tree top-down, re-evaluates template bindings and updates DOM nodes whose values changed. Classic Angular uses **zone.js**, which monkey-patches async browser APIs (events, `setTimeout`, promises, XHR) so Angular knows *when* something might have changed and triggers a CD pass over the app.

| | `Default` | `OnPush` |
|---|---|---|
| Component is checked | on **every** CD cycle | only when marked dirty |
| Marked dirty by | anything | a new **input reference**, an event handled in the component or its children, the `async` pipe emitting, a **signal** read in its template changing, or `markForCheck()` |
| Mutating an input object in place | shows up | **not** shown (same reference) |
| Cost | grows with app size | checks only dirty subtrees |

```typescript
@Component({
  selector: 'app-order-row',
  changeDetection: ChangeDetectionStrategy.OnPush,
  template: `{{ order().id }} - {{ order().total | currency }}`
})
export class OrderRowComponent { order = input.required<Order>(); }

// parent: WRONG with OnPush (same array/object reference)
this.order.total = 99;
// RIGHT: new reference
this.orders = this.orders.map(o => (o.id === id ? { ...o, total: 99 } : o));
```

`ChangeDetectorRef` APIs: `markForCheck()` (mark this component and ancestors dirty for the next cycle - use after a manual subscription updates a field in an OnPush component), `detectChanges()` (run CD for this subtree now), `detach()`/`reattach()` (take a widget out of CD). `NgZone.runOutsideAngular()` runs high-frequency work (scroll, mousemove, chart animation) without triggering CD.

**ExpressionChangedAfterItHasBeenCheckedError** (dev only): a binding changed during the same CD pass after it was checked, typically because `ngAfterViewInit` or a child changed parent state. Fix the data flow (compute earlier, use a signal), don't hide it with `setTimeout`.

**Zoneless direction.** Signals tell Angular *exactly* which views need updating, so zone.js becomes unnecessary: smaller bundles, no monkey-patching, clearer stack traces. `provideExperimentalZonelessChangeDetection()` arrived in v18; it was renamed `provideZonelessChangeDetection()` and promoted in later versions, and newer CLI versions generate zoneless apps by default (verify for your Angular version). Zoneless apps rely on signals, the `async` pipe, `markForCheck` and event handlers to schedule CD.

:::q What does OnPush do, and what triggers a check?
An OnPush component is skipped by change detection unless it is marked dirty: an `@Input`/`input()` receives a new reference, a DOM event fires inside it, an `async` pipe in its template emits, a signal read by its template changes, or code calls `markForCheck()`. It forces immutable data flow and is the single biggest CD performance win.
:::

### Signals: signal, computed, effect

**Definition.** A **signal** is a reactive value container: read it by calling it (`count()`), write with `set`/`update`. Angular tracks which signals a template, `computed` or `effect` reads, and re-runs only those consumers when the signal changes. Introduced in v16, core APIs stable by v17-v20 (`signal`/`computed` early; `effect`, `toSignal`, `linkedSignal` stabilised around v20 - check the docs for your version).

```typescript
@Component({
  selector: 'app-cart',
  changeDetection: ChangeDetectionStrategy.OnPush,
  template: `
    <p>{{ count() }} items, total {{ total() | currency }}</p>
    @for (l of lines(); track l.productId) { <app-cart-line [line]="l" /> }
    <button (click)="add(sample)">Add</button>`
})
export class CartComponent {
  lines = signal<CartLine[]>([]);                                     // writable
  count = computed(() => this.lines().reduce((n, l) => n + l.qty, 0)); // derived, cached, lazy
  total = computed(() => this.lines().reduce((s, l) => s + l.qty * l.price, 0));

  constructor() {
    effect(() => localStorage.setItem('cart', JSON.stringify(this.lines())));   // side effect
  }
  add(line: CartLine) { this.lines.update(ls => [...ls, line]); }              // immutable update
  clear() { this.lines.set([]); }
}
```

Rules and facts:
- `computed` is **lazy and memoised**: recalculated only when a dependency changes *and* someone reads it. It is read-only.
- `effect` runs at least once and whenever a signal it read changes. Use it for side effects (logging, `localStorage`, imperative third-party APIs), **not** for deriving state (use `computed`) or copying signal to signal (use `linkedSignal`, v19+). Effects need an injection context and are destroyed with their component.
- Signals compare with `Object.is` by default: mutating an array in place and calling `set` with the same reference does not notify. Use `update` with a new array.
- `untracked(() => x())` reads without creating a dependency.
- `linkedSignal` (v19+) is a writable signal that resets when a source changes (e.g. selected item resets when the list changes). `resource()`/`httpResource()` (experimental in v19/v20) load async data into signals - verify status before using.

### Signal inputs, outputs, model and queries

```typescript
@Component({
  selector: 'app-qty-picker',
  template: `
    <button (click)="dec()">-</button> {{ qty() }} <button (click)="inc()">+</button>
    @if (overLimit()) { <small>Max {{ max() }}</small> }`
})
export class QtyPickerComponent {
  productId = input.required<number>();               // required signal input
  max = input(10);                                    // optional, default 10
  label = input('', { transform: (v: string | undefined) => v?.trim() ?? '' });
  qty = model(1);                                     // two-way: [(qty)]="lineQty"
  limitReached = output<number>();                    // replaces @Output + EventEmitter

  overLimit = computed(() => this.qty() >= this.max());
  inc() {
    if (this.overLimit()) { this.limitReached.emit(this.productId()); return; }
    this.qty.update(q => q + 1);                      // writes back to the parent's signal
  }
  dec() { this.qty.update(q => Math.max(1, q - 1)); }
}
// parent: <app-qty-picker [productId]="p.id" [(qty)]="lineQty" (limitReached)="warn($event)" />
// queries: input = viewChild.required<ElementRef>('search');  items = contentChildren(TabComponent);
```

Signal inputs are read-only inside the component (no accidental mutation), work naturally with `computed`, and replace most `ngOnChanges` code. `input()`, `output()`, `model()`, `viewChild()` and friends are stable as of v19.

### Interop: toSignal and toObservable

```typescript
export class OrdersPageComponent {
  private orders = inject(OrderService);
  private route = inject(ActivatedRoute);

  // Observable -> Signal (subscribes immediately, unsubscribes on destroy)
  page = toSignal(this.route.queryParamMap.pipe(map(p => Number(p.get('page') ?? 1))),
                  { initialValue: 1 });

  // Signal -> Observable, then use RxJS for the async part (switchMap cancels stale calls)
  result = toSignal(
    toObservable(this.page).pipe(switchMap(p => this.orders.list(p))),
    { initialValue: { items: [], page: 1, pageSize: 20, total: 0 } as Page<Order> }
  );
}
```

| | Signals | RxJS Observables |
|---|---|---|
| Model | a **value** that changes (synchronous read) | a **stream of events** over time |
| Always has a current value | yes | no (except `BehaviorSubject`) |
| Subscription management | automatic | manual / `async` pipe / `takeUntilDestroyed` |
| Async orchestration (debounce, cancel, retry, combine) | weak | **excellent** |
| Change detection | fine-grained, enables zoneless | needs `async` pipe / `markForCheck` |
| Best for | component/UI state, derived values, inputs | HTTP pipelines, events, WebSockets, complex async flows |

:::tip The interview answer on signals vs RxJS
"They complement each other. Signals for synchronous state and what the template reads; RxJS for asynchronous event streams. I use RxJS where time matters - debounce, switchMap, retry - and convert the result to a signal with `toSignal` at the edge so templates stay simple and OnPush/zoneless-friendly."
:::

## Lifecycle Hooks

**Definition.** Angular calls lifecycle hook methods at defined moments of a component/directive's life. Implement the interface (`OnInit`, `OnDestroy`...) for type safety.

| Order | Hook | When | Typical use |
|---|---|---|---|
| 0 | `constructor` | class instantiated (DI) | `inject()` fields only; inputs **not** set yet |
| 1 | `ngOnChanges(changes)` | before `ngOnInit` and whenever an `@Input` reference changes | react to input changes (`changes['id'].previousValue`) |
| 2 | `ngOnInit` | once, after first `ngOnChanges` | initial data load, read inputs |
| 3 | `ngDoCheck` | every CD run | custom change detection (rare, expensive) |
| 4 | `ngAfterContentInit` | once, after projected `<ng-content>` is initialised | read `@ContentChild` |
| 5 | `ngAfterContentChecked` | after every check of projected content | rare |
| 6 | `ngAfterViewInit` | once, after the component's view and child views are ready | read `@ViewChild`, init a chart/third-party lib |
| 7 | `ngAfterViewChecked` | after every check of the view | rare; avoid state changes here |
| 8 | `ngOnDestroy` | just before removal | unsubscribe, clear timers, detach listeners |

```typescript
export class OrderChartComponent implements OnChanges, OnInit, AfterViewInit, OnDestroy {
  @Input({ required: true }) orderId!: number;
  @ViewChild('canvas') canvas!: ElementRef<HTMLCanvasElement>;
  private chart?: Chart;

  ngOnChanges(changes: SimpleChanges) {
    if (changes['orderId'] && !changes['orderId'].firstChange) this.reload();
  }
  ngOnInit()        { this.reload(); }                     // inputs are available here
  ngAfterViewInit() { this.chart = new Chart(this.canvas.nativeElement, {/*...*/}); }
  ngOnDestroy()     { this.chart?.destroy(); }
  private reload()  { /* fetch data */ }
}
```

**Render hooks (v16+).** `afterNextRender(() => ...)` runs once after the next render, `afterRender` (renamed `afterEveryRender` in later versions - verify) after every render. They run **only in the browser** (never during SSR), so they are the safe place for DOM measurement and browser-only libraries. `DestroyRef.onDestroy(cb)` is a hook-free alternative to `ngOnDestroy` usable from any injection context.

:::q constructor vs ngOnInit?
The constructor is for dependency injection and simple field setup; inputs are not bound yet and the view doesn't exist. `ngOnInit` runs once after Angular has set the initial inputs, so it is where initialisation that depends on inputs (and the first data load) belongs. With signal inputs you can often skip both and use `computed`/`effect`.
:::

## State Management

### Options in increasing order of ceremony

| Approach | Good for | Notes |
|---|---|---|
| Component state (fields/signals) | local UI | default |
| Service with `BehaviorSubject` or **signals** | feature/app state in small-medium apps | simple, no library; expose read-only |
| **NgRx SignalStore** (`@ngrx/signals`) | medium-large apps wanting structure without boilerplate | signal-based, functional, lightweight |
| **NgRx Store** (Redux pattern) + Effects | large apps, many teams, complex flows, need devtools/time travel | most boilerplate, most predictable |

```typescript
// Signal-based service store
@Injectable({ providedIn: 'root' })
export class CartService {
  private readonly _lines = signal<CartLine[]>([]);
  readonly lines = this._lines.asReadonly();                       // public read-only
  readonly total = computed(() => this._lines().reduce((s, l) => s + l.qty * l.price, 0));
  add(line: CartLine) { this._lines.update(ls => [...ls, line]); }
  remove(id: number)  { this._lines.update(ls => ls.filter(l => l.productId !== id)); }
}
```

### NgRx Store overview

```text
Component --dispatch(action)--> Store --> Reducer (pure) --> new State --> Selectors --> Component
                                   |
                                   +--> Effects (side effects: HTTP) --> dispatch success/failure action
```

```typescript
// orders.actions.ts
export const OrdersActions = createActionGroup({
  source: 'Orders Page',
  events: {
    'Load': props<{ page: number }>(),
    'Load Success': props<{ orders: Order[]; total: number }>(),
    'Load Failure': props<{ error: string }>()
  }
});   // -> OrdersActions.load, .loadSuccess, .loadFailure

// orders.reducer.ts
export interface OrdersState { orders: Order[]; total: number; loading: boolean; error: string | null }
const initialState: OrdersState = { orders: [], total: 0, loading: false, error: null };

export const ordersReducer = createReducer(initialState,
  on(OrdersActions.load, s => ({ ...s, loading: true, error: null })),
  on(OrdersActions.loadSuccess, (s, { orders, total }) => ({ ...s, orders, total, loading: false })),
  on(OrdersActions.loadFailure, (s, { error }) => ({ ...s, error, loading: false }))
);

// orders.selectors.ts
export const selectOrdersState = createFeatureSelector<OrdersState>('orders');
export const selectOrders = createSelector(selectOrdersState, s => s.orders);
export const selectPaidTotal = createSelector(selectOrders,
  orders => orders.filter(o => o.status === 'Paid').reduce((sum, o) => sum + o.total, 0));

// orders.effects.ts (functional effect)
export const loadOrders = createEffect(
  (actions$ = inject(Actions), api = inject(OrderService)) => actions$.pipe(
    ofType(OrdersActions.load),
    switchMap(({ page }) => api.list(page).pipe(
      map(p => OrdersActions.loadSuccess({ orders: p.items, total: p.total })),
      catchError((e: ApiProblem) => of(OrdersActions.loadFailure({ error: e.title })))
    ))
  ),
  { functional: true }
);

// app.config.ts:  provideStore({ orders: ordersReducer }), provideEffects({ loadOrders }),
//                 provideStoreDevtools({ maxAge: 25 })
// component:      orders = this.store.selectSignal(selectOrders);
//                 ngOnInit() { this.store.dispatch(OrdersActions.load({ page: 1 })); }
```

### NgRx SignalStore (mention)

```typescript
export const CartStore = signalStore(
  { providedIn: 'root' },
  withState({ lines: [] as CartLine[] }),
  withComputed(({ lines }) => ({
    total: computed(() => lines().reduce((s, l) => s + l.qty * l.price, 0))
  })),
  withMethods(store => ({
    add(line: CartLine) { patchState(store, s => ({ lines: [...s.lines, line] })); },
    clear() { patchState(store, { lines: [] }); }
  }))
);
// component: readonly cart = inject(CartStore);  template: {{ cart.total() | currency }}
```

:::q When would you introduce NgRx instead of services with BehaviorSubject or signals?
When many features share and mutate the same state, when you need an audit trail of every change (actions + devtools/time travel), strict separation of side effects (effects), or many developers need one enforced pattern. For most CRUD apps a signal or `BehaviorSubject` service per feature, or NgRx SignalStore, is enough and much less code. Server data can also stay in services with caching (`shareReplay`) instead of the store.
:::
