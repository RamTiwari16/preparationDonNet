## `this` in Practice

**Definition.** Recap: `this` is fixed at the *call site* (arrows are the exception). The table is the quickest way to answer "what is `this` here?".

| Situation | `this` is |
|---|---|
| `fn()` in a module / strict mode | `undefined` |
| `fn()` in sloppy script | `globalThis` (`window` in browsers) |
| `obj.fn()` | `obj` |
| `const f = obj.fn; f()` | `undefined` / `globalThis` (binding lost) |
| `fn.call(x)`, `apply(x)`, `bind(x)()` | `x` |
| `new Fn()` | the new object |
| Arrow function | `this` of the enclosing scope, forever |
| DOM handler, regular function: `el.addEventListener('click', function () {})` | `el` (`currentTarget`) |
| DOM handler, arrow function | enclosing scope (not the element - use `e.currentTarget`) |
| `setTimeout(function () {...})` | `globalThis`/`undefined` (Node: the `Timeout` object) |
| Class method passed as callback | `undefined` (class bodies are strict) - bind it or use a field arrow |

```javascript
class Cart {
  items = [];
  add(item) { this.items.push(item); }               // normal method
  addLater = item => { this.items.push(item); };     // class field arrow: this always the instance
}
const cart = new Cart();
const { add, addLater } = cart;
// add('pen');            // TypeError: Cannot read properties of undefined (reading 'items')
addLater('pen');          // works
button.addEventListener('click', cart.add.bind(cart, 'pen'));
```

## JSON

**Definition.** JSON is a text format (strings, numbers, booleans, `null`, arrays, objects). `JSON.stringify` serialises, `JSON.parse` deserialises. It is the lingua franca between a JavaScript frontend and an ASP.NET Core API.

```javascript
const order = { id: 7, placedAt: new Date('2025-01-15T10:30:00Z'), note: undefined,
                lines: [{ sku: 'A1', qty: 2 }], fn() {}, big: 10n };

JSON.stringify({ ...order, big: undefined });
// '{"id":7,"placedAt":"2025-01-15T10:30:00.000Z","lines":[{"sku":"A1","qty":2}]}'
// undefined and functions are dropped; Date -> ISO string; BigInt throws TypeError

JSON.stringify(order.lines, null, 2);                 // pretty-print, 2 spaces
JSON.stringify(order, ['id', 'lines']);               // replacer array = whitelist
JSON.stringify({ n: NaN, i: Infinity });              // '{"n":null,"i":null}'

const parsed = JSON.parse('{"id":7,"placedAt":"2025-01-15T10:30:00Z"}',
  (key, value) => (key === 'placedAt' ? new Date(value) : value));   // reviver revives Dates
parsed.placedAt instanceof Date;                      // true

try { JSON.parse("{'bad': 1}"); } catch (e) { console.log(e.name); }  // SyntaxError

// toJSON lets an object control its own serialisation
class Money { constructor(a, c) { this.a = a; this.c = c; } toJSON() { return `${this.a} ${this.c}`; } }
JSON.stringify({ price: new Money(10, 'USD') });      // '{"price":"10 USD"}'
```

**.NET interop points.** ASP.NET Core's default `System.Text.Json` web options use **camelCase** property names (`OrderId` becomes `orderId`) and ISO-8601 dates; enums are numbers unless you add `JsonStringEnumConverter`. A C# `long` above 2^53 loses precision in JS - serialise as string. Model-binding validation failures come back as `application/problem+json` (see Fetch below).

## Fetch API

**Definition.** `fetch(url, options)` is the built-in promise-based HTTP client in browsers and Node 18+. It resolves with a `Response` as soon as headers arrive. Crucially, it **only rejects on network failure** (or abort), *not* on HTTP 4xx/5xx; check `response.ok`.

```javascript
const API = 'https://localhost:5001/api';

// GET with query string, token, abort + timeout
async function getOrders(page, signal) {
  const res = await fetch(`${API}/orders?page=${page}&pageSize=20`, {
    headers: { Accept: 'application/json', Authorization: `Bearer ${getToken()}` },
    signal: signal ?? AbortSignal.timeout(8000)          // cancel after 8 s
  });
  if (!res.ok) throw await toApiError(res);
  const pagination = JSON.parse(res.headers.get('X-Pagination') ?? '{}');
  return { data: await res.json(), pagination };         // header readable only if CORS exposes it
}

// POST JSON
async function createOrder(dto) {
  const res = await fetch(`${API}/orders`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json', Authorization: `Bearer ${getToken()}` },
    body: JSON.stringify(dto)
  });
  if (!res.ok) throw await toApiError(res);
  return res.status === 204 ? null : res.json();         // body can be read only ONCE
}

// Map ASP.NET Core ProblemDetails / ValidationProblemDetails to an Error
async function toApiError(res) {
  let problem = null;
  try { problem = await res.json(); } catch { /* not JSON */ }
  const err = new Error(problem?.title ?? `HTTP ${res.status}`);
  err.status = res.status;
  err.errors = problem?.errors;          // { "Email": ["Invalid email"] } for validation failures
  err.traceId = problem?.traceId;
  return err;
}

// Cancel the previous search when the user types again
let controller;
async function search(term) {
  controller?.abort();
  controller = new AbortController();
  try {
    const res = await fetch(`${API}/products?search=${encodeURIComponent(term)}`,
                            { signal: controller.signal });
    return await res.json();
  } catch (e) { if (e.name !== 'AbortError') throw e; }  // ignore our own cancellation
}

// File upload: let the browser set the multipart Content-Type + boundary
const fd = new FormData(); fd.append('file', fileInput.files[0]);
await fetch(`${API}/products/1/image`, { method: 'POST', body: fd });
```

**CORS in one paragraph.** A cross-origin request from `http://localhost:5173` (Vite/React) or `:4200` (Angular) to `https://localhost:5001` is allowed only if the API sends `Access-Control-Allow-Origin`. "Non-simple" requests (custom headers like `Authorization`, JSON `Content-Type`, `PUT/DELETE`) trigger a **preflight** `OPTIONS` request first. Cookies need `credentials: 'include'` on the client **and** `AllowCredentials()` with an explicit origin on the server. CORS is enforced by the *browser*; Postman or curl are never blocked, which is why "works in Postman, fails in the browser" is almost always CORS.

:::q Does fetch reject on a 404 or 500?
No. It only rejects on network errors, CORS failures or aborts. For HTTP errors it resolves with `response.ok === false`, so you must check `res.ok` (or `res.status`) and throw yourself. Axios differs: it rejects for any non-2xx by default.
:::

## Browser Storage

| | `localStorage` | `sessionStorage` | Cookies | IndexedDB |
|---|---|---|---|---|
| Capacity | about 5 MB per origin | about 5 MB per origin | about 4 KB per cookie | hundreds of MB+ |
| Lifetime | until cleared | until the **tab** closes | `Expires`/`Max-Age`, else session | until cleared |
| Sent to server automatically | no | no | **yes**, on every matching request | no |
| Readable by JS | yes | yes | yes, unless `HttpOnly` | yes |
| Scope | origin, shared across tabs | origin + single tab | domain + path (+ `SameSite`) | origin |
| API | sync, strings only | sync, strings only | `document.cookie` / `Set-Cookie` | async, structured data |
| XSS exposure | full | full | safe if `HttpOnly` | full |
| CSRF exposure | none | none | yes unless `SameSite`/anti-forgery | none |

```javascript
localStorage.setItem('theme', 'dark');
localStorage.setItem('cart', JSON.stringify([{ sku: 'A1', qty: 2 }]));   // strings only
const cart = JSON.parse(localStorage.getItem('cart') ?? '[]');
localStorage.removeItem('theme');   sessionStorage.clear();
window.addEventListener('storage', e => { /* fired in OTHER tabs when localStorage changes */ });
```

:::warn Where to keep the JWT?
Anything JS can read, an XSS attack can steal: `localStorage`, `sessionStorage`, non-HttpOnly cookies. Safer: keep the short-lived access token in memory (a variable/state) and the refresh token in an `HttpOnly; Secure; SameSite` cookie that the API sets, accepting that you must then protect the refresh endpoint against CSRF. `localStorage` is still widely used in tutorials and many real apps; say the trade-off out loud in an interview, and mention a strong CSP.
:::

## Quick-fire Q&A

:::q Output? Hoisting and TDZ.
```javascript
var a = 1;
function f() { console.log(a); var a = 2; }
f();
console.log(typeof x);
var x = 1;
console.log(typeof y);
let y = 2;
```
`undefined`, `"undefined"`, then `ReferenceError`. Inside `f` the local `var a` is hoisted and shadows the outer `a`, so it logs `undefined`. `typeof x` sees a hoisted `var` (`undefined`). `typeof y` hits the TDZ, and `typeof` does not protect you there.
:::

:::q Output? Coercion.
```javascript
console.log(1 + '2', '3' - 1, [] + [], [] + {}, true + 1, null + 1, undefined + 1);
```
`12 2  [object Object] 2 1 NaN` (the third value is an empty string). `+` with a string concatenates; `-` converts to number; `[] + []` is `'' + ''`; `{}` stringifies to `[object Object]`; `true` is 1; `null` is 0; `undefined` is `NaN`.
:::

:::q Output? Equality.
```javascript
console.log(0.1 + 0.2 === 0.3, NaN === NaN, [] == false, null == undefined,
            null === undefined, null >= 0, typeof NaN);
```
`false false true true false true "number"`. Floating point error; `NaN` equals nothing; `[]` -> `''` -> `0` equals `false`; `null == undefined` is a special rule; `>=` converts `null` to 0 but `==` does not.
:::

:::q Output? map with parseInt.
```javascript
console.log(['1', '2', '3'].map(parseInt));
```
`[1, NaN, NaN]`. `map` passes `(value, index)`, so it calls `parseInt('2', 1)` (radix 1 is invalid -> NaN) and `parseInt('3', 2)` ('3' is not a binary digit -> NaN). Fix: `.map(Number)` or `.map(s => parseInt(s, 10))`.
:::

:::q Output? var vs let in loops.
```javascript
for (var i = 0; i < 3; i++) setTimeout(() => console.log(i), 0);
for (let j = 0; j < 3; j++) setTimeout(() => console.log(j), 0);
```
`3 3 3 0 1 2`. One shared function-scoped `i` is already 3 when the timers fire; `let` creates a new binding per iteration.
:::

:::q Output? Lost this.
```javascript
// run as an ES module (strict)
const user = { name: 'Asha', hi() { return this?.name; }, arrow: () => this };
const f = user.hi;
console.log(user.hi(), f(), user.arrow());
```
`Asha undefined undefined`. `user.hi()` has `user` left of the dot. `f()` is a plain call, `this` is `undefined` in strict code. The arrow takes `this` from the module top level, which is `undefined` in an ES module (in a sloppy script it would be `window`).
:::

:::q Output? Event loop ordering.
```javascript
setTimeout(() => console.log('A'), 0);
Promise.resolve().then(() => console.log('B'));
Promise.resolve().then(() => {
  console.log('C');
  Promise.resolve().then(() => console.log('D'));
});
setTimeout(() => console.log('E'), 0);
console.log('F');
```
`F B C D A E`. Sync code first (`F`). Then the microtask queue is drained completely, including `D` which `C` queued. Only afterwards do the two timer macrotasks run in order.
:::

:::q Output? Promise chain.
```javascript
Promise.resolve(1)
  .then(v => { console.log(v); return v + 1; })
  .then(v => { console.log(v); throw new Error('x'); })
  .catch(() => { console.log('caught'); return 10; })
  .finally(() => console.log('finally'))
  .then(v => console.log(v));
```
`1 2 caught finally 10`. `catch` handles the error and returns 10, so the chain is fulfilled again. `finally` takes no argument and passes the value `10` through to the last `then`.
:::

:::q Output? Closures with factories.
```javascript
function make() { let c = 0; return () => ++c; }
const a = make(), b = make();
console.log(a(), a(), b(), a());
```
`1 2 1 3`. Each call to `make` creates a new lexical environment with its own `c`; `a` and `b` close over different variables.
:::

:::q Output? Shallow copy vs structuredClone.
```javascript
const a = { n: { v: 1 } };
const b = { ...a };
b.n.v = 2;
const c = structuredClone(a);
c.n.v = 3;
console.log(a.n.v, b.n.v, c.n.v);
```
`2 2 3`. Spread copies only the top level, so `a.n` and `b.n` are the same object. `structuredClone` copies deeply, so changing `c` does not touch `a`.
:::

:::q Output? || vs ??
```javascript
console.log(0 || 'x', 0 ?? 'x', '' ?? 'x', null ?? undefined ?? 'z', false || null);
```
`x 0  z null` (third value is an empty string). `||` replaces any falsy value; `??` replaces only `null`/`undefined`, so `0` and `''` survive.
:::

:::q Output? typeof, sort and NaN.
```javascript
console.log(typeof null, typeof [], typeof class {}, [10, 1, 2].sort(),
            [NaN].includes(NaN), [NaN].indexOf(NaN));
```
`object object function [1, 10, 2] true -1`. A class is a function; the default sort compares strings, so `10` comes before `2`; `includes` uses SameValueZero (finds `NaN`) while `indexOf` uses `===` (cannot).
:::

:::q What is the difference between null and undefined?
`undefined` means "no value was assigned" (uninitialised variable, missing property, function with no return). `null` is an explicit "intentionally empty". `null == undefined` is true, `null === undefined` is false, and `typeof` gives `"object"` and `"undefined"`. JSON has `null` but no `undefined`, which matters when mapping to C# nullable fields.
:::

:::q Where do you store a JWT in a SPA, and why?
There is a trade-off. `localStorage` is simple but readable by any injected script (XSS). An in-memory access token plus a refresh token in an `HttpOnly; Secure; SameSite` cookie avoids XSS theft but needs CSRF thought and a silent refresh on page load. Whatever you pick: short access-token lifetime, HTTPS everywhere, a CSP, and sanitised output.
:::

:::q Why does a fetch to my ASP.NET Core API work in Postman but fail in the browser?
CORS. The browser blocks reading a cross-origin response unless the API sends `Access-Control-Allow-Origin` (and answers the preflight `OPTIONS` for `Authorization`/JSON requests). Fix it on the server with `AddCors` + `UseCors` (before auth middleware), listing the exact SPA origin, and `WithExposedHeaders("X-Pagination")` if the client must read custom headers.
:::
