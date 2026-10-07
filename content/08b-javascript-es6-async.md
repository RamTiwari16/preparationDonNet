## Asynchronous JavaScript

### Callbacks and callback hell

**Definition.** A *callback* is a function passed to another function to be invoked later (on completion, on an event, on a timer). JavaScript is single-threaded, so anything slow (network, timers, disk) is started and a callback is registered instead of blocking.

**Why it matters.** Callbacks are the foundation under Promises and async/await, and "explain callback hell and how you escape it" is a standard warm-up question.

```javascript
// Synchronous callback
[1, 2, 3].forEach(n => console.log(n));

// Asynchronous, Node-style error-first callback
getUser(1, (err, user) => {
  if (err) return console.error(err);
  getOrders(user.id, (err, orders) => {              // callback hell: pyramid of doom
    if (err) return console.error(err);
    getPayment(orders[0].id, (err, payment) => {
      if (err) return console.error(err);
      console.log(payment.status);
    });
  });
});
```

Problems: deep nesting, error handling repeated at every level, *inversion of control* (you trust the library to call you exactly once). The fix is Promises (flat chains, one `catch`) and then `async/await`:

```javascript
async function showPayment() {
  try {
    const user = await getUser(1);
    const orders = await getOrders(user.id);
    const payment = await getPayment(orders[0].id);
    console.log(payment.status);
  } catch (err) { console.error(err); }
}
```

### Promises

**Definition.** A `Promise` is an object representing the eventual result of an async operation. It is in one of three states: **pending**, **fulfilled** (has a value) or **rejected** (has a reason). Once settled it never changes.

```javascript
const sleep = ms => new Promise(resolve => setTimeout(resolve, ms));

const p = new Promise((resolve, reject) => {     // executor runs synchronously
  const ok = true;
  setTimeout(() => (ok ? resolve({ id: 1 }) : reject(new Error('boom'))), 100);
});

p.then(v => v.id)                // .then returns a NEW promise
 .then(id => { throw new Error('bad ' + id); })
 .catch(err => { console.log(err.message); return 'recovered'; })
 .finally(() => console.log('cleanup'))        // no args; value passes through
 .then(v => console.log(v));
// Output: bad 1 -> cleanup -> recovered
```

Chaining rules (frequently tested):
- A value returned from `.then` becomes the next promise's value; a returned *promise* is awaited (flattened); a *thrown* error rejects the next promise.
- `.catch(fn)` is `.then(undefined, fn)`; if it returns normally the chain continues as fulfilled.
- `.finally` runs either way, receives nothing, and does not change the outcome (unless it throws).
- Always **return** the inner promise in a `then`, otherwise the chain doesn't wait for it.
- Handlers are always run asynchronously, as **microtasks**.

#### Combinators

| Method | Resolves when | Rejects when | Result |
|---|---|---|---|
| `Promise.all([...])` | all fulfil | **first** rejection (fail-fast) | array of values, in input order |
| `Promise.allSettled([...])` | all settle | never | `[{status:'fulfilled', value}, {status:'rejected', reason}]` |
| `Promise.race([...])` | first to settle, if it fulfilled | first to settle, if it rejected | that one value/reason |
| `Promise.any([...])` | first to **fulfil** | all reject -> `AggregateError` | first value |

```javascript
const [products, categories] = await Promise.all([
  fetch('/api/products').then(r => r.json()),
  fetch('/api/categories').then(r => r.json())
]);

const results = await Promise.allSettled([loadOrders(), loadInvoices(), loadReturns()]);
const failed = results.filter(r => r.status === 'rejected');   // dashboard: show partial data

// Timeout pattern with race
const withTimeout = (promise, ms) =>
  Promise.race([promise, new Promise((_, rej) => setTimeout(() => rej(new Error('timeout')), ms))]);

// Mirror failover: first healthy region wins
const data = await Promise.any([fetch(euApi), fetch(usApi)]);
```

:::q Promise.all vs Promise.allSettled?
`all` is fail-fast: one rejection rejects the whole thing (the other requests still run, you just stop waiting). Use it when you need *every* result to continue. `allSettled` never rejects and reports each outcome, so use it for independent widgets/batch jobs where partial success is acceptable. Note: neither cancels the other requests - cancellation needs `AbortController`.
:::

:::warn Unhandled rejections
A rejected promise with no handler fires `unhandledrejection` in browsers and (since Node 15) crashes the Node process by default. Always end chains with `catch`, or use `try/catch` around `await`. Never create a promise and forget it (`floating promise`) - the same sin as an un-awaited `Task` in C#.
:::

### async / await

**Definition.** `async` makes a function always return a Promise; `await` suspends *that function* (not the thread) until the awaited promise settles, then resumes it as a microtask. It is syntactic sugar over promises, giving synchronous-looking code and ordinary `try/catch`.

```javascript
async function loadOrder(id) {
  try {
    const res = await fetch(`/api/orders/${id}`);
    if (!res.ok) throw new Error(`HTTP ${res.status}`);     // fetch does NOT reject on 404/500
    return await res.json();                                // return await inside try => caught here
  } catch (err) {
    console.error('loadOrder failed', err);
    throw err;                                              // rethrow so the caller can react
  } finally {
    hideSpinner();
  }
}
```

#### Sequential vs parallel

```javascript
// Sequential: 3 s total (each waits for the previous) - needed ONLY if they depend on each other
const a = await getA();   // 1 s
const b = await getB();   // 1 s
const c = await getC();   // 1 s

// Parallel: 1 s total - start all, then await together
const [a2, b2, c2] = await Promise.all([getA(), getB(), getC()]);

// Equivalent: start first, await later
const pb = getB();  const pc = getC();
const b3 = await pb; const c3 = await pc;
```

#### await in loops

```javascript
const ids = [1, 2, 3];

ids.forEach(async id => { await save(id); });     // BUG: forEach ignores the returned promises
console.log('done');                              // prints BEFORE any save finished

for (const id of ids) await save(id);             // sequential, preserves order
await Promise.all(ids.map(id => save(id)));       // parallel (watch the API rate limits)
```

Other facts: `await` works at the top level of ES modules; `await` on a non-promise wraps it in a resolved promise (still yields one microtask turn); an `async` function that throws returns a *rejected promise* instead of throwing synchronously.

:::scenario Dashboard is slow: 5 independent API calls take 5x as long
Cause: five `await`s in a row. Fix: `Promise.all` (or `allSettled` if one failing widget must not blank the page). Then check the backend: five parallel calls into an ASP.NET Core API means five scoped DbContexts - fine, but consider a single aggregate endpoint (BFF) if the calls are always made together.
:::

### The event loop

**Definition.** JavaScript runs on one thread with one **call stack**. Asynchronous work is delegated to the host (browser Web APIs or Node's libuv): timers, network, DOM events. When they complete, a callback is queued. The **event loop** pushes queued callbacks onto the stack *only when the stack is empty*.

```text
            ┌─────────────┐   delegates    ┌──────────────────────────┐
 code  ───▶ │ Call Stack  │ ─────────────▶ │ Web APIs / Node APIs     │
            └─────▲───────┘                │ (timers, fetch, DOM evt) │
                  │                         └───────────┬──────────────┘
                  │ event loop picks next               │ when done, enqueue
        ┌─────────┴──────────┐                          ▼
        │ 1. Microtask queue │◀── promise .then/.catch/await, queueMicrotask
        │ 2. Task (macrotask)│◀── setTimeout, setInterval, I/O, click, MessageChannel
        └────────────────────┘
```

**One turn of the loop:** run one macrotask to completion -> **drain the whole microtask queue** (including microtasks queued by microtasks) -> let the browser render if needed -> next macrotask. So **microtasks always run before the next timer**, even `setTimeout(fn, 0)`.

#### Output-order puzzle

```javascript
console.log('1');
setTimeout(() => console.log('2'), 0);
Promise.resolve().then(() => console.log('3'));
queueMicrotask(() => console.log('4'));
(async () => { console.log('5'); await null; console.log('6'); })();
console.log('7');
// Output: 1 5 7 3 4 6 2
```

Walk-through: synchronous code first: `1`, `5` (an async function runs synchronously until its first `await`), `7`. Along the way the timer was handed to the Web API (macrotask), and three microtasks were queued in order: `3`, `4`, and the continuation after `await null` (`6`). When the stack empties, microtasks drain in FIFO order: `3 4 6`. Only then does the timer's macrotask run: `2`.

```javascript
async function a1() { console.log('a1 start'); await a2(); console.log('a1 end'); }
async function a2() { console.log('a2'); }
console.log('script start');
setTimeout(() => console.log('timeout'), 0);
a1();
new Promise(res => { console.log('p1'); res(); }).then(() => console.log('p2'));
console.log('script end');
// Output: script start, a1 start, a2, p1, script end, a1 end, p2, timeout
// (modern engines: awaiting a native promise costs one microtask tick; a1 end is queued
//  before p2, so it runs first)
```

**Facts to state.**
- `setTimeout(fn, 0)` is not instant: it means "after the current stack and microtasks, at the earliest" (browsers clamp nested timers to >= 4 ms).
- A long synchronous loop blocks everything: no rendering, no clicks. Break work up (`setTimeout`/`requestIdleCallback`), or use a Web Worker.
- A microtask that endlessly queues microtasks starves rendering and timers.
- Node: `process.nextTick` runs before promise microtasks; `setImmediate` runs in the check phase after I/O.

:::q Explain the event loop, and why does a Promise callback run before setTimeout(0)?
The stack runs synchronous code. Async operations are delegated to the host and their callbacks are queued. After each macrotask the engine drains the microtask queue completely (promise reactions, `await` continuations, `queueMicrotask`) before taking the next macrotask (timers, I/O, UI events). A `.then` callback is a microtask, `setTimeout` is a macrotask, so the promise always wins.
:::

## Events & the DOM

### Event bubbling, capturing and delegation

**Definition.** When an event fires on an element it travels in three phases: **capturing** (window -> ... -> parent, top-down), **target**, then **bubbling** (target -> parent -> ... -> window, bottom-up). By default listeners run in the bubbling phase; pass `{ capture: true }` to listen while capturing.

```html
<ul id="orders">
  <li data-id="7">Order 7 <button class="cancel">Cancel</button></li>
  <li data-id="8">Order 8 <button class="cancel">Cancel</button></li>
</ul>
```

```javascript
const list = document.getElementById('orders');

// Event DELEGATION: one listener on the parent handles current AND future children
list.addEventListener('click', e => {
  const btn = e.target.closest('button.cancel');   // target = what was clicked
  if (!btn || !list.contains(btn)) return;
  const id = btn.closest('li').dataset.id;         // data-id -> dataset.id
  cancelOrder(id);
});

// Phases
window.addEventListener('click', () => console.log('window capture'), { capture: true });
list.addEventListener('click', () => console.log('ul bubble'));
// click on <button>: window capture -> ... -> button target -> li -> ul bubble -> ... window
```

| API | Effect |
|---|---|
| `e.target` | element that actually triggered the event |
| `e.currentTarget` | element the running listener is attached to (`this` for non-arrow handlers) |
| `e.stopPropagation()` | stop the event travelling to further elements (other listeners on the *same* element still run) |
| `e.stopImmediatePropagation()` | also stop remaining listeners on the same element |
| `e.preventDefault()` | cancel the browser default (form submit, link navigation, checkbox toggle) - does **not** stop propagation |
| `{ once: true }` | auto-remove after first call |
| `{ passive: true }` | promise not to call `preventDefault`; lets scroll stay smooth on touch/wheel |

**Why delegation:** fewer listeners (memory), works for dynamically added rows, one place to clean up. Caveats: not every event bubbles (`focus`, `blur`, `mouseenter`, `mouseleave` do not - use `focusin`/`focusout`/`mouseover`), and `stopPropagation` somewhere below breaks delegation. React uses delegation internally (a single listener at the root container since React 17).

:::q stopPropagation vs preventDefault?
`preventDefault` cancels the browser's default action for the event (the form not submitting, the link not navigating) but the event keeps bubbling. `stopPropagation` stops the event reaching ancestor listeners but the default action still happens. They are independent. (`return false` only prevents the default in an inline `onclick`, does both in a jQuery handler, and does nothing in `addEventListener`.)
:::

### DOM manipulation basics

**Definition.** The DOM is the browser's live object tree of the page. JavaScript selects nodes, changes their content/attributes/classes, and listens to events. React and Angular hide most of this, but interviewers still ask the fundamentals.

```javascript
// Select
const el  = document.getElementById('total');
const one = document.querySelector('.card > h2');           // first match, or null
const all = document.querySelectorAll('input[type=checkbox]'); // static NodeList
[...all].filter(cb => cb.checked);                           // NodeList is not an Array

// Create + insert (build off-DOM, insert once to avoid repeated reflow)
const frag = document.createDocumentFragment();
for (const p of products) {
  const li = document.createElement('li');
  li.textContent = `${p.name} - ${p.price}`;                 // safe: treated as text
  li.classList.add('item');
  li.dataset.id = p.id;
  frag.append(li);
}
document.querySelector('#list').append(frag);

// Update / remove
el.textContent = 'Total: 120';
el.setAttribute('aria-live', 'polite');
el.style.display = 'none';           // prefer classList.toggle('hidden')
el.remove();

// Run when ready
document.addEventListener('DOMContentLoaded', init);         // or <script type="module"> / defer
```

| | `textContent` | `innerText` | `innerHTML` |
|---|---|---|---|
| Parses HTML | no | no | **yes** |
| XSS risk with user/API data | none | none | **high** |
| Reads hidden text / CSS aware | no / no | no / yes (slower, triggers layout) | n/a |

**Performance.** Changing the DOM can trigger *reflow* (layout) and *repaint*. Batch writes, use `DocumentFragment` or `classList` toggles, avoid reading layout (`offsetHeight`) between writes, use `requestAnimationFrame` for animation. `<script defer>` runs after parsing in order; `async` runs as soon as downloaded, unordered.

:::warn innerHTML + data from an API = XSS
`el.innerHTML = product.description` executes `<img src=x onerror=...>` if an attacker stored it. Use `textContent`, or sanitize (DOMPurify). React escapes `{value}` by default (watch `dangerouslySetInnerHTML`); Angular sanitises `[innerHTML]` automatically. On the backend side also encode/validate, and set a CSP header from ASP.NET Core.
:::

:::q What is event delegation and why use it?
Attach one listener to a common ancestor and use `event.target` (usually with `closest()`) to find which child triggered it. It saves memory, handles dynamically inserted elements automatically and makes teardown simple. It relies on the event bubbling, so it won't work for events that don't bubble.
:::
