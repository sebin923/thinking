// =============================================================
// ChallengePage.jsx — 맞춤법 도전 모드 (랭킹 게임)
// -------------------------------------------------------------
// 규칙: 맞춤법 문제를 하나씩 풀다가 "처음 틀리는 순간" 게임 끝!
//       연속으로 맞힌 문제 수 = 점수 → 이 점수로 랭킹 순위가 정해짐
//
// 화면은 3단계로 바뀜 (phase 상태값)
//   "ready"    : 시작 전 안내 화면 (규칙 + 도전 시작 버튼)
//   "playing"  : 문제 푸는 중
//   "gameover" : 틀렸거나, 모든 문제를 다 맞혀서 끝난 화면
//
// 일반 퀴즈(QuizPage)는 연습용이라 랭킹에 안 들어가고,
// 랭킹 기록은 오직 이 도전 모드에서만 저장됨 (category = "spelling")
// =============================================================

import { useState, useEffect, useRef } from "react";
import {
  Flame,
  Swords,
  CheckCircle2,
  XCircle,
  RotateCcw,
  Medal,
  Trophy,
  Heart,
  Zap,
  ListChecks,
  Clock,
} from "lucide-react";

import PageHero from "../components/PageHero";
// 문제 카드·보기 버튼 모양은 일반 퀴즈와 똑같이 쓰려고 QuizPage.css를 같이 불러옴
import "./QuizPage.css";
import "./ChallengePage.css";

// 백엔드 주소 (frontend/.env의 VITE_API_URL이 있으면 그 값, 없으면 기본값)
const API_URL = import.meta.env.VITE_API_URL || "http://127.0.0.1:8000";

// 랭킹에 저장할 종류 → 랭킹은 맞춤법만 있으니까 고정
const CATEGORY = "spelling";

// 정답을 맞힌 뒤 다음 문제로 자동으로 넘어가기까지 기다리는 시간 (밀리초, 1000 = 1초)
const NEXT_DELAY = 900;

// ★ [추가] 문항별 제한 시간 (초 단위, 예: 5초)
const QUESTION_TIME_LIMIT = 5;

// ----- 도우미 함수 -----

// 배열 섞기 (피셔-예이츠 셔플: 뒤에서부터 하나씩 무작위 자리와 바꾸는 방법)
// 원본을 망가뜨리지 않으려고 [...list]로 복사해서 섞음
function shuffle(list) {
  const copy = [...list];
  for (let i = copy.length - 1; i > 0; i -= 1) {
    const j = Math.floor(Math.random() * (i + 1)); // 0 ~ i 중 무작위 번호
    [copy[i], copy[j]] = [copy[j], copy[i]]; // 두 칸 바꾸기
  }
  return copy;
}

// 문제 문장을 빈칸 앞 / 뒤로 나누기
// DB 문제에는 ‘____’처럼 작은따옴표가 붙어 있는 것도 있어서, 따옴표는 빼고 나눔
// (정규식 [‘’']? : 따옴표가 있어도 되고 없어도 됨)
function splitQuestion(text = "") {
  const [before = "", after = ""] = text.replace(/[‘’']?____[‘’']?/, "____").split("____");
  return { before, after };
}

// 점수(연속 정답 수)에 따라 한마디
function getComment(streak, cleared) {
  if (cleared) return "모든 문제를 정복했어요! 진짜 맞춤법 마스터 👑";
  if (streak >= 20) return "놀라워요! 맞춤법 고수가 나타났다 🔥";
  if (streak >= 10) return "대단해요! 두 자릿수 연속 정답이에요 🎉";
  if (streak >= 5) return "좋아요! 감이 잡히고 있어요.";
  if (streak >= 1) return "좋은 출발이에요. 다시 도전하면 더 갈 수 있어요!";
  return "첫 문제부터 아쉬워요. 다시 한번 도전해 봐요!";
}

// props
//  - user: 로그인한 사용자 (로그인 안 했으면 undefined) → 있을 때만 랭킹에 저장
//  - onGoRanking: "랭킹 보기" 버튼
//  - onGoLogin: "로그인하기" 버튼 (로그인 안 했을 때 안내)
function ChallengePage({ user, onGoRanking, onGoLogin }) {
  // ----- 상태값 -----
  const [allQuestions, setAllQuestions] = useState([]); // 서버에서 받은 맞춤법 문제 전부
  const [loading, setLoading] = useState(true); // 문제 불러오는 중?
  const [loadError, setLoadError] = useState(""); // 불러오기 실패 문구

  const [phase, setPhase] = useState("ready"); // "ready" | "playing" | "gameover"
  const [deck, setDeck] = useState([]); // 이번 판에 나올 문제 순서 (섞인 것)
  const [index, setIndex] = useState(0); // 지금 몇 번째 문제인지 (0부터)
  const [streak, setStreak] = useState(0); // 연속 정답 수 = 점수
  const [selected, setSelected] = useState(null); // 고른 보기 글자 (아직 안 골랐으면 null)
  const [cleared, setCleared] = useState(false); // 모든 문제를 다 맞혔는지

  // ★ [추가] 문항별 남은 제한 시간 (초)
  const [timeLeft, setTimeLeft] = useState(QUESTION_TIME_LIMIT);

  // 랭킹 저장 상태: "idle"(아무것도 안 함) | "saving" | "saved" | "skipped"(0점이라 저장 안 함) | "error"
  const [saveState, setSaveState] = useState("idle");

  // timerRef: 다음 문제로 넘어가는 예약(setTimeout)을 기억해 두는 곳
  const timerRef = useRef(null);
  
  // ★ [추가] 초읽기 타이머(setInterval)를 담아둘 ref
  const questionTimerRef = useRef(null);

  // 총 소요 시간 측정용 ref
  const startTimeRef = useRef(null);

  // ----- 맞춤법 문제 불러오기 (화면이 처음 열릴 때 한 번) -----
  useEffect(() => {
    let ignore = false; // 응답 오기 전에 화면을 떠나면 결과 무시

    fetch(`${API_URL}/api/quizzes/?category=${CATEGORY}`)
      .then((res) => {
        if (!res.ok) throw new Error(`응답 실패: ${res.status}`);
        return res.json();
      })
      .then((data) => {
        if (ignore) return;
        setAllQuestions(data);
        setLoading(false);
      })
      .catch((err) => {
        if (ignore) return;
        console.error("도전 모드 문제 불러오기 실패:", err);
        setLoadError("문제를 불러오지 못했어요. 백엔드가 켜져 있는지 확인해 주세요.");
        setLoading(false);
      });

    // 정리 함수: 화면을 떠날 때 실행 → 응답 무시 + 예약해 둔 타이머 취소
    return () => {
      ignore = true;
      clearTimeout(timerRef.current);
      clearInterval(questionTimerRef.current);
    };
  }, []);

  // ----- 랭킹 저장 (총 소요 시간 elapsed_time 함께 전송) -----
  const saveRecord = (finalStreak) => {
    if (!user) return; // 로그인 안 했으면 누구 기록인지 몰라서 저장 안 함
    if (finalStreak === 0) {
      setSaveState("skipped"); // 0문제는 순위에 의미가 없으니 저장 안 함
      return;
    }

    const elapsedSeconds = startTimeRef.current 
      ? Number(((Date.now() - startTimeRef.current) / 1000).toFixed(2)) 
      : 0.0;

    setSaveState("saving");
    fetch(`${API_URL}/api/quizzes/rankings/survival`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ 
        user_id: user.user_id, 
        category: CATEGORY, 
        score: finalStreak,
        elapsed_time: elapsedSeconds 
      }),
    })
      .then((res) => {
        if (!res.ok) throw new Error(`응답 실패: ${res.status}`);
        setSaveState("saved");
      })
      .catch((err) => {
        console.error("랭킹 저장 실패:", err);
        setSaveState("error");
      });
  };

  // ----- 게임 끝내기 -----
  const finishGame = (finalStreak, isCleared) => {
    clearInterval(questionTimerRef.current); // 타이머 정지
    setCleared(isCleared);
    setPhase("gameover");
    saveRecord(finalStreak);
  };

  // ----- ★ [추가] 문제별 초읽기 타이머 실행 함수 -----
  useEffect(() => {
    if (phase !== "playing") return;

    // 새 문제가 나올 때마다 남은 시간 초기화
    setTimeLeft(QUESTION_TIME_LIMIT);
    clearInterval(questionTimerRef.current);

    questionTimerRef.current = setInterval(() => {
      setTimeLeft((prev) => {
        if (prev <= 1) {
          // 시간이 다 되면(=0초) 자동으로 오답 처리 후 게임 종료
          clearInterval(questionTimerRef.current);
          if (selected === null) {
            setSelected("시간초과"); // 시간 초과 표시용
            timerRef.current = setTimeout(() => finishGame(streak, false), NEXT_DELAY);
          }
          return 0;
        }
        return prev - 1;
      });
    }, 1000);

    return () => clearInterval(questionTimerRef.current);
  }, [index, phase]);

  // ----- 도전 시작 (처음 시작 + 다시 도전 둘 다) -----
  const handleStart = () => {
    clearTimeout(timerRef.current);
    clearInterval(questionTimerRef.current);
    
    const shuffled = shuffle(allQuestions).map((q) => ({ ...q, options: shuffle(q.options) }));
    setDeck(shuffled);
    setIndex(0);
    setStreak(0);
    setSelected(null);
    setCleared(false);
    setSaveState("idle");
    
    startTimeRef.current = Date.now();
    setPhase("playing");
  };

  // ----- 보기 고르기 (고르는 순간 바로 채점) -----
  const handleSelect = (option) => {
    if (selected !== null) return; // 이미 골랐으면 무시 (두 번 누르기 방지)
    clearInterval(questionTimerRef.current); // 답을 고르면 타이머 멈춤
    setSelected(option);

    const question = deck[index];

    if (option !== question.answer) {
      // ✗ 틀림 → 지금까지의 연속 정답 수로 바로 게임 끝
      timerRef.current = setTimeout(() => finishGame(streak, false), NEXT_DELAY);
      return;
    }

    // ○ 정답 → 연속 기록 +1
    const nextStreak = streak + 1;
    setStreak(nextStreak);

    // 마지막 문제까지 다 맞혔으면 "모든 문제 정복"으로 끝
    if (index === deck.length - 1) {
      timerRef.current = setTimeout(() => finishGame(nextStreak, true), NEXT_DELAY);
      return;
    }

    // 아니면 잠깐 뒤에 다음 문제로
    timerRef.current = setTimeout(() => {
      setIndex((i) => i + 1);
      setSelected(null);
    }, NEXT_DELAY);
  };

  // 보기 버튼 모양 (QuizPage.css의 correct / wrong 클래스 재사용)
  const getOptionClass = (option, answer) => {
    let className = "quiz-option";
    if (selected === null) return className;
    if (option === answer) className += " correct"; // 정답 보기는 초록
    else if (option === selected) className += " wrong"; // 내가 고른 오답은 빨강
    return className;
  };

  // ================= 화면 그리기 =================

  // 페이지 맨 위 제목 영역 (모든 단계에서 같이 씀)
  const hero = (
    <PageHero
      eyebrow="틀리면 끝! 한 번에 몇 문제까지?"
      title="맞춤법 도전 모드"
      description={"맞춤법 문제를 틀릴 때까지 계속 풀어요.\n연속으로 맞힌 문제 수가 그대로 랭킹 점수가 돼요."}
      memoText={"한 문제\n한 문제\n신중하게!"}
      memoVariant="note"
    />
  );

  // 불러오는 중 / 실패 / 문제 없음
  if (loading || loadError || allQuestions.length === 0) {
    return (
      <div className="sub-page">
        <div className="sub-page-inner">
          {hero}
          <section className="panel quiz-card challenge-message">
            {loading && <p>문제를 불러오는 중이에요...</p>}
            {loadError && <p>{loadError}</p>}
            {!loading && !loadError && (
              <p>등록된 맞춤법 문제가 없어요.</p>
            )}
          </section>
        </div>
      </div>
    );
  }

  // ----- 1. 시작 전 안내 -----
  if (phase === "ready") {
    return (
      <div className="sub-page">
        <div className="sub-page-inner">
          {hero}
          <section className="panel quiz-card challenge-ready">
            <div className="challenge-ready-icon">
              <Swords size={40} strokeWidth={1.6} />
            </div>
            <h2>도전 규칙</h2>

            {/* 규칙 3줄 */}
            <ul className="challenge-rules">
              <li>
                <Heart size={18} />
                <span>
                  목숨은 <strong>단 하나</strong>! 한 문제라도 틀리면 바로 끝나요.
                </span>
              </li>
              <li>
                <Zap size={18} />
                <span>보기를 누르는 순간 바로 채점돼요. 신중하게 골라 주세요.</span>
              </li>
              <li>
                <Clock size={18} />
                <span>
                  문제당 <strong>{QUESTION_TIME_LIMIT}초</strong>의 제한 시간이 있어요!
                </span>
              </li>
            </ul>

            {/* 로그인 안 했으면 기록이 안 남는다는 안내 */}
            {!user && (
              <p className="challenge-login-note">
                지금은 로그인하지 않아서 기록이 랭킹에 남지 않아요.{" "}
                {onGoLogin && (
                  <button type="button" className="challenge-text-link" onClick={onGoLogin}>
                    로그인하기
                  </button>
                )}
              </p>
            )}

            <div className="quiz-result-actions">
              {onGoRanking && (
                <button type="button" className="btn-outline" onClick={onGoRanking}>
                  <Medal size={18} />
                  랭킹 보기
                </button>
              )}
              <button type="button" className="btn-primary" onClick={handleStart}>
                <Flame size={18} />
                도전 시작
              </button>
            </div>
          </section>
        </div>
      </div>
    );
  }

  // ----- 3. 게임 끝 -----
  if (phase === "gameover") {
    const missed = cleared ? null : deck[index];

    return (
      <div className="sub-page">
        <div className="sub-page-inner">
          {hero}
          <section className="panel quiz-card">
            <div className="quiz-result">
              <div className="quiz-result-trophy">
                <Trophy size={44} strokeWidth={1.6} />
              </div>
              <p className="quiz-result-label">{cleared ? "모든 문제 정복!" : "연속 정답"}</p>
              <p className="quiz-result-score">
                {streak}
                <span>문제</span>
              </p>
              <p className="quiz-result-message">{getComment(streak, cleared)}</p>

              {/* 틀린 문제 다시 보기 */}
              {missed && (
                <div className="quiz-feedback wrong challenge-missed">
                  <strong>
                    <XCircle size={18} /> 정답은 ‘{missed.answer}’ (내가 고른 답: ‘{selected === "시간초과" ? "시간 초과" : selected}’)
                  </strong>
                  <p>{missed.explanation}</p>
                </div>
              )}

              {/* 랭킹 저장 결과 안내 */}
              {!user && <p className="quiz-result-note">로그인하면 기록이 랭킹에 남아요.</p>}
              {saveState === "saving" && <p className="quiz-result-note">기록을 저장하는 중이에요...</p>}
              {saveState === "saved" && (
                <p className="quiz-result-note challenge-saved">랭킹에 기록이 저장됐어요!</p>
              )}
              {saveState === "skipped" && (
                <p className="quiz-result-note">0문제 기록은 랭킹에 남지 않아요.</p>
              )}
              {saveState === "error" && (
                <p className="quiz-result-note challenge-error">
                  기록 저장에 실패했어요. 백엔드가 켜져 있는지 확인해 주세요.
                </p>
              )}

              <div className="quiz-result-actions">
                <button type="button" className="btn-outline" onClick={handleStart}>
                  <RotateCcw size={18} />
                  다시 도전
                </button>
                {onGoRanking && (
                  <button type="button" className="btn-primary" onClick={onGoRanking}>
                    <Medal size={18} />
                    랭킹 보기
                  </button>
                )}
              </div>
            </div>
          </section>
        </div>
      </div>
    );
  }

  // ----- 2. 문제 푸는 중 -----
  const question = deck[index];
  const { before, after } = splitQuestion(question.question);
  const answered = selected !== null; // 이 문제에 답을 골랐는지
  const isCorrect = selected === question.answer;

  return (
    <div className="sub-page">
      <div className="sub-page-inner">
        {hero}
        <section className="panel quiz-card">
          {/* 머리: 왼쪽 문제 번호 / 오른쪽 초읽기 타이머 및 연속 정답 수 */}
          <div className="quiz-head" style={{ display: "flex", justifyContent: "space-between", alignItems: "center" }}>
            <h2 className="quiz-head-title">
              <Swords size={24} />
              {index + 1}번째 문제
            </h2>
            
            <div style={{ display: "flex", alignItems: "center", gap: "12px" }}>
              {/* ★ [추가] 남은 제한 시간 표시 (3초 이하일 때 빨간색 강조) */}
              <div 
                style={{ 
                  display: "flex", 
                  alignItem: "center", 
                  gap: "4px", 
                  fontWeight: "700", 
                  color: timeLeft <= 2 ? "#e74c3c" : "var(--navy)",
                  background: timeLeft <= 2 ? "#fde8e8" : "#f0f5fa",
                  padding: "4px 10px",
                  borderRadius: "20px",
                  fontSize: "14px",
                  transition: "all 0.2s"
                }}
              >
                <Clock size={16} />
                <span>{timeLeft}초</span>
              </div>

              <div className="challenge-streak" key={streak}>
                <Flame size={20} />
                <strong>{streak}</strong>
                <span>연속</span>
              </div>
            </div>
          </div>

          <div className="quiz-body">
            <h3 className="quiz-question">
              {before}
              <span className={answered ? "quiz-blank filled" : "quiz-blank"}>
                {answered ? question.answer : ""}
              </span>
              {after}
              <br />
              빈칸에 들어갈 올바른 표현은 무엇일까요?
            </h3>

            <div className="quiz-options" role="radiogroup" aria-label="보기">
              {question.options.map((option) => (
                <button
                  key={`${index}-${option}`}
                  type="button"
                  role="radio"
                  aria-checked={selected === option}
                  className={getOptionClass(option, question.answer)}
                  onClick={() => handleSelect(option)}
                  disabled={answered}
                >
                  <span className="quiz-radio" aria-hidden="true" />
                  <span className="quiz-option-text">{option}</span>
                  {answered && option === question.answer && (
                    <CheckCircle2 className="quiz-mark" size={20} />
                  )}
                  {answered && option === selected && option !== question.answer && (
                    <XCircle className="quiz-mark" size={20} />
                  )}
                </button>
              ))}
            </div>

            {/* 채점 결과 한 줄 */}
            <p
              className={`challenge-verdict ${answered ? (isCorrect ? "correct" : "wrong") : ""}`}
              aria-live="polite"
            >
              {answered && (isCorrect ? "정답! 다음 문제로 넘어가요" : "아쉬워요! 도전이 끝났어요")}
            </p>
          </div>
        </section>
      </div>
    </div>
  );
}

export default ChallengePage;