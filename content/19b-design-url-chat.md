## Design 3: URL Shortener

Flow from the outline: *Generate short URL, Redirect, Database, Cache, Scalability*.

### 1. Requirements

**Clarifying questions.** Custom aliases? Expiry? Analytics (click counts, geo)? Can a user delete or edit a link? How long do links live? Same long URL always gets the same short code, or a new one per request? Read-heavy, I assume.

**Functional:** create short URL (optional alias and expiry), redirect, basic click analytics, delete/disable.
**Non-functional:** redirect p99 < 50 ms; very high availability (a dead redirect breaks every page that links to it); codes are unpredictable enough to prevent enumeration; scales to billions of rows.

### 2. Capacity estimation (illustrative)

- 100M new URLs/month = ~40 writes/s average.
- Read:write = 100:1 -> ~4,000 redirects/s average, ~20,000/s peak.
- 5 years x 12 x 100M = 6B URLs. At ~500 B per row = ~3 TB. A single SQL box is uncomfortable; plan for partitioning or a key-value store.
- **Code length:** 62^7 = ~3.5 trillion combinations, so 7 characters of base62 is plenty for 6B.
- Cache: 80/20 rule. Cache the hottest 20% of daily traffic: 4,000 x 86,400 = 345M reads/day, unique hot URLs maybe 20M x 500 B = ~10 GB. Fits in one Redis node.

### 3. API design

```json
// POST /api/v1/urls      Authorization: Bearer ...
{ "longUrl": "https://example.com/products/42?utm=abc", "customAlias": "sale24",
  "expiresAtUtc": "2027-01-01T00:00:00Z" }
// 201 Created
{ "shortUrl": "https://sho.rt/sale24", "code": "sale24", "createdAtUtc": "2026-10-06T10:00:00Z" }

// GET /{code}  ->  302 Found, Location: https://example.com/products/42?utm=abc
//             ->  404 Not Found (unknown)   410 Gone (expired / disabled)

// GET /api/v1/urls/{code}/stats
{ "code": "sale24", "totalClicks": 18230, "last7Days": [ 120, 340, 410, 380, 290, 300, 280 ] }

// DELETE /api/v1/urls/{code}   -> 204
```

### 4. Data model

```sql
CREATE TABLE ShortUrls (
  Code         VARCHAR(10)   NOT NULL PRIMARY KEY,   -- lookup is always by Code
  LongUrl      NVARCHAR(2048) NOT NULL,
  OwnerId      BIGINT NULL,
  CreatedAtUtc DATETIME2 NOT NULL,
  ExpiresAtUtc DATETIME2 NULL,
  IsDisabled   BIT NOT NULL DEFAULT 0
);
CREATE INDEX IX_ShortUrls_Owner ON ShortUrls (OwnerId, CreatedAtUtc DESC);
-- optional: dedup same long URL per owner
CREATE INDEX IX_ShortUrls_Hash ON ShortUrls (LongUrlHash) ;   -- HASHBYTES column

-- Clicks go to a separate append-only store (not the hot table)
-- ClickEvents(Code, TimestampUtc, Country, Referrer, UserAgentHash)
```

Access pattern is pure key-value (`Code -> LongUrl`), so DynamoDB/Cosmos DB (partition key = Code) scales horizontally with no effort. SQL with a clustered key on `Code` also works to a few billion rows with partitioning. Say: *"key-value access, so I would choose Cosmos DB or Redis-backed SQL; I'll show SQL because it's what I would run on the team's existing stack."*

### 5. High-level architecture

```text
 Client --> CDN/Front Door --> Load balancer --> Redirect API (stateless, N instances)
                                                    |
                                    1) local MemoryCache (tiny TTL)
                                    2) Redis  (cache-aside, Code -> LongUrl)
                                    3) DB     (miss only)  --> populate caches
                                                    |
                                      click event --> Channel<T> / Service Bus
                                                    |
                                          Analytics consumer --> ClickHouse / ADX
 Create API --> ID generator --> base62 --> DB insert (unique) --> warm cache
```

### 6. Deep dives

#### 6a. Base62 encoding

Base62 = `0-9a-zA-Z`, URL-safe, no padding. Convert a numeric ID to a string.

```csharp
public static class Base62
{
    private const string Alphabet =
        "0123456789ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz";

    public static string Encode(long value)
    {
        if (value == 0) return "0";
        Span<char> buffer = stackalloc char[11];            // 62^11 > 2^63
        int pos = buffer.Length;
        while (value > 0)
        {
            buffer[--pos] = Alphabet[(int)(value % 62)];
            value /= 62;
        }
        return new string(buffer[pos..]);
    }

    public static long Decode(string s)
    {
        long result = 0;
        foreach (char c in s)
            result = result * 62 + Alphabet.IndexOf(c);
        return result;
    }
}
// Base62.Encode(125) => "21"     Base62.Encode(3_521_614_606_207) => "zzzzzzz"
```

#### 6b. ID generation strategies

| Strategy | How | Pros | Cons |
|---|---|---|---|
| **Counter** (DB sequence / Redis `INCR`) | `Base62.Encode(nextId)` | No collisions, short codes, simple | Sequential = guessable; single point of contention |
| **Counter with ranges** | Each app instance leases a block of 1,000 IDs, hands them out in memory | Removes per-request round trip; scales | Gaps on crash (harmless); still guessable unless scrambled |
| **Snowflake** (41-bit time + 10-bit machine + 12-bit seq) | Local, no coordination | Unique across nodes, time-sortable | 64-bit ID -> 10-11 chars; clock skew handling |
| **Hash + collision handling** | `SHA256(longUrl + salt)`, take first 7 chars, insert; on unique violation, re-salt | Same URL -> same code (dedup) | Collision retries; truncation risk grows with scale |
| **Random + unique constraint / KGS** | Pre-generate random codes into a key table; pop one per request | Unguessable, no collision at request time | Needs a key-generation service and its storage |

To stop enumeration with a counter, *scramble* the number first (multiply by a large odd constant modulo 62^7, or XOR with a secret) and encode that. Keep it reversible and collision-free.

```csharp
// Range-allocating counter: DB is hit once per 1000 URLs, not once per URL.
public sealed class RangeIdGenerator(IDbConnectionFactory db)
{
    private long _next, _max;
    private readonly SemaphoreSlim _gate = new(1, 1);

    public async Task<long> NextAsync()
    {
        await _gate.WaitAsync();
        try
        {
            if (_next >= _max)
            {   // atomic: "UPDATE Counters SET Value = Value + 1000 OUTPUT inserted.Value"
                _max = await db.LeaseBlockAsync(size: 1000);
                _next = _max - 1000;
            }
            return _next++;
        }
        finally { _gate.Release(); }
    }
}

// Hash + collision retry
public async Task<string> CreateAsync(string longUrl, CancellationToken ct)
{
    for (int salt = 0; salt < 5; salt++)
    {
        byte[] hash = SHA256.HashData(Encoding.UTF8.GetBytes($"{longUrl}#{salt}"));
        string code = Base62.Encode(BitConverter.ToInt64(hash, 0) & 0x7FFF_FFFF_FFFF)[..7];
        try { await _repo.InsertAsync(code, longUrl, ct); return code; }
        catch (UniqueConstraintException) { /* collision: try next salt */ }
    }
    throw new InvalidOperationException("Could not allocate a short code");
}
```

#### 6c. Redirect: 301 vs 302 and the cache

| | 301 Moved Permanently | 302 Found (or 307) |
|---|---|---|
| Browser caching | Cached, often indefinitely | Not cached (unless headers say so) |
| Server load | Lowest; repeat visits skip us | Every click hits us |
| Analytics | Lost after first visit per browser | Every click counted |
| Edit/expire link later | Browsers keep old target | Works immediately |

Say this: *"If analytics, expiry or editing matter, use 302 and put a CDN/short `Cache-Control: max-age` in front. If we only want maximum offload and links are immutable, 301."* Most commercial shorteners use 301/302 depending on plan; 302 is the safe default.

```csharp
app.MapGet("/{code:regex(^[0-9A-Za-z_-]{{3,10}}$)}", async (
    string code, IShortUrlCache cache, IShortUrlRepository repo,
    Channel<ClickEvent> clicks, HttpContext ctx) =>
{
    var entry = await cache.GetOrAddAsync(code, () => repo.FindAsync(code));  // cache-aside
    if (entry is null)    return Results.NotFound();
    if (entry.IsExpired)  return Results.StatusCode(StatusCodes.Status410Gone);

    clicks.Writer.TryWrite(new ClickEvent(code, DateTime.UtcNow,                // fire-and-forget
        ctx.Request.Headers.Referer.ToString(), ctx.Connection.RemoteIpAddress));
    return Results.Redirect(entry.LongUrl, permanent: false);                   // 302
});

public sealed class ShortUrlCache(IDistributedCache redis, IMemoryCache local)
{
    public async Task<ShortUrlEntry?> GetOrAddAsync(string code, Func<Task<ShortUrlEntry?>> load)
    {
        if (local.TryGetValue(code, out ShortUrlEntry? hit)) return hit;
        var json = await redis.GetStringAsync($"u:{code}");
        ShortUrlEntry? entry = json is null ? null : JsonSerializer.Deserialize<ShortUrlEntry>(json);
        if (entry is null)
        {
            entry = await load();
            // negative caching: remember "not found" briefly to stop scanners hammering the DB
            await redis.SetStringAsync($"u:{code}",
                JsonSerializer.Serialize(entry),
                new DistributedCacheEntryOptions { AbsoluteExpirationRelativeToNow =
                    entry is null ? TimeSpan.FromMinutes(1) : TimeSpan.FromHours(24) });
        }
        local.Set(code, entry, TimeSpan.FromSeconds(30));
        return entry;
    }
}
```

Click analytics must **never** block the redirect: write to an in-memory `Channel<ClickEvent>`, a background consumer batches to a queue or analytics store.

### 7. Scaling, failure modes, trade-offs

- **Reads:** stateless redirect API behind a load balancer; Redis cluster; CDN for popular codes if 302 with `max-age`.
- **Writes:** partition by `Code` hash (Cosmos/Dynamo does this automatically). Single primary in SQL is fine at 40 writes/s.
- **Hot key:** one viral link = one Redis key. Mitigate with the in-process `MemoryCache` layer (as above) so each instance serves it locally.
- **Cache stampede:** a popular key expires, 1,000 requests hit the DB. Use a per-key lock (`SemaphoreSlim`/single-flight) or probabilistic early refresh.
- **Abuse:** rate limit creation per user/IP, check destination against Safe Browsing/blocklist, forbid redirect loops to ourselves.
- **Expiry cleanup:** background job deletes expired rows in batches; lazy check at read time covers the gap.
- **Availability:** multi-region active-active reads (Cosmos multi-region or geo-replicated SQL) because redirects are read-only.

:::warn Common mistakes
Using `Random` with no collision handling; hashing the long URL and truncating to 6 chars with no unique-constraint retry; awaiting analytics writes inside the redirect path; returning 301 and then wondering why click counts are wrong.
:::

:::tip How to present this in 45 minutes
This is the "warm-up" design, so finish the basics in 20 minutes and spend the remaining time on ID generation trade-offs, 301 vs 302, and cache stampede/hot keys. Always do the 7-char x base62 maths out loud.
:::

:::q Follow-up 1: Can two users get the same short code? How do you prevent it?
Never at the data layer: `Code` is the primary key, so a duplicate insert fails with a unique violation. With a counter or Snowflake IDs collisions cannot occur by construction; with hash or random codes we catch the violation and retry with a new salt.
:::

:::q Follow-up 2: How would you build per-link analytics at 20K clicks/s?
Redirect path writes a click event to a bounded in-memory channel; a background service batches events into Service Bus/Event Hubs; a stream processor aggregates into counters per code per minute in a column store (ADX/ClickHouse). The stats API reads the aggregates, never raw events.
:::

:::q Follow-up 3: How do you handle a link that must be taken down immediately (malware)?
Set `IsDisabled` in the DB and delete the Redis key plus publish an invalidation event so in-process caches evict. Keep local cache TTL short (30 s) so the worst-case takedown delay is bounded. This is another reason to prefer 302 over 301: browsers do not cache the old target.
:::

## Design 4: Chat Application

Flow from the outline: *WebSocket, SignalR, Message queue, Online/offline status, Message persistence*.

### 1. Requirements

**Clarifying questions.** 1:1 only or group chat too (max group size)? Text only or attachments? Do we need read receipts, typing indicators, presence? Message history retention? Multi-device per user? End-to-end encryption (out of scope unless asked)? Web + mobile?

**Functional:** send/receive messages in real time; 1:1 and group conversations; message history with paging; online/offline/last-seen; delivery receipts (sent, delivered, read); push notification when offline; attachments via the File Storage service.

**Non-functional:** end-to-end delivery < 200 ms for online users; **per-conversation ordering**; no message loss (at-least-once + client-side dedup); horizontal scale of connections; graceful reconnect.

### 2. Capacity estimation (illustrative)

- 10M DAU, 40 messages/user/day = 400M messages/day = ~4,600/s average, ~15,000/s peak.
- Concurrent connections: assume 10% of DAU online = 1M WebSockets. One SignalR server comfortably holds on the order of tens of thousands of idle connections (depends on message rate and memory), so ~50 nodes, or offload to Azure SignalR Service.
- Storage: 400M x 200 B = 80 GB/day = ~29 TB/year. This is write-heavy, append-mostly, read by conversation: a wide-column/NoSQL store (Cosmos DB, Cassandra) is a better fit than a single SQL database.

### 3. API design

Real-time traffic goes over a SignalR hub; REST handles history and management.

```text
Hub  /hubs/chat   (JWT via access_token query string for WebSockets)
  client -> server:  SendMessage(conversationId, clientMsgId, text)
                     MarkRead(conversationId, upToSeq)
                     Typing(conversationId)
  server -> client:  ReceiveMessage(msg)   MessageAck(clientMsgId, seq)
                     ReceiptUpdated(convId, userId, status, upToSeq)
                     PresenceChanged(userId, online, lastSeenUtc)

REST
  GET  /api/v1/conversations                         -> list with last message + unread
  POST /api/v1/conversations                         -> create group
  GET  /api/v1/conversations/{id}/messages?beforeSeq=900&limit=50
  GET  /api/v1/conversations/{id}/messages?afterSeq=870   (gap fill on reconnect)
```

```json
// ReceiveMessage payload
{ "conversationId": "c-1", "seq": 871, "messageId": "01J9Z...", "senderId": "u-7",
  "text": "Is the build green?", "sentAtUtc": "2026-10-06T08:15:01Z",
  "clientMsgId": "f2c1..." }
```

### 4. Data model

```sql
-- SQL: low-volume relational data
CREATE TABLE Conversations (
  ConversationId UNIQUEIDENTIFIER PRIMARY KEY, Type TINYINT,   -- 0 direct, 1 group
  Title NVARCHAR(100) NULL, CreatedAtUtc DATETIME2, LastSeq BIGINT NOT NULL DEFAULT 0
);
CREATE TABLE ConversationMembers (
  ConversationId UNIQUEIDENTIFIER, UserId BIGINT,
  LastDeliveredSeq BIGINT NOT NULL DEFAULT 0,    -- receipts as watermarks, not per message
  LastReadSeq      BIGINT NOT NULL DEFAULT 0,
  PRIMARY KEY (ConversationId, UserId)
);
CREATE INDEX IX_Members_User ON ConversationMembers (UserId);   -- "my conversations"
```

```json
// Cosmos DB / Cassandra: Messages  (partition key = conversationId, sort = seq)
{ "id": "c-1:871", "conversationId": "c-1", "seq": 871, "senderId": "u-7",
  "clientMsgId": "f2c1...", "text": "Is the build green?",
  "attachments": [], "sentAtUtc": "2026-10-06T08:15:01Z", "deleted": false }
```

A single conversation's messages live in one partition, so "load last 50" is a single-partition range query. Very large groups/channels need *bucketing* (`conversationId + month`) to cap partition size.

### 5. High-level architecture

```text
 Web / Mobile clients  <== WebSocket ==>  Azure SignalR Service (or SignalR nodes + Redis)
                                                    |
                                          Chat Hub (ASP.NET Core, stateless)
                                           |     |         |
                  validate member       persist   publish   presence
                  (Redis cache)          |         |           |
                                    Messages DB   Service Bus  Redis
                                    (Cosmos)      topic: chat  (presence:{user} TTL)
                                                      |
                              +-----------------------+-----------------+
                              v                       v                 v
                       Fan-out / delivery      Push notifier       Search/Indexer
                       (to recipients' hub)    (offline users ->   (optional)
                                               Notification Svc)
```

### 6. Deep dives

#### 6a. SignalR hub with groups

Authenticate with JWT; use `Context.UserIdentifier` (maps to the `NameIdentifier` claim by default). A SignalR **group** is a named set of connections. One group per conversation is the simplest fan-out model.

```csharp
[Authorize]
public sealed class ChatHub(IChatService chat, IPresenceService presence,
                            ILogger<ChatHub> log) : Hub
{
    public override async Task OnConnectedAsync()
    {
        var userId = Context.UserIdentifier!;
        foreach (var convId in await chat.GetConversationIdsAsync(userId))
            await Groups.AddToGroupAsync(Context.ConnectionId, $"c:{convId}");

        await presence.ConnectedAsync(userId, Context.ConnectionId);
        await base.OnConnectedAsync();
    }

    public override async Task OnDisconnectedAsync(Exception? ex)
    {
        await presence.DisconnectedAsync(Context.UserIdentifier!, Context.ConnectionId);
        await base.OnDisconnectedAsync(ex);
    }

    public async Task SendMessage(Guid conversationId, Guid clientMsgId, string text)
    {
        var userId = Context.UserIdentifier!;
        if (string.IsNullOrWhiteSpace(text) || text.Length > 4000)
            throw new HubException("Invalid message");
        if (!await chat.IsMemberAsync(conversationId, userId))
            throw new HubException("Not a member");               // never trust the client

        // 1) persist + assign seq (idempotent on clientMsgId)  2) then broadcast
        Message saved = await chat.AppendAsync(conversationId, userId, clientMsgId, text);

        await Clients.Caller.SendAsync("MessageAck", clientMsgId, saved.Seq);
        await Clients.OthersInGroup($"c:{conversationId}").SendAsync("ReceiveMessage", saved);
        await chat.PublishAsync(saved);        // -> Service Bus: push for offline members
    }

    public Task MarkRead(Guid conversationId, long upToSeq) =>
        chat.AdvanceReadWatermarkAsync(conversationId, Context.UserIdentifier!, upToSeq);
}

// Program.cs
builder.Services.AddSignalR().AddAzureSignalR();     // or .AddStackExchangeRedis(redisConn)
app.MapHub<ChatHub>("/hubs/chat");
```

**Scale-out.** A group lives on one server's memory, so with several servers a message sent via server A must reach connections on server B. Two options:

| | Redis backplane | Azure SignalR Service |
|---|---|---|
| What it does | Every server publishes/subscribes to Redis channels | Clients connect to the managed service; your servers hold only a few connections to it |
| Connection limits | Per-server memory and sockets | Service scales to many thousands of connections per unit |
| Ops | You run and size Redis; sticky sessions needed if WebSockets are not forced | Managed; fewer moving parts; cost per unit |
| Package | `Microsoft.AspNetCore.SignalR.StackExchangeRedis` | `Microsoft.Azure.SignalR` |

With self-hosted servers, either force WebSockets with `SkipNegotiation = true` or enable sticky sessions, because SignalR's negotiate and the follow-up transport request must reach the same server for non-WebSocket transports.

#### 6b. Message persistence and ordering

Rule: **persist first, then deliver**. If you broadcast first and the DB write fails, recipients see a message that does not exist.

- **Ordering:** wall-clock timestamps from different servers disagree. Assign a **monotonic per-conversation sequence** at write time (`seq`). In Cosmos use a transactional batch per partition or a stored procedure; with SQL, `UPDATE Conversations SET LastSeq = LastSeq + 1 OUTPUT inserted.LastSeq`. Clients sort by `seq`; a missing number means "gap, fetch `afterSeq`".
- **Idempotency:** the client generates `clientMsgId` before sending and retries on timeout. The server dedups on `(conversationId, clientMsgId)`, so a retry returns the original `seq`.
- **At-least-once** delivery to devices plus client dedup by `messageId`.

```csharp
public async Task<Message> AppendAsync(Guid convId, string userId, Guid clientMsgId, string text)
{
    var existing = await _messages.FindByClientIdAsync(convId, clientMsgId);
    if (existing is not null) return existing;                  // retry: same answer

    long seq = await _conversations.NextSeqAsync(convId);       // atomic increment
    var msg = new Message(convId, seq, Ulid.NewUlid().ToString(), userId,
                          clientMsgId, text, DateTime.UtcNow);
    await _messages.InsertAsync(msg);                           // unique (convId, seq)
    return msg;
}
```

(`Ulid` is from the `Ulid` NuGet package; any time-sortable ID works.)

#### 6c. Presence and heartbeat

SignalR already pings: server `KeepAliveInterval` default 15 s, client `ServerTimeout` default 30 s. For presence, store it in Redis with a TTL so crashed servers cannot leave users "online" forever.

```csharp
public sealed class RedisPresenceService(IConnectionMultiplexer mux) : IPresenceService
{
    private static readonly TimeSpan Ttl = TimeSpan.FromSeconds(60);

    public async Task ConnectedAsync(string userId, string connId)
    {
        var db = mux.GetDatabase();
        await db.SetAddAsync($"conns:{userId}", connId);           // multi-device
        await db.KeyExpireAsync($"conns:{userId}", Ttl);
        await db.StringSetAsync($"presence:{userId}", "online", Ttl);
    }

    public async Task HeartbeatAsync(string userId)                 // called every ~25 s
    {
        var db = mux.GetDatabase();
        await db.KeyExpireAsync($"presence:{userId}", Ttl);
        await db.KeyExpireAsync($"conns:{userId}", Ttl);
    }

    public async Task DisconnectedAsync(string userId, string connId)
    {
        var db = mux.GetDatabase();
        await db.SetRemoveAsync($"conns:{userId}", connId);
        if (await db.SetLengthAsync($"conns:{userId}") == 0)        // last device gone
            await db.StringSetAsync($"lastseen:{userId}", DateTime.UtcNow.ToString("O"));
        // presence key simply expires; avoids flapping offline/online on quick reconnects
    }

    public async Task<bool> IsOnlineAsync(string userId) =>
        await mux.GetDatabase().KeyExistsAsync($"presence:{userId}");
}
```

Do not broadcast presence to everyone. Send changes only to people who have the user in an open conversation list (subscribe-on-view), otherwise presence fan-out is O(contacts) on every flap.

#### 6d. Delivery receipts and offline push

| State | Trigger |
|---|---|
| Sent | Server persisted the message and sent `MessageAck` to the sender |
| Delivered | Recipient device received `ReceiveMessage` and called back (or advanced `LastDeliveredSeq`) |
| Read | Recipient opened the conversation, `MarkRead(conv, upToSeq)` |

Store receipts as **watermarks per member** (`LastReadSeq`), not a row per message per recipient: a group of 500 would otherwise create 500 rows per message. "Read by all" = `MIN(LastReadSeq)`.

**Offline users:** after persisting, check `IsOnlineAsync(recipient)`. If offline, enqueue a push through the *Notification Service* (design 2) with a collapse key per conversation. On reconnect the client calls `GET .../messages?afterSeq=<lastKnownSeq>` to sync; SignalR is the fast path, REST is the source of truth.

### 7. Scaling, failure modes, trade-offs

- **Hot groups/channels** (100K members): switch to pull-based fan-out or topic-per-channel with client-side paging, not per-recipient writes.
- **Reconnect storms** after a deploy: stagger restarts, use client exponential backoff with jitter (`withAutomaticReconnect([0, 2000, 10000, 30000])`).
- **Server crash:** clients reconnect, rejoin groups in `OnConnectedAsync`, and gap-fill with `afterSeq`. No state is only in server memory.
- **Poison/abuse:** per-user rate limit in the hub (`SendMessage` is a normal method; use a token bucket per `UserIdentifier`), max message size, content moderation hook.
- **Trade-off:** SignalR (WebSocket with fallbacks, groups, .NET ecosystem) vs raw WebSockets (less overhead, you build reconnect/groups yourself). For .NET teams SignalR is the right default.

:::tip How to present this in 45 minutes
Lead with "persist first, ordering via per-conversation sequence, receipts as watermarks". Draw the SignalR-to-backplane picture explicitly; interviewers love asking "what if I have two servers?". Mention that SignalR is the transport, not the system of record.
:::

:::q Follow-up 1: Two servers - how does user A on server 1 reach user B on server 2?
Through the backplane. With Redis, server 1 publishes the group message to Redis and every server forwards it to its local connections in that group; with Azure SignalR Service the managed service holds the connections so routing is internal. Either way the hub code is unchanged.
:::

:::q Follow-up 2: How do you prevent duplicates when a mobile client retries on a bad network?
The client sends a `clientMsgId` generated once per message. The server treats `(conversationId, clientMsgId)` as a unique key and returns the existing `seq` on retry. Clients also dedup incoming `messageId`s.
:::

:::q Follow-up 3: How would you add end-to-end encryption?
Clients hold keys (Signal protocol/double ratchet); the server stores and relays opaque ciphertext plus metadata. Consequences: no server-side search or moderation of content, key distribution/device management complexity, and push previews cannot show text. State the trade-off rather than promising it is easy.
:::

