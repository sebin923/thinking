import { API_BASE_URL as BASE } from "./baseUrl";
export async function adminRequest(token, path, body, blob = false) {
  const response = await fetch(`${BASE}${path}`, {
    method: body === undefined ? 'GET' : 'POST',
    headers: { Authorization: `Bearer ${token}`, ...(body === undefined ? {} : {'Content-Type':'application/json'}) },
    ...(body === undefined ? {} : {body: JSON.stringify(body)}),
  });
  if (!response.ok) {
    const data = await response.json().catch(() => ({}));
    const error = new Error(typeof data.detail === 'string' ? data.detail : '요청을 처리하지 못했습니다. 입력과 서버 상태를 확인해 주세요.');
    error.status = response.status; throw error;
  }
  return blob ? response.blob() : response.json();
}
export async function downloadDataset(token, id) {
  const blob = await adminRequest(token, `/api/training/exports/${encodeURIComponent(id)}/download`, undefined, true);
  const url = URL.createObjectURL(blob); const a = document.createElement('a');
  a.href = url; a.download = `qwen_training_${id}.zip`; document.body.append(a); a.click(); a.remove();
  setTimeout(() => URL.revokeObjectURL(url), 1000);
}
