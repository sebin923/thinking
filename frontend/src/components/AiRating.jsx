// =============================================================
// AiRating.jsx — AI 결과(초안·피드백) 별점 평가 상자
// -------------------------------------------------------------
// 글쓰기 화면의 "AI 초안 비교" 아래, "AI 피드백 결과" 아래에 붙음
//   ☆☆☆☆☆  ← 마우스를 올리면 미리 채워지고, 누르면 그 개수로 선택
//   한 줄 의견 (선택)
//   [평가 보내기] → 저장 후 "평가해 줘서 고마워요" (다시 평가할 수도 있음)
// 저장: api/aiRating.js (지금은 브라우저 저장, 백엔드 생기면 DB)
// 스타일: AiRating.css
//
// ★ 새 AI 결과가 나오면 평가 상자도 처음부터 다시 시작해야 해서,
//   쓰는 쪽(WritingPage)에서 key를 결과마다 다르게 줌 (key가 바뀌면 React가 새로 만듦)
// =============================================================

import { useState } from "react";
// Star: 별 아이콘, Loader2: 저장 중, CheckCircle2: 저장 완료
import { Star, Loader2, CheckCircle2 } from "lucide-react";

import { saveAiRating } from "../api/aiRating";
// 저장 중 빙글빙글 도는 .spin 클래스가 들어 있는 파일
import "./AuthLayout.css";
import "./AiRating.css";

// 별 개수별 설명 (마우스를 올리거나 고르면 옆에 보여줌)
const RATING_LABELS = ["", "별로예요", "아쉬워요", "보통이에요", "좋아요", "아주 좋아요"];
const COMMENT_MAX = 100; // 한 줄 의견 최대 글자 수

// props
//  - title: 상자 제목 (예: "이 AI 초안은 어땠나요?")
//  - user: 로그인한 회원 (평가를 회원별로 저장)
//  - kind: "draft"(초안) / "feedback"(피드백)
//  - model: "clova" / "common" / "personal" (어떤 AI가 만든 결과인지)
//  - documentId: 지금 글 번호 (없으면 null)
//  - resultText: AI가 만든 결과 글 / requestText: AI에게 보낸 원래 글
function AiRating({ title, user, kind, model, documentId, resultText, requestText }) {
  const [rating, setRating] = useState(0); // 고른 별 개수 (0 = 아직 안 고름)
  const [hover, setHover] = useState(0); // 마우스를 올린 별 (0 = 없음)
  const [comment, setComment] = useState("");
  const [saving, setSaving] = useState(false);
  const [saved, setSaved] = useState(null); // 저장한 평가 (null = 아직 안 보냄)
  const [error, setError] = useState("");

  // 화면에 칠할 별 개수: 마우스를 올리고 있으면 그 개수, 아니면 고른 개수
  const shown = hover || rating;

  const handleSubmit = async () => {
    if (rating === 0) {
      setError("별을 먼저 골라 주세요.");
      return;
    }
    setSaving(true);
    setError("");
    try {
      const result = await saveAiRating(user, { kind, model, rating, comment, documentId, resultText, requestText });
      setSaved(result);
    } catch (err) {
      setError(err.message);
    } finally {
      setSaving(false);
    }
  };

  // ----- 보낸 뒤: 고맙다는 안내 + 다시 평가하기 -----
  if (saved) {
    return (
      <div className="ai-rating done" role="status">
        <CheckCircle2 size={18} />
        <span>
          평가해 줘서 고마워요! <b>{"★".repeat(saved.rating)}</b>
          <small> 더 좋은 AI를 만드는 데 참고할게요.</small>
        </span>
        <button type="button" className="ai-rating-again" onClick={() => setSaved(null)}>
          다시 평가
        </button>
      </div>
    );
  }

  return (
    <div className="ai-rating">
      <p className="ai-rating-title">{title}</p>

      <div className="ai-rating-row">
        {/* 별 5개 (라디오 버튼처럼 하나만 고름) */}
        <div className="ai-rating-stars" role="radiogroup" aria-label="별점" onMouseLeave={() => setHover(0)}>
          {[1, 2, 3, 4, 5].map((value) => (
            <button
              key={value}
              type="button"
              role="radio"
              aria-checked={rating === value}
              aria-label={`별 ${value}개 - ${RATING_LABELS[value]}`}
              className={value <= shown ? "ai-rating-star on" : "ai-rating-star"}
              onMouseEnter={() => setHover(value)}
              onFocus={() => setHover(value)}
              onBlur={() => setHover(0)}
              onClick={() => {
                setRating(value);
                setError("");
              }}
            >
              {/* fill: 별 안쪽 색 (켜진 별만 노랗게 채움) */}
              <Star size={26} fill={value <= shown ? "currentColor" : "none"} strokeWidth={1.8} />
            </button>
          ))}
        </div>
        {/* 별 개수 설명 */}
        <span className="ai-rating-label">{shown ? RATING_LABELS[shown] : "별을 눌러 평가해 주세요"}</span>
      </div>

      {/* 별을 고른 뒤에만 의견 칸과 보내기 버튼을 보여줌 (처음엔 간단하게) */}
      {rating > 0 && (
        <div className="ai-rating-extra">
          <input
            type="text"
            className="ai-rating-comment"
            value={comment}
            maxLength={COMMENT_MAX}
            onChange={(event) => setComment(event.target.value)}
            placeholder="한 줄 의견을 남겨 주세요 (선택)"
            aria-label="한 줄 의견"
          />
          <button type="button" className="btn-primary ai-rating-submit" onClick={handleSubmit} disabled={saving}>
            {saving ? <Loader2 size={15} className="spin" /> : null} 평가 보내기
          </button>
        </div>
      )}

      {error && (
        <p className="ai-rating-error" role="alert">
          {error}
        </p>
      )}
    </div>
  );
}

export default AiRating;
