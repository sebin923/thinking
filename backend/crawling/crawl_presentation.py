# =============================================================
# crawl_presentation.py — 대한민국 정책브리핑 발표문·연설문 수집 (최종 완성 버전)
# -------------------------------------------------------------
# 실행 방법:
#   python crawl_crawl_presentation.py               ← 기본 500개
#   python crawl_crawl_presentation.py --target 1000 ← 개수 바꾸기
# =============================================================

import argparse
import json
import time
from datetime import datetime, timezone
from pathlib import Path

import requests
from bs4 import BeautifulSoup

BASE_LIST_URL = "https://www.korea.kr/briefing/speechList.do"
OUTPUT_DIR = Path(__file__).resolve().parent / "output"
RAW_PATH = OUTPUT_DIR / "total_raw.jsonl"

def main() -> None:
    parser = argparse.ArgumentParser(description="대한민국 정책브리핑 발표문/연설문 수집")
    parser.add_argument("--target", type=int, default=300, help="모을 글 개수 (기본 300)")
    args = parser.parse_args()

    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    
    done = set()
    if RAW_PATH.exists():
        with open(RAW_PATH, encoding="utf-8") as file:
            for line in file:
                try:
                    data = json.loads(line)
                    if data.get("source") == "대한민국 정책브리핑":
                        done.add(data["title"])
                except (json.JSONDecodeError, KeyError):
                    continue

    print(f"정책브리핑 연설문 수집 시작 (목표: {args.target}개)... [현재 수집된 개수: {len(done)}개]")
    
    saved = len(done)
    page = 1
    headers = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"}

    with open(RAW_PATH, "a", encoding="utf-8") as out:
        while saved < args.target and page <= 30:
            print(f"\n[페이지 {page}] 요청 중...")
            try:
                res = requests.get(BASE_LIST_URL, params={"pageIndex": page}, headers=headers, timeout=10)
                print(f"[페이지 {page}] 응답 코드: {res.status_code}")
                
                if res.status_code != 200:
                    page += 1
                    continue

                soup = BeautifulSoup(res.text, "html.parser")
                items = []
                seen_hrefs = set()
                
                # 정책브리핑 목록의 모든 링크 중 상세페이지 관련 패턴(.do)을 가진 것들을 수집
                for a in soup.find_all("a", href=True):
                    href = a["href"]
                    text = a.get_text(strip=True)
                    if len(text) > 10 and ".do" in href and href not in seen_hrefs:
                        seen_hrefs.add(href)
                        items.append(a)

                print(f"[페이지 {page}] 유효한 게시글 링크 수: {len(items)}개")
                if not items:
                    page += 1
                    continue

                for item in items:
                    if saved >= args.target:
                        break
                    title = item.get_text(strip=True)
                    if not title or title in done:
                        continue

                    href = item["href"]
                    if href.startswith("http"):
                        detail_url = href
                    elif href.startswith("/"):
                        detail_url = "https://www.korea.kr" + href
                    else:
                        detail_url = "https://www.korea.kr/briefing/" + href

                    # 상세 페이지 본문 가져오기
                    time.sleep(1)
                    detail_res = requests.get(detail_url, headers=headers, timeout=10)
                    if detail_res.status_code != 200:
                        continue

                    detail_soup = BeautifulSoup(detail_res.text, "html.parser")
                    view_box = detail_soup.select_one(".view_text, .con_view, .article_view, div.view-content")
                    body = view_box.get_text(separator="\n", strip=True) if view_box else detail_soup.get_text(separator="\n", strip=True)

                    if len(body) < 300:
                        continue

                    done.add(title)
                    record = {
                        "title": title,
                        "url": detail_url,
                        "page_id": f"pres_{saved+1}",
                        "headings": ["발표문", "연설문"],
                        "body": body,
                        "source": "대한민국 정책브리핑",
                        "license": "공공누리 개방 표준",
                        "retrieved_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
                    }
                    out.write(json.dumps(record, ensure_ascii=False) + "\n")
                    out.flush()
                    saved += 1
                    print(f"  [{saved}/{args.target}] 수집 완료: {title}")

                page += 1
            except Exception as e:
                print(f"  [에러 발생] {e}")
                time.sleep(2)
                page += 1

    print(f"\n완료! 총 {saved}개 저장 → {RAW_PATH}")

if __name__ == "__main__":
    main()