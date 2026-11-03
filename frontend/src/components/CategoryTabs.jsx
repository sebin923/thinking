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
// =============================================================

import { QUIZ_CATEGORIES } from "../data/quizCategories";
import "./CategoryTabs.css";

// props
//  - value: 지금 선택된 탭의 key (예: "spelling")
//  - onChange: 탭을 눌렀을 때 실행할 함수 (누른 탭의 key를 넘겨줌)
//  - variant: "sub"면 큰 탭 아래에 들어가는 작은 하위 탭 모양 (기본은 큰 알약 모양)
function CategoryTabs({ value, onChange, variant }) {
  return (
    // role="tablist": 화면 읽기 프로그램에게 "여기는 탭 묶음"이라고 알려줌 (접근성)
    <div className={variant === "sub" ? "category-tabs sub" : "category-tabs"} role="tablist" aria-label="퀴즈 종류">
      {QUIZ_CATEGORIES.map((category) => {
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
