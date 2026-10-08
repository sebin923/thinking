// =============================================================
// LoginPage.jsx — 로그인 페이지 (아이디 + 비밀번호)
// -------------------------------------------------------------
// 로그인 버튼을 누르면
//   1. 빈 칸이 없는지 확인
//   2. 서버에 로그인 요청 (api/auth.js)
//      → 서버가 저장된 bcrypt 암호화 값과 비교해서 맞으면 토큰(JWT)을 줌
//   3. 성공하면 부모(App)에게 사용자 정보 + 토큰을 넘김
// =============================================================

import { useState } from "react";
import { LogIn, Loader2, CheckCircle2 } from "lucide-react";

import AuthLayout from "../components/AuthLayout";
import FormField from "../components/FormField";
import { login } from "../api/auth";

// props
//  - onLogin(result, remember): 로그인 성공 시 실행 (result = 서버 응답, remember = 로그인 유지 체크 여부)
//  - onGoSignup(): "회원가입" 링크를 눌렀을 때 실행
//  - initialLoginId: 처음부터 채워둘 아이디 (회원가입 직후 넘어왔을 때)
//  - notice: 위쪽에 보여줄 초록 안내 문구 (예: "회원가입이 완료됐어요.")
function LoginPage({ onLogin, onGoSignup, initialLoginId = "", notice = "" }) {
  const [loginId, setLoginId] = useState(initialLoginId);
  const [password, setPassword] = useState("");

  // remember: "로그인 상태 유지" 체크 여부
  const [remember, setRemember] = useState(false);

  // errors: 칸별 에러 / serverError: 아이디·비밀번호 불일치 같은 서버 에러
  const [errors, setErrors] = useState({});
  const [serverError, setServerError] = useState("");

  // loading: 로그인 요청 중인지 (버튼 비활성화 + 빙글빙글 아이콘)
  const [loading, setLoading] = useState(false);

  // findNotice: "아이디/비밀번호 찾기"를 눌렀을 때 보여줄 안내
  const [findNotice, setFindNotice] = useState("");

  const handleSubmit = async (event) => {
    event.preventDefault(); // 페이지 새로고침 막기

    // 1. 빈 칸 검사 (로그인에서는 형식까지 자세히 검사하지 않음 — 틀리면 서버가 알려줌)
    const nextErrors = {
      loginId: loginId.trim() ? "" : "아이디를 입력해 주세요.",
      password: password ? "" : "비밀번호를 입력해 주세요.",
    };
    setErrors(nextErrors);
    if (nextErrors.loginId || nextErrors.password) return;

    // 2. 서버에 로그인 요청
    setLoading(true);
    setServerError("");
    try {
      const result = await login(loginId.trim(), password);
      // 3. 성공 → App이 사용자 정보를 저장하고 화면을 바꿈
      onLogin(result, remember);
    } catch (error) {
      setServerError(error.message);
      setPassword(""); // 보안상 틀리면 비밀번호 칸 비우기
    } finally {
      setLoading(false);
    }
  };

  return (
    <AuthLayout
      panelTitle={"다시 만나서\n반가워요 :)"}
      panelDesc={"로그인하고 이어서\n생각을 글로 완성해보세요."}
    >
      <div className="auth-form-head">
        <h1>
          <LogIn size={26} /> 로그인
        </h1>
        <p>아이디와 비밀번호를 입력해 주세요.</p>
      </div>

      {/* 회원가입 직후 넘어왔을 때 초록 안내 */}
      {notice && (
        <p className="auth-notice">
          <CheckCircle2 size={18} />
          {notice}
        </p>
      )}

      <form className="auth-form" onSubmit={handleSubmit} noValidate>
        <FormField
          id="login-id"
          label="아이디"
          value={loginId}
          onChange={(value) => {
            setLoginId(value.toLowerCase()); // 아이디는 소문자로 통일
            setErrors((prev) => ({ ...prev, loginId: "" }));
            setServerError("");
          }}
          placeholder="아이디를 입력해 주세요"
          autoComplete="username"
          maxLength={20}
          error={errors.loginId}
        />

        <FormField
          id="login-password"
          label="비밀번호"
          type="password"
          value={password}
          onChange={(value) => {
            setPassword(value);
            setErrors((prev) => ({ ...prev, password: "" }));
            setServerError("");
          }}
          placeholder="비밀번호를 입력해 주세요"
          autoComplete="current-password"
          maxLength={64}
          error={errors.password}
        />

        {/* 로그인 유지 + 찾기 링크 */}
        <div className="login-options">
          <label className="remember">
            <input
              type="checkbox"
              checked={remember}
              onChange={(event) => setRemember(event.target.checked)}
            />
            <span>로그인 상태 유지</span>
          </label>
          <button
            type="button"
            className="text-link"
            onClick={() => setFindNotice("아이디·비밀번호 찾기는 준비 중이에요.")}
          >
            아이디 / 비밀번호 찾기
          </button>
        </div>

        {findNotice && <p className="form-hint">{findNotice}</p>}

        {/* 아이디·비밀번호 불일치 등 서버 에러 */}
        {serverError && (
          <p className="auth-server-error" role="alert">
            {serverError}
          </p>
        )}

        <button type="submit" className="auth-submit" disabled={loading}>
          {loading ? (
            <>
              <Loader2 className="spin" size={18} /> 로그인 중...
            </>
          ) : (
            <>
              <LogIn size={18} /> 로그인
            </>
          )}
        </button>

        <p className="auth-switch">
          아직 계정이 없나요?
          <button type="button" onClick={onGoSignup}>
            회원가입
          </button>
        </p>
      </form>
    </AuthLayout>
  );
}

export default LoginPage;
