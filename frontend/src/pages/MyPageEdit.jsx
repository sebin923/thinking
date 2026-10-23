// =============================================================
// MyPageEdit.jsx — 마이페이지 수정 화면
// -------------------------------------------------------------
// 마이페이지 프로필 카드의 "마이페이지 수정" 버튼을 누르면 오는 화면
// 위쪽 탭 3개로 나눠서 하나씩 보여줌
//   1. 회원정보   : 이름, 전화번호, 이메일 바꾸기 (이메일은 새 주소로 인증해야 바뀜, 아이디는 못 바꿈)
//   2. 비밀번호   : 지금 비밀번호 확인 → 새 비밀번호로 바꾸기
//   3. 회원 탈퇴  : 지워지는 내용 안내 → 확인 체크 + 비밀번호 입력 → 탈퇴
//
// 파일 구조: 맨 아래 MyPageEdit(부모)가 프로필을 불러오고 탭을 고르면,
//           위에 있는 ProfileSection / PasswordSection / WithdrawSection 중 하나를 보여줌
//
// 데이터: 백엔드 routers/mypage.py (PUT /profile, PUT /password, POST /withdraw)
//        이메일 인증은 회원가입과 같은 API (api/auth.js의 sendEmailCode, verifyEmailCode)
// =============================================================

import { useState, useEffect } from "react";
import {
  ArrowLeft,
  UserRound,
  KeyRound,
  UserX,
  Loader2,
  CheckCircle2,
  AlertTriangle,
  RefreshCw,
  LogIn,
} from "lucide-react";

import PageHero from "../components/PageHero";
import FormField from "../components/FormField";
import { sendEmailCode, verifyEmailCode } from "../api/auth";
import { fetchMyProfile, updateMyProfile, changeMyPassword, withdrawAccount } from "../api/mypage";
import {
  validateName,
  validatePhone,
  validateEmail,
  validateCode,
  validatePassword,
  validatePasswordConfirm,
  formatPhone,
  onlyDigits,
} from "../utils/validation";
// 입력칸·버튼 모양(.form-field, .field-button 등)은 회원가입 화면과 똑같이 쓰려고 같이 불러옴
import "../components/AuthLayout.css";
import "./MyPage.css";

// 위쪽 탭 목록 (key: 탭 이름, label: 버튼 글자, icon: 아이콘)
const TABS = [
  { key: "profile", label: "회원정보", icon: UserRound },
  { key: "password", label: "비밀번호 변경", icon: KeyRound },
  { key: "withdraw", label: "회원 탈퇴", icon: UserX },
];

// 남은 초 → "4:59" 모양 (인증번호 타이머용)
function formatTime(seconds) {
  const minutes = Math.floor(seconds / 60);
  const rest = String(seconds % 60).padStart(2, "0");
  return `${minutes}:${rest}`;
}

// =============================================================
// 1. 회원정보 수정
// -------------------------------------------------------------
// props
//  - token: 로그인 토큰
//  - profile: 지금 저장된 내 정보 (입력칸 처음 값으로 씀)
//  - onSaved: 저장 성공 시 실행 (새 프로필을 넘겨줌 → 부모·App이 화면과 로그인 정보를 갱신)
//  - onSessionExpired: 토큰 만료(401) 시 실행
// =============================================================
function ProfileSection({ token, profile, onSaved, onSessionExpired }) {
  // form: 입력칸 값 (처음에는 지금 저장된 값으로 채움)
  const [form, setForm] = useState({
    name: profile.name,
    phone: formatPhone(profile.phone), // "01012345678" → "010-1234-5678"
    email: profile.email,
    code: "",
  });
  const [errors, setErrors] = useState({}); // 입력칸별 에러 문구
  const [saving, setSaving] = useState(false); // 저장 요청 중인지
  const [serverError, setServerError] = useState(""); // 서버가 돌려준 에러
  const [doneMessage, setDoneMessage] = useState(""); // 저장 성공 문구

  // 이메일 인증 상태 (회원가입 화면과 같은 방식)
  // sentTo: 인증번호를 보낸 이메일 / verifiedEmail: 인증을 마친 이메일 / expiresAt: 만료 시각(밀리초)
  const [emailAuth, setEmailAuth] = useState({
    sentTo: "",
    verifiedEmail: "",
    expiresAt: 0,
    remaining: 0,
    devMode: false,
    sending: false,
    verifying: false,
  });

  // ----- 상태에서 계산하는 값 -----
  const email = form.email.trim().toLowerCase(); // 서버도 소문자로 저장하니까 비교도 소문자로
  const emailChanged = email !== profile.email; // 이메일을 바꾸려는 중인지
  const isEmailVerified = emailChanged && emailAuth.verifiedEmail === email; // 바꾼 이메일 인증까지 끝났는지
  const isCodeSent = emailChanged && emailAuth.sentTo === email && !isEmailVerified; // 인증번호 입력칸을 보여줄지
  // 바뀐 게 하나라도 있는지 (아무것도 안 바꿨으면 저장 버튼을 꺼 둠)
  const hasChanges =
    form.name.trim() !== profile.name || onlyDigits(form.phone) !== profile.phone || emailChanged;

  // ----- 인증번호 남은 시간 타이머 (1초마다 다시 계산) -----
  useEffect(() => {
    if (!emailAuth.expiresAt) return; // 아직 안 보냈으면 타이머 없음
    const timer = setInterval(() => {
      const left = Math.max(0, Math.ceil((emailAuth.expiresAt - Date.now()) / 1000));
      setEmailAuth((prev) => ({ ...prev, remaining: left }));
      if (left === 0) clearInterval(timer); // 0초가 되면 멈춤
    }, 1000);
    // 정리 함수: 새 타이머를 시작하기 전/화면을 떠날 때 이전 타이머를 꼭 멈춤
    return () => clearInterval(timer);
  }, [emailAuth.expiresAt]);

  // ----- 입력값 바꾸기 공통 함수 -----
  const updateField = (field, value) => {
    // [field]: value → 변수 field에 든 글자를 key로 씀 (예: { name: value })
    setForm((prev) => ({ ...prev, [field]: value }));
    setErrors((prev) => ({ ...prev, [field]: "" })); // 다시 입력하면 그 칸 에러는 지움
    setServerError("");
    setDoneMessage("");
  };

  // ----- 인증번호 받기 -----
  const handleSendCode = async () => {
    const formatError = validateEmail(form.email);
    if (formatError) {
      setErrors((prev) => ({ ...prev, email: formatError }));
      return;
    }
    setEmailAuth((prev) => ({ ...prev, sending: true }));
    try {
      // 서버가 "이미 가입된 이메일"이면 여기서 에러를 돌려줌 → 아래 catch로 감
      const result = await sendEmailCode(email);
      const seconds = result.expires_in || 300; // 유효시간(초), 기본 5분
      setEmailAuth((prev) => ({
        ...prev,
        sentTo: email,
        expiresAt: Date.now() + seconds * 1000,
        remaining: seconds,
        devMode: Boolean(result.dev_mode),
        sending: false,
      }));
      setForm((prev) => ({ ...prev, code: "" })); // 예전에 적은 인증번호 지우기
      setErrors((prev) => ({ ...prev, email: "", code: "" }));
    } catch (error) {
      setEmailAuth((prev) => ({ ...prev, sending: false }));
      setErrors((prev) => ({ ...prev, email: error.message }));
    }
  };

  // ----- 인증번호 확인 -----
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
      await verifyEmailCode(email, form.code);
      setEmailAuth((prev) => ({ ...prev, verifiedEmail: email, verifying: false, expiresAt: 0 }));
      setErrors((prev) => ({ ...prev, email: "", code: "" }));
    } catch (error) {
      setEmailAuth((prev) => ({ ...prev, verifying: false }));
      setErrors((prev) => ({ ...prev, code: error.message }));
    }
  };

  // ----- 저장하기 (form 제출) -----
  const handleSubmit = async (event) => {
    event.preventDefault(); // form 제출 시 페이지가 새로고침되는 걸 막음

    // 1. 칸마다 검사해서 에러 모으기
    const nextErrors = {
      name: validateName(form.name),
      phone: validatePhone(form.phone),
      email: validateEmail(form.email) || (emailChanged && !isEmailVerified ? "새 이메일 인증을 완료해 주세요." : ""),
    };
    setErrors(nextErrors);
    // Object.values: 객체의 값만 배열로 / some: 하나라도 조건에 맞으면 true → 에러가 하나라도 있으면 멈춤
    if (Object.values(nextErrors).some(Boolean)) return;

    // 2. 서버에 저장 요청
    setSaving(true);
    setServerError("");
    try {
      const result = await updateMyProfile(token, {
        name: form.name.trim(),
        phone: onlyDigits(form.phone), // 하이픈 빼고 숫자만 보냄
        email,
      });
      setSaving(false);
      setDoneMessage(result.message);
      // 인증 상태는 초기화 (이제 새 이메일이 "지금 이메일"이 됨)
      setEmailAuth((prev) => ({ ...prev, sentTo: "", verifiedEmail: "", expiresAt: 0 }));
      onSaved(result.profile);
    } catch (error) {
      setSaving(false);
      if (error.status === 401) {
        onSessionExpired?.();
        return;
      }
      setServerError(error.message);
    }
  };

  return (
    <form className="auth-form mypage-form" onSubmit={handleSubmit} noValidate>
      {/* 아이디는 로그인 기준이라 못 바꿈 → 보여주기만 (disabled) */}
      <FormField
        id="edit-login-id"
        label="아이디"
        value={profile.login_id}
        onChange={() => {}}
        disabled
        hint="아이디는 바꿀 수 없어요."
      />

      {/* 이름 + 전화번호를 가로로 나란히 (모바일에서는 세로로) */}
      <div className="form-grid-2">
        <FormField
          id="edit-name"
          label="이름"
          value={form.name}
          onChange={(value) => updateField("name", value)}
          autoComplete="name"
          maxLength={20}
          error={errors.name}
        />
        <FormField
          id="edit-phone"
          label="전화번호"
          type="tel"
          value={form.phone}
          // 입력할 때마다 자동으로 하이픈을 넣어 줌 (01012345678 → 010-1234-5678)
          onChange={(value) => updateField("phone", formatPhone(value))}
          placeholder="010-1234-5678"
          autoComplete="tel"
          inputMode="numeric"
          maxLength={13}
          error={errors.phone}
        />
      </div>

      {/* 이메일: 지금과 다른 주소를 적으면 "인증번호 받기" 버튼이 생김 */}
      <FormField
        id="edit-email"
        label="이메일"
        type="email"
        value={form.email}
        onChange={(value) => updateField("email", value)}
        autoComplete="email"
        maxLength={100}
        error={errors.email}
        success={isEmailVerified ? "새 이메일 인증이 완료됐어요. 저장하면 바뀌어요." : ""}
        hint={emailChanged ? "" : "이메일을 바꾸려면 새 주소를 입력하고 인증해 주세요."}
        disabled={isEmailVerified} // 인증 끝나면 못 고치게 (고치려면 "변경" 버튼)
        action={
          !emailChanged ? null : isEmailVerified ? (
            <button
              type="button"
              className="field-button ghost"
              // 다시 바꾸고 싶으면 인증 상태를 초기화
              onClick={() => setEmailAuth((prev) => ({ ...prev, verifiedEmail: "", sentTo: "", expiresAt: 0 }))}
            >
              변경
            </button>
          ) : (
            <button type="button" className="field-button" onClick={handleSendCode} disabled={emailAuth.sending}>
              {emailAuth.sending ? <Loader2 className="spin" size={16} /> : isCodeSent ? "재전송" : "인증번호 받기"}
            </button>
          )
        }
      />

      {/* 인증번호 입력 (보낸 뒤에만 보임) */}
      {isCodeSent && (
        <FormField
          id="edit-code"
          label="인증번호"
          value={form.code}
          onChange={(value) => updateField("code", onlyDigits(value).slice(0, 6))} // 숫자만 6자리까지
          placeholder="메일로 받은 6자리 숫자"
          autoComplete="one-time-code"
          inputMode="numeric"
          maxLength={6}
          error={errors.code}
          hint={
            emailAuth.devMode
              ? "개발 모드: 메일 대신 백엔드 터미널에 인증번호가 표시돼요."
              : `${email} 으로 인증번호를 보냈어요. 메일이 안 보이면 스팸함도 확인해 주세요.`
          }
          suffix={
            // 1분 이하로 남으면 빨갛게
            <span className={emailAuth.remaining <= 60 ? "timer urgent" : "timer"}>
              {formatTime(emailAuth.remaining)}
            </span>
          }
          action={
            <button type="button" className="field-button" onClick={handleVerifyCode} disabled={emailAuth.verifying}>
              {emailAuth.verifying ? <Loader2 className="spin" size={16} /> : "확인"}
            </button>
          }
        />
      )}

      {/* 서버 에러 / 저장 성공 문구 (role: 화면 읽기 프로그램이 바로 읽어 줌) */}
      {serverError && (
        <p className="auth-server-error" role="alert">
          {serverError}
        </p>
      )}
      {doneMessage && (
        <p className="mypage-done" role="status">
          <CheckCircle2 size={18} /> {doneMessage}
        </p>
      )}

      <button type="submit" className="auth-submit" disabled={saving || !hasChanges}>
        {saving ? (
          <>
            <Loader2 className="spin" size={18} /> 저장하는 중...
          </>
        ) : (
          "회원정보 저장"
        )}
      </button>
    </form>
  );
}

// =============================================================
// 2. 비밀번호 변경
// =============================================================
function PasswordSection({ token, onSessionExpired }) {
  const [form, setForm] = useState({ current: "", next: "", confirm: "" });
  const [errors, setErrors] = useState({});
  const [saving, setSaving] = useState(false);
  const [serverError, setServerError] = useState("");
  const [doneMessage, setDoneMessage] = useState("");

  const updateField = (field, value) => {
    setForm((prev) => ({ ...prev, [field]: value }));
    setErrors((prev) => ({ ...prev, [field]: "" }));
    setServerError("");
    setDoneMessage("");
  };

  const handleSubmit = async (event) => {
    event.preventDefault();

    // 1. 화면에서 먼저 검사 (서버에서도 똑같은 규칙으로 한 번 더 검사함)
    const nextErrors = {
      current: form.current ? "" : "현재 비밀번호를 입력해 주세요.",
      next:
        validatePassword(form.next) ||
        (form.next && form.next === form.current ? "지금 쓰는 비밀번호와 다른 비밀번호를 입력해 주세요." : ""),
      confirm: validatePasswordConfirm(form.next, form.confirm),
    };
    setErrors(nextErrors);
    if (Object.values(nextErrors).some(Boolean)) return;

    // 2. 서버에 변경 요청
    setSaving(true);
    setServerError("");
    try {
      const result = await changeMyPassword(token, form.current, form.next);
      setSaving(false);
      setDoneMessage(result.message);
      setForm({ current: "", next: "", confirm: "" }); // 다 바꿨으니 입력칸 비우기
    } catch (error) {
      setSaving(false);
      if (error.status === 401) {
        onSessionExpired?.();
        return;
      }
      setServerError(error.message);
    }
  };

  return (
    <form className="auth-form mypage-form" onSubmit={handleSubmit} noValidate>
      <FormField
        id="pw-current"
        label="현재 비밀번호"
        type="password"
        value={form.current}
        onChange={(value) => updateField("current", value)}
        autoComplete="current-password" // 브라우저가 저장된 비밀번호를 채워 줄 수 있게
        maxLength={64}
        error={errors.current}
      />
      <FormField
        id="pw-next"
        label="새 비밀번호"
        type="password"
        value={form.next}
        onChange={(value) => updateField("next", value)}
        autoComplete="new-password" // "새 비밀번호"라고 알려 주면 브라우저가 강한 비밀번호를 제안해 줌
        maxLength={64}
        error={errors.next}
        hint="영문과 숫자를 포함해 8~64자로 입력해 주세요."
      />
      <FormField
        id="pw-confirm"
        label="새 비밀번호 확인"
        type="password"
        value={form.confirm}
        onChange={(value) => updateField("confirm", value)}
        autoComplete="new-password"
        maxLength={64}
        error={errors.confirm}
        success={form.confirm && form.next === form.confirm ? "비밀번호가 일치해요." : ""}
      />

      {serverError && (
        <p className="auth-server-error" role="alert">
          {serverError}
        </p>
      )}
      {doneMessage && (
        <p className="mypage-done" role="status">
          <CheckCircle2 size={18} /> {doneMessage}
        </p>
      )}

      <button type="submit" className="auth-submit" disabled={saving}>
        {saving ? (
          <>
            <Loader2 className="spin" size={18} /> 변경하는 중...
          </>
        ) : (
          "비밀번호 변경"
        )}
      </button>
    </form>
  );
}

// =============================================================
// 3. 회원 탈퇴
// -------------------------------------------------------------
//  - onWithdrawn: 탈퇴 성공 시 실행 (App이 로그아웃시키고 홈으로 보냄)
// =============================================================
function WithdrawSection({ token, profile, onWithdrawn, onSessionExpired }) {
  const [agreed, setAgreed] = useState(false); // "안내를 확인했어요" 체크 여부
  const [password, setPassword] = useState("");
  const [error, setError] = useState("");
  const [submitting, setSubmitting] = useState(false);

  const handleSubmit = async (event) => {
    event.preventDefault();
    if (!agreed) {
      setError("안내 내용을 확인하고 체크해 주세요.");
      return;
    }
    if (!password) {
      setError("비밀번호를 입력해 주세요.");
      return;
    }

    setSubmitting(true);
    setError("");
    try {
      const result = await withdrawAccount(token, password);
      onWithdrawn(result.message); // 이 화면은 곧 사라지니까 submitting은 되돌릴 필요 없음
    } catch (err) {
      setSubmitting(false);
      if (err.status === 401) {
        onSessionExpired?.();
        return;
      }
      setError(err.message);
    }
  };

  return (
    <form className="auth-form mypage-form" onSubmit={handleSubmit} noValidate>
      {/* 경고 상자: 지워지는 내용 안내 */}
      <div className="mypage-warning" role="note">
        <p className="mypage-warning-title">
          <AlertTriangle size={18} /> 탈퇴하면 아래 내용이 모두 삭제되고 되돌릴 수 없어요.
        </p>
        <ul>
          <li>
            회원정보 (아이디 <strong>{profile.login_id}</strong>, 이메일, 전화번호)
          </li>
          <li>내가 쓴 글 {profile.document_count}편과 저장본, AI 피드백 기록</li>
          <li>맞춤법 도전 모드 기록과 랭킹 (최고 {profile.best_challenge_score}문제 연속)</li>
          <li>글쓰기 취향 설정</li>
        </ul>
      </div>

      {/* 확인 체크박스 (회원가입 약관 체크박스와 같은 모양) */}
      <label className="agree-item mypage-agree">
        <input
          type="checkbox"
          checked={agreed}
          onChange={(event) => {
            setAgreed(event.target.checked);
            setError("");
          }}
        />
        위 안내를 모두 확인했고, 탈퇴에 동의해요.
      </label>

      <FormField
        id="withdraw-password"
        label="비밀번호 확인"
        type="password"
        value={password}
        onChange={(value) => {
          setPassword(value);
          setError("");
        }}
        autoComplete="current-password"
        maxLength={64}
        hint="본인 확인을 위해 비밀번호를 한 번 더 입력해 주세요."
      />

      {error && (
        <p className="auth-server-error" role="alert">
          {error}
        </p>
      )}

      {/* 빨간 탈퇴 버튼 (체크하고 비밀번호를 적어야 눌림) */}
      <button type="submit" className="auth-submit danger" disabled={submitting || !agreed || !password}>
        {submitting ? (
          <>
            <Loader2 className="spin" size={18} /> 탈퇴 처리 중...
          </>
        ) : (
          "회원 탈퇴"
        )}
      </button>
    </form>
  );
}

// =============================================================
// 부모: MyPageEdit
// -------------------------------------------------------------
// props
//  - auth: 로그인 정보 { token, user }
//  - onBack: "마이페이지로" 버튼 (마이페이지 보기 화면으로 돌아감)
//  - onProfileUpdated: 회원정보 저장 성공 시 (App이 헤더 이름 등 로그인 정보를 갱신)
//  - onWithdrawn: 탈퇴 성공 시 (App이 로그아웃 처리)
//  - onGoLogin: 로그인 안 했을 때 "로그인하기" 버튼
//  - onSessionExpired: 토큰 만료 시
// =============================================================
function MyPageEdit({ auth, onBack, onProfileUpdated, onWithdrawn, onGoLogin, onSessionExpired }) {
  const token = auth?.token;

  const [tab, setTab] = useState("profile"); // 지금 고른 탭
  const [profile, setProfile] = useState(null); // 지금 저장된 내 정보 (입력칸 처음 값 + 탈퇴 안내에 씀)
  const [loading, setLoading] = useState(Boolean(token));
  const [error, setError] = useState("");
  const [reloadKey, setReloadKey] = useState(0);

  // ----- 지금 내 정보 불러오기 -----
  useEffect(() => {
    if (!token) return;
    let ignore = false;

    fetchMyProfile(token)
      .then((data) => {
        if (ignore) return;
        setProfile(data);
        setError("");
        setLoading(false);
      })
      .catch((err) => {
        if (ignore) return;
        if (err.status === 401) {
          onSessionExpired?.();
          return;
        }
        setError(err.message);
        setLoading(false);
      });

    return () => {
      ignore = true;
    };
  }, [token, reloadKey, onSessionExpired]);

  // 회원정보 저장 성공 → 이 화면의 프로필도 새 값으로, App에도 알림
  const handleSaved = (nextProfile) => {
    setProfile(nextProfile);
    onProfileUpdated(nextProfile);
  };

  const hero = (
    <PageHero
      eyebrow="마이페이지"
      title="회원정보 수정"
      description={"내 정보와 비밀번호를 바꾸거나 회원 탈퇴를 할 수 있어요.\n바꾼 내용은 저장 버튼을 눌러야 반영돼요."}
      memoText={"내 정보는\n안전하게\n지킬게요 :)"}
      memoVariant="notebook"
    />
  );

  // ----- 로그인 안 했을 때 -----
  if (!token) {
    return (
      <div className="sub-page">
        <div className="sub-page-inner">
          {hero}
          <section className="panel mypage-message">
            <LogIn size={36} strokeWidth={1.6} className="mypage-message-icon" />
            <p>회원정보 수정은 로그인한 뒤에 할 수 있어요.</p>
            <button type="button" className="btn-primary" onClick={onGoLogin}>
              로그인하기
            </button>
          </section>
        </div>
      </div>
    );
  }

  return (
    <div className="sub-page">
      <div className="sub-page-inner">
        {hero}

        {/* 마이페이지로 돌아가기 */}
        <button type="button" className="mypage-back" onClick={onBack}>
          <ArrowLeft size={16} /> 마이페이지로
        </button>

        <section className="panel mypage-edit-card">
          {/* ----- 위쪽 탭 (role="tablist": 화면 읽기 프로그램에 "탭 묶음"이라고 알려줌) ----- */}
          <div className="mypage-tabs" role="tablist" aria-label="수정할 항목">
            {TABS.map((item) => {
              const Icon = item.icon;
              const selected = tab === item.key;
              return (
                <button
                  key={item.key}
                  type="button"
                  role="tab"
                  id={`tab-${item.key}`}
                  aria-selected={selected}
                  aria-controls={`panel-${item.key}`}
                  className={
                    // 탈퇴 탭은 빨간 글씨로 구분 (danger)
                    `mypage-tab${selected ? " active" : ""}${item.key === "withdraw" ? " danger" : ""}`
                  }
                  onClick={() => setTab(item.key)}
                >
                  <Icon size={17} />
                  {item.label}
                </button>
              );
            })}
          </div>

          {/* ----- 고른 탭의 내용 ----- */}
          <div role="tabpanel" id={`panel-${tab}`} aria-labelledby={`tab-${tab}`} className="mypage-tabpanel">
            {loading ? (
              <p className="mypage-doc-muted">
                <Loader2 size={16} className="spin" /> 내 정보를 불러오는 중이에요...
              </p>
            ) : error || !profile ? (
              <div className="mypage-message inline">
                <p>{error || "내 정보를 불러오지 못했어요."}</p>
                <button
                  type="button"
                  className="btn-outline"
                  onClick={() => {
                    setLoading(true);
                    setReloadKey((key) => key + 1);
                  }}
                >
                  <RefreshCw size={16} /> 다시 불러오기
                </button>
              </div>
            ) : tab === "profile" ? (
              // 저장하면 profile이 새 값으로 바뀌고, 입력칸 값과 같아지니까 "바뀐 것 없음" 상태로 돌아감
              <ProfileSection
                token={token}
                profile={profile}
                onSaved={handleSaved}
                onSessionExpired={onSessionExpired}
              />
            ) : tab === "password" ? (
              <PasswordSection token={token} onSessionExpired={onSessionExpired} />
            ) : (
              <WithdrawSection
                token={token}
                profile={profile}
                onWithdrawn={onWithdrawn}
                onSessionExpired={onSessionExpired}
              />
            )}
          </div>
        </section>
      </div>
    </div>
  );
}

export default MyPageEdit;
