import { StrictMode } from "react";
import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { afterEach, beforeEach, describe, expect, test, vi } from "vitest";
import App from "./App.jsx";

// A trimmed /api/solve response for the default inputs (As Kh Qd, range model).
const SOLVE_OK = {
  summary: {
    pot: 100000,
    bet_size: 50000,
    fold_equity: 0.35,
    opponent_model: "range",
    range_coverage_percent: 100.0,
    profitable_combinations: 22100,
    pure_bluff_break_even_fold_equity: 0.3333,
    category_breakdown: [
      { category: "SAP", classes: 13, combos: 52, profitable_combos: 52 },
      { category: "LIENG", classes: 12, combos: 768, profitable_combos: 768 },
      { category: "DI", classes: 6, combos: 144, profitable_combos: 144 },
      { category: "DIEM", classes: 424, combos: 21136, profitable_combos: 21136 },
    ],
  },
  hand_evaluation: {
    hand: "As Kh Qd",
    score_name: "Liêng Q-K-A",
    canonical_id: "Q-K-A",
    showdown_equity: 0.9952,
    equity_vs_random: 0.9969,
    ev: 131876.0,
    profitable_fold_zones: [[0.0, 1.0]],
    decision: "RAISE",
  },
  top_hands: [
    { canonical_id: "A-A-A", category: "SAP", showdown_equity: 1.0, ev: 132500.0, multiplicity: 4, is_profitable: true, decision: "RAISE" },
  ],
};
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
    expect(await screen.findByRole("heading", { name: "Raise / all-in" })).toBeInTheDocument();
    expect(screen.getAllByText(/\+131,876/).length).toBeGreaterThan(0);
  });

  test("sends the selected caller-range percentage to the solver", async () => {
    const calls = mockFetch({ "/api/solve": reply(200, SOLVE_OK), "/api/analyze": reply(200, ANALYZE_OK) });
    render(<App />);
    await screen.findByRole("heading", { name: "Raise / all-in" });

    const slider = screen.getByRole("slider", { name: "Estimated calling range" });
    fireEvent.change(slider, { target: { value: "31" } });
    fireEvent.click(screen.getByRole("button", { name: "Run solver" }));

    await waitFor(() => {
      const solveCalls = calls.filter((call) => call.path === "/api/solve");
      expect(solveCalls.at(-1).body.call_range_percent).toBe(31);
    });
  });

  test("the top-hands table reads showdown_equity", async () => {
    mockFetch({ "/api/solve": reply(200, SOLVE_OK), "/api/analyze": reply(200, ANALYZE_OK) });
    render(<App />);
    const row = (await screen.findByText("A-A-A")).closest("tr");
    expect(row).toHaveTextContent("100.0%");
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
    await screen.findByRole("heading", { name: "Raise / all-in" });

    await user.click(screen.getByRole("button", { name: "Run solver" }));
    expect(await screen.findByRole("alert")).toHaveTextContent("Check your hand: Invalid card 'Xh': Invalid rank 'X'.");
    expect(screen.queryByRole("heading", { name: "Raise / all-in" })).not.toBeInTheDocument();
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
    await screen.findByRole("heading", { name: "Raise / all-in" });

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
      "call_range_percent",
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
    await screen.findByRole("heading", { name: "Raise / all-in" });
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
    expect(await screen.findByRole("heading", { name: "Raise / all-in" })).toBeInTheDocument();
    const solves = calls.filter((c) => c.path === "/api/solve");
    expect(solves).toHaveLength(2);
    expect(solves[0].signal.aborted).toBe(true);
    expect(solves[1].signal.aborted).toBe(false);
  });
});
