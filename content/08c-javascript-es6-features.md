## ES6+ Essentials

### Destructuring, spread, rest and template literals

**Definition.** *Destructuring* unpacks values from arrays/objects into variables. *Spread* (`...x` in a call/literal) expands an iterable or object. *Rest* (`...x` in a parameter or destructuring pattern) collects the remainder. They use the same `...` token; position decides the meaning. *Template literals* are back-tick strings with `${expression}` interpolation and multi-line support.

```javascript
const order = { id: 7, customer: { name: 'Asha', city: 'Pune' }, items: ['pen', 'book', 'bag'] };

// Object destructuring: rename, default, nested
const { id, status = 'New', customer: { name: customerName } } = order;

// Array destructuring: skip, rest, swap
const [first, , third, ...others] = ['a', 'b', 'c', 'd', 'e'];   // others = ['d','e']
let x = 1, y = 2;  [x, y] = [y, x];                              // swap

// In function parameters (typical for React props and options objects)
function createOrder({ customerId, items = [], note = '' } = {}) { /* ... */ }
const [state, setState] = useState(0);                           // array destructuring in React

// Spread
const all = [...order.items, 'pen'];                             // copy + add
const updated = { ...order, status: 'Paid' };                    // shallow copy + override
Math.max(...[3, 9, 4]);                                          // spread into arguments

// Rest
const sum = (...nums) => nums.reduce((a, b) => a + b, 0);
const { id: _omit, ...withoutId } = order;                       // omit a property

// Template literals
const msg = `Order #${id} for ${customerName}: ${order.items.length} item(s)
  total = ${(1234.5).toFixed(2)}`;
```

:::warn Spread is shallow
`{ ...order }` copies the top level only; `copy.customer` is still the same object as `order.customer`. Mutating it changes both. For nested updates spread each level (see Immutability) or use `structuredClone`.
:::

### Modules (ESM) vs CommonJS

**Definition.** ES Modules (`import`/`export`) are the language-standard module system: one file = one module with its own scope, strict mode, and explicit exports. CommonJS (`require`/`module.exports`) is Node's original system.

```javascript
// pricing.js
export const TAX = 0.18;                                  // named exports
export function total(items) { return items.reduce((s, i) => s + i.price, 0) * (1 + TAX); }
export default class PricingService { /* ... */ }         // one default per module

// app.js
import PricingService, { TAX, total as calcTotal } from './pricing.js';
import * as pricing from './pricing.js';                  // namespace object
const { default: Chart } = await import('./chart.js');    // dynamic import -> separate bundle chunk

// export { a, b as c };  export * from './other.js';     // re-exports (barrel files)
```

| | ES Modules | CommonJS |
|---|---|---|
| Syntax | `import` / `export` | `require()` / `module.exports` |
| Loading | static, analysed before running (async) | dynamic, synchronous at runtime |
| Exports | **live bindings** (read-only views) | **copies** of values at require time |
| Tree-shaking | yes (static structure) | hard |
| Top-level `await` | yes | no |
| `this` at top level | `undefined` | `module.exports` |
| Browser | native (`<script type="module">`) | needs a bundler |
| Node | `.mjs` or `"type": "module"` | `.cjs` / default |

:::tip Why tree-shaking and code-splitting need ESM
Bundlers (Vite, esbuild, webpack) can drop unused exports and split on `import()` boundaries only because the import graph is static. That is how `React.lazy(() => import('./Admin'))` and Angular `loadComponent` produce lazy chunks.
:::

### Classes

**Definition.** `class` is syntax over prototypes (`typeof Product === 'function'`). It adds constructors, `extends`/`super`, getters/setters, static members, and truly private `#` members. Class bodies run in strict mode and class declarations are in the TDZ (not usable before the line).

```javascript
class Product {
  static count = 0;                        // static field (on the class itself)
  #cost;                                   // private field: invisible outside the class

  constructor(name, price, cost) {
    this.name = name;
    this.price = price;
    this.#cost = cost;
    Product.count++;
  }
  get margin() { return this.price - this.#cost; }          // accessor
  #audit() { console.log('audit', this.name); }             // private method
  describe() { this.#audit(); return `${this.name}: ${this.price}`; }
  static fromDto(dto) { return new Product(dto.name, dto.price, dto.cost); }
}

class DigitalProduct extends Product {
  constructor(name, price, cost, downloadUrl) {
    super(name, price, cost);              // MUST call super() before touching this
    this.downloadUrl = downloadUrl;
  }
  describe() { return `${super.describe()} [digital]`; }    // override + call parent
}

const p = new DigitalProduct('E-book', 10, 2, '/dl/1');
p.margin;            // 8
// p.#cost;          // SyntaxError - private
p instanceof Product // true
```

Notes: `#private` is enforced by the engine (unlike the `_name` convention or TypeScript's `private`, which is compile-time only). Methods live on the prototype (shared); class-field arrow functions are created per instance. Mixins and composition are often preferred to deep hierarchies.

:::q Are JavaScript classes real classes like in C#?
No. They are syntactic sugar over prototype-based inheritance. `class B extends A` wires `B.prototype`'s prototype to `A.prototype`. There are no interfaces, no abstract classes (in plain JS), and instances are open objects (properties can be added). That is why TypeScript adds `interface`, `abstract`, access modifiers and types on top.
:::

### Array methods

```javascript
const orders = [
  { id: 1, customer: 'Asha', total: 120, status: 'Paid',    items: ['pen', 'book'] },
  { id: 2, customer: 'Ravi', total: 40,  status: 'Pending', items: ['bag'] },
  { id: 3, customer: 'Asha', total: 300, status: 'Paid',    items: ['lamp', 'desk'] }
];

orders.map(o => o.total);                                   // [120, 40, 300]   transform 1:1
orders.filter(o => o.status === 'Paid');                    // 2 orders          keep matching
orders.find(o => o.id === 2);                               // object | undefined (first match)
orders.findIndex(o => o.id === 9);                          // -1
orders.some(o => o.total > 200);                            // true   (any)
orders.every(o => o.total > 100);                           // false  (all)
orders.flatMap(o => o.items);                               // ['pen','book','bag','lamp','desk']
orders.reduce((sum, o) => sum + o.total, 0);                // 460

// reduce: group by customer -> { Asha: [..], Ravi: [..] }
const byCustomer = orders.reduce((acc, o) => {
  (acc[o.customer] ??= []).push(o);
  return acc;
}, {});

// chain: total of paid orders, sorted desc
const top = orders.filter(o => o.status === 'Paid')
                  .toSorted((a, b) => b.total - a.total)    // non-mutating (ES2023)
                  .map(o => o.id);                          // [3, 1]

[10, 1, 2].sort();                  // [1, 10, 2]  default sort = string order! pass comparer
[10, 1, 2].sort((a, b) => a - b);   // [1, 2, 10]  (sort MUTATES the array)
[1, 2, 3].at(-1);                   // 3
Object.entries({ a: 1 });           // [['a', 1]]    Object.fromEntries(pairs) reverses it
```

| Method | Returns | Mutates? |
|---|---|---|
| `map`, `filter`, `flatMap`, `slice`, `concat`, `toSorted`, `toReversed`, `with` | new array | no |
| `find`, `at` | element or `undefined` | no |
| `some`, `every`, `includes` | boolean | no |
| `reduce` | any value | no |
| `push`, `pop`, `shift`, `unshift`, `splice`, `sort`, `reverse` | varies | **yes** |
| `forEach` | `undefined` (cannot break; ignores async) | no |

`Object.groupBy(items, fn)` and `Map.groupBy` (ES2024) replace the reduce-grouping idiom; check browser/Node support (Node 21+) before relying on them. `reduce` with no initial value on an empty array throws a `TypeError`: always pass the seed.

### Map, Set, WeakMap, WeakSet

| | `Object` | `Map` | `Set` | `WeakMap` |
|---|---|---|---|---|
| Keys | strings / symbols | **any value**, objects included | unique values | **objects only**, held weakly |
| Order | mostly insertion (numeric keys first) | insertion, guaranteed | insertion | n/a |
| Size | manual | `.size` | `.size` | none |
| Iterable | via `Object.keys` | yes | yes | **no** |
| Prevents GC of key | yes | yes | yes | **no** |

```javascript
const unique = [...new Set([1, 2, 2, 3])];                 // [1, 2, 3]   dedupe
const seen = new Set(); const dup = ids.find(id => seen.has(id) || !seen.add(id));

const stockByProduct = new Map([[101, 5], [102, 0]]);
stockByProduct.set(103, 12).get(101);                       // 5
for (const [id, qty] of stockByProduct) { /* ... */ }

// WeakMap: attach metadata to objects without leaking them
const metadata = new WeakMap();
function track(el) { metadata.set(el, { clicks: 0 }); }     // entry vanishes when el is GC'd
```

Use `Map` for dictionaries with frequent add/remove or non-string keys (the equivalent of `Dictionary<TKey, TValue>`), `Set` for uniqueness and O(1) membership (`HashSet<T>`), `WeakMap` for private data and caches keyed by objects.

### Optional chaining and nullish coalescing

```javascript
const city = order?.customer?.address?.city;      // undefined if any link is null/undefined
const first = order.items?.[0];                   // optional index
const result = repo.find?.(id);                   // optional call

const qty = input.qty ?? 1;                       // default ONLY for null/undefined
const price = input.price || 10;                  // default for ANY falsy (0, '', NaN, false)
settings.theme ??= 'light';                       // logical assignment: assign if nullish
settings.retries ||= 3;   settings.debug &&= false;
```

```javascript
// Result when x is...      0      ''     null   false
//   x || 5                 5      5      5      5      (any falsy -> default)
//   x ?? 5                 0      ''     5      false  (only null/undefined -> default)
```

:::warn || as a default hides valid values
`const pageSize = query.pageSize || 20` turns an explicit `0` into 20, and `const flag = cfg.enabled || true` can never be `false`. Use `??`. Optional chaining short-circuits the *whole* chain: `a?.b.c` does not throw when `a` is null, but does throw if `a.b` is null.
:::

### Immutability patterns

**Why.** React, Redux and Angular's `OnPush`/signals detect change by *reference*. If you mutate and re-set the same object, nothing re-renders. Immutable updates also make time-travel debugging and memoisation reliable.

```javascript
const state = { user: { name: 'Asha', tags: ['vip'] }, cart: [{ id: 1, qty: 1 }] };

// Object: spread each level on the path you change
const s1 = { ...state, user: { ...state.user, name: 'Asha K' } };

// Array: add / remove / update without mutation
const added   = [...state.cart, { id: 2, qty: 1 }];
const removed = state.cart.filter(l => l.id !== 1);
const updated = state.cart.map(l => (l.id === 1 ? { ...l, qty: l.qty + 1 } : l));
const sorted  = state.cart.toSorted((a, b) => a.qty - b.qty);   // not .sort()
const replaced = state.cart.with(0, { id: 1, qty: 5 });         // ES2023

Object.freeze(state);                       // shallow, throws in strict mode if mutated later
// Deeply nested? Use Immer: produce(state, draft => { draft.user.tags.push('new'); })
```

## Objects: Prototypes and Copying

### Prototypes and the prototype chain

**Definition.** Every object has an internal `[[Prototype]]` link (read via `Object.getPrototypeOf(obj)`, historically `obj.__proto__`) to another object. Property lookup walks this **prototype chain** until found or `null`. Functions have a `prototype` property: the object that becomes the `[[Prototype]]` of instances created with `new`.

```javascript
function Animal(name) { this.name = name; }
Animal.prototype.speak = function () { return `${this.name} makes a sound`; };

function Dog(name) { Animal.call(this, name); }             // "super constructor"
Dog.prototype = Object.create(Animal.prototype);            // inherit
Dog.prototype.constructor = Dog;
Dog.prototype.speak = function () { return `${this.name} barks`; };

const d = new Dog('Rex');
d.speak();                                  // "Rex barks"  (found on Dog.prototype)
Object.getPrototypeOf(d) === Dog.prototype; // true
// chain: d -> Dog.prototype -> Animal.prototype -> Object.prototype -> null
d.hasOwnProperty('name');                   // true  (own);  Object.hasOwn(d, 'name') preferred
d.toString();                               // inherited from Object.prototype
'speak' in d;                               // true  (own + inherited)

const proto = { greet() { return 'hi ' + this.name; } };
const o = Object.create(proto); o.name = 'x';   // direct prototype inheritance
```

What `new Fn(args)` does: (1) creates an empty object, (2) links its `[[Prototype]]` to `Fn.prototype`, (3) calls `Fn` with `this` = that object, (4) returns it (unless `Fn` returns another object). Writing to a property always creates an *own* property (it shadows, never edits the prototype's), which is why methods go on the prototype and data on the instance.

:::q Explain prototypal inheritance and how it differs from class inheritance in C#.
In C# a class is a compile-time blueprint and instances are copies shaped by it. In JavaScript objects inherit directly from other objects at run time via the prototype chain: if a property isn't on the object, the engine looks at its prototype, then that object's prototype, up to `Object.prototype`. `class`/`extends` just sets those links up for you. Mutating a prototype affects all existing linked objects.
:::

### Shallow vs deep copy

**Definition.** A *shallow copy* duplicates the top-level container; nested objects are still shared. A *deep copy* recursively duplicates everything.

| Technique | Depth | Notes |
|---|---|---|
| `{ ...o }`, `Object.assign({}, o)`, `[...a]`, `a.slice()` | shallow | nested references shared |
| `JSON.parse(JSON.stringify(o))` | deep, **lossy** | drops `undefined`/functions/symbols, `Date` -> string, `Map`/`Set` -> `{}`, `NaN` -> `null`, throws on circular refs and BigInt |
| `structuredClone(o)` | deep, correct for most data | handles `Date`, `Map`, `Set`, `RegExp`, typed arrays, circular refs; **throws** on functions/DOM nodes; drops prototypes (class instances become plain objects) |
| Hand-written recursion / lodash `cloneDeep` | deep | for custom classes and functions |

```javascript
const src = { id: 1, when: new Date(), tags: new Set(['a']), meta: { n: 1 } };

const shallow = { ...src };
shallow.meta.n = 99;
console.log(src.meta.n);                     // 99  - shared!

const deep = structuredClone(src);
deep.meta.n = 5;
console.log(src.meta.n, deep.when instanceof Date);   // 99 true

const lossy = JSON.parse(JSON.stringify(src));
console.log(typeof lossy.when, lossy.tags);           // "string" {}

// structuredClone({ fn() {} });   // DataCloneError: function could not be cloned
```

:::q How would you deep clone an object?
Use `structuredClone(obj)` - built in, handles dates, maps, sets and circular references. `JSON.parse(JSON.stringify())` is a quick hack that loses `undefined`, functions, dates, maps and sets. For class instances with methods or functions use lodash `cloneDeep` or a custom clone. In React/Redux the better answer is "don't deep clone: copy-on-write only the path that changes".
:::
