### System Design Interview Approach

**In simple words:** In a system design interview, you design a large system, like an online shop, in about 45 minutes. There is no single right answer. The interviewer checks how you think: do you ask questions, make sensible choices and explain trade-offs? Use the same 7 steps every time: (1) agree the requirements, (2) estimate the size, (3) define the API, (4) design the data model, (5) draw the high-level design, (6) go deep on the 2 hardest parts, (7) discuss scaling, failures and trade-offs. Finish with a short summary. All numbers are rough guesses, so say your assumptions aloud.

**Real-life example:** Building a house: first you ask the family what they need, then count rooms and budget, then draw the plan. Next you check the hard parts, like plumbing and the roof. Finally you plan for extensions and emergencies.

**Interview question:** How do you approach a system design interview?

**Simple answer:** I follow a fixed order. First I ask questions and write the functional and non-functional requirements. Then I do quick maths for users, requests per second and storage, and I define the main APIs and tables. Next I draw the main boxes and walk one request through them. I spend most of the remaining time on the two hardest parts. Then I discuss bottlenecks, failures and what changes at 10 times the traffic.

### Design 1: E-Commerce System

**In simple words:** An online shop where users browse products, fill a cart, check out and pay. The main parts are: an API gateway (the front door that checks login and limits traffic), a Catalog service with a cache and a search index, a cart in Redis, an Order service that runs checkout, and Payment and Inventory services. Each service owns its own database, and they talk through events on a message queue. Browsing must be fast; checkout and stock must be exactly correct.

**Real-life example:** A big supermarket: shelves anyone can look at (catalog), a trolley (cart), a checkout counter (order and payment), and a stock room that must never promise items it does not have.

**Interview question:** Design an e-commerce system.

**Simple answer:** Users mostly browse, about 100 reads for each write, so I cache the catalog in Redis and a CDN (servers near users) and use a separate search index. Checkout is the hard part. The Order service saves the order, then a saga (steps with undo actions) reserves stock, takes payment and confirms. If payment fails, the saga releases the stock. To stop overselling, one atomic SQL update checks and reserves the stock together. An idempotency key on checkout stops double orders. For flash sales, I add rate limits, keep stock counts in Redis and queue the orders.

### Design 2: Notification Service

**In simple words:** A shared service that other systems call to send email, SMS and push messages. The main parts are: a Notification API that checks the request, removes duplicates, reads user preferences and fills templates; separate queues for each channel and priority; workers that send through providers like SendGrid or Twilio; and a dead-letter queue for messages that keep failing. Callers do not wait for the send; they get "Queued" at once.

**Real-life example:** A post office: you drop letters in the box and leave. Urgent mail goes in a fast lane, the postman tries again if nobody is home, and undeliverable letters go to a special office.

**Interview question:** Design a notification service that sends email, SMS and push messages.

**Simple answer:** Producers call one API or publish an event. The API checks preferences and quiet hours, renders the template, and puts one message per channel on a queue. OTPs and marketing use separate queues, so a big campaign never delays an OTP. Workers retry temporary errors with growing waits plus jitter (a small random delay). Permanent errors, or too many failures, go to the dead-letter queue. Delivery is at-least-once, so a dedup key stops repeats. To scale, I add workers when queues grow and respect each provider's rate limit.

### Design 3: URL Shortener

**In simple words:** A service that turns a long link into a short one, like `sho.rt/abc1234`, and sends visitors on to the long link. The main parts are: a Create API that makes a unique short code, a database that maps code to long URL, a Redirect API, a cache in front of the database, and click analytics on the side. Reads are about 100 times more than writes, and redirects must be very fast.

**Real-life example:** A coat-check counter: you hand over your long coat and get a small numbered token. Later you show the token and get the right coat back at once.

**Interview question:** Design a URL shortener.

**Simple answer:** I give each new link a unique number from a counter, scramble it so codes are hard to guess, and convert it to base62 (digits plus small and capital letters). Seven characters give about 3.5 trillion codes, which is plenty. The code is the primary key, so duplicates are impossible. For a redirect, I check a small in-memory cache, then Redis, then the database. I return 302, not 301, so every click reaches us for analytics and links can expire. Click events go to a queue, so they never slow the redirect. The redirect API is stateless, so I just add more servers.

### Design 4: Chat Application

**In simple words:** A real-time chat app for one-to-one and group messages. The main parts are: live connections through SignalR (the .NET library for WebSockets), a stateless chat hub, a message store like Cosmos DB, Redis for online/offline status, and a queue that triggers push notifications for offline users. Messages must arrive in order, never get lost, and reach all of a user's devices.

**Real-life example:** A class monitor passing notes: the monitor first writes each note in a register with a number, then gives copies to everyone in the group. Absent friends read the missed notes from the register later.

**Interview question:** Design a real-time chat application.

**Simple answer:** Clients keep a WebSocket open to a SignalR hub. When a user sends a message, the server first saves it with a sequence number for that conversation, then sends it to the group. The sequence number keeps the order, and a client message id stops duplicates when the phone retries. With many servers, two users may be on different servers, so I use a Redis backplane or Azure SignalR Service to pass messages between them. Online status lives in Redis with an expiry time. Offline users get a push notification and fetch missed messages when they reconnect.

### Design 5: File Storage (Drive/Dropbox-style)

**In simple words:** A service to upload, download and share files, like an online drive. The main parts are: a File API that checks permissions and keeps metadata (name, owner, size, status) in SQL, Azure Blob Storage for the actual bytes, a virus-scan worker, and short-lived signed links (SAS URLs) for upload and download. The key idea is that big files never pass through your API servers.

**Real-life example:** A bank locker: the front desk checks your ID and gives you a key that works for a short time. You then go to the locker room yourself; the desk never carries your valuables.

**Interview question:** Design a file storage service like Google Drive or Dropbox.

**Simple answer:** The client asks the API to start an upload. The API checks the user and their quota, then returns a SAS URL that works for a few minutes, for one file only. The client uploads straight to Blob Storage in blocks, so a broken upload resumes with only the missing blocks. Files land in a quarantine container, get scanned for viruses, and only then become available. Downloads work the same way: check permission, then give a 5-minute read link. Blob Storage and a CDN carry the bytes, so the API stays small, and old files move to cheaper storage automatically.

### Design 6: Payment System

**In simple words:** A shop's payment service that charges customers through a payment provider (PSP) like Stripe or Razorpay. The main parts are: a Payment API with idempotency keys, a state machine (only allowed status changes), a webhook endpoint where the provider sends results, a double-entry ledger (every money movement written as equal debits and credits), and a nightly reconciliation job. The hard part is correctness, not traffic.

**Real-life example:** A shop's cash register with a receipt book: every payment gets a numbered receipt, nothing is erased, and at the end of the day the owner matches the book with the bank statement.

**Interview question:** Design a payment system.

**Simple answer:** Card numbers go straight from the browser to the provider, and we keep only a token. That keeps our PCI (card security rules) scope small. Every payment request has an idempotency key, so a retry returns the first result and never charges twice. Status changes follow a state machine, so duplicate or out-of-order webhooks do no harm. A timeout means "unknown", not "failed", so I ask the provider for the status instead of charging again. A daily reconciliation job compares our records with the provider's report. The volume is low, so I choose strong consistency in SQL over raw speed.

### Design 7: Multi-Tenant Application

**In simple words:** One application serving many customer companies (tenants), like an online invoicing product. The main parts are: a tenant catalog that knows each tenant's plan and database, middleware that finds the tenant on every request (from the subdomain or the login token), data isolation, per-tenant settings, and per-tenant rate limits. The worst possible bug is one tenant seeing another tenant's data.

**Real-life example:** An apartment building: everyone shares the building, lift and water supply, but each flat has its own lock. A very large family can rent a whole separate house.

**Interview question:** Design a multi-tenant SaaS application.

**Simple answer:** I find the tenant from the host name, then check that it matches the tenant claim in the user's token; if not, I reject the request. Every table has a `TenantId`, and an EF Core global query filter adds it to every query automatically. SQL Row-Level Security is a second guard, and every cache key starts with the tenant id. Small tenants share a database, while large or regulated tenants get their own; the catalog tells the app which one to use. Per-tenant rate limits stop one busy tenant from slowing the others.
