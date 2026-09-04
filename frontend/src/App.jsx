import { useState, useEffect } from 'react';
import './App.css';

const API_BASE = import.meta.env.VITE_API_URL || "http://127.0.0.1:5000";

function formatMoney(num) {
  if (num === undefined || num === null) return "0";
  return new Intl.NumberFormat("vi-VN").format(Math.round(num));
}

export default function App() {
  const [pot, setPot] = useState(100000);
  const [betSize, setBetSize] = useState(50000);
  const [hand, setHand] = useState("As Kh Qd");
  const [foldEquity, setFoldEquity] = useState(0.35);

  const [isLoading, setIsLoading] = useState(false);
  const [isAiLoading, setIsAiLoading] = useState(false);
  const [solveData, setSolveData] = useState(null);
  const [aiAdvice, setAiAdvice] = useState("");
  const [error, setError] = useState("");

  const handleSolve = async () => {
    setIsLoading(true);
    setIsAiLoading(true);
    setError("");

    try {
      // 1. Call solve endpoint
      const solveRes = await fetch(`${API_BASE}/api/solve`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          pot: Number(pot),
          bet_size: Number(betSize),
          fold_equity: Number(foldEquity),
          hand: hand.trim(),
        }),
      });

      if (!solveRes.ok) {
        const errJson = await solveRes.json();
        throw new Error(errJson.error || `Server responded with ${solveRes.status}`);
      }

      const solveJson = await solveRes.json();
      setSolveData(solveJson);
      setIsLoading(false);

      // 2. Call analyze endpoint for strategic AI advice
      try {
        const analyzeRes = await fetch(`${API_BASE}/api/analyze`, {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({
            pot: Number(pot),
            bet_size: Number(betSize),
            fold_equity: Number(foldEquity),
            hand: hand.trim(),
            hand_evaluation: solveJson.hand_evaluation,
            range_coverage_percent: solveJson.summary?.range_coverage_percent,
          }),
        });

        if (analyzeRes.ok) {
          const analyzeJson = await analyzeRes.json();
          setAiAdvice(analyzeJson.advice || "Không có lời khuyên.");
        } else {
          setAiAdvice("Không thể kết nối AI gateway.");
        }
      } catch (aiErr) {
        setAiAdvice("Lỗi khi tải AI Commentary: " + aiErr.message);
      } finally {
        setIsAiLoading(false);
      }
    } catch (err) {
      setError("Backend offline. Ensure 'python app.py' is running on port 5000.");
      setIsLoading(false);
      setIsAiLoading(false);
    }
  };

  // Run initial solve on mount
  useEffect(() => {
    handleSolve();
  }, []);

  const handEval = solveData?.hand_evaluation;
  const summary = solveData?.summary;
  const isRaise = handEval?.decision === "RAISE";

  return (
    <div className="app-container">
      {/* Header */}
      <header className="app-header">
        <div className="brand-badge">
          <span className="dot"></span>
          <span>GAME-THEORETIC SOLVER & AI ADVISOR</span>
        </div>
        <h1 className="app-title">Liêng Stealer</h1>
        <p className="app-subtitle">
          High-performance Expected Value solver and optimal range calculator for 3-card Vietnamese Liêng.
        </p>
      </header>

      {/* Main Dashboard Grid */}
      <main className="dashboard-grid">
        {/* Left Column: Form Controls */}
        <section className="card-panel">
          <h2 className="panel-title">
            <span>⚙️</span> Game State Parameters
          </h2>

          <div className="form-group">
            <label className="form-label">Current Pot (Dead Money)</label>
            <input
              type="number"
              className="input-field"
              value={pot}
              onChange={(e) => setPot(Number(e.target.value))}
              step="10000"
              min="1000"
            />
            <div className="quick-tags">
              {[50000, 100000, 200000, 500000].map((v) => (
                <button key={v} type="button" className="tag-btn" onClick={() => setPot(v)}>
                  {v / 1000}k
                </button>
              ))}
            </div>
          </div>

          <div className="form-group">
            <label className="form-label">Bet / Raise Sizing</label>
            <input
              type="number"
              className="input-field"
              value={betSize}
              onChange={(e) => setBetSize(Number(e.target.value))}
              step="10000"
              min="1000"
            />
            <div className="quick-tags">
              <button type="button" className="tag-btn" onClick={() => setBetSize(Math.round(pot * 0.5))}>
                0.5x Pot
              </button>
              <button type="button" className="tag-btn" onClick={() => setBetSize(pot)}>
                1x Pot
              </button>
              <button type="button" className="tag-btn" onClick={() => setBetSize(pot * 2)}>
                2x Pot
              </button>
            </div>
          </div>

          <div className="form-group">
            <label className="form-label">Player Hand (3 Cards)</label>
            <input
              type="text"
              className="input-field mono"
              value={hand}
              onChange={(e) => setHand(e.target.value)}
              placeholder="e.g. As Kh Qd or 9s 10c Kd"
            />
            <div className="quick-tags">
              <button type="button" className="tag-btn" onClick={() => setHand("As Kh Qd")}>
                Liêng Q-K-A
              </button>
              <button type="button" className="tag-btn" onClick={() => setHand("7s 7h 7d")}>
                Sáp 7
              </button>
              <button type="button" className="tag-btn" onClick={() => setHand("Js Qh Kd")}>
                Liêng J-Q-K
              </button>
              <button type="button" className="tag-btn" onClick={() => setHand("9s 10h Kd")}>
                9 điểm
              </button>
              <button type="button" className="tag-btn" onClick={() => setHand("2s 3h 5d")}>
                0 điểm (Bù)
              </button>
            </div>
          </div>

          <div className="form-group">
            <div className="slider-header">
              <label className="form-label" style={{ marginBottom: 0 }}>Opponent Fold Equity</label>
              <span className="slider-val mono">{Math.round(foldEquity * 100)}%</span>
            </div>
            <input
              type="range"
              min="0"
              max="1"
              step="0.01"
              value={foldEquity}
              onChange={(e) => setFoldEquity(parseFloat(e.target.value))}
              className="range-slider"
            />
            <div className="slider-hints">
              <span>0% (Calling Station)</span>
              <span>50%</span>
              <span>100% (Tight/Fold)</span>
            </div>
          </div>

          <button
            type="button"
            className="btn-primary"
            onClick={handleSolve}
            disabled={isLoading}
          >
            {isLoading ? <span className="spinner"></span> : "⚡ Solve & Analyze"}
          </button>

          {error && (
            <div style={{ marginTop: "1rem", color: "var(--accent-rose)", fontSize: "0.85rem" }}>
              ⚠️ {error}
            </div>
          )}
        </section>

        {/* Right Column: Output Dashboards */}
        <section className="results-container">
          {/* Decision Hero Card */}
          {handEval && (
            <div className={`decision-card ${isRaise ? "raise" : "check-fold"}`}>
              <div>
                <span className="decision-label">Recommended Action</span>
                <h3 className="decision-action">
                  {isRaise ? "RAISE / ALL-IN" : "CHECK / FOLD"}
                </h3>
                <p className="decision-hand-tag">
                  {handEval.hand} • <span style={{ color: "#93c5fd" }}>{handEval.score_name}</span>
                </p>
              </div>
              <div style={{ textAlign: "right" }}>
                <span className="decision-label">Expected Value</span>
                <h3 className="decision-action" style={{ fontSize: "1.8rem" }}>
                  {handEval.ev > 0 ? "+" : ""}{formatMoney(handEval.ev)} VND
                </h3>
                <p className="metric-subtext">
                  Break-even Fold Equity: {Math.round(handEval.break_even_fold_equity * 100)}%
                </p>
              </div>
            </div>
          )}

          {/* Metrics Grid */}
          <div className="metrics-grid">
            <div className="metric-card">
              <div className="metric-label">Range Coverage</div>
              <div className="metric-value positive">
                {summary?.range_coverage_percent?.toFixed(1) || "0.0"}%
              </div>
              <div className="metric-subtext">
                {summary?.profitable_combinations?.toLocaleString()} / 22,100 hands
              </div>
            </div>

            <div className="metric-card">
              <div className="metric-label">Showdown Equity</div>
              <div className="metric-value" style={{ color: "#38bdf8" }}>
                {handEval ? `${(handEval.showdown_equity * 100).toFixed(1)}%` : "N/A"}
              </div>
              <div className="metric-subtext">vs. random 49 cards</div>
            </div>

            <div className="metric-card">
              <div className="metric-label">Pure Bluff Threshold</div>
              <div className="metric-value" style={{ color: "#fbbf24" }}>
                {summary ? `${(summary.pure_bluff_break_even_fold_equity * 100).toFixed(1)}%` : "N/A"}
              </div>
              <div className="metric-subtext">Fold Equity needed to bluff 0 pts</div>
            </div>

            <div className="metric-card">
              <div className="metric-label">Final Pot</div>
              <div className="metric-value" style={{ color: "#e2e8f0" }}>
                {formatMoney(summary?.final_pot)}
              </div>
              <div className="metric-subtext">Pot + 2x Bet</div>
            </div>
          </div>

          {/* AI Strategic Commentary Block */}
          <div className="ai-card">
            <div className="ai-header">
              <div className="ai-title">
                <span>🤖</span> AI Strategic Commentary
              </div>
              <span className="ai-badge">Llama 3.1 8B Instruct</span>
            </div>
            {isAiLoading ? (
              <div style={{ display: "flex", alignItems: "center", gap: "0.5rem", color: "var(--text-secondary)" }}>
                <span className="spinner"></span>
                <span>Generating game-theoretic breakdown via OpenRouter...</span>
              </div>
            ) : (
              <div className="ai-content">{aiAdvice || "No analysis available yet."}</div>
            )}
          </div>

          {/* Top Profitable Hands Table */}
          {solveData?.top_hands && (
            <div className="card-panel" style={{ padding: "1.25rem" }}>
              <h3 className="panel-title" style={{ fontSize: "1rem" }}>
                <span>🏆</span> Top Profitable Raising Holdings (Sample Range)
              </h3>
              <div className="table-container">
                <table className="hands-table">
                  <thead>
                    <tr>
                      <th>Canonical Class</th>
                      <th>Category</th>
                      <th>Showdown Equity</th>
                      <th>Expected Value (EV)</th>
                      <th>Multiplicity</th>
                    </tr>
                  </thead>
                  <tbody>
                    {solveData.top_hands.slice(0, 10).map((item) => (
                      <tr key={item.canonical_id}>
                        <td className="mono" style={{ fontWeight: 700, color: "#f8fafc" }}>
                          {item.canonical_id}
                        </td>
                        <td>
                          <span className={`badge-cat badge-${item.category}`}>
                            {item.category}
                          </span>
                        </td>
                        <td>{(item.equity * 100).toFixed(1)}%</td>
                        <td style={{ fontWeight: 700, color: item.ev > 0 ? "var(--accent-emerald)" : "var(--accent-rose)" }}>
                          {item.ev > 0 ? "+" : ""}{formatMoney(item.ev)} VND
                        </td>
                        <td style={{ color: "var(--text-muted)" }}>{item.multiplicity} combos</td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            </div>
          )}
        </section>
      </main>
    </div>
  );
}
