// =============================================================
// admin/AdminShared.jsx — 관리자 페이지의 모든 탭이 같이 쓰는 화면 부품
// -------------------------------------------------------------
// 예전에는 AdminPage.jsx 안에만 있어서 다른 파일로 만든 탭(학습 데이터·별점 평가)은
// 자기만의 "이전 / 1페이지 / 다음" 버튼, "표시할 항목이 없습니다." 문구를 따로 만들어 썼음
// → 탭마다 모양이 달라 보여서 여기로 빼고 모든 탭이 같은 부품을 쓰게 함
//
// 들어 있는 것
//   Pagination  : 페이지 번호  ‹ 1 2 [3] 4 5 ›  (전체 페이지 수를 알 때)
//   SimplePager : ‹ [3] ›  (서버가 "다음 페이지가 있는지"만 알려 줄 때, 같은 모양)
//   ListState   : 불러오는 중 / 실패(다시 불러오기) / 비어 있음 / 정상 목록
//   AdminChips  : [전체 | 정상 | 정지] 같은 작은 알약 버튼 묶음 (거르기·보기 전환용)
// 스타일은 전부 AdminPage.css의 admin-* 클래스
// =============================================================

import { ChevronLeft, ChevronRight, Loader2, RefreshCw, ShieldCheck } from "lucide-react";
// 창만 스크롤하는 도구 (scrollIntoView를 쓰면 overflow: hidden 상자 안 내용이 밀려 올라가는 문제가 있어서)
import scrollToElement from "../../utils/scrollToElement";

// =============================================================
// 페이지 번호 (페이지네이션)
// =============================================================
// page: 지금 페이지, totalPages: 전체 페이지 수, onChange: 번호를 누르면 그 번호로 실행, label: 화면 읽기용 이름
// 1페이지뿐이어도 항상 보여줌 (‹ 1 › — 화살표는 둘 다 흐리게 막힘)
export function Pagination({ page, totalPages, onChange, label, disabled = false }) {
  // 보여줄 번호: 페이지가 많으면 지금 페이지 근처 최대 5개만 (예: 3 4 [5] 6 7)
  const start = Math.max(1, Math.min(page - 2, totalPages - 4));
  const end = Math.min(totalPages, start + 4);
  // Array.from({ length: n }, (_, i) => ...): n개짜리 배열을 만들면서 값 채우기
  const numbers = Array.from({ length: end - start + 1 }, (_, i) => start + i);

  // 페이지 이동: 번호를 바꾸고 탭 위치로 부드럽게 스크롤 (목록 맨 위부터 보이게)
  const go = (next) => {
    if (disabled || next < 1 || next > totalPages || next === page) return;
    onChange(next);
    scrollToElement(".admin-tabs");
  };

  return (
    // nav: "이동 메뉴" 태그 → 화면 읽기 프로그램이 페이지 이동 버튼 묶음으로 알아들음
    <nav className="admin-pagination" aria-label={label}>
      <button
        type="button"
        className="admin-page-arrow"
        onClick={() => go(page - 1)}
        disabled={disabled || page === 1}
        aria-label="이전 페이지"
      >
        <ChevronLeft size={18} />
      </button>
      {numbers.map((number) => (
        <button
          key={number}
          type="button"
          className={number === page ? "admin-page active" : "admin-page"}
          onClick={() => go(number)}
          disabled={disabled && number !== page}
          aria-current={number === page ? "page" : undefined} // 지금 보고 있는 페이지 표시
        >
          {number}
        </button>
      ))}
      <button
        type="button"
        className="admin-page-arrow"
        onClick={() => go(page + 1)}
        disabled={disabled || page === totalPages}
        aria-label="다음 페이지"
      >
        <ChevronRight size={18} />
      </button>
    </nav>
  );
}

// =============================================================
// 간단한 페이지 이동  ‹ [3] ›
// =============================================================
// 학습 데이터 후보 목록처럼 서버가 "전체 개수" 없이 50개씩만 주는 목록용
// (전체 페이지 수를 몰라서 번호 대신 지금 페이지만 보여 줌, 모양은 Pagination과 같음)
//  - page: 지금 페이지 (1부터)
//  - hasNext: 다음 페이지가 있는지 (받은 개수가 한 페이지를 꽉 채웠으면 있다고 봄)
//  - onChange: 이동할 페이지 번호를 넘겨줌
export function SimplePager({ page, hasNext, onChange, label, disabled = false }) {
  const go = (next) => {
    if (disabled || next < 1) return;
    onChange(next);
    scrollToElement(".admin-tabs");
  };

  return (
    <nav className="admin-pagination" aria-label={label}>
      <button
        type="button"
        className="admin-page-arrow"
        onClick={() => go(page - 1)}
        disabled={disabled || page === 1}
        aria-label="이전 페이지"
      >
        <ChevronLeft size={18} />
      </button>
      <span className="admin-page active" aria-current="page">
        {page}
      </span>
      <button
        type="button"
        className="admin-page-arrow"
        onClick={() => go(page + 1)}
        disabled={disabled || !hasNext}
        aria-label="다음 페이지"
      >
        <ChevronRight size={18} />
      </button>
    </nav>
  );
}

// =============================================================
// 불러오는 중 / 실패 / 비어 있음 / 목록 보여주기
// =============================================================
// children: 정상일 때 보여줄 목록 (부모가 태그 사이에 넣은 내용)
export function ListState({ loading, error, empty, emptyText, onRetry, children }) {
  if (loading) {
    return (
      <p className="admin-state">
        <Loader2 size={18} className="spin" /> 불러오는 중이에요...
      </p>
    );
  }
  if (error) {
    return (
      <div className="admin-state">
        <p>{error}</p>
        <button type="button" className="admin-secondary small" onClick={onRetry}>
          <RefreshCw size={14} /> 다시 불러오기
        </button>
      </div>
    );
  }
  if (empty) {
    return (
      <p className="admin-state">
        <ShieldCheck size={18} /> {emptyText}
      </p>
    );
  }
  return children;
}

// =============================================================
// 작은 알약 버튼 묶음  [전체 | 정상 | 정지]
// =============================================================
//  - items: [{ key, label }, ...] 버튼 목록
//  - value: 지금 고른 key / onChange: 다른 버튼을 누르면 그 key를 넘겨줌
//  - label: 화면 읽기 프로그램용 묶음 이름 (예: "검토 상태")
//  - title: 버튼 앞에 보일 작은 제목 (예: "별점") — 없으면 안 보임
//  - disabled: 서버에 요청 중일 때 막기
export function AdminChips({ items, value, onChange, label, title, disabled = false }) {
  return (
    <div className="admin-chips" role="group" aria-label={label}>
      {title && <span className="admin-chips-title">{title}</span>}
      {items.map((item) => (
        <button
          key={item.key}
          type="button"
          className={value === item.key ? "admin-chip active" : "admin-chip"}
          aria-pressed={value === item.key}
          disabled={disabled}
          // 이미 고른 버튼을 또 누르면 아무 일도 안 함 (목록을 괜히 다시 불러오지 않게)
          onClick={() => value !== item.key && onChange(item.key)}
        >
          {item.label}
        </button>
      ))}
    </div>
  );
}
