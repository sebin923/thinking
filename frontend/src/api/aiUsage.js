// =============================================================
// api/aiUsage.js — 글쓰기 AI 하루 무료 이용 횟수 관리
// -------------------------------------------------------------
// 글쓰기 화면의 AI 기능(AI 초안 작성 · AI 피드백 및 수정 · 공통 LLM 초안 · 개인화 LLM 초안)은
// 회원마다 하루 FREE_DAILY_AI_USES회(3회)까지 무료 → 다 쓰면 이용권 충전 안내
//   - 성공한 요청만 1회로 셈 (AI가 실패하면 횟수가 안 줄어듦)
//   - 날짜가 바뀌면(자정) 다시 3회
//   - 관리자 계정은 제한 없음 (테스트·운영용)
//
// ★ 지금은 백엔드가 없어서 브라우저 저장소(localStorage)에 셈
//   → 브라우저를 바꾸거나 저장소를 지우면 다시 3회가 됨 (진짜로 막으려면 서버에서 세야 함)
//   백엔드로 옮길 때 (예시)
//     GET  /api/ai-usage/today   → { used, limit, credits(충전한 남은 횟수) }
//     AI API(draft-ai, feedback-ai …)에서 서버가 직접 횟수를 확인하고, 넘으면 402/429 에러로 거절
//     → 그때는 이 파일 함수 "안쪽"만 서버 요청으로 바꾸면 됨
//   충전한 이용권(결제) 횟수도 서버가 생기면 "무료 3회를 다 쓴 뒤 이용권에서 1회씩 차감"으로 붙이면 됨
// =============================================================

import { FREE_DAILY_AI_USES } from "../data/aiCredits";

const USAGE_PREFIX = "saenggak-hanjul-ai-usage:"; // 뒤에 user_id가 붙음

function usageKey(user) {
  return USAGE_PREFIX + (user?.user_id ?? user?.login_id ?? "guest");
}

// 오늘 날짜 "2026-11-06" (사용자 컴퓨터 시간 기준)
// sv-SE(스웨덴) 날짜 형식이 마침 "연-월-일" 모양이라 이걸 씀
function today() {
  return new Date().toLocaleDateString("sv-SE");
}

// 관리자는 제한 없음
function isUnlimited(user) {
  return user?.role === "admin";
}

// 오늘 사용 현황
// 돌려주는 값: { used: 오늘 쓴 횟수, limit: 하루 무료 횟수, remaining: 남은 횟수, unlimited: 제한 없는지 }
export function getAiUsage(user) {
  const limit = FREE_DAILY_AI_USES;
  if (isUnlimited(user)) return { used: 0, limit, remaining: Infinity, unlimited: true };

  let used = 0;
  try {
    const saved = JSON.parse(localStorage.getItem(usageKey(user)) || "null");
    // 저장된 날짜가 오늘이면 그 횟수, 어제 이전이면 0부터 (= 날짜가 바뀌면 초기화)
    if (saved?.date === today()) used = Number(saved.used) || 0;
  } catch {
    used = 0;
  }
  return { used, limit, remaining: Math.max(0, limit - used), unlimited: false };
}

// AI를 1회 썼다고 기록 (AI 요청이 성공한 뒤에 부름)
// 돌려주는 값: 기록 후 사용 현황 (getAiUsage와 같은 모양)
export function recordAiUse(user) {
  if (isUnlimited(user)) return getAiUsage(user);
  const { used } = getAiUsage(user);
  try {
    localStorage.setItem(usageKey(user), JSON.stringify({ date: today(), used: used + 1 }));
  } catch {
    // 저장에 실패해도 글쓰기는 계속할 수 있게 조용히 넘어감
  }
  return getAiUsage(user);
}
