// =============================================================
// SupportTabs.jsx — 고객지원 화면 위쪽의 작은 탭 (공지사항 · 이용약관 · 개인정보처리방침)
// -------------------------------------------------------------
// 세 화면 어디에 있든 이 탭으로 바로 옆 화면으로 넘어갈 수 있게 함
// (푸터 "고객지원" 묶음과 같은 세 개)
// 스타일: pages/SupportPages.css (.support-tabs)
// =============================================================

// key: App.jsx의 activeNav 값 (헤더·푸터 메뉴 key와 같아야 눌렀을 때 그 화면으로 이동)
const SUPPORT_TABS = [
  { key: "notice", label: "공지사항" },
  { key: "terms", label: "이용약관" },
  { key: "privacy", label: "개인정보처리방침" },
];

// props
//  - active: 지금 보고 있는 화면 key ("notice" / "terms" / "privacy")
//  - onNavigate: 탭을 누르면 실행할 함수 (App의 handleNavigate)
function SupportTabs({ active, onNavigate }) {
  return (
    // nav: "이동 메뉴" 묶음이라는 뜻의 태그
    <nav className="support-tabs" aria-label="고객지원 메뉴">
      {SUPPORT_TABS.map((tab) => (
        <button
          key={tab.key}
          type="button"
          className={active === tab.key ? "support-tab active" : "support-tab"}
          // aria-current="page": 화면 읽기 프로그램에 "지금 보고 있는 화면"이라고 알려줌
          aria-current={active === tab.key ? "page" : undefined}
          onClick={() => {
            if (active !== tab.key) onNavigate(tab.key);
          }}
        >
          {tab.label}
        </button>
      ))}
    </nav>
  );
}

export default SupportTabs;
