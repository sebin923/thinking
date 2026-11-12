// =============================================================
// admin/LearnManager.jsx — 관리자 페이지 "학습 관리" 탭
// -------------------------------------------------------------
// 학습 단원의 개념(제목·요약·핵심 내용·예시·팁·글쓰기 할 일)과 O/X 문제를 고치는 곳
//  1) 글 유형(보고서·자기소개서·발표문) 고르기
//  2) 단원 고르기 (목록 상자)
//  3) 내용 고치기 → "저장하기"
//  - O/X 문제는 추가·삭제·정답(O/X) 바꾸기 가능
//  - "기본 내용으로 되돌리기": 고친 내용을 지우고 처음 내용(data/learn)으로
//
// ★ 지금은 백엔드가 없어서 고친 내용이 이 브라우저에만 저장됨 (api/learn.js)
//  → 다른 사람 컴퓨터에는 반영되지 않음. 백엔드 API가 생기면 api/learn.js만 바꾸면 모두에게 반영됨
// 스타일: AdminPage.css (admin-* 공통 + 맨 아래 "학습 관리" 부분)
// =============================================================

import { useEffect, useState } from "react";
// Plus: 문제 추가, Trash2: 문제 삭제, RotateCcw: 되돌리기, Save: 저장, Info: 안내, Loader2: 처리 중, CheckCircle2: 저장 완료
import { Plus, Trash2, RotateCcw, Save, Info, Loader2, CheckCircle2 } from "lucide-react";

import ConfirmModal from "../../components/ConfirmModal";
import { fetchLearnContent, saveLearnUnit, resetLearnUnit, fetchOxQuizzes } from "../../api/learn";

// 단원 → 입력 폼에 넣을 모양으로 바꾸기
// points(배열)는 textarea에서 고치기 쉽게 "한 줄에 하나" 글자로 바꿈
function toForm(unit) {
  return {
    title: unit.title || "",
    summary: unit.summary || "",
    pointsText: (unit.points || []).join("\n"),
    good: unit.good || "",
    bad: unit.bad || "",
    tip: unit.tip || "",
    task: unit.task || "",
    // 문제는 복사해서 씀 (원본을 직접 바꾸지 않게)
    quiz: (unit.quiz || []).map((item) => ({ q: item.q, a: item.a, e: item.e || "" })),
  };
}

// 입력 폼 → 저장할 단원 모양으로 되돌리기
function fromForm(id, form) {
  return {
    id,
    title: form.title.trim(),
    summary: form.summary.trim(),
    // 줄마다 나누고, 빈 줄은 버림
    points: form.pointsText
      .split("\n")
      .map((line) => line.trim())
      .filter(Boolean),
    good: form.good.trim(),
    bad: form.bad.trim(),
    tip: form.tip.trim(),
    task: form.task.trim(),
    quiz: form.quiz.map((item) => ({ q: item.q.trim(), a: item.a, e: item.e.trim() })),
  };
}

function LearnManager({ token, onSessionExpired }) {
  const [content, setContent] = useState(null); // 학습 내용 전체
  const [typeKey, setTypeKey] = useState("report"); // 고른 유형
  const [unitIndex, setUnitIndex] = useState(0); // 고른 단원 순서
  const [form, setForm] = useState(null); // 입력 폼 값
  const [saving, setSaving] = useState(false);
  const [message, setMessage] = useState(""); // 성공 문구
  const [error, setError] = useState("");
  const [confirmReset, setConfirmReset] = useState(false); // 되돌리기 확인창
  const [reloadKey, setReloadKey] = useState(0); // +1 하면 다시 불러오기

  // ----- 학습 내용 기본 뼈대 불러오기 + 즉시 DB 30문제로 오버라이드 -----
  useEffect(() => {
    let ignore = false;
    async function loadAllData() {
      try {
        const data = await fetchLearnContent();
        if (ignore) return;

        // 각 유형별 모든 단원의 퀴즈를 백엔드 DB에서 가져온 30문제로 즉시 채워넣기
        for (const typeItem of data) {
          for (let i = 0; i < typeItem.units.length; i++) {
            const unitNum = i + 1;
            const dbQuizzes = await fetchOxQuizzes(typeItem.key, unitNum);
            if (Array.isArray(dbQuizzes) && dbQuizzes.length > 0) {
              typeItem.units[i].quiz = dbQuizzes;
            }
          }
        }

        if (!ignore) {
          setContent(data);
        }
      } catch (err) {
        console.error("관리자 데이터 로드 실패:", err);
      }
    }
    loadAllData();
    return () => {
      ignore = true;
    };
  }, [reloadKey]);

  const type = content?.find((item) => item.key === typeKey);
  const unit = type?.units[unitIndex];

  // ----- 단원이 바뀌거나 데이터가 갱신되면 폼을 해당 단원의 DB 30문제 내용으로 확실히 채우기 -----
  const unitKey = unit ? `${unit.id}:${reloadKey}:${unit.quiz?.length}` : "";
  const [loadedKey, setLoadedKey] = useState("");
  if (unit && loadedKey !== unitKey) {
    setLoadedKey(unitKey);
    setForm(toForm(unit));
  }

  if (!content || !form || !unit) {
    return (
      <p className="admin-state">
        <Loader2 size={18} className="spin" /> 불러오는 중이에요...
      </p>
    );
  }

  // 폼 값 하나 바꾸기
  const update = (changes) => {
    setForm((prev) => ({ ...prev, ...changes }));
    setMessage("");
    setError("");
  };

  // 문제 하나 바꾸기
  const updateQuestion = (index, changes) =>
    update({ quiz: form.quiz.map((item, i) => (i === index ? { ...item, ...changes } : item)) });

  const addQuestion = () => update({ quiz: [...form.quiz, { q: "", a: true, e: "" }] });

  const removeQuestion = (index) => update({ quiz: form.quiz.filter((_, i) => i !== index) });

  // 고친 게 있는지 (저장 전 경고·버튼 상태용)
  const dirty = JSON.stringify(fromForm(unit.id, form)) !== JSON.stringify(fromForm(unit.id, toForm(unit)));

  // 유형이나 단원을 바꿀 때 저장 안 한 내용이 있으면 물어보기
  const confirmLeave = () => !dirty || window.confirm("저장하지 않은 내용이 있어요. 버리고 이동할까요?");

  const handleSave = async () => {
    setSaving(true);
    setError("");
    try {
      await saveLearnUnit(fromForm(unit.id, form), token);
      setMessage("저장했어요.");
      setReloadKey((n) => n + 1); // 저장한 내용으로 다시 불러오기 ("수정됨" 표시 갱신)
    } catch (err) {
      if (err.message && err.message.includes("401")) {
        if (onSessionExpired) onSessionExpired();
      }
      setError(err.message);
    } finally {
      setSaving(false);
    }
  };

  const handleReset = async () => {
    try {
      await resetLearnUnit(unit.id, token);
      setConfirmReset(false);
      setMessage("기본 내용으로 되돌렸어요.");
      setReloadKey((n) => n + 1);
    } catch (err) {
      if (err.message && err.message.includes("401")) {
        if (onSessionExpired) onSessionExpired();
      }
      setError(err.message);
      setConfirmReset(false);
    }
  };

  return (
    <>
      {/* 안내: 지금은 이 브라우저에만 저장됨 */}
      <p className="admin-learn-info">
        <Info size={16} />
        <span>
          고친 내용은 지금 <strong>이 브라우저에만</strong> 저장돼요. 백엔드가 연결되면 모든 사용자에게 반영돼요.
        </span>
      </p>

      {/* 유형 고르기 + 단원 고르기 */}
      <div className="admin-toolbar">
        <div className="admin-chips" role="group" aria-label="글 유형">
          {content.map((item) => (
            <button
              key={item.key}
              type="button"
              className={item.key === typeKey ? "admin-chip active" : "admin-chip"}
              onClick={() => {
                if (item.key === typeKey || !confirmLeave()) return;
                setTypeKey(item.key);
                setUnitIndex(0);
                setMessage("");
              }}
            >
              {item.label}
            </button>
          ))}
        </div>
        <select
          className="admin-learn-select"
          value={unitIndex}
          onChange={(event) => {
            if (!confirmLeave()) return;
            setUnitIndex(Number(event.target.value));
            setMessage("");
          }}
          aria-label="단원 고르기"
        >
          {type.units.map((item, index) => (
            <option key={item.id} value={index}>
              {String(index + 1).padStart(2, "0")}. {item.title}
              {item.edited ? " (수정됨)" : ""}
            </option>
          ))}
        </select>
      </div>

      {/* ===== 개념 ===== */}
      <div className="admin-form">
        <div className="admin-form-head">
          <strong>
            {type.label} {unitIndex + 1}단원 {unit.edited && <span className="admin-learn-edited">수정됨</span>}
          </strong>
        </div>

        <label className="admin-field">
          <span className="admin-label">단원 제목</span>
          <input className="admin-input" value={form.title} onChange={(e) => update({ title: e.target.value })} />
        </label>
        <label className="admin-field">
          <span className="admin-label">한 줄 요약</span>
          <textarea rows={2} value={form.summary} onChange={(e) => update({ summary: e.target.value })} />
        </label>
        <label className="admin-field">
          <span className="admin-label">꼭 알아야 할 내용 (한 줄에 하나씩, 글쓰기 연습 AI 채점 기준으로도 쓰여요)</span>
          <textarea rows={4} value={form.pointsText} onChange={(e) => update({ pointsText: e.target.value })} />
        </label>
        <div className="admin-learn-two">
          <label className="admin-field">
            <span className="admin-label">좋은 예</span>
            <textarea rows={3} value={form.good} onChange={(e) => update({ good: e.target.value })} />
          </label>
          <label className="admin-field">
            <span className="admin-label">고칠 예</span>
            <textarea rows={3} value={form.bad} onChange={(e) => update({ bad: e.target.value })} />
          </label>
        </div>
        <label className="admin-field">
          <span className="admin-label">팁</span>
          <input className="admin-input" value={form.tip} onChange={(e) => update({ tip: e.target.value })} />
        </label>
        <label className="admin-field">
          <span className="admin-label">글쓰기 연습 할 일</span>
          <textarea rows={2} value={form.task} onChange={(e) => update({ task: e.target.value })} />
        </label>
      </div>

      {/* ===== O/X 문제 ===== */}
      <div className="admin-form">
        <div className="admin-form-head">
          <strong>O/X 문제 {form.quiz.length}개</strong>
          <span className="admin-hint">사용자는 이 문제를 모두 맞혀야 단원을 완료해요. (권장 10개)</span>
        </div>

        <ol className="admin-learn-quiz">
          {form.quiz.map((item, index) => (
            // key에 index를 쓰는 이유: 문제에 고유 id가 없고, 순서 자체가 문제 번호라서
            <li key={index} className="admin-learn-q">
              <div className="admin-learn-q-head">
                <span className="admin-learn-q-number">{index + 1}</span>
                <textarea
                  rows={2}
                  value={item.q}
                  onChange={(e) => updateQuestion(index, { q: e.target.value })}
                  placeholder="문제 문장 (맞으면 O, 틀리면 X)"
                  aria-label={`${index + 1}번 문제`}
                />
                {/* 정답 O/X 고르기 */}
                <div className="admin-learn-ox" role="group" aria-label={`${index + 1}번 정답`}>
                  <button
                    type="button"
                    className={item.a === true ? "active o" : ""}
                    onClick={() => updateQuestion(index, { a: true })}
                    aria-pressed={item.a === true}
                  >
                    O
                  </button>
                  <button
                    type="button"
                    className={item.a === false ? "active x" : ""}
                    onClick={() => updateQuestion(index, { a: false })}
                    aria-pressed={item.a === false}
                  >
                    X
                  </button>
                </div>
                <button
                  type="button"
                  className="admin-icon-button"
                  onClick={() => removeQuestion(index)}
                  aria-label={`${index + 1}번 문제 삭제`}
                  disabled={form.quiz.length <= 1}
                >
                  <Trash2 size={16} />
                </button>
              </div>
              <input
                className="admin-learn-explain"
                value={item.e}
                onChange={(e) => updateQuestion(index, { e: e.target.value })}
                placeholder="해설 (틀렸을 때 보여줄 설명)"
                aria-label={`${index + 1}번 해설`}
              />
            </li>
          ))}
        </ol>

        <button type="button" className="admin-secondary admin-learn-add" onClick={addQuestion}>
          <Plus size={15} /> 문제 추가
        </button>
      </div>

      {error && (
        <p className="admin-error" role="alert">
          {error}
        </p>
      )}
      {message && (
        <p className="admin-notice" role="status">
          <CheckCircle2 size={16} /> {message}
        </p>
      )}

      {/* 아래 버튼 줄 */}
      <div className="admin-form-actions admin-learn-actions">
        {unit.edited && (
          <button type="button" className="admin-secondary" onClick={() => setConfirmReset(true)}>
            <RotateCcw size={15} /> 기본 내용으로 되돌리기
          </button>
        )}
        <button type="button" className="admin-secondary" onClick={() => update(toForm(unit))} disabled={!dirty}>
          고친 내용 취소
        </button>
        <button type="button" className="admin-primary" onClick={handleSave} disabled={saving || !dirty}>
          {saving ? <Loader2 size={15} className="spin" /> : <Save size={15} />} 저장하기
        </button>
      </div>

      {confirmReset && (
        <ConfirmModal
          danger
          title="기본 내용으로 되돌릴까요?"
          message={`"${unit.title}" 단원에서 고친 내용이 모두 지워지고\n처음 내용으로 돌아가요.`}
          confirmLabel="되돌리기"
          onCancel={() => setConfirmReset(false)}
          onConfirm={handleReset}
        />
      )}
    </>
  );
}

export default LearnManager;