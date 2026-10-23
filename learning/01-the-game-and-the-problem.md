# 01 — The Game and the Problem

> **Goal:** understand the rules of Liêng and the exact question our program answers, before writing any code.
> **You will build:** nothing yet. This chapter is all thinking.
> **Time:** ~45 minutes.
> **Prerequisites:** none.

---

## The big picture

Before you write a program, you must be able to solve the problem **by hand**, at least for a small
example. If you cannot explain the rules to a friend, you cannot explain them to a computer.

This chapter answers three questions:

1. **What are the rules?** (Which hand beats which?)
2. **What decision does a player face?** (Raise or give up?)
3. **How can a computer help?** (And why is the program designed the way it is?)

---

## Part 1 — The cards

Liêng uses a normal 52-card deck:

- **13 ranks:** 2, 3, 4, 5, 6, 7, 8, 9, 10, J, Q, K, A
- **4 suits:** ♠ spades, ♣ clubs, ♦ diamonds, ♥ hearts

In our program we write a card as **rank + one-letter suit**: `As` = A♠, `Kh` = K♥, `10d` = 10♦,
`9c` = 9♣. (`T` is also accepted for ten: `Td` = 10♦.)

Each player gets **3 cards**. Players bet, and if nobody gives up, everyone shows their cards
("showdown") and the strongest hand wins all the money in the middle (the **pot**).

> 🔑 **Suits never matter for who wins.** A♠ K♥ Q♦ is exactly as strong as A♣ K♣ Q♥. Remember this,
> because in chapter 6 it lets us shrink the problem from 22,100 hands to 455.

---

## Part 2 — Which hand wins? (The four categories)

Every 3-card hand belongs to **exactly one** of four categories. A hand from a higher category
**always** beats a hand from a lower category, no matter what the cards are.

```
  STRONGEST
     ▲     Category 4 — Sáp    (three of a kind)        e.g. 7♠ 7♥ 7♦
     │     Category 3 — Liêng  (three in a row)          e.g. 7♠ 8♥ 9♦
     │     Category 2 — Đĩ     (three face cards)        e.g. J♠ Q♥ Q♦
     │     Category 1 — Điểm   (points, 0 to 9)          e.g. 2♠ 5♥ 9♦  → 6 points
  WEAKEST
```

The order of the checks matters. To find a hand's category, ask the questions **from the top down**
and stop at the first "yes":

1. Are all three ranks the same? → **Sáp**
2. Are the three ranks consecutive? → **Liêng**
3. Are all three cards J, Q or K? → **Đĩ**
4. Otherwise → **Điểm**

### Category 4 — Sáp (three of a kind)

Three cards of the same rank. There are 13 possible Sáp: `2-2-2` (weakest) up to `A-A-A` (strongest).
Between two Sáp, the higher rank wins: `A-A-A > K-K-K > … > 3-3-3 > 2-2-2`.

Even the weakest Sáp (`2-2-2`) beats the strongest Liêng (`Q-K-A`).

### Category 3 — Liêng (a straight)

Three **consecutive** ranks, any suits. There are exactly **12** of them:

```
A-2-3  <  2-3-4  <  3-4-5  <  4-5-6  <  5-6-7  <  6-7-8  <  7-8-9  <  8-9-10  <  9-10-J  <  10-J-Q  <  J-Q-K  <  Q-K-A
(weakest)                                                                                                (strongest)
```

Three tricky edge cases:

| Hand | Liêng? | Why |
|------|--------|-----|
| `A-2-3` | ✅ yes, the **weakest** Liêng | The Ace can act as "1" at the bottom. |
| `Q-K-A` | ✅ yes, the **strongest** Liêng | The Ace can act as the top card. |
| `K-A-2` | ❌ **no** | No "wrapping around" from K to A to 2. This is just a Điểm hand (K=0, A=1, 2=2 → **3 points**). |

### Category 2 — Đĩ (three face cards)

All three cards are face cards (J, Q or K), **but** the hand is not already a Sáp or a Liêng:

- `J-J-J`, `Q-Q-Q`, `K-K-K` are three face cards, but they are **Sáp** (checked first).
- `J-Q-K` is three face cards, but it is a **Liêng** (checked first).

That leaves exactly **6** Đĩ shapes: `J-J-Q`, `J-J-K`, `J-Q-Q`, `J-K-K`, `Q-Q-K`, `Q-K-K`.

> ⚠️ **The Ace is not a face card.** `A-J-J` is **not** Đĩ. It is a Điểm hand worth A(1)+J(0)+J(0) = **1 point**.

The most important rule about Đĩ: **any Đĩ beats any Điểm hand, even 9 points.**

### Category 1 — Điểm (points)

Everything else. Each card has a point value:

| Card | 2 | 3 | 4 | 5 | 6 | 7 | 8 | 9 | 10 | J | Q | K | A |
|------|---|---|---|---|---|---|---|---|----|---|---|---|---|
| Points | 2 | 3 | 4 | 5 | 6 | 7 | 8 | 9 | **0** | **0** | **0** | **0** | **1** |

Add the three values and **keep only the last digit** (that is, take the sum *modulo 10*, written `% 10`
in Python). The score is between 0 and 9. **9 is best, 0 is worst.** A hand with 0 points is called
**Bù** (or *Tịt*).

| Hand | Sum | Score |
|------|-----|-------|
| `9-10-K` | 9 + 0 + 0 = 9 | **9** |
| `A-3-5` | 1 + 3 + 5 = 9 | **9** |
| `9-8-2` | 9 + 8 + 2 = **19** | **9** (19 % 10 = 9) |
| `2-2-4` | 8 | **8** |
| `10-10-K` | 0 + 0 + 0 = 0 | **0 (Bù)** |
| `2-3-5` | 10 | **0 (Bù)** (10 % 10 = 0) |

### How ties are broken in this project

Real-life Liêng tables use different house rules for ties. **This project** breaks ties like this
(you will code it in chapter 5):

- Two Sáp: higher rank wins.
- Two Liêng: higher sequence wins (`Q-K-A` > `J-Q-K` > …).
- Two Đĩ: compare the highest card, then the middle card (`K-K-Q` > `K-Q-Q`).
- Two Điểm with the same score: compare the **highest card** (Ace counts as the highest, 14), then the
  other cards. Example: `A-3-5` (9 points, Ace high) beats `K-10-9` (9 points, King high).
- A true tie happens only when the ranks are identical, e.g. `Q♠ K♠ A♠` vs `Q♥ K♥ A♥`.

### 🧪 Check your understanding (answers below)

1. `2♠ 2♥ 2♦` vs `Q♠ K♥ A♦` — who wins?
2. `A♠ 2♥ 3♦` vs `K♠ K♥ Q♦` — who wins?
3. `J♠ Q♥ Q♦` vs `9♠ 10♥ K♦` — who wins?
4. What is `K♠ A♥ 2♦` worth?
5. What is `A♠ J♥ J♦` worth?

<details>
<summary>Answers</summary>

1. `2-2-2` (Sáp beats Liêng).
2. `A-2-3` (the weakest Liêng still beats any Đĩ; `K-K-Q` is a Đĩ).
3. `J-Q-Q` (Đĩ beats 9 points).
4. A Điểm hand worth 3 points (no wrap-around Liêng).
5. A Điểm hand worth 1 point (the Ace is not a face card, so it is not Đĩ).

</details>

---

## Part 3 — The decision: raise or give up?

Here is a simplified situation, the one our program studies:

- There is already money in the middle: the **pot**, `P`. Example: **P = 100,000 VND**.
- You may **raise** (*Tố*) by putting in a **bet** of size `B`. Example: **B = 50,000 VND**.
- The opponent then either:
  - **folds** (gives up): you take the pot immediately, without showing cards, or
  - **calls** (matches your 50,000): both hands are shown and the stronger hand takes everything.

So there are three possible outcomes:

```
                         You raise B = 50,000
                                  │
             ┌────────────────────┴────────────────────┐
     opponent FOLDS                              opponent CALLS
     (probability f)                             (probability 1 − f)
             │                                          │
     you win the pot                        ┌───────────┴────────────┐
     +100,000                           you win                   you lose
                                        (probability = equity)    (probability = 1 − equity)
                                        +150,000                   −50,000
                                        (pot 100k + their 50k)     (your bet)
```

Two numbers decide whether raising is a good idea:

- **Fold equity `f`**: how likely the opponent is to fold. You estimate this from how the
  opponent plays. A "calling station" almost never folds (f ≈ 0); a scared player folds a lot.
- **Showdown equity**: how often your hand wins if the opponent calls. **This is what the
  computer calculates for us.**

### Expected Value (EV) in one paragraph

If you could play this exact situation thousands of times, how much would you win **on average** per
game? That average is the **Expected Value**. To compute it: for each outcome, multiply its
probability by its profit, then add everything up.

A tiny example first. A friend offers: "Flip a coin. Heads, I pay you 30. Tails, you pay me 10."

```
EV = 0.5 × (+30) + 0.5 × (−10) = 15 − 5 = +10   → on average you win 10 per flip. Take the bet!
```

### The Liêng example, by hand

Say the opponent folds 35% of the time (f = 0.35) and you hold `A♠ K♥ Q♦` (the best Liêng). The program
will tell us this hand wins 99.69% of showdowns against a random hand. Then:

```
EV = 0.35 × 100,000  +  0.65 × (0.9969 × 200,000 − 50,000)
   = 35,000          +  0.65 × (199,380 − 50,000)
   = 35,000          +  0.65 × 149,380
   = 35,000          +  97,097
   = +132,097 VND    → raise!
```

(Why `0.9969 × 200,000 − 50,000`? If the opponent calls, the final pot is 100k + 50k + 50k = 200k. You
win it 99.69% of the time, and you had to pay 50k to get there. Chapter 9 derives this carefully.)

Now the same situation with the worst kind of hand, `2♠ 3♥ 5♦` (0 points, wins only 0.24% of
showdowns):

```
EV = 0.35 × 100,000 + 0.65 × (0.0024 × 200,000 − 50,000)
   = 35,000         + 0.65 × (−49,520)
   = 35,000         − 32,188
   = +2,812 VND     → still (slightly) profitable!
```

Surprising? With a 100k pot and a 50k bet, a pure bluff makes money whenever the opponent folds more
than **33.3%** of the time. At 35%, **every hand** (all 22,100) is profitable to raise. If the opponent
folded only 5% of the time, that same junk hand would lose about 42,000 per game on average.

This is the whole point of the project: **"strong hand → raise" is too simple.** The right decision
depends on the pot, the bet size, the opponent's folding habits **and** the hand's equity together.

---

## Part 4 — How a computer helps (and why the program looks like it does)

To compute EV we need the **equity** of a hand: how often it wins against an unknown opponent hand.

**The honest way to get it:** take your 3 cards out of the deck. 49 cards remain. The opponent could hold
any 3 of them: there are C(49, 3) = **18,424** possibilities. Compare your hand with every one, and
count wins, ties and losses. That is exact, and it is what our generator does.

**The problem:** there are C(52, 3) = **22,100** different starting hands. Doing 18,424 comparisons for
each one is about 22,100 × 18,424 ≈ **407 million** comparisons. In Python that takes more than 20 minutes
on one CPU core, far too slow to do every time a user clicks a button.

**The two tricks this project uses:**

1. **Suits don't matter → shrink the problem.** Many of the 22,100 hands are the "same" hand with
   different suits. If we only keep the ranks, there are just **455** different hand types (called
   *canonical hands*). We only need to simulate 455 hands, not 22,100. (Chapter 6.)
2. **Do the slow work once, ahead of time.** We run the simulation **once** (≈ 30 seconds on a laptop) and
   save the 455 answers in a file, `data/winrates.json`. When a user asks a question, the program just
   **looks up** the answer in a Python dictionary, which takes well under a microsecond. (Chapters 7–8.)

This pattern, **"offline precomputation + fast online lookup"**, is very common in real software
(search engines, maps, game AIs, …).

```
OFFLINE (slow, once):   455 hand types × 18,424 opponents  ──►  winrates.json
ONLINE  (fast, always): user's hand ──► find its type ──► look up equity ──► EV formula ──► answer
```

---

## Part 5 — The project's own documents

The repository contains several Markdown files written by the original authors. You don't need them to
follow this guide, but it helps to know what they are:

| File | What it is |
|------|------------|
| [`AGENTS.md`](../AGENTS.md) | The **technical specification**: rules, data types, maths and performance budgets. The code was written to follow it. |
| [`DESIGN.md`](../DESIGN.md) | The **visual design spec** for the web page (colours, fonts, layout). |
| [`SKILLS.md`](../SKILLS.md) | A cheat-sheet of **commands** (run tests, run the generator, run the CLI). |
| [`README.md`](../README.md) | The project's front page: architecture, API reference, quickstart. |
| [`BLOG.md`](../BLOG.md), [`EXPERIMENT.md`](../EXPERIMENT.md) | The story and the academic report of the project (in Vietnamese). |

> 💡 Reading `AGENTS.md` after this chapter is a good exercise: you should now understand most of it.

---

## ✅ Checkpoint

You are ready for the next chapter if you can, **without looking**:

- [ ] list the four categories from strongest to weakest,
- [ ] say why `K-A-2` is not a Liêng and why `A-J-J` is not a Đĩ,
- [ ] compute the Điểm score of `9-8-2` (answer: 9),
- [ ] explain in one sentence what **fold equity** and **showdown equity** are,
- [ ] explain why the program precomputes a file instead of simulating on every click.

## Recap

- Liêng hands fall into 4 categories: **Sáp > Liêng > Đĩ > Điểm**, checked in that order.
- Edge cases: `A-2-3` lowest Liêng, `Q-K-A` highest, `K-A-2` invalid; Ace is not a face card; Đĩ beats 9 points.
- The decision to raise is judged by **Expected Value**, which combines pot, bet, fold equity and showdown equity.
- The program precomputes the equity of **455** hand types once and then answers questions by lookup.

**Next:** [02 — Setup and project skeleton](02-setup-and-project-skeleton.md)
