// =============================================================
// api/learn.js — 학습 데이터·진도·오답노트 저장 담당
// -------------------------------------------------------------
// 화면(LearnPage, MyPage, AdminPage)은 저장 방법을 몰라도 되게 이 파일의 함수만 부름
//
// ★ 지금은 백엔드가 없어서 고친 내용이 이 브라우저에만 저장됨 (api/learn.js)
//  - 같은 컴퓨터·같은 브라우저에서만 이어짐 (다른 기기에서 로그인하면 진도가 안 보임)
//  - 회원마다 따로 저장 (저장 이름에 user_id를 붙임)
//  → 백엔드가 생기면 함수 "안쪽"만 fetch로 바꾸면 되고, 함수 이름·모양은 그대로 두면 화면은 안 고쳐도 됨
//    (그래서 지금도 일부러 async 함수로 만들어 둠 → 나중에 서버 요청으로 바꿔도 쓰는 쪽 코드가 같음)
//
// 백엔드로 옮길 때 필요한 API (예시)
//  GET  /api/learn/content                         학습 내용 (유형·단원·문제)
//  PUT  /api/admin/learn/units/{unit_id}   관리자: 단원 내용 수정
//  GET  /api/learn/progress                        내 진도 + 오답노트
//  POST /api/learn/units/{unit_id}/quiz    O/X 결과 저장
//  PUT  /api/learn/units/{unit_id}/writing 글쓰기 연습 저장 (채점 결과 포함)
//  POST /api/learn/writing-score           ★ 이미 있음: 글쓰기 연습 AI 채점 (backend/routers/learn.py)
//  POST /api/learn/wrong/{key}/answer      오답노트 다시 풀기
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

// 관리자: 단원 하나 저장 (고칠 수 있는 칸만 골라서 저장 + 백엔드 DB 연동)
export async function saveLearnUnit(unit, token) {
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

  // 인증 토큰 확보 (인자로 넘어오지 않았을 경우 로컬 스토리지에서 탐색)
  const authToken = token || localStorage.getItem("token") || localStorage.getItem("access_token");
  if (!authToken) {
    throw new Error("로그인이 필요해요.");
  }

  // ★ 백엔드 DB에도 단원 수정 내용 반영 요청 (인증 토큰 헤더 추가)
  try {
    const response = await fetch(`${API_URL}/api/admin/learn/units/${unit.id}`, {
      method: "PUT",
      headers: { 
        "Content-Type": "application/json",
        "Authorization": `Bearer ${authToken}`
      },
      body: JSON.stringify(saved),
    });

    if (!response.ok) {
      const errData = await response.json().catch(() => ({}));
      throw new Error(errData.detail || "서버 저장에 실패했어요.");
    }
  } catch (err) {
    console.error("백엔드 DB 단원 저장 동기화 실패:", err);
    throw err;
  }

  return saved;
}

// 관리자: 단원을 기본 내용으로 되돌리기 (고친 내용 지우기 + 백엔드 연동)
export async function resetLearnUnit(unitId, token) {
  const overrides = readJson(CONTENT_KEY, {});
  delete overrides[unitId];
  writeJson(CONTENT_KEY, overrides);

  const authToken = token || localStorage.getItem("token") || localStorage.getItem("access_token");
  if (!authToken) {
    throw new Error("로그인이 필요해요.");
  }

  try {
    const response = await fetch(`${API_URL}/api/admin/learn/units/${unitId}/reset`, {
      method: "POST",
      headers: {
        "Authorization": `Bearer ${authToken}`
      }
    });

    if (!response.ok) {
      const errData = await response.json().catch(() => ({}));
      throw new Error(errData.detail || "서버 초기화에 실패했어요.");
    }
  } catch (err) {
    console.error("백엔드 DB 단원 초기화 동기화 실패:", err);
    throw err;
  }
}

// =============================================================
// 2. 진도 + 오답노트
// =============================================================
// 저장 모양
// {
//  units: {
//    "report-01": {
//      attempts: 3,        푼 횟수
//      lastScore: 9,       마지막 점수
//      bestScore: 10,      최고 점수
//      total: 10,          문제 수
//      passed: true,       O/X 만점을 한 번이라도 받았는지 (= 글쓰기 연습 열림)
//      passedAt: "2026-…", 처음 만점 받은 시각
//      writing: {          마지막으로 AI 채점 받은 글
//        text, score, criteria: [{ label, score, max, comment }], overallFeedback, nextStep, onTask, scoredAt
//      },
//      writingAttempts: 2, AI 채점 받은 횟수
//      writingBest: 93,    글쓰기 최고 점수
//      completed: true,    AI 채점 90점 이상을 한 번이라도 받았는지 (= 단원 완료, 다음 단원 열림)
//      completedAt: "2026-…" 처음 90점 이상 받은 시각
//    }
//  },
//  wrong: {
//    (학습 단원 O/X)   "report-01#3": { key, typeKey, unitId, unitTitle, index, q, a, e, myAnswer, count, lastAt, resolved, resolvedAt }
//    (퀴즈 화면 객관식) "quiz-12": { key, source: "quiz", typeKey: "quiz-spelling", unitTitle: "맞춤법 퀴즈",
//                                q, options: [보기…], answer: "정답 보기", e, myAnswer: "내가 고른 보기", count, … }
//  }
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

// O/X 결과 저장 (DB 퀴즈 및 오답노트가 예전 더미와 섞이지 않도록 quiz_id 또는 질문 내용 기반으로 고정)
export async function saveQuizAttempt(user, { typeKey, unit, answers }) {
  const progress = await fetchLearnProgress(user);
  const now = new Date().toISOString();
  
  const quizList = unit.quiz || [];
  const total = quizList.length;

  let score = 0;
  answers.forEach(({ index, chosen }) => {
    const question = quizList[index];
    if (!question) return;

    // ★ 핵심 수정: 예전 팀원 더미 데이터 인덱스 충돌을 원천 차단하기 위해 
    // DB의 고유 quiz_id가 있으면 그걸 쓰고, 없으면 질문 내용(q)을 해시/인코딩하여 고유 키 생성
    const uniqueId = question.quiz_id ?? encodeURIComponent(question.q.trim());
    const key = `${unit.id}#db-${uniqueId}`;

    if (chosen === question.a) {
      score += 1;
      const note = progress.wrong[key];
      if (note && !note.resolved) {
        progress.wrong[key] = { ...note, resolved: true, resolvedAt: now };
      }
    } else {
      const before = progress.wrong[key];
      progress.wrong[key] = {
        key,
        typeKey,
        unitId: unit.id,
        unitTitle: unit.title,
        index,
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

  const passed = score === total;
  const before = progress.units[unit.id] || {};
  const firstPass = passed && !before.passed;
  progress.units[unit.id] = {
    ...before,
    attempts: (before.attempts || 0) + 1,
    lastScore: score,
    bestScore: Math.max(before.bestScore || 0, score),
    total,
    passed: Boolean(before.passed || passed),
    passedAt: before.passedAt || (passed ? now : null),
  };

  writeJson(userKey(user), progress);
  return { progress, score, total, passed, firstPass };
}

// 연습 자료를 AI에게 보낼 글자로 바꾸기
function practiceToText(practice) {
  if (!practice) return "";
  if (practice.kind === "question") return `문항: ${practice.question}`;
  return [`주제: ${practice.topic}`, ...(practice.facts || []).map((fact) => `- ${fact}`)].join("\n");
}

// 글쓰기 연습 AI 채점 받기 + 결과 저장
export async function scoreWriting(user, token, { typeLabel, unit, practice, text }) {
  const before = await fetchLearnProgress(user);
  if (!before.units[unit.id]?.passed) throw new Error("O/X 문제를 모두 맞혀야 글쓰기 연습을 할 수 있어요.");
  if (!text?.trim()) throw new Error("글을 입력해 주세요.");

  // 제출마다 동의를 묻고, 거절해도 기존 채점은 진행한다.
  const trainingConsent = window.confirm(
    "이 글이 90점 이상이면 공통 AI 학습 후보로 제공할까요?\n" +
    "동의하면 글·과제·평가 결과를 저장하고 관리자 검토 후 모델 학습에 사용할 수 있습니다.\n" +
    "본인이 작성하고 이용 권한이 있는 글만 제공하고 개인정보는 제외해 주세요.\n" +
    "동의 철회는 관리자에게 요청할 수 있습니다. 이미 학습한 모델은 별도 조치가 필요합니다.\n" +
    "확인: 동의 / 취소: 동의하지 않고 채점"
  );

  let response;
  try {
    response = await fetch(`${API_URL}/api/learn/writing-score`, {
      method: "POST",
      headers: { "Content-Type": "application/json", Authorization: `Bearer ${token}` },
      body: JSON.stringify({
        unit_id: String(unit.id),
        training_consent: trainingConsent,
        type_label: typeLabel,
        unit_title: unit.title,
        rules: unit.points,
        task: unit.task,
        material: practiceToText(practice),
        text: text.trim(),
      }),
    });
  } catch {
    throw new Error("서버에 연결할 수 없어요. 백엔드가 켜져 있는지 확인해 주세요.");
  }
  const data = await response.json().catch(() => ({}));
  if (!response.ok) {
    if (response.status === 401) throw new Error("로그인이 풀렸어요. 다시 로그인해 주세요.");
    const detail = typeof data.detail === "string" ? data.detail : "AI 채점에 실패했어요. 잠시 후 다시 시도해 주세요.";
    throw new Error(detail);
  }

  const result = {
    score: data.score,
    passScore: data.pass_score ?? LEARN_PASS_SCORE,
    passed: data.score >= LEARN_PASS_SCORE,
    onTask: data.on_task !== false,
    criteria: data.criteria || [],
    overallFeedback: data.overall_feedback || "",
    nextStep: data.next_step || "",
    trainingCandidate: data.training_candidate || null,
  };

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
    completed: Boolean(unitProgress.completed || result.passed),
    completedAt: unitProgress.completedAt || (result.passed ? now : null),
  };
  writeJson(userKey(user), progress);
  if (trainingConsent) {
    const state = data.training_candidate?.status;
    if (state === "pending") {
      window.alert("채점을 완료했고 학습 후보로 저장했습니다. 관리자 승인 후 학습에 사용할 수 있습니다.");
    } else if (state === "save_failed" || !state) {
      window.alert("채점은 완료했지만 학습 후보 저장은 확인되지 않았습니다. 관리자에게 문의해 주세요.");
    } else if (state === "duplicate") {
      window.alert("이미 제출한 후보입니다. 기존 검토 상태를 유지합니다.");
    }
  }
  return { progress, result, firstComplete };
}

// 퀴즈 화면 결과 반영
export async function recordQuizAnswer(user, { quiz, category, categoryLabel, chosen }) {
  const progress = await fetchLearnProgress(user);
  const now = new Date().toISOString();
  const key = `quiz-${quiz.quiz_id ?? quiz.question}`;
  const before = progress.wrong[key];

  if (chosen === quiz.answer) {
    if (!before || before.resolved) return progress;
    progress.wrong[key] = { ...before, resolved: true, resolvedAt: now };
  } else {
    progress.wrong[key] = {
      key,
      source: "quiz",
      typeKey: `quiz-${category}`,
      unitTitle: `${categoryLabel} 퀴즈`,
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

export async function answerWrongNote(user, key, chosen) {
  const progress = await fetchLearnProgress(user);
  const note = progress.wrong[key];
  if (!note) throw new Error("오답노트에서 문제를 찾을 수 없어요.");

  const correct = note.source === "quiz" ? chosen === note.answer : chosen === note.a;
  const now = new Date().toISOString();
  progress.wrong[key] = correct
    ? { ...note, resolved: true, resolvedAt: now }
    : { ...note, myAnswer: chosen, count: note.count + 1, lastAt: now };
  writeJson(userKey(user), progress);
  return { correct, progress };
}

export async function deleteWrongNote(user, key) {
  const progress = await fetchLearnProgress(user);
  delete progress.wrong[key];
  writeJson(userKey(user), progress);
  return progress;
}

// =============================================================
// 3. 계산 도우미
// =============================================================
export function isUnitUnlocked(units, index, progress) {
  if (index === 0) return true;
  const self = progress.units[units[index].id];
  if (self?.passed || self?.completed) return true;
  const prev = progress.units[units[index - 1].id];
  return Boolean(prev?.completed);
}

export function unitStatus(units, index, progress) {
  const p = progress.units[units[index].id];
  if (p?.completed) return "completed";
  if (p?.passed) return "writing";
  return isUnitUnlocked(units, index, progress) ? "open" : "locked";
}

export function summarizeProgress(content, progress) {
  return content.map((type) => {
    const done = type.units.filter((unit) => progress.units[unit.id]?.completed).length;
    const quizPassed = type.units.filter((unit) => progress.units[unit.id]?.passed).length;
    return { key: type.key, label: type.label, done, quizPassed, total: type.units.length };
  });
}

export function countOpenWrong(progress) {
  return Object.values(progress.wrong).filter((note) => !note.resolved).length;
}

// =============================================================
// 4. 백엔드 DB O/X 퀴즈 조회 함수 (관리자 수정 내용 우선 반영)
// =============================================================
export async function fetchOxQuizzes(category, unitId) {
  try {
    // 1순위: 관리자 페이지에서 수정하여 브라우저에 저장한 내용이 있는지 확인
    const overrides = readJson(CONTENT_KEY, {});
    
    // 가능한 모든 단원 ID 포맷을 정밀하게 유추하여 대조 (예: report-1, report-01 등)
    const possibleIds = [
      `${category}-${unitId}`,
      `${category}-${String(unitId).padStart(2, "0")}`,
      `${category}-${String(unitId).replace(/^0+/, "")}`
    ];

    for (const targetId of possibleIds) {
      if (overrides[targetId] && Array.isArray(overrides[targetId].quiz)) {
        return overrides[targetId].quiz;
      }
    }

    // 2순위: 수정된 내용이 없으면 기존처럼 백엔드 DB에서 가져오기
    const response = await fetch(`${API_URL}/api/learn/quizzes?category=${category}&unit_id=${unitId}`);
    if (!response.ok) {
      throw new Error("퀴즈를 불러오지 못했어요.");
    }
    return await response.json();
  } catch (error) {
    console.error("퀴즈 조회 에러:", error);
    return [];
  }
}