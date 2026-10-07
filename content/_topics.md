# .NET Full Stack Developer — Complete Interview Topics (SOURCE OUTLINE)

This is the source-of-truth outline. Every bullet below must be covered (grouping closely-related bullets under one heading is fine).
Target audience: a developer with 2–5 years of experience preparing for .NET Full Stack interviews.

## 1. C# — Core & Advanced
### C# Fundamentals
Data types; Value type vs Reference type; Variables and constants; Type casting; Boxing and Unboxing; var, dynamic, object; Nullable types; String vs StringBuilder; const vs readonly; ref, out, in; Static classes and static members
### OOP Concepts
Class and Object; Encapsulation; Abstraction; Inheritance; Polymorphism; Method Overloading; Method Overriding; Abstract class; Interface; Abstract class vs Interface; Composition vs Inheritance; SOLID principles
### Collections
Array; ArrayList; List; Dictionary; HashSet; Queue; Stack; LinkedList; IEnumerable; ICollection; IList; IDictionary; IEnumerable vs IQueryable
### LINQ
LINQ basics; Where; Select; SelectMany; OrderBy; ThenBy; GroupBy; Join; Any; All; Contains; First; FirstOrDefault; Single; SingleOrDefault; Count; Sum; Average; Max; Min; Deferred execution; LINQ to Objects; LINQ with Entity Framework
### Exception Handling
try; catch; finally; throw; Custom exceptions; Global exception handling; Exception middleware; Logging exceptions; Best practices
### Multithreading / Async
Thread; Task; async/await; Task vs Thread; Task.WhenAll; Task.WhenAny; CancellationToken; Parallel programming; Race conditions; Deadlocks; Thread safety; Lock; Semaphore/SemaphoreSlim; Concurrent collections
### Design Patterns
Singleton; Factory; Abstract Factory; Repository; Unit of Work; Strategy; Observer; Adapter; Decorator; Dependency Injection; Mediator; CQRS

## 2. .NET / ASP.NET Core
### .NET Versions
Differences and features of: .NET 6, .NET 7, .NET 8, .NET 9, .NET 10; .NET Framework vs modern .NET
### ASP.NET Core
Application lifecycle; Configuration; appsettings.json; Environment-specific configuration; Program.cs; Dependency Injection; Service lifetime (Singleton, Scoped, Transient); Middleware; Routing; Controllers; Minimal APIs; Filters; Model Binding; Model Validation; Action Results; DTOs; ViewModels
### Web API
REST principles; HTTP methods (GET, POST, PUT, PATCH, DELETE); HTTP status codes; Request/Response; Headers; Query parameters; Route parameters; Request body; Content negotiation; JSON serialization; Swagger/OpenAPI; API versioning; Pagination; Sorting; Filtering; API validation
### Middleware
How to create custom middleware. Examples: Authentication middleware; Exception middleware; Logging middleware; Request/response middleware; Correlation ID middleware
### Filters
Authorization Filter; Action Filter; Result Filter; Exception Filter; Resource Filter; Filter execution order; Custom filters

## 3. Dependency Injection (very important)
What is Dependency Injection?; Why DI?; IoC; Constructor Injection; Property Injection; Method Injection; Singleton; Scoped; Transient; Service registration; AddSingleton; AddScoped; AddTransient
Common scenario: Why should DbContext generally be Scoped? Explain with a real-world API example.

## 4. Authentication & Authorization
### Authentication
Authentication vs Authorization; JWT; Access Token; Refresh Token; Claims; Roles; Policies; Cookies; OAuth 2.0; OpenID Connect; SSO
### ASP.NET Core Security
[Authorize]; [AllowAnonymous]; Role-based authorization; Policy-based authorization; JWT Bearer authentication; Token validation; CORS; CSRF; XSS; SQL Injection; HTTPS; Secret management

## 5. Entity Framework Core
### EF Core Fundamentals
DbContext; DbSet; Entity; Model; Relationships; Migrations; Code First; Database First; Fluent API; Data Annotations
### Relationships
One-to-One; One-to-Many; Many-to-Many; Foreign Keys; Navigation Properties
### Querying
LINQ; Include; ThenInclude; Projection; Select; Filtering; Sorting; Pagination
### Tracking (very important)
Tracking; AsNoTracking(); AsNoTrackingWithIdentityResolution(); Change Tracker; When to use tracking; When to use AsNoTracking
### EF Performance
N+1 query problem; Eager loading; Lazy loading; Explicit loading; Projection; Query optimization; Compiled queries; Indexes; Batch operations

## 6. SQL Server
### SQL Fundamentals
SELECT; INSERT; UPDATE; DELETE; WHERE; GROUP BY; HAVING; ORDER BY; DISTINCT; CASE; Subqueries; CTE
### Joins (must know extremely well)
INNER JOIN; LEFT JOIN; RIGHT JOIN; FULL OUTER JOIN; CROSS JOIN; SELF JOIN
### SQL Objects
Tables; Views; Stored Procedures; Functions; Triggers; CTE; Temporary tables; Table variables; Table-valued parameters
### Keys
Primary Key; Foreign Key; Composite Key; Unique Key; Candidate Key
### Indexes
Clustered Index; Non-clustered Index; Composite Index; Covering Index; Unique Index; Index fragmentation; Index seek; Index scan
### Stored Procedures
Input parameters; Output parameters; Transactions; Error handling; Dynamic SQL; Performance optimization; TVP
### Window Functions (very important)
ROW_NUMBER(); RANK(); DENSE_RANK(); LEAD(); LAG(); SUM() OVER; COUNT() OVER; PARTITION BY
### SQL Performance
Execution plan; Query optimization; Index optimization; Avoiding unnecessary joins; SARGability; Deadlocks; Blocking; Transactions; Isolation levels; Normalization; Denormalization

## 7. Coding / DSA
### Arrays & Strings
Reverse an array; Reverse a string; Find duplicate elements; Find missing number; Find second largest; Find maximum/minimum; Two Sum; Remove duplicates; Character frequency; Palindrome; Anagram
### Hashing
Dictionary/HashMap; Frequency counting; Two Sum; Duplicate detection; HashSet problems
### Stack & Queue
Implement Stack; Implement Queue; Balanced parentheses; Next greater element; Queue using Stack; Stack using Queue
### Linked List
Reverse linked list; Detect cycle; Find middle node; Merge two lists; Remove duplicate nodes
### Trees
Binary Tree; Binary Search Tree; Tree traversal (Inorder, Preorder, Postorder, Level order); Height of tree; Search in BST
### Graphs
BFS; DFS; Graph representation; Shortest path basics; Cycle detection
### Sorting
Bubble Sort; Selection Sort; Insertion Sort; Merge Sort; Quick Sort
### Searching
Linear Search; Binary Search
### Dynamic Programming
Fibonacci; Climbing stairs; Knapsack basics; Longest common subsequence; Coin change
### Greedy Algorithms
Activity selection; Fractional knapsack; Scheduling problems

## 8. Frontend — JavaScript (for React / Angular)
### JavaScript Fundamentals
var, let, const; Data types; Functions; Arrow functions; Scope; Hoisting; Closures; Callbacks; Promises; Async/Await; Event loop; Event bubbling; Event capturing; DOM; ES6+
### Important ES6 Topics
Destructuring; Spread operator; Rest operator; Template literals; Modules; Classes; Map; Filter; Reduce; Optional chaining; Nullish coalescing

## 9. React
### Core
Components; JSX; Props; State; Functional components; Component lifecycle
### Hooks
useState; useEffect; useContext; useMemo; useCallback; useRef; Custom Hooks
### State Management
Context API; Redux; Redux Toolkit; Global vs local state
### API Integration
REST API; Axios; Fetch; HTTP interceptors; Error handling; Loading states
### React Performance
Memoization; React.memo; useMemo; useCallback; Lazy loading; Code splitting

## 10. Angular
Components; Modules; Standalone components; Services; Dependency Injection; Directives; Pipes; Routing; Route Guards; Lazy Loading; HTTP Client; Interceptors; Reactive Forms; Template-driven Forms; RxJS; Observable; Subject; BehaviorSubject; switchMap; mergeMap; forkJoin; debounceTime; catchError; Authentication; JWT; MSAL/SSO; State management; Signals; Lifecycle hooks

## 11. Azure Cloud
Compute: Azure App Service; Azure VM; Azure Functions; Container Apps; AKS
Storage: Blob Storage; Queue Storage; Table Storage; File Storage
Database: Azure SQL; Cosmos DB
Networking: Virtual Network; Load Balancer; Application Gateway; API Management; CDN
Monitoring: Application Insights; Azure Monitor; Log Analytics
Security: Azure Key Vault; Managed Identity; Azure AD / Microsoft Entra ID; RBAC

## 12. Azure DevOps / CI-CD
Git; Branching strategies; Pull Requests; Merge conflicts; Azure Repos; Azure Pipelines; Build pipeline; Release pipeline; CI; CD; YAML pipelines; Environment variables; Secrets; Artifacts; Deployment approvals; Rollback; Blue-Green deployment; Canary deployment
Typical pipeline: Developer -> Git Push -> Build -> Unit Tests -> Code Quality -> Docker Build -> Artifact -> Deploy -> Azure

## 13. Docker
Container; Image; Dockerfile; Docker commands; Docker Compose; Volumes; Networks; Environment variables; Multi-stage Docker builds; Container registry; Dockerizing ASP.NET Core application

## 14. Kubernetes
Kubernetes architecture; Pod; Node; Cluster; Deployment; Service; ConfigMap; Secret; Namespace; Ingress; ReplicaSet; Horizontal Pod Autoscaler; Rolling deployment; Health checks; Liveness probe; Readiness probe

## 15. Microservices
### Fundamentals
Monolith vs Microservices; Microservice characteristics; Service boundaries; Database per service; Independent deployment
### Architecture
API Gateway; Service Discovery; Authentication; Communication between services; REST; gRPC; Event-driven architecture
### Messaging
RabbitMQ; Kafka; Azure Service Bus
### Resilience
Retry; Timeout; Circuit Breaker; Bulkhead; Rate Limiting
### Distributed Systems
Distributed transactions; Eventual consistency; CAP theorem; Idempotency; Saga pattern; Outbox pattern; Distributed locking

## 16. Caching
Why caching?; In-memory caching; Distributed caching; Redis; Cache-aside; Write-through; Write-behind; Cache expiration; Cache invalidation; Distributed cache in ASP.NET Core
Example flow: Client -> API -> Redis Cache -> SQL Server

## 17. System Design — HLD (High Level Design)
Requirements gathering; Functional requirements; Non-functional requirements; Scalability; Availability; Reliability; Performance; Security; Load balancing; Caching; Database selection; Message queues; Microservices; API Gateway; CDN; Monitoring
### Load Balancing
Load Balancer; Reverse Proxy; Horizontal scaling; Vertical scaling
### Database Design
SQL vs NoSQL; Normalization; Denormalization; Sharding; Replication; Read replicas; Partitioning

## 18. LLD — Low Level Design
Classes; Interfaces; Relationships; SOLID; Design patterns; UML; Class diagrams; Sequence diagrams; Object relationships
### Practice LLD Problems
Parking Lot; Library Management; ATM; E-commerce; Hotel Booking; Cab Booking; Notification Service; Payment System

## 19. Real-World System Design Problems
E-Commerce System (User -> API Gateway -> Auth Service -> Product Service -> Order Service -> Payment Service -> Database)
Notification Service (Email, SMS, Push notification, Queue, Retry, Dead-letter queue)
URL Shortener (Generate short URL, Redirect, Database, Cache, Scalability)
Chat Application (WebSocket, SignalR, Message queue, Online/offline status, Message persistence)
File Storage (Upload, Download, Blob Storage, Metadata, Access control)
Payment System (Payment Gateway, Transaction, Idempotency, Retry, Failure handling, Reconciliation)
Multi-Tenant Application (Tenant identification, Tenant isolation, Database strategy, Security, Configuration)

## 20. Performance Optimization (every layer)
C#: Async programming; Memory management; Efficient collections; Avoid unnecessary allocations
.NET: Async APIs; Response compression; Caching; Pagination; Connection pooling; Middleware optimization
EF Core: AsNoTracking; Projection; Avoid N+1; Proper indexes; Query optimization
SQL: Execution plans; Indexes; Stored procedure optimization; Query optimization; Avoid table scans
Frontend: Lazy loading; Code splitting; Caching; API optimization; Pagination; Debouncing

## 21. Observability & Monitoring
Logging; Structured logging; Serilog; Application Insights; Metrics; Tracing; Distributed tracing; Health checks; Alerts; Performance monitoring
Know the difference: Logs = What happened? Metrics = How much/how often? Traces = Where did the request travel?

## 22. AI / GenAI for .NET
### Fundamentals
LLM basics; Prompt engineering; Tokens; Embeddings; Vector databases
### RAG
Retrieval Augmented Generation; Document ingestion; Chunking; Embeddings; Vector search; Retrieval; Prompt construction; LLM response
### AI Agents
Agent architecture; Tools; Function calling; Memory; Planning; Multi-agent systems
### .NET + AI
Integrating LLM APIs with ASP.NET Core; AI-powered APIs; Semantic Kernel; Azure OpenAI; Vector databases; AI services

## 23. Managerial / HR / Client Round
### Project Questions
Explain your current project; What is your role; What architecture does your project use; Biggest challenge; Performance issue you solved; Technical decision you made; Why you chose a particular technology; How do you handle production issues
### Behavioral
Tell me about yourself; Why this company (e.g., Deloitte); Why are you changing; Where do you see yourself in 5 years; Biggest achievement; Biggest failure; Strengths; Weaknesses; How do you handle pressure; How do you handle conflict; How do you work with a difficult team member
### Client Communication
Explain a technical issue to a non-technical client; What do you do when requirements are unclear; What if the client changes requirements near release; How do you handle an unhappy client

## 24. Coding Questions You Should Practice (solve in C#, with complexity)
Easy: 1 Reverse string; 2 Reverse array; 3 Palindrome; 4 Fibonacci; 5 Factorial; 6 Prime number; 7 Second largest number; 8 Remove duplicates; 9 Count characters; 10 Find missing number
Medium: 11 Two Sum; 12 Three Sum; 13 Anagram; 14 Merge sorted arrays; 15 Binary search; 16 Sliding window; 17 Longest substring (without repeating chars); 18 Valid parentheses; 19 Reverse linked list; 20 Detect linked-list cycle; 21 Tree traversal; 22 BFS; 23 DFS; 24 Top K frequent elements; 25 Merge intervals

## 25. SQL Coding Questions (T-SQL, with sample tables + data + solution + explanation)
Second highest salary; Nth highest salary; Duplicate records; Delete duplicate records; Employees without department; Department-wise highest salary; Top 3 salaries per department; Employees earning more than manager; Find missing IDs; Running total; Rank employees; Find consecutive records; Find duplicate transactions; Latest record for each customer; Monthly sales report
Master: JOIN; GROUP BY; HAVING; CTE; Subquery; Window Functions; ROW_NUMBER; RANK; DENSE_RANK; LEAD; LAG; Indexes; Stored Procedures; Transactions; Execution Plans

## 26. Preparation Priority (handled by the site owner, not by content agents)
