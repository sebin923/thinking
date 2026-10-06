// =============================================================
// QuizPage.jsx — 팀원 원본 디자인 유지 + 백엔드 데이터 연동 버전
// =============================================================

import { useState, useEffect } from "react";
import {
  BookOpenCheck,
  Lightbulb,
  ArrowRight,
  Trophy,
  CheckCircle2,
  XCircle,
  RotateCcw,
} from "lucide-react";

import PageHero from "../components/PageHero";
import "./QuizPage.css";

const POINT_PER_QUESTION = 10;

function QuizPage() {
  const [quizQuestions, setQuizQuestions] = useState([]);
  const [loading, setLoading] = useState(true);

  const [current, setCurrent] = useState(0);
  const [selected, setSelected] = useState(null);
  const [checked, setChecked] = useState(false);
  const [showHint, setShowHint] = useState(false);
  const [results, setResults] = useState([]);
  const [finished, setFinished] = useState(false);

  // 백엔드에서 퀴즈 목록 가져오기
  useEffect(() => {
    fetch("http://localhost:8000/api/quizzes/?category=spelling")
      .then((res) => res.json())
      .then((data) => {
        setQuizQuestions(data);
        setResults(Array(data.length).fill(null));
        setLoading(false);
      })
      .catch((err) => {
        console.error("퀴즈 로딩 실패:", err);
        setLoading(false);
      });
  }, []);

  if (loading) {
    return (
      <div className="sub-page">
        <div className="sub-page-inner" style={{ textAlign: "center", padding: "50px" }}>
          <h2>퀴즈를 불러오는 중입니다...</h2>
        </div>
      </div>
    );
  }

  if (quizQuestions.length === 0) {
    return (
      <div className="sub-page">
        <div className="sub-page-inner" style={{ textAlign: "center", padding: "50px" }}>
          <h2>등록된 퀴즈가 없습니다.</h2>
        </div>
      </div>
    );
  }

  const question = quizQuestions[current];
  const total = quizQuestions.length;
  const score = results.filter((result) => result === true).length * POINT_PER_QUESTION;
  const progress = ((current + 1) / total) * 100;
  
  // 백엔드 데이터의 answer 문자열과 비교
  const isCorrect = question && selected !== null && question.options[selected] === question.answer;

  const handleSelect = (index) => {
    if (checked) return;
    setSelected(index);
  };

  const handleCheck = () => {
    if (selected === null) return;
    setChecked(true);
    const next = [...results];
    next[current] = isCorrect;
    setResults(next);
  };

  // 랭킹 점수 백엔드 전송
  const sendRankingToBackend = (finalScore) => {
    fetch("http://localhost:8000/api/quizzes/rankings", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        user_id: 1,
        category: "spelling",
        score: finalScore,
      }),
    }).catch((err) => console.error("랭킹 저장 실패:", err));
  };

  const handleNext = () => {
    if (current === total - 1) {
      setFinished(true);
      sendRankingToBackend(score);
      return;
    }
    setCurrent(current + 1);
    setSelected(null);
    setChecked(false);
    setShowHint(false);
  };

  const handleRestart = () => {
    setCurrent(0);
    setSelected(null);
    setChecked(false);
    setShowHint(false);
    setResults(Array(total).fill(null));
    setFinished(false);
  };

  const getOptionClass = (index) => {
    let className = "quiz-option";
    if (!checked) {
      if (index === selected) className += " selected";
    } else {
      if (question.options[index] === question.answer) className += " correct";
      else if (index === selected) className += " wrong";
    }
    return className;
  };

  const getResultMessage = () => {
    if (score === 100) return "완벽해요! 맞춤법 박사네요 🎉";
    if (score >= 70) return "아주 잘했어요! 조금만 더 연습하면 완벽해요.";
    if (score >= 40) return "좋은 시작이에요. 틀린 문제를 다시 확인해 봐요.";
    return "괜찮아요, 연습할수록 실력이 늘어요!";
  };

  // 팀원 원본의 문장 분할 방식 유지
  const [before, after] = question.question ? question.question.split("____") : ["", ""];

  return (
    <div className="sub-page">
      <div className="sub-page-inner">
        <PageHero
          eyebrow="글쓰기가 더 쉬워지는 작은 연습"
          title="맞춤법 퀴즈"
          description={
            "문장을 바르게 쓰는 연습을 통해\n더 정확하고 자연스러운 글을 작성할 수 있어요."
          }
          memoText={"조금 더\n바른 표현을\n위해 :)"}
          memoVariant="notebook"
        />

        <section className="panel quiz-card">
          <div className="quiz-head">
            <h2 className="quiz-head-title">
              <BookOpenCheck size={24} />
              맞춤법 퀴즈
            </h2>
            {!finished && (
              <div className="quiz-progress">
                <span>
                  {current + 1} / {total}
                </span>
                <div className="quiz-progress-bar">
                  <div className="quiz-progress-fill" style={{ width: `${progress}%` }} />
                </div>
              </div>
            )}
          </div>

          {finished ? (
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
            <div className="quiz-body">
              <span className="quiz-badge">문제 {current + 1}</span>

              <h3 className="quiz-question">
                ‘{before}
                <span className={checked ? "quiz-blank filled" : "quiz-blank"}>
                  {checked ? question.answer : ""}
                </span>
                {after}’
                <br />
                빈칸에 들어갈 올바른 표현은 무엇일까요?
              </h3>

              <div className="quiz-options" role="radiogroup" aria-label="보기">
                {question.options.map((option, index) => (
                  <button
                    key={`${current}-${index}`}
                    type="button"
                    role="radio"
                    aria-checked={selected === index}
                    className={getOptionClass(index)}
                    onClick={() => handleSelect(index)}
                    disabled={checked}
                  >
                    <span className="quiz-radio" aria-hidden="true" />
                    <span className="quiz-option-text">{option}</span>

                    {checked && option === question.answer && (
                      <CheckCircle2 className="quiz-mark" size={20} />
                    )}
                    {checked && index === selected && option !== question.answer && (
                      <XCircle className="quiz-mark" size={20} />
                    )}
                  </button>
                ))}
              </div>

              {showHint && !checked && question.hint && (
                <p className="quiz-hint">
                  <Lightbulb size={16} />
                  {question.hint}
                </p>
              )}

              {checked && (
                <div className={isCorrect ? "quiz-feedback correct" : "quiz-feedback wrong"}>
                  <strong>
                    {isCorrect ? (
                      <>
                        <CheckCircle2 size={18} /> 정답이에요!
                      </>
                    ) : (
                      <>
                        <XCircle size={18} /> 아쉬워요! 정답은 ‘{question.answer}’
                      </>
                    )}
                  </strong>
                  <p>{question.explanation}</p>
                </div>
              )}

              <div className="quiz-actions">
                <button
                  type="button"
                  className="btn-outline"
                  onClick={() => setShowHint(!showHint)}
                  disabled={checked}
                >
                  <Lightbulb size={18} />
                  {showHint && !checked ? "힌트 닫기" : "힌트 보기"}
                </button>

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
                    disabled={selected === null}
                  >
                    정답 확인
                    <ArrowRight size={18} />
                  </button>
                )}
              </div>
            </div>
          )}

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