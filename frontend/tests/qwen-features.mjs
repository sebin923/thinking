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
  const selected = { practice: { kind: "data", topic: "스터디룸 예약 중복 방지 기능 점검",
    facts: ["보고 목적: 점검 결과를 정리한다.", "예약 시험은 20회였다.", "수정 전 중복 예약은 6회였다.", "수정 후 같은 시험에서 중복 예약은 없었다.", "실제 다중 접속 상황은 아직 확인하지 않았다.", "다음 주 추가 시험을 할 계획이다."],
    source: "생각한줄 자체 제작 가상 연습 자료", url: "", license: "글쓰기 연습을 위한 가상 설정입니다." } };
  let sent;
  globalThis.fetch = async (url, options) => {
    assert.ok(url.endsWith("/api/learn/practice-recommendation-v2"));
    assert.equal(options.headers.Authorization, "Bearer test-token");
    sent = JSON.parse(options.body);
    return { ok: true, json: async () => ({ practice: selected.practice, personalized: true, reason: "저장한 전공·관심사를 바탕으로 골랐어요." }) };
  };
  const recommended = await recommendWritingPractice("test-token", { typeLabel: report.label, unit, candidates, currentPractice: initial });
  assert.equal(sent.candidates, undefined, "고정된 10개 후보로 분야별 자료를 제한하지 않는다");
  assert.equal(sent.current_topic, initial.topic);
  assert.ok(!candidates.some((item) => item.practice.topic === selected.practice.topic));
  assert.equal(recommended.practice, selected.practice);
  assert.equal(recommended.practice.url, selected.practice.url);
  console.log("PASS topic recommendation preserves original facts and source");

  const reason = "저장한 관심사를 바탕으로 골랐어요.";
  for (const practice of [null, { ...selected.practice, facts: [] }, { ...selected.practice, topic: initial.topic },
    { ...selected.practice, url: "javascript:alert(1)" }, { ...selected.practice, facts: ["a".repeat(1201)] },
    { ...selected.practice, facts: Array(31).fill("사실") }, { ...selected.practice, facts: Array(5).fill("가".repeat(900)) },
    { kind: "question", question: "자료형 응답 대신 질문을 반환" }]) {
    globalThis.fetch = async () => ({ ok: true, json: async () => ({ practice, reason }) });
    await assert.rejects(() => recommendWritingPractice("token", { typeLabel: report.label, unit, candidates, currentPractice: initial }), /추천 결과/);
  }
  globalThis.fetch = async () => ({ ok: true, json: async () => null });
  await assert.rejects(() => recommendWritingPractice("token", { typeLabel: report.label, unit, candidates, currentPractice: initial }), /추천 결과/);
  const question = { kind: "question", question: "본인이 실제로 웹이나 프로그램의 오류를 해결한 경험과 본인의 행동을 써 보세요.", source: "생각한줄 자체 제작 경험 중심 연습 문항" };
  globalThis.fetch = async () => ({ ok: true, json: async () => ({ practice: question, reason }) });
  const cover = await recommendWritingPractice("token", { typeLabel: "자기소개서", unit, candidates: [], currentPractice: { kind: "question", question: "이전 문항" } });
  assert.deepEqual(cover.practice, question);
  await assert.rejects(() => recommendWritingPractice("token", { typeLabel: "자기소개서", unit, candidates: [], currentPractice: question }), /추천 결과/);
  console.log("PASS curated materials outside old candidates, metadata retention, question mode, malformed and repeated results rejected");

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
  assert.deepEqual(sent.practice.facts, recommended.practice.facts);
  assert.ok(!sent.material.includes("예시 답안"));
  console.log("PASS grading submits the selected topic without the example answer");

  const saved = { text: "저장된 연습 글", score: 90, practice: recommended.practice };
  const markup = renderToStaticMarkup(React.createElement(WritingPractice, { unit, practice: initial, saved, completed: true, best: 90, onScore: async () => {}, onRecommend: async () => {} }));
  assert.ok(markup.includes(recommended.practice.topic));
  assert.ok(markup.includes("다른 연습 주제 추천받기"));
  assert.ok(markup.includes(recommended.practice.source));
  assert.ok(!markup.includes('href=""'), "자체 제작 자료의 빈 출처 URL을 링크로 표시하지 않는다");
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
      assert.ok(writing.includes("AI 초안 작성"));
      assert.ok(writing.includes("AI 피드백"));
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
