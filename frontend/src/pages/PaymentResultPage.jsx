// =============================================================
// PaymentResultPage.jsx — 토스페이먼츠 결제창에서 돌아왔을 때 보여주는 화면
// -------------------------------------------------------------
// 결제창에서 결제가 끝나면 토스페이먼츠가 우리 사이트로 돌려보내 줌
//   성공: /payment/success?paymentKey=...&orderId=...&amount=...
//   실패: /payment/fail?code=...&message=...&orderId=...
// App.jsx가 처음 켜질 때 주소를 보고 이 화면을 띄움 (utils/tossPayments.js의 readPaymentReturn)
//
// 성공으로 돌아왔을 때 할 일
//   1) 주소의 orderId·amount가 결제하러 가기 전에 저장해 둔 주문과 같은지 확인 (중간에 바뀐 값 막기)
//   2) 백엔드에 "결제 승인" 요청 → 서버가 토스페이먼츠에 최종 승인 + 이용권 횟수 추가
//      ★ 이 승인까지 해야 결제가 진짜로 완료됨
// =============================================================

import { useEffect, useRef, useState } from "react";
// CheckCircle2: 성공, XCircle: 실패, Loader2: 승인 중, AlertTriangle: 확인 필요
import { CheckCircle2, XCircle, Loader2, AlertTriangle } from "lucide-react";

import PageHero from "../components/PageHero";
import { confirmPayment } from "../api/payment";
import { readPendingOrder, clearPendingOrder } from "../utils/tossPayments";
import { formatWon } from "../data/aiCredits";
// 로딩 아이콘이 도는 .spin 클래스가 들어 있는 파일
import "../components/AuthLayout.css";
import "./PaymentPage.css";

// ----- 처음 화면 상태 정하기 (화면이 처음 만들어질 때 한 번만 실행) -----
// 돌려주는 값: { status, title, detail, order }
//  status 종류
//   "confirming" : 승인 요청 중 (이 경우에만 서버에 요청을 보냄)
//   "done"       : 결제 완료
//   "noServer"   : 결제창 인증은 끝났는데 백엔드 승인 API가 아직 없음
//   "error"      : 승인 실패 / 주문 정보 불일치
//   "canceled"   : 사용자가 결제창을 닫음
//   "failed"     : 결제창에서 실패
//   "login"      : 로그인이 풀려 있어서 승인 요청을 못 보냄
function initialState(result, token) {
  if (result.kind === "fail") {
    // PAY_PROCESS_CANCELED: 사용자가 결제를 취소했을 때 토스페이먼츠가 보내는 코드
    if (result.code === "PAY_PROCESS_CANCELED") {
      return { status: "canceled", title: "결제를 취소했어요", detail: "언제든지 다시 충전할 수 있어요." };
    }
    return {
      status: "failed",
      title: "결제에 실패했어요",
      detail: result.message || "잠시 후 다시 시도해 주세요.",
    };
  }

  // ----- 성공 주소로 돌아온 경우 -----
  const order = readPendingOrder(); // 결제하러 가기 전에 저장해 둔 주문
  if (!result.paymentKey || !result.orderId || !Number.isFinite(result.amount)) {
    return { status: "error", title: "결제 정보를 확인할 수 없어요", detail: "결제 화면에서 다시 시도해 주세요." };
  }
  // 우리가 보낸 주문번호·금액과 돌아온 값이 다르면 승인하지 않음 (주소를 조작한 경우 등)
  if (!order || order.orderId !== result.orderId || order.amount !== result.amount) {
    return {
      status: "error",
      title: "주문 정보가 맞지 않아요",
      detail: "결제를 승인하지 않았어요. 결제 화면에서 다시 시도해 주세요.",
    };
  }
  if (!token) {
    return {
      status: "login",
      title: "로그인이 필요해요",
      detail: "로그인이 풀려서 결제를 마무리하지 못했어요. 다시 로그인한 뒤 결제해 주세요.",
      order,
    };
  }
  return { status: "confirming", title: "결제를 마무리하는 중이에요", detail: "창을 닫지 말고 잠시만 기다려 주세요.", order };
}

// props
//  - result: readPaymentReturn()이 돌려준 값 (성공/실패 정보)
//  - auth: 로그인 정보 (승인 요청에 토큰이 필요)
//  - onNavigate: 버튼으로 다른 화면 이동 (App의 handleNavigate)
function PaymentResultPage({ result, auth, onNavigate }) {
  // useState(함수): 처음 한 번만 함수를 실행해서 시작 값을 정함
  const [state, setState] = useState(() => initialState(result, auth?.token));

  // 승인 요청을 이미 보냈는지 (개발 모드에서 화면이 두 번 실행돼도 두 번 승인하지 않게)
  const requestedRef = useRef(false);

  // ----- 승인 요청 (status가 confirming일 때 한 번만) -----
  useEffect(() => {
    if (state.status !== "confirming" || requestedRef.current) return;
    requestedRef.current = true;

    confirmPayment(auth.token, {
      paymentKey: result.paymentKey,
      orderId: result.orderId,
      amount: result.amount,
    })
      .then((data) => {
        clearPendingOrder(); // 끝난 주문은 지움
        setState({
          status: "done",
          title: "충전이 완료됐어요",
          detail: data.message || `AI 초안 ${state.order.count}회가 추가됐어요.`,
          order: state.order,
        });
      })
      .catch((err) => {
        if (err.status === 404) {
          // 백엔드에 /api/payments/confirm 이 아직 없음
          setState({
            status: "noServer",
            title: "결제창 인증까지 완료됐어요",
            detail:
              "결제 승인 서버(백엔드)가 아직 준비되지 않아서 여기서 멈췄어요.\n승인하지 않은 결제는 완료되지 않아요.",
            order: state.order,
          });
          return;
        }
        setState({ status: "error", title: "결제 승인에 실패했어요", detail: err.message, order: state.order });
      });
  }, [state, auth, result]);

  // 상태별 아이콘
  const icon =
    state.status === "confirming" ? (
      <Loader2 size={44} className="spin" />
    ) : state.status === "done" ? (
      <CheckCircle2 size={44} />
    ) : state.status === "noServer" || state.status === "login" ? (
      <AlertTriangle size={44} />
    ) : (
      <XCircle size={44} />
    );

  return (
    <div className="sub-page">
      <div className="sub-page-inner">
        <PageHero eyebrow="AI 이용권" title="결제 결과" description="토스페이먼츠 결제 결과를 확인해요." memoText={"충전\n결과\n확인"} />

        <section className={`panel pay-result-card is-${state.status}`} role="status">
          <div className="pay-result-icon">{icon}</div>
          <h2>{state.title}</h2>
          <p className="pay-result-detail">{state.detail}</p>

          {/* 주문 내용 (주문 정보가 있을 때만) */}
          {state.order && (
            <dl className="pay-result-order">
              <div>
                <dt>상품</dt>
                <dd>AI 초안 {state.order.count}회</dd>
              </div>
              <div>
                <dt>결제 금액</dt>
                <dd>{formatWon(state.order.amount)}</dd>
              </div>
              <div>
                <dt>주문번호</dt>
                <dd className="pay-order-id">{state.order.orderId}</dd>
              </div>
            </dl>
          )}

          {/* 승인 중에는 버튼을 숨김 (중간에 다른 화면으로 가지 않게) */}
          {state.status !== "confirming" && (
            <div className="pay-result-buttons">
              {state.status === "done" ? (
                <button type="button" className="btn-primary" onClick={() => onNavigate("write")}>
                  글쓰기 하러 가기
                </button>
              ) : state.status === "login" ? (
                <button type="button" className="btn-primary" onClick={() => onNavigate("login")}>
                  로그인하기
                </button>
              ) : (
                <button type="button" className="btn-primary" onClick={() => onNavigate("payment")}>
                  결제 화면으로
                </button>
              )}
              <button type="button" className="btn-outline" onClick={() => onNavigate("mypage")}>
                마이페이지
              </button>
            </div>
          )}
        </section>
      </div>
    </div>
  );
}

export default PaymentResultPage;
