// =============================================================
// CategoryTabs.jsx — "맞춤법 | 문법" 처럼 퀴즈 종류를 고르는 탭 버튼 묶음
// -------------------------------------------------------------
// 퀴즈 화면 구성 (헤더 "퀴즈" 메뉴)
//   [퀴즈 | 랭킹]       ← 큰 탭 (QuizSectionTabs.jsx)
//     └ [맞춤법 | 문법]  ← 이 컴포넌트 (퀴즈 탭 안에서만, 작은 탭 모양)
//
// 사용 예)
//   <CategoryTabs value="spelling" onChange={(key) => ...} />              ← 기본(큰) 모양
//   <CategoryTabs value="spelling" onChange={(key) => ...} variant="sub" /> ← 작은 하위 탭 모양
//   <CategoryTabs value="easy" onChange={...} variant="level" items={QUIZ_LEVELS} ariaLabel="문법 난이도" />
//       ← 문법 퀴즈의 [상 | 중 | 하] 난이도 탭 (탭 목록만 바꿔서 같은 컴포넌트를 다시 씀)
// =============================================================

import { QUIZ_CATEGORIES } from "../data/quizCategories";
import "./CategoryTabs.css";

// props
//  - value: 지금 선택된 탭의 key (예: "spelling")
//  - onChange: 탭을 눌렀을 때 실행할 함수 (누른 탭의 key를 넘겨줌)
//  - variant: 탭 모양
//      "sub"   → 큰 탭 아래에 들어가는 작은 하위 탭 (글자 + 밑줄)
//      "level" → 문법 난이도 [상 | 중 | 하] 탭 (작은 알약 모양)
//      없음    → 기본 큰 알약 모양
//  - items: 보여줄 탭 목록 [{ key, label }, ...] (안 넘기면 퀴즈 종류 [맞춤법 | 문법])
//  - ariaLabel: 화면 읽기 프로그램이 읽어 줄 탭 묶음 이름 (기본 "퀴즈 종류")
function CategoryTabs({ value, onChange, variant, items = QUIZ_CATEGORIES, ariaLabel = "퀴즈 종류" }) {
  // variant가 있으면 "category-tabs sub"처럼 클래스를 하나 더 붙여서 모양을 바꿈
  const className = variant ? `category-tabs ${variant}` : "category-tabs";

  return (
    // role="tablist": 화면 읽기 프로그램에게 "여기는 탭 묶음"이라고 알려줌 (접근성)
    <div className={className} role="tablist" aria-label={ariaLabel}>
      {items.map((category) => {
        const isActive = category.key === value; // 이 탭이 선택된 탭인지

        return (
          <button
            key={category.key}
            type="button"
            role="tab"
            aria-selected={isActive}
            className={isActive ? "category-tab active" : "category-tab"}
            // 이미 선택된 탭을 또 누르면 아무 일도 안 일어나게
            onClick={() => !isActive && onChange(category.key)}
          >
            {category.label}
          </button>
        );
      })}
    </div>
  );
}

export default CategoryTabs;
