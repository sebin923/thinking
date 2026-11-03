// =============================================================
// WrongNotePage.jsx — 오답노트 화면 (헤더 "오답노트")
// -------------------------------------------------------------
// ★ 아직 기능이 없어서 "준비 중" 안내만 보여주는 화면
//   나중에 퀴즈에서 틀린 문제를 모아 보여주는 기능을 여기에 만들면 됨
//   (백엔드 quiz_results 테이블에 is_correct = False인 기록이 이미 쌓이고 있어서 그걸 쓰면 됨)
// =============================================================

// NotebookPen: 오답노트 아이콘, ArrowRight: 버튼 화살표
import { NotebookPen, ArrowRight } from "lucide-react";

import PageHero from "../components/PageHero";
import "./WrongNotePage.css";

// props: onNavigate → "퀴즈 풀러 가기" 버튼을 눌렀을 때 화면 이동 (App의 handleNavigate)
function WrongNotePage({ onNavigate }) {
  return (
    <div className="sub-page">
      <div className="sub-page-inner">
        <PageHero
          eyebrow="틀린 문제 다시 보기"
          title="오답노트"
          description={"퀴즈에서 틀린 문제를 모아 다시 확인하는 공간이에요."}
          memoText={"틀린 만큼\n자라는\n문장력"}
          memoVariant="notebook"
        />

        <section className="panel wrong-note-ready">
          {/* 동그란 아이콘 배경 */}
          <div className="wrong-note-icon" aria-hidden="true">
            <NotebookPen size={34} strokeWidth={1.6} />
          </div>
          <h2>준비 중인 화면이에요</h2>
          <p>
            곧 퀴즈에서 틀린 문제와 정답·해설을 한곳에 모아 볼 수 있어요.{" "}
            {/* {" "}: 모바일에서 줄바꿈(br)을 숨겨도 두 문장 사이에 띄어쓰기가 남게 */}
            <br />
            그동안 퀴즈를 풀면서 실력을 쌓아 보세요!
          </p>
          <button type="button" className="btn-primary" onClick={() => onNavigate("quiz")}>
            퀴즈 풀러 가기 <ArrowRight size={16} />
          </button>
        </section>
      </div>
    </div>
  );
}

export default WrongNotePage;
