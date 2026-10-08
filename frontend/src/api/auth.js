// =============================================================
// api/auth.js — 회원가입 / 로그인 관련 서버 요청을 모아둔 파일
// -------------------------------------------------------------
// 화면(LoginPage, SignupPage)은 이 파일의 함수만 부름.
// → 서버 통신 코드를 한 곳에 모아두면, 주소가 바뀌어도 이 파일만 고치면 됨.
//
// 백엔드(FastAPI) 주소 목록 (backend/routers/auth.py 와 1:1로 맞춰져 있음)
//   GET  /api/auth/check-login-id?login_id=...  아이디 중복 확인
//   POST /api/auth/email/send-code              이메일 인증번호 보내기
//   POST /api/auth/email/verify                 이메일 인증번호 확인
//   POST /api/auth/signup                       회원가입
//   POST /api/auth/login                        로그인 (아이디 + 비밀번호)
//
// ※ 비밀번호 암호화는 "서버"에서 bcrypt로 함 (backend/security.py)
//   브라우저 → 서버로 갈 때는 원래 비밀번호 그대로 보내고, 대신 실제 배포할 때
//   HTTPS(자물쇠 주소)로 통신 자체를 암호화해서 중간에서 못 엿보게 함.
//   (프론트에서 미리 암호화해서 보내면 그 암호화된 값이 곧 비밀번호가 돼버려서 의미가 없음)
//
// ★ USE_MOCK
//   false(기본): 진짜 백엔드에 요청
//   true: 백엔드 없이 화면만 테스트하고 싶을 때. 브라우저 저장소를 가짜 서버로 씀
//         (가짜 서버도 비밀번호는 SHA-256으로 바꿔서 저장하지만, 연습용일 뿐 진짜 보안은 백엔드 bcrypt)
// =============================================================

const USE_MOCK = false;

// 백엔드 서버 주소
// frontend/.env 에 VITE_API_URL=http://127.0.0.1:8000 처럼 적어두면 그 값을 쓰고, 없으면 기본값
const API_URL = import.meta.env.VITE_API_URL || "http://127.0.0.1:8000";

// =============================================================
// 진짜 서버 요청 공통 함수
// =============================================================

// request(path, options): 서버에 요청 → 성공하면 응답 JSON, 실패하면 에러를 던짐
async function request(path, { method = "GET", body } = {}) {
  let response;
  try {
    // fetch: 서버에 요청을 보내는 브라우저 기본 함수
    response = await fetch(`${API_URL}${path}`, {
      method,
      // body가 있을 때만 "JSON으로 보낼게요" 헤더를 붙임
      headers: body ? { "Content-Type": "application/json" } : undefined,
      body: body ? JSON.stringify(body) : undefined, // 객체 → JSON 글자
    });
  } catch {
    // 서버가 꺼져 있거나 주소가 틀리면 여기로 옴
    throw new Error("서버에 연결할 수 없어요. 백엔드가 켜져 있는지 확인해 주세요.");
  }

  // 응답 내용을 JSON으로 읽기 (비어 있으면 빈 객체)
  const data = await response.json().catch(() => ({}));

  // response.ok: 200번대(성공)면 true
  if (!response.ok) {
    throw new Error(readErrorMessage(data));
  }
  return data;
}

// FastAPI 에러 응답에서 사람이 읽을 문구를 꺼내는 함수
//  - 우리가 직접 낸 에러: { detail: "이미 사용 중인 아이디예요." }
//  - 입력 형식 에러(422): { detail: [ { msg: "...", ... }, ... ] }
function readErrorMessage(data) {
  if (typeof data.detail === "string") return data.detail;
  if (Array.isArray(data.detail) && data.detail.length > 0) {
    // pydantic 에러 문구 앞에 붙는 "Value error, " 는 떼고 보여줌
    return String(data.detail[0].msg || "").replace(/^Value error,\s*/, "") || "입력값을 확인해 주세요.";
  }
  return "요청에 실패했어요. 잠시 후 다시 시도해 주세요.";
}

// =============================================================
// 화면에서 부르는 함수들
// =============================================================

// 아이디 중복 확인 → { available: true/false, message }
export function checkLoginId(loginId) {
  if (USE_MOCK) return mock.checkLoginId(loginId);
  // encodeURIComponent: 주소에 넣어도 안전한 글자로 바꿈
  return request(`/api/auth/check-login-id?login_id=${encodeURIComponent(loginId)}`);
}

// 이메일 인증번호 보내기 → { message, expires_in(초), dev_mode }
//  dev_mode가 true면 메일 대신 백엔드 터미널에 인증번호가 찍힘 (메일 설정 전 개발용)
export function sendEmailCode(email) {
  if (USE_MOCK) return mock.sendEmailCode(email);
  return request("/api/auth/email/send-code", { method: "POST", body: { email } });
}

// 이메일 인증번호 확인 → { message, verified: true }
export function verifyEmailCode(email, code) {
  if (USE_MOCK) return mock.verifyEmailCode(email, code);
  return request("/api/auth/email/verify", { method: "POST", body: { email, code } });
}

// 회원가입 → { message, user }
//  form: { loginId, password, name, phone, email }
//  서버는 파이썬 관례대로 snake_case(login_id)를 쓰니까 이름을 바꿔서 보냄
export function signup(form) {
  const body = {
    login_id: form.loginId,
    password: form.password,
    name: form.name,
    phone: form.phone, // 숫자만 (예: "01012345678")
    email: form.email,
  };
  if (USE_MOCK) return mock.signup(body);
  return request("/api/auth/signup", { method: "POST", body });
}

// 로그인 → { access_token, token_type, user: { user_id, login_id, name, email } }
//  access_token: "로그인한 사람" 증명서(JWT). 이후 요청마다 같이 보내서 누군지 알려줌
export function login(loginId, password) {
  const body = { login_id: loginId, password };
  if (USE_MOCK) return mock.login(body);
  return request("/api/auth/login", { method: "POST", body });
}

// =============================================================
// 가짜 서버 (USE_MOCK = true 일 때만 사용)
// 백엔드 없이 화면 흐름만 테스트하는 용도
// =============================================================

const MOCK_USERS_KEY = "saenggak-mock-users";
const MOCK_CODES_KEY = "saenggak-mock-codes";

// 잠깐 기다리기 (진짜 서버처럼 로딩이 보이게)
const wait = (ms) => new Promise((resolve) => setTimeout(resolve, ms));

// localStorage에서 JSON 꺼내기/넣기
const readJson = (key, fallback) => {
  try {
    return JSON.parse(localStorage.getItem(key)) ?? fallback; // ??: 앞이 null/undefined면 뒤의 값
  } catch {
    return fallback;
  }
};
const writeJson = (key, value) => localStorage.setItem(key, JSON.stringify(value));

// SHA-256으로 글자를 바꾸는 함수 (가짜 서버용 "암호화" 흉내)
// crypto.subtle: 브라우저에 들어 있는 암호 기능
async function sha256(text) {
  const bytes = new TextEncoder().encode(text); // 글자 → 바이트
  const hash = await crypto.subtle.digest("SHA-256", bytes);
  // 바이트 배열을 16진수 글자로 바꿔서 이어 붙임
  return [...new Uint8Array(hash)].map((b) => b.toString(16).padStart(2, "0")).join("");
}

const mock = {
  async checkLoginId(loginId) {
    await wait(400);
    const taken = readJson(MOCK_USERS_KEY, []).some((u) => u.login_id === loginId);
    return taken
      ? { available: false, message: "이미 사용 중인 아이디예요." }
      : { available: true, message: "사용할 수 있는 아이디예요." };
  },

  async sendEmailCode(email) {
    await wait(500);
    // 6자리 숫자 만들기 (100000 ~ 999999)
    const code = String(Math.floor(100000 + Math.random() * 900000));
    const codes = readJson(MOCK_CODES_KEY, {});
    codes[email] = { code, expiresAt: Date.now() + 5 * 60 * 1000, verified: false };
    writeJson(MOCK_CODES_KEY, codes);
    console.log(`[가짜 서버] ${email} 인증번호: ${code}`); // F12 → Console에서 확인
    return { message: "인증번호를 보냈어요.", expires_in: 300, dev_mode: true };
  },

  async verifyEmailCode(email, code) {
    await wait(400);
    const codes = readJson(MOCK_CODES_KEY, {});
    const saved = codes[email];
    if (!saved || Date.now() > saved.expiresAt) throw new Error("인증번호가 만료됐어요. 다시 받아 주세요.");
    if (saved.code !== code) throw new Error("인증번호가 일치하지 않아요.");
    saved.verified = true;
    writeJson(MOCK_CODES_KEY, codes);
    return { message: "이메일 인증이 완료됐어요.", verified: true };
  },

  async signup(body) {
    await wait(600);
    const users = readJson(MOCK_USERS_KEY, []);
    if (users.some((u) => u.login_id === body.login_id)) throw new Error("이미 사용 중인 아이디예요.");
    if (users.some((u) => u.email === body.email)) throw new Error("이미 가입된 이메일이에요.");
    if (!readJson(MOCK_CODES_KEY, {})[body.email]?.verified) throw new Error("이메일 인증을 먼저 완료해 주세요.");

    const user = {
      user_id: Date.now(),
      login_id: body.login_id,
      password_hash: await sha256(body.password), // 비밀번호는 바꿔서 저장
      name: body.name,
      phone: body.phone,
      email: body.email,
    };
    writeJson(MOCK_USERS_KEY, [...users, user]);
    return { message: "회원가입이 완료됐어요.", user: { user_id: user.user_id, login_id: user.login_id } };
  },

  async login(body) {
    await wait(600);
    const hash = await sha256(body.password);
    const found = readJson(MOCK_USERS_KEY, []).find(
      (u) => u.login_id === body.login_id && u.password_hash === hash
    );
    if (!found) throw new Error("아이디 또는 비밀번호가 올바르지 않아요.");
    return {
      access_token: `mock-token-${found.user_id}`,
      token_type: "bearer",
      user: { user_id: found.user_id, login_id: found.login_id, name: found.name, email: found.email },
    };
  },
};
