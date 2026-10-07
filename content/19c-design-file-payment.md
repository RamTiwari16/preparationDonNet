## Design 5: File Storage (Drive/Dropbox-style)

Flow from the outline: *Upload, Download, Blob Storage, Metadata, Access control*.

### 1. Requirements

**Clarifying questions.** Max file size (5 GB? 100 GB)? Folders and sharing? Versioning? Preview/thumbnails? Is deduplication desired? Compliance (virus scan, retention, encryption at rest)? Download via CDN?

**Functional:** upload (resumable for big files), download, list/search metadata, rename/move/delete, share with users or by link, optional versions.
**Non-functional:** durability (11 nines via LRS/ZRS/GRS Blob), uploads must not stream through our API servers, large-file resilience (resume), secure by default (no public blobs), cost-efficient (tiering), scan all uploads.

### 2. Capacity estimation (illustrative)

100K uploads/day x 2 MB avg = ~200 GB/day = ~73 TB/year; downloads 5x uploads = ~1 TB/day egress = ~100 Mbit/s average. Upload API QPS: ~1/s, but each upload is megabytes, so *bandwidth, not QPS*, drives design. Metadata: 100K/day x 1 KB = 100 MB/day = tiny; one SQL database is enough.

### 3. API design

```json
// 1) POST /api/v1/files/uploads
{ "name": "report.pdf", "size": 52428800, "contentType": "application/pdf",
  "sha256": "9f86d0818...", "folderId": "f-12" }
// 201 -> client uploads straight to Blob using these URLs
{ "uploadId": "up-1", "blockSizeBytes": 8388608,
  "uploadUrl": "https://acct.blob.core.windows.net/quarantine/up-1?sv=...&sig=...",
  "expiresAtUtc": "2026-10-06T09:00:00Z" }
// (instant dedup case) -> 200 { "fileId": "fl-9", "deduplicated": true }

// 2) POST /api/v1/files/uploads/up-1/complete   { "blockIds": ["AAAA","AAAB", "..."] }
// 202 { "fileId": "fl-9", "status": "Scanning" }

// GET  /api/v1/files/fl-9                       -> metadata + status
// GET  /api/v1/files/fl-9/download-url          -> { "url": "https://...?sig=...", "expiresInSec": 300 }
// POST /api/v1/files/fl-9/shares   { "principal": "user:u-5", "permission": "read",
//                                    "expiresAtUtc": "2026-11-01T00:00:00Z" }
```

### 4. Data model

```sql
CREATE TABLE Blobs (                          -- physical content, deduplicated
  Sha256 BINARY(32) PRIMARY KEY, BlobPath NVARCHAR(300) NOT NULL,
  SizeBytes BIGINT NOT NULL, RefCount INT NOT NULL, Tier TINYINT NOT NULL
);
CREATE TABLE Files (                          -- logical files owned by users
  FileId UNIQUEIDENTIFIER PRIMARY KEY, OwnerId BIGINT NOT NULL, FolderId BIGINT NULL,
  Name NVARCHAR(255) NOT NULL, ContentType NVARCHAR(100), SizeBytes BIGINT,
  Sha256 BINARY(32) NULL REFERENCES Blobs(Sha256),
  Status TINYINT NOT NULL,                    -- 0 Uploading, 1 Scanning, 2 Available, 3 Quarantined
  Version INT NOT NULL DEFAULT 1, CreatedAtUtc DATETIME2, DeletedAtUtc DATETIME2 NULL
);
CREATE INDEX IX_Files_Folder ON Files (OwnerId, FolderId, Name) WHERE DeletedAtUtc IS NULL;
CREATE TABLE FileShares (
  FileId UNIQUEIDENTIFIER, PrincipalType TINYINT, PrincipalId NVARCHAR(100),
  Permission TINYINT, ExpiresAtUtc DATETIME2 NULL,
  PRIMARY KEY (FileId, PrincipalType, PrincipalId)
);
CREATE TABLE UploadSessions (UploadId UNIQUEIDENTIFIER PRIMARY KEY, OwnerId BIGINT,
  ExpectedSize BIGINT, Sha256 BINARY(32), BlobPath NVARCHAR(300), ExpiresAtUtc DATETIME2);
```

### 5. High-level architecture

```text
 Client --(1 init upload)--> File API --- authz, quota, dedup check --- SQL (metadata)
   |                              \--(returns SAS URL)
   |
   +--(2 PUT blocks directly)--> Azure Blob Storage  [container: quarantine]
                                        |  BlobCreated event
                                        v
                                   Event Grid --> Scan worker (Defender for Storage / ClamAV)
                                        |  clean?            infected?
                                        v                       v
                              copy to [container: files]   delete + mark Quarantined
                              Files.Status = Available     notify owner
 Client --(3 download)--> File API: authz -> user-delegation SAS (5 min) --> Blob / CDN
 Lifecycle policy: Hot -> Cool (30d) -> Archive (180d)
```

### 6. Deep dives

#### 6a. Pre-signed (SAS) upload and download

API servers must not proxy gigabytes. The API authorises the user and hands out a **short-lived, narrowly scoped SAS URL**; the client talks to Blob Storage directly. Prefer a **user delegation SAS** (signed with Entra ID credentials, no storage account key in your app).

```csharp
public sealed class SasService(BlobServiceClient service)
{
    private UserDelegationKey? _key;
    private DateTimeOffset _keyExpires;

    private async Task<UserDelegationKey> GetKeyAsync()
    {
        if (_key is null || _keyExpires < DateTimeOffset.UtcNow.AddMinutes(10))
        {
            _keyExpires = DateTimeOffset.UtcNow.AddHours(4);
            _key = (await service.GetUserDelegationKeyAsync(
                DateTimeOffset.UtcNow.AddMinutes(-5), _keyExpires)).Value;
        }
        return _key;
    }

    public async Task<Uri> CreateAsync(string container, string blobName,
        BlobSasPermissions perms, TimeSpan lifetime)
    {
        var sas = new BlobSasBuilder
        {
            BlobContainerName = container, BlobName = blobName, Resource = "b",
            StartsOn = DateTimeOffset.UtcNow.AddMinutes(-2),     // clock skew
            ExpiresOn = DateTimeOffset.UtcNow.Add(lifetime),
            Protocol = SasProtocol.Https
        };
        sas.SetPermissions(perms);                                // Read, or Create|Write

        var uri = new BlobUriBuilder(service.GetBlobContainerClient(container)
                                            .GetBlobClient(blobName).Uri)
        { Sas = sas.ToSasQueryParameters(await GetKeyAsync(), service.AccountName) };
        return uri.ToUri();
    }
}

// Download endpoint: authorise first, then sign
app.MapGet("/api/v1/files/{id:guid}/download-url", async (Guid id, ClaimsPrincipal user,
    IFileRepository files, IAuthorizationService authz, SasService sas) =>
{
    var file = await files.GetAsync(id);
    if (file is null) return Results.NotFound();
    if (!(await authz.AuthorizeAsync(user, file, Operations.Read)).Succeeded)
        return Results.Forbid();
    if (file.Status != FileStatus.Available) return Results.Conflict("Not available yet");

    var url = await sas.CreateAsync("files", file.BlobPath,
                                    BlobSasPermissions.Read, TimeSpan.FromMinutes(5));
    return Results.Ok(new { url, expiresInSec = 300 });
});
```

For revocable "anyone with the link" sharing, issue an opaque share token stored in `FileShares` and resolve it server-side to a fresh 5-minute SAS on each click, instead of handing out long-lived SAS URLs that cannot be revoked.

#### 6b. Chunked / resumable upload

Block blobs are made of up to 50,000 blocks; each block is staged independently and the blob only becomes visible at **commit**. This gives parallelism and resume (re-send only missing blocks).

```csharp
// Server-side or worker-side upload helper (the SDK does chunking + parallelism)
var blob = container.GetBlockBlobClient(path);
await blob.UploadAsync(stream, new BlobUploadOptions
{
    HttpHeaders = new BlobHttpHeaders { ContentType = contentType },
    TransferOptions = new StorageTransferOptions
    {
        InitialTransferSize = 8 * 1024 * 1024,
        MaximumTransferSize = 8 * 1024 * 1024,     // block size
        MaximumConcurrency = 8                      // parallel blocks
    }
}, ct);

// Manual control (what a browser client does via REST, shown with the SDK)
var blockIds = new List<string>();
for (int i = 0; ; i++)
{
    var buffer = new byte[8 * 1024 * 1024];
    int read = await stream.ReadAtLeastAsync(buffer, buffer.Length, throwOnEndOfStream: false);
    if (read == 0) break;
    string id = Convert.ToBase64String(BitConverter.GetBytes(i));   // equal-length IDs
    await blob.StageBlockAsync(id, new MemoryStream(buffer, 0, read));
    blockIds.Add(id);
}
await blob.CommitBlockListAsync(blockIds);

// Resume: ask the service which blocks already arrived
var staged = (await blob.GetBlockListAsync(BlockListTypes.Uncommitted)).Value.UncommittedBlocks;
```

#### 6c. Dedup by hash, virus scan, lifecycle

- **Dedup:** the client sends the SHA-256 at init. If `Blobs` already has it, create a `Files` row pointing to the same blob and `RefCount++`: instant upload, zero bytes transferred. On delete, `RefCount--`; a janitor removes blobs at 0. **Security caveat:** "this hash exists" leaks that someone stored that file. Restrict dedup to within one tenant/account or require the server to re-verify the hash after upload (proof of possession).
- **Virus scan:** upload lands in a `quarantine` container that users can never read. A worker (triggered by Event Grid `BlobCreated`, or Microsoft Defender for Storage malware scanning) scans, then *copies* clean files to `files` and sets `Status = Available`, or deletes and marks `Quarantined`. Downloads check `Status`.
- **Integrity:** after commit, compare blob `Content-MD5`/computed SHA-256 to the declared hash; mismatch rejects the file.
- **Lifecycle tiers:** a storage lifecycle management policy moves cold data automatically.

```json
{ "rules": [ { "name": "tiering", "enabled": true, "type": "Lifecycle",
  "definition": {
    "filters": { "blobTypes": ["blockBlob"], "prefixMatch": ["files/"] },
    "actions": { "baseBlob": {
      "tierToCool":    { "daysAfterLastAccessTimeGreaterThan": 30 },
      "tierToArchive": { "daysAfterModificationGreaterThan": 180 },
      "delete":        { "daysAfterModificationGreaterThan": 3650 } } } } } ] }
```

Archive-tier blobs need hours to rehydrate, so the UI must show "restoring".

#### 6d. Access control

1. Storage account: **no public access**, `allowSharedKeyAccess` off if possible, private endpoints for internal traffic.
2. Authorisation lives in the API (owner, share ACL, tenant) using ASP.NET Core **resource-based authorization**; SAS is only the *delivery mechanism* after the decision.
3. SAS lifetime: minutes, least permission (read-only for downloads, create/write for one blob for uploads), HTTPS only, optionally IP-restricted.
4. Encryption: at rest by default (Microsoft-managed or customer-managed keys), TLS in transit.
5. Audit log of share/download events.

### 7. Scaling, failure modes, trade-offs

- **Bandwidth:** Blob Storage and CDN carry the bytes, so API instances stay small. Use Azure CDN/Front Door with token auth for hot public-ish content.
- **Incomplete uploads:** blobs with uncommitted blocks are garbage collected by Azure after 7 days; `UploadSessions` rows are expired by a job.
- **Metadata DB** scale: index on `(OwnerId, FolderId)`; shard by owner only at very large scale.
- **Consistency:** metadata row and blob can disagree if a crash occurs between steps. Status flags (`Uploading`) plus a reconciler job that finds blobs without rows and rows stuck in `Uploading` solve it.
- **Trade-off:** direct-to-blob upload is cheaper and faster, but you lose chance to inspect bytes in-flight; the quarantine scan compensates.

:::tip How to present this in 45 minutes
The headline is "bytes bypass the API". Then cover resumable block upload, quarantine + scan, and SAS scoping. Mention dedup *and* its privacy caveat; it signals seniority.
:::

:::q Follow-up 1: Why not just proxy uploads through the API and write to Blob?
It ties up Kestrel threads and memory/bandwidth for large files, doubles the traffic, makes retries painful, and caps scalability at the API tier. Direct SAS upload moves the heavy lifting to Azure and keeps the API a lightweight control plane.
:::

:::q Follow-up 2: How do you let a user revoke a shared link?
Do not hand out long-lived SAS URLs. Hand out an opaque token that maps to a `FileShares` row; the API validates it on each use and issues a 5-minute SAS. Revoke = delete the row; at most 5 minutes of residual access.
:::

:::q Follow-up 3: How would you support file versioning?
Enable Blob versioning or add a `FileVersions` table (FileId, VersionNo, BlobSha256). Upload creates a new blob and a new version row; "restore" repoints `Files.Sha256`. Lifecycle rules move old versions to cool/archive and delete after retention.
:::


## Design 6: Payment System

Flow from the outline: *Payment Gateway, Transaction, Idempotency, Retry, Failure handling, Reconciliation*. We build the **merchant-side payment service** that integrates a PSP (Stripe, Razorpay, Adyen, PayPal), not a new card network.

### 1. Requirements

**Clarifying questions.** Are we a merchant integrating a PSP, or a PSP ourselves? Which methods (cards, UPI, wallets, bank transfer)? Auth+capture (hold then charge) or immediate charge? Refunds/partial refunds? Multi-currency? Recurring/subscriptions? Do we hold customer balances (wallet) needing a ledger?

**Functional:** create payment, authorize, capture, void, refund; receive async gateway results via webhooks; payment status API; ledger of every money movement; daily reconciliation against the PSP settlement report.

**Non-functional:** *correctness first*: never charge twice, never lose a payment result; every change auditable and immutable; 99.99% availability of the payment API; p95 < 2 s (dominated by the gateway); PCI DSS scope as small as possible; money never stored in `float`.

### 2. Capacity estimation (illustrative)

1M payments/day = ~12/s average, ~100/s peak, flash sale ~1,000/s. Each payment writes ~1 payment row + ~5 state events + 2-3 ledger rows + idempotency record ~ 3 KB, so ~3 GB/day, ~1 TB/year. The load is low; **the difficulty is correctness, not QPS.** Idempotency keys are kept 24-72 hours.

### 3. API design

```json
// POST /api/v1/payments         Idempotency-Key: 9c2e1f6a-...   (mandatory)
{ "orderId": "o-7788", "amountMinor": 149900, "currency": "INR",
  "paymentMethodToken": "tok_1Nx...", "capture": false,
  "returnUrl": "https://shop.example.com/pay/return" }
// 201 Created   (or 200 with the SAME body when the key is replayed)
{ "paymentId": "pay_01J9...", "status": "Authorized", "amountMinor": 149900,
  "nextAction": null }
// 3-D Secure / UPI: "status": "RequiresAction", "nextAction": { "type": "redirect", "url": "..." }

// POST /api/v1/payments/{id}/capture   Idempotency-Key: ...   { "amountMinor": 149900 }
// POST /api/v1/payments/{id}/refund    Idempotency-Key: ...   { "amountMinor": 50000, "reason": "damaged" }
// GET  /api/v1/payments/{id}
// POST /webhooks/psp                   (called by the PSP; signature verified, no JWT)
```

Amounts are **integers in minor units** (paise/cents) to avoid rounding; `decimal` is acceptable in the DB but never `double`.

### 4. Data model

```sql
CREATE TABLE Payments (
  PaymentId      UNIQUEIDENTIFIER PRIMARY KEY,
  OrderId        NVARCHAR(40) NOT NULL,
  AmountMinor    BIGINT NOT NULL, Currency CHAR(3) NOT NULL,
  Status         TINYINT NOT NULL,
  CapturedMinor  BIGINT NOT NULL DEFAULT 0, RefundedMinor BIGINT NOT NULL DEFAULT 0,
  PspReference   NVARCHAR(100) NULL,           -- gateway's id, key for reconciliation
  TokenLast4     CHAR(4), CardBrand NVARCHAR(20),   -- never PAN/CVV
  RowVersion     ROWVERSION, CreatedAtUtc DATETIME2, UpdatedAtUtc DATETIME2
);
CREATE UNIQUE INDEX UX_Payments_Psp ON Payments (PspReference) WHERE PspReference IS NOT NULL;
CREATE INDEX IX_Payments_Order ON Payments (OrderId);

CREATE TABLE PaymentEvents (                    -- append-only audit of every transition
  EventId BIGINT IDENTITY PRIMARY KEY, PaymentId UNIQUEIDENTIFIER,
  FromStatus TINYINT, ToStatus TINYINT, Source NVARCHAR(20),  -- api | webhook | job
  Detail NVARCHAR(500), CreatedAtUtc DATETIME2
);
CREATE TABLE IdempotencyKeys (
  [Key] NVARCHAR(100) NOT NULL, Scope NVARCHAR(100) NOT NULL,   -- scope = tenant/user + route
  RequestHash BINARY(32) NOT NULL, State TINYINT NOT NULL,      -- 0 InProgress, 1 Completed
  ResponseStatus INT NULL, ResponseBody NVARCHAR(MAX) NULL,
  CreatedAtUtc DATETIME2, LockedUntilUtc DATETIME2,
  PRIMARY KEY (Scope, [Key])
);
CREATE TABLE WebhookInbox (                     -- dedupe + replay + audit
  PspEventId NVARCHAR(100) PRIMARY KEY, Type NVARCHAR(80), Payload NVARCHAR(MAX),
  ReceivedAtUtc DATETIME2, ProcessedAtUtc DATETIME2 NULL
);
CREATE TABLE LedgerAccounts (AccountId INT PRIMARY KEY, Name NVARCHAR(80),
  Type TINYINT);                                -- asset | liability | revenue | expense
CREATE TABLE LedgerEntries (                    -- immutable; never UPDATE or DELETE
  EntryId BIGINT IDENTITY PRIMARY KEY, TransactionId UNIQUEIDENTIFIER NOT NULL,
  AccountId INT NOT NULL, Direction CHAR(1) NOT NULL CHECK (Direction IN ('D','C')),
  AmountMinor BIGINT NOT NULL CHECK (AmountMinor > 0), Currency CHAR(3),
  PaymentId UNIQUEIDENTIFIER, CreatedAtUtc DATETIME2
);
CREATE INDEX IX_Ledger_Txn ON LedgerEntries (TransactionId);
```

### 5. High-level architecture

```text
 Browser/Mobile --(card data)--> PSP hosted fields (Stripe Elements / Razorpay Checkout)
        |                                   |  returns a TOKEN (card never touches us)
        v (token + order)                   |
  Payment API (ASP.NET Core)                |
   - JWT auth, Idempotency middleware       |
   - State machine, outbox                  v
        |  charge/authorize (with PSP idempotency key)     PSP / Gateway
        +--------------------------------------------->  (acquirer, card networks)
        |                                                      |
   SQL: Payments, PaymentEvents, Ledger, Outbox                | webhooks (async result)
        |                                                      v
        +--- Outbox --> Service Bus: payment-events      Webhook endpoint
                 (Order service, Notification)           verify HMAC -> inbox -> process
                                                               |
 Nightly: Reconciliation job <-- PSP settlement report/API ----+--> exceptions queue (ops)
```

### 6. Deep dives

#### 6a. Payment state machine

Never let code set `Status = X` freely. Allow only legal transitions; reject the rest (this also tames duplicate or out-of-order webhooks).

```text
 Created -> RequiresAction -> Authorized -> Captured -> PartiallyRefunded -> Refunded
    |            |               |   \          \-> Disputed (chargeback)
    v            v               v    \-> Voided / Expired
  Failed       Failed         Failed
```

```csharp
public enum PaymentStatus : byte
{ Created, RequiresAction, Authorized, Captured, PartiallyRefunded, Refunded,
  Voided, Failed, Disputed }

public static class PaymentRules
{
    private static readonly Dictionary<PaymentStatus, PaymentStatus[]> Allowed = new()
    {
        [PaymentStatus.Created]           = [PaymentStatus.RequiresAction, PaymentStatus.Authorized,
                                             PaymentStatus.Captured, PaymentStatus.Failed],
        [PaymentStatus.RequiresAction]    = [PaymentStatus.Authorized, PaymentStatus.Captured,
                                             PaymentStatus.Failed],
        [PaymentStatus.Authorized]        = [PaymentStatus.Captured, PaymentStatus.Voided,
                                             PaymentStatus.Failed],
        [PaymentStatus.Captured]          = [PaymentStatus.PartiallyRefunded, PaymentStatus.Refunded,
                                             PaymentStatus.Disputed],
        [PaymentStatus.PartiallyRefunded] = [PaymentStatus.PartiallyRefunded, PaymentStatus.Refunded],
    };

    public static bool CanMove(PaymentStatus from, PaymentStatus to) =>
        Allowed.TryGetValue(from, out var next) && next.Contains(to);
}

public sealed class Payment
{
    public Guid Id { get; private set; }
    public PaymentStatus Status { get; private set; }
    public byte[] RowVersion { get; private set; } = default!;   // optimistic concurrency

    public void MoveTo(PaymentStatus to, string source, List<PaymentEvent> audit)
    {
        if (Status == to) return;                                 // idempotent no-op (duplicate webhook)
        if (!PaymentRules.CanMove(Status, to))
            throw new InvalidPaymentTransitionException(Id, Status, to);
        audit.Add(new PaymentEvent(Id, Status, to, source));
        Status = to;
    }
}
```

#### 6b. Idempotency-key middleware

**Definition.** Clients attach a unique `Idempotency-Key` to every mutating request. If the same key arrives again (network timeout, double-click, mobile retry) the server returns the *stored* original response instead of executing again. Same key + different body is a client bug (422). **Why:** "the request timed out" does not mean "the payment failed".

```csharp
public sealed class IdempotencyMiddleware(RequestDelegate next, IIdempotencyStore store)
{
    public async Task InvokeAsync(HttpContext ctx)
    {
        var endpoint = ctx.GetEndpoint();
        if (!HttpMethods.IsPost(ctx.Request.Method) ||
            endpoint?.Metadata.GetMetadata<RequiresIdempotencyAttribute>() is null)
        { await next(ctx); return; }

        if (!ctx.Request.Headers.TryGetValue("Idempotency-Key", out var keyValues)
            || string.IsNullOrWhiteSpace(keyValues))
        { ctx.Response.StatusCode = 400; await ctx.Response.WriteAsync("Idempotency-Key required"); return; }

        string scope = $"{ctx.User.FindFirst("sub")?.Value}:{ctx.Request.Path}";
        string key = keyValues.ToString();

        ctx.Request.EnableBuffering();
        byte[] hash = await SHA256.HashDataAsync(ctx.Request.Body, ctx.RequestAborted);
        ctx.Request.Body.Position = 0;

        // Atomic: INSERT ... State=InProgress; unique (Scope, Key) decides the winner.
        var claim = await store.TryBeginAsync(scope, key, hash, lockFor: TimeSpan.FromSeconds(60));
        switch (claim.Outcome)
        {
            case ClaimOutcome.Replay:                            // finished before: replay
                ctx.Response.StatusCode = claim.Status;
                ctx.Response.Headers["Idempotent-Replayed"] = "true";
                await ctx.Response.WriteAsync(claim.Body!);
                return;
            case ClaimOutcome.InProgress:                        // concurrent duplicate
                ctx.Response.StatusCode = 409;
                ctx.Response.Headers.RetryAfter = "2";
                return;
            case ClaimOutcome.HashMismatch:                      // same key, different body
                ctx.Response.StatusCode = 422;
                await ctx.Response.WriteAsync("Key reused with a different request");
                return;
        }

        var original = ctx.Response.Body;
        await using var buffer = new MemoryStream();
        ctx.Response.Body = buffer;
        try
        {
            await next(ctx);
            buffer.Position = 0;
            string body = await new StreamReader(buffer).ReadToEndAsync();
            if (ctx.Response.StatusCode < 500)                   // do not cache transient failures
                await store.CompleteAsync(scope, key, ctx.Response.StatusCode, body);
            else
                await store.ReleaseAsync(scope, key);            // allow a retry to re-execute
            buffer.Position = 0;
            await buffer.CopyToAsync(original);
        }
        catch { await store.ReleaseAsync(scope, key); throw; }
        finally { ctx.Response.Body = original; }
    }
}
// Program.cs:  app.UseAuthentication(); app.UseAuthorization(); app.UseMiddleware<IdempotencyMiddleware>();
// endpoint:    app.MapPost("/api/v1/payments", Handler).WithMetadata(new RequiresIdempotencyAttribute());
```

Also pass **your own derived key to the PSP** (e.g. `payment:{paymentId}:capture`): if our process dies after the PSP charged but before we saved, a retry with the same PSP key returns the same charge instead of a second one.

#### 6c. Authorize, capture, retries, unknown outcomes

- **Authorize** reserves funds on the card (typically valid ~7 days); **capture** moves the money (full or partial); **void** releases an uncaptured authorization; **refund** returns captured money. E-commerce usually authorizes at checkout and captures when the order ships.
- **Retry rules:** retry only calls that carry an idempotency key, only on network errors/5xx/429, with exponential backoff + jitter and a hard cap. Never retry 4xx business declines (insufficient funds, card declined).
- **Timeout = unknown.** If the PSP call times out, do not mark `Failed`. Mark `Pending`, then ask the PSP "what is the status of reference X?" (status inquiry). Webhooks and the reconciliation job close the gap.

```csharp
services.AddHttpClient<IPspClient, PspClient>()
    .AddResilienceHandler("psp", b =>                       // Microsoft.Extensions.Http.Resilience
    {
        b.AddTimeout(TimeSpan.FromSeconds(10));
        b.AddRetry(new HttpRetryStrategyOptions
        {
            MaxRetryAttempts = 3, BackoffType = DelayBackoffType.Exponential, UseJitter = true,
            ShouldHandle = args => ValueTask.FromResult(
                args.Outcome.Exception is HttpRequestException ||
                args.Outcome.Result?.StatusCode is >= HttpStatusCode.InternalServerError
                    or HttpStatusCode.TooManyRequests)
        });
        b.AddCircuitBreaker(new HttpCircuitBreakerStrategyOptions
        { FailureRatio = 0.5, MinimumThroughput = 20, BreakDuration = TimeSpan.FromSeconds(30) });
    });
// PspClient adds:  request.Headers.Add("Idempotency-Key", $"payment:{id}:authorize");
```

#### 6d. Webhooks with signature verification

The PSP calls us when the final result is known (UPI approval, 3-D Secure completion, dispute). The endpoint is public, so anyone can POST to it: **verify the HMAC signature over the raw body** and reject old timestamps.

```csharp
app.MapPost("/webhooks/psp", async (HttpRequest req, IWebhookInbox inbox,
    IOptions<PspOptions> opt, IBackgroundTaskQueue queue) =>
{
    using var reader = new StreamReader(req.Body);
    string raw = await reader.ReadToEndAsync();                    // RAW body, before any parsing

    string header = req.Headers["X-Psp-Signature"].ToString();     // "t=1696580000,v1=ab12..."
    var parts = header.Split(',').Select(p => p.Split('=', 2)).ToDictionary(p => p[0], p => p[1]);
    if (!parts.TryGetValue("t", out var ts) || !parts.TryGetValue("v1", out var sig))
        return Results.BadRequest();

    if (Math.Abs(DateTimeOffset.UtcNow.ToUnixTimeSeconds() - long.Parse(ts)) > 300)
        return Results.BadRequest("Timestamp outside tolerance");   // replay protection

    byte[] expected = HMACSHA256.HashData(Encoding.UTF8.GetBytes(opt.Value.WebhookSecret),
                                          Encoding.UTF8.GetBytes($"{ts}.{raw}"));
    if (!CryptographicOperations.FixedTimeEquals(expected, Convert.FromHexString(sig)))
        return Results.Unauthorized();                              // constant-time compare

    var evt = JsonSerializer.Deserialize<PspEvent>(raw)!;
    if (!await inbox.TryAddAsync(evt.Id, evt.Type, raw))            // unique PspEventId
        return Results.Ok();                                        // duplicate delivery: ack

    await queue.EnqueueAsync(evt.Id);                               // process asynchronously
    return Results.Ok();                                            // respond 2xx FAST
});
```

Rules: return 2xx quickly or the PSP retries (often for days); make processing idempotent (inbox + state machine); tolerate out-of-order events (`captured` before `authorized`); never trust the payload amount blindly, re-fetch the payment from the PSP if money logic depends on it. (The exact header format differs per PSP: read your PSP's docs.)

#### 6e. Double-entry ledger

**Definition.** Every movement is recorded as two or more entries whose debits equal credits. Nothing is updated or deleted; mistakes are fixed with *reversing* entries. **Why:** you can always prove where every paisa went, and balances are derived, not stored.

Customer pays Rs. 1,000; PSP fee Rs. 30:

| Account | Debit | Credit |
|---|---|---|
| PSP Clearing (asset) | 970.00 | |
| PSP Fee Expense | 30.00 | |
| Sales Revenue / Order Payable | | 1,000.00 |

(Rule: total debits 1,000 = total credits 1,000.)

```csharp
public async Task PostAsync(Guid txnId, Guid paymentId, IEnumerable<Leg> legs, CancellationToken ct)
{
    var list = legs.ToList();
    long debits  = list.Where(l => l.Dir == 'D').Sum(l => l.AmountMinor);
    long credits = list.Where(l => l.Dir == 'C').Sum(l => l.AmountMinor);
    if (debits != credits || debits == 0)
        throw new InvalidOperationException($"Unbalanced txn {txnId}: D={debits} C={credits}");

    await using var tx = await _db.Database.BeginTransactionAsync(ct);
    foreach (var l in list)
        _db.LedgerEntries.Add(new LedgerEntry(txnId, l.AccountId, l.Dir, l.AmountMinor,
                                              l.Currency, paymentId, DateTime.UtcNow));
    await _db.SaveChangesAsync(ct);          // unique (TransactionId, AccountId, Dir) = idempotent
    await tx.CommitAsync(ct);
}
```

#### 6f. Reconciliation job

**Why:** webhooks can be lost, our DB write can fail after the PSP charged, PSP and bank settle days later. Reconciliation compares *our records* with the *PSP settlement report* and flags differences.

```csharp
public sealed class ReconciliationJob(IPspReports psp, PaymentsDbContext db,
    ILogger<ReconciliationJob> log) : BackgroundService
{
    protected override async Task ExecuteAsync(CancellationToken stop)
    {
        using var timer = new PeriodicTimer(TimeSpan.FromHours(24));       // or a cron-triggered job
        do { await RunForAsync(DateOnly.FromDateTime(DateTime.UtcNow.AddDays(-1)), stop); }
        while (await timer.WaitForNextTickAsync(stop));
    }

    private async Task RunForAsync(DateOnly day, CancellationToken ct)
    {
        var theirs = (await psp.GetSettlementAsync(day, ct)).ToDictionary(x => x.PspReference);
        var ours = await db.Payments.AsNoTracking()
            .Where(p => DateOnly.FromDateTime(p.UpdatedAtUtc) == day && p.PspReference != null)
            .ToDictionaryAsync(p => p.PspReference!, ct);

        foreach (var (reference, t) in theirs)
        {
            if (!ours.TryGetValue(reference, out var o))
                await Flag("MissingInternally", reference, t.AmountMinor, null);   // we lost a webhook
            else if (o.CapturedMinor != t.AmountMinor)
                await Flag("AmountMismatch", reference, t.AmountMinor, o.CapturedMinor);
        }
        foreach (var reference in ours.Keys.Except(theirs.Keys))
            await Flag("MissingAtPsp", reference, null, ours[reference].CapturedMinor);
    }
    private Task Flag(string kind, string refId, long? psp, long? ours) { /* write exception row + alert */ return Task.CompletedTask; }
}
```

Auto-heal where safe (query PSP, move state), otherwise route the exception to a finance/ops queue with a runbook.

#### 6g. PCI scope reduction via tokenization

**PCI DSS** applies to anyone who stores, processes or transmits cardholder data. The cheapest compliance is to **never see the card number**: the browser sends the PAN straight to the PSP's hosted field/iframe; the PSP returns a **token**; we store the token, last4, brand, expiry. That keeps us in the lightest self-assessment (SAQ A / A-EP) rather than SAQ D.

- Never log request bodies on payment routes; mask in logs; never store CVV (even encrypted).
- Secrets (PSP API keys, webhook secret) live in Key Vault, rotated; use managed identity.
- TLS 1.2+ everywhere; restrict who can call the webhook (signature, optionally PSP IP allow-list).
- Strong customer authentication (3-D Secure/OTP, RBI mandates for India) is handled via `RequiresAction` redirect flows.

### 7. Scaling, failure modes, trade-offs

| Failure | Handling |
|---|---|
| Client retries or double-clicks | Idempotency key replays stored response |
| PSP timeout | Status `Pending`; inquiry + webhook + reconciliation resolve it |
| Webhook lost / duplicated / out of order | Inbox dedupe, state machine, reconciliation |
| PSP outage | Circuit breaker; queue orders as `PendingPayment`; optional secondary PSP routing |
| Our DB fails after PSP charged | PSP idempotency key + status inquiry + reconciliation (never double charge) |
| Partial capture/refund races | Optimistic concurrency (`RowVersion`) + `Captured - Refunded >= 0` check |

**Trade-offs.** Strong consistency and single-writer per payment (partition by `PaymentId`) over raw throughput. Synchronous call to PSP in the request path (simple UX) vs fully async (resilient but more states). Build vs buy ledger: for a merchant, PSP + a lightweight internal ledger is enough; a wallet product needs a real ledger service.

:::tip How to present this in 45 minutes
Say the three words early: *idempotency, state machine, reconciliation*. Spend deep-dive time on the idempotency key lifecycle (InProgress/Completed/replay/mismatch) and "timeout means unknown". Mention tokenization to show you know you should not touch card numbers.
:::

:::q Follow-up 1: The client times out after calling /payments. They retry with a new idempotency key. What happens?
That is a client bug: a new key means a new payment. Client SDKs must reuse the key for retries of the *same* intent (generate it once when the user clicks Pay, persist it). Server-side defence: a unique constraint on `(OrderId)` active payment, or per-order dedupe, rejects a second open payment for the same order.
:::

:::q Follow-up 2: How do you make sure the ledger and the payment status never disagree?
Write the status change, the audit event, the ledger entries and the outbox message in **one local DB transaction**. Events to other services go through the outbox, so they cannot be published without the DB commit, and a periodic check asserts `SUM(debits) = SUM(credits)` per transaction.
:::

:::q Follow-up 3: How would you support multiple PSPs?
Define an `IPaymentGateway` abstraction (authorize/capture/refund/status) with one adapter per PSP; a routing policy picks by method, region, cost or health. Store `PspName` + `PspReference` on the payment, normalise statuses to our state machine, and run reconciliation per PSP.
:::
