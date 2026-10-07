### Components and JSX

**In simple words:** In React, you build the screen from *components*. A component is a function that takes inputs (props) and returns what the UI should look like. *JSX* is HTML-like syntax inside JavaScript. A compiler turns JSX into normal function calls that create plain objects describing the UI.

**Real-life example:** Components are like LEGO bricks. You build small bricks (a button, a card) and join them to make a bigger model (a page).

**Interview question:** What is JSX and is it required?

**Simple answer:** JSX is optional syntax that looks like HTML. The build tool compiles it to `jsx()` or `React.createElement()` calls, which return simple objects like `{ type, props }`. Values inside `{ }` are escaped, so React is safe from script injection by default.

```javascript
function ProductCard({ product }) {
  return <li className="card">{product.name} - {product.price}</li>;
}
```

### Props vs state and one-way data flow

**In simple words:** *Props* are inputs a parent gives to a child. The child can only read them. *State* is data a component owns and can change with its setter, which re-renders the component. Data flows down through props. Events flow up when the child calls a function the parent passed in.

**Real-life example:** Props are like the order slip a waiter gives the chef — the chef does not change it. State is the chef's own notes about which dishes are cooking right now.

**Interview question:** What is the difference between props and state?

**Simple answer:** Props come from the parent and are read-only. State belongs to the component and changes over time through its setter, causing a re-render. If two siblings need the same data, I lift the state up to their nearest common parent and pass it down as props.

```javascript
function ProductCard({ product, onAdd }) {
  return <button onClick={() => onAdd(product.id)}>Add</button>;
}
```

### Function components and the "lifecycle"

**In simple words:** Function components do not have lifecycle methods like class components. A component *mounts* (first shows), *updates* (re-renders when props, state or context change) and *unmounts* (is removed). You use `useEffect` for work after rendering, and its cleanup function for work before the next run or on unmount.

**Real-life example:** A shop opens in the morning (mount), changes its window display during the day (update) and locks up at night (unmount, cleanup).

**Interview question:** How do you do `componentDidMount` and `componentWillUnmount` in a function component?

**Simple answer:** `useEffect(() => { ... }, [])` runs after the first render, like `componentDidMount`. The function you return from it is the cleanup, which runs on unmount. In development, Strict Mode runs effect, cleanup, effect once on mount to check your cleanup works; this does not happen in production.

```javascript
useEffect(() => {
  const id = setInterval(tick, 1000);  // on mount
  return () => clearInterval(id);      // on unmount
}, []);
```

### Virtual DOM, reconciliation and keys

**In simple words:** On each update, React calls your components and gets a new tree of light objects (the *virtual DOM*). It compares this tree with the previous one. This compare step is *reconciliation*. Then it changes only the parts of the real page that are different. In lists, a `key` tells React which item is which between renders.

**Real-life example:** A teacher compares today's attendance list with yesterday's and only updates the names that changed. Roll numbers (keys) make it easy to match each student.

**Interview question:** Why do lists need keys, and why not use the array index?

**Simple answer:** Keys give each item a stable identity, so React can reuse the right DOM element and state. If you use the index and insert or reorder items, the keys shift, and state like typed text can end up on the wrong row. Use a stable id from the data, like the database id.

```javascript
{todos.map(t => <TodoRow key={t.id} todo={t} />)}
```

### Controlled vs uncontrolled inputs, conditional rendering, lists

**In simple words:** A *controlled* input keeps its value in React state (`value` plus `onChange`). An *uncontrolled* input keeps its value in the DOM, and you read it with a ref when needed. *Conditional rendering* shows different UI using `if`, ternary (`? :`) or `&&`. Lists are rendered with `map` and a `key`.

**Real-life example:** A controlled input is like a cashier who writes down every item as you scan it. An uncontrolled one is like checking the basket only at the end.

**Interview question:** What is the difference between controlled and uncontrolled components?

**Simple answer:** In a controlled input, React state is the single source of truth, so I can validate on every keystroke. In an uncontrolled input, the DOM holds the value and I read it with a ref or `FormData` on submit. Uncontrolled inputs re-render less, which is why React Hook Form uses them.

```javascript
const [term, setTerm] = useState('');
<input value={term} onChange={e => setTerm(e.target.value)} />
{items.length > 0 && <List items={items} />}  // not items.length && ...
```

### useState

**In simple words:** `useState` gives a component a piece of data that it remembers between renders, plus a function to change it. Calling the setter tells React to re-render. Inside one render, the state value is a fixed *snapshot*. To update based on the old value, pass a function to the setter.

**Real-life example:** It is like a scoreboard at a match. The number shown stays the same until the official presses the update button, and then the board refreshes.

**Interview question:** If you call `setCount(count + 1)` three times in a row, what happens?

**Simple answer:** The count goes up by only 1, because `count` is the same snapshot value in that render. Using `setCount(c => c + 1)` three times adds 3, because each update uses the latest queued value. Also, never mutate state directly; always set a new object or array.

```javascript
const [count, setCount] = useState(0);
setCount(c => c + 1);   // safe update based on the latest value
```

### useEffect

**In simple words:** `useEffect` runs code after React has updated the page. Use it to sync with things outside React: API calls, timers, subscriptions, `document.title`. The *dependency array* decides when it runs again. If you return a function, React calls it as *cleanup* before the next run and on unmount.

**Real-life example:** After a delivery is dropped at your door (the render), you sign the receipt (the effect). If a new delivery comes, you first cancel the old receipt (cleanup).

**Interview question:** Explain the dependency array and cleanup in `useEffect`.

**Simple answer:** With no array, the effect runs after every render. With `[]`, it runs once after mount. With `[a, b]`, it runs when `a` or `b` changes. Before running again, React calls the old cleanup, where I clear timers or abort requests. Missing dependencies cause *stale closures* (using old values).

```javascript
useEffect(() => {
  const ctrl = new AbortController();
  fetch(`/api/products?c=${category}`, { signal: ctrl.signal });
  return () => ctrl.abort();      // cancel old request
}, [category]);
```

### useContext

**In simple words:** *Context* lets you share a value with any child component without passing props through every level. You create a context, wrap part of the app in a Provider, and read the value with `useContext`. It is good for data that changes rarely, like the logged-in user or the theme.

**Real-life example:** It is like a building's notice board. Anyone on any floor can read it, without each floor passing the message down by hand.

**Interview question:** What is the main performance problem with Context?

**Simple answer:** When the Provider's value changes, every component that uses that context re-renders. So I keep fast-changing data out of context, memoise the value with `useMemo`, and split one big context into smaller ones. For frequent global updates, a store with selectors like Redux or Zustand is better.

```javascript
const AuthContext = createContext(null);
// <AuthContext.Provider value={auth}>...</AuthContext.Provider>
const auth = useContext(AuthContext);
```

### useReducer

**In simple words:** `useReducer` manages state with a *reducer*: a pure function that takes the current state and an *action* and returns the new state. You call `dispatch(action)` to change state. It is useful when state has many related fields or many kinds of changes.

**Real-life example:** A bank teller gets a slip saying "deposit 100" or "withdraw 50". The teller follows fixed rules for each slip type and updates the balance.

**Interview question:** When would you choose `useReducer` over `useState`?

**Simple answer:** I use `useReducer` when the next state depends on the previous one in complex ways, or when many actions change the same object, like a shopping cart. All the update logic is in one pure function, which is easy to test. The reducer must not fetch data or mutate state.

```javascript
function cartReducer(state, action) {
  switch (action.type) {
    case 'clear': return { lines: [] };
    default: return state;
  }
}
const [cart, dispatch] = useReducer(cartReducer, { lines: [] });
```

### useMemo and useCallback

**In simple words:** `useMemo` remembers a calculated *value* between renders. `useCallback` remembers a *function* so it keeps the same identity. Both recalculate only when a dependency changes. They are performance tools; use them only where they help.

**Real-life example:** `useMemo` is like writing a long sum's answer on a sticky note so you do not calculate it again unless the numbers change.

**Interview question:** What is the difference between `useMemo`, `useCallback` and `React.memo`?

**Simple answer:** `useMemo` caches a computed value. `useCallback` caches a function reference, mainly to pass stable props to a memoised child. `React.memo` wraps a component and skips re-rendering if its props are the same. I add them after measuring, not everywhere, because they also have a cost.

```javascript
const visible = useMemo(() => products.filter(p => p.price < max), [products, max]);
const onSelect = useCallback(id => setSelected(id), []);
```

### useRef

**In simple words:** `useRef` gives you a box `{ current }` that stays the same across renders. Changing `.current` does NOT cause a re-render. You use it to point to a DOM element (for example, to focus an input) or to keep a value like a timer id.

**Real-life example:** It is like a sticky note on your desk. You can change what is written on it at any time, and nobody gets notified.

**Interview question:** What is the difference between `useRef` and `useState`?

**Simple answer:** Both keep a value between renders. Changing state triggers a re-render, but changing a ref does not. I use state for anything shown on screen, and refs for DOM nodes and values that do not affect the UI, like timer ids or the previous value.

```javascript
const inputRef = useRef(null);
useEffect(() => { inputRef.current?.focus(); }, []);
return <input ref={inputRef} />;
```

### useLayoutEffect (briefly)

**In simple words:** `useLayoutEffect` works like `useEffect`, but it runs right after React changes the DOM and *before* the browser paints the screen. Use it to measure an element and adjust its position without a visible flicker. Because it blocks painting, use `useEffect` by default.

**Real-life example:** A tailor measures and adjusts a suit before the customer looks in the mirror, so they never see the bad fit.

**Interview question:** When would you use `useLayoutEffect` instead of `useEffect`?

**Simple answer:** `useEffect` runs after paint, so it does not block the screen; it is right for data fetching and subscriptions. `useLayoutEffect` runs before paint, so I use it only to read layout, like an element's size, and fix position before the user sees it, for example a tooltip.

### useFetch (complete)

**In simple words:** `useFetch` is a *custom hook* (your own hook built from other hooks) that wraps data loading. It returns `data`, `loading`, `error` and a `refetch` function. Inside, it uses `useEffect` to call the API and an `AbortController` to cancel old requests.

**Real-life example:** It is like a food delivery app that tracks your order for you: "preparing", "delivered" or "failed", with a "try again" button.

**Interview question:** What is a custom hook and do two components using it share state?

**Simple answer:** A custom hook is a function starting with `use` that calls other hooks to reuse stateful logic. Each component that calls it gets its own separate state; it is not shared. For real apps, I prefer TanStack Query, because it adds caching, retries and de-duplication.

```javascript
const { data: orders, loading, error, refetch } =
  useFetch('/api/orders?page=1');
```

### useDebounce and a search box

**In simple words:** *Debounce* means "wait until the user stops typing for a short time, then act". `useDebounce` returns a value that updates only after a pause, for example 400 ms. A search box uses it so the API is called once after typing stops, not on every key.

**Real-life example:** A lift waits a few seconds after the last person enters before closing the doors. If someone else walks in, the wait starts again.

**Interview question:** How do you stop a search box from calling the API on every keystroke?

**Simple answer:** I debounce the input value with a hook that uses `setTimeout` inside `useEffect` and clears the timer in cleanup. Only the debounced value is used in the API URL. I also cancel old requests so a slow, older response cannot overwrite a newer one.

```javascript
function useDebounce(value, delay = 400) {
  const [d, setD] = useState(value);
  useEffect(() => {
    const id = setTimeout(() => setD(value), delay);
    return () => clearTimeout(id);
  }, [value, delay]);
  return d;
}
```

### Local vs global vs server state

**In simple words:** Not all state is the same kind. *Local* state belongs to one component, like an input's text. *Global* client state is shared across the app, like the logged-in user or cart. *Server* state is a copy of data from your API, like products. Each kind has a best tool.

**Real-life example:** In a restaurant, a waiter's notepad is local. The menu on the wall is global. The kitchen's stock list is server state — it lives somewhere else and you keep a copy.

**Interview question:** When would you choose Context, Redux or TanStack Query?

**Simple answer:** I keep state as local as possible. Context is for rarely changing values like theme or user. Redux Toolkit or Zustand is for complex, often-changing client state. For data from the API, I use TanStack Query or RTK Query, because they handle caching, refetching and loading states.

### Redux and Redux Toolkit

**In simple words:** Redux keeps app state in one central *store*. The UI sends *actions* (like `{ type: 'cart/added' }`). Pure *reducers* create the new state. *Selectors* read parts of it. Redux Toolkit (RTK) is the official, modern way to write Redux with much less code; it lets you write "mutating" code that is turned into safe immutable updates.

**Real-life example:** It is like a bank's central ledger. Nobody edits it directly; everyone submits a request slip, and the ledger is updated by fixed rules.

**Interview question:** What does Redux Toolkit add over plain Redux?

**Simple answer:** RTK gives `configureStore` with devtools set up, `createSlice` to write reducers and actions together, Immer so updates look like mutation but stay immutable, `createAsyncThunk` for API calls, and RTK Query for server data. It removes most of the old boilerplate.

```typescript
const cartSlice = createSlice({
  name: 'cart',
  initialState: { lines: [] as Line[] },
  reducers: { cleared: state => { state.lines = []; } }
});
```

### TanStack Query and Zustand

**In simple words:** TanStack Query (React Query) manages *server state*. It stores API results in a cache by a key, refetches in the background, retries on failure and removes duplicate requests. Zustand is a very small store for *client state*, with no Provider and very little code.

**Real-life example:** TanStack Query is like a library that keeps popular books on a front shelf and checks for new editions. Zustand is a small shared notebook on the office desk.

**Interview question:** Why use TanStack Query instead of `useEffect` + `fetch`?

**Simple answer:** Hand-written fetching has no cache, no de-duplication and no retries, and it is easy to get race conditions. TanStack Query gives caching by `queryKey`, background refresh, retries and `invalidateQueries` after a save. Zustand is a light choice for global client state, with selectors that limit re-renders.

```typescript
const { data, isPending, isError } = useQuery({
  queryKey: ['orders', page],
  queryFn: () => api.get('/orders', { params: { page } }).then(r => r.data)
});
```

### fetch vs Axios

**In simple words:** `fetch` is built into the browser. Axios is an extra library. The big difference: `fetch` does NOT fail on HTTP errors like 404 or 500, so you must check `res.ok`. Axios throws an error for non-2xx responses, converts JSON automatically and has *interceptors* (code that runs on every request or response).

**Real-life example:** `fetch` is a basic post office counter: it delivers, but you must open and check the reply yourself. Axios is a courier service that also checks the parcel and tells you if something went wrong.

**Interview question:** What is the difference between `fetch` and Axios?

**Simple answer:** `fetch` is built in but does not reject on HTTP errors and needs manual JSON handling. Axios rejects on non-2xx, handles JSON both ways, supports timeouts and has interceptors for things like adding a JWT. Both can cancel requests with `AbortController`.

```javascript
const res = await fetch('/api/orders');
if (!res.ok) throw new Error(`HTTP ${res.status}`);
const orders = await res.json();
```

### Axios instance with JWT and refresh-token retry queue

**In simple words:** You create one Axios instance for your API. A *request interceptor* adds `Authorization: Bearer <token>` to every call. When the API returns 401 (token expired), a *response interceptor* calls the refresh endpoint only once. Other failed requests wait in a queue and are retried with the new token. If refresh fails, the user goes to login.

**Real-life example:** When your gym card expires, one person goes to the desk to renew the group pass. Everyone else waits in line, then enters together with the new pass.

**Interview question:** How do you handle JWT expiry and token refresh in a React app?

**Simple answer:** I keep the access token in memory and the refresh token in an HttpOnly cookie. On a 401, the interceptor refreshes once, queues other failed requests and replays them with the new token. Without the queue, ten parallel 401s would trigger ten refresh calls and could log the user out.

```typescript
api.interceptors.request.use(cfg => {
  if (accessToken) cfg.headers.Authorization = `Bearer ${accessToken}`;
  return cfg;
});
```

### Error handling and ProblemDetails

**In simple words:** ASP.NET Core returns errors in a standard JSON shape called *ProblemDetails*, with `title`, `status`, `detail` and sometimes `errors` per field. In React, you convert any error into one shape once, then show field errors in forms and a message for others. *Error boundaries* catch errors thrown while rendering and show a fallback screen.

**Real-life example:** A hospital uses the same report form for every test result. Any doctor can read it quickly because the layout is always the same.

**Interview question:** What do React error boundaries not catch?

**Simple answer:** They catch only errors thrown during rendering of their child components. They do not catch errors in event handlers, async code like promises or timers, server rendering, or the boundary itself. For those, I use `try/catch` or the error state from my data library.

```typescript
// 400 + errors -> show under each field
// 401 -> go to login, 403 -> "no permission"
// 5xx -> toast with traceId
const problem = toProblem(error);
```

### Loading, error and empty states pattern

**In simple words:** Every screen that loads data has four states: loading, error, empty and data. You should handle each one clearly instead of guessing from `undefined`. Show a skeleton while loading, a message with a Retry button on error, and a friendly text when there is no data.

**Real-life example:** A delivery app shows "preparing", "something went wrong — retry", "no orders yet" or your order list. You always know what is happening.

**Interview question:** How do you handle loading and error states in a React component?

**Simple answer:** I model all four states explicitly: loading, error, empty and data. Early returns keep the code clear. I keep the skeleton the same size as the content to avoid layout jumps, and I always offer a retry on error.

```javascript
if (loading) return <Spinner />;
if (error) return <ErrorBox onRetry={refetch} />;
if (orders.length === 0) return <p>No orders yet.</p>;
return <OrderList orders={orders} />;
```

### CORS with ASP.NET Core

**In simple words:** *CORS* (Cross-Origin Resource Sharing) is a browser rule. A page from one *origin* (scheme + host + port) cannot read responses from another origin unless the server allows it. So if React runs on `localhost:5173` and the API on `localhost:5001`, the API must send CORS headers.

**Real-life example:** A school gate guard lets in visitors only if their name is on the approved list. The API's CORS policy is that list.

**Interview question:** How do you configure CORS in ASP.NET Core for a React app?

**Simple answer:** I add a named policy with the exact allowed origins, and call `UseCors` before `UseAuthentication` and `UseAuthorization`. I never combine `AllowAnyOrigin` with credentials. CORS is enforced by the browser, so it is not a replacement for authentication.

```csharp
builder.Services.AddCors(o => o.AddPolicy("spa", p => p
    .WithOrigins("http://localhost:5173")
    .AllowAnyHeader().AllowAnyMethod().AllowCredentials()));
app.UseCors("spa"); // before UseAuthentication
```

### Why components re-render and how to reduce it

**In simple words:** A component re-renders when its state changes, its parent re-renders, or a context it uses changes. A re-render means React calls your function again and compares the result; the real DOM changes only if something is different. Most re-renders are cheap. Problems come from big, slow parts re-rendering too often.

**Real-life example:** When a manager changes one rule, the whole team re-reads the notice board, even people it does not affect. Better to put the notice only where it matters.

**Interview question:** How do you avoid unnecessary re-renders in React?

**Simple answer:** First, I measure with the React Profiler. Then I move fast-changing state down into small components, use `React.memo` with stable props from `useCallback` and `useMemo`, split big contexts, and virtualise long lists. I add memoisation only where it helps.

```javascript
const OrderRow = React.memo(function OrderRow({ order, onSelect }) {
  return <tr onClick={() => onSelect(order.id)}><td>{order.id}</td></tr>;
});
```

### Lazy loading and code splitting

**In simple words:** *Code splitting* breaks your app's JavaScript into smaller files. *Lazy loading* downloads a file only when it is needed. In React, `React.lazy` with `<Suspense>` loads a page's code the first time the user opens it. Splitting by route gives the biggest win.

**Real-life example:** A restaurant brings each course when you are ready for it, instead of putting every dish on the table at once.

**Interview question:** What is code splitting and how do you do it in React?

**Simple answer:** It reduces the first download so the app starts faster. I use `React.lazy(() => import('./Page'))` and wrap it in `<Suspense fallback>` to show a spinner while it loads. The bundler (Vite or webpack) creates the separate files automatically.

```javascript
const AdminDashboard = lazy(() => import('./pages/AdminDashboard'));
<Suspense fallback={<Spinner />}><AdminDashboard /></Suspense>
```

### Virtualising long lists

**In simple words:** If you render 10,000 rows, the browser creates 10,000 sets of elements, which is slow. *Virtualisation* (or *windowing*) renders only the rows you can see, plus a few extra, and swaps them as you scroll. Libraries like TanStack Virtual and react-window do this.

**Real-life example:** A train window shows only a small part of the view at a time. The rest of the landscape is there, but you only see what passes the window.

**Interview question:** How would you show a list of 10,000 items without the page lagging?

**Simple answer:** I virtualise the list so only visible rows exist in the DOM, using a library like TanStack Virtual. For very large data, I also add server-side paging with `page` and `pageSize`, so the browser never loads everything at once.

### Measuring: Profiler, bundle analysis, debouncing

**In simple words:** Before you optimise, you measure. The React DevTools *Profiler* shows which components rendered, why, and how long it took. A *bundle analyzer* shows what is inside your JavaScript files, so you can remove heavy libraries. *Debouncing* input reduces how often expensive work or API calls run.

**Real-life example:** A doctor checks blood tests before prescribing medicine. You check the Profiler before changing code.

**Interview question:** A table with 5,000 rows lags when typing in the filter box. How do you fix it?

**Simple answer:** First I record it in the Profiler to see what re-renders. Then I keep the input state small and pass a debounced value, `React.memo` the rows with stable handlers, `useMemo` the filtered list, and virtualise the rows. If it is still slow, I move filtering and paging to the server.

### React Router v6: routes and protected routes

**In simple words:** React Router shows different components for different URLs, without reloading the page. You define routes, nested layouts use `<Outlet />`, and `:id` in a path gives a parameter. A *protected route* checks if the user is logged in and, if not, redirects to the login page.

**Real-life example:** A building directory sends you to the right floor for each department. A security desk stops you before the restricted floors unless you have a badge.

**Interview question:** How do you build a protected route, and is it enough for security?

**Simple answer:** I make a guard component that checks the user and returns `<Navigate to="/login" />` or `<Outlet />`. But this only improves the user experience; anyone can bypass it in the browser. The real protection is `[Authorize]` on the ASP.NET Core API.

```javascript
function RequireAuth() {
  const { user } = useAuth();
  if (!user) return <Navigate to="/login" replace />;
  return <Outlet />;
}
```

### Forms: React Hook Form (brief)

**In simple words:** React Hook Form is a library for forms. It uses uncontrolled inputs, so typing does not re-render the whole form. It is often used with *zod*, a library for describing validation rules. You can also show server validation errors on the matching fields with `setError`.

**Real-life example:** It is like a bank form that a clerk checks once when you hand it in, not after every letter you write.

**Interview question:** Why use React Hook Form, and should you still validate on the server?

**Simple answer:** It gives good performance, less code and easy schema validation with zod. Yes, I always validate on the server too, because client checks can be bypassed. I map ASP.NET Core validation errors back to fields using `setError`.

```typescript
const { register, handleSubmit, formState: { errors } } =
  useForm({ resolver: zodResolver(schema) });
<input {...register('email')} />
```

### Testing: React Testing Library + Vitest/Jest (brief)

**In simple words:** React Testing Library tests components the way a user uses them. You render the component, find elements by role or text, click or type with `userEvent`, and check what is on screen. Vitest or Jest runs the tests. MSW (Mock Service Worker) fakes the API at the network level.

**Real-life example:** It is like a mystery shopper who tests a shop by using it like a real customer, not by checking the shop's internal wiring.

**Interview question:** What is the testing philosophy of React Testing Library?

**Simple answer:** Test behaviour, not implementation details. I query by role or label, as a user or screen reader would, interact with `userEvent`, and assert on the DOM. I mock the network with MSW instead of mocking `fetch` directly, so the tests stay close to real use.

```javascript
render(<ProductList category="all" />);
expect(await screen.findByText('Pen')).toBeInTheDocument();
```
