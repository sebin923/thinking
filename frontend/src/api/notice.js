// =============================================================
// api/notice.js — 공지사항 보기 API (로그인 안 해도 누구나)
// -------------------------------------------------------------
// 화면(NoticePage.jsx)에서는 fetch를 직접 쓰지 않고 여기 함수만 부름
// 공지 등록·수정·삭제는 관리자만 할 수 있어서 api/admin.js에 따로 있음
//
// 서버 쪽 코드: backend/routers/notice.py
// =============================================================

// 백엔드 주소 (frontend/.env의 VITE_API_URL이 있으면 그 값, 없으면 기본값)
const API_URL = import.meta.env.VITE_API_URL || "http://127.0.0.1:8000";

// 공지 목록 (고정 공지가 맨 위 → 그다음 최신 순, 서버가 정렬해서 보내 줌)
// 돌려주는 값: [{ notice_id, title, content, is_pinned, created_at, updated_at }, ...]
export async function fetchNotices() {
  let response;
  try {
    response = await fetch(`${API_URL}/api/notices`);
  } catch {
    // fetch 자체가 실패 = 서버가 꺼져 있거나 주소가 틀림
    throw new Error("서버에 연결할 수 없어요. 잠시 후 다시 시도해 주세요.");
  }

  // .catch(() => []): 응답이 JSON이 아니어도 화면이 멈추지 않게
  const data = await response.json().catch(() => []);
  if (!response.ok) {
    throw new Error(typeof data.detail === "string" ? data.detail : "공지사항을 불러오지 못했어요.");
  }
  return data;
}
