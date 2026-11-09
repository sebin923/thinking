// =============================================================
// learn/WritingPractice.jsx — 단원의 "글쓰기 연습" (O/X 만점을 받아야 열림)
// -------------------------------------------------------------
// 흐름
//   ① 할 일(task) + 연습 자료(학습 데이터의 주제·사실, 또는 자기소개서 문항) 보여주기
//   ② 사용자가 직접 글쓰기 (글자 수 표시)
//   ③ "AI 채점받기" → 단원 규칙을 기준으로 AI(CLOVA)가 100점 만점으로 채점
//        - 기준별 점수(10점 만점) + 이유, 전체 평가, 다음에 고칠 점
//   ④ 90점 이상 → 단원 완료 → 다음 단원이 열림
//      90점 미만 → 피드백을 보고 글을 고쳐서 다시 채점 (몇 번이든 가능)
//   ⑤ 단원을 완료하면 원문(학습 데이터) / 예시 답안과 비교해 볼 수 있음
//      (완료 전에 보여주면 예시 답안을 베껴서 통과할 수 있어서 완료 뒤에만 보여줌)
// 채점·저장: api/learn.js의 scoreWriting (백엔드 POST /api/learn/writing-score)
// =============================================================

import { useState } from "react";
// PenLine: 할 일, FileText: 자료, ExternalLink: 출처 링크, Sparkles: AI 채점, Loader2: 채점 중
// Trophy: 통과, Target: 다음에 고칠 점, ArrowRight: 다음 단원, BookOpenText: 비교 자료
import {
  PenLine,
  FileText,
  ExternalLink,
  Sparkles,
  Loader2,
  Trophy,
  Target,
  ArrowRight,
  BookOpenText,
} from "lucide-react";

import { LEARN_PASS_SCORE } from "../../api/learn";

// 글이 너무 짧으면 채점을 막음 (최소 글자 수, 백엔드도 30자 미만은 거절함)
const MIN_LENGTH = 30;
// 글이 너무 길면 막음 (백엔드 제한 3000자)
const MAX_LENGTH = 3000;

// 기준 점수(10점 만점)에 따라 막대 색 정하기
function criterionLevel(score, max) {
  const ratio = max ? score / max : 0;
  if (ratio >= 0.9) return "good"; // 9~10점
  if (ratio >= 0.6) return "mid"; // 6~8점
  return "low"; // 0~5점
}

// props
//  - unit: 단원 (task, points 사용)
//  - practice: 연습 자료 (data/learn/index.js의 getPracticeFor 결과)
//  - saved: 예전에 채점 받은 글 { text, score, criteria, overallFeedback, nextStep, onTask } (없으면 undefined)
//  - completed: 이 단원을 이미 완료했는지 (90점 이상 받은 적 있는지)
//  - best: 글쓰기 최고 점수 (없으면 0)
//  - onScore: 채점 함수 (text를 넘기면 Promise<{ result, firstComplete }>를 돌려줌)
//  - onNextUnit: "다음 단원" 버튼 (다음 단원이 아직 잠겨 있거나 마지막 단원이면 null)
function WritingPractice({ unit, practice, saved, completed, best, onScore, onNextUnit }) {
  // 예전에 채점 받은 글이 있으면 그 글로 시작
  const [text, setText] = useState(saved?.text || "");
  // 지금 보여줄 채점 결과 (예전 결과가 있으면 그걸로 시작)
  // saved는 저장 모양(score, criteria …)이라 화면 모양으로 맞춰 줌
  const [result, setResult] = useState(() =>
    saved?.score !== undefined
      ? {
          score: saved.score,
          passed: saved.score >= LEARN_PASS_SCORE,
          onTask: saved.onTask !== false,
          criteria: saved.criteria || [],
          overallFeedback: saved.overallFeedback || "",
          nextStep: saved.nextStep || "",
        }
      : null,
  );
  // 채점한 글 (글을 고치지 않고 같은 글로 또 채점하는 걸 막으려고 기억)
  const [scoredText, setScoredText] = useState(saved?.score !== undefined ? saved.text : null);
  const [firstComplete, setFirstComplete] = useState(false); // 이번 채점으로 처음 완료했는지
  const [scoring, setScoring] = useState(false);
  const [error, setError] = useState("");

  const length = text.trim().length;
  const unchanged = scoredText !== null && text.trim() === scoredText.trim(); // 채점 뒤에 안 고쳤는지

  const handleScore = async () => {
    setScoring(true);
    setError("");
    try {
      const scored = await onScore(text);
      setResult(scored.result);
      setScoredText(text);
      setFirstComplete(scored.firstComplete);
    } catch (err) {
      setError(err.message);
    } finally {
      setScoring(false);
    }
  };

  // 채점 버튼 옆 안내 문구 (막힌 이유를 알려줌)
  let hint = `AI 채점 ${LEARN_PASS_SCORE}점 이상이면 단원 완료예요.`;
  if (length < MIN_LENGTH) hint = `${MIN_LENGTH}자 이상 써야 채점받을 수 있어요.`;
  else if (length > MAX_LENGTH) hint = `${MAX_LENGTH.toLocaleString("ko-KR")}자 이하로 줄여 주세요.`;
  else if (unchanged) hint = "글을 고친 뒤에 다시 채점받을 수 있어요.";

  return (
    <div className="writing-practice">
      {/* ① 할 일 */}
      <div className="wp-task">
        <PenLine size={18} />
        <p>{unit.task}</p>
      </div>

      {/* ① 연습 자료 */}
      {practice?.kind === "data" && (
        <div className="wp-material">
          <p className="wp-material-title">
            <FileText size={16} /> 주제: {practice.topic}
          </p>
          <ul>
            {practice.facts.map((fact) => (
              <li key={fact}>{fact}</li>
            ))}
          </ul>
          {/* 출처 표기 (위키백과·정책브리핑 자료는 출처를 꼭 보여줘야 함) */}
          <a className="wp-source" href={practice.url} target="_blank" rel="noreferrer">
            출처: {practice.source} 「{practice.topic}」 · {practice.license} <ExternalLink size={12} />
          </a>
        </div>
      )}
      {practice?.kind === "question" && (
        <div className="wp-material">
          <p className="wp-material-title">
            <FileText size={16} /> 연습 문항
          </p>
          <p className="wp-question">{practice.question}</p>
        </div>
      )}

      {/* 채점 기준 미리 보기 (무엇을 보고 채점하는지 알고 쓰게) */}
      <div className="wp-criteria-preview">
        <p>
          <Sparkles size={15} /> AI가 이렇게 채점해요 <span>(기준마다 10점, 100점으로 환산)</span>
        </p>
        <ul>
          {unit.points.map((point) => (
            <li key={point}>{point}</li>
          ))}
          <li>과제 수행: 할 일을 빠짐없이 하고, 자료에 없는 사실을 지어내지 않기</li>
          <li>맞춤법·문장: 맞춤법·띄어쓰기, 주어와 서술어 호응</li>
        </ul>
      </div>

      {/* ② 직접 쓰기 */}
      <label className="wp-editor">
        <span className="wp-editor-label">내 글</span>
        <textarea
          value={text}
          onChange={(event) => setText(event.target.value)}
          rows={9}
          placeholder="이 단원에서 배운 규칙을 떠올리며 직접 써 보세요."
          readOnly={scoring} // 채점하는 동안은 못 고치게
        />
        <span className={length > MAX_LENGTH ? "wp-length over" : "wp-length"}>{length.toLocaleString("ko-KR")}자</span>
      </label>

      {/* ③ 채점 버튼 */}
      <div className="wp-actions">
        <span className="wp-hint">{hint}</span>
        <button
          type="button"
          className="btn-primary"
          onClick={handleScore}
          disabled={scoring || length < MIN_LENGTH || length > MAX_LENGTH || unchanged}
        >
          {scoring ? <Loader2 size={16} className="spin" /> : <Sparkles size={16} />}
          {scoring ? "AI가 채점하는 중..." : result ? "다시 채점받기" : "AI 채점받기"}
        </button>
      </div>

      {error && (
        <p className="learn-error" role="alert">
          {error}
        </p>
      )}

      {/* ③ 채점 결과 */}
      {result && (
        // aria-live: 결과가 바뀌면 화면 읽기 프로그램이 읽어 줌
        <section className={result.passed ? "wp-score passed" : "wp-score"} aria-live="polite" aria-label="AI 채점 결과">
          <div className="wp-score-head">
            <div className="wp-score-number">
              {result.passed && <Trophy size={28} />}
              <strong>{result.score}</strong>
              <span>/ 100점</span>
            </div>
            <div className="wp-score-message">
              {result.passed ? (
                <>
                  <p className="wp-score-title">{firstComplete ? "단원 완료! 축하해요" : `${LEARN_PASS_SCORE}점 넘었어요!`}</p>
                  <p className="wp-score-desc">
                    {firstComplete && onNextUnit ? "다음 단원이 열렸어요." : "이 단원의 규칙을 잘 지켜서 썼어요."}
                  </p>
                </>
              ) : (
                <>
                  <p className="wp-score-title">
                    {LEARN_PASS_SCORE - result.score}점만 더! {LEARN_PASS_SCORE}점 이상이면 단원 완료예요
                  </p>
                  <p className="wp-score-desc">아래 피드백을 보고 글을 고친 뒤 다시 채점받아 보세요.</p>
                </>
              )}
            </div>
          </div>

          {/* 점수 막대 + 90점 기준선 */}
          <div className="wp-score-bar" aria-hidden="true">
            <span className="wp-score-fill" style={{ width: `${result.score}%` }} />
            <span className="wp-score-line" style={{ left: `${LEARN_PASS_SCORE}%` }} />
          </div>
          <p className="wp-score-best">
            {completed ? "단원 완료" : "아직 완료 전"} · 최고 {Math.max(best || 0, result.score)}점
          </p>

          {!result.onTask && (
            <p className="learn-error">과제와 다른 내용으로 쓴 것 같아요. 할 일과 자료를 다시 확인해 주세요. (최대 50점)</p>
          )}

          {result.overallFeedback && <p className="wp-score-overall">{result.overallFeedback}</p>}

          {/* 기준별 점수 */}
          <ul className="wp-criteria">
            {result.criteria.map((item) => {
              const level = criterionLevel(item.score, item.max);
              return (
                <li key={item.label} className={`wp-criterion ${level}`}>
                  <div className="wp-criterion-head">
                    <span className="wp-criterion-label">{item.label}</span>
                    <span className="wp-criterion-score">
                      {item.score}
                      <small>/{item.max}</small>
                    </span>
                  </div>
                  <span className="wp-criterion-bar" aria-hidden="true">
                    <span style={{ width: `${(item.score / item.max) * 100}%` }} />
                  </span>
                  {item.comment && <p className="wp-criterion-comment">{item.comment}</p>}
                </li>
              );
            })}
          </ul>

          {/* 다음에 고칠 점 (통과 못 했을 때 가장 중요) */}
          {result.nextStep && (
            <p className="wp-next-step">
              <Target size={16} />
              <span>
                <strong>{result.passed ? "더 좋아지려면" : "먼저 이것부터 고쳐 보세요"}</strong>
                {result.nextStep}
              </span>
            </p>
          )}

          {result.passed && onNextUnit && (
            <div className="wp-actions">
              <button type="button" className="btn-primary" onClick={onNextUnit}>
                다음 단원 <ArrowRight size={16} />
              </button>
            </div>
          )}
        </section>
      )}

      {/* ⑤ 비교 자료: 단원을 완료한 뒤에만 */}
      {completed && (practice?.example || practice?.sample) && (
        <details className="wp-compare">
          <summary>
            <BookOpenText size={16} />
            {practice.kind === "data" ? "같은 사실로 쓴 원문과 비교해 보기" : "예시 답안과 비교해 보기"}
          </summary>
          <div className="wp-compare-text">{practice.example || practice.sample}</div>
          {practice.kind === "data" && (
            <p className="wp-compare-note">
              ※ 원문은 이 단원의 규칙을 기준으로 쓴 글이 아니에요. 내 글이 규칙을 더 잘 지켰는지 비교해 보세요.
            </p>
          )}
        </details>
      )}
    </div>
  );
}

export default WritingPractice;
