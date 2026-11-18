// =============================================================
// admin/TrainingManager.jsx — 관리자 페이지 "학습 데이터" 탭
// -------------------------------------------------------------
// AI(Qwen) 학습에 쓸 글을 사람이 직접 검토하고, 데이터셋을 만들고, 학습 결과를 기록하는 곳
//   [후보 검토]      사용자가 학습 동의하고 낸 글을 하나씩 보고 승인 / 제외
//   [데이터셋]       승인한 글을 모아 학습·검증·테스트용 파일(ZIP)로 만들기 + 내려받기
//   [학습 실험 기록] 실제로 학습을 돌린 뒤 결과(손실값 등)를 남기기
//
// ★ 화면 모양은 다른 관리자 탭(퀴즈·회원·랭킹…)과 똑같이 맞춤
//   - 버튼·표·입력칸·안내 문구: AdminPage.css의 admin-* 클래스
//   - 페이지 이동·불러오는 중 표시: AdminShared.jsx (다른 탭과 같은 부품)
//   - 승인/제외 확인: 다른 탭과 같은 ConfirmModal (예전엔 브라우저 기본 확인창이었음)
//   - 날짜: "2026.11.18 14:05" (adminFormat.js)
// ★ 서버와 주고받는 내용(주소·보내는 값·승인 조건)은 예전과 똑같음 → api/trainingAdmin.js
// =============================================================

import { useEffect, useState } from "react";
// RefreshCw: 새로고침, Eye: 상세 보기, X: 닫기, Plus: 등록, Download: ZIP 내려받기
// PackagePlus: 데이터셋 만들기, CheckCircle2: 성공 안내, Loader2: 저장 중 빙글빙글
import { RefreshCw, Eye, X, Plus, Download, PackagePlus, CheckCircle2, Loader2 } from "lucide-react";
import { adminRequest, downloadDataset } from "../../api/trainingAdmin";
import ConfirmModal from "../../components/ConfirmModal";
import { AdminChips, ListState, SimplePager } from "./AdminShared";
import { formatDateTime } from "./adminFormat";
// 창만 스크롤하는 도구 (상세가 열리면 그 위치로 내려 주려고)
import scrollToElement from "../../utils/scrollToElement";

// 검토 상태 이름 (서버 값 → 화면 글자)
const labels = { pending: "검토 대기", approved: "승인", rejected: "제외", withdrawn: "동의 철회" };
// 검토 상태 배지 색 (AdminPage.css의 admin-badge 색 이름)
const statusBadge = { pending: "me", approved: "active", rejected: "suspended", withdrawn: "suspended" };

// 승인 전에 관리자가 꼭 확인해야 하는 항목 (전부 체크해야 승인 버튼이 눌림)
const checks = {
  facts_checked: "주체·시간·부정 표현과 사실을 확인했습니다.",
  quality_checked: "과제 형식·분량·맞춤법·반복을 확인했습니다.",
  privacy_checked: "이름·연락처 등 개인정보가 없습니다.",
  author_confirmed: "작성자 본인의 글과 이용 권한을 확인했습니다.",
  context_confirmed: "입력 자료만으로 이 글을 작성할 수 있습니다.",
};

// 위쪽 [후보 검토 | 데이터셋 | 학습 실험 기록] 버튼
const VIEWS = [
  { key: "candidates", label: "후보 검토" },
  { key: "exports", label: "데이터셋" },
  { key: "runs", label: "학습 실험 기록" },
];

// [검토 대기 | 승인 | 제외 | 동의 철회] 거르기 버튼 (labels를 버튼 목록 모양으로 바꿈)
const STATUS_FILTERS = Object.entries(labels).map(([key, label]) => ({ key, label }));

// 후보 목록은 서버가 한 번에 50개씩 줌 (offset = 몇 번째부터)
const CANDIDATE_PAGE_SIZE = 50;

// 학습 실험 등록 폼의 처음 값
const emptyRunForm = () => ({
  export_id: "",
  base_model: "Qwen/Qwen3.5-2B",
  epochs: "",
  learning_rate: "",
  before_loss: "",
  after_loss: "",
  adapter_reference: "",
  note: "",
});

// 목록이 비었을 때 보기별 안내 문구
const EMPTY_TEXT = {
  candidates: "이 상태의 후보 글이 없어요.",
  exports: "아직 만든 데이터셋이 없어요.",
  runs: "아직 기록한 학습 실험이 없어요.",
};

// props
//  - token: 관리자 로그인 토큰 (서버 요청에 같이 보냄)
//  - onSessionExpired: 로그인이 풀렸을 때(401) App에 알리는 함수
export default function TrainingManager({ token, onSessionExpired }) {
  // ----- 무엇을 보고 있는지 -----
  const [view, setView] = useState("candidates"); // 보기: candidates / exports / runs
  const [status, setStatus] = useState("pending"); // 후보 검토의 상태 거르기
  const [offset, setOffset] = useState(0); // 후보 목록 몇 번째부터 (페이지)

  // ----- 서버에서 받은 것 -----
  const [rows, setRows] = useState([]); // 지금 보기의 목록
  const [selected, setSelected] = useState(null); // 상세로 열어 본 후보 (없으면 null)
  const [history, setHistory] = useState([]); // 그 후보의 검토 이력

  // ----- 상세 검토 입력값 -----
  const [form, setForm] = useState({}); // 체크 항목 + 사실 자료 + 메모 + 합성 글 여부
  const [real, setReal] = useState(false); // "실제 작성자가 제출한 글" 확인

  // ----- 상태 표시 -----
  const [loading, setLoading] = useState(false); // 목록 불러오는 중
  const [busy, setBusy] = useState(false); // 저장·생성 등 요청 처리 중 (버튼 막기)
  const [error, setError] = useState(""); // 실패 문구
  const [notice, setNotice] = useState(""); // 성공 문구
  const [reload, setReload] = useState(0); // +1 하면 목록을 다시 불러옴

  // ----- 학습 실험 등록 폼 -----
  const [showRunForm, setShowRunForm] = useState(false);
  const [runForm, setRunForm] = useState(emptyRunForm);

  // 승인/제외 확인창 { decision: "approved" | "rejected", busy, error } (null이면 안 보임)
  const [confirm, setConfirm] = useState(null);

  function changeRunField(key, value) {
    setRunForm((previous) => ({ ...previous, [key]: value }));
  }

  // 실패 처리: 문구를 보여주고, 로그인이 풀렸으면(401) App에 알림
  function fail(e) {
    setError(e.message);
    if (e.status === 401) onSessionExpired?.();
  }

  // ----- 목록 불러오기 (보기·상태·페이지가 바뀌거나 새로고침할 때) -----
  useEffect(() => {
    let active = true; // 응답이 오기 전에 다른 보기로 바꾸면 이전 응답은 무시
    setLoading(true);
    setError("");
    setRows([]);
    setSelected(null);
    const path =
      view === "candidates"
        ? `/api/training/candidates?status=${status}&offset=${offset}`
        : `/api/training/${view}`;
    adminRequest(token, path)
      .then((data) => {
        if (active) setRows(data);
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
    // fail은 매번 새로 만들어지는 함수라 넣지 않음 (넣으면 목록을 계속 다시 불러옴)
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [token, view, status, offset, reload]);

  // ----- 상세를 열면 그 후보의 검토 이력 불러오기 -----
  useEffect(() => {
    let active = true;
    setHistory([]);
    if (selected)
      adminRequest(token, `/api/training/candidates/${selected.id}/reviews`)
        .then((data) => {
          if (active) setHistory(data);
        })
        .catch((e) => {
          if (active) fail(e);
        });
    return () => {
      active = false;
    };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [token, selected]);

  // 버튼 동작 공통: 처리 중 표시 → 실행 → 실패하면 문구
  async function act(fn) {
    setBusy(true);
    setError("");
    setNotice("");
    try {
      await fn();
    } catch (e) {
      fail(e);
    } finally {
      setBusy(false);
    }
  }

  // 보기 바꾸기 [후보 검토 | 데이터셋 | 학습 실험 기록]
  function changeView(key) {
    setRows([]);
    setSelected(null);
    setLoading(true);
    setView(key);
    setOffset(0);
    setNotice("");
  }

  // 후보 상세 열기 (검토 입력값은 처음부터)
  function select(row) {
    setSelected(row);
    setForm({ note: "", training_context: row.training_context || "", synthetic: row.synthetic });
    setReal(false);
  }

  // 상세가 열리면 그 위치로 스크롤 (상세는 목록 아래에 나와서, 안 내려 주면 열린 줄 모름)
  useEffect(() => {
    if (selected) {
      // 화면이 다 그려진 다음에 스크롤 (바로 하면 아직 상세 상자가 없음)
      const timer = setTimeout(() => scrollToElement(".admin-detail"), 0);
      return () => clearTimeout(timer);
    }
  }, [selected]);

  // ----- 승인 / 제외 저장 (확인창에서 "확인"을 눌렀을 때) -----
  async function review() {
    const { decision } = confirm;
    setConfirm((prev) => ({ ...prev, busy: true, error: "" }));
    try {
      await adminRequest(token, `/api/training/candidates/${selected.id}/review`, {
        ...form,
        decision,
        expected_revision: selected.revision, // 그사이 다른 사람이 고쳤으면 서버가 거절
      });
    } catch (e) {
      if (e.status === 401) onSessionExpired?.();
      setConfirm((prev) => ({ ...prev, busy: false, error: e.message }));
      return;
    }
    setConfirm(null);
    setNotice("검토 결과를 저장했어요.");
    setReload((x) => x + 1);
  }

  // 승인 버튼이 눌리는 조건 (예전과 똑같음)
  //  - 작성자 동의가 있고, 합성(AI) 글이 아니고, "실제 작성자" 확인 + 체크 항목 전부
  //  - 자기소개서는 "작성자가 확인한 사실 자료"까지 적어야 함
  const approvable =
    selected?.consent &&
    !form.synthetic &&
    real &&
    Object.keys(checks).every((k) => form[k]) &&
    (selected?.source?.type_label !== "자기소개서" || form.training_context?.trim());

  // ----- 학습 실험 기록 저장 -----
  async function saveRun(event) {
    event.preventDefault(); // form 제출 시 페이지가 새로고침되는 기본 동작 막기

    await act(async () => {
      const exportId = runForm.export_id.trim();
      const model = runForm.base_model.trim();

      // 데이터셋 ID는 32자리 영문·숫자 (데이터셋 목록에 보이는 값)
      if (!/^[a-f0-9]{32}$/i.test(exportId)) {
        throw new Error("데이터셋 화면에 표시된 32자리 ID를 입력해 주세요.");
      }

      if (!model) {
        throw new Error("모델명을 입력해 주세요.");
      }

      const parameters = {}; // 학습 설정 (에포크·학습률)
      const metrics = {}; // 결과 숫자 (학습 전·후 손실)

      // [입력칸 이름, 담을 곳, 서버에 보낼 이름, 화면 이름]
      const fields = [
        ["epochs", parameters, "epochs", "에포크"],
        ["learning_rate", parameters, "learning_rate", "학습률"],
        ["before_loss", metrics, "eval_loss_before", "학습 전 검증 손실"],
        ["after_loss", metrics, "eval_loss_after", "학습 후 검증 손실"],
      ];

      for (const [field, destination, key, label] of fields) {
        const raw = runForm[field].trim();
        if (!raw) continue; // 비워 둔 칸은 안 보냄

        const value = Number(raw);

        if (!Number.isFinite(value) || value < 0) {
          throw new Error(`${label}에 올바른 숫자를 입력해 주세요.`);
        }

        if (field === "epochs" && (!Number.isInteger(value) || value < 1)) {
          throw new Error("에포크는 1 이상의 정수로 입력해 주세요.");
        }

        if (field === "learning_rate" && value <= 0) {
          throw new Error("학습률은 0보다 커야 합니다.");
        }

        destination[key] = value;
      }

      const result = await adminRequest(token, "/api/training/runs", {
        export_id: exportId,
        base_model: model,
        parameters,
        metrics,
        adapter_reference: runForm.adapter_reference.trim(),
        note: runForm.note.trim(),
      });

      setNotice(`학습 실험 #${result.id} 기록을 저장했어요.`);
      setShowRunForm(false);
      setRunForm(emptyRunForm());
      setReload((value) => value + 1);
    });
  }

  // ----- 승인한 글로 데이터셋 만들기 -----
  const createExport = () =>
    act(async () => {
      const data = await adminRequest(token, "/api/training/exports", {});
      setNotice(
        `데이터셋을 만들었어요: 학습 ${data.counts.train} / 검증 ${data.counts.valid} / 테스트 ${data.counts.test}건. (실제 학습은 실행하지 않았어요)`
      );
      setReload((x) => x + 1);
    });

  return (
    <>
      {/* ----- 위쪽 도구 줄: 보기 전환 + 새로고침 + (보기별) 주요 버튼 ----- */}
      <div className="admin-toolbar">
        <AdminChips items={VIEWS} value={view} onChange={changeView} label="학습 데이터 보기" disabled={busy} />
        <div className="admin-toolbar-actions">
          <button
            type="button"
            className="admin-secondary"
            disabled={busy || loading}
            onClick={() => setReload((x) => x + 1)}
          >
            <RefreshCw size={15} /> 새로고침
          </button>
          {view === "exports" && (
            <button type="button" className="admin-primary" disabled={busy} onClick={createExport}>
              <PackagePlus size={16} /> 데이터셋 만들기
            </button>
          )}
          {view === "runs" && (
            <button
              type="button"
              className="admin-primary"
              disabled={busy || showRunForm}
              onClick={() => setShowRunForm(true)}
            >
              <Plus size={16} /> 학습 실험 등록
            </button>
          )}
        </div>
      </div>

      {/* 후보 검토일 때만: 검토 상태로 거르기 */}
      {view === "candidates" && (
        <div className="admin-subfilters">
          <AdminChips
            items={STATUS_FILTERS}
            value={status}
            title="검토 상태"
            label="검토 상태로 거르기"
            disabled={busy}
            onChange={(key) => {
              setStatus(key);
              setOffset(0);
            }}
          />
        </div>
      )}

      {error && (
        <p className="admin-error admin-error-box" role="alert">
          {error}
        </p>
      )}
      {notice && (
        <p className="admin-notice" role="status">
          <CheckCircle2 size={16} /> {notice}
        </p>
      )}

      {/* ----- 학습 실험 등록 폼 (학습 실험 기록 보기 + "등록"을 눌렀을 때) ----- */}
      {view === "runs" && showRunForm && (
        <form className="admin-form" onSubmit={saveRun}>
          <div className="admin-form-head">
            <strong>학습 실험 등록</strong>
            <button
              type="button"
              className="admin-icon-button"
              onClick={() => setShowRunForm(false)}
              aria-label="닫기"
              disabled={busy}
            >
              <X size={18} />
            </button>
          </div>
          <p className="admin-hint">완료한 학습 결과를 기록해요. 실제로 사용한 데이터셋 ID를 입력해 주세요.</p>

          {/* fieldset disabled: 저장하는 동안 안의 입력칸을 한꺼번에 막음 */}
          <fieldset className="admin-form-grid" disabled={busy}>
            <label className="admin-field wide">
              <span className="admin-label">데이터셋 ID *</span>
              <input
                className="admin-input"
                required
                minLength={32}
                maxLength={32}
                placeholder="데이터셋 목록에 보이는 32자리 ID"
                value={runForm.export_id}
                onChange={(e) => changeRunField("export_id", e.target.value)}
              />
            </label>

            <label className="admin-field wide">
              <span className="admin-label">기본 모델 *</span>
              <input
                className="admin-input"
                required
                maxLength={200}
                value={runForm.base_model}
                onChange={(e) => changeRunField("base_model", e.target.value)}
              />
            </label>

            {/* 숫자 칸 4개는 두 칸씩 나란히 */}
            {[
              ["epochs", "에포크", "3"],
              ["learning_rate", "학습률", "0.00002"],
              ["before_loss", "학습 전 검증 손실", ""],
              ["after_loss", "학습 후 검증 손실", ""],
            ].map(([key, label, placeholder]) => (
              <label className="admin-field" key={key}>
                <span className="admin-label">{label}</span>
                <input
                  className="admin-input"
                  type="number"
                  min={key === "epochs" ? "1" : "0"}
                  step={key === "epochs" ? "1" : "any"}
                  placeholder={placeholder}
                  value={runForm[key]}
                  onChange={(e) => changeRunField(key, e.target.value)}
                />
              </label>
            ))}

            <label className="admin-field wide">
              <span className="admin-label">어댑터 저장 위치</span>
              <input
                className="admin-input"
                maxLength={500}
                value={runForm.adapter_reference}
                onChange={(e) => changeRunField("adapter_reference", e.target.value)}
              />
            </label>

            <label className="admin-field wide">
              <span className="admin-label">응답 품질·결과 메모</span>
              <textarea
                maxLength={1000}
                rows={3}
                placeholder="사실 유지, 분량, 문체, 반복 여부 등을 기록하세요."
                value={runForm.note}
                onChange={(e) => changeRunField("note", e.target.value)}
              />
            </label>
          </fieldset>

          <div className="admin-form-actions">
            <button type="button" className="admin-secondary" onClick={() => setShowRunForm(false)} disabled={busy}>
              취소
            </button>
            <button type="submit" className="admin-primary" disabled={busy}>
              {busy ? (
                <>
                  <Loader2 size={16} className="spin" /> 저장하는 중...
                </>
              ) : (
                "실험 기록 저장"
              )}
            </button>
          </div>
        </form>
      )}

      {/* ----- 목록 (불러오는 중 / 비어 있음 / 목록) ----- */}
      <ListState loading={loading} empty={!rows.length} emptyText={EMPTY_TEXT[view]}>
        {/* 후보 검토: 표 */}
        {view === "candidates" && (
          <>
            <p className="admin-count">
              {labels[status]} {rows.length}건{rows.length === CANDIDATE_PAGE_SIZE ? " (다음 페이지 있음)" : ""}
            </p>
            <div className="admin-table-wrap">
              <table className="admin-table">
                <thead>
                  <tr>
                    <th scope="col">ID</th>
                    <th scope="col">유형·단원</th>
                    <th scope="col">AI 점수</th>
                    <th scope="col">제출일</th>
                    <th scope="col">
                      <span className="sr-only">검토</span>
                    </th>
                  </tr>
                </thead>
                <tbody>
                  {rows.map((row) => (
                    // 지금 상세로 열어 둔 줄은 색으로 표시
                    <tr key={row.id} className={selected?.id === row.id ? "selected" : undefined}>
                      <td className="num">{row.id}</td>
                      <td className="wrap">
                        {row.source?.type_label || "-"} · {row.source?.unit_title || "철회된 글"}
                      </td>
                      <td className="num strong">{row.score}점</td>
                      <td className="num">{formatDateTime(row.created_at)}</td>
                      <td className="right">
                        <button
                          type="button"
                          className="admin-secondary small"
                          disabled={busy}
                          onClick={() => select(row)}
                        >
                          <Eye size={14} /> 상세 보기
                        </button>
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          </>
        )}

        {/* 데이터셋: 카드 목록 */}
        {view === "exports" && (
          <>
            <p className="admin-count">최근 100개까지 보여줘요 · 승인한 글로만 만들어져요</p>
            <ul className="admin-list">
              {rows.map((row) => {
                const counts = row.manifest.counts || {};
                // 상태: 무효화 / 분할 부족 / 완료
                const state = row.revoked
                  ? { badge: "suspended", text: "무효화됨" }
                  : !row.manifest.all_splits_nonempty
                    ? { badge: "me", text: "분할 부족 — 학습 준비 전" }
                    : { badge: "active", text: "내보내기 완료 — 별도 품질 검증 필요" };
                return (
                  <li key={row.id} className="admin-item">
                    <div className="admin-item-main">
                      <p className="admin-item-title">
                        <span className={`admin-badge ${state.badge}`}>{state.text}</span>
                      </p>
                      <p className="admin-mono">{row.id}</p>
                      <p className="admin-meta">
                        {formatDateTime(row.created_at)} · 학습 {counts.train || 0} / 검증 {counts.valid || 0} / 테스트{" "}
                        {counts.test || 0}
                      </p>
                    </div>
                    <div className="admin-item-actions">
                      <button
                        type="button"
                        className="admin-secondary small"
                        disabled={busy || row.revoked}
                        onClick={() => act(() => downloadDataset(token, row.id))}
                      >
                        <Download size={14} /> ZIP 다운로드
                      </button>
                    </div>
                  </li>
                );
              })}
            </ul>
          </>
        )}

        {/* 학습 실험 기록: 카드 목록 */}
        {view === "runs" && (
          <>
            <p className="admin-count">최근 100개 실험 기록이에요</p>
            <ul className="admin-list">
              {rows.map((row) => (
                <li key={row.id} className="admin-item">
                  <div className="admin-item-main">
                    <p className="admin-item-title">
                      <strong>실험 #{row.id}</strong>
                    </p>
                    <p className="admin-meta">{formatDateTime(row.created_at)} 등록</p>
                    {/* 서버가 저장한 설정·결과를 그대로 보여줌 (JSON.stringify(값, null, 2): 보기 좋게 줄 맞춤) */}
                    <pre className="admin-pre">{JSON.stringify(row.details, null, 2)}</pre>
                  </div>
                </li>
              ))}
            </ul>
          </>
        )}
      </ListState>

      {/* 후보 목록 페이지 이동 (50개씩) */}
      {view === "candidates" && !loading && (rows.length > 0 || offset > 0) && (
        <SimplePager
          page={Math.floor(offset / CANDIDATE_PAGE_SIZE) + 1}
          hasNext={rows.length === CANDIDATE_PAGE_SIZE}
          disabled={busy}
          label="후보 목록 페이지"
          onChange={(page) => setOffset((page - 1) * CANDIDATE_PAGE_SIZE)}
        />
      )}

      {/* ----- 후보 상세 + 검토 ----- */}
      {selected && view === "candidates" && (
        <section className="admin-form admin-detail" aria-label={`후보 #${selected.id} 상세`}>
          <div className="admin-form-head">
            <strong>
              후보 #{selected.id}{" "}
              <span className={`admin-badge ${statusBadge[selected.status] || "me"}`}>{labels[selected.status]}</span>
            </strong>
            <button type="button" className="admin-icon-button" onClick={() => setSelected(null)} aria-label="상세 닫기">
              <X size={18} />
            </button>
          </div>
          <p className="admin-meta">
            동의 {selected.consent ? "있음" : "철회"} · AI 점수 {selected.score}점 · 버전 {selected.revision}
          </p>

          <div className="admin-field">
            <span className="admin-label">과제</span>
            <pre className="admin-pre">{selected.source?.task || "-"}</pre>
          </div>
          <div className="admin-field">
            <span className="admin-label">제공 자료</span>
            <pre className="admin-pre">{selected.source?.material || "-"}</pre>
          </div>
          <div className="admin-field">
            <span className="admin-label">채점 기준</span>
            <ul className="admin-bullets">
              {selected.source?.rules?.map((r, i) => (
                <li key={i}>{r}</li>
              ))}
            </ul>
          </div>
          <div className="admin-field">
            <span className="admin-label">제출 글</span>
            <pre className="admin-pre">{selected.answer || "철회로 삭제된 글입니다."}</pre>
          </div>
          <details className="admin-details">
            <summary>AI 채점 상세</summary>
            <pre className="admin-pre">{JSON.stringify(selected.assessment, null, 2)}</pre>
          </details>

          {/* 관리자 검토 (동의 철회된 글은 검토할 수 없음) */}
          {selected.status !== "withdrawn" && (
            <fieldset className="admin-fieldset" disabled={busy}>
              <legend className="admin-label">관리자 검토</legend>
              {Object.entries(checks).map(([k, label]) => (
                <label className="admin-check" key={k}>
                  <input type="checkbox" checked={!!form[k]} onChange={(e) => setForm({ ...form, [k]: e.target.checked })} />
                  <span>
                    <strong>{label}</strong>
                  </span>
                </label>
              ))}
              <label className="admin-check">
                <input
                  type="checkbox"
                  checked={!!form.synthetic}
                  onChange={(e) => setForm({ ...form, synthetic: e.target.checked })}
                />
                <span>
                  <strong>AI 작성·합성·데모 테스트 글입니다.</strong>
                  <small>체크하면 승인할 수 없어요.</small>
                </span>
              </label>
              <label className="admin-check">
                <input type="checkbox" checked={real} onChange={(e) => setReal(e.target.checked)} />
                <span>
                  <strong>실제 작성자가 제출한 글임을 확인했습니다.</strong>
                </span>
              </label>

              <label className="admin-field">
                <span className="admin-label">작성자가 확인한 사실 자료 (자기소개서 필수)</span>
                <textarea
                  maxLength={6000}
                  rows={4}
                  value={form.training_context || ""}
                  onChange={(e) => setForm({ ...form, training_context: e.target.value })}
                />
              </label>
              <label className="admin-field">
                <span className="admin-label">검토 메모 (선택)</span>
                <textarea
                  maxLength={1000}
                  rows={3}
                  value={form.note || ""}
                  onChange={(e) => setForm({ ...form, note: e.target.value })}
                />
              </label>

              {/* 승인이 막혀 있으면 이유를 알려 줌 */}
              {!approvable && (
                <p className="admin-hint">
                  승인하려면 위 확인 항목을 모두 체크하고, 합성 글이 아니어야 해요. (자기소개서는 사실 자료도 필요해요)
                </p>
              )}
              <div className="admin-form-actions">
                <button
                  type="button"
                  className="admin-danger"
                  onClick={() => setConfirm({ decision: "rejected", busy: false, error: "" })}
                >
                  제외
                </button>
                <button
                  type="button"
                  className="admin-primary"
                  disabled={!approvable}
                  onClick={() => setConfirm({ decision: "approved", busy: false, error: "" })}
                >
                  승인
                </button>
              </div>
            </fieldset>
          )}

          <div className="admin-field">
            <span className="admin-label">검토 이력</span>
            {history.length ? (
              <ul className="admin-bullets">
                {history.map((r, i) => (
                  <li key={i}>
                    {formatDateTime(r.at)} · {labels[r.event.decision] || r.event.action || "검토"}
                    {r.event.note && ` · ${r.event.note}`}
                  </li>
                ))}
              </ul>
            ) : (
              <p className="admin-muted">검토 이력이 없어요.</p>
            )}
          </div>
        </section>
      )}

      {/* 승인 / 제외 확인창 (다른 관리자 탭과 같은 모양) */}
      {confirm && (
        <ConfirmModal
          danger={confirm.decision === "rejected"}
          title={confirm.decision === "approved" ? "이 글을 학습 후보로 승인할까요?" : "이 글을 학습 대상에서 제외할까요?"}
          message={`후보 #${selected?.id} · ${selected?.source?.type_label || "-"} · ${
            selected?.source?.unit_title || "철회된 글"
          }`}
          confirmLabel={confirm.decision === "approved" ? "승인하기" : "제외하기"}
          busy={confirm.busy}
          error={confirm.error}
          onCancel={() => setConfirm(null)}
          onConfirm={review}
        />
      )}
    </>
  );
}
