# AGENTS.MD: ARCHITECTURAL GUARDRAILS & SYSTEM SPECIFICATION

## 1. System Overview & Philosophy
**Liêng Stealer** is a high-performance decision-support engine for the Vietnamese card game **Liêng** (a 3-card imperfect information game). The core problem is evaluating whether to **Raise (Tố)** or **Go All-In (Tất tay)** by calculating **Expected Value (EV)** across all canonical hand combinations given pot odds, bet sizing, and opponent fold equity. It computes EV under stated assumptions (one betting round, a chosen opponent model); it does not solve for a game-theoretic equilibrium.

The system strictly adheres to:
- **Separation of Concerns (SoC)**: Independent domain modules (game rules, simulation, finance/EV, data access, presentation).
- **Zero Global Mutable State**: All state transformations are pure, functional, or encapsulated within immutable data models.
- **Offline Computation + $O(1)$ Online Query**: Win rates precomputed by exact enumeration (every one of the $C(49, 3) = 18{,}424$ opponent hands per class; Monte Carlo remains available for experiments), stored on disk and cached in-memory.

---

## 2. Coding Standards & Conventions

### 2.1 Runtime & Environment
- **Python Version**: `3.11+` (Leveraging enhanced tracebacks, `typing.Self`, and performance optimizations).
- **Typing**: Strict type annotations, enforced by `mypy --strict` and `ruff` (configured in `backend/pyproject.toml`, run in CI). No untyped functions or use of `Any` without explicit justification.
- **Data Structures**: Prefer `@dataclass(frozen=True)` or `typing.NamedTuple` for domain entities (`Card`, `Hand`, `HandScore`, `EVResult`).
- **Docstrings**: Google style with explicit `Args`, `Returns`, and `Raises` sections for all public classes and functions.
- **Error Handling**: Explicit custom exception hierarchy inherited from `LiengError` (e.g., `InvalidCardError`, `InvalidHandSizeError`, `DuplicateCardError`, `DatabaseNotLoadedError`, and `ModelError` for a missing or inconsistent model, which is a bug rather than bad input). `InvalidGameParamsError` is also a `ValueError` and `UnknownHandError` also a `KeyError`, so code written against the built-ins keeps working; `tests/test_exceptions.py` pins the hierarchy. Never silently swallow exceptions.

### 2.2 Functional & Architectural Constraints
- **Pure Functions**: `evaluator.py` and `ev.py` must be completely deterministic and free of side effects or external I/O.
- **No Global Mutable State**: Do not use global variables to store game state or cached databases. State must be injected via constructors or parameters (Dependency Injection). The Flask app is built by `create_app(db=..., calling_model=..., config=...)`, which keeps its services in `app.extensions`; the module-level `app` object exists only as the entry point for gunicorn and `python app.py`.
- **Immutability**: Card and Hand instances must be hashable and immutable so they can serve as dictionary keys and set members. `Hand` equality means equal strength (the hands would tie), and its hash agrees with it.
- **One opponent assumption, one equity source**: `fold_equity` is the only caller assumption the API accepts; under the `range` model the calling range is derived, `(1 - f) × 100%`, and only echoed back as `call_range_percent` (never sent). A request builds one `OpponentEquities` and answers a hand as `HandSolution.record`, i.e. the matching row of the 455-class table, so a second equity implementation cannot exist again. `src/opponent_model.py` was deleted in 2.0.0 for exactly that reason; `git log` has the history.
- **One recommendation, one policy object**: the advice is one frozen `Recommendation` built by `src/advice.py`, and `HandEVRecord.advice` carries it into both the single-hand answer and the 455-class table, so the card and the table row are the same object and cannot disagree. The policy walks down a three-rung ladder (33%, 75% and 100% of the pot) and a rung may be the answer only when its EV is at least 5% of the pot in the centre fold cell and in the worst cell at the fold rate ±10 points; `ALL_IN` also requires a win rate of at least 85%, and a bluff may never use anything but the small rung. The nine numbers live in one frozen `AdviceThresholds`, are injected through `create_app(thresholds=...)` or the `ADVICE_*` settings, and are echoed as `summary.sizing` so no client has to hard-code one.

---

## 3. Domain Rules & Strict Hand Evaluation Hierarchies

### 3.1 Card Representation
- A standard 52-card French deck: Ranks `2, 3, 4, 5, 6, 7, 8, 9, 10, J, Q, K, A`.
- Suit representation: Spades (`♠`), Clubs (`♣`), Diamonds (`♦`), Hearts (`♥`).
- In standard Liêng, showdown hand strength is strictly rank-based (suits do not alter category or numerical hierarchy unless designated in optional house tie-breakers).

### 3.2 Hand Hierarchy (Strict Total Ordering)
Hand categories are strictly ranked from highest to lowest:
$$\text{Sáp} > \text{Liêng} > \text{Đĩ} > \text{Điểm}$$

Category values assigned for tuple comparison:
- **Category 4: Sáp (Three of a Kind)**
  - Three cards of identical rank (e.g., `7-7-7`, `A-A-A`).
  - **Ranking Order**: $2\text{-}2\text{-}2 < 3\text{-}3\text{-}3 < \dots < K\text{-}K\text{-}K < A\text{-}A\text{-}A$.
  - Sáp $A$ is the strongest Sáp; Sáp $2$ is the weakest.

- **Category 3: Liêng (Straight / Consecutive Sequence)**
  - Three cards of consecutive ranks, regardless of suit.
  - Valid sequences (12 possible):
    $$\text{A-2-3} < \text{2-3-4} < \text{3-4-5} < \dots < \text{10-J-Q} < \text{J-Q-K} < \text{Q-K-A}$$
  - **Crucial Edge Cases**:
    - `A-2-3` is valid and ranks as the **lowest** Liêng.
    - `Q-K-A` is valid and ranks as the **highest** Liêng.
    - `K-A-2` is **INVALID** as a Liêng (wraparound across K-A-2 is strictly prohibited).

- **Category 2: Đĩ / Liên Đồng Hoa (Three Face Cards)**
  - All three cards are face cards ($\text{Rank} \in \{J, Q, K\}$), **excluding** hands that already qualify as:
    - Sáp (i.e., `J-J-J`, `Q-Q-Q`, `K-K-K` $\rightarrow$ evaluated as Sáp, Category 4).
    - Liêng (i.e., `J-Q-K` $\rightarrow$ evaluated as Liêng, Category 3).
  - Valid Đĩ examples: `J-Q-Q`, `J-K-K`, `J-J-Q`, `J-J-K`, `Q-Q-K`, `Q-K-K`.
  - **Crucial Rule**: Any Đĩ strictly beats any point-based hand (Category 1), including $9$ points!
  - **Tie-Breaker** (house rule, as implemented; there is no configuration switch): compared by highest face card ($K > Q > J$), then the middle card, then the last card, so `K-K-Q` > `K-K-J` > `K-Q-Q` > `K-J-J` > `Q-Q-J` > `Q-J-J`. Making Đĩ hands tie would also require changing `calling_range.py`, which assumes all 455 classes have distinct strengths (and checks it at start-up).

- **Category 1: Điểm (Points modulo 10)**
  - Any 3-card hand that is not Sáp, Liêng, or Đĩ.
  - Card numerical point values:
    - Ranks $2$ through $9$: Face value ($2 \dots 9$).
    - Ranks $10, J, Q, K$: Value $= 0$.
    - Rank $A$: Value $= 1$.
  - Hand Score calculation:
    $$\text{Score} = \left(\sum_{i=1}^3 \text{CardValue}_i\right) \pmod{10}$$
  - Possible scores range from $0$ (Bù / Tịt) to $9$ (Chín điểm).
  - **Score Order**: $9 > 8 > 7 > 6 > 5 > 4 > 3 > 2 > 1 > 0$. Equal scores are broken by the highest card (Ace high), then the remaining cards (house rule).
  - **Edge Cases**:
    - $19$ points ($9 + 10 + K$) and $9$ points ($A + 3 + 5$) both evaluate to $9$ points ($19 \equiv 9 \equiv 9 \pmod{10}$).
    - $20$ points (e.g., $10 + 10 + K \rightarrow 0 \pmod{10}$) evaluates to $0$ points (Bù).

### 3.3 Comparison Tuple Specification
`evaluator.py` outputs a frozen `HandScore` dataclass:
```python
HandScore(category: HandCategory, primary_rank: int, secondary_rank: int, score: int,
          tie_breaker: tuple[int, ...], name: str)
```
Comparison uses `score_tuple = (category, primary_rank, secondary_rank, score, tie_breaker)`; `name` is display text only. This enables direct comparison of scores (`hand_a.score > hand_b.score`) or hands (`hand_a > hand_b`). Because suits never matter, `evaluate_hand` looks the score up in a 455-entry table keyed by the sorted ranks.

---

## 4. Combinatorics & Hand Isomorphism

### 4.1 State Space
- Complete 3-card combinations from 52 cards:
  $$\binom{52}{3} = \frac{52 \times 51 \times 50}{3 \times 2 \times 1} = 22,100 \text{ hands}$$

### 4.2 Canonical Representation
Because Liêng hand strength is suit-invariant pre-showdown:
- Hands differing only by suit permutations belong to the same **Canonical Equivalence Class**.
- Ranks are ordered descending: $r_1 \ge r_2 \ge r_3$.
- Total rank multisets:
  $$\binom{13 + 3 - 1}{3} = \binom{15}{3} = 455 \text{ canonical hand types}$$
  - 13 Sáp forms (`2-2-2` to `A-A-A`).
  - 12 Liêng forms (`A-2-3` to `Q-K-A`).
  - 6 Đĩ forms (`J-J-Q`, `J-J-K`, `J-Q-Q`, `J-K-K`, `Q-Q-K`, `Q-K-K`).
  - 424 Điểm forms.
- Reducing $22,100 \rightarrow 455$ canonical keys cuts the offline work to $455 \times 18{,}424 \approx 8.4$ million exact showdowns and keeps the database below 100 KB.

---

## 5. Mathematical Formulation (Expected Value & Game Theory)

### 5.1 The EV Equation
When choosing to **Raise / Tố** or **Push / Tất tay** with bet amount $B$ into existing pot $P$:
$$\text{EV} = \big[ P(\text{Fold}) \times P \big] + \big[ 1 - P(\text{Fold}) \big] \times \Big[ \big( P(\text{Win} \mid \text{Call}) \times \text{FinalPot} \big) - B \Big]$$

Where:
- $P$: Current Pot before player's bet (Dead Money).
- $B$: Player's additional Bet Size.
- $P(\text{Fold})$: Opponent's probability of folding to the bet (Fold Equity).
- $P(\text{Win} \mid \text{Call})$: Player's showdown equity against opponent's calling range.
- $\text{FinalPot} = P + B + C_{\text{opp}}$, where $C_{\text{opp}}$ is opponent's call contribution. The code assumes $C_{\text{opp}} = B$: `ev.final_pot(P, B)` returns $P + 2B$.
- Showdown Value: $[P(\text{Win} \mid \text{Call}) \times \text{FinalPot}] - B$.
- **Decision Rule** (3.0.0): $\text{EV} > 0$ is necessary, not sufficient. `src/advice.py` prices the three rungs and answers with the first one that clears the 5%-of-pot floor in the centre cell and in the worst $\pm 0.10$ cell, starting from the largest rung the win rate allows; `ALL_IN` also needs a win rate of at least 0.85. See §2.2.

---

## 6. Performance Budgets & Latency Guardrails
Measured on a developer laptop (2026-10-24); the tested budgets are scaled by `PERF_BUDGET_FACTOR` in CI.
- **Single Hand Evaluation**: $< 1.0\ \mu\text{s}$ per 3-card hand. Met: about 0.3 µs (tested in `test_evaluator.py`).
- **In-Memory Hash Table Lookup**: $O(1)$ time complexity, $< 5.0\ \mu\text{s}$ per hand key. Met: about 0.1 µs (tested in `test_db.py`).
- **Full Range EV Calculation (all 455 canonical hands)**: $< 25\ \text{ms}$. Met: the calling-range equity table takes about 0.4 ms and a full `solve_range` about 2 ms (tested in `test_calling_range.py`).
- **CLI Command Execution**: $< 300\ \text{ms}$ for one cold-start command. Measured 0.13–0.19 s: Python start-up, imports including `rich`, and building the calling-range tables for `--opponent-model range`. The earlier 50 ms target is not reachable for a fresh Python process with these dependencies. Not covered by a test.
- **Memory Footprint**: RAM usage for the lookup structures $< 10\ \text{MB}$. Met: about 0.2 MB for the win-rate database and 1.1 MB for the calling-range tables.

