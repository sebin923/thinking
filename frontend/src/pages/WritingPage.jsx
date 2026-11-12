import { useState, useRef, useEffect } from "react";
import {
  PenLine,
  FilePlus2,
  Check,
  Copy,
  Undo2,
  Redo2,
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
  Ticket, // 보유 이용권 아이콘
} from "lucide-react";
import PageHero from "../components/PageHero";
// AI 초안·피드백 결과 아래에 붙는 별점 평가 상자
import AiRating from "../components/AiRating";
// 글쓰기 AI 하루 무료 횟수(3회) 세기
import { getAiUsage, recordAiUse } from "../api/aiUsage";
// 내 프로필 가져오기 (보유 이용권 개수 ai_credits가 들어 있음)
import { fetchMyProfile } from "../api/mypage";
import "./WritingPage.css";
import "./WritingPageCustom.css";
import "./WritingCompare.css";
const API_BASE_URL = (import.meta.env.VITE_API_BASE_URL || (import.meta.env.DEV ? "http://localhost:8000" : "")).replace(/\/+$/, "");
const AI_DOCUMENT_TYPES = ["보고서", "자기소개서", "발표문", "자유 글쓰기"];
const TITLE_MAX = 50;
const BODY_MAX = 2000;
const DRAFT_KEY_PREFIX = "saenggak-hanjul-draft";
const getDraftKey = (userId) => `${DRAFT_KEY_PREFIX}-${userId ?? "guest"}`;
const WRITING_TYPES = [
  { value: "자유 글쓰기", label: "자유 글쓰기", detail: "주제와 형식에 제한 없이" },
  { value: "자기소개서", label: "자기소개서", detail: "경험과 역량을 중심으로" },
  { value: "보고서", label: "보고서", detail: "주제와 근거를 체계적으로" },
  { value: "발표문", label: "발표문", detail: "듣는 사람을 고려하여" },
  { value: "기타", label: "기타", detail: "원하는 글 유형 직접 입력" },
];
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
const TIPS = ["제목은 구체적으로", "핵심 내용을 중심으로", "문장은 간결하게"];
// 임시저장 데이터 불러오기
function loadDraft(userId) {
  try {
    const saved = localStorage.getItem(getDraftKey(userId));
    return saved ? JSON.parse(saved) : null;
  } catch (error) {
    console.error("임시저장 불러오기 실패:", error);
    return null;
  }
}
// 저장 상태에 따른 글쓰기 단계
function getStage(savedVersion, isComplete) {
  if (isComplete) return "완료";
  if (savedVersion >= 2) return "수정";
  return "초안";
}
const STAGE_CLASS = { 초안: "draft", 수정: "revise", 완료: "done" };
// 텍스트를 안전한 HTML로 변환
function textToHtml(text) {
  return (text || "")
    .replace(/&/g, "&amp;")
    .replace(/</g, "&lt;")
    .replace(/>/g, "&gt;")
    .replace(/\n/g, "<br>");
}
// 서버 문서를 편집용 데이터로 변환
function documentToDraft(doc) {
  const isKnownType = WRITING_TYPES.some((item) => item.value === doc.document_type);
  return {
    title: doc.title || "",
    html: textToHtml(doc.content),
    writingType: isKnownType ? doc.document_type : "기타",
    customType: isKnownType ? "" : doc.document_type,
    documentId: doc.id,
    savedVersion: doc.latest_version || 0,
    isComplete: doc.status === "완료",
    fromServer: true,
  };
}
function countText(html) {
  const temp = document.createElement("div");
  temp.innerHTML = html || "";
  return temp.textContent.trim().length;
}
function splitForCompare(text) {
  return (text || "").match(/\s+|[^\s]+/g) || [];
}
// 원문과 수정문 차이 계산
function compareText(before, after) {
  const a = splitForCompare(before);
  const b = splitForCompare(after);
  if (a.length * b.length > 120000) {
    return [
      { kind: "removed", text: before || "" },
      { kind: "added", text: after || "" },
    ];
  }
  const dp = Array.from({ length: a.length + 1 }, () => new Uint16Array(b.length + 1));
  for (let i = a.length - 1; i >= 0; i--) {
    for (let j = b.length - 1; j >= 0; j--) {
      dp[i][j] = a[i] === b[j] ? 1 + dp[i + 1][j + 1] : Math.max(dp[i + 1][j], dp[i][j + 1]);
    }
  }
  const parts = [];
  const push = (kind, text) => {
    if (!text) return;
    const previous = parts[parts.length - 1];
    if (previous?.kind === kind) previous.text += text;
    else parts.push({ kind, text });
  };
  let i = 0, j = 0;
  while (i < a.length && j < b.length) {
    if (a[i] === b[j]) { push("same", a[i++]); j++; }
    else if (dp[i + 1][j] >= dp[i][j + 1]) push("removed", a[i++]);
    else push("added", b[j++]);
  }
  while (i < a.length) push("removed", a[i++]);
  while (j < b.length) push("added", b[j++]);
  return parts;
}
// 변경 부분 강조 표시
// 본문 문자열 위치를 DOM Range로 변환해 서식을 건드리지 않고 강조합니다.
function highlightEditorMatches(editor, phrases) {
  if (!editor || !window.CSS?.highlights || typeof Highlight === "undefined") return;
  const nodes = [];
  const walker = document.createTreeWalker(editor, NodeFilter.SHOW_TEXT);
  let text = "";
  while (walker.nextNode()) {
    const node = walker.currentNode;
    nodes.push({ node, start: text.length, end: text.length + node.textContent.length });
    text += node.textContent;
  }
  const ranges = [];
  const seen = new Set();
  for (const phrase of phrases) {
    if (!phrase?.trim()) continue;
    let from = 0;
    while (from < text.length) {
      const index = text.indexOf(phrase, from);
      if (index === -1) break;
      from = index + phrase.length;
      const key = `${index}:${from}`;
      if (seen.has(key)) continue;
      seen.add(key);
      const first = nodes.find((n) => n.start <= index && index < n.end);
      const last = nodes.find((n) => n.start < from && from <= n.end);
      if (!first || !last) continue;
      const range = document.createRange();
      range.setStart(first.node, index - first.start);
      range.setEnd(last.node, from - last.start);
      ranges.push(range);
    }
  }
  if (ranges.length) CSS.highlights.set("writing-ai-issues", new Highlight(...ranges));
  else CSS.highlights.delete("writing-ai-issues");
}
// AI 초안이 바꾸려고 제안한 원문 부분만 추출합니다.
function getDraftChangedPhrases(before, after) {
  return compareText(before, after)
    .filter((part) => part.kind === "removed" && part.text.trim())
    .map((part) => part.text.trim());
}
function CompareText({ before, after, side }) {
  const parts = compareText(before, after);
  return <div className="writing-compare-content">{parts.map((part, index) => {
    if (part.kind === "removed" && side === "after") return null;
    if (part.kind === "added" && side === "before") return null;
    return <span key={index} className={part.kind === "same" ? "" : `writing-compare-${part.kind}`}>{part.text}</span>;
  })}</div>;
}
// 글쓰기 페이지
function WritingPage({
  idea = "",
  auth = null,
  onOpenSettings,
  initialDocument = null,
  onNewWriting,
  onWritingStateChange,
  onCharge, // 무료 횟수를 다 썼을 때 "이용권 충전" 버튼 → 결제 화면으로
}) {
  // ----- 하루 무료 AI 횟수 -----
  // aiUsage: { used(오늘 쓴 횟수), limit(3), remaining(남은 횟수), unlimited(관리자) }
  const [aiUsage, setAiUsage] = useState(() => getAiUsage(auth?.user));
  const aiLimitReached = aiUsage.remaining <= 0; // 오늘 무료 횟수를 다 썼는지
  // AI 요청 전에 부름: 남은 횟수가 없으면 안내하고 false (요청을 안 보냄)
  // (다른 탭에서 쓴 횟수나 날짜 변경도 반영되게 저장소에서 다시 읽음)
  const checkAiQuota = () => {
    const usage = getAiUsage(auth?.user);
    setAiUsage(usage);
    if (usage.remaining <= 0) {
      showToast(`오늘 무료 AI ${usage.limit}회를 모두 썼어요. 내일 다시 쓸 수 있어요.`);
      return false;
    }
    return true;
  };
  // AI 요청이 성공한 뒤에 부름: 1회 사용으로 기록
  const markAiUsed = () => setAiUsage(recordAiUse(auth?.user));

  // ----- 보유 이용권 개수 (결제로 충전한 횟수, 서버 users.ai_credits) -----
  // null = 아직 불러오는 중(또는 로그인 안 함) → 화면에 안 보여줌 / "error" = 불러오기 실패 → "확인 불가"
  const [aiCredits, setAiCredits] = useState(null);
  useEffect(() => {
    if (!auth?.token) return; // 로그인 안 했으면 물어볼 수 없음
    let cancelled = false; // 화면이 먼저 닫히면 결과를 무시하려고 (닫힌 화면 state를 바꾸면 경고가 남)
    fetchMyProfile(auth.token)
      .then((profile) => {
        if (cancelled) return;
        // 서버가 ai_credits를 안 보내 주면(백엔드 재시작 전 등) 이용권이 없는 것으로 보고 0회로 표시
        setAiCredits(typeof profile?.ai_credits === "number" ? profile.ai_credits : 0);
      })
      .catch(() => {
        // 불러오지 못해도 글쓰기는 계속 쓸 수 있어야 해서 조용히 넘어감
        // (서버 연결 실패 등 → "확인 불가"로 표시)
        if (!cancelled) setAiCredits("error");
      });
    return () => {
      cancelled = true;
    };
  }, [auth?.token]);

  const [pendingAiDraft, setPendingAiDraft] = useState(null);
  const [pendingAiOriginal, setPendingAiOriginal] = useState("");
  // ----- 별점 평가용 -----
  // 실제 응답의 공통/개인 모델을 별점 평가에 기록한다.
  const [pendingAiModel, setPendingAiModel] = useState("common");
  // aiResultCount: AI 결과(초안·피드백)가 새로 나올 때마다 +1
  //   → 별점 상자의 key로 써서, 새 결과가 나오면 별점 상자가 처음부터 다시 시작되게 함
  const [aiResultCount, setAiResultCount] = useState(0);
  // feedbackRequestText: AI 피드백을 요청할 때 보낸 본문 (평가 저장 때 같이 남김)
  const [feedbackRequestText, setFeedbackRequestText] = useState("");
  const [draftLoading, setDraftLoading] = useState(false);
  const aiRequestRef = useRef(false);
  const [draft] = useState(() => {
    const saved = loadDraft(auth?.user?.user_id);
    if (!initialDocument) {
      // 1순위: 설정 화면에 다녀온 경우 → 쓰던 글(임시저장본) 그대로
      if (saved) return { ...saved, resumedFromSettings: true };
      // 2순위: 메인 화면 입력창에 적은 생각(idea)이 있으면 → 그 글을 본문에 넣고 시작
      //   textToHtml: 글자 속 <, > 같은 기호를 안전하게 바꾸고 줄바꿈을 살려서 HTML로 만듦
      //   dirty: true → 아직 저장 안 한 내용이 있다는 표시 (다른 메뉴로 나가면 "저장 안 하고 나갈까요?" 경고)
      if (idea.trim()) return { html: textToHtml(idea.trim()), dirty: true, fromIdea: true };
      return null;
    }
    if (saved?.documentId === initialDocument.id) return { ...saved, resumedFromSettings: true };
    return documentToDraft(initialDocument);
  });
  const [isComplete, setIsComplete] = useState(Boolean(draft?.isComplete));
  const [savedVersion, setSavedVersion] = useState(draft?.savedVersion || 0);
  const stage = getStage(savedVersion, isComplete);
  const [createdHere, setCreatedHere] = useState(Boolean(draft?.createdHere));
  const [dirty, setDirty] = useState(Boolean(draft?.dirty));
  const [writingType, setWritingType] = useState(draft?.writingType || "자유 글쓰기");
  const [customType, setCustomType] = useState(draft?.customType || "");
  const selectedDocumentType = writingType === "기타" ? customType.trim() : writingType;
  const [title, setTitle] = useState(draft?.title || "");
  const [bodyLength, setBodyLength] = useState(() => countText(draft?.html));
  const [toast, setToast] = useState(() => {
    if (!draft) return "";
    if (draft.fromIdea) return "메인에서 적은 생각을 본문에 넣어 두었어요.";
    if (draft.fromServer) return `"${draft.title}" 글을 불러왔어요.`;
    return "임시저장된 글을 불러왔어요.";
  });
  const [documentId, setDocumentId] = useState(draft?.documentId ?? null);
  const [apiMessage, setApiMessage] = useState(
    draft?.isComplete ? "최종 저장이 완료된 글이에요. 내용은 볼 수만 있어요." : ""
  );
  const [savedDrafts, setSavedDrafts] = useState([]);
  const [feedback, setFeedback] = useState(null);
  const [feedbackLoading, setFeedbackLoading] = useState(false);
  const [undoAiHtml, setUndoAiHtml] = useState(null);
  const [redoAiHtml, setRedoAiHtml] = useState(null);
  const editorRef = useRef(null);
  const toastTimerRef = useRef(null);
  // 두 AI 기능의 지적 문장을 같은 방식으로 본문에 표시합니다.
  const refreshEditorHighlights = () => {
    const phrases = [
      ...(feedback?.highlights || []).map((item) => item.original_text),
      ...(pendingAiDraft === null ? [] : getDraftChangedPhrases(pendingAiOriginal, pendingAiDraft)),
    ];
    highlightEditorMatches(editorRef.current, phrases);
  };
  useEffect(() => {
    refreshEditorHighlights();
    return () => CSS?.highlights?.delete("writing-ai-issues");
  }, [feedback, pendingAiDraft, pendingAiOriginal]);
  const showToast = (message) => {
    setToast(message);
    clearTimeout(toastTimerRef.current);
    toastTimerRef.current = setTimeout(() => setToast(""), 2500);
  };
  useEffect(() => {
    if (draft?.resumedFromSettings) {
      try {
        localStorage.removeItem(getDraftKey(auth?.user?.user_id));
      } catch {
      }
    }
  }, [draft, auth?.user?.user_id]);
  useEffect(() => {
    onWritingStateChange?.({ documentId, savedVersion, isComplete, createdHere, dirty });
  }, [documentId, savedVersion, isComplete, createdHere, dirty, onWritingStateChange]);
  useEffect(() => {
    return () => clearTimeout(toastTimerRef.current);
  }, []);
  useEffect(() => {
    if (draft && editorRef.current) {
      editorRef.current.innerHTML = draft.html || "";
    }
    if (draft) {
      toastTimerRef.current = setTimeout(() => setToast(""), 2500);
    }
  }, [draft]);
  const handleBodyInput = (event) => {
    if (event) {
      setUndoAiHtml(null);
      setRedoAiHtml(null);
    }
    setBodyLength(editorRef.current.innerText.trim().length);
    setDirty(true);
    refreshEditorHighlights();
  };
  const handleToolbar = (command) => {
    let value = null;
    if (command === "createLink") {
      value = window.prompt("연결할 주소를 입력하세요", "https://");
      if (!value) return;
    }
    setUndoAiHtml(null);
    setRedoAiHtml(null);
    document.execCommand(command, false, value);
    editorRef.current.focus();
    handleBodyInput();
  };
  const getBodyText = () => {
    return editorRef.current?.innerText?.trim() || "";
  };
  const getBodyHtml = () => {
    return editorRef.current?.innerHTML || "";
  };
  // 현재 글 임시저장
  const saveBrowserDraft = () => {
    try {
      localStorage.setItem(getDraftKey(auth?.user?.user_id), JSON.stringify({
        title,
        html: editorRef.current?.innerHTML || "",
        writingType,
        customType,
        documentId,
        isComplete,
        savedVersion,
        createdHere,
        dirty,
        savedAt: new Date().toISOString(),
      }));
      return true;
    } catch (error) {
      console.error("임시저장 실패:", error);
      return false;
    }
  };
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
    setCreatedHere(true);
    return data.id;
  };
  const saveThoughtFromIdea = async (targetDocumentId, thoughtText) => {
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
  // 비교 내용 복사
  const copyText = async (value, label = "내용") => {
    try {
      await navigator.clipboard.writeText(value || "");
      showToast(`${label}을(를) 복사했습니다.`);
    } catch (error) {
      console.error("복사 실패:", error);
      showToast("복사에 실패했습니다. 브라우저의 클립보드 권한을 확인해 주세요.");
    }
  };
  // AI 문장을 본문에 적용
  const applyAiText = (value) => {
    if (isComplete || !editorRef.current) return;
    if (value.length > BODY_MAX) {
      showToast(`본문은 ${BODY_MAX}자 이하만 적용할 수 있습니다.`);
      return;
    }
    setUndoAiHtml(editorRef.current.innerHTML);
    setRedoAiHtml(null);
    editorRef.current.innerText = value;
    handleBodyInput();
    showToast("AI 수정안이 본문에 적용되었습니다. 저장은 별도로 해 주세요.");
  };
  // AI 적용 전 상태로 돌아가기
  const undoAiApply = () => {
    if (isComplete || undoAiHtml === null || !editorRef.current) return;
    setRedoAiHtml(editorRef.current.innerHTML);
    editorRef.current.innerHTML = undoAiHtml;
    setUndoAiHtml(null);
    handleBodyInput();
    showToast("AI 수정안 적용을 취소했습니다.");
  };
  // 취소한 AI 수정안 다시 적용
  const redoAiApply = () => {
    if (isComplete || redoAiHtml === null || !editorRef.current) return;
    setUndoAiHtml(editorRef.current.innerHTML);
    editorRef.current.innerHTML = redoAiHtml;
    setRedoAiHtml(null);
    handleBodyInput();
    showToast("AI 수정안을 다시 적용했습니다.");
  };
  // 완성된 수정 문장만 원문 위치에 적용
  const applyHighlightedEdit = (original, proposed) => {
    const before = (original || "").trim();
    const after = (proposed || "").trim();
    if (isComplete || !before || !after || before === after || /\[[^\]]+\]/.test(after)) return;
    const current = getBodyText();
    if (!current.includes(before)) {
      showToast("현재 본문에서 해당 원문을 찾을 수 없습니다.");
      return;
    }
    const updated = current.replace(before, after);
    if (updated.length > BODY_MAX) {
      showToast(`본문은 ${BODY_MAX}자 이하만 적용할 수 있습니다.`);
      return;
    }
    applyAiText(updated);
  };
  // 생성 버튼 하나: 인증된 사용자 기준으로 서버가 모델을 선택한다.
  const handleAiDraft = async () => {
    if (aiRequestRef.current || draftLoading || feedbackLoading || isComplete) return;
    if (!auth?.token) { showToast("로그인이 필요합니다."); return; }
    if (!AI_DOCUMENT_TYPES.includes(selectedDocumentType)) {
      showToast("보고서·자기소개서·발표문·자유 글쓰기에서 사용할 수 있어요."); return;
    }
    const originalAtRequest = getBodyText();
    const sourceText = originalAtRequest.trim() || idea.trim();
    if (!sourceText) { showToast("생각이나 본문을 먼저 입력해 주세요."); return; }
    if (sourceText.length > BODY_MAX) { showToast("본문은 " + BODY_MAX + "자 이하로 입력해 주세요."); return; }
    if (!checkAiQuota()) return;
    aiRequestRef.current = true;
    setDraftLoading(true);
    try {
      setApiMessage("");
      showToast("AI가 초안을 작성하고 있어요.");
      const targetDocumentId = await createDocumentIfNeeded();
      await saveThoughtFromIdea(targetDocumentId, sourceText);
      const response = await fetch(API_BASE_URL + "/api/documents/" + targetDocumentId + "/draft-ai", {
        method: "POST", headers: getAuthHeaders(), body: JSON.stringify({content: sourceText}),
      });
      const data = await response.json().catch(() => ({}));
      if (!response.ok) throw new Error(typeof data.detail === "string" ? data.detail : "AI 초안 생성에 실패했습니다.");
      if (typeof data.content !== "string" || !data.content.trim() || data.content.length > BODY_MAX) {
        throw new Error("AI가 사용할 수 있는 초안을 반환하지 않았습니다.");
      }
      setPendingAiOriginal(originalAtRequest || sourceText);
      setPendingAiDraft(data.content);
      setPendingAiModel(data.personalized === true ? "personal" : "common");
      setAiResultCount((n) => n + 1);
      markAiUsed();
      setApiMessage(Array.isArray(data.checks) ? data.checks.filter((v) => typeof v === "string").join(" · ") : "");
      showToast("AI 초안이 생성됐어요. 내용을 확인한 뒤 적용해 주세요.");
    } catch (error) {
      console.error("AI 초안 오류:", error);
      showToast(error.message || "AI 초안 생성에 실패했습니다.");
    } finally {
      aiRequestRef.current = false;
      setDraftLoading(false);
    }
  };
  // 글 버전 저장
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
      setSavedVersion(data.version);
      setDirty(false);
      // 저장 결과는 잠깐 떴다 사라지는 알림(toast)으로만 알려줌
      // (본문 아래에 "수정본으로 저장했어요. (N번째 저장)" 같은 안내 문구는 띄우지 않음)
      // 이전에 떠 있던 안내 문구(예: AI 초안 생성 완료)도 저장하면 지움
      setApiMessage("");
      showToast(data.version === 1 ? "초안 저장 완료" : "수정본 저장 완료");
    } catch (error) {
      console.error(error);
      showToast(error.message || "초안 저장 실패");
    }
  };
  // AI 피드백 요청
  const handleAiFeedback = async () => {
    if (aiRequestRef.current || feedbackLoading || draftLoading || isComplete) return;
    if (!auth?.token) { showToast("로그인이 필요합니다."); return; }
    const bodyText = getBodyText();
    if (!title.trim() || !bodyText) {
      showToast("제목과 본문을 먼저 작성해 주세요.");
      return;
    }
    if (bodyText.length > BODY_MAX) {
      showToast(`본문은 ${BODY_MAX}자 이하로 작성해 주세요.`);
      return;
    }
    if (!checkAiQuota()) return; // 오늘 무료 횟수를 다 썼으면 멈춤
    aiRequestRef.current = true;
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
      setSavedVersion(savedDraft.version);
      setDirty(false);
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
      if (!result.feedback || typeof result.feedback.overall_feedback !== "string" || !Array.isArray(result.feedback.highlights)) {
        throw new Error("AI 피드백 형식이 올바르지 않습니다.");
      }
      setFeedback(result.feedback);
      setFeedbackRequestText(bodyText); // 별점 평가용: 피드백을 요청한 본문
      setAiResultCount((n) => n + 1);
      markAiUsed(); // 성공했을 때만 1회 차감
      setApiMessage("");
      showToast("AI 피드백이 완료되었습니다.");
    } catch (error) {
      console.error("AI 피드백 오류:", error);
      showToast(error.message || "AI 피드백 요청 실패");
    } finally {
      aiRequestRef.current = false;
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
  const handleSaveDraft = () => {
    showToast(saveBrowserDraft() ? "임시저장했어요." : "임시저장에 실패했어요.");
  };
  // 최종 저장
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
      const finalDraft = await saveResponse.json();
      setSavedVersion(finalDraft.version);
      setDirty(false);
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
        <PageHero
          eyebrow="당신의 생각이, 하나의 글이 되는 과정"
          title="내 생각을 글로 완성해보세요"
          description={
            "필요한 AI 기능을 자유롭게 선택해 글을 완성해보세요.\n" +
            "AI를 사용하지 않고 바로 저장할 수도 있습니다."
          }
          // 메모지 폭이 좁아서 "글이 되는 곳"을 한 줄에 쓰면 "곳"만 혼자 떨어짐 → 줄을 미리 나눠 둠
          memoText={"당신의\n생각이\n글이\n되는 곳"}
          memoVariant="note"
        />
        <div className={`writing-layout ${feedback ? "writing-layout-feedback" : ""}`}>
          <section className="panel writing-card">
            <div className="writing-card-heading">
              <h2 className="writing-card-title">
                <PenLine size={22} /> 글쓰기
                <span className={`writing-stage-badge ${STAGE_CLASS[stage]}`} title="마이페이지 '내가 쓴 글'에도 이 단계로 보여요">
                  {stage}
                  <small>{savedVersion > 0 ? `· ${savedVersion}번 저장` : "· 저장 전"}</small>
                </span>
              </h2>
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
            <label className="field-label" htmlFor="writing-title">
              제목
            </label>
            <div className="title-input-box">
              <input
                id="writing-title"
                type="text"
                placeholder="글의 제목을 입력해주세요."
                value={title}
                onChange={(event) => {
                  setTitle(event.target.value);
                  setDirty(true);
                }}
                disabled={isComplete}
                maxLength={TITLE_MAX}
              />
              <span className="counter">
                {title.length}/{TITLE_MAX}
              </span>
            </div>
            <div className="writing-body-heading">
              <span className="field-label" id="writing-body-label">본문</span>
              <div className="writing-body-actions">
                <button type="button" className="writing-compare-copy" onClick={undoAiApply} disabled={isComplete || undoAiHtml === null}>
                  <Undo2 size={14} /> 실행 취소
                </button>
                <button type="button" className="writing-compare-copy" onClick={redoAiApply} disabled={isComplete || redoAiHtml === null}>
                  <Redo2 size={14} /> 다시 실행
                </button>
                <button type="button" className="writing-compare-copy" onClick={() => copyText(getBodyText(), "본문")} disabled={bodyLength === 0}>
                  <Copy size={14} /> 본문 복사
                </button>
              </div>
            </div>
            <div className="editor-box">
              <div className="editor-toolbar" role="toolbar" aria-label="본문 서식">
                {TOOLBAR.map((tool, index) => {
                  const Icon = tool.icon;
                  const needDivider = index > 0 && TOOLBAR[index - 1].group !== tool.group;
                  return (
                    <span key={tool.command} className="toolbar-item">
                      {needDivider && <span className="toolbar-divider" aria-hidden="true" />}
                      <button
                        type="button"
                        className="toolbar-button"
                        title={tool.label}
                        aria-label={tool.label}
                        onMouseDown={(event) => event.preventDefault()}
                        onClick={() => handleToolbar(tool.command)}
                      >
                        <Icon size={16} />
                      </button>
                    </span>
                  );
                })}
              </div>
              <div
                ref={editorRef}
                className={bodyLength === 0 ? "editor is-empty" : "editor"}
                contentEditable={!isComplete}
                suppressContentEditableWarning
                onInput={handleBodyInput}
                role="textbox"
                aria-multiline="true"
                aria-labelledby="writing-body-label"
                data-placeholder={
                  "직접 글을 작성하거나 AI 초안을 활용할 수 있습니다."
                }
              />
              <div className={bodyLength > BODY_MAX ? "editor-counter over" : "editor-counter"}>
                {bodyLength.toLocaleString()} / {BODY_MAX.toLocaleString()}
              </div>
            </div>
            <div className="writing-ai-tools">
              <div className="writing-ai-tools-head">
                <h3 className="writing-ai-tools-title">AI 글쓰기 도구</h3>
                {/* 오늘 남은 무료 횟수 (관리자는 제한 없음) */}
                {!aiUsage.unlimited && (
                  // 위: 오늘 남은 무료 횟수 / 아래: 내가 가진 이용권 개수
                  <div className="writing-ai-quota-group">
                    <span className={aiLimitReached ? "writing-ai-quota empty" : "writing-ai-quota"}>
                      오늘 무료 <strong>{aiUsage.remaining}</strong>/{aiUsage.limit}회 남음
                    </span>
                    {aiCredits !== null && (
                      <span className="writing-ai-credits">
                        <Ticket size={14} aria-hidden="true" />
                        {/* 글자를 span 하나로 묶어야 숫자와 "회" 사이가 안 벌어짐 (아이콘과의 간격만 gap 적용) */}
                        <span>
                          {aiCredits === "error" ? (
                            "보유 이용권 확인 불가"
                          ) : (
                            <>
                              보유 이용권 <strong>{aiCredits.toLocaleString("ko-KR")}</strong>회
                            </>
                          )}
                        </span>
                      </span>
                    )}
                  </div>
                )}
              </div>
              <p className="writing-ai-tools-subtitle">
                필요한 기능만 선택하세요. AI 사용은 필수가 아닙니다. (AI 기능은 종류와 상관없이 하루 {aiUsage.limit}회까지 무료)
              </p>
              {/* 무료 횟수를 다 썼을 때 안내 + 이용권 충전 */}
              {aiLimitReached && (
                <div className="writing-ai-limit" role="status">
                  <p>
                    <strong>오늘 무료 AI {aiUsage.limit}회를 모두 썼어요.</strong>
                    <span>내일 다시 {aiUsage.limit}회가 생겨요. 지금 더 쓰려면 이용권을 충전해 주세요.</span>
                  </p>
                  {onCharge && (
                    <button type="button" className="btn-primary writing-ai-limit-button" onClick={onCharge}>
                      <Sparkles size={15} /> 이용권 충전
                    </button>
                  )}
                </div>
              )}
              <div className="writing-ai-tool-buttons">
                <button type="button" className="writing-ai-tool-button" onClick={handleAiDraft} disabled={aiLimitReached || draftLoading || feedbackLoading || isComplete || !AI_DOCUMENT_TYPES.includes(selectedDocumentType)} title={AI_DOCUMENT_TYPES.includes(selectedDocumentType) ? "입력한 내용으로 글을 작성합니다." : "보고서·자기소개서·발표문·자유 글쓰기에서 사용할 수 있습니다."}>
                  <FileText size={19} />
                  <span><strong>{draftLoading ? "AI 초안 생성 중..." : "AI 초안 생성"}</strong><small>입력한 생각을 바탕으로 초안 생성</small></span>
                </button>
                <button type="button" className="writing-ai-tool-button" onClick={handleAiFeedback} disabled={aiLimitReached || draftLoading || feedbackLoading || isComplete}>
                  <Lightbulb size={19} />
                  <span><strong>{feedbackLoading ? "AI 분석 중..." : "AI 피드백 및 수정"}</strong><small>문제점 분석과 개선 방향 확인</small></span>
                </button>
              </div>
            </div>
            {pendingAiDraft !== null && (
              <section className="writing-ai-draft-preview writing-compare-panel" aria-label="AI 초안 비교">
                <h3>AI 초안 비교</h3>
                <p>빨간색은 변경된 내용입니다. 왼쪽 본문에도 변경 제안 부분이 빨간 밑줄로 표시됩니다.</p>
                <div className="writing-compare-grid">
                  <div className="writing-compare-card">
                    <div className="writing-compare-card-heading"><strong>현재 원문</strong>
                      <button type="button" className="writing-compare-copy" onClick={() => copyText(pendingAiOriginal, "원문")}><Copy size={14} /> 복사</button>
                    </div>
                    <CompareText before={pendingAiOriginal} after={pendingAiDraft} side="before" />
                  </div>
                  <div className="writing-compare-card">
                    <div className="writing-compare-card-heading"><strong>AI 초안</strong>
                      <button type="button" className="writing-compare-copy" onClick={() => copyText(pendingAiDraft, "AI 초안")}><Copy size={14} /> 복사</button>
                    </div>
                    <CompareText before={pendingAiOriginal} after={pendingAiDraft} side="after" />
                  </div>
                </div>
                <div className="writing-ai-preview-actions">
                  <button type="button" className="btn-outline" onClick={() => setPendingAiDraft(null)}>닫기</button>
                  <button type="button" className="btn-primary" disabled={isComplete} onClick={() => {
                    applyAiText(pendingAiDraft);
                    if (pendingAiDraft.length <= BODY_MAX) setPendingAiDraft(null);
                  }}>AI 초안 본문에 적용</button>
                </div>
                {/* 이 초안에 대한 별점 평가 (새 초안이 나오면 key가 바뀌어 처음부터) */}
                <AiRating
                  key={`draft-${aiResultCount}`}
                  title="이 AI 초안은 어땠나요?"
                  user={auth?.user}
                  kind="draft"
                  model={pendingAiModel}
                  documentId={documentId}
                  resultText={pendingAiDraft}
                  requestText={pendingAiOriginal}
                />
              </section>
            )}
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
          <aside className="panel tip-card">
            {feedback ? (
              <div className="ai-feedback-panel">
                <h2 className="tip-title">AI 피드백 결과</h2>
                <p className="ai-feedback-summary">
                  {feedback.overall_feedback}
                </p>
                <h4>수정 권장 문장</h4>
                {feedback.highlights?.length > 0 ? (
                  feedback.highlights.map((item, index) => {
                    const revised = item.revised_text || item.corrected_text || item.suggested_text || item.replacement_text || "";
                    const canApply = Boolean(
                      !isComplete && item.original_text?.trim() && revised.trim() &&
                      item.original_text.trim() !== revised.trim() &&
                      !/\[[^\]]+\]/.test(revised) &&
                      getBodyText().includes(item.original_text.trim()) &&
                      getBodyText().replace(item.original_text.trim(), revised.trim()).length <= BODY_MAX
                    );
                    return (
                      <div className="ai-feedback-item writing-feedback-compare" key={index}>
                        {revised ? (
                          <>
                            <div className="writing-compare-card-heading"><strong>AI 수정 문장</strong>
                              <button type="button" className="writing-compare-copy" onClick={() => copyText(revised, "AI 수정 문장")}><Copy size={14} /> 복사</button>
                            </div>
                            <CompareText before={item.original_text || ""} after={revised} side="after" />
                            <button type="button" className="writing-compare-apply" disabled={!canApply} onClick={() => applyHighlightedEdit(item.original_text, revised)}>본문에 적용</button>
                          </>
                        ) : null}
                        {item.reason && <p><strong>개선 이유:</strong> {item.reason}</p>}
                        {item.suggestion && (
                          <div>
                            <p><strong>수정 조언:</strong> {item.suggestion}</p>
                          </div>
                        )}
                      </div>
                    );
                  })
                ) : (
                  <p>표시할 수 있는 구체적인 수정 제안이 없습니다.</p>
                )}
                {/* 이 피드백에 대한 별점 평가 (새 피드백이 나오면 key가 바뀌어 처음부터) */}
                <AiRating
                  key={`feedback-${aiResultCount}`}
                  title="이 AI 피드백은 도움이 됐나요?"
                  user={auth?.user}
                  kind="feedback"
                  model="common"
                  documentId={documentId}
                  resultText={feedback.overall_feedback || ""}
                  requestText={feedbackRequestText}
                />
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
      {toast && (
        <div className="toast" role="status">
          {toast}
        </div>
      )}
    </div>
  );
}
export default WritingPage;
