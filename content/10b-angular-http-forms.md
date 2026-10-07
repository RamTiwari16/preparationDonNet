## HttpClient and Interceptors

### HttpClient basics against an ASP.NET Core API

**Definition.** `HttpClient` is Angular's HTTP service. Every call returns a **cold Observable**: nothing is sent until someone subscribes (or the `async` pipe does), and each subscription sends a new request. It parses JSON by default and throws `HttpErrorResponse` for non-2xx and network errors (unlike `fetch`).

```typescript
// app.config.ts
provideHttpClient(withInterceptors([authInterceptor, errorInterceptor]), withFetch());

// order.service.ts
export type Page<T> = { items: T[]; page: number; pageSize: number; total: number };

@Injectable({ providedIn: 'root' })
export class OrderService {
  private http = inject(HttpClient);
  private base = `${inject(API_URL)}/orders`;

  list(page = 1, status?: string) {
    let params = new HttpParams().set('page', page).set('pageSize', 20);   // immutable: reassign
    if (status) params = params.set('status', status);
    // observe: 'response' exposes headers, e.g. ASP.NET Core's X-Pagination
    return this.http.get<Order[]>(this.base, { params, observe: 'response' }).pipe(
      map(res => ({
        items: res.body ?? [],
        ...JSON.parse(res.headers.get('X-Pagination') ?? '{"total":0}')
      }) as Page<Order>)
    );
  }
  get(id: number)                { return this.http.get<Order>(`${this.base}/${id}`); }
  create(dto: NewOrder)          { return this.http.post<Order>(this.base, dto); }
  update(id: number, dto: Order) { return this.http.put<void>(`${this.base}/${id}`, dto); }
  remove(id: number)             { return this.http.delete<void>(`${this.base}/${id}`); }
}
```

Facts: `HttpHeaders`/`HttpParams` are immutable (`set` returns a new object); the header `X-Pagination` is readable only if the API exposes it via CORS (`WithExposedHeaders`); `withCredentials: true` sends cookies cross-origin; upload progress uses `reportProgress: true, observe: 'events'`; `HttpClientTestingModule`/`provideHttpClientTesting()` mock it in tests.

:::warn Cold observable surprise
Calling `service.create(dto)` without subscribing does nothing. Subscribing twice (or using `| async` twice on the same observable) sends **two** POSTs. Convert with `shareReplay(1)` or bind once with `@if (x$ | async; as x)`.
:::

### Functional interceptors: JWT, refresh-on-401, global errors

**Definition.** An interceptor sits in the HTTP pipeline: it can clone/modify the request, and process or retry the response. Since v15 write them as functions (`HttpInterceptorFn`) registered with `withInterceptors([...])`. Order: requests pass through them left to right, responses in reverse. Class-based interceptors (`HTTP_INTERCEPTORS`) need `withInterceptorsFromDi()`, which libraries like MSAL still use.

```typescript
// problem.ts - map ProblemDetails to a typed error
export type ApiProblem = {
  status: number; title: string; detail?: string;
  errors?: Record<string, string[]>; traceId?: string;
};
export function toProblem(err: HttpErrorResponse): ApiProblem {
  if (err.status === 0) return { status: 0, title: 'Cannot reach the server.' };
  const b = err.error ?? {};
  return { status: err.status, title: b.title ?? err.statusText, detail: b.detail,
           errors: b.errors, traceId: b.traceId };
}

// auth.interceptor.ts
const FAILED = Symbol('refresh-failed');
let refreshing = false;
const token$ = new BehaviorSubject<string | typeof FAILED | null>(null);  // null = in progress

const withToken = (req: HttpRequest<unknown>, token: string) =>
  req.clone({ setHeaders: { Authorization: `Bearer ${token}` } });

export const authInterceptor: HttpInterceptorFn = (req, next) => {
  const auth = inject(AuthService);
  const isApi = req.url.startsWith(inject(API_URL));
  const isAuthCall = req.url.includes('/auth/');
  const token = auth.accessToken();

  const authReq = token && isApi && !isAuthCall ? withToken(req, token) : req;

  return next(authReq).pipe(
    catchError((err: HttpErrorResponse) => {
      if (err.status === 401 && isApi && !isAuthCall) {
        return refreshAndRetry(authReq, next, auth);
      }
      return throwError(() => err);
    })
  );
};

function refreshAndRetry(req: HttpRequest<unknown>, next: HttpHandlerFn, auth: AuthService) {
  if (refreshing) {
    // queue: wait for the in-flight refresh, then replay with the new token
    return token$.pipe(
      filter((t): t is string | typeof FAILED => t !== null),
      take(1),
      switchMap(t => t === FAILED
        ? throwError(() => new Error('Session expired'))
        : next(withToken(req, t)))
    );
  }
  refreshing = true;
  token$.next(null);
  return auth.refresh().pipe(                               // POST /api/auth/refresh -> new access token
    switchMap(newToken => { token$.next(newToken); return next(withToken(req, newToken)); }),
    catchError(err => { token$.next(FAILED); auth.logout(); return throwError(() => err); }),
    finalize(() => { refreshing = false; })
  );
}

// error.interceptor.ts - global handling, after auth logic has had its chance
export const errorInterceptor: HttpInterceptorFn = (req, next) => {
  const toast = inject(ToastService);
  const router = inject(Router);
  return next(req).pipe(
    catchError((err: HttpErrorResponse) => {
      const problem = toProblem(err);
      if (err.status === 0 || err.status >= 500) toast.error(`${problem.title} (ref ${problem.traceId ?? '-'})`);
      else if (err.status === 403) router.navigateByUrl('/forbidden');
      // 400/404/409/422: the component decides (field errors, not-found view)
      return throwError(() => problem);
    })
  );
};
```

How it works: the first 401 sets `refreshing`, calls the refresh endpoint and replays its own request with `switchMap`. Any other request that gets a 401 meanwhile subscribes to the `BehaviorSubject`, waits for the first non-null value, and replays with the new token. On failure `FAILED` is broadcast so queued requests error out instead of hanging, and the user is logged out.

Other typical interceptors: loading-bar counter (`finalize`), `retry({ count: 2, delay: ... })` for idempotent GETs, correlation-id header, caching, and `HttpContextToken` flags (`SKIP_AUTH`) to bypass specific interceptors per request.

:::q Why register interceptors as functions now? How does order work?
Functional interceptors (`HttpInterceptorFn`) are plain functions using `inject()`, tree-shakable, and composed with `withInterceptors([a, b])`: request goes through `a` then `b`, response comes back through `b` then `a`. The class-based `HTTP_INTERCEPTORS` multi-provider still works through `withInterceptorsFromDi()`.
:::

## Forms

### Template-driven vs reactive

| | Template-driven | Reactive |
|---|---|---|
| Model defined in | the template (`ngModel`, `ngForm`) | the component class (`FormGroup`, `FormControl`) |
| Module | `FormsModule` | `ReactiveFormsModule` |
| Validation | HTML attributes/directives | functions (`Validators.*`, custom, async) |
| Data flow | asynchronous (the form model is built after view init) | synchronous, explicit |
| Types | loose | **strongly typed** (v14+) |
| Testing | needs the DOM/`fixture.whenStable()` | unit-testable without a template |
| Dynamic fields | awkward | easy (`FormArray`, add/remove controls) |
| Best for | tiny, simple forms | anything real: validation, dynamic, cross-field, async |

```html
<!-- template-driven: fine for a 2-field login -->
<form #f="ngForm" (ngSubmit)="login(f.value)">
  <input name="email" [(ngModel)]="model.email" required email #email="ngModel">
  @if (email.invalid && email.touched) { <small>Valid email required</small> }
  <button [disabled]="f.invalid">Login</button>
</form>
```

### Reactive form: typed, validators, async validator, FormArray

```typescript
// validators.ts
export const noBlank: ValidatorFn = c =>
  (c.value ?? '').toString().trim().length === 0 ? { blank: true } : null;

export function matchFields(a: string, b: string): ValidatorFn {          // group-level
  return group => group.get(a)?.value === group.get(b)?.value ? null : { mismatch: true };
}

export function uniqueEmail(users: UserService): AsyncValidatorFn {
  return control =>
    timer(400).pipe(                                  // debounce; previous run is unsubscribed
      switchMap(() => users.emailExists(control.value)),     // GET /api/users/exists?email=
      map(exists => (exists ? { emailTaken: true } : null)),
      catchError(() => of(null))                      // never block the form if the API is down
    );
}
```

```typescript
@Component({
  selector: 'app-order-form', standalone: true,
  imports: [ReactiveFormsModule, CurrencyPipe],
  templateUrl: './order-form.component.html'
})
export class OrderFormComponent {
  private fb = inject(NonNullableFormBuilder);              // controls are never null (typed)
  private users = inject(UserService);
  private orders = inject(OrderService);
  private router = inject(Router);
  submitting = signal(false);

  form = this.fb.group({
    email: this.fb.control('', {
      validators: [Validators.required, Validators.email],
      asyncValidators: [uniqueEmail(this.users)],
      updateOn: 'blur'                                       // validate when leaving the field
    }),
    note: ['', [Validators.maxLength(200)]],
    lines: this.fb.array([this.newLine()], { validators: [Validators.minLength(1)] })
  });

  get lines() { return this.form.controls.lines; }

  newLine() {
    return this.fb.group({
      productId: this.fb.control(0, [Validators.min(1)]),
      qty: this.fb.control(1, [Validators.required, Validators.min(1), Validators.max(99)])
    });
  }
  addLine()           { this.lines.push(this.newLine()); }
  removeLine(i: number) { this.lines.removeAt(i); }

  submit() {
    if (this.form.invalid) { this.form.markAllAsTouched(); return; }
    this.submitting.set(true);
    const dto = this.form.getRawValue();                     // typed: { email: string; lines: {...}[] ... }
    this.orders.create(dto).pipe(finalize(() => this.submitting.set(false))).subscribe({
      next: o => this.router.navigate(['/orders', o.id]),
      error: (p: ApiProblem) => {                            // ValidationProblemDetails -> fields
        Object.entries(p.errors ?? {}).forEach(([field, msgs]) => {
          const key = field.charAt(0).toLowerCase() + field.slice(1);   // "Email" -> "email"
          this.form.get(key)?.setErrors({ server: msgs[0] });
        });
      }
    });
  }
}
```

Reminder: `inject()` works only in an injection context (field initialisers, constructor), so `Router` is captured as a field rather than injected inside the `next` callback.

```html
<form [formGroup]="form" (ngSubmit)="submit()" novalidate>
  <input type="email" formControlName="email" placeholder="Customer email">
  @let email = form.controls.email;
  @if (email.touched || email.dirty) {
    @if (email.pending) { <small>Checking...</small> }
    @if (email.hasError('required')) { <small>Email is required</small> }
    @if (email.hasError('emailTaken')) { <small>Already registered</small> }
    @if (email.hasError('server')) { <small>{{ email.getError('server') }}</small> }
  }

  <div formArrayName="lines">
    @for (line of lines.controls; track line; let i = $index) {
      <div [formGroupName]="i">
        <input type="number" formControlName="productId">
        <input type="number" formControlName="qty">
        <button type="button" (click)="removeLine(i)">Remove</button>
      </div>
    }
  </div>
  <button type="button" (click)="addLine()">Add line</button>
  <button type="submit" [disabled]="submitting() || form.invalid || form.pending">Place order</button>
</form>
```

Facts to remember:
- `FormControl` value/status: `valid`, `invalid`, `pending` (async validator running), `disabled`; flags `touched/untouched`, `dirty/pristine`. Disabled controls are excluded from `form.value`; `getRawValue()` includes them.
- `setValue` needs the full shape; `patchValue` accepts partial; `reset()` returns to initial (typed non-nullable resets to the initial value).
- `valueChanges` / `statusChanges` are Observables (use `debounceTime`, `takeUntilDestroyed`).
- `@let` (template variable) is available from Angular 18.1 (stable in 19); on older versions use `form.controls.email` or `#ref`.
- Typed forms (v14+): `FormControl<string | null>` by default; use `NonNullableFormBuilder` or `{ nonNullable: true }` to get `string`. `UntypedFormGroup` exists for migration only.

:::q Template-driven vs reactive forms - which would you pick and why?
Reactive for anything beyond trivial: the model lives in code, is typed, validators are plain testable functions, dynamic controls (`FormArray`) and cross-field/async validation are first-class, and you can react to `valueChanges` with RxJS. Template-driven is OK for a tiny form where `ngModel` and HTML attributes are enough.
:::

:::q How do you write an async validator that hits the server without spamming it?
Return an `Observable<ValidationErrors | null>` from an `AsyncValidatorFn`. Angular unsubscribes the previous validator run when the value changes, so `timer(400).pipe(switchMap(() => api.exists(value)))` debounces and cancels stale requests. Set `updateOn: 'blur'` to validate less often and `catchError(() => of(null))` so an API failure doesn't make the field invalid. Async validators only run if all sync validators pass.
:::
