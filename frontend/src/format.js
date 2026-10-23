// Pure formatting helpers, kept outside React so they can be unit-tested without a browser.

export function formatMoney(num, locale) {
  if (num === undefined || num === null) return "0";
  return new Intl.NumberFormat(locale).format(Math.round(num));
}

export function formatZones(zones) {
  const pct = (f) => `${Math.round(f * 100)}%`;
  return zones.map(([start, end]) => (start === end ? pct(start) : `${pct(start)}–${pct(end)}`)).join(" · ");
}
