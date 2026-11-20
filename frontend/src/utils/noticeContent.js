// 별도 줄에 적은 사이트 내부 이미지만 표시합니다.
// HTML과 외부 주소를 포함한 나머지 입력은 일반 글자로 유지합니다.
const IMAGE_LINE = /^!\[([^\]\r\n]{0,200})\]\((\/notice-assets\/[a-zA-Z0-9/_-]+\.(?:png|jpe?g|webp))\)$/;

export function parseNoticeContent(content) {
  const blocks = [];
  let pending = [];
  const flush = () => {
    const text = pending.join("\n").trim();
    if (text) blocks.push({ type: "text", text });
    pending = [];
  };

  for (const line of String(content ?? "").replace(/\r\n?/g, "\n").split("\n")) {
    const match = line.trim().match(IMAGE_LINE);
    if (!match) {
      pending.push(line);
      continue;
    }
    flush();
    blocks.push({ type: "image", alt: match[1] || "공지 첨부 이미지", src: match[2] });
  }
  flush();
  return blocks;
}
