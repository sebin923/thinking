import { FREE_DAILY_AI_USES } from "../data/aiCredits";

import { API_BASE_URL as API_URL } from "./baseUrl";
export const EMPTY_AI_USAGE = Object.freeze({
  used: 0, limit: FREE_DAILY_AI_USES, remaining: 0, credits: 0, unlimited: false,
});

export function canUseAi(usage) {
  return Boolean(usage && (usage.unlimited || usage.remaining > 0 || usage.credits > 0));
}

export async function fetchAiUsage(token) {
  if (!token) throw new Error("AI 기능은 로그인 후 사용할 수 있어요.");
  let response;
  try {
    response = await fetch(`${API_URL}/api/ai-usage/today`, {
      headers: { Authorization: `Bearer ${token}` }, cache: "no-store",
    });
  } catch {
    throw new Error("AI 이용 횟수를 확인하지 못했어요. 서버 연결을 확인해 주세요.");
  }
  const data = await response.json().catch(() => ({}));
  if (!response.ok) throw new Error(typeof data.detail === "string" ? data.detail : "AI 이용 횟수를 확인하지 못했어요.");
  if (!data || !["used", "limit", "remaining", "credits"].every((key) => Number.isInteger(data[key]) && data[key] >= 0)
      || typeof data.unlimited !== "boolean") {
    throw new Error("AI 이용 횟수 응답이 올바르지 않아요.");
  }
  return data;
}
