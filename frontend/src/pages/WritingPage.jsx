import { useState, useRef, useEffect } from "react";

import {
  PenLine,
  Check,
  ArrowRight,
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
} from "lucide-react";

import PageHero from "../components/PageHero";
import "./WritingPage.css";

const API_BASE_URL = "http://localhost:8000";

const TITLE_MAX = 50; // 제목 최대 글자 수
const BODY_MAX = 2000; // 본문 최대 글자 수

// 임시저장할 때 브라우저 저장소(localStorage)에 쓸 이름표
const DRAFT_KEY = "saenggak-hanjul-draft";

// 위쪽 진행 단계 (지금 페이지는 3단계)
const STEPS = ["생각 입력", "구조화", "직접 문장화", "생각 반영 확인"];
const CURRENT_STEP = 3; // 1부터 셈

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
function loadDraft() {
  // try { } catch { }: 안에서 에러가 나도 화면이 멈추지 않게 감싸는 문법
  // (브라우저 설정에 따라 localStorage 사용이 막혀 있을 수 있음)
  try {
    // localStorage.getItem: 브라우저에 저장해둔 값을 꺼냄 (없으면 null)
    const saved = localStorage.getItem(DRAFT_KEY);
    // 저장할 때 글자로 바꿔서 저장했으니, JSON.parse로 다시 객체로 되돌림
    return saved ? JSON.parse(saved) : null;
  } catch (error) {
    console.error("임시저장 불러오기 실패:", error);
    return null;
  }
}

// ----- 서식이 들어간 HTML에서 글자 수만 세기 -----
function countText(html) {
  // 화면에 안 붙인 임시 div에 HTML을 넣고, 태그를 뺀 글자(textContent)만 꺼냄
  const temp = document.createElement("div");
  temp.innerHTML = html || "";
  return temp.textContent.trim().length;
}

// WritingPage 컴포넌트
// props: idea → 메인 페이지에서 처음 입력한 생각 (없으면 빈 문자열)
function WritingPage({ idea = "" }) {
  // draft: 페이지가 처음 뜰 때 딱 한 번 임시저장본을 꺼내서 기억해둠
  // useState(함수) 처럼 함수를 넣으면 "처음 한 번만" 그 함수를 실행해서 초기값으로 씀
  // (setDraft는 안 쓰니까 배열에서 첫 번째 값만 꺼냄)
  const [draft] = useState(loadDraft);

  // title: 제목 입력칸 글자 (임시저장본이 있으면 그 제목으로 시작)
  // ?. (옵셔널 체이닝): draft가 null이면 에러 없이 undefined를 돌려줌
  const [title, setTitle] = useState(draft?.title || "");

  // bodyLength: 본문 글자 수 (본문 내용 자체는 editorRef로 직접 읽음)
  const [bodyLength, setBodyLength] = useState(() => countText(draft?.html));

  // toast: 화면 아래에 잠깐 떴다 사라지는 알림 문구 (빈 문자열이면 안 보임)
  // 임시저장본을 불러왔으면 처음부터 안내 문구를 띄운 상태로 시작
  const [toast, setToast] = useState(draft ? "임시저장된 글을 불러왔어요." : "");

  const [documentId, setDocumentId] = useState(null);
  const [apiMessage, setApiMessage] = useState("");
  const [savedDrafts, setSavedDrafts] = useState([]);

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

  const createDocumentIfNeeded = async () => {
    if (documentId) {
      return documentId;
    }

    if (title.trim() === "") {
      showToast("제목을 입력해 주세요.");
      throw new Error("제목 없음");
    }

    const response = await fetch(
      `${API_BASE_URL}/api/documents`,
      {
        method: "POST",
        headers: {
          "Content-Type": "application/json",
        },
        body: JSON.stringify({
          document_type: "자기소개서",
          title: title.trim(),
        }),
      }
    );

    if (!response.ok) {
      throw new Error("문서 생성 실패");
    }

    const data = await response.json();

    setDocumentId(data.id);

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
        headers: {
          "Content-Type": "application/json",
        },
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
    try {
      showToast("AI가 초안을 작성하고 있어요.");

      const targetDocumentId = await createDocumentIfNeeded();

      await saveThoughtFromIdea(targetDocumentId);

      const response = await fetch(
        `${API_BASE_URL}/api/documents/${targetDocumentId}/draft-ai`,
        {
          method: "POST",
        }
      );

      if (!response.ok) {
        const errorData = await response.json();

        throw new Error(
          errorData.detail || "AI 초안 작성 실패"
        );
      }

      const data = await response.json();

      if (editorRef.current) {
        editorRef.current.innerText = data.content;
        handleBodyInput();
      }

      setApiMessage("AI 초안이 작성되었습니다. 내용을 수정해보세요.");
      showToast("AI 초안 작성 완료");
    } catch (error) {
      console.error(error);
      showToast(error.message || "AI 초안 작성 실패");
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
          headers: {
            "Content-Type": "application/json",
          },
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

      setApiMessage(`초안 버전 ${data.version}이 저장되었습니다.`);
      showToast(`초안 버전 ${data.version} 저장 완료`);
    } catch (error) {
      console.error(error);
      showToast(error.message || "초안 저장 실패");
    }
  };

  const handleLoadDrafts = async () => {
    try {
      if (!documentId) {
        showToast("먼저 버전을 저장해 주세요.");
        return;
      }

      const response = await fetch(
        `${API_BASE_URL}/api/documents/${documentId}/drafts`
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

  // ----- 임시저장 버튼 -----
  const handleSaveDraft = () => {
    try {
      const draft = {
        title,
        html: editorRef.current.innerHTML,
        savedAt: new Date().toISOString(), // 저장한 시각
      };
      // localStorage는 글자만 저장할 수 있어서 JSON.stringify로 객체를 글자로 바꿈
      localStorage.setItem(DRAFT_KEY, JSON.stringify(draft));
      showToast("임시저장했어요.");
    } catch (error) {
      console.error("임시저장 실패:", error);
      showToast("임시저장에 실패했어요.");
    }
    // TODO: 백엔드가 완성되면 localStorage 대신 API(DRAFT_VERSIONS 테이블)로 저장
  };

  // ----- 작성 완료 버튼 -----
  const handleComplete = () => {
    // 빠진 게 있으면 알려주고 멈춤
    if (title.trim() === "") {
      showToast("제목을 입력해 주세요.");
      return;
    }
    if (bodyLength === 0) {
      showToast("본문을 작성해 주세요.");
      editorRef.current.focus();
      return;
    }
    if (bodyLength > BODY_MAX) {
      showToast(`본문은 ${BODY_MAX}자 이하로 작성해 주세요.`);
      return;
    }

    // 개발 중 확인용 (F12 → Console)
    console.log("작성 완료:", {
      title: title.trim(),
      html: editorRef.current.innerHTML,
      text: editorRef.current.innerText,
    });

    // 다 썼으니 임시저장본은 지움
    try {
      localStorage.removeItem(DRAFT_KEY);
    } catch {
      // 지우기 실패해도 큰 문제 없으니 무시
    }

    showToast("작성 완료! 다음은 ④ 생각 반영 확인 단계예요.");
    // TODO: 백엔드에 글 저장 후 "④ 생각 반영 확인" 화면으로 이동
  };

  return (
    <div className="sub-page">
      <div className="sub-page-inner">
        {/* ===== 1. 페이지 제목 영역 ===== */}
        <PageHero
          eyebrow="당신의 생각이, 하나의 글이 되는 과정"
          title="내 생각을 글로 완성해보세요"
          description={
            "구조화된 내용을 바탕으로, 이제는 직접 문장을 작성해보세요.\n" +
            "처음 떠오른 생각이 글 속에 자연스럽게 반영되었는지 확인할 수 있어요."
          }
          memoText={"당신의\n생각이\n글이 되는 곳"}
          memoVariant="note"
        />

        {/* ===== 2. 진행 단계 표시 ===== */}
        {/* ol: 순서 있는 목록 */}
        <ol className="panel writing-steps">
          {STEPS.map((step, index) => {
            const stepNumber = index + 1; // 1, 2, 3, 4
            // 단계 상태: 지난 단계 = done, 지금 단계 = current, 남은 단계 = todo
            let status = "todo";
            if (stepNumber < CURRENT_STEP) status = "done";
            if (stepNumber === CURRENT_STEP) status = "current";

            return (
              <li key={step} className={`writing-step ${status}`}>
                <span className="writing-step-badge">
                  {/* 지난 단계는 체크 아이콘, 나머지는 번호 */}
                  {status === "done" ? <Check size={16} strokeWidth={3} /> : stepNumber}
                </span>
                <span className="writing-step-label">{step}</span>

                {/* 마지막 단계가 아니면 오른쪽에 화살표 */}
                {stepNumber < STEPS.length && (
                  <ArrowRight className="writing-step-arrow" size={18} aria-hidden="true" />
                )}
              </li>
            );
          })}
        </ol>

        {/* ===== 3. 글쓰기 카드 + 작성 팁 ===== */}
        <div className="writing-layout">
          {/* ----- 왼쪽: 글쓰기 카드 ----- */}
          <section className="panel writing-card">
            <h2 className="writing-card-title">
              <PenLine size={22} />
              글쓰기
            </h2>

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
                onChange={(event) => setTitle(event.target.value)}
                maxLength={TITLE_MAX} // 50자 넘게는 입력 자체가 안 됨
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
                        title={tool.label} // 마우스 올리면 뜨는 설명
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
                ref={editorRef} // editorRef가 이 div를 가리키게 연결
                className={bodyLength === 0 ? "editor is-empty" : "editor"}
                contentEditable
                // React가 "contentEditable 안의 내용은 React가 관리 안 한다"는 경고를 안 띄우게
                suppressContentEditableWarning
                onInput={handleBodyInput}
                role="textbox"
                aria-multiline="true"
                aria-labelledby="writing-body-label"
                // 비어 있을 때 보여줄 안내 문구 (CSS의 ::before가 이 값을 꺼내서 보여줌)
                data-placeholder={
                  "여기에 글을 작성해보세요.\n" +
                  "처음에 작성한 생각이 자연스럽게 녹아들 수 있도록\n" +
                  "구조화된 내용을 참고하여 작성해보세요."
                }
              />

              {/* 본문 글자 수 (2000자 넘으면 over 클래스로 빨갛게) */}
              <div className={bodyLength > BODY_MAX ? "editor-counter over" : "editor-counter"}>
                {bodyLength.toLocaleString()} / {BODY_MAX.toLocaleString()}
              </div>
            </div>

            {/* 아래 버튼들 */}
            <div className="writing-actions">
              <button
                type="button"
                className="btn-outline"
                onClick={handleAiDraft}
              >
                <FileText size={18} />
                AI 초안 작성
              </button>

              <button
                type="button"
                className="btn-outline"
                onClick={handleSaveVersion}
              >
                <FileText size={18} />
                버전 저장
              </button>

              <button
                type="button"
                className="btn-primary"
                onClick={handleComplete}
              >
                작성 완료
                <ArrowRight size={18} />
              </button>
            </div>

            {apiMessage && (
              <p style={{ marginTop: "12px" }}>
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

          {/* ----- 오른쪽: 작성 팁 ----- */}
          <aside className="panel tip-card">
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

            {/* 메인 페이지에서 입력한 생각이 있으면 보여주기 (idea가 빈 문자열이면 안 보임) */}
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

            {/* 손글씨 응원 문구 */}
            <p className="tip-handwriting">
              당신의 생각이
              <br />
              좋은 글이 될 수 있어요 :)
            </p>
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
