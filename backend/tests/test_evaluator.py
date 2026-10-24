"""Unit tests for Card, Hand, and strict Hand Evaluator in Liêng.

Verifies:
- Sáp hierarchy (AAA > KKK > ... > 222)
- Sáp > Liêng > Đĩ > Điểm
- Liêng edge sequences (QKA > ... > 234 > A23)
- Strict rejection of wrap-around sequence K-A-2 as Liêng
- Priority of Đĩ over any 9-point hand (JQQ > 9-10-K)
- Isolation of JJJ as Sáp and JQK as Liêng (neither evaluated as Đĩ)
- Modulo 10 arithmetic (10+J+Q = 0 pts, 9+10+K = 9 pts, A+3+5 = 9 pts)
- Strict error handling (invalid cards, duplicate cards, hand size != 3)
"""

import timeit

import pytest

from src.evaluator import (
    Card,
    Hand,
    HandCategory,
    Rank,
    Suit,
    calculate_points,
    evaluate_hand,
)
from src.exceptions import DuplicateCardError, InvalidCardError, InvalidHandSizeError
from tests.perf import budget


class TestCardAndRank:
    """Test Card domain model, Rank values, and string parser."""

    def test_card_from_str_standard(self) -> None:
        card = Card.from_str("Ah")
        assert card.rank == Rank.ACE
        assert card.suit == Suit.HEARTS
        assert card.point_value == 1

        card_10 = Card.from_str("10s")
        assert card_10.rank == Rank.TEN
        assert card_10.suit == Suit.SPADES
        assert card_10.point_value == 0

        card_t = Card.from_str("Td")
        assert card_t.rank == Rank.TEN
        assert card_t.suit == Suit.DIAMONDS
        assert card_t.point_value == 0

    def test_card_from_str_case_and_symbols(self) -> None:
        c1 = Card.from_str("kd")
        assert c1.rank == Rank.KING
        assert c1.suit == Suit.DIAMONDS
        assert c1.is_face_card is True

        c2 = Card.from_str("9♠")
        assert c2.rank == Rank.NINE
        assert c2.suit == Suit.SPADES
        assert c2.point_value == 9

    def test_invalid_card_string_raises(self) -> None:
        with pytest.raises(InvalidCardError):
            Card.from_str("X")
        with pytest.raises(InvalidCardError):
            Card.from_str("11h")
        with pytest.raises(InvalidCardError):
            Card.from_str("Ax")


class TestHandCreation:
    """Test Hand creation, validation, and error boundaries."""

    def test_valid_hand_from_str(self) -> None:
        hand = Hand.from_str("As Kh Qd")
        assert len(hand.cards) == 3
        assert hand.cards[0] == Card(Rank.ACE, Suit.SPADES)

    def test_duplicate_cards_raises(self) -> None:
        with pytest.raises(InvalidHandSizeError):
            Hand.from_str("As As Qd")

    def test_invalid_hand_size_raises(self) -> None:
        with pytest.raises(InvalidHandSizeError):
            Hand.from_str("As Kh")
        with pytest.raises(InvalidHandSizeError):
            Hand.from_str("As Kh Qd Jc")


class TestSapHierarchy:
    """Test Sáp (Three of a Kind, Category 4) evaluation and ranking."""

    def test_sap_isolation_and_order(self) -> None:
        sap_a = Hand.from_str("As Ah Ad")
        sap_k = Hand.from_str("Ks Kh Kd")
        sap_2 = Hand.from_str("2s 2h 2d")

        assert sap_a.score.category == HandCategory.SAP
        assert sap_k.score.category == HandCategory.SAP
        assert sap_2.score.category == HandCategory.SAP

        # Total order: AAA > KKK > ... > 222
        assert sap_a > sap_k
        assert sap_k > sap_2
        assert sap_a > sap_2

    def test_sap_beats_highest_lieng(self) -> None:
        sap_2 = Hand.from_str("2s 2h 2d")
        highest_lieng = Hand.from_str("Qs Kh Ad")  # Q-K-A
        assert sap_2 > highest_lieng


class TestLiengHierarchy:
    """Test Liêng (Straight, Category 3) evaluation and sequences."""

    def test_all_twelve_valid_lieng_sequences(self) -> None:
        sequences = [
            "As 2h 3d",  # 1: A-2-3 (Lowest)
            "2s 3h 4d",  # 2: 2-3-4
            "3s 4h 5d",  # 3: 3-4-5
            "4s 5h 6d",  # 4: 4-5-6
            "5s 6h 7d",  # 5: 5-6-7
            "6s 7h 8d",  # 6: 6-7-8
            "7s 8h 9d",  # 7: 7-8-9
            "8s 9h 10d", # 8: 8-9-10
            "9s 10h Jd", # 9: 9-10-J
            "10s Jh Qd", # 10: 10-J-Q
            "Js Qh Kd",  # 11: J-Q-K
            "Qs Kh Ad",  # 12: Q-K-A (Highest)
        ]
        hands = [Hand.from_str(seq) for seq in sequences]

        # Verify each is recognized as Category LIENG
        for h in hands:
            assert h.score.category == HandCategory.LIENG

        # Verify strict monotonicity: sequence i < sequence i + 1
        for i in range(len(hands) - 1):
            assert hands[i] < hands[i + 1]

        # Verify edge checks: Q-K-A is highest, A-2-3 is lowest
        assert hands[-1] > hands[0]
        assert hands[1] > hands[0]  # 2-3-4 > A-2-3

    def test_ka2_wraparound_rejection(self) -> None:
        """K-A-2 is strictly prohibited as a Liêng and falls back to Điểm."""
        ka2_hand = Hand.from_str("Ks Ah 2d")
        score = ka2_hand.score
        assert score.category == HandCategory.DIEM
        assert score.category != HandCategory.LIENG
        # K(0) + A(1) + 2(2) = 3 points
        assert score.score == 3
        assert score.primary_rank == 3


class TestDiHierarchy:
    """Test Đĩ (Three Face Cards, Category 2) evaluation and priority."""

    def test_di_valid_combinations(self) -> None:
        di_hands = [
            Hand.from_str("Js Qh Qd"),  # J-Q-Q
            Hand.from_str("Js Kh Kd"),  # J-K-K
            Hand.from_str("Js Jh Qd"),  # J-J-Q
            Hand.from_str("Js Jh Kd"),  # J-J-K
            Hand.from_str("Qs Qh Kd"),  # Q-Q-K
            Hand.from_str("Qs Kh Kd"),  # Q-K-K
        ]
        for h in di_hands:
            assert h.score.category == HandCategory.DI

    def test_di_isolation_from_sap_and_lieng(self) -> None:
        """JJJ must be SAP (Cat 4), and JQK must be LIENG (Cat 3), NOT Đĩ (Cat 2)."""
        jjj = Hand.from_str("Js Jh Jd")
        assert jjj.score.category == HandCategory.SAP
        assert jjj.score.category != HandCategory.DI

        jqk = Hand.from_str("Js Qh Kd")
        assert jqk.score.category == HandCategory.LIENG
        assert jqk.score.category != HandCategory.DI

    def test_ace_plus_face_cards_not_di(self) -> None:
        """Ace is not a face card in Liêng, so A-J-J and A-Q-J are Điểm (1 pt), NOT Đĩ."""
        ajj = Hand.from_str("As Jh Jd")
        assert ajj.score.category == HandCategory.DIEM
        assert ajj.score.score == 1

        aqj = Hand.from_str("As Qh Jd")
        assert aqj.score.category == HandCategory.DIEM
        assert aqj.score.score == 1

    def test_di_strictly_beats_nine_points(self) -> None:
        """Crucial rule: Any Đĩ strictly beats any point hand, including 9 points."""
        di_hand = Hand.from_str("Js Qh Qd")
        nine_pts_1 = Hand.from_str("9s 10h Kd")  # 9 + 0 + 0 = 9 pts
        nine_pts_2 = Hand.from_str("As 3h 5d")   # 1 + 3 + 5 = 9 pts

        assert nine_pts_1.score.category == HandCategory.DIEM
        assert nine_pts_1.score.score == 9

        assert nine_pts_2.score.category == HandCategory.DIEM
        assert nine_pts_2.score.score == 9

        assert di_hand > nine_pts_1
        assert di_hand > nine_pts_2

    def test_lieng_beats_di(self) -> None:
        """Lowest Liêng (A-2-3) strictly beats any Đĩ."""
        lowest_lieng = Hand.from_str("As 2h 3d")
        strongest_di = Hand.from_str("Qs Kh Kd")  # Q-K-K
        assert lowest_lieng > strongest_di


class TestDiemModulo10:
    """Test Category 1 Điểm modulo 10 scoring and comparisons."""

    def test_point_sum_values(self) -> None:
        # Card value calculation: 10 + J + Q = 0 + 0 + 0 = 0 pts
        c10 = Card.from_str("10s")
        cj = Card.from_str("Jc")
        cq = Card.from_str("Qd")
        assert calculate_points([c10, cj, cq]) == 0

    def test_modulo_10_calculations(self) -> None:
        # 9 + 10 + K = 19 -> 9 pts
        hand_19 = Hand.from_str("9s 10h Kd")
        assert hand_19.score.category == HandCategory.DIEM
        assert hand_19.score.score == 9

        # A + 3 + 5 = 9 pts
        hand_9 = Hand.from_str("As 3h 5d")
        assert hand_9.score.category == HandCategory.DIEM
        assert hand_9.score.score == 9

        # 0 pts (Bù): 10 + J + K = 0 + 0 + 0 = 0 pts (non-straight, non-face only)
        hand_bu = Hand.from_str("10s Jh Kd")
        assert hand_bu.score.category == HandCategory.DIEM
        assert hand_bu.score.score == 0

        # 20 pts: 10 + 10 + K -> 0 pts (Bù)
        hand_20 = Hand.from_str("10s 10h Kd")
        assert hand_20.score.category == HandCategory.DIEM
        assert hand_20.score.score == 0

    def test_points_ordering(self) -> None:
        hand_9 = Hand.from_str("As 3h 5d")  # 9 pts
        hand_8 = Hand.from_str("2s 2h 4d")  # 8 pts
        hand_0 = Hand.from_str("10s Jh Kd") # 0 pts

        assert hand_9 > hand_8
        assert hand_8 > hand_0
        assert hand_9 > hand_0


class TestTieBreakHouseRules:
    """AGENTS.md leaves ties inside Đĩ and Điểm to "game configuration"; these pin what the code does."""

    def test_di_order_highest_face_card_then_middle_then_rest(self) -> None:
        hands = ["Qs Jh Jd", "Qs Qh Jd", "Ks Jh Jd", "Ks Qh Qd", "Ks Kh Jd", "Ks Kh Qd"]
        ordered = sorted((Hand.from_str(h) for h in hands), reverse=True)
        assert [str(h) for h in ordered] == ["Ks Kh Qd", "Ks Kh Jd", "Ks Qh Qd", "Ks Jh Jd", "Qs Qh Jd", "Qs Jh Jd"]

    def test_diem_ties_broken_by_highest_rank_with_ace_high(self) -> None:
        """A-K-8 and K-Q-9 are both 9 points; the Ace counts as the highest card (rank 14)."""
        assert Hand.from_str("As Kd 8c") > Hand.from_str("Ks Qd 9c")

    def test_same_ranks_tie_whatever_the_suits(self) -> None:
        assert Hand.from_str("As 8d Kc") == Hand.from_str("Ah 8s Kd")


class TestHashing:
    """Equal objects must hash equally (weak spot H1)."""

    def test_equal_hands_hash_equally_and_collapse_in_a_set(self) -> None:
        a, b = Hand.from_str("As Kh Qd"), Hand.from_str("Ac Kd Qh")
        assert a == b
        assert hash(a) == hash(b)
        assert len({a, b}) == 1

    def test_hand_scores_hash_by_score_tuple(self) -> None:
        a, b = Hand.from_str("As Kh Qd").score, Hand.from_str("Ac Kd Qh").score
        assert a == b and hash(a) == hash(b)

    def test_score_is_cached_on_the_hand(self) -> None:
        """cached_property stores the score in the instance dict on first access (a plain
        @property would not), so later comparisons don't evaluate the hand again."""
        hand = Hand.from_str("As Kh Qd")
        assert "score" not in hand.__dict__
        first = hand.score
        assert hand.__dict__["score"] is first


class TestErrorsAndSpeed:
    def test_duplicate_cards_raise_duplicate_card_error(self) -> None:
        with pytest.raises(DuplicateCardError):
            Hand.from_str("As As Kd")
        with pytest.raises(DuplicateCardError):
            evaluate_hand([Card.from_str("As")] * 3)

    def test_card_error_names_the_whole_card(self) -> None:
        with pytest.raises(InvalidCardError, match=r"Invalid card '11h'"):
            Card.from_str("11h")

    def test_evaluation_within_latency_budget(self) -> None:
        """AGENTS.md section 6: one hand evaluation in under 1 microsecond."""
        cards = Hand.from_str("As Kh Qd").cards
        best = min(timeit.repeat(lambda: evaluate_hand(cards), number=20000, repeat=5)) / 20000
        assert best * 1e6 < budget(1.0), f"evaluate_hand took {best * 1e6:.3f} us"
