## React Performance

### Why components re-render and how to reduce it

**Definition.** A component re-renders when (1) its own state changes, (2) its **parent re-renders** (children re-render by default even if their props are identical), or (3) a context it consumes changes. "Render" means *calling your function and diffing the output*; it is usually cheap. The DOM is touched only when the diff finds a change.

**Why it matters.** Slow UIs are typically caused by a few expensive subtrees re-rendering on every keystroke, or by long lists. Fix by measuring (Profiler), then applying the cheapest remedy first.

Order of remedies (cheapest first):
1. **Move state down / colocate.** Keep fast-changing state (input text) in a small child so the big parent doesn't re-render.
2. **Lift content up** with `children`: a component that receives `children` as a prop doesn't re-render them when its own state changes.
3. `React.memo` the expensive child + stable props.
4. `useMemo` for an expensive calculation; `useCallback` for handlers passed to memoised children.
5. Defer work: `useTransition` / `useDeferredValue`, debounce input.
6. Virtualise long lists; split code.

```typescript
// 1. Colocate: only <Clock/> re-renders every second, not the whole page
function Page() { return <><Clock /><HeavyReport /></>; }

// 3. React.memo: skip re-render if props are shallow-equal
const OrderRow = React.memo(function OrderRow({ order, onSelect }: RowProps) {
  console.log('render row', order.id);
  return <tr onClick={() => onSelect(order.id)}><td>{order.id}</td></tr>;
});

function OrderTable({ orders }: { orders: Order[] }) {
  const [selected, setSelected] = useState<number | null>(null);
  const onSelect = useCallback((id: number) => setSelected(id), []);   // stable identity
  return <table><tbody>{orders.map(o => <OrderRow key={o.id} order={o} onSelect={onSelect} />)}</tbody></table>;
}
// Without useCallback, a new onSelect each render defeats React.memo. Inline objects
// (style={{...}}, options={[...]}) break it the same way.

// 5. Keep typing responsive while a heavy list filters
function Search({ items }: { items: Product[] }) {
  const [q, setQ] = useState('');
  const deferred = useDeferredValue(q);               // lags behind during heavy renders
  const visible = useMemo(() => items.filter(i => i.name.includes(deferred)), [items, deferred]);
  return <><input value={q} onChange={e => setQ(e.target.value)} /><List rows={visible} /></>;
}
```

:::warn Memoisation is not free
`React.memo` + `useMemo` + `useCallback` everywhere adds comparisons, closures and mental load, and can hide the real problem (too much state in one place). Add them where the Profiler shows wasted renders of an expensive subtree. Object/array/function props created inline silently break `memo`. React Compiler (opt-in, verify the status in your React version) automates most of this.
:::

### Lazy loading and code splitting

**Definition.** *Code splitting* breaks the bundle into chunks loaded on demand. `React.lazy(() => import('./Admin'))` plus `<Suspense fallback>` loads a component's chunk only when first rendered. Split **by route** first (biggest win), then by heavy widgets (charts, editors, maps).

```typescript
import { lazy, Suspense } from 'react';
import { createBrowserRouter, RouterProvider } from 'react-router-dom';

const AdminDashboard = lazy(() => import('./pages/AdminDashboard'));  // default export required
const Reports = lazy(() => import('./pages/Reports'));

const router = createBrowserRouter([
  { path: '/', element: <Home /> },
  { path: '/admin', element: <Suspense fallback={<Spinner />}><AdminDashboard /></Suspense> },
  { path: '/reports', element: <Suspense fallback={<Spinner />}><Reports /></Suspense> }
]);
// Vite/webpack emit separate JS files; the browser fetches them on first navigation.
// Prefetch on hover: onMouseEnter={() => import('./pages/Reports')}
```

### Virtualising long lists

Rendering 10,000 rows creates 10,000 DOM subtrees. **Windowing** renders only the visible rows (+ overscan) and positions them with transforms. Libraries: TanStack Virtual, react-window / react-virtualized. Pair with server-side paging (`page`, `pageSize`, `X-Pagination`) for really large data.

```typescript
import { useVirtualizer } from '@tanstack/react-virtual';

function BigList({ rows }: { rows: Product[] }) {
  const parentRef = useRef<HTMLDivElement>(null);
  const virt = useVirtualizer({
    count: rows.length, getScrollElement: () => parentRef.current,
    estimateSize: () => 48, overscan: 8
  });
  return (
    <div ref={parentRef} style={{ height: 500, overflow: 'auto' }}>
      <div style={{ height: virt.getTotalSize(), position: 'relative' }}>
        {virt.getVirtualItems().map(v => (
          <div key={v.key} style={{ position: 'absolute', top: 0, width: '100%',
                height: v.size, transform: `translateY(${v.start}px)` }}>
            {rows[v.index].name}
          </div>
        ))}
      </div>
    </div>
  );
}
```

### Measuring: Profiler, bundle analysis, debouncing

- **React DevTools Profiler**: record an interaction, see which components rendered and why ("props changed", "hooks changed", "parent rendered") and how long each took. The `<Profiler id onRender>` component gives programmatic timings.
- **Bundle analysis**: `rollup-plugin-visualizer` (Vite) or `webpack-bundle-analyzer`/`source-map-explorer` shows what is in each chunk; fix by lazy loading, importing specific functions (`lodash-es`, not whole lodash), dropping moment.js, tree-shaking, and compressing (Brotli at the reverse proxy / ASP.NET Core response compression).
- **Web Vitals / Lighthouse** for LCP, INP, CLS; check the Network tab for waterfall requests.
- **Debounce user input** (search, autosave) and cancel stale requests (see `useDebounce`, `AbortController`).
- Stable `key`s, avoid unnecessary effects, avoid giant context values, images lazy (`loading="lazy"`), cache server state with TanStack Query.

:::scenario A table with 5,000 rows lags on every keystroke in the filter box
Diagnose with the Profiler: every keystroke re-renders all rows. Fixes in order: (1) keep the input state in a child so only the input re-renders and pass the *debounced* value to the table; (2) `React.memo` the row with a stable `onSelect`; (3) `useMemo` the filtered array; (4) `useDeferredValue` for the input; (5) virtualise the rows; (6) move filtering/paging to the server (`GET /api/products?search=&page=`) with an index on the column. Always measure after each step.
:::

## Routing, Forms and Testing

### React Router v6: routes and protected routes

**Definition.** React Router maps URLs to components in the browser without a full page reload. v6 (v6.4+ "data router") uses `createBrowserRouter` + `RouterProvider`, nested routes rendering children through `<Outlet />`, dynamic params (`:id`), and optional `loader`/`action` functions. React Router v7 continues this API (package is `react-router`; verify import paths for your version).

```typescript
const router = createBrowserRouter([
  { path: '/login', element: <Login /> },
  {
    element: <RequireAuth />,                              // layout route: guard for children
    children: [
      { path: '/', element: <AppLayout />, children: [     // layout renders <Outlet />
          { index: true, element: <Dashboard /> },
          { path: 'orders', element: <Orders /> },
          { path: 'orders/:id', element: <OrderDetails /> },
          { element: <RequireAuth roles={['Admin']} />,
            children: [{ path: 'admin', element: <Admin /> }] }
      ] }
    ]
  },
  { path: '*', element: <NotFound /> }
]);

function RequireAuth({ roles }: { roles?: string[] }) {
  const { user } = useAuth();
  const location = useLocation();
  if (!user) return <Navigate to="/login" state={{ from: location }} replace />;
  if (roles && !roles.some(r => user.roles.includes(r))) return <Navigate to="/403" replace />;
  return <Outlet />;
}

function OrderDetails() {
  const { id } = useParams();                              // string | undefined
  const [search, setSearch] = useSearchParams();           // ?tab=lines
  const navigate = useNavigate();                          // navigate('/orders'), navigate(-1)
  /* ... */
}
// After login: navigate(location.state?.from?.pathname ?? '/', { replace: true })
```

:::warn Client-side guards are only UX
Anyone can open dev tools and bypass `RequireAuth`. The real protection is `[Authorize]` / policies on the ASP.NET Core API, which must return 401/403 regardless of what the SPA does. Treat the route guard as navigation convenience.
:::

### Forms: React Hook Form (brief)

React Hook Form (RHF) uses **uncontrolled inputs** + refs, so typing doesn't re-render the whole form; pair it with `zod` for schema validation. Map server-side `ValidationProblemDetails` onto fields with `setError`.

```typescript
import { useForm } from 'react-hook-form';
import { zodResolver } from '@hookform/resolvers/zod';
import { z } from 'zod';

const schema = z.object({
  email: z.string().email('Enter a valid email'),
  quantity: z.coerce.number().int().min(1, 'At least 1')
});
type FormValues = z.infer<typeof schema>;

function OrderForm() {
  const { register, handleSubmit, setError, formState: { errors, isSubmitting } } =
    useForm<FormValues>({ resolver: zodResolver(schema), defaultValues: { quantity: 1 } });

  const onSubmit = handleSubmit(async values => {
    try {
      await api.post('/orders', values);
    } catch (e) {
      const p = toProblem(e);                              // ASP.NET Core ProblemDetails
      Object.entries(p.errors ?? {}).forEach(([field, msgs]) => {
        const name = (field.charAt(0).toLowerCase() + field.slice(1)) as keyof FormValues;
        setError(name, { message: msgs[0] });              // "Email" -> "email"
      });
      if (!p.errors) setError('root', { message: p.title });
    }
  });

  return (
    <form onSubmit={onSubmit} noValidate>
      <input {...register('email')} placeholder="Email" />
      {errors.email && <span role="alert">{errors.email.message}</span>}
      <input type="number" {...register('quantity')} />
      {errors.quantity && <span role="alert">{errors.quantity.message}</span>}
      <button disabled={isSubmitting}>Place order</button>
    </form>
  );
}
```

React 19 `<form action>` + `useActionState` covers simple cases without a library. Always validate on the server too: client validation is a convenience.

### Testing: React Testing Library + Vitest/Jest (brief)

**Philosophy.** Test what the **user** sees and does, not implementation details: render, query by role/text/label, interact with `userEvent`, assert on the DOM. Mock the network at the HTTP boundary (MSW) rather than mocking `fetch`/Axios functions. Vite projects use **Vitest** (Jest-compatible API, `environment: 'jsdom'`); Create React App/older projects use Jest. (Create React App is deprecated; start new projects with Vite or a framework.)

```typescript
import { render, screen } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { http, HttpResponse } from 'msw';
import { setupServer } from 'msw/node';
import { describe, test, expect, vi, beforeAll, afterEach, afterAll } from 'vitest';

const server = setupServer(
  http.get('*/api/products', () => HttpResponse.json([{ id: 1, name: 'Pen', price: 2 }]))
);
beforeAll(() => server.listen());
afterEach(() => server.resetHandlers());
afterAll(() => server.close());

describe('ProductList', () => {
  test('shows loading then products', async () => {
    render(<ProductList category="all" />);
    expect(screen.getByText(/loading/i)).toBeInTheDocument();
    expect(await screen.findByText('Pen')).toBeInTheDocument();    // findBy* waits
  });

  test('shows an error when the API fails', async () => {
    server.use(http.get('*/api/products', () => new HttpResponse(null, { status: 500 })));
    render(<ProductList category="all" />);
    expect(await screen.findByRole('alert')).toHaveTextContent(/failed/i);
  });
});

test('adds to cart on click', async () => {
  const user = userEvent.setup();
  const onAdd = vi.fn();
  render(<ProductCard product={{ id: 1, name: 'Pen', price: 2 }} onAdd={onAdd} />);
  await user.click(screen.getByRole('button', { name: /add/i }));
  expect(onAdd).toHaveBeenCalledWith(1);
});
```

Query priority: `getByRole` > `getByLabelText` > `getByText` > `getByTestId` (last resort). `getBy` throws if missing, `queryBy` returns null (assert absence), `findBy` is async. Test custom hooks with `renderHook`. For full flows use Playwright/Cypress E2E.

## Quick-fire Q&A

:::q What is the virtual DOM and why does React use it?
It is an in-memory tree of lightweight element objects describing the UI. On each update React builds a new tree, diffs it against the previous one and applies only the minimal real-DOM changes in one commit. The benefit is a declarative programming model with good-enough performance, not that the virtual DOM is faster than hand-tuned DOM code.
:::

:::q What is the difference between props and state?
Props are inputs passed by the parent and are read-only for the receiving component. State is data owned by the component that can change over time and trigger a re-render through its setter. Data flows down through props; events flow up through callbacks.
:::

:::q Why must hooks be called unconditionally and at the top level?
React tracks hooks by call order per component. A hook inside an `if` or loop changes that order between renders, so values map to the wrong hooks. Always call hooks at the top level of a component or custom hook, and keep the `rules-of-hooks` ESLint rule on.
:::

:::q useEffect vs useLayoutEffect?
`useEffect` runs after the browser paints, so it doesn't block rendering: use it for data fetching, subscriptions, logging. `useLayoutEffect` runs synchronously after DOM mutation but before paint: use it only to measure layout and adjust before the user sees a flicker.
:::

:::q useMemo vs useCallback vs React.memo?
`React.memo` wraps a component and skips re-rendering if props are shallow-equal. `useMemo` caches a computed value; `useCallback` caches a function reference, mainly to keep props stable for memoised children or effect dependencies. They are optimisations to apply after measuring, not defaults.
:::

:::q Controlled vs uncontrolled components?
Controlled: the input's value lives in React state (`value` + `onChange`), so React is the single source of truth and can validate or transform on every change. Uncontrolled: the DOM keeps the value and you read it with a ref or `FormData` on submit. React Hook Form uses uncontrolled inputs for performance.
:::

:::q How do you avoid unnecessary re-renders?
First measure with the Profiler. Then colocate state, split components so fast-changing state is isolated, use `React.memo` with stable props (`useCallback`/`useMemo`), split context, use selectors in Redux/Zustand, virtualise long lists, and defer heavy work with `useDeferredValue`/`useTransition`.
:::

:::q What is a stale closure and how do you fix it?
A handler or effect that captured props/state from an old render and keeps using those values. Typical case: `setInterval(() => setN(n + 1), 1000)` in an effect with `[]`. Fix with a functional update (`setN(c => c + 1)`), correct dependency arrays, or a ref to hold the latest value.
:::

:::q Where should API calls live in a React app?
Not scattered inside components. Put transport in a single Axios/fetch client with interceptors, server-state in TanStack Query or RTK Query (caching, dedupe, retries, invalidation), and expose feature hooks like `useOrders()`. Components only render loading, error, empty and data states.
:::

:::q How do you handle JWT and token refresh in React?
Keep the access token in memory and the refresh token in an HttpOnly cookie. An Axios request interceptor adds the Bearer header. A response interceptor, on 401, calls the refresh endpoint once, queues concurrent failed requests, retries them with the new token, and redirects to login if refresh fails. Route guards are UX only; the ASP.NET Core API enforces authorization.
:::

:::q What do error boundaries not catch?
Errors in event handlers, asynchronous code (timers, promises), server-side rendering, and errors thrown in the boundary component itself. They only catch errors during rendering, lifecycle and constructors of their children. Handle the others with `try/catch` or the data library's error state.
:::

:::q Context API vs Redux - which and when?
Context for low-frequency global values like theme and current user; it re-renders every consumer on change. Redux Toolkit for complex, frequently updated client state shared by many components that benefits from selectors, middleware and devtools. For server data use TanStack Query/RTK Query regardless.
:::

:::q What is code splitting and how do you do it in React?
Splitting the bundle into chunks that load on demand to reduce initial load time. Use `React.lazy(() => import('./Page'))` with `<Suspense fallback>`, ideally per route, and dynamic `import()` for heavy libraries. Bundlers (Vite/webpack) emit the chunks automatically.
:::

:::q What are concurrent features in React 18 (useTransition, useDeferredValue)?
They let React keep the UI responsive by marking some updates as non-urgent. `startTransition`/`useTransition` marks a state update as a transition that can be interrupted by urgent input; `useDeferredValue` gives you a lagging copy of a value for expensive rendering. Typing stays smooth while a big list updates a moment later.
:::

:::q useRef vs useState?
Both persist across renders. Changing state schedules a re-render; changing `ref.current` does not. Use state for anything displayed, refs for DOM nodes and values that don't affect rendering (timer ids, previous values, instance variables).
:::
