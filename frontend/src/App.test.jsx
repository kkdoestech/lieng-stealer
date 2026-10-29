import { StrictMode } from "react";
import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { afterEach, beforeEach, describe, expect, test, vi } from "vitest";
import App from "./App.jsx";
import solveContract from "./solve-contract.json";

// A trimmed /api/solve response for the default inputs (As Kh Qd, range model). The advice block is
// the Q-K-A all-in from the shared contract (solve-contract.json) and the backend's pinned numbers.
const ALL_IN_ADVICE = {
  action: "ALL_IN",
  kind: "VALUE",
  reason: "ALL_IN_VALUE",
  amount: 100000.0,
  ev: 164064.0,
  ev_ratio: 1.64064,
  equity_when_called: 0.9952,
  win_rate_defined: true,
  robust: true,
  why: { fold_component: 35000.0, call_component: 129064.0, net: 164064.0 },
  ladder: [
    { action: "SMALL_BET", amount: 33000.0, ev: 120932.08, ev_ratio: 1.2093208, worst_ev_ratio: 1.1763872, robust: true, eligible: true, blocked_by: null },
    { action: "LARGE_BET", amount: 75000.0, ev: 147970.0, ev_ratio: 1.4797, worst_ev_ratio: 1.4048, robust: true, eligible: true, blocked_by: null },
    { action: "ALL_IN", amount: 100000.0, ev: 164064.0, ev_ratio: 1.64064, worst_ev_ratio: 1.54076, robust: true, eligible: true, blocked_by: null },
  ],
};

// Ks Qh 3d: a bluff financed by folds, so the policy caps it at the small rung.
const SMALL_BLUFF_ADVICE = {
  action: "SMALL_BET",
  kind: "BLUFF",
  reason: "SMALL_BLUFF",
  amount: 33000.0,
  ev: 14715.32,
  ev_ratio: 0.1471532,
  equity_when_called: 0.0108,
  win_rate_defined: true,
  robust: true,
  why: { fold_component: 35000.0, call_component: -20284.68, net: 14715.32 },
  ladder: [
    { action: "SMALL_BET", amount: 33000.0, ev: 14715.32, ev_ratio: 0.1471532, worst_ev_ratio: 0.1471532, robust: true, eligible: true, blocked_by: null },
    { action: "LARGE_BET", amount: 75000.0, ev: -11995.0, ev_ratio: -0.11995, worst_ev_ratio: -0.11995, robust: false, eligible: false, blocked_by: "EV_BELOW_FLOOR" },
    { action: "ALL_IN", amount: 100000.0, ev: -27894.0, ev_ratio: -0.27894, worst_ev_ratio: -0.27894, robust: false, eligible: false, blocked_by: "EV_BELOW_FLOOR" },
  ],
};

// 2s 3h 5d: the small bet pays at the assumed fold rate and collapses one cell lower.
const FRAGILE_ADVICE = {
  action: "CHECK",
  kind: "BLUFF",
  reason: "CHECK_ASSUMPTION_FRAGILE",
  amount: 0.0,
  ev: 0.0,
  ev_ratio: 0.0,
  equity_when_called: 0.0,
  win_rate_defined: true,
  robust: true,
  why: { fold_component: 0.0, call_component: 0.0, net: 0.0 },
  ladder: [
    { action: "SMALL_BET", amount: 33000.0, ev: 13550.0, ev_ratio: 0.1355, worst_ev_ratio: 0.0025, robust: true, eligible: false, blocked_by: "EV_BELOW_FLOOR" },
    { action: "LARGE_BET", amount: 75000.0, ev: -13750.0, ev_ratio: -0.1375, worst_ev_ratio: -0.1375, robust: false, eligible: false, blocked_by: "EV_BELOW_FLOOR" },
    { action: "ALL_IN", amount: 100000.0, ev: -30000.0, ev_ratio: -0.3, worst_ev_ratio: -0.3, robust: false, eligible: false, blocked_by: "EV_BELOW_FLOOR" },
  ],
};

// Fold rate 1.0 under the range model: the calling range is empty, so there is no win rate to show.
const NO_CALLERS_ADVICE = {
  action: "SMALL_BET",
  kind: "BLUFF",
  reason: "SMALL_BLUFF",
  amount: 33000.0,
  ev: 100000.0,
  ev_ratio: 1.0,
  equity_when_called: 0.0,
  win_rate_defined: false,
  robust: true,
  why: { fold_component: 100000.0, call_component: 0.0, net: 100000.0 },
  ladder: [
    { action: "SMALL_BET", amount: 33000.0, ev: 100000.0, ev_ratio: 1.0, worst_ev_ratio: 1.0, robust: true, eligible: true, blocked_by: null },
    { action: "LARGE_BET", amount: 75000.0, ev: 100000.0, ev_ratio: 1.0, worst_ev_ratio: 1.0, robust: true, eligible: false, blocked_by: "BLUFF_TOO_SMALL_ONLY" },
    { action: "ALL_IN", amount: 100000.0, ev: 100000.0, ev_ratio: 1.0, worst_ev_ratio: 1.0, robust: true, eligible: false, blocked_by: "BLUFF_TOO_SMALL_ONLY" },
  ],
};

// A check card's ladder: no rung clears, and the small rung is the one its sentence quotes.
const CHECK_ONLY = { action: "CHECK", amount: 0.0, ev: 0.0, ev_ratio: 0.0, ladder: FRAGILE_ADVICE.ladder };

const SUMMARY = {
  pot: 100000,
  bet_size: 50000,
  fold_equity: 0.35,
  opponent_model: "range",
  call_range_percent: 65.0,
  range_coverage_percent: 100.0,
  profitable_combinations: 22100,
  pure_bluff_break_even_fold_equity: 0.3333,
  action_counts: { CHECK: 128, SMALL_BET: 175, LARGE_BET: 98, ALL_IN: 54 },
  bet_recommended_percent: 71.62,
  bet_ladder: [33000.0, 75000.0, 100000.0],
  sizing: {
    small_fraction: 0.33,
    large_fraction: 0.75,
    all_in_fraction: 1.0,
    min_edge_ratio: 0.05,
    all_in_min_equity: 0.85,
    large_min_equity: 0.5,
    value_equity_floor: 0.55,
    bluff_equity_ceiling: 0.45,
    fold_step: 0.1,
    all_in_size: 100000.0,
  },
  category_breakdown: [
    { category: "SAP", classes: 13, combos: 52, profitable_combos: 52 },
    { category: "LIENG", classes: 12, combos: 768, profitable_combos: 768 },
    { category: "DI", classes: 6, combos: 144, profitable_combos: 144 },
    { category: "DIEM", classes: 424, combos: 21136, profitable_combos: 21136 },
  ],
};

const HAND = {
  hand: "As Kh Qd",
  score_name: "Liêng Q-K-A",
  canonical_id: "Q-K-A",
  showdown_equity: 0.9952,
  equity_vs_random: 0.99693335,
  ev: 131876.0,
  call_range_percent: 65.0,
  sensitivity: {
    fold_equity_range: [0.25, 0.45],
    call_range_percent_range: [55.0, 75.0],
    central_equity_when_called: 0.9952,
    status: "ROBUST_BET",
    scenarios: [],
  },
  profitable_fold_zones: [[0.0, 1.0]],
  advice: ALL_IN_ADVICE,
};

const TOP_HANDS = [
  { canonical_id: "A-A-A", category: "SAP", showdown_equity: 1.0, ev: 132500.0, multiplicity: 4, action: "ALL_IN", kind: "VALUE", amount: 100000.0 },
];

const solveWith = (handOverrides = {}, summaryOverrides = {}) => ({
  summary: { ...SUMMARY, ...summaryOverrides },
  hand_evaluation: { ...HAND, ...handOverrides },
  top_hands: TOP_HANDS,
});

const SOLVE_OK = solveWith();

// The same response when the hand field is empty: the range answers, no verdict card.
const SOLVE_OK_NO_HAND = { ...SOLVE_OK, hand_evaluation: null };

const ANALYZE_OK = { advice: "Tố lớn.", model: "rule-based-solver-engine (OPENROUTER_API_KEY not configured)" };

const reply = (status, body) => ({ ok: status < 400, status, json: async () => body });

// Answer each POST by path; `routes[path]` is a reply, or a function (call index) => reply/Promise.
function mockFetch(routes) {
  const calls = [];
  const fetchMock = vi.fn((url, options) => {
    const path = new URL(url, "http://localhost").pathname;
    calls.push({ path, body: JSON.parse(options.body), signal: options.signal });
    const route = routes[path];
    const count = calls.filter((c) => c.path === path).length - 1;
    const result = typeof route === "function" ? route(count) : route;
    return result instanceof Error ? Promise.reject(result) : Promise.resolve(result);
  });
  vi.stubGlobal("fetch", fetchMock);
  return calls;
}

beforeEach(() => {
  localStorage.clear();
});

afterEach(() => {
  vi.unstubAllGlobals();
});

describe("App", () => {
  test("renders the verdict and figures from /api/solve", async () => {
    mockFetch({ "/api/solve": reply(200, SOLVE_OK), "/api/analyze": reply(200, ANALYZE_OK) });
    render(<App />);
    expect(await screen.findByRole("heading", { name: "All in" })).toBeInTheDocument();
    expect(screen.getAllByText(/\+164,064/).length).toBeGreaterThan(0);
    expect(
      screen.getByText(
        "You win about 99.5% when called, so the all-in is worth the risk even if they fold 10% less than you think."
      )
    ).toBeInTheDocument();
    expect(
      screen.getByText(
        "We recommend a bet only when it earns at least 5% of the pot and still earns it if the opponent folds 10% less than you think."
      )
    ).toBeInTheDocument();
  });

  test("the small-bluff card explains where the money comes from, in English and Vietnamese", async () => {
    const user = userEvent.setup();
    mockFetch({
      "/api/solve": reply(200, solveWith({
        hand: "Ks Qh 3d",
        score_name: "Điểm 3",
        canonical_id: "K-Q-3",
        showdown_equity: 0.0108,
        equity_vs_random: 0.4021,
        ev: 3904.0,
        profitable_fold_zones: [[0.35, 1.0]],
        advice: SMALL_BLUFF_ADVICE,
      })),
      "/api/analyze": reply(200, ANALYZE_OK),
    });
    render(<App />);

    expect(await screen.findByRole("heading", { name: "Small bet" })).toBeInTheDocument();
    expect(
      screen.getByText(
        "Positive EV (+14,715) but a low win rate (1.1%). The money comes from folds, so use the smallest bet that still buys the fold."
      )
    ).toBeInTheDocument();

    await user.click(screen.getByRole("button", { name: "Switch language to Vietnamese" }));
    expect(
      screen.getByText(
        "EV dương (+14.715) nhưng tỷ lệ thắng thấp (1.1%). Lãi đến từ việc đối thủ bỏ bài, nên chỉ cần cược mức nhỏ nhất đủ để họ bỏ."
      )
    ).toBeInTheDocument();
  });

  test("the check card quotes the fold read where the small bet stops paying", async () => {
    mockFetch({
      "/api/solve": reply(200, solveWith({
        hand: "2s 3h 5d",
        score_name: "Điểm 0",
        canonical_id: "5-3-2",
        showdown_equity: 0.0,
        equity_vs_random: 0.2361,
        ev: 2500.0,
        profitable_fold_zones: [[0.35, 1.0]],
        advice: FRAGILE_ADVICE,
      })),
      "/api/analyze": reply(200, ANALYZE_OK),
    });
    render(<App />);

    expect(await screen.findByRole("heading", { name: "Check" })).toBeInTheDocument();
    expect(
      screen.getByText(
        "Betting earns +13,550 if they fold 35%, but only +250 if they fold 25%. One bad read from break-even."
      )
    ).toBeInTheDocument();
    // A check has no kind chip: the sentence, not a label, is the explanation.
    expect(screen.getByRole("heading", { name: "Check" }).closest(".verdict-card")).not.toHaveTextContent("Bluff");
  });

  test.each([
    [
      "LARGE_VALUE",
      { action: "LARGE_BET", kind: "VALUE", equity_when_called: 0.62 },
      "You are ahead when called (62.0%), but not enough to risk the whole pot.",
    ],
    [
      "LARGE_THIN",
      { action: "LARGE_BET", kind: "THIN_VALUE", equity_when_called: 0.51 },
      "Only a slight favourite when called (51.0%), so keep it to a large bet.",
    ],
    [
      "SMALL_VALUE",
      { action: "SMALL_BET", kind: "VALUE", equity_when_called: 0.58 },
      "Strong enough to bet 33,000 VND for value; a bigger bet risks more than it adds.",
    ],
    [
      "SMALL_THIN",
      { action: "SMALL_BET", kind: "THIN_VALUE", equity_when_called: 0.49 },
      "Close to a coin flip when called (49.0%), so keep the pot small.",
    ],
    [
      "CHECK_NO_EDGE",
      { ...CHECK_ONLY, kind: "BLUFF", equity_when_called: 0.0 },
      "Every size loses money at this fold read (35%).",
    ],
    [
      "CHECK_EDGE_TOO_SMALL",
      { ...CHECK_ONLY, kind: "BLUFF", equity_when_called: 0.02 },
      "Betting earns only +13,550 (13.6% of pot), under the 5% we need.",
    ],
  ])("%s explains itself with the response's own numbers", async (reason, overrides, sentence) => {
    mockFetch({
      "/api/solve": reply(200, solveWith({ advice: { ...SMALL_BLUFF_ADVICE, reason, ...overrides } })),
      "/api/analyze": reply(200, ANALYZE_OK),
    });
    render(<App />);
    expect(await screen.findByText(sentence)).toBeInTheDocument();
  });

  test("a rung that does not clear is struck through with its reason", async () => {
    mockFetch({
      "/api/solve": reply(200, solveWith({ canonical_id: "K-Q-3", advice: SMALL_BLUFF_ADVICE })),
      "/api/analyze": reply(200, ANALYZE_OK),
    });
    render(<App />);
    await screen.findByRole("heading", { name: "Small bet" });

    const chosen = screen.getByText(/33,000/).closest(".ladder-rung");
    expect(chosen).toHaveClass("chosen");
    expect(chosen).toHaveTextContent("✓");
    expect(chosen).toHaveTextContent("Small bet");
    expect(chosen).not.toHaveTextContent("not worth the extra risk");

    const blocked = screen.getAllByText("not worth the extra risk").map((node) => node.closest(".ladder-rung"));
    expect(blocked).toHaveLength(2);
    expect(blocked[0]).toHaveClass("rung-blocked");
    expect(blocked[0]).toHaveTextContent("✗");
    expect(blocked[0]).toHaveTextContent("75,000");
    expect(blocked[0]).toHaveTextContent("EV -11,995");
  });

  test("the nobody-calls state hides the win rate instead of showing 0%", async () => {
    mockFetch({
      "/api/solve": reply(200, solveWith(
        { canonical_id: "Q-K-A", showdown_equity: 0.0, equity_vs_random: 0.34, ev: 100000.0, advice: NO_CALLERS_ADVICE },
        { fold_equity: 1.0, call_range_percent: 0.0 }
      )),
      "/api/analyze": reply(200, ANALYZE_OK),
    });
    render(<App />);
    await screen.findByRole("heading", { name: "Small bet" });

    // Once in the card's why-line, once in the HUD's showdown-equity figure.
    expect(screen.getAllByText(/nobody calls at this setting/)).toHaveLength(2);

    const [equityLabel] = screen.getAllByText("Showdown equity");
    const equityCard = equityLabel.closest(".hud-card");
    expect(equityCard).toHaveTextContent("nobody calls at this setting, so the win rate is undefined");
    expect(equityCard).not.toHaveTextContent("0.0%");
  });

  test("the solve body matches the shared contract with the backend", async () => {
    const calls = mockFetch({ "/api/solve": reply(200, SOLVE_OK), "/api/analyze": reply(200, ANALYZE_OK) });
    render(<App />);
    await screen.findByRole("heading", { name: "All in" });
    expect(calls[0].body).toEqual(solveContract.request);
  });

  test("the calling-range slider writes fold_equity and never sends its own field", async () => {
    const calls = mockFetch({ "/api/solve": reply(200, SOLVE_OK), "/api/analyze": reply(200, ANALYZE_OK) });
    render(<App />);
    await screen.findByRole("heading", { name: "All in" });

    const slider = screen.getByRole("slider", { name: "Estimated calling range" });
    fireEvent.change(slider, { target: { value: "30" } });
    fireEvent.click(screen.getByRole("button", { name: "Run solver" }));

    await waitFor(() => {
      const solveCalls = calls.filter((call) => call.path === "/api/solve");
      const body = solveCalls.at(-1).body;
      expect(body.fold_equity).toBeCloseTo(0.7, 10);
      expect("call_range_percent" in body).toBe(false);
    });
  });

  test("the fold slider moves the calling-range slider with it", async () => {
    mockFetch({ "/api/solve": reply(200, SOLVE_OK), "/api/analyze": reply(200, ANALYZE_OK) });
    render(<App />);
    await screen.findByRole("heading", { name: "All in" });

    expect(screen.getByRole("slider", { name: "Estimated calling range" })).toHaveValue("65");
    fireEvent.change(screen.getByRole("slider", { name: "Opponent fold frequency" }), { target: { value: "0.2" } });
    expect(screen.getByRole("slider", { name: "Estimated calling range" })).toHaveValue("80");
  });

  test("the top-hands table labels each row with its action and kind", async () => {
    mockFetch({ "/api/solve": reply(200, SOLVE_OK), "/api/analyze": reply(200, ANALYZE_OK) });
    render(<App />);
    const row = (await screen.findByText("A-A-A")).closest("tr");
    expect(row).toHaveTextContent("100.0%");
    expect(row).toHaveTextContent("All in · Value");
  });

  test("clearing the hand shows the range instead of an error", async () => {
    const user = userEvent.setup();
    const calls = mockFetch({
      "/api/solve": (n) => (n === 0 ? reply(200, SOLVE_OK) : reply(200, SOLVE_OK_NO_HAND)),
      "/api/analyze": reply(200, ANALYZE_OK),
    });
    render(<App />);
    await screen.findByRole("heading", { name: "All in" });

    await user.clear(screen.getByLabelText("Your hand (3 cards)"));
    await user.click(screen.getByRole("button", { name: "Run solver" }));

    expect(await screen.findByText("No hand entered")).toBeInTheDocument();
    expect(screen.queryByRole("alert")).not.toBeInTheDocument();
    expect(calls.filter((call) => call.path === "/api/solve").at(-1).body.hand).toBe("");
    expect(screen.getByText("A-A-A")).toBeInTheDocument();
  });

  test("the empty state counts the hands behind each action", async () => {
    const user = userEvent.setup();
    mockFetch({
      "/api/solve": (n) => (n === 0 ? reply(200, SOLVE_OK) : reply(200, SOLVE_OK_NO_HAND)),
      "/api/analyze": reply(200, ANALYZE_OK),
    });
    render(<App />);
    await screen.findByRole("heading", { name: "All in" });

    await user.clear(screen.getByLabelText("Your hand (3 cards)"));
    await user.click(screen.getByRole("button", { name: "Run solver" }));

    expect(
      await screen.findByText("54 hands go all in here, 98 bet large, 175 bet small, and 128 check.")
    ).toBeInTheDocument();
  });

  test("an invalid hand shows its message and clears the old verdict", async () => {
    const user = userEvent.setup();
    mockFetch({
      "/api/solve": (n) => (n === 0
        ? reply(200, SOLVE_OK)
        : reply(400, { error: "Invalid card 'Xh': Invalid rank 'X'.", code: "invalid_hand" })),
      "/api/analyze": reply(200, ANALYZE_OK),
    });
    render(<App />);
    await screen.findByRole("heading", { name: "All in" });

    await user.click(screen.getByRole("button", { name: "Run solver" }));
    expect(await screen.findByRole("alert")).toHaveTextContent("Check your hand: Invalid card 'Xh': Invalid rank 'X'.");
    expect(screen.queryByRole("heading", { name: "All in" })).not.toBeInTheDocument();
  });

  test.each([
    ["a network failure", new TypeError("Failed to fetch"), "Can't reach the solver"],
    ["a server error", reply(500, { error: "Internal server error.", code: "internal_error" }), "internal error"],
    ["a 5xx that did not come from the API", reply(502, {}), "Can't reach the solver"],
    ["a 404 that did not come from the API", reply(404, {}), "Can't reach the solver"],
    ["an API error that isn't about the input", reply(404, { error: "Not found.", code: "not_found" }), "internal error"],
  ])("%s shows the matching message", async (_name, result, message) => {
    mockFetch({ "/api/solve": result, "/api/analyze": reply(200, ANALYZE_OK) });
    render(<App />);
    expect(await screen.findByRole("alert")).toHaveTextContent(message);
  });

  test("the language toggle switches the text and is remembered", async () => {
    const user = userEvent.setup();
    mockFetch({ "/api/solve": reply(200, SOLVE_OK), "/api/analyze": reply(200, ANALYZE_OK) });
    render(<App />);
    await screen.findByRole("heading", { name: "All in" });

    await user.click(screen.getByRole("button", { name: "Switch language to Vietnamese" }));
    expect(screen.getByRole("button", { name: "Chạy bộ giải" })).toBeInTheDocument();
    expect(localStorage.getItem("lieng-scope-lang")).toBe("vi");
  });

  test("the pot stepper moves by 10k and stops at 1,000", async () => {
    const user = userEvent.setup();
    mockFetch({ "/api/solve": reply(200, SOLVE_OK), "/api/analyze": reply(200, ANALYZE_OK) });
    render(<App />);
    const pot = screen.getByLabelText("Current pot (VND)");
    await user.click(screen.getByRole("button", { name: "Current pot (VND) −10k" }));
    expect(pot).toHaveValue(90000);

    await user.clear(pot);
    await user.type(pot, "5000");
    await user.click(screen.getByRole("button", { name: "Current pot (VND) −10k" }));
    expect(pot).toHaveValue(1000);
  });

  test("the notes show the model the API reports", async () => {
    const user = userEvent.setup();
    mockFetch({ "/api/solve": reply(200, SOLVE_OK), "/api/analyze": reply(200, ANALYZE_OK) });
    render(<App />);
    await user.click(screen.getByRole("button", { name: /Show analysis notes/ }));
    expect(await screen.findByText(ANALYZE_OK.model)).toBeInTheDocument();
    expect(screen.getByText("Tố lớn.")).toBeInTheDocument();
  });

  test("analysis requests send only the inputs, never client-side results", async () => {
    const calls = mockFetch({ "/api/solve": reply(200, SOLVE_OK), "/api/analyze": reply(200, ANALYZE_OK) });
    render(<App />);
    await waitFor(() => expect(calls.some((c) => c.path === "/api/analyze")).toBe(true));
    const analyze = calls.find((c) => c.path === "/api/analyze");
    expect(Object.keys(analyze.body).sort()).toEqual([
      "bet_size",
      "fold_equity",
      "hand",
      "opponent_model",
      "pot",
    ]);
    expect(calls.filter((c) => c.path === "/api/solve")).toHaveLength(1);
  });

  test("a click while the analysis is still loading cancels the old run", async () => {
    const user = userEvent.setup();
    let releaseFirstAnalysis;
    const calls = mockFetch({
      "/api/solve": reply(200, SOLVE_OK),
      "/api/analyze": (n) => (n === 0
        ? new Promise((resolve) => { releaseFirstAnalysis = resolve; })
        : reply(200, { advice: "Second run", model: "m2" })),
    });
    render(<App />);
    await screen.findByRole("heading", { name: "All in" });
    await user.click(screen.getByRole("button", { name: /Show analysis notes/ }));

    // The first analysis is still pending; start a new run, then let the old answer arrive late.
    await user.click(screen.getByRole("button", { name: "Run solver" }));
    expect(await screen.findByText("Second run")).toBeInTheDocument();
    releaseFirstAnalysis(reply(200, { advice: "First run", model: "m1" }));

    await waitFor(() => expect(calls.filter((c) => c.path === "/api/analyze")[0].signal.aborted).toBe(true));
    expect(screen.queryByText("First run")).not.toBeInTheDocument();
    expect(screen.getByText("Second run")).toBeInTheDocument();
  });

  test("StrictMode's double mount aborts the duplicate first request", async () => {
    const calls = mockFetch({ "/api/solve": reply(200, SOLVE_OK), "/api/analyze": reply(200, ANALYZE_OK) });
    render(<StrictMode><App /></StrictMode>);
    expect(await screen.findByRole("heading", { name: "All in" })).toBeInTheDocument();
    const solves = calls.filter((c) => c.path === "/api/solve");
    expect(solves).toHaveLength(2);
    expect(solves[0].signal.aborted).toBe(true);
    expect(solves[1].signal.aborted).toBe(false);
  });
});
