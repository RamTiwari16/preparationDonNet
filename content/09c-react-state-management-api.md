## State Management

### Local vs global vs server state

**The most useful mental model:** not all state is equal. Pick the tool by *kind* of state.

| Kind | Examples | Best tool |
|---|---|---|
| **Local UI state** | input text, open/closed, selected tab | `useState` / `useReducer` in the component |
| **Shared UI state** (few components) | wizard step, filters of a page | lift state up, or a small context |
| **Global client state** | auth session, cart, theme, feature flags | Context (rarely changing) or Redux Toolkit / Zustand (frequently changing) |
| **Server state** (cache of remote data) | products, orders, user profile | **TanStack Query** or **RTK Query** - caching, dedupe, refetch, invalidation |
| **URL state** | page, sort, search term | the router (`useSearchParams`): shareable and back-button friendly |
| **Form state** | values, errors, touched | React Hook Form / Formik |

Rule: keep state **as local as possible**, lift it only when needed, and do not copy server data into Redux by hand if a data-fetching library can own it. Most "we need Redux" problems turn out to be server-state problems.

:::q Context API vs Redux - when would you choose which?
Context is a *transport* for values, not a state manager: great for low-churn values (theme, current user). Every consumer re-renders when the value changes and there are no selectors, no middleware, no devtools. Redux Toolkit gives a single predictable store, selectors that limit re-renders, middleware for async work, time-travel debugging and a strict pattern for large teams. For server data use TanStack Query/RTK Query; for small global client state Zustand is often enough.
:::

### Redux and Redux Toolkit

**Definition.** Redux is a predictable state container: one **store** holds the state tree; the UI **dispatches actions** (`{ type, payload }`); pure **reducers** compute the next state; **selectors** read it. **Redux Toolkit (RTK)** is the official, opinionated way to write Redux: `configureStore` (sets up devtools and thunk middleware), `createSlice` (reducers + actions together, **Immer** lets you write "mutating" code that is turned into immutable updates), `createAsyncThunk`, and RTK Query.

```text
UI --dispatch(action)--> store --> reducer(state, action) --> new state --> subscribed UI
                           |
                  middleware (thunk, listener, logging) for async/side effects
```

#### Complete example: cart + product loading

```typescript
// api.ts (Axios instance is defined in the API section below)
export type ApiProblem = { status: number; title: string; errors?: Record<string, string[]> };
export type Product = { id: number; name: string; price: number };

// productsSlice.ts
import { createAsyncThunk, createSlice } from '@reduxjs/toolkit';
import { api, toProblem } from './api';

export const fetchProducts = createAsyncThunk<
  Product[], { category?: string } | void, { rejectValue: ApiProblem }
>('products/fetch', async (args, { rejectWithValue, signal }) => {
  try {
    const { data } = await api.get<Product[]>('/products', { params: args ?? {}, signal });
    return data;
  } catch (e) {
    return rejectWithValue(toProblem(e));                // typed error payload (ProblemDetails)
  }
});

type ProductsState = { items: Product[]; status: 'idle' | 'loading' | 'failed'; error?: ApiProblem };
const initialState: ProductsState = { items: [], status: 'idle' };

const productsSlice = createSlice({
  name: 'products',
  initialState,
  reducers: {},
  extraReducers: builder => builder
    .addCase(fetchProducts.pending, s => { s.status = 'loading'; s.error = undefined; })
    .addCase(fetchProducts.fulfilled, (s, a) => { s.status = 'idle'; s.items = a.payload; })
    .addCase(fetchProducts.rejected, (s, a) => { s.status = 'failed'; s.error = a.payload; })
});
export default productsSlice.reducer;
```

```typescript
// cartSlice.ts
import { createSlice, PayloadAction, createSelector } from '@reduxjs/toolkit';
import type { RootState } from './store';

type Line = { productId: number; name: string; price: number; qty: number };
const cartSlice = createSlice({
  name: 'cart',
  initialState: { lines: [] as Line[] },
  reducers: {
    added(state, action: PayloadAction<Omit<Line, 'qty'>>) {
      const line = state.lines.find(l => l.productId === action.payload.productId);
      if (line) line.qty += 1;                           // "mutation" is safe: Immer
      else state.lines.push({ ...action.payload, qty: 1 });
    },
    removed(state, action: PayloadAction<number>) {
      state.lines = state.lines.filter(l => l.productId !== action.payload);
    },
    cleared: state => { state.lines = []; }
  }
});
export const { added, removed, cleared } = cartSlice.actions;
export default cartSlice.reducer;

export const selectTotal = createSelector(               // memoised derived data
  (s: RootState) => s.cart.lines,
  lines => lines.reduce((sum, l) => sum + l.price * l.qty, 0)
);
```

```typescript
// store.ts
import { configureStore } from '@reduxjs/toolkit';
import { useDispatch, useSelector } from 'react-redux';
import cart from './cartSlice';
import products from './productsSlice';
import { shopApi } from './shopApi';

export const store = configureStore({
  reducer: { cart, products, [shopApi.reducerPath]: shopApi.reducer },
  middleware: getDefault => getDefault().concat(shopApi.middleware)
});
export type RootState = ReturnType<typeof store.getState>;
export type AppDispatch = typeof store.dispatch;
export const useAppDispatch = useDispatch.withTypes<AppDispatch>();
export const useAppSelector = useSelector.withTypes<RootState>();

// main.tsx:  <Provider store={store}><App /></Provider>
```

```typescript
// ProductsPage.tsx
function ProductsPage() {
  const dispatch = useAppDispatch();
  const { items, status, error } = useAppSelector(s => s.products);
  const total = useAppSelector(selectTotal);

  useEffect(() => {
    const promise = dispatch(fetchProducts());
    return () => promise.abort();                        // thunk receives the AbortSignal
  }, [dispatch]);

  if (status === 'loading') return <Spinner />;
  if (status === 'failed') return <p role="alert">{error?.title}</p>;
  return (
    <>
      <p>Cart total: {total}</p>
      {items.map(p => (
        <button key={p.id} onClick={() => dispatch(added({ productId: p.id, name: p.name, price: p.price }))}>
          Add {p.name}
        </button>
      ))}
    </>
  );
}
```

**Rules.** Reducers are pure (no async, no `Date.now`, no random); state is serialisable (no class instances, Dates, functions - RTK warns in dev); one store per app; do the async in thunks/RTK Query/listeners.

#### RTK Query

RTK Query is Redux's built-in server-state layer: you declare endpoints and it generates hooks with caching, deduplication, loading flags, refetching and tag-based invalidation.

```typescript
// shopApi.ts
import { createApi, fetchBaseQuery } from '@reduxjs/toolkit/query/react';

export const shopApi = createApi({
  reducerPath: 'shopApi',
  baseQuery: fetchBaseQuery({
    baseUrl: '/api',
    prepareHeaders: (headers, { getState }) => {
      const token = (getState() as RootState).auth.token;      // JWT from an auth slice
      if (token) headers.set('Authorization', `Bearer ${token}`);
      return headers;
    }
  }),
  tagTypes: ['Order'],
  endpoints: build => ({
    getOrders: build.query<Order[], { page: number }>({
      query: ({ page }) => `/orders?page=${page}&pageSize=20`,
      providesTags: result =>
        result ? [...result.map(o => ({ type: 'Order' as const, id: o.id })), 'Order'] : ['Order']
    }),
    addOrder: build.mutation<Order, NewOrder>({
      query: body => ({ url: '/orders', method: 'POST', body }),
      invalidatesTags: ['Order']                               // refetches getOrders automatically
    })
  })
});
export const { useGetOrdersQuery, useAddOrderMutation } = shopApi;

// component
const { data = [], isLoading, isError, error, refetch } = useGetOrdersQuery({ page });
const [addOrder, { isLoading: saving }] = useAddOrderMutation();
```

### TanStack Query and Zustand

**TanStack Query (React Query v5)** is the most popular server-state library, independent of Redux. It treats fetched data as a **cache keyed by `queryKey`**, with `staleTime`, background refetch on focus/reconnect, retries, request dedupe, pagination helpers and optimistic updates.

```typescript
function Orders({ page }: { page: number }) {
  const qc = useQueryClient();
  const { data, isPending, isError, error, isFetching } = useQuery({
    queryKey: ['orders', page],                                   // part of the cache key
    queryFn: ({ signal }) => api.get<Order[]>('/orders', { params: { page }, signal }).then(r => r.data),
    placeholderData: keepPreviousData,                            // smooth pagination (v5)
    staleTime: 30_000
  });

  const create = useMutation({
    mutationFn: (dto: NewOrder) => api.post<Order>('/orders', dto).then(r => r.data),
    onSuccess: () => qc.invalidateQueries({ queryKey: ['orders'] })   // refetch lists
  });

  if (isPending) return <Spinner />;
  if (isError) return <ErrorBox problem={toProblem(error)} />;
  return <OrderTable rows={data} busy={isFetching} onCreate={create.mutate} />;
}
```

**Zustand** is a tiny hook-based store with no providers/boilerplate and selector-based subscriptions - a popular lightweight alternative to Redux for client state:

```typescript
import { create } from 'zustand';
type CartStore = { lines: Line[]; add(l: Line): void; clear(): void };
export const useCartStore = create<CartStore>()(set => ({
  lines: [],
  add: l => set(s => ({ lines: [...s.lines, l] })),
  clear: () => set({ lines: [] })
}));
const count = useCartStore(s => s.lines.length);   // re-renders only when the count changes
```

| | Context | Redux Toolkit | Zustand | TanStack / RTK Query |
|---|---|---|---|---|
| Purpose | pass values | structured global store | light global store | server-state cache |
| Boilerplate | low | medium | very low | low |
| Selectors (avoid re-render) | no | yes | yes | yes (`select`) |
| Devtools / middleware | no | excellent | basic | devtools |
| Async handling | manual | thunks, listeners | manual / middleware | built in |

## API Integration

### fetch vs Axios

| | `fetch` | Axios |
|---|---|---|
| Availability | built in (browser, Node 18+) | extra dependency (~13 KB gz) |
| Rejects on 4xx/5xx | **no**, check `res.ok` | **yes** (non-2xx throws `AxiosError`) |
| JSON | manual `res.json()`, `JSON.stringify` | automatic both ways |
| Interceptors | none (write a wrapper) | request/response interceptors |
| Timeout | `AbortSignal.timeout()` | `timeout` option |
| Cancel | `AbortController` | `AbortController` (CancelToken deprecated) |
| Upload progress | no (streams only) | yes (`onUploadProgress`) |
| Defaults/instances | no | `axios.create({ baseURL, headers })` |
| XSRF helper | no | built in |

:::tip What interviewers want
Not "Axios is better". They want: *fetch doesn't reject on HTTP errors*, *interceptors centralise cross-cutting concerns (JWT, refresh, logging, error mapping)*, and *both support AbortController*. In a modern app the transport is hidden behind TanStack Query / RTK Query anyway.
:::

### Axios instance with JWT and refresh-token retry queue

**Flow.** Request interceptor adds `Authorization: Bearer <access>`. When the API answers `401`, a response interceptor calls `POST /api/auth/refresh` **once**, queues every other request that failed meanwhile, then replays them all with the new token. If refresh fails, log out.

```typescript
import axios, { AxiosError, InternalAxiosRequestConfig } from 'axios';

export const api = axios.create({
  baseURL: import.meta.env.VITE_API_URL ?? 'https://localhost:5001/api',
  timeout: 15_000,
  withCredentials: true                                  // refresh token travels in an HttpOnly cookie
});

let accessToken: string | null = null;                   // in memory, not localStorage
export const setAccessToken = (t: string | null) => { accessToken = t; };

api.interceptors.request.use(cfg => {
  if (accessToken) cfg.headers.Authorization = `Bearer ${accessToken}`;
  return cfg;
});

type Retryable = InternalAxiosRequestConfig & { _retry?: boolean };
let refreshing = false;
let waiters: Array<(token: string | null) => void> = [];
const flush = (token: string | null) => { waiters.forEach(w => w(token)); waiters = []; };

api.interceptors.response.use(
  res => res,
  async (error: AxiosError) => {
    const original = error.config as Retryable;
    const is401 = error.response?.status === 401;
    if (!is401 || original._retry || original.url?.includes('/auth/')) {
      return Promise.reject(error);                      // not ours to handle
    }
    original._retry = true;

    if (refreshing) {                                    // someone is already refreshing: wait
      return new Promise((resolve, reject) => {
        waiters.push(token => {
          if (!token) return reject(error);
          original.headers.Authorization = `Bearer ${token}`;
          resolve(api(original));
        });
      });
    }

    refreshing = true;
    try {
      // plain axios (no interceptors) to avoid an infinite loop
      const { data } = await axios.post<{ accessToken: string }>(
        `${api.defaults.baseURL}/auth/refresh`, null, { withCredentials: true });
      setAccessToken(data.accessToken);
      flush(data.accessToken);
      original.headers.Authorization = `Bearer ${data.accessToken}`;
      return api(original);                              // replay the original request
    } catch (refreshError) {
      setAccessToken(null);
      flush(null);                                       // reject everyone waiting
      window.location.assign('/login');
      return Promise.reject(refreshError);
    } finally {
      refreshing = false;
    }
  }
);
```

:::warn Refresh stampede
Without the `refreshing` flag + queue, ten parallel requests that all get a 401 would trigger ten refresh calls; with rotating refresh tokens the second call would be rejected and the user logged out. The single in-flight refresh with a waiting queue is the standard fix (same idea as the Angular `BehaviorSubject` version later).
:::

### Error handling and ProblemDetails

ASP.NET Core returns errors as RFC 7807 **ProblemDetails** (`application/problem+json`): `{ type, title, status, detail, traceId, errors? }`. `[ApiController]` auto-returns `ValidationProblemDetails` for model-state failures, with `errors: { "Email": ["..."] }`. Map it once, then show field errors in forms and a toast for the rest.

```typescript
export function toProblem(e: unknown): ApiProblem {
  if (axios.isAxiosError(e)) {
    if (!e.response) return { status: 0, title: 'Cannot reach the server. Check your connection.' };
    const d = e.response.data as Partial<ApiProblem> & { detail?: string };
    return { status: e.response.status, title: d?.title ?? e.message, errors: d?.errors };
  }
  return { status: -1, title: (e as Error)?.message ?? 'Unexpected error' };
}
// 400 + errors -> setError(field, ...)   401 -> login   403 -> "no permission"
// 404 -> not-found view   409 -> concurrency message   5xx -> generic toast + traceId
```

**Error boundaries** catch errors thrown during *rendering* of their subtree and show a fallback. They are still **class components** (or use `react-error-boundary`). They do **not** catch errors in event handlers, async code (promises, timers), SSR, or in the boundary itself - handle those with `try/catch` or the query library's error state.

```typescript
class ErrorBoundary extends React.Component<
  { fallback: React.ReactNode; children: React.ReactNode }, { hasError: boolean }
> {
  state = { hasError: false };
  static getDerivedStateFromError() { return { hasError: true }; }
  componentDidCatch(error: Error, info: React.ErrorInfo) {
    reportToServer({ message: error.message, stack: info.componentStack });   // e.g. App Insights
  }
  render() { return this.state.hasError ? this.props.fallback : this.props.children; }
}
// <ErrorBoundary fallback={<p>Something went wrong.</p>}><Routes /></ErrorBoundary>
```

### Loading, error and empty states pattern

Every async view has **four** states: loading, error, empty, data. Model them explicitly, never as "data is undefined" guesses; keep skeletons the same size as content to avoid layout shift, and offer *retry* on error.

```typescript
type AsyncViewProps<T> = {
  loading: boolean; error?: ApiProblem | null; data?: T[] | null;
  onRetry?: () => void; empty?: React.ReactNode; children: (rows: T[]) => React.ReactNode;
};
export function AsyncView<T>({ loading, error, data, onRetry, empty, children }: AsyncViewProps<T>) {
  if (loading) return <div aria-busy="true" className="skeleton" />;
  if (error) return (
    <div role="alert">{error.title} {onRetry && <button onClick={onRetry}>Retry</button>}</div>
  );
  if (!data || data.length === 0) return <>{empty ?? <p>Nothing here yet.</p>}</>;
  return <>{children(data)}</>;
}
```

### CORS with ASP.NET Core

The browser blocks a SPA on another origin unless the API opts in. Use a **named policy with explicit origins** (never `AllowAnyOrigin` together with credentials), expose custom headers, and place `UseCors` before authentication/authorization.

```csharp
builder.Services.AddCors(options => options.AddPolicy("spa", policy => policy
    .WithOrigins("http://localhost:5173", "https://shop.contoso.com")   // React/Vite, prod
    .AllowAnyHeader()
    .AllowAnyMethod()
    .AllowCredentials()                          // cookies (refresh token) + explicit origins only
    .WithExposedHeaders("X-Pagination")));       // else JS cannot read this response header

builder.Services.AddProblemDetails();            // consistent application/problem+json

var app = builder.Build();
app.UseExceptionHandler();                       // unhandled exceptions -> ProblemDetails
app.UseHttpsRedirection();
app.UseCors("spa");                              // BEFORE UseAuthentication / UseAuthorization
app.UseAuthentication();
app.UseAuthorization();
app.MapControllers();

// controller: pagination metadata in a header
Response.Headers["X-Pagination"] = JsonSerializer.Serialize(new { page, pageSize, total });
```

:::scenario Axios call fails with "blocked by CORS policy: No 'Access-Control-Allow-Origin' header"
Checks, in order: (1) is the exact origin (scheme + host + port) in `WithOrigins`? (2) is `UseCors` before `UseAuthorization`? A 401 response without CORS headers is shown as a CORS error. (3) Preflight `OPTIONS` must succeed: `AllowAnyHeader` for `Authorization`. (4) With cookies you need `withCredentials` on the client and `AllowCredentials` on the server. (5) In dev, a Vite `server.proxy` to `/api` avoids CORS entirely.
:::
