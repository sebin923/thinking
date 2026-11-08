// =============================================================
// api/aiRating.js — AI 결과(초안·피드백) 별점 평가 저장
// -------------------------------------------------------------
// 글쓰기 화면에서 AI 초안 / AI 피드백을 받은 뒤 사용자가 매긴 별점(1~5)과 한 줄 의견을 저장
//
// ★ 지금은 백엔드 API가 없어서 브라우저 저장소(localStorage)에 저장함 (회원별로 따로)
//   백엔드가 생기면 saveAiRating 함수 "안쪽"만 fetch로 바꾸면 되고, 화면 코드는 그대로 두면 됨
//
// 백엔드로 옮길 때 필요한 API (예시)
//   POST /api/ai-ratings   (로그인 필요)
//     보내는 값: { kind, model, rating, comment, document_id, result_text, request_text }
//       kind        : "draft"(AI 초안) / "feedback"(AI 피드백)
//       model       : "clova"(CLOVA) / "common"(공통 LLM) / "personal"(개인화 LLM)
//       rating      : 별점 1~5
//       comment     : 한 줄 의견 (없으면 빈 칸)
//       result_text : AI가 만든 결과 (초안 글 또는 피드백 요약)
//       request_text: AI에게 보낸 원래 글 (초안 요청 때의 본문)
//   ★ 이 데이터는 나중에 Qwen 학습 때 "사람이 좋다고 한 결과 / 별로라고 한 결과" 데이터로 쓸 수 있음
// =============================================================

const RATING_PREFIX = "saenggak-hanjul-ai-ratings:"; // 뒤에 user_id가 붙음
const MAX_SAVED = 200; // 브라우저에는 최근 200개까지만 보관 (저장 공간이 넘치지 않게)

function ratingKey(user) {
  return RATING_PREFIX + (user?.user_id ?? user?.login_id ?? "guest");
}

// 내 평가 목록 가져오기 (최근 것이 앞)
export async function fetchAiRatings(user) {
  try {
    const raw = localStorage.getItem(ratingKey(user));
    return raw ? JSON.parse(raw) : [];
  } catch {
    return [];
  }
}

// 평가 하나 저장
// rating: { kind, model, rating, comment, documentId, resultText, requestText }
// 돌려주는 값: 저장한 평가 (id·저장 시각 포함)
export async function saveAiRating(user, rating) {
  // 별점은 1~5 정수만 (화면에서도 막지만 한 번 더 확인)
  if (!Number.isInteger(rating.rating) || rating.rating < 1 || rating.rating > 5) {
    throw new Error("별점을 1~5개 중에서 골라 주세요.");
  }

  const saved = {
    // id: 저장 시각 + 무작위 글자 (겹치지 않게)
    id: `${Date.now()}-${Math.random().toString(36).slice(2, 8)}`,
    kind: rating.kind,
    model: rating.model,
    rating: rating.rating,
    comment: (rating.comment || "").trim(),
    documentId: rating.documentId ?? null,
    // 결과 글이 너무 길면 저장 공간을 많이 차지해서 앞부분 2000자만 보관
    resultText: (rating.resultText || "").slice(0, 2000),
    requestText: (rating.requestText || "").slice(0, 2000),
    createdAt: new Date().toISOString(),
  };

  const list = await fetchAiRatings(user);
  // 새 평가를 맨 앞에 넣고, 최근 MAX_SAVED개만 남김
  const next = [saved, ...list].slice(0, MAX_SAVED);
  try {
    localStorage.setItem(ratingKey(user), JSON.stringify(next));
  } catch {
    throw new Error("평가를 저장하지 못했어요. 잠시 후 다시 시도해 주세요.");
  }
  return saved;
}
