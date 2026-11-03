// =============================================================
// PolicyPage.jsx — 이용약관 / 개인정보처리방침 화면 (푸터 "고객지원")
// -------------------------------------------------------------
// 두 화면은 모양이 똑같고 글만 달라서 컴포넌트 하나로 같이 씀
//   <PolicyPage kind="terms" />   → 이용약관
//   <PolicyPage kind="privacy" /> → 개인정보처리방침
//
// 문구는 전부 data/policies.js에 있음 → 글을 고칠 때는 그 파일만 고치면 됨
// =============================================================

// CalendarCheck: 시행일 옆 달력 아이콘
import { CalendarCheck } from "lucide-react";

import PageHero from "../components/PageHero";
import SupportTabs from "../components/SupportTabs";
import { POLICIES } from "../data/policies";
import "./SupportPages.css";

// props
//  - kind: "terms"(이용약관) 또는 "privacy"(개인정보처리방침)
//  - onNavigate: 위쪽 고객지원 탭을 눌렀을 때 화면 이동 (App의 handleNavigate)
function PolicyPage({ kind, onNavigate }) {
  // POLICIES[kind]: kind가 "terms"면 POLICIES.terms를 꺼냄
  const policy = POLICIES[kind];

  return (
    <div className="sub-page">
      <div className="sub-page-inner">
        <PageHero eyebrow="고객지원" title={policy.title} description={policy.description} memoText={policy.memoText} />

        <div className="support-wrap">
          <SupportTabs active={kind} onNavigate={onNavigate} />

          {/* article: 혼자서도 뜻이 통하는 한 편의 글이라는 의미의 태그 */}
          <article className="panel support-card policy">
            <p className="policy-date">
              <CalendarCheck size={15} /> 시행일 {policy.effectiveDate}
            </p>
            <p className="policy-intro">{policy.intro}</p>

            {policy.sections.map((section, index) => (
              // 제목이 빈 칸인 묶음도 있어서 key는 순서 번호로 (문구 순서가 바뀌지 않는 고정 데이터라 괜찮음)
              <section key={index} className="policy-section">
                {/* 제목이 있는 묶음만 제목을 그림 (앞 묶음에 이어지는 내용은 제목 없이) */}
                {section.title && <h2>{section.title}</h2>}
                {/* ?.: paragraphs가 없는 묶음이면 그냥 건너뜀 (에러 안 남) */}
                {section.paragraphs?.map((text) => (
                  <p key={text}>{text}</p>
                ))}
                {section.items && (
                  <ul>
                    {section.items.map((text) => (
                      <li key={text}>{text}</li>
                    ))}
                  </ul>
                )}
                {/* note: 목록 아래에 붙는 문단 */}
                {section.note && <p>{section.note}</p>}
              </section>
            ))}
          </article>
        </div>
      </div>
    </div>
  );
}

export default PolicyPage;
