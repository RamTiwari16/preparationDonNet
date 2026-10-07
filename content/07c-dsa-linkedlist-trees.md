## Linked List

**Definition.** A *singly linked list* is a chain of nodes; each node holds a value and a reference to the next node. The list is identified by its `head`; the last node's `Next` is `null`.

**Why it matters.** Linked lists test pointer manipulation and edge-case discipline with no library help. The tricks (dummy node, fast/slow pointers, save-before-overwrite) transfer to trees, graphs and caches such as LRU.

| | Array / `List<T>` | Linked list |
|---|---|---|
| Access by index | O(1) | O(n) |
| Insert/delete at head | O(n) (array) | O(1) |
| Insert/delete after a known node | O(n) | O(1) |
| Memory | contiguous, cache friendly | pointer per node, scattered |
| .NET type | `List<T>` | `LinkedList<T>` (doubly linked) |

:::tip Four habits that prevent 90% of linked-list bugs
1. Draw 3-4 nodes on paper and move the pointers by hand. 2. Save `cur.Next` *before* you overwrite it. 3. Use a **dummy (sentinel) node** when the head may change. 4. Always test: empty list, one node, two nodes, and the head/tail positions.
:::

### The node class and a minimal list

```csharp
public class ListNode
{
    public int Val;
    public ListNode? Next;
    public ListNode(int val, ListNode? next = null) { Val = val; Next = next; }
}

// Helpers used by the examples below.
static ListNode? Build(params int[] values)
{
    var dummy = new ListNode(0);
    var tail = dummy;
    foreach (int v in values)
    {
        tail.Next = new ListNode(v);
        tail = tail.Next;
    }
    return dummy.Next;
}

static string Show(ListNode? head)
{
    var parts = new List<string>();
    for (var n = head; n is not null; n = n.Next) parts.Add(n.Val.ToString());
    return string.Join(" -> ", parts);       // "1 -> 2 -> 3"
}

public class SinglyLinkedList
{
    public ListNode? Head { get; private set; }
    public int Count { get; private set; }

    public void AddFirst(int val)                       // O(1)
    {
        Head = new ListNode(val, Head);
        Count++;
    }

    public void AddLast(int val)                        // O(n): walk to the tail
    {
        var node = new ListNode(val);
        if (Head is null) Head = node;
        else
        {
            var cur = Head;
            while (cur.Next is not null) cur = cur.Next;
            cur.Next = node;
        }
        Count++;
    }

    public bool Remove(int val)                         // O(n): remove first match
    {
        if (Head is null) return false;
        if (Head.Val == val) { Head = Head.Next; Count--; return true; }
        for (var cur = Head; cur.Next is not null; cur = cur.Next)
        {
            if (cur.Next.Val == val)
            {
                cur.Next = cur.Next.Next;               // unlink
                Count--;
                return true;
            }
        }
        return false;
    }

    public bool Contains(int val)                       // O(n)
    {
        for (var cur = Head; cur is not null; cur = cur.Next)
            if (cur.Val == val) return true;
        return false;
    }
}
```

:::q Why is AddLast O(n) here, and how do you make it O(1)?
Because we only keep `Head`, so we must walk to the last node. Keep a `Tail` pointer as well (update it on add and when the last node is removed) and appending becomes O(1). .NET's `LinkedList<T>` keeps both ends and each node has `Previous` and `Next`.
:::

### Reverse a linked list

**Problem.** Reverse a singly linked list and return the new head.

**Example.** `1 -> 2 -> 3 -> 4` becomes `4 -> 3 -> 2 -> 1`.

**Intuition.** Every node's `Next` must point to its *previous* node instead. Walk once, keeping three references: `prev` (already reversed part), `cur` (node being processed) and `next` (saved so you do not lose the rest).

**Approach (iterative).**
1. `prev = null`, `cur = head`.
2. While `cur != null`: save `next = cur.Next`; set `cur.Next = prev`; move `prev = cur`; `cur = next`.
3. Return `prev`.

**Approach (recursive).** Reverse the rest of the list first (`head.Next`), then make the node after `head` point back to `head`, and cut `head.Next`.

```csharp
// Iterative: O(n) time, O(1) space.
static ListNode? ReverseIterative(ListNode? head)
{
    ListNode? prev = null, cur = head;
    while (cur is not null)
    {
        ListNode? next = cur.Next;   // 1. remember the rest
        cur.Next = prev;             // 2. flip the pointer
        prev = cur;                  // 3. advance prev
        cur = next;                  // 4. advance cur
    }
    return prev;
}

// Recursive: O(n) time, O(n) space (call stack).
static ListNode? ReverseRecursive(ListNode? head)
{
    if (head?.Next is null) return head;                 // empty or single node
    ListNode newHead = ReverseRecursive(head.Next)!;     // reverse the tail
    head.Next.Next = head;                               // node after head points back
    head.Next = null;                                    // head becomes the new tail
    return newHead;
}
// Show(ReverseIterative(Build(1, 2, 3, 4))) -> "4 -> 3 -> 2 -> 1"
```

**Complexity.**

| Version | Time | Space |
|---|---|---|
| Iterative | O(n) | O(1) |
| Recursive | O(n) | O(n) call stack (risk of `StackOverflowException` for ~100k+ nodes) |

**Edge cases.** `null` head, one node, two nodes.

:::q Follow-up: reverse only the nodes between positions left and right, or in groups of k.
For positions: use a dummy node, walk to the node before `left`, then reverse `right-left` links with the same prev/cur loop and stitch the two ends. For groups of `k`: reverse each block of `k` nodes in place and connect the blocks, leaving the final short block as is. Both stay O(n) time and O(1) space.
:::

### Detect a cycle (Floyd's tortoise and hare)

**Problem.** Decide whether a linked list contains a cycle; then find the node where the cycle begins.

**Example.** `1 -> 2 -> 3 -> 4 -> 2 (back to the node with value 2)` has a cycle starting at `2`.

**Intuition.** Walk a *slow* pointer one step and a *fast* pointer two steps at a time. Without a cycle, `fast` reaches `null`. With a cycle, `fast` gains one node per step on `slow` inside the loop, so they must meet.

**Why the start can be found.** Let `L` be the distance from head to the cycle start, `C` the cycle length, and `k` how far into the cycle they meet. When they meet, `slow` walked `L + k` and `fast` walked `2(L + k)`, so `L + k` is a multiple of `C`, i.e. `L = mC - k`. A new pointer starting at the head and `slow` walking from the meeting point, one step each, meet exactly at the cycle start after `L` steps.

**Approach.**
1. Brute force: store visited nodes in a `HashSet<ListNode>` - first repeat is the start (O(n) space).
2. Floyd: advance `slow` by 1 and `fast` by 2; if they meet there is a cycle.
3. To find the start: reset one pointer to `head`, move both one step at a time until they meet.

```csharp
// Brute force: HashSet of visited nodes (reference equality). O(n) time, O(n) space.
static ListNode? FindCycleStartHashSet(ListNode? head)
{
    var seen = new HashSet<ListNode>();
    for (var n = head; n is not null; n = n.Next)
        if (!seen.Add(n)) return n;
    return null;
}

// Floyd: O(n) time, O(1) space.
static bool HasCycle(ListNode? head)
{
    ListNode? slow = head, fast = head;
    while (fast?.Next is not null)
    {
        slow = slow!.Next;
        fast = fast.Next.Next;
        if (slow == fast) return true;
    }
    return false;
}

static ListNode? FindCycleStart(ListNode? head)
{
    ListNode? slow = head, fast = head;
    while (fast?.Next is not null)
    {
        slow = slow!.Next;
        fast = fast.Next.Next;
        if (slow == fast)                    // meeting point inside the cycle
        {
            ListNode? p = head;
            while (p != slow)                // both walk L steps
            {
                p = p!.Next;
                slow = slow!.Next;
            }
            return p;
        }
    }
    return null;
}

static int CycleLength(ListNode? head)
{
    ListNode? slow = head, fast = head;
    while (fast?.Next is not null)
    {
        slow = slow!.Next;
        fast = fast.Next.Next;
        if (slow == fast)
        {
            int length = 1;
            for (var n = slow!.Next; n != slow; n = n!.Next) length++;
            return length;
        }
    }
    return 0;
}
```

**Complexity.** O(n) time, O(1) space for Floyd.

**Edge cases.** Empty list, single node pointing to itself, cycle that includes the head, no cycle, two-node cycle.

:::q Follow-up: why does fast move two steps and not three?
Any speed difference of one step per iteration guarantees a meeting inside the cycle because the gap shrinks by exactly one node each step and cannot "jump over" the slow pointer. With three steps the gap shrinks by two and may skip over `slow`, so the meeting is not guaranteed for some cycle lengths (and the start-finding proof breaks). One-versus-two is the standard choice.
:::

### Find the middle node

**Problem.** Return the middle node of a singly linked list in a single pass. For an even length return the second middle.

**Example.** `1 -> 2 -> 3 -> 4 -> 5` returns node `3`. `1 -> 2 -> 3 -> 4` returns node `3`.

**Intuition.** When `fast` has travelled the whole list at double speed, `slow` has travelled exactly half of it.

```csharp
// Brute force: count, then walk n/2 nodes. Two passes.
static ListNode? MiddleTwoPass(ListNode? head)
{
    int n = 0;
    for (var cur = head; cur is not null; cur = cur.Next) n++;
    var mid = head;
    for (int i = 0; i < n / 2; i++) mid = mid!.Next;
    return mid;
}

// Slow/fast: one pass, O(n) time, O(1) space. Even length returns the second middle.
static ListNode? Middle(ListNode? head)
{
    ListNode? slow = head, fast = head;
    while (fast?.Next is not null)
    {
        slow = slow!.Next;
        fast = fast.Next.Next;
    }
    return slow;
}
// For the FIRST middle of an even list use: while (fast?.Next?.Next is not null)
```

**Complexity.** O(n) time, O(1) space.

**Edge cases.** Empty list (`null`), one node, two nodes (returns the second).

:::q Follow-up: how do you find the k-th node from the end in one pass?
Advance `fast` k nodes ahead, then move `slow` and `fast` together until `fast` reaches the end; `slow` is the k-th from the end. With a dummy node before the head the same trick deletes the k-th node from the end (stop one node earlier). O(n) time, O(1) space.
:::

### Merge two sorted lists

**Problem.** Merge two sorted linked lists into one sorted list by re-linking the existing nodes.

**Example.** `1 -> 2 -> 4` and `1 -> 3 -> 4` give `1 -> 1 -> 2 -> 3 -> 4 -> 4`.

**Intuition.** Same as the merge step of merge sort. Compare the two heads, attach the smaller to the result tail, advance that list. Using a *dummy* node removes the special case for the first node.

```csharp
// Iterative with a dummy node: O(n + m) time, O(1) space.
static ListNode? MergeSorted(ListNode? a, ListNode? b)
{
    var dummy = new ListNode(0);
    var tail = dummy;
    while (a is not null && b is not null)
    {
        if (a.Val <= b.Val) { tail.Next = a; a = a.Next; }   // <= keeps it stable
        else { tail.Next = b; b = b.Next; }
        tail = tail.Next;
    }
    tail.Next = a ?? b;                                      // attach the leftover list
    return dummy.Next;
}

// Recursive: O(n + m) time, O(n + m) call stack.
static ListNode? MergeRecursive(ListNode? a, ListNode? b)
{
    if (a is null) return b;
    if (b is null) return a;
    if (a.Val <= b.Val) { a.Next = MergeRecursive(a.Next, b); return a; }
    b.Next = MergeRecursive(a, b.Next);
    return b;
}
// Show(MergeSorted(Build(1, 2, 4), Build(1, 3, 4))) -> "1 -> 1 -> 2 -> 3 -> 4 -> 4"
```

**Complexity.** O(n + m) time; iterative O(1) extra space.

**Edge cases.** One or both lists `null`, lists of different lengths, all of one list smaller, equal values.

:::q Follow-up: merge k sorted lists.
Use a min-heap (`PriorityQueue<ListNode,int>`) holding the current head of every list: dequeue the smallest, append it, enqueue its `Next`. That is O(N log k) for `N` total nodes. Or merge pairwise in a divide-and-conquer fashion - same complexity, no heap.
:::

### Remove duplicate nodes

**Problem.** (a) Remove duplicates from a *sorted* list. (b) Remove duplicates from an *unsorted* list, keeping the first occurrence.

**Example.** Sorted `1 -> 1 -> 2 -> 3 -> 3` becomes `1 -> 2 -> 3`. Unsorted `3 -> 1 -> 3 -> 2 -> 1` becomes `3 -> 1 -> 2`.

**Intuition.** Sorted: duplicates are adjacent, so one pass comparing `cur` with `cur.Next` is enough. Unsorted: remember the values already seen in a `HashSet<int>` and unlink a node whose value was seen (track `prev`). Without extra memory you can fall back to O(n^2): for every node, scan the rest and remove equal ones.

```csharp
// Sorted: O(n) time, O(1) space.
static ListNode? RemoveDuplicatesSortedList(ListNode? head)
{
    var cur = head;
    while (cur?.Next is not null)
    {
        if (cur.Val == cur.Next.Val) cur.Next = cur.Next.Next;   // skip the duplicate
        else cur = cur.Next;
    }
    return head;
}

// Unsorted with a HashSet: O(n) time, O(n) space.
static ListNode? RemoveDuplicatesUnsorted(ListNode? head)
{
    var seen = new HashSet<int>();
    ListNode? prev = null;
    for (var cur = head; cur is not null; cur = cur.Next)
    {
        if (seen.Add(cur.Val)) prev = cur;       // first time: keep it
        else prev!.Next = cur.Next;              // seen before: unlink it
    }
    return head;
}

// Unsorted without extra memory: O(n^2) time, O(1) space.
static ListNode? RemoveDuplicatesNoBuffer(ListNode? head)
{
    for (var cur = head; cur is not null; cur = cur.Next)
    {
        for (var runner = cur; runner.Next is not null;)
        {
            if (runner.Next.Val == cur.Val) runner.Next = runner.Next.Next;
            else runner = runner.Next;
        }
    }
    return head;
}
```

**Complexity.**

| Version | Time | Space |
|---|---|---|
| Sorted | O(n) | O(1) |
| Unsorted + HashSet | O(n) | O(n) |
| Unsorted, no buffer | O(n^2) | O(1) |

**Edge cases.** Empty list, all values equal, duplicates at the tail, no duplicates.

:::q Follow-up: delete *every* node whose value appears more than once (keep only distinct values).
On a sorted list use a dummy node and a `prev` pointer: when `cur.Val == cur.Next.Val`, skip the whole run of equal values and set `prev.Next` to the node after the run; otherwise advance `prev`. The dummy node handles the case where the head itself is removed.
:::

## Trees

**Definition.** A *binary tree* is a hierarchy where each node has at most two children (`Left`, `Right`). A *binary search tree* (BST) adds an ordering rule: every value in a node's left subtree is smaller, every value in its right subtree is larger - and this holds for every node, not just the root.

**Why it matters.** Trees show up everywhere: file systems, the DOM, category hierarchies, expression parsing, indexes (SQL Server indexes are B+ trees), and `SortedDictionary`/`SortedSet` (red-black trees). Most tree solutions are a three-line recursion; the skill is choosing *which traversal* and *what each call returns*.

| Term | Meaning |
|---|---|
| Root / leaf | top node / node with no children |
| Depth of a node | edges from the root to the node |
| Height of a tree | longest root-to-leaf path (in nodes or edges - state which) |
| Full | every node has 0 or 2 children |
| Complete | every level full except possibly the last, filled left to right (binary heap shape) |
| Perfect | all leaves on the same level, all internal nodes have 2 children |
| Balanced | left/right heights differ by at most 1 at every node (AVL, red-black keep this) |

### Binary tree node and a sample tree

```csharp
public class TreeNode
{
    public int Val;
    public TreeNode? Left, Right;
    public TreeNode(int val, TreeNode? left = null, TreeNode? right = null)
    {
        Val = val;
        Left = left;
        Right = right;
    }
}

//        1
//       / \
//      2   3
//     / \
//    4   5
static TreeNode SampleTree() =>
    new(1, new TreeNode(2, new TreeNode(4), new TreeNode(5)), new TreeNode(3));
```

### Binary Search Tree: insert, search, delete

**Problem.** Implement `Insert`, `Search` (and `Delete`) on a BST.

**Intuition.** At each node the ordering rule tells you which half cannot contain the value, so you discard half the tree per step. That is O(h) where `h` is the height: O(log n) for a balanced tree, but O(n) if you insert sorted data into a plain BST (it degenerates into a linked list).

**Approach.**
1. *Search:* compare with the node; go left if smaller, right if larger; stop at equal or `null`.
2. *Insert:* search for the position where the value would be; attach a new leaf there.
3. *Delete:* leaf -> remove it; one child -> replace the node by that child; two children -> copy the in-order successor (smallest value in the right subtree) into the node, then delete the successor.

```csharp
// Recursive insert: returns the (possibly new) subtree root. O(h).
static TreeNode BstInsert(TreeNode? root, int val)
{
    if (root is null) return new TreeNode(val);
    if (val < root.Val) root.Left = BstInsert(root.Left, val);
    else if (val > root.Val) root.Right = BstInsert(root.Right, val);
    return root;                       // duplicates are ignored
}

// Iterative search: O(h) time, O(1) space.
static TreeNode? BstSearch(TreeNode? root, int val)
{
    var cur = root;
    while (cur is not null && cur.Val != val)
        cur = val < cur.Val ? cur.Left : cur.Right;
    return cur;
}

// Recursive search for comparison.
static TreeNode? BstSearchRecursive(TreeNode? root, int val)
{
    if (root is null || root.Val == val) return root;
    return val < root.Val ? BstSearchRecursive(root.Left, val)
                          : BstSearchRecursive(root.Right, val);
}

static TreeNode? BstDelete(TreeNode? root, int val)
{
    if (root is null) return null;
    if (val < root.Val) root.Left = BstDelete(root.Left, val);
    else if (val > root.Val) root.Right = BstDelete(root.Right, val);
    else
    {
        if (root.Left is null) return root.Right;          // 0 or 1 child
        if (root.Right is null) return root.Left;
        TreeNode successor = root.Right;                   // 2 children
        while (successor.Left is not null) successor = successor.Left;
        root.Val = successor.Val;
        root.Right = BstDelete(root.Right, successor.Val);
    }
    return root;
}

static TreeNode? BuildBst(params int[] values)
{
    TreeNode? root = null;
    foreach (int v in values) root = BstInsert(root, v);
    return root;
}
// BuildBst(8, 3, 10, 1, 6, 14) builds:   8
//                                       / \
//                                      3   10
//                                     / \    \
//                                    1   6    14
```

**Complexity.**

| Operation | Balanced | Worst (skewed) |
|---|---|---|
| Search / insert / delete | O(log n) | O(n) |
| Space (recursive) | O(log n) | O(n) call stack |

**Edge cases.** Empty tree, duplicates (decide: ignore, count, or go right), deleting the root, inserting already-sorted data.

:::q A BST degenerates when you insert sorted data. How do you prevent it?
Use a self-balancing tree - AVL (strict balance, faster lookups) or red-black (fewer rotations, faster inserts) - which restructure with rotations after inserts and deletes to keep height O(log n). In .NET, `SortedDictionary<K,V>` and `SortedSet<T>` are red-black trees, so you rarely write one yourself.
:::

### Tree traversals

**Definition.** A traversal visits every node exactly once. Depth-first orders differ only in *when the node itself is visited*; level order visits breadth-first.

| Traversal | Order | Typical use |
|---|---|---|
| Inorder | Left, Node, Right | BST yields values in **sorted** order |
| Preorder | Node, Left, Right | copy/serialise a tree, prefix expression |
| Postorder | Left, Right, Node | delete a tree, compute sizes/heights (children first) |
| Level order | level by level | shortest depth, "view from the right", BFS |

For the sample tree (1 with children 2 and 3; 2 with children 4 and 5): inorder `4 2 5 1 3`, preorder `1 2 4 5 3`, postorder `4 5 2 3 1`, level order `[1] [2 3] [4 5]`.

```csharp
// Recursive DFS traversals: O(n) time, O(h) call stack.
static List<int> Inorder(TreeNode? root)
{
    var result = new List<int>();
    void Visit(TreeNode? n)
    {
        if (n is null) return;
        Visit(n.Left);
        result.Add(n.Val);          // visit between children
        Visit(n.Right);
    }
    Visit(root);
    return result;
}

static List<int> Preorder(TreeNode? root)
{
    var result = new List<int>();
    void Visit(TreeNode? n)
    {
        if (n is null) return;
        result.Add(n.Val);          // visit before children
        Visit(n.Left);
        Visit(n.Right);
    }
    Visit(root);
    return result;
}

static List<int> Postorder(TreeNode? root)
{
    var result = new List<int>();
    void Visit(TreeNode? n)
    {
        if (n is null) return;
        Visit(n.Left);
        Visit(n.Right);
        result.Add(n.Val);          // visit after children
    }
    Visit(root);
    return result;
}

// Iterative inorder with an explicit stack: O(n) time, O(h) space.
static List<int> InorderIterative(TreeNode? root)
{
    var result = new List<int>();
    var stack = new Stack<TreeNode>();
    var cur = root;
    while (cur is not null || stack.Count > 0)
    {
        while (cur is not null)             // go as far left as possible
        {
            stack.Push(cur);
            cur = cur.Left;
        }
        cur = stack.Pop();                  // leftmost unvisited node
        result.Add(cur.Val);
        cur = cur.Right;                    // then its right subtree
    }
    return result;
}

// Iterative preorder: push right first so left is processed first.
static List<int> PreorderIterative(TreeNode? root)
{
    var result = new List<int>();
    if (root is null) return result;
    var stack = new Stack<TreeNode>();
    stack.Push(root);
    while (stack.Count > 0)
    {
        var n = stack.Pop();
        result.Add(n.Val);
        if (n.Right is not null) stack.Push(n.Right);
        if (n.Left is not null) stack.Push(n.Left);
    }
    return result;
}

// Level order (BFS) with a queue: O(n) time, O(w) space (w = max width).
static List<List<int>> LevelOrder(TreeNode? root)
{
    var levels = new List<List<int>>();
    if (root is null) return levels;
    var queue = new Queue<TreeNode>();
    queue.Enqueue(root);
    while (queue.Count > 0)
    {
        int size = queue.Count;             // freeze the number of nodes in this level
        var level = new List<int>(size);
        for (int i = 0; i < size; i++)
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

**Complexity.** All traversals O(n) time. Recursive DFS uses O(h) stack (O(n) for a skewed tree); level order uses O(w) queue space (up to n/2 for a complete tree).

**Edge cases.** Empty tree, single node, skewed trees (deep recursion risk), `null` children.

:::tip Post-order iteratively
The easy trick: do an iterative preorder visiting *Node, Right, Left* (push left first, then right), then reverse the result list - which yields Left, Right, Node.
:::

:::q Which traversal gives sorted output for a BST, and how do you get the k-th smallest?
Inorder. For the k-th smallest, run an iterative inorder and stop after popping the k-th node - O(h + k) time instead of visiting the whole tree. If you query it often, store subtree sizes in each node so the k-th element is found in O(h).
:::

### Height of a tree

**Problem.** Return the height (maximum depth) of a binary tree. Here height = number of nodes on the longest root-to-leaf path, so an empty tree is `0`.

**Intuition.** The height of a node is `1 + max(height(left), height(right))`. An empty subtree has height 0. This is a postorder computation: children first.

```csharp
// Recursive: O(n) time, O(h) space.
static int Height(TreeNode? n) =>
    n is null ? 0 : 1 + Math.Max(Height(n.Left), Height(n.Right));

// Iterative with BFS: count levels. O(n) time, O(w) space.
static int HeightIterative(TreeNode? root)
{
    if (root is null) return 0;
    var queue = new Queue<TreeNode>();
    queue.Enqueue(root);
    int height = 0;
    while (queue.Count > 0)
    {
        height++;
        for (int i = queue.Count; i > 0; i--)       // i starts at the level size
        {
            var n = queue.Dequeue();
            if (n.Left is not null) queue.Enqueue(n.Left);
            if (n.Right is not null) queue.Enqueue(n.Right);
        }
    }
    return height;
}

// Bonus: is the tree height-balanced? Return -1 as a "unbalanced" signal. O(n).
static bool IsHeightBalanced(TreeNode? root)
{
    int Check(TreeNode? n)
    {
        if (n is null) return 0;
        int l = Check(n.Left);
        if (l < 0) return -1;
        int r = Check(n.Right);
        if (r < 0 || Math.Abs(l - r) > 1) return -1;
        return 1 + Math.Max(l, r);
    }
    return Check(root) >= 0;
}
// Height(SampleTree()) -> 3
```

**Complexity.** O(n) time, O(h) space (recursive) or O(w) (BFS).

**Edge cases.** Empty tree (0 vs -1 convention), skewed tree, single node.

:::q Height measured in nodes or edges - which should I use?
Say which one you use before coding. Many textbooks define a single node as height 0 (edges) while LeetCode-style problems count nodes (height 1). The conversion is `edges = nodes - 1`. Stating the convention avoids an off-by-one argument.
:::

### Validate a BST

**Problem.** Check whether a binary tree is a valid BST.

**Example.** `[2, 1, 3]` is valid. `[5, 1, 6, null, null, 3, 7]` is *not* valid, because `3` sits in the right subtree of `5`.

**Intuition.** The rule applies to the whole subtree, not just a node's direct children. Pass down the allowed open interval `(min, max)`: going left sets `max = node.Val`; going right sets `min = node.Val`. Use `long` bounds so a node holding `int.MinValue` or `int.MaxValue` is handled.

```csharp
// Bounds: O(n) time, O(h) space.
static bool IsValidBst(TreeNode? root) => IsValidBst(root, long.MinValue, long.MaxValue);

static bool IsValidBst(TreeNode? n, long min, long max)
{
    if (n is null) return true;
    if (n.Val <= min || n.Val >= max) return false;       // strict: no duplicates
    return IsValidBst(n.Left, min, n.Val) && IsValidBst(n.Right, n.Val, max);
}

// Inorder must be strictly increasing: O(n) time, O(h) space.
static bool IsValidBstInorder(TreeNode? root)
{
    long prev = long.MinValue;
    var stack = new Stack<TreeNode>();
    var cur = root;
    while (cur is not null || stack.Count > 0)
    {
        while (cur is not null) { stack.Push(cur); cur = cur.Left; }
        cur = stack.Pop();
        if (cur.Val <= prev) return false;
        prev = cur.Val;
        cur = cur.Right;
    }
    return true;
}
```

**Complexity.** O(n) time, O(h) space.

**Edge cases.** Empty tree (valid), single node, duplicates (usually invalid), `int.MinValue`/`int.MaxValue` nodes, a node that obeys its parent but violates a grandparent.

:::warn The classic wrong answer
Checking only `node.Left.Val < node.Val < node.Right.Val` passes `[5,1,6,null,null,3,7]` even though it is not a BST. You must carry the bounds from all ancestors (or use the inorder-increasing property).
:::

### Lowest common ancestor (LCA)

**Problem.** Given two nodes `p` and `q`, return the deepest node that has both as descendants (a node counts as its own descendant).

**Intuition.** *In a BST* the ordering tells you the answer: if both values are smaller go left, both larger go right, otherwise the current node is the split point and the LCA. *In a general binary tree* recurse into both subtrees: if both sides return a node, the current node is the LCA; if only one does, bubble that up.

```csharp
// BST: O(h) time, O(1) space.
static TreeNode? LcaBst(TreeNode? root, int p, int q)
{
    var cur = root;
    while (cur is not null)
    {
        if (p < cur.Val && q < cur.Val) cur = cur.Left;
        else if (p > cur.Val && q > cur.Val) cur = cur.Right;
        else return cur;                 // paths diverge here (or one equals cur)
    }
    return null;
}

// General binary tree: O(n) time, O(h) space.
static TreeNode? Lca(TreeNode? root, TreeNode p, TreeNode q)
{
    if (root is null || root == p || root == q) return root;
    TreeNode? left = Lca(root.Left, p, q);
    TreeNode? right = Lca(root.Right, p, q);
    return left is not null && right is not null ? root : left ?? right;
}
```

**Edge cases.** One node is the ancestor of the other, nodes not present in the tree, root as the LCA.

:::q Follow-up: what are other classic tree problems to practise?
Diameter of a tree (max over nodes of `leftHeight + rightHeight`), maximum path sum, serialize/deserialize, invert a tree (swap children recursively), symmetric tree, path sum, right-side view (level order, take the last node of each level), and construct a tree from preorder + inorder. Almost all are a postorder recursion where each call returns one number up and updates a global answer.
:::
