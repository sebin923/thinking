import assert from "node:assert/strict";
import test from "node:test";
import { resolveApiBaseUrl } from "../src/api/baseUrl.js";

test("production defaults to the current origin", () => {
  assert.equal(resolveApiBaseUrl(undefined, false), "");
  assert.equal(resolveApiBaseUrl("", false), "");
});

test("development retains the local backend", () => {
  assert.equal(resolveApiBaseUrl(undefined, true), "http://127.0.0.1:8000");
});

test("an explicit API origin is respected and normalized", () => {
  assert.equal(resolveApiBaseUrl(" https://thinking.example/ ", false), "https://thinking.example");
});
