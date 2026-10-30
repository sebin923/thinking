# =============================================================
# crawl_essay.py — 한국어 위키문헌에서 자유글쓰기·에세이 모으기 (수정 완료 버전)
# -------------------------------------------------------------
# 실행 방법:
#   python crawl_essay.py               ← 기본 500개
#   python crawl_essay.py --target 1000 ← 개수 바꾸기
# =============================================================

import argparse
import json
import re
import time
from datetime import datetime, timezone
from pathlib import Path

import requests

API_URL = "https://ko.wikisource.org/w/api.php"

CONTACT = "sebinhan4@example.com"
USER_AGENT = f"SaenggakHanjul-StudentProject/1.0 (Kyungdong University capstone project; contact: {CONTACT})"

REQUEST_DELAY = 1.0

# 에세이·산문·수필 관련 위키문헌 분류
SEED_CATEGORIES = [
    "산문",
    "에세이",
    "수필",
    "한국의 문학",
    "일반 산문",
]
CATEGORY_DEPTH = 2

CUT_SECTIONS = {"각주", "같이 보기", "외부 링크", "참고 문헌", "참고 자료", "내용주", "출처", "참조", "더 읽어보기"}

MIN_BODY_CHARS = 300
MAX_BODY_CHARS = 1500

OUTPUT_DIR = Path(__file__).resolve().parent / "output"
RAW_PATH = OUTPUT_DIR / "wiki_raw.jsonl"

session = requests.Session()
session.headers["User-Agent"] = USER_AGENT


def call_api(params: dict) -> dict:
    full_params = {"format": "json", "formatversion": "2", "maxlag": "5", **params}
    for attempt in range(1, 4):
        time.sleep(REQUEST_DELAY)
        try:
            response = session.get(API_URL, params=full_params, timeout=20)
            if response.status_code in (429, 503):
                wait = int(response.headers.get("Retry-After", "10"))
                print(f"  서버가 바쁘대요. {wait}초 기다렸다가 다시 시도해요.")
                time.sleep(wait)
                continue
            response.raise_for_status()
            data = response.json()
            if data.get("error", {}).get("code") == "maxlag":
                time.sleep(5)
                continue
            return data
        except (requests.RequestException, ValueError) as error:
            print(f"  요청 실패 ({attempt}/3): {error}")
            time.sleep(3 * attempt)
    return {}


def collect_titles(limit: int) -> list[str]:
    titles: list[str] = []
    seen_titles: set[str] = set()
    seen_categories: set[str] = set()
    queue = [(f"분류:{name}", 0) for name in SEED_CATEGORIES]

    while queue and len(titles) < limit:
        category, depth = queue.pop(0)
        if category in seen_categories:
            continue
        seen_categories.add(category)
        print(f"[분류] {category} (깊이 {depth}) — 지금까지 제목 {len(titles)}개")

        cont = None
        while True:
            params = {
                "action": "query",
                "list": "categorymembers",
                "cmtitle": category,
                "cmtype": "page|subcat",
                "cmnamespace": "0|14",
                "cmlimit": "500",
            }
            if cont:
                params["cmcontinue"] = cont
            data = call_api(params)
            for member in data.get("query", {}).get("categorymembers", []):
                title = member["title"]
                if member.get("ns") == 14:
                    if depth + 1 <= CATEGORY_DEPTH:
                        queue.append((title, depth + 1))
                elif title not in seen_titles and is_useful_title(title):
                    seen_titles.add(title)
                    titles.append(title)
            cont = data.get("continue", {}).get("cmcontinue")
            if not cont or len(titles) >= limit:
                break
    return titles


def is_useful_title(title: str) -> bool:
    if "목록" in title or "동음이의" in title or "저작권" in title:
        return False
    return True


def fetch_article(title: str) -> dict | None:
    data = call_api(
        {
            "action": "query",
            "prop": "extracts|info|pageprops",
            "explaintext": "1",
            "exsectionformat": "wiki",
            "inprop": "url",
            "redirects": "1",
            "titles": title,
        }
    )
    pages = data.get("query", {}).get("pages", [])
    if not pages:
        return None
    page = pages[0]
    if page.get("missing"):
        return None
    return {
        "page_id": page.get("pageid"),
        "title": page.get("title", title),
        "url": page.get("fullurl", ""),
        "extract": page.get("extract", ""),
    }


def split_sections(extract: str) -> list[tuple[str, str]]:
    sections: list[tuple[str, str]] = []
    current_title = ""
    current_lines: list[str] = []
    for line in extract.splitlines():
        heading = re.fullmatch(r"\s*(=+)\s*(.+?)\s*\1\s*", line)
        if heading:
            sections.append((current_title, "\n".join(current_lines).strip()))
            current_title = heading.group(2)
            current_lines = []
        else:
            current_lines.append(line)
    sections.append((current_title, "\n".join(current_lines).strip()))
    return sections


def clean_article(extract: str) -> tuple[str, list[str]]:
    paragraphs: list[str] = []
    used_headings: list[str] = []
    total = 0
    for heading, content in split_sections(extract):
        if heading in CUT_SECTIONS:
            break
        lines = [line.strip() for line in content.splitlines() if line.strip()]
        if not lines:
            continue
        for line in lines:
            if len(line) < 15 or not re.search(r"[.다요]\s*$", line):
                continue
            if total + len(line) > MAX_BODY_CHARS and paragraphs:
                return "\n\n".join(paragraphs), used_headings
            paragraphs.append(line)
            total += len(line)
            if heading and heading not in used_headings:
                used_headings.append(heading)
    return "\n\n".join(paragraphs), used_headings


def load_done() -> set[str]:
    done = set()
    if RAW_PATH.exists():
        with open(RAW_PATH, encoding="utf-8") as file:
            for line in file:
                try:
                    data = json.loads(line)
                    # 한국어 위키문헌에서 수집한 데이터만 중복 체크
                    if data.get("source") == "한국어 위키문헌":
                        done.add(data["title"])
                except (json.JSONDecodeError, KeyError):
                    continue
    return done


def main() -> None:
    parser = argparse.ArgumentParser(description="한국어 위키문헌에서 자유글쓰기·에세이 수집")
    parser.add_argument("--target", type=int, default=500, help="모을 글 개수 (기본 500)")
    args = parser.parse_args()

    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    done = load_done()
    if len(done) >= args.target:
        print(f"이미 {len(done)}개를 모아 뒀어요.")
        return

    titles = [t for t in collect_titles(args.target * 3) if t not in done]
    print(f"\n후보 제목 {len(titles)}개 확보. 본문을 받아요.\n")

    saved = len(done)
    skipped = 0
    with open(RAW_PATH, "a", encoding="utf-8") as out:
        for title in titles:
            if saved >= args.target:
                break
            article = fetch_article(title)
            if article is None:
                skipped += 1
                continue
            body, headings = clean_article(article["extract"])
            if len(body) < MIN_BODY_CHARS:
                skipped += 1
                continue
            record = {
                "title": article["title"],
                "url": article["url"],
                "page_id": article["page_id"],
                "headings": headings,
                "body": body,
                "source": "한국어 위키문헌",
                "license": "CC BY-SA 4.0",
                "retrieved_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
            }
            out.write(json.dumps(record, ensure_ascii=False) + "\n")
            out.flush()
            saved += 1
            if saved % 50 == 0:
                print(f"  {saved}/{args.target}개 저장 (건너뜀 {skipped}개)")

    print(f"\n완료! 총 {saved}개 저장 → {RAW_PATH}")


if __name__ == "__main__":
    main()