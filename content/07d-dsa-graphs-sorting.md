## Graphs

**Definition.** A *graph* is a set of vertices (nodes) connected by edges. Edges can be *directed* or *undirected*, and *weighted* or unweighted. A tree is a connected graph with no cycles.

**Why it matters.** Social networks, road maps, dependency graphs (NuGet packages, build order), workflows and microservice call graphs are all graphs. Interview graph problems reduce to a few templates: BFS, DFS, shortest path, cycle detection.

### Graph representation

| | Adjacency list | Adjacency matrix |
|---|---|---|
| Structure | array/dictionary of neighbour lists | `V x V` table, `m[u,v]` = edge/weight |
| Space | O(V + E) | O(V^2) |
| Is there an edge u-v? | O(degree(u)) | O(1) |
| Iterate neighbours of u | O(degree(u)) | O(V) |
| Best for | sparse graphs (most real graphs) | dense graphs, fast edge lookup, Floyd-Warshall |

```csharp
public class Graph
{
    private readonly List<int>[] _adj;
    public int VertexCount { get; }

    public Graph(int vertexCount)
    {
        VertexCount = vertexCount;
        _adj = new List<int>[vertexCount];
        for (int i = 0; i < vertexCount; i++) _adj[i] = new List<int>();
    }

    public void AddEdge(int from, int to, bool directed = false)
    {
        _adj[from].Add(to);
        if (!directed) _adj[to].Add(from);
    }

    public IReadOnlyList<int> Neighbors(int v) => _adj[v];
}

// Weighted adjacency list: each entry is (neighbour, weight).
public class WeightedGraph
{
    private readonly List<(int To, int Weight)>[] _adj;
    public int VertexCount => _adj.Length;

    public WeightedGraph(int vertexCount)
    {
        _adj = new List<(int, int)>[vertexCount];
        for (int i = 0; i < vertexCount; i++) _adj[i] = new List<(int, int)>();
    }

    public void AddEdge(int u, int v, int weight, bool directed = false)
    {
        _adj[u].Add((v, weight));
        if (!directed) _adj[v].Add((u, weight));
    }

    public IReadOnlyList<(int To, int Weight)> Edges(int v) => _adj[v];
}

// Adjacency matrix (undirected, unweighted).
static int[,] ToMatrix(int n, (int U, int V)[] edges)
{
    var m = new int[n, n];
    foreach (var (u, v) in edges) { m[u, v] = 1; m[v, u] = 1; }
    return m;
}
// Edges 0-1, 0-2, 1-3, 2-3 form a square:
//   adjacency list: 0:[1,2]  1:[0,3]  2:[0,3]  3:[1,2]
```

:::q Which representation do you pick and why?
Adjacency list by default: real graphs are sparse, and the list uses O(V+E) memory and makes "visit all neighbours" proportional to the degree. I pick a matrix only when the graph is small and dense, I need O(1) edge-existence checks, or the algorithm is naturally matrix based (Floyd-Warshall, transitive closure). For grids, the grid *is* the graph - neighbours are computed from `(row, col)` offsets.
:::

### Breadth-first search (BFS)

**Problem.** Visit every vertex reachable from a start vertex, level by level (nearest first).

**Intuition.** A queue gives FIFO order, so all vertices at distance 1 are processed before any at distance 2. Mark vertices as visited *when you enqueue them* so a vertex enters the queue only once - otherwise you will enqueue it repeatedly and cycles loop forever.

**Approach.**
1. Mark `start` visited and enqueue it.
2. Dequeue `v`, process it.
3. For each unvisited neighbour: mark visited, enqueue.
4. Repeat until the queue is empty.

```csharp
// O(V + E) time, O(V) space.
static List<int> Bfs(Graph g, int start)
{
    var order = new List<int>();
    var visited = new bool[g.VertexCount];
    var queue = new Queue<int>();
    visited[start] = true;                 // mark on ENQUEUE
    queue.Enqueue(start);
    while (queue.Count > 0)
    {
        int v = queue.Dequeue();
        order.Add(v);
        foreach (int w in g.Neighbors(v))
        {
            if (visited[w]) continue;
            visited[w] = true;
            queue.Enqueue(w);
        }
    }
    return order;
}

// Number of connected components in an undirected graph (restart BFS from unvisited nodes).
static int CountComponents(Graph g)
{
    var visited = new bool[g.VertexCount];
    int components = 0;
    for (int s = 0; s < g.VertexCount; s++)
    {
        if (visited[s]) continue;
        components++;
        var queue = new Queue<int>();
        visited[s] = true;
        queue.Enqueue(s);
        while (queue.Count > 0)
            foreach (int w in g.Neighbors(queue.Dequeue()))
                if (!visited[w]) { visited[w] = true; queue.Enqueue(w); }
    }
    return components;
}
// Square graph above: Bfs(g, 0) -> [0, 1, 2, 3]
```

**Complexity.** O(V + E) time, O(V) space for `visited` and the queue.

**Edge cases.** Disconnected graph (BFS from one start only reaches its component), self loops, a start vertex with no neighbours, empty graph.

### Depth-first search (DFS)

**Problem.** Explore as deep as possible along each branch before backtracking.

**Intuition.** Recursion (or an explicit stack) follows one path until it is stuck, then backs up. DFS is the engine behind cycle detection, topological sort, connected components, flood fill and backtracking.

```csharp
// Recursive: O(V + E) time, O(V) stack depth in the worst case.
static List<int> DfsRecursive(Graph g, int start)
{
    var order = new List<int>();
    var visited = new bool[g.VertexCount];
    void Visit(int v)
    {
        visited[v] = true;
        order.Add(v);
        foreach (int w in g.Neighbors(v))
            if (!visited[w]) Visit(w);
    }
    Visit(start);
    return order;
}

// Iterative with an explicit stack (avoids StackOverflow on deep graphs).
static List<int> DfsIterative(Graph g, int start)
{
    var order = new List<int>();
    var visited = new bool[g.VertexCount];
    var stack = new Stack<int>();
    stack.Push(start);
    while (stack.Count > 0)
    {
        int v = stack.Pop();
        if (visited[v]) continue;          // mark on POP for DFS
        visited[v] = true;
        order.Add(v);
        var neighbors = g.Neighbors(v);
        for (int i = neighbors.Count - 1; i >= 0; i--)   // reverse: same order as recursion
            if (!visited[neighbors[i]]) stack.Push(neighbors[i]);
    }
    return order;
}
// Square graph (0-1, 0-2, 1-3, 2-3): DfsRecursive(g, 0) -> [0, 1, 3, 2]
```

| | BFS | DFS |
|---|---|---|
| Data structure | queue | stack / recursion |
| Visits | nearest vertices first | deepest path first |
| Shortest path (unweighted) | yes | no |
| Memory | O(width of graph) | O(depth of graph) |
| Typical use | shortest path, level order, minimum steps | cycle detection, topological sort, components, backtracking, maze existence |

**Complexity.** O(V + E) time, O(V) space.

**Edge cases.** Disconnected graphs (loop over all vertices), very deep graphs (recursion limit - use the iterative version), directed vs undirected.

:::q BFS or DFS - how do you choose?
BFS when the question asks for the *shortest* number of steps in an unweighted graph or for level-by-level processing. DFS when you need to explore all possibilities, detect cycles, order dependencies (topological sort), or the answer lives deep in the graph. Memory differs too: BFS may hold a whole level, DFS holds one path.
:::

### Shortest path in an unweighted graph

**Problem.** Find the fewest edges from `src` to `dst` and return the path.

**Intuition.** BFS discovers vertices in order of increasing distance, so the first time you reach `dst` is via a shortest path. Store each vertex's `parent` when you discover it; walk the parents back from `dst` to rebuild the path.

```csharp
// O(V + E) time, O(V) space. Returns null if dst is unreachable.
static List<int>? ShortestPath(Graph g, int src, int dst)
{
    var parent = new int[g.VertexCount];
    Array.Fill(parent, -1);
    var visited = new bool[g.VertexCount];
    var queue = new Queue<int>();
    visited[src] = true;
    queue.Enqueue(src);
    while (queue.Count > 0)
    {
        int v = queue.Dequeue();
        if (v == dst) break;
        foreach (int w in g.Neighbors(v))
        {
            if (visited[w]) continue;
            visited[w] = true;
            parent[w] = v;
            queue.Enqueue(w);
        }
    }
    if (!visited[dst]) return null;
    var path = new List<int>();
    for (int v = dst; v != -1; v = parent[v]) path.Add(v);
    path.Reverse();
    return path;
}

// Same idea on a grid: 0 = open, 1 = wall; 4-directional moves.
static int ShortestPathGrid(int[,] grid, (int R, int C) start, (int R, int C) goal)
{
    int rows = grid.GetLength(0), cols = grid.GetLength(1);
    var dist = new int[rows, cols];
    for (int r = 0; r < rows; r++)
        for (int c = 0; c < cols; c++) dist[r, c] = -1;

    int[] dr = { 1, -1, 0, 0 }, dc = { 0, 0, 1, -1 };
    var queue = new Queue<(int R, int C)>();
    dist[start.R, start.C] = 0;
    queue.Enqueue(start);
    while (queue.Count > 0)
    {
        var (r, c) = queue.Dequeue();
        if ((r, c) == goal) return dist[r, c];
        for (int k = 0; k < 4; k++)
        {
            int nr = r + dr[k], nc = c + dc[k];
            if (nr < 0 || nc < 0 || nr >= rows || nc >= cols) continue;
            if (grid[nr, nc] == 1 || dist[nr, nc] != -1) continue;
            dist[nr, nc] = dist[r, c] + 1;
            queue.Enqueue((nr, nc));
        }
    }
    return -1;
}
// ShortestPath(square graph, 0, 3) -> [0, 1, 3]
```

**Edge cases.** `src == dst` (path of one vertex), unreachable target, walls around the start in the grid.

### PriorityQueue<TElement, TPriority> in 60 seconds

**Definition.** `System.Collections.Generic.PriorityQueue<TElement,TPriority>` (since .NET 6) is a binary-heap-style collection that removes the element with the *lowest priority value first* (a min-heap by default).

```csharp
static void PriorityQueueDemo()
{
    var pq = new PriorityQueue<string, int>();
    pq.Enqueue("write report", 3);
    pq.Enqueue("fix prod bug", 1);          // lowest number = highest urgency
    pq.Enqueue("reply to email", 2);

    string next = pq.Peek();                 // "fix prod bug" (not removed)
    string first = pq.Dequeue();             // "fix prod bug"
    pq.TryDequeue(out string? e, out int p); // "reply to email", 2

    // Max-heap: supply a reversed comparer.
    var max = new PriorityQueue<int, int>(Comparer<int>.Create((a, b) => b.CompareTo(a)));
    max.Enqueue(10, 10);
    max.Enqueue(50, 50);                     // max.Dequeue() -> 50
}
```

| Fact | Detail |
|---|---|
| `Enqueue` / `Dequeue` | O(log n); `Peek` O(1); building from a collection is O(n) |
| Ties | no ordering guarantee for equal priorities (not stable) |
| Update priority | not supported - enqueue again and ignore stale entries when dequeued (lazy deletion) |
| `Count`, `TryPeek`, `TryDequeue` | available; no `Contains` |

### Dijkstra's shortest path (weighted graph)

**Problem.** Find the cheapest path from a source to every vertex in a graph with **non-negative** edge weights.

**Example.** Edges `0-1 (4)`, `0-2 (1)`, `2-1 (2)`, `1-3 (1)`, `2-3 (5)`: shortest `0 -> 3` is `0 -> 2 -> 1 -> 3` with cost 4.

**Intuition.** BFS finds the fewest *edges*; Dijkstra finds the fewest *total weight*. Keep a tentative distance to each vertex and always expand the unexpanded vertex with the smallest distance (a min-heap gives it in O(log V)). Once a vertex is popped with its smallest distance, no later path can beat it because weights are non-negative. This is greedy.

**Approach.**
1. `dist[source] = 0`, others `int.MaxValue`; push `(source, 0)`.
2. Pop `(u, d)`. If `d > dist[u]` it is a stale entry - skip.
3. For each edge `(u, v, w)`: if `d + w < dist[v]`, update `dist[v]`, record `prev[v] = u`, push `(v, d + w)`.
4. Rebuild a path by following `prev` backwards.

```csharp
// O((V + E) log V) time, O(V + E) space.
static (int[] Dist, int[] Prev) Dijkstra(WeightedGraph g, int source)
{
    var dist = new int[g.VertexCount];
    var prev = new int[g.VertexCount];
    Array.Fill(dist, int.MaxValue);
    Array.Fill(prev, -1);
    dist[source] = 0;

    var pq = new PriorityQueue<int, int>();          // element = vertex, priority = distance
    pq.Enqueue(source, 0);
    while (pq.TryDequeue(out int u, out int d))
    {
        if (d > dist[u]) continue;                   // stale entry (lazy deletion)
        foreach (var (v, w) in g.Edges(u))
        {
            int nd = d + w;
            if (nd < dist[v])
            {
                dist[v] = nd;
                prev[v] = u;
                pq.Enqueue(v, nd);
            }
        }
    }
    return (dist, prev);
}

static List<int> PathTo(int[] prev, int target)
{
    var path = new List<int>();
    for (int v = target; v != -1; v = prev[v]) path.Add(v);
    path.Reverse();
    return path;
}
// var (dist, prev) = Dijkstra(g, 0);  dist[3] -> 4,  PathTo(prev, 3) -> [0, 2, 1, 3]
```

**Complexity.** O((V + E) log V) with a binary heap; the dense-graph array version is O(V^2).

**Edge cases.** Unreachable vertices stay `int.MaxValue` (do not add to them), zero-weight edges are fine, **negative weights break it** (use Bellman-Ford), multiple equal shortest paths, large sums (use `long` for big weights).

:::q Why does Dijkstra fail with negative edges, and what do you use instead?
Dijkstra assumes that once a vertex is finalised, no later path can be shorter - a negative edge can make a longer-looking path cheaper afterwards. Use Bellman-Ford (O(VE), also detects negative cycles) or, for DAGs, relax edges in topological order. For unweighted graphs plain BFS is enough; for a single target with a good heuristic use A*.
:::

### Cycle detection

#### Directed graph: three colours

**Intuition.** A directed cycle exists exactly when DFS meets a vertex that is *currently on the recursion path* (a back edge). Colour vertices: white = unvisited, gray = on the current DFS path, black = fully explored. Reaching a gray vertex means a cycle; reaching a black vertex is harmless (cross/forward edge). A plain `visited` array is not enough - it would flag diamonds like `A->B, A->C, B->D, C->D` as cycles.

```csharp
// O(V + E) time, O(V) space. Build the graph with directed: true.
static bool HasCycleDirected(Graph g)
{
    const int White = 0, Gray = 1, Black = 2;
    var color = new int[g.VertexCount];

    bool Dfs(int v)
    {
        color[v] = Gray;                              // v is on the current path
        foreach (int w in g.Neighbors(v))
        {
            if (color[w] == Gray) return true;        // back edge -> cycle
            if (color[w] == White && Dfs(w)) return true;
        }
        color[v] = Black;                             // finished, no cycle through v
        return false;
    }

    for (int v = 0; v < g.VertexCount; v++)
        if (color[v] == White && Dfs(v)) return true;
    return false;
}
```

#### Undirected graph: parent tracking or union-find

**Intuition.** In an undirected graph every edge is seen twice (once from each end), so reaching a visited vertex is only a cycle if it is *not the parent you came from*. Alternatively, union-find: process each edge; if both endpoints already belong to the same set, the edge closes a cycle.

```csharp
// DFS with parent tracking: O(V + E).
static bool HasCycleUndirected(Graph g)
{
    var visited = new bool[g.VertexCount];

    bool Dfs(int v, int parent)
    {
        visited[v] = true;
        foreach (int w in g.Neighbors(v))
        {
            if (!visited[w]) { if (Dfs(w, v)) return true; }
            else if (w != parent) return true;        // visited and not the way we came
        }
        return false;
    }

    for (int v = 0; v < g.VertexCount; v++)
        if (!visited[v] && Dfs(v, -1)) return true;
    return false;
}

// Union-Find (disjoint set) with path compression + union by rank: ~O(alpha(n)) per op.
public class UnionFind
{
    private readonly int[] _parent;
    private readonly int[] _rank;

    public UnionFind(int n)
    {
        _parent = Enumerable.Range(0, n).ToArray();
        _rank = new int[n];
    }

    public int Find(int x)
    {
        while (_parent[x] != x)
        {
            _parent[x] = _parent[_parent[x]];         // path halving
            x = _parent[x];
        }
        return x;
    }

    public bool Union(int a, int b)                    // false if already connected
    {
        int ra = Find(a), rb = Find(b);
        if (ra == rb) return false;
        if (_rank[ra] < _rank[rb]) (ra, rb) = (rb, ra);
        _parent[rb] = ra;
        if (_rank[ra] == _rank[rb]) _rank[ra]++;
        return true;
    }
}

static bool HasCycleUndirectedUnionFind(int vertexCount, (int U, int V)[] edges)
{
    var uf = new UnionFind(vertexCount);
    foreach (var (u, v) in edges)
        if (!uf.Union(u, v)) return true;              // edge joins two already-connected nodes
    return false;
}
```

**Complexity.** DFS versions O(V + E) time, O(V) space. Union-find O(E * alpha(V)), effectively linear.

**Edge cases.** Self loops, parallel edges (parent tracking misses a double edge between the same two vertices - union-find catches it), disconnected components, a single vertex.

:::q Follow-up: how do you order tasks with dependencies, and detect impossible ones?
Topological sort. Kahn's algorithm: compute each vertex's in-degree, enqueue those with 0, repeatedly dequeue, append to the result, and decrement neighbours' in-degrees (enqueue when they reach 0). If the result has fewer than V vertices there is a cycle and no valid order. It runs in O(V + E) and is exactly how "course schedule" and build-order problems are solved.
:::

## Sorting

**Definition.** Sorting rearranges elements into an order (usually ascending) defined by a comparison. Algorithms are judged on time complexity, extra memory (*in-place*?), and *stability* - whether equal elements keep their original relative order.

**Why it matters.** Sorting is a building block (binary search, two pointers, intervals, duplicates). In an interview you rarely implement it for production - you implement it to prove you understand loop invariants, recursion and complexity trade-offs. In real code you call `Array.Sort`, `List<T>.Sort` or `OrderBy`.

| Algorithm | Best | Average | Worst | Extra space | Stable | In place |
|---|---|---|---|---|---|---|
| Bubble | O(n) (early exit) | O(n^2) | O(n^2) | O(1) | Yes | Yes |
| Selection | O(n^2) | O(n^2) | O(n^2) | O(1) | No | Yes |
| Insertion | O(n) | O(n^2) | O(n^2) | O(1) | Yes | Yes |
| Merge | O(n log n) | O(n log n) | O(n log n) | O(n) | Yes | No (arrays) |
| Quick | O(n log n) | O(n log n) | O(n^2) | O(log n) stack | No | Yes |
| Heap | O(n log n) | O(n log n) | O(n log n) | O(1) | No | Yes |
| Counting (small integer range k) | O(n + k) | O(n + k) | O(n + k) | O(k) | Yes | No |

:::tip How to answer "which sort would you use?"
Real code: the built-in sort. Small or nearly sorted data: insertion sort. Need stability or guaranteed O(n log n) or sorting a linked list/huge file: merge sort. Fast average on arrays with low memory: quicksort. Integers in a small known range: counting sort.
:::

The snippets sort an `int[]` ascending, in place.

### Bubble sort

**Intuition.** Repeatedly swap adjacent out-of-order elements; after each pass the largest remaining element "bubbles" to the end. A `swapped` flag exits early when a pass makes no swaps (already sorted: O(n)).

```csharp
// O(n^2) time (O(n) if already sorted), O(1) space, stable.
static void BubbleSort(int[] a)
{
    for (int pass = 0; pass < a.Length - 1; pass++)
    {
        bool swapped = false;
        for (int i = 0; i < a.Length - 1 - pass; i++)   // tail is already sorted
        {
            if (a[i] > a[i + 1])
            {
                (a[i], a[i + 1]) = (a[i + 1], a[i]);
                swapped = true;
            }
        }
        if (!swapped) break;
    }
}
// [5, 1, 4, 2] -> pass 1: [1, 4, 2, 5] -> pass 2: [1, 2, 4, 5] -> pass 3: no swaps, stop
```

### Selection sort

**Intuition.** Find the minimum of the unsorted part and swap it to the front. Makes at most `n-1` swaps - useful when writes are expensive - but always does O(n^2) comparisons. Not stable because the long-distance swap can jump an element over an equal one.

```csharp
// O(n^2) time always, O(1) space, not stable.
static void SelectionSort(int[] a)
{
    for (int i = 0; i < a.Length - 1; i++)
    {
        int min = i;
        for (int j = i + 1; j < a.Length; j++)
            if (a[j] < a[min]) min = j;
        if (min != i) (a[i], a[min]) = (a[min], a[i]);
    }
}
```

### Insertion sort

**Intuition.** Like sorting playing cards in your hand: take the next element and slide it left past larger elements into its place within the already-sorted prefix. Very fast on small or nearly sorted data, which is why real libraries use it for tiny partitions.

```csharp
// O(n^2) worst/average, O(n) best, O(1) space, stable.
static void InsertionSort(int[] a)
{
    for (int i = 1; i < a.Length; i++)
    {
        int key = a[i];
        int j = i - 1;
        while (j >= 0 && a[j] > key)      // shift larger elements one slot right
        {
            a[j + 1] = a[j];
            j--;
        }
        a[j + 1] = key;
    }
}
```

### Merge sort

**Intuition.** Divide and conquer: split the array in half, sort each half recursively, then *merge* the two sorted halves in linear time using a temporary buffer. The recursion depth is `log n` levels and each level does O(n) merge work.

**Approach.**
1. Base case: a range of 0 or 1 elements is sorted.
2. Sort the left half, sort the right half.
3. Merge: walk both halves with two indices, always copying the smaller; take from the left on ties to keep it **stable**.

```csharp
// O(n log n) time in all cases, O(n) extra space, stable.
static void MergeSort(int[] a)
{
    if (a.Length < 2) return;
    var temp = new int[a.Length];
    SortRange(0, a.Length - 1);

    void SortRange(int lo, int hi)
    {
        if (lo >= hi) return;
        int mid = lo + (hi - lo) / 2;
        SortRange(lo, mid);
        SortRange(mid + 1, hi);
        MergeRanges(lo, mid, hi);
    }

    void MergeRanges(int lo, int mid, int hi)
    {
        int i = lo, j = mid + 1, k = lo;
        while (i <= mid && j <= hi)
            temp[k++] = a[i] <= a[j] ? a[i++] : a[j++];   // <= keeps equal items in order
        while (i <= mid) temp[k++] = a[i++];
        while (j <= hi) temp[k++] = a[j++];
        Array.Copy(temp, lo, a, lo, hi - lo + 1);
    }
}
```

### Quick sort (Lomuto partition)

**Intuition.** Pick a *pivot*, partition the array so everything smaller is left of the pivot and everything larger is right of it (the pivot is now in its final position), then recurse on both sides. No merge step, sorts in place.

**Lomuto partition.** Use the last element as pivot. Keep `i` = the boundary of the "smaller than pivot" region; scan `j` from `lo`; whenever `a[j] < pivot`, swap it into the region and grow it; finally swap the pivot into `a[i]`.

```csharp
// Average O(n log n); worst O(n^2) when pivots are always extreme (e.g. sorted input
// with a last-element pivot). O(log n) average stack, not stable.
static void QuickSort(int[] a) => QuickSort(a, 0, a.Length - 1);

static void QuickSort(int[] a, int lo, int hi)
{
    if (lo >= hi) return;
    int p = Partition(a, lo, hi);
    QuickSort(a, lo, p - 1);
    QuickSort(a, p + 1, hi);
}

static int Partition(int[] a, int lo, int hi)
{
    int pivot = a[hi];
    int i = lo;                              // a[lo..i-1] are all < pivot
    for (int j = lo; j < hi; j++)
    {
        if (a[j] < pivot)
        {
            (a[i], a[j]) = (a[j], a[i]);
            i++;
        }
    }
    (a[i], a[hi]) = (a[hi], a[i]);           // pivot lands in its final position
    return i;
}

// Defence against the O(n^2) case: randomise the pivot before partitioning.
static void QuickSortRandom(int[] a, int lo, int hi)
{
    if (lo >= hi) return;
    int r = Random.Shared.Next(lo, hi + 1);
    (a[r], a[hi]) = (a[hi], a[r]);
    int p = Partition(a, lo, hi);
    QuickSortRandom(a, lo, p - 1);
    QuickSortRandom(a, p + 1, hi);
}
// Partition([3, 8, 2, 5, 1, 4], 0, 5) with pivot 4 -> [3, 2, 1, 4, 8, 5], returns 3
```

**Edge cases for all sorts.** Empty array, one element, already sorted, reverse sorted, all equal, many duplicates (Lomuto degrades to O(n^2) on all-equal input - the three-way partition fixes that), negatives.

:::warn Quick sort's two traps
(1) Sorted input with a fixed first/last pivot gives O(n^2) time **and O(n) recursion depth**, which can overflow the stack - randomise the pivot or use median-of-three, and recurse into the smaller half first. (2) Quicksort is not stable; use merge sort (or LINQ `OrderBy`) when equal keys must keep their order.
:::

### Sorting in .NET

`Array.Sort` and `List<T>.Sort` use **introsort**: quicksort with a median-of-three pivot that switches to **heapsort** when the recursion depth exceeds about `2 * log2(n)` (guaranteeing O(n log n) worst case) and uses **insertion sort** for tiny partitions (16 elements or fewer). It is **not stable**.

```csharp
static void BuiltInSorts()
{
    int[] numbers = { 5, 2, 9, 1 };
    Array.Sort(numbers);                                   // introsort, in place
    Array.Sort(numbers, (x, y) => y.CompareTo(x));         // descending via comparison

    var orders = new List<(string Customer, decimal Total)>
        { ("Asha", 40m), ("Ben", 40m), ("Chen", 10m) };
    orders.Sort((x, y) => x.Total.CompareTo(y.Total));     // NOT stable: Asha/Ben may swap

    // OrderBy / ThenBy is a STABLE sort (and returns a new sequence).
    var stable = orders.OrderBy(o => o.Total).ThenBy(o => o.Customer).ToList();
}
```

| API | Algorithm | Stable | In place |
|---|---|---|---|
| `Array.Sort`, `List<T>.Sort` | introsort | No | Yes |
| `Enumerable.OrderBy` | quicksort on keys, ties broken by original index | Yes | No (new sequence) |
| `SortedSet<T>`, `SortedDictionary<K,V>` | keep order on insert (red-black tree) | n/a | n/a |

:::q Why is merge sort used for linked lists and external sorting, but quicksort for arrays?
Merge sort needs only sequential access and can merge by relinking nodes (O(1) extra space for lists), while quicksort relies on random access and swaps, which is cheap for arrays but poor for lists. For data too large for memory, you sort chunks, write them out, then k-way merge - which is merge sort's merge step. For in-memory arrays quicksort wins in practice because it is cache friendly and has small constants.
:::

:::q What is the lower bound for comparison sorting, and how can counting sort beat it?
Any comparison-based sort needs at least O(n log n) comparisons in the worst case (a decision tree with n! leaves has height log2(n!)). Counting and radix sort avoid comparisons and run in O(n + k) when keys are integers in a small range `k`, but they use extra memory and only work for that kind of key.
:::

:::q What does it mean for a sort to be stable? Give an example where it matters.
Stable means records with equal keys stay in their original relative order. If orders are first sorted by date and then by customer, a stable second sort keeps each customer's orders in date order. With an unstable sort (`Array.Sort`) you would have to sort once by `(customer, date)` or use LINQ `OrderBy(...).ThenBy(...)`.
:::
