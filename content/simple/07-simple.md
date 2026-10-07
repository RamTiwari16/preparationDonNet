### The 7-step framework

**In simple words:** A coding round tests how you think, not only your final code. Follow seven steps: clarify, write examples, give a brute-force (simple but slow) answer, improve it, code, test, and state the cost. Saying each step aloud lets the interviewer follow your thinking.

**Real-life example:** A good doctor does not prescribe at once. They ask questions, examine you, consider a simple treatment, improve it, and explain the risks.

**Interview question:** How do you approach a coding problem you have never seen before?

**Simple answer:** I restate the problem and ask about empty input, duplicates, negatives and input size. I write examples, say a brute-force solution with its complexity, then find the slow part and pick a pattern to fix it. After coding, I dry-run (trace by hand) my code on the examples and state the time and space complexity.

### Pattern cheat-sheet

**In simple words:** Most interview problems are a known pattern in disguise. Words in the question are clues. "Sorted" suggests two pointers or binary search, "contiguous subarray" suggests a sliding window, and "have I seen this?" suggests a dictionary. "Fewest steps" suggests BFS, and "number of ways" suggests dynamic programming.

**Real-life example:** A mechanic hears a strange noise and guesses the cause from experience. Clue words in a problem work the same way: they point to the right tool.

**Interview question:** How do you decide which technique to use?

**Simple answer:** I look for signals. Sorted data means two pointers or binary search; a contiguous range means a sliding window; fast lookups mean a `Dictionary` or `HashSet`; "top K" means a heap. If the question asks for a minimum, maximum or count of ways with repeated subproblems, I use dynamic programming, and I name the pattern aloud.

### Reverse an array in place

**In simple words:** Use two pointers (indexes that mark positions): one at the start and one at the end. Swap the two values, then move both pointers one step toward the middle. Stop when they meet. You need no second array.

**Real-life example:** Two people stand at both ends of a row of chairs. They swap the chairs in front of them, step toward each other, and repeat until they meet.

**Interview question:** How do you rotate an array right by k positions without extra memory?

**Simple answer:** First I set `k = k % n`, so a large k still works. Then I reverse the whole array, reverse the first k items, and reverse the rest. Each reversal is the two-pointer swap, so time is O(n) (work grows in step with the array length) and extra space is O(1) (a fixed amount, whatever the size).

### Reverse a string

**In simple words:** In C#, a string cannot be changed after it is created (it is *immutable*). So copy its characters into a `char[]` array. Swap characters from both ends toward the middle, like an array. Then build a new string from the array.

**Real-life example:** You cannot rearrange the letters printed on a sign. You copy the letters onto cards, rearrange the cards, and print a new sign.

**Interview question:** Why does reversing a string need O(n) extra memory, even with two pointers?

**Simple answer:** Strings are immutable, so I need a changeable copy, like a `char[]`, and then a new string. The swap is in place on the copy, and time is O(n) because I touch each character once. For real text, I mention that some characters, like emoji, use two `char`s, so reversing `char`s can break them.

### Find duplicate elements

**In simple words:** Walk through the array once. Keep a `HashSet` (a fast collection of unique items) of the values you have seen. `HashSet.Add` returns `false` when the value is already there, so that value is a duplicate. Save duplicates in a second set so each one is reported once.

**Real-life example:** A guard at a party ticks names on a guest list. If a name is already ticked, the guard knows that person came in twice.

**Interview question:** What are your options, and what does each cost?

**Simple answer:** Comparing every pair is O(n^2) time (work grows with the square of the size) but needs no extra memory. Sorting first puts equal values side by side: O(n log n) time with little extra memory. A `HashSet` makes it one pass, O(n) time, but it uses O(n) memory, so I pick it unless memory is tight.

### Find the missing number

**In simple words:** The array should hold every number from 0 to n, but one is missing. The full total is n x (n + 1) / 2. Subtract the real total of the array; what is left is the missing number. XOR (a bit trick where equal numbers cancel out) also works and cannot overflow.

**Real-life example:** A class has roll numbers 1 to 30, and one student is absent. The teacher adds the roll numbers present; the shortfall from the full total is the absent student's number.

**Interview question:** What about overflow, and what if two numbers are missing?

**Simple answer:** I compute the sums in a `long`, or use XOR, so nothing overflows; both are O(n) time and O(1) space. With two missing numbers, one equation is not enough. The simplest fix is a `bool[]` of size n + 1 to mark what I see: O(n) time and O(n) space.

### Find the second largest

**In simple words:** Walk the array once with two variables: largest and second. When a value beats largest, the old largest moves down to second. When a value is below largest but above second, it replaces second. Values equal to largest are skipped, so duplicates do not count twice.

**Real-life example:** A race board shows only gold and silver. A faster runner pushes the gold winner down to silver; a runner between them only takes silver.

**Interview question:** Why not start "second" at `int.MinValue`?

**Simple answer:** If the array really contains `int.MinValue`, I cannot tell "no answer" from a real answer. So I use a nullable `int?` that starts as `null`. The method is one pass, O(n) time and O(1) space, while sorting would cost O(n log n).

### Find the maximum and minimum

**In simple words:** Start both min and max at the first element, not at 0, because every value might be negative. Then look at each remaining element once. Update min if it is smaller, and max if it is larger.

**Real-life example:** A teacher marks test papers one by one. She remembers the highest and lowest score so far and updates them as she goes.

**Interview question:** Can you find both with fewer comparisons?

**Simple answer:** My basic loop is O(n) time and O(1) space. To save comparisons, I take elements in pairs: compare the pair first, then the smaller with min and the larger with max. That is 3 comparisons per 2 elements, about 1.5n instead of 2n, but it is still O(n).

### Two Sum

**In simple words:** For each number x, you need its partner: `target - x`. Keep a dictionary of the numbers you have already passed, mapping value to index. For each new number, first check if its partner is in the dictionary. If yes, return both indexes; if not, store x and move on.

**Real-life example:** At a party, a host writes down every guest who arrives. Each new guest asks the host, "Is my partner already here?" instead of searching the whole room.

**Interview question:** Why check the dictionary before adding the current number?

**Simple answer:** If I add first, a number could pair with itself, like using one 3 for 3 + 3 = 6. Each lookup is O(1) on average, so the solution is O(n) time and O(n) space, instead of O(n^2) with two loops. If the array is sorted, two pointers give O(n) time and O(1) space.

```csharp
var seen = new Dictionary<int, int>();   // value -> index
for (int i = 0; i < nums.Length; i++)
{
    if (seen.TryGetValue(target - nums[i], out int j)) return [j, i];
    seen[nums[i]] = i;                    // add AFTER the check
}
return [];
```

### Remove duplicates from a sorted array

**In simple words:** The array is sorted, so equal values sit next to each other. Use a "read" pointer that visits every element and a "write" pointer that marks where the next unique value goes. When read finds a value different from the last written one, copy it to write and move write forward. Return write as the new length.

**Real-life example:** A librarian walks along a shelf of sorted books. She keeps the first copy of each title, slides it next to the last kept book, and skips the extra copies.

**Interview question:** What if each value may appear at most twice?

**Simple answer:** I compare with the value two slots back instead of one: copy when `write < 2 || a[read] != a[write - 2]`. Everything else stays the same. It is one pass, so O(n) time, and O(1) extra space because I change the array in place.

### Character frequency

**In simple words:** Walk the string once and add 1 to each character's counter. For lowercase a to z only, use an `int[26]` array. For any character, use a `Dictionary<char, int>`.

**Real-life example:** A shopkeeper counts the sweets in a jar by colour. He makes a tally mark under each colour as he takes them out.

**Interview question:** How do you find the first non-repeating character?

**Simple answer:** I use two passes. First I count every character; then I walk the string again and return the first character with count 1. Walking the string, not the dictionary, keeps the original order, and it is O(n) time and O(k) space for k different characters.

### Palindrome check

**In simple words:** A palindrome reads the same both ways, like "madam". Put one pointer at the start and one at the end, and compare the two characters. If they differ, it is not a palindrome; if they match, move both inward. To ignore case and punctuation, skip non-letters and compare in lowercase.

**Real-life example:** Two people read a word on a banner, one from each end. They call out letters as they walk toward each other; one different pair means it is not a palindrome.

**Interview question:** Why not just reverse the string and compare?

**Simple answer:** Reversing works, but it builds a full copy, so it needs O(n) extra memory. Two pointers compare in place, O(n) time and O(1) space, and they stop at the first mismatch. For the "ignore symbols" version, I skip characters that are not letters or digits and compare with `char.ToLowerInvariant`.

### Anagram check

**In simple words:** Two words are anagrams if they have the same letters, the same number of times, like "listen" and "silent". If the lengths differ, return `false`. Otherwise add 1 for each letter of the first word and subtract 1 for each letter of the second. If every counter ends at zero, they are anagrams.

**Real-life example:** Two children each get a bag of letter tiles. They lay the tiles out in piles by letter; if every pile matches, the bags hold the same letters.

**Interview question:** Is sorting or counting better?

**Simple answer:** Sorting both words and comparing is simple but O(n log n). Counting with an `int[26]` array is O(n) time and O(1) space. For any Unicode character, I use a `Dictionary<char, int>`, which is O(n) time and O(k) space.

### Dictionary and HashSet in .NET

**In simple words:** A `Dictionary` stores key-value pairs, and a `HashSet` stores unique items. Both use a hash code (a number calculated from the key) to jump straight to the right slot. So add, find and remove take O(1) time on average. This is the most common way to turn a slow nested loop into one fast pass.

**Real-life example:** A coat check gives you a numbered token. To return your coat, the staff go straight to that hook number instead of searching every hook.

**Interview question:** How does `Dictionary` handle collisions (two keys landing in the same slot)?

**Simple answer:** Each slot, called a bucket, points to a short chain of entries. A lookup walks that chain, comparing hash codes and then calling `Equals`. When the table is full, it grows and re-spreads the entries, so operations stay O(1) on average; a bad `GetHashCode` can make them O(n).

### Frequency counting

**In simple words:** First, count every item in one pass with a dictionary. Then answer the question from the counts: the most common item, the first unique one, or anything above a limit. This idea is the base of "top K frequent", "first unique character" and anagram problems.

**Real-life example:** After an election, officials first count the votes for each candidate. Only then do they announce the winner.

**Interview question:** Can you find the majority element (more than half) without a dictionary?

**Simple answer:** Yes, with Boyer-Moore voting. I keep one candidate and a counter: a matching item adds 1, a different item subtracts 1, and at zero the next item becomes the candidate. Different items cancel out, so the true majority survives; it is O(n) time and O(1) space.

### Two Sum and complement lookups

**In simple words:** A complement lookup means: remember what you have seen, then ask whether the value you need is already remembered. In Two Sum, the needed value is `target - x`. The same idea checks for a pair with a given difference, or counts all pairs that make a sum.

**Real-life example:** In a jigsaw puzzle, you keep the loose pieces on the table. For each new piece, you look for the one shape that fits it, not at every piece.

**Interview question:** When is two pointers better than a dictionary for Two Sum?

**Simple answer:** When the array is already sorted, or sorting is allowed, and memory is tight. Two pointers on sorted data take O(n) time and O(1) space. The dictionary suits unsorted data when I must return the original indexes, at O(n) time and O(n) space.

### Duplicate detection within a window

**In simple words:** You must find two equal values whose positions are at most k apart. Only the last k items matter, so keep them in a `HashSet`. Add each new item; if it is already there, you found a close duplicate. When the set grows past k, remove the oldest item.

**Real-life example:** A security guard remembers only the faces from the last ten minutes. If a face appears again in that time, he raises an alarm; older faces he forgets.

**Interview question:** What is the time and space complexity, and why?

**Simple answer:** Each item is added once and removed at most once, and `HashSet` operations are O(1) on average. So time is O(n). The set never holds more than about k items, so space is O(min(n, k)).

### HashSet problems

**In simple words:** A `HashSet` keeps unique items and answers "is this here?" in O(1) on average. It also has set tools like `UnionWith` and `IntersectWith`. A classic use is the longest run of consecutive numbers. Put all numbers in a set, then start counting only from numbers whose `x - 1` is missing.

**Real-life example:** To find the longest run of house numbers on a street, you start walking only at houses whose previous number does not exist. From there you count forward.

**Interview question:** Why is the longest consecutive sequence O(n), not O(n^2)?

**Simple answer:** The counting loop runs only from the start of each run. So each number is visited at most about twice in total, giving O(n) time and O(n) space. Sorting first also works in O(n log n), so I mention both.

### Group anagrams

**In simple words:** Anagrams look the same once their letters are sorted: "eat", "tea" and "ate" all become "aet". Use that sorted form as a dictionary key, and keep a list of words for each key. At the end, the dictionary values are your groups.

**Real-life example:** A post office puts every letter with the same postcode into the same bag. Here, the sorted letters act like the postcode.

**Interview question:** What is the complexity, and can you build the key faster?

**Simple answer:** For n words of length k, sorting each word gives O(n x k log k) time and O(n x k) space. A faster key is the count of the 26 letters, which avoids sorting. That makes it O(n x k) time.

### Subarray sum equals K (prefix sums + hashing)

**In simple words:** A prefix sum is the running total from the start to a position. A block of items sums to k exactly when "current total minus an earlier total" equals k. So as you walk, ask a dictionary how many earlier totals equal `current - k`, and add that to the answer. Start the dictionary with `{0: 1}`.

**Real-life example:** A bank statement shows your balance after each payment. To find a period where you spent exactly 500, you look for two balances that differ by 500.

**Interview question:** Why start with `{0: 1}`, and why not use a sliding window?

**Simple answer:** `{0: 1}` stands for "nothing taken yet"; without it, blocks that start at index 0 are missed. A sliding window fails because negative numbers break the rule "grow to add, shrink to remove". This method is O(n) time and O(n) space, instead of O(n^2) for trying every block.

### Implement a Stack

**In simple words:** A stack is "last in, first out" (LIFO). Build it with an array and a count: `Push` stores the item at position count and adds 1, and `Pop` subtracts 1 and returns that item. When the array is full, copy it into one twice as big. Linked nodes also work, with the first node as the top.

**Real-life example:** A pile of plates in a kitchen. You put a clean plate on top, and you also take the top plate first.

**Interview question:** Would you build it with an array or with linked nodes?

**Simple answer:** Usually an array: the items sit side by side in memory, which is fast, and it creates fewer objects. `Push` is amortised O(1) (O(1) on average, because doubling is rare), and `Pop` and `Peek` are O(1). Linked nodes give O(1) every time but need one object per item; either way, `Pop` on an empty stack throws `InvalidOperationException`.

### Implement a Queue

**In simple words:** A queue is "first in, first out" (FIFO). A plain array is slow, because removing the front shifts every item. Instead, use a circular buffer: keep a head index and a count, and wrap past the end with `%` (modulo). With linked nodes, keep both a head and a tail.

**Real-life example:** A sushi conveyor belt. Plates go on at one point and come off at another, and empty spots are reused as the belt turns.

**Interview question:** What is a circular queue, and why use it?

**Simple answer:** It is a fixed array treated as a ring, so freed slots at the front are reused. `Enqueue` and `Dequeue` are O(1) (`Enqueue` is O(1) on average, because growing is rare), and nothing shifts. .NET's `Queue<T>` works this way, while `List<T>.RemoveAt(0)` would cost O(n) per dequeue.

### Balanced parentheses

**In simple words:** Read the string from left to right. Push each opening bracket onto a stack. For a closing bracket, pop the stack and check it is the matching opener; if the stack is empty or the type differs, it is unbalanced. At the end, the stack must be empty.

**Real-life example:** Nesting boxes. You must close the box you opened most recently before you can close the box around it.

**Interview question:** With only one type of bracket, can you use O(1) space?

**Simple answer:** Yes, a counter is enough: add 1 for `(`, subtract 1 for `)`, fail if it goes below zero, and need zero at the end. With several bracket types the order matters, so I need the stack. The stack version is O(n) time and O(n) space.

### Next greater element (monotonic stack)

**In simple words:** For each number, find the first bigger number to its right. Keep a stack of positions still waiting for an answer; their values go down from bottom to top. When a new number is bigger than the top, it is that position's answer, so pop and record it, and repeat. Then push the new position.

**Real-life example:** People in a line each wait for the first taller person to arrive behind them. When a tall person arrives, every shorter person still waiting gets their answer at once.

**Interview question:** Why is it O(n) when there is a loop inside a loop?

**Simple answer:** Each position is pushed once and popped at most once. So the inner loop does at most n pops over the whole run, giving O(n) time and O(n) space. The same pattern solves daily temperatures, stock span and the largest rectangle in a histogram.

### Queue using two stacks

**In simple words:** Use an "in" stack and an "out" stack. `Enqueue` always pushes onto "in". To dequeue, if "out" is empty, pour everything from "in" into "out", which puts the oldest item on top; then pop from "out". Refill "out" only when it is empty.

**Real-life example:** You pile letters in a tray, newest on top. To read them oldest first, you flip the whole pile into a second tray.

**Interview question:** Why is `Dequeue` amortised O(1) when one call can be O(n)?

**Simple answer:** Each item is pushed to "in" once, moved to "out" once, and popped once: at most three steps in its life. So m operations cost O(m) in total, which is O(1) each on average. This is a guaranteed total, not luck, and `Enqueue` is always O(1).

### Stack using queue(s)

**In simple words:** A queue gives the oldest item, but a stack needs the newest. With one queue, after adding a new item, move every older item from the front to the back. Now the newest item is at the front, so `Pop` and `Peek` just take the front.

**Real-life example:** A new person joins a ticket queue, and everyone ahead steps out and rejoins behind them. Now the newest person is first in line.

**Interview question:** What do the one-queue and two-queue versions cost?

**Simple answer:** With one queue, `Push` is O(n) because of the rotation, and `Pop` and `Peek` are O(1). With two queues, `Push` is O(1), but `Pop` is O(n), because I move all but the last item to a helper queue and swap them. I choose based on which operation happens more often.

### The node class and a minimal list

**In simple words:** A linked list is a chain of nodes. Each node holds a value and a reference to the next node, and the list remembers only the first node, the head. The last node points to `null`. Adding at the front is fast, but adding at the end means walking the whole chain.

**Real-life example:** A treasure hunt. Each clue tells you where the next clue is, so to reach clue five you must follow clues one to four.

**Interview question:** Why is `AddLast` O(n) here, and how do you make it O(1)?

**Simple answer:** The list keeps only `Head`, so `AddLast` must walk to the end. If I also keep a `Tail` reference and update it on add and remove, appending becomes O(1). .NET's `LinkedList<T>` does this, and it is doubly linked, with `Next` and `Previous` on each node.

### Reverse a linked list

**In simple words:** Walk the list once and turn every arrow around. Keep three references: prev (the part already reversed), cur (the node you are working on) and next (saved so you do not lose the rest). For each node, save next, point cur to prev, then move prev and cur forward. At the end, prev is the new head.

**Real-life example:** A line of people each points to the person in front. You walk down the line and ask each one to point to the person behind instead.

**Interview question:** Would you write it iteratively or recursively?

**Simple answer:** Iteratively: O(n) time and O(1) extra space. The recursive version is also O(n) time, but it uses O(n) call-stack space, and a very long list can cause a `StackOverflowException`. In both, the key rule is to save `cur.Next` before changing it.

```csharp
ListNode? prev = null, cur = head;
while (cur is not null)
{
    var next = cur.Next;     // 1. save the rest
    cur.Next = prev;         // 2. flip the arrow
    prev = cur; cur = next;  // 3. move forward
}
return prev;
```

### Detect a cycle (Floyd's tortoise and hare)

**In simple words:** Move a slow pointer one step and a fast pointer two steps at a time. With no loop, fast reaches the end; with a loop, fast catches slow inside it. To find where the loop starts, put one pointer back at the head and move both one step at a time. They meet at the loop's first node.

**Real-life example:** Two runners on a track. On a circular track, the faster runner laps the slower one; on a straight road, the fast runner just reaches the end.

**Interview question:** Why does fast move two steps and not three?

**Simple answer:** With speeds one and two, the gap shrinks by exactly one node each step, so fast cannot jump over slow and they must meet. With three steps, it could skip past. Floyd's method is O(n) time and O(1) space, while a `HashSet` of visited nodes needs O(n) memory.

### Find the middle node

**In simple words:** Move a slow pointer one step and a fast pointer two steps at a time. When fast reaches the end, slow is at the middle. For an even number of nodes, this gives the second middle node.

**Real-life example:** Two friends start a trail together, and one walks twice as fast. When the fast one reaches the end, the slow one is exactly halfway.

**Interview question:** How do you find the k-th node from the end in one pass?

**Simple answer:** I move fast k nodes ahead first, then move both pointers one step at a time. When fast reaches the end, slow is k nodes from the end. Like the middle-node trick, this is O(n) time and O(1) space.

### Merge two sorted lists

**In simple words:** Compare the first nodes of both lists. Attach the smaller one to the result and move forward in that list, until one list is empty. Then attach the rest of the other list. A dummy node (a fake first node) removes special code for the head.

**Real-life example:** Two lines of students, each sorted by height, merge into one line. At each step, the shorter of the two front students steps forward.

**Interview question:** How do you merge k sorted lists?

**Simple answer:** For two lists, I relink the existing nodes, so it is O(n + m) time and O(1) extra space. For k lists, I put each list's head in a min-heap (`PriorityQueue`), take the smallest, attach it, and add its next node. That is O(N log k) for N nodes in total.

### Remove duplicate nodes

**In simple words:** In a sorted list, duplicates are neighbours, so compare each node with the next and skip the next if it is equal. In an unsorted list, keep a `HashSet` of values you have seen. If a value is already in the set, unlink that node by pointing the previous node past it.

**Real-life example:** Checking a class register. On a sorted register, a repeated name sits right below the first; on a messy one, you tick names on a sheet to spot repeats.

**Interview question:** How do you do it on an unsorted list with no extra memory?

**Simple answer:** For each node, I run a second pointer over the rest of the list and remove nodes with the same value. That is O(n^2) time but O(1) space. With a `HashSet` it is O(n) time and O(n) space, and a sorted list needs only one pass in O(n) time and O(1) space.

### Binary tree node and a sample tree

**In simple words:** A binary tree is made of nodes, and each node has a value and at most two children, `Left` and `Right`. The top node is the root, and nodes without children are leaves. In C#, a `TreeNode` class has `Val`, `Left` and `Right`. A small sample tree helps you test your code by hand.

**Real-life example:** A family tree where each parent has up to two children. You start at the top ancestor and move down.

**Interview question:** What is the difference between a binary tree and a binary search tree?

**Simple answer:** A binary tree only limits each node to two children. A binary search tree (BST) adds a rule: every value in the left subtree is smaller and every value in the right subtree is larger, at every node. That rule lets you search in O(h) time, where h is the tree height.

### Binary Search Tree: insert, search, delete

**In simple words:** To search, start at the root; go left if the value is smaller and right if it is larger, until you find it or reach `null`. To insert, search until `null` and add a new leaf there. To delete a node with two children, copy in the smallest value from its right subtree, then delete that node instead.

**Real-life example:** A guessing game: "Is it bigger or smaller than 50?" Each answer throws away half of the options.

**Interview question:** What happens if you insert sorted data, and how do you prevent it?

**Simple answer:** Operations cost O(h), where h is the height, so O(log n) when the tree is balanced. Sorted inserts turn the tree into a long chain, so h becomes n and operations become O(n). Self-balancing trees like AVL or red-black trees fix this, and .NET's `SortedDictionary` and `SortedSet` already use red-black trees.

### Tree traversals

**In simple words:** A traversal visits every node once. Depth-first orders differ only in when you record the node: preorder is node-left-right, inorder is left-node-right, and postorder is left-right-node. Level order visits the tree row by row with a queue.

**Real-life example:** Postorder is like a manager who signs a report only after every team member finishes their part. Level order is like a teacher greeting the front row first, then the next row.

**Interview question:** Which traversal gives sorted output for a BST, and how do you get the k-th smallest?

**Simple answer:** Inorder gives a BST's values in sorted order. For the k-th smallest, I run an iterative inorder with a stack and stop at the k-th node, in O(h + k) time. All traversals are O(n) time; depth-first uses O(h) space and level order uses O(w), where w is the widest level.

### Height of a tree

**In simple words:** The height of a node is 1 plus the bigger height of its two children, and an empty tree has height 0. So ask both children for their heights, take the bigger one, and add 1. You can also count the levels with a queue.

**Real-life example:** In a family tree, each person asks their children, "How many generations are below you?" They take the bigger answer and add one for themselves.

**Interview question:** Do you count height in nodes or in edges?

**Simple answer:** I state my convention before coding. Here I count nodes, so a single node has height 1; counting edges gives 0, because edges = nodes - 1. The recursive version is O(n) time and O(h) stack space, and the level version uses O(w) queue space.

### Validate a BST

**In simple words:** Comparing a node with its direct children is not enough. Every node must fit inside a range set by all its ancestors. Going left, the node's value becomes the new maximum; going right, it becomes the new minimum. If any node falls outside its range, the tree is not a BST.

**Real-life example:** School groups by age. A child placed in "under 10" and then in the "over 7" subgroup must be between 7 and 10, because each split narrows the range.

**Interview question:** What is the classic wrong answer?

**Simple answer:** Checking only left < node < right at each node. The tree [5, 1, 6, null, null, 3, 7] passes that check, but 3 sits in the right subtree of 5, so it is invalid. I pass min and max bounds down (as `long`, so extreme `int` values still work), or check that an inorder walk is strictly increasing; both are O(n) time and O(h) space.

### Lowest common ancestor (LCA)

**In simple words:** The LCA of two nodes is the deepest node that has both below it, and a node counts as below itself. In a BST, go left if both values are smaller and right if both are larger; otherwise the current node is the split point and the answer. In a normal binary tree, search both sides; if both sides find a node, the current node is the LCA.

**Real-life example:** Two cousins look for their closest shared relative. They go up the family tree until they reach the first person who is an ancestor of both.

**Interview question:** How does the solution change between a BST and a normal binary tree?

**Simple answer:** In a BST the order tells me the direction, so one path down is enough: O(h) time and O(1) space. In a normal tree, I recurse into both sides and return whatever each side finds. If both sides find something, the current node is the answer; this is O(n) time and O(h) space.

### Graph representation

**In simple words:** A graph is a set of nodes (vertices) joined by edges. An adjacency list stores, for each node, a list of its neighbours. An adjacency matrix is a V x V table where each cell says whether an edge exists. Lists suit sparse graphs (few edges), and matrices suit small, dense graphs.

**Real-life example:** Your phone contacts are like an adjacency list: each person has a list of friends. A big chart with every name on both sides and a tick for each friendship is a matrix.

**Interview question:** Which representation do you pick and why?

**Simple answer:** An adjacency list by default, because most real graphs are sparse. It uses O(V + E) memory, and visiting a node's neighbours costs only its number of neighbours. I pick a matrix when the graph is small and dense or I need O(1) "is there an edge?" checks; it uses O(V^2) memory.

### Breadth-first search (BFS)

**In simple words:** BFS visits nodes level by level, nearest first. Put the start node in a queue and mark it visited. Then repeatedly take a node from the queue and add each unvisited neighbour, marking it visited as you add it. Stop when the queue is empty.

**Real-life example:** Ripples in a pond. The water moves out in rings: first the closest ring, then the next one.

**Interview question:** Why mark a node visited when you add it to the queue, not when you take it out?

**Simple answer:** If I mark it only when I take it out, different neighbours can add the same node many times. Marking on add means each node enters the queue once. So BFS runs in O(V + E) time, where V is nodes and E is edges, and O(V) space.

### Depth-first search (DFS)

**In simple words:** DFS goes as deep as it can along one path, then backs up and tries the next path. Use recursion or your own stack, and mark nodes visited so you never loop forever. DFS is the base for cycle detection, topological sort, connected components and flood fill.

**Real-life example:** Exploring a maze: you follow one corridor to its end. At a dead end, you walk back to the last junction and try another corridor.

**Interview question:** BFS or DFS - how do you choose?

**Simple answer:** I use BFS for the fewest steps in an unweighted graph or for level-by-level work. I use DFS to explore all paths, detect cycles, or order dependencies. Both are O(V + E) time; for very deep graphs, I use an explicit stack to avoid a stack overflow.

### Shortest path in an unweighted graph

**In simple words:** BFS reaches nodes in order of distance, so the first time it reaches the target, it used the fewest edges. While searching, save each node's parent, the node you came from. At the end, follow the parents back from the target and reverse that list to get the path.

**Real-life example:** You explore a building and, in each room, write a note saying which room you came from. At the goal, you follow the notes back to the entrance.

**Interview question:** How do you find the shortest path in a grid with walls?

**Simple answer:** The grid is the graph: each open cell connects to the cells up, down, left and right. I run BFS from the start, store each cell's distance, and skip walls and visited cells. The first time I reach the goal, its distance is the answer, in O(rows x cols) time and space.

### PriorityQueue<TElement, TPriority> in 60 seconds

**In simple words:** `PriorityQueue`, added in .NET 6, always gives you the item with the smallest priority value first. It is a min-heap (a tree kept so the smallest item is always on top). `Enqueue` and `Dequeue` are O(log n), and `Peek` is O(1). For a max-heap, pass a comparer that reverses the order.

**Real-life example:** A hospital emergency room. Patients are not seen in arrival order; the most urgent case goes first.

**Interview question:** How do you change an item's priority in .NET's `PriorityQueue`?

**Simple answer:** It has no update method. The usual trick is to enqueue the item again with the new priority. When an old copy comes out later, I see it is stale (out of date) and skip it; this is called lazy deletion. I also remember that equal priorities come out in no fixed order.

### Dijkstra's shortest path (weighted graph)

**In simple words:** Dijkstra finds the cheapest total cost from one start node to every node, when no edge cost is negative. Keep a best-known distance for each node, and always take the closest unfinished node from a min-heap. For each edge from it, if the route to a neighbour gets cheaper, update it and push the neighbour. Skip heap entries that are out of date.

**Real-life example:** A delivery app plans routes outward from the depot, always extending from the closest place reached so far. Once a place is settled, no later route can beat it.

**Interview question:** Why does Dijkstra fail with negative edges, and what do you use instead?

**Simple answer:** Dijkstra assumes a finished node can never become cheaper, and a negative edge breaks that. Then I use Bellman-Ford, which is O(V x E) and also finds negative cycles. With a heap, Dijkstra is O((V + E) log V); for unweighted graphs, plain BFS is enough.

### Cycle detection

**In simple words:** In a directed graph, run DFS with three colours: white (new), gray (on the current path) and black (finished). Reaching a gray node means you came back to your own path, so there is a cycle. In an undirected graph, a visited neighbour that is not your parent means a cycle. Union-find also works: an edge that joins two nodes already in the same group closes a cycle.

**Real-life example:** An office request is passed from Bob to Ana to Raj and back to Bob. Meeting a person who is already in your current chain means you are going in circles.

**Interview question:** How do you order tasks with dependencies and detect impossible ones?

**Simple answer:** I use topological sort with Kahn's algorithm. I count each node's incoming edges, queue the nodes with zero, and each time I take one out I reduce its neighbours' counts. If the result has fewer than V nodes, there is a cycle; it runs in O(V + E).

### Bubble sort

**In simple words:** Walk through the array and swap any two neighbours that are in the wrong order. After each pass, the largest remaining value has moved to the end. Repeat on the unsorted part, and stop early if a whole pass makes no swaps.

**Real-life example:** Bubbles in a glass of soda. The biggest bubbles rise to the top first, one pass at a time.

**Interview question:** What is bubble sort's complexity, and is it ever useful?

**Simple answer:** It is O(n^2) time on average and in the worst case, with O(1) extra space. With the "no swaps" check, an already sorted array takes only O(n). It is stable (equal items keep their order), but it is mainly for teaching; in real code I call `Array.Sort`.

### Selection sort

**In simple words:** Find the smallest value in the unsorted part and swap it to the front. Then move the front boundary one step right and repeat. It always scans the whole unsorted part, even when the array is already sorted.

**Real-life example:** Arranging books by height. Each time, you search the pile for the shortest book and put it next on the shelf.

**Interview question:** When is selection sort useful, and is it stable?

**Simple answer:** It always does O(n^2) comparisons with O(1) extra space. But it makes at most n - 1 swaps, which helps when writing data is expensive. It is not stable, because a long swap can jump an item past an equal one.

### Insertion sort

**In simple words:** Build a sorted part on the left, one item at a time. Take the next item and slide it left past bigger items until it reaches its place. It is very fast on small or nearly sorted arrays.

**Real-life example:** Sorting playing cards in your hand. You pick up one card and slide it into place among the cards you have already sorted.

**Interview question:** Why do real libraries still use insertion sort?

**Simple answer:** Its worst case is O(n^2), but on nearly sorted data it is close to O(n), because each item moves only a little. It uses O(1) extra space, is stable, and has very little overhead. So .NET's introsort uses it for tiny pieces of 16 items or fewer.

### Merge sort

**In simple words:** Split the array into two halves and sort each half the same way (recursion). Then merge the two sorted halves: compare the front items and copy the smaller one into a temporary array. On a tie, take from the left half, so equal items keep their order.

**Real-life example:** Two teachers each sort half of the exam papers by name. Then they merge the two piles by always taking the top paper with the earlier name.

**Interview question:** Why is merge sort used for linked lists and huge files?

**Simple answer:** It is always O(n log n): about log n levels, each doing O(n) merge work. For arrays it needs O(n) extra space, and it is stable. It reads data in order, so it suits linked lists and files too big for memory, while quicksort is usually faster for arrays in memory.

### Quick sort (Lomuto partition)

**In simple words:** Pick a pivot value, and move smaller values to its left and larger values to its right. Now the pivot is in its final place. Sort the left and right parts the same way. In Lomuto partition, the pivot is the last item, and a boundary grows the "smaller" zone as you scan.

**Real-life example:** A teacher says, "Everyone shorter than Sam, stand left; everyone taller, stand right." Sam is now in his final spot, and each group repeats with a new leader.

**Interview question:** When is quicksort O(n^2), and how do you avoid it?

**Simple answer:** On average it is O(n log n) time with O(log n) stack space, and it sorts in place. If the pivot is always the smallest or largest, like sorted input with a last-item pivot, it becomes O(n^2). A random pivot or median-of-three makes this very unlikely; also note that quicksort is not stable.

### Sorting in .NET

**In simple words:** `Array.Sort` and `List<T>.Sort` use introsort. It starts with quicksort, switches to heapsort if recursion gets too deep, and uses insertion sort for tiny parts. So it is O(n log n) in the worst case and sorts in place, but it is not stable. LINQ `OrderBy` is stable and returns a new sequence.

**Real-life example:** A delivery company uses vans in the city, trucks for long trips and bikes for short hops. Introsort also picks the best method for each situation.

**Interview question:** What does "stable" mean, and when does it matter?

**Simple answer:** A stable sort keeps items with equal keys in their original order. If orders are sorted by date and then by customer, a stable second sort keeps each customer's orders in date order. `Array.Sort` is not stable, so then I use `OrderBy(...).ThenBy(...)`.

### Linear search

**In simple words:** Check the items one by one from the start. If one matches the target, return its index; if you reach the end, return -1. It works on any data, sorted or not, but it is slow for big inputs.

**Real-life example:** Looking for your keys by checking every pocket, one after another, until you find them.

**Interview question:** When would you use linear search, and when not?

**Simple answer:** Linear search is O(n) time and O(1) space, which is fine for small or unsorted data searched once. If I search the same data many times, I build a `HashSet` or `Dictionary` once, so each lookup is O(1) on average. If the data is sorted, binary search gives O(log n).

### Binary search

**In simple words:** It works only on sorted data. Look at the middle item: if it is the target, you are done. If the target is bigger, drop the left half; if smaller, drop the right half. Each step halves the range, so it takes about log2(n) steps.

**Real-life example:** Finding a word in a paper dictionary. You open the middle, see if your word comes before or after, and keep halving.

**Interview question:** What are the common bugs in binary search?

**Simple answer:** First, `(lo + hi) / 2` can overflow, so I write `lo + (hi - lo) / 2`. Second, with `hi = n - 1`, the loop must be `lo <= hi`, or I miss the last item. Third, I must move to `mid + 1` or `mid - 1`, or the loop can run forever; the loop version is O(log n) time and O(1) space.

```csharp
int lo = 0, hi = a.Length - 1;
while (lo <= hi)
{
    int mid = lo + (hi - lo) / 2;          // no overflow
    if (a[mid] == target) return mid;
    if (a[mid] < target) lo = mid + 1; else hi = mid - 1;
}
return -1;
```

### Fibonacci: recursion to O(1) space

**In simple words:** Each Fibonacci number is the sum of the two before it. The plain recursion computes the same values again and again, so it is very slow. Memoisation (saving each answer in a cache) or a table removes the repeats. Since you only ever need the last two numbers, two variables are enough.

**Real-life example:** A teacher keeps being asked the same sum, so she writes the answer on the board once. After that, she just reads it.

**Interview question:** Why is the plain recursive version so slow?

**Simple answer:** Each call makes two more calls, and F(n-2) is computed inside both F(n) and F(n-1), so time grows like O(2^n). Caching makes it O(n) time and O(n) space. A loop with two variables gives O(n) time and O(1) space; after F(92), `long` overflows, so I use `BigInteger`.

### Climbing stairs

**In simple words:** You climb 1 or 2 steps at a time. Your last move to step n came from step n - 1 or step n - 2. So ways(n) = ways(n - 1) + ways(n - 2), which is the Fibonacci pattern. Keep the last two values in a loop.

**Real-life example:** To land on step 5 with 1- or 2-step jumps, you must have just stood on step 4 or step 3. So you add the ways of reaching those two steps.

**Interview question:** If each step has a cost, how do you find the cheapest way up?

**Simple answer:** The pattern stays the same, but I use min instead of plus. The cost to reach step i is cost[i] plus the smaller of the costs for i - 1 and i - 2. It is still O(n) time and O(1) space with two rolling variables.

### 0/1 Knapsack

**In simple words:** Each item has a weight and a value, and the bag has a weight limit. You take each item once or not at all. Fill a table where each cell holds the best value using the first i items with capacity w. For each item, keep the better of "skip it" and "take it" (its value plus the best for the remaining capacity).

**Real-life example:** Packing a suitcase with a 20 kg airline limit. For each item, you decide to take it or leave it, to carry the most useful things.

**Interview question:** How do you save memory, and what is the trap?

**Simple answer:** The full table is O(n x W) time and space, where W is the capacity. I can keep one row to make space O(W). The trap is that the inner loop must go from the capacity down; going up lets one item be used many times, which is a different problem.

### Longest common subsequence (LCS)

**In simple words:** A subsequence keeps the order of characters but may skip some. Fill a table where cell (i, j) is the LCS length of the first i letters of one string and the first j letters of the other. If the two letters match, take the diagonal cell plus 1. If not, take the bigger of the cell above and the cell to the left.

**Real-life example:** File-compare (diff) tools use this idea. They find the longest set of lines both versions share, in the same order.

**Interview question:** How do you get the actual subsequence, not just its length?

**Simple answer:** I walk back from the bottom-right cell: on a match I keep the letter and move diagonally, otherwise I move toward the bigger neighbour. I reverse the kept letters at the end. The table takes O(m x n) time and space; two rows save memory but cannot rebuild the string.

### Coin change

**In simple words:** For the fewest coins, let best[a] be the fewest coins for amount a. Try every coin as the last coin: best[a] = 1 + best[a - coin], and keep the smallest. For the number of ways, loop over the coins on the outside and the amounts inside, so each combination is counted once.

**Real-life example:** A cashier making change asks, "If my last coin is a 5, how few coins can make the rest?" They check this for every coin and keep the best.

**Interview question:** Why not just pick the biggest coin first (greedy)?

**Simple answer:** Greedy fails for many coin sets. With coins 1, 3 and 4 and amount 6, greedy uses 4 + 1 + 1, three coins, but 3 + 3 needs only two. Dynamic programming tries every last coin, so it is always right, in O(amount x coins) time and O(amount) space.

### Activity selection (interval scheduling)

**In simple words:** You want the most non-overlapping activities in one room. Sort them by end time and take the first one. Then take each next activity that starts no earlier than the last chosen one ends. Always picking the earliest finish leaves the most time for the rest.

**Real-life example:** A busy person with one free afternoon picks the meeting that ends first, then the next one that starts after it. This fits in the most meetings.

**Interview question:** How do you prove the earliest-end choice is correct?

**Simple answer:** With an exchange argument: take any best schedule and swap its first activity for the one that ends earliest. It ends no later, so nothing new overlaps and the count stays the same; then repeat for the rest. The algorithm is O(n log n) for the sort plus one O(n) pass.

### Fractional knapsack

**In simple words:** Here you may take part of an item, like some grams of rice. So only the value per kilo matters. Sort the items by value divided by weight, highest first, and add whole items in that order. When the next item does not fit, take just the fraction that fills the bag.

**Real-life example:** Buying loose spices at a market with a small bag. You fill it with the most valuable spice per gram first, then the next.

**Interview question:** Does this greedy method work for 0/1 knapsack?

**Simple answer:** No. With weights 10, 20, 30, values 60, 100, 120 and capacity 50, the ratio greedy takes the first two items for 160, but items two and three give 220. When items cannot be split, I need dynamic programming; fractional knapsack is O(n log n) because of the sort.

### Scheduling problems

**In simple words:** Many scheduling problems are "sort, then one smart pass". For jobs with deadlines and profits, take the most profitable job first and put it in the latest free slot before its deadline. For meeting rooms, sort the start times and end times separately and sweep through them.

**Real-life example:** A railway station planning platforms. If a train arrives before any platform is free, the station needs one more platform.

**Interview question:** How many meeting rooms do you need for a list of meetings?

**Simple answer:** I sort the starts and ends separately and walk through the starts. If a meeting starts before the earliest running meeting ends, I need a new room; otherwise a room is free, so I reuse it and move the end pointer. This is O(n log n) time and O(n) space, and a min-heap of end times also works.
