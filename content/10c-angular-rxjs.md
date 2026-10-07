## RxJS Deep Dive

### Observables: cold vs hot, Observable vs Promise

**Definition.** An **Observable** is a lazy stream of zero or more values over time. Nothing runs until `subscribe()`. The subscriber gets `next`, `error` (terminal) and `complete` (terminal) notifications and can **unsubscribe** to run the producer's teardown. RxJS is the library of operators that transform, combine and control these streams.

```typescript
const ticks$ = new Observable<number>(subscriber => {
  let n = 0;
  const id = setInterval(() => subscriber.next(n++), 1000);   // producer starts per subscription
  return () => clearInterval(id);                              // teardown on unsubscribe/complete
});
const sub = ticks$.pipe(take(3)).subscribe({
  next: v => console.log(v), error: e => console.error(e), complete: () => console.log('done')
});
// $ suffix convention: variables holding observables end with $
```

| | Promise | Observable |
|---|---|---|
| Values | exactly one | zero, one, or many over time |
| Execution | **eager** - starts immediately | **lazy** - starts on `subscribe` |
| Cancellation | no (native) | yes - `unsubscribe()` runs teardown (HTTP gets aborted) |
| Reuse | result cached, `then` can attach later | each subscription re-executes (cold) |
| Operators | `then/catch/finally`, `Promise.all` | 100+ operators (`map`, `switchMap`, `retry`, `debounceTime`) |
| Sync/async | always async | can be sync or async |
| Convert | `firstValueFrom(obs$)`, `lastValueFrom` | `from(promise)` |

**Cold vs hot.**
- **Cold**: the producer is created *per subscriber*, so each subscription gets its own execution from the start. `HttpClient.get()`, `of()`, `interval()`, `from(array)`. Two subscriptions = two HTTP calls.
- **Hot**: the producer exists *outside* and is shared; late subscribers miss earlier values. DOM events (`fromEvent`), `Subject`s, WebSocket streams, router events.
- Make cold hot with **`share()`** (multicast while subscribed) or **`shareReplay({ bufferSize: 1, refCount: true })`** (multicast + replay the last value to late subscribers - the common way to cache one HTTP result).

```typescript
// Cold: two subscriptions => two requests
const products$ = this.http.get<Product[]>('/api/products');
products$.subscribe(); products$.subscribe();

// Shared: one request, both get the result (and late subscribers get the cached one)
readonly categories$ = this.http.get<Category[]>('/api/categories').pipe(
  shareReplay({ bufferSize: 1, refCount: false })     // keep cached even with 0 subscribers
);
```

### Subjects

A **Subject** is both an Observable and an Observer: you can call `.next()` on it and many subscribers receive the value (multicast, hot).

| Type | Initial value | Late subscriber gets | Typical use |
|---|---|---|---|
| `Subject<T>` | no | only future values | event bus, "refresh" triggers, destroy notifier |
| `BehaviorSubject<T>(init)` | **required** | the **latest** value immediately; `.value` readable | current state: user, cart, selected filter |
| `ReplaySubject<T>(n)` | no | the last **n** values | caching recent events, late joiners (chat, logs) |
| `AsyncSubject<T>` | no | only the **last** value, and only after `complete()` | a single deferred result (rare) |

```typescript
@Injectable({ providedIn: 'root' })
export class CartStore {
  private readonly _lines$ = new BehaviorSubject<CartLine[]>([]);       // private writable
  readonly lines$ = this._lines$.asObservable();                         // public read-only
  readonly total$ = this.lines$.pipe(map(ls => ls.reduce((s, l) => s + l.qty * l.price, 0)));

  add(line: CartLine) {
    const cur = this._lines$.value;                                      // synchronous snapshot
    this._lines$.next([...cur.filter(l => l.productId !== line.productId), line]);  // immutable
  }
  clear() { this._lines$.next([]); }
}
```

Always expose `asObservable()` so consumers can't call `next()`. Prefer the `BehaviorSubject` service pattern for small apps; for bigger ones NgRx or signals (later section).

### Core operators

Use `pipe()` to chain. Operators are pure functions returning a new Observable.

```typescript
this.search.valueChanges.pipe(
  debounceTime(300),               // wait for a pause
  map(v => v.trim()),              // transform
  filter(v => v.length >= 2),      // drop
  distinctUntilChanged(),          // skip identical consecutive values
  tap(v => console.log('searching', v)),   // side effect only (logging), never changes the stream
  switchMap(v => this.api.search(v))
);
```

#### The flattening (higher-order mapping) operators

All four take a function that returns an *inner* Observable (usually an HTTP call) and flatten the results. They differ in what they do when a **new outer value arrives while the previous inner is still running**.

| Operator | Behaviour | Use for | Danger |
|---|---|---|---|
| **`switchMap`** | cancel the previous inner, switch to the new one | search-as-you-type, route-param-driven loads, "latest wins" | cancels in-flight **writes**: don't use for saves/POST |
| **`mergeMap`** (flatMap) | run all inners **in parallel** (optional `concurrent` limit) | independent fire-and-forget calls, bulk uploads with `mergeMap(f, 3)` | results can return out of order |
| **`concatMap`** | queue inners, run **one at a time, in order** | ordered saves, sequential API calls that must not overlap | slow if the queue grows |
| **`exhaustMap`** | **ignore** new outer values while one inner is active | login/submit/save button, anti double-click | drops events silently |

```text
outer:    --a-----b--c----------
inner(x): each takes 3 ticks
switchMap : cancels a when b arrives, cancels b when c arrives -> only c completes
mergeMap  : a, b, c all running at once, results interleave
concatMap : a finishes, then b starts, then c
exhaustMap: a runs; b and c ignored (arrive while busy)
```

```typescript
// 1. Search-as-you-type (complete)
@Component({ /* ... */ imports: [ReactiveFormsModule, AsyncPipe] })
export class ProductSearchComponent {
  private api = inject(ProductService);
  term = new FormControl('', { nonNullable: true });

  results$ = this.term.valueChanges.pipe(
    debounceTime(300),
    map(t => t.trim()),
    distinctUntilChanged(),
    switchMap(t => t.length < 2 ? of([] as Product[]) :
      this.api.search(t).pipe(catchError(() => of([] as Product[])))   // catchError INSIDE
    ),
    startWith([] as Product[])
  );
}

// 2. Submit once even if the user double-clicks
this.submit$.pipe(exhaustMap(() => this.orders.create(this.form.getRawValue())))
  .subscribe(o => this.router.navigate(['/orders', o.id]));

// 3. Save edits in order
this.edits$.pipe(concatMap(e => this.api.save(e))).subscribe();

// 4. Upload up to 3 files in parallel
from(files).pipe(mergeMap(f => this.api.upload(f), 3)).subscribe();
```

:::warn Put catchError inside the inner observable
If `catchError` is on the outer pipe, one failed request terminates the whole stream and the search box stops working. Catch inside `switchMap(... .pipe(catchError(() => of([]))))` so the outer stream survives. This is the number one RxJS bug in production Angular code.
:::

:::q switchMap vs mergeMap vs concatMap vs exhaustMap?
All map each value to an inner Observable and flatten. `switchMap` cancels the previous inner (latest wins: search, navigation). `mergeMap` runs them concurrently (independent work). `concatMap` queues them and preserves order (sequential saves). `exhaustMap` ignores new triggers until the current inner completes (submit buttons). I would not use `switchMap` for POSTs because the cancellation could abort a write the server may still process.
:::

#### Combining streams

| Operator | Emits | Completes when | Example |
|---|---|---|---|
| `forkJoin([a$, b$])` | **once**, array of the **last** value of each | all complete (HTTP calls do) | load order + customer in parallel |
| `combineLatest([a$, b$])` | every time **any** emits, latest of each (after all emitted once) | all complete | filter + page + sort -> query |
| `zip([a$, b$])` | pairs by index (1st with 1st, 2nd with 2nd) | any completes | rare: pairing two ordered streams |
| `withLatestFrom(b$)` | when the **source** emits, plus latest of `b$` | source completes | click + current form value |
| `merge(a$, b$)` | any value from any source | all complete | several triggers -> one handler |
| `concat(a$, b$)` | all of a$, then all of b$ | b$ completes | sequential |

```typescript
// forkJoin: parallel HTTP calls, one result (fails fast if any errors)
vm$ = this.route.paramMap.pipe(
  map(p => Number(p.get('id'))),
  switchMap(id => forkJoin({
    order: this.orders.get(id),
    lines: this.orders.lines(id),
    customer: this.orders.get(id).pipe(switchMap(o => this.customers.get(o.customerId)))
  }))
);

// combineLatest: reactive filters drive the query
orders$ = combineLatest([this.page$, this.status$, this.sort$]).pipe(
  debounceTime(0),                                       // coalesce simultaneous changes
  switchMap(([page, status, sort]) => this.orders.list(page, status, sort))
);

// withLatestFrom: take the latest form value only when Save is clicked
this.saveClick$.pipe(
  withLatestFrom(this.form.valueChanges),
  map(([, value]) => value),
  exhaustMap(value => this.api.save(value))
);
```

:::q forkJoin vs combineLatest vs zip?
`forkJoin` waits until every source completes and emits one array of last values: perfect for parallel HTTP calls. `combineLatest` never needs completion; it re-emits the latest tuple whenever any source emits (after each has emitted at least once): for reactive filters/derived state. `zip` pairs emissions by position. A `forkJoin` with a never-completing source (e.g. a `BehaviorSubject`) never emits.
:::

#### Error handling and retry

```typescript
this.http.get<Order[]>('/api/orders').pipe(
  retry({ count: 3, delay: (err, attempt) =>                  // exponential backoff; retry only transient errors
    err.status >= 500 || err.status === 0 ? timer(2 ** attempt * 250) : throwError(() => err) }),
  catchError((err: ApiProblem) => {
    if (err.status === 404) return of([] as Order[]);          // recover with a fallback value
    return throwError(() => err);                              // or rethrow for the caller
  }),
  finalize(() => this.loading.set(false))                      // runs on complete, error, or unsubscribe
);
```

`retry` re-subscribes to the source (so cold HTTP is re-sent); never auto-retry non-idempotent POSTs. `retryWhen` is deprecated in favour of `retry({ delay })`. After an error the stream is **terminated**; to keep a long-lived stream alive, catch errors on the inner observable.

### Unsubscribing and memory leaks

**Why it matters.** A subscription to a long-lived source (`interval`, `fromEvent`, a `Subject`, `router.events`, `valueChanges`, a store) keeps the callback - and the component it closes over - alive after the component is destroyed: memory leaks and phantom updates. HTTP observables complete by themselves and are safe.

```typescript
export class OrderTickerComponent {
  private destroyRef = inject(DestroyRef);
  private ws = inject(OrdersSocket);
  latest = signal<Order | null>(null);

  constructor() {
    // 1. Best (v16+): takeUntilDestroyed() in an injection context
    this.ws.orders$.pipe(takeUntilDestroyed()).subscribe(o => this.latest.set(o));
  }

  start() {
    // 2. Outside the constructor: pass the DestroyRef
    interval(5000).pipe(takeUntilDestroyed(this.destroyRef)).subscribe(() => this.refresh());
  }
}

// 3. Template: async pipe subscribes and unsubscribes for you
//    @if (orders$ | async; as orders) { ... }

// 4. Legacy: destroy$ + takeUntil (must be the LAST operator in the pipe)
private destroy$ = new Subject<void>();
ngOnInit() { this.stream$.pipe(takeUntil(this.destroy$)).subscribe(); }
ngOnDestroy() { this.destroy$.next(); this.destroy$.complete(); }

// 5. One-shot: take(1) / first() when you only need the first value
```

:::tip How to answer "how do you prevent memory leaks in Angular?"
"I prefer not to subscribe manually: use the `async` pipe or convert to signals with `toSignal`. When I must subscribe, I use `takeUntilDestroyed()`, or `takeUntil(destroy$)` as the last operator in older code. HTTP calls complete themselves; `Subject`s, `interval`, `fromEvent` and store selectors don't."
:::

:::q What is the difference between a cold and a hot observable, with an example?
Cold: the producer is created per subscription, so each subscriber gets its own run from the beginning - `http.get()` sends one request per subscribe. Hot: the producer is shared, subscribers just tap into what's already flowing - a `Subject` or `fromEvent(button, 'click')`. Use `shareReplay(1)` to make an HTTP observable behave like a cached hot one.
:::

:::q Subject vs BehaviorSubject vs ReplaySubject?
`Subject` has no memory: late subscribers only see future values. `BehaviorSubject` requires an initial value and hands the current one to every new subscriber, with a synchronous `.value`: ideal for state. `ReplaySubject(n)` replays the last n values to late subscribers: for caching events. All are hot and multicast.
:::
