// =============================================================
// LandingPage.jsx — 처음 들어왔을 때 보이는 메인 페이지
// -------------------------------------------------------------
// 화면 구성
//   ┌──────────────────────────────┬──────────────────┐
//   │ 왼쪽: 손글씨 제목, 설명,          │ 오른쪽: 메모지     │
//   │       입력창, 시작 버튼          │        일러스트    │
//   ├──────────────────────────────┴──────────────────┤
//   │ 아래: 생각 입력 → 구조화 → 문장 완성 3단계 카드          │
//   └─────────────────────────────────────────────────┘
// =============================================================

// useState: 화면에서 바뀌는 값(상태)을 저장하는 React 기능
import { useState } from "react";

// 아이콘들 (lucide-react)
//  - PenLine: 펜 / Puzzle: 퍼즐 조각 / Pencil: 연필 / ArrowRight: 화살표
//  - Cloud: 구름 / Smile: 웃는 얼굴 (메모지 낙서용)
import { PenLine, Puzzle, Pencil, ArrowRight, Cloud, Smile } from "lucide-react";

// 이 페이지 전용 CSS
import "./LandingPage.css";

// 아래쪽 3단계 카드에 들어갈 데이터
// 배열로 만들어두면 아래에서 map으로 반복해서 그릴 수 있음
// icon: 위에서 가져온 아이콘 컴포넌트 자체를 넣어둠 (아래에서 <Icon />으로 그림)
const STEPS = [
  {
    icon: PenLine,
    title: "생각 입력",
    description: "키워드와 메모를\n자유롭게 적어요.", // \n: 줄바꿈 (CSS에서 줄바꿈으로 보이게 처리함)
  },
  {
    icon: Puzzle,
    title: "구조화",
    description: "AI가 흐름을\n정리해 줘요.",
  },
  {
    icon: Pencil,
    title: "문장 완성",
    description: "당신의 문장으로\n완성해 보세요.",
  },
];

// LandingPage 컴포넌트
// props: onStart → 사용자가 생각을 입력하고 시작 버튼을 눌렀을 때 실행할 함수 (부모 App이 넘겨줌)
function LandingPage({ onStart }) {
  // idea: 입력창에 적은 글자 / setIdea: idea 값을 바꾸는 함수
  const [idea, setIdea] = useState("");

  // error: 빈 칸으로 시작을 눌렀을 때 보여줄 안내 문구 (평소엔 빈 문자열)
  const [error, setError] = useState("");

  // 시작(화살표 버튼, 큰 버튼, 엔터키)을 눌렀을 때 실행되는 함수
  // event: 브라우저가 넘겨주는 "무슨 일이 일어났는지" 정보
  const handleSubmit = (event) => {
    // form을 제출하면 브라우저는 원래 페이지를 새로고침함
    // → 새로고침되면 입력한 값이 다 날아가니까 그걸 막는 코드
    event.preventDefault();

    // trim(): 앞뒤 공백 제거 → 스페이스만 친 경우도 빈 칸으로 처리
    if (idea.trim() === "") {
      setError("먼저 정리하고 싶은 생각을 한 줄 적어주세요.");
      return; // 여기서 함수 끝 (아래 코드는 실행 안 됨)
    }

    setError(""); // 에러 문구 지우기
    onStart(idea.trim()); // 부모(App)에게 입력한 생각을 전달
  };

  return (
    <section className="landing">
      {/*
        ===== 배경 구름 장식 =====
        div 여러 개를 흐릿한 흰 원으로 만들어서 하늘의 구름처럼 보이게 함 (모양은 CSS에서)
        aria-hidden="true": 장식용이라 화면 읽기 프로그램이 무시하게 함
      */}
      <div className="sky-clouds" aria-hidden="true">
        <span className="sky-cloud cloud-1" />
        <span className="sky-cloud cloud-2" />
        <span className="sky-cloud cloud-3" />
        <span className="sky-cloud cloud-4" />
      </div>

      {/* 실제 내용 (구름 위에 올라감) */}
      <div className="landing-inner">
        {/* ================= 위쪽: 왼쪽 글 + 오른쪽 메모지 ================= */}
        <div className="hero">
          {/* ----- 왼쪽 ----- */}
          <div className="hero-text">
            {/* 손글씨 느낌 제목 (글꼴은 CSS에서 "Nanum Pen Script"로 지정) */}
            <h1 className="hero-title">
              흩어진 생각이
              {/* <br />: 줄바꿈 (JSX에서는 반드시 /> 로 닫아야 함) */}
              <br />한 줄의 글이 되는 곳,
              <br />
              {/* 서비스 이름만 더 크고 진하게 */}
              <strong>생각한줄</strong>
            </h1>

            <p className="hero-desc">
              {/* {" "}: 띄어쓰기 한 칸. 모바일에서 <br />을 숨겨도 글자가 붙지 않게 */}
              지금 떠오르는 생각을 적어보세요.{" "}
              <br />
              당신의 글쓰기를 응원합니다.
            </p>

            {/*
              <form>으로 감싸면 입력창에서 엔터를 쳐도 onSubmit이 실행됨
              → 화살표 버튼, 큰 버튼, 엔터키 셋 다 같은 handleSubmit을 실행
            */}
            <form className="hero-form" onSubmit={handleSubmit}>
              <div className="idea-input-box">
                <input
                  type="text"
                  className="idea-input"
                  placeholder="예) 나의 장점에 대해 정리해보고 싶어요."
                  // value: 입력창에 보이는 글자 = idea 상태값 (React가 입력창을 관리)
                  value={idea}
                  // onChange: 글자를 칠 때마다 실행 → 입력한 내용을 idea에 저장
                  // event.target.value: 지금 입력창에 들어있는 글자 전체
                  onChange={(event) => {
                    setIdea(event.target.value);
                    if (error) setError(""); // 다시 입력하면 에러 문구 지우기
                  }}
                  maxLength={200} // 최대 200자
                  aria-label="정리하고 싶은 생각 입력"
                />
                {/* type="submit": 누르면 form의 onSubmit이 실행되는 버튼 */}
                <button type="submit" className="idea-submit" aria-label="생각 정리 시작">
                  <ArrowRight size={20} />
                </button>
              </div>

              {/* error에 글자가 있을 때만 안내 문구 표시 (A && B: A가 참일 때만 B를 그림) */}
              {error && <p className="idea-error">{error}</p>}

              <button type="submit" className="start-button">
                생각 정리 시작하기
                <ArrowRight size={18} />
              </button>
            </form>
          </div>

          {/* ----- 오른쪽: 메모지 일러스트 (전부 장식이라 aria-hidden) ----- */}
          <div className="hero-visual" aria-hidden="true">
            {/* 주변에 흩날리는 작은 종이 조각들 → "흩어진 생각" 느낌 */}
            <span className="paper-scrap scrap-1" />
            <span className="paper-scrap scrap-2" />
            <span className="paper-scrap scrap-3" />
            <span className="paper-scrap scrap-4" />

            {/* 가운데 큰 메모지 */}
            <div className="memo">
              {/* 왼쪽 위 구름 낙서 */}
              <Cloud className="memo-cloud" size={44} strokeWidth={1.4} />

              {/* 메모지에 손글씨로 적힌 문구 */}
              <p className="memo-text">
                생각을
                <br />
                차근차근
                <br />
                정리해봐요
              </p>

              {/* 오른쪽 아래 웃는 얼굴 낙서 */}
              <Smile className="memo-smile" size={34} strokeWidth={1.4} />
            </div>
          </div>
        </div>

        {/* ================= 아래쪽: 3단계 안내 카드 ================= */}
        {/* ol: 순서가 있는 목록 */}
        <ol className="steps-card">
          {STEPS.map((step, index) => {
            // 아이콘 컴포넌트를 대문자 변수에 꺼냄 (JSX 태그는 대문자로 시작해야 함)
            const Icon = step.icon;

            return (
              // key: map으로 만든 요소를 구분하는 이름표 (필수)
              <li key={step.title} className="step">
                {/* 동그란 아이콘 배경 */}
                <div className="step-icon">
                  <Icon size={28} strokeWidth={1.6} />
                </div>

                <div className="step-text">
                  <strong>{step.title}</strong>
                  <span>{step.description}</span>
                </div>

                {/* 마지막 단계가 아니면 오른쪽에 작은 화살표 (STEPS.length - 1 = 마지막 index) */}
                {index < STEPS.length - 1 && (
                  <ArrowRight className="step-arrow" size={18} aria-hidden="true" />
                )}
              </li>
            );
          })}
        </ol>
      </div>
    </section>
  );
}

export default LandingPage;
