// =============================================================
// FindAccountPage.jsx — 아이디 찾기 / 비밀번호 찾기 페이지
// -------------------------------------------------------------
// 로그인 화면의 "아이디 / 비밀번호 찾기"를 누르면 오는 화면
// 위쪽 탭 [아이디 찾기 | 비밀번호 찾기]로 바꿔 가며 씀
//
// 아이디 찾기
//   ① 이름 + 가입한 이메일 입력 → "인증번호 받기"
//   ② 메일로 받은 6자리 입력 → "아이디 확인하기"
//   ③ 아이디를 보여줌 → "이 아이디로 로그인" / "비밀번호 찾기"
//
// 비밀번호 찾기
//   ① 아이디 + 가입한 이메일 입력 → "인증번호 받기"
//   ② 메일로 받은 6자리 입력 → "인증하기"
//   ③ 새 비밀번호 + 확인 입력 → "비밀번호 변경" → 로그인 화면으로 (아이디는 미리 채워 줌)
//
// 서버 요청은 api/auth.js (백엔드 routers/auth.py 아래쪽 "아이디 찾기 / 비밀번호 찾기")
// 화면 모양은 로그인·회원가입과 같은 AuthLayout + FormField를 그대로 씀
// =============================================================

import { useState, useEffect } from "react";
import { KeyRound, Loader2, CheckCircle2, UserRound, LogIn } from "lucide-react";

import AuthLayout from "../components/AuthLayout";
import FormField from "../components/FormField";
// 위쪽 탭: 퀴즈 화면의 [맞춤법 | 문법] 탭과 같은 부품 (탭 목록만 바꿔서 씀)
import CategoryTabs from "../components/CategoryTabs";
import { sendFindIdCode, verifyFindIdCode, sendResetCode, verifyResetCode, resetPassword } from "../api/auth";
import {
  validateLoginId,
  validatePassword,
  validatePasswordConfirm,
  validateName,
  validateEmail,
  validateCode,
  onlyDigits,
} from "../utils/validation";

// 위쪽 탭 목록
const TABS = [
  { key: "id", label: "아이디 찾기" },
  { key: "password", label: "비밀번호 찾기" },
];

// 초 → "04:59" 모양 글자 (회원가입 화면과 같은 모양)
function formatTime(seconds) {
  const m = String(Math.floor(seconds / 60)).padStart(2, "0");
  const s = String(seconds % 60).padStart(2, "0");
  return `${m}:${s}`;
}

// 날짜 → "2026.11.03" (가입일 표시용)
function formatDate(value) {
  const date = new Date(value);
  if (Number.isNaN(date.getTime())) return "";
  const two = (n) => String(n).padStart(2, "0");
  return `${date.getFullYear()}.${two(date.getMonth() + 1)}.${two(date.getDate())}`;
}

// =============================================================
// 인증번호 남은 시간 타이머 (두 탭이 같이 씀)
// -------------------------------------------------------------
// expiresAt: 인증번호 만료 시각(밀리초, 0이면 아직 안 보냄) → 남은 초를 돌려줌
// =============================================================
function useCodeTimer(expiresAt) {
  const [remaining, setRemaining] = useState(0);

  useEffect(() => {
    if (!expiresAt) return undefined; // 아직 안 보냈으면 타이머 없음
    // 1초마다 남은 시간 다시 계산 (setInterval: 정해진 간격마다 함수 실행)
    const tick = () => setRemaining(Math.max(0, Math.ceil((expiresAt - Date.now()) / 1000)));
    tick(); // 처음 한 번은 바로
    const timer = setInterval(tick, 1000);
    // 정리 함수: 새 인증번호를 받거나 화면을 떠나면 이전 타이머를 멈춤
    return () => clearInterval(timer);
  }, [expiresAt]);

  return remaining;
}

// 서버가 준 에러 문구가 "인증번호" 칸 문제인지 (그 칸 아래에 빨갛게 보여주려고)
const isCodeError = (message) => message.includes("인증번호") && !message.includes("초 후에");

// 인증번호 칸 아래 안내 문구
const codeHint = (devMode, email) =>
  devMode
    ? "개발 모드: 메일 대신 백엔드 터미널에 인증번호가 표시돼요."
    : `${email} 으로 인증번호를 보냈어요. 메일이 안 보이면 스팸함도 확인해 주세요.`;

// =============================================================
// 아이디 찾기
// =============================================================
// props
//  - onGoLogin(loginId): "이 아이디로 로그인" → 로그인 화면 (아이디 미리 채움)
//  - onFindPassword(prefill): "비밀번호 찾기" → 비밀번호 찾기 탭 (아이디·이메일 미리 채움)
function FindIdForm({ onGoLogin, onFindPassword }) {
  const [form, setForm] = useState({ name: "", email: "", code: "" });
  const [errors, setErrors] = useState({});
  const [serverError, setServerError] = useState("");

  // sentKey: 인증번호를 보낸 "이름|이메일" (보낸 뒤 이름·이메일을 고치면 다시 받아야 함)
  const [sent, setSent] = useState({ sentKey: "", expiresAt: 0, devMode: false });
  const [sending, setSending] = useState(false);
  const [verifying, setVerifying] = useState(false);
  // result: 찾은 아이디 { login_id, created_at } (찾기 전에는 null)
  const [result, setResult] = useState(null);

  const name = form.name.trim();
  const email = form.email.trim();
  const remaining = useCodeTimer(sent.expiresAt);
  const isCodeSent = sent.sentKey !== "" && sent.sentKey === `${name}|${email}`;

  // 입력값 바꾸기 (그 칸 에러와 서버 에러는 지움)
  const updateField = (field, value) => {
    setForm((prev) => ({ ...prev, [field]: value }));
    setErrors((prev) => ({ ...prev, [field]: "" }));
    setServerError("");
  };

  // ① 인증번호 받기
  const handleSendCode = async () => {
    const nextErrors = { name: validateName(form.name), email: validateEmail(form.email) };
    setErrors(nextErrors);
    if (nextErrors.name || nextErrors.email) return;

    setSending(true);
    setServerError("");
    try {
      const response = await sendFindIdCode(name, email);
      const seconds = response.expires_in || 300; // 서버가 알려준 유효시간(초), 기본 5분
      setSent({ sentKey: `${name}|${email}`, expiresAt: Date.now() + seconds * 1000, devMode: !!response.dev_mode });
      setForm((prev) => ({ ...prev, code: "" })); // 예전에 적은 인증번호 지우기
    } catch (error) {
      setServerError(error.message); // 예: "입력한 정보와 일치하는 회원이 없어요."
    } finally {
      setSending(false);
    }
  };

  // ② 인증번호 확인 → 아이디 받기
  const handleSubmit = async (event) => {
    event.preventDefault(); // form 제출 시 페이지 새로고침 막기
    if (!isCodeSent) {
      setServerError("먼저 인증번호를 받아 주세요.");
      return;
    }
    if (remaining === 0) {
      setErrors((prev) => ({ ...prev, code: "인증 시간이 지났어요. 인증번호를 다시 받아 주세요." }));
      return;
    }
    const codeError = validateCode(form.code);
    if (codeError) {
      setErrors((prev) => ({ ...prev, code: codeError }));
      return;
    }

    setVerifying(true);
    setServerError("");
    try {
      const response = await verifyFindIdCode(name, email, form.code);
      setResult({ login_id: response.login_id, created_at: response.created_at });
    } catch (error) {
      if (isCodeError(error.message)) setErrors((prev) => ({ ...prev, code: error.message }));
      else setServerError(error.message);
    } finally {
      setVerifying(false);
    }
  };

  // ③ 찾은 아이디 보여주기
  if (result) {
    return (
      <div className="find-result" role="status">
        <span className="find-result-icon" aria-hidden="true">
          <UserRound size={26} />
        </span>
        <p className="find-result-label">{name} 님의 아이디는</p>
        <p className="find-result-id">{result.login_id}</p>
        {result.created_at && <p className="find-result-date">{formatDate(result.created_at)} 가입</p>}

        <button type="button" className="auth-submit" onClick={() => onGoLogin(result.login_id)}>
          <LogIn size={18} /> 이 아이디로 로그인
        </button>
        <p className="auth-switch">
          비밀번호도 기억나지 않나요?
          <button type="button" onClick={() => onFindPassword({ loginId: result.login_id, email })}>
            비밀번호 찾기
          </button>
        </p>
      </div>
    );
  }

  return (
    <form className="auth-form" onSubmit={handleSubmit} noValidate>
      <FormField
        id="find-id-name"
        label="이름"
        value={form.name}
        onChange={(value) => updateField("name", value)}
        placeholder="가입할 때 적은 이름"
        autoComplete="name"
        maxLength={20}
        error={errors.name}
      />

      <FormField
        id="find-id-email"
        label="가입한 이메일"
        type="email"
        value={form.email}
        onChange={(value) => updateField("email", value)}
        placeholder="example@email.com"
        autoComplete="email"
        maxLength={100}
        error={errors.email}
        action={
          <button type="button" className="field-button" onClick={handleSendCode} disabled={sending}>
            {sending ? <Loader2 className="spin" size={16} /> : isCodeSent ? "재전송" : "인증번호 받기"}
          </button>
        }
      />

      {/* 인증번호 입력 (보낸 뒤에만 보임) */}
      {isCodeSent && (
        <FormField
          id="find-id-code"
          label="인증번호"
          value={form.code}
          onChange={(value) => updateField("code", onlyDigits(value).slice(0, 6))} // 숫자만 6자리까지
          placeholder="메일로 받은 6자리 숫자"
          autoComplete="one-time-code"
          inputMode="numeric"
          maxLength={6}
          error={errors.code}
          hint={codeHint(sent.devMode, email)}
          suffix={<span className={remaining <= 60 ? "timer urgent" : "timer"}>{formatTime(remaining)}</span>}
        />
      )}

      {serverError && (
        <p className="auth-server-error" role="alert">
          {serverError}
        </p>
      )}

      <button type="submit" className="auth-submit" disabled={verifying}>
        {verifying ? (
          <>
            <Loader2 className="spin" size={18} /> 확인하는 중...
          </>
        ) : (
          "아이디 확인하기"
        )}
      </button>
    </form>
  );
}

// =============================================================
// 비밀번호 찾기 (재설정)
// =============================================================
// props
//  - prefill: 아이디 찾기에서 넘어왔을 때 미리 채울 { loginId, email } (없으면 빈칸)
//  - onDone(loginId): 비밀번호를 바꾼 뒤 → 로그인 화면 (아이디 미리 채움 + 안내 문구)
function ResetPasswordForm({ prefill, onDone }) {
  const [form, setForm] = useState({
    loginId: prefill?.loginId || "",
    email: prefill?.email || "",
    code: "",
    password: "",
    passwordConfirm: "",
  });
  const [errors, setErrors] = useState({});
  const [serverError, setServerError] = useState("");

  const [sent, setSent] = useState({ sentKey: "", expiresAt: 0, devMode: false });
  const [sending, setSending] = useState(false);
  // verified: 인증번호 확인을 마쳤는지 (마치면 아이디·이메일·인증번호 칸을 잠그고 새 비밀번호 칸을 보여줌)
  const [verified, setVerified] = useState(false);
  const [submitting, setSubmitting] = useState(false);

  const loginId = form.loginId.trim();
  const email = form.email.trim();
  const remaining = useCodeTimer(sent.expiresAt);
  const isCodeSent = sent.sentKey !== "" && sent.sentKey === `${loginId}|${email}`;

  const updateField = (field, value) => {
    setForm((prev) => ({ ...prev, [field]: value }));
    setErrors((prev) => ({ ...prev, [field]: "" }));
    setServerError("");
  };

  // 처음부터 다시 (인증을 마친 뒤 아이디·이메일을 바꾸고 싶을 때)
  const handleRestart = () => {
    setVerified(false);
    setSent({ sentKey: "", expiresAt: 0, devMode: false });
    setForm((prev) => ({ ...prev, code: "", password: "", passwordConfirm: "" }));
    setErrors({});
    setServerError("");
  };

  // ① 인증번호 받기
  const handleSendCode = async () => {
    const nextErrors = {
      loginId: loginId ? validateLoginId(loginId) : "아이디를 입력해 주세요.",
      email: validateEmail(form.email),
    };
    setErrors(nextErrors);
    if (nextErrors.loginId || nextErrors.email) return;

    setSending(true);
    setServerError("");
    try {
      const response = await sendResetCode(loginId, email);
      const seconds = response.expires_in || 300;
      setSent({ sentKey: `${loginId}|${email}`, expiresAt: Date.now() + seconds * 1000, devMode: !!response.dev_mode });
      setForm((prev) => ({ ...prev, code: "" }));
    } catch (error) {
      setServerError(error.message);
    } finally {
      setSending(false);
    }
  };

  // ② 인증하기 / ③ 비밀번호 변경 (아래 큰 버튼 하나가 단계에 따라 다르게 동작)
  const handleSubmit = async (event) => {
    event.preventDefault();
    setServerError("");

    // ----- ② 인증번호 확인 -----
    if (!verified) {
      if (!isCodeSent) {
        setServerError("먼저 인증번호를 받아 주세요.");
        return;
      }
      if (remaining === 0) {
        setErrors((prev) => ({ ...prev, code: "인증 시간이 지났어요. 인증번호를 다시 받아 주세요." }));
        return;
      }
      const codeError = validateCode(form.code);
      if (codeError) {
        setErrors((prev) => ({ ...prev, code: codeError }));
        return;
      }
      setSubmitting(true);
      try {
        await verifyResetCode(loginId, email, form.code);
        setVerified(true);
      } catch (error) {
        if (isCodeError(error.message)) setErrors((prev) => ({ ...prev, code: error.message }));
        else setServerError(error.message);
      } finally {
        setSubmitting(false);
      }
      return;
    }

    // ----- ③ 새 비밀번호 저장 -----
    const nextErrors = {
      password: validatePassword(form.password),
      passwordConfirm: validatePasswordConfirm(form.password, form.passwordConfirm),
    };
    setErrors(nextErrors);
    if (nextErrors.password || nextErrors.passwordConfirm) return;

    setSubmitting(true);
    try {
      await resetPassword(loginId, email, form.code, form.password);
      onDone(loginId); // 로그인 화면으로 (아이디 미리 채움)
    } catch (error) {
      // 인증 시간이 지났으면 처음부터 다시 받아야 함
      if (error.message.includes("인증")) {
        setVerified(false);
        setSent({ sentKey: "", expiresAt: 0, devMode: false });
      }
      if (error.message.includes("비밀번호")) setErrors((prev) => ({ ...prev, password: error.message }));
      else setServerError(error.message);
    } finally {
      setSubmitting(false);
    }
  };

  return (
    <form className="auth-form" onSubmit={handleSubmit} noValidate>
      <FormField
        id="reset-login-id"
        label="아이디"
        value={form.loginId}
        onChange={(value) => updateField("loginId", value.toLowerCase())} // 아이디는 소문자로 통일
        placeholder="아이디를 입력해 주세요"
        autoComplete="username"
        maxLength={20}
        error={errors.loginId}
        disabled={verified}
      />

      <FormField
        id="reset-email"
        label="가입한 이메일"
        type="email"
        value={form.email}
        onChange={(value) => updateField("email", value)}
        placeholder="example@email.com"
        autoComplete="email"
        maxLength={100}
        error={errors.email}
        success={verified ? "본인 확인이 완료됐어요." : ""}
        disabled={verified}
        action={
          verified ? (
            <button type="button" className="field-button ghost" onClick={handleRestart}>
              변경
            </button>
          ) : (
            <button type="button" className="field-button" onClick={handleSendCode} disabled={sending}>
              {sending ? <Loader2 className="spin" size={16} /> : isCodeSent ? "재전송" : "인증번호 받기"}
            </button>
          )
        }
      />

      {/* 인증번호 입력 (보낸 뒤, 인증 전까지만) */}
      {isCodeSent && !verified && (
        <FormField
          id="reset-code"
          label="인증번호"
          value={form.code}
          onChange={(value) => updateField("code", onlyDigits(value).slice(0, 6))}
          placeholder="메일로 받은 6자리 숫자"
          autoComplete="one-time-code"
          inputMode="numeric"
          maxLength={6}
          error={errors.code}
          hint={codeHint(sent.devMode, email)}
          suffix={<span className={remaining <= 60 ? "timer urgent" : "timer"}>{formatTime(remaining)}</span>}
        />
      )}

      {/* 새 비밀번호 (인증을 마친 뒤에만) */}
      {verified && (
        <>
          <FormField
            id="reset-password"
            label="새 비밀번호"
            type="password"
            value={form.password}
            onChange={(value) => updateField("password", value)}
            placeholder="영문 + 숫자 8자 이상"
            autoComplete="new-password"
            maxLength={64}
            error={errors.password}
            hint="영문과 숫자를 섞어 8~64자로 입력해 주세요."
          />
          <FormField
            id="reset-password-confirm"
            label="새 비밀번호 확인"
            type="password"
            value={form.passwordConfirm}
            onChange={(value) => updateField("passwordConfirm", value)}
            placeholder="새 비밀번호를 한 번 더 입력"
            autoComplete="new-password"
            maxLength={64}
            error={errors.passwordConfirm}
            success={
              form.passwordConfirm && form.password === form.passwordConfirm ? "비밀번호가 일치해요." : ""
            }
          />
        </>
      )}

      {serverError && (
        <p className="auth-server-error" role="alert">
          {serverError}
        </p>
      )}

      <button type="submit" className="auth-submit" disabled={submitting}>
        {submitting ? (
          <>
            <Loader2 className="spin" size={18} /> {verified ? "바꾸는 중..." : "확인하는 중..."}
          </>
        ) : verified ? (
          <>
            <CheckCircle2 size={18} /> 비밀번호 변경
          </>
        ) : (
          "인증하기"
        )}
      </button>
    </form>
  );
}

// =============================================================
// 페이지 (탭 + 위 두 폼)
// =============================================================
// props
//  - initialTab: 처음 열 탭 ("id" 또는 "password", 기본 "id")
//  - onGoLogin(loginId, message): 로그인 화면으로 (아이디·안내 문구를 미리 채움, 둘 다 없어도 됨)
//  - onGoSignup(): "회원가입" 링크
function FindAccountPage({ initialTab = "id", onGoLogin, onGoSignup }) {
  const [tab, setTab] = useState(initialTab === "password" ? "password" : "id");
  // 아이디 찾기 → "비밀번호 찾기"로 넘어갈 때 채워 줄 값
  const [prefill, setPrefill] = useState(null);

  // 탭 바꾸기 (직접 누르면 미리 채운 값은 비움)
  const changeTab = (key) => {
    setPrefill(null);
    setTab(key);
  };

  return (
    <AuthLayout
      panelTitle={"괜찮아요,\n다시 찾아 드릴게요 :)"}
      panelDesc={"가입할 때 쓴 이메일로\n본인 확인을 해요."}
    >
      <div className="auth-form-head">
        <h1>
          <KeyRound size={26} /> 아이디 / 비밀번호 찾기
        </h1>
        <p>
          {tab === "id"
            ? "이름과 가입한 이메일로 아이디를 찾아요."
            : "아이디와 가입한 이메일로 본인 확인 후 새 비밀번호를 정해요."}
        </p>
      </div>

      <div className="find-tabs">
        <CategoryTabs value={tab} onChange={changeTab} items={TABS} ariaLabel="찾을 항목" />
      </div>

      {/* key: 탭이 바뀌면 폼을 새로 만들어서 입력값·타이머가 처음부터 시작 */}
      {tab === "id" ? (
        <FindIdForm
          key="id"
          onGoLogin={(loginId) => onGoLogin(loginId)}
          onFindPassword={(values) => {
            setPrefill(values);
            setTab("password");
          }}
        />
      ) : (
        <ResetPasswordForm
          key={`password-${prefill?.loginId || ""}`}
          prefill={prefill}
          onDone={(loginId) => onGoLogin(loginId, "비밀번호를 바꿨어요. 새 비밀번호로 로그인해 주세요.")}
        />
      )}

      <p className="auth-switch find-switch">
        생각났나요?
        <button type="button" onClick={() => onGoLogin()}>
          로그인
        </button>
        <span className="find-switch-sep" aria-hidden="true">
          ·
        </span>
        <button type="button" onClick={onGoSignup}>
          회원가입
        </button>
      </p>
    </AuthLayout>
  );
}

export default FindAccountPage;
