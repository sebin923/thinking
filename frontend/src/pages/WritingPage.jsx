import { useState, useRef, useEffect } from "react";
import {
  PenLine,
  FilePlus2, // "새 글 쓰기" 버튼 아이콘
  Check,
  Bold,
  Italic,
  Underline,
  List,
  ListOrdered,
  AlignLeft,
  AlignCenter,
  Link,
  FileText,
  Lightbulb,
  CheckCircle2,
  Settings2,
  Sparkles,
  GraduationCap,
} from "lucide-react";
import PageHero from "../components/PageHero";
import "./WritingPage.css";
import "./WritingPageCustom.css";
const API_BASE_URL = "http://localhost:8000";
const TITLE_MAX = 50; // 제목 최대 글자 수
const BODY_MAX = 2000; // 본문 최대 글자 수
// 임시저장할 때 브라우저 저장소(localStorage)에 쓸 이름표
const DRAFT_KEY_PREFIX = "saenggak-hanjul-draft";
const getDraftKey = (userId) => `${DRAFT_KEY_PREFIX}-${userId ?? "guest"}`;
const WRITING_TYPES = [
  { value: "자유 글쓰기", label: "자유 글쓰기", detail: "주제와 형식에 제한 없이" },
  { value: "자기소개서", label: "자기소개서", detail: "경험과 역량을 중심으로" },
  { value: "보고서", label: "보고서", detail: "주제와 근거를 체계적으로" },
  { value: "발표문", label: "발표문", detail: "듣는 사람을 고려하여" },
  { value: "기타", label: "기타", detail: "원하는 글 유형 직접 입력" },
];
// 본문 툴바 버튼 목록
// command: 브라우저에 내릴 서식 명령 이름 (document.execCommand에 넣는 값)
// group: 같은 group끼리 묶고, group이 바뀌는 곳에 구분선을 그림
const TOOLBAR = [
  { command: "bold", icon: Bold, label: "굵게", group: 1 },
  { command: "italic", icon: Italic, label: "기울임", group: 1 },
  { command: "underline", icon: Underline, label: "밑줄", group: 1 },
  { command: "insertUnorderedList", icon: List, label: "점 목록", group: 2 },
  { command: "insertOrderedList", icon: ListOrdered, label: "번호 목록", group: 2 },
  { command: "justifyLeft", icon: AlignLeft, label: "왼쪽 정렬", group: 2 },
  { command: "justifyCenter", icon: AlignCenter, label: "가운데 정렬", group: 2 },
  { command: "createLink", icon: Link, label: "링크", group: 3 },
];
// 오른쪽 작성 팁 체크리스트
const TIPS = ["제목은 구체적으로", "핵심 내용을 중심으로", "문장은 간결하게"];
// ----- 임시저장된 글 꺼내기 (컴포넌트 밖에 만든 일반 함수) -----
// 저장된 글이 있으면 { title, html } 객체를, 없으면 null을 돌려줌
function loadDraft(userId) {
  // try { } catch { }: 안에서 에러가 나도 화면이 멈추지 않게 감싸는 문법
  // (브라우저 설정에 따라 localStorage 사용이 막혀 있을 수 있음)
  try {
    // localStorage.getItem: 브라우저에 저장해둔 값을 꺼냄 (없으면 null)
    const saved = localStorage.getItem(getDraftKey(userId));
    // 저장할 때 글자로 바꿔서 저장했으니, JSON.parse로 다시 객체로 되돌림
    return saved ? JSON.parse(saved) : null;
  } catch (error) {
    console.error("임시저장 불러오기 실패:", error);
    return null;
  }
}
// ----- 글 단계 정하기 (초안 / 수정 / 완료) -----
// 백엔드 routers/mypage.py의 get_stage와 똑같은 규칙 → 글쓰기 화면과 마이페이지가 항상 같은 단계를 보여줌
//  - 최종 저장을 누른 글                → 완료
//  - 2번 이상 저장한 글 (버전 2 이상)   → 수정  (처음 저장한 뒤 다시 저장할 때마다)
//  - 아직 저장 안 했거나 1번만 저장     → 초안  (맨 처음 저장 = 초안)
// ※ "AI 피드백 및 수정"도 피드백을 받기 전에 본문을 한 번 저장하기 때문에 저장 1번으로 셈
function getStage(savedVersion, isComplete) {
  if (isComplete) return "완료";
  if (savedVersion >= 2) return "수정";
  return "초안";
}
// 단계 → 배지 색 CSS 이름 (WritingPageCustom.css의 .writing-stage-badge.draft 등)
const STAGE_CLASS = { 초안: "draft", 수정: "revise", 완료: "done" };
// ----- 일반 글자 → 본문 칸에 넣을 HTML로 바꾸기 -----
// 서버에는 본문이 서식 없는 글자(줄바꿈 포함)로 저장돼 있음
// 본문 칸(div)에 그대로 넣으려면 &, <, > 같은 특수문자를 안전한 글자로 바꾸고, 줄바꿈은 <br>로 바꿔야 함
// (바꾸지 않으면 본문에 "<b>" 같은 글자가 있을 때 진짜 태그로 실행돼 버림)
function textToHtml(text) {
  return (text || "")
    .replace(/&/g, "&amp;")
    .replace(/</g, "&lt;")
    .replace(/>/g, "&gt;")
    .replace(/\n/g, "<br>");
}
// ----- 마이페이지에서 연 글 → 임시저장본과 같은 모양으로 바꾸기 -----
// doc: { id, title, document_type, status, content } (App이 넘겨줌)
// 임시저장본과 모양을 맞춰 두면, 아래에서 처음 값을 정하는 코드를 그대로 같이 쓸 수 있음
function documentToDraft(doc) {
  // 글쓰기 유형 버튼에 있는 값이면 그 버튼을, 없으면(직접 입력한 유형) "기타" + 직접 입력칸
  const isKnownType = WRITING_TYPES.some((item) => item.value === doc.document_type);
  return {
    title: doc.title || "",
    html: textToHtml(doc.content),
    writingType: isKnownType ? doc.document_type : "기타",
    customType: isKnownType ? "" : doc.document_type,
    documentId: doc.id, // ★ 이 번호가 있어야 저장할 때 새 글이 아니라 이 글에 이어서 저장됨
    savedVersion: doc.latest_version || 0, // 지금까지 저장한 횟수 (초안/수정 단계를 정하는 데 씀)
    isComplete: doc.status === "완료", // 최종 저장까지 끝난 글이면 읽기 전용으로 열기
    fromServer: true, // 서버에서 불러온 글이라는 표시 (안내 문구를 다르게 띄우려고)
  };
}
// ----- 서식이 들어간 HTML에서 글자 수만 세기 -----
function countText(html) {
  // 화면에 안 붙인 임시 div에 HTML을 넣고, 태그를 뺀 글자(textContent)만 꺼냄
  const temp = document.createElement("div");
  temp.innerHTML = html || "";
  return temp.textContent.trim().length;
}
// WritingPage 컴포넌트
// props:
//  - idea → 메인 페이지에서 처음 입력한 생각 (없으면 빈 문자열)
//  - initialDocument → 마이페이지 "내가 쓴 글"에서 연 글 { id, title, document_type, status, content, latest_version }
//                      (없으면 null → 새 글쓰기 또는 임시저장본 이어 쓰기)
//  - onNewWriting → "새 글 쓰기" 버튼을 눌렀을 때 실행 (App이 글쓰기 화면을 빈 새 글로 다시 만듦)
//  - onWritingStateChange → 지금 글 상태 { documentId, savedVersion, isComplete, createdHere }가 바뀔 때마다 App에 알려줌
//                           (App이 글쓰기 화면을 떠날 때 "쓰다 만 글"인지 보고 지우는 데 씀)
function WritingPage({
  idea = "",
  auth = null,
  onOpenSettings,
  initialDocument = null,
  onNewWriting,
  onWritingStateChange,
}) {
  const [pendingAiDraft, setPendingAiDraft] = useState(null);
  const [draftLoading, setDraftLoading] = useState(false);
  // draft: 페이지가 처음 뜰 때 딱 한 번 임시저장본을 꺼내서 기억해둠
  // useState(함수) 처럼 함수를 넣으면 "처음 한 번만" 그 함수를 실행해서 초기값으로 씀
  // (setDraft는 안 쓰니까 배열에서 첫 번째 값만 꺼냄)
  // 초기 글 유형/작성 방식도 임시저장에 함께 기록합니다.
  //
  // 처음 값을 정하는 순서
  //  1) 마이페이지에서 글을 열었고, 그 글을 고치다가 개인 맞춤 설정에 다녀온 경우
  //     → 브라우저 임시저장본이 서버 글보다 최신이니까 임시저장본 사용 (고치던 내용이 안 사라지게)
  //  2) 마이페이지에서 글을 연 경우 → 서버에 마지막으로 저장된 글
  //  3) 그 외 → 브라우저 임시저장본 (설정 화면에 다녀오기 전에 쓰던 글, 없으면 빈 새 글)
  //
  // ★ 글 단계(초안/수정/완료)는 "글 하나" 기준이라, 새 글은 저장 횟수 0부터 시작해야 함
  //   그래서 임시저장본은 한 번 화면에 옮기면 바로 지움 (resumedFromSettings → 아래 useEffect)
  //   → 안 지우면 나중에 새 글을 쓰러 왔을 때 예전 글 번호가 다시 살아나서
  //     새 글의 첫 저장이 예전 글의 "수정"으로 들어가 버림
  const [draft] = useState(() => {
    const saved = loadDraft(auth?.user?.user_id);
    if (!initialDocument) return saved ? { ...saved, resumedFromSettings: true } : null;
    if (saved?.documentId === initialDocument.id) return { ...saved, resumedFromSettings: true };
    return documentToDraft(initialDocument);
  });
  // isComplete: 최종 저장까지 끝난 글인지 (true면 제목·본문 수정과 저장 버튼이 막힘)
  const [isComplete, setIsComplete] = useState(Boolean(draft?.isComplete));
  // savedVersion: 이 글을 서버에 저장한 횟수 (= 마지막 버전 번호, 아직 안 했으면 0)
  // 0~1이면 초안, 2 이상이면 수정 단계 (getStage 참고)
  const [savedVersion, setSavedVersion] = useState(draft?.savedVersion || 0);
  // stage: 지금 글의 단계 (글쓰기 카드 제목 옆 배지에 보여줌)
  const stage = getStage(savedVersion, isComplete);
  // createdHere: 이 글을 지금 글쓰기 화면에서 새로 만들었는지
  // (마이페이지에서 연 예전 글은 false → 떠날 때 자동으로 지우면 안 되니까 구분해 둠)
  // 설정 화면에 다녀와도 유지되게 임시저장본에도 같이 기록함
  const [createdHere, setCreatedHere] = useState(Boolean(draft?.createdHere));
  // dirty: 마지막으로 저장한 뒤에 제목·본문을 고쳤는지 (true면 떠날 때 App이 경고창을 띄움)
  // 설정 화면에 다녀와도 "고친 게 있음"이 유지되게 임시저장본에서 이어받음
  const [dirty, setDirty] = useState(Boolean(draft?.dirty));
  const [writingType, setWritingType] = useState(draft?.writingType || "자유 글쓰기");
  const [customType, setCustomType] = useState(draft?.customType || "");
  const selectedDocumentType = writingType === "기타" ? customType.trim() : writingType;
  // title: 제목 입력칸 글자 (임시저장본이 있으면 그 제목으로 시작)
  // ?. (옵셔널 체이닝): draft가 null이면 에러 없이 undefined를 돌려줌
  const [title, setTitle] = useState(draft?.title || "");
  // bodyLength: 본문 글자 수 (본문 내용 자체는 editorRef로 직접 읽음)
  const [bodyLength, setBodyLength] = useState(() => countText(draft?.html));
  // toast: 화면 아래에 잠깐 떴다 사라지는 알림 문구 (빈 문자열이면 안 보임)
  // 임시저장본을 불러왔으면 처음부터 안내 문구를 띄운 상태로 시작
  const [toast, setToast] = useState(() => {
    if (!draft) return "";
    if (draft.fromServer) return `"${draft.title}" 글을 불러왔어요.`; // 마이페이지에서 연 글
    return "임시저장된 글을 불러왔어요.";
  });
  // documentId: 서버에 만들어진 글 번호 (null이면 아직 서버에 없는 새 글)
  // 마이페이지에서 열었거나 임시저장본에 번호가 있으면 그 번호로 시작 → 저장하면 그 글에 새 버전으로 쌓임
  const [documentId, setDocumentId] = useState(draft?.documentId ?? null);
  // 최종 저장된 글을 열었으면 처음부터 안내 문구를 보여줌
  const [apiMessage, setApiMessage] = useState(
    draft?.isComplete ? "최종 저장이 완료된 글이에요. 내용은 볼 수만 있어요." : ""
  );
  const [savedDrafts, setSavedDrafts] = useState([]);
  const [feedback, setFeedback] = useState(null);
  const [feedbackLoading, setFeedbackLoading] = useState(false);
  // editorRef: 본문 입력칸(div)을 가리키는 손잡이
  // editorRef.current 로 실제 HTML 요소에 접근할 수 있음
  const editorRef = useRef(null);
  // toastTimerRef: 알림을 지우는 타이머 번호를 기억해두는 곳
  // (useRef는 값이 바뀌어도 화면을 다시 그리지 않아서, 이런 "기억용 값"에 딱 맞음)
  const toastTimerRef = useRef(null);
  // ----- 알림 띄우기 함수 -----
  // message를 보여주고 2.5초 뒤에 자동으로 지움
  const showToast = (message) => {
    setToast(message);
    // 앞에서 띄운 알림의 타이머가 남아 있으면 취소
    // (안 그러면 새 알림이 뜨자마자 이전 타이머 때문에 금방 사라질 수 있음)
    clearTimeout(toastTimerRef.current);
    // setTimeout(함수, 밀리초): 정해진 시간 뒤에 함수를 한 번 실행하고, 타이머 번호를 돌려줌
    toastTimerRef.current = setTimeout(() => setToast(""), 2500);
  };
  // 설정 화면에 다녀와서 이어 쓰는 경우, 그때 만든 임시저장본은 이미 화면에 옮겼으니 지움
  // → 나중에 마이페이지에서 같은 글을 다시 열 때 예전 임시저장본이 아니라 서버의 최신 글이 열리고,
  //   새 글을 쓰러 왔을 때 예전 글이 다시 불러와지지 않게
  // (useState 안이 아니라 useEffect에서 지우는 이유: 개발 모드(StrictMode)에서는 useState 초기값 함수가
  //  두 번 실행될 수 있어서, 거기서 지우면 두 번째 실행 때 임시저장본을 못 찾게 됨)
  useEffect(() => {
    if (draft?.resumedFromSettings) {
      try {
        localStorage.removeItem(getDraftKey(auth?.user?.user_id));
      } catch {
        // 지우기 실패해도 화면에는 문제없으니 무시
      }
    }
    // draft와 auth는 처음 한 번 정해지고 안 바뀌니까 사실상 처음 한 번만 실행됨
  }, [draft, auth?.user?.user_id]);
  // ----- 지금 글 상태를 App에 알려주기 -----
  // 글 번호·저장 횟수·완료 여부가 바뀔 때마다 App에 전달
  // → App은 사용자가 다른 메뉴로 갈 때 이 값을 보고, "새로 만들었는데 한 번도 저장 안 한 글"이면 서버에서 지움
  useEffect(() => {
    onWritingStateChange?.({ documentId, savedVersion, isComplete, createdHere, dirty });
  }, [documentId, savedVersion, isComplete, createdHere, dirty, onWritingStateChange]);
  // 페이지를 떠날 때(컴포넌트가 사라질 때) 남은 타이머 정리
  // useEffect 안에서 return한 함수는 "정리(clean-up) 함수"로, 화면에서 사라질 때 실행됨
  useEffect(() => {
    return () => clearTimeout(toastTimerRef.current);
  }, []);
  // ----- 화면이 처음 뜰 때: 임시저장된 본문을 입력칸에 넣기 -----
  // useEffect(함수, [draft]) → draft는 처음 한 번 정해지고 안 바뀌니까 사실상 처음 한 번만 실행됨
  // 본문 칸(div)은 React가 아니라 우리가 직접 관리하니까, 여기서 HTML을 직접 넣어줌
  useEffect(() => {
    if (draft && editorRef.current) {
      // innerHTML: 서식(굵게 등)까지 포함된 본문 내용
      editorRef.current.innerHTML = draft.html || "";
    }
    // 처음부터 떠 있는 "불러왔어요" 안내는 2.5초 뒤에 지움
    // (setTimeout 안에서 state를 바꾸는 건 괜찮음 — 바로 바꾸는 게 아니라 나중에 바꾸니까)
    if (draft) {
      toastTimerRef.current = setTimeout(() => setToast(""), 2500);
    }
  }, [draft]);
  // ----- 본문에 글자를 칠 때마다 실행 -----
  const handleBodyInput = () => {
    // innerText: 서식 없이 글자만 꺼냄 → 글자 수 세기용
    setBodyLength(editorRef.current.innerText.trim().length);
    // 본문이 수정되면 이전 피드백 표시 제거
    setFeedback(null);
    // 저장 안 한 수정이 생김 → 떠날 때 경고창 대상
    setDirty(true);
  };
  // ----- 툴바 버튼을 눌렀을 때 -----
  const handleToolbar = (command) => {
    let value = null; // 명령에 필요한 추가 값 (링크 주소 등)
    if (command === "createLink") {
      // 링크는 주소가 필요해서 입력창을 띄워 물어봄
      value = window.prompt("연결할 주소를 입력하세요", "https://");
      if (!value) return; // 취소하거나 비워두면 아무것도 안 함
    }
    // document.execCommand: 본문에서 선택(드래그)한 글자에 서식을 입히는 브라우저 기능
    // ※ 오래된 기능이라 "곧 없어질 예정"으로 분류돼 있지만 지금 모든 브라우저에서 동작함
    //   (나중에 기능을 늘릴 때는 TipTap 같은 에디터 라이브러리로 바꾸는 걸 추천)
    document.execCommand(command, false, value);
    editorRef.current.focus(); // 버튼 누른 뒤에도 계속 이어서 쓸 수 있게 본문에 커서 돌려놓기
    handleBodyInput();
  };
  const getBodyText = () => {
    return editorRef.current?.innerText?.trim() || "";
  };
  const getBodyHtml = () => {
    return editorRef.current?.innerHTML || "";
  };
  const saveBrowserDraft = () => {
    try {
      localStorage.setItem(getDraftKey(auth?.user?.user_id), JSON.stringify({
        title,
        html: editorRef.current?.innerHTML || "",
        writingType,
        customType,
        // 서버에 이미 만들어진 글이면 그 번호도 같이 기억
        // → 설정 화면에 다녀와도 같은 글에 이어서 저장됨 (없으면 새 글이 하나 더 생겨 버림)
        documentId,
        isComplete,
        savedVersion, // 설정 화면에 다녀와도 초안/수정 단계가 그대로 유지되게
        createdHere, // 설정 화면에 다녀와도 "새로 만든 글" 표시가 유지되게
        dirty, // 설정 화면에 다녀와도 "저장 안 한 수정 있음"이 유지되게 (떠날 때 경고창용)
        savedAt: new Date().toISOString(),
      }));
      return true;
    } catch (error) {
      console.error("임시저장 실패:", error);
      return false;
    }
  };

  // ----- 새 글 쓰기 버튼 -----
  // 지금 글을 닫고 빈 새 글로 시작 → 새 글은 저장 횟수 0부터 (첫 저장 = 초안)
  // 저장 안 한 내용이 있으면 App이 "나가기 경고창"을 띄워서 한 번 물어봄 (메뉴 이동할 때와 같은 창)
  const handleNewWriting = () => {
    onNewWriting?.();
  };

  const handleOpenSettings = () => {
    saveBrowserDraft();
    onOpenSettings?.();
  };

  const createDocumentIfNeeded = async () => {
    if (documentId) {
      return documentId;
    }
    if (title.trim() === "") {
      showToast("제목을 입력해 주세요.");
      throw new Error("제목 없음");
    }
    if (!selectedDocumentType) {
      showToast("글 유형을 입력해 주세요.");
      throw new Error("글 유형 없음");
    }
    const response = await fetch(
      `${API_BASE_URL}/api/documents`,
      {
        method: "POST",
        headers: getAuthHeaders(),
        body: JSON.stringify({
          document_type: selectedDocumentType,
          title: title.trim(),
        }),
      }
    );
    if (!response.ok) {
      throw new Error("문서 생성 실패");
    }
    const data = await response.json();
    setDocumentId(data.id);
    setCreatedHere(true); // 이 화면에서 새로 만든 글이라고 표시 (저장 안 하고 떠나면 App이 지움)
    return data.id;
  };
  const saveThoughtFromIdea = async (targetDocumentId) => {
    const thoughtText = idea || getBodyText();
    if (!thoughtText.trim()) {
      showToast("AI 초안을 만들 생각이나 본문이 필요해요.");
      throw new Error("생각 없음");
    }
    const response = await fetch(
      `${API_BASE_URL}/api/thoughts`,
      {
        method: "POST",
        headers: getAuthHeaders(),
        body: JSON.stringify({
          document_id: targetDocumentId,
          content: thoughtText,
        }),
      }
    );
    if (!response.ok) {
      throw new Error("생각 저장 실패");
    }
    await response.json();
  };
  const handleAiDraft = async () => {
    if (draftLoading || isComplete) return;
    setDraftLoading(true);
    try {
      showToast("AI가 초안을 작성하고 있어요.");
      const targetDocumentId = await createDocumentIfNeeded();
      await saveThoughtFromIdea(targetDocumentId);
      const response = await fetch(
        `${API_BASE_URL}/api/documents/${targetDocumentId}/draft-ai`,
        {
          method: "POST",
          headers: getAuthHeaders()
        }
      );
      if (!response.ok) {
        const errorData = await response.json();
        throw new Error(
          errorData.detail || "AI 초안 작성 실패"
        );
      }
      const data = await response.json();
      // 원문을 자동 덮어쓰지 않고 사용자가 초안을 확인한 후 적용합니다.
      setPendingAiDraft(data.content || "");
      setApiMessage("AI 초안이 생성되었습니다. 아래에서 내용을 확인해 주세요.");
      showToast("AI 초안 작성 완료");
    } catch (error) {
      console.error(error);
      showToast(error.message || "AI 초안 작성 실패");
    } finally {
      setDraftLoading(false);
    }
  };
  const handleSaveVersion = async () => {
    try {
      const bodyText = getBodyText();
      if (title.trim() === "") {
        showToast("제목을 입력해 주세요.");
        return;
      }
      if (!bodyText) {
        showToast("본문을 작성해 주세요.");
        return;
      }
      const targetDocumentId = await createDocumentIfNeeded();
      const response = await fetch(
        `${API_BASE_URL}/api/drafts`,
        {
          method: "POST",
          headers: getAuthHeaders(),
          body: JSON.stringify({
            document_id: targetDocumentId,
            content: bodyText,
          }),
        }
      );
      if (!response.ok) {
        const errorData = await response.json();
        throw new Error(
          errorData.detail || "초안 저장 실패"
        );
      }
      const data = await response.json();
      // 서버가 알려준 버전 번호로 저장 횟수 갱신 → 위쪽 단계 배지도 같이 바뀜
      setSavedVersion(data.version);
      setDirty(false); // 방금 저장했으니 "저장 안 한 수정" 없음
      // 맨 처음 저장(버전 1)은 초안, 그다음부터는 수정으로 저장됨
      if (data.version === 1) {
        setApiMessage("초안으로 저장했어요. 다음 저장부터는 '수정' 단계로 저장돼요.");
        showToast("초안 저장 완료");
      } else {
        setApiMessage(`수정본으로 저장했어요. (${data.version}번째 저장)`);
        showToast("수정본 저장 완료");
      }
    } catch (error) {
      console.error(error);
      showToast(error.message || "초안 저장 실패");
    }
  };
  const handleAiFeedback = async () => {
    if (feedbackLoading) return;
    const bodyText = getBodyText();
    if (!title.trim() || !bodyText) {
      showToast("제목과 본문을 먼저 작성해 주세요.");
      return;
    }
    if (bodyText.length > BODY_MAX) {
      showToast(`본문은 ${BODY_MAX}자 이하로 작성해 주세요.`);
      return;
    }
    setFeedbackLoading(true);
    setFeedback(null);
    try {
      const targetDocumentId = await createDocumentIfNeeded();
      const saveResponse = await fetch(`${API_BASE_URL}/api/drafts`, {
        method: "POST",
        headers: getAuthHeaders(),
        body: JSON.stringify({
          document_id: targetDocumentId,
          content: bodyText,
        }),
      });
      if (!saveResponse.ok) {
        throw new Error("글 저장에 실패했습니다.");
      }
      const savedDraft = await saveResponse.json();
      // 피드백 받기 전에 본문을 한 번 저장했으니 저장 횟수도 갱신 (초안 → 수정 단계가 바뀔 수 있음)
      setSavedVersion(savedDraft.version);
      setDirty(false); // 피드백 받기 전에 본문을 저장했으니 "저장 안 한 수정" 없음
      const feedbackResponse = await fetch(
        `${API_BASE_URL}/api/drafts/${savedDraft.id}/feedback-ai`,
        {
          method: "POST",
          headers: getAuthHeaders()
        }
      );
      if (!feedbackResponse.ok) {
        const errorData = await feedbackResponse.json().catch(() => ({}));
        throw new Error(errorData.detail || "AI 피드백 요청에 실패했습니다.");
      }
      const result = await feedbackResponse.json();
      setFeedback(result.feedback);
      setApiMessage("");
      showToast("AI 피드백이 완료되었습니다.");
    } catch (error) {
      console.error("AI 피드백 오류:", error);
      showToast(error.message || "AI 피드백 요청 실패");
    } finally {
      setFeedbackLoading(false);
    }
  };
  const handleLoadDrafts = async () => {
    try {
      if (!documentId) {
        showToast("먼저 버전을 저장해 주세요.");
        return;
      }
      const response = await fetch(
        `${API_BASE_URL}/api/documents/${documentId}/drafts`,
        { headers: getAuthHeaders() }
      );
      if (!response.ok) {
        throw new Error("저장된 버전 불러오기 실패");
      }
      const data = await response.json();
      setSavedDrafts(data);
      setApiMessage("저장된 버전을 불러왔습니다.");
      showToast("저장된 버전 불러오기 완료");
    } catch (error) {
      console.error(error);
      showToast(error.message || "저장된 버전 불러오기 실패");
    }
  };
  const getAuthHeaders = () => {
    const headers = {
      "Content-Type": "application/json"
    };

    if (auth?.token) {
      headers.Authorization = `Bearer ${auth.token}`;
    }

    return headers;
  };
  // ----- 임시저장 버튼 -----
  const handleSaveDraft = () => {
    showToast(saveBrowserDraft() ? "임시저장했어요." : "임시저장에 실패했어요.");
  };
  // ----- 작성 완료 버튼 -----
  const handleComplete = async () => {
    const bodyText = getBodyText();
    if (!title.trim() || !bodyText) {
      showToast("제목과 본문을 입력해 주세요.");
      return;
    }
    if (bodyText.length > BODY_MAX) {
      showToast(`본문은 ${BODY_MAX}자 이하로 작성해 주세요.`);
      return;
    }
    try {
      const targetDocumentId = await createDocumentIfNeeded();
      // 최종 내용을 새 버전으로 저장
      const saveResponse = await fetch(`${API_BASE_URL}/api/drafts`, {
        method: "POST",
        headers: getAuthHeaders(),
        body: JSON.stringify({
          document_id: targetDocumentId,
          content: bodyText,
        }),
      });
      if (!saveResponse.ok) {
        throw new Error("최종 글 저장에 실패했습니다.");
      }
      // 최종 저장도 본문을 새 버전으로 한 번 저장하니까 저장 횟수 갱신 (배지의 "○번 저장"이 서버와 맞게)
      const finalDraft = await saveResponse.json();
      setSavedVersion(finalDraft.version);
      setDirty(false); // 최종 저장까지 끝남
      // 문서 상태를 '완료'로 변경
      const completeResponse = await fetch(
        `${API_BASE_URL}/api/documents/${targetDocumentId}/complete`,
        { method: "PATCH", headers: getAuthHeaders() }
      );
      if (!completeResponse.ok) {
        throw new Error("문서 완료 처리에 실패했습니다.");
      }
      setIsComplete(true);
      setPendingAiDraft(null);
      setApiMessage("최종 저장이 완료되었습니다. 이 글은 이제 '완료' 단계예요. 다른 글은 위쪽 '새 글 쓰기'로 시작해 주세요.");
      localStorage.removeItem(getDraftKey(auth?.user?.user_id));
      showToast("최종 저장 완료!");
    } catch (error) {
      console.error("최종 저장 오류:", error);
      showToast(error.message || "최종 저장 실패");
    }
  };
  return (
    <div className="sub-page">
      <div className="sub-page-inner">
        {/* ===== 1. 페이지 제목 영역 ===== */}
        <PageHero
          eyebrow="당신의 생각이, 하나의 글이 되는 과정"
          title="내 생각을 글로 완성해보세요"
          description={
            "필요한 AI 기능을 자유롭게 선택해 글을 완성해보세요.\n" +
            "AI를 사용하지 않고 바로 저장할 수도 있습니다."
          }
          memoText={"당신의\n생각이\n글이 되는 곳"}
          memoVariant="note"
        />
        {/* ===== 3. 글쓰기 카드 + 작성 팁 ===== */}
        <div className="writing-layout">
          {/* ----- 왼쪽: 글쓰기 카드 ----- */}
          <section className="panel writing-card">
            <div className="writing-card-heading">
              <h2 className="writing-card-title">
                <PenLine size={22} /> 글쓰기
                {/* 지금 글의 단계 배지 (초안 / 수정 / 완료) + 저장 횟수 */}
                <span className={`writing-stage-badge ${STAGE_CLASS[stage]}`} title="마이페이지 '내가 쓴 글'에도 이 단계로 보여요">
                  {stage}
                  <small>{savedVersion > 0 ? `· ${savedVersion}번 저장` : "· 저장 전"}</small>
                </span>
              </h2>
              {/* 오른쪽 위 버튼들: (이미 저장된 글을 쓰는 중이면) 새 글 쓰기 + 개인 맞춤 설정 */}
              <div className="writing-heading-actions">
                {documentId !== null && (
                  <button type="button" className="writing-settings-button writing-new-button" onClick={handleNewWriting}>
                    <FilePlus2 size={16} /> 새 글 쓰기
                  </button>
                )}
                <button type="button" className="writing-settings-button" onClick={handleOpenSettings}>
                  <Settings2 size={16} /> 개인 맞춤 설정
                </button>
              </div>
            </div>
            <div className="writing-setup">
              <div className="writing-setup-header">
                <span className="field-label">어떤 글을 작성할까요?</span>
              </div>
              {/* 글 유형 버튼 줄: 왼쪽에 유형 버튼들, 같은 줄 오른쪽 끝에 버전 저장 */}
              <div className="writing-type-row">
                <div className="writing-type-options" role="group" aria-label="글 유형 선택">
                  {WRITING_TYPES.map((item) => (
                    <button
                      key={item.value}
                      type="button"
                      className={`writing-type-option ${writingType === item.value ? "selected" : ""}`}
                      aria-pressed={writingType === item.value}
                      disabled={documentId !== null}
                      title={item.detail}
                      onClick={() => setWritingType(item.value)}
                    >
                      {item.label}
                    </button>
                  ))}
                </div>
                {/* 버전 저장: 지금 본문을 새 버전으로 서버에 저장 (예전엔 맨 아래 최종 저장 옆에 있었음) */}
                <button
                  type="button"
                  className="writing-settings-button writing-version-button"
                  onClick={handleSaveVersion}
                  disabled={feedbackLoading || draftLoading || isComplete}
                >
                  <FileText size={16} /> 버전 저장
                </button>
              </div>
              {writingType === "기타" && (
                <input
                  className="writing-custom-type"
                  value={customType}
                  maxLength={50}
                  disabled={documentId !== null}
                  onChange={(event) => setCustomType(event.target.value)}
                  placeholder="예: 독후감, 에세이, 기획서"
                  aria-label="직접 입력할 글 유형"
                />
              )}
              {documentId !== null && <p className="writing-hint">문서가 생성된 뒤에는 글 유형을 변경할 수 없습니다.</p>}
            </div>
            {/* 제목 입력 */}
            {/* htmlFor: 이 라벨이 어떤 입력칸 것인지 id로 연결 (라벨을 눌러도 입력칸에 커서가 감) */}
            <label className="field-label" htmlFor="writing-title">
              제목
            </label>
            <div className="title-input-box">
              <input
                id="writing-title"
                type="text"
                placeholder="글의 제목을 입력해주세요."
                value={title}
                // 글자를 칠 때마다 title에 저장
                onChange={(event) => {
                  setTitle(event.target.value);
                  setDirty(true); // 저장 안 한 수정이 생김
                }}
                disabled={isComplete}
                maxLength={TITLE_MAX}
              />
              {/* 글자 수 표시 (예: 12/50) */}
              <span className="counter">
                {title.length}/{TITLE_MAX}
              </span>
            </div>
            {/* 본문 */}
            <span className="field-label" id="writing-body-label">
              본문
            </span>
            <div className="editor-box">
              {/* 툴바 */}
              <div className="editor-toolbar" role="toolbar" aria-label="본문 서식">
                {TOOLBAR.map((tool, index) => {
                  const Icon = tool.icon;
                  // 앞 버튼과 group이 다르면 그 사이에 구분선을 넣음
                  const needDivider = index > 0 && TOOLBAR[index - 1].group !== tool.group;
                  return (
                    // <span>으로 감싼 이유: 구분선과 버튼을 한 묶음으로 반복하려고
                    <span key={tool.command} className="toolbar-item">
                      {needDivider && <span className="toolbar-divider" aria-hidden="true" />}
                      <button
                        type="button"
                        className="toolbar-button"
                        title={tool.label}
                        aria-label={tool.label}
                        // onMouseDown에서 preventDefault: 버튼을 눌러도 본문에서 선택한 글자가 풀리지 않게 함
                        // (안 막으면 버튼으로 초점이 옮겨가면서 드래그한 선택이 사라짐)
                        onMouseDown={(event) => event.preventDefault()}
                        onClick={() => handleToolbar(tool.command)}
                      >
                        <Icon size={16} />
                      </button>
                    </span>
                  );
                })}
              </div>
              {/*
                본문 입력칸
                contentEditable: 일반 div를 글을 쓸 수 있는 칸으로 만듦
                → textarea와 달리 굵게/밑줄 같은 서식을 넣을 수 있음
              */}
              <div
                ref={editorRef}
                className={bodyLength === 0 ? "editor is-empty" : "editor"}
                contentEditable={!isComplete}
                // React가 "contentEditable 안의 내용은 React가 관리 안 한다"는 경고를 안 띄우게
                suppressContentEditableWarning
                onInput={handleBodyInput}
                role="textbox"
                aria-multiline="true"
                aria-labelledby="writing-body-label"
                // 비어 있을 때 보여줄 안내 문구 (CSS의 ::before가 이 값을 꺼내서 보여줌)
                data-placeholder={
                  "직접 글을 작성하거나 AI 초안을 활용할 수 있습니다."
                }
              />
              {/* 본문 글자 수 (2000자 넘으면 over 클래스로 빨갛게) */}
              <div className={bodyLength > BODY_MAX ? "editor-counter over" : "editor-counter"}>
                {bodyLength.toLocaleString()} / {BODY_MAX.toLocaleString()}
              </div>
            </div>

            {/* 원하는 AI 기능을 순서 없이 사용할 수 있습니다. */}
            <div className="writing-ai-tools">
              <h3 className="writing-ai-tools-title">AI 글쓰기 도구</h3>
              <p className="writing-ai-tools-subtitle">필요한 기능만 선택하세요. AI 사용은 필수가 아닙니다.</p>
              <div className="writing-ai-tool-buttons">
                <button type="button" className="writing-ai-tool-button" onClick={handleAiDraft} disabled={draftLoading || feedbackLoading || isComplete}>
                  <FileText size={19} />
                  <span><strong>{draftLoading ? "AI 초안 생성 중..." : "AI 초안 작성"}</strong><small>입력한 생각을 바탕으로 초안 생성</small></span>
                </button>
                <button type="button" className="writing-ai-tool-button" onClick={handleAiFeedback} disabled={draftLoading || feedbackLoading || isComplete}>
                  <Lightbulb size={19} />
                  <span><strong>{feedbackLoading ? "AI 분석 중..." : "AI 피드백 및 수정"}</strong><small>문제점 분석과 개선 방향 확인</small></span>
                </button>
                <button type="button" className="writing-ai-tool-button" disabled title="코칭 API 연결 후 이용할 수 있습니다.">
                  <GraduationCap size={19} />
                  <span><strong>AI 글쓰기 코칭</strong><small>맞춤형 질문과 힌트 (준비 중)</small></span>
                </button>
              </div>
            </div>
            {pendingAiDraft !== null && (
              <section className="writing-ai-draft-preview" aria-label="AI 초안 미리보기">
                <h3>AI 초안 미리보기</h3>
                <p>작성 중인 글은 아직 변경되지 않았습니다.</p>
                <div className="writing-ai-preview-text">{pendingAiDraft}</div>
                <div className="writing-ai-preview-actions">
                  <button type="button" className="btn-outline" onClick={() => setPendingAiDraft(null)}>취소</button>
                  <button type="button" className="btn-primary" onClick={() => {
                    if (editorRef.current) {
                      editorRef.current.innerText = pendingAiDraft;
                      handleBodyInput();
                    }
                    setPendingAiDraft(null);
                    showToast("AI 초안이 본문에 적용되었습니다.");
                  }}>본문에 적용하기</button>
                </div>
              </section>
            )}
            {/* 맨 아래: 최종 저장 (버전 저장은 위쪽 "개인 맞춤 설정" 아래로 옮김) */}
            <div className="writing-actions writing-save-actions">
              <button type="button" className="btn-primary" onClick={handleComplete} disabled={feedbackLoading || draftLoading || isComplete}>
                <Check size={18} /> {isComplete ? "저장 완료" : "최종 저장"}
              </button>
            </div>
            {apiMessage && (
              <p className="writing-api-message">
                {apiMessage}
              </p>
            )}
            {savedDrafts.length > 0 && (
              <div style={{ marginTop: "20px" }}>
                <h3>저장된 버전</h3>
                {savedDrafts.map((item) => (
                  <div
                    key={item.id}
                    style={{
                      border: "1px solid #ddd",
                      borderRadius: "12px",
                      padding: "14px",
                      marginTop: "12px",
                      backgroundColor: "#fff",
                    }}
                  >
                    <strong>버전 {item.version}</strong>
                    <p
                      style={{
                        whiteSpace: "pre-wrap",
                        marginTop: "10px",
                      }}
                    >
                      {item.content}
                    </p>
                    <small>
                      저장 시간: {item.created_at}
                    </small>
                  </div>
                ))}
              </div>
            )}
          </section>
          {/* AI 피드백이 있으면 작성 팁 대신 피드백만 보여줍니다. */}
          <aside className="panel tip-card">
            {feedback ? (
              <div className="ai-feedback-panel">
                <h2 className="tip-title">AI 피드백 결과</h2>
                <p className="ai-feedback-summary">
                  {feedback.overall_feedback}
                </p>
                <h4>수정 권장 문장</h4>
                {feedback.highlights?.length > 0 ? (
                  feedback.highlights.map((item, index) => (
                    <div className="ai-feedback-item" key={index}>
                      <p><strong>원문:</strong> {item.original_text}</p>
                      <p><strong>개선 이유:</strong> {item.reason}</p>
                      <p><strong>수정 조언:</strong> {item.suggestion}</p>
                    </div>
                  ))
                ) : (
                  <p>수정이 필요한 문장이 발견되지 않았습니다.</p>
                )}
              </div>
            ) : (
              <>
                <h2 className="tip-title">
                  <Lightbulb size={22} />
                  작성 팁
                </h2>
                <p className="tip-desc">
                  글의 목적에 맞게
                  <br />
                  처음에 작성한 생각을
                  <br />
                  자연스럽게 연결해보세요.
                </p>
                {idea && (
                  <div className="tip-idea">
                    <span>처음 적은 생각</span>
                    <p>“{idea}”</p>
                  </div>
                )}
                <ul className="tip-list">
                  {TIPS.map((tip) => (
                    <li key={tip}>
                      <CheckCircle2 size={20} />
                      {tip}
                    </li>
                  ))}
                </ul>
                <p className="tip-handwriting">
                  당신의 생각이
                  <br />
                  좋은 글이 될 수 있어요 :)
                </p>
              </>
            )}
          </aside>
        </div>
      </div>
      {/*
        알림(토스트): toast에 글자가 있을 때만 화면 아래에 뜸
        role="status": 화면 읽기 프로그램이 이 문구가 바뀌면 읽어주게 함
      */}
      {toast && (
        <div className="toast" role="status">
          {toast}
        </div>
      )}
    </div>
  );
}
export default WritingPage;
