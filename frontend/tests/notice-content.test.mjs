import assert from "node:assert/strict";
import test from "node:test";
import { parseNoticeContent } from "../src/utils/noticeContent.js";

test("기존 공지의 줄바꿈과 일반 글자를 유지한다", () => {
  assert.deepEqual(parseNoticeContent("첫 문단\r\n\r\n둘째 문단"), [{ type: "text", text: "첫 문단\n\n둘째 문단" }]);
});

test("비교 이미지 두 장을 본문에서 지정한 순서대로 표시한다", () => {
  const blocks = parseNoticeContent("처음\n\n![답변 비교](/notice-assets/ai-writing-20261120/answer-comparison.png)\n\n중간\n\n![모델 비교](/notice-assets/ai-writing-20261120/model-comparison.png)\n\n마지막");
  assert.deepEqual(blocks.map((block) => block.type), ["text", "image", "text", "image", "text"]);
  assert.equal(blocks[1].alt, "답변 비교");
  assert.equal(blocks[4].text, "마지막");
});

test("HTML과 스크립트·외부 주소·상위 폴더 경로는 이미지로 처리하지 않는다", () => {
  for (const source of [
    '<img src=x onerror="alert(1)">',
    "![x](javascript:alert(1))",
    "![x](https://example.com/pixel.png)",
    "![x](//example.com/pixel.png)",
    "![x](/notice-assets/../../private.png)",
    "![x](/notice-assets/%2e%2e/private.png)",
    "![x](/notice-assets/vector.svg)",
    "![x](/notice-assets/file.png?redirect=https://example.com)",
  ]) {
    assert.deepEqual(parseNoticeContent(source), [{ type: "text", text: source }]);
  }
});

test("이미지 설명이 비어 있으면 기본 설명을 제공한다", () => {
  assert.equal(parseNoticeContent("![](/notice-assets/comparison.webp)")[0].alt, "공지 첨부 이미지");
});
