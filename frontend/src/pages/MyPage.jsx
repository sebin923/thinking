// =============================================================
// MyPage.jsx — 마이페이지 (보기 화면)
// -------------------------------------------------------------
// 구성 (위에서 아래로)
//   1. 페이지 제목 영역 (PageHero)
//   2. 내 프로필 카드: 이름·아이디·이메일·전화번호·가입일 + 오른쪽 위 "마이페이지 수정" 버튼
//      아래쪽에 활동 요약 3칸 (내가 쓴 글 / 완료한 글 / 도전 최고 기록)
//   3. 내가 쓴 글 목록
//      - 위쪽 카테고리 버튼(전체 / 자유 글쓰기 / 자기소개서 / 보고서 / 발표문 / 기타)을 누르면
//        그 카테고리에 들어 있는 글만 보여줌
//      - 그 아래 단계 버튼(초안 / 수정 / 완료)을 누르면 "글"이 아니라 "저장본" 하나하나가 카드로 보임
//          초안 = 글마다 첫 번째 저장본
//          수정 = 두 번째 저장본부터 (글마다 최근 3개까지, 더 오래된 수정본은 서버가 자동으로 지움)
//          완료 = 최종 저장본
//        → 글 하나가 여러 탭에 동시에 나옴 (수정해도 초안 탭의 첫 저장본은 그대로 남음)
//        (같은 단계 버튼을 다시 누르면 꺼지고 글 단위 목록으로 돌아감)
//      - 글마다 미리보기, "본문 보기"를 누르면 그 저장본 전체를 펼쳐서 보여줌
//      - 글 제목·미리보기나 "글쓰기에서 열기"를 누르면 그 글이 채워진 글쓰기 페이지로 이동
//      - "삭제"를 누르면 확인창을 거쳐 그 글을 지움 (서버 API: DELETE /api/documents/{id}, 백엔드 담당 작업)
//
// 데이터: 백엔드 routers/mypage.py
//   GET /api/mypage/profile, GET /api/mypage/documents
//   (본문 전체는 GET /api/documents/{id}/drafts)
// =============================================================

import { useState, useEffect, useCallback } from "react";
import {
  Settings,
  Mail,
  Phone,
  CalendarDays,
  FileText,
  CheckCircle2,
  Flame,
  PenLine,
  ChevronDown,
  ArrowRight,
  ChevronUp,
  ChevronLeft,
  ChevronRight,
  RefreshCw,
  LogIn,
  Loader2,
  Trash2,
} from "lucide-react";

import PageHero from "../components/PageHero";
// 글 삭제 확인창
import DeleteDocumentModal from "../components/DeleteDocumentModal";
import { fetchMyProfile, fetchMyDocuments, fetchDocumentDrafts, deleteDocument } from "../api/mypage";
import { formatPhone } from "../utils/validation";
// 로딩 아이콘이 빙글빙글 도는 .spin 클래스가 들어 있는 파일 (로그인·회원가입과 같이 씀)
import "../components/AuthLayout.css";
import "./MyPage.css";

// ----- 카테고리(글 유형) 목록 -----
// 글쓰기 화면(WritingPage.jsx)의 WRITING_TYPES와 이름을 똑같이 맞춤
// → 글쓰기에서 고른 글 유형(document_type)이 그대로 카테고리가 됨
// ※ 글쓰기 화면에 글 유형을 새로 추가하면 여기에도 같이 추가해야 함
const CATEGORIES = ["자유 글쓰기", "자기소개서", "보고서", "발표문", "기타"];

// "기타"에서 직접 입력한 유형(예: "편지")처럼 위 목록에 없는 글은 전부 "기타"로 모음
const OTHER_CATEGORY = "기타";

// 맨 앞 "전체" 버튼의 key
const ALL = "all";

// 한 페이지에 보여줄 글(카드) 수 — 바꾸고 싶으면 이 숫자만 고치면 됨
const PAGE_SIZE = 10;

// ----- 단계 목록 -----
// 서버(routers/mypage.py)가 두 가지로 계산해서 보내 줌
//  1) 글마다 stage: 지금 그 글이 어느 단계인지 (글 카드의 배지)
//  2) 저장본마다 kind: 그 저장본이 어느 탭에 들어가는지 (단계 버튼을 눌렀을 때 카드)
//  - 초안: 첫 번째 저장본
//  - 수정: 두 번째 저장본부터
//  - 완료: 글쓰기 화면에서 최종 저장한 저장본
// className: 배지·버튼 색을 정하는 CSS 이름 (MyPage.css)
const STAGES = [
  { key: "초안", className: "draft" },
  { key: "수정", className: "revise" },
  { key: "완료", className: "done" },
];

// 글 하나가 어느 카테고리인지 (목록에 없는 유형이면 "기타")
function categoryOf(doc) {
  // includes: 배열 안에 그 값이 있으면 true
  return CATEGORIES.includes(doc.document_type) ? doc.document_type : OTHER_CATEGORY;
}

// 단계 이름 → CSS 이름 ("초안" → "draft"), 모르는 값이면 초안 색으로
function stageClass(stage) {
  return STAGES.find((item) => item.key === stage)?.className || "draft";
}

// ----- 날짜 글자 → "2026.10.22" 모양 -----
function formatDate(value) {
  if (!value) return "-";
  const date = new Date(value);
  if (Number.isNaN(date.getTime())) return "-"; // 날짜로 못 바꾸면 "-"
  const month = String(date.getMonth() + 1).padStart(2, "0"); // getMonth()는 0부터 시작해서 +1
  const day = String(date.getDate()).padStart(2, "0"); // padStart(2, "0"): 한 자리면 앞에 0 붙이기
  return `${date.getFullYear()}.${month}.${day}`;
}

// ----- 카드 하나를 구분하는 이름표 -----
// 글 카드: "doc-3" / 저장본 카드: "doc-3-v2" (React의 key, 펼친 카드 기억에 씀)
function entryKey(documentId, version) {
  return version ? `doc-${documentId}-v${version}` : `doc-${documentId}`;
}

// props
//  - auth: 로그인 정보 { token, user } (로그인 안 했으면 null)
//  - onEdit: "마이페이지 수정" 버튼을 눌렀을 때 실행 (수정 화면으로 이동)
//  - onGoWrite: 쓴 글이 없을 때 "글쓰기 시작하기" 버튼
//  - onGoLogin: 로그인 안 했을 때 "로그인하기" 버튼
//  - onSessionExpired: 토큰이 만료됐을 때 (App이 로그아웃시키고 로그인 화면으로 보냄)
//  - onOpenDocument: 글을 눌렀을 때 실행 → { id, title, document_type, status, content }를 넘기면
//                    App이 그 글이 들어간 글쓰기 페이지로 이동시킴
function MyPage({ auth, onEdit, onGoWrite, onGoLogin, onSessionExpired, onOpenDocument }) {
  const token = auth?.token;

  // ----- 상태값 -----
  const [profile, setProfile] = useState(null); // 프로필 + 활동 요약
  const [documents, setDocuments] = useState([]); // 내가 쓴 글 목록
  // loading: 처음부터 불러오는 중으로 시작 (로그인 안 했으면 불러올 게 없으니 false)
  const [loading, setLoading] = useState(Boolean(token));
  const [error, setError] = useState(""); // 불러오기 실패 문구
  const [reloadKey, setReloadKey] = useState(0); // "다시 불러오기"를 누를 때마다 +1 → 아래 useEffect 다시 실행

  const [category, setCategory] = useState(ALL); // 지금 고른 카테고리 (처음엔 전체)
  const [stage, setStage] = useState(null); // 지금 고른 단계 (null이면 단계로 거르지 않음 = 모든 단계)
  // page: 지금 보고 있는 페이지 번호 (1부터 시작) — 글 목록을 PAGE_SIZE개씩 나눠서 보여줌 (페이지네이션)
  const [page, setPage] = useState(1);
  // openKey: 본문을 펼친 카드 (하나만 펼침, 없으면 null)
  //  - 글 카드: "doc-글번호" / 저장본 카드: "doc-글번호-v버전" (아래 entryKey 참고)
  const [openKey, setOpenKey] = useState(null);
  // bodies: 불러온 저장본들을 글별로 기억해 두는 곳 { 글번호: { loading, drafts: [저장본...], error } }
  // → 한 번 불러온 글은 다른 저장본 카드를 펼쳐도 서버에 또 묻지 않음
  const [bodies, setBodies] = useState({});
  // openingId: 글쓰기 페이지로 여는 중인 글 번호 (본문을 불러오는 동안 그 글에 "여는 중..." 표시)
  const [openingId, setOpeningId] = useState(null);
  // deleteTarget: 삭제 확인창에 띄운 글 (null이면 창 안 보임)
  //  { doc: 지울 글, deleting: 서버에 지우는 중인지, error: 실패 문구 }
  const [deleteTarget, setDeleteTarget] = useState(null);

  // ----- 프로필 + 글 목록 불러오기 -----
  useEffect(() => {
    if (!token) return; // 로그인 안 했으면 아무것도 안 함

    let ignore = false; // 응답이 오기 전에 화면을 떠나면 결과를 무시하려고 쓰는 깃발

    // Promise.all: 두 요청을 동시에 보내고, 둘 다 끝나면 결과를 배열로 받음 (하나씩 기다리는 것보다 빠름)
    Promise.all([fetchMyProfile(token), fetchMyDocuments(token)])
      .then(([profileData, documentList]) => {
        if (ignore) return;
        setProfile(profileData);
        setDocuments(documentList);
        setError("");
        setLoading(false);
      })
      .catch((err) => {
        if (ignore) return;
        // 401: 토큰이 만료됐거나 잘못됨 → App에 알려서 다시 로그인하게 함
        if (err.status === 401) {
          onSessionExpired?.(); // ?.(): 함수가 있을 때만 실행
          return;
        }
        setError(err.message);
        setLoading(false);
      });

    // 정리 함수: 화면을 떠나거나 다시 불러오기 전에 이전 요청 결과를 무시하도록 표시
    return () => {
      ignore = true;
    };
  }, [token, reloadKey, onSessionExpired]);

  // "다시 불러오기" 버튼
  const handleReload = () => {
    setLoading(true);
    setReloadKey((key) => key + 1);
  };

  // ----- 저장본 불러오기 (글 하나의 저장본 전부, 최신 버전부터) -----
  // 이미 불러왔으면 기억해 둔 걸 그대로 돌려줌 → 실패하면 에러를 던짐
  const loadDrafts = async (documentId) => {
    const cached = bodies[documentId]?.drafts;
    if (cached) return cached;
    // prev => ({ ...prev, [키]: 값 }): 기존 내용은 그대로 두고 이 글 번호 칸만 바꿈
    setBodies((prev) => ({ ...prev, [documentId]: { loading: true } }));
    const drafts = await fetchDocumentDrafts(token, documentId);
    setBodies((prev) => ({ ...prev, [documentId]: { loading: false, drafts } }));
    return drafts;
  };

  // 저장본 목록에서 원하는 버전 본문 꺼내기 (version이 null이면 마지막 저장본 = 맨 앞)
  const pickContent = (drafts, version) => {
    const draft = version ? drafts.find((item) => item.version === version) : drafts[0];
    return draft?.content || "";
  };

  // ----- 본문 펼치기 / 접기 -----
  // entry: 화면의 카드 하나 { key, doc, version } (version이 null이면 글 카드 = 마지막 저장본)
  const handleToggle = async (entry) => {
    // 이미 펼친 카드를 다시 누르면 접기
    if (openKey === entry.key) {
      setOpenKey(null);
      return;
    }
    setOpenKey(entry.key);

    try {
      await loadDrafts(entry.doc.id);
    } catch (err) {
      if (err.status === 401) {
        onSessionExpired?.();
        return;
      }
      setBodies((prev) => ({ ...prev, [entry.doc.id]: { loading: false, error: err.message } }));
    }
  };

  // ----- 글쓰기 페이지에서 열기 -----
  // 글 카드 → 마지막 저장본, 저장본 카드 → 그 저장본 본문을 채워서 App에 넘김
  // (예전 수정본을 열어서 저장하면, 그 내용이 이 글의 새 버전으로 이어서 저장됨)
  const handleOpen = async (entry) => {
    if (openingId !== null) return; // 이미 다른 글을 여는 중이면 무시 (두 번 누르기 방지)
    const { doc, version } = entry;

    let content = "";
    if (doc.latest_version > 0) {
      setOpeningId(entry.key);
      try {
        content = pickContent(await loadDrafts(doc.id), version);
      } catch (err) {
        setOpeningId(null);
        if (err.status === 401) {
          onSessionExpired?.();
          return;
        }
        // 실패하면 펼친 본문 자리에 에러를 보여줌
        setOpenKey(entry.key);
        setBodies((prev) => ({ ...prev, [doc.id]: { loading: false, error: err.message } }));
        return;
      }
    }

    // 이 화면은 곧 사라지니까 openingId는 되돌리지 않아도 됨
    onOpenDocument?.({
      id: doc.id,
      title: doc.title,
      document_type: doc.document_type,
      status: doc.status, // "완료"면 글쓰기 페이지에서 읽기 전용으로 열림
      content, // 저장한 본문이 없으면 빈 글
      latest_version: doc.latest_version, // 지금까지 저장한 횟수 → 글쓰기 화면의 초안/수정 단계 배지에 씀
    });
  };

  // ----- 글 삭제 -----
  // 1) "삭제" 버튼 → 확인창 띄우기
  const handleAskDelete = (doc) => {
    setDeleteTarget({ doc, deleting: false, error: "" });
  };

  // 2) 확인창의 "취소" (Esc, 바깥 클릭 포함)
  // useCallback: 확인창의 Esc 키 처리(useEffect)가 쓸데없이 다시 등록되지 않게 함수를 고정
  const handleCancelDelete = useCallback(() => setDeleteTarget(null), []);

  // 3) 확인창의 "삭제하기" → 서버에 삭제 요청
  const handleConfirmDelete = async () => {
    if (!deleteTarget || deleteTarget.deleting) return; // 두 번 누르기 방지
    const { doc } = deleteTarget;
    setDeleteTarget({ doc, deleting: true, error: "" });

    try {
      await deleteDocument(token, doc.id);
    } catch (err) {
      if (err.status === 401) {
        onSessionExpired?.();
        return;
      }
      // 실패하면 창은 그대로 두고 빨간 문구로 이유를 보여줌
      setDeleteTarget({ doc, deleting: false, error: err.message });
      return;
    }

    // 성공: 서버에 다시 묻지 않고 화면에서 바로 빼기
    // filter: 조건이 참인 것만 남긴 새 배열 → 지운 글만 빠짐
    setDocuments((prev) => prev.filter((item) => item.id !== doc.id));
    // 프로필 카드의 "내가 쓴 글 / 완료한 글" 숫자도 하나씩 줄이기
    setProfile((prev) =>
      prev
        ? {
            ...prev,
            document_count: Math.max(0, prev.document_count - 1),
            completed_count:
              doc.stage === "완료" ? Math.max(0, prev.completed_count - 1) : prev.completed_count,
          }
        : prev
    );
    // 그 글의 카드를 펼쳐 뒀으면 닫고, 기억해 둔 본문도 지움
    if (openKey?.startsWith(`doc-${doc.id}`)) setOpenKey(null);
    setBodies((prev) => {
      const next = { ...prev };
      delete next[doc.id];
      return next;
    });
    setDeleteTarget(null);
  };

  // ===================== 화면 그리기 =====================

  // 페이지 맨 위 제목 영역 (모든 경우에 같이 씀)
  const hero = (
    <PageHero
      eyebrow="나의 글쓰기 기록"
      title="마이페이지"
      description={"내 정보와 지금까지 쓴 글을 한눈에 확인해요."}
      memoText={"차곡차곡\n쌓이는\n내 문장 :)"}
      memoVariant="note"
    />
  );

  // ----- 로그인 안 했을 때 -----
  if (!token) {
    return (
      <div className="sub-page">
        <div className="sub-page-inner">
          {hero}
          <section className="panel mypage-message">
            <LogIn size={36} strokeWidth={1.6} className="mypage-message-icon" />
            <p>마이페이지는 로그인한 뒤에 볼 수 있어요.</p>
            <button type="button" className="btn-primary" onClick={onGoLogin}>
              로그인하기
            </button>
          </section>
        </div>
      </div>
    );
  }

  // ----- 불러오는 중 / 실패 -----
  if (loading || error || !profile) {
    return (
      <div className="sub-page">
        <div className="sub-page-inner">
          {hero}
          <section className="panel mypage-message">
            {error ? (
              <>
                <p>{error}</p>
                <button type="button" className="btn-outline" onClick={handleReload}>
                  <RefreshCw size={16} /> 다시 불러오기
                </button>
              </>
            ) : (
              <p>
                <Loader2 size={18} className="spin" /> 내 정보를 불러오는 중이에요...
              </p>
            )}
          </section>
        </div>
      </div>
    );
  }

  // ----- 화면에 보여줄 카드 고르기 (2단계로 거름) -----
  // 1단계: 고른 카테고리에 들어 있는 글 (filter: 조건에 맞는 것만 골라 새 배열을 만듦)
  const categoryDocuments = category === ALL ? documents : documents.filter((doc) => categoryOf(doc) === category);

  // 그 글들의 저장본 중 한 단계(초안/수정/완료)에 들어가는 것만 카드로 만들기
  // flatMap: 글마다 나온 카드 배열을 하나로 이어 붙임 (글 2개 × 저장본 2개 → 카드 4개)
  // 최근 저장본이 위로 오게 정렬 (sort: 저장 시각이 큰 것 먼저)
  //  → 같은 초에 저장해서 시각이 같으면 저장 번호가 큰 것(더 나중 저장본) 먼저
  const versionEntries = (stageKey) =>
    categoryDocuments
      .flatMap((doc) =>
        (doc.versions || [])
          .filter((item) => item.kind === stageKey)
          .map((item) => ({ key: entryKey(doc.id, item.version), doc, version: item.version, info: item }))
      )
      .sort(
        (a, b) =>
          new Date(b.info.created_at || 0) - new Date(a.info.created_at || 0) || b.version - a.version
      );

  // 2단계: 단계를 골랐으면 그 단계의 저장본 카드, 안 골랐으면 글 카드 (글마다 한 장)
  const entries = stage
    ? versionEntries(stage)
    : categoryDocuments.map((doc) => ({ key: entryKey(doc.id, null), doc, version: null, info: null }));

  // ----- 페이지 나누기 (페이지네이션) -----
  // 전체 페이지 수: 카드 23개면 23 / 10 = 2.3 → 올림(Math.ceil)해서 3페이지 (최소 1페이지)
  const totalPages = Math.max(1, Math.ceil(entries.length / PAGE_SIZE));
  // 글을 지워서 페이지 수가 줄었는데 지금 페이지가 그보다 크면 마지막 페이지를 보여줌
  // (예: 3페이지의 마지막 글을 지우면 → 2페이지로)
  const currentPage = Math.min(page, totalPages);
  // slice(시작, 끝): 배열에서 그 구간만 잘라냄 → 1페이지는 0~9번, 2페이지는 10~19번 카드
  const pageEntries = entries.slice((currentPage - 1) * PAGE_SIZE, currentPage * PAGE_SIZE);
  // 아래에 보여줄 페이지 번호들 (페이지가 많으면 지금 페이지 근처 최대 5개만: 예) 3 4 [5] 6 7)
  const pageNumbers = (() => {
    const start = Math.max(1, Math.min(currentPage - 2, totalPages - 4));
    const end = Math.min(totalPages, start + 4);
    // Array.from({ length: n }, (_, i) => ...): n개짜리 배열을 만들면서 값 채우기
    return Array.from({ length: end - start + 1 }, (_, i) => start + i);
  })();

  // 페이지 번호 누르기: 그 페이지로 바꾸고, 펼쳐 둔 본문은 접고, 목록 맨 위로 스크롤
  const handlePage = (next) => {
    if (next < 1 || next > totalPages || next === currentPage) return;
    setPage(next);
    setOpenKey(null);
    // scrollIntoView: 그 요소가 화면 맨 위에 오도록 스크롤 (behavior: "smooth" → 부드럽게)
    document.getElementById("mypage-docs-title")?.scrollIntoView({ behavior: "smooth", block: "start" });
  };

  // 버튼 옆에 보여줄 개수
  //  - 카테고리 버튼: 그 카테고리의 글 수
  //  - 단계 버튼: 지금 고른 카테고리 안에서 그 단계에 들어가는 저장본 수
  const countOfCategory = (key) =>
    key === ALL ? documents.length : documents.filter((doc) => categoryOf(doc) === key).length;
  const countOfStage = (key) => versionEntries(key).length;

  // 카테고리 버튼 누르기: 카테고리를 바꾸고 펼쳐 둔 본문은 접음
  const handleCategory = (key) => {
    setCategory(key);
    setOpenKey(null);
    setPage(1); // 목록이 바뀌니까 1페이지부터
  };

  // 단계 버튼 누르기: 이미 고른 단계를 다시 누르면 꺼짐(null) → 모든 단계 보기
  const handleStage = (key) => {
    setStage((prev) => (prev === key ? null : key));
    setOpenKey(null);
    setPage(1); // 목록이 바뀌니까 1페이지부터
  };

  // 걸러진 결과가 없을 때 보여줄 문구 (어떤 조건으로 걸렀는지 알려줌)
  const emptyMessage = (() => {
    const where = category === ALL ? "" : `${category} 카테고리에 `;
    return stage ? `${where}${stage} 단계 저장본이 없어요.` : `${where}아직 쓴 글이 없어요.`;
  })();

  return (
    <div className="sub-page">
      <div className="sub-page-inner">
        {hero}

        {/* ===================== 1. 내 프로필 카드 ===================== */}
        <section className="panel mypage-profile" aria-labelledby="mypage-profile-title">
          <div className="mypage-profile-top">
            {/* 동그란 프로필 (이름 첫 글자) */}
            <div className="mypage-avatar" aria-hidden="true">
              {profile.name.slice(0, 1)}
            </div>

            <div className="mypage-profile-main">
              <h2 id="mypage-profile-title" className="mypage-name">
                {profile.name}
                <span className="mypage-login-id">@{profile.login_id}</span>
              </h2>

              {/* 연락처·가입일 (dl: 이름-값 짝으로 된 목록을 나타내는 태그) */}
              <dl className="mypage-info">
                <div>
                  <dt>
                    <Mail size={15} /> 이메일
                  </dt>
                  <dd>{profile.email}</dd>
                </div>
                <div>
                  <dt>
                    <Phone size={15} /> 전화번호
                  </dt>
                  <dd>{formatPhone(profile.phone)}</dd>
                </div>
                <div>
                  <dt>
                    <CalendarDays size={15} /> 가입일
                  </dt>
                  <dd>{formatDate(profile.created_at)}</dd>
                </div>
              </dl>
            </div>

            {/* 오른쪽 위: 마이페이지 수정 버튼 */}
            <button type="button" className="btn-outline mypage-edit-button" onClick={onEdit}>
              <Settings size={16} />
              마이페이지 수정
            </button>
          </div>

          {/* 활동 요약 3칸 */}
          <ul className="mypage-stats">
            <li>
              <FileText size={20} />
              <span className="mypage-stat-label">내가 쓴 글</span>
              <strong>{profile.document_count}편</strong>
            </li>
            <li>
              <CheckCircle2 size={20} />
              <span className="mypage-stat-label">완료한 글</span>
              <strong>{profile.completed_count}편</strong>
            </li>
            <li>
              <Flame size={20} />
              <span className="mypage-stat-label">도전 최고 기록</span>
              <strong>{profile.best_challenge_score}문제 연속</strong>
            </li>
          </ul>
        </section>

        {/* ===================== 2. 내가 쓴 글 ===================== */}
        <section className="panel mypage-docs" aria-labelledby="mypage-docs-title">
          <div className="mypage-docs-head">
            <h2 id="mypage-docs-title">
              <PenLine size={20} />
              내가 쓴 글
            </h2>

            {/* 단계 버튼 (초안 / 수정 / 완료) — 글이 하나도 없으면 숨김 */}
            {documents.length > 0 && (
              <div className="mypage-filters" role="group" aria-label="단계로 거르기">
                {STAGES.map((item) => (
                  <button
                    key={item.key}
                    type="button"
                    className={`mypage-filter ${item.className}${stage === item.key ? " active" : ""}`}
                    aria-pressed={stage === item.key} // 눌린 상태를 화면 읽기 프로그램에 알려줌
                    onClick={() => handleStage(item.key)}
                    title={stage === item.key ? "한 번 더 누르면 모든 단계 보기" : `${item.key} 단계만 보기`}
                  >
                    {item.key} <span>{countOfStage(item.key)}</span>
                  </button>
                ))}
              </div>
            )}
          </div>

          {/* 카테고리 버튼 (전체 + 글 유형별) — 글이 하나도 없으면 숨김 */}
          {documents.length > 0 && (
            <div className="mypage-categories" role="group" aria-label="카테고리로 거르기">
              {/* [ALL, ...CATEGORIES]: 맨 앞에 "전체"를 붙인 새 배열 */}
              {[ALL, ...CATEGORIES].map((key) => {
                const count = countOfCategory(key);
                return (
                  <button
                    key={key}
                    type="button"
                    className={`mypage-category${category === key ? " active" : ""}${count === 0 ? " empty" : ""}`}
                    aria-pressed={category === key}
                    onClick={() => handleCategory(key)}
                  >
                    {key === ALL ? "전체" : key}
                    <span className="mypage-category-count">{count}</span>
                  </button>
                );
              })}
            </div>
          )}

          {documents.length === 0 ? (
            // ----- 쓴 글이 하나도 없을 때 -----
            <div className="mypage-empty">
              <FileText size={36} strokeWidth={1.5} />
              <p>
                아직 쓴 글이 없어요.
                <br />
                생각 한 줄로 첫 글을 시작해 보세요!
              </p>
              <button type="button" className="btn-primary" onClick={onGoWrite}>
                <PenLine size={16} /> 글쓰기 시작하기
              </button>
            </div>
          ) : entries.length === 0 ? (
            // ----- 고른 카테고리·단계에 맞는 글이 없을 때 -----
            <div className="mypage-empty-filter">
              <p>{emptyMessage}</p>
              {/* 단계까지 골라서 비었으면 단계만 풀 수 있게 버튼 제공 */}
              {stage && (
                <button type="button" className="mypage-doc-toggle" onClick={() => handleStage(stage)}>
                  글 목록으로 보기
                </button>
              )}
            </div>
          ) : (
            // ----- 글 목록 -----
            <>
            <ul className="mypage-doc-list">
              {/* 지금 페이지에 해당하는 카드(최대 10개)만 그림 */}
              {pageEntries.map((entry) => {
                const { doc, version, info } = entry; // info: 저장본 카드일 때 그 저장본 정보 (글 카드면 null)
                const isOpen = openKey === entry.key;
                const body = bodies[doc.id]; // 불러온 적 있으면 저장본 정보, 없으면 undefined
                const bodyId = `body-${entry.key}`;
                // 배지에 보여줄 단계: 저장본 카드면 그 저장본의 탭, 글 카드면 글의 지금 단계
                const badge = info ? info.kind : doc.stage;
                // 미리보기: 저장본 카드면 그 저장본, 글 카드면 마지막 저장본
                const preview = info ? info.preview : doc.preview;
                const savedCount = info ? info.version : doc.latest_version;

                return (
                  <li key={entry.key} className={isOpen ? "mypage-doc open" : "mypage-doc"}>
                    <div className="mypage-doc-top">
                      {/* 배지: 글 유형(카테고리) / 단계 (초안·수정·완료) */}
                      <span className="doc-badge type">{doc.document_type}</span>
                      <span className={`doc-badge ${stageClass(badge)}`}>{badge}</span>
                      <span className="mypage-doc-date">
                        {savedCount > 0 && `저장 ${savedCount}번째 · `}
                        {info
                          ? `${formatDate(info.created_at)} 저장`
                          : `${formatDate(doc.updated_at || doc.created_at)} 수정`}
                      </span>
                    </div>

                    {/*
                      제목 + 미리보기 = 누르면 글쓰기 페이지로 여는 버튼
                      (카드 전체를 버튼으로 만들면 안쪽의 "본문 보기" 버튼과 겹쳐서, 이 부분만 버튼으로 만듦)
                    */}
                    <button
                      type="button"
                      className="mypage-doc-open"
                      onClick={() => handleOpen(entry)}
                      disabled={openingId !== null}
                      aria-label={`${doc.title}${version ? ` ${version}번째 저장본` : ""} 글쓰기 페이지에서 열기`}
                    >
                      <span className="mypage-doc-title">{doc.title}</span>
                      {/* 펼치기 전에만 미리보기 (펼치면 아래에 본문 전체가 보이니까) */}
                      {!isOpen && (
                        <span className="mypage-doc-preview">{preview || "아직 저장한 본문이 없어요."}</span>
                      )}
                    </button>

                    {/* 아래 버튼 줄: 왼쪽 "본문 보기", 오른쪽 "삭제" + "글쓰기에서 열기" */}
                    <div className="mypage-doc-actions">
                      {/* 본문 보기 / 접기 버튼 (저장한 본문이 있을 때만) */}
                      {savedCount > 0 && (
                        <button
                          type="button"
                          className="mypage-doc-toggle"
                          onClick={() => handleToggle(entry)}
                          aria-expanded={isOpen} // 펼쳐졌는지 화면 읽기 프로그램에 알려줌
                          aria-controls={bodyId}
                        >
                          {isOpen ? (
                            <>
                              접기 <ChevronUp size={16} />
                            </>
                          ) : (
                            <>
                              본문 보기 <ChevronDown size={16} />
                            </>
                          )}
                        </button>
                      )}

                      {/*
                        오른쪽 버튼 묶음 (삭제 + 글쓰기에서 열기)
                        묶어 두면 화면이 좁아서 줄이 넘어갈 때도 두 버튼이 같이 오른쪽에 붙어 있음
                      */}
                      <div className="mypage-doc-right">
                      {/*
                        삭제 버튼 → 확인창 (글을 여는 중에는 막음)
                        글 전체를 지우는 버튼이라 글 카드에만 보여줌 (저장본 카드에는 없음)
                      */}
                      {!info && (
                        <button
                          type="button"
                          className="mypage-doc-delete"
                          onClick={() => handleAskDelete(doc)}
                          disabled={openingId !== null}
                          aria-label={`${doc.title} 삭제`}
                        >
                          <Trash2 size={14} /> 삭제
                        </button>
                      )}

                      {/* 글쓰기 페이지에서 열기 (완료된 글은 고칠 수 없으니 "글 보기") */}
                      <button
                        type="button"
                        className="mypage-doc-go"
                        onClick={() => handleOpen(entry)}
                        disabled={openingId !== null}
                      >
                        {openingId === entry.key ? (
                          <>
                            <Loader2 size={15} className="spin" /> 여는 중...
                          </>
                        ) : (
                          <>
                            {doc.stage === "완료" ? "글 보기" : "글쓰기에서 열기"} <ArrowRight size={15} />
                          </>
                        )}
                      </button>
                      </div>
                    </div>

                    {/* 펼친 본문 */}
                    {isOpen && (
                      <div id={bodyId} className="mypage-doc-body">
                        {!body || body.loading ? (
                          <p className="mypage-doc-muted">
                            <Loader2 size={16} className="spin" /> 본문을 불러오는 중이에요...
                          </p>
                        ) : body.error ? (
                          <p className="mypage-doc-muted">{body.error}</p>
                        ) : (
                          // white-space: pre-wrap(CSS)으로 줄바꿈을 그대로 보여줌
                          // React는 글자를 자동으로 안전하게 바꿔서 넣기 때문에 본문에 태그가 있어도 실행되지 않음
                          <p className="mypage-doc-text">{pickContent(body.drafts || [], version)}</p>
                        )}
                      </div>
                    )}
                  </li>
                );
              })}
            </ul>

            {/* ----- 페이지 번호 (1페이지뿐이어도 항상 보여줌) ----- */}
            {totalPages >= 1 && (
              // nav: "이동 메뉴"라는 뜻의 태그 → 화면 읽기 프로그램이 페이지 이동 버튼 묶음으로 알아들음
              <nav className="mypage-pagination" aria-label="내가 쓴 글 페이지">
                <button
                  type="button"
                  className="mypage-page-arrow"
                  onClick={() => handlePage(currentPage - 1)}
                  disabled={currentPage === 1}
                  aria-label="이전 페이지"
                >
                  <ChevronLeft size={18} />
                </button>

                {pageNumbers.map((number) => (
                  <button
                    key={number}
                    type="button"
                    className={number === currentPage ? "mypage-page active" : "mypage-page"}
                    onClick={() => handlePage(number)}
                    // aria-current="page": 지금 보고 있는 페이지라는 표시
                    aria-current={number === currentPage ? "page" : undefined}
                  >
                    {number}
                  </button>
                ))}

                <button
                  type="button"
                  className="mypage-page-arrow"
                  onClick={() => handlePage(currentPage + 1)}
                  disabled={currentPage === totalPages}
                  aria-label="다음 페이지"
                >
                  <ChevronRight size={18} />
                </button>
              </nav>
            )}
            </>
          )}
        </section>
      </div>

      {/* 글 삭제 확인창 (deleteTarget이 있을 때만) */}
      {deleteTarget && (
        <DeleteDocumentModal
          title={deleteTarget.doc.title}
          deleting={deleteTarget.deleting}
          error={deleteTarget.error}
          onCancel={handleCancelDelete}
          onConfirm={handleConfirmDelete}
        />
      )}
    </div>
  );
}

export default MyPage;
