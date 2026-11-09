// =============================================================
// learn/UnitList.jsx — 글 유형 하나의 단원 목록 (카드 10개)
// -------------------------------------------------------------
// 단원 카드 상태 (api/learn.js의 unitStatus)
//   locked  : 잠김 (앞 단원을 완료해야 열림) → 누를 수 없음
//   open      : 풀 수 있음 (아직 O/X 만점 전)
//   writing   : O/X 만점 → 글쓰기 연습 AI 채점 90점 이상이 남음
//   completed : 단원 완료 (O/X 만점 + 글쓰기 90점 이상) → 다음 단원 열림
// 처음엔 순서대로만 열리고, 한 번 완료한 단원은 언제든 다시 골라서 할 수 있음
// =============================================================

// Lock: 잠김, PlayCircle: 시작, CheckCircle2: 완료, PenLine: 글쓰기 남음, ExternalLink: 참고 자료 링크
import { Lock, PlayCircle, CheckCircle2, PenLine, ExternalLink } from "lucide-react";

import { unitStatus } from "../../api/learn";

// 상태별 표시 글자와 아이콘
const STATUS_INFO = {
  locked: { label: "잠김", icon: Lock },
  open: { label: "학습하기", icon: PlayCircle },
  writing: { label: "글쓰기 남음", icon: PenLine },
  completed: { label: "완료", icon: CheckCircle2 },
};

// props
//  - type: 글 유형 (units, sources 사용)
//  - progress: 내 진도
//  - onOpenUnit: 단원 카드를 눌렀을 때 (단원 순서를 넘김)
function UnitList({ type, progress, onOpenUnit }) {
  return (
    <>
      <ol className="unit-list">
        {type.units.map((unit, index) => {
          const status = unitStatus(type.units, index, progress);
          const info = STATUS_INFO[status];
          const Icon = info.icon;
          const unitProgress = progress.units[unit.id];
          return (
            <li key={unit.id}>
              <button
                type="button"
                className={`unit-card is-${status}`}
                onClick={() => onOpenUnit(index)}
                disabled={status === "locked"}
                // 잠긴 카드에 마우스를 올리면 이유를 알려줌
                title={status === "locked" ? `${index}단원을 완료하면 열려요` : undefined}
              >
                <span className="unit-card-number">{String(index + 1).padStart(2, "0")}</span>
                <span className="unit-card-body">
                  <strong>{unit.title}</strong>
                  <span className="unit-card-summary">{unit.summary}</span>
                </span>
                <span className="unit-card-status">
                  <Icon size={15} />
                  {info.label}
                  {/* 푼 적이 있으면 최고 점수도 (O/X는 10문제 중 몇 개, 글쓰기는 100점 중 몇 점) */}
                  {unitProgress?.attempts > 0 && status === "open" && (
                    <em>
                      최고 {unitProgress.bestScore}/{unitProgress.total}
                    </em>
                  )}
                  {unitProgress?.writingAttempts > 0 && status !== "open" && <em>최고 {unitProgress.writingBest}점</em>}
                </span>
              </button>
            </li>
          );
        })}
      </ol>

      {/* 참고 자료 (단원 내용을 정리할 때 참고한 곳) */}
      {type.sources?.length > 0 && (
        <p className="learn-sources">
          참고 자료:{" "}
          {type.sources.map((source) => (
            <a key={source.url} href={source.url} target="_blank" rel="noreferrer">
              {source.label} <ExternalLink size={11} />
            </a>
          ))}
        </p>
      )}
    </>
  );
}

export default UnitList;
