// =============================================================
// NoticePage.jsx — 공지사항 화면 (푸터 "고객지원 → 공지사항")
// -------------------------------------------------------------
// 화면이 두 가지 모드로 바뀜
//   1) 목록 모드 : 공지 제목 목록 (10개씩 페이지로 나눔, "중요" 고정 공지가 맨 위)
//   2) 상세 모드 : 목록에서 누른 공지의 제목·날짜·내용 + "목록으로" 버튼
//
// 공지는 관리자 페이지 → "공지사항 관리" 탭에서 등록·수정·삭제함
// 데이터: 백엔드 GET /api/notices (로그인 없이 누구나)
// =============================================================

import { useEffect, useState } from "react";
// Megaphone: 빈 목록 아이콘, Pin: 고정 공지 표시, ArrowLeft: 목록으로, ChevronLeft/Right: 페이지 화살표
// Loader2: 불러오는 중 빙글빙글, RefreshCw: 다시 불러오기
import { Megaphone, Pin, ArrowLeft, ChevronLeft, ChevronRight, Loader2, RefreshCw } from "lucide-react";

import PageHero from "../components/PageHero";
// 창만 스크롤하는 도구 (scrollIntoView를 쓰면 overflow: hidden 상자 안 내용이 밀려 올라가는 문제가 있어서)
import scrollToElement from "../utils/scrollToElement";
import SupportTabs from "../components/SupportTabs";
import { fetchNotices } from "../api/notice";
// 로딩 아이콘이 도는 .spin 클래스가 들어 있는 파일
import "../components/AuthLayout.css";
import "./SupportPages.css";

// 한 페이지에 보여줄 공지 개수
const PAGE_SIZE = 10;

// ----- 날짜 → "2026.11.03" -----
function formatDate(value) {
  if (!value) return "";
  const date = new Date(value);
  if (Number.isNaN(date.getTime())) return "";
  const month = String(date.getMonth() + 1).padStart(2, "0"); // getMonth()는 0부터 시작해서 +1
  const day = String(date.getDate()).padStart(2, "0");
  return `${date.getFullYear()}.${month}.${day}`;
}

// 등록 후 수정했는지 (수정 시각이 등록 시각보다 1분 넘게 뒤면 "수정됨"으로 봄)
// → 등록할 때도 두 시각이 거의 같이 찍히니까 몇 초 차이는 무시
function isEdited(notice) {
  if (!notice.updated_at || !notice.created_at) return false;
  return new Date(notice.updated_at) - new Date(notice.created_at) > 60 * 1000;
}

// props: onNavigate → 위쪽 고객지원 탭을 눌렀을 때 화면 이동 (App의 handleNavigate)
function NoticePage({ onNavigate }) {
  const [notices, setNotices] = useState([]); // 서버에서 받은 공지 목록
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");
  const [reloadKey, setReloadKey] = useState(0); // +1 하면 목록을 다시 불러옴
  const [page, setPage] = useState(1); // 지금 보고 있는 페이지
  // selectedId: 상세로 보고 있는 공지 번호 (null이면 목록 모드)
  const [selectedId, setSelectedId] = useState(null);

  // ----- 목록 불러오기 (처음 들어올 때 + "다시 불러오기"를 눌렀을 때) -----
  useEffect(() => {
    let ignore = false; // 화면을 떠난 뒤에 응답이 오면 무시 (이미 없는 화면의 상태를 바꾸지 않게)
    fetchNotices()
      .then((data) => {
        if (ignore) return;
        setNotices(data);
        setError("");
        setLoading(false);
      })
      .catch((err) => {
        if (ignore) return;
        setError(err.message);
        setLoading(false);
      });
    return () => {
      ignore = true;
    };
  }, [reloadKey]);

  // ----- 페이지 나누기 -----
  // 23개면 23 / 10 = 2.3 → 올림해서 3페이지 (최소 1페이지)
  const totalPages = Math.max(1, Math.ceil(notices.length / PAGE_SIZE));
  // 목록이 줄어서 지금 페이지가 없어졌으면 마지막 페이지로
  const currentPage = Math.min(page, totalPages);
  const pageNotices = notices.slice((currentPage - 1) * PAGE_SIZE, currentPage * PAGE_SIZE);

  // 상세로 보고 있는 공지 (목록에 없으면 undefined → 목록 모드로 보여줌)
  const selected = notices.find((notice) => notice.notice_id === selectedId);

  // 화면 위쪽(탭 위치)으로 부드럽게 올리기 → 상세·페이지를 바꿨을 때 처음부터 보이게
  const scrollToTop = () => {
    scrollToElement(".support-tabs");
  };

  const openNotice = (noticeId) => {
    setSelectedId(noticeId);
    scrollToTop();
  };

  const goPage = (next) => {
    if (next < 1 || next > totalPages || next === currentPage) return;
    setPage(next);
    scrollToTop();
  };

  // 페이지 번호: 페이지가 많으면 지금 페이지 근처 최대 5개만 (예: 3 4 [5] 6 7)
  const start = Math.max(1, Math.min(currentPage - 2, totalPages - 4));
  const end = Math.min(totalPages, start + 4);
  const numbers = Array.from({ length: end - start + 1 }, (_, i) => start + i);

  // ----- 가운데 카드에 들어갈 내용 고르기 -----
  let body;
  if (loading) {
    body = (
      <p className="support-state">
        <Loader2 size={18} className="spin" /> 공지사항을 불러오는 중이에요...
      </p>
    );
  } else if (error) {
    body = (
      <div className="support-state">
        <p>{error}</p>
        <button
          type="button"
          className="btn-outline"
          onClick={() => {
            setLoading(true);
            setReloadKey((key) => key + 1);
          }}
        >
          <RefreshCw size={15} /> 다시 불러오기
        </button>
      </div>
    );
  } else if (selected) {
    // ===== 상세 모드 =====
    body = (
      <article className="notice-detail">
        <button type="button" className="notice-back" onClick={() => setSelectedId(null)}>
          <ArrowLeft size={16} /> 목록으로
        </button>
        <header className="notice-detail-head">
          {selected.is_pinned && (
            <span className="notice-badge">
              <Pin size={12} /> 중요
            </span>
          )}
          <h2>{selected.title}</h2>
          <p className="notice-date">
            {formatDate(selected.created_at)}
            {isEdited(selected) && ` · ${formatDate(selected.updated_at)} 수정`}
          </p>
        </header>
        {/* white-space: pre-line(CSS)으로 관리자가 넣은 줄바꿈이 그대로 보임 */}
        <div className="notice-content">{selected.content}</div>
      </article>
    );
  } else if (notices.length === 0) {
    body = (
      <p className="support-state">
        <Megaphone size={20} /> 아직 등록된 공지사항이 없어요.
      </p>
    );
  } else {
    // ===== 목록 모드 =====
    body = (
      <>
        <p className="notice-count">전체 {notices.length}건</p>
        <ul className="notice-list">
          {pageNotices.map((notice) => (
            <li key={notice.notice_id}>
              {/* 한 줄 전체가 버튼 → 어디를 눌러도 상세로 (키보드 Enter로도 됨) */}
              <button
                type="button"
                className={notice.is_pinned ? "notice-row pinned" : "notice-row"}
                onClick={() => openNotice(notice.notice_id)}
              >
                {notice.is_pinned && (
                  <span className="notice-badge">
                    <Pin size={12} /> 중요
                  </span>
                )}
                <span className="notice-row-title">{notice.title}</span>
                <span className="notice-date">{formatDate(notice.created_at)}</span>
              </button>
            </li>
          ))}
        </ul>

        {/* 페이지 번호 (1페이지뿐이어도 항상 보여줌) */}
        <nav className="support-pagination" aria-label="공지사항 페이지">
          <button
            type="button"
            className="support-page-arrow"
            onClick={() => goPage(currentPage - 1)}
            disabled={currentPage === 1}
            aria-label="이전 페이지"
          >
            <ChevronLeft size={18} />
          </button>
          {numbers.map((number) => (
            <button
              key={number}
              type="button"
              className={number === currentPage ? "support-page active" : "support-page"}
              onClick={() => goPage(number)}
              aria-current={number === currentPage ? "page" : undefined}
            >
              {number}
            </button>
          ))}
          <button
            type="button"
            className="support-page-arrow"
            onClick={() => goPage(currentPage + 1)}
            disabled={currentPage === totalPages}
            aria-label="다음 페이지"
          >
            <ChevronRight size={18} />
          </button>
        </nav>
      </>
    );
  }

  return (
    <div className="sub-page">
      <div className="sub-page-inner">
        <PageHero
          eyebrow="고객지원"
          title="공지사항"
          description={"생각한줄의 새 소식과 업데이트, 점검 안내를 알려 드려요."}
          memoText={"새 소식\n놓치지\n마세요"}
        />
        <div className="support-wrap">
          <SupportTabs active="notice" onNavigate={onNavigate} />
          <section className="panel support-card">{body}</section>
        </div>
      </div>
    </div>
  );
}

export default NoticePage;
