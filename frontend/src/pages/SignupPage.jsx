// =============================================================
// SignupPage.jsx — 회원가입 페이지
// -------------------------------------------------------------
// 입력 항목: 아이디(중복 확인) / 비밀번호 / 비밀번호 확인 / 이름 / 전화번호 / 이메일(인증)
// + 약관 동의 (필수 2개)
//
// 가입 버튼을 누르면
//   1. 화면에서 먼저 입력값 검사 (utils/validation.js)
//   2. 아이디 중복 확인, 이메일 인증을 했는지 확인
//   3. 서버에 회원가입 요청 (api/auth.js → 백엔드가 비밀번호를 bcrypt로 암호화해서 저장)
//   4. 성공하면 로그인 페이지로 이동
// =============================================================

import { useState, useEffect } from "react";
import { UserPlus, Loader2, CheckCircle2 } from "lucide-react";

import AuthLayout from "../components/AuthLayout";
import FormField from "../components/FormField";
import { checkLoginId, sendEmailCode, verifyEmailCode, signup } from "../api/auth";
import {
  validateLoginId,
  validatePassword,
  validatePasswordConfirm,
  validateName,
  validatePhone,
  validateEmail,
  validateCode,
  formatPhone,
  onlyDigits,
} from "../utils/validation";

// 초 → "04:59" 모양 글자로 바꾸기
// padStart(2, "0"): 한 자리 숫자 앞에 0을 붙여 두 자리로 (5 → "05")
function formatTime(seconds) {
  const m = String(Math.floor(seconds / 60)).padStart(2, "0");
  const s = String(seconds % 60).padStart(2, "0");
  return `${m}:${s}`;
}

// props
//  - onSignupSuccess(loginId): 가입 성공 시 실행 (App이 로그인 페이지로 보내줌)
//  - onGoLogin(): "로그인" 링크를 눌렀을 때 실행
function SignupPage({ onSignupSuccess, onGoLogin }) {
  // ===== 입력값 =====
  // 입력칸이 많아서 state를 하나하나 만들지 않고 객체 하나로 묶음
  const [form, setForm] = useState({
    loginId: "",
    password: "",
    passwordConfirm: "",
    name: "",
    phone: "", // 화면에는 "010-1234-5678"처럼 하이픈이 들어간 모양으로 저장
    email: "",
    code: "", // 이메일 인증번호
  });

  // errors: 입력칸별 에러 문구 { loginId: "…", email: "…" } (없으면 빈 객체)
  const [errors, setErrors] = useState({});

  // ===== 아이디 중복 확인 상태 =====
  // checkedId: 중복 확인을 마친 아이디 / available: 쓸 수 있는지 / message: 결과 문구
  const [idCheck, setIdCheck] = useState({ checkedId: "", available: false, message: "", loading: false });

  // ===== 이메일 인증 상태 =====
  // sentTo: 인증번호를 보낸 이메일 / verifiedEmail: 인증을 마친 이메일
  // expiresAt: 인증번호 만료 시각(밀리초) / remaining: 남은 초
  const [emailAuth, setEmailAuth] = useState({
    sentTo: "",
    verifiedEmail: "",
    expiresAt: 0,
    remaining: 0,
    devMode: false,
    sending: false,
    verifying: false,
    message: "",
  });

  // ===== 약관 동의 =====
  const [agree, setAgree] = useState({ terms: false, privacy: false });

  // 가입 요청 중인지 / 서버 에러 문구
  const [submitting, setSubmitting] = useState(false);
  const [serverError, setServerError] = useState("");

  // ===== 상태에서 계산하는 값들 =====
  const email = form.email.trim();
  // 지금 입력된 아이디가 "중복 확인 통과한 아이디"와 똑같아야 확인 완료로 인정
  // (확인 후에 아이디를 고치면 자동으로 다시 확인해야 하는 상태가 됨)
  const isIdChecked = idCheck.available && idCheck.checkedId === form.loginId;
  // 지금 입력된 이메일이 인증 끝난 이메일과 같아야 인증 완료
  const isEmailVerified = emailAuth.verifiedEmail !== "" && emailAuth.verifiedEmail === email;
  // 지금 이메일로 인증번호를 보낸 상태인지 (인증번호 입력칸을 보여줄지)
  const isCodeSent = emailAuth.sentTo !== "" && emailAuth.sentTo === email && !isEmailVerified;
  const allAgreed = agree.terms && agree.privacy;

  // ===== 인증번호 남은 시간 타이머 =====
  // expiresAt이 바뀔 때(인증번호를 새로 받을 때)마다 1초 간격 타이머를 새로 시작
  useEffect(() => {
    if (!emailAuth.expiresAt) return; // 아직 안 보냈으면 타이머 없음

    // setInterval(함수, 1000): 1초마다 함수 실행
    const timer = setInterval(() => {
      const left = Math.max(0, Math.ceil((emailAuth.expiresAt - Date.now()) / 1000));
      // prev => ({ ...prev, remaining: left }): 기존 값은 그대로 두고 remaining만 바꿈
      setEmailAuth((prev) => ({ ...prev, remaining: left }));
      if (left === 0) clearInterval(timer); // 0초가 되면 타이머 멈춤
    }, 1000);

    // 정리 함수: 새 타이머를 시작하기 전/페이지를 떠날 때 이전 타이머를 꼭 멈춤
    return () => clearInterval(timer);
  }, [emailAuth.expiresAt]);

  // ===== 입력값 바꾸기 공통 함수 =====
  // name: 바꿀 칸 이름("loginId" 등), value: 새 값
  const updateField = (name, value) => {
    // [name]: value → 변수 name에 들어 있는 글자를 key로 씀 (예: { loginId: value })
    setForm((prev) => ({ ...prev, [name]: value }));
    // 다시 입력하면 그 칸의 에러 문구는 지움
    setErrors((prev) => ({ ...prev, [name]: "" }));
    setServerError("");
  };

  // ===== 아이디 중복 확인 버튼 =====
  const handleCheckId = async () => {
    // 형식부터 확인
    const formatError = validateLoginId(form.loginId);
    if (formatError) {
      setErrors((prev) => ({ ...prev, loginId: formatError }));
      return;
    }
    setIdCheck((prev) => ({ ...prev, loading: true }));
    try {
      // await: 서버 응답이 올 때까지 기다림 (async 함수 안에서만 쓸 수 있음)
      const result = await checkLoginId(form.loginId);
      setIdCheck({
        checkedId: form.loginId,
        available: result.available,
        message: result.message,
        loading: false,
      });
      if (!result.available) setErrors((prev) => ({ ...prev, loginId: result.message }));
    } catch (error) {
      setIdCheck((prev) => ({ ...prev, loading: false }));
      setErrors((prev) => ({ ...prev, loginId: error.message }));
    }
  };

  // ===== 인증번호 받기 버튼 =====
  const handleSendCode = async () => {
    const formatError = validateEmail(form.email);
    if (formatError) {
      setErrors((prev) => ({ ...prev, email: formatError }));
      return;
    }
    setEmailAuth((prev) => ({ ...prev, sending: true, message: "" }));
    try {
      const result = await sendEmailCode(email);
      const seconds = result.expires_in || 300; // 서버가 알려준 유효시간(초), 기본 5분
      setEmailAuth((prev) => ({
        ...prev,
        sentTo: email,
        expiresAt: Date.now() + seconds * 1000,
        remaining: seconds,
        devMode: Boolean(result.dev_mode),
        sending: false,
        message: result.message,
      }));
      setForm((prev) => ({ ...prev, code: "" })); // 예전에 적은 인증번호 지우기
      setErrors((prev) => ({ ...prev, email: "", code: "" }));
    } catch (error) {
      setEmailAuth((prev) => ({ ...prev, sending: false }));
      setErrors((prev) => ({ ...prev, email: error.message }));
    }
  };

  // ===== 인증번호 확인 버튼 =====
  const handleVerifyCode = async () => {
    if (emailAuth.remaining === 0) {
      setErrors((prev) => ({ ...prev, code: "인증 시간이 지났어요. 인증번호를 다시 받아 주세요." }));
      return;
    }
    const formatError = validateCode(form.code);
    if (formatError) {
      setErrors((prev) => ({ ...prev, code: formatError }));
      return;
    }
    setEmailAuth((prev) => ({ ...prev, verifying: true }));
    try {
      const result = await verifyEmailCode(email, form.code);
      setEmailAuth((prev) => ({
        ...prev,
        verifiedEmail: email,
        verifying: false,
        expiresAt: 0, // 인증 끝났으니 타이머 멈춤
        message: result.message,
      }));
      setErrors((prev) => ({ ...prev, email: "", code: "" }));
    } catch (error) {
      setEmailAuth((prev) => ({ ...prev, verifying: false }));
      setErrors((prev) => ({ ...prev, code: error.message }));
    }
  };

  // ===== 약관 "전체 동의" =====
  const handleAgreeAll = (checked) => {
    setAgree({ terms: checked, privacy: checked });
    setErrors((prev) => ({ ...prev, agree: "" }));
  };

  // ===== 가입하기 버튼 (form 제출) =====
  const handleSubmit = async (event) => {
    event.preventDefault(); // 페이지 새로고침 막기

    // 1. 모든 칸 검사해서 에러 모으기
    const nextErrors = {
      loginId: validateLoginId(form.loginId) || (isIdChecked ? "" : "아이디 중복 확인을 해 주세요."),
      password: validatePassword(form.password),
      passwordConfirm: validatePasswordConfirm(form.password, form.passwordConfirm),
      name: validateName(form.name),
      phone: validatePhone(form.phone),
      email: validateEmail(form.email) || (isEmailVerified ? "" : "이메일 인증을 완료해 주세요."),
      agree: allAgreed ? "" : "필수 약관에 모두 동의해 주세요.",
    };
    setErrors(nextErrors);

    // Object.values: 객체의 값들만 배열로 → 하나라도 에러 문구가 있으면 멈춤
    if (Object.values(nextErrors).some((message) => message)) return;

    // 2. 서버에 가입 요청
    setSubmitting(true);
    setServerError("");
    try {
      await signup({
        loginId: form.loginId,
        password: form.password,
        name: form.name.trim(),
        phone: onlyDigits(form.phone), // 서버에는 숫자만 보냄
        email,
      });
      // 3. 성공 → 부모(App)에게 알려서 로그인 페이지로 이동
      onSignupSuccess(form.loginId);
    } catch (error) {
      // 서버 에러 문구에 따라 해당 칸 아래에 보여주기
      if (error.message.includes("아이디")) setErrors((prev) => ({ ...prev, loginId: error.message }));
      else if (error.message.includes("이메일")) setErrors((prev) => ({ ...prev, email: error.message }));
      else setServerError(error.message);
    } finally {
      // finally: 성공하든 실패하든 마지막에 꼭 실행
      setSubmitting(false);
    }
  };

  return (
    <AuthLayout
      panelTitle={"생각이 글이 되는\n첫 걸음을 함께해요"}
      panelDesc={"가입하고 나만의 생각 노트를\n차곡차곡 쌓아보세요."}
    >
      <div className="auth-form-head">
        <h1>
          <UserPlus size={26} /> 회원가입
        </h1>
        <p>생각한줄과 함께 글쓰기를 시작해보세요.</p>
      </div>

      {/* noValidate: 브라우저 기본 검사 말풍선 대신 우리가 만든 에러 문구를 쓰려고 끔 */}
      <form className="auth-form" onSubmit={handleSubmit} noValidate>
        {/* ----- 아이디 + 중복 확인 ----- */}
        <FormField
          id="signup-login-id"
          label="아이디"
          value={form.loginId}
          // 아이디는 소문자만 쓰니까 대문자를 쳐도 소문자로 바꿔서 저장
          onChange={(value) => updateField("loginId", value.toLowerCase())}
          placeholder="영문 소문자로 시작하는 4~20자"
          autoComplete="username"
          maxLength={20}
          error={errors.loginId}
          success={isIdChecked ? idCheck.message : ""}
          action={
            <button
              type="button"
              className="field-button"
              onClick={handleCheckId}
              disabled={idCheck.loading || isIdChecked}
            >
              {idCheck.loading ? <Loader2 className="spin" size={16} /> : isIdChecked ? "확인 완료" : "중복 확인"}
            </button>
          }
        />

        {/* ----- 비밀번호 ----- */}
        <FormField
          id="signup-password"
          label="비밀번호"
          type="password"
          value={form.password}
          onChange={(value) => updateField("password", value)}
          placeholder="영문, 숫자 포함 8자 이상"
          autoComplete="new-password"
          maxLength={64}
          error={errors.password}
          hint="영문과 숫자를 포함해 8~64자로 입력해 주세요."
        />

        <FormField
          id="signup-password-confirm"
          label="비밀번호 확인"
          type="password"
          value={form.passwordConfirm}
          onChange={(value) => updateField("passwordConfirm", value)}
          placeholder="비밀번호를 한 번 더 입력해 주세요"
          autoComplete="new-password"
          maxLength={64}
          error={errors.passwordConfirm}
          // 둘 다 입력했고 같으면 초록 문구
          success={form.passwordConfirm && form.password === form.passwordConfirm ? "비밀번호가 일치해요." : ""}
        />

        {/* ----- 이름 + 전화번호 (PC에서는 한 줄에 두 칸) ----- */}
        <div className="form-grid-2">
          <FormField
            id="signup-name"
            label="이름"
            value={form.name}
            onChange={(value) => updateField("name", value)}
            placeholder="홍길동"
            autoComplete="name"
            maxLength={20}
            error={errors.name}
          />
          <FormField
            id="signup-phone"
            label="전화번호"
            type="tel"
            value={form.phone}
            // 입력하는 대로 010-1234-5678 모양으로 하이픈 자동 삽입
            onChange={(value) => updateField("phone", formatPhone(value))}
            placeholder="010-1234-5678"
            autoComplete="tel"
            inputMode="numeric"
            maxLength={13}
            error={errors.phone}
          />
        </div>

        {/* ----- 이메일 + 인증번호 받기 ----- */}
        <FormField
          id="signup-email"
          label="이메일"
          type="email"
          value={form.email}
          onChange={(value) => updateField("email", value)}
          placeholder="example@email.com"
          autoComplete="email"
          maxLength={100}
          error={errors.email}
          success={isEmailVerified ? "이메일 인증이 완료됐어요." : ""}
          disabled={isEmailVerified} // 인증 끝나면 못 바꾸게 (바꾸려면 아래 "변경" 버튼)
          action={
            isEmailVerified ? (
              <button
                type="button"
                className="field-button ghost"
                // 이메일 변경: 인증 상태를 초기화해서 다시 입력할 수 있게
                onClick={() =>
                  setEmailAuth((prev) => ({ ...prev, verifiedEmail: "", sentTo: "", expiresAt: 0, message: "" }))
                }
              >
                변경
              </button>
            ) : (
              <button
                type="button"
                className="field-button"
                onClick={handleSendCode}
                disabled={emailAuth.sending}
              >
                {emailAuth.sending ? (
                  <Loader2 className="spin" size={16} />
                ) : isCodeSent ? (
                  "재전송"
                ) : (
                  "인증번호 받기"
                )}
              </button>
            )
          }
        />

        {/* ----- 인증번호 입력 (인증번호를 보낸 뒤에만 보임) ----- */}
        {isCodeSent && (
          <FormField
            id="signup-code"
            label="인증번호"
            value={form.code}
            // 숫자만 6자리까지
            onChange={(value) => updateField("code", onlyDigits(value).slice(0, 6))}
            placeholder="메일로 받은 6자리 숫자"
            autoComplete="one-time-code"
            inputMode="numeric"
            maxLength={6}
            error={errors.code}
            hint={
              emailAuth.devMode
                ? "개발 모드: 메일 대신 백엔드 터미널(또는 F12 콘솔)에 인증번호가 표시돼요."
                : `${email} 으로 인증번호를 보냈어요. 메일이 안 보이면 스팸함도 확인해 주세요.`
            }
            // 남은 시간 (1분 이하면 빨갛게)
            suffix={
              <span className={emailAuth.remaining <= 60 ? "timer urgent" : "timer"}>
                {formatTime(emailAuth.remaining)}
              </span>
            }
            action={
              <button
                type="button"
                className="field-button"
                onClick={handleVerifyCode}
                disabled={emailAuth.verifying}
              >
                {emailAuth.verifying ? <Loader2 className="spin" size={16} /> : "확인"}
              </button>
            }
          />
        )}

        {/* ----- 약관 동의 ----- */}
        <fieldset className="agree-box">
          {/* legend: fieldset 묶음의 제목 (화면에서는 숨김) */}
          <legend className="sr-only">약관 동의</legend>

          <label className="agree-all">
            <input
              type="checkbox"
              checked={allAgreed}
              onChange={(event) => handleAgreeAll(event.target.checked)}
            />
            <span>전체 동의</span>
          </label>

          <label className="agree-item">
            <input
              type="checkbox"
              checked={agree.terms}
              onChange={(event) => {
                setAgree((prev) => ({ ...prev, terms: event.target.checked }));
                setErrors((prev) => ({ ...prev, agree: "" }));
              }}
            />
            <span>
              <em>(필수)</em> 서비스 이용약관 동의
            </span>
          </label>

          <label className="agree-item">
            <input
              type="checkbox"
              checked={agree.privacy}
              onChange={(event) => {
                setAgree((prev) => ({ ...prev, privacy: event.target.checked }));
                setErrors((prev) => ({ ...prev, agree: "" }));
              }}
            />
            <span>
              <em>(필수)</em> 개인정보 수집 및 이용 동의
            </span>
          </label>

          {errors.agree && (
            <p className="form-error" role="alert">
              {errors.agree}
            </p>
          )}
        </fieldset>

        {/* 서버에서 온 기타 에러 */}
        {serverError && (
          <p className="auth-server-error" role="alert">
            {serverError}
          </p>
        )}

        {/* 가입하기 버튼 (요청 중에는 빙글빙글 + 비활성화) */}
        <button type="submit" className="auth-submit" disabled={submitting}>
          {submitting ? (
            <>
              <Loader2 className="spin" size={18} /> 가입하는 중...
            </>
          ) : (
            <>
              <CheckCircle2 size={18} /> 가입하기
            </>
          )}
        </button>

        <p className="auth-switch">
          이미 계정이 있나요?
          <button type="button" onClick={onGoLogin}>
            로그인
          </button>
        </p>
      </form>
    </AuthLayout>
  );
}

export default SignupPage;
