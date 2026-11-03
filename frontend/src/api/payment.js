// =============================================================
// api/payment.js — 결제 관련 백엔드 API 호출
// -------------------------------------------------------------
// ★ 백엔드에 아직 없는 API (백엔드 담당이 만들어야 함)
//
//   POST /api/payments/confirm   (로그인 필요: Authorization: Bearer 토큰)
//     보내는 값: { paymentKey, orderId, amount }  ← 토스페이먼츠가 성공 주소에 붙여 준 값 그대로
//     서버가 할 일:
//       1) amount가 진짜 상품 가격과 같은지 서버 기준으로 다시 확인 (화면 값은 조작될 수 있음)
//       2) 토스페이먼츠 결제 승인 API 호출
//            POST https://api.tosspayments.com/v1/payments/confirm
//            헤더 Authorization: Basic base64("시크릿키:")   ← 시크릿 키 뒤에 콜론(:) 붙여서 인코딩
//            본문 { paymentKey, orderId, amount }
//       3) 승인되면 그 회원의 AI 초안 이용권 횟수를 늘리고 결제 기록 저장
//     돌려주는 값(예시): { message, added_count, remaining_count }
//
//   ★ 결제 승인을 안 하면 결제가 완료되지 않음 (결제창에서 인증만 된 상태로 끝남)
// =============================================================

const API_URL = import.meta.env.VITE_API_URL || "http://127.0.0.1:8000";

// 결제 승인 요청
// 실패하면 Error를 던짐 → error.status에 응답 번호(404면 "아직 API 없음")를 넣어 둠
export async function confirmPayment(token, { paymentKey, orderId, amount }) {
  let response;
  try {
    response = await fetch(`${API_URL}/api/payments/confirm`, {
      method: "POST",
      headers: {
        "Content-Type": "application/json",
        Authorization: `Bearer ${token}`,
      },
      body: JSON.stringify({ paymentKey, orderId, amount }),
    });
  } catch {
    throw new Error("서버에 연결할 수 없어요. 잠시 후 다시 시도해 주세요.");
  }

  const data = await response.json().catch(() => ({}));
  if (!response.ok) {
    const error = new Error(typeof data.detail === "string" ? data.detail : "결제 승인에 실패했어요.");
    error.status = response.status;
    throw error;
  }
  return data;
}
