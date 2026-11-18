// =============================================================
// admin/RatingsManager.jsx — 관리자 페이지 "별점 평가" 탭
// -------------------------------------------------------------
// 글쓰기 화면에서 사용자가 AI 초안·AI 피드백에 준 별점(1~5점)과 의견을 모아 보는 곳
//   - 위: 평가 종류 / 별점으로 거르기
//   - 요약: 조건에 맞는 평가 수, 평균 별점, 낮은 평가(1~2점) 수 + 점수별 막대
//   - 표: 평가 하나씩 → "보기"를 누르면 아래에 상세(요청 원문, AI 결과)가 열림
//
// ★ 화면 모양은 다른 관리자 탭과 똑같이 맞춤 (admin-* 클래스 + AdminShared.jsx 부품)
// ★ 서버와 주고받는 내용은 예전과 똑같음 (GET /api/admin/ratings, /api/admin/ratings/{id})
// =============================================================

import { useEffect, useState } from "react";
// RefreshCw: 새로고침, Eye: 보기, X: 닫기, Star: 별점, Loader2: 상세 불러오는 중
import { RefreshCw, Eye, X, Star, Loader2 } from "lucide-react";
import { adminRequest } from "../../api/trainingAdmin";
import { AdminChips, ListState, Pagination } from "./AdminShared";
import { formatDateTime } from "./adminFormat";
// 창만 스크롤하는 도구 (상세가 열리면 그 위치로 내려 주려고)
import scrollToElement from "../../utils/scrollToElement";

// 평가 종류 이름 (서버 값 → 화면 글자)
const kindLabel = {
  draft: "AI 초안",
  feedback: "AI 피드백",
};

// 거르기 버튼 목록 (key ""는 "전체" = 거르지 않음)
const KIND_FILTERS = [
  { key: "", label: "전체" },
  { key: "draft", label: "AI 초안" },
  { key: "feedback", label: "AI 피드백" },
];
const STAR_FILTERS = [
  { key: "", label: "전체" },
  ...[5, 4, 3, 2, 1].map((s) => ({ key: String(s), label: `${s}점` })),
];

// 서버가 한 번에 주는 평가 수 (offset = 몇 번째부터)
const RATING_PAGE_SIZE = 20;

// props
//  - token: 관리자 로그인 토큰
//  - onSessionExpired: 로그인이 풀렸을 때(401) App에 알리는 함수
export default function RatingsManager({ token, onSessionExpired }) {
  const [filters, setFilters] = useState({ kind: "", stars: "" }); // 평가 종류·별점 거르기
  const [offset, setOffset] = useState(0); // 몇 번째 평가부터 (페이지)
  const [reload, setReload] = useState(0); // +1 하면 다시 불러옴
  const [data, setData] = useState(null); // 서버 응답 { total, average, distribution, items }
  const [selected, setSelected] = useState(null); // 상세로 연 평가 id (없으면 null)
  const [detail, setDetail] = useState(null); // 그 평가의 상세 내용
  const [error, setError] = useState("");
  const [loading, setLoading] = useState(true); // 처음 화면을 열면 바로 불러오니까 true로 시작

  // 실패 처리: 문구를 보여주고, 로그인이 풀렸으면(401) App에 알림
  function fail(e) {
    setError(e.message);
    if (e.status === 401) onSessionExpired?.();
  }

  // ----- 다시 불러오기 전에 화면 비우기 -----
  // (거르기·페이지·새로고침 버튼을 누를 때 부름 → 아래 useEffect가 새로 불러옴)
  // useEffect 안에서 바로 화면 상태를 바꾸면 한 번 더 그려지는 낭비가 생겨서, 버튼 쪽에서 미리 바꿈
  function startLoading() {
    setLoading(true);
    setError("");
    setSelected(null);
    setData(null);
  }

  // ----- 목록 + 요약 불러오기 (거르기·페이지가 바뀌거나 새로고침할 때) -----
  useEffect(() => {
    let active = true;
    // 빈 값("" = 전체)은 빼고 주소 뒤에 붙임 (예: ?kind=draft&offset=0)
    const q = new URLSearchParams({
      ...Object.fromEntries(Object.entries(filters).filter(([, v]) => v !== "")),
      offset,
    });
    adminRequest(token, `/api/admin/ratings?${q}`)
      .then((r) => {
        if (active) setData(r);
      })
      .catch((e) => {
        if (active) fail(e);
      })
      .finally(() => {
        if (active) setLoading(false);
      });
    return () => {
      active = false;
    };
    // fail은 매번 새로 만들어지는 함수라 넣지 않음 (넣으면 계속 다시 불러옴)
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [token, filters, offset, reload]);

  // ----- "보기" 버튼: 상세 열기 (이전 상세는 비우고) + 그 위치로 스크롤 -----
  function openDetail(id) {
    setSelected(id);
    setDetail(null);
    // 화면이 다 그려진 다음에 스크롤 (상세는 표 아래에 나와서, 안 내려 주면 열린 줄 모름)
    setTimeout(() => scrollToElement(".admin-detail"), 0);
  }

  // ----- 상세를 열면 그 평가의 상세 내용 불러오기 -----
  useEffect(() => {
    let active = true;
    if (selected) {
      adminRequest(token, `/api/admin/ratings/${encodeURIComponent(selected)}`)
        .then((r) => {
          if (active) setDetail(r);
        })
        .catch((e) => {
          if (active) fail(e);
        });
    }
    return () => {
      active = false;
    };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [token, selected]);

  // 거르기 바꾸기 → 1페이지부터
  function filter(key, value) {
    startLoading();
    setFilters({ ...filters, [key]: value });
    setOffset(0);
  }

  // 새로고침 (같은 조건으로 다시 불러오기)
  function refresh() {
    startLoading();
    setReload((x) => x + 1);
  }

  // 페이지 번호 계산 (서버는 offset, 화면은 1, 2, 3 …)
  const page = Math.floor(offset / RATING_PAGE_SIZE) + 1;
  const totalPages = data ? Math.max(1, Math.ceil(data.total / RATING_PAGE_SIZE)) : 1;
  // 점수별 막대 길이 기준 (가장 많은 점수 = 꽉 찬 막대, 0건이면 1로 나눠서 0%)
  const maxCount = data ? Math.max(1, ...[1, 2, 3, 4, 5].map((s) => data.distribution[s] || 0)) : 1;

  return (
    <>
      {/* ----- 위쪽 도구 줄: 평가 종류 + 새로고침 ----- */}
      <div className="admin-toolbar">
        <AdminChips
          items={KIND_FILTERS}
          value={filters.kind}
          onChange={(key) => filter("kind", key)}
          label="평가 종류로 거르기"
          disabled={loading}
        />
        <div className="admin-toolbar-actions">
          <button type="button" className="admin-secondary" disabled={loading} onClick={refresh}>
            <RefreshCw size={15} /> 새로고침
          </button>
        </div>
      </div>
      <div className="admin-subfilters">
        <AdminChips
          items={STAR_FILTERS}
          value={filters.stars}
          onChange={(key) => filter("stars", key)}
          title="별점"
          label="별점으로 거르기"
          disabled={loading}
        />
      </div>

      <ListState
        loading={loading}
        error={error && !data ? error : ""} // 목록을 못 불러왔을 때만 (상세 실패는 아래 상세 칸에)
        onRetry={refresh}
      >
        {data && (
          <>
            {/* ----- 요약 카드 3개 ----- */}
            <div className="admin-stats">
              <div className="admin-stat">
                <span>조건에 맞는 평가</span>
                <strong>{data.total}건</strong>
              </div>
              <div className="admin-stat">
                <span>평균 별점</span>
                <strong>
                  {data.average ?? "-"} <small>/ 5</small>
                </strong>
              </div>
              <div className="admin-stat warn">
                <span>낮은 평가 (1~2점)</span>
                <strong>{(data.distribution["1"] || 0) + (data.distribution["2"] || 0)}건</strong>
              </div>
            </div>

            {/* ----- 점수별 막대 ----- */}
            <ul className="admin-bars" aria-label="현재 검색 조건의 별점 분포">
              {[5, 4, 3, 2, 1].map((s) => {
                const count = data.distribution[s] || 0;
                return (
                  <li key={s}>
                    <span className="admin-bars-label">
                      <Star size={13} /> {s}점
                    </span>
                    <span className="admin-bars-track" aria-hidden="true">
                      <span style={{ width: `${(count / maxCount) * 100}%` }} />
                    </span>
                    <span className="admin-bars-count">{count}건</span>
                  </li>
                );
              })}
            </ul>

            {/* ----- 평가 표 ----- */}
            {data.items.length === 0 ? (
              <ListState empty emptyText="조건에 맞는 평가가 없어요." />
            ) : (
              <div className="admin-table-wrap">
                <table className="admin-table">
                  <thead>
                    <tr>
                      <th scope="col">일시</th>
                      <th scope="col">평가 종류</th>
                      <th scope="col">별점</th>
                      <th scope="col">의견</th>
                      <th scope="col">
                        <span className="sr-only">상세</span>
                      </th>
                    </tr>
                  </thead>
                  <tbody>
                    {data.items.map((r) => (
                      <tr key={r.id} className={selected === r.id ? "selected" : undefined}>
                        <td className="num">{formatDateTime(r.created_at)}</td>
                        <td>
                          <span className="admin-badge admin">{kindLabel[r.kind] || r.kind}</span>
                        </td>
                        {/* 1~2점은 빨간 글자로 (낮은 평가 눈에 띄게) */}
                        <td className={r.rating <= 2 ? "num strong low" : "num strong"}>★ {r.rating}</td>
                        <td className="ellipsis" title={r.comment || ""}>
                          {r.comment || <span className="admin-muted">의견 없음</span>}
                        </td>
                        <td className="right">
                          <button type="button" className="admin-secondary small" onClick={() => openDetail(r.id)}>
                            <Eye size={14} /> 보기
                          </button>
                        </td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            )}

            <Pagination
              page={page}
              totalPages={totalPages}
              disabled={loading}
              label="별점 평가 페이지"
              onChange={(next) => {
                startLoading();
                setOffset((next - 1) * RATING_PAGE_SIZE);
              }}
            />
          </>
        )}
      </ListState>

      {/* ----- 평가 상세 ----- */}
      {selected && (
        <section className="admin-form admin-detail" aria-label="평가 상세">
          <div className="admin-form-head">
            <strong>평가 상세</strong>
            <button type="button" className="admin-icon-button" onClick={() => setSelected(null)} aria-label="상세 닫기">
              <X size={18} />
            </button>
          </div>
          {detail ? (
            <>
              <p className="admin-meta">
                ★ {detail.rating} / 5 · 문서 ID {detail.document_id || "-"}
              </p>
              <div className="admin-field">
                <span className="admin-label">사용자 의견</span>
                <pre className="admin-pre">{detail.comment || "의견 없음"}</pre>
              </div>
              <div className="admin-field">
                <span className="admin-label">요청 원문</span>
                <pre className="admin-pre">{detail.request_text || "저장된 내용 없음"}</pre>
              </div>
              <div className="admin-field">
                <span className="admin-label">평가한 AI 결과</span>
                <pre className="admin-pre">{detail.result_text || "저장된 내용 없음"}</pre>
              </div>
              <p className="admin-hint">
                원문·결과는 최대 2,000자까지만 저장돼요. 이 평가는 학습 동의를 뜻하지 않아요.
              </p>
            </>
          ) : error ? (
            <p className="admin-error" role="alert">
              {error}
            </p>
          ) : (
            <p className="admin-state">
              <Loader2 size={18} className="spin" /> 상세를 불러오는 중이에요...
            </p>
          )}
        </section>
      )}
    </>
  );
}
