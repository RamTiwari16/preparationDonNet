## React Core Concepts

### Components and JSX

**Definition.** React is a declarative UI library: you describe *what the UI should look like for the current state* (`UI = f(state)`) and React updates the DOM. A **component** is a function that takes `props` and returns JSX (a description of UI). **JSX** is syntax sugar that a compiler (Babel, esbuild/SWC in Vite) turns into function calls.

**Why it matters.** Everything else (state, hooks, performance) builds on the model "render = call your function, compare the result with the previous result, patch the DOM". JSX questions are warm-ups in almost every React interview.

```javascript
// What you write
function ProductCard({ product }) {
  return <li className="card">{product.name} - {product.price}</li>;
}

// What the automatic JSX runtime (React 17+) compiles it to (roughly)
import { jsx as _jsx } from 'react/jsx-runtime';
function ProductCard({ product }) {
  return _jsx('li', { className: 'card', children: [product.name, ' - ', product.price] });
}
// Before React 17: React.createElement('li', { className: 'card' }, product.name, ...)
// Result is a plain object: { type: 'li', props: {...} } - an element in the virtual tree
```

JSX rules to remember:
- Return **one root** element, or a fragment `<>...</>` (no extra DOM node).
- `className`, `htmlFor`, `onClick` (camelCase events), `style={{ color: 'red' }}` (object), `tabIndex`.
- `{ }` holds any JavaScript *expression* (not statements: use ternary/`&&`/`map`, not `if`/`for`).
- Lowercase tag = DOM element; **Capitalised tag = component**. All tags must close (`<img />`).
- Values in `{}` are **escaped**, so React is XSS-safe by default. `dangerouslySetInnerHTML` bypasses that - sanitise first.

:::q What does JSX compile to? Is it required?
JSX is optional syntax sugar. It compiles to `jsx()` calls (React 17+ automatic runtime) or `React.createElement()` calls (older), which return plain element objects `{ type, props }`. You can write React without JSX, it is just unpleasant.
:::

### Props vs state and one-way data flow

| | Props | State |
|---|---|---|
| Owned by | the **parent** | the component itself |
| Mutable by the component? | **No** (read-only) | Yes, via the setter (never mutate directly) |
| Triggers re-render | when the parent passes new values | when the setter is called with a different value |
| Purpose | configuration / inputs | data that changes over time (form input, fetched data, toggle) |
| Direction | parent -> child | local, can be passed down as props |

**One-way data flow.** Data flows *down* via props; events flow *up* via callback props. A child never edits the parent's data directly; it calls a function the parent gave it. This keeps the data trail debuggable.

```javascript
function ProductCard({ product, onAdd }) {              // props: data down, callback up
  return (
    <li>
      {product.name} - ${product.price}
      <button onClick={() => onAdd(product.id)}>Add</button>
    </li>
  );
}

function Shop({ products }) {
  const [cartIds, setCartIds] = useState([]);           // state lives in the lowest common parent
  const add = id => setCartIds(ids => [...ids, id]);    // immutable update
  return (
    <>
      <ul>{products.map(p => <ProductCard key={p.id} product={p} onAdd={add} />)}</ul>
      <p>Cart: {cartIds.length} item(s)</p>
    </>
  );
}
```

**Lifting state up:** if two siblings need the same data, move the state to their closest common parent and pass it down. `children` is just another prop (`<Card><h2>Title</h2></Card>` gives `props.children`), the basis of composition.

### Function components and the "lifecycle"

**Definition.** Function components have no lifecycle *methods*. They render, and `useEffect` lets you run side effects *after* the DOM is committed. A component goes through **mount** (first render), **update** (re-render when props/state/context change) and **unmount** (removed).

| Class component | Function component |
|---|---|
| `componentDidMount` | `useEffect(() => { ... }, [])` |
| `componentDidUpdate` | `useEffect(() => { ... }, [dep1, dep2])` |
| `componentWillUnmount` | cleanup function returned from `useEffect` |
| `shouldComponentUpdate` / `PureComponent` | `React.memo` |
| `getDerivedStateFromProps` | compute during render (or `useMemo`) |
| `getSnapshotBeforeUpdate` | `useLayoutEffect` |
| Error boundary methods | still need a class (or `react-error-boundary`) |

```javascript
function Lifecycle({ orderId }) {
  console.log('render', orderId);                       // runs on every render
  useEffect(() => {
    console.log('effect: mount or orderId changed', orderId);
    return () => console.log('cleanup: before next effect or on unmount', orderId);
  }, [orderId]);
  return <p>Order {orderId}</p>;
}
// mount:   render 1 -> effect 1
// update:  render 2 -> cleanup 1 -> effect 2
// unmount: cleanup 2
```

**Strict Mode (development only).** `<React.StrictMode>` (default in Vite/Next templates) intentionally **double-invokes** component bodies, state initialisers and reducers, and on mount it runs **effect -> cleanup -> effect** once. The goal is to surface impure renders and missing cleanups. Nothing double-runs in production. If a double-fired effect "creates two subscriptions", your cleanup is missing, not React broken.

:::warn "My API is called twice"
In dev with Strict Mode, an effect that fetches on mount runs twice. That is expected. Make the effect idempotent and give it an `AbortController` cleanup (see useEffect). Do not remove StrictMode to hide it, and do not use a `ref` flag hack as the main solution; better still, use TanStack Query, which dedupes.
:::

### Virtual DOM, reconciliation and keys

**Definition.** On each update React calls your components to produce a new tree of elements (the *virtual DOM*), **diffs** it against the previous tree (*reconciliation*), and applies only the minimal changes to the real DOM (the *commit*). The diff is O(n) thanks to two heuristics: (1) elements of **different type** produce different trees (the subtree is unmounted and rebuilt); (2) in lists, **`key`** tells React which child is which across renders.

```text
render phase (pure, may be paused/restarted in concurrent mode)
   components run -> new element tree -> diff vs previous (Fiber)
commit phase (synchronous)
   DOM mutations -> refs attached -> useLayoutEffect -> (paint) -> useEffect
```

**Key rules.** Keys must be **unique among siblings** and **stable** (the database id, not `Math.random()`, not the array index when the list can be reordered, filtered, inserted into or deleted from). With index keys, state (like a typed-in input) sticks to the *position* and ends up on the wrong item.

```javascript
{todos.map(t => <TodoRow key={t.id} todo={t} />)}        // good: stable id
{todos.map((t, i) => <TodoRow key={i} todo={t} />)}      // bug-prone on reorder/insert/delete

// A key also resets state on purpose: new user => brand-new form, state discarded
<ProfileForm key={userId} userId={userId} />
```

:::q Why do lists need keys? Why not use the index?
Keys give each list item a stable identity so reconciliation can match old and new items, reuse the right DOM node and component state, and move rather than recreate them. With index keys, inserting at the top shifts every key, so React updates every row and local state (inputs, focus, animations) attaches to the wrong rows. Index is acceptable only for a static list that never reorders.
:::

### Controlled vs uncontrolled inputs, conditional rendering, lists

| | Controlled | Uncontrolled |
|---|---|---|
| Source of truth | React state (`value` + `onChange`) | the DOM itself (read via `ref` or `FormData`) |
| Validate/format on each keystroke | easy | harder |
| Re-renders per keystroke | yes | no |
| Good for | validation, dependent fields, masks | simple forms, file inputs, performance (React Hook Form) |

```javascript
function SearchBox({ onSearch }) {
  const [term, setTerm] = useState('');
  return (
    <form onSubmit={e => { e.preventDefault(); onSearch(term); }}>
      <input value={term} onChange={e => setTerm(e.target.value)} />   {/* controlled */}
      <button disabled={!term.trim()}>Search</button>
    </form>
  );
}

function Newsletter() {
  const emailRef = useRef(null);                                         // uncontrolled
  const submit = e => { e.preventDefault(); console.log(emailRef.current.value); };
  return <form onSubmit={submit}><input ref={emailRef} defaultValue="" /></form>;
}
```

```javascript
function OrderList({ orders, loading, error }) {
  if (loading) return <Spinner />;                       // early returns read best
  if (error) return <ErrorMessage error={error} />;
  if (orders.length === 0) return <p>No orders yet.</p>; // empty state is a real state

  return (
    <ul>
      {orders.map(o => (
        <li key={o.id}>
          #{o.id} {o.status === 'Paid' ? <Badge ok /> : <Badge />}
          {o.discount > 0 && <span>-{o.discount}%</span>}
        </li>
      ))}
    </ul>
  );
}
```

:::warn The `0 &&` trap
`{items.length && <List />}` renders the number `0` when the array is empty (0 is falsy but renderable). Use `items.length > 0 && ...` or a ternary. `null`, `undefined`, `false`, `true` render nothing.
:::

## Hooks

**Definition.** Hooks are functions (`use...`) that let function components keep state and run effects. React stores each component's hook values in an ordered list attached to its Fiber, which is why the **Rules of Hooks** exist.

**Rules of Hooks.**
1. Call hooks only at the **top level** of a component or custom hook: never inside conditions, loops, nested functions or after an early `return`.
2. Call hooks only from **function components or other custom hooks** (names start with `use`).

Why: React identifies a hook by its **call order** (1st `useState`, 2nd `useEffect`...). A conditional hook shifts the order and state lands on the wrong hook. The `eslint-plugin-react-hooks` rules `rules-of-hooks` and `exhaustive-deps` catch violations; keep them on as errors.

### useState

```javascript
const [count, setCount] = useState(0);                           // initial value (first render only)
const [user, setUser] = useState(() => loadFromStorage());        // lazy init: function runs once

setCount(5);                       // set value
setCount(c => c + 1);              // functional update: based on the latest queued state
```

Facts interviewers check:
- **State is a snapshot.** Inside one render `count` never changes, even after `setCount`. So `setCount(count + 1)` three times in a handler yields **+1**; `setCount(c => c + 1)` three times yields **+3**.
- **Batching.** React 18 batches all updates in the same tick (events, timeouts, promises, native handlers) into one re-render ("automatic batching"). React 17 batched only inside React events. Use `flushSync` to opt out (rare).
- **Replace, not merge.** Unlike class `setState`, the setter replaces the value: `setUser({ ...user, name })`.
- **Immutable updates only.** `user.name = 'x'; setUser(user)` does nothing (same reference, `Object.is` bail-out).
- Setting the same value skips the re-render (React may still render the component once more without committing).

```javascript
function Cart() {
  const [lines, setLines] = useState([{ id: 1, name: 'Pen', qty: 1 }]);

  const inc = id => setLines(ls => ls.map(l => (l.id === id ? { ...l, qty: l.qty + 1 } : l)));
  const remove = id => setLines(ls => ls.filter(l => l.id !== id));
  const total = lines.reduce((s, l) => s + l.qty, 0);        // derived: do NOT put it in state

  return (/* ... */);
}
```

:::tip Derived data is not state
If a value can be computed from props or other state (filtered list, total, `fullName`), compute it during render. Duplicated state drifts out of sync, which causes many "UI shows stale value" bugs.
:::

### useEffect

**Definition.** `useEffect(setup, deps)` runs `setup` **after** React has committed to the DOM and the browser can paint. It synchronises your component with something *outside* React: network, subscriptions, timers, `document.title`, third-party widgets. If `setup` returns a function, that **cleanup** runs before the next effect run and on unmount.

| Dependency array | Runs |
|---|---|
| omitted | after **every** render |
| `[]` | once after mount (twice in dev Strict Mode) |
| `[a, b]` | after mount and whenever `a` or `b` change (`Object.is`) |

Every reactive value used inside the effect (props, state, functions defined in the component) must be in the array. The `exhaustive-deps` lint rule enforces it; silencing it is the usual cause of stale-closure bugs.

#### Fetching with AbortController (complete)

```typescript
type Product = { id: number; name: string; price: number };

export function ProductList({ category }: { category: string }) {
  const [products, setProducts] = useState<Product[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    const controller = new AbortController();               // one per effect run
    setLoading(true);
    setError(null);

    fetch(`/api/products?category=${encodeURIComponent(category)}`, {
      signal: controller.signal
    })
      .then(res => {
        if (!res.ok) throw new Error(`HTTP ${res.status}`);  // fetch doesn't reject on 4xx/5xx
        return res.json() as Promise<Product[]>;
      })
      .then(setProducts)
      .catch(err => {
        if (err.name !== 'AbortError') setError(err.message); // ignore our own abort
      })
      .finally(() => { if (!controller.signal.aborted) setLoading(false); });

    return () => controller.abort();                         // category changed or unmounted
  }, [category]);

  if (loading) return <p>Loading...</p>;
  if (error) return <p role="alert">Failed: {error}</p>;
  return <ul>{products.map(p => <li key={p.id}>{p.name}</li>)}</ul>;
}
```

Why abort: if `category` changes quickly, response A may arrive *after* response B (a **race condition**) and overwrite newer data; abort (or an `ignore` flag) guarantees only the latest request writes state. It also prevents updates after unmount. In 2025+ code you often replace this whole component with TanStack Query (below).

#### Stale closures

```javascript
function Ticker() {
  const [n, setN] = useState(0);

  // BUG: callback captured n = 0 on mount and the effect never re-ran
  useEffect(() => {
    const id = setInterval(() => setN(n + 1), 1000);   // always sets 1
    return () => clearInterval(id);
  }, []);

  // FIX 1: functional update - no dependency on n
  useEffect(() => {
    const id = setInterval(() => setN(c => c + 1), 1000);
    return () => clearInterval(id);
  }, []);
  // FIX 2: list n in deps (interval recreated each tick) or read latest via a ref
}
```

Each render has its own props/state/functions; an effect or handler "sees" the values of the render that created it. That is a closure (see JavaScript section) and it is the single most asked React gotcha.

:::warn You might not need an effect
Do not use an effect to (a) transform data for rendering (compute it in render), (b) reset state when a prop changes (use a `key`), (c) respond to a click (use the event handler), or (d) chain state updates. Effects are only for syncing with external systems. Overused effects cause render loops: `useEffect(() => setX(f(y)), [x, y])`.
:::

:::q Walk me through the dependency array and cleanup.
React compares each dependency with the previous render using `Object.is`. If any differ, it first runs the previous effect's cleanup, then runs the new effect. `[]` means "no reactive deps": run on mount, cleanup on unmount. No array means every render. Cleanup is where you unsubscribe, clear timers, and abort requests; in Strict Mode dev React runs setup-cleanup-setup on mount to prove your cleanup works.
:::

:::q Why does my useEffect run twice in development?
Strict Mode deliberately mounts, unmounts and re-mounts every component once in development to catch effects that are not cleaned up properly. It does not happen in production. The correct response is to write idempotent effects with cleanup (abort the fetch, clear the interval, unsubscribe), not to delete StrictMode.
:::
