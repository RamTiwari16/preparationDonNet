### var, let, const

**In simple words:** These three words create variables. `var` is the old way and is visible in the whole function. `let` and `const` are visible only inside the `{ }` block where you write them. `const` means you cannot point the name to a new value, but you can still change the inside of an object it holds.

**Real-life example:** `const` is like a house address written on a card. You cannot change the address, but you can still move the furniture inside the house.

**Interview question:** What is the difference between `var`, `let` and `const`?

**Simple answer:** `var` is function-scoped and gets `undefined` before its line runs. `let` and `const` are block-scoped and throw an error if you use them before their line (the Temporal Dead Zone). I use `const` by default, `let` only when I must reassign, and never `var`.

```javascript
const order = { status: 'New' };
order.status = 'Paid'; // OK: changing the object
// order = {};         // TypeError: cannot reassign a const
```

### Data types

**In simple words:** JavaScript has 7 *primitive* types (simple values): string, number, bigint, boolean, undefined, null and symbol. Everything else is an object, including arrays and functions. Primitives are copied by value. For objects, the variable holds a reference (an address to the object).

**Real-life example:** A primitive is like handing someone a photocopy of a note. An object is like giving someone your locker number — both of you now open the same locker.

**Interview question:** What are the data types in JavaScript, and is JavaScript pass-by-reference?

**Simple answer:** There are seven primitives plus objects. JavaScript always passes by value, but for objects that value is a reference. So if a function changes the object's properties, the caller sees it, but if it assigns a new object to the parameter, the caller does not. Also note `typeof null` is `"object"`, which is an old bug.

### == vs ===, truthy and falsy, NaN

**In simple words:** `===` checks type and value with no conversion. `==` first converts types, which gives surprising results. *Falsy* values act like `false` in an `if`: `false`, `0`, `-0`, `0n`, `""`, `null`, `undefined` and `NaN`. Everything else is *truthy*, even `[]` and `"0"`. `NaN` (Not a Number) is not equal to anything, even itself.

**Real-life example:** `===` is a security guard who checks both your face and your ID card. `==` is a guard who only checks that you look roughly similar.

**Interview question:** Why should you prefer `===` over `==`?

**Simple answer:** `==` converts types first, so `0 == ''` and `'1' == 1` are both true, which causes bugs. `===` compares type and value exactly. The only common use of `==` is `x == null`, which checks for both `null` and `undefined`. To check for NaN, I use `Number.isNaN(x)`.

```javascript
'1' == 1          // true  (converted)
'1' === 1         // false
NaN === NaN       // false
Number.isNaN(NaN) // true
```

### Declarations, expressions and arrow functions

**In simple words:** You can write a function in three main ways. A *declaration* (`function total() {}`) can be called even before its line. A *function expression* stores a function in a variable. An *arrow function* (`() => {}`) is shorter and does not have its own `this`; it uses the `this` of the code around it.

**Real-life example:** A regular function is like a phone that rings for whoever is holding it. An arrow function is like a phone fixed to one office desk — it always belongs to that office.

**Interview question:** What is the difference between a regular function and an arrow function?

**Simple answer:** Arrow functions take `this` from the surrounding code, have no `arguments` object, and cannot be used with `new`. Regular functions get `this` from how they are called. I use arrows for callbacks, and normal method syntax for object methods that need their own `this`.

```javascript
function add(a, b) { return a + b; }      // declaration
const tax = (price) => price * 0.18;      // arrow
```

### this binding

**In simple words:** `this` is the object a function is working with. For normal functions, `this` is decided when the function is called, not where it is written. `obj.fn()` gives `this = obj`. A plain `fn()` call gives `undefined` in strict mode. Arrow functions do not have their own `this`; they use the outer one.

**Real-life example:** The word "here" depends on where the speaker is standing at that moment. If you copy a sentence with "here" to another place, its meaning changes.

**Interview question:** How is the value of `this` decided in JavaScript?

**Simple answer:** There are four rules, in order: `new` creates a new object as `this`; `call`, `apply` or `bind` set it explicitly; `obj.method()` uses `obj`; a plain call gets `undefined` in strict mode. Arrow functions ignore these rules and use the surrounding `this`. That is why passing `obj.method` as a callback often loses `this`.

```javascript
const order = { id: 7, show() { console.log(this.id); } };
order.show();            // 7
const f = order.show;
f();                     // "this" is lost: undefined (or error in strict mode)
```

### call, apply, bind

**In simple words:** All three let you choose what `this` is for a function. `call` runs the function now and takes arguments one by one. `apply` runs it now and takes arguments as an array. `bind` does not run it; it returns a new function with `this` fixed forever.

**Real-life example:** `call` and `apply` are like giving instructions to a driver for one trip right now. `bind` is like hiring a driver who will always drive for your company.

**Interview question:** What is the difference between `call`, `apply` and `bind`?

**Simple answer:** `call` and `apply` both run the function immediately with a chosen `this`. The only difference is that `call` takes a list of arguments and `apply` takes an array. `bind` returns a new function with `this` (and optionally some arguments) fixed, so you can call it later.

```javascript
function hi(greet) { return `${greet}, ${this.name}`; }
const user = { name: 'Asha' };
hi.call(user, 'Hello');      // runs now
hi.apply(user, ['Hello']);   // runs now, array of args
const later = hi.bind(user); // new function, run later
```

### Scope, scope chain and lexical environment

**In simple words:** *Scope* is the area of code where a variable can be seen. JavaScript uses *lexical* scope: what you can see depends on where the code is written. When you use a name, JavaScript looks in the current block, then the outer function, then further out, up to the global level. This path is the *scope chain*.

**Real-life example:** If you need a pen, you first check your desk, then your office, then the building store room. You stop at the first place you find one.

**Interview question:** What is the scope chain?

**Simple answer:** Each scope keeps its own variables plus a link to the outer scope where it was written. When code reads a variable, the engine searches the current scope, then follows the links outward until it finds it, or throws a `ReferenceError`. JavaScript has global, function, block and module scope.

### Hoisting

**In simple words:** Before a scope runs, JavaScript first registers all the declarations in it. So names exist before their line. Function declarations are ready to call. `var` variables exist but are `undefined`. `let`, `const` and `class` exist but you cannot touch them until their line runs.

**Real-life example:** Before a meeting starts, the organiser writes all attendee names on the list. Some people are already seated (functions), some have a chair but are not there yet (`var`), and some must not be called until they arrive (`let`/`const`).

**Interview question:** What is hoisting? Does JavaScript move code to the top?

**Simple answer:** No code moves. In the creation phase, the engine reserves names for declarations. Functions are hoisted with their body, `var` is set to `undefined`, and `let`/`const` stay in the Temporal Dead Zone until their line runs, so reading them early throws a `ReferenceError`.

```javascript
sayHi();               // works: function is hoisted
console.log(a);        // undefined
var a = 1;
function sayHi() { console.log('hi'); }
```

### Closures

**In simple words:** A *closure* is a function that remembers the variables from the place where it was created. It can still use them after the outer function has finished. This gives you private data, factories, debounce and the way React hooks work.

**Real-life example:** A child leaves home for school but still carries a house key. Home is closed, but the child can still open the door with the key they took.

**Interview question:** What is a closure and where would you use it?

**Simple answer:** A closure is a function together with the outer variables it was created with. It keeps access to them even after the outer function returns. I use it for private state like a counter, for debounce and throttle, and it is how event handlers in React remember props and state.

```javascript
function makeCounter() {
  let count = 0;                 // private
  return () => ++count;
}
const next = makeCounter();
next(); next();                  // 2
```

### Callbacks and callback hell

**In simple words:** A *callback* is a function you pass to another function so it can call you back later, for example when data arrives. JavaScript runs on one thread, so slow work uses callbacks instead of waiting. When many async steps nest inside each other, the code becomes a deep "pyramid" that is hard to read. This is *callback hell*.

**Real-life example:** You leave your phone number at a restaurant so they can call you when your table is ready. If every step needs another phone call inside the last one, it gets messy fast.

**Interview question:** What is callback hell and how do you avoid it?

**Simple answer:** Callback hell is deeply nested callbacks where each step depends on the previous one. Error handling is repeated at every level and the code is hard to follow. Promises flatten the chain with one `catch`, and `async/await` makes it look like normal step-by-step code with `try/catch`.

### Promises

**In simple words:** A *Promise* is an object that stands for a result that will come later. It is either *pending*, *fulfilled* (success with a value) or *rejected* (failed with an error). Once settled, it never changes. You use `.then` for success and `.catch` for errors.

**Real-life example:** When you order food, you get a token number. Later the token gives you either your meal or a message that the dish is not available.

**Interview question:** What is the difference between `Promise.all` and `Promise.allSettled`?

**Simple answer:** `Promise.all` waits for all promises and fails as soon as one fails. I use it when I need every result. `Promise.allSettled` never fails; it reports each result as fulfilled or rejected, so it suits dashboards where partial data is fine. Neither one cancels the other requests.

```javascript
const [products, categories] = await Promise.all([
  fetch('/api/products').then(r => r.json()),
  fetch('/api/categories').then(r => r.json())
]);
```

### async / await

**In simple words:** `async` makes a function always return a Promise. `await` pauses that function until a Promise finishes, then continues. It does not block the thread; other code keeps running. It lets you write async code that reads like normal step-by-step code, with ordinary `try/catch`.

**Real-life example:** In a bank, you take a token and sit down. The counter serves other people while you wait, and you continue when your number is called.

**Interview question:** How do you run three independent API calls in parallel with `async/await`?

**Simple answer:** If I write three `await`s one after another, they run one by one. For independent calls I start them all and wait together with `Promise.all`. Also, `fetch` does not fail on 404 or 500, so I check `res.ok` myself.

```javascript
// one by one: slow
const a = await getA();
const b = await getB();
// parallel: fast
const [a2, b2] = await Promise.all([getA(), getB()]);
```

### The event loop

**In simple words:** JavaScript has one thread and one *call stack* (the list of functions running now). Slow work like timers and network calls is handed to the browser. When it finishes, its callback waits in a queue. The *event loop* moves the next callback onto the stack only when the stack is empty. Promise callbacks (*microtasks*) always run before timer callbacks (*macrotasks*).

**Real-life example:** A single cashier serves one customer at a time. Priority customers (promises) are served before the normal queue (timers), but only after the current customer is finished.

**Interview question:** Why does a Promise callback run before `setTimeout(fn, 0)`?

**Simple answer:** After each task, the event loop empties the whole microtask queue before taking the next macrotask. Promise `.then` and `await` continuations are microtasks. `setTimeout` is a macrotask. So promise callbacks always run first, even if the timer delay is zero.

```javascript
console.log('1');
setTimeout(() => console.log('2'), 0);
Promise.resolve().then(() => console.log('3'));
console.log('4');
// Output: 1 4 3 2
```

### Event bubbling, capturing and delegation

**In simple words:** When you click an element, the event travels in three phases. First *capturing* goes down from the window to the element. Then the *target* phase runs on the element. Then *bubbling* goes back up through the parents. *Event delegation* means putting one listener on a parent and checking which child was clicked.

**Real-life example:** A complaint in a school goes from the student up to the teacher, then the principal. Instead of a helper in every classroom, the principal's office can handle requests from all rooms.

**Interview question:** What is event delegation and why use it?

**Simple answer:** You add one listener to a parent element and use `event.target` to find which child triggered it. It saves memory and works for elements added later. It depends on bubbling, so it does not work for events that do not bubble, like `focus`.

```javascript
list.addEventListener('click', e => {
  const btn = e.target.closest('button.cancel');
  if (btn) cancelOrder(btn.closest('li').dataset.id);
});
```

### DOM manipulation basics

**In simple words:** The *DOM* (Document Object Model) is the browser's live tree of objects for the page. JavaScript can find elements, change their text, add classes and create new elements. Frameworks like React and Angular do most of this for you, but you should know the basics.

**Real-life example:** The DOM is like the floor plan of a shop. JavaScript is the staff who move shelves, change price labels and add new items.

**Interview question:** What is the difference between `textContent` and `innerHTML`?

**Simple answer:** `textContent` sets plain text, so any HTML is shown as text and is safe. `innerHTML` parses the string as HTML, so data from a user or API can run a script attack (XSS). I use `textContent` for data, and sanitize if I really need HTML.

```javascript
const el = document.querySelector('#total');
el.textContent = 'Total: 120';   // safe
el.classList.add('highlight');
```

### Destructuring, spread, rest and template literals

**In simple words:** *Destructuring* takes values out of an object or array into variables in one line. *Spread* (`...`) expands an array or object into another one. *Rest* (also `...`) collects "the remaining" items into one variable. *Template literals* are back-tick strings where you can put values with `${ }`.

**Real-life example:** Destructuring is like unpacking a delivery box and placing each item straight on its shelf. Spread is like pouring one box into a bigger box.

**Interview question:** What is the difference between spread and rest?

**Simple answer:** They use the same `...` but in different places. Spread is used in a call or literal to expand values out. Rest is used in parameters or destructuring to collect the remaining values in. Remember that spread makes only a shallow copy.

```javascript
const { id, status = 'New' } = order;          // destructuring
const updated = { ...order, status: 'Paid' };  // spread
const sum = (...nums) => nums.reduce((a, b) => a + b, 0); // rest
const msg = `Order #${id} is ${status}`;       // template literal
```

### Modules (ESM) vs CommonJS

**In simple words:** A *module* is a file with its own scope that shares only what it exports. ES Modules (ESM) use `import` and `export` and are the standard in browsers and modern Node. CommonJS uses `require` and `module.exports` and is Node's older system. ESM imports are known before the code runs, so bundlers can remove unused code.

**Real-life example:** Each module is like a shop in a mall. You can buy only the items a shop puts on its counter (exports), not things in its back room.

**Interview question:** What are the main differences between ES Modules and CommonJS?

**Simple answer:** ESM is static and analysed before running, supports top-level `await`, and allows *tree-shaking* (removing unused exports). CommonJS loads synchronously at runtime with `require`. Lazy loading with `import()` in React or Angular also depends on ESM.

```javascript
// pricing.js
export const TAX = 0.18;
export default function total(p) { return p * (1 + TAX); }
// app.js
import total, { TAX } from './pricing.js';
```

### Classes

**In simple words:** `class` gives a clean way to write constructors, methods, inheritance and private fields. But it is built on top of JavaScript prototypes; it is not a separate class system like in C#. Fields starting with `#` are truly private and the engine blocks outside access.

**Real-life example:** A class is like a printed form template at a bank. The form is easy to fill in, but behind it the bank still uses the same old filing system (prototypes).

**Interview question:** Are JavaScript classes the same as C# classes?

**Simple answer:** No. They are mostly a nicer syntax over prototype-based inheritance. `extends` links prototypes for you. Plain JavaScript has no interfaces or abstract classes, which is one reason TypeScript adds them. `#private` fields are enforced at runtime, unlike TypeScript's `private`.

```javascript
class Product {
  #cost;
  constructor(name, cost) { this.name = name; this.#cost = cost; }
}
class Digital extends Product { }
```

### Array methods

**In simple words:** Arrays have built-in methods to work with lists. `map` changes each item, `filter` keeps matching items, `find` returns the first match, and `reduce` combines all items into one value. Some methods return a new array, but `sort`, `push` and `splice` change the original array.

**Real-life example:** Think of a box of fruit. `filter` picks out only apples, `map` peels each one, and `reduce` makes one glass of juice from all of them.

**Interview question:** What is the difference between `map`, `filter` and `reduce`?

**Simple answer:** `map` returns a new array of the same length with each item changed. `filter` returns a new array with only the items that pass a test. `reduce` turns the array into one value, like a total. Watch out: `sort()` changes the array and sorts numbers as text unless you pass a compare function.

```javascript
orders.map(o => o.total);                    // [120, 40]
orders.filter(o => o.status === 'Paid');
orders.reduce((sum, o) => sum + o.total, 0); // 160
[10, 1, 2].sort((a, b) => a - b);            // [1, 2, 10]
```

### Map, Set, WeakMap, WeakSet

**In simple words:** `Map` stores key-value pairs, and the key can be any value, even an object. `Set` stores unique values only. `WeakMap` and `WeakSet` hold objects *weakly*: if nothing else uses the object, it can be removed from memory. They are like `Dictionary<TKey, TValue>` and `HashSet<T>` in C#.

**Real-life example:** A `Set` is a guest list where each name appears once. A `WeakMap` is a coat-check ticket: once the guest leaves the building, the coat entry is thrown away automatically.

**Interview question:** When would you use a `Map` instead of a plain object?

**Simple answer:** I use a `Map` when keys are not strings, when I add and remove keys often, or when I need the size and a guaranteed order. I use a `Set` to remove duplicates. I use a `WeakMap` to attach data to objects without stopping them from being garbage collected.

```javascript
const unique = [...new Set([1, 2, 2, 3])];   // [1, 2, 3]
const stock = new Map([[101, 5]]);
stock.set(102, 0).get(101);                  // 5
```

### Optional chaining and nullish coalescing

**In simple words:** Optional chaining (`?.`) stops and returns `undefined` if a value in the chain is `null` or `undefined`, instead of throwing an error. Nullish coalescing (`??`) gives a default value only when the left side is `null` or `undefined`. The older `||` gives the default for any falsy value, even a valid `0` or empty string.

**Real-life example:** `?.` is like asking "Is anyone at home? If yes, ask for the city." `??` is like "use the customer's chosen quantity, but if they left it blank, use 1."

**Interview question:** What is the difference between `??` and `||`?

**Simple answer:** `||` falls back to the default for any falsy value, so `0`, `''` and `false` are replaced. `??` falls back only for `null` or `undefined`, so a real `0` is kept. For defaults like page size or quantity, `??` is the safe choice.

```javascript
const city = order?.customer?.address?.city; // no error if missing
const qty = 0;
qty || 1;   // 1  (0 lost)
qty ?? 1;   // 0  (0 kept)
```

### Immutability patterns

**In simple words:** *Immutability* means you never change an existing object. You create a new copy with the change instead. React, Redux and Angular `OnPush` check for changes by comparing references. If you change an object in place, the reference is the same, so the screen may not update.

**Real-life example:** Instead of crossing out lines on a signed contract, you print a new version. Everyone can see clearly that the document changed.

**Interview question:** Why do React and Redux need immutable updates?

**Simple answer:** They detect changes by checking if the reference is new. If I mutate the same object, the reference does not change and nothing re-renders. So I copy each level I change with spread, and use `map`, `filter` or `toSorted` instead of `push` or `sort`.

```javascript
const added   = [...cart, newItem];
const removed = cart.filter(i => i.id !== 1);
const updated = cart.map(i => i.id === 1 ? { ...i, qty: 2 } : i);
```

### Prototypes and the prototype chain

**In simple words:** Every JavaScript object has a hidden link to another object, called its *prototype*. If a property is not found on the object, JavaScript looks at its prototype, then that prototype's prototype, until it reaches `null`. This is the *prototype chain*, and it is how inheritance works in JavaScript.

**Real-life example:** If a child does not know an answer, they ask a parent. If the parent does not know, they ask the grandparent, and so on.

**Interview question:** How does prototypal inheritance differ from class inheritance in C#?

**Simple answer:** In C#, a class is a fixed blueprint at compile time. In JavaScript, objects inherit directly from other objects at run time through the prototype chain. `class` and `extends` just set up these links for you. If you add a method to a prototype, all linked objects see it.

```javascript
const animal = { speak() { return 'sound'; } };
const dog = Object.create(animal);   // dog -> animal -> Object.prototype
dog.speak();                         // 'sound' (found on prototype)
```

### Shallow vs deep copy

**In simple words:** A *shallow copy* copies only the top level. Nested objects are still shared between the copy and the original. A *deep copy* copies everything, at every level. Spread (`{ ...obj }`) is shallow. `structuredClone(obj)` makes a deep copy.

**Real-life example:** A shallow copy is like copying a list of locker numbers — both lists still open the same lockers. A deep copy is like building new lockers with copies of everything inside.

**Interview question:** How would you deep clone an object in JavaScript?

**Simple answer:** I use the built-in `structuredClone`, which handles dates, maps, sets and circular references. `JSON.parse(JSON.stringify(obj))` works for simple data but loses dates, functions and `undefined`. In React or Redux, I usually avoid deep cloning and copy only the path I change.

```javascript
const src = { meta: { n: 1 } };
const shallow = { ...src };
shallow.meta.n = 99;            // src.meta.n is also 99
const deep = structuredClone(src);
```
