import { API_BASE_URL as API_URL } from "../api/baseUrl";
// =============================================================
// QuizPage.jsx — 팀원 원본 디자인 유지 + 백엔드 데이터 연동 버전
// -------------------------------------------------------------
// 맞춤법 / 문법 퀴즈를 같은 화면에서 탭으로 바꿔 가며 풀 수 있음
// (category 값에 따라 백엔드에서 해당 종류의 문제만 가져옴)
//
// ※ 여기는 "연습용" 퀴즈라서 점수가 랭킹에 저장되지 않음
//   랭킹은 맞춤법 도전 모드(ChallengePage.jsx)에서만 기록됨
//
// 헤더 "퀴즈" 메뉴로 들어오는 화면
//   맨 위 큰 탭 [퀴즈 | 랭킹] → 랭킹을 누르면 랭킹 화면으로
//   그 아래 작은 탭 [맞춤법 | 문법] → 퀴즈 종류 바꾸기
//   문법을 고르면 그 아래 난이도 탭 [상 | 중 | 하]가 나옴
//     → 고른 난이도 문제 중에서 10문제(QUIZ_LEVEL_SIZE)를 랜덤으로 뽑아서 냄
//     → "다시 풀기"를 누르면 같은 난이도에서 10문제를 새로 뽑음
// =============================================================

import { useState, useEffect } from "react";
import {
  BookOpenCheck,
  ArrowRight,
  Trophy,
  CheckCircle2,
  XCircle,
  RotateCcw,
  Flame, // "도전 모드" 버튼 아이콘
  NotebookPen, // "오답노트" 안내·버튼 아이콘
} from "lucide-react";

import PageHero from "../components/PageHero";
// QuizSectionTabs: 맨 위 큰 탭 [퀴즈 | 랭킹]
import QuizSectionTabs from "../components/QuizSectionTabs";
// CategoryTabs: 퀴즈 안의 작은 탭 [맞춤법 | 문법]
import CategoryTabs from "../components/CategoryTabs";
// getQuizCategory: 종류별 제목·설명 등 설정 꺼내기
// QUIZ_LEVELS: 문법 난이도 탭 목록 [상 | 중 | 하] / getQuizLevel: 난이도 key로 이름("상") 찾기
// QUIZ_LEVEL_SIZE: 난이도 하나에서 낼 문제 수 (10)
import { getQuizCategory, getQuizLevel, QUIZ_LEVELS, QUIZ_LEVEL_SIZE } from "../data/quizCategories";
// 틀린 문제를 학습 화면의 오답노트에 담는 함수 (로그인했을 때만)
import { recordQuizAnswer } from "../api/learn";
import "./QuizPage.css";

const POINT_PER_QUESTION = 10;

// ----- ★ [추가] 배열을 무작위로 섞어주는 도우미 함수 -----
function shuffle(list) {
  const copy = [...list];
  for (let i = copy.length - 1; i > 0; i -= 1) {
    const j = Math.floor(Math.random() * (i + 1));
    [copy[i], copy[j]] = [copy[j], copy[i]];
  }
  return copy;
}

// ----- 문제 은행(pool)에서 이번에 풀 문제 고르기 -----
//  - 문제 순서와 보기 순서를 랜덤으로 섞음
//  - limit가 있으면(문법 난이도 퀴즈) 섞은 것 중 앞에서 limit개만 → "랜덤 10문제"
//    (문제가 10개보다 적으면 있는 만큼만 냄)
function pickQuestions(pool, limit) {
  const mixed = shuffle(pool);
  const picked = limit ? mixed.slice(0, limit) : mixed;
  return picked.map((q) => ({
    ...q,
    options: shuffle(q.options), // 보기 순서도 랜덤으로 섞음
  }));
}

// props
//  - category: 퀴즈 종류 ("spelling" = 맞춤법, "grammar" = 문법), 기본값 맞춤법
//  - onChangeCategory: [맞춤법 | 문법] 탭을 눌렀을 때 실행 (App이 종류를 바꾸고 이 화면을 새로 그림)
//  - level: 문법 퀴즈 난이도 ("hard" 상 / "medium" 중 / "easy" 하) → 문법일 때만 씀
//  - onChangeLevel: [상 | 중 | 하] 탭을 눌렀을 때 실행 (App이 난이도를 바꾸고 이 화면을 새로 그림)
//  - onChangeSection: [퀴즈 | 랭킹] 탭을 눌렀을 때 실행 ("ranking"이면 랭킹 화면으로)
//  - onGoChallenge: "도전 모드" 버튼을 눌렀을 때 실행 (랭킹에 기록이 남는 맞춤법 도전 모드로 이동)
//  - auth: 로그인 정보 → 로그인했으면 틀린 문제를 오답노트(학습 화면)에 담음 (안 했으면 담지 않음)
//  - onGoWrongNotes: 결과 화면 "오답노트 보기" 버튼 (학습 화면의 오답노트 탭으로)
function QuizPage({
  category = "spelling",
  onChangeCategory,
  level,
  onChangeLevel,
  onChangeSection,
  onGoChallenge,
  auth,
  onGoWrongNotes,
}) {
  const user = auth?.user; // 로그인한 회원 (없으면 undefined)
  // info: 지금 종류의 제목·설명·메모 문구 등 (data/quizCategories.js)
  const info = getQuizCategory(category);
  // levelInfo: 문법이면 지금 난이도 { key: "easy", label: "하" }, 맞춤법이면 null (난이도 없음)
  const levelInfo = category === "grammar" ? getQuizLevel(level) : null;
  // 화면·오답노트에 쓸 이름: "맞춤법" / "문법(하)"
  const quizLabel = levelInfo ? `${info.label}(${levelInfo.label})` : info.label;
  // 한 번에 낼 문제 수: 문법 난이도 퀴즈는 10문제, 맞춤법은 제한 없음(전부)
  const limit = levelInfo ? QUIZ_LEVEL_SIZE : null;
  // levelKey: 서버에 보낼 난이도 값 ("easy" 등, 맞춤법이면 null)
  const levelKey = levelInfo ? levelInfo.key : null;

  // pool: 서버에서 받은 문제 전체 ("다시 풀기" 때 여기서 다시 랜덤으로 뽑음)
  const [pool, setPool] = useState([]);
  // quizQuestions: 이번에 실제로 푸는 문제들 (pool에서 뽑아서 섞은 것)
  const [quizQuestions, setQuizQuestions] = useState([]);
  const [loading, setLoading] = useState(true);

  const [current, setCurrent] = useState(0);
  const [selected, setSelected] = useState(null);
  const [checked, setChecked] = useState(false);
  const [results, setResults] = useState([]);
  const [finished, setFinished] = useState(false);

  // 백엔드에서 퀴즈 목록 가져오기
  useEffect(() => {
    // category 값에 맞는 문제만 가져옴 (encodeURIComponent: 주소에 안전한 글자로 변환)
    // 문법이면 난이도도 같이 보내서 그 난이도 문제만 받음 (예: ...?category=grammar&level=easy)
    let url = `${API_URL}/api/quizzes/?category=${encodeURIComponent(category)}`;
    if (levelKey) url += `&level=${encodeURIComponent(levelKey)}`;

    fetch(url)
      .then((res) => res.json())
      .then((data) => {
        // 서버가 에러 모양({ detail: ... })을 보내도 화면이 깨지지 않게 배열일 때만 씀
        const list = Array.isArray(data) ? data : [];
        // ★ 가져온 문제를 섞어서 고름 (문법 난이도 퀴즈는 그중 10문제만)
        const randomized = pickQuestions(list, limit);

        setPool(list);
        setQuizQuestions(randomized);
        setResults(Array(randomized.length).fill(null));
        setLoading(false);
      })
      .catch((err) => {
        console.error("퀴즈 로딩 실패:", err);
        setLoading(false);
      });
    // [category, levelKey, limit]: 종류·난이도가 바뀌면 다시 불러옴
    // (App에서 key로 화면 자체를 새로 만들어서, 실제로는 처음 한 번만 실행됨)
  }, [category, levelKey, limit]);

  // 맨 위 탭 (불러오는 중 / 문제 없음 / 문제 풀이 화면 모두에서 같이 보여주려고 변수로 만듦)
  // 위: 큰 탭 [퀴즈 | 랭킹] (지금은 퀴즈 쪽) / 가운데: 작은 탭 [맞춤법 | 문법]
  // 아래: 문법일 때만 난이도 탭 [상 | 중 | 하]
  const tabs = (
    <div className="quiz-tabs-row">
      <QuizSectionTabs value="quiz" onChange={onChangeSection} />
      <CategoryTabs value={category} onChange={onChangeCategory} variant="sub" />
      {levelInfo && (
        <CategoryTabs
          value={levelInfo.key}
          onChange={onChangeLevel}
          variant="level"
          items={QUIZ_LEVELS}
          ariaLabel="문법 난이도"
        />
      )}
    </div>
  );

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
          <h2>등록된 {quizLabel} 퀴즈가 없습니다.</h2>
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

    // 로그인했으면 오답노트에 반영 (틀리면 담고, 예전에 틀린 문제를 맞히면 해결 처리)
    // 저장이 실패해도 퀴즈는 계속 풀 수 있게 에러는 조용히 넘김
    if (user) {
      recordQuizAnswer(user, {
        quiz: question,
        category,
        categoryLabel: quizLabel, // 오답노트에 "문법(하) 퀴즈"처럼 난이도까지 보이게
        chosen: question.options[selected],
      }).catch(() => {});
    }
  };

  const handleNext = () => {
    if (current === total - 1) {
      setFinished(true); // 연습용이라 랭킹 저장은 안 함 (랭킹은 도전 모드에서만)
      return;
    }
    setCurrent(current + 1);
    setSelected(null);
    setChecked(false);
  };

  const handleRestart = () => {
    // ★ 다시 풀기: 전체 문제(pool)에서 다시 랜덤으로 뽑음
    //   → 문법 난이도 퀴즈는 문제가 10개보다 많으면 매번 다른 10문제가 나옴
    const randomized = pickQuestions(pool, limit);
    setQuizQuestions(randomized);
    setCurrent(0);
    setSelected(null);
    setChecked(false);
    setResults(Array(randomized.length).fill(null));
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

        {/* [퀴즈 | 랭킹] + [맞춤법 | 문법] 탭 (가운데 정렬) */}
        {tabs}

        <section className="panel quiz-card">
          <div className="quiz-head">
            <h2 className="quiz-head-title">
              <BookOpenCheck size={24} />
              {info.title}
              {/* 문법이면 지금 난이도를 작은 배지로 (예: 난이도 하) */}
              {levelInfo && <span className="quiz-level-badge">난이도 {levelInfo.label}</span>}
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

              {/* 연습 퀴즈 점수는 랭킹에 안 남는다는 안내 */}
              <p className="quiz-result-note">
                연습 퀴즈 점수는 랭킹에 남지 않아요. 랭킹은 맞춤법 도전 모드 기록으로 정해져요.
              </p>
              {/* 틀린 문제 안내: 로그인했으면 오답노트에 담겼고, 안 했으면 로그인하면 담긴다고 알려줌 */}
              {results.some((result) => result === false) && (
                <p className="quiz-result-note">
                  {user
                    ? "틀린 문제는 글쓰기 연습 → 오답노트에 담아 두었어요."
                    : "로그인하면 틀린 문제가 오답노트에 담겨요."}
                </p>
              )}

              <div className="quiz-result-actions">
                <button type="button" className="btn-outline" onClick={handleRestart}>
                  <RotateCcw size={18} />
                  다시 풀기
                </button>
                {/* 로그인했고 틀린 문제가 있으면 오답노트로 바로 가기 */}
                {user && onGoWrongNotes && results.some((result) => result === false) && (
                  <button type="button" className="btn-outline" onClick={onGoWrongNotes}>
                    <NotebookPen size={18} />
                    오답노트 보기
                  </button>
                )}
                {/* onGoChallenge가 있을 때만 버튼 표시 */}
                {onGoChallenge && (
                  <button type="button" className="btn-primary" onClick={onGoChallenge}>
                    <Flame size={18} />
                    도전 모드
                  </button>
                )}
              </div>
            </div>
          ) : (
            <div className="quiz-body">
              <span className="quiz-badge">문제 {current + 1}</span>

              {/* 문제 문장 자체에 이미 '____' 따옴표가 들어 있어서 바깥 따옴표는 붙이지 않음
                  (붙이면 ‘내일 다시 연락 ‘할게’.’ 처럼 따옴표가 겹쳐 보임) */}
              <h3 className="quiz-question">
                {before}
                <span className={checked ? "quiz-blank filled" : "quiz-blank"}>
                  {checked ? question.answer : ""}
                </span>
                {after}
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
                  {/* 틀렸고 로그인했으면: 오답노트에 담았다는 안내 */}
                  {!isCorrect && user && (
                    <p className="quiz-wrong-saved">
                      <NotebookPen size={14} /> 오답노트에 담았어요
                    </p>
                  )}
                </div>
              )}

              {/* 아래 버튼: 정답 확인 → 다음 문제(마지막이면 결과 보기)
                  ※ 예전에 있던 "힌트 보기" 버튼은 시험처럼 풀게 하려고 없앰
                     (문제 데이터에 hint가 들어 있어도 화면에는 안 보여 줌) */}
              <div className="quiz-actions">
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