### 1. Reverse a string

**In simple words:** C# strings cannot be changed (they are *immutable*), so copy the characters into a `char[]` array. Put one pointer (an index that marks a position) at each end. Swap the two characters and move both pointers toward the middle until they meet. Then build a new string from the array.

**Real-life example:** Two people hold the ends of a row of letter cards. They swap the cards in their hands, step inward, and swap again until they meet.

**Interview question:** How do you reverse each word but keep the word order?

**Simple answer:** I split the sentence on spaces, reverse each word with the same two-pointer swap, and join the words with spaces, so "hello world" becomes "olleh dlrow". It is O(n) time (the work grows in step with the text length). Space is also O(n), because strings are immutable and I need new buffers.

### 2. Reverse an array

**In simple words:** Use two pointers, one at the start and one at the end. Swap the two values, then move the left pointer right and the right pointer left. Stop when they meet in the middle. The array changes in place, with no copy.

**Real-life example:** Two people at opposite ends of a bookshelf swap books. They walk toward each other and keep swapping until they meet.

**Interview question:** How do you rotate the array right by k steps?

**Simple answer:** First I set `k = k % n`, so a large k still works. Then I reverse the whole array, reverse the first k items, and reverse the rest: [1,2,3,4,5,6,7] with k = 3 becomes [5,6,7,1,2,3,4]. Each reversal is a two-pointer swap, so it is O(n) time and O(1) extra space (a fixed amount of memory, whatever the size).

### 3. Palindrome

**In simple words:** Compare the first and last characters. If they match, move both pointers inward and compare again; if any pair differs, it is not a palindrome. For the "ignore symbols" version, skip anything that is not a letter or digit and compare in lowercase.

**Real-life example:** Two inspectors check a row of floor tiles, starting from both ends. They walk toward each other and compare each pair of tiles.

**Interview question:** Can the string become a palindrome by deleting at most one character?

**Simple answer:** I run the normal two-pointer check. At the first mismatch, I try skipping the left character, then the right one, and check if either remaining part is a palindrome. That is still O(n) time and O(1) space.

### 4. Fibonacci

**In simple words:** Each number is the sum of the two before it: 0, 1, 1, 2, 3, 5, 8. Keep two variables, a and b. In each step, a becomes b and b becomes a + b. After n steps, a holds F(n).

**Real-life example:** A notebook where each new line is the sum of the two lines above it. To write the next line, you only look at the last two.

**Interview question:** Why is the naive recursion exponential?

**Simple answer:** Each call splits into two calls, and the same values are computed again and again; F(n-2) is computed by both F(n) and F(n-1). So time grows like O(2^n), roughly doubling with each extra n. Saving each answer (memoisation) gives O(n) time and O(n) space, and my loop gives O(n) time and O(1) space.

```csharp
static long Fibonacci(int n)
{
    long a = 0, b = 1;
    for (int i = 0; i < n; i++)
        (a, b) = (b, a + b);
    return a;
}
```

### 5. Factorial

**In simple words:** n! means 1 x 2 x 3 x ... x n, and 0! is 1. Start with result = 1 and multiply by each number from 2 to n. Use `long`, and wrap the multiplication in `checked` so an overflow throws an error instead of giving a wrong number. 20! is the largest value that fits in a `long`.

**Real-life example:** Counting the ways to line up n people. The first spot has n choices, the next has n - 1, and so on, so you multiply them all.

**Interview question:** How many trailing zeros does n! have?

**Simple answer:** Each trailing zero comes from a 10, which is 2 x 5, and there are always more 2s than 5s. So I count the 5s: n/5 + n/25 + n/125 and so on, which gives 24 for 100!. That takes O(log n) time (it grows very slowly); the factorial loop itself is O(n) time and O(1) space.

### 6. Prime number

**In simple words:** A prime has no divisors except 1 and itself. To test n, try divisors only up to sqrt(n), because if n = a x b, one of them is at most sqrt(n). To list all primes up to n, use the Sieve of Eratosthenes. For each prime, cross out its multiples; the numbers left are prime.

**Real-life example:** Number cards on a table. Keep 2 and remove the other multiples of 2, then keep 3 and remove its multiples, and so on; the cards left are the primes.

**Interview question:** Why does the sieve start crossing out at p x p?

**Simple answer:** A smaller multiple, like 2p or 3p, has a smaller prime factor, so it was already crossed out. Starting at p x p saves work, and it is why the outer loop can stop at sqrt(n). A single test is O(sqrt(n)), and the sieve is O(n log log n) time and O(n) space.

### 7. Second largest number

**In simple words:** Walk the array once with two variables: largest and second. If a value is bigger than largest, the old largest becomes second. If a value is below largest but above second, it becomes the new second. Values equal to largest are ignored, so [4, 4] has no second largest.

**Real-life example:** A talent show board shows only first and second place. A better act pushes the winner down to second, but a tie with the winner changes nothing.

**Interview question:** What goes wrong if you start second at `int.MinValue`?

**Simple answer:** If the array really contains `int.MinValue`, I cannot tell "no answer" from "the answer is `int.MinValue`". So I use a nullable `int?` or a found flag, and saying this unprompted is a good sign. The one-pass method is O(n) time and O(1) space, while sorting costs O(n log n).

### 8. Remove duplicates

**In simple words:** For an unsorted array, keep a `HashSet` (a fast set of unique values) of what you have seen. Add a value to the result only if it is new, which keeps the first-seen order. For a sorted array, use read and write pointers to move unique values to the front in place. For a string, use the same `HashSet` idea with a `StringBuilder`.

**Real-life example:** A wedding guest book. If someone signs twice, the second signature is ignored because the name is already there.

**Interview question:** What if the array is unsorted and you cannot use extra memory?

**Simple answer:** I can sort first in O(n log n) and then use the in-place method, but the original order is lost. Or I can use nested loops: O(n^2) time (work grows with the square of the size) and O(1) space. The `HashSet` way is O(n) time but O(n) memory, so I explain the trade-off between time, memory and order.

### 9. Count characters

**In simple words:** Walk the string once and add 1 to each character's counter in a `Dictionary<char, int>`. For categories, check each character: vowel, other letter, digit or space, and add to that counter. To count words, split on whitespace and remove the empty parts.

**Real-life example:** Counting votes by hand. Each ballot adds one tally mark under the right name.

**Interview question:** How do you print the characters by frequency, highest first?

**Simple answer:** I build the frequency map in O(n), then sort its entries by count, which is O(k log k) for k different characters. For O(n), I use bucket sort: an array of lists where the index is the count, read from the top down. The map itself uses O(k) space.

### 10. Find the missing number

**In simple words:** The array should hold every number from 0 to n, but one is missing. The full total is n x (n + 1) / 2. Subtract the real total of the array; what is left is the missing number. XOR (a bit trick where equal numbers cancel out) gives the same answer with no overflow risk.

**Real-life example:** Lockers numbered 1 to 50 each hold a coat, except one. Add the numbers of the full lockers; the gap from the full total is the empty locker.

**Interview question:** If the array is sorted, can you beat O(n)?

**Simple answer:** Yes. In a sorted 0..n array, every position before the gap has `a[i] == i`, and every position after it does not. So I binary search for the first index where `a[i] != i`, in O(log n) time. For unsorted data, the sum or XOR method is O(n) time and O(1) space.

### 11. Two Sum

**In simple words:** For each number, you need its partner: target minus that number. Keep a dictionary of the numbers you have passed, with their indexes. For each new number, first check if its partner is in the dictionary; if yes, return both indexes. If not, add the current number and continue.

**Real-life example:** A lost-and-found desk keeps a list of items handed in. When someone asks for an item, the desk checks the list instead of searching the whole building.

**Interview question:** Numbers arrive as a stream, and add(number) and find(sum) are called many times. How do you design it?

**Simple answer:** I keep a `Dictionary` of counts, so add is O(1). find loops over the distinct keys x and checks if `sum - x` exists, needing a count of 2 when `sum - x` equals x; that is O(k). If find is called far more often, I store all pair sums in a `HashSet` instead, making find O(1) and add O(k).

### 12. Three Sum

**In simple words:** Sort the array and fix the first number. In the rest, use two pointers, one at each end, to find pairs that sum to minus the first number. If the total is too small, move the left pointer right; if too big, move the right pointer left. Skip equal neighbours so each triplet appears once.

**Real-life example:** A shop assistant with items sorted by price helps you pick three that cost exactly your budget. She fixes the first item, then adjusts the cheapest and dearest of the rest until the total fits.

**Interview question:** How do you avoid duplicate triplets, and what is the complexity?

**Simple answer:** Sorting puts equal values side by side. So I skip a first number equal to the one before it, and after a match I move both pointers past equal values. The sort is O(n log n) and each first number needs an O(n) scan, so the total is O(n^2), compared with O(n^3) for brute force.

### 13. Anagram

**In simple words:** Two strings are anagrams if they have the same letters with the same counts. If the lengths differ, return `false`. Count the first string's letters up in an `int[26]` array and the second string's letters down. If any counter drops below zero, return `false`.

**Real-life example:** Two shopping bags hold the same fruits in a different order. You count each fruit type in both bags; if all counts match, the bags hold the same things.

**Interview question:** How do you find all anagrams of p inside a longer string s?

**Simple answer:** I slide a window of length p across s and keep letter counts for p and for the window. Each step adds the new letter and removes the old one, and comparing 26 counters is O(1), so the scan is O(n). A single anagram check by counting is O(n) time and O(1) space; sorting is O(n log n).

### 14. Merge two sorted arrays

**In simple words:** Keep one pointer in each array. Compare the two current values, copy the smaller into the result, and move that pointer. When one array runs out, copy the rest of the other. For the in-place version, fill `nums1` from the back with the largest values, so nothing is overwritten before you read it.

**Real-life example:** Two bank queues, each in ticket order, are served by one clerk. The clerk always calls the smaller ticket number from the two queue fronts.

**Interview question:** How do you merge k sorted arrays?

**Simple answer:** I put the first item of each array in a min-heap (`PriorityQueue`), with the value as the priority. I take out the smallest, add it to the result, and push the next item from the same array; that is O(N log k) for N items. Merging two arrays is O(n + m) time, and the in-place version needs O(1) extra space.

### 15. Binary search

**In simple words:** The array must be sorted. Look at the middle item: if it equals the target, return its index. If the target is bigger, search the right half; if smaller, search the left half. Repeat until the range is empty, then return -1.

**Real-life example:** Guessing a number from 1 to 100 when you are told "higher" or "lower". Always guessing the middle finds it in at most 7 guesses.

**Interview question:** What three things should you say while writing it?

**Simple answer:** First, I use `lo + (hi - lo) / 2`, because `lo + hi` can overflow. Second, with `hi = n - 1`, the loop is `lo <= hi`, or the last item is never checked. Third, I always move to `mid + 1` or `mid - 1`, or the loop may never end; it runs in O(log n) time and O(1) space.

### 16. Sliding window

**In simple words:** For a fixed window of size k, sum the first k items. Then slide one step at a time: add the item entering on the right and subtract the item leaving on the left. For a variable window, grow the right edge until the condition holds. Then shrink the left edge while it still holds, recording the best.

**Real-life example:** Looking out of a train window. As the train moves, one new tree appears and one old tree disappears, so you never recount every tree.

**Interview question:** Why is it O(n) even with a while loop inside the for loop?

**Simple answer:** Each item enters the window once and leaves at most once, so both pointers together move about 2n steps. That is O(n) time and O(1) space, compared with O(n x k) for recomputing every window. The variable window needs positive numbers; with negatives, I use prefix sums with a dictionary.

```csharp
int window = 0;
for (int i = 0; i < k; i++) window += a[i];   // first window
int best = window;
for (int i = k; i < a.Length; i++)
{
    window += a[i] - a[i - k];                // add new, remove old
    best = Math.Max(best, window);
}
```

### 17. Longest substring without repeating characters

**In simple words:** Keep a window from left to right that has no repeated characters. Move right one step at a time, and keep a dictionary of each character's last position. If the new character was last seen inside the window, jump left to just after that position. After each step, update the best length.

**Real-life example:** Threading beads where no two beads may share a colour. When a repeated colour arrives, you drop beads from the start until the old bead of that colour is gone.

**Interview question:** Why check that the previous position is at least left before moving left?

**Simple answer:** The dictionary can hold an old position from before the window. Without the check, left could jump backwards, for example in "abba". With it, left only moves forward, so each character is handled once: O(n) time and O(k) space for k different characters.

### 18. Valid parentheses

**In simple words:** Use a stack. For each opening bracket, push the closing bracket you expect, such as `)` for `(`. For a closing bracket, pop the stack and check that it matches; if the stack is empty or it does not match, return `false`. At the end, the stack must be empty.

**Real-life example:** Opening boxes inside boxes. You must close the most recently opened box first; closing an outer box while an inner one is open is not allowed.

**Interview question:** How do you find the longest valid parentheses substring?

**Simple answer:** I keep a stack of indexes with -1 at the bottom as a base. For `(`, I push its index; for `)`, I pop, and if the stack is then empty I push the current index as the new base. Otherwise, the valid length is i minus the top index; this is O(n) time and O(n) space.

### 19. Reverse a linked list

**In simple words:** Walk the list once and flip each arrow to point backwards. Keep prev (the reversed part), cur (the current node) and next (saved before you change anything). For each node: save next, set `cur.Next` to prev, then move prev and cur one step. When cur is `null`, prev is the new head.

**Real-life example:** A conga line where each dancer holds the person in front. You go down the line and ask each dancer to turn around and hold the person behind.

**Interview question:** How do you check if a linked list is a palindrome with O(1) extra space?

**Simple answer:** I find the middle with slow and fast pointers and reverse the second half in place. I compare both halves node by node, then reverse the second half again to restore the list. This is O(n) time and O(1) space; plain reversal is also O(n) time and O(1) space.

### 20. Detect a linked-list cycle

**In simple words:** Use two pointers: slow moves one step and fast moves two. If fast reaches `null`, there is no cycle; if they meet, there is one. To find the start, move one pointer back to the head and step both one node at a time. They meet at the first node of the cycle.

**Real-life example:** Two joggers on a path. If the path loops like a running track, the faster jogger will catch the slower one from behind.

**Interview question:** If you use a `HashSet`, why must it compare node references, not values?

**Simple answer:** Two different nodes can hold the same value, like 1 -> 2 -> 1 -> null, which has no cycle. A cycle means the same node object is reached twice, and `HashSet<ListNode>` already compares references. The `HashSet` way is O(n) time and space; Floyd's two pointers are O(n) time and O(1) space.

### 21. Tree traversal

**In simple words:** Depth-first traversals differ by when you record the node: preorder is node-left-right, inorder is left-node-right, and postorder is left-right-node. Level order uses a queue. At each level, note how many nodes are in the queue, take exactly that many, and add their children.

**Real-life example:** Visiting a building floor by floor is level order. Walking one corridor to its end before trying the next is depth-first.

**Interview question:** How do you get the right-side view, or a zigzag level order?

**Simple answer:** Both reuse the level-order loop, with the node count fixed at the start of each level. For the right-side view, I keep the last value of each level; for zigzag, I reverse every second level. All traversals are O(n) time, with O(h) space for depth-first (h is the height) and O(w) for the widest level.

### 22. Breadth-first search (BFS)

**In simple words:** Put the start node in a queue and mark it seen. Repeatedly take a node from the front, record it, and add every unseen neighbour to the back, marking each one seen. For distances, each new neighbour's distance is the current node's distance plus 1.

**Real-life example:** News spreading in a village. First your direct neighbours hear it, then their neighbours, ring by ring.

**Interview question:** How do you solve "rotting oranges" or other problems with many starting points?

**Simple answer:** I use multi-source BFS: before the loop, I put all the starting points in the queue at distance 0. Then I run normal BFS, so each cell gets its distance to the nearest source in one O(rows x cols) pass. For a graph, BFS is O(V + E) time (nodes plus edges) and O(V) space.

### 23. Depth-first search (DFS)

**In simple words:** DFS follows one path as deep as it can, then goes back and tries the next one. Use recursion or a stack, and mark nodes visited. To count islands in a grid, scan every cell; when you find land, add 1 and "sink" the whole island with DFS. Sinking turns connected land into water, so you never count it twice.

**Real-life example:** Exploring caves: you follow one tunnel to its end, then return to the last fork and try another tunnel.

**Interview question:** What if you are not allowed to change the grid?

**Simple answer:** I use a separate `bool[,] visited` array, or a `HashSet` of (row, col) for sparse grids, instead of changing cells. Time stays O(rows x cols), plus O(rows x cols) extra memory. For huge grids, I use an explicit stack or BFS to avoid very deep recursion.

### 24. Top K frequent elements

**In simple words:** First, count each value in a dictionary. Then pick the k values with the highest counts. You can sort by count, or keep a min-heap of size k and remove the smallest count whenever it grows past k. Bucket sort also works: an array where the index is the count, read from the top.

**Real-life example:** A shop finds today's three best-selling products. It counts sales per product, then keeps a short top-three board, dropping the weakest whenever a better one appears.

**Interview question:** Why use a min-heap, not a max-heap, for the top k?

**Simple answer:** A min-heap capped at k holds only the current top k, and its top is the weakest one, exactly the item to compare and remove. That gives O(n + m log k) time for m distinct values, with O(k) heap memory. Sorting all counts is O(m log m), and bucket sort is O(n).

### 25. Merge intervals

**In simple words:** Sort the intervals by start and put the first one in the result. For each next interval, if it starts at or before the end of the last merged block, they overlap: extend the end to the bigger of the two ends. Otherwise, add it as a new block.

**Real-life example:** A meeting room booked from 1 to 3 and again from 2 to 6 is busy from 1 to 6. You write it as one block in the calendar.

**Interview question:** How do you insert a new interval into a sorted, non-overlapping list?

**Simple answer:** No sort is needed. In one pass, I copy the intervals that end before the new one starts, merge every interval that overlaps it using the smallest start and largest end, then copy the rest. That is O(n); the main merge is O(n log n) because of the sort, with O(n) space for the output.
