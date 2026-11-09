// =============================================================
// LearnPage.jsx — "학습" 화면 (헤더 메뉴 "학습")
// -------------------------------------------------------------
// 글쓰기 기본 규칙을 단원별로 공부하는 화면
//
// 화면 구성
//   PageHero (제목)
//   [학습 | 오답노트] 큰 탭
//     학습    : 글 유형 3개(보고서·자기소개서·발표문) 고르기 → 단원 목록 10개 → 단원 학습(UnitView)
//     오답노트 : 단원 O/X에서 틀린 문제 모음 (WrongNotes)
//
// 규칙 (팀에서 정한 조건)
//   - 로그인해야 학습 가능
//   - 단원은 순서대로 열리고, 한 번 완료한 단원은 언제든 다시 할 수 있음
//   - 단원마다 O/X 10문제 → 전부 맞혀야 글쓰기 연습 열림
//   - 글쓰기 연습을 AI(CLOVA)가 채점 → 90점 이상이면 단원 완료 → 다음 단원 열림
//
// 데이터·저장: api/learn.js (지금은 브라우저 저장, 백엔드 생기면 DB)
// AI 채점: 백엔드 POST /api/learn/writing-score (backend/routers/learn.py)
// =============================================================

import { useEffect, useState } from "react";
// FileText/UserRound/Mic: 유형 아이콘, BookOpenCheck: 학습 탭, NotebookPen: 오답노트 탭, LogIn: 로그인 안내
import { FileText, UserRound, Mic, BookOpenCheck, NotebookPen, LogIn, Loader2 } from "lucide-react";

import PageHero from "../components/PageHero";
// 창만 스크롤하는 도구 (scrollIntoView를 쓰면 overflow: hidden 상자 안 내용이 밀려 올라가는 문제가 있어서)
import scrollToElement from "../utils/scrollToElement";
import UnitList from "./learn/UnitList";
import UnitView from "./learn/UnitView";
import WrongNotes from "./learn/WrongNotes";
import { getPracticeFor } from "../data/learn";
import {
  fetchLearnContent,
  fetchLearnProgress,
  saveQuizAttempt,
  scoreWriting,
  answerWrongNote,
  deleteWrongNote,
  summarizeProgress,
  countOpenWrong,
  isUnitUnlocked,
} from "../api/learn";
// 로딩 아이콘이 도는 .spin 클래스, 큰 탭 모양(.category-tabs)
import "../components/AuthLayout.css";
import "../components/CategoryTabs.css";
import "./LearnPage.css";

// 유형 key → 아이콘
const TYPE_ICONS = { report: FileText, cover: UserRound, speech: Mic };

// props
//  - auth: 로그인 정보 (없으면 로그인 안내)
//  - onGoLogin: "로그인하기" 버튼
//  - initialTab: 처음 보여줄 탭 ("learn" 기본 / "wrong" → 퀴즈 결과의 "오답노트 보기"로 들어왔을 때)
function LearnPage({ auth, onGoLogin, initialTab = "learn" }) {
  const user = auth?.user;
  const token = auth?.token; // AI 채점 요청에 붙이는 로그인 토큰

  const [tab, setTab] = useState(initialTab); // "learn"(학습) / "wrong"(오답노트)
  const [content, setContent] = useState(null); // 학습 내용 (유형 3개 + 단원)
  const [progress, setProgress] = useState(null); // 내 진도
  const [error, setError] = useState("");
  const [typeKey, setTypeKey] = useState("report"); // 고른 유형
  const [unitIndex, setUnitIndex] = useState(null); // 보고 있는 단원 (null이면 목록)

  // ----- 처음 들어올 때: 학습 내용 + 내 진도 불러오기 (로그인했을 때만) -----
  useEffect(() => {
    if (!user) return undefined;
    let ignore = false; // 화면을 떠난 뒤 늦게 온 결과는 무시
    Promise.all([fetchLearnContent(), fetchLearnProgress(user)])
      .then(([loadedContent, loadedProgress]) => {
        if (ignore) return;
        setContent(loadedContent);
        setProgress(loadedProgress);
      })
      .catch((err) => {
        if (!ignore) setError(err.message);
      });
    return () => {
      ignore = true;
    };
  }, [user]);

  const hero = (
    <PageHero
      eyebrow="글쓰기 기본기"
      title="스터디"
      description={"보고서·자기소개서·발표문의 작성 규칙을 단원별로 익혀요.\nO/X를 모두 맞히고, 글쓰기 AI 채점 90점을 넘기면 단원 완료!"}
      memoText={"규칙을 알면\n글이\n쉬워져요"}
      memoVariant="notebook"
    />
  );

  // ----- 로그인 안 했을 때 -----
  if (!user) {
    return (
      <div className="sub-page">
        <div className="sub-page-inner">
          {hero}
          <section className="panel learn-login">
            <LogIn size={36} strokeWidth={1.6} />
            <p>학습은 로그인한 뒤에 할 수 있어요.</p>
            <p className="learn-login-sub">로그인하면 진도와 오답노트가 저장돼요.</p>
            <button type="button" className="btn-primary" onClick={onGoLogin}>
              로그인하기
            </button>
          </section>
        </div>
      </div>
    );
  }

  // ----- 불러오는 중 / 실패 -----
  if (!content || !progress) {
    return (
      <div className="sub-page">
        <div className="sub-page-inner">
          {hero}
          <p className="learn-state">
            {error ? error : (
              <>
                <Loader2 size={18} className="spin" /> 학습 내용을 불러오는 중이에요...
              </>
            )}
          </p>
        </div>
      </div>
    );
  }

  const type = content.find((item) => item.key === typeKey) || content[0];
  const summary = summarizeProgress(content, progress); // 유형별 완료 개수
  const openWrong = countOpenWrong(progress); // 미해결 오답 수

  // ----- 저장 함수들 (저장 후 새 진도로 화면 갱신) -----
  const handleSubmitQuiz = async (answers) => {
    const unit = type.units[unitIndex];
    const saved = await saveQuizAttempt(user, { typeKey: type.key, unit, answers });
    setProgress(saved.progress);
    return saved;
  };

  // 글쓰기 AI 채점 (채점 결과는 WritingPractice가 보여주고, 진도는 여기서 갱신)
  const handleScoreWriting = async (text) => {
    const unit = type.units[unitIndex];
    const scored = await scoreWriting(user, token, { typeLabel: type.label, unit, practice: getPracticeFor(type, unit, unitIndex), text });
    setProgress(scored.progress);
    return scored;
  };

  const handleAnswerWrong = async (key, chosen) => {
    const result = await answerWrongNote(user, key, chosen);
    setProgress(result.progress);
    return result;
  };

  const handleDeleteWrong = async (key) => {
    setProgress(await deleteWrongNote(user, key));
  };

  // 화면 위쪽(탭 위치)으로 부드럽게 올리기 → 단원을 열거나 닫을 때 처음부터 보이게
  const scrollToTabs = () => {
    scrollToElement(".learn-tabs");
  };

  const openUnit = (index) => {
    setUnitIndex(index);
    scrollToTabs();
  };

  // 다음 단원 버튼: 마지막 단원이 아니고, 다음 단원이 열려 있을 때만
  const nextUnitIndex = unitIndex !== null && unitIndex + 1 < type.units.length ? unitIndex + 1 : null;
  const canGoNext = nextUnitIndex !== null && isUnitUnlocked(type.units, nextUnitIndex, progress);

  return (
    <div className="sub-page">
      <div className="sub-page-inner">
        {hero}

        {/* [학습 | 오답노트] 큰 탭 (퀴즈 화면의 [퀴즈 | 랭킹]과 같은 모양) */}
        <div className="learn-tabs-row">
          <div className="category-tabs section learn-tabs" role="tablist" aria-label="학습 메뉴">
            <button
              type="button"
              role="tab"
              aria-selected={tab === "learn"}
              className={tab === "learn" ? "category-tab active" : "category-tab"}
              onClick={() => setTab("learn")}
            >
              <BookOpenCheck size={17} /> 학습
            </button>
            <button
              type="button"
              role="tab"
              aria-selected={tab === "wrong"}
              className={tab === "wrong" ? "category-tab active" : "category-tab"}
              onClick={() => setTab("wrong")}
            >
              <NotebookPen size={17} /> 오답노트
              {openWrong > 0 && <span className="learn-tab-badge">{openWrong}</span>}
            </button>
          </div>
        </div>

        {tab === "wrong" ? (
          <WrongNotes
            content={content}
            progress={progress}
            onAnswer={handleAnswerWrong}
            onDelete={handleDeleteWrong}
            onGoLearn={() => setTab("learn")}
          />
        ) : unitIndex !== null ? (
          // ===== 단원 학습 화면 =====
          <UnitView
            key={`${type.key}-${unitIndex}`} // 단원이 바뀌면 화면을 새로 시작
            type={type}
            unit={type.units[unitIndex]}
            unitIndex={unitIndex}
            unitProgress={progress.units[type.units[unitIndex].id]}
            practice={getPracticeFor(type, type.units[unitIndex], unitIndex)}
            onBack={() => {
              setUnitIndex(null);
              scrollToTabs();
            }}
            onSubmitQuiz={handleSubmitQuiz}
            onScoreWriting={handleScoreWriting}
            onOpenWrongNotes={() => {
              setUnitIndex(null);
              setTab("wrong");
            }}
            onNextUnit={canGoNext ? () => openUnit(nextUnitIndex) : null}
          />
        ) : (
          // ===== 유형 고르기 + 단원 목록 =====
          <>
            <div className="learn-types">
              {content.map((item) => {
                const Icon = TYPE_ICONS[item.key] || FileText;
                const stat = summary.find((s) => s.key === item.key);
                const percent = stat.total ? Math.round((stat.done / stat.total) * 100) : 0;
                return (
                  <button
                    key={item.key}
                    type="button"
                    className={item.key === type.key ? "learn-type active" : "learn-type"}
                    onClick={() => setTypeKey(item.key)}
                    aria-pressed={item.key === type.key}
                  >
                    <span className="learn-type-icon">
                      <Icon size={22} />
                    </span>
                    <span className="learn-type-body">
                      <strong>{item.label}</strong>
                      <span className="learn-type-desc">{item.description}</span>
                      {/* 진도 막대 */}
                      <span className="learn-type-progress" aria-label={`${stat.done}/${stat.total} 단원 완료`}>
                        <span className="learn-type-bar">
                          <span style={{ width: `${percent}%` }} />
                        </span>
                        <em>
                          {stat.done}/{stat.total}
                        </em>
                      </span>
                    </span>
                  </button>
                );
              })}
            </div>

            <UnitList type={type} progress={progress} onOpenUnit={openUnit} />
          </>
        )}
      </div>
    </div>
  );
}

export default LearnPage;
