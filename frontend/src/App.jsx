// =============================================================
// App.jsx — 앱 전체의 뼈대
// -------------------------------------------------------------
// 위에 Header(메뉴바), 가운데에 선택된 메뉴의 화면, 맨 아래에 Footer(정보 영역)를 보여줌.
// 지금 만든 화면: 홈(LandingPage), 글쓰기 학습(WritingPage), 퀴즈(QuizPage),
//                로그인(LoginPage), 회원가입(SignupPage)
// 나머지 메뉴는 "준비 중" 화면이 나옴.
// (나중에 react-router를 배우면 주소(URL)로 페이지를 이동하는 방식으로 바꿀 예정)
// =============================================================

import { useState, useEffect } from "react";

// 우리가 만든 컴포넌트들
import Header from "./components/Header";
import Footer from "./components/Footer";
import LandingPage from "./pages/LandingPage";
import WritingPage from "./pages/WritingPage";
import QuizPage from "./pages/QuizPage";
import LoginPage from "./pages/LoginPage";
import SignupPage from "./pages/SignupPage";
import RankingPage from "./pages/RankingPage";

// 공통 CSS (헤더, 푸터 등)
import "./App.css";

// 로그인 정보(토큰 + 사용자)를 브라우저에 저장할 때 쓰는 이름표
const AUTH_KEY = "saenggak-hanjul-auth";

// ----- 저장된 로그인 정보 꺼내기 -----
// "로그인 상태 유지"를 체크했으면 localStorage(브라우저를 꺼도 남음)에,
// 안 했으면 sessionStorage(탭을 닫으면 사라짐)에 저장해 두었음 → 둘 다 찾아봄
function loadAuth() {
  try {
    const saved = localStorage.getItem(AUTH_KEY) || sessionStorage.getItem(AUTH_KEY);
    return saved ? JSON.parse(saved) : null; // { token, user } 또는 null
  } catch {
    return null; // 저장소를 못 쓰는 환경이면 로그인 안 된 상태로 시작
  }
}

function App() {
  // activeNav: 지금 보여줄 화면 이름
  //  - 헤더 메뉴: "home"(홈), "about"(서비스 소개), "write"(글쓰기 학습), "quiz"(퀴즈), "ranking"(랭킹), "guide"(이용안내)
  //  - 헤더 오른쪽 버튼: "login"(로그인), "signup"(회원가입)
  //  - 푸터에만 있는 메뉴: "notice", "terms", "privacy"
  // 처음 들어오면 "home"
  const [activeNav, setActiveNav] = useState("home");

  // idea: 메인 페이지 입력창에 적은 생각 → 글쓰기 페이지로 넘겨줌
  const [idea, setIdea] = useState("");

  // auth: 로그인 정보 { token, user } (로그인 안 했으면 null)
  // useState(loadAuth): 처음 한 번만 저장소에서 꺼내서 시작값으로 씀 → 새로고침해도 로그인 유지
  const [auth, setAuth] = useState(loadAuth);

  // quizCategory: 퀴즈·랭킹 화면에서 지금 선택된 종류 ("spelling" = 맞춤법, "grammar" = 문법)
  // App에 두는 이유: 퀴즈에서 "랭킹 보기"를 누르면 같은 종류의 랭킹이 바로 보이게 하려고
  const [quizCategory, setQuizCategory] = useState("spelling");

  // loginNotice: 회원가입 직후 로그인 화면에 보여줄 안내 + 미리 채울 아이디
  const [loginNotice, setLoginNotice] = useState({ loginId: "", message: "" });

  // 화면(activeNav)이 바뀔 때마다 맨 위로 스크롤
  // useEffect(함수, [activeNav]) → activeNav 값이 바뀔 때마다 실행됨
  useEffect(() => {
    window.scrollTo({ top: 0 });
  }, [activeNav]);

  // ----- 메뉴 이동 -----
  // 로그인/회원가입 화면을 새로 열 때는 이전 안내 문구를 지움
  const handleNavigate = (key) => {
    if (key === "login" || key === "signup") setLoginNotice({ loginId: "", message: "" });
    setActiveNav(key);
  };

  // ----- 메인에서 "생각 정리 시작하기" -----
  const handleStart = (newIdea) => {
    setIdea(newIdea); // 입력한 생각 저장
    setActiveNav("write"); // 글쓰기 학습 화면으로 이동 (헤더의 "글쓰기 학습"과 같은 화면)
    // TODO: 원래 흐름은 ① 생각 입력 → ② 구조화(AI) → ③ 글쓰기
  };

  // ----- 회원가입 성공 -----
  const handleSignupSuccess = (loginId) => {
    // 로그인 화면에 아이디를 미리 채우고 안내 문구 띄우기
    setLoginNotice({ loginId, message: "회원가입이 완료됐어요. 로그인해 주세요." });
    setActiveNav("login");
  };

  // ----- 로그인 성공 -----
  // result: 서버 응답 { access_token, user } / remember: "로그인 상태 유지" 체크 여부
  const handleLogin = (result, remember) => {
    const nextAuth = { token: result.access_token, user: result.user };
    try {
      // 유지 체크 → localStorage(계속 남음), 아니면 sessionStorage(탭 닫으면 사라짐)
      const storage = remember ? localStorage : sessionStorage;
      storage.setItem(AUTH_KEY, JSON.stringify(nextAuth));
    } catch {
      // 저장 실패해도 지금 화면에서는 로그인 상태로 쓸 수 있으니 무시
    }
    setAuth(nextAuth);
    setActiveNav("home");
    // TODO: 다른 API를 부를 때 헤더에 "Authorization: Bearer 토큰"을 붙여서 보내기
  };

  // ----- 로그아웃 -----
  const handleLogout = () => {
    try {
      localStorage.removeItem(AUTH_KEY);
      sessionStorage.removeItem(AUTH_KEY);
    } catch {
      // 무시
    }
    setAuth(null);
    setActiveNav("home");
  };

  // activeNav 값에 따라 가운데에 보여줄 화면을 고르는 함수
  // switch: 값에 따라 여러 경우로 나눌 때 쓰는 문법 (if를 여러 번 쓰는 것과 같음)
  const renderPage = () => {
    switch (activeNav) {
      case "home":
        return <LandingPage onStart={handleStart} />;
      case "write":
        return <WritingPage idea={idea} />;
      case "quiz":
        return (
          <QuizPage
            // key: 종류가 바뀌면 React가 화면을 새로 만들어서 문제·점수가 처음부터 시작됨
            key={quizCategory}
            category={quizCategory}
            onChangeCategory={setQuizCategory}
            // user: 로그인한 사람 정보 → 퀴즈 랭킹을 그 사람 번호로 저장 (로그인 안 했으면 저장 안 함)
            user={auth?.user}
            onGoRanking={() => setActiveNav("ranking")}
          />
        );
      case "ranking":
        return (
          <RankingPage
            key={quizCategory} // 종류가 바뀌면 랭킹을 새로 불러옴
            category={quizCategory}
            onChangeCategory={setQuizCategory}
            user={auth?.user}
            onGoQuiz={() => setActiveNav("quiz")}
          />
        );
      case "login":
        return (
          <LoginPage
            // key: 값이 바뀌면 React가 컴포넌트를 새로 만듦 → 미리 채울 아이디가 바뀌면 입력칸도 새로 시작
            key={loginNotice.loginId}
            onLogin={handleLogin}
            onGoSignup={() => handleNavigate("signup")}
            initialLoginId={loginNotice.loginId}
            notice={loginNotice.message}
          />
        );
      case "signup":
        return (
          <SignupPage onSignupSuccess={handleSignupSuccess} onGoLogin={() => handleNavigate("login")} />
        );
      default:
        // 위의 어떤 경우에도 해당 안 되면 "준비 중"
        return (
          <div className="placeholder">
            <h2>준비 중인 화면이에요</h2>
            <p>상단의 홈 아이콘을 눌러 메인으로 돌아가세요.</p>
          </div>
        );
    }
  };

  return (
    <div className="app">
      {/*
        상단 메뉴바
        - user: 로그인한 사용자 (auth?.user → auth가 null이면 에러 없이 undefined)
        - onLogout: 로그아웃 버튼을 누르면 실행
      */}
      <Header
        activeNav={activeNav}
        onNavClick={handleNavigate}
        user={auth?.user}
        onLogout={handleLogout}
      />

      {/* main: 페이지의 핵심 내용이 들어가는 영역 */}
      <main>{renderPage()}</main>

      {/* 맨 아래 푸터: 링크를 눌러도 헤더와 똑같이 화면이 바뀜 */}
      <Footer onNavClick={handleNavigate} />
    </div>
  );
}

export default App;
