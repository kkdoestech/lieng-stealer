# AGENTS.MD: ARCHITECTURAL GUARDRAILS & SYSTEM SPECIFICATION

## 1. System Overview & Philosophy
**Liêng Stealer** is a high-performance decision-support engine and game-theoretic solver for the Vietnamese card game **Liêng** (a 3-card imperfect information game). The core problem is evaluating whether to **Raise (Tố)** or **Go All-In (Tất tay)** by calculating **Expected Value (EV)** across all canonical hand combinations given pot odds, bet sizing, and opponent fold equity.

The system strictly adheres to:
- **Separation of Concerns (SoC)**: Independent domain modules (game rules, simulation, finance/EV, data access, presentation).
- **Zero Global Mutable State**: All state transformations are pure, functional, or encapsulated within immutable data models.
- **Offline Computation + $O(1)$ Online Query**: Precomputed Monte Carlo / combinatorial win rates stored on disk and cached in-memory.

---

## 2. Coding Standards & Conventions

### 2.1 Runtime & Environment
- **Python Version**: `3.11+` (Leveraging enhanced tracebacks, `typing.Self`, and performance optimizations).
- **Typing**: Strict type annotations (`mypy` compliant). No untyped functions or use of `Any` without explicit justification.
- **Data Structures**: Prefer `@dataclass(frozen=True)` or `typing.NamedTuple` for domain entities (`Card`, `Hand`, `HandScore`, `EVResult`).
- **Docstrings**: Google style with explicit `Args`, `Returns`, and `Raises` sections for all public classes and functions.
- **Error Handling**: Explicit custom exception hierarchy inherited from `LiengError` (e.g., `InvalidCardError`, `InvalidHandSizeError`, `DatabaseNotLoadedError`). Never silently swallow exceptions.

### 2.2 Functional & Architectural Constraints
- **Pure Functions**: `evaluator.py` and `ev.py` must be completely deterministic and free of side effects or external I/O.
- **No Global Mutable State**: Do not use global variables to store game state or cached databases. State must be injected via constructors or parameters (Dependency Injection).
- **Immutability**: Card and Hand instances must be hashable and immutable so they can serve as dictionary keys and set members.

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
  - **Tie-Breaker**: Hands within Đĩ are considered equal (Tie) or compared by highest face card ($K > Q > J$) based on game configuration.

- **Category 1: Điểm (Points modulo 10)**
  - Any 3-card hand that is not Sáp, Liêng, or Đĩ.
  - Card numerical point values:
    - Ranks $2$ through $9$: Face value ($2 \dots 9$).
    - Ranks $10, J, Q, K$: Value $= 0$.
    - Rank $A$: Value $= 1$.
  - Hand Score calculation:
    $$\text{Score} = \left(\sum_{i=1}^3 \text{CardValue}_i\right) \pmod{10}$$
  - Possible scores range from $0$ (Bù / Tịt) to $9$ (Chín điểm).
  - **Score Order**: $9 > 8 > 7 > 6 > 5 > 4 > 3 > 2 > 1 > 0$.
  - **Edge Cases**:
    - $19$ points ($9 + 10 + K$) and $9$ points ($A + 3 + 5$) both evaluate to $9$ points ($19 \equiv 9 \equiv 9 \pmod{10}$).
    - $20$ points (e.g., $10 + 10 + K \rightarrow 0 \pmod{10}$) evaluates to $0$ points (Bù).

### 3.3 Comparison Tuple Specification
`evaluator.py` must output a standardized `HandScore` named tuple / dataclass:
```python
HandScore(category: int, primary_rank: int, secondary_rank: int, score: int)
```
This enables direct Python tuple comparison (`hand_a.score_tuple > hand_b.score_tuple`).

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
- Reducing $22,100 \rightarrow 455$ canonical keys minimizes offline Monte Carlo overhead and compresses database size below 100 KB.

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
- $\text{FinalPot} = P + B + C_{\text{opp}}$, where $C_{\text{opp}}$ is opponent's call contribution (typically $C_{\text{opp}} = B$).
- Showdown Value: $[P(\text{Win} \mid \text{Call}) \times \text{FinalPot}] - B$.
- **Decision Rule**: Execute Raise if and only if $\text{EV} > 0$.

---

## 6. Performance Budgets & Latency Guardrails
- **Single Hand Evaluation**: $< 1.0\ \mu\text{s}$ per 3-card hand.
- **In-Memory Hash Table Lookup**: $O(1)$ time complexity, $< 5.0\ \mu\text{s}$ per hand key.
- **Full Range EV Calculation (all 455 canonical hands)**: $< 25\ \text{ms}$.
- **CLI Interactive Command Execution**: $< 50\ \text{ms}$ total response latency.
- **Memory Footprint**: RAM usage for the lookup database $< 10\ \text{MB}$.

