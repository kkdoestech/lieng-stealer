import { percent } from '../format.js';

// Reference figures printed on the dark board, under the notes. Deliberately does not repeat the
// verdict's EV or equity: those belong to the polaroid.
export default function StatStrip({ summary, t }) {
  const cells = [
    {
      label: t.betRecommended,
      // These two fields arrive as percentages (71.62, 100); only the bluff break-even is a fraction.
      value: `${summary.bet_recommended_percent.toFixed(1)}%`,
      sub: t.combosWorthBet,
    },
    {
      label: t.rangeCoverage,
      value: `${summary.range_coverage_percent.toFixed(1)}%`,
      sub: t.showdownEquitySub,
    },
    {
      label: t.bluffThreshold,
      value: percent(summary.pure_bluff_break_even_fold_equity),
      sub: t.bluffThresholdSub,
    },
  ];

  return (
    <section className="hud-strip">
      {cells.map((cell) => (
        <div className="hud-cell" key={cell.label}>
          <div className="kicker">{cell.label}</div>
          <div className="hud-value">{cell.value}</div>
          <div className="hud-sub">{cell.sub}</div>
        </div>
      ))}
    </section>
  );
}
