// 서버 오류 본문이 없거나 JSON 형식이 달라도 사용자 안내는 유지한다.
export function makeAiError(data, fallback) {
  const detail = data?.detail;
  return new Error(typeof detail === "string" && detail.trim() ? detail : fallback);
}
