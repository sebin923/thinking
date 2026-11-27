import assert from "node:assert/strict";
import { fileURLToPath } from "node:url";
import { createServer } from "vite";

const server = await createServer({ root: fileURLToPath(new URL("..", import.meta.url)), server: { middlewareMode: true }, appType: "custom" });
const original = globalThis.fetch;
try {
  const { fetchMyProfile, updateMyProfile } = await server.ssrLoadModule("/src/api/mypage.js");
  const member = { name: "테스트", phone: "01000000000", email: "test@example.com" };
  let payload;
  globalThis.fetch = async (url, options) => {
    assert.ok(url.endsWith("/api/mypage/profile"));
    assert.equal(options.headers.Authorization, "Bearer account-token");
    payload = options.body ? JSON.parse(options.body) : null;
    return { ok: true, json: async () => payload ? { profile: payload } : { ...member, major: "컴퓨터공학과", interests: ["웹 개발"] } };
  };
  const profile = await fetchMyProfile("account-token");
  assert.equal(profile.major, "컴퓨터공학과");
  const changed = await updateMyProfile("account-token", { ...member, major: "경영학과", interests: ["경영", "예산"] });
  assert.deepEqual(changed.profile.interests, ["경영", "예산"]);
  assert.equal(payload.major, "경영학과");
  await updateMyProfile("account-token", member);
  assert.equal("major" in payload, false);
  assert.equal("interests" in payload, false);
  await updateMyProfile("account-token", { ...member, major: "", interests: [] });
  assert.deepEqual(payload.interests, []);
  console.log("PASS authenticated profile loading, combined member/preferences save, legacy omission and explicit clearing");
  globalThis.fetch = async () => ({ ok: false, status: 401, json: async () => ({ detail: "로그인이 풀렸어요." }) });
  await assert.rejects(() => updateMyProfile("account-token", member), error => error.status === 401);
  globalThis.fetch = async () => ({ ok: false, status: 422, json: async () => ({ detail: [{ msg: "Value error, 관심 분야는 각각 1~40자로 입력해 주세요." }] }) });
  await assert.rejects(() => updateMyProfile("account-token", member), /관심 분야/);
  console.log("PASS login expiry and validation errors remain visible to the existing form");
} finally {
  globalThis.fetch = original;
  await server.close();
}
