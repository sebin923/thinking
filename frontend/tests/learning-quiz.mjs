import assert from "node:assert/strict";
import { performance } from "node:perf_hooks";
import { fileURLToPath } from "node:url";
import { createServer } from "vite";

const server = await createServer({ root: fileURLToPath(new URL("..", import.meta.url)), server: { middlewareMode: true }, appType: "custom" });
const originalFetch = globalThis.fetch;
try {
  const { LEARN_TYPES } = await server.ssrLoadModule("/src/data/learn/index.js");
  const { loadUnitQuiz, QUIZ_BANK_VERSION, DB_QUIZ_BANK_VERSION } = await server.ssrLoadModule("/src/data/learn/quizBank.js");
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

  const unit = { ...LEARN_TYPES[0].units[0], quizVersion: DB_QUIZ_BANK_VERSION, quizCount: 30 };
  let bank = await loadUnitQuiz(unit.id);
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
  const exhausted = { correctQuestionIds: bank.map(questionId) };
  assert.equal(drawQuestions(bank, exhausted).length, 10);
  assert.equal(new Set(drawQuestions(bank, exhausted).map(questionId)).size, 10);
  assert.equal(remainingQuestions(bank, exhausted).length, 0);
  assert.deepEqual(drawQuestions([], exhausted), []);
  console.log("PASS unbiased redraw, correct-answer exclusion, short final rounds, repeated review after mastery");

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
  // API 응답 계약용 합성 DB. 실제 운영 DB의 900문제는 별도 읽기 전용 검사로 확인한다.
  const dbBanks = new Map(LEARN_TYPES.flatMap((type, typeIndex) => type.units.map((item, index) => [item.id,
    Array.from({ length: 30 }, (_, qIndex) => ({
      quiz_id: typeIndex * 300 + index * 30 + qIndex + 1,
      q: `${item.id} DB 확인용 문제 ${qIndex + 1}`, a: qIndex % 2 === 0,
      e: `DB 해설 ${item.id} ${qIndex + 1}`,
    })),
  ])));
  let quizFailure = null;
  let quizOverride;
  let quizCalls = 0;
  let failSave = false;
  globalThis.fetch = async (url, options = {}) => {
    if (url.includes("/api/learn/quizzes?")) {
      quizCalls += 1;
      if (quizFailure === "network") throw new TypeError("연결 끊김");
      if (quizFailure === "http") return { ok: false, status: 503, json: async () => ({ detail: "문제 조회 실패" }) };
      if (quizFailure === "json") return { ok: true, json: async () => { throw new SyntaxError(); } };
      const query = new URL(url).searchParams;
      assert.equal(query.has("limit"), false, "단원 문제를 전부 받아야 한다");
      const id = `${query.get("category")}-${query.get("unit_id").padStart(2, "0")}`;
      return { ok: true, json: async () => clone(quizOverride ?? dbBanks.get(id)) };
    }
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
  const dbQuestions = [];
  const dbContent = await api.fetchLearnContent();
  for (const type of dbContent) for (const item of type.units) {
    assert.equal(item.quizVersion, DB_QUIZ_BANK_VERSION);
    assert.equal(item.quizCount, 30);
    assert.equal(item.quiz, undefined);
    const questions = await api.fetchOxQuizzes(type.key, item.id.split("-").at(-1));
    assert.equal(questions.length, 30);
    dbQuestions.push(...questions);
  }
  assert.equal(quizCalls, 30);
  assert.equal(dbQuestions.length, 900);
  assert.equal(new Set(dbQuestions.map(questionId)).size, 900);
  bank = await api.fetchOxQuizzes("report", 1);
  storage.set("saenggak-hanjul-learn-content", JSON.stringify({ [unit.id]: { title: "팀원 제목 유지", quiz: [{ q: "이전 문제", a: true }] } }));
  assert.equal((await api.fetchLearnContent())[0].units[0].title, "팀원 제목 유지");
  assert.deepEqual(await api.fetchOxQuizzes("report", 1), bank);
  assert.deepEqual(await api.fetchOxQuizzes("report", "01"), bank);
  storage.set("saenggak-hanjul-learn-content", JSON.stringify({ [unit.id]: { title: "팀원 제목 유지", quizVersion: DB_QUIZ_BANK_VERSION, quiz: [{ q: "로컬 문제", a: true }] } }));
  assert.equal((await api.fetchLearnContent())[0].units[0].quiz, undefined);
  assert.deepEqual(await api.fetchOxQuizzes("report", 1), bank);
  for (const failure of ["network", "http", "json"]) {
    quizFailure = failure;
    await assert.rejects(() => api.fetchOxQuizzes("report", 1));
  }
  quizFailure = null;
  for (const invalid of [[], {}, [null], [{ ...dbBanks.get(unit.id)[0], a: "false" }], [dbBanks.get(unit.id)[0], dbBanks.get(unit.id)[0]]]) {
    quizOverride = invalid;
    await assert.rejects(() => api.fetchOxQuizzes("report", 1), /문제/);
  }
  quizOverride = undefined;
  const callsBefore = quizCalls;
  await assert.rejects(() => api.fetchOxQuizzes("other", 1));
  await assert.rejects(() => api.fetchOxQuizzes("report", 11));
  assert.equal(quizCalls, callsBefore);
  const textRecord = questionId({ q: bank[0].q, a: bank[0].a });
  assert.equal(remainingQuestions(bank, { correctQuestionIds: [textRecord] }).length, 29);
  assert.equal(remainingQuestions(bank, { correctQuestionIds: [questionId({ q: bank[0].q, a: !bank[0].a })] }).length, 30);
  console.log("PASS 900 DB question identities, canonical API only, teammate lessons preserved, no fallback on server/response errors, compatible old DB records");
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
  assert.equal(summary.remaining, 21);
  assert.equal(summary.passed, false);
  assert.equal(row().progress.wrong[key].count, 1, "round summary must not count wrong answers again");
  await api.answerWrongNote(user(), key, wrong.a);
  assert.equal(row().progress.wrong[key].resolved, true);
  assert.equal(remainingQuestions(bank, row().progress.units[unit.id]).length, 20);
  await api.deleteWrongNote(user(), key);
  assert.equal(row().progress.wrong[key], undefined);
  assert.ok(!drawQuestions(bank, row().progress.units[unit.id]).some((question) => questionId(question) === questionId(wrong)));
  for (const question of bank.slice(10, 29)) await answer(question);
  assert.equal(drawQuestions(bank, row().progress.units[unit.id]).length, 1);
  await answer(bank[29], !bank[29].a);
  const finalNote = wrongNoteKey(unit.id, bank[29]);
  await api.answerWrongNote(user(), finalNote, bank[29].a);
  assert.equal(row().progress.units[unit.id].passed, true);
  assert.equal(row().progress.units[unit.id].quizMastered, true);
  assert.equal(remainingQuestions(bank, row().progress.units[unit.id]).length, 0);
  assert.equal(row().progress.units[unit.id].quizCorrectCount, 30);
  console.log("PASS wrong-note retry updates mastery; deleting solved notes does not restore questions; all 30 DB questions unlock writing");

  row().progress.units[unit.id] = { ...row().progress.units[unit.id], completed: true, writingBest: 95, writing: { text: "보존할 글" } };
  const passedAt = row().progress.units[unit.id].passedAt;
  for (let attempt = 0; attempt < 3; attempt += 1) {
    const review = drawQuestions(bank, row().progress.units[unit.id]);
    assert.equal(review.length, 10);
    for (const [index, question] of review.entries()) await answer(question, index === 0 ? !question.a : question.a);
    const result = await api.saveQuizAttempt(user(), { typeKey: "report", unit: { ...unit, quiz: review },
      answers: review.map((question, index) => ({ index, chosen: index === 0 ? !question.a : question.a })), answersRecorded: true });
    assert.equal(result.score, 9);
    assert.equal(result.firstPass, false);
    assert.equal(result.remaining, 0);
    assert.equal(result.progress.units[unit.id].completed, true);
    assert.equal(result.progress.units[unit.id].writingBest, 95);
    assert.equal(result.progress.units[unit.id].writing.text, "보존할 글");
    assert.equal(result.progress.units[unit.id].passedAt, passedAt);
    assert.equal(result.progress.units[unit.id].quizCorrectCount, 30);
    const note = result.progress.wrong[wrongNoteKey(unit.id, review[0])];
    assert.equal(note.resolved, false);
    assert.equal(note.e, review[0].e);
  }
  console.log("PASS repeated review, real round scores, review wrong notes, original mastery/writing/completion retained");

  login(2);
  assert.equal(drawQuestions(bank, (await api.fetchLearnProgress(user())).units[unit.id]).length, 10);
  assert.equal(row().progress.wrong[finalNote], undefined);
  failSave = true;
  await assert.rejects(() => answer(bank[0]), /저장 실패/);
  assert.equal(row().progress.units[unit.id], undefined);
  failSave = false;
  const oldId = questionId((await loadUnitQuiz(unit.id))[0]);
  row().progress.units[unit.id] = { correctQuestionIds: [oldId], passed: true, completed: true, writingBest: 95, lastScore: 10 };
  await answer(bank[0]);
  assert.equal(row().progress.units[unit.id].completed, true);
  assert.equal(row().progress.units[unit.id].writingBest, 95);
  assert.equal(row().progress.units[unit.id].correctQuestionIds.length, 2, "old records remain alongside new DB question results");
  assert.ok(row().progress.units[unit.id].correctQuestionIds.includes(oldId));
  assert.equal(row().progress.units[unit.id].quizCorrectCount, 1, "unrelated old questions must not count as new DB answers");
  console.log("PASS account isolation, save failure handling, existing writing progress retained without guessing old question results");

  const content = await api.fetchLearnContent();
  await api.saveLearnUnit({ ...content[0].units[0], quiz: bank.map(({ q, a, e }) => ({ q, a, e })) }, "test-2");
  assert.deepEqual((await api.fetchOxQuizzes("report", 1)).map(questionId), bank.map(questionId));
  console.log("PASS admin lesson edits retain unchanged canonical question identities");
} finally {
  globalThis.fetch = originalFetch;
  await server.close();
}
