// =============================================================
// api/learn.js — 학습 데이터·진도·오답노트 저장 담당
// -------------------------------------------------------------
// 화면(LearnPage, MyPage, AdminPage)은 저장 방법을 몰라도 되게 이 파일의 함수만 부름
//
// ★ 지금은 백엔드 API가 없어서 브라우저 저장소(localStorage)에 저장함
//   - 같은 컴퓨터·같은 브라우저에서만 이어짐 (다른 기기에서 로그인하면 진도가 안 보임)
//   - 회원마다 따로 저장 (저장 이름에 user_id를 붙임)
//   → 백엔드가 생기면 함수 "안쪽"만 fetch로 바꾸면 되고, 함수 이름·모양은 그대로 두면 화면은 안 고쳐도 됨
//     (그래서 지금도 일부러 async 함수로 만들어 둠 → 나중에 서버 요청으로 바꿔도 쓰는 쪽 코드가 같음)
//
// 백엔드로 옮길 때 필요한 API (예시)
//   GET  /api/learn/content                 학습 내용 (유형·단원·문제)
//   PUT  /api/admin/learn/units/{unit_id}   관리자: 단원 내용 수정
//   GET  /api/learn/progress                내 진도 + 오답노트
//   POST /api/learn/units/{unit_id}/quiz    O/X 결과 저장
//   PUT  /api/learn/units/{unit_id}/writing 글쓰기 연습 저장 (채점 결과 포함)
//   POST /api/learn/writing-score           ★ 이미 있음: 글쓰기 연습 AI 채점 (backend/routers/learn.py)
//   POST /api/learn/wrong/{key}/answer      오답노트 다시 풀기
// =============================================================

import { LEARN_TYPES } from "../data/learn";

// 백엔드 주소 (frontend/.env의 VITE_API_URL이 있으면 그 값, 없으면 기본값)
const API_URL = import.meta.env.VITE_API_URL || "http://127.0.0.1:8000";

// 단원 완료 기준: 글쓰기 연습 AI 채점 점수 (백엔드 routers/learn.py의 PASS_SCORE와 같은 값)
export const LEARN_PASS_SCORE = 90;

// 저장 이름표 (localStorage에 이 이름으로 저장됨)
const CONTENT_KEY = "saenggak-hanjul-learn-content"; // 관리자가 고친 단원들
const PROGRESS_PREFIX = "saenggak-hanjul-learn-progress:"; // 뒤에 user_id가 붙음

// 관리자가 고칠 수 있는 칸 (이 칸만 저장·덮어쓰기 함 → id 같은 중요한 값은 못 바꾸게)
const EDITABLE_FIELDS = ["title", "summary", "points", "good", "bad", "tip", "task", "quiz"];

// ----- localStorage 읽기·쓰기 (실패해도 화면이 멈추지 않게 try/catch) -----
// 사생활 보호 모드, 저장소 꽉 참 등으로 실패할 수 있음
function readJson(key, fallback) {
  try {
    const raw = localStorage.getItem(key);
    return raw ? JSON.parse(raw) : fallback;
  } catch {
    return fallback;
  }
}

function writeJson(key, value) {
  try {
    localStorage.setItem(key, JSON.stringify(value));
  } catch {
    throw new Error("저장 공간에 저장하지 못했어요. 브라우저 설정을 확인해 주세요.");
  }
}

// 회원 구분 값 (user_id가 없으면 아이디로)
function userKey(user) {
  return PROGRESS_PREFIX + (user?.user_id ?? user?.login_id ?? "guest");
}

// =============================================================
// 1. 학습 내용 (유형·단원·문제)
// =============================================================

// 학습 내용 가져오기
// 기본 내용(data/learn) 위에 관리자가 고친 단원을 덮어써서 돌려줌
// 고친 단원에는 edited: true 표시가 붙음 (관리자 화면에서 "수정됨" 표시용)
export async function fetchLearnContent() {
  const overrides = readJson(CONTENT_KEY, {});
  return LEARN_TYPES.map((type) => ({
    ...type,
    units: type.units.map((unit) =>
      overrides[unit.id] ? { ...unit, ...overrides[unit.id], id: unit.id, edited: true } : unit
    ),
  }));
}

// 관리자: 단원 하나 저장 (고칠 수 있는 칸만 골라서 저장)
export async function saveLearnUnit(unit) {
  // 저장하기 전에 마지막으로 검사 (화면에서도 검사하지만 여기서 한 번 더)
  if (!unit.title?.trim()) throw new Error("단원 제목을 입력해 주세요.");
  if (!Array.isArray(unit.quiz) || unit.quiz.length === 0) throw new Error("O/X 문제를 1개 이상 넣어 주세요.");
  unit.quiz.forEach((item, index) => {
    if (!item.q?.trim()) throw new Error(`${index + 1}번 문제 내용을 입력해 주세요.`);
    if (typeof item.a !== "boolean") throw new Error(`${index + 1}번 문제의 정답(O/X)을 골라 주세요.`);
  });

  const overrides = readJson(CONTENT_KEY, {});
  const saved = {};
  EDITABLE_FIELDS.forEach((field) => {
    if (unit[field] !== undefined) saved[field] = unit[field];
  });
  saved.updatedAt = new Date().toISOString();
  overrides[unit.id] = saved;
  writeJson(CONTENT_KEY, overrides);
  return saved;
}

// 관리자: 단원을 기본 내용으로 되돌리기 (고친 내용 지우기)
export async function resetLearnUnit(unitId) {
  const overrides = readJson(CONTENT_KEY, {});
  delete overrides[unitId];
  writeJson(CONTENT_KEY, overrides);
}

// =============================================================
// 2. 진도 + 오답노트
// =============================================================
// 저장 모양
// {
//   units: {
//     "report-01": {
//       attempts: 3,          푼 횟수
//       lastScore: 9,         마지막 점수
//       bestScore: 10,        최고 점수
//       total: 10,            문제 수
//       passed: true,         O/X 만점을 한 번이라도 받았는지 (= 글쓰기 연습 열림)
//       passedAt: "2026-…",   처음 만점 받은 시각
//       writing: {            마지막으로 AI 채점 받은 글
//         text, score, criteria: [{ label, score, max, comment }], overallFeedback, nextStep, onTask, scoredAt
//       },
//       writingAttempts: 2,   AI 채점 받은 횟수
//       writingBest: 93,      글쓰기 최고 점수
//       completed: true,      AI 채점 90점 이상을 한 번이라도 받았는지 (= 단원 완료, 다음 단원 열림)
//       completedAt: "2026-…" 처음 90점 이상 받은 시각
//     }
//   },
//   wrong: {
//     (학습 단원 O/X)   "report-01#3": { key, typeKey, unitId, unitTitle, index, q, a, e, myAnswer, count, lastAt, resolved, resolvedAt }
//     (퀴즈 화면 객관식) "quiz-12": { key, source: "quiz", typeKey: "quiz-spelling", unitTitle: "맞춤법 퀴즈",
//                                    q, options: [보기…], answer: "정답 보기", e, myAnswer: "내가 고른 보기", count, … }
//   }
// }

function emptyProgress() {
  return { units: {}, wrong: {} };
}

// 내 진도 가져오기
export async function fetchLearnProgress(user) {
  const saved = readJson(userKey(user), null);
  // 예전 모양이거나 비어 있어도 항상 { units, wrong } 모양으로 돌려줌
  return { ...emptyProgress(), ...(saved || {}) };
}

// O/X 결과 저장
// answers: [{ index: 문제 번호(0부터), chosen: 내가 고른 답(true/false) }, …]  ← 문제 순서대로 전부
// 돌려주는 값: { progress: 새 진도, score, total, passed: 이번에 만점인지, firstPass: 이번이 첫 만점인지 }
export async function saveQuizAttempt(user, { typeKey, unit, answers }) {
  const progress = await fetchLearnProgress(user);
  const now = new Date().toISOString();
  const total = unit.quiz.length;

  // 맞힌 개수 세기
  let score = 0;
  answers.forEach(({ index, chosen }) => {
    const question = unit.quiz[index];
    const key = `${unit.id}#${index}`; // 오답노트 구분 값: "단원id#문제번호"
    if (!question) return;

    if (chosen === question.a) {
      score += 1;
      // 예전에 틀렸던 문제를 이번에 맞혔으면 오답노트에서 "해결"로 표시
      const note = progress.wrong[key];
      if (note && !note.resolved) {
        progress.wrong[key] = { ...note, resolved: true, resolvedAt: now };
      }
    } else {
      // 틀린 문제 → 오답노트에 담기 (이미 있으면 틀린 횟수만 늘리고 다시 "미해결"로)
      const before = progress.wrong[key];
      progress.wrong[key] = {
        key,
        typeKey,
        unitId: unit.id,
        unitTitle: unit.title,
        index,
        // 문제 내용을 그대로 복사해 둠 → 나중에 관리자가 문제를 고쳐도 내가 틀린 문제는 그대로 보임
        q: question.q,
        a: question.a,
        e: question.e,
        myAnswer: chosen,
        count: (before?.count || 0) + 1,
        lastAt: now,
        resolved: false,
        resolvedAt: null,
      };
    }
  });

  const passed = score === total; // 전부 맞혀야 통과
  const before = progress.units[unit.id] || {};
  const firstPass = passed && !before.passed;
  progress.units[unit.id] = {
    ...before,
    attempts: (before.attempts || 0) + 1,
    lastScore: score,
    bestScore: Math.max(before.bestScore || 0, score),
    total,
    passed: Boolean(before.passed || passed), // 한 번 통과하면 계속 통과 상태
    passedAt: before.passedAt || (passed ? now : null),
  };

  writeJson(userKey(user), progress);
  return { progress, score, total, passed, firstPass };
}

// 연습 자료를 AI에게 보낼 글자로 바꾸기
// practice: data/learn/index.js의 getPracticeFor 결과 (kind "data" = 주제·사실 / "question" = 자기소개서 문항)
function practiceToText(practice) {
  if (!practice) return "";
  if (practice.kind === "question") return `문항: ${practice.question}`;
  return [`주제: ${practice.topic}`, ...(practice.facts || []).map((fact) => `- ${fact}`)].join("\n");
}

// 글쓰기 연습 AI 채점 받기 + 결과 저장 (O/X 만점 받은 단원만 가능)
// token: 로그인 토큰 / typeLabel: "보고서" 등 / unit: 단원 / practice: 연습 자료 / text: 내가 쓴 글
// 돌려주는 값: { progress: 새 진도, result: 채점 결과, firstComplete: 이번에 처음 단원 완료인지 }
//   result: { score, passScore, passed, onTask, criteria: [{ label, score, max, comment }], overallFeedback, nextStep }
export async function scoreWriting(user, token, { typeLabel, unit, practice, text }) {
  const before = await fetchLearnProgress(user);
  if (!before.units[unit.id]?.passed) throw new Error("O/X 문제를 모두 맞혀야 글쓰기 연습을 할 수 있어요.");
  if (!text?.trim()) throw new Error("글을 입력해 주세요.");

  // ----- ① 백엔드에 채점 요청 -----
  let response;
  try {
    response = await fetch(`${API_URL}/api/learn/writing-score`, {
      method: "POST",
      headers: { "Content-Type": "application/json", Authorization: `Bearer ${token}` },
      body: JSON.stringify({
        type_label: typeLabel,
        unit_title: unit.title,
        rules: unit.points, // 단원 규칙 = 채점 기준
        task: unit.task,
        material: practiceToText(practice),
        text: text.trim(),
      }),
    });
  } catch {
    // fetch 자체가 실패 = 서버가 꺼져 있거나 주소가 틀림
    throw new Error("서버에 연결할 수 없어요. 백엔드가 켜져 있는지 확인해 주세요.");
  }
  const data = await response.json().catch(() => ({}));
  if (!response.ok) {
    if (response.status === 401) throw new Error("로그인이 풀렸어요. 다시 로그인해 주세요.");
    // FastAPI 에러 모양: { detail: "문구" } 또는 { detail: [{ msg }] }(입력값 검사 에러)
    const detail = typeof data.detail === "string" ? data.detail : "AI 채점에 실패했어요. 잠시 후 다시 시도해 주세요.";
    throw new Error(detail);
  }

  // 서버 이름(snake_case) → 화면에서 쓰는 이름(camelCase)
  const result = {
    score: data.score,
    passScore: data.pass_score ?? LEARN_PASS_SCORE,
    passed: data.score >= LEARN_PASS_SCORE,
    onTask: data.on_task !== false,
    criteria: data.criteria || [],
    overallFeedback: data.overall_feedback || "",
    nextStep: data.next_step || "",
  };

  // ----- ② 결과 저장 (채점이 끝나는 동안 다른 곳에서 진도가 바뀌었을 수 있어서 다시 읽음) -----
  const progress = await fetchLearnProgress(user);
  const now = new Date().toISOString();
  const unitProgress = progress.units[unit.id] || {};
  const firstComplete = result.passed && !unitProgress.completed;
  progress.units[unit.id] = {
    ...unitProgress,
    writing: {
      text: text.trim(),
      score: result.score,
      criteria: result.criteria,
      overallFeedback: result.overallFeedback,
      nextStep: result.nextStep,
      onTask: result.onTask,
      scoredAt: now,
    },
    writingAttempts: (unitProgress.writingAttempts || 0) + 1,
    writingBest: Math.max(unitProgress.writingBest || 0, result.score),
    // 한 번 완료하면 계속 완료 상태 (나중에 점수가 낮게 나와도 잠기지 않음)
    completed: Boolean(unitProgress.completed || result.passed),
    completedAt: unitProgress.completedAt || (result.passed ? now : null),
  };
  writeJson(userKey(user), progress);
  return { progress, result, firstComplete };
}

// 퀴즈 화면(맞춤법·문법 객관식) 결과를 오답노트에 반영
// 틀리면 오답노트에 담고, 예전에 틀렸던 문제를 이번에 맞히면 "해결"로 표시
// quiz: 퀴즈 문제 { quiz_id, question, options, answer, explanation } / category: "spelling" 또는 "grammar"
// categoryLabel: 화면에 보일 이름 ("맞춤법" 등) / chosen: 내가 고른 보기 글자
export async function recordQuizAnswer(user, { quiz, category, categoryLabel, chosen }) {
  const progress = await fetchLearnProgress(user);
  const now = new Date().toISOString();
  // 구분 값: "quiz-문제번호" (같은 문제를 또 틀리면 같은 칸에 횟수만 늘어남)
  const key = `quiz-${quiz.quiz_id ?? quiz.question}`;
  const before = progress.wrong[key];

  if (chosen === quiz.answer) {
    // 맞혔으면: 예전에 틀렸던 문제일 때만 해결 처리 (처음부터 맞힌 문제는 오답노트에 안 넣음)
    if (!before || before.resolved) return progress;
    progress.wrong[key] = { ...before, resolved: true, resolvedAt: now };
  } else {
    progress.wrong[key] = {
      key,
      source: "quiz", // 퀴즈 화면에서 온 오답 (학습 단원 O/X와 구분)
      typeKey: `quiz-${category}`,
      unitTitle: `${categoryLabel} 퀴즈`,
      // 문제 내용을 그대로 복사해 둠 (나중에 관리자가 문제를 고쳐도 내가 틀린 문제는 그대로 보임)
      q: quiz.question,
      options: [...quiz.options],
      answer: quiz.answer,
      e: quiz.explanation || "",
      myAnswer: chosen,
      count: (before?.count || 0) + 1,
      lastAt: now,
      resolved: false,
      resolvedAt: null,
    };
  }
  writeJson(userKey(user), progress);
  return progress;
}

// 오답노트에서 다시 풀기
// chosen: O/X 문제면 true/false, 퀴즈(객관식) 문제면 고른 보기 글자
// 돌려주는 값: { correct: 맞혔는지, progress: 새 진도 }
export async function answerWrongNote(user, key, chosen) {
  const progress = await fetchLearnProgress(user);
  const note = progress.wrong[key];
  if (!note) throw new Error("오답노트에서 문제를 찾을 수 없어요.");

  // 퀴즈(객관식)는 보기 글자로, 학습 O/X는 true/false로 비교
  const correct = note.source === "quiz" ? chosen === note.answer : chosen === note.a;
  const now = new Date().toISOString();
  progress.wrong[key] = correct
    ? { ...note, resolved: true, resolvedAt: now }
    : { ...note, myAnswer: chosen, count: note.count + 1, lastAt: now };
  writeJson(userKey(user), progress);
  return { correct, progress };
}

// 오답노트에서 지우기 (해결한 문제 정리용)
export async function deleteWrongNote(user, key) {
  const progress = await fetchLearnProgress(user);
  delete progress.wrong[key];
  writeJson(userKey(user), progress);
  return progress;
}

// =============================================================
// 3. 계산 도우미 (화면에서 바로 쓰는 일반 함수, 저장은 안 함)
// =============================================================

// 단원이 열려 있는지
// 규칙: 첫 단원은 항상 열림 / 앞 단원을 완료(O/X 만점 + 글쓰기 90점 이상)했으면 열림
//       이미 시작한 단원(O/X 만점)·완료한 단원은 언제든 다시 할 수 있음
export function isUnitUnlocked(units, index, progress) {
  if (index === 0) return true;
  const self = progress.units[units[index].id];
  if (self?.passed || self?.completed) return true;
  const prev = progress.units[units[index - 1].id];
  return Boolean(prev?.completed);
}

// 단원 상태 하나로 정리
//   "locked"    : 잠김 (앞 단원을 완료해야 열림)
//   "open"      : 풀 수 있음 (O/X 만점 전)
//   "writing"   : O/X 만점 → 글쓰기 연습 90점 이상이 남음
//   "completed" : 단원 완료 (O/X 만점 + 글쓰기 90점 이상)
export function unitStatus(units, index, progress) {
  const p = progress.units[units[index].id];
  if (p?.completed) return "completed";
  if (p?.passed) return "writing";
  return isUnitUnlocked(units, index, progress) ? "open" : "locked";
}

// 유형별 진도 요약 → [{ key, label, done(완료 단원 수), quizPassed(O/X 만점까지 한 단원 수), total }]
export function summarizeProgress(content, progress) {
  return content.map((type) => {
    const done = type.units.filter((unit) => progress.units[unit.id]?.completed).length;
    const quizPassed = type.units.filter((unit) => progress.units[unit.id]?.passed).length;
    return { key: type.key, label: type.label, done, quizPassed, total: type.units.length };
  });
}

// 아직 해결 못 한 오답 개수
export function countOpenWrong(progress) {
  return Object.values(progress.wrong).filter((note) => !note.resolved).length;
}
