import { parseNoticeContent } from "../utils/noticeContent";

export default function NoticeContent({ content }) {
  return (
    <div className="notice-content">
      {parseNoticeContent(content).map((block, index) =>
        block.type === "image" ? (
          <figure className="notice-figure" key={index}>
            <a href={block.src} target="_blank" rel="noopener noreferrer" aria-label={`${block.alt} 크게 보기 (새 창)`}>
              <img src={block.src} alt={block.alt} loading="lazy" decoding="async" />
            </a>
            <figcaption>
              <span>{block.alt}</span>
              <a href={block.src} target="_blank" rel="noopener noreferrer">크게 보기</a>
            </figcaption>
          </figure>
        ) : (
          <p className="notice-paragraph" key={index}>{block.text}</p>
        ),
      )}
    </div>
  );
}
