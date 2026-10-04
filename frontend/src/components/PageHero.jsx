// =============================================================
// PageHero.jsx — 서브 페이지(글쓰기, 퀴즈 등) 맨 위의 제목 영역
// -------------------------------------------------------------
// 왼쪽: 작은 안내 문구 + 큰 제목 + 설명
// 오른쪽: 손글씨가 적힌 메모지 + 펜 + 풀잎 장식
// 글쓰기 페이지와 퀴즈 페이지가 똑같은 모양을 쓰니까 컴포넌트 하나로 만들고,
// 글자만 props로 바꿔서 재사용함
// =============================================================

// 아이콘들 (lucide-react): PenLine = 펜, Sprout = 새싹(풀잎 장식)
import { PenLine, Sprout } from "lucide-react";

import "./PageHero.css";

// PageHero 컴포넌트
// props(부모가 넘겨주는 값)
//  - eyebrow: 제목 위 작은 안내 문구 (예: "당신의 생각이, 하나의 글이 되는 과정")
//  - title: 큰 제목
//  - description: 제목 아래 설명 (\n을 넣으면 줄바꿈됨)
//  - memoText: 오른쪽 메모지에 적힐 손글씨 (\n을 넣으면 줄바꿈됨)
//  - memoVariant: 메모지 모양 ("note" = 접힌 쪽지, "notebook" = 스프링 노트), 기본값 "note"
function PageHero({ eyebrow, title, description, memoText, memoVariant = "note" }) {
  return (
    <section className="page-hero">
      {/* ===== 왼쪽: 글 ===== */}
      <div className="page-hero-text">
        <p className="page-hero-eyebrow">{eyebrow}</p>
        <h1 className="page-hero-title">{title}</h1>
        {/* CSS의 white-space: pre-line 덕분에 \n이 줄바꿈으로 보임 */}
        <p className="page-hero-desc">{description}</p>
      </div>

      {/* ===== 오른쪽: 메모지 일러스트 (장식이라 aria-hidden) ===== */}
      <div className="page-hero-visual" aria-hidden="true">
        {/* 뒤쪽에 흐릿한 구름 */}
        <span className="hero-cloud" />

        {/* 메모지 (memoVariant에 따라 클래스가 달라져서 모양이 바뀜) */}
        <div className={`hero-memo hero-memo-${memoVariant}`}>
          <p>{memoText}</p>
        </div>

        {/* 메모지에 기대 놓인 펜 */}
        <PenLine className="hero-pen" size={56} strokeWidth={1.3} />

        {/* 양옆 풀잎 장식 */}
        <Sprout className="hero-sprout sprout-left" size={30} strokeWidth={1.4} />
        <Sprout className="hero-sprout sprout-right" size={34} strokeWidth={1.4} />
      </div>
    </section>
  );
}

export default PageHero;
