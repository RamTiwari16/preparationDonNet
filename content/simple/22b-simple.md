### What MCP is and why it exists

**In simple words:** *MCP* (Model Context Protocol) is an open standard for connecting AI apps to tools and data. A system exposes an *MCP server* once, and any AI app that speaks MCP (the *host*, like VS Code, Copilot, Claude or your own agent) can use it. A server can offer *tools* (actions), *resources* (read-only data) and *prompts* (reusable templates). Messages travel as JSON-RPC over `stdio` for local servers or Streamable HTTP for remote ones.

**Real-life example:** MCP is like USB-C for AI tools. One standard plug, so any device works with any charger, without a special cable for each pair.

**Interview question:** What is MCP and what problem does it solve?

**Simple answer:** MCP is an open protocol for exposing tools, resources and prompts to AI hosts through MCP servers. Without it, every assistant needs custom code for every system, which grows as M times N. With MCP, each system builds one server and each assistant builds one client. Anthropic introduced it in late 2024, and it is now widely used, including by Microsoft.

### MCP server and client in C#

**In simple words:** The official C# SDK lets you build an MCP server in ASP.NET Core. You mark a class with `[McpServerToolType]` and its methods with `[McpServerTool]`, and add descriptions so the model knows when to use them. Remote servers must require authentication. On the client side, the server's tools appear as `AIFunction`s, so you can pass them to any `IChatClient` or agent. Watch for risks like *tool poisoning* (a malicious tool description that hides instructions).

**Real-life example:** You open a shop counter (server) with a clear menu board (tool descriptions). Any customer (AI app) can read the menu and order.

**Interview question:** How do you build a secure MCP server in .NET?

**Simple answer:** I use `AddMcpServer().WithHttpTransport().WithToolsFromAssembly()` and map it with `MapMcp` plus `RequireAuthorization()`. Inside each tool, I take the user's identity from the token, not from the tool arguments, and check ownership. I also use trusted, pinned servers, least privilege, approval for side effects, and I log every call.

```csharp
builder.Services.AddMcpServer().WithHttpTransport().WithToolsFromAssembly();
app.MapMcp("/mcp").RequireAuthorization();
```

### Where they fit

**In simple words:** Microsoft has several AI libraries for .NET. `Microsoft.Extensions.AI` gives simple common interfaces, `IChatClient` and `IEmbeddingGenerator`, plus middleware for tools, caching and telemetry. `Microsoft.Extensions.VectorData` gives a common API for vector stores. *Semantic Kernel* is an older, larger SDK with plugins, prompt templates and filters. *Microsoft Agent Framework* is the newer successor to Semantic Kernel agents and AutoGen, made for agents and multi-agent workflows.

**Real-life example:** It is like kitchen tools. A good knife (Microsoft.Extensions.AI) handles most jobs. A full food processor (Agent Framework) is for big, complex meals.

**Interview question:** Semantic Kernel, Microsoft.Extensions.AI or Agent Framework — which would you pick today?

**Simple answer:** For simple features like chat, RAG or a few tools, I use `Microsoft.Extensions.AI` directly, because it is small and provider-neutral. For agents and multi-agent workflows, I use Microsoft Agent Framework, the successor to Semantic Kernel agents and AutoGen. In an existing Semantic Kernel codebase, I keep SK and plan migration only where it pays off.

### Semantic Kernel core concepts

**In simple words:** In Semantic Kernel (SK), the *Kernel* is a container that holds AI services, plugins and filters. A *plugin* is a named group of functions, like "Orders". A *KernelFunction* is either a C# method marked `[KernelFunction]` or a prompt template. With `FunctionChoiceBehavior.Auto()`, the model can call plugin functions on its own. *Filters* are middleware around function calls and prompts, used for logging, approval and hiding personal data.

**Real-life example:** The Kernel is like a toolbox. Plugins are the labelled drawers, functions are the tools, and filters are the safety checks before you use a tool.

**Interview question:** What are Semantic Kernel plugins and filters?

**Simple answer:** Plugins are named groups of `KernelFunction`s, either C# methods or prompt templates, that the model can call through function calling. Filters are middleware around function invocation, prompt rendering and automatic tool calls. I use filters for logging, human approval, PII redaction and guardrails. The old planners are deprecated and replaced by native function calling.

```csharp
kb.Plugins.AddFromType<OrderPlugin>("Orders");
var settings = new OpenAIPromptExecutionSettings
    { FunctionChoiceBehavior = FunctionChoiceBehavior.Auto() };
```

### Microsoft Agent Framework in one snippet

**In simple words:** Microsoft Agent Framework is built on `Microsoft.Extensions.AI`. An `AIAgent` wraps a chat client and takes instructions and tools. It keeps the conversation state in an `AgentSession`, which is its short-term memory. *Workflows* connect several agents and functions in a clear graph: one after another, in parallel, handoff, or with human approval steps. The API changed between previews and 1.0, so check current docs.

**Real-life example:** An agent is like a trained employee with a job description (instructions) and a set of tools. The session is their notebook for the current customer.

**Interview question:** How do you create a simple agent with Microsoft Agent Framework?

**Simple answer:** I create a `ChatClientAgent` from an `IChatClient`, give it instructions, a name and tools built with `AIFunctionFactory.Create`. I create an `AgentSession` to keep conversation state, then call `RunAsync` with the user's message. For multi-step or multi-agent processes, I connect agents with workflows.

```csharp
AIAgent agent = new ChatClientAgent(chatClient,
    instructions: "You are ShopX support. Use tools for order data.",
    tools: [AIFunctionFactory.Create(orderTools.GetOrderStatus)]);
AgentSession session = await agent.CreateSessionAsync();
```

### Resources, deployments and endpoints

**In simple words:** Azure OpenAI runs OpenAI models inside Azure, with Azure security and compliance. It is part of Azure AI Foundry (now also called Microsoft Foundry). You create a *resource* in a region, which gives you an *endpoint* URL. Then you create a *deployment*: a chosen model and version under a name you pick. Your code calls the deployment name, so you can upgrade the model behind it in a controlled way.

**Real-life example:** The resource is a restaurant branch with an address. A deployment is a dish on its menu with your own name, like "chef's special". You can change the recipe behind that name when you are ready.

**Interview question:** What is a deployment in Azure OpenAI, and what deployment types exist?

**Simple answer:** A deployment is a specific model and version published under a name I choose; my code calls that name. Types include Standard (regional, pay per token), Global Standard (routed across regions with higher limits), Data Zone (data stays in the EU or US), Provisioned (reserved capacity for steady latency) and Batch (cheaper, runs over hours). Microsoft does not use my prompts to train the base models.

### API keys vs managed identity

**In simple words:** You can call Azure OpenAI with an *API key* (a static secret) or with *managed identity* through Microsoft Entra ID (Azure gives your app an identity, so there is no secret to store). Managed identity rotates tokens automatically, supports fine-grained roles, and shows who called in the logs. Use the *Cognitive Services OpenAI User* role for inference only. Never call Azure OpenAI from the browser with a key.

**Real-life example:** An API key is like a shared office key that anyone can copy. Managed identity is like a personal staff badge that is checked at the door and logged.

**Interview question:** API key or managed identity for Azure OpenAI?

**Simple answer:** Managed identity with Entra ID and the least-privileged role, Cognitive Services OpenAI User. There is no secret to leak or rotate, each call is audited per identity, and I can turn off key auth. I use keys only for local experiments, stored in Key Vault. In code, I pass `DefaultAzureCredential` to `AzureOpenAIClient`.

```csharp
var client = new AzureOpenAIClient(new Uri(endpoint), new DefaultAzureCredential());
```

### Content filters, quotas (TPM) and regions

**In simple words:** Azure OpenAI checks prompts and answers with *content filters* for hate, sexual content, violence and self-harm, plus *Prompt Shields* for attacks. A blocked prompt returns HTTP 400, and a filtered answer ends with `finish_reason = content_filter`. *TPM* (tokens per minute) is your throughput quota per deployment and region. Going over it returns HTTP 429 with a `Retry-After` header. Models and versions differ by region, and old versions are retired on a schedule.

**Real-life example:** TPM is like a water pipe with a fixed width. If you try to push more water through per minute, it backs up and you must wait.

**Interview question:** What is TPM and what happens when you exceed it?

**Simple answer:** TPM is tokens per minute, the throughput quota per deployment per region, which also implies a requests-per-minute limit. Going over returns 429 with `Retry-After`. I handle it with backoff, realistic `MaxOutputTokens` (because the quota counts it), queuing, more quota, Global Standard, several deployments behind API Management, or provisioned throughput.

### DI registration and configuration

**In simple words:** You register an `IChatClient` in dependency injection (DI) and inject it like any other service. With `AddChatClient(...)` you build a *pipeline* by adding middleware like caching, function calling, usage tracking, telemetry and logging. Each `Use...` wraps the next one, so the order matters. You can also register a second, cheaper model as a *keyed* service. Keep endpoint and deployment names in configuration.

**Real-life example:** It is like airport checks in a line: ticket, then security, then gate. If the ticket check says you are already boarded (a cache hit), you skip the rest.

**Interview question:** How do you register an LLM client in ASP.NET Core?

**Simple answer:** I create one `AzureOpenAIClient` with managed identity and register `AddChatClient` with a middleware pipeline: cache, function invocation, usage tracking, OpenTelemetry and logging. The order matters; with the cache first, a hit skips tools, tracking and the network call. For simple tasks I add a keyed client for a smaller model.

```csharp
builder.Services.AddChatClient(sp => client.GetChatClient("chat-prod").AsIChatClient())
    .UseDistributedCache()
    .UseFunctionInvocation()
    .UseOpenTelemetry();
```

### Resilience

**In simple words:** *Resilience* means your app keeps working when the AI service is slow or failing. Set a total timeout per call and pass the request's `CancellationToken`. The Azure and OpenAI SDKs already retry short errors and 429, so do not add a second retry layer that multiplies load. Use a fallback deployment or smaller model, and show a friendly "AI unavailable" message instead of breaking the main feature. Send long jobs to a queue.

**Real-life example:** If the coffee machine in a café breaks, the café still sells tea and cake. It does not close the whole shop.

**Interview question:** How do you make an LLM integration resilient?

**Simple answer:** I set timeouts and pass cancellation tokens, so aborted requests stop generation. I rely on the SDK's built-in retries and avoid double retry layers, and I never blindly retry a stream halfway through. I add a fallback deployment or model, degrade gracefully when the AI is down, and move long jobs to a background queue that returns `202 Accepted`.

### Caching responses

**In simple words:** Caching saves money and time by reusing AI answers. An *exact-match cache* reuses an answer when the full prompt and options are identical. A *semantic cache* reuses an answer when a new question means almost the same as an earlier one; it hits more often but can answer a slightly different question. You can also cache embeddings by content hash. Never share cached answers between users or tenants when the prompt contains their data.

**Real-life example:** A help desk keeps a list of answers to frequently asked questions. They reuse the answer instead of researching it again, but never share one customer's private details with another.

**Interview question:** How would you cache LLM responses safely?

**Simple answer:** I use an exact-match cache, `UseDistributedCache()`, for repeated identical prompts with temperature 0. A semantic cache gives more hits, but I use a strict similarity threshold and only for non-personal content. I cache embeddings by content hash. When prompts contain user or tenant data, I include them in the cache key or do not cache at all.

### Per-user rate limiting, cost and token tracking

**In simple words:** AI calls cost money per token, so you must control and track usage. *Rate limiting* per user limits how many requests each person can make, using ASP.NET Core's rate limiter keyed by user id. A *token budget* limits how many tokens each user can use per day. You can build it as `IChatClient` middleware that checks the budget before the call and records tokens after it. Store tokens per request with model, user, tenant and feature, and alert on unusual cost.

**Real-life example:** A mobile phone plan gives each person a monthly data limit and shows how much they have used.

**Interview question:** How do you control and track the cost of LLM calls per user?

**Simple answer:** I add a per-user rate limit with `AddRateLimiter`, partitioned by the user's id claim. I write a `DelegatingChatClient` that checks a daily token budget before each call and records input and output tokens afterwards. I report cost by feature, model and tenant, and alert on spikes. `UseOpenTelemetry()` also gives standard token-usage metrics.

### Logging prompts safely and handling secrets

**In simple words:** By default, log only *metadata* about AI calls, not the content. That means model name, prompt version, token counts, latency, tools called, document ids and trace id. Prompts and answers often contain personal or confidential data. If you must store them, use a separate store with redaction, short retention and limited access. Keep `EnableSensitiveData = false` in telemetry. Treat the system prompt as public, so never put secrets in it.

**Real-life example:** A doctor's appointment log records the time and the doctor's name, but not your private medical details.

**Interview question:** What should you log for LLM calls, and what should you avoid?

**Simple answer:** I log metadata: model, prompt version, token counts, latency, finish reason, tool names, retrieved document ids and the trace id. I avoid logging prompt and answer text by default, because it can contain personal data. If needed for debugging, I store it separately with redaction and short retention. Secrets go through managed identity or Key Vault, never into prompts or config files.

### AI-powered API design examples

**In simple words:** Design AI endpoints like any other API. Check input length, require login, apply per-user rate limits and set timeouts. Wrap user text in tags and tell the model it is data, not instructions. Use structured output, and always validate it, for example against an allowed list of categories. Return the model name and prompt version for traceability, and use `202 Accepted` with a job id for long work.

**Real-life example:** A bank form has fixed fields, length limits and checks before it is accepted. A clerk also checks the result before acting on it.

**Interview question:** How would you design a "classify support ticket" API that uses an LLM?

**Simple answer:** I make an authenticated, rate-limited POST endpoint that validates the input length. I put the ticket inside `<ticket>` tags and ask for structured output, `GetResponseAsync<ClassifyResult>`, at temperature 0, maybe with a smaller model. I validate the category against an allowed list and return "Unknown" otherwise. I also return the model and prompt version.

### Testing with a fake IChatClient

**In simple words:** Your code depends on the `IChatClient` interface, so in unit tests you can swap in a *fake* client. The fake returns fixed answers, so tests are fast, free, offline and always give the same result. Test what your code controls: how the prompt is built, how output is parsed and validated, tool permission checks, and error handling like a 429. Model quality is measured separately with evaluation suites.

**Real-life example:** Pilots train in a flight simulator. It behaves in a known way, so they can practise safely without a real plane.

**Interview question:** How do you unit test code that calls an LLM?

**Simple answer:** I depend on `IChatClient` and use a fake that returns canned responses. Then I assert on prompt building, parsing, validation, tool authorisation and error handling. In integration tests I replace the real client using `WebApplicationFactory` and `ConfigureTestServices`. Model quality is tested separately with an evaluation suite in CI.

```csharp
var fake = new FakeChatClient(_ => """{"category":"Lottery","confidence":0.99}""");
var result = await new TicketClassifier(fake).ClassifyAsync("I won a prize!");
Assert.Equal("Unknown", result.Category);
```
