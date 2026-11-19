import assert from "node:assert/strict";
import { performance } from "node:perf_hooks";
import { fileURLToPath } from "node:url";
import { createServer } from "vite";

const server = await createServer({ root: fileURLToPath(new URL("..", import.meta.url)), server: { middlewareMode: true }, appType: "custom" });
const originalFetch = globalThis.fetch;
try {
  const { LEARN_TYPES } = await server.ssrLoadModule("/src/data/learn/index.js");
  const { loadUnitQuiz, QUIZ_BANK_VERSION } = await server.ssrLoadModule("/src/data/learn/quizBank.js");
  const { questionId, drawQuestions, remainingQuestions, wrongNoteKey } = await server.ssrLoadModule("/src/utils/learningQuiz.js");
  const api = await server.ssrLoadModule("/src/api/learn.js");
  const all = [];
  const started = performance.now();
  for (const type of LEARN_TYPES) for (const unit of type.units) {
    assert.equal(unit.quizVersion, QUIZ_BANK_VERSION);
    assert.equal(unit.quizCount, 20);
    assert.equal(unit.quiz, undefined, "questions must not be included in the initial lesson module");
    const questions = await loadUnitQuiz(unit.id);
    assert.equal(questions.length, 20);
    assert.equal(questions.filter((question) => question.a).length, 10);
    questions.forEach((question) => {
      assert.ok(question.id.startsWith(`${QUIZ_BANK_VERSION}:${unit.id}:`));
      assert.ok(question.q.trim().length >= 20);
      assert.ok(question.e.trim().length >= 10);
      assert.equal(typeof question.a, "boolean");
      assert.ok(!question.q.includes("�"));
    });
    all.push(...questions);
  }
  assert.equal(all.length, 600);
  assert.equal(new Set(all.map((question) => question.q.trim())).size, 600);
  assert.equal(new Set(all.map(questionId)).size, 600);
  console.log(`PASS 600 unique questions, 30 lazy unit banks, balanced O/X (${Math.round(performance.now() - started)}ms SSR cold imports)`);

  const unit = LEARN_TYPES[0].units[0];
  const bank = await loadUnitQuiz(unit.id);
  const originalIds = bank.map(questionId);
  const first = drawQuestions(bank, undefined, 10, () => 0.1);
  const different = drawQuestions(bank, undefined, 10, () => 0.9);
  assert.equal(first.length, 10);
  assert.equal(new Set(first.map(questionId)).size, 10);
  assert.notDeepEqual(first.map(questionId), different.map(questionId));
  assert.deepEqual(bank.map(questionId), originalIds);
  const partial = { correctQuestionIds: bank.slice(0, 17).map(questionId) };
  assert.equal(drawQuestions(bank, partial).length, 3);
  assert.ok(drawQuestions(bank, partial).every((question) => !partial.correctQuestionIds.includes(questionId(question))));
  assert.deepEqual(drawQuestions(bank, { correctQuestionIds: bank.map(questionId) }), []);
  console.log("PASS unbiased redraw, correct-answer exclusion, short final rounds, exhausted banks");

  const storage = new Map();
  globalThis.localStorage = globalThis.sessionStorage = {
    getItem: (key) => storage.get(key) ?? null,
    setItem: (key, value) => storage.set(key, value),
  };
  globalThis.window = { dispatchEvent() {}, confirm: () => false };
  let activeUser = 1;
  const user = () => ({ user_id: activeUser });
  const login = (id) => {
    activeUser = id;
    storage.set("saenggak-hanjul-auth", JSON.stringify({ user: user(), token: `test-${id}` }));
  };
  const rows = new Map();
  const row = () => {
    if (!rows.has(activeUser)) rows.set(activeUser, { progress: { units: {}, wrong: {} }, revision: 0, legacy_imported: true });
    return rows.get(activeUser);
  };
  const clone = (object) => JSON.parse(JSON.stringify(object));
  let failSave = false;
  globalThis.fetch = async (url, options = {}) => {
    assert.equal(options.headers.Authorization, `Bearer test-${activeUser}`);
    if (url.includes("/api/admin/learn/units/")) return { ok: true, json: async () => ({ ok: true }) };
    assert.ok(url.endsWith("/api/learn/progress"), `unexpected network call ${url}`);
    if (options.method === "PUT") {
      if (failSave) return { ok: false, status: 503, json: async () => ({ detail: "저장 실패" }) };
      const body = JSON.parse(options.body);
      assert.equal(body.expected_revision, row().revision);
      row().progress = body.progress;
      row().revision += 1;
    }
    return { ok: true, json: async () => clone(row()) };
  };
  login(1);
  storage.set("saenggak-hanjul-learn-content", JSON.stringify({ [unit.id]: { title: "팀원 제목 유지", quiz: [{ q: "이전 문제", a: true }] } }));
  assert.equal((await api.fetchLearnContent())[0].units[0].title, "팀원 제목 유지");
  assert.deepEqual(await api.fetchOxQuizzes("report", 1), bank);
  assert.deepEqual(await api.fetchOxQuizzes("report", "01"), bank);
  console.log("PASS outdated quiz overrides ignored, teammate lesson edits preserved, no quiz API requests");
  storage.delete("saenggak-hanjul-learn-content");

  const answer = (question, chosen = question.a, answerId) => api.saveQuizAnswer(user(), { typeKey: "report", unit, question, chosen, answerId });
  await answer(bank[0]);
  const resumed = await api.fetchLearnProgress(user());
  assert.ok(!drawQuestions(bank, resumed.units[unit.id]).some((question) => questionId(question) === questionId(bank[0])));
  assert.equal(resumed.units[unit.id].passed, false);
  const wrong = bank[1];
  await answer(wrong, !wrong.a, "same-network-retry");
  await answer(wrong, !wrong.a, "same-network-retry");
  const key = wrongNoteKey(unit.id, wrong);
  assert.equal(row().progress.wrong[key].count, 1);
  assert.equal(row().progress.wrong[key].resolved, false);
  assert.equal(row().progress.wrong[key].e, wrong.e);
  assert.ok(remainingQuestions(bank, row().progress.units[unit.id]).some((question) => questionId(question) === questionId(wrong)));
  console.log("PASS immediate account persistence survives interrupted rounds; wrong answers keep explanation and deduplicate retries");

  const round = bank.slice(0, 10);
  for (const question of round.slice(2)) await answer(question);
  const summary = await api.saveQuizAttempt(user(), { typeKey: "report", unit: { ...unit, quiz: round }, answers: round.map((question, index) => ({ index, chosen: index === 1 ? !question.a : question.a })), answersRecorded: true });
  assert.equal(summary.score, 9);
  assert.equal(summary.remaining, 11);
  assert.equal(summary.passed, false);
  assert.equal(row().progress.wrong[key].count, 1, "round summary must not count wrong answers again");
  await api.answerWrongNote(user(), key, wrong.a);
  assert.equal(row().progress.wrong[key].resolved, true);
  assert.equal(remainingQuestions(bank, row().progress.units[unit.id]).length, 10);
  await api.deleteWrongNote(user(), key);
  assert.equal(row().progress.wrong[key], undefined);
  assert.ok(!drawQuestions(bank, row().progress.units[unit.id]).some((question) => questionId(question) === questionId(wrong)));
  for (const question of bank.slice(10, 19)) await answer(question);
  assert.equal(drawQuestions(bank, row().progress.units[unit.id]).length, 1);
  await answer(bank[19], !bank[19].a);
  const finalNote = wrongNoteKey(unit.id, bank[19]);
  await api.answerWrongNote(user(), finalNote, bank[19].a);
  assert.equal(row().progress.units[unit.id].passed, true);
  assert.equal(row().progress.units[unit.id].quizMastered, true);
  assert.equal(remainingQuestions(bank, row().progress.units[unit.id]).length, 0);
  console.log("PASS wrong-note retry updates mastery; deleting solved notes does not restore questions; all 20 unlock writing");

  login(2);
  assert.equal(drawQuestions(bank, (await api.fetchLearnProgress(user())).units[unit.id]).length, 10);
  assert.equal(row().progress.wrong[finalNote], undefined);
  failSave = true;
  await assert.rejects(() => answer(bank[0]), /저장 실패/);
  assert.equal(row().progress.units[unit.id], undefined);
  failSave = false;
  row().progress.units[unit.id] = { passed: true, completed: true, writingBest: 95, lastScore: 10 };
  await answer(bank[0]);
  assert.equal(row().progress.units[unit.id].completed, true);
  assert.equal(row().progress.units[unit.id].writingBest, 95);
  assert.equal(row().progress.units[unit.id].correctQuestionIds.length, 1, "legacy aggregate scores must not fabricate individual correct records");
  console.log("PASS account isolation, save failure handling, existing writing progress retained without guessing old question results");

  const content = await api.fetchLearnContent();
  await api.saveLearnUnit({ ...content[0].units[0], quiz: bank.map(({ q, a, e }) => ({ q, a, e })) }, "test-2");
  assert.deepEqual((await api.fetchOxQuizzes("report", 1)).map(questionId), bank.map(questionId));
  console.log("PASS admin lesson edits retain unchanged canonical question identities");
} finally {
  globalThis.fetch = originalFetch;
  await server.close();
}
