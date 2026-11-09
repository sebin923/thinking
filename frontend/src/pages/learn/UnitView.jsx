// =============================================================
// learn/UnitView.jsx — 단원 하나 학습 화면
// -------------------------------------------------------------
// 위쪽 단계 탭: [① 개념] → [② O/X 퀴즈] → [③ 글쓰기 연습]
//   ① 개념   : 요약 + 핵심 내용 + 좋은 예/고칠 예 + 팁 → "O/X 문제 풀기"
//   ② 퀴즈   : OxQuiz로 10문제 → 결과 (만점이면 글쓰기 열림, 틀린 문제는 오답노트로)
//   ③ 글쓰기 : 만점을 받은 단원만 열림 (WritingPractice)
//              AI 채점 90점 이상 → 단원 완료 → 다음 단원 열림
// =============================================================

import { useState } from "react";
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
} from "lucide-react";

import OxQuiz from "./OxQuiz";
import WritingPractice from "./WritingPractice";

// props
//  - type: 글 유형 (label 사용)
//  - unit: 단원 / unitIndex: 단원 순서(0부터)
//  - unitProgress: 이 단원의 진도 (없으면 undefined)
//  - practice: 글쓰기 연습 자료
//  - onBack: 단원 목록으로
//  - onSubmitQuiz: O/X 결과 저장 (answers → Promise<{ score, total, passed, firstPass }>)
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
  onScoreWriting,
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

  const passed = Boolean(unitProgress?.passed); // 만점 받은 적 있는지 = 글쓰기 열림
  const completed = Boolean(unitProgress?.completed); // 글쓰기 90점 이상 받은 적 있는지 = 단원 완료

  // ----- 퀴즈를 다 풀었을 때 -----
  const handleFinish = async (answers) => {
    setError("");
    try {
      const saved = await onSubmitQuiz(answers);
      setResult({ ...saved, wrongCount: saved.total - saved.score });
      setStep("result");
    } catch (err) {
      setError(err.message);
    }
  };

  const startQuiz = () => {
    setQuizRound((n) => n + 1);
    setStep("quiz");
  };

  // 위쪽 단계 탭 (결과 화면은 "퀴즈" 탭에 불이 들어오게)
  const steps = [
    { key: "concept", label: "개념", icon: BookOpen, enabled: true },
    { key: "quiz", label: "O/X 퀴즈", icon: ListChecks, enabled: true },
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
                disabled={!item.enabled}
                // 퀴즈 탭을 누르면 처음부터 새로 시작
                onClick={() => (item.key === "quiz" ? startQuiz() : setStep(item.key))}
                title={item.enabled ? undefined : "O/X 문제를 모두 맞히면 열려요"}
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
            <button type="button" className="btn-primary" onClick={startQuiz}>
              O/X 문제 풀기 ({unit.quiz.length}문제) <ArrowRight size={16} />
            </button>
          </div>
        </div>
      )}

      {/* ===== ② 퀴즈 ===== */}
      {step === "quiz" && (
        <OxQuiz key={quizRound} questions={unit.quiz} onFinish={handleFinish} onCancel={() => setStep("concept")} />
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
                {result.firstPass ? "만점! 글쓰기 연습이 열렸어요" : "이번에도 만점이에요"}
              </p>
              <p className="unit-result-desc">
                {completed
                  ? "이미 완료한 단원이에요. 글쓰기 연습으로 다시 실력을 확인해 볼 수도 있어요."
                  : "배운 규칙으로 글을 써서 AI 채점 90점 이상을 받으면 단원이 완료되고 다음 단원이 열려요."}
              </p>
            </>
          ) : (
            <>
              <p className="unit-result-title">조금만 더! 모두 맞혀야 글쓰기 연습이 열려요</p>
              <p className="unit-result-desc">
                틀린 {result.wrongCount}문제는 오답노트에 담아 두었어요. 해설을 확인하고 다시 풀어 보세요.
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
                <button type="button" className="btn-primary" onClick={startQuiz}>
                  <RotateCcw size={16} /> 다시 풀기
                </button>
                <button type="button" className="btn-outline" onClick={onOpenWrongNotes}>
                  <NotebookPen size={16} /> 오답노트 보기
                </button>
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
