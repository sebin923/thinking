// =============================================================
// AuthLayout.jsx — 로그인 / 회원가입 화면의 공통 틀
// -------------------------------------------------------------
// ┌───────────────────┬──────────────────────┐
// │ 왼쪽: 하늘색 패널   │ 오른쪽: 입력 폼        │
// │ (손글씨 + 메모지)   │ (children으로 받음)    │
// └───────────────────┴──────────────────────┘
// 로그인과 회원가입이 같은 모양이라 틀은 여기 하나만 만들고,
// 오른쪽 폼 부분만 각 페이지에서 children으로 넣어줌
// =============================================================

import { Cloud, Smile, ShieldCheck } from "lucide-react";

import "./AuthLayout.css";

// props
//  - panelTitle: 왼쪽 패널 손글씨 큰 문구 (\n 줄바꿈 가능)
//  - panelDesc: 왼쪽 패널 작은 설명 (\n 줄바꿈 가능)
//  - children: 이 컴포넌트 태그 사이에 넣은 내용 (= 오른쪽 폼)
//    예) <AuthLayout ...> 여기 내용이 children </AuthLayout>
function AuthLayout({ panelTitle, panelDesc, children }) {
  return (
    <div className="auth-page">
      <div className="auth-card">
        {/* ===== 왼쪽 패널 (장식 + 문구) ===== */}
        <aside className="auth-panel">
          <p className="auth-panel-title">{panelTitle}</p>
          <p className="auth-panel-desc">{panelDesc}</p>

          {/* 작은 메모지 장식 (장식이라 aria-hidden) */}
          <div className="auth-memo" aria-hidden="true">
            <Cloud className="auth-memo-cloud" size={30} strokeWidth={1.4} />
            <span>
              오늘의 생각,
              <br />
              한 줄로 시작해요
            </span>
            <Smile className="auth-memo-smile" size={24} strokeWidth={1.4} />
          </div>

          {/* 보안 안내 */}
          <p className="auth-panel-secure">
            <ShieldCheck size={16} />
            비밀번호는 암호화되어 안전하게 저장돼요.
          </p>
        </aside>

        {/* ===== 오른쪽 폼 영역 ===== */}
        <section className="auth-form-area">{children}</section>
      </div>
    </div>
  );
}

export default AuthLayout;
