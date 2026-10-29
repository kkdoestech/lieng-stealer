import { assumptionLine } from '../verdict.js';

// The assumption is a small manila scrap tucked under the polaroid: labelled, visible, secondary.
export default function AssumptionSlip({ summary, t, tone }) {
  return (
    <section className={`assumption-slip scrap ${tone}`}>
      <span className="tape tape-mid" aria-hidden="true" />
      <span className="kicker">{t.assumptionTag}</span>
      <p className="assumption-text">{assumptionLine(t, summary)}</p>
    </section>
  );
}
