import test from "node:test";
import assert from "node:assert/strict";

import { BADGE_LABELS, badgeClass } from "../src/badge.js";

test("badge labels expose supported variants", () => {
  assert.deepEqual(Object.keys(BADGE_LABELS), ["alert", "info", "success"]);
});

test("badgeClass maps success to a success style", () => {
  assert.equal(badgeClass("success"), "badge badge--success");
});
