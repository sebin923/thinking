export function resolveApiBaseUrl(configured, development = false) {
  const value = String(configured || "").trim().replace(/\/+$/, "");
  return value || (development ? "http://127.0.0.1:8000" : "");
}

// Production uses nginx's /api proxy on the same origin. The GPU URL and token
// belong to the backend environment and must never be exposed to the browser.
export const API_BASE_URL = resolveApiBaseUrl(
  import.meta.env?.VITE_API_URL,
  import.meta.env?.DEV,
);
