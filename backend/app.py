"""Liêng Stealer - Flask REST API Backend.

Provides RESTful endpoints for game-theoretic range solving, single-hand valuation,
and AI-powered strategic commentary via OpenRouter LLM.
"""

from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Callable, Sequence

import requests
from flask import Flask, jsonify, request
from flask_cors import CORS

from src.calling_range import CallingRangeModel, OpponentModel
from src.db import WinRateDB
from src.evaluator import Hand, HandCategory
from src.exceptions import InvalidGameParamsError, LiengError
from src.ev import EVResult, calculate_break_even_fold_equity, evaluate_action, profitable_fold_zones
from src.hands import to_canonical
from src.range_finder import HandEVRecord, RangeFinder

app = Flask(__name__)
# Explicitly enable CORS for all origins on /api/*, /, and /health
CORS(app, resources={r"/api/*": {"origins": "*"}, r"/": {"origins": "*"}, r"/health": {"origins": "*"}})

# Initialize WinRateDB and the calling-range model at startup
DB_PATH = Path(__file__).resolve().parent / "data" / "winrates.json"
win_rate_db = WinRateDB()
if DB_PATH.is_file():
    win_rate_db.load(DB_PATH)
calling_model = CallingRangeModel()
range_finder = RangeFinder(win_rate_db, calling_model)


@dataclass(frozen=True)
class GameParams:
    """Validated game-state parameters shared by the solver endpoints."""
    pot: float
    bet_size: float
    fold_equity: float
    opponent_model: OpponentModel


def _parse_game_params(data: dict[str, Any]) -> GameParams:
    """Parse and validate pot, bet size, fold equity, and opponent model from a request body.

    Raises:
        InvalidGameParamsError: If any parameter is missing a valid value or out of bounds.
    """
    try:
        pot = float(data.get("pot", 100000.0))
        bet_size = float(data.get("bet_size", data.get("bet", 50000.0)))
        fold_equity = float(data.get("fold_equity", 0.35))
    except (ValueError, TypeError) as err:
        raise InvalidGameParamsError("Invalid numerical parameters for pot, bet_size, or fold_equity.") from err

    if pot <= 0 or bet_size <= 0:
        raise InvalidGameParamsError("Pot and bet_size must be strictly greater than zero.")
    if not (0.0 <= fold_equity <= 1.0):
        raise InvalidGameParamsError("Fold equity must be between 0.0 and 1.0.")

    try:
        opponent_model = OpponentModel(data.get("opponent_model", OpponentModel.RANDOM.value))
    except ValueError as err:
        choices = ", ".join(m.value for m in OpponentModel)
        raise InvalidGameParamsError(f"opponent_model must be one of: {choices}.") from err

    return GameParams(pot, bet_size, fold_equity, opponent_model)


@app.errorhandler(InvalidGameParamsError)
def handle_invalid_params(err: InvalidGameParamsError) -> Any:
    """Render invalid game parameters as a 400 JSON error."""
    return jsonify({"error": str(err)}), 400


def _equity_function(canonical_id: str, random_equity: float, model: OpponentModel) -> Callable[[float], float]:
    """Map a fold frequency to Hero's equity when called, under the chosen opponent model."""
    if model is OpponentModel.RANGE:
        return lambda f: calling_model.equity(canonical_id, f)
    return lambda f: random_equity


def _evaluate_hand(
    canonical_id: str,
    random_equity: float,
    params: GameParams,
) -> tuple[EVResult, list[tuple[float, float]]]:
    """Return the EV result and the profitable fold-frequency zones."""
    equity_at = _equity_function(canonical_id, random_equity, params.opponent_model)
    ev_res = evaluate_action(params.pot, params.bet_size, params.fold_equity, equity_at(params.fold_equity))
    zones = profitable_fold_zones(params.pot, params.bet_size, equity_at)
    return ev_res, zones


def _break_even_fields(
    ev_res: EVResult,
    zones: list[tuple[float, float]],
    model: OpponentModel,
) -> dict[str, float | None]:
    """Describe when raising pays off, with one unambiguous meaning per field.

    break_even_fold_equity: exact fold frequency where EV = 0 (random model only; under
        RANGE, EV is not monotonic in fold equity, so no single break-even point exists).
    profitable_from_fold_equity: first 1%-grid fold frequency from which raising stays +EV.
        The last zone always ends at 1.0, because EV there equals the pot.
    """
    return {
        "break_even_fold_equity": ev_res.break_even_fold_equity if model is OpponentModel.RANDOM else None,
        "profitable_from_fold_equity": zones[-1][0],
    }


def _category_breakdown(records: Sequence[HandEVRecord]) -> list[dict[str, Any]]:
    """Summarize classes, combos, and profitable combos per hand category (strongest first)."""
    breakdown = []
    for category in sorted(HandCategory, reverse=True):
        members = [r for r in records if r.category is category]
        breakdown.append({
            "category": category.name,
            "classes": len(members),
            "combos": sum(r.multiplicity for r in members),
            "profitable_combos": sum(r.multiplicity for r in members if r.is_raise_profitable),
        })
    return breakdown


@app.route("/", methods=["GET"])
def root() -> Any:
    """Root endpoint providing service metadata."""
    return jsonify({
        "service": "Lieng Stealer API",
        "status": "online",
        "endpoints": ["/health", "/api/solve", "/api/evaluate", "/api/range", "/api/analyze"],
    }), 200


@app.route("/health", methods=["GET"])
def health_check() -> Any:
    """Health check endpoint returning system status and database stats."""
    return jsonify({
        "status": "healthy",
        "database_loaded": win_rate_db.is_loaded,
        "classes_loaded": len(win_rate_db),
        "version": "1.0.0",
    })


@app.route("/api/solve", methods=["POST"])
def solve_api() -> Any:
    """Calculate EV range and specific hand decision.

    Expected JSON body:
        pot (float): Dead pot size (> 0).
        bet_size (float): Hero raise / wager amount (> 0).
        fold_equity (float): Opponent fold probability in [0.0, 1.0].
        hand (str, optional): Player 3-card hand notation (e.g. 'As Kh Qd').
        opponent_model (str, optional): 'random' (default) or 'range'.
    """
    data = request.get_json(silent=True) or {}
    params = _parse_game_params(data)
    pot, bet_size, fold_equity = params.pot, params.bet_size, params.fold_equity

    hand_input = data.get("hand")
    hand_eval_result = None

    if hand_input and isinstance(hand_input, str) and hand_input.strip():
        try:
            player_hand = Hand.from_str(hand_input.strip())
            stats = win_rate_db.get_by_cards(player_hand.cards)
            canonical = to_canonical(player_hand.cards)
        except LiengError as err:
            return jsonify({"error": f"Invalid hand: {err}"}), 400

        ev_res, zones = _evaluate_hand(canonical.canonical_id, stats.equity, params)
        hand_eval_result = {
            "hand": str(player_hand),
            "score_name": str(player_hand.score),
            "category": stats.category.name,
            "category_name": stats.category.display_name,
            "canonical_id": canonical.canonical_id,
            "showdown_equity": ev_res.win_rate_when_called,
            "equity_vs_random": stats.equity,
            "ev": ev_res.ev,
            **_break_even_fields(ev_res, zones, params.opponent_model),
            "profitable_fold_zones": [[start, end] for start, end in zones],
            "is_profitable": ev_res.is_profitable,
            "decision": "RAISE" if ev_res.is_profitable else "CHECK/FOLD",
        }

    # Solve full range
    records = range_finder.solve_range(pot, bet_size, fold_equity, params.opponent_model)
    profitable_records = [r for r in records if r.is_raise_profitable]
    coverage = range_finder.calculate_range_coverage(profitable_records)
    be_bluff = calculate_break_even_fold_equity(pot, bet_size, win_rate_when_called=0.0)

    # Format top profitable hands (top 30)
    top_hands = [
        {
            "canonical_id": r.canonical_id,
            "category": r.category.name,
            "equity": r.equity,
            "ev": r.ev,
            "multiplicity": r.multiplicity,
            "is_profitable": r.is_raise_profitable,
        }
        for r in records[:30]
    ]

    total_combos_in_range = sum(r.multiplicity for r in profitable_records)

    return jsonify({
        "summary": {
            "pot": pot,
            "bet_size": bet_size,
            "fold_equity": fold_equity,
            "opponent_model": params.opponent_model.value,
            "final_pot": pot + 2.0 * bet_size,
            "pure_bluff_break_even_fold_equity": be_bluff,
            "total_canonical_classes": len(records),
            "profitable_classes": len(profitable_records),
            "total_combinations": 22100,
            "profitable_combinations": total_combos_in_range,
            "range_coverage_percent": coverage,
            "highest_ev_hand": records[0].canonical_id if records else None,
            "highest_ev_value": records[0].ev if records else None,
            "threshold_hand": profitable_records[-1].canonical_id if profitable_records else None,
            "threshold_ev_value": profitable_records[-1].ev if profitable_records else None,
            "category_breakdown": _category_breakdown(records),
        },
        "hand_evaluation": hand_eval_result,
        "top_hands": top_hands,
    })


@app.route("/api/evaluate", methods=["POST"])
def evaluate_api() -> Any:
    """Evaluate a single 3-card hand against current game parameters."""
    data = request.get_json(silent=True) or {}
    params = _parse_game_params(data)
    pot, bet, fold_equity = params.pot, params.bet_size, params.fold_equity

    hand_input = data.get("hand")
    if not hand_input or not isinstance(hand_input, str) or not hand_input.strip():
        return jsonify({"error": "Field 'hand' is required."}), 400

    try:
        player_hand = Hand.from_str(hand_input.strip())
        stats = win_rate_db.get_by_cards(player_hand.cards)
        canonical = to_canonical(player_hand.cards)
    except LiengError as err:
        return jsonify({"error": f"Invalid hand: {err}"}), 400

    ev_res, zones = _evaluate_hand(canonical.canonical_id, stats.equity, params)
    return jsonify({
        "hand": str(player_hand),
        "canonical_id": canonical.canonical_id,
        "category": stats.category.name,
        "pot": pot,
        "bet": bet,
        "fold_equity": fold_equity,
        "opponent_model": params.opponent_model.value,
        "showdown_equity": ev_res.win_rate_when_called,
        "equity_vs_random": stats.equity,
        "ev": ev_res.ev,
        **_break_even_fields(ev_res, zones, params.opponent_model),
        "recommended_action": "RAISE" if ev_res.is_profitable else "CHECK/FOLD",
        "is_profitable": ev_res.is_profitable,
    }), 200


@app.route("/api/range", methods=["POST"])
def range_api() -> Any:
    """Scan and return full combinatorial range coverage and thresholds."""
    data = request.get_json(silent=True) or {}
    params = _parse_game_params(data)
    pot, bet, fold_equity = params.pot, params.bet_size, params.fold_equity

    records = range_finder.solve_range(pot, bet, fold_equity, params.opponent_model)
    profitable = [r for r in records if r.is_raise_profitable]
    coverage = range_finder.calculate_range_coverage(profitable)
    be_bluff = calculate_break_even_fold_equity(pot, bet, win_rate_when_called=0.0)
    combos = sum(r.multiplicity for r in profitable)

    return jsonify({
        "pot": pot,
        "bet": bet,
        "fold_equity": fold_equity,
        "opponent_model": params.opponent_model.value,
        "final_pot": pot + 2.0 * bet,
        "pure_bluff_break_even_fold_equity": be_bluff,
        "total_combinations": 22100,
        "profitable_combinations": combos,
        "range_coverage_percent": coverage,
        "total_canonical_classes": len(records),
        "profitable_classes": len(profitable),
        "top_hands": [
            {
                "canonical_id": r.canonical_id,
                "category": r.category.name,
                "showdown_equity": r.equity,
                "ev": r.ev,
                "multiplicity": r.multiplicity,
                "recommended_action": "RAISE" if r.is_raise_profitable else "CHECK/FOLD",
            }
            for r in records[:30]
        ],
    }), 200


@app.route("/api/analyze", methods=["POST"])
def analyze_api() -> Any:
    """Query OpenRouter LLM for strategic game-theoretic commentary."""
    data = request.get_json(silent=True) or {}
    params = _parse_game_params(data)
    pot, bet_size, fold_equity = params.pot, params.bet_size, params.fold_equity

    hand = data.get("hand", "None")
    hand_eval = data.get("hand_evaluation") or {}
    if not isinstance(hand_eval, dict):
        raise InvalidGameParamsError("hand_evaluation must be a JSON object.")
    try:
        hand_ev = float(hand_eval.get("ev", 0))
        hand_equity = float(hand_eval.get("showdown_equity", 0))
    except (ValueError, TypeError) as err:
        raise InvalidGameParamsError("hand_evaluation.ev and showdown_equity must be numbers.") from err
    coverage = data.get("range_coverage_percent", 0.0)
    folds_weakest = params.opponent_model is OpponentModel.RANGE

    api_key = os.environ.get("OPENROUTER_API_KEY")

    if folds_weakest:
        model_line = f"folds their weakest hands (calls only with the top {(1 - fold_equity) * 100:.0f}%)"
    else:
        model_line = "folds at random, regardless of hand strength"
    prompt = (
        f"You are a World-Class Game Theory Expert and High-Stakes Vietnamese Liêng Solver.\n"
        f"Analyze this decision spot with precision and strategic depth in Vietnamese:\n\n"
        f"- Current Pot: {pot:,.0f} VND\n"
        f"- Bet / Raise Size: {bet_size:,.0f} VND\n"
        f"- Opponent Fold Equity: {fold_equity * 100:.1f}%\n"
        f"- Opponent Model: {model_line}\n"
        f"- Total Range Coverage (Hands with EV > 0): {coverage}%\n"
    )

    if hand_eval:
        prompt += (
            f"- Hero's Hand: {hand_eval.get('hand')} ({hand_eval.get('score_name')})\n"
            f"- Showdown Equity: {hand_equity * 100:.1f}%\n"
            f"- Calculated EV: {hand_ev:+,.0f} VND\n"
            f"- Solver Decision: {hand_eval.get('decision')}\n"
        )
    else:
        prompt += f"- Hero's Hand: {hand} (General Range Analysis)\n"

    prompt += (
        "\nProvide a structured breakdown:\n"
        "1. [Quyết định Toán học & EV]: Phân tích EV, Fold Equity và ngưỡng hòa vốn.\n"
        "2. [Chiến thuật Bluff & Giá trị]: Hero có nên Tố (Raise)/Tất tay hay Check/Bỏ bài? Giải thích tâm lý đối thủ.\n"
        "3. [Lời khuyên GTO]: Nhận xét ngắn gọn về độ rủi ro và cách khai thác đối thủ."
    )

    if not api_key:
        # Fallback commentary when no OpenRouter API key is configured
        fallback_advice = (
            f"**[Phân Tích Chiến Thuật Hệ Thống (Offline Solver)]**\n\n"
            f"1. **Quyết định Toán học:** Với Pot = {pot:,.0f}, Cược = {bet_size:,.0f}, và Fold Equity = {fold_equity*100:.1f}%, "
            f"ngưỡng hòa vốn cược hù (bluff) là {(bet_size / (pot + bet_size))*100:.1f}%. "
            f"Khoảng bài có lãi (EV > 0) chiếm **{coverage}%** toàn bộ thế bài có thể có. "
            + ("Giả định đối thủ bỏ những bài yếu nhất, nên khi bị theo, Hero đối đầu với nhóm bài mạnh hơn.\n\n" if folds_weakest
               else "Giả định đối thủ bỏ bài ngẫu nhiên, không phụ thuộc độ mạnh của bài.\n\n")
            + "2. **Hành động Khuyến nghị:** "
        )
        if hand_eval:
            decision = hand_eval.get("decision", "EVALUATE")
            fallback_advice += (
                f"Hero cầm **{hand_eval.get('hand')}** ({hand_eval.get('score_name')}) "
                f"với xác suất thắng đối đầu {hand_equity*100:.1f}%. "
                f"Kỳ vọng thu nhập (EV) đạt **{hand_ev:+,.0f} VND**. "
                f"Khuyến nghị tối ưu: **{decision}**.\n\n"
                f"3. **GTO Insight:** "
                + ("Bài có EV dương rõ rệt nhờ cả showdown equity lẫn fold equity. Tố lớn để tối đa hóa lợi nhuận." if hand_ev > 0
                   else "EV âm. Showdown equity quá thấp và đối thủ ít bỏ bài. Không nên mạo hiểm, hãy Bỏ bài (Fold) hoặc Theo nhẹ nếu có thể.")
            )
        else:
            fallback_advice += (
                f"Với tần suất đối thủ bỏ bài {fold_equity*100:.1f}%, hãy ưu tiên nâng cược với các nhóm bài Sáp, Liêng, Đĩ "
                f"và các tổ hợp điểm cao (> 7 điểm). Cẩn trọng cược hù khi đối thủ có xu hướng theo cược dính."
            )

        return jsonify({
            "advice": fallback_advice,
            "model": "rule-based-solver-engine (OPENROUTER_API_KEY not configured)",
        })

    # Call OpenRouter API
    headers = {
        "Authorization": f"Bearer {api_key}",
        "Content-Type": "application/json",
        "HTTP-Referer": "https://github.com/lieng-stealer",
        "X-Title": "Lieng Stealer Solver",
    }
    payload = {
        "model": "meta-llama/llama-3.1-8b-instruct:free",
        "messages": [
            {"role": "system", "content": "You are a professional game theory analyst specializing in Vietnamese card games like Liêng."},
            {"role": "user", "content": prompt},
        ],
        "temperature": 0.7,
        "max_tokens": 500,
    }

    try:
        resp = requests.post(
            "https://openrouter.ai/api/v1/chat/completions",
            headers=headers,
            json=payload,
            timeout=20,
        )
        if resp.status_code == 200:
            result_json = resp.json()
            advice = result_json["choices"][0]["message"]["content"]
            return jsonify({
                "advice": advice,
                "model": "meta-llama/llama-3.1-8b-instruct:free",
            })
        else:
            return jsonify({
                "error": f"OpenRouter API returned status {resp.status_code}: {resp.text}",
                "advice": f"Không thể lấy phân tích từ AI (Mã lỗi {resp.status_code}). Vui lòng kiểm tra OPENROUTER_API_KEY.",
            }), 502
    except requests.RequestException as err:
        return jsonify({
            "error": str(err),
            "advice": "Lỗi kết nối tới OpenRouter AI gateway.",
        }), 502


if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5000))
    app.run(host="0.0.0.0", port=port, debug=False)

