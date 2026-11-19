import assert from "node:assert/strict";
import { fileURLToPath } from "node:url";
import { createServer } from "vite";
import React from "react";
import { renderToStaticMarkup } from "react-dom/server";

const server = await createServer({ root: fileURLToPath(new URL("..", import.meta.url)), server: { middlewareMode: true }, appType: "custom" });
const originalFetch = globalThis.fetch;
try {
  const { LEARN_TYPES, getPracticeCandidates, getPracticeFor } = await server.ssrLoadModule("/src/data/learn/index.js");
  const { recommendWritingPractice, scoreWriting } = await server.ssrLoadModule("/src/api/learn.js");
  const { default: WritingPractice } = await server.ssrLoadModule("/src/pages/learn/WritingPractice.jsx");
  const report = LEARN_TYPES.find((item) => item.key === "report");
  const unit = report.units[0];
  const initial = getPracticeFor(report, unit, 0);
  const candidates = getPracticeCandidates(report);
  const selected = candidates.find((item) => item.practice.topic !== initial.topic);
  let sent;
  globalThis.fetch = async (url, options) => {
    assert.ok(url.endsWith("/api/learn/practice-recommendation"));
    sent = JSON.parse(options.body);
    return { ok: true, json: async () => ({ candidate_id: selected.id, reason: "이 단원 규칙을 연습하기 좋아요." }) };
  };
  const recommended = await recommendWritingPractice("test-token", { typeLabel: report.label, unit, candidates, currentPractice: initial });
  assert.ok(!sent.candidates.some((item) => item.title === initial.topic));
  assert.equal(recommended.practice, selected.practice);
  assert.equal(recommended.practice.url, selected.practice.url);
  console.log("PASS topic recommendation preserves original facts and source");

  globalThis.fetch = async () => ({ ok: true, json: async () => ({ candidate_id: "unknown", reason: "알 수 없는 자료" }) });
  await assert.rejects(() => recommendWritingPractice("token", { typeLabel: report.label, unit, candidates, currentPractice: initial }));
  globalThis.fetch = async () => ({ ok: false, json: async () => ({ detail: "Qwen 모델이 준비되지 않았습니다." }) });
  await assert.rejects(() => recommendWritingPractice("token", { typeLabel: report.label, unit, candidates, currentPractice: initial }), /Qwen/);
  console.log("PASS invalid recommendations and unavailable Qwen produce errors");

  const auth = JSON.stringify({ token: "test-token", user: { user_id: 1 } });
  const storage = new Map([["saenggak-hanjul-auth", auth]]);
  globalThis.localStorage = globalThis.sessionStorage = {
    getItem: (key) => storage.get(key) ?? null,
    setItem: (key, value) => storage.set(key, value),
  };
  globalThis.window = { confirm: () => false, dispatchEvent: () => {}, alert: () => assert.fail("unexpected alert") };
  const progress = { units: { [unit.id]: { passed: true } }, wrong: {} };
  globalThis.fetch = async (url, options) => {
    if (url.endsWith("/api/learn/progress")) return { ok: true, json: async () => ({ progress, revision: 1, legacy_imported: true }) };
    assert.ok(url.endsWith("/api/learn/writing-score"));
    sent = JSON.parse(options.body);
    return { ok: true, json: async () => ({ score: 90, criteria: [], on_task: true, progress_saved: true, saved_progress: { progress, revision: 2, first_complete: true } }) };
  };
  await scoreWriting({ user_id: 1 }, "test-token", { typeLabel: report.label, unit, practice: recommended.practice, text: "새로 추천받은 자료를 활용하여 확인한 사실만 바탕으로 본문을 작성했습니다." });
  assert.deepEqual(sent.practice, recommended.practice);
  assert.ok(sent.material.includes(recommended.practice.topic));
  assert.ok(!sent.material.includes(recommended.practice.example));
  console.log("PASS grading submits the selected topic without the example answer");

  const saved = { text: "저장된 연습 글", score: 90, practice: recommended.practice };
  const markup = renderToStaticMarkup(React.createElement(WritingPractice, { unit, practice: initial, saved, completed: true, best: 90, onScore: async () => {}, onRecommend: async () => {} }));
  assert.ok(markup.includes(recommended.practice.topic));
  assert.ok(markup.includes("다른 연습 주제 추천받기"));
  assert.ok(markup.includes(recommended.practice.source));
  assert.ok(markup.includes("저장된 연습 글"));
  console.log("PASS reopening practice restores its saved topic, source and text");

  const originalDocument = globalThis.document;
  globalThis.document = { createElement: () => ({
    innerHTML: "",
    get textContent() { return this.innerHTML.replace(/<[^>]*>/g, ""); },
  }) };
  try {
    const { default: WritingPage } = await server.ssrLoadModule("/src/pages/WritingPage.jsx");
    for (const authState of [null, { token: "test-token", user: { user_id: 1 } }]) {
      const writing = renderToStaticMarkup(React.createElement(WritingPage, { auth: authState, idea: "" }));
      assert.ok(writing.includes("초안 작성 방식"));
      assert.ok(writing.includes("내 문체를 학습한 AI"));
      assert.ok(!writing.includes("CLOVA"));
    }
    console.log("PASS integrated writing page renders with Qwen controls for guests and members");
  } finally {
    globalThis.document = originalDocument;
  }

  // Every bundled practice must fit the backend's persisted-material constraints.
  for (const type of LEARN_TYPES) {
    for (const candidate of getPracticeCandidates(type)) {
      const practice = candidate.practice;
      assert.ok(practice.facts.length <= 30);
      assert.ok(practice.facts.every((fact) => fact.length <= 1200));
      assert.ok((practice.example || "").length <= 10000);
      const material = [`주제: ${practice.topic}`, ...practice.facts.map((fact) => `- ${fact}`)].join("\n");
      assert.ok(material.length <= 4000);
    }
  }
  console.log("PASS bundled learning materials fit the Qwen API limits");
} finally {
  globalThis.fetch = originalFetch;
  await server.close();
}
