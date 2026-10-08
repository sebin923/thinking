// =============================================================
// FormField.jsx — 라벨 + 입력칸 + (옆 버튼) + 안내/에러 문구를 한 묶음으로 만든 컴포넌트
// -------------------------------------------------------------
// 로그인·회원가입에 입력칸이 여러 개 있는데 모양이 다 똑같아서,
// 한 번 만들어두고 props만 바꿔서 여러 번 쓰려고 분리함
//
// 사용 예)
//   <FormField id="loginId" label="아이디" value={loginId} onChange={setLoginId}
//              error={errors.loginId}
//              action={<button>중복 확인</button>} />
// =============================================================

import { useState } from "react";

// Eye: 눈 아이콘(비밀번호 보기) / EyeOff: 빗금 친 눈(비밀번호 숨기기)
import { Eye, EyeOff } from "lucide-react";

// props
//  - id: 입력칸 고유 이름 (라벨과 연결할 때 씀)
//  - label: 입력칸 위 이름 (예: "아이디")
//  - type: 입력 종류 ("text", "email", "password", "tel")
//  - value: 입력칸에 보일 값 (부모의 state)
//  - onChange: 값이 바뀌면 실행할 함수 → 새 값을 넘겨줌
//  - error: 빨간 에러 문구 (빈 문자열이면 안 보임)
//  - success: 초록 성공 문구 (예: "사용할 수 있는 아이디예요.")
//  - hint: 에러·성공이 없을 때 보여줄 회색 안내 문구
//  - action: 입력칸 오른쪽에 붙일 버튼 등 (예: 중복 확인, 인증번호 받기)
//  - suffix: 입력칸 안쪽 오른쪽에 붙일 작은 글자 (예: 남은 시간 04:59)
//  - disabled: true면 입력 못 하게 막음 (예: 인증 끝난 이메일)
//  - 그 밖: placeholder, autoComplete, maxLength, inputMode
function FormField({
  id,
  label,
  type = "text", // 안 넘겨주면 기본값 "text"
  value,
  onChange,
  error = "",
  success = "",
  hint = "",
  action = null,
  suffix = null,
  disabled = false,
  placeholder = "",
  autoComplete,
  maxLength,
  inputMode,
}) {
  // showPassword: 비밀번호를 글자로 보여줄지 (눈 아이콘을 누를 때마다 바뀜)
  const [showPassword, setShowPassword] = useState(false);

  // 비밀번호 칸인지 확인
  const isPassword = type === "password";

  // 실제 input에 넣을 type
  // 비밀번호 칸인데 "보기"를 켰으면 "text"로 바꿔서 글자가 보이게 함
  const inputType = isPassword && showPassword ? "text" : type;

  // 아래 문구에 붙일 id (입력칸과 문구를 연결해서 화면 읽기 프로그램이 같이 읽게 함)
  const messageId = `${id}-message`;

  // 입력 상자 테두리 색을 정하는 클래스
  let boxClass = "form-input-box";
  if (error) boxClass += " has-error"; // 빨강
  else if (success) boxClass += " has-success"; // 초록
  if (disabled) boxClass += " is-disabled"; // 회색 배경

  return (
    <div className="form-field">
      {/* htmlFor: 이 라벨이 어떤 입력칸 것인지 id로 연결 → 라벨을 눌러도 입력칸에 커서가 감 */}
      <label htmlFor={id} className="form-label">
        {label}
      </label>

      {/* 입력 상자 + 오른쪽 버튼(action)을 가로로 나란히 */}
      <div className="form-row">
        <div className={boxClass}>
          <input
            id={id}
            type={inputType}
            value={value}
            // 글자를 칠 때마다 새 값을 부모에게 넘김
            onChange={(event) => onChange(event.target.value)}
            placeholder={placeholder}
            autoComplete={autoComplete}
            maxLength={maxLength}
            inputMode={inputMode} // 모바일에서 숫자 키패드 등을 띄우는 힌트 (예: "numeric")
            disabled={disabled}
            // aria-invalid: 이 칸에 문제가 있다고 알려줌 (접근성)
            aria-invalid={error ? "true" : "false"}
            aria-describedby={error || success || hint ? messageId : undefined}
          />

          {/* 입력칸 안쪽 오른쪽 작은 글자 (타이머 등) */}
          {suffix && <span className="form-suffix">{suffix}</span>}

          {/* 비밀번호 칸일 때만 눈 아이콘 버튼 표시 */}
          {isPassword && (
            <button
              type="button" // form 안 버튼은 기본이 "제출"이라서, 제출 안 되게 type="button"
              className="password-toggle"
              onClick={() => setShowPassword(!showPassword)}
              aria-label={showPassword ? "비밀번호 숨기기" : "비밀번호 보기"}
            >
              {showPassword ? <EyeOff size={18} /> : <Eye size={18} />}
            </button>
          )}
        </div>

        {/* 오른쪽 버튼이 있으면 표시 */}
        {action}
      </div>

      {/*
        아래 문구: 에러(빨강) > 성공(초록) > 힌트(회색) 순서로 하나만 보여줌
        role="alert": 에러가 생기면 화면 읽기 프로그램이 바로 읽어줌
      */}
      {error ? (
        <p id={messageId} className="form-error" role="alert">
          {error}
        </p>
      ) : success ? (
        <p id={messageId} className="form-success">
          {success}
        </p>
      ) : (
        hint && (
          <p id={messageId} className="form-hint">
            {hint}
          </p>
        )
      )}
    </div>
  );
}

export default FormField;
