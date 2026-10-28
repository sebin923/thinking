// =============================================================
// App.jsx — 앱 전체의 뼈대
// -------------------------------------------------------------
// 위에 Header(메뉴바), 가운데에 선택된 메뉴의 화면, 맨 아래에 Footer(정보 영역)를 보여줌.
// 지금 만든 화면: 홈(LandingPage), 글쓰기 학습(WritingPage), 퀴즈(QuizPage),
//                랭킹(RankingPage), 맞춤법 도전 모드(ChallengePage),
//                로그인(LoginPage), 회원가입(SignupPage),
//                마이페이지(MyPage), 회원정보 수정(MyPageEdit)
// 나머지 메뉴는 "준비 중" 화면이 나옴.
// (나중에 react-router를 배우면 주소(URL)로 페이지를 이동하는 방식으로 바꿀 예정)
// =============================================================

import { useState, useEffect, useCallback, useRef } from "react";

// 우리가 만든 컴포넌트들
import Header from "./components/Header";
import Footer from "./components/Footer";
import LandingPage from "./pages/LandingPage";
import WritingPage from "./pages/WritingPage";
import QuizPage from "./pages/QuizPage";
import LoginPage from "./pages/LoginPage";
import SignupPage from "./pages/SignupPage";
import RankingPage from "./pages/RankingPage";
import ChallengePage from "./pages/ChallengePage";
import WritingSettingPage from "./pages/WritingSettingPage";
import MyPage from "./pages/MyPage";
import MyPageEdit from "./pages/MyPageEdit";
// 관리자 페이지 (퀴즈·회원·랭킹 관리, 관리자 계정만)
import AdminPage from "./pages/AdminPage";
// 글쓰기에서 저장 안 한 채로 나가려고 할 때 띄우는 경고창
import LeaveConfirmModal from "./components/LeaveConfirmModal";
// 쓰다 만 글(한 번도 저장 안 한 글)을 서버에서 지우는 함수
import { discardUnsavedDocument } from "./api/mypage";

// 공통 CSS (헤더, 푸터 등)
import "./App.css";

// 로그인 정보(토큰 + 사용자)를 브라우저에 저장할 때 쓰는 이름표
const AUTH_KEY = "saenggak-hanjul-auth";

// 글쓰기에 속한 화면들 (글쓰기 ↔ 개인 맞춤 설정 사이를 오가는 건 "떠난 것"이 아님)
const WRITING_PAGES = ["write", "writing-settings"];

// 글쓰기 화면이 설정 화면에 다녀올 때 쓰는 임시저장본 이름표 (WritingPage.jsx의 getDraftKey와 똑같이 맞춤)
const writingDraftKey = (userId) => `saenggak-hanjul-draft-${userId ?? "guest"}`;

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

// ----- 지난번에 쓰다 만 글 정리하기 (컴퓨터가 꺼지거나 브라우저가 튕긴 경우) -----
// 보통은 글쓰기 화면을 떠날 때(메뉴 이동, 탭 닫기, 새로고침) 바로 정리되지만,
// 전원이 갑자기 꺼지거나 브라우저가 강제 종료되면 "떠난다"는 신호(pagehide)가 안 와서 못 지움
// → 다음에 사이트를 열 때(또는 로그인할 때) 브라우저에 남아 있는 임시저장본을 보고 마저 정리
//
// 임시저장본이 남아 있다 = 지난번에 정상적으로 떠나지 못했다는 뜻
//  (정상적으로 떠나면 App의 discardWriting이 항상 지우고,
//   설정 화면에 다녀오는 건 사이트 안에서만 이동하는 거라 그 사이에 이 함수가 불릴 일이 없음)
//  - 한 번도 저장 안 한 새 글이었으면 → 서버에서도 지움 (마이페이지에 안 남게)
//  - 한 번이라도 저장한 글이었으면 → 서버 글은 그대로, 저장 안 한 내용(임시저장본)만 버림
// authInfo: { token, user } (로그인 안 했으면 null)
function cleanupLeftoverDraft(authInfo) {
  const key = writingDraftKey(authInfo?.user?.user_id);
  try {
    const raw = localStorage.getItem(key);
    if (!raw) return; // 남은 게 없음 = 지난번에 잘 정리됨
    const leftover = JSON.parse(raw);
    if (
      authInfo?.token &&
      leftover?.createdHere && // 이번에 새로 만든 글만 (마이페이지에서 연 예전 글은 건드리지 않음)
      leftover.documentId &&
      leftover.savedVersion === 0 && // 한 번도 저장 안 함
      !leftover.isComplete
    ) {
      // 서버도 "저장본 0개인 글"만 지워 주니까, 혹시 판단이 틀려도 저장한 글이 지워질 일은 없음
      discardUnsavedDocument(authInfo.token, leftover.documentId);
    }
    localStorage.removeItem(key);
  } catch {
    // 저장소를 못 쓰거나 내용이 깨져 있으면 그냥 넘어감 (서버도 하루 지난 빈 글은 알아서 지움)
  }
}

// ----- 로그인 정보 다시 저장하기 (회원정보를 고쳤을 때) -----
// 처음 로그인할 때 골랐던 저장소(localStorage 또는 sessionStorage)에 그대로 덮어씀
// → "로그인 상태 유지"를 안 골랐던 사람이 갑자기 유지되는 일이 없게
function saveAuth(nextAuth) {
  try {
    const storage = localStorage.getItem(AUTH_KEY) ? localStorage : sessionStorage;
    storage.setItem(AUTH_KEY, JSON.stringify(nextAuth));
  } catch {
    // 저장 실패해도 지금 화면에서는 바뀐 정보로 보이니까 무시
  }
}

// ----- 저장된 로그인 정보 지우기 (로그아웃·탈퇴·토큰 만료) -----
function clearAuth() {
  try {
    localStorage.removeItem(AUTH_KEY);
    sessionStorage.removeItem(AUTH_KEY);
  } catch {
    // 무시
  }
}

function App() {
  // activeNav: 지금 보여줄 화면 이름
  //  - 헤더 메뉴: "home"(홈), "about"(서비스 소개), "write"(글쓰기 학습), "quiz"(퀴즈), "ranking"(랭킹), "guide"(이용안내)
  //  - 헤더 오른쪽 버튼: "login"(로그인), "signup"(회원가입)
  //  - 랭킹 화면 안의 버튼: "challenge"(맞춤법 도전 모드)
  //  - 푸터에만 있는 메뉴: "notice", "terms", "privacy"
  // 처음 들어오면 "home"
  const [activeNav, setActiveNav] = useState("home");

  // idea: 메인 페이지 입력창에 적은 생각 → 글쓰기 페이지로 넘겨줌
  const [idea, setIdea] = useState("");

  // openedDocument: 마이페이지 "내가 쓴 글"에서 연 글 { id, title, document_type, status, content, latest_version }
  // 이 값이 있으면 글쓰기 페이지가 빈 화면이 아니라 이 글을 채운 상태로 열림 (없으면 null = 새 글쓰기)
  const [openedDocument, setOpenedDocument] = useState(null);

  // writingSession: 글쓰기 화면에서 "새 글 쓰기"를 누를 때마다 1씩 올림
  // → WritingPage의 key가 바뀌어서 화면이 빈 새 글로 처음부터 다시 만들어짐 (저장 횟수도 0부터 = 첫 저장이 초안)
  const [writingSession, setWritingSession] = useState(0);

  // writingStateRef: 글쓰기 화면이 알려준 "지금 쓰는 글 상태" { documentId, savedVersion, isComplete, createdHere }
  // 화면에 보여줄 값이 아니라 떠날 때 확인만 하면 돼서 state 대신 ref에 보관 (바뀌어도 다시 그리지 않음)
  const writingStateRef = useRef(null);
  // useCallback: 함수가 매번 새로 만들어지지 않게 → WritingPage의 useEffect가 쓸데없이 다시 실행되지 않음
  const handleWritingStateChange = useCallback((state) => {
    writingStateRef.current = state;
  }, []);

  // leaveConfirm: 나가기 경고창 정보 (null이면 창 안 보임)
  //  { willDelete: 한 번도 저장 안 한 글이라 지워지는지, onLeave: "저장 안 하고 나가기"를 누르면 할 일 }
  const [leaveConfirm, setLeaveConfirm] = useState(null);

  // auth: 로그인 정보 { token, user } (로그인 안 했으면 null)
  // useState(loadAuth): 처음 한 번만 저장소에서 꺼내서 시작값으로 씀 → 새로고침해도 로그인 유지
  const [auth, setAuth] = useState(loadAuth);

  // quizCategory: 퀴즈 화면에서 지금 선택된 종류 ("spelling" = 맞춤법, "grammar" = 문법)
  // App에 두는 이유: 다른 메뉴에 갔다 와도 마지막으로 보던 종류가 그대로 남게 하려고
  // (랭킹은 맞춤법 도전 모드만 있어서 이 값과 상관없음)
  const [quizCategory, setQuizCategory] = useState("spelling");

  // loginNotice: 회원가입 직후 로그인 화면에 보여줄 안내 + 미리 채울 아이디
  const [loginNotice, setLoginNotice] = useState({ loginId: "", message: "" });

  // toast: 화면 아래에 잠깐 떴다 사라지는 알림 문구 (예: 회원 탈퇴 완료)
  const [toast, setToast] = useState("");
  // toastTimerRef: 알림을 지우는 예약(setTimeout) 번호를 기억 (새 알림이 오면 이전 예약 취소)
  const toastTimerRef = useRef(null);

  // 화면(App)이 사라질 때 남은 알림 예약도 취소
  useEffect(() => () => clearTimeout(toastTimerRef.current), []);

  // 사이트를 처음 열었을 때, 지난번에 비정상 종료로 못 지운 쓰다 만 글 정리 (위 cleanupLeftoverDraft 참고)
  // loadAuth()로 저장된 로그인 정보를 다시 꺼내 씀 → 처음 한 번만 실행하면 돼서 [] (의존성 없음)
  // ※ 개발 모드에서 두 번 실행돼도 괜찮음: 두 번째에는 임시저장본이 이미 지워져서 아무것도 안 함
  useEffect(() => {
    cleanupLeftoverDraft(loadAuth());
  }, []);

  // 알림 띄우기: 3초 뒤에 자동으로 사라짐
  const showToast = (message) => {
    clearTimeout(toastTimerRef.current);
    setToast(message);
    toastTimerRef.current = setTimeout(() => setToast(""), 3000);
  };

  // 화면(activeNav)이 바뀔 때마다 맨 위로 스크롤
  // useEffect(함수, [activeNav]) → activeNav 값이 바뀔 때마다 실행됨
  useEffect(() => {
    window.scrollTo({ top: 0 });
  }, [activeNav]);

  // ----- 쓰다 만 글 버리기 -----
  // 글쓰기 화면을 떠날 때 부름
  //  1) 저장 안 한 내용: 글쓰기 화면이 새로 만들어지면서 자연스럽게 사라짐 + 설정용 임시저장본도 여기서 지움
  //  2) 이번에 새로 만들었는데 한 번도 저장 안 한 글(예: "AI 초안 작성"만 누르고 떠남): 서버에서도 지움
  //     → 마이페이지에 빈 글이 남지 않게
  //  ※ 한 번이라도 저장한 글(초안·수정)이나 완료된 글은 그대로 둠 (저장 안 한 수정 내용만 사라짐)
  const discardWriting = () => {
    const state = writingStateRef.current;
    if (
      auth?.token &&
      state?.createdHere && // 마이페이지에서 연 예전 글은 건드리지 않음
      state.documentId &&
      state.savedVersion === 0 && // 한 번도 저장 안 함
      !state.isComplete
    ) {
      discardUnsavedDocument(auth.token, state.documentId);
    }
    writingStateRef.current = null;
    try {
      localStorage.removeItem(writingDraftKey(auth?.user?.user_id));
    } catch {
      // 무시
    }
  };

  // ----- 지금 글을 떠나면 잃어버리는 게 있는지 -----
  // 돌려주는 값: "delete"(한 번도 저장 안 한 글 → 서버에서도 지워짐) / "unsaved"(저장 안 한 수정만 사라짐) / null(잃을 것 없음)
  const getUnsavedLoss = () => {
    const state = writingStateRef.current;
    if (!state || state.isComplete) return null; // 글쓰기 화면이 아니거나 완료된 글(읽기 전용)
    if (state.createdHere && state.documentId && state.savedVersion === 0) return "delete";
    if (state.dirty) return "unsaved";
    return null; // 아무것도 안 썼거나 다 저장함 → 경고 없이 이동
  };

  // ----- 글쓰기를 떠나는 동작을 할 때 거치는 함수 -----
  // leave: 실제로 떠나는 동작 (메뉴 이동, 로그아웃, 새 글 시작 등)
  // 잃을 게 있으면 경고창을 먼저 띄우고, "저장 안 하고 나가기"를 눌렀을 때만 버리고 떠남
  const confirmLeaveWriting = (leave) => {
    const loss = getUnsavedLoss();
    const doLeave = () => {
      setLeaveConfirm(null);
      discardWriting(); // 쓰다 만 글 버리기 (위 discardWriting 참고)
      leave();
    };
    if (loss) {
      setLeaveConfirm({ willDelete: loss === "delete", onLeave: doLeave });
    } else {
      doLeave();
    }
  };

  // ----- 탭을 닫거나 새로고침할 때 -----
  // beforeunload: 페이지를 떠나기 직전 신호 → preventDefault 하면 브라우저 기본 경고창이 뜸
  //   (보안 때문에 브라우저가 문구를 못 바꾸게 막아 둬서, 우리 경고창 대신 브라우저 창이 나옴)
  // 그래도 떠나면 pagehide 신호에서 쓰다 만 글을 버림
  // 브라우저 신호(beforeunload·pagehide)를 처리하는 함수는 처음 한 번만 등록되니까,
  // 그 안에서 쓸 최신 값·함수는 ref에 넣어 두고 꺼내 씀 (화면이 다시 그려질 때마다 갱신)
  const activeNavRef = useRef(activeNav);
  const getUnsavedLossRef = useRef(getUnsavedLoss);
  const discardWritingRef = useRef(discardWriting);
  useEffect(() => {
    activeNavRef.current = activeNav;
    getUnsavedLossRef.current = getUnsavedLoss;
    discardWritingRef.current = discardWriting;
  });
  useEffect(() => {
    const handleBeforeUnload = (event) => {
      if (WRITING_PAGES.includes(activeNavRef.current) && getUnsavedLossRef.current()) {
        event.preventDefault();
        event.returnValue = ""; // 예전 브라우저용 (이 값이 있어야 경고창이 뜸)
      }
    };
    window.addEventListener("beforeunload", handleBeforeUnload);
    return () => window.removeEventListener("beforeunload", handleBeforeUnload);
  }, []);

  // ----- 탭을 닫거나 새로고침할 때도 쓰다 만 글 버리기 -----
  // pagehide: 페이지가 사라지기 직전에 브라우저가 알려주는 신호
  useEffect(() => {
    const handlePageHide = () => {
      if (WRITING_PAGES.includes(activeNavRef.current)) discardWritingRef.current();
    };
    window.addEventListener("pagehide", handlePageHide);
    // 정리 함수: App이 사라질 때 신호 듣기를 그만둠
    return () => window.removeEventListener("pagehide", handlePageHide);
  }, []);

  // ----- 메뉴 이동 -----
  // 로그인/회원가입 화면을 새로 열 때는 이전 안내 문구를 지움
  const handleNavigate = (key) => {
    const go = () => {
      if (key === "login" || key === "signup") setLoginNotice({ loginId: "", message: "" });
      // 헤더·푸터의 "글쓰기 학습"을 누르면 마이페이지에서 열었던 글은 닫고 새 글쓰기로 시작
      if (key === "write") setOpenedDocument(null);
      setActiveNav(key);
    };

    // 지금 쓰던 글을 떠나게 되는 경우
    //  1) 글쓰기(설정 화면 포함)에서 다른 메뉴로 갈 때
    //  2) 마이페이지에서 연 글을 쓰다가 "글쓰기 학습"을 눌러 새 글 화면으로 바뀔 때
    const inWriting = WRITING_PAGES.includes(activeNav);
    const leavesWriting =
      inWriting && (!WRITING_PAGES.includes(key) || (key === "write" && openedDocument !== null));

    if (leavesWriting) confirmLeaveWriting(go); // 잃을 게 있으면 경고창 → 확인하면 이동
    else go();
  };

  // ----- 글쓰기 화면의 "새 글 쓰기" 버튼 -----
  // 저장 안 한 내용이 있으면 경고창을 먼저 띄움 (확인하면 지금 글을 버리고 새 글 시작)
  const handleNewWriting = () => {
    confirmLeaveWriting(() => {
      setOpenedDocument(null); // 마이페이지에서 열었던 글이면 닫음
      setIdea(""); // 메인에서 적은 생각도 이전 글 거니까 비움
      setWritingSession((n) => n + 1); // key를 바꿔서 글쓰기 화면을 새로 만듦
    });
  };

  // ----- 마이페이지 "내가 쓴 글"에서 글을 눌렀을 때 -----
  // doc: { id, title, document_type, status, content } → 그 글이 들어간 글쓰기 페이지로 이동
  const handleOpenDocument = (doc) => {
    setOpenedDocument(doc);
    setActiveNav("write");
  };

  // ----- 메인에서 "생각 정리 시작하기" -----
  const handleStart = (newIdea) => {
    setIdea(newIdea); // 입력한 생각 저장
    setOpenedDocument(null); // 새 생각으로 시작하니까 마이페이지에서 열었던 글은 닫음
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
    // 지난번에 이 계정으로 쓰다가 컴퓨터가 꺼진 글이 있으면 정리 (로그인해야 서버 글을 지울 수 있어서 여기서도 한 번)
    cleanupLeftoverDraft(nextAuth);
    // 로그인 후 첫 화면: 관리자 계정이면 바로 관리자 페이지, 일반 회원은 홈
    // (role은 로그인 응답의 user에 들어 있음 → backend/auth_schemas.py의 UserOut)
    setActiveNav(nextAuth.user?.role === "admin" ? "admin" : "home");
    // TODO: 다른 API를 부를 때 헤더에 "Authorization: Bearer 토큰"을 붙여서 보내기
  };

  // ----- 로그아웃 -----
  const handleLogout = () => {
    const logout = () => {
      clearAuth();
      setAuth(null);
      setOpenedDocument(null); // 다른 사람이 로그인했을 때 이전 사람의 글이 열려 있지 않게
      setActiveNav("home");
    };
    // 글쓰기 중이면 저장 안 한 내용 확인 → 확인하면 쓰다 만 글을 버리고 로그아웃
    // (버리기는 토큰이 지워지기 전에 해야 서버에 요청할 수 있음 → confirmLeaveWriting이 logout보다 먼저 버림)
    if (WRITING_PAGES.includes(activeNav)) confirmLeaveWriting(logout);
    else logout();
  };

  // ----- 로그인 만료 (마이페이지에서 서버가 401을 돌려줬을 때) -----
  // useCallback: App이 다시 그려져도 같은 함수를 계속 쓰게 함
  // → 마이페이지의 useEffect 의존성 배열에 들어가 있어서, 함수가 매번 새로 만들어지면 불필요하게 다시 불러오게 됨
  const handleSessionExpired = useCallback(() => {
    clearAuth();
    setAuth(null);
    setLoginNotice({ loginId: "", message: "로그인이 만료됐어요. 다시 로그인해 주세요." });
    setActiveNav("login");
  }, []);

  // ----- 회원정보 수정 성공 (마이페이지 수정 화면) -----
  // 헤더의 "○○님"과 저장된 로그인 정보도 새 이름·이메일로 바꿔 줌
  const handleProfileUpdated = (profile) => {
    setAuth((prev) => {
      if (!prev) return prev;
      // { ...prev.user, name, email }: 기존 사용자 정보는 그대로 두고 이름·이메일만 바꿈
      const nextAuth = { ...prev, user: { ...prev.user, name: profile.name, email: profile.email } };
      saveAuth(nextAuth);
      return nextAuth;
    });
  };

  // ----- 회원 탈퇴 성공 -----
  // 로그인 정보를 지우고 홈으로 보낸 뒤 알림 띄우기
  const handleWithdrawn = (message) => {
    clearAuth();
    setAuth(null);
    setActiveNav("home");
    showToast(message);
  };

  // activeNav 값에 따라 가운데에 보여줄 화면을 고르는 함수
  // switch: 값에 따라 여러 경우로 나눌 때 쓰는 문법 (if를 여러 번 쓰는 것과 같음)
  const renderPage = () => {
    switch (activeNav) {
      case "home":
        return <LandingPage onStart={handleStart} />;
      case "write":
        return (
          <WritingPage
            // key: 연 글이 바뀌면 React가 글쓰기 화면을 새로 만들어서 그 글로 처음부터 채움
            // (key가 같으면 이전 글의 입력칸 값이 그대로 남아 있게 됨)
            key={openedDocument ? `document-${openedDocument.id}` : `new-${writingSession}`}
            // 마이페이지에서 연 글이면 메인에서 적은 생각(idea)은 상관없으니 빈 값으로
            idea={openedDocument ? "" : idea}
            auth={auth}
            initialDocument={openedDocument}
            onNewWriting={handleNewWriting}
            onWritingStateChange={handleWritingStateChange}
            // 설정 화면에 다녀와도 openedDocument는 그대로라서 같은 글로 돌아옴
            onOpenSettings={() => setActiveNav("writing-settings")}
          />
        );

      case "writing-settings":
        return (
          <WritingSettingPage
            auth={auth}
            onBack={() => setActiveNav("write")}
          />
        );
      case "quiz":
        return (
          <QuizPage
            // key: 종류가 바뀌면 React가 화면을 새로 만들어서 문제·점수가 처음부터 시작됨
            key={quizCategory}
            category={quizCategory}
            onChangeCategory={setQuizCategory}
            // 퀴즈는 연습용이라 랭킹 저장 없음 → 결과 화면에서 도전 모드로 안내
            onGoChallenge={() => setActiveNav("challenge")}
          />
        );
      case "ranking":
        return (
          <RankingPage
            user={auth?.user} // 내 순위 강조용
            onGoChallenge={() => setActiveNav("challenge")}
          />
        );
      case "challenge":
        return (
          <ChallengePage
            // user: 로그인한 사람 → 도전 기록을 그 사람 번호로 랭킹에 저장 (로그인 안 했으면 저장 안 함)
            user={auth?.user}
            onGoRanking={() => setActiveNav("ranking")}
            onGoLogin={() => handleNavigate("login")}
          />
        );
      case "mypage":
        return (
          <MyPage
            auth={auth}
            onEdit={() => setActiveNav("mypage-edit")}
            onGoWrite={() => handleNavigate("write")}
            onOpenDocument={handleOpenDocument}
            onGoLogin={() => handleNavigate("login")}
            onSessionExpired={handleSessionExpired}
          />
        );
      case "mypage-edit":
        return (
          <MyPageEdit
            auth={auth}
            onBack={() => setActiveNav("mypage")}
            onProfileUpdated={handleProfileUpdated}
            onWithdrawn={handleWithdrawn}
            onGoLogin={() => handleNavigate("login")}
            onSessionExpired={handleSessionExpired}
          />
        );
      case "admin":
        return (
          <AdminPage
            auth={auth}
            onGoLogin={() => handleNavigate("login")}
            onSessionExpired={handleSessionExpired}
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
        // 헤더 메뉴에 따로 없는 화면은 가까운 메뉴에 불이 들어오게 함
        //  - 도전 모드 → "랭킹" / 회원정보 수정 → 헤더의 "○○님"(마이페이지)
        activeNav={activeNav === "challenge" ? "ranking" : activeNav === "mypage-edit" ? "mypage" : activeNav}
        onNavClick={handleNavigate}
        user={auth?.user}
        onLogout={handleLogout}
      />

      {/* main: 페이지의 핵심 내용이 들어가는 영역 */}
      <main>{renderPage()}</main>

      {/* 맨 아래 푸터: 링크를 눌러도 헤더와 똑같이 화면이 바뀜 */}
      <Footer onNavClick={handleNavigate} />

      {/* 잠깐 떴다 사라지는 알림 (role="status": 화면 읽기 프로그램이 읽어 줌) */}
      {/* 글쓰기에서 저장 안 한 채로 나가려고 할 때 경고창 */}
      {leaveConfirm && (
        <LeaveConfirmModal
          willDelete={leaveConfirm.willDelete}
          onStay={() => setLeaveConfirm(null)} // 계속 쓰기: 창만 닫음
          onLeave={leaveConfirm.onLeave} // 저장 안 하고 나가기: 버리고 이동
        />
      )}

      {toast && (
        <div className="toast" role="status">
          {toast}
        </div>
      )}
    </div>
  );
}

export default App;
