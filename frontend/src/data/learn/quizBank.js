// 단원에 들어갈 때 해당 20문제만 로드한다. 문제 내용은 초기 화면 번들에 넣지 않는다.
export const QUIZ_BANK_VERSION = "university-20261119-v1";
export const QUIZ_ROUND_SIZE = 10;
const banks = import.meta.glob("./quizzes/*.json", { import: "default" });

export async function loadUnitQuiz(unitId) {
  const load = banks[`./quizzes/${unitId}.json`];
  if (!load) throw new Error("이 단원의 문제를 찾을 수 없어요.");
  const questions = await load();
  return questions.map((question) => ({ ...question }));
}
