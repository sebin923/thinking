// =============================================================
// App.jsx — 앱 전체의 뼈대
// -------------------------------------------------------------
// 위에 Header(메뉴바), 가운데에 선택된 메뉴의 화면, 맨 아래에 Footer(정보 영역)를 보여줌.
// 지금 만든 화면: 홈(LandingPage), 글쓰기 학습(WritingPage), 퀴즈(QuizPage)
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

// 공통 CSS (헤더, 푸터 등)
import "./App.css";

function App() {
  // activeNav: 지금 보여줄 화면 이름
  //  - 헤더 메뉴: "home"(홈), "about"(서비스 소개), "write"(글쓰기 학습), "quiz"(퀴즈), "guide"(이용안내)
  //  - 푸터에만 있는 메뉴: "notice", "terms", "privacy"
  // 메인에서 "생각 정리 시작하기"를 눌러도 "write"가 되니까, 헤더에서 "글쓰기 학습"이 선택된 걸로 보임
  // 처음 들어오면 "home"
  const [activeNav, setActiveNav] = useState("home");

  // idea: 메인 페이지 입력창에 적은 생각 → 글쓰기 페이지로 넘겨줌
  const [idea, setIdea] = useState("");

  // 화면(activeNav)이 바뀔 때마다 맨 위로 스크롤
  // useEffect(함수, [activeNav]) → activeNav 값이 바뀔 때마다 실행됨
  useEffect(() => {
    window.scrollTo({ top: 0 });
  }, [activeNav]);

  // 메인 페이지에서 생각을 입력하고 시작 버튼을 눌렀을 때 실행되는 함수
  // newIdea: 사용자가 입력창에 적은 생각 (LandingPage가 넘겨줌)
  const handleStart = (newIdea) => {
    setIdea(newIdea); // 입력한 생각 저장
    setActiveNav("write"); // 글쓰기 학습 화면으로 이동 (헤더의 "글쓰기 학습"과 같은 화면)

    // TODO: 원래 흐름은 ① 생각 입력 → ② 구조화(AI) → ③ 글쓰기
    // 지금은 ①②가 아직 없어서 바로 ③ 글쓰기 화면으로 보냄
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
        return <QuizPage />;
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
      {/* 상단 메뉴바: 어떤 메뉴가 선택됐는지와, 메뉴를 바꾸는 함수를 넘겨줌 */}
      <Header activeNav={activeNav} onNavClick={setActiveNav} />

      {/* main: 페이지의 핵심 내용이 들어가는 영역 */}
      <main>{renderPage()}</main>

      {/*
        맨 아래 푸터: Header와 같은 setActiveNav 함수를 넘겨줘서
        푸터 링크를 눌러도 똑같이 화면이 바뀌게 함
      */}
      <Footer onNavClick={setActiveNav} />
    </div>
  );
}

export default App;
