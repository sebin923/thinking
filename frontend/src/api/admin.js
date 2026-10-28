// =============================================================
// api/admin.js — 관리자 페이지 API 호출 모음
// -------------------------------------------------------------
// 화면(AdminPage.jsx)에서는 fetch를 직접 쓰지 않고 여기 함수만 부름
// → 서버 주소나 에러 처리 방식이 바뀌어도 이 파일 하나만 고치면 됨
//
// ★ 관리자 API는 전부 "관리자만" 쓸 수 있어서
//   요청 헤더에 "Authorization: Bearer 토큰"을 꼭 붙여서 보냄
//   (서버가 토큰으로 누구인지 확인하고, 관리자가 아니면 403으로 거절)
//
// 서버 쪽 코드: backend/routers/admin.py
// =============================================================

// 백엔드 주소 (frontend/.env의 VITE_API_URL이 있으면 그 값, 없으면 기본값)
const API_URL = import.meta.env.VITE_API_URL || "http://127.0.0.1:8000";

// ----- 서버 에러 응답에서 사람이 읽을 문구만 꺼내기 -----
// FastAPI는 에러를 두 가지 모양으로 보냄
//  1) { detail: "관리자만 이용할 수 있어요." }                  ← 우리가 직접 만든 에러
//  2) { detail: [{ msg: "Value error, 보기는 2개 이상..." }] } ← 입력값 검사(Pydantic) 에러
function readErrorMessage(data) {
  if (typeof data.detail === "string") return data.detail;
  if (Array.isArray(data.detail) && data.detail.length > 0) {
    // "Value error, " 같은 앞부분은 사용자한테 필요 없으니 지움
    return String(data.detail[0].msg || "").replace(/^Value error,\s*/, "") || "입력값을 확인해 주세요.";
  }
  return "요청에 실패했어요. 잠시 후 다시 시도해 주세요.";
}

// ----- 공통 요청 함수 -----
// path: "/api/admin/users" 같은 주소 뒷부분
// method: "GET"(조회) / "POST"(추가) / "PUT"(수정) / "PATCH"(일부 수정) / "DELETE"(삭제)
// body: 서버로 보낼 데이터 (객체) → JSON 글자로 바꿔서 보냄
// params: 주소 뒤에 붙일 검색 조건 { q: "민수" } → "?q=민수"
async function request(path, token, { method = "GET", body, params } = {}) {
  // URLSearchParams: 객체를 "?키=값&키=값" 모양으로 바꿔 주는 도구 (한글도 안전하게 바꿔 줌)
  // 값이 비어 있는 조건은 빼고 보냄 (예: 검색어를 안 썼으면 q를 아예 안 붙임)
  const query = new URLSearchParams(
    Object.entries(params || {}).filter(([, value]) => value !== undefined && value !== null && value !== "")
  ).toString();

  const headers = { Authorization: `Bearer ${token}` };
  if (body) headers["Content-Type"] = "application/json"; // "보내는 데이터는 JSON이에요"

  let response;
  try {
    response = await fetch(`${API_URL}${path}${query ? `?${query}` : ""}`, {
      method,
      headers,
      body: body ? JSON.stringify(body) : undefined,
    });
  } catch {
    // fetch 자체가 실패 = 서버가 꺼져 있거나 주소가 틀림
    throw new Error("서버에 연결할 수 없어요. 백엔드가 켜져 있는지 확인해 주세요.");
  }

  const data = await response.json().catch(() => ({}));
  if (!response.ok) {
    const error = new Error(readErrorMessage(data));
    // status: 401이면 로그인이 풀림, 403이면 관리자가 아님 → 화면에서 구분해서 안내
    error.status = response.status;
    throw error;
  }
  return data;
}

// ===================== 1. 퀴즈 관리 =====================

// 퀴즈 목록 (category: "spelling" 맞춤법 / "grammar" 문법)
export function fetchAdminQuizzes(token, category) {
  return request("/api/admin/quizzes", token, { params: { category } });
}

// 퀴즈 추가 → quiz: { category, question, options: [...], answer, explanation }
export function createQuiz(token, quiz) {
  return request("/api/admin/quizzes", token, { method: "POST", body: quiz });
}

// 퀴즈 수정 (추가와 같은 모양으로 보냄)
export function updateQuiz(token, quizId, quiz) {
  return request(`/api/admin/quizzes/${quizId}`, token, { method: "PUT", body: quiz });
}

// 퀴즈 삭제 (그 문제를 푼 기록도 서버에서 같이 지워짐)
export function deleteQuiz(token, quizId) {
  return request(`/api/admin/quizzes/${quizId}`, token, { method: "DELETE" });
}

// ===================== 2. 회원 관리 =====================

// 회원 목록 → filters: { q: 검색어, status: "active" | "suspended" | "" }
export function fetchAdminUsers(token, filters) {
  return request("/api/admin/users", token, { params: filters });
}

// 이용 상태 바꾸기 (status: "active" 정상 / "suspended" 정지) → 바뀐 회원 한 줄을 돌려줌
export function changeUserStatus(token, userId, status) {
  return request(`/api/admin/users/${userId}/status`, token, { method: "PATCH", body: { status } });
}

// ===================== 3. 랭킹 관리 =====================

// 도전 기록 전체 (점수 높은 순)
export function fetchAdminRankings(token, category = "spelling") {
  return request("/api/admin/rankings", token, { params: { category } });
}

// 도전 기록 하나 삭제
export function deleteRanking(token, rankingId) {
  return request(`/api/admin/rankings/${rankingId}`, token, { method: "DELETE" });
}
