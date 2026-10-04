// =============================================================
// QuizPage.jsx — 글쓰기 학습: 맞춤법 퀴즈 페이지
// -------------------------------------------------------------
// 흐름
//   1. 보기 하나를 고른다
//   2. "정답 확인" → 맞았는지/틀렸는지 + 설명이 나옴
//   3. "다음 문제" → 다음 문제로 (10문제)
//   4. 다 풀면 결과 화면 (점수 + 다시 풀기)
// =============================================================

import { useState } from "react";

// 아이콘들 (lucide-react)
import {
  BookOpenCheck, // 퀴즈 카드 제목 옆 아이콘
  Lightbulb, // 힌트 버튼
  ArrowRight, // 정답 확인 / 다음 문제 버튼
  Trophy, // 점수 트로피
  CheckCircle2, // 정답 표시
  XCircle, // 오답 표시
  RotateCcw, // 다시 풀기
} from "lucide-react";

import PageHero from "../components/PageHero";
import { quizQuestions } from "../data/quizData";
import "./QuizPage.css";

// 한 문제 맞힐 때마다 올라가는 점수
const POINT_PER_QUESTION = 10;

function QuizPage() {
  // ===== 상태(state)들 =====

  // current: 지금 풀고 있는 문제 번호 (0부터 시작)
  const [current, setCurrent] = useState(0);

  // selected: 지금 고른 보기 번호 (아직 안 골랐으면 null)
  const [selected, setSelected] = useState(null);

  // checked: "정답 확인"을 눌렀는지 (true면 정답/오답 결과를 보여주는 상태)
  const [checked, setChecked] = useState(false);

  // showHint: 힌트를 펼쳤는지
  const [showHint, setShowHint] = useState(false);

  // results: 문제마다 맞았는지 기록하는 배열
  // 처음엔 전부 null(아직 안 품) → 풀면 true(정답) / false(오답)
  // Array(10).fill(null) → [null, null, ... 10개]
  const [results, setResults] = useState(Array(quizQuestions.length).fill(null));

  // finished: 10문제를 다 풀었는지
  const [finished, setFinished] = useState(false);

  // ===== 상태로부터 계산하는 값들 (따로 저장 안 하고 그때그때 계산) =====

  const question = quizQuestions[current]; // 지금 문제 객체
  const total = quizQuestions.length; // 전체 문제 수 (10)

  // filter: 조건에 맞는 것만 남긴 새 배열 → 맞은(true) 개수 × 10점
  const score = results.filter((result) => result === true).length * POINT_PER_QUESTION;

  // 진행률(%) : 지금 몇 번째 문제인지를 막대 길이로
  const progress = ((current + 1) / total) * 100;

  // 지금 고른 답이 정답인지
  const isCorrect = selected === question.answer;

  // ===== 버튼 동작들 =====

  // 보기를 눌렀을 때
  const handleSelect = (index) => {
    if (checked) return; // 이미 정답 확인을 했으면 답을 못 바꾸게
    setSelected(index);
  };

  // "정답 확인" 버튼
  const handleCheck = () => {
    if (selected === null) return; // 아무것도 안 골랐으면 무시 (버튼도 비활성화돼 있음)

    setChecked(true);

    // results 배열에서 지금 문제 자리에 정답 여부 기록
    // 주의: React에서는 배열을 직접 고치지 않고, 복사본을 만들어 고친 뒤 통째로 바꿔야 화면이 다시 그려짐
    const next = [...results]; // ... (전개 연산자): 배열 복사
    next[current] = isCorrect;
    setResults(next);
  };

  // "다음 문제" / "결과 보기" 버튼
  const handleNext = () => {
    if (current === total - 1) {
      // 마지막 문제였으면 결과 화면으로
      setFinished(true);
      return;
    }
    // 다음 문제로 넘어가면서 고른 답, 확인 여부, 힌트를 초기화
    setCurrent(current + 1);
    setSelected(null);
    setChecked(false);
    setShowHint(false);
  };

  // "다시 풀기" 버튼: 모든 상태를 처음으로
  const handleRestart = () => {
    setCurrent(0);
    setSelected(null);
    setChecked(false);
    setShowHint(false);
    setResults(Array(total).fill(null));
    setFinished(false);
  };

  // 보기 버튼에 붙일 클래스 이름을 정하는 함수
  // (고름 / 정답 / 오답에 따라 색이 달라짐)
  const getOptionClass = (index) => {
    let className = "quiz-option";
    if (!checked) {
      // 확인 전: 고른 것만 파랗게
      if (index === selected) className += " selected";
    } else {
      // 확인 후: 정답 보기는 초록, 내가 고른 오답은 빨강
      if (index === question.answer) className += " correct";
      else if (index === selected) className += " wrong";
    }
    return className;
  };

  // 결과 화면에서 점수에 따라 다른 응원 문구
  const getResultMessage = () => {
    if (score === 100) return "완벽해요! 맞춤법 박사네요 🎉";
    if (score >= 70) return "아주 잘했어요! 조금만 더 연습하면 완벽해요.";
    if (score >= 40) return "좋은 시작이에요. 틀린 문제를 다시 확인해 봐요.";
    return "괜찮아요, 연습할수록 실력이 늘어요!";
  };

  // 문장의 빈칸(____)을 강조 표시용 span으로 바꿔서 보여주기
  // split("____"): "____"를 기준으로 문장을 두 조각으로 나눔 → [앞부분, 뒷부분]
  const [before, after] = question.sentence.split("____");

  return (
    <div className="sub-page">
      <div className="sub-page-inner">
        {/* ===== 페이지 제목 영역 ===== */}
        <PageHero
          eyebrow="글쓰기가 더 쉬워지는 작은 연습"
          title="맞춤법 퀴즈"
          description={
            "문장을 바르게 쓰는 연습을 통해\n더 정확하고 자연스러운 글을 작성할 수 있어요."
          }
          memoText={"조금 더\n바른 표현을\n위해 :)"}
          memoVariant="notebook"
        />

        {/* ===== 퀴즈 카드 ===== */}
        <section className="panel quiz-card">
          {/* 카드 머리: 제목 + 진행률 */}
          <div className="quiz-head">
            <h2 className="quiz-head-title">
              <BookOpenCheck size={24} />
              맞춤법 퀴즈
            </h2>
            {/* 결과 화면이 아닐 때만 진행률 표시 */}
            {!finished && (
              <div className="quiz-progress">
                <span>
                  {current + 1} / {total}
                </span>
                {/* 회색 막대 안에 파란 막대 (너비를 % 로) */}
                <div className="quiz-progress-bar">
                  <div className="quiz-progress-fill" style={{ width: `${progress}%` }} />
                </div>
              </div>
            )}
          </div>

          {/*
            finished가 true면 결과 화면, false면 문제 화면
            (조건 ? A : B 를 큰 덩어리에 쓴 것)
          */}
          {finished ? (
            // ===================== 결과 화면 =====================
            <div className="quiz-result">
              <div className="quiz-result-trophy">
                <Trophy size={44} strokeWidth={1.6} />
              </div>
              <p className="quiz-result-label">최종 점수</p>
              <p className="quiz-result-score">
                {score}
                <span>점</span>
              </p>
              <p className="quiz-result-message">{getResultMessage()}</p>
              <button type="button" className="btn-primary" onClick={handleRestart}>
                <RotateCcw size={18} />
                다시 풀기
              </button>
            </div>
          ) : (
            // ===================== 문제 화면 =====================
            <div className="quiz-body">
              <span className="quiz-badge">문제 {current + 1}</span>

              {/* 문제 문장: 빈칸 부분만 밑줄 박스로 강조 */}
              <h3 className="quiz-question">
                ‘{before}
                {/* 정답 확인 후에는 빈칸에 정답을 채워서 보여줌 */}
                <span className={checked ? "quiz-blank filled" : "quiz-blank"}>
                  {checked ? question.options[question.answer] : ""}
                </span>
                {after}’
                <br />
                빈칸에 들어갈 올바른 표현은 무엇일까요?
              </h3>

              {/* 보기 목록 */}
              {/* role="radiogroup": 여러 개 중 하나만 고르는 묶음이라는 걸 알려줌 (접근성) */}
              <div className="quiz-options" role="radiogroup" aria-label="보기">
                {question.options.map((option, index) => (
                  <button
                    // key에 문제 번호를 같이 넣어서 문제가 바뀌면 보기 버튼도 새로 만들어지게 함
                    key={`${current}-${index}`}
                    type="button"
                    role="radio"
                    aria-checked={selected === index}
                    className={getOptionClass(index)}
                    onClick={() => handleSelect(index)}
                    disabled={checked} // 확인 후에는 못 누르게
                  >
                    {/* 동그란 라디오 표시 */}
                    <span className="quiz-radio" aria-hidden="true" />
                    <span className="quiz-option-text">{option}</span>

                    {/* 확인 후: 정답 보기엔 초록 체크, 내가 고른 오답엔 빨간 X */}
                    {checked && index === question.answer && (
                      <CheckCircle2 className="quiz-mark" size={20} />
                    )}
                    {checked && index === selected && index !== question.answer && (
                      <XCircle className="quiz-mark" size={20} />
                    )}
                  </button>
                ))}
              </div>

              {/* 힌트 (펼쳤고, 아직 확인 전일 때만) */}
              {showHint && !checked && (
                <p className="quiz-hint">
                  <Lightbulb size={16} />
                  {question.hint}
                </p>
              )}

              {/* 정답 확인 후 결과 + 설명 */}
              {checked && (
                <div className={isCorrect ? "quiz-feedback correct" : "quiz-feedback wrong"}>
                  <strong>
                    {isCorrect ? (
                      <>
                        <CheckCircle2 size={18} /> 정답이에요!
                      </>
                    ) : (
                      <>
                        <XCircle size={18} /> 아쉬워요! 정답은 ‘{question.options[question.answer]}’
                      </>
                    )}
                  </strong>
                  <p>{question.explanation}</p>
                </div>
              )}

              {/* 아래 버튼 줄 */}
              <div className="quiz-actions">
                <button
                  type="button"
                  className="btn-outline"
                  // 누를 때마다 힌트 열기/닫기 (!: true↔false 뒤집기)
                  onClick={() => setShowHint(!showHint)}
                  disabled={checked} // 확인 후에는 힌트가 필요 없으니 비활성화
                >
                  <Lightbulb size={18} />
                  {/* 힌트가 열려 있고 아직 확인 전일 때만 "힌트 닫기" */}
                  {showHint && !checked ? "힌트 닫기" : "힌트 보기"}
                </button>

                {/* 확인 전에는 "정답 확인", 확인 후에는 "다음 문제" (마지막이면 "결과 보기") */}
                {checked ? (
                  <button type="button" className="btn-primary" onClick={handleNext}>
                    {current === total - 1 ? "결과 보기" : "다음 문제"}
                    <ArrowRight size={18} />
                  </button>
                ) : (
                  <button
                    type="button"
                    className="btn-primary"
                    onClick={handleCheck}
                    disabled={selected === null} // 보기를 골라야 누를 수 있음
                  >
                    정답 확인
                    <ArrowRight size={18} />
                  </button>
                )}
              </div>
            </div>
          )}

          {/* ===== 카드 아래: 현재 점수 + 진행 상황 ===== */}
          <div className="quiz-status">
            <div className="quiz-score">
              <span className="quiz-score-icon">
                <Trophy size={22} />
              </span>
              <div>
                <span className="quiz-status-label">현재 점수</span>
                <strong>{score}점</strong>
              </div>
            </div>

            <div className="quiz-dots-wrap">
              <span className="quiz-status-label">진행 상황</span>
              {/* 문제 번호 동그라미 10개: 맞음=초록, 틀림=빨강, 지금 문제=파랑 */}
              <ol className="quiz-dots">
                {results.map((result, index) => {
                  let dotClass = "quiz-dot";
                  if (result === true) dotClass += " correct";
                  else if (result === false) dotClass += " wrong";
                  if (index === current && !finished) dotClass += " current";

                  return (
                    <li key={index} className={dotClass}>
                      {index + 1}
                    </li>
                  );
                })}
              </ol>
            </div>
          </div>
        </section>
      </div>
    </div>
  );
}

export default QuizPage;
