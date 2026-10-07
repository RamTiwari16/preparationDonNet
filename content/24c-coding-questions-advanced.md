## Medium Problems (19-25)

### 19. Reverse a linked list

**Problem.** Reverse a singly linked list and return the new head.

**Examples.** `1 -> 2 -> 3 -> 4 -> 5` becomes `5 -> 4 -> 3 -> 2 -> 1`. `1` stays `1`. An empty list stays empty.

Deep dive: *Reverse a linked list* in Section 7, Linked List (it also covers why the recursive version is O(n) stack).

```csharp
public class ListNode
{
    public int Val;
    public ListNode? Next;
    public ListNode(int val, ListNode? next = null) { Val = val; Next = next; }
}

static ListNode? FromArray(params int[] values)
{
    ListNode? head = null;
    for (int i = values.Length - 1; i >= 0; i--) head = new ListNode(values[i], head);
    return head;
}

static string Print(ListNode? head)
{
    var sb = new StringBuilder();
    for (var n = head; n is not null; n = n.Next)
        sb.Append(sb.Length == 0 ? "" : " -> ").Append(n.Val);
    return sb.ToString();
}

// Brute force: push nodes on a stack, then relink in pop order. O(n) time, O(n) space.
static ListNode? ReverseWithStack(ListNode? head)
{
    var stack = new Stack<ListNode>();
    for (var n = head; n is not null; n = n.Next) stack.Push(n);
    if (stack.Count == 0) return null;
    ListNode newHead = stack.Pop(), cur = newHead;
    while (stack.Count > 0)
    {
        cur.Next = stack.Pop();
        cur = cur.Next;
    }
    cur.Next = null;                         // old head is the new tail
    return newHead;
}

// Optimal iterative: O(n) time, O(1) space.
static ListNode? ReverseList(ListNode? head)
{
    ListNode? prev = null, cur = head;
    while (cur is not null)
    {
        ListNode? next = cur.Next;           // save the rest
        cur.Next = prev;                     // flip the link
        prev = cur;
        cur = next;
    }
    return prev;
}

// Recursive: O(n) time, O(n) call stack.
static ListNode? ReverseListRecursive(ListNode? head)
{
    if (head?.Next is null) return head;
    ListNode? newHead = ReverseListRecursive(head.Next);
    head.Next.Next = head;
    head.Next = null;
    return newHead;
}
// Print(ReverseList(FromArray(1, 2, 3, 4, 5))) -> "5 -> 4 -> 3 -> 2 -> 1"
```

**Complexity.** Iterative O(n) time and O(1) space. Recursive O(n) time and O(n) stack. Stack version O(n) space.

:::q Follow-up: check whether a linked list is a palindrome in O(1) extra space.
Find the middle with slow/fast pointers, reverse the second half in place, and compare it node by node with the first half. Then reverse the second half again to restore the list, which is polite to the caller. That is O(n) time and O(1) space. It combines problems 19 and 20.
:::

### 20. Detect a linked-list cycle

**Problem.** Return whether the list has a cycle. Follow-up: return the node where the cycle starts.

**Examples.** `3 -> 2 -> 0 -> -4 -> (back to 2)` has a cycle starting at node `2`. `1 -> 2 -> null` has no cycle.

Deep dive: *Detect a cycle (Floyd's tortoise and hare)* in Section 7, with the proof of why the start-finding step works.

```csharp
// Brute force: remember visited nodes (reference equality). O(n) time, O(n) space.
static bool HasCycleWithSet(ListNode? head)
{
    var visited = new HashSet<ListNode>();
    for (var n = head; n is not null; n = n.Next)
        if (!visited.Add(n)) return true;
    return false;
}

// Floyd: slow moves 1, fast moves 2. O(n) time, O(1) space.
static bool HasCycleFloyd(ListNode? head)
{
    ListNode? slow = head, fast = head;
    while (fast?.Next is not null)
    {
        slow = slow!.Next;
        fast = fast.Next.Next;
        if (ReferenceEquals(slow, fast)) return true;
    }
    return false;
}

// Start of the cycle: after they meet, restart one pointer from head; step both by 1.
static ListNode? DetectCycleStart(ListNode? head)
{
    ListNode? slow = head, fast = head;
    while (fast?.Next is not null)
    {
        slow = slow!.Next;
        fast = fast.Next.Next;
        if (!ReferenceEquals(slow, fast)) continue;
        for (var p = head; ; p = p!.Next, slow = slow!.Next)
            if (ReferenceEquals(p, slow)) return p;
    }
    return null;
}
```

**Complexity.** Floyd: O(n) time, O(1) space. HashSet: O(n) time, O(n) space.

**Edge cases.** Empty list, one node pointing to itself, cycle back to the head, very long tail before the cycle.

:::q Follow-up: why must the HashSet compare references, not values?
Two different nodes can hold the same value, for example `1 -> 2 -> 1 -> null`, and that is not a cycle. A cycle means the *same node object* is reached twice. `ListNode` is a class that does not override `Equals`/`GetHashCode`, so `HashSet<ListNode>` already uses reference equality. Storing `node.Val` in a `HashSet<int>` would be a bug.
:::

### 21. Tree traversal

**Problem.** Return the inorder, preorder, postorder and level-order traversals of a binary tree.

**Example.** For the tree below: inorder `4 2 5 1 3`, preorder `1 2 4 5 3`, postorder `4 5 2 3 1`, level order `[[1], [2, 3], [4, 5]]`.

```text
        1
       / \
      2   3
     / \
    4   5
```

Deep dive: *Tree traversals* in Section 7, Trees (includes iterative preorder and a postorder trick).

```csharp
public class TreeNode
{
    public int Val;
    public TreeNode? Left, Right;
    public TreeNode(int val, TreeNode? left = null, TreeNode? right = null)
    {
        Val = val; Left = left; Right = right;
    }
}

// Recursive DFS: one helper, three orders. O(n) time, O(h) stack.
static void Traverse(TreeNode? n, List<int> pre, List<int> inOrder, List<int> post)
{
    if (n is null) return;
    pre.Add(n.Val);                          // before children
    Traverse(n.Left, pre, inOrder, post);
    inOrder.Add(n.Val);                      // between children
    Traverse(n.Right, pre, inOrder, post);
    post.Add(n.Val);                         // after children
}

// Iterative inorder with an explicit stack: O(n) time, O(h) space.
static List<int> InorderIterative(TreeNode? root)
{
    var result = new List<int>();
    var stack = new Stack<TreeNode>();
    var cur = root;
    while (cur is not null || stack.Count > 0)
    {
        for (; cur is not null; cur = cur.Left) stack.Push(cur);   // dive left
        cur = stack.Pop();
        result.Add(cur.Val);
        cur = cur.Right;
    }
    return result;
}

// Level order (BFS): O(n) time, O(width) space.
static List<List<int>> LevelOrder(TreeNode? root)
{
    var levels = new List<List<int>>();
    if (root is null) return levels;
    var queue = new Queue<TreeNode>([root]);
    while (queue.Count > 0)
    {
        var level = new List<int>();
        for (int i = queue.Count; i > 0; i--)        // exactly the nodes of this level
        {
            var n = queue.Dequeue();
            level.Add(n.Val);
            if (n.Left is not null) queue.Enqueue(n.Left);
            if (n.Right is not null) queue.Enqueue(n.Right);
        }
        levels.Add(level);
    }
    return levels;
}
```

| Traversal | Order | Remember it by |
|---|---|---|
| Preorder | Node, Left, Right | copy / serialise a tree |
| Inorder | Left, Node, Right | sorted output of a BST |
| Postorder | Left, Right, Node | delete a tree or compute heights (children first) |
| Level order | level by level | BFS, minimum depth, right-side view |

**Complexity.** O(n) time for all. Space: O(h) for DFS (O(n) if skewed), O(w) for BFS.

:::q Follow-up: zigzag level order, or the right-side view?
Both reuse the level-order loop. Zigzag: reverse every other `level` list, or insert at the front on odd levels. Right-side view: take the last value of each level. Interviewers like these because they check whether you know the "freeze `queue.Count` per level" trick.
:::

### 22. Breadth-first search (BFS)

**Problem.** Given an undirected graph, return the BFS visiting order from a start vertex and the distance (in edges) from the start to every reachable vertex.

**Example.** Edges `1-2, 1-3, 2-4, 3-4, 4-5`, start `1`: order `[1, 2, 3, 4, 5]`, distances `1:0, 2:1, 3:1, 4:2, 5:3`.

Deep dive: *Breadth-first search* and *Shortest path in an unweighted graph* in Section 7, Graphs.

```csharp
// Adjacency list from an edge list (undirected).
static Dictionary<int, List<int>> BuildGraph((int U, int V)[] edges)
{
    var graph = new Dictionary<int, List<int>>();
    foreach (var (u, v) in edges)
    {
        if (!graph.TryGetValue(u, out var nu)) graph[u] = nu = new List<int>();
        if (!graph.TryGetValue(v, out var nv)) graph[v] = nv = new List<int>();
        nu.Add(v);
        nv.Add(u);
    }
    return graph;
}

// BFS order: O(V + E) time, O(V) space.
static List<int> BfsOrder(Dictionary<int, List<int>> graph, int start)
{
    var order = new List<int>();
    var visited = new HashSet<int> { start };       // mark when enqueued
    var queue = new Queue<int>();
    queue.Enqueue(start);
    while (queue.Count > 0)
    {
        int v = queue.Dequeue();
        order.Add(v);
        if (!graph.TryGetValue(v, out var neighbors)) continue;
        foreach (int w in neighbors)
            if (visited.Add(w)) queue.Enqueue(w);    // Add returns false if already seen
    }
    return order;
}

// Distances in edges from start: the dictionary doubles as the visited set.
static Dictionary<int, int> BfsDistances(Dictionary<int, List<int>> graph, int start)
{
    var dist = new Dictionary<int, int> { [start] = 0 };
    var queue = new Queue<int>();
    queue.Enqueue(start);
    while (queue.Count > 0)
    {
        int v = queue.Dequeue();
        if (!graph.TryGetValue(v, out var neighbors)) continue;
        foreach (int w in neighbors)
        {
            if (dist.ContainsKey(w)) continue;
            dist[w] = dist[v] + 1;
            queue.Enqueue(w);
        }
    }
    return dist;
}
// BfsOrder(BuildGraph(new[] { (1, 2), (1, 3), (2, 4), (3, 4), (4, 5) }), 1) -> [1, 2, 3, 4, 5]
```

**Complexity.** O(V + E) time, O(V) space.

**Edge cases.** Start vertex with no edges, disconnected vertices (not reached), cycles (the visited set prevents infinite loops), self loops.

:::q Follow-up: "rotting oranges" or "minimum steps from any gate" - many starting points?
Use **multi-source BFS**: enqueue *all* sources at distance 0 before the loop starts, then run normal BFS. Each cell gets its distance to the *nearest* source in a single O(rows x cols) pass, instead of one BFS per source. The answer to "rotting oranges" is the largest distance reached, or -1 if a fresh orange is never reached.
:::

### 23. Depth-first search (DFS)

**Problem.** (a) Return the DFS order of a graph from a start vertex, recursively and iteratively. (b) Count the islands in a grid of `'1'` (land) and `'0'` (water), where land connects up, down, left and right.

**Examples.** Same graph as problem 22, start `1`: DFS order `[1, 2, 4, 3, 5]`. The grid below has `3` islands.

```text
1 1 0 0 0
1 1 0 0 0
0 0 1 0 0
0 0 0 1 1
```

Deep dive: *Depth-first search* and *Cycle detection* in Section 7, Graphs.

```csharp
// Recursive DFS: O(V + E) time, O(V) stack depth.
static List<int> DfsOrder(Dictionary<int, List<int>> graph, int start)
{
    var order = new List<int>();
    var visited = new HashSet<int>();
    void Visit(int v)
    {
        if (!visited.Add(v)) return;
        order.Add(v);
        if (graph.TryGetValue(v, out var neighbors))
            foreach (int w in neighbors) Visit(w);
    }
    Visit(start);
    return order;
}

// Iterative DFS with an explicit stack: same order, no recursion-depth limit.
static List<int> DfsOrderIterative(Dictionary<int, List<int>> graph, int start)
{
    var order = new List<int>();
    var visited = new HashSet<int>();
    var stack = new Stack<int>();
    stack.Push(start);
    while (stack.Count > 0)
    {
        int v = stack.Pop();
        if (!visited.Add(v)) continue;               // mark when popped
        order.Add(v);
        if (!graph.TryGetValue(v, out var neighbors)) continue;
        for (int i = neighbors.Count - 1; i >= 0; i--)   // reversed: first neighbour on top
            if (!visited.Contains(neighbors[i])) stack.Push(neighbors[i]);
    }
    return order;
}

// Number of islands: DFS "flood fill" sinks each island once. O(rows * cols).
static int NumIslands(char[][] grid)
{
    int islands = 0;
    for (int r = 0; r < grid.Length; r++)
        for (int c = 0; c < grid[r].Length; c++)
            if (grid[r][c] == '1')
            {
                islands++;
                Sink(grid, r, c);
            }
    return islands;
}

static void Sink(char[][] grid, int r, int c)
{
    if (r < 0 || c < 0 || r >= grid.Length || c >= grid[r].Length) return;
    if (grid[r][c] != '1') return;
    grid[r][c] = '0';                                 // mark visited by sinking the land
    Sink(grid, r + 1, c);
    Sink(grid, r - 1, c);
    Sink(grid, r, c + 1);
    Sink(grid, r, c - 1);
}
```

**Complexity.** Graph DFS: O(V + E) time, O(V) space. Islands: O(rows x cols) time, with O(rows x cols) recursion depth in the worst case (one giant snake-shaped island).

**Edge cases.** Empty grid, all water, all land (deepest recursion, so prefer the iterative version or BFS for huge grids), diagonal neighbours (they do not connect unless the problem says so).

:::q Follow-up: you are not allowed to modify the grid.
Use a separate `bool[rows, cols] visited` array, or a `HashSet<(int, int)>` for sparse grids, and check it instead of overwriting cells. The complexity is the same, plus O(rows x cols) memory. Mention that mutating input is a side effect a caller may not expect. In production code, prefer not to.
:::

### 24. Top K frequent elements

**Problem.** Return the `k` most frequent elements. The answer is unique, and any order is accepted.

**Examples.** `[1, 1, 1, 2, 2, 3]`, `k = 2` returns `[1, 2]`. `[4]`, `k = 1` returns `[4]`. In an e-commerce setting this is "top k best-selling product IDs from today's order lines".

**Intuition.** Step 1 is always a frequency dictionary. Step 2 picks the top `k` by count:
- **Sort** all distinct values by count: O(m log m) for `m` distinct values.
- **Min-heap of size k**: keep only the `k` best seen so far. The heap's *minimum* is the weakest candidate, so a new value only has to beat it. O(m log k).
- **Bucket sort**: a frequency is between 1 and `n`, so use an array of buckets indexed by frequency and walk it from the top. O(n).

```csharp
// Brute force: group, sort by count, take k. O(n + m log m).
static int[] TopKFrequentSort(int[] nums, int k) =>
    nums.GroupBy(x => x)
        .OrderByDescending(g => g.Count())
        .Take(k)
        .Select(g => g.Key)
        .ToArray();

// Dictionary + min-heap (PriorityQueue) of size k: O(n + m log k) time, O(m + k) space.
static int[] TopKFrequentHeap(int[] nums, int k)
{
    var freq = new Dictionary<int, int>();
    foreach (int x in nums) freq[x] = freq.GetValueOrDefault(x) + 1;

    var heap = new PriorityQueue<int, int>();      // element = value, priority = count
    foreach (var (value, count) in freq)
    {
        heap.Enqueue(value, count);
        if (heap.Count > k) heap.Dequeue();         // evict the least frequent
    }

    var result = new int[heap.Count];
    for (int i = result.Length - 1; i >= 0; i--)    // fill from the back: most frequent first
        result[i] = heap.Dequeue();
    return result;
}

// Bucket sort: O(n) time, O(n) space.
static int[] TopKFrequentBucket(int[] nums, int k)
{
    var freq = new Dictionary<int, int>();
    foreach (int x in nums) freq[x] = freq.GetValueOrDefault(x) + 1;

    var buckets = new List<int>?[nums.Length + 1];  // buckets[f] = values seen f times
    foreach (var (value, count) in freq)
        (buckets[count] ??= new List<int>()).Add(value);

    var result = new List<int>(k);
    for (int f = buckets.Length - 1; f > 0 && result.Count < k; f--)
    {
        if (buckets[f] is not { } values) continue;
        foreach (int v in values)
        {
            result.Add(v);
            if (result.Count == k) break;
        }
    }
    return result.ToArray();
}
// TopKFrequentHeap(new[] { 1, 1, 1, 2, 2, 3 }, 2) -> [1, 2]
```

**Complexity.**

| Approach | Time | Space |
|---|---|---|
| Sort by count | O(n + m log m) | O(m) |
| Min-heap of size k | O(n + m log k) | O(m + k) |
| Bucket sort | O(n) | O(n) |

**Edge cases.** `k` equal to the number of distinct values, ties at the k-th place (clarify what to do), negative numbers (fine, because they are dictionary keys and not array indexes), a single element.

:::q Why a MIN-heap for the top k largest, not a max-heap?
A max-heap of all `m` values costs O(m log m) to build with enqueues and holds everything. A min-heap capped at `k` holds only the current top `k`. Its root is the weakest of them, which is exactly the element to compare against and evict. That gives O(m log k) time and O(k) heap memory, which matters for streaming data where `m` is huge and `k` is small. (.NET's `PriorityQueue` is a min-heap by default, so it fits directly.)
:::

### 25. Merge intervals

**Problem.** Merge all overlapping intervals and return the non-overlapping result.

**Examples.** `[[1,3], [2,6], [8,10], [15,18]]` returns `[[1,6], [8,10], [15,18]]`. `[[1,4], [4,5]]` returns `[[1,5]]` (touching counts as overlapping). In an e-commerce setting: merge a warehouse's booked delivery windows to find its free slots.

**Intuition.** After sorting by start, any interval that overlaps the current merged block must come right after it. One pass is enough. If the next start is `<=` the last merged end, extend that end (with `max`, because the next interval may sit entirely inside). Otherwise start a new block.

**Approach.**
1. Sort by start.
2. Put the first interval in `merged`.
3. For each next interval: if it overlaps `merged[^1]`, set `last.End = max(last.End, cur.End)`. Otherwise append it.

```csharp
// Brute force idea: repeatedly scan all pairs and merge until nothing changes - O(n^2)+.
// Optimal: sort + one pass. O(n log n) time, O(n) output.
static int[][] MergeIntervals(int[][] intervals)
{
    if (intervals.Length == 0) return [];
    int[][] sorted = intervals.OrderBy(iv => iv[0]).ToArray();
    var merged = new List<int[]> { new[] { sorted[0][0], sorted[0][1] } };  // copy input
    foreach (int[] cur in sorted.Skip(1))
    {
        int[] last = merged[^1];
        if (cur[0] <= last[1])
            last[1] = Math.Max(last[1], cur[1]);     // overlap: extend the block
        else
            merged.Add([cur[0], cur[1]]);            // gap: start a new block
    }
    return merged.ToArray();
}

// Same algorithm with named tuples - closer to how you would write it in a real service.
static List<(int Start, int End)> MergeSlots(IEnumerable<(int Start, int End)> slots)
{
    var result = new List<(int Start, int End)>();
    foreach (var s in slots.OrderBy(s => s.Start))
    {
        if (result.Count > 0 && s.Start <= result[^1].End)
            result[^1] = (result[^1].Start, Math.Max(result[^1].End, s.End));
        else
            result.Add(s);
    }
    return result;
}
// MergeIntervals([[1,3],[2,6],[8,10],[15,18]]) -> [[1,6],[8,10],[15,18]]
```

**Complexity.** O(n log n) time for the sort and O(n) for the pass. O(n) space for the output (plus the sort).

**Edge cases.** Empty input, a single interval, one interval containing another (`[1,10],[2,3]`, hence the `max`), touching intervals (`<=` vs `<`, so clarify), unsorted input.

:::q Follow-up: insert a new interval into an already sorted, non-overlapping list.
No sort is needed. In one O(n) pass, copy the intervals that end before the new one starts. Then merge every interval that overlaps it by widening `start = min(...)` and `end = max(...)`. Then copy the rest. For "how many meeting rooms", see *Minimum meeting rooms* in Section 7, Greedy Algorithms (sweep the sorted starts and ends).
:::

## 3-Week Practice Schedule

Aim for 1.5-2 hours a day: about 60% solving new problems, 40% re-solving old ones without looking. Time each attempt. Easy problems should take about 15 minutes, medium about 25-30 minutes.

| Day | Focus | Problems (this section + Section 7) | Done when you can... |
|---|---|---|---|
| 1 | Arrays, two pointers | 1, 2, 3, 7 + rotate array | write each in under 10 min with edge cases |
| 2 | Math basics | 4, 5, 6, 10 + sieve | explain recursion vs memo vs iterative |
| 3 | Hashing | 8, 9, 11, 13 + group anagrams | replace a nested loop with a dictionary on sight |
| 4 | Two pointers on sorted data | 12, 14 + remove duplicates in place | skip duplicates in Three Sum without hesitation |
| 5 | Binary search | 15 + lower bound, integer sqrt | write the template with no off-by-one |
| 6 | Sliding window | 16, 17 + subarray sum = K (prefix sums) | say when a window works and when it does not |
| 7 | Review + mock | re-solve 1-17, one timed mock (2 problems / 45 min) | talk through every solution aloud |
| 8 | Stack | 18 + next greater element, min stack | spot a monotonic-stack problem |
| 9 | Queue designs | queue via stacks, stack via queue, circular queue | explain amortised O(1) |
| 10 | Linked list | 19, 20 + middle node, merge two lists | reverse a list in under 3 minutes |
| 11 | Trees | 21 + height, validate BST, LCA | write iterative inorder from memory |
| 12 | Graph BFS | 22 + shortest path in grid, multi-source BFS | build an adjacency list in 2 minutes |
| 13 | Graph DFS | 23 + cycle detection (both kinds), topological sort | explain the gray/black colouring |
| 14 | Review + mock | re-solve 18-23, one timed mock | finish a medium problem in 30 min |
| 15 | Heap + intervals | 24, 25 + meeting rooms, merge k lists | use `PriorityQueue` without looking up the API |
| 16 | Sorting | implement merge sort and quick sort (Lomuto) | state complexity and stability of all five |
| 17 | DP I | Fibonacci (4 ways), climbing stairs, coin change | write state + recurrence before coding |
| 18 | DP II | 0/1 knapsack, LCS with reconstruction | fill a DP table by hand on paper |
| 19 | Greedy | activity selection, fractional knapsack, job sequencing | give an exchange-argument proof |
| 20 | Weak spots | re-solve every problem you got wrong or were slow on | everything under target time |
| 21 | Light review | read the pattern cheat-sheet + quick-fire Q&A, then rest | sleep well before the interview |

:::tip Keep an error log
For every failed attempt, write one line: *problem - what went wrong - the fix* (for example "Three Sum - forgot to skip duplicate `a[i]` - add `if (i > 0 && a[i] == a[i-1]) continue`"). Re-reading this log the night before is worth more than solving five new problems.
:::

## Interview-Day Communication Script

Interviewers grade the conversation as much as the code. Use this script so you are never silent for long.

**1. Restate and clarify (2-3 min).**
> "Let me restate: given an array of order amounts and a target, return the indices of two orders that sum to the target. Can the array be empty? Can values be negative? Is there always exactly one answer? Can I use the same element twice? Roughly how large is n?"

**2. Examples and edge cases (2 min).**
> "Normal case: `[2, 7, 11, 15]`, target 9 gives `[0, 1]`. Edge cases I'll keep in mind: duplicates like `[3, 3]`, negatives, and no answer. For that I'll return an empty array, unless you'd prefer an exception."

**3. Brute force first (1-2 min).**
> "The straightforward way is to check every pair. That's O(n^2) time and O(1) space. It works, but we can do better."

**4. Optimise with a reason (3-5 min).**
> "The bottleneck is searching for the complement. If I store values I've already seen in a dictionary, each lookup is O(1), so the whole thing becomes O(n) time at the cost of O(n) memory. Is that trade-off OK?"

**5. Code while narrating (10-15 min).**
> "I'll use a `Dictionary<int,int>` from value to index... I check before inserting so an element can't pair with itself..." Use clear names. If you get stuck, say what you are thinking: "I'm deciding whether the loop should be `<` or `<=`. Let me check with a two-element array."

**6. Test by dry-running (3-5 min).**
> "Let me trace `[3, 2, 4]`, target 6. At i=0, need 3, not seen, store 3->0. At i=1, need 4, not seen, store 2->1. At i=2, need 2, found at 1, so return `[1, 2]`. Correct. Now `[3, 3]`: returns `[0, 1]`. And an empty array returns empty."

**7. Complexity and wrap-up (1 min).**
> "Time O(n), space O(n). If memory were tight and I could reorder the data, I'd sort and use two pointers: O(n log n) time and O(1) extra space. In production I'd add input validation and unit tests for the edge cases we listed."

:::warn Things that cost offers
Coding in silence for 10 minutes. Jumping straight to code before clarifying. Arguing when the interviewer gives a hint (take it: "Good point, that suggests a heap..."). Claiming "done" without testing. Not knowing the complexity of your own solution.
:::

:::tip When you are stuck
Say it, and go back to the pattern cheat-sheet out loud: "Is it sorted? Then two pointers or binary search. Do I need fast lookup? Then a dictionary. Is it contiguous? Then a sliding window. Shortest steps? Then BFS. Count the ways? Then DP." Working through a correct brute force while you think still scores points. A blank screen scores none.
:::

## Quick-fire Q&A

:::q How do you approach a coding problem you have never seen before?
Clarify the inputs and constraints, then work through two or three examples by hand, including edge cases. State a brute-force solution with its complexity. Then look for the bottleneck and match it to a known pattern (hashing, two pointers, sliding window, BFS/DFS, heap, DP). Only then do I write code, and afterwards I dry-run it and state the time and space complexity.
:::

:::q Is it OK to use LINQ in a coding interview?
Use it for clarity in non-critical parts (for example `GroupBy` for frequencies), but be ready to write the loop and to explain the cost: `OrderBy` is O(n log n), `Distinct` and `GroupBy` allocate, and `Count()` inside a loop can make O(n) into O(n^2). Many interviewers ban `Reverse()`, `Sort()` or `Distinct()` for the core logic because they want to see the algorithm.
:::

:::q When would you choose a HashSet over sorting for duplicate problems?
A HashSet gives O(n) time but O(n) extra memory and loses ordering. Sorting gives O(n log n) time and O(1) extra memory (if you may modify the input), and groups equal values. Choose the HashSet for speed on unsorted data. Choose sorting when memory is tight, the data is already sorted, or you also need order (Three Sum, merge intervals).
:::

:::q Why do Three Sum and Merge Intervals both start with a sort?
Sorting creates structure you can exploit. In Three Sum it makes the two-pointer move rules valid (sum too small, move left; too big, move right) and puts duplicates next to each other so they can be skipped. In Merge Intervals it guarantees that any interval overlapping the current block comes immediately after it, so one pass is enough. Sorting costs O(n log n), which is cheaper than the O(n^2) or O(n^3) brute force.
:::

:::q What is the difference between a fixed and a variable sliding window?
A fixed window has a constant size `k`: add the entering element and remove the leaving one each step (maximum sum of k elements). A variable window grows the right edge and shrinks the left edge while a condition holds (longest substring without repeats, shortest subarray with sum >= target). Both are O(n) because each index enters and leaves once. Variable windows need a monotonic condition, so with negative numbers use prefix sums instead.
:::

:::q Recursive or iterative tree/graph traversal in production C#?
Iterative, when the depth is unbounded or driven by user data. C# does not guarantee tail calls, and a `StackOverflowException` cannot be caught, so it kills the process. Recursion is fine and clearer for balanced trees (depth about log n) or small, known depths. In an interview, write the recursive version first and mention this trade-off.
:::

:::q How do you test your solution during the interview?
Dry-run it line by line on the normal example, then on the edge cases: empty, single element, duplicates, negatives, the largest values (overflow), and a case where the answer does not exist. In a real codebase I would turn those exact cases into xUnit `[Theory]` + `[InlineData]` tests.
:::

:::q Explain the time-space trade-off with an example.
Two Sum: brute force uses O(n^2) time and O(1) space. Adding a dictionary uses O(n) extra memory to cut the time to O(n). Memoised Fibonacci, caching in web APIs, and database indexes are the same trade: spend memory or storage to avoid repeated computation.
:::

:::q What do you do if you cannot reach the optimal solution in time?
Implement the correct brute force cleanly, test it, and state its complexity. Then explain the direction for optimising ("I suspect a monotonic stack removes the inner loop, because each element only needs its next greater element"). A correct, well-tested O(n^2) with a clear plan usually scores better than an unfinished O(n).
:::

:::q How does .NET's PriorityQueue differ from a sorted collection like SortedSet?
`PriorityQueue<TElement,TPriority>` is a heap. It gives only the minimum, in O(log n) per enqueue and dequeue, allows duplicate priorities, and does not support ordered iteration or cheap priority updates. `SortedSet<T>` is a red-black tree. It keeps everything ordered, supports `Min`, `Max` and range views, and removes any element in O(log n), but it rejects duplicates (as decided by the comparer) and carries more overhead per node. Use the heap for top-K and Dijkstra, and the sorted set when you need ordered traversal or arbitrary removal.
:::
