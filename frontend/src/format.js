// Pure formatting helpers, kept outside React so they can be unit-tested without a browser.

export function formatMoney(num, locale) {
  if (num === undefined || num === null) return "0";
  return new Intl.NumberFormat(locale).format(Math.round(num));
}

export function formatZones(zones) {
  const pct = (f) => `${Math.round(f * 100)}%`;
  return zones.map(([start, end]) => (start === end ? pct(start) : `${pct(start)}–${pct(end)}`)).join(" · ");
}

// One decimal for win rates and equity: 99.5%, 1.1%.
export const percent = (value) => `${(value * 100).toFixed(1)}%`;

// Whole numbers for fold rates and the sliders: 35%.
export const wholePercent = (value) => `${Math.round(value * 100)}%`;

// EV is always signed so a column of numbers can be read down without a legend.
export const signedMoney = (value, locale) => `${value > 0 ? "+" : ""}${formatMoney(value, locale)}`;
