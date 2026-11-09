// =============================================================
// utils/scrollToElement.js — 화면 속 요소가 맨 위에 오도록 부드럽게 스크롤
// -------------------------------------------------------------
// ★ 왜 element.scrollIntoView()를 안 쓰는지
//   우리 화면의 바깥 상자(.sub-page)는 장식(배경 언덕)이 넘치지 않게 overflow: hidden 이 걸려 있음
//   scrollIntoView는 "스크롤할 수 있는 모든 상자"를 같이 움직이는데,
//   overflow: hidden 상자도 코드로는 스크롤이 돼서 .sub-page 안쪽 내용이 위로 밀려 올라가 버림
//   (위쪽 제목이 잘리고, 사용자는 다시 내릴 방법이 없음)
//   → 창(window)만 스크롤하도록 위치를 직접 계산해서 window.scrollTo를 씀
//
// 사용 예) scrollToElement(".learn-tabs")   ← CSS 선택자 또는 요소 자체
// =============================================================

// 헤더(위쪽 메뉴)에 가리지 않게 남겨 둘 여백(px)
const TOP_GAP = 90;

export default function scrollToElement(target) {
  // 글자(선택자)로 받으면 요소를 찾고, 요소로 받으면 그대로 씀
  const element = typeof target === "string" ? document.querySelector(target) : target;
  if (!element) return;

  // getBoundingClientRect().top: 지금 화면 맨 위에서 요소까지 거리
  // + window.scrollY(이미 내려온 만큼) = 페이지 맨 위에서 요소까지 거리
  const top = element.getBoundingClientRect().top + window.scrollY - TOP_GAP;
  // Math.max(0, …): 0보다 위로는 못 올라가게
  window.scrollTo({ top: Math.max(0, top), behavior: "smooth" });
}
