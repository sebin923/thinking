// =============================================================
// LearnProgressCard.jsx — 마이페이지의 "학습 진도" 카드
// -------------------------------------------------------------
// 글 유형별(보고서·자기소개서·발표문) 완료한 단원 수를 막대로 보여주고,
// (단원 완료 = O/X 10문제 만점 + 글쓰기 AI 채점 90점 이상)
// 아직 해결 못 한 오답 수 + "학습 이어 하기" 버튼을 둠
// 데이터: api/learn.js (지금은 브라우저 저장, 백엔드 생기면 DB)
// 스타일: pages/MyPage.css (.mypage-learn …)
// =============================================================

import { useEffect, useState } from "react";
// GraduationCap: 학습 아이콘, NotebookPen: 오답, ArrowRight: 버튼 화살표
import { GraduationCap, NotebookPen, ArrowRight } from "lucide-react";

import { fetchLearnContent, fetchLearnProgress, summarizeProgress, countOpenWrong } from "../api/learn";

// props
//  - user: 로그인한 회원 (auth.user)
//  - onGoLearn: "학습 이어 하기" 버튼 → 학습 화면으로
function LearnProgressCard({ user, onGoLearn }) {
  // summary: [{ key, label, done, quizPassed, total }] / openWrong: 미해결 오답 수
  const [data, setData] = useState(null);

  useEffect(() => {
    let ignore = false;
    Promise.all([fetchLearnContent(), fetchLearnProgress(user)])
      .then(([content, progress]) => {
        if (ignore) return;
        setData({ summary: summarizeProgress(content, progress), openWrong: countOpenWrong(progress) });
      })
      .catch(() => {
        // 진도를 못 불러와도 마이페이지 나머지는 보여야 하니까 조용히 0으로
        if (!ignore) setData({ summary: [], openWrong: 0 });
      });
    return () => {
      ignore = true;
    };
  }, [user]);

  if (!data) return null; // 불러오는 동안은 아무것도 안 그림 (아주 빨라서 깜빡이지 않음)

  // 전체 합계 (예: 7/30 단원)
  const done = data.summary.reduce((sum, item) => sum + item.done, 0);
  const total = data.summary.reduce((sum, item) => sum + item.total, 0);

  return (
    <section className="panel mypage-learn" aria-labelledby="mypage-learn-title">
      <div className="mypage-learn-head">
        <h2 id="mypage-learn-title">
          <GraduationCap size={20} />
          스터디 진도
        </h2>
        <span className="mypage-learn-total">
          전체 <strong>{done}</strong> / {total} 단원 완료
        </span>
      </div>

      {/* 유형별 진도 막대 */}
      <ul className="mypage-learn-list">
        {data.summary.map((item) => {
          const percent = item.total ? Math.round((item.done / item.total) * 100) : 0;
          return (
            <li key={item.key}>
              <span className="mypage-learn-label">{item.label}</span>
              {/* role="progressbar": 화면 읽기 프로그램이 진행률로 읽어 줌 */}
              <span
                className="mypage-learn-bar"
                role="progressbar"
                aria-valuenow={item.done}
                aria-valuemin={0}
                aria-valuemax={item.total}
                aria-label={`${item.label} 진도`}
              >
                <span style={{ width: `${percent}%` }} />
              </span>
              <span className="mypage-learn-count">
                {item.done}/{item.total}
              </span>
            </li>
          );
        })}
      </ul>

      <div className="mypage-learn-foot">
        <span className="mypage-learn-wrong">
          <NotebookPen size={15} /> 해결하지 않은 오답 {data.openWrong}개
        </span>
        <button type="button" className="btn-outline mypage-learn-button" onClick={onGoLearn}>
          스터디 이어 하기 <ArrowRight size={15} />
        </button>
      </div>
    </section>
  );
}

export default LearnProgressCard;
