import assert from "node:assert/strict";
import test from "node:test";
import { makeAiError } from "../src/utils/aiError.js";

test("AI failures preserve the server's quota and availability messages", () => {
  for (const detail of [
    "오늘 무료 AI 횟수와 보유 이용권을 모두 사용했어요.",
    "AI 서버에 연결하지 못했습니다.",
  ]) {
    const error = makeAiError({ detail }, "AI 요청 실패");
    assert.ok(error instanceof Error);
    assert.equal(error.message, detail);
  }
});

test("missing or malformed error bodies use the action's fallback message", () => {
  for (const data of [undefined, null, {}, { detail: "" }, { detail: "  " }, { detail: [] }, { detail: {} }]) {
    assert.equal(makeAiError(data, "AI 초안 작성 실패").message, "AI 초안 작성 실패");
    assert.equal(makeAiError(data, "AI 피드백 요청 실패").message, "AI 피드백 요청 실패");
  }
});
