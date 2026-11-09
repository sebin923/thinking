// =============================================================
// learn/OxQuiz.jsx — 단원의 O/X 문제 풀기 (한 문제씩)
// -------------------------------------------------------------
// 흐름
//   문제 보여주기 → O 또는 X 누르기 → 바로 정답·해설 보여주기 → "다음 문제" → … → 마지막 문제 뒤 onFinish
// 점수 계산·저장은 여기서 안 하고, 고른 답 목록만 부모(UnitView)에게 넘김
// =============================================================

import { useState } from "react";
// Circle: O 버튼 아이콘, X: X 버튼 아이콘, CheckCircle2/XCircle: 정답·오답 표시, ArrowRight: 다음
import { Circle, X, CheckCircle2, XCircle, ArrowRight } from "lucide-react";

// props
//  - questions: [{ q, a, e }, …] 문제 목록
//  - onFinish: 다 풀었을 때 실행 → [{ index, chosen }, …] (문제 순서대로)를 넘겨줌
//  - onCancel: "그만 풀기" 버튼 (개념 화면으로 돌아가기)
function OxQuiz({ questions, onFinish, onCancel }) {
  const [current, setCurrent] = useState(0); // 지금 푸는 문제 번호 (0부터)
  const [chosen, setChosen] = useState(null); // 이 문제에서 고른 답 (null = 아직 안 고름)
  const [answers, setAnswers] = useState([]); // 지금까지 고른 답 목록

  const question = questions[current];
  const answered = chosen !== null; // 이 문제를 이미 골랐는지
  const isCorrect = answered && chosen === question.a;
  const isLast = current === questions.length - 1;

  // ----- O 또는 X 고르기 (한 번 고르면 바꿀 수 없음) -----
  const choose = (value) => {
    if (answered) return;
    setChosen(value);
    setAnswers((prev) => [...prev, { index: current, chosen: value }]);
  };

  // ----- 다음 문제로 (마지막이면 결과 넘기기) -----
  const next = () => {
    if (isLast) {
      onFinish(answers);
      return;
    }
    setCurrent((n) => n + 1);
    setChosen(null);
  };

  // 진행 막대 길이: 푼 문제 수 / 전체 (지금 문제를 골랐으면 그것까지 포함)
  const progressPercent = ((current + (answered ? 1 : 0)) / questions.length) * 100;

  // O/X 버튼 모양 정하기: 고르기 전엔 기본, 고른 뒤엔 정답은 초록, 내가 고른 오답은 빨강
  const buttonClass = (value) => {
    if (!answered) return "ox-button";
    if (value === question.a) return "ox-button correct";
    if (value === chosen) return "ox-button wrong";
    return "ox-button dim";
  };

  return (
    <div className="ox-quiz">
      {/* 위쪽: 몇 번째 문제인지 + 진행 막대 */}
      <div className="ox-head">
        <span className="ox-count">
          {current + 1} / {questions.length}
        </span>
        <div className="ox-progress" aria-hidden="true">
          <div className="ox-progress-fill" style={{ width: `${progressPercent}%` }} />
        </div>
        <button type="button" className="learn-text-button" onClick={onCancel}>
          그만 풀기
        </button>
      </div>

      {/* 문제 */}
      <p className="ox-question">
        <span className="ox-question-number">Q{current + 1}.</span> {question.q}
      </p>

      {/* O / X 버튼 */}
      <div className="ox-buttons">
        <button
          type="button"
          className={buttonClass(true)}
          onClick={() => choose(true)}
          disabled={answered}
          aria-label="O (맞다)"
        >
          <Circle size={44} strokeWidth={2.6} />
          <span>맞아요</span>
        </button>
        <button
          type="button"
          className={buttonClass(false)}
          onClick={() => choose(false)}
          disabled={answered}
          aria-label="X (틀리다)"
        >
          <X size={50} strokeWidth={2.6} />
          <span>아니에요</span>
        </button>
      </div>

      {/* 고른 뒤: 정답 여부 + 해설 + 다음 버튼 */}
      {answered && (
        // role="status": 화면 읽기 프로그램이 결과를 바로 읽어 줌
        <div className={isCorrect ? "ox-feedback correct" : "ox-feedback wrong"} role="status">
          <p className="ox-feedback-title">
            {isCorrect ? <CheckCircle2 size={20} /> : <XCircle size={20} />}
            {isCorrect ? "정답이에요!" : `아쉬워요. 정답은 ${question.a ? "O" : "X"}예요.`}
          </p>
          {question.e && <p className="ox-feedback-explain">{question.e}</p>}
          <button type="button" className="btn-primary ox-next" onClick={next}>
            {isLast ? "결과 보기" : "다음 문제"} <ArrowRight size={16} />
          </button>
        </div>
      )}
    </div>
  );
}

export default OxQuiz;
