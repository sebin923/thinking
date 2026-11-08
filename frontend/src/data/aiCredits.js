// =============================================================
// data/aiCredits.js — 글쓰기 AI 이용권(추가 횟수) 상품 정보
// -------------------------------------------------------------
// 결제 화면(PaymentPage.jsx)이 이 값을 그대로 그림
//   → 가격·횟수를 바꾸고 싶으면 이 파일만 고치면 됨
//
// ★ 지금 숫자는 화면을 만들기 위한 "임시 값"
//   백엔드에서 횟수 제한·결제 API를 만들면, 같은 값을 서버에서도 쓰도록 맞추거나
//   서버에서 상품 목록을 받아오는 방식으로 바꾸기
//   (가격은 반드시 서버 기준으로 계산해야 함 → 화면 값은 조작될 수 있으니까)
// =============================================================

// 하루에 무료로 쓸 수 있는 글쓰기 AI 횟수
// (AI 초안 작성 · AI 피드백 및 수정 · 공통/개인화 LLM 초안을 모두 합쳐서 하루 3회)
// 횟수 세기는 api/aiUsage.js
export const FREE_DAILY_AI_USES = 3;

// 이용권 상품 목록
//  - id: 상품 구분 이름 (서버에 "이 상품 살게요"라고 보낼 때 쓸 값)
//  - count: 추가되는 AI 이용 횟수
//  - price: 가격(원)
//  - badge: 카드 위에 붙는 작은 이름표 (없으면 안 붙음)
export const CREDIT_PACKAGES = [
  { id: "ai_5", count: 5, price: 1000 }, // 1회 200원
  { id: "ai_30", count: 30, price: 5000, badge: "인기" }, // 1회 약 167원
  { id: "ai_50", count: 50, price: 8000, badge: "가장 저렴" }, // 1회 160원
];

// 숫자 → "2,500원" (toLocaleString: 세 자리마다 쉼표)
export function formatWon(price) {
  return `${price.toLocaleString("ko-KR")}원`;
}

// 1회당 가격 → "83원" (소수점은 반올림)
export function pricePerDraft(item) {
  return formatWon(Math.round(item.price / item.count));
}
