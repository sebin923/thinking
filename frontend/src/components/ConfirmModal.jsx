// =============================================================
// ConfirmModal.jsx — "정말 할까요?" 확인창 (여러 화면에서 같이 쓰는 범용 버전)
// -------------------------------------------------------------
// 관리자 페이지에서 퀴즈 삭제·회원 정지·랭킹 기록 삭제처럼
// 되돌리기 어려운 동작 전에 한 번 더 묻는 데 씀
//   - "취소": 창만 닫음 (Esc 키, 바깥 어두운 부분 클릭도 같음)
//   - 확인 버튼(예: "삭제하기"): 부모가 넘겨준 onConfirm 실행
//
// 모양은 글쓰기 나가기 경고창(LeaveConfirmModal)과 똑같이 맞추려고 그 CSS를 같이 씀
//
// props
//  - title: 창 제목 (예: "이 퀴즈를 삭제할까요?")
//  - message: 설명 글 (여러 줄이면 \n으로 줄바꿈)
//  - confirmLabel: 확인 버튼 글자 (예: "삭제하기")
//  - danger: true면 아이콘이 빨간 휴지통, false면 주황 경고 아이콘
//  - busy: true면 서버에 요청 중 → 버튼을 막고 "처리하는 중..." 표시
//  - error: 실패 문구 (없으면 빈 문자열)
//  - onCancel / onConfirm: 취소 / 확인
// =============================================================

import { useEffect } from "react";
import { AlertTriangle, Trash2, Loader2 } from "lucide-react";

import "./LeaveConfirmModal.css";

function ConfirmModal({ title, message, confirmLabel, danger = false, busy = false, error = "", onCancel, onConfirm }) {
  // ----- Esc 키를 누르면 취소 (처리 중에는 결과를 봐야 하니까 막아 둠) -----
  useEffect(() => {
    const handleKeyDown = (event) => {
      if (event.key === "Escape" && !busy) onCancel();
    };
    window.addEventListener("keydown", handleKeyDown);
    // 정리 함수: 창이 닫히면 키보드 신호 듣기를 그만둠
    return () => window.removeEventListener("keydown", handleKeyDown);
  }, [busy, onCancel]);

  // 아이콘: 위험한 동작(삭제)은 빨간 휴지통, 그 외(정지 등)는 주황 경고
  const Icon = danger ? Trash2 : AlertTriangle;

  return (
    // 화면 전체를 어둡게 덮는 배경 (바깥을 누르면 취소, 처리 중에는 무시)
    <div className="leave-modal-backdrop" onClick={() => !busy && onCancel()}>
      {/*
        가운데 하얀 확인창
        role="alertdialog": 화면 읽기 프로그램에 "중요한 확인 창"이라고 알려줌
        stopPropagation: 창 안을 눌렀을 때는 바깥(배경) 클릭으로 치지 않게 막음
      */}
      <div
        className="leave-modal"
        role="alertdialog"
        aria-modal="true"
        aria-labelledby="confirm-modal-title"
        aria-describedby="confirm-modal-desc"
        onClick={(event) => event.stopPropagation()}
      >
        <Icon
          size={38}
          strokeWidth={1.8}
          className="leave-modal-icon"
          style={danger ? { color: "#d9534f" } : undefined}
        />

        <p id="confirm-modal-title" className="leave-modal-title">
          {title}
        </p>

        {/* white-space: pre-line → message 안의 \n을 실제 줄바꿈으로 보여줌 */}
        <p id="confirm-modal-desc" className="leave-modal-desc" style={{ whiteSpace: "pre-line" }}>
          {message}
        </p>

        {/* 실패 문구 */}
        {error && (
          <p className="leave-modal-desc" role="alert" style={{ marginTop: -8, color: "#d9534f" }}>
            {error}
          </p>
        )}

        <div className="leave-modal-actions">
          {/* 실수로 엔터를 눌러도 실행되지 않게 처음 커서는 "취소"에 둠 (autoFocus) */}
          <button type="button" className="leave-modal-stay" onClick={onCancel} disabled={busy} autoFocus>
            취소
          </button>
          <button type="button" className="leave-modal-leave" onClick={onConfirm} disabled={busy}>
            {busy ? (
              <>
                <Loader2 size={15} className="spin" /> 처리하는 중...
              </>
            ) : (
              confirmLabel
            )}
          </button>
        </div>
      </div>
    </div>
  );
}

export default ConfirmModal;
