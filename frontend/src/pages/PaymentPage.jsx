// =============================================================
// PaymentPage.jsx — 글쓰기 AI 이용권 충전(결제) 화면
// -------------------------------------------------------------
// 들어오는 곳: 헤더 "이용권 충전" 버튼, 마이페이지 프로필 카드의 "이용권 충전" 버튼
//
// 화면 구성
//   1) 안내 카드 : 하루 무료 횟수 안내
//   2) 상품 고르기 : 10회 / 30회 / 100회 카드 중 하나 (라디오 버튼처럼 하나만)
//   3) 결제 안내 : 결제 수단은 토스페이먼츠 결제창에서 고른다는 안내
//   4) 주문 요약 : 고른 상품·금액 + 동의 체크 + "결제하기" 버튼
//
// 결제 흐름 (토스페이먼츠 결제창 SDK v2)
//   1) "결제하기" → 토스페이먼츠 스크립트를 불러와서 결제창을 띄움
//      (카드·토스페이·카카오페이·네이버페이 등 결제 수단은 결제창 안에서 고름)
//   2) 결제창에서 결제 → 토스페이먼츠가 /payment/success 또는 /payment/fail 로 돌려보냄
//   3) PaymentResultPage.jsx가 백엔드에 결제 승인을 요청해서 마무리
//   → 카드 번호 같은 결제 정보는 우리 사이트가 직접 받지 않고, 토스페이먼츠 결제창에서만 입력함
//
// ★ 필요한 설정: frontend/.env 에 VITE_TOSS_CLIENT_KEY (utils/tossPayments.js 맨 위 설명 참고)
// =============================================================

import { useState } from "react";
// Sparkles: 이용권 아이콘, Gift: 무료 안내, CreditCard: 결제 안내, Check: 고른 표시
// LogIn: 로그인 안내, Info: 안내 문구, Loader2: 결제창 여는 중
import { Sparkles, Gift, CreditCard, Check, LogIn, Info, Loader2 } from "lucide-react";

import PageHero from "../components/PageHero";
import { CREDIT_PACKAGES, FREE_DAILY_AI_USES, formatWon, pricePerDraft } from "../data/aiCredits";
import {
  TOSS_CLIENT_KEY,
  PAYMENT_SUCCESS_PATH,
  PAYMENT_FAIL_PATH,
  loadTossPayments,
  makeOrderId,
  savePendingOrder,
} from "../utils/tossPayments";
// 로딩 아이콘이 도는 .spin 클래스가 들어 있는 파일
import "../components/AuthLayout.css";
import "./PaymentPage.css";

// props
//  - auth: 로그인 정보 { token, user } (로그인 안 했으면 null)
//  - onGoLogin: 로그인 안 했을 때 "로그인하기" 버튼
//  - onNavigate: 다른 화면으로 이동 (이용약관 링크 등, App의 handleNavigate)
function PaymentPage({ auth, onGoLogin, onNavigate }) {
  // 고른 상품 id (처음엔 "인기" 상품을 골라 둠 → 바로 결제 흐름을 볼 수 있게)
  const [packageId, setPackageId] = useState("ai_30");
  // paying: 결제창을 여는 중인지 (true면 버튼을 막아서 두 번 눌리지 않게)
  const [paying, setPaying] = useState(false);
  // 주문 내용 확인·동의 체크
  const [agreed, setAgreed] = useState(false);
  // 결제 버튼을 누른 뒤 보여줄 안내 문구
  const [message, setMessage] = useState("");

  const hero = (
    <PageHero
      eyebrow="AI 이용권"
      title="AI 이용권 충전"
      description={`글쓰기 AI는 하루 ${FREE_DAILY_AI_USES}회까지 무료로 쓸 수 있어요.\n더 필요하면 이용권을 충전해서 횟수를 늘릴 수 있어요.`}
      memoText={"마음껏\n더 써 보기"}
    />
  );

  // ----- 로그인 안 했을 때: 누구 이용권인지 알 수 없어서 로그인부터 -----
  if (!auth?.token) {
    return (
      <div className="sub-page">
        <div className="sub-page-inner">
          {hero}
          <section className="panel pay-message">
            <LogIn size={36} strokeWidth={1.6} />
            <p>이용권 충전은 로그인한 뒤에 할 수 있어요.</p>
            <button type="button" className="btn-primary" onClick={onGoLogin}>
              로그인하기
            </button>
          </section>
        </div>
      </div>
    );
  }

  // 지금 고른 상품 객체 (find: 조건에 맞는 첫 번째 것)
  const selected = CREDIT_PACKAGES.find((item) => item.id === packageId);

  // ----- 결제하기 → 토스페이먼츠 결제창 열기 -----
  // async: 안에서 await(기다리기)를 쓰는 함수
  const handlePay = async (event) => {
    event.preventDefault(); // form 제출 시 새로고침 막기
    if (paying) return;
    if (!agreed) {
      setMessage("주문 내용을 확인하고 동의에 체크해 주세요.");
      return;
    }
    if (!TOSS_CLIENT_KEY) {
      // .env에 키를 안 넣었을 때 (개발자용 안내)
      setMessage("토스페이먼츠 클라이언트 키가 설정되지 않았어요.\nfrontend/.env에 VITE_TOSS_CLIENT_KEY를 넣고 개발 서버를 다시 켜 주세요.");
      return;
    }

    setPaying(true);
    setMessage("");
    try {
      // 1) 토스페이먼츠 스크립트 불러오기 → TossPayments 함수를 받음
      const TossPayments = await loadTossPayments();

      // 2) 결제 객체 만들기
      //    customerKey: 구매자 구분 값 → 비회원 결제처럼 ANONYMOUS 사용
      //    (브랜드페이·자동결제를 안 쓰면 이걸로 충분, 회원별 값이 필요해지면 서버에서 무작위 값을 만들어 주기)
      const payment = TossPayments(TOSS_CLIENT_KEY).payment({ customerKey: TossPayments.ANONYMOUS });

      // 3) 주문번호 만들고, 돌아왔을 때 확인할 수 있게 주문 정보 저장
      const orderId = makeOrderId();
      savePendingOrder({ orderId, packageId: selected.id, count: selected.count, amount: selected.price });

      // 4) 결제창 열기
      //    method "CARD" + flowMode "DEFAULT" = 카드·간편결제(토스페이·카카오페이·네이버페이 등) 통합결제창
      //    결제가 끝나면 successUrl / failUrl 로 이 탭 전체가 이동함 → 아래 줄 이후 코드는 보통 실행되지 않음
      await payment.requestPayment({
        method: "CARD",
        amount: { currency: "KRW", value: selected.price },
        orderId,
        orderName: `생각한줄 AI 이용권 ${selected.count}회`, // 결제창·영수증에 보이는 상품 이름 (100자 이하)
        successUrl: window.location.origin + PAYMENT_SUCCESS_PATH,
        failUrl: window.location.origin + PAYMENT_FAIL_PATH,
        customerName: auth.user?.name || undefined,
        customerEmail: auth.user?.email || undefined, // 결제 내역 메일이 이 주소로 감
        card: {
          flowMode: "DEFAULT",
          useEscrow: false,
        },
      });
    } catch (error) {
      // 결제창을 닫았거나(USER_CANCEL) 스크립트를 못 불러온 경우 → 화면에 남아서 안내
      setPaying(false);
      if (error?.code === "USER_CANCEL") {
        setMessage("결제를 취소했어요. 언제든지 다시 시도할 수 있어요.");
      } else {
        setMessage(error?.message || "결제창을 여는 중 문제가 생겼어요. 잠시 후 다시 시도해 주세요.");
      }
    }
  };

  return (
    <div className="sub-page">
      <div className="sub-page-inner">
        {hero}

        {/* form: 엔터나 "결제하기" 버튼으로 handlePay 실행 */}
        <form className="pay-layout" onSubmit={handlePay}>
          {/* ===== 왼쪽: 고르기 ===== */}
          <div className="pay-main">
            {/* 1) 무료 안내 */}
            <section className="panel pay-free">
              <Gift size={22} strokeWidth={1.8} />
              <p>
                <strong>{auth.user?.name}님</strong>, 글쓰기 AI(초안 작성·피드백)는 매일{" "}
                <strong>{FREE_DAILY_AI_USES}회 무료</strong>예요. 충전한 이용권은 무료 횟수를 다 쓴 뒤에 하나씩 차감돼요.
              </p>
            </section>

            {/* 2) 상품 고르기 */}
            {/* fieldset + legend: "이 라디오 버튼들은 한 묶음"이라고 화면 읽기 프로그램에 알려줌 */}
            <fieldset className="panel pay-section">
              <legend className="pay-section-title">
                <Sparkles size={18} /> 이용권 선택
              </legend>
              <div className="pay-packages">
                {CREDIT_PACKAGES.map((item) => {
                  const checked = item.id === packageId;
                  return (
                    // label로 감싸면 카드 어디를 눌러도 안의 라디오 버튼이 선택됨
                    <label key={item.id} className={checked ? "pay-package checked" : "pay-package"}>
                      {/* 진짜 라디오는 눈에만 안 보이게 숨김 (키보드 방향키·화면 읽기는 그대로 됨) */}
                      <input
                        type="radio"
                        name="credit-package"
                        value={item.id}
                        checked={checked}
                        onChange={() => {
                          setPackageId(item.id);
                          setMessage("");
                        }}
                      />
                      {item.badge && <span className="pay-badge">{item.badge}</span>}
                      <span className="pay-package-count">
                        AI 이용 <strong>{item.count}회</strong>
                      </span>
                      <span className="pay-package-price">{formatWon(item.price)}</span>
                      <span className="pay-package-unit">1회 {pricePerDraft(item)}</span>
                      {/* 고른 카드 오른쪽 위 체크 표시 */}
                      {checked && (
                        <span className="pay-check" aria-hidden="true">
                          <Check size={14} strokeWidth={3} />
                        </span>
                      )}
                    </label>
                  );
                })}
              </div>
            </fieldset>

            {/* 3) 결제 안내 (결제 수단은 토스페이먼츠 결제창에서 고름) */}
            <section className="panel pay-section">
              <h2 className="pay-section-title">
                <CreditCard size={18} /> 결제 방법
              </h2>
              <p className="pay-toss-text">
                &lsquo;결제하기&rsquo;를 누르면 <strong>토스페이먼츠 결제창</strong>이 열려요. 신용·체크카드, 토스페이,
                카카오페이, 네이버페이 등 원하는 결제 수단을 결제창에서 골라 주세요.
              </p>
              <p className="pay-hint">카드 번호 등 결제 정보는 토스페이먼츠 결제창에서만 입력하며, 생각한줄에 저장되지 않아요.</p>
            </section>
          </div>

          {/* ===== 오른쪽: 주문 요약 (PC에서는 스크롤해도 따라옴) ===== */}
          <aside className="panel pay-summary" aria-label="주문 요약">
            <h2>주문 요약</h2>
            <dl>
              <div>
                <dt>상품</dt>
                <dd>AI 이용 {selected.count}회</dd>
              </div>
              <div>
                <dt>결제 수단</dt>
                <dd>토스페이먼츠 결제창에서 선택</dd>
              </div>
              <div className="pay-total">
                <dt>결제 금액</dt>
                <dd>{formatWon(selected.price)}</dd>
              </div>
            </dl>

            <label className="pay-agree">
              <input
                type="checkbox"
                checked={agreed}
                onChange={(event) => {
                  setAgreed(event.target.checked);
                  setMessage("");
                }}
              />
              <span>
                주문 내용을 확인했고, 결제에 동의해요.{" "}
                {/* 약관 보기: 화면 이동 버튼 (글자 링크처럼 보이게) */}
                <button type="button" className="pay-link" onClick={() => onNavigate("terms")}>
                  이용약관 보기
                </button>
              </span>
            </label>

            <button type="submit" className="btn-primary pay-submit" disabled={paying}>
              {paying ? (
                <>
                  <Loader2 size={16} className="spin" /> 결제창 여는 중...
                </>
              ) : (
                `${formatWon(selected.price)} 결제하기`
              )}
            </button>

            {message && (
              <p className="pay-result" role="status">
                <Info size={16} />
                <span>{message}</span>
              </p>
            )}
          </aside>
        </form>
      </div>
    </div>
  );
}

export default PaymentPage;
