// =============================================================
// utils/tossPayments.js — 토스페이먼츠 결제창 준비 도구 모음
// -------------------------------------------------------------
// 토스페이먼츠 결제창(SDK v2)을 쓰려면 토스페이먼츠가 제공하는 스크립트를 불러와야 함
//   → npm으로 따로 설치하지 않고, 결제하기를 누를 때만 공식 주소에서 스크립트를 불러옴
//     (팀원들이 npm install을 다시 할 필요가 없고, 결제 화면을 안 쓰는 사람은 스크립트를 안 받음)
//
// ★ 필요한 설정: frontend/.env 파일에 클라이언트 키 넣기
//     VITE_TOSS_CLIENT_KEY=test_ck_...
//   - 토스페이먼츠 개발자센터(developers.tosspayments.com) → API 키 메뉴에서 확인
//   - "test_"로 시작하는 테스트 키는 결제창이 떠도 실제로 돈이 나가지 않음
//   - 클라이언트 키는 화면(브라우저)에 들어가도 되는 키라서 프론트에 둬도 괜찮음
//   - ★ 시크릿 키(test_sk_... / live_sk_...)는 절대 프론트에 넣으면 안 됨 → 백엔드 .env에만!
//   - .env를 고친 뒤에는 npm run dev를 껐다 켜야 값이 반영됨
// =============================================================

// 토스페이먼츠 SDK v2 공식 스크립트 주소
const TOSS_SCRIPT_URL = "https://js.tosspayments.com/v2/standard";

// .env의 클라이언트 키 (없으면 빈 문자열 → 결제 화면에서 "키가 없어요" 안내)
export const TOSS_CLIENT_KEY = import.meta.env.VITE_TOSS_CLIENT_KEY || "";

// 결제가 끝나면 토스페이먼츠가 돌려보내 줄 우리 사이트 주소
// window.location.origin: 지금 사이트의 "http://localhost:5173" 같은 앞부분
//   → 개발할 때도, 배포한 뒤에도 알아서 맞는 주소가 됨
// 토스페이먼츠가 이 주소 뒤에 ?paymentKey=...&orderId=...&amount=... (실패면 ?code=...&message=...)를 붙여 줌
export const PAYMENT_SUCCESS_PATH = "/payment/success";
export const PAYMENT_FAIL_PATH = "/payment/fail";

// 결제를 시작하기 직전에 "이 주문을 결제하러 갔다"는 정보를 잠깐 저장해 두는 이름표
// (결제창에서 돌아왔을 때 금액·주문번호가 우리가 보낸 것과 같은지 확인하는 데 씀)
const PENDING_ORDER_KEY = "saenggak-hanjul-pending-order";

// 스크립트를 한 번만 불러오도록 기억해 두는 곳 (두 번 누르면 두 번 불러오지 않게)
let scriptPromise = null;

// ----- 토스페이먼츠 스크립트 불러오기 -----
// 돌려주는 값: window.TossPayments 함수 (TossPayments(클라이언트키)로 결제 객체를 만듦)
export function loadTossPayments() {
  // 이미 불러와져 있으면 바로 돌려줌
  if (window.TossPayments) return Promise.resolve(window.TossPayments);
  if (scriptPromise) return scriptPromise;

  // new Promise: "스크립트가 다 불러와지면 알려 줄게"라는 약속을 만듦
  scriptPromise = new Promise((resolve, reject) => {
    const script = document.createElement("script"); // <script> 태그를 새로 만들어서
    script.src = TOSS_SCRIPT_URL;
    script.async = true;
    script.onload = () => {
      if (window.TossPayments) resolve(window.TossPayments);
      else reject(new Error("토스페이먼츠 결제창을 불러오지 못했어요."));
    };
    script.onerror = () => {
      scriptPromise = null; // 실패했으면 다음에 다시 시도할 수 있게 비워 둠
      reject(new Error("토스페이먼츠 결제창을 불러오지 못했어요. 인터넷 연결을 확인해 주세요."));
    };
    document.head.appendChild(script); // <head>에 붙이는 순간 브라우저가 스크립트를 받기 시작함
  });
  return scriptPromise;
}

// ----- 주문번호 만들기 -----
// 토스페이먼츠 규칙: 영문·숫자·-·_·= 로만 된 6~64자, 주문마다 달라야 함
// crypto.randomUUID(): 겹칠 일이 거의 없는 무작위 값 (예: "3f2a...-...") → "hanjul-3f2a..." (43자)
// ★ 원래는 서버가 주문을 만들고 주문번호를 정해 주는 게 더 안전함 (백엔드 생기면 그쪽으로 옮기기)
export function makeOrderId() {
  return `hanjul-${crypto.randomUUID()}`;
}

// ----- 결제하러 가기 전 주문 정보 저장 / 꺼내기 / 지우기 -----
// sessionStorage: 탭을 닫으면 사라지는 저장소 (결제창에 갔다가 같은 탭으로 돌아오니까 이걸로 충분)
// try/catch: 사생활 보호 모드 등에서 저장소를 못 쓰면 에러가 나서 → 조용히 넘어감
export function savePendingOrder(order) {
  try {
    sessionStorage.setItem(PENDING_ORDER_KEY, JSON.stringify(order));
  } catch {
    // 저장 못 해도 결제는 진행 (돌아왔을 때 확인만 못 함)
  }
}

export function readPendingOrder() {
  try {
    const raw = sessionStorage.getItem(PENDING_ORDER_KEY);
    return raw ? JSON.parse(raw) : null;
  } catch {
    return null;
  }
}

export function clearPendingOrder() {
  try {
    sessionStorage.removeItem(PENDING_ORDER_KEY);
  } catch {
    // 무시
  }
}

// ----- 지금 주소가 결제창에서 돌아온 주소인지 확인 -----
// 결제가 끝나면 토스페이먼츠가 /payment/success?... 또는 /payment/fail?... 로 보내 줌
// 돌려주는 값:
//   성공 → { kind: "success", paymentKey, orderId, amount }
//   실패 → { kind: "fail", code, message, orderId }
//   둘 다 아니면 → null (평소처럼 홈 화면)
export function readPaymentReturn() {
  const { pathname, search } = window.location;
  // URLSearchParams: "?a=1&b=2"를 get("a")로 꺼낼 수 있게 해 주는 도구
  const params = new URLSearchParams(search);

  if (pathname === PAYMENT_SUCCESS_PATH) {
    return {
      kind: "success",
      paymentKey: params.get("paymentKey") || "",
      orderId: params.get("orderId") || "",
      amount: Number(params.get("amount")), // 주소의 값은 글자라서 숫자로 바꿈
    };
  }
  if (pathname === PAYMENT_FAIL_PATH) {
    return {
      kind: "fail",
      code: params.get("code") || "",
      message: params.get("message") || "",
      orderId: params.get("orderId") || "",
    };
  }
  return null;
}
