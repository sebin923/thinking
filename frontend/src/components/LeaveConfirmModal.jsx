// =============================================================
// LeaveConfirmModal.jsx — "작성 중인 글이 있어요" 나가기 경고창
// -------------------------------------------------------------
// 글쓰기 화면에서 저장하지 않은 내용이 있는 채로 다른 곳으로 가려고 할 때 App이 띄움
//   - "계속 쓰기": 창만 닫고 글쓰기 화면에 그대로 남음
//   - "저장 안 하고 나가기": 저장 안 한 내용을 버리고 원래 가려던 곳으로 이동
//
// props
//  - willDelete: true면 "한 번도 저장 안 한 글이라 마이페이지에도 안 남는다"는 안내를 추가
//  - onStay: "계속 쓰기" (또는 Esc 키, 바깥 어두운 부분 클릭)
//  - onLeave: "저장 안 하고 나가기"
// =============================================================

import { useEffect } from "react";
import { AlertTriangle } from "lucide-react";

import "./LeaveConfirmModal.css";

function LeaveConfirmModal({ willDelete, onStay, onLeave }) {
  // ----- Esc 키를 누르면 "계속 쓰기"와 똑같이 창 닫기 -----
  useEffect(() => {
    const handleKeyDown = (event) => {
      if (event.key === "Escape") onStay();
    };
    // keydown: 키보드를 누를 때마다 브라우저가 알려주는 신호
    window.addEventListener("keydown", handleKeyDown);
    // 정리 함수: 창이 닫히면 신호 듣기를 그만둠
    return () => window.removeEventListener("keydown", handleKeyDown);
  }, [onStay]);

  return (
    // 화면 전체를 어둡게 덮는 배경 (바깥을 누르면 계속 쓰기)
    <div className="leave-modal-backdrop" onClick={onStay}>
      {/*
        가운데 하얀 경고창
        role="alertdialog": 화면 읽기 프로그램에 "중요한 확인 창"이라고 알려줌
        onClick의 stopPropagation: 창 안을 눌렀을 때는 바깥(배경) 클릭으로 치지 않게 막음
      */}
      <div
        className="leave-modal"
        role="alertdialog"
        aria-modal="true"
        aria-labelledby="leave-modal-title"
        aria-describedby="leave-modal-desc"
        onClick={(event) => event.stopPropagation()}
      >
        <AlertTriangle size={40} strokeWidth={1.8} className="leave-modal-icon" />

        <p id="leave-modal-title" className="leave-modal-title">
          작성 중인 글이 있어요
        </p>

        <p id="leave-modal-desc" className="leave-modal-desc">
          지금 나가면 저장하지 않은 내용이 사라져요.
          {willDelete && (
            <>
              <br />
              <strong>아직 한 번도 저장하지 않은 글이라 마이페이지에도 남지 않아요.</strong>
            </>
          )}
          <br />
          남기고 싶다면 계속 쓰기를 눌러 <strong>버전 저장</strong>을 해 주세요.
        </p>

        <div className="leave-modal-actions">
          {/* 실수로 엔터를 눌러도 글이 안 날아가게, 처음 커서는 "계속 쓰기"에 둠 (autoFocus) */}
          <button type="button" className="leave-modal-stay" onClick={onStay} autoFocus>
            계속 쓰기
          </button>
          <button type="button" className="leave-modal-leave" onClick={onLeave}>
            저장 안 하고 나가기
          </button>
        </div>
      </div>
    </div>
  );
}

export default LeaveConfirmModal;
