// =============================================================
// learn/UnitView.jsx — 단원 하나 학습 화면
// -------------------------------------------------------------
// 위쪽 단계 탭: [① 개념] → [② O/X 퀴즈] → [③ 글쓰기 연습]
//   ① 개념   : 요약 + 핵심 내용 + 좋은 예/고칠 예 + 팁 → "O/X 문제 풀기"
//   ② 퀴즈   : 남은 문제 중 최대 10개 → 20문제를 누적해서 맞히면 글쓰기 열림
//   ③ 글쓰기 : O/X를 모두 맞힌 단원만 열림 (WritingPractice)
//              AI 채점 90점 이상 → 단원 완료 → 다음 단원 열림
// =============================================================

import { useState, useEffect } from "react";
// ArrowLeft: 목록으로, BookOpen: 개념, ListChecks: 퀴즈, PenLine: 글쓰기, Lock: 잠김
// ThumbsUp/ThumbsDown: 좋은 예/고칠 예, Lightbulb: 팁, Trophy: 만점, RotateCcw: 다시 풀기, NotebookPen: 오답노트
import {
  ArrowLeft,
  BookOpen,
  ListChecks,
  PenLine,
  Lock,
  ThumbsUp,
  ThumbsDown,
  Lightbulb,
  Trophy,
  RotateCcw,
  NotebookPen,
  ArrowRight,
  Loader2,
} from "lucide-react";

import OxQuiz from "./OxQuiz";
import WritingPractice from "./WritingPractice";
import { fetchOxQuizzes } from "../../api/learn";
import { drawQuestions, remainingQuestions } from "../../utils/learningQuiz";
import { QUIZ_ROUND_SIZE } from "../../data/learn/quizBank";

// props
//  - type: 글 유형 (label 사용)
//  - unit: 단원 / unitIndex: 단원 순서(0부터)
//  - unitProgress: 이 단원의 진도 (없으면 undefined)
//  - practice: 글쓰기 연습 자료
//  - onBack: 단원 목록으로
//  - onSubmitQuiz: O/X 결과 저장 (answers → Promise<{ score, total, passed, firstPass }>)
//  - onAnswerQuiz: 문항별 답을 즉시 저장 (중간 종료·재접속 시에도 정답 제외)
//  - onScoreWriting: 글쓰기 AI 채점 (text → Promise<{ result, firstComplete }>)
//  - onOpenWrongNotes: 결과 화면 "오답노트 보기" 버튼
//  - onNextUnit: "다음 단원" 버튼 (다음 단원이 잠겨 있거나 마지막 단원이면 null)
function UnitView({
  type,
  unit,
  unitIndex,
  unitProgress,
  practice,
  onBack,
  onSubmitQuiz,
  onAnswerQuiz,
  onScoreWriting,
  onRecommendPractice,
  onOpenWrongNotes,
  onNextUnit,
}) {
  // step: "concept"(개념) / "quiz"(풀기) / "result"(결과) / "writing"(글쓰기)
  const [step, setStep] = useState("concept");
  // 마지막 퀴즈 결과 { score, total, passed, firstPass, wrongCount }
  const [result, setResult] = useState(null);
  const [error, setError] = useState("");
  // quizRound: 다시 풀 때마다 +1 → OxQuiz를 새로 만들어서 처음부터 시작하게 (key로 씀)
  const [quizRound, setQuizRound] = useState(0);

  const [currentQuiz, setCurrentQuiz] = useState([]);
  const [questionBank, setQuestionBank] = useState([]);
  const [loadingQuiz, setLoadingQuiz] = useState(true);
  const [savingQuiz, setSavingQuiz] = useState(false);

  useEffect(() => {
    let ignore = false;
    async function loadQuizzes() {
      setLoadingQuiz(true);
      try {
        const questions = await fetchOxQuizzes(type.key, unitIndex + 1);
        if (!ignore) { setQuestionBank(questions); setError(""); }
      } catch (err) {
        if (!ignore) setError(err.message || "문제를 불러오지 못했어요. 단원을 다시 열어 주세요.");
      } finally {
        if (!ignore) setLoadingQuiz(false);
      }
    }
    loadQuizzes();
    return () => {
      ignore = true;
    };
  }, [type.key, unitIndex, unit]);

  const passed = Boolean(unitProgress?.passed); // 만점 받은 적 있는지 = 글쓰기 열림
  const completed = Boolean(unitProgress?.completed); // 글쓰기 90점 이상 받은 적 있는지 = 단원 완료
  const remaining = remainingQuestions(questionBank, unitProgress).length;
  const mastered = questionBank.length > 0 && remaining === 0;

  // ----- 퀴즈를 다 풀었을 때 -----
  const handleFinish = async (answers) => {
    setError("");
    setSavingQuiz(true);
    try {
      // 실제 출제한 문항으로만 이번 회차의 결과를 계산한다.
      const quizToSubmit = {
        ...unit,
        quiz: currentQuiz,
      };
      const saved = await onSubmitQuiz(answers, quizToSubmit);
      setResult({ ...saved, wrongCount: saved.total - saved.score });
      setStep("result");
    } catch (err) {
      setError(err.message);
    } finally {
      setSavingQuiz(false);
    }
  };

  const startQuiz = () => {
    if (loadingQuiz || savingQuiz || !questionBank.length || step === "quiz") return;
    const selected = drawQuestions(questionBank, unitProgress, QUIZ_ROUND_SIZE);
    if (!selected.length) { setStep("concept"); return; }
    setCurrentQuiz(selected);
    setError("");
    setQuizRound((n) => n + 1);
    setStep("quiz");
  };

  // 위쪽 단계 탭 (결과 화면은 "퀴즈" 탭에 불이 들어오게)
  const steps = [
    { key: "concept", label: "개념", icon: BookOpen, enabled: true },
    { key: "quiz", label: "O/X 퀴즈", icon: ListChecks, enabled: !loadingQuiz && !savingQuiz && questionBank.length > 0 },
    { key: "writing", label: "글쓰기 연습", icon: PenLine, enabled: passed },
  ];
  const activeStep = step === "result" ? "quiz" : step;

  return (
    <section className="panel unit-view">
      {/* 맨 위: 목록으로 + 단원 제목 */}
      <button type="button" className="learn-back" onClick={onBack}>
        <ArrowLeft size={16} /> {type.label} 단원 목록
      </button>
      <p className="unit-view-eyebrow">
        {type.label} · {unitIndex + 1}단원
        {/* 완료한 단원이면 표시 */}
        {completed && <span className="unit-view-done">완료 · 글쓰기 최고 {unitProgress.writingBest}점</span>}
      </p>
      <h2 className="unit-view-title">{unit.title}</h2>

      {/* 단계 탭 */}
      <ol className="unit-steps">
        {steps.map((item, index) => {
          const Icon = item.enabled ? item.icon : Lock;
          return (
            <li key={item.key}>
              <button
                type="button"
                className={activeStep === item.key ? "unit-step active" : "unit-step"}
                disabled={!item.enabled || (step === "quiz" && item.key !== "quiz")}
                // 퀴즈 탭을 누르면 처음부터 새로 시작
                onClick={() => (item.key === "quiz" ? startQuiz() : setStep(item.key))}
                title={!item.enabled ? "퀴즈를 불러오는 중이거나 잠겨 있어요" : undefined}
              >
                <span className="unit-step-number">{index + 1}</span>
                <Icon size={15} />
                {item.label}
              </button>
            </li>
          );
        })}
      </ol>

      {error && (
        <p className="learn-error" role="alert">
          {error}
        </p>
      )}

      {loadingQuiz && (
        <p className="admin-state" style={{ textAlign: "center", padding: "10px" }}>
          <Loader2 size={16} className="spin" /> 이 단원의 문제를 불러오는 중...
        </p>
      )}

      {/* ===== ① 개념 ===== */}
      {step === "concept" && (
        <div className="unit-concept">
          <p className="concept-summary">{unit.summary}</p>

          <h3 className="concept-heading">꼭 알아야 할 내용</h3>
          <ul className="concept-points">
            {unit.points.map((point) => (
              <li key={point}>{point}</li>
            ))}
          </ul>

          {/* 좋은 예 / 고칠 예 나란히 (비교하면서 보면 차이가 잘 보임) */}
          <div className="concept-examples">
            <div className="concept-example good">
              <p className="concept-example-label">
                <ThumbsUp size={15} /> 좋은 예
              </p>
              <p className="concept-example-text">{unit.good}</p>
            </div>
            <div className="concept-example bad">
              <p className="concept-example-label">
                <ThumbsDown size={15} /> 고칠 예
              </p>
              <p className="concept-example-text">{unit.bad}</p>
            </div>
          </div>

          {unit.tip && (
            <p className="concept-tip">
              <Lightbulb size={16} /> {unit.tip}
            </p>
          )}

          <div className="unit-actions">
            {mastered ? (
              <p className="learn-locked-note"><Trophy size={18} /> 이 단원 {questionBank.length}문제를 모두 맞혔어요.</p>
            ) : (
              <button type="button" className="btn-primary" onClick={startQuiz} disabled={loadingQuiz || !questionBank.length}>
                {loadingQuiz ? "퀴즈 불러오는 중..." : `O/X 문제 풀기 (${Math.min(remaining, QUIZ_ROUND_SIZE)}문제)`} <ArrowRight size={16} />
              </button>
            )}
            {passed && <button type="button" className="btn-outline" onClick={() => setStep("writing")}><PenLine size={16} /> 글쓰기 연습하기</button>}
          </div>
          {!loadingQuiz && questionBank.length > 0 && <p className="unit-result-desc">전체 {questionBank.length}문제 중 {questionBank.length - remaining}문제 정답 · 남은 문제 {remaining}개. 맞힌 문제는 다시 출제하지 않아요.</p>}
        </div>
      )}

      {/* ===== ② 퀴즈 ===== */}
      {step === "quiz" && (
        <OxQuiz key={quizRound} questions={currentQuiz} onAnswer={onAnswerQuiz} onFinish={handleFinish} savingResult={savingQuiz} onCancel={() => setStep("concept")} />
      )}

      {/* ===== ② 결과 ===== */}
      {step === "result" && result && (
        <div className={result.passed ? "unit-result passed" : "unit-result"}>
          <div className="unit-result-score">
            {result.passed && <Trophy size={34} />}
            <strong>
              {result.score} / {result.total}
            </strong>
          </div>

          {result.passed ? (
            <>
              <p className="unit-result-title">
                이 단원 O/X 문제를 모두 맞혔어요!
              </p>
              <p className="unit-result-desc">
                {completed
                  ? "이미 완료한 단원이에요. 글쓰기 연습으로 다시 실력을 확인해 볼 수도 있어요."
                  : "배운 규칙으로 글을 써서 AI 채점 90점 이상을 받으면 단원이 완료되고 다음 단원이 열려요."}
              </p>
            </>
          ) : (
            <>
              <p className="unit-result-title">{result.wrongCount === 0 ? "이번 문제는 모두 정답이에요!" : "해설을 확인하고 이어서 도전해 보세요"}</p>
              <p className="unit-result-desc">
                {result.wrongCount > 0 && <>틀린 {result.wrongCount}문제는 오답노트에 담아 두었어요. </>}
                아직 맞히지 않은 문제는 {result.remaining}개예요. {passed ? "열린 글쓰기 연습도 계속할 수 있어요." : "전체 문제를 한 번씩 맞히면 글쓰기 연습이 열려요."}
              </p>
            </>
          )}

          <div className="unit-actions">
            {result.passed ? (
              <>
                <button type="button" className="btn-primary" onClick={() => setStep("writing")}>
                  <PenLine size={16} /> 글쓰기 연습하기
                </button>
                {onNextUnit && (
                  <button type="button" className="btn-outline" onClick={onNextUnit}>
                    다음 단원 <ArrowRight size={16} />
                  </button>
                )}
              </>
            ) : (
              <>
                <button type="button" className="btn-primary" onClick={startQuiz} disabled={loadingQuiz}>
                  <RotateCcw size={16} /> 남은 문제 풀기
                </button>
                <button type="button" className="btn-outline" onClick={onOpenWrongNotes}>
                  <NotebookPen size={16} /> 오답노트 보기
                </button>
                {passed && <button type="button" className="btn-outline" onClick={() => setStep("writing")}><PenLine size={16} /> 글쓰기 연습하기</button>}
              </>
            )}
          </div>
        </div>
      )}

      {/* ===== ③ 글쓰기 연습 ===== */}
      {step === "writing" &&
        (passed ? (
          <WritingPractice
            // 단원이 바뀌면 입력 칸을 새로 만들도록 key에 단원 id
            key={unit.id}
            unit={unit}
            practice={practice}
            saved={unitProgress?.writing}
            completed={completed}
            best={unitProgress?.writingBest || 0}
            onScore={onScoreWriting}
            onRecommend={onRecommendPractice}
            onNextUnit={onNextUnit}
          />
        ) : (
          <p className="learn-locked-note">
            <Lock size={16} /> O/X 문제를 모두 맞히면 글쓰기 연습이 열려요.
          </p>
        ))}
    </section>
  );
}

export default UnitView;
