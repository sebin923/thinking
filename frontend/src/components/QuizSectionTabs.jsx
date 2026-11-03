// =============================================================
// QuizSectionTabs.jsx — 퀴즈 화면 맨 위의 큰 탭 [퀴즈 | 랭킹]
// -------------------------------------------------------------
// 헤더 "퀴즈" 메뉴 하나 안에 퀴즈 풀기와 랭킹이 같이 있음
//   [퀴즈 | 랭킹]       ← 이 컴포넌트
//     └ [맞춤법 | 문법]  ← 퀴즈 탭 안의 작은 탭 (CategoryTabs.jsx, variant="sub")
//
// 퀴즈 화면(QuizPage)과 랭킹 화면(RankingPage) 둘 다 이 탭을 똑같이 보여줘서
// 사용자에게는 한 화면 안에서 탭만 바뀌는 것처럼 보임
// 스타일: CategoryTabs.css (.category-tabs 큰 알약 모양을 같이 씀)
// =============================================================

// BookOpenCheck: 퀴즈 아이콘, Trophy: 랭킹 아이콘
import { BookOpenCheck, Trophy } from "lucide-react";
import "./CategoryTabs.css";

// key: App.jsx의 화면 이름(activeNav)과 같음 → 누르면 그 화면으로 이동
const SECTIONS = [
  { key: "quiz", label: "퀴즈", icon: BookOpenCheck },
  { key: "ranking", label: "랭킹", icon: Trophy },
];

// props
//  - value: 지금 보고 있는 쪽 ("quiz" 또는 "ranking")
//  - onChange: 탭을 눌렀을 때 실행 (누른 탭의 key를 넘겨줌)
function QuizSectionTabs({ value, onChange }) {
  return (
    <div className="category-tabs section" role="tablist" aria-label="퀴즈 메뉴">
      {SECTIONS.map((section) => {
        const isActive = section.key === value;
        // 아이콘 컴포넌트를 대문자 변수로 꺼냄 (JSX 태그는 대문자로 시작해야 함)
        const Icon = section.icon;
        return (
          <button
            key={section.key}
            type="button"
            role="tab"
            aria-selected={isActive}
            className={isActive ? "category-tab active" : "category-tab"}
            onClick={() => !isActive && onChange(section.key)}
          >
            <Icon size={17} />
            {section.label}
          </button>
        );
      })}
    </div>
  );
}

export default QuizSectionTabs;
