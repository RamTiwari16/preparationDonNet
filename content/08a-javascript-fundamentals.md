## Variables, Types & Coercion

### var, let, const

**Definition.** `var` is function-scoped and legacy. `let` and `const` (ES6) are block-scoped. `const` forbids *re-assignment of the binding*, not mutation of the value it points to.

**Why it matters.** Scope and hoisting bugs from `var` are the root of many classic interview puzzles (the loop + `setTimeout` bug, accidental globals). Modern code uses `const` by default, `let` when you must reassign, and never `var`.

| | `var` | `let` | `const` |
|---|---|---|---|
| Scope | function (or global) | block `{}` | block `{}` |
| Hoisted? | yes, initialised to `undefined` | yes, but in the **TDZ** until declaration runs | same as `let` |
| Re-declare in same scope | allowed | SyntaxError | SyntaxError |
| Re-assign | yes | yes | no (binding is fixed) |
| Becomes `window` property (global scope) | yes | no | no |
| Needs initialiser | no | no | yes |

```javascript
console.log(a);        // undefined  (var is hoisted and initialised)
var a = 10;

console.log(b);        // ReferenceError: Cannot access 'b' before initialization
let b = 20;            // b is in the Temporal Dead Zone from block start to here

if (true) {
  var leaked = 'I escape the block';
  let scoped = 'I stay here';
}
console.log(leaked);   // "I escape the block"
console.log(typeof scoped); // "undefined"  (not in scope; typeof of an undeclared name is safe)

const order = { id: 1, status: 'New' };
order.status = 'Paid';          // OK - mutating the object
// order = {};                  // TypeError: Assignment to constant variable
Object.freeze(order);           // shallow freeze: order.status = 'X' now silently fails
                                // (throws TypeError in strict mode / modules)
```

**Temporal Dead Zone (TDZ).** The period between entering a scope and the line where a `let`/`const`/`class` is initialised. Accessing the name throws `ReferenceError`. The variable *is* hoisted (that is why an outer variable of the same name is shadowed), it is just uninitialised.

:::warn const is not immutability
`const items = []; items.push(1)` is perfectly legal. For real immutability use `Object.freeze` (shallow), `structuredClone` + copy-on-write, or a library like Immer. In React/Redux you *never* mutate state, but you still declare it with `const`.
:::

:::q Is `let` hoisted?
Yes. The declaration is hoisted to the top of its block, but unlike `var` it is not initialised, so it sits in the Temporal Dead Zone until execution reaches the declaration. Reading it earlier throws a `ReferenceError`. The proof that it *is* hoisted: an inner `let x` shadows an outer `x` for the whole block, even above the declaration line.
:::

### Data types

**Definition.** JavaScript is dynamically and weakly typed. There are **7 primitives** (immutable, compared by value) and **objects** (mutable, compared by reference).

| Primitive | Example | `typeof` |
|---|---|---|
| string | `'abc'` | `"string"` |
| number (IEEE-754 double) | `42`, `3.14`, `NaN`, `Infinity` | `"number"` |
| bigint | `9007199254740993n` | `"bigint"` |
| boolean | `true` | `"boolean"` |
| undefined | declared but unassigned | `"undefined"` |
| null | intentional "no value" | `"object"` (historic bug) |
| symbol | `Symbol('id')` | `"symbol"` |

Everything else (object, array, function, Date, Map, Set, RegExp, class instances) is an **object**. `typeof` of a function is `"function"` (still an object underneath), `typeof []` is `"object"`.

```javascript
typeof null;              // "object"  <- historic bug, never fixed
typeof NaN;               // "number"
typeof [];                // "object"  -> use Array.isArray(x)
typeof function () {};    // "function"
typeof undeclaredVar;     // "undefined" (no ReferenceError)
typeof 10n;               // "bigint"

// primitives: copied by value
let a = 5; let b = a; b = 6;       // a is still 5

// objects: copy of the *reference*
const o1 = { qty: 1 }; const o2 = o1; o2.qty = 99;
console.log(o1.qty);               // 99  (same object)

// strings are immutable
const s = 'abc'; s[0] = 'X';       // silently ignored (TypeError in strict mode)
```

:::tip Precise phrasing
Say "JavaScript passes everything **by value**, but for objects the value is a reference". That is the accurate answer to "is JS pass-by-reference?". Reassigning a parameter never affects the caller; mutating the object it points to does.
:::

**Numbers gotchas.** All numbers are 64-bit floats, so `0.1 + 0.2 !== 0.3` (it is `0.30000000000000004`). Compare with `Math.abs(a - b) < Number.EPSILON`, or work in integer cents for money (same advice as `decimal` vs `double` in C#). Integers are exact only up to `Number.MAX_SAFE_INTEGER` (2^53 - 1); beyond that use `BigInt`. This matters when an ASP.NET Core API returns a `long` id: JSON parse silently loses precision for ids above 2^53, so serialise big ids as strings.

### == vs ===, truthy and falsy, NaN

**`===`** (strict) compares type and value, no conversion. **`==`** (loose) applies the *Abstract Equality* algorithm: converts types (mostly to number) before comparing. Default to `===`; the one idiomatic use of `==` is `x == null` (true for both `null` and `undefined`).

**Falsy values (exactly 8):** `false`, `0`, `-0`, `0n`, `""`, `null`, `undefined`, `NaN`. **Everything else is truthy**, including `"0"`, `"false"`, `[]`, `{}`, `function(){}`, `new Boolean(false)`.

```javascript
0 == false          // true
'' == false         // true
null == undefined   // true
null == 0           // false   (null only loosely equals undefined)
null >= 0           // true    (relational ops convert null to 0, == does not)
'1' == 1            // true
[] == false         // true    ([] -> '' -> 0, false -> 0)
[] == ![]           // true    (![] is false; see above)
NaN == NaN          // false   (NaN is never equal to anything)
NaN === NaN         // false
Object.is(NaN, NaN) // true
Object.is(0, -0)    // false   (=== says true)

isNaN('abc')            // true   (coerces to number first -> misleading)
Number.isNaN('abc')     // false  (only true for the actual NaN value)
Number.isNaN(NaN)       // true
```

```javascript
// Truthiness in practice
const cart = [];
if (cart) { /* runs - empty array is truthy! */ }
if (cart.length) { /* correct check */ }

const qty = 0;
const shown = qty || 1;   // 1  - wrongly overrides a valid 0
const right = qty ?? 1;   // 0  - ?? only falls back on null/undefined
```

**Implicit coercion cheat sheet.** `+` with any string operand concatenates (`'5' + 2 = '52'`); `-`, `*`, `/` convert to number (`'5' - 2 = 3`); unary `+` converts to number (`+'42' = 42`, `+'abc' = NaN`). Objects convert via `valueOf()` then `toString()` (or `Symbol.toPrimitive`).

:::q Why does `typeof null` return "object"?
It is a bug from the first JavaScript implementation: values were tagged with a type bit and `null` (the NULL pointer, all zeros) matched the object tag. It was never fixed because it would break existing web code. Test for null with `x === null`.
:::

:::q How do you reliably check for an array, NaN, and null?
`Array.isArray(x)`, `Number.isNaN(x)` (or `Object.is(x, NaN)`), and `x === null`. `typeof` cannot distinguish arrays or null from plain objects, and the global `isNaN` coerces its argument first.
:::

## Functions

### Declarations, expressions and arrow functions

**Definition.** Functions are first-class objects: they can be assigned, passed as arguments, returned, and have properties. A function that takes or returns a function is a *higher-order function* (`map`, `filter`, `debounce`).

```javascript
// 1. Declaration - fully hoisted (callable before the line)
function total(price, qty = 1) { return price * qty; }

// 2. Expression - only the variable is hoisted (var -> undefined, let/const -> TDZ)
const discount = function (p) { return p * 0.9; };

// 3. Arrow - concise, lexical this, no own arguments, cannot be a constructor
const tax = (p, rate = 0.18) => p * rate;
const toDto = o => ({ id: o.id, total: o.total });   // wrap object literal in ()

// 4. IIFE - run once, private scope (pre-modules pattern)
(function () { const secret = 42; })();

// Rest parameters (real array) vs legacy arguments object
const sum = (...nums) => nums.reduce((a, b) => a + b, 0);
function legacy() { return arguments.length; }  // arguments: array-like, not in arrows
```

| | Regular function | Arrow function |
|---|---|---|
| `this` | dynamic - depends on *how it is called* | lexical - captured from the enclosing scope |
| `arguments` | yes | no (use rest params) |
| `new` (constructor) | yes | no - `TypeError` |
| `prototype` property | yes | no |
| Can be a method that needs its own `this` | yes | no (usually wrong choice) |
| `call/apply/bind` can change `this` | yes | no - `this` is fixed |
| Hoisting | declarations are fully hoisted | like any `const` |

:::warn Arrow functions as object methods or event handlers needing this
```javascript
const cart = {
  items: ['pen'],
  count: () => this.items.length,        // BUG: this is the outer scope (undefined / window)
  countOk() { return this.items.length; } // method shorthand: this = cart
};
```
Use arrows for callbacks inside methods (they inherit the method's `this`), use method syntax for the methods themselves.
:::

### this binding

**Rule of thumb: `this` is decided at the call site, not where the function is defined** (except arrows).

1. **`new Fn()`** - `this` is the freshly created object.
2. **Explicit** - `fn.call(obj)`, `fn.apply(obj)`, `fn.bind(obj)`.
3. **Implicit** - `obj.fn()` - `this` is `obj` (the thing left of the dot).
4. **Default** - plain `fn()` - `undefined` in strict mode/modules/classes, `globalThis` otherwise.
5. **Arrow** - ignores all of the above; uses the `this` of the surrounding code.

```javascript
const order = {
  id: 7,
  show() { console.log(this.id); },
  later() { setTimeout(function () { console.log(this.id); }, 0); },     // lost this
  laterArrow() { setTimeout(() => console.log(this.id), 0); }           // keeps this
};

order.show();                 // 7           (implicit)
const f = order.show;
f();                          // undefined   (default binding - method detached)
setTimeout(order.show, 0);    // undefined   (callback = detached call)
setTimeout(order.show.bind(order), 0); // 7  (explicit bind)
order.later();                // undefined   (regular fn inside timeout)
order.laterArrow();           // 7
```

In React class components this is why `this.handleClick = this.handleClick.bind(this)` (or a class-field arrow) was required. Function components and hooks removed the problem entirely.

### call, apply, bind

All three set `this` explicitly. `call(thisArg, a, b)` invokes immediately with args listed; `apply(thisArg, [a, b])` invokes immediately with an array; `bind(thisArg, a)` returns a **new function** with `this` (and optionally leading args) permanently fixed - used for partial application.

```javascript
function describe(currency, suffix) {
  return `${this.name} costs ${currency}${this.price}${suffix}`;
}
const product = { name: 'Keyboard', price: 49 };

describe.call(product, '$', ' only');      // "Keyboard costs $49 only"
describe.apply(product, ['$', ' only']);   // same, args as array
const inUsd = describe.bind(product, '$'); // partial application
inUsd(' today');                           // "Keyboard costs $49 today"

// Borrowing a method
Math.max.apply(null, [3, 9, 4]);           // 9  (modern: Math.max(...arr))
Array.prototype.slice.call(arguments);     // array-like -> real array

// bind polyfill (interview favourite)
Function.prototype.myBind = function (ctx, ...preset) {
  const fn = this;
  return function (...later) { return fn.apply(ctx, [...preset, ...later]); };
};
```

:::q What is the difference between call, apply and bind?
`call` and `apply` invoke the function immediately with a chosen `this`; they differ only in argument passing (comma-separated vs array). `bind` does not invoke - it returns a new function permanently bound to that `this` (and optional preset arguments). A bound function cannot be re-bound, and `new` on it ignores the bound `this`.
:::

## Scope, Hoisting & Closures

### Scope, scope chain and lexical environment

**Definition.** *Scope* is the region of code where a name is visible. JavaScript is **lexically scoped**: visibility is decided by where code is *written*, not where it is called. Each execution context has a **Lexical Environment** = an environment record (the variables declared here) + a reference to the **outer** environment. Resolving a name walks this chain outward - the **scope chain** - until found, or `ReferenceError` at the global environment.

```text
global { appName }
  └─ function checkout() { taxRate }
        └─ block { let discount }      <- lookup of `appName` walks up: block -> function -> global
```

Four kinds: **global**, **function**, **block** (`let`/`const`/`class` only), and **module** (top-level of an ES module is not global).

```javascript
const appName = 'Shop';                 // global / module scope
function checkout() {
  const taxRate = 0.18;                 // function scope
  if (taxRate > 0) {
    let discount = 5;                   // block scope
    console.log(appName, taxRate, discount); // all three visible via the chain
  }
  // console.log(discount);             // ReferenceError - block ended
}

// Shadowing: inner name hides outer one
let x = 'outer';
{ let x = 'inner'; console.log(x); }    // "inner"
console.log(x);                         // "outer"

// Accidental global (non-strict mode only) - always use 'use strict' / modules
function oops() { leaked = 1; }         // creates global in sloppy mode; ReferenceError in strict
```

### Hoisting

**Definition.** Before running a scope, the engine registers its declarations (creation phase). The effect is that names exist before their line is reached - but with different initial states.

| Declaration | Hoisted? | Value before its line |
|---|---|---|
| `function f(){}` | yes, **with body** | callable |
| `var x` | yes (declaration only) | `undefined` |
| `let` / `const` / `class` | yes | **TDZ** - ReferenceError |
| function expression / arrow in `var` | variable only | `undefined` -> "x is not a function" |

```javascript
console.log(typeof getTotal);   // "function"
console.log(typeof getTax);     // "undefined"
getTotal();                     // works
// getTax();                    // TypeError: getTax is not a function

function getTotal() { return 1; }
var getTax = function () { return 2; };

// Declaration beats var of the same name; assignment later overwrites it
console.log(typeof dup);        // "function"
var dup = 5;
function dup() {}
console.log(typeof dup);        // "number"
```

:::q What is hoisting? Does it physically move code?
No code moves. During the creation phase the engine allocates bindings for declarations in the scope: functions get their full definition, `var` gets `undefined`, and `let`/`const`/`class` are allocated but left uninitialised (TDZ). Hoisting is just a description of that observable behaviour.
:::

### Closures

**Definition.** A **closure** is a function bundled with a reference to the lexical environment where it was created. The function keeps access to those outer variables *even after the outer function has returned*. The variables live as long as any closure references them.

**Why it matters.** Closures give you private state, factories, memoization, debounce/throttle, React hooks (a hook's value is closed over by each render's function), event handlers and the module pattern.

```javascript
function makeCounter(start = 0) {
  let count = start;                 // private - no way to reach it from outside
  return {
    increment: () => ++count,
    decrement: () => --count,
    value: () => count
  };
}
const c1 = makeCounter(), c2 = makeCounter(10);
c1.increment(); c1.increment();
console.log(c1.value(), c2.value());   // 2 10   (each closure has its own count)
console.log(c1.count);                 // undefined - encapsulated
```

#### The classic loop bug

```javascript
for (var i = 0; i < 3; i++) {
  setTimeout(() => console.log(i), 0);
}
// Output: 3 3 3  - var is function-scoped: ONE shared i, already 3 when timers fire
```

Fixes:

```javascript
// Fix 1 (best): let creates a fresh binding per iteration
for (let i = 0; i < 3; i++) setTimeout(() => console.log(i), 0);   // 0 1 2

// Fix 2: IIFE captures the current value (pre-ES6 solution)
for (var j = 0; j < 3; j++) {
  (function (k) { setTimeout(() => console.log(k), 0); })(j);
}

// Fix 3: pass the value as the setTimeout argument (or use bind)
for (var m = 0; m < 3; m++) setTimeout(console.log, 0, m);          // 0 1 2
```

#### Utility closures: memoize, once, debounce, throttle

```javascript
// memoize - cache results by arguments (pure functions only)
function memoize(fn) {
  const cache = new Map();
  return function (...args) {
    const key = JSON.stringify(args);          // fine for primitives; costly for big args
    if (cache.has(key)) return cache.get(key);
    const result = fn.apply(this, args);
    cache.set(key, result);
    return result;
  };
}
const slowFib = n => (n < 2 ? n : fastFib(n - 1) + fastFib(n - 2));
const fastFib = memoize(slowFib);
fastFib(40);                                   // instant instead of ~300M calls

// once - run the function a single time, return the first result afterwards
function once(fn) {
  let called = false, result;
  return function (...args) {
    if (!called) { called = true; result = fn.apply(this, args); }
    return result;
  };
}
const initPayment = once(() => console.log('SDK loaded'));
initPayment(); initPayment();                  // prints once

// debounce - run AFTER the user stops triggering for `delay` ms
function debounce(fn, delay = 300) {
  let timerId;
  return function (...args) {
    clearTimeout(timerId);
    timerId = setTimeout(() => fn.apply(this, args), delay);
  };
}

// throttle - run at most once per `interval` ms (leading edge)
function throttle(fn, interval = 300) {
  let last = 0;
  return function (...args) {
    const now = Date.now();
    if (now - last >= interval) { last = now; fn.apply(this, args); }
  };
}

searchBox.addEventListener('input', debounce(e => callSearchApi(e.target.value), 400));
window.addEventListener('scroll', throttle(updateStickyHeader, 100));
```

| | Debounce | Throttle |
|---|---|---|
| Fires | once, after calls *stop* for N ms | at a steady rate, at most once per N ms |
| Typical use | search-as-you-type, auto-save, window-resize end | scroll, mousemove, drag, rate-limited button |
| Burst of 100 events over 1 s (N=300) | 1 call (at the end) | about 3 calls |
| State kept | timer id | timestamp (or timer) |

:::example Debounced search against an ASP.NET Core endpoint
Typing "laptop" fires 6 `input` events. Without debounce that is 6 requests to `GET /api/products?search=...`, and the responses may return out of order so an old result overwrites a newer one. With `debounce(…, 400)` only one request leaves after the user pauses. Pair it with `AbortController` to cancel the previous in-flight request (see the Fetch section).
:::

:::warn Closure memory leaks
A closure keeps its *whole* captured scope alive. A long-lived listener that closes over a large array or a DOM node prevents garbage collection. Always `removeEventListener`, clear intervals/timeouts, and in React return a cleanup function from `useEffect`.
:::

:::q What is a closure? Give a practical use.
A closure is a function together with the lexical environment it was defined in, so it can still read and write those outer variables after the outer function has finished. Practical uses: private state (a counter or a cached token), function factories, memoization, debounce/throttle, and React hooks - each render's handler closes over that render's props and state, which is also the source of "stale closure" bugs.
:::

:::q Why does the var + setTimeout loop print 3 3 3 and how do you fix it?
`var` has one function-scoped `i`. All three callbacks close over the same variable and run after the loop has finished, when `i` is 3. Declaring it with `let` gives each iteration its own binding, so the callbacks print 0 1 2. Pre-ES6 you wrapped the body in an IIFE to capture the current value.
:::
