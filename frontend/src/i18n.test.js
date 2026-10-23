import { test } from "vitest";
import assert from "node:assert/strict";
import { LANGUAGES, STRINGS } from "./i18n.js";

// key -> "string" | "function", so a missing key or a wrong kind of value shows up in the diff
const shape = (dictionary) =>
  Object.fromEntries(Object.entries(dictionary).map(([key, value]) => [key, typeof value]));

test("every language defines exactly the English keys, with the same kinds of values", () => {
  for (const lang of LANGUAGES) {
    assert.deepEqual(shape(STRINGS[lang]), shape(STRINGS.en), `language "${lang}"`);
  }
});

test("messages with a parameter include it in every language", () => {
  for (const lang of LANGUAGES) {
    for (const [key, value] of Object.entries(STRINGS[lang])) {
      if (typeof value === "function" && value.length > 0) {
        assert.ok(String(value("DETAIL-123")).includes("DETAIL-123"), `${lang}.${key}`);
      }
    }
  }
});
