// =============================================================
// DeleteDocumentModal.jsx — 마이페이지 "글 삭제" 확인창
// -------------------------------------------------------------
// 마이페이지 글 목록에서 "삭제"를 누르면 MyPage가 띄움
//   - "취소": 창만 닫음 (Esc 키, 바깥 어두운 부분 클릭도 같음)
//   - "삭제하기": MyPage가 서버에 삭제 요청을 보냄
//
// 모양은 글쓰기 나가기 경고창(LeaveConfirmModal)과 똑같이 맞추려고 그 CSS를 같이 씀
//
// props
//  - title: 지울 글 제목 (창에 보여줌)
//  - deleting: true면 서버에 지우는 중 → 버튼을 막고 "삭제하는 중..." 표시
//  - error: 삭제 실패 문구 (없으면 빈 문자열)
//  - onCancel: 취소
//  - onConfirm: 삭제하기
// =============================================================

import { useEffect } from "react";
import { Trash2, Loader2 } from "lucide-react";

import "./LeaveConfirmModal.css";

function DeleteDocumentModal({ title, deleting, error, onCancel, onConfirm }) {
  // ----- Esc 키를 누르면 취소 -----
  // (지우는 중에는 닫으면 결과를 못 보니까 막아 둠)
  useEffect(() => {
    const handleKeyDown = (event) => {
      if (event.key === "Escape" && !deleting) onCancel();
    };
    // keydown: 키보드를 누를 때마다 브라우저가 알려주는 신호
    window.addEventListener("keydown", handleKeyDown);
    // 정리 함수: 창이 닫히면 신호 듣기를 그만둠
    return () => window.removeEventListener("keydown", handleKeyDown);
  }, [deleting, onCancel]);

  return (
    // 화면 전체를 어둡게 덮는 배경 (바깥을 누르면 취소, 지우는 중에는 무시)
    <div className="leave-modal-backdrop" onClick={() => !deleting && onCancel()}>
      {/*
        가운데 하얀 확인창
        role="alertdialog": 화면 읽기 프로그램에 "중요한 확인 창"이라고 알려줌
        stopPropagation: 창 안을 눌렀을 때는 바깥(배경) 클릭으로 치지 않게 막음
      */}
      <div
        className="leave-modal"
        role="alertdialog"
        aria-modal="true"
        aria-labelledby="delete-modal-title"
        aria-describedby="delete-modal-desc"
        onClick={(event) => event.stopPropagation()}
      >
        {/* 휴지통 아이콘 (빨간색은 아래 style로만 살짝 바꿈) */}
        <Trash2 size={38} strokeWidth={1.8} className="leave-modal-icon" style={{ color: "#d9534f" }} />

        <p id="delete-modal-title" className="leave-modal-title">
          이 글을 삭제할까요?
        </p>

        <p id="delete-modal-desc" className="leave-modal-desc">
          <strong>"{title}"</strong>
          <br />
          저장한 모든 버전과 AI 피드백까지 함께 지워지고,
          <br />
          삭제한 글은 <strong>되돌릴 수 없어요.</strong>
        </p>

        {/* 실패 문구 (예: 서버에 아직 삭제 기능이 없을 때) */}
        {error && (
          <p className="leave-modal-desc" role="alert" style={{ marginTop: -8, color: "#d9534f" }}>
            {error}
          </p>
        )}

        <div className="leave-modal-actions">
          {/* 실수로 엔터를 눌러도 안 지워지게 처음 커서는 "취소"에 둠 (autoFocus) */}
          <button type="button" className="leave-modal-stay" onClick={onCancel} disabled={deleting} autoFocus>
            취소
          </button>
          <button type="button" className="leave-modal-leave" onClick={onConfirm} disabled={deleting}>
            {deleting ? (
              <>
                <Loader2 size={15} className="spin" /> 삭제하는 중...
              </>
            ) : (
              "삭제하기"
            )}
          </button>
        </div>
      </div>
    </div>
  );
}

export default DeleteDocumentModal;
