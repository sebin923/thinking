// =============================================================
// admin/adminFormat.js — 관리자 페이지 탭들이 같이 쓰는 "글자 모양 맞추기" 함수
// -------------------------------------------------------------
// 예전에는 탭마다 날짜를 다르게 보여줬음
//   퀴즈·회원·랭킹: "2026.11.18" / 학습 데이터: "2026. 11. 18. 오후 2:05:33" / 별점: 서버 글자 그대로
// → 모든 탭이 이 파일의 함수를 써서 똑같은 모양으로 보여주게 함
// (컴포넌트가 아닌 함수만 모아 둔 파일이라 .js — 화면 부품은 AdminShared.jsx)
// =============================================================

// 날짜 글자/숫자 → Date (잘못된 값이면 null)
function toDate(value) {
  if (!value) return null;
  const date = new Date(value);
  // getTime()이 NaN이면 날짜로 못 읽은 것 (예: 빈 글자, 이상한 글자)
  return Number.isNaN(date.getTime()) ? null : date;
}

// 한 자리 숫자 앞에 0 붙이기 (3 → "03")
const two = (number) => String(number).padStart(2, "0");

// ----- 날짜만: "2026.11.18" (목록의 등록일·가입일 등) -----
export function formatDate(value) {
  const date = toDate(value);
  if (!date) return "-";
  // getMonth()는 0부터 시작해서 +1
  return `${date.getFullYear()}.${two(date.getMonth() + 1)}.${two(date.getDate())}`;
}

// ----- 날짜 + 시각: "2026.11.18 14:05" (평가 일시·검토 이력처럼 시간까지 필요할 때) -----
export function formatDateTime(value) {
  const date = toDate(value);
  if (!date) return "-";
  return `${formatDate(date)} ${two(date.getHours())}:${two(date.getMinutes())}`;
}
