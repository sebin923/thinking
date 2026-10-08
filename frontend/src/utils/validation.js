// =============================================================
// utils/validation.js — 입력값 검사 함수 모음
// -------------------------------------------------------------
// 로그인, 회원가입에서 같이 쓰는 검사 규칙을 한 곳에 모아둠
// 각 함수는 문제가 있으면 "안내 문구"를, 문제가 없으면 빈 문자열("")을 돌려줌
// → 화면에서는 돌려받은 문구가 있으면 빨간 글씨로 보여주기만 하면 됨
//
// ※ 여기 검사는 "사용자 편의용"이고, 진짜 검사는 백엔드(schemas.py)가 똑같이 한 번 더 함
//   (브라우저 검사는 개발자 도구로 우회할 수 있어서 서버 검사가 꼭 필요함)
//   규칙을 바꾸면 백엔드 schemas.py도 같이 바꿔야 함!
// =============================================================

// ----- 정규표현식(글자 패턴 규칙)들 -----

// 아이디: 영문 소문자로 시작 + 영문 소문자/숫자/밑줄(_) 조합, 총 4~20자
//  ^[a-z]        : 첫 글자는 영문 소문자
//  [a-z0-9_]{3,19}: 나머지 3~19자는 소문자·숫자·밑줄
//  $             : 여기서 끝
const LOGIN_ID_PATTERN = /^[a-z][a-z0-9_]{3,19}$/;

// 이메일: 아무글자@아무글자.아무글자 (공백과 @는 각 부분에 못 들어감)
const EMAIL_PATTERN = /^[^\s@]+@[^\s@]+\.[^\s@]+$/;

// 휴대전화: 010으로 시작하는 숫자 10~11자리 (하이픈 뺀 상태로 검사)
const PHONE_PATTERN = /^01[016789][0-9]{7,8}$/;

// 인증번호: 숫자 6자리
const CODE_PATTERN = /^[0-9]{6}$/;

// ----- 검사 함수들 -----

export function validateLoginId(loginId) {
  if (!loginId) return "아이디를 입력해 주세요.";
  // test(): 글자가 패턴에 맞으면 true
  if (!LOGIN_ID_PATTERN.test(loginId)) {
    return "영문 소문자로 시작하는 4~20자 (소문자, 숫자, _ 사용 가능)로 입력해 주세요.";
  }
  return "";
}

export function validatePassword(password) {
  if (!password) return "비밀번호를 입력해 주세요.";
  if (password.length < 8 || password.length > 64) return "비밀번호는 8~64자로 입력해 주세요.";
  // /[A-Za-z]/: 영문자가 하나라도 있는지, /[0-9]/: 숫자가 하나라도 있는지
  if (!/[A-Za-z]/.test(password) || !/[0-9]/.test(password)) {
    return "영문과 숫자를 모두 포함해 주세요.";
  }
  // 공백은 실수로 들어가기 쉬워서 막음
  if (/\s/.test(password)) return "비밀번호에 공백은 넣을 수 없어요.";
  return "";
}

export function validatePasswordConfirm(password, confirm) {
  if (!confirm) return "비밀번호를 한 번 더 입력해 주세요.";
  if (password !== confirm) return "비밀번호가 일치하지 않아요.";
  return "";
}

export function validateName(name) {
  const trimmed = name.trim(); // trim(): 앞뒤 공백 제거
  if (!trimmed) return "이름을 입력해 주세요.";
  if (trimmed.length < 2 || trimmed.length > 20) return "이름은 2~20자로 입력해 주세요.";
  return "";
}

export function validatePhone(phone) {
  const digits = onlyDigits(phone);
  if (!digits) return "전화번호를 입력해 주세요.";
  if (!PHONE_PATTERN.test(digits)) return "휴대전화 번호를 정확히 입력해 주세요. (예: 010-1234-5678)";
  return "";
}

export function validateEmail(email) {
  const trimmed = email.trim();
  if (!trimmed) return "이메일을 입력해 주세요.";
  if (!EMAIL_PATTERN.test(trimmed)) return "이메일 형식이 올바르지 않아요.";
  return "";
}

export function validateCode(code) {
  if (!code) return "인증번호를 입력해 주세요.";
  if (!CODE_PATTERN.test(code)) return "인증번호 6자리 숫자를 입력해 주세요.";
  return "";
}

// ----- 도우미 함수들 -----

// 글자에서 숫자만 남기기 ("010-12a34" → "01234")
// replace(/\D/g, ""): 숫자가 아닌 것(\D)을 전부(g) 빈 글자로 바꿈
export function onlyDigits(value) {
  return value.replace(/\D/g, "");
}

// 전화번호를 입력하는 대로 하이픈(-) 자동으로 넣기
// "01012345678" → "010-1234-5678"
export function formatPhone(value) {
  const digits = onlyDigits(value).slice(0, 11); // 최대 11자리까지만
  if (digits.length < 4) return digits;
  if (digits.length < 8) return `${digits.slice(0, 3)}-${digits.slice(3)}`;
  // 10자리(011-123-4567)와 11자리(010-1234-5678)는 가운데 자리 수가 다름
  if (digits.length === 10) {
    return `${digits.slice(0, 3)}-${digits.slice(3, 6)}-${digits.slice(6)}`;
  }
  return `${digits.slice(0, 3)}-${digits.slice(3, 7)}-${digits.slice(7)}`;
}
