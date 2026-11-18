import assert from "node:assert/strict";
import { fileURLToPath } from "node:url";
import { createServer } from "vite";

const server = await createServer({ root: fileURLToPath(new URL("..", import.meta.url)), server: { middlewareMode: true }, appType: "custom" });
const originalFetch = globalThis.fetch;
try {
  const { fetchAiUsage, canUseAi, EMPTY_AI_USAGE } = await server.ssrLoadModule("/src/api/aiUsage.js");
  assert.equal(canUseAi(null), false);
  assert.equal(canUseAi(EMPTY_AI_USAGE), false);
  assert.equal(canUseAi({ remaining: 1, credits: 0, unlimited: false }), true);
  assert.equal(canUseAi({ remaining: 0, credits: 5, unlimited: false }), true);
  assert.equal(canUseAi({ remaining: 0, credits: 0, unlimited: false }), false);
  assert.equal(canUseAi({ remaining: 0, credits: 0, unlimited: true }), true);
  console.log("PASS paid credits allow AI after the three daily free uses");

  // The server status is authoritative; old local usage counters are ignored.
  globalThis.localStorage = { getItem: () => assert.fail("local counters must not decide usage") };
  const paid = { used: 3, limit: 3, remaining: 0, credits: 5, unlimited: false };
  globalThis.fetch = async (url, options) => {
    assert.ok(url.endsWith("/api/ai-usage/today"));
    assert.equal(options.headers.Authorization, "Bearer test-token");
    assert.equal(options.cache, "no-store");
    return { ok: true, json: async () => paid };
  };
  assert.deepEqual(await fetchAiUsage("test-token"), paid);
  console.log("PASS usage comes from the authenticated server instead of localStorage");

  await assert.rejects(() => fetchAiUsage(""), /로그인/);
  globalThis.fetch = async () => ({ ok: false, json: async () => ({ detail: "로그인이 필요합니다." }) });
  await assert.rejects(() => fetchAiUsage("expired"), /로그인/);
  globalThis.fetch = async () => ({ ok: true, json: async () => ({ ...paid, credits: -1 }) });
  await assert.rejects(() => fetchAiUsage("test-token"), /올바르지/);
  globalThis.fetch = async () => { throw new TypeError("Failed to fetch"); };
  await assert.rejects(() => fetchAiUsage("test-token"), /서버 연결/);
  console.log("PASS missing login, server errors and invalid credit balances are rejected");
} finally {
  globalThis.fetch = originalFetch;
  await server.close();
}
