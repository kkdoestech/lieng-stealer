"""Liêng Stealer - Flask REST API Backend.

Provides RESTful endpoints for game-theoretic range solving, single-hand valuation,
and AI-powered strategic commentary via OpenRouter LLM.
"""

from __future__ import annotations

import os
from math import isfinite
from pathlib import Path
from typing import Any, Sequence

import requests
from flask import Flask, jsonify, request
from flask_cors import CORS

from src.db import WinRateDB
from src.evaluator import Hand, HandCategory
from src.exceptions import LiengError
from src.ev import calculate_break_even_fold_equity, evaluate_action
from src.hands import to_canonical
from src.opponent_model import calculate_calling_range_equities
from src.range_finder import HandEVRecord, RangeFinder

app = Flask(__name__)
# Explicitly enable CORS for all origins on /api/*, /, and /health
CORS(app, resources={r"/api/*": {"origins": "*"}, r"/": {"origins": "*"}, r"/health": {"origins": "*"}})

# Initialize WinRateDB at startup
DB_PATH = Path(__file__).resolve().parent / "data" / "winrates.json"
win_rate_db = WinRateDB()
if DB_PATH.is_file():
    win_rate_db.load(DB_PATH)
range_finder = RangeFinder(win_rate_db)
FOLD_EQUITY_SENSITIVITY = 0.10
CALL_RANGE_SENSITIVITY = 10.0


def _build_category_breakdown(
    records: Sequence[HandEVRecord],
) -> list[dict[str, Any]]:
    """Aggregate exact class and combination counts for each hand category."""
    breakdown: list[dict[str, Any]] = []
    for category in (
        HandCategory.SAP,
        HandCategory.LIENG,
        HandCategory.DI,
        HandCategory.DIEM,
    ):
        category_records = [record for record in records if record.category == category]
        profitable_records = [
            record for record in category_records if record.is_raise_profitable
        ]
        total_combinations = sum(record.multiplicity for record in category_records)
        profitable_combinations = sum(
            record.multiplicity for record in profitable_records
        )
        breakdown.append({
            "category": category.name,
            "total_classes": len(category_records),
            "total_combinations": total_combinations,
            "profitable_classes": len(profitable_records),
            "profitable_combinations": profitable_combinations,
            "coverage_percent": round(
                profitable_combinations / total_combinations * 100.0,
                2,
            ),
        })
    return breakdown


def _build_hand_sensitivity(
    player_hand: Hand,
    pot: float,
    bet_size: float,
    fold_equity: float,
    call_range_percent: float,
) -> dict[str, Any]:
    """Evaluate EV on a 3-by-3 grid around the supplied model assumptions."""
    fold_scenarios = sorted({
        round(max(0.0, fold_equity - FOLD_EQUITY_SENSITIVITY), 10),
        round(fold_equity, 10),
        round(min(1.0, fold_equity + FOLD_EQUITY_SENSITIVITY), 10),
    })
    call_range_scenarios = sorted({
        max(1.0, call_range_percent - CALL_RANGE_SENSITIVITY),
        call_range_percent,
        min(100.0, call_range_percent + CALL_RANGE_SENSITIVITY),
    })
    equities = calculate_calling_range_equities(
        player_hand.cards,
        call_range_scenarios,
    )
    scenarios = [
        {
            "fold_equity": fold_rate,
            "call_range_percent": call_percent,
            "equity_when_called": equities[call_percent],
            "ev": evaluate_action(
                pot,
                bet_size,
                fold_rate,
                equities[call_percent],
            ).ev,
        }
        for fold_rate in fold_scenarios
        for call_percent in call_range_scenarios
    ]
    scenario_evs = [scenario["ev"] for scenario in scenarios]
    if all(ev > 0.0 for ev in scenario_evs):
        status = "ROBUST_BET"
    elif all(ev <= 0.0 for ev in scenario_evs):
        status = "ROBUST_NO_BET"
    else:
        status = "ASSUMPTION_SENSITIVE"

    return {
        "fold_equity_range": [fold_scenarios[0], fold_scenarios[-1]],
        "call_range_percent_range": [
            call_range_scenarios[0],
            call_range_scenarios[-1],
        ],
        "central_equity_when_called": equities[call_range_percent],
        "status": status,
        "scenarios": scenarios,
    }


@app.route("/", methods=["GET"])
def root() -> Any:
    """Root endpoint providing service metadata."""
    return jsonify({
        "service": "Lieng Stealer API",
        "status": "online",
        "endpoints": ["/health", "/api/solve", "/api/analyze"],
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
        call_range_percent (float): Strongest share of hands that call (0, 100].
        hand (str, optional): Player 3-card hand notation (e.g. 'As Kh Qd').
    """
    data = request.get_json(silent=True) or {}

    try:
        pot = float(data.get("pot", 100000.0))
        bet_size = float(data.get("bet_size", 50000.0))
        fold_equity = float(data.get("fold_equity", 0.35))
        call_range_percent = float(data.get("call_range_percent", 30.0))
    except (ValueError, TypeError):
        return jsonify({
            "error": "Invalid numerical parameters for pot, bet_size, fold_equity, or call_range_percent."
        }), 400

    if not all(isfinite(value) for value in (pot, bet_size, fold_equity, call_range_percent)):
        return jsonify({
            "error": "Pot, bet_size, fold_equity, and call_range_percent must be finite numbers."
        }), 400
    if pot <= 0 or bet_size <= 0:
        return jsonify({"error": "Pot and bet_size must be strictly greater than zero."}), 400
    if not (0.0 <= fold_equity <= 1.0):
        return jsonify({"error": "Fold equity must be between 0.0 and 1.0."}), 400
    if not (0.0 < call_range_percent <= 100.0):
        return jsonify({"error": "Call range percent must be greater than 0 and at most 100."}), 400

    hand_input = data.get("hand")
    hand_eval_result = None

    if hand_input and isinstance(hand_input, str) and hand_input.strip():
        try:
            player_hand = Hand.from_str(hand_input.strip())
            stats = win_rate_db.get_by_cards(player_hand.cards)
            sensitivity = _build_hand_sensitivity(
                player_hand,
                pot,
                bet_size,
                fold_equity,
                call_range_percent,
            )
            caller_equity = sensitivity["central_equity_when_called"]
            ev_res = evaluate_action(pot, bet_size, fold_equity, caller_equity)
            canonical = to_canonical(player_hand.cards)
            hand_eval_result = {
                "hand": str(player_hand),
                "score_name": str(player_hand.score),
                "category": stats.category.name,
                "category_name": stats.category.display_name,
                "canonical_id": canonical.canonical_id,
                "showdown_equity": caller_equity,
                "random_hand_equity": stats.equity,
                "call_range_percent": call_range_percent,
                "ev": ev_res.ev,
                "break_even_fold_equity": ev_res.break_even_fold_equity,
                "sensitivity": sensitivity,
                "is_profitable": ev_res.is_profitable,
                "decision": "BET" if ev_res.is_profitable else "NO BET",
            }
        except LiengError as err:
            return jsonify({"error": f"Invalid hand: {err}"}), 400

    # Solve full range
    records = range_finder.solve_range(pot, bet_size, fold_equity)
    profitable_records = [r for r in records if r.is_raise_profitable]
    coverage = range_finder.calculate_range_coverage(profitable_records)
    category_breakdown = _build_category_breakdown(records)
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
            "call_range_percent": call_range_percent,
            "final_pot": pot + 2.0 * bet_size,
            "range_model": "random_opponent_equity_baseline",
            "pure_bluff_break_even_fold_equity": be_bluff,
            "total_canonical_classes": len(records),
            "profitable_classes": len(profitable_records),
            "total_combinations": 22100,
            "profitable_combinations": total_combos_in_range,
            "range_coverage_percent": coverage,
            "category_breakdown": category_breakdown,
            "highest_ev_hand": records[0].canonical_id if records else None,
            "highest_ev_value": records[0].ev if records else None,
            "threshold_hand": profitable_records[-1].canonical_id if profitable_records else None,
            "threshold_ev_value": profitable_records[-1].ev if profitable_records else None,
        },
        "hand_evaluation": hand_eval_result,
        "top_hands": top_hands,
    })


@app.route("/api/evaluate", methods=["POST"])
def evaluate_api() -> Any:
    """Evaluate a single 3-card hand against current game parameters."""
    data = request.get_json(silent=True) or {}
    try:
        pot = float(data.get("pot", 100000.0))
        bet = float(data.get("bet", data.get("bet_size", 50000.0)))
        fold_equity = float(data.get("fold_equity", 0.35))
        call_range_percent = float(data.get("call_range_percent", 30.0))
    except (ValueError, TypeError):
        return jsonify({
            "error": "Invalid numerical parameters for pot, bet, fold_equity, or call_range_percent."
        }), 400

    if not all(isfinite(value) for value in (pot, bet, fold_equity, call_range_percent)):
        return jsonify({
            "error": "Pot, bet, fold_equity, and call_range_percent must be finite numbers."
        }), 400
    if pot <= 0 or bet <= 0:
        return jsonify({"error": "Pot and bet must be strictly greater than zero."}), 400
    if not (0.0 <= fold_equity <= 1.0):
        return jsonify({"error": "Fold equity must be between 0.0 and 1.0."}), 400
    if not (0.0 < call_range_percent <= 100.0):
        return jsonify({"error": "Call range percent must be greater than 0 and at most 100."}), 400

    hand_input = data.get("hand")
    if not hand_input or not isinstance(hand_input, str) or not hand_input.strip():
        return jsonify({"error": "Field 'hand' is required."}), 400

    try:
        player_hand = Hand.from_str(hand_input.strip())
        stats = win_rate_db.get_by_cards(player_hand.cards)
        sensitivity = _build_hand_sensitivity(
            player_hand,
            pot,
            bet,
            fold_equity,
            call_range_percent,
        )
        caller_equity = sensitivity["central_equity_when_called"]
        ev_res = evaluate_action(pot, bet, fold_equity, caller_equity)
        canonical = to_canonical(player_hand.cards)
        return jsonify({
            "hand": str(player_hand),
            "canonical_id": canonical.canonical_id,
            "category": stats.category.name,
            "pot": pot,
            "bet": bet,
            "fold_equity": fold_equity,
            "showdown_equity": caller_equity,
            "random_hand_equity": stats.equity,
            "call_range_percent": call_range_percent,
            "ev": ev_res.ev,
            "break_even_fold_equity": ev_res.break_even_fold_equity,
            "sensitivity": sensitivity,
            "recommended_action": "BET" if ev_res.is_profitable else "NO BET",
            "is_profitable": ev_res.is_profitable,
        }), 200
    except LiengError as err:
        return jsonify({"error": f"Invalid hand: {err}"}), 400


@app.route("/api/range", methods=["POST"])
def range_api() -> Any:
    """Scan and return full combinatorial range coverage and thresholds."""
    data = request.get_json(silent=True) or {}
    try:
        pot = float(data.get("pot", 100000.0))
        bet = float(data.get("bet", data.get("bet_size", 50000.0)))
        fold_equity = float(data.get("fold_equity", 0.35))
    except (ValueError, TypeError):
        return jsonify({"error": "Invalid numerical parameters for pot, bet, or fold_equity."}), 400

    if not all(isfinite(value) for value in (pot, bet, fold_equity)):
        return jsonify({"error": "Pot, bet, and fold_equity must be finite numbers."}), 400
    if pot <= 0 or bet <= 0:
        return jsonify({"error": "Pot and bet must be strictly greater than zero."}), 400
    if not (0.0 <= fold_equity <= 1.0):
        return jsonify({"error": "Fold equity must be between 0.0 and 1.0."}), 400

    records = range_finder.solve_range(pot, bet, fold_equity)
    profitable = [r for r in records if r.is_raise_profitable]
    coverage = range_finder.calculate_range_coverage(profitable)
    be_bluff = calculate_break_even_fold_equity(pot, bet, win_rate_when_called=0.0)
    combos = sum(r.multiplicity for r in profitable)

    return jsonify({
        "pot": pot,
        "bet": bet,
        "fold_equity": fold_equity,
        "range_model": "random_opponent_equity_baseline",
        "final_pot": pot + 2.0 * bet,
        "pure_bluff_break_even_fold_equity": be_bluff,
        "total_combinations": 22100,
        "profitable_combinations": combos,
        "range_coverage_percent": coverage,
        "category_breakdown": _build_category_breakdown(records),
        "total_canonical_classes": len(records),
        "profitable_classes": len(profitable),
        "top_hands": [
            {
                "canonical_id": r.canonical_id,
                "category": r.category.name,
                "showdown_equity": r.equity,
                "ev": r.ev,
                "multiplicity": r.multiplicity,
                "recommended_action": "BET" if r.is_raise_profitable else "NO BET",
            }
            for r in records[:30]
        ],
    }), 200


@app.route("/api/analyze", methods=["POST"])
def analyze_api() -> Any:
    """Query OpenRouter LLM for strategic game-theoretic commentary."""
    data = request.get_json(silent=True) or {}

    pot = data.get("pot", 100000.0)
    bet_size = data.get("bet_size", 50000.0)
    fold_equity = data.get("fold_equity", 0.35)
    hand = data.get("hand", "None")
    hand_eval = data.get("hand_evaluation") or {}
    coverage = data.get("range_coverage_percent", 0.0)

    api_key = os.environ.get("OPENROUTER_API_KEY")

    prompt = (
        f"You analyze expected value for Vietnamese Liêng bets.\n"
        f"Explain this bet under the supplied assumptions in Vietnamese:\n\n"
        f"- Current Pot: {pot:,.0f} VND\n"
        f"- Bet / Raise Size: {bet_size:,.0f} VND\n"
        f"- Opponent Fold Equity: {float(fold_equity) * 100:.1f}%\n"
        f"- Random-hand baseline range coverage (not call-conditioned): {coverage}%\n"
    )

    if hand_eval:
        prompt += (
            f"- Hero's Hand: {hand_eval.get('hand')} ({hand_eval.get('score_name')})\n"
            f"- Equity versus strongest {float(hand_eval.get('call_range_percent', 30)):.1f}% of legal hands: "
            f"{float(hand_eval.get('showdown_equity', 0)) * 100:.1f}%\n"
            f"- Equity versus a random hand: {float(hand_eval.get('random_hand_equity', 0)) * 100:.1f}%\n"
            f"- Calculated EV: {float(hand_eval.get('ev', 0)):+,.0f} VND\n"
            f"- Solver Decision: {hand_eval.get('decision')}\n"
            f"- Assumption Sensitivity: {hand_eval.get('sensitivity', {}).get('status', 'not available')}\n"
        )
    else:
        prompt += f"- Hero's Hand: {hand} (General Range Analysis)\n"

    prompt += (
        "\nAnalyze only the specified bet's expected value under the supplied assumptions. "
        "Do not claim to solve GTO or recommend an all-in, check, call, or fold, because "
        "those alternatives are not modeled. The caller range is a simplifying strength-percentile assumption, "
        "not a learned opponent-specific range.\n"
        "Provide a structured breakdown:\n"
        "1. [Quyết định Toán học & EV]: Phân tích EV, Fold Equity và ngưỡng hòa vốn.\n"
        "2. [Đánh giá mức cược]: Nêu BET nếu EV dương hoặc NO BET nếu EV không dương, "
        "và nhắc rõ kết quả phụ thuộc vào các giả định đầu vào.\n"
        "3. [Giới hạn mô hình]: Nêu rõ range gọi là giả định top X% theo độ mạnh bài, fold frequency do người dùng "
        "ước lượng, và phân tích độ nhạy là theo khoảng đã chọn; không phải dữ liệu đối thủ thực tế."
    )

    if not api_key:
        # Fallback commentary when no OpenRouter API key is configured
        fallback_advice = (
            f"**[Phân Tích Chiến Thuật Hệ Thống (Offline Solver)]**\n\n"
            f"1. **Quyết định Toán học:** Với Pot = {pot:,.0f}, Cược = {bet_size:,.0f}, và Fold Equity = {float(fold_equity)*100:.1f}%, "
            f"ngưỡng hòa vốn cược hù (bluff) là {(bet_size / (pot + bet_size))*100:.1f}%. "
            f"Khoảng bài có lãi (EV > 0) chiếm **{coverage}%** toàn bộ thế bài có thể có.\n\n"
            f"2. **Hành động Khuyến nghị:** "
        )
        if hand_eval:
            decision = hand_eval.get("decision", "EVALUATE")
            ev = hand_eval.get("ev", 0)
            fallback_advice += (
                f"Hero cầm **{hand_eval.get('hand')}** ({hand_eval.get('score_name')}) "
                f"với equity {float(hand_eval.get('showdown_equity', 0))*100:.1f}% khi bị call bởi "
                f"top {float(hand_eval.get('call_range_percent', 30)):.0f}% bài mạnh nhất. "
                f"Kỳ vọng thu nhập (EV) đạt **{ev:+,.0f} VND**. "
                f"Tín hiệu EV cho mức cược đã nhập: **{decision}**. "
                f"Độ nhạy giả định: **{hand_eval.get('sensitivity', {}).get('status', 'N/A')}**.\n\n"
                f"3. **Giới hạn mô hình:** Fold frequency vẫn do người dùng ước lượng; range gọi chỉ là "
                f"mô hình top-percentile theo sức mạnh, không phải dữ liệu người chơi thực. "
                f"Kết quả chỉ đánh giá mức cược đã nhập; không tự quyết định check, call, fold hay all-in."
            )
        else:
            fallback_advice += (
                f"Với Fold Equity giả định {float(fold_equity)*100:.1f}%, {coverage}% canonical hand classes "
                f"có EV dương trong baseline equity-vs-random hiện tại. Đây không phải phân tích theo range gọi; "
                f"hãy xem là tham khảo có điều kiện, không phải chiến lược tối ưu."
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
