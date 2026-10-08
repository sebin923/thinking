// =============================================================
// QuizPage.jsx — 팀원 원본 디자인 유지 + 백엔드 데이터 연동 버전
// -------------------------------------------------------------
// 맞춤법 / 문법 퀴즈를 같은 화면에서 탭으로 바꿔 가며 풀 수 있음
// (category 값에 따라 백엔드에서 해당 종류의 문제만 가져옴)
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
  Medal, // "랭킹 보기" 버튼 아이콘
} from "lucide-react";

import PageHero from "../components/PageHero";
// CategoryTabs: 맞춤법 | 문법 탭 버튼
import CategoryTabs from "../components/CategoryTabs";
// getQuizCategory: 종류별 제목·설명 등 설정 꺼내기
import { getQuizCategory } from "../data/quizCategories";
import "./QuizPage.css";

const POINT_PER_QUESTION = 10;

// props
//  - user: 로그인한 사용자 정보 (App이 넘겨줌, 로그인 안 했으면 undefined)
//    → 랭킹 점수를 저장할 때 이 사람의 user_id로 저장함
//  - category: 퀴즈 종류 ("spelling" = 맞춤법, "grammar" = 문법), 기본값 맞춤법
//  - onChangeCategory: 탭을 눌렀을 때 실행 (App이 종류를 바꾸고 이 화면을 새로 그림)
//  - onGoRanking: "랭킹 보기" 버튼을 눌렀을 때 실행
function QuizPage({ user, category = "spelling", onChangeCategory, onGoRanking }) {
  // info: 지금 종류의 제목·설명·메모 문구 등 (data/quizCategories.js)
  const info = getQuizCategory(category);

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
    // category 값에 맞는 문제만 가져옴 (encodeURIComponent: 주소에 안전한 글자로 변환)
    fetch(`http://localhost:8000/api/quizzes/?category=${encodeURIComponent(category)}`)
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
    // [category]: 종류가 바뀌면 다시 불러옴
    // (App에서 key={category}로 화면 자체를 새로 만들어서, 실제로는 처음 한 번만 실행됨)
  }, [category]);

  // 맨 위 탭 (불러오는 중 / 문제 없음 / 문제 풀이 화면 모두에서 같이 보여주려고 변수로 만듦)
  const tabs = <CategoryTabs value={category} onChange={onChangeCategory} />;

  if (loading) {
    return (
      <div className="sub-page">
        <div className="sub-page-inner" style={{ textAlign: "center", padding: "50px" }}>
          {tabs}
          <h2>퀴즈를 불러오는 중입니다...</h2>
        </div>
      </div>
    );
  }

  if (quizQuestions.length === 0) {
    return (
      <div className="sub-page">
        <div className="sub-page-inner" style={{ textAlign: "center", padding: "50px" }}>
          {tabs}
          <h2>등록된 {info.label} 퀴즈가 없습니다.</h2>
          {/* 백엔드 폴더에서 python insert_quiz_data.py 를 실행하면 문제가 들어감 */}
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
    // 로그인 안 했으면 누구 점수인지 모르니까 랭킹에 저장하지 않음
    if (!user) return;

    fetch("http://localhost:8000/api/quizzes/rankings", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        user_id: user.user_id, // 로그인한 사람의 번호 (예전엔 1로 고정돼 있었음)
        category, // 지금 푼 종류로 저장 (맞춤법 / 문법 랭킹이 따로 집계됨)
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

  // 결과 문구: 문제 수가 바뀌어도 맞게 "점수 비율(%)"로 판단
  // (예전엔 100점 기준이라 5문제(최대 50점)일 때는 만점 문구가 안 나왔음)
  const getResultMessage = () => {
    const percent = (score / (total * POINT_PER_QUESTION)) * 100;
    if (percent === 100) return info.perfectMessage;
    if (percent >= 70) return "아주 잘했어요! 조금만 더 연습하면 완벽해요.";
    if (percent >= 40) return "좋은 시작이에요. 틀린 문제를 다시 확인해 봐요.";
    return "괜찮아요, 연습할수록 실력이 늘어요!";
  };

  // 팀원 원본의 문장 분할 방식 유지
  const [before, after] = question.question ? question.question.split("____") : ["", ""];

  return (
    <div className="sub-page">
      <div className="sub-page-inner">
        <PageHero
          eyebrow="글쓰기가 더 쉬워지는 작은 연습"
          title={info.title}
          description={info.description}
          memoText={info.memoText}
          memoVariant="notebook"
        />

        {/* 맞춤법 | 문법 탭 (가운데 정렬) */}
        <div className="quiz-tabs-row">{tabs}</div>

        <section className="panel quiz-card">
          <div className="quiz-head">
            <h2 className="quiz-head-title">
              <BookOpenCheck size={24} />
              {info.title}
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

              {/* 로그인 안 했으면 랭킹에 안 남는다는 안내 */}
              {!user && (
                <p className="quiz-result-note">로그인하면 점수가 랭킹에 기록돼요.</p>
              )}

              <div className="quiz-result-actions">
                <button type="button" className="btn-outline" onClick={handleRestart}>
                  <RotateCcw size={18} />
                  다시 풀기
                </button>
                {/* onGoRanking이 있을 때만 버튼 표시 */}
                {onGoRanking && (
                  <button type="button" className="btn-primary" onClick={onGoRanking}>
                    <Medal size={18} />
                    랭킹 보기
                  </button>
                )}
              </div>
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
                  // 정답 확인 후이거나, 이 문제에 힌트가 없으면 비활성화
                  disabled={checked || !question.hint}
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