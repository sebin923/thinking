// =============================================================
// learn/WrongNotes.jsx — 학습 화면의 "오답노트" 탭
// -------------------------------------------------------------
// 틀린 문제가 모이는 곳 (두 군데에서 모임)
//   ① 학습 단원 O/X 문제 (보고서·자기소개서·발표문)
//   ② 퀴즈 화면의 맞춤법·문법 객관식 문제 (note.source === "quiz", 로그인했을 때만 저장)
//   - 골라 보기 (전체 / 보고서 / 자기소개서 / 발표문 / 퀴즈)
//   - 문제마다 다시 풀기 → 맞히면 "해결" (단원 퀴즈에서 다시 맞혀도 자동으로 해결 처리됨)
//   - "해결한 문제도 보기"를 켜면 해결한 문제도 보이고, 해결한 문제는 지울 수 있음
//   - 10개씩 페이지로 나눠 보여줌 (1페이지뿐이어도 번호는 항상 보임, 마이페이지·관리자 페이지와 같은 방식)
// =============================================================

import { useState } from "react";
// 창만 스크롤하는 도구 (페이지를 바꿨을 때 목록 맨 위로 올리기)
import scrollToElement from "../../utils/scrollToElement";
// Circle/X: O/X 버튼, CheckCircle2: 해결, Trash2: 지우기, NotebookPen: 빈 화면 아이콘
// ChevronLeft/ChevronRight: 페이지 번호 양옆 화살표
import { Circle, X, CheckCircle2, Trash2, NotebookPen, ChevronLeft, ChevronRight } from "lucide-react";

// 한 페이지에 보여줄 오답 개수 (바꾸고 싶으면 이 숫자만 고치면 됨)
const PAGE_SIZE = 10;

// props
//  - content: 학습 내용 (유형 이름 찾기용)
//  - progress: 내 진도 (wrong 사용)
//  - onAnswer: 다시 풀기 (key, chosen) → Promise<{ correct }>
//  - onDelete: 지우기 (key) → Promise
//  - onGoLearn: 빈 화면 "학습하러 가기"
function WrongNotes({ content, progress, onAnswer, onDelete, onGoLearn }) {
  const [filter, setFilter] = useState("all"); // 유형 골라 보기 ("all" 또는 유형 key)
  const [showResolved, setShowResolved] = useState(false); // 해결한 문제도 볼지
  // 방금 다시 푼 결과 { [key]: { chosen, correct } } → 그 카드에 정답·해설을 보여줌
  const [answered, setAnswered] = useState({});
  const [error, setError] = useState("");
  const [page, setPage] = useState(1); // 지금 보고 있는 페이지 (1부터)

  // 오답이 속한 묶음: 퀴즈에서 온 건 "quiz", 학습 단원은 유형 key ("report" 등)
  const groupOf = (note) => (note.source === "quiz" ? "quiz" : note.typeKey);

  // 이름표 글자: 퀴즈는 "퀴즈", 학습은 유형 이름 ("report" → "보고서")
  const typeLabel = (note) =>
    note.source === "quiz" ? "퀴즈" : content.find((type) => type.key === note.typeKey)?.label || note.typeKey;

  // 목록 만들기: 묶음 필터 + 해결 여부 + 최근에 틀린 순서
  const notes = Object.values(progress.wrong)
    .filter((note) => filter === "all" || groupOf(note) === filter)
    // 방금 다시 풀어서 해결된 문제는 결과를 볼 수 있게 이번에는 남겨 둠
    .filter((note) => showResolved || !note.resolved || answered[note.key])
    .sort((a, b) => (b.lastAt || "").localeCompare(a.lastAt || ""));

  // 묶음별 미해결 개수 (필터 버튼 옆 숫자)
  const openCount = (key) =>
    Object.values(progress.wrong).filter((note) => !note.resolved && (key === "all" || groupOf(note) === key))
      .length;

  // ----- 페이지 나누기 -----
  // 23개면 23 / 10 = 2.3 → 올림해서 3페이지 (최소 1페이지)
  const totalPages = Math.max(1, Math.ceil(notes.length / PAGE_SIZE));
  // 문제를 해결하거나 지워서 목록이 줄면 지금 페이지가 없어질 수 있음 → 마지막 페이지로 맞춤
  const currentPage = Math.min(page, totalPages);
  // slice(시작, 끝): 지금 페이지에 해당하는 10개만 잘라냄 (끝 번호는 포함 안 됨)
  const pageNotes = notes.slice((currentPage - 1) * PAGE_SIZE, currentPage * PAGE_SIZE);
  // 페이지 번호: 페이지가 많으면 지금 페이지 근처 최대 5개만 (예: 3 4 [5] 6 7)
  const firstNumber = Math.max(1, Math.min(currentPage - 2, totalPages - 4));
  const lastNumber = Math.min(totalPages, firstNumber + 4);
  const pageNumbers = Array.from({ length: lastNumber - firstNumber + 1 }, (_, i) => firstNumber + i);

  const goPage = (next) => {
    if (next < 1 || next > totalPages || next === currentPage) return;
    setPage(next);
    scrollToElement(".wrong-toolbar"); // 목록 맨 위로
  };

  const handleAnswer = async (key, chosen) => {
    setError("");
    try {
      const { correct } = await onAnswer(key, chosen);
      setAnswered((prev) => ({ ...prev, [key]: { chosen, correct } }));
    } catch (err) {
      setError(err.message);
    }
  };

  const handleDelete = async (key) => {
    setError("");
    try {
      await onDelete(key);
    } catch (err) {
      setError(err.message);
    }
  };

  // 필터 버튼: 전체 + 학습 유형 3개 + 퀴즈
  const filters = [
    { key: "all", label: "전체" },
    ...content.map((type) => ({ key: type.key, label: type.label })),
    { key: "quiz", label: "퀴즈" },
  ];

  return (
    <div className="wrong-notes">
      {/* 위쪽: 유형 필터 + 해결한 문제 보기 */}
      <div className="wrong-toolbar">
        <div className="learn-chips" role="group" aria-label="오답 유형 고르기">
          {filters.map((item) => (
            <button
              key={item.key}
              type="button"
              className={filter === item.key ? "learn-chip active" : "learn-chip"}
              onClick={() => {
                setFilter(item.key);
                setPage(1); // 골라 보기를 바꾸면 1페이지부터
              }}
              aria-pressed={filter === item.key}
            >
              {item.label}
              <span className="learn-chip-count">{openCount(item.key)}</span>
            </button>
          ))}
        </div>
        <label className="wrong-toggle">
          <input
            type="checkbox"
            checked={showResolved}
            onChange={(event) => {
              setShowResolved(event.target.checked);
              setPage(1); // 보이는 목록이 바뀌니까 1페이지부터
            }}
          />
          해결한 문제도 보기
        </label>
      </div>

      {error && (
        <p className="learn-error" role="alert">
          {error}
        </p>
      )}

      {notes.length === 0 ? (
        <div className="panel learn-empty">
          <NotebookPen size={32} strokeWidth={1.6} />
          <p>
            {Object.keys(progress.wrong).length === 0
              ? "아직 틀린 문제가 없어요. 학습 단원 O/X나 퀴즈에서 틀린 문제가 여기에 모여요."
              : "이 조건에 맞는 오답이 없어요. 모두 해결했어요!"}
          </p>
          <button type="button" className="btn-outline" onClick={onGoLearn}>
            학습하러 가기
          </button>
        </div>
      ) : (
        // <> </>: 목록(ul)과 페이지 번호(nav) 두 개를 한 묶음으로 돌려주기 위한 빈 껍데기
        <>
        <ul className="wrong-list">
          {pageNotes.map((note) => {
            const result = answered[note.key]; // 방금 다시 푼 결과 (없으면 undefined)
            const showAnswer = note.resolved || result; // 해결했거나 방금 풀었으면 정답·해설 공개
            return (
              <li key={note.key} className={note.resolved ? "panel wrong-card resolved" : "panel wrong-card"}>
                <p className="wrong-meta">
                  <span className={note.source === "quiz" ? "wrong-type quiz" : "wrong-type"}>{typeLabel(note)}</span>
                  {note.unitTitle} · 틀린 횟수 {note.count}번
                  {note.resolved && (
                    <span className="wrong-resolved">
                      <CheckCircle2 size={13} /> 해결
                    </span>
                  )}
                </p>
                <p className="wrong-question">{note.q}</p>

                {/* 다시 풀기 — 퀴즈(객관식): 보기 버튼들 */}
                {!showAnswer && note.source === "quiz" && (
                  <div className="wrong-options">
                    {note.options.map((option) => (
                      <button
                        key={option}
                        type="button"
                        className="wrong-option"
                        onClick={() => handleAnswer(note.key, option)}
                      >
                        {option}
                      </button>
                    ))}
                  </div>
                )}

                {/* 다시 풀기 — 학습 O/X (해결 전 + 아직 이번에 안 풀었을 때만) */}
                {!showAnswer && note.source !== "quiz" && (
                  <div className="wrong-retry">
                    <span>다시 풀어 보기</span>
                    <button type="button" className="wrong-ox" onClick={() => handleAnswer(note.key, true)} aria-label="O">
                      <Circle size={18} strokeWidth={2.6} />
                    </button>
                    <button type="button" className="wrong-ox" onClick={() => handleAnswer(note.key, false)} aria-label="X">
                      <X size={20} strokeWidth={2.6} />
                    </button>
                  </div>
                )}

                {showAnswer && (
                  <div className={result && !result.correct ? "wrong-answer again" : "wrong-answer"} role="status">
                    {result && <strong>{result.correct ? "정답이에요! 해결로 옮겼어요." : "또 틀렸어요. 해설을 다시 읽어 보세요."}</strong>}
                    {/* 퀴즈는 보기 글자 그대로, 학습 O/X는 O/X로 보여줌 */}
                    <p>
                      {note.source === "quiz" ? (
                        <>
                          정답: <b>{note.answer}</b> · 내가 틀렸던 답: {note.myAnswer}
                        </>
                      ) : (
                        <>
                          정답: <b>{note.a ? "O" : "X"}</b> · 내가 틀렸던 답: {note.myAnswer ? "O" : "X"}
                        </>
                      )}
                    </p>
                    {note.e && <p className="wrong-explain">{note.e}</p>}
                    {/* 또 틀렸으면 다시 풀 수 있게 */}
                    {result && !result.correct && (
                      <button
                        type="button"
                        className="learn-text-button"
                        onClick={() =>
                          setAnswered((prev) => {
                            const next = { ...prev };
                            delete next[note.key];
                            return next;
                          })
                        }
                      >
                        한 번 더 풀기
                      </button>
                    )}
                  </div>
                )}

                {note.resolved && (
                  <button type="button" className="wrong-delete" onClick={() => handleDelete(note.key)}>
                    <Trash2 size={14} /> 오답노트에서 지우기
                  </button>
                )}
              </li>
            );
          })}
        </ul>

        {/* 페이지 번호 (1페이지뿐이어도 항상 보여줌) */}
        <nav className="learn-pagination" aria-label="오답노트 페이지">
          <button
            type="button"
            className="learn-page-arrow"
            onClick={() => goPage(currentPage - 1)}
            disabled={currentPage === 1}
            aria-label="이전 페이지"
          >
            <ChevronLeft size={18} />
          </button>
          {pageNumbers.map((number) => (
            <button
              key={number}
              type="button"
              className={number === currentPage ? "learn-page active" : "learn-page"}
              onClick={() => goPage(number)}
              aria-current={number === currentPage ? "page" : undefined}
            >
              {number}
            </button>
          ))}
          <button
            type="button"
            className="learn-page-arrow"
            onClick={() => goPage(currentPage + 1)}
            disabled={currentPage === totalPages}
            aria-label="다음 페이지"
          >
            <ChevronRight size={18} />
          </button>
        </nav>
        </>
      )}
    </div>
  );
}

export default WrongNotes;
