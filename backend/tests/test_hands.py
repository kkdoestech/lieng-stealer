"""Unit tests for Canonical Hand Isomorphism & State Space Compression in Liêng.

Verifies:
- Complete state space coverage: exactly 455 canonical classes
- Multiplicity summation: sum of class multiplicities equals 22,100
- Category distribution:
    - Sáp: 13 classes
    - Liêng: 12 classes
    - Đĩ: 6 classes
    - Điểm: 424 classes
- Suit invariance: permutations of suits map to identical canonical_id
- Representative cards validity: all 455 classes yield 3 distinct valid cards
"""

from collections import Counter
import pytest

from src.evaluator import Card, HandCategory, Rank, Suit
from src.hands import (
    CanonicalHand,
    generate_all_canonical_hands,
    get_canonical_id,
    get_representative_cards,
    to_canonical,
)


class TestCanonicalHandEngine:
    """Test suite for canonical hand isomorphism and combinatorics."""

    def test_canonical_space_size(self) -> None:
        """Verify that exactly 455 unique canonical classes are generated."""
        canonical_hands = generate_all_canonical_hands()
        assert len(canonical_hands) == 455

        # Ensure all canonical_ids are strictly unique
        unique_ids = {c.canonical_id for c in canonical_hands}
        assert len(unique_ids) == 455

    def test_multiplicity_sum(self) -> None:
        """Verify that total combinations across all 455 classes sum to C(52, 3) = 22,100."""
        canonical_hands = generate_all_canonical_hands()
        total_combos = sum(c.multiplicity for c in canonical_hands)
        assert total_combos == 22100

        # Verify multiplicity distribution (13 trips of 4, 156 pairs of 24, 286 distinct of 64)
        mult_counts = Counter(c.multiplicity for c in canonical_hands)
        assert mult_counts[4] == 13      # 13 * 4 = 52
        assert mult_counts[24] == 156    # 156 * 24 = 3744
        assert mult_counts[64] == 286    # 286 * 64 = 18304

    def test_category_distribution(self) -> None:
        """Verify class counts partition exactly into theoretical categories."""
        canonical_hands = generate_all_canonical_hands()
        category_counts = Counter(c.category for c in canonical_hands)

        # 1. Sáp: 13 classes (2-2-2 to A-A-A)
        assert category_counts[HandCategory.SAP] == 13

        # 2. Liêng: 12 classes (A-2-3 to Q-K-A)
        assert category_counts[HandCategory.LIENG] == 12

        # 3. Đĩ: 6 classes (multisets of J, Q, K with 1 pair)
        di_hands = [c for c in canonical_hands if c.category == HandCategory.DI]
        assert len(di_hands) == 6
        expected_di_rank_multisets = {
            (Rank.JACK, Rank.JACK, Rank.QUEEN),
            (Rank.JACK, Rank.JACK, Rank.KING),
            (Rank.JACK, Rank.QUEEN, Rank.QUEEN),
            (Rank.JACK, Rank.KING, Rank.KING),
            (Rank.QUEEN, Rank.QUEEN, Rank.KING),
            (Rank.QUEEN, Rank.KING, Rank.KING),
        }
        actual_di_rank_multisets = {tuple(sorted(c.ranks)) for c in di_hands}
        assert actual_di_rank_multisets == expected_di_rank_multisets

        # 4. Điểm: Exactly 424 classes (455 - 13 - 12 - 6)
        assert category_counts[HandCategory.DIEM] == 424

    def test_suit_invariance(self) -> None:
        """Verify that hands with identical ranks but different suits map to identical canonical_id."""
        hand1 = [Card.from_str("7s"), Card.from_str("8h"), Card.from_str("9d")]
        hand2 = [Card.from_str("7c"), Card.from_str("8d"), Card.from_str("9s")]
        hand3 = [Card.from_str("9h"), Card.from_str("7d"), Card.from_str("8c")]

        id1 = get_canonical_id(hand1)
        id2 = get_canonical_id(hand2)
        id3 = get_canonical_id(hand3)

        assert id1 == id2 == id3 == "9-8-7"

        # Check Q-K-A invariance
        qka1 = [Card.from_str("Qs"), Card.from_str("Kh"), Card.from_str("Ad")]
        qka2 = [Card.from_str("Qc"), Card.from_str("Kd"), Card.from_str("As")]
        assert get_canonical_id(qka1) == get_canonical_id(qka2) == "Q-K-A"

        # Check A-2-3 invariance
        a23_1 = [Card.from_str("As"), Card.from_str("2h"), Card.from_str("3d")]
        a23_2 = [Card.from_str("Ac"), Card.from_str("2d"), Card.from_str("3s")]
        assert get_canonical_id(a23_1) == get_canonical_id(a23_2) == "A-2-3"

    def test_representative_cards_validity(self) -> None:
        """Verify all 455 canonical classes produce valid 3-card hands with no duplicate cards."""
        canonical_hands = generate_all_canonical_hands()
        for ch in canonical_hands:
            cards = get_representative_cards(ch.canonical_id)
            assert len(cards) == 3
            # Ensure cards are all unique
            assert len(set(cards)) == 3
            # Ensure mapped back to the same canonical_id
            assert get_canonical_id(cards) == ch.canonical_id

