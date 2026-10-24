"""Liêng Stealer - Flask REST API Backend.

Provides RESTful endpoints for range solving, single-hand valuation, and AI-assisted strategic
commentary via OpenRouter. ``create_app()`` builds an app with its own database, calling-range
model and settings (dependency injection); the module-level ``app`` is the one that
``gunicorn app:app`` and ``python app.py`` serve.

Every response uses one vocabulary (``bet_size``, ``showdown_equity``, ``decision`` …), and every
error is JSON: ``{"error": "<message>", "code": "<code>"}``.
"""

from __future__ import annotations

import math
import os
from collections.abc import Callable, Mapping, Sequence
from dataclasses import dataclass
from typing import Any, Final

import requests
from flask import Blueprint, Flask, Response, current_app, jsonify, request
from flask_cors import CORS
from flask_limiter import Limiter
from flask_limiter.util import get_remote_address
from werkzeug.exceptions import HTTPException
from werkzeug.middleware.proxy_fix import ProxyFix

from src.calling_range import CallingRangeModel, OpponentModel
from src.db import HandStats, WinRateDB
from src.ev import (
    DEFAULT_BET_SIZE,
    DEFAULT_FOLD_EQUITY,
    DEFAULT_POT,
    EVResult,
    calculate_break_even_fold_equity,
    evaluate_action,
    final_pot,
    profitable_fold_zones,
)
from src.evaluator import Hand
from src.exceptions import InvalidCardError, InvalidGameParamsError, InvalidHandSizeError
from src.hands import TOTAL_COMBINATIONS, CanonicalHand, to_canonical
from src.paths import DEFAULT_DB_PATH
from src.range_finder import HandEVRecord, RangeFinder, category_breakdown

API_VERSION: Final[str] = "1.1.0"
TOP_HANDS_LIMIT: Final[int] = 30
OPENROUTER_URL: Final[str] = "https://openrouter.ai/api/v1/chat/completions"
FALLBACK_MODEL_NAME: Final[str] = "rule-based-solver-engine (OPENROUTER_API_KEY not configured)"

# Settings and their defaults. create_app() reads each one from the environment when it is set,
# and an explicit ``config`` argument overrides both (tests use that).
DEFAULT_CONFIG: Final[dict[str, Any]] = {
    "CORS_ORIGINS": "http://localhost:5173,http://127.0.0.1:5173",
    "ANALYZE_RATE_LIMIT": "10 per minute",
    "RATELIMIT_STORAGE_URI": "memory://",
    "RATELIMIT_ENABLED": True,
    # Number of reverse proxies in front of the app whose X-Forwarded-For header to trust (0 = none).
    # Behind a hosting proxy, set it to 1 so the rate limit counts each visitor, not the proxy.
    "PROXY_FIX_X_FOR": 0,
    "OPENROUTER_API_KEY": "",
    "OPENROUTER_MODEL": "meta-llama/llama-3.1-8b-instruct:free",
    "OPENROUTER_TIMEOUT": 15.0,
}

Json = dict[str, Any]  # a JSON object as returned by the API


@dataclass(frozen=True)
class GameParams:
    """Validated game-state parameters shared by the solver endpoints."""
    pot: float
    bet_size: float
    fold_equity: float
    opponent_model: OpponentModel


@dataclass(frozen=True)
class Services:
    """Everything a request needs, built once per app and stored in ``app.extensions``."""
    db: WinRateDB
    calling_model: CallingRangeModel
    range_finder: RangeFinder


@dataclass(frozen=True)
class HandResult:
    """One evaluated hand: what it is, its equity source, its EV, and where raising pays."""
    hand: Hand
    canonical: CanonicalHand
    stats: HandStats
    ev: EVResult
    zones: list[tuple[float, float]]


api = Blueprint("api", __name__)
analysis = Blueprint("analysis", __name__)  # separate so the rate limit applies to it alone


# --------------------------------------------------------------------------------------------
# Application factory
# --------------------------------------------------------------------------------------------
def create_app(
    *,
    db: WinRateDB | None = None,
    calling_model: CallingRangeModel | None = None,
    config: Mapping[str, Any] | None = None,
) -> Flask:
    """Build the Flask app and its services.

    Args:
        db: A loaded win-rate database. Defaults to loading backend/data/winrates.json.
        calling_model: The calling-range model. Defaults to building one (about 60 ms).
        config: Settings that override DEFAULT_CONFIG and the environment. ``TESTING=True``
            also turns the rate limiter off and ignores any OPENROUTER_API_KEY from the
            environment (so a test can never call the real service), unless the config sets
            ``RATELIMIT_ENABLED`` / ``OPENROUTER_API_KEY`` explicitly.

    Raises:
        DatabaseError: If the default database file is missing or invalid (fail fast at start-up).
        ValueError: If a numeric setting in the environment is not a number.
    """
    app = Flask(__name__)
    app.config.update(DEFAULT_CONFIG)
    app.config.update(_settings_from_env())
    overrides = dict(config or {})
    if overrides.get("TESTING"):
        overrides.setdefault("RATELIMIT_ENABLED", False)
        overrides.setdefault("OPENROUTER_API_KEY", "")
    app.config.update(overrides)

    if int(app.config["PROXY_FIX_X_FOR"]) > 0:
        app.wsgi_app = ProxyFix(app.wsgi_app, x_for=int(app.config["PROXY_FIX_X_FOR"]))  # type: ignore[method-assign]

    if db is None:
        db = WinRateDB(DEFAULT_DB_PATH)
    if calling_model is None:
        calling_model = CallingRangeModel()
    app.extensions["lieng"] = Services(db, calling_model, RangeFinder(db, calling_model))

    origins = [o.strip() for o in str(app.config["CORS_ORIGINS"]).split(",") if o.strip()]
    CORS(app, resources={r"/api/*": {"origins": origins}, r"/": {"origins": origins}, r"/health": {"origins": origins}})

    limiter = Limiter(
        get_remote_address,
        app=app,
        storage_uri=app.config["RATELIMIT_STORAGE_URI"],
        enabled=bool(app.config["RATELIMIT_ENABLED"]),
        headers_enabled=True,  # Retry-After and X-RateLimit-* headers tell clients when to retry
    )
    limiter.limit(lambda: str(current_app.config["ANALYZE_RATE_LIMIT"]))(analysis)

    app.register_blueprint(api)
    app.register_blueprint(analysis)
    _register_error_handlers(app)
    return app


def _settings_from_env() -> dict[str, Any]:
    """Read every DEFAULT_CONFIG key that is set in the environment, converted to its type."""
    settings: dict[str, Any] = {}
    for key, default in DEFAULT_CONFIG.items():
        raw = os.environ.get(key)
        if raw is None:
            continue
        if isinstance(default, bool):
            settings[key] = raw.strip().lower() in {"1", "true", "yes", "on"}
        elif isinstance(default, int | float):
            try:
                settings[key] = type(default)(raw)
            except ValueError as err:
                raise ValueError(f"Environment variable {key} must be a number, got {raw!r}.") from err
        else:
            settings[key] = raw
    return settings


def _services() -> Services:
    services: Services = current_app.extensions["lieng"]
    return services


# --------------------------------------------------------------------------------------------
# Errors: one JSON shape everywhere
# --------------------------------------------------------------------------------------------
_HTTP_CODES: Final[dict[int, str]] = {
    400: "bad_request",
    404: "not_found",
    405: "method_not_allowed",
    429: "rate_limited",
}


def _error(message: str, code: str, status: int) -> tuple[Response, int]:
    return jsonify({"error": message, "code": code}), status


def _register_error_handlers(app: Flask) -> None:
    @app.errorhandler(InvalidGameParamsError)
    def handle_invalid_params(err: InvalidGameParamsError) -> tuple[Response, int]:
        return _error(str(err), "invalid_params", 400)

    @app.errorhandler(InvalidCardError)
    @app.errorhandler(InvalidHandSizeError)
    def handle_invalid_hand(err: Exception) -> tuple[Response, int]:
        return _error(str(err), "invalid_hand", 400)

    @app.errorhandler(HTTPException)
    def handle_http_error(err: HTTPException) -> tuple[Response, int]:
        status = err.code or 500
        message = err.description or err.name
        if status == 429:
            message = f"Too many analysis requests (limit: {message}). Wait a moment, then try again."
        return _error(message, _HTTP_CODES.get(status, "http_error"), status)

    @app.errorhandler(Exception)
    def handle_unexpected(err: Exception) -> tuple[Response, int]:
        # Log the details for the operator; never send internals to the client.
        app.logger.exception("Unhandled error on %s %s", request.method, request.path)
        return _error("Internal server error.", "internal_error", 500)


# --------------------------------------------------------------------------------------------
# Request parsing
# --------------------------------------------------------------------------------------------
def _request_body() -> Json:
    """The JSON body as a dict. No body means "use the defaults"; anything else must be a JSON object."""
    data = request.get_json(silent=True)
    if data is None:
        if request.get_data():
            raise InvalidGameParamsError("The request body must be valid JSON (Content-Type: application/json).")
        return {}
    if not isinstance(data, dict):
        raise InvalidGameParamsError("The request body must be a JSON object.")
    return data


def _number(data: Json, name: str, default: float, *aliases: str) -> float:
    """Read a finite number (int, float or numeric string), falling back to ``default``."""
    value: Any = default
    for key in (name, *aliases):
        if key in data:
            value = data[key]
            break
    if isinstance(value, bool) or not isinstance(value, int | float | str):
        raise InvalidGameParamsError(f"{name} must be a number.")
    try:
        number = float(value)
    except ValueError as err:
        raise InvalidGameParamsError(f"{name} must be a number, got {value!r}.") from err
    if not math.isfinite(number):
        raise InvalidGameParamsError(f"{name} must be a finite number, got {value!r}.")
    return number


def _parse_game_params(data: Json) -> GameParams:
    """Parse and validate pot, bet size, fold equity, and opponent model from a request body.

    Missing fields take the documented defaults; ``bet`` is still accepted for ``bet_size``.

    Raises:
        InvalidGameParamsError: If any parameter is not a valid value or out of bounds.
    """
    pot = _number(data, "pot", DEFAULT_POT)
    bet_size = _number(data, "bet_size", DEFAULT_BET_SIZE, "bet")
    fold_equity = _number(data, "fold_equity", DEFAULT_FOLD_EQUITY)

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


def _parse_hand(data: Json, *, required: bool) -> Hand | None:
    """Parse the optional ``hand`` field ("As Kh Qd").

    Raises:
        InvalidGameParamsError: If the field is missing but required, or is not a string.
        InvalidCardError / InvalidHandSizeError: If the text is not a valid hand (→ invalid_hand).
    """
    value = data.get("hand")
    if value is None or (isinstance(value, str) and not value.strip()):
        if required:
            raise InvalidGameParamsError("Field 'hand' is required.")
        return None
    if not isinstance(value, str):
        raise InvalidGameParamsError("Field 'hand' must be a string such as 'As Kh Qd'.")
    return Hand.from_str(value.strip())


# --------------------------------------------------------------------------------------------
# Computation shared by the endpoints
# --------------------------------------------------------------------------------------------
def _equity_function(
    services: Services, canonical_id: str, random_equity: float, model: OpponentModel
) -> Callable[[float], float]:
    """Map a fold frequency to Hero's equity when called, under the chosen opponent model."""
    if model is OpponentModel.RANGE:
        return lambda f: services.calling_model.equity(canonical_id, f)
    return lambda f: random_equity


def _evaluate_hand(services: Services, hand: Hand, params: GameParams) -> HandResult:
    """Evaluate one hand: EV at the given fold rate and the zones where raising is +EV."""
    canonical = to_canonical(hand.cards)
    stats = services.db.get(canonical.canonical_id)
    equity_at = _equity_function(services, canonical.canonical_id, stats.equity, params.opponent_model)
    ev_res = evaluate_action(params.pot, params.bet_size, params.fold_equity, equity_at(params.fold_equity))
    zones = profitable_fold_zones(params.pot, params.bet_size, equity_at)
    return HandResult(hand, canonical, stats, ev_res, zones)


def _decision(is_profitable: bool) -> str:
    return "RAISE" if is_profitable else "CHECK/FOLD"


def _hand_payload(result: HandResult, model: OpponentModel) -> Json:
    """The hand-evaluation fields, identical in /api/solve and /api/evaluate.

    break_even_fold_equity: exact fold frequency where EV = 0 (random model only; under RANGE,
        EV is not monotonic in fold equity, so no single break-even point exists).
    profitable_from_fold_equity: first 1%-grid fold frequency from which raising stays +EV.
        The last zone always ends at 1.0, because EV there equals the pot.
    """
    return {
        "hand": str(result.hand),
        "score_name": str(result.hand.score),
        "category": result.stats.category.name,
        "category_name": result.stats.category.display_name,
        "canonical_id": result.canonical.canonical_id,
        "showdown_equity": result.ev.win_rate_when_called,
        "equity_vs_random": result.stats.equity,
        "ev": result.ev.ev,
        "break_even_fold_equity": result.ev.break_even_fold_equity if model is OpponentModel.RANDOM else None,
        "profitable_from_fold_equity": result.zones[-1][0],
        "profitable_fold_zones": [[start, end] for start, end in result.zones],
        "is_profitable": result.ev.is_profitable,
        "decision": _decision(result.ev.is_profitable),
    }


def _solve_range(services: Services, params: GameParams) -> tuple[list[HandEVRecord], Json]:
    """Score all 455 classes; return the records (best first) and the summary payload."""
    records = services.range_finder.solve_range(params.pot, params.bet_size, params.fold_equity, params.opponent_model)
    profitable = [r for r in records if r.is_raise_profitable]
    summary: Json = {
        "pot": params.pot,
        "bet_size": params.bet_size,
        "fold_equity": params.fold_equity,
        "opponent_model": params.opponent_model.value,
        "final_pot": final_pot(params.pot, params.bet_size),
        "pure_bluff_break_even_fold_equity": calculate_break_even_fold_equity(params.pot, params.bet_size, 0.0),
        "total_canonical_classes": len(records),
        "profitable_classes": len(profitable),
        "total_combinations": TOTAL_COMBINATIONS,
        "profitable_combinations": sum(r.multiplicity for r in profitable),
        "range_coverage_percent": services.range_finder.calculate_range_coverage(profitable),
        "highest_ev_hand": records[0].canonical_id if records else None,
        "highest_ev_value": records[0].ev if records else None,
        "threshold_hand": profitable[-1].canonical_id if profitable else None,
        "threshold_ev_value": profitable[-1].ev if profitable else None,
        "category_breakdown": [
            {
                "category": row.category.name,
                "classes": row.classes,
                "combos": row.combos,
                "profitable_combos": row.profitable_combos,
            }
            for row in category_breakdown(records)
        ],
    }
    return records, summary


def _top_hands_payload(records: Sequence[HandEVRecord]) -> list[Json]:
    """The best hands by EV, in the same shape for /api/solve and /api/range."""
    return [
        {
            "canonical_id": r.canonical_id,
            "category": r.category.name,
            "showdown_equity": r.equity,
            "ev": r.ev,
            "multiplicity": r.multiplicity,
            "is_profitable": r.is_raise_profitable,
            "decision": _decision(r.is_raise_profitable),
        }
        for r in records[:TOP_HANDS_LIMIT]
    ]


# --------------------------------------------------------------------------------------------
# Endpoints
# --------------------------------------------------------------------------------------------
@api.get("/")
def root() -> Response:
    """Service metadata."""
    return jsonify({
        "service": "Lieng Stealer API",
        "status": "online",
        "endpoints": ["/health", "/api/solve", "/api/evaluate", "/api/range", "/api/analyze"],
    })


@api.get("/health")
def health_check() -> Response:
    """System status and database stats."""
    db = _services().db
    return jsonify({
        "status": "healthy",
        "database_loaded": db.is_loaded,
        "classes_loaded": len(db),
        "version": API_VERSION,
    })


@api.post("/api/solve")
def solve_api() -> Response:
    """Rank all 455 hands and, if ``hand`` is given, evaluate that hand too.

    JSON body (all optional): pot (> 0), bet_size (> 0), fold_equity in [0, 1],
    opponent_model ('random' default, or 'range'), hand (e.g. 'As Kh Qd').
    """
    services = _services()
    data = _request_body()
    params = _parse_game_params(data)
    hand = _parse_hand(data, required=False)

    hand_evaluation = _hand_payload(_evaluate_hand(services, hand, params), params.opponent_model) if hand else None
    records, summary = _solve_range(services, params)
    return jsonify({
        "summary": summary,
        "hand_evaluation": hand_evaluation,
        "top_hands": _top_hands_payload(records),
    })


@api.post("/api/evaluate")
def evaluate_api() -> Response:
    """Evaluate a single 3-card hand (``hand`` required) against the game parameters."""
    services = _services()
    data = _request_body()
    params = _parse_game_params(data)
    hand = _parse_hand(data, required=True)
    assert hand is not None  # required=True never returns None

    return jsonify({
        "pot": params.pot,
        "bet_size": params.bet_size,
        "fold_equity": params.fold_equity,
        "opponent_model": params.opponent_model.value,
        **_hand_payload(_evaluate_hand(services, hand, params), params.opponent_model),
    })


@api.post("/api/range")
def range_api() -> Response:
    """The range summary and the best hands, without a specific hand."""
    services = _services()
    params = _parse_game_params(_request_body())
    records, summary = _solve_range(services, params)
    return jsonify({**summary, "top_hands": _top_hands_payload(records)})


@analysis.post("/api/analyze")
def analyze_api() -> Response | tuple[Response, int]:
    """Strategic commentary for the same inputs as /api/solve.

    The server recomputes every number itself; only validated values (numbers and the parsed
    hand) reach the prompt. Without OPENROUTER_API_KEY a rule-based answer is returned instead.
    """
    services = _services()
    data = _request_body()
    params = _parse_game_params(data)
    hand = _parse_hand(data, required=False)
    result = _evaluate_hand(services, hand, params) if hand else None
    _, summary = _solve_range(services, params)
    coverage = float(summary["range_coverage_percent"])

    api_key = str(current_app.config["OPENROUTER_API_KEY"])
    if not api_key:
        return jsonify({"advice": _fallback_advice(params, coverage, result), "model": FALLBACK_MODEL_NAME})

    model = str(current_app.config["OPENROUTER_MODEL"])
    try:
        resp = requests.post(
            OPENROUTER_URL,
            headers={
                "Authorization": f"Bearer {api_key}",
                "Content-Type": "application/json",
                "HTTP-Referer": "https://github.com/lieng-stealer",
                "X-Title": "Lieng Stealer Solver",
            },
            json={
                "model": model,
                "messages": [
                    {"role": "system", "content": "You are a professional game theory analyst specializing in Vietnamese card games like Liêng."},
                    {"role": "user", "content": _build_prompt(params, coverage, result)},
                ],
                "temperature": 0.7,
                "max_tokens": 500,
            },
            timeout=float(current_app.config["OPENROUTER_TIMEOUT"]),
        )
    except requests.RequestException:
        current_app.logger.exception("OpenRouter request failed")
        return _error("Could not reach the AI analysis service.", "upstream_error", 502)

    if resp.status_code != 200:
        current_app.logger.warning("OpenRouter returned %s: %.500s", resp.status_code, resp.text)
        return _error(f"The AI analysis service returned status {resp.status_code}.", "upstream_error", 502)
    try:
        advice = resp.json()["choices"][0]["message"]["content"]
        if not isinstance(advice, str):
            raise TypeError("content is not a string")
    except (ValueError, KeyError, IndexError, TypeError):
        current_app.logger.exception("Unexpected OpenRouter response: %.500s", resp.text)
        return _error("The AI analysis service sent an unexpected response.", "upstream_error", 502)
    return jsonify({"advice": advice, "model": model})


def _model_line(params: GameParams) -> str:
    if params.opponent_model is OpponentModel.RANGE:
        return f"folds their weakest hands (calls only with the top {(1 - params.fold_equity) * 100:.0f}%)"
    return "folds at random, regardless of hand strength"


def _build_prompt(params: GameParams, coverage: float, result: HandResult | None) -> str:
    """The LLM prompt, built only from server-computed values."""
    prompt = (
        f"You are a World-Class Game Theory Expert and High-Stakes Vietnamese Liêng Solver.\n"
        f"Analyze this decision spot with precision and strategic depth in Vietnamese:\n\n"
        f"- Current Pot: {params.pot:,.0f} VND\n"
        f"- Bet / Raise Size: {params.bet_size:,.0f} VND\n"
        f"- Opponent Fold Equity: {params.fold_equity * 100:.1f}%\n"
        f"- Opponent Model: {_model_line(params)}\n"
        f"- Total Range Coverage (Hands with EV > 0): {coverage}%\n"
    )
    if result is not None:
        prompt += (
            f"- Hero's Hand: {result.hand} ({result.hand.score})\n"
            f"- Showdown Equity: {result.ev.win_rate_when_called * 100:.1f}%\n"
            f"- Calculated EV: {result.ev.ev:+,.0f} VND\n"
            f"- Solver Decision: {_decision(result.ev.is_profitable)}\n"
        )
    else:
        prompt += "- Hero's Hand: None (General Range Analysis)\n"
    return prompt + (
        "\nProvide a structured breakdown:\n"
        "1. [Quyết định Toán học & EV]: Phân tích EV, Fold Equity và ngưỡng hòa vốn.\n"
        "2. [Chiến thuật Bluff & Giá trị]: Hero có nên Tố (Raise)/Tất tay hay Check/Bỏ bài? Giải thích tâm lý đối thủ.\n"
        "3. [Lời khuyên chiến thuật]: Nhận xét ngắn gọn về độ rủi ro và cách khai thác đối thủ."
    )


def _fallback_advice(params: GameParams, coverage: float, result: HandResult | None) -> str:
    """Rule-based commentary (Vietnamese) used when no OpenRouter key is configured."""
    pot, bet_size, fold_equity = params.pot, params.bet_size, params.fold_equity
    bluff_break_even = calculate_break_even_fold_equity(pot, bet_size, 0.0)
    advice = (
        f"**[Phân Tích Chiến Thuật Hệ Thống (Offline Solver)]**\n\n"
        f"1. **Quyết định Toán học:** Với Pot = {pot:,.0f}, Cược = {bet_size:,.0f}, và Fold Equity = {fold_equity*100:.1f}%, "
        f"ngưỡng hòa vốn cược hù (bluff) là {bluff_break_even*100:.1f}%. "
        f"Khoảng bài có lãi (EV > 0) chiếm **{coverage}%** toàn bộ thế bài có thể có. "
        + ("Giả định đối thủ bỏ những bài yếu nhất, nên khi bị theo, Hero đối đầu với nhóm bài mạnh hơn.\n\n"
           if params.opponent_model is OpponentModel.RANGE
           else "Giả định đối thủ bỏ bài ngẫu nhiên, không phụ thuộc độ mạnh của bài.\n\n")
        + "2. **Hành động Khuyến nghị:** "
    )
    if result is None:
        return advice + (
            f"Với tần suất đối thủ bỏ bài {fold_equity*100:.1f}%, hãy ưu tiên nâng cược với các nhóm bài Sáp, Liêng, Đĩ "
            f"và các tổ hợp điểm cao (> 7 điểm). Cẩn trọng cược hù khi đối thủ có xu hướng theo cược dính."
        )
    ev = result.ev.ev
    return advice + (
        f"Hero cầm **{result.hand}** ({result.hand.score}) "
        f"với xác suất thắng đối đầu {result.ev.win_rate_when_called*100:.1f}%. "
        f"Kỳ vọng thu nhập (EV) đạt **{ev:+,.0f} VND**. "
        f"Khuyến nghị tối ưu: **{_decision(result.ev.is_profitable)}**.\n\n"
        f"3. **Nhận định chiến thuật:** "
        + ("Bài có EV dương rõ rệt nhờ cả showdown equity lẫn fold equity. Tố lớn để tối đa hóa lợi nhuận." if ev > 0
           else "EV âm. Showdown equity quá thấp và đối thủ ít bỏ bài. Không nên mạo hiểm, hãy Bỏ bài (Fold) hoặc Theo nhẹ nếu có thể.")
    )


app = create_app()


if __name__ == "__main__":
    # Listen on this machine only unless HOST says otherwise (e.g. HOST=0.0.0.0 to share on a LAN).
    app.run(host=os.environ.get("HOST", "127.0.0.1"), port=int(os.environ.get("PORT", 5000)), debug=False)
