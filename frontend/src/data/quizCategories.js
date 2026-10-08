// =============================================================
// quizCategories.js — 퀴즈 종류(카테고리)별 설정 모음
// -------------------------------------------------------------
// 퀴즈 화면과 랭킹 화면이 같이 씀
// key는 백엔드 DB의 quizzes.category 값과 똑같아야 함 ("spelling", "grammar")
// 새 종류를 추가하려면 여기에 객체 하나만 더 넣으면 탭에도 자동으로 생김
// =============================================================

export const QUIZ_CATEGORIES = [
  {
    key: "spelling", // 백엔드로 보낼 값
    label: "맞춤법", // 탭에 보일 이름
    title: "맞춤법 퀴즈", // 페이지 큰 제목
    description: "문장을 바르게 쓰는 연습을 통해\n더 정확하고 자연스러운 글을 작성할 수 있어요.",
    memoText: "조금 더\n바른 표현을\n위해 :)", // 오른쪽 메모지 손글씨
    perfectMessage: "완벽해요! 맞춤법 박사네요 🎉", // 만점일 때 문구
  },
  {
    key: "grammar",
    label: "문법",
    title: "문법 퀴즈",
    description: "조사와 어미를 알맞게 고르는 연습으로\n문장의 짜임을 더 탄탄하게 만들어요.",
    memoText: "문장이\n술술 읽히게\n:)",
    perfectMessage: "완벽해요! 문법 고수네요 🎉",
  },
];

// key로 설정 하나를 찾는 도우미 함수 (없으면 첫 번째 = 맞춤법)
// find: 배열에서 조건에 맞는 첫 번째 항목을 찾음 / ||: 못 찾으면 뒤의 값을 씀
export function getQuizCategory(key) {
  return QUIZ_CATEGORIES.find((category) => category.key === key) || QUIZ_CATEGORIES[0];
}
