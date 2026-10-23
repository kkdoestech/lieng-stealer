import { test } from "node:test";
import assert from "node:assert/strict";
import { formatMoney, formatZones } from "./format.js";

test("formatMoney uses the requested locale's thousands separator", () => {
  assert.equal(formatMoney(131876, "en-US"), "131,876");
  assert.equal(formatMoney(131876, "vi-VN"), "131.876");
});

test("formatMoney rounds to whole VND and keeps the minus sign", () => {
  assert.equal(formatMoney(-27894.4, "en-US"), "-27,894");
});

test("formatMoney shows 0 before any value has arrived", () => {
  assert.equal(formatMoney(undefined, "en-US"), "0");
  assert.equal(formatMoney(null, "vi-VN"), "0");
});

test("formatZones lists every profitable fold-frequency interval", () => {
  assert.equal(formatZones([[0, 0.08], [0.51, 1]]), "0%–8% · 51%–100%");
  assert.equal(formatZones([[1, 1]]), "100%");
});
