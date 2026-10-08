// =============================================================
// RankingPage.jsx — 퀴즈 랭킹 페이지
// -------------------------------------------------------------
// 구성 (위에서 아래로)
//   1. 페이지 제목 영역 (PageHero)
//   2. 맞춤법 | 문법 탭
//   3. 내 기록 안내 (로그인했을 때)
//   4. 1~3위 시상대
//   5. 4~10위 목록
//
// 데이터: 백엔드 GET /api/quizzes/rankings?category=spelling (routers/quiz.py)
//  → [{ ranking_id, user_id, nickname, category, score, challenged_at }, ...]
// =============================================================

import { useState, useEffect } from "react";
import { Trophy, Medal, Crown, ArrowRight, UserRound, RefreshCw } from "lucide-react";

import PageHero from "../components/PageHero";
import CategoryTabs from "../components/CategoryTabs";
import { getQuizCategory } from "../data/quizCategories";
import "./RankingPage.css";

// 백엔드 주소 (frontend/.env의 VITE_API_URL이 있으면 그 값, 없으면 기본값)
const API_URL = import.meta.env.VITE_API_URL || "http://127.0.0.1:8000";

// ----- 도우미 함수들 (컴포넌트 밖에 둔 일반 함수) -----

// 같은 사람이 여러 번 도전하면 기록이 여러 줄 오니까, 사람마다 "최고 점수 한 줄"만 남김
function keepBestPerUser(rows) {
  // best: { user_id: 그 사람의 최고 기록 } 모양으로 모으는 객체
  const best = {};
  rows.forEach((row) => {
    const prev = best[row.user_id];
    // 처음 보는 사람이거나, 점수가 더 높으면 교체
    if (!prev || row.score > prev.score) best[row.user_id] = row;
  });

  // Object.values: 객체의 값들만 배열로 → 점수 높은 순 정렬
  // 점수가 같으면 먼저 달성한 사람(날짜가 빠른 사람)이 위로
  return Object.values(best).sort(
    (a, b) => b.score - a.score || new Date(a.challenged_at) - new Date(b.challenged_at)
  );
}

// 등수 매기기: 점수가 같으면 같은 등수 (예: 100, 90, 90, 80 → 1, 2, 2, 4)
function addRanks(rows) {
  let prevScore = null; // 바로 앞사람 점수
  let prevRank = 0; // 바로 앞사람 등수

  return rows.map((row, index) => {
    // 앞사람과 점수가 같으면 같은 등수, 다르면 (순서 + 1)등
    const rank = row.score === prevScore ? prevRank : index + 1;
    prevScore = row.score;
    prevRank = rank;
    // { ...row, rank }: 원래 칸들은 그대로 두고 rank 칸만 추가한 새 객체
    return { ...row, rank };
  });
}

// 날짜 글자 → "10.08" 모양
function formatDate(value) {
  const date = new Date(value);
  if (Number.isNaN(date.getTime())) return ""; // 날짜가 이상하면 빈칸
  const month = String(date.getMonth() + 1).padStart(2, "0"); // getMonth()는 0부터 시작해서 +1
  const day = String(date.getDate()).padStart(2, "0");
  return `${month}.${day}`;
}

// props
//  - user: 로그인한 사용자 (로그인 안 했으면 undefined) → 내 기록 강조용
//  - category: 보여줄 랭킹 종류 ("spelling" | "grammar")
//  - onChangeCategory: 탭을 눌렀을 때 실행 (App이 종류를 바꾸고 이 화면을 새로 그림)
//  - onGoQuiz: "퀴즈 풀러 가기" 버튼을 눌렀을 때 실행 (지금 종류의 퀴즈로 이동)
function RankingPage({ user, category = "spelling", onChangeCategory, onGoQuiz }) {
  const info = getQuizCategory(category);

  // rows: 등수까지 매긴 랭킹 목록 / loading: 불러오는 중 / error: 실패 문구
  const [rows, setRows] = useState([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");

  // reloadKey: "다시 불러오기" 버튼을 누를 때마다 1씩 올려서 아래 useEffect를 다시 실행시킴
  const [reloadKey, setReloadKey] = useState(0);

  // ----- 랭킹 불러오기 -----
  useEffect(() => {
    // ignore: 응답이 오기 전에 화면을 떠나면 결과를 무시하려고 쓰는 깃발
    let ignore = false;

    fetch(`${API_URL}/api/quizzes/rankings?category=${encodeURIComponent(category)}`)
      .then((res) => {
        if (!res.ok) throw new Error(`응답 실패: ${res.status}`);
        return res.json();
      })
      .then((data) => {
        if (ignore) return;
        setRows(addRanks(keepBestPerUser(data)));
        setError("");
        setLoading(false);
      })
      .catch((err) => {
        if (ignore) return;
        console.error("랭킹 불러오기 실패:", err);
        setError("랭킹을 불러오지 못했어요. 백엔드가 켜져 있는지 확인해 주세요.");
        setLoading(false);
      });

    // 정리 함수: 화면을 떠나거나 다시 불러오기 전에 이전 요청 결과를 무시하도록 표시
    return () => {
      ignore = true;
    };
  }, [category, reloadKey]);

  // "다시 불러오기" 버튼
  const handleReload = () => {
    setLoading(true);
    setReloadKey((key) => key + 1);
  };

  // ----- 화면에 쓸 값 계산 -----
  const podium = rows.slice(0, 3); // 1~3위
  const others = rows.slice(3); // 4위부터
  // 내 기록 찾기 (로그인했을 때만)
  const myRow = user ? rows.find((row) => row.user_id === user.user_id) : null;

  // 시상대 순서: 가운데가 1위가 되도록 [2위, 1위, 3위]로 다시 배치
  // (filter(Boolean): 3명이 안 될 때 비어 있는 자리(undefined) 빼기)
  const podiumOrder = [podium[1], podium[0], podium[2]].filter(Boolean);

  // 메달 아이콘 색 클래스 (1=금, 2=은, 3=동)
  const medalClass = { 1: "gold", 2: "silver", 3: "bronze" };

  // ----- 가운데 내용 (상태에 따라 다르게) -----
  let content;

  if (loading) {
    content = <p className="ranking-message">랭킹을 불러오는 중이에요...</p>;
  } else if (error) {
    content = (
      <div className="ranking-message">
        <p>{error}</p>
        <button type="button" className="btn-outline" onClick={handleReload}>
          <RefreshCw size={16} /> 다시 불러오기
        </button>
      </div>
    );
  } else if (rows.length === 0) {
    content = (
      <div className="ranking-message">
        <Trophy size={40} strokeWidth={1.5} className="ranking-empty-icon" />
        <p>
          아직 {info.label} 랭킹 기록이 없어요.
          <br />첫 번째 주인공이 되어보세요!
        </p>
        <button type="button" className="btn-primary" onClick={onGoQuiz}>
          {info.title} 풀러 가기 <ArrowRight size={18} />
        </button>
      </div>
    );
  } else {
    content = (
      <>
        {/* ===== 1~3위 시상대 ===== */}
        <ol className="podium">
          {podiumOrder.map((row) => (
            <li
              key={row.user_id}
              // rank-1 / rank-2 / rank-3 클래스로 높이와 색을 다르게
              // 내 기록이면 is-me 클래스 추가
              className={`podium-item rank-${row.rank}${user && row.user_id === user.user_id ? " is-me" : ""}`}
            >
              {/* 1위 위에만 왕관 */}
              {row.rank === 1 && <Crown className="podium-crown" size={26} />}
              <span className="podium-avatar">
                {/* 이름 첫 글자 (없으면 ?) */}
                {(row.nickname || "?").slice(0, 1)}
              </span>
              <strong className="podium-name">{row.nickname || "알 수 없음"}</strong>
              <span className="podium-score">{row.score}점</span>
              {/* 단상 (등수 숫자 + 메달) */}
              <div className="podium-stand">
                <Medal size={18} className={`medal ${medalClass[row.rank] || ""}`} />
                {row.rank}위
              </div>
            </li>
          ))}
        </ol>

        {/* ===== 4위부터 목록 ===== */}
        {others.length > 0 && (
          <ol className="ranking-list" start={4}>
            {others.map((row) => (
              <li
                key={row.user_id}
                className={user && row.user_id === user.user_id ? "ranking-row is-me" : "ranking-row"}
              >
                <span className="ranking-rank">{row.rank}</span>
                <span className="ranking-name">{row.nickname || "알 수 없음"}</span>
                <span className="ranking-date">{formatDate(row.challenged_at)}</span>
                <strong className="ranking-score">{row.score}점</strong>
              </li>
            ))}
          </ol>
        )}
      </>
    );
  }

  return (
    <div className="sub-page">
      <div className="sub-page-inner">
        <PageHero
          eyebrow="함께 성장하는 글쓰기 연습"
          title="퀴즈 랭킹"
          description={"퀴즈를 풀고 다른 사람들과 실력을 겨뤄보세요.\n한 사람당 가장 높은 점수로 순위가 매겨져요."}
          memoText={"오늘의\n1등은\n누구? :)"}
          memoVariant="note"
        />

        <div className="ranking-tabs-row">
          <CategoryTabs value={category} onChange={onChangeCategory} />
        </div>

        <section className="panel ranking-card">
          <div className="ranking-head">
            <h2>
              <Trophy size={22} />
              {info.label} TOP 10
            </h2>
            <button type="button" className="text-icon-button" onClick={handleReload} disabled={loading}>
              <RefreshCw size={15} /> 새로고침
            </button>
          </div>

          {/* ===== 내 기록 안내 (로그인 + 불러오기 성공했을 때만) ===== */}
          {!loading && !error && (
            <div className="my-ranking">
              <UserRound size={18} />
              {!user ? (
                <span>로그인하면 내 순위를 확인하고 기록을 남길 수 있어요.</span>
              ) : myRow ? (
                <span>
                  <strong>{user.name}</strong>님은 지금 <strong>{myRow.rank}위</strong>예요! (최고 {myRow.score}점)
                </span>
              ) : (
                <span>
                  <strong>{user.name}</strong>님은 아직 TOP 10에 없어요. 퀴즈에 도전해 보세요!
                </span>
              )}
              {/* 퀴즈 바로가기 (오른쪽 끝) */}
              <button type="button" className="my-ranking-link" onClick={onGoQuiz}>
                도전하기 <ArrowRight size={14} />
              </button>
            </div>
          )}

          {content}
        </section>
      </div>
    </div>
  );
}

export default RankingPage;
