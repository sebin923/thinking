// 현재 출제는 DB API를 사용한다. 아래 JSON 로더는 이전 문제 자료 확인용이다.
export const DB_QUIZ_BANK_VERSION = "db-ox-v1";
export const DB_QUIZ_UNIT_COUNT = 30;
export const QUIZ_BANK_VERSION = "university-20261119-v1";
export const QUIZ_ROUND_SIZE = 10;
const banks = import.meta.glob("./quizzes/*.json", { import: "default" });

export async function loadUnitQuiz(unitId) {
  const load = banks[`./quizzes/${unitId}.json`];
  if (!load) throw new Error("이 단원의 문제를 찾을 수 없어요.");
  const questions = await load();
  return questions.map((question) => ({ ...question }));
}
