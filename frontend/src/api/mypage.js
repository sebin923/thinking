// =============================================================
// api/mypage.js — 마이페이지 API 호출 모음
// -------------------------------------------------------------
// 화면(MyPage.jsx, MyPageEdit.jsx)에서는 fetch를 직접 쓰지 않고 여기 함수만 부름
// → 서버 주소나 에러 처리 방식이 바뀌어도 이 파일 하나만 고치면 됨
//
// ★ 마이페이지 API는 전부 "로그인한 사람만" 쓸 수 있어서
//   요청 헤더에 "Authorization: Bearer 토큰"을 꼭 붙여서 보냄
//   (서버는 이 토큰을 보고 누가 보낸 요청인지 알아냄)
// =============================================================

// 백엔드 주소 (frontend/.env의 VITE_API_URL이 있으면 그 값, 없으면 기본값)
const API_URL = import.meta.env.VITE_API_URL || "http://127.0.0.1:8000";

// ----- 서버 에러 응답에서 사람이 읽을 문구만 꺼내기 -----
// FastAPI는 에러를 두 가지 모양으로 보냄
//  1) { detail: "현재 비밀번호가 올바르지 않아요." }            ← 우리가 직접 만든 에러
//  2) { detail: [{ msg: "Value error, 이름은 2~20자로..." }] } ← 입력값 검사(Pydantic) 에러
function readErrorMessage(data) {
  if (typeof data.detail === "string") return data.detail;
  if (Array.isArray(data.detail) && data.detail.length > 0) {
    // "Value error, " 같은 앞부분은 사용자한테 필요 없으니 지움
    return String(data.detail[0].msg || "").replace(/^Value error,\s*/, "") || "입력값을 확인해 주세요.";
  }
  return "요청에 실패했어요. 잠시 후 다시 시도해 주세요.";
}

// ----- 공통 요청 함수 -----
// path: "/api/mypage/profile" 같은 주소 뒷부분
// token: 로그인할 때 받은 토큰
// method: "GET"(조회) / "PUT"(수정) / "POST"(만들기·실행)
// body: 서버로 보낼 데이터 (객체) → JSON 글자로 바꿔서 보냄
async function request(path, token, { method = "GET", body } = {}) {
  // 헤더: 요청에 붙이는 추가 정보
  const headers = { Authorization: `Bearer ${token}` };
  if (body) headers["Content-Type"] = "application/json"; // "보내는 데이터는 JSON이에요"라고 알려줌

  let response;
  try {
    response = await fetch(`${API_URL}${path}`, {
      method,
      headers,
      body: body ? JSON.stringify(body) : undefined, // 객체 → JSON 글자
    });
  } catch {
    // fetch 자체가 실패 = 서버가 꺼져 있거나 주소가 틀림
    throw new Error("서버에 연결할 수 없어요. 백엔드가 켜져 있는지 확인해 주세요.");
  }

  // 응답 본문을 JSON으로 읽기 (비어 있으면 빈 객체)
  const data = await response.json().catch(() => ({}));

  if (!response.ok) {
    const error = new Error(readErrorMessage(data));
    // status: HTTP 상태 번호 (401이면 "로그인이 풀림" → 화면에서 다시 로그인하라고 안내)
    error.status = response.status;
    throw error;
  }
  return data;
}

// ===================== 마이페이지 (보기) =====================

// 내 프로필 + 활동 요약 (글 수, 완료 글 수, 도전 최고 기록)
export function fetchMyProfile(token) {
  return request("/api/mypage/profile", token);
}

// 내가 쓴 글 목록 (최근 수정한 글부터, 미리보기 포함)
export function fetchMyDocuments(token) {
  return request("/api/mypage/documents", token);
}

// 글 하나의 저장본 목록 (팀원이 만든 글쓰기 API를 그대로 사용, 최신 버전이 맨 앞)
// → 목록에서 글을 펼쳤을 때 본문 전체를 보여주는 데 씀
export function fetchDocumentDrafts(token, documentId) {
  return request(`/api/documents/${documentId}/drafts`, token);
}

// 쓰다 만 글 지우기 (한 번도 저장 안 한 글만 서버가 지워 줌, 저장한 글은 거절)
// 글쓰기 화면을 떠날 때 App이 부름
// keepalive: true → 탭을 닫거나 새로고침해서 페이지가 사라지는 순간에도 요청이 끝까지 전송됨
// (결과를 기다릴 수 없는 상황에서 부르니까, 실패해도 화면에는 아무 영향 없게 에러는 그냥 무시)
export function discardUnsavedDocument(token, documentId) {
  fetch(`${API_URL}/api/mypage/documents/${documentId}`, {
    method: "DELETE",
    headers: { Authorization: `Bearer ${token}` },
    keepalive: true,
  }).catch(() => {});
}

// 저장한 글 삭제 (마이페이지 글 목록의 "삭제" 버튼)
// ★ 백엔드 담당에게 요청할 API: DELETE /api/documents/{document_id}
//   - 로그인한 사람 본인 글만 지울 수 있게 (남의 글이면 404)
//   - 지우는 순서: AI 피드백 → 저장본(drafts) → 생각(thoughts) → 글(documents)
//   - 성공하면 200 + { "message": "..." }
//   아직 서버에 이 API가 없으면 FastAPI가 404 "Not Found"(또는 405)를 돌려줌
//   → 그 경우는 아래에서 알아보기 쉬운 문구로 바꿔서 화면에 보여줌
export async function deleteDocument(token, documentId) {
  try {
    return await request(`/api/documents/${documentId}`, token, { method: "DELETE" });
  } catch (error) {
    // 404 "Not Found": 주소 자체가 없음(서버에 API가 아직 없음) / 405: 주소는 있는데 DELETE를 안 받음
    // (백엔드가 만든 진짜 404는 "글을 찾을 수 없어요." 같은 우리말 문구라서 구분됨)
    if (error.status === 405 || (error.status === 404 && error.message === "Not Found")) {
      const notReady = new Error("아직 서버에 글 삭제 기능이 준비되지 않았어요.");
      notReady.status = error.status;
      throw notReady;
    }
    throw error;
  }
}

// ===================== 마이페이지 수정 =====================

// 회원정보 수정 (이름, 전화번호, 이메일)
// 이메일을 바꿀 때는 api/auth.js의 sendEmailCode → verifyEmailCode로 새 이메일 인증을 먼저 마쳐야 함
export function updateMyProfile(token, { name, phone, email }) {
  return request("/api/mypage/profile", token, { method: "PUT", body: { name, phone, email } });
}

// 비밀번호 변경
export function changeMyPassword(token, currentPassword, newPassword) {
  return request("/api/mypage/password", token, {
    method: "PUT",
    body: { current_password: currentPassword, new_password: newPassword },
  });
}

// 회원 탈퇴 (비밀번호를 한 번 더 확인)
export function withdrawAccount(token, password) {
  return request("/api/mypage/withdraw", token, { method: "POST", body: { password } });
}
