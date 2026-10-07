## More Hooks

### useContext

**Definition.** Context passes a value to any descendant without threading props through every level ("prop drilling"). `createContext` makes it, a `Provider` supplies it, `useContext` reads the nearest provider's value.

**Why/when.** Low-frequency, app-wide data: current user/auth, theme, locale, feature flags. Not a general state store (see pitfalls).

```typescript
type AuthState = { user: { name: string; roles: string[] } | null; token: string | null };
type AuthApi = AuthState & { login(email: string, pw: string): Promise<void>; logout(): void };

const AuthContext = createContext<AuthApi | null>(null);

export function AuthProvider({ children }: { children: React.ReactNode }) {
  const [state, setState] = useState<AuthState>({ user: null, token: null });

  const login = useCallback(async (email: string, password: string) => {
    const res = await fetch('/api/auth/login', {
      method: 'POST', headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ email, password })
    });
    if (!res.ok) throw new Error('Invalid credentials');
    const { accessToken, user } = await res.json();      // ASP.NET Core issues the JWT
    setState({ user, token: accessToken });
  }, []);
  const logout = useCallback(() => setState({ user: null, token: null }), []);

  // Memoise the value: otherwise a NEW object every render re-renders ALL consumers
  const value = useMemo(() => ({ ...state, login, logout }), [state, login, logout]);
  return <AuthContext.Provider value={value}>{children}</AuthContext.Provider>;
}

export function useAuth() {                               // custom hook hides the context
  const ctx = useContext(AuthContext);
  if (!ctx) throw new Error('useAuth must be used inside <AuthProvider>');
  return ctx;
}
```

:::warn Context re-renders every consumer
When the provider's `value` changes (by reference), **every** component that calls `useContext` for it re-renders, and `React.memo` on the consumer doesn't help. Pitfalls: inline `value={{ a, b }}` objects, putting rapidly changing state (mouse position, form text) in context, one giant context for everything. Mitigations: memoise the value, split contexts (state vs dispatch, or by domain), colocate state, or use a store with selectors (Zustand/Redux/`useSyncExternalStore`).
:::

### useReducer

**Definition.** `useReducer(reducer, initial)` manages state with a pure function `(state, action) => newState`. Prefer it over `useState` when state has several related fields or many transitions. The `dispatch` function has a stable identity.

```typescript
type Line = { productId: number; name: string; qty: number; price: number };
type CartState = { lines: Line[]; coupon: string | null };
type CartAction =
  | { type: 'add'; line: Line }
  | { type: 'remove'; productId: number }
  | { type: 'setQty'; productId: number; qty: number }
  | { type: 'applyCoupon'; code: string }
  | { type: 'clear' };

function cartReducer(state: CartState, action: CartAction): CartState {
  switch (action.type) {
    case 'add': {
      const id = action.line.productId;
      const exists = state.lines.some(l => l.productId === id);
      const lines = exists
        ? state.lines.map(l => (l.productId === id ? { ...l, qty: l.qty + 1 } : l))
        : [...state.lines, action.line];
      return { ...state, lines };
    }
    case 'remove':
      return { ...state, lines: state.lines.filter(l => l.productId !== action.productId) };
    case 'setQty':
      return {
        ...state,
        lines: state.lines.map(l =>
          l.productId === action.productId ? { ...l, qty: action.qty } : l)
      };
    case 'applyCoupon': return { ...state, coupon: action.code };
    case 'clear':       return { lines: [], coupon: null };
  }
}

function CartPage() {
  const [cart, dispatch] = useReducer(cartReducer, { lines: [], coupon: null });
  const total = cart.lines.reduce((s, l) => s + l.qty * l.price, 0);
  return <button onClick={() => dispatch({ type: 'clear' })}>Clear ({total})</button>;
}
```

The reducer must be **pure** (no fetches, no mutation, no `Date.now()`): Strict Mode calls it twice. Put `useReducer` + two contexts (`CartStateContext`, `CartDispatchContext`) together for a lightweight store; this is the pattern Redux generalised.

### useMemo and useCallback

**Definition.** `useMemo(() => compute(), deps)` caches a **value** between renders; `useCallback(fn, deps)` caches a **function identity** (`useCallback(fn, d)` equals `useMemo(() => fn, d)`). Both re-compute only when a dependency changes. They are **performance hints, not semantic guarantees**: React may discard the cache.

```typescript
function ProductTable({ products, query }: { products: Product[]; query: string }) {
  // expensive derivation: 20k rows filtered + sorted
  const visible = useMemo(
    () => products.filter(p => p.name.toLowerCase().includes(query.toLowerCase()))
                  .sort((a, b) => a.price - b.price),
    [products, query]
  );

  // stable identity so the memoised child doesn't re-render needlessly
  const handleSelect = useCallback((id: number) => selectProduct(id), []);
  return <Rows rows={visible} onSelect={handleSelect} />;
}
const Rows = React.memo(function Rows({ rows, onSelect }: RowsProps) { /* ... */ });
```

| Use it when | Do NOT use it when |
|---|---|
| The calculation is measurably expensive (profile!) | The work is trivial (`a + b`, a small `map`) - memo bookkeeping costs more |
| The value/function is a dependency of another hook | Nothing downstream depends on its identity |
| It is a prop to a `React.memo` child | The child isn't memoised (the callback change changes nothing) |
| Object/array identity must stay stable for an effect | Used "just in case" everywhere (adds noise, hides real problems) |

React Compiler (a build-time tool; stable 1.0 announced late 2025, verify the current status for your version) auto-memoises components, so hand-written `useMemo`/`useCallback` become rarer in new code. You still need to understand them for existing code bases and for interviews.

### useRef

**Definition.** `useRef(initial)` returns a stable object `{ current }` that survives renders. **Changing `.current` does not trigger a re-render.** Two uses: (1) hold a **DOM node**, (2) hold a **mutable value** that isn't part of the rendered output (timer id, previous value, "is mounted" flag, latest callback).

```typescript
function SearchInput() {
  const inputRef = useRef<HTMLInputElement>(null);          // DOM ref
  useEffect(() => { inputRef.current?.focus(); }, []);      // focus on mount
  return <input ref={inputRef} placeholder="Search products" />;
}

function usePrevious<T>(value: T) {
  const ref = useRef<T | undefined>(undefined);             // mutable box
  useEffect(() => { ref.current = value; });                // runs after render
  return ref.current;                                       // value from the previous render
}

function Stopwatch() {
  const [seconds, setSeconds] = useState(0);
  const timerId = useRef<number | null>(null);
  const start = () => { timerId.current = window.setInterval(() => setSeconds(s => s + 1), 1000); };
  const stop = () => { if (timerId.current) clearInterval(timerId.current); };
  return <button onClick={start}>Start</button>;
}
```

| | `useState` | `useRef` |
|---|---|---|
| Re-renders on change | yes | **no** |
| Value between renders | preserved | preserved |
| Readable during render | yes | avoid (don't read/write `.current` in render) |

Pass a ref to a child's DOM node: React 19 allows `ref` as a normal prop on function components (`function Input({ ref, ...p }) { return <input ref={ref} {...p} /> }`); React 18 requires `forwardRef`. `useImperativeHandle` exposes a restricted API (e.g. `focus()`) instead of the raw node.

### useLayoutEffect (briefly)

Same signature as `useEffect`, but runs **synchronously after DOM mutations and before the browser paints**. Use it to measure layout (`getBoundingClientRect`) and adjust (tooltip position) without a visible flicker. It blocks painting, so default to `useEffect`. It warns during server rendering because it cannot run there.

## Custom Hooks

**Definition.** A custom hook is a function whose name starts with `use` that calls other hooks to package reusable *stateful logic* (not UI). Each call gets its own independent state. It is how you share logic across components without HOCs or render props.

### useFetch (complete)

```typescript
export class ApiError extends Error {
  constructor(public status: number, message: string,
              public errors?: Record<string, string[]>, public traceId?: string) {
    super(message);
  }
}

async function toApiError(res: Response): Promise<ApiError> {
  let p: any = null;
  try { p = await res.json(); } catch { /* body is not JSON */ }       // ProblemDetails
  return new ApiError(res.status, p?.title ?? `HTTP ${res.status}`, p?.errors, p?.traceId);
}

type FetchState<T> = { data: T | null; error: ApiError | Error | null; loading: boolean };

export function useFetch<T>(url: string | null) {
  const [state, setState] = useState<FetchState<T>>({ data: null, error: null, loading: !!url });
  const [reloadKey, setReloadKey] = useState(0);
  const refetch = useCallback(() => setReloadKey(k => k + 1), []);

  useEffect(() => {
    if (!url) return;                                                  // conditional fetching
    const controller = new AbortController();
    setState(s => ({ ...s, loading: true, error: null }));

    (async () => {
      try {
        const res = await fetch(url, { signal: controller.signal, credentials: 'include' });
        if (!res.ok) throw await toApiError(res);
        const data = (res.status === 204 ? null : await res.json()) as T | null;
        setState({ data, error: null, loading: false });
      } catch (e) {
        if ((e as Error).name === 'AbortError') return;                // superseded or unmounted
        setState({ data: null, error: e as Error, loading: false });
      }
    })();

    return () => controller.abort();
  }, [url, reloadKey]);

  return { ...state, refetch };
}

// usage
const { data: orders, loading, error, refetch } = useFetch<Order[]>('/api/orders?page=1');
```

### useDebounce and a search box

```typescript
export function useDebounce<T>(value: T, delay = 400): T {
  const [debounced, setDebounced] = useState(value);
  useEffect(() => {
    const id = setTimeout(() => setDebounced(value), delay);
    return () => clearTimeout(id);                                      // restart on each change
  }, [value, delay]);
  return debounced;
}

function ProductSearch() {
  const [term, setTerm] = useState('');
  const debounced = useDebounce(term.trim(), 400);
  const url = debounced.length >= 2 ? `/api/products?search=${encodeURIComponent(debounced)}` : null;
  const { data, loading, error } = useFetch<Product[]>(url);            // fires only after a pause

  return (
    <>
      <input value={term} onChange={e => setTerm(e.target.value)} placeholder="Search..." />
      {loading && <p>Searching...</p>}
      {error && <p role="alert">{error.message}</p>}
      <ul>{data?.map(p => <li key={p.id}>{p.name}</li>)}</ul>
    </>
  );
}
```

:::tip What to say about custom hooks
"A custom hook extracts reusable logic; every component that calls it gets its own state; it is not a singleton. Rules of Hooks still apply inside it. I'd use `useFetch` only in small apps; for real apps TanStack Query gives caching, dedupe, retries and invalidation." Show you know the limits of hand-rolled data fetching.
:::

:::q Custom hook vs a normal utility function?
A custom hook may call other hooks (state, effects, context), so it can hold state and subscribe to things, and it must follow the Rules of Hooks. A utility function is pure logic with no React awareness. Two components using the same custom hook do **not** share state; if you want shared state use context or a store.
:::

## React 19 at a Glance

React 19 went stable in December 2024 (18.x remains very common in interviews and existing code). Features worth naming, hedged where details evolve - verify in the official release notes.

| Feature | What it is |
|---|---|
| **Actions** | Async functions used in transitions / `<form action={fn}>`; React manages pending state, errors, optimistic updates and form reset |
| `useActionState` | `[state, formAction, isPending] = useActionState(action, initialState)` - state from the last action result |
| `useFormStatus` (react-dom) | child of a `<form>` reads `pending` without prop drilling |
| `useOptimistic` | show the expected result immediately; React reverts if the action fails |
| `use(resource)` | reads a Promise (suspends until resolved) or Context; unlike hooks it may be called conditionally |
| `ref` as a prop | function components receive `ref` directly; `forwardRef` becomes unnecessary |
| `<Context value>` | provider shorthand (no `.Provider`) |
| Document metadata | `<title>`, `<meta>`, `<link>` rendered inside components are hoisted to `<head>` |
| Server Components / Server Actions | framework-level (Next.js etc.); not used in a Vite SPA + ASP.NET Core API setup |
| React Compiler | separate build plugin that auto-memoises; opt-in |

```typescript
type FormState = { ok: boolean; error: string | null };

async function addToCart(_prev: FormState, formData: FormData): Promise<FormState> {
  const res = await fetch('/api/cart', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ productId: Number(formData.get('productId')), qty: 1 })
  });
  if (!res.ok) return { ok: false, error: (await res.json()).title ?? 'Could not add' };
  return { ok: true, error: null };
}

function AddToCart({ productId }: { productId: number }) {
  const [state, formAction, isPending] = useActionState(addToCart, { ok: false, error: null });
  return (
    <form action={formAction}>
      <input type="hidden" name="productId" value={productId} />
      <button disabled={isPending}>{isPending ? 'Adding...' : 'Add to cart'}</button>
      {state.error && <p role="alert">{state.error}</p>}
    </form>
  );
}

// useOptimistic: the like count updates instantly, rolls back if the request throws
function LikeButton({ likes, onLike }: { likes: number; onLike: () => Promise<void> }) {
  const [optimisticLikes, addOptimistic] = useOptimistic(likes, (cur, inc: number) => cur + inc);
  const [, startTransition] = useTransition();
  return (
    <button onClick={() => startTransition(async () => { addOptimistic(1); await onLike(); })}>
      {optimisticLikes} likes
    </button>
  );
}
```

:::q What changed in React 18 vs 19 that matters day to day?
18 introduced `createRoot`, automatic batching, concurrent features (`useTransition`, `useDeferredValue`, Suspense on the server) and Strict Mode effect double-run. 19 adds Actions with `useActionState`/`useOptimistic`/`useFormStatus`, the `use` API, `ref` as a prop, and simpler context/metadata handling; the React Compiler arrives as an opt-in build tool. Existing hooks code keeps working.
:::
