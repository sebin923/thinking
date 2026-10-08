// =============================================================
// Header.jsx — 맨 위 상단 메뉴바
// -------------------------------------------------------------
// 왼쪽: 로고 / 가운데: 홈(아이콘)·서비스 소개·글쓰기 학습·퀴즈·랭킹·이용안내
// 오른쪽: 로그인 전 → 로그인·회원가입 / 로그인 후 → "OOO님" + 로그아웃
// 여러 페이지에서 같이 쓸 거라서 컴포넌트로 따로 분리함
// =============================================================

// useState: 화면에서 바뀌는 값을 저장하는 React 기능
// (여기서는 모바일에서 메뉴가 열렸는지/닫혔는지 저장하는 데 씀)
import { useState } from "react";

// 아이콘 (lucide-react): Menu = 햄버거(≡) 아이콘, X = 닫기 아이콘, Home = 집 모양 아이콘
// UserRound = 사람 아이콘 (로그인한 사용자 이름 옆)
import { Menu, X, Home, UserRound } from "lucide-react";

// 가운데 메뉴 목록
// 배열로 만들어두면 아래에서 map으로 반복해서 메뉴를 그릴 수 있음
// (메뉴를 추가하려면 여기에 한 줄만 추가하면 됨)
// icon: 글자 대신 아이콘으로 보여줄 메뉴만 넣음 (홈은 집 아이콘으로 표시)
const NAV_ITEMS = [
  { key: "home", label: "홈", icon: Home },
  { key: "about", label: "서비스 소개" },
  { key: "write", label: "글쓰기 학습" }, // 글쓰기 페이지
  { key: "quiz", label: "퀴즈" }, // 맞춤법·문법 퀴즈 페이지
  { key: "ranking", label: "랭킹" }, // 퀴즈 랭킹 페이지
  { key: "guide", label: "이용안내" },
];

// Header 컴포넌트
// props(부모가 넘겨주는 값)
//  - activeNav: 지금 선택된 메뉴의 key (예: "home") → 선택된 메뉴만 진하게 표시
//  - onNavClick: 메뉴를 눌렀을 때 실행할 함수 ("login", "signup"도 이 함수로 이동)
//  - user: 로그인한 사용자 정보 (로그인 안 했으면 null)
//  - onLogout: 로그아웃 버튼을 눌렀을 때 실행할 함수
function Header({ activeNav, onNavClick, user, onLogout }) {
  // isMenuOpen: 모바일 화면에서 메뉴가 펼쳐져 있는지 (true / false)
  // 처음에는 닫혀 있으니까 false
  const [isMenuOpen, setIsMenuOpen] = useState(false);

  // 메뉴 하나를 클릭했을 때 실행되는 함수
  const handleNavClick = (key) => {
    onNavClick(key); // 부모(App)에게 어떤 메뉴를 눌렀는지 알려줌
    setIsMenuOpen(false); // 모바일에서는 메뉴를 고른 뒤 자동으로 닫아줌
  };

  // 로그아웃 버튼: 부모에게 알리고 모바일 메뉴 닫기
  const handleLogout = () => {
    onLogout();
    setIsMenuOpen(false);
  };

  // 로그인 상태에 따라 오른쪽에 보여줄 버튼 묶음
  // (PC 오른쪽과 모바일 메뉴 안에서 똑같이 쓰려고 변수에 담아둠)
  // user가 있으면(로그인 상태) 이름 + 로그아웃, 없으면 로그인 + 회원가입
  const authButtons = user ? (
    <>
      <span className="header-user">
        <UserRound size={18} />
        {user.name}님
      </span>
      <button className="login-button" onClick={handleLogout}>
        로그아웃
      </button>
    </>
  ) : (
    <>
      <button
        className={activeNav === "login" ? "login-button active" : "login-button"}
        onClick={() => handleNavClick("login")}
      >
        로그인
      </button>
      <button className="signup-button" onClick={() => handleNavClick("signup")}>
        회원가입
      </button>
    </>
  );

  return (
    // <header>: 페이지의 머리 부분이라는 의미의 HTML 태그
    <header className="header">
      {/* ===== 왼쪽: 로고 ===== */}
      {/* 로고를 누르면 홈으로 이동 */}
      <button className="header-logo" onClick={() => handleNavClick("home")}>
        생각한줄
      </button>

      {/*
        ===== 가운데: 메뉴 =====
        isMenuOpen이 true면 "header-nav open" 클래스가 붙음
        → 모바일 CSS에서 open일 때만 메뉴를 보여줌 (PC에서는 항상 보임)
      */}
      <nav className={isMenuOpen ? "header-nav open" : "header-nav"}>
        {NAV_ITEMS.map((item) => {
          // 아이콘이 있는 메뉴면 아이콘 컴포넌트를 꺼내둠 (없으면 undefined)
          const Icon = item.icon;

          return (
            <button
              key={item.key} // map으로 만든 요소를 구분하는 이름표 (필수)
              // 선택된 메뉴면 active 클래스를 붙여서 진하게 표시
              className={activeNav === item.key ? "nav-link active" : "nav-link"}
              onClick={() => handleNavClick(item.key)}
              // 아이콘만 보이는 메뉴는 화면 읽기 프로그램을 위해 이름을 알려줌
              aria-label={item.label}
            >
              {/*
                아이콘이 있으면: 아이콘 + 글자(글자는 PC에서 숨기고 모바일 메뉴에서만 보임)
                아이콘이 없으면: 글자만
              */}
              {Icon ? (
                <>
                  {/* <> </>: 아무 태그 없이 여러 요소를 묶을 때 쓰는 빈 태그 (Fragment) */}
                  <Icon size={18} />
                  <span className="nav-icon-label">{item.label}</span>
                </>
              ) : (
                item.label
              )}
            </button>
          );
        })}

        {/* 모바일 메뉴 안에서만 보이는 로그인/회원가입 (PC에서는 CSS로 숨김) */}
        <div className="header-nav-auth">{authButtons}</div>
      </nav>

      {/* ===== 오른쪽: 로그인 / 회원가입 또는 사용자 이름 / 로그아웃 (PC 화면용) ===== */}
      <div className="header-auth">{authButtons}</div>

      {/*
        ===== 모바일 전용: 햄버거 버튼 =====
        누를 때마다 isMenuOpen을 반대로 바꿈 (true ↔ false)
        ! : true를 false로, false를 true로 뒤집는 기호
      */}
      <button
        className="menu-toggle"
        onClick={() => setIsMenuOpen(!isMenuOpen)}
        // aria-label: 화면을 읽어주는 프로그램(시각장애인용)을 위한 설명
        aria-label="메뉴 열기"
      >
        {/* 메뉴가 열려 있으면 X 아이콘, 닫혀 있으면 ≡ 아이콘 */}
        {isMenuOpen ? <X size={24} /> : <Menu size={24} />}
      </button>
    </header>
  );
}

export default Header;
