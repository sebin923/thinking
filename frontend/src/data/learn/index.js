// =============================================================
// data/learn/index.js — 학습 데이터 한곳에 모으기
// -------------------------------------------------------------
// 학습 화면·관리자 화면·마이페이지는 이 파일에서만 데이터를 가져옴
//   LEARN_TYPES      : 글 유형 3개(보고서·자기소개서·발표문)와 각 유형의 단원 목록
//   getPracticeFor() : 단원의 "글쓰기 연습" 자료 꺼내기
//
// ★ 여기 있는 건 "기본 내용"
//   관리자가 고친 내용은 api/learn.js가 이 기본 내용 위에 덮어써서 돌려줌
//   (백엔드가 생기면 api/learn.js에서 서버로 바꾸면 되고, 이 파일은 처음 넣을 데이터로 쓰면 됨)
// =============================================================

import REPORT_UNITS from "./report";
import COVER_LETTER_UNITS from "./coverLetter";
import SPEECH_UNITS from "./speech";
import PRACTICE_DATA from "./practiceData";

// 글 유형 목록 (화면에 보이는 순서대로)
//  - key: 구분 이름 (저장 데이터에 쓰여서 한 번 정하면 바꾸지 않기)
//  - practiceKey: practiceData.js에서 연습 자료를 가져올 이름 (없으면 단원 안의 practice를 씀)
//  - sources: 화면 아래 "참고 자료"로 보여줄 링크
export const LEARN_TYPES = [
  {
    key: "report",
    label: "보고서",
    description: "읽는 사람이 바로 판단할 수 있게, 핵심부터 분명하게 쓰는 법",
    practiceKey: "report",
    units: REPORT_UNITS,
    sources: [
      { label: "패스트캠퍼스 · 직장인 보고서 작성법", url: "https://fastcampus.co.kr/story_article_bsk" },
    ],
  },
  {
    key: "cover",
    label: "자기소개서",
    description: "직무와 연결된 나의 경험을 구체적으로 보여주는 법",
    practiceKey: null,
    units: COVER_LETTER_UNITS,
    sources: [
      { label: "하이잡 · STAR 기법 자소서 작성법", url: "https://www.haijob.co.kr/blog/?p=772" },
    ],
  },
  {
    key: "speech",
    label: "발표문",
    description: "한 번 듣고도 기억에 남도록, 귀를 위해 쓰는 법",
    practiceKey: "speech",
    units: SPEECH_UNITS,
    sources: [
      { label: "AhaSlides · 프레젠테이션 작성법", url: "https://ahaslides.com/ko/blog/how-to-write-a-presentation/" },
    ],
  },
];

// O/X 만점 기준 (이 개수를 모두 맞혀야 단원 완료 + 글쓰기 열림)
// → 실제 기준은 "그 단원의 문제 수 전부"라서, 관리자가 문제 수를 바꿔도 자동으로 맞춰짐
export const QUESTIONS_PER_UNIT = 10;

// ----- 단원의 글쓰기 연습 자료 꺼내기 -----
// type: LEARN_TYPES의 항목 하나 / unit: 단원 / unitIndex: 단원 순서(0부터)
// 돌려주는 값
//   학습 데이터 자료(보고서·발표문): { kind: "data", topic, facts, example, source, url, license }
//   직접 넣은 문항(자기소개서):      { kind: "question", question, sample }
//   자료가 없으면 null
export function getPracticeFor(type, unit, unitIndex) {
  // 단원 안에 practice가 따로 있으면 그걸 먼저 씀 (자기소개서)
  if (unit.practice) return { kind: "question", ...unit.practice };

  const pool = type.practiceKey ? PRACTICE_DATA[type.practiceKey] : null;
  if (!pool || pool.length === 0) return null;
  // %: 나머지 → 자료가 단원 수보다 적어도 0, 1, 2 … 처음부터 돌아가며 씀
  return { kind: "data", ...pool[unitIndex % pool.length] };
}

// 유형 key로 유형 찾기 (없으면 undefined)
export function findLearnType(key) {
  return LEARN_TYPES.find((type) => type.key === key);
}
