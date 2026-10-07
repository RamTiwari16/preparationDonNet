## Greedy Algorithms

**Definition.** A greedy algorithm builds a solution step by step, always taking the choice that looks best *right now*, and never revisits it.

**Why it matters.** When greedy is correct it is usually the simplest and fastest solution (often just "sort, then one pass" = O(n log n)). The interview skill is knowing *when* it is correct and being able to justify it.

**When greedy works.** Two properties must hold:
- **Greedy-choice property** - some optimal solution starts with the greedy choice.
- **Optimal substructure** - after making that choice, the remaining problem is a smaller instance of the same problem.

The usual proof is an **exchange argument**: take any optimal solution, swap its first choice for the greedy choice, and show the result is no worse. Repeat for every step.

| | Greedy | Dynamic programming |
|---|---|---|
| Decisions | one locally best choice per step, never undone | considers all choices for each subproblem |
| Speed | usually O(n log n) | usually O(n * something) |
| Correctness | only with the greedy-choice property (needs a proof) | always correct when the recurrence is right |
| Example where it wins | activity selection, fractional knapsack, Dijkstra, Huffman | 0/1 knapsack, coin change with arbitrary coins, LCS |

### Activity selection (interval scheduling)

**Problem.** Given activities with start and end times, select the maximum number of non-overlapping activities (one room, one person).

**Example.** `(1,4) (3,5) (0,6) (5,7) (3,9) (5,9) (6,10) (8,11) (8,12) (2,14) (12,16)` gives 4 activities: `(1,4) (5,7) (8,11) (12,16)`.

**Intuition.** Always pick the activity that **finishes earliest** among those compatible with what you already picked - it leaves the most time for everything else. Sorting by start time or by shortest duration both fail on simple counter-examples.

**Proof intuition (exchange argument).** Let `g` be the earliest-finishing activity and `o` the first activity in some optimal schedule. Since `g` ends no later than `o`, replacing `o` with `g` cannot create an overlap, so there is an optimal schedule that starts with `g`. Apply the same argument to the remaining activities that start after `g` ends.

**Approach.**
1. Sort by end time.
2. Keep `lastEnd`; take an activity if `start >= lastEnd`, then update `lastEnd`.

```csharp
// O(n log n) for the sort + O(n) scan, O(n) for the sorted copy.
static List<(int Start, int End)> SelectActivities((int Start, int End)[] activities)
{
    var chosen = new List<(int Start, int End)>();
    int lastEnd = int.MinValue;
    foreach (var a in activities.OrderBy(a => a.End))
    {
        if (a.Start >= lastEnd)               // compatible with the last chosen one
        {
            chosen.Add(a);
            lastEnd = a.End;
        }
    }
    return chosen;
}
```

**Edge cases.** Empty input, touching intervals (`end == start` - clarify whether that counts as overlap), identical intervals, one activity covering everything.

:::q Follow-up: what is the minimum number of intervals to remove so the rest do not overlap?
It is `n - (maximum number of non-overlapping intervals)`, so it is the same earliest-end greedy. That is the classic "non-overlapping intervals" problem.
:::

### Fractional knapsack

**Problem.** Same as knapsack, but you may take a *fraction* of an item. Maximise the value within the weight capacity.

**Example.** Items `(weight 10, value 60)`, `(20, 100)`, `(30, 120)`, capacity `50` gives `240`: all of item 1 (60), all of item 2 (100), and 20/30 of item 3 (80).

**Intuition.** Because items can be split, value per unit of weight is all that matters. Fill the bag with the highest `value / weight` first; the last item may be taken partially.

**Proof intuition.** If an optimal bag contains some weight of a lower-ratio item while a higher-ratio item is not fully used, swapping an equal amount of weight from the lower-ratio item to the higher-ratio item increases (or keeps) the value - so the greedy filling order is optimal.

```csharp
// O(n log n) time, O(n) for the sorted order.
static double FractionalKnapsack((int Weight, int Value)[] items, int capacity)
{
    double total = 0;
    foreach (var item in items.OrderByDescending(i => (double)i.Value / i.Weight))
    {
        if (capacity == 0) break;
        int take = Math.Min(item.Weight, capacity);
        total += item.Value * (double)take / item.Weight;   // full item or a fraction
        capacity -= take;
    }
    return total;
}
// FractionalKnapsack(new[] { (10, 60), (20, 100), (30, 120) }, 50) -> 240
```

**Edge cases.** Zero capacity, zero-weight items (division by zero - filter them and always take them), capacity larger than the total weight.

:::warn Greedy does not solve 0/1 knapsack
With weights `[10, 20, 30]`, values `[60, 100, 120]`, capacity `50`, ratio-greedy takes items 1 and 2 for 160, but the optimum is items 2 and 3 for 220. When items cannot be split you need the DP table from the Dynamic Programming group.
:::

### Scheduling problems

#### Job sequencing with deadlines

**Problem.** Each job takes one time unit, has a deadline and a profit. Only one job runs at a time. Maximise profit.

**Example.** `(deadline, profit)`: `(2,100) (1,19) (2,27) (1,25) (3,15)` gives 3 jobs and profit `142` (100 + 27 + 15).

**Intuition.** Consider the most profitable jobs first, and schedule each one in the **latest free slot** before its deadline - that keeps earlier slots free for jobs with tighter deadlines.

```csharp
// O(n log n + n * D) time, O(D) space where D is the largest deadline.
static (int Count, int Profit) JobSequencing((int Deadline, int Profit)[] jobs)
{
    if (jobs.Length == 0) return (0, 0);
    int maxDeadline = jobs.Max(j => j.Deadline);
    var used = new bool[maxDeadline + 1];        // used[t]: time slot t (1-based) is taken
    int count = 0, profit = 0;
    foreach (var job in jobs.OrderByDescending(j => j.Profit))
    {
        for (int t = job.Deadline; t >= 1; t--)  // latest free slot first
        {
            if (used[t]) continue;
            used[t] = true;
            count++;
            profit += job.Profit;
            break;
        }
    }
    return (count, profit);
}
```

#### Minimum meeting rooms

**Problem.** Given meeting intervals, how many rooms are needed so no two overlapping meetings share a room?

**Example.** `(0,30) (5,10) (15,20)` needs `2` rooms.

**Intuition.** Sort start times and end times separately and sweep: each start either reuses a room whose meeting has already ended (advance the end pointer) or needs a new room. Equivalent: a min-heap of end times (`PriorityQueue<int,int>`) where the top is the room that frees up first.

```csharp
// O(n log n) time, O(n) space.
static int MinMeetingRooms((int Start, int End)[] meetings)
{
    int[] starts = meetings.Select(m => m.Start).OrderBy(x => x).ToArray();
    int[] ends = meetings.Select(m => m.End).OrderBy(x => x).ToArray();
    int rooms = 0, e = 0;
    for (int s = 0; s < starts.Length; s++)
    {
        if (starts[s] < ends[e]) rooms++;   // nobody has left yet: open a new room
        else e++;                           // a meeting ended: reuse its room
    }
    return rooms;
}
// MinMeetingRooms(new[] { (0, 30), (5, 10), (15, 20) }) -> 2
```

| Scheduling problem | Greedy rule | Complexity |
|---|---|---|
| Max non-overlapping meetings in one room | earliest **end** time first | O(n log n) |
| Minimum rooms / platforms | sweep sorted starts and ends (or min-heap of ends) | O(n log n) |
| Job sequencing with deadlines | highest **profit** first, latest free slot | O(n log n + n*D) |
| Minimise average waiting time (one CPU) | shortest job first | O(n log n) |
| Minimise maximum lateness | earliest **deadline** first | O(n log n) |
| Merge overlapping intervals | sort by **start**, extend the last interval | O(n log n) |

:::q How do you convince an interviewer that your greedy algorithm is correct?
Use an exchange argument: take any optimal solution, show that replacing its first decision with the greedy decision does not make it worse, and that what is left is the same kind of problem. If you cannot find such an argument, try a small counter-example (for example coins `{1,3,4}` for amount 6). If greedy fails, switch to DP.
:::

:::q Weighted interval scheduling: each meeting has a value. Does earliest-end greedy still work?
No. A single high-value meeting can be worth more than several short ones. Sort by end time and use DP: `dp[i] = max(dp[i-1], value[i] + dp[p(i)])`, where `p(i)` is the last interval that ends before `i` starts (found with binary search). Total O(n log n).
:::

## Quick-fire Q&A

:::q What is Big-O, and why do we drop constants?
Big-O describes how the running time or memory grows as the input grows, as an upper bound. Constants and lower-order terms are dropped because for large `n` the growth rate dominates: `3n + 20` and `n` are both O(n). In practice constants still matter, so for small inputs a simple O(n^2) can beat a complex O(n log n).
:::

:::q What is the time complexity of a Dictionary lookup in .NET?
O(1) on average and O(n) in the worst case, when many keys land in the same bucket. Say this: "Average constant time, assuming a good `GetHashCode`. A bad hash makes it a linked scan."
:::

:::q Array vs List<T> vs LinkedList<T> - when do you use each?
Use an array when the size is fixed and you want speed. Use `List<T>` by default: O(1) index access and amortised O(1) `Add`. Use `LinkedList<T>` only when you insert or remove at known nodes very often and never index (for example the order list of an LRU cache). Its poor cache locality usually makes it slower than `List<T>` in practice.
:::

:::q What does "amortised O(1)" mean for List<T>.Add?
Most `Add` calls just write into spare capacity. When the list is full, it doubles its array and copies everything, which is O(n). Because doubling makes those copies rarer and rarer, the total work for `n` adds is O(n), so it is O(1) per add on average over the sequence. This is a worst-case total bound, not a probability.
:::

:::q Recursion vs iteration - what are the trade-offs in C#?
Recursion is clearer for trees, DFS and divide-and-conquer. Each call uses stack space, and C# does not guarantee tail-call optimisation. Deep recursion (roughly tens of thousands of frames) can throw `StackOverflowException`, which cannot be caught and kills the process. For deep or unbounded depth, convert to iteration with an explicit `Stack<T>`/`Queue<T>`.
:::

:::q Which sorting algorithm does Array.Sort use, and is it stable?
Introsort: quicksort, switching to heapsort when recursion gets too deep and to insertion sort for small partitions. It is O(n log n) in the worst case and in place, but **not stable**. Use LINQ `OrderBy`/`ThenBy` when equal keys must keep their order.
:::

:::q Why is quicksort O(n^2) in the worst case, and why is it still popular?
When the pivot is always the smallest or largest element (for example, sorted input with a last-element pivot), each partition removes only one element. It is popular because its average O(n log n) has small constants, it sorts in place, and it is cache friendly. Random or median-of-three pivots make the worst case very unlikely, and introsort removes it entirely.
:::

:::q BFS vs DFS - which finds the shortest path?
BFS, in an unweighted graph, because it explores vertices in order of distance. DFS finds *a* path, not necessarily the shortest one. For weighted graphs with non-negative weights use Dijkstra. With negative weights use Bellman-Ford.
:::

:::q Memoisation vs tabulation?
Both are DP. Memoisation is top-down: you write the recursion and cache the results, and only the states you need get computed. Tabulation is bottom-up: you fill a table in dependency order. That avoids recursion-depth problems and makes it easy to shrink the table to O(1) or O(row) memory.
:::

:::q How do you recognise a DP problem?
The question asks for a minimum, maximum, count of ways, or yes/no feasibility over a sequence of choices. A brute-force recursion would solve the same subproblems many times, and the best answer can be built from best answers to smaller prefixes or capacities. Examples: knapsack, coin change, LCS, edit distance, climbing stairs.
:::

:::q Greedy vs dynamic programming - how do you decide?
Try to prove the greedy choice with an exchange argument, and test it on small counter-examples. If a locally best choice can block a better global answer (0/1 knapsack, coin change with `{1,3,4}`), use DP. Greedy is correct for activity selection, fractional knapsack, Dijkstra and Huffman coding.
:::

:::q What is the space complexity of a recursive algorithm?
At least the maximum recursion depth multiplied by the frame size, plus any data structures. Recursive binary search uses O(log n) stack, recursive DFS on a skewed tree uses O(n), and merge sort uses O(n) for buffers plus O(log n) stack. Interviewers often check whether you count the call stack.
:::
