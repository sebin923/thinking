// =============================================================
// AboutPage.jsx — "서비스 소개" 화면
// -------------------------------------------------------------
// 화면 구성 (위에서 아래로)
//   1) PageHero      : 다른 화면들과 똑같은 제목 + 오른쪽 메모지
//   2) 소개 카드      : 생각한줄이 뭘 하는 서비스인지 한 문단으로 (왼쪽 글 + 오른쪽 "메모 → 글" 예시)
//   3) 이렇게 써요    : 사용 흐름 4단계 (생각 적기 → AI 정리 → 피드백 → 저장)
//   4) 주요 기능      : 기능 카드 6개 (누르면 그 화면으로 바로 이동)
//   5) 약속          : 생각한줄이 AI를 쓰는 원칙 3가지
//   6) 마지막 안내    : "지금 시작하기" 버튼
//
// 화면에 들어갈 글(단계·기능·약속)은 전부 위쪽 배열에 모아 둠
//   → 문구를 고치고 싶으면 아래 JSX는 건드리지 말고 배열만 고치면 됨
// =============================================================

// 아이콘들 (lucide-react) — 각각 어디에 쓰는지는 아래 배열에 적어 둠
import {
  PenLine,
  Sparkles,
  MessageSquareText,
  Save,
  SlidersHorizontal,
  SpellCheck,
  Trophy,
  FolderOpen,
  ShieldCheck,
  Hand,
  FileCheck2,
  ArrowRight,
  ArrowDown,
} from "lucide-react";

// PageHero: 위쪽 제목 + 메모지 (PageHero.css도 같이 불러와져서 sub-page, panel, btn-primary 등 공통 스타일을 쓸 수 있음)
import PageHero from "../components/PageHero";
// 이 화면 전용 스타일
import "./AboutPage.css";

// ----- 3) 사용 흐름 4단계 -----
// step: 단계 번호 / icon: 동그라미 안 아이콘 / title: 제목 / description: 설명 (\n = 줄바꿈)
const FLOW_STEPS = [
  {
    step: 1,
    icon: PenLine,
    title: "생각 적기",
    description: "떠오르는 키워드나 메모를\n순서 없이 편하게 적어요.",
  },
  {
    step: 2,
    icon: Sparkles,
    title: "AI가 흐름 정리",
    description: "적은 생각만 가지고\nAI가 글의 뼈대를 잡아 줘요.",
  },
  {
    step: 3,
    icon: MessageSquareText,
    title: "피드백으로 다듬기",
    description: "어색한 문장과 고칠 방향을\n짚어 주면 직접 고쳐요.",
  },
  {
    step: 4,
    icon: Save,
    title: "버전 저장",
    description: "초안·수정본·완료본을\n차곡차곡 남겨요.",
  },
];

// ----- 4) 주요 기능 카드 -----
// target: 카드를 눌렀을 때 이동할 화면 이름 (App.jsx의 activeNav 값과 같아야 함)
// tag: 카드 위에 붙는 작은 분류 글자
const FEATURES = [
  {
    icon: PenLine,
    tag: "글쓰기",
    title: "글쓰기",
    description: "자유 글쓰기·자기소개서·보고서·발표문 등 글 유형을 골라 쓰고, 서식 도구로 바로 편집해요.",
    target: "write",
  },
  {
    icon: MessageSquareText,
    tag: "AI",
    title: "AI 초안 · 피드백",
    description: "내가 적은 생각으로 초안을 받아 보고, 문제 문장과 수정 방향을 확인해 원하는 것만 적용해요.",
    target: "write",
  },
  {
    icon: SlidersHorizontal,
    tag: "AI",
    title: "개인 맞춤 설정",
    description: "선호하는 문체·문장 길이·피드백 방식을 저장하면 AI가 내 스타일에 맞춰 도와줘요.",
    target: "writing-settings",
  },
  {
    icon: SpellCheck,
    tag: "연습",
    title: "맞춤법 · 문법 퀴즈",
    description: "자주 틀리는 표현을 문제로 풀고, 힌트와 해설로 왜 그런지까지 익혀요.",
    target: "quiz",
  },
  {
    icon: Trophy,
    tag: "연습",
    title: "도전 모드 · 랭킹",
    description: "제한 시간 안에 몇 문제를 연속으로 맞히는지 도전하고 다른 사람들과 순위를 겨뤄요.",
    target: "ranking",
  },
  {
    icon: FolderOpen,
    tag: "기록",
    title: "마이페이지",
    description: "내가 쓴 글을 종류별로 모아 보고, 저장한 버전을 열어 이어 쓸 수 있어요.",
    target: "mypage",
  },
];

// ----- 5) 약속 3가지 -----
const PROMISES = [
  {
    icon: FileCheck2,
    title: "내가 준 사실만 써요",
    description: "AI는 사용자가 적은 내용만 바탕으로 글을 정리해요. 없는 이야기를 지어내지 않게 설계했어요.",
  },
  {
    icon: Hand,
    title: "AI는 선택이에요",
    description: "AI를 하나도 쓰지 않고 직접 써도 괜찮아요. 제안은 내가 고른 것만 본문에 들어가요.",
  },
  {
    icon: ShieldCheck,
    title: "내 글은 나만 봐요",
    description: "쓴 글과 기록은 로그인한 본인만 볼 수 있고, 비밀번호는 암호화해서 저장해요.",
  },
];

// AboutPage 컴포넌트
// props: onNavigate → 다른 화면으로 이동하는 함수 (App의 handleNavigate, 헤더 메뉴와 같은 함수)
function AboutPage({ onNavigate }) {
  // 버튼·카드를 눌렀을 때: 화면을 바꾸고 맨 위로 스크롤
  // (화면만 바뀌고 스크롤이 그대로면 새 화면의 중간부터 보여서 어색함)
  const go = (target) => {
    onNavigate(target);
    window.scrollTo({ top: 0, behavior: "smooth" });
  };

  return (
    <div className="sub-page">
      <div className="sub-page-inner">
        {/* ===== 1) 위쪽 제목 ===== */}
        <PageHero
          eyebrow="서비스 소개"
          title="흩어진 생각을, 내 문장으로"
          description={"생각한줄은 쓰고 싶은 건 있는데 첫 문장이 막막할 때\n생각을 정리하고 직접 글로 완성하도록 돕는 글쓰기 서비스예요."}
          memoText={"생각이\n글이 되는\n과정"}
        />

        {/* ===== 2) 소개 카드 ===== */}
        <section className="panel about-intro">
          <div className="about-intro-text">
            <h2 className="about-section-title">생각한줄은 이런 서비스예요</h2>
            <p>
              글을 쓸 때 가장 어려운 건 <strong>무엇을 어떤 순서로 쓸지</strong> 정하는 일이에요.
              생각한줄은 머릿속에 흩어진 생각을 한 줄씩 적기만 하면, AI가 그 생각만으로 글의 흐름을 잡아 줘요.
            </p>
            <p>
              그다음부터는 <strong>내가 직접</strong> 고치고 완성해요. AI는 대신 써 주는 도구가 아니라
              옆에서 방향을 알려 주는 글쓰기 코치예요.
            </p>
          </div>

          {/* 오른쪽: "메모 → 글"로 바뀌는 모습 예시 (실제 화면이 아니라 이해를 돕는 예시) */}
          <div className="about-example">
            <div className="about-example-memo">
              <span className="about-example-label">내가 적은 생각</span>
              <ul>
                <li>동아리에서 웹 프로젝트</li>
                <li>React 처음 써 봄</li>
                <li>팀원이랑 매주 회의</li>
              </ul>
            </div>
            {/* 메모와 문장 사이 아래 방향 화살표 */}
            <ArrowDown className="about-example-arrow" size={22} aria-hidden="true" />
            <div className="about-example-result">
              <span className="about-example-label">정리된 문장</span>
              <p>
                동아리에서 웹 프로젝트를 진행하며 React를 처음 다뤄 보았고, 매주 팀원들과 회의하며
                방향을 맞춰 나갔습니다.
              </p>
            </div>
          </div>
        </section>

        {/* ===== 3) 사용 흐름 ===== */}
        <section className="about-section">
          <h2 className="about-section-title">이렇게 사용해요</h2>
          {/* ol: 순서가 있는 목록 (화면 읽기 프로그램이 "1단계, 2단계"처럼 읽어 줌) */}
          <ol className="about-flow">
            {FLOW_STEPS.map((item) => {
              // 아이콘 컴포넌트를 대문자 변수로 꺼냄 (JSX 태그는 대문자로 시작해야 함)
              const Icon = item.icon;
              return (
                <li key={item.step} className="panel about-flow-step">
                  <span className="about-flow-number">STEP {item.step}</span>
                  <div className="about-flow-icon">
                    <Icon size={26} strokeWidth={1.7} />
                  </div>
                  <strong>{item.title}</strong>
                  <p>{item.description}</p>
                </li>
              );
            })}
          </ol>
        </section>

        {/* ===== 4) 주요 기능 ===== */}
        <section className="about-section">
          <h2 className="about-section-title">주요 기능</h2>
          <p className="about-section-desc">카드를 누르면 해당 화면으로 바로 이동해요.</p>
          <div className="about-features">
            {FEATURES.map((feature) => {
              const Icon = feature.icon;
              return (
                // 카드 전체가 버튼 → 어디를 눌러도 이동 (키보드 Tab·Enter로도 됨)
                <button
                  key={feature.title}
                  type="button"
                  className="panel about-feature"
                  onClick={() => go(feature.target)}
                >
                  <div className="about-feature-head">
                    <span className="about-feature-icon">
                      <Icon size={22} strokeWidth={1.8} />
                    </span>
                    <span className="about-feature-tag">{feature.tag}</span>
                  </div>
                  <strong>{feature.title}</strong>
                  <p>{feature.description}</p>
                  <span className="about-feature-link">
                    바로 가기 <ArrowRight size={14} />
                  </span>
                </button>
              );
            })}
          </div>
        </section>

        {/* ===== 5) 약속 ===== */}
        <section className="about-section">
          <h2 className="about-section-title">생각한줄의 약속</h2>
          <div className="about-promises">
            {PROMISES.map((promise) => {
              const Icon = promise.icon;
              return (
                <div key={promise.title} className="about-promise">
                  <Icon className="about-promise-icon" size={28} strokeWidth={1.6} />
                  <strong>{promise.title}</strong>
                  <p>{promise.description}</p>
                </div>
              );
            })}
          </div>
        </section>

        {/* ===== 6) 마지막 안내 ===== */}
        <section className="panel about-cta">
          <p className="about-cta-title">오늘의 생각, 한 줄로 시작해 볼까요?</p>
          <p className="about-cta-desc">로그인하지 않아도 글쓰기와 퀴즈를 먼저 둘러볼 수 있어요.</p>
          <div className="about-cta-buttons">
            <button type="button" className="btn-primary" onClick={() => go("write")}>
              글쓰기 시작하기 <ArrowRight size={16} />
            </button>
            <button type="button" className="btn-outline" onClick={() => go("quiz")}>
              퀴즈 풀어 보기
            </button>
          </div>
        </section>
      </div>
    </div>
  );
}

export default AboutPage;
