# =============================================================
# crawl_wikipedia.py — 한국어 위키백과에서 보고서·설명문용 글 모으기 (1단계: 수집)
# -------------------------------------------------------------
# 왜 위키백과?
#   - 글 라이선스가 CC BY-SA 4.0 → "출처 표기 + 같은 조건으로 공유"하면 AI 학습에 써도 됨
#   - 공식 API(MediaWiki API)를 열어 두고 "이렇게 쓰세요" 규칙까지 공개해 둠
#     → 화면(HTML)을 긁는 게 아니라 API로 받아서 사이트 구조가 바뀌어도 잘 안 깨짐
#   - 설명문·보고서 문체(객관적, 사실 위주)라서 우리 서비스의 "보고서" 유형 학습에 잘 맞음
#
# 하는 일
#   1) 주제 분류(경제·사회·환경·교육·과학 등)에 들어 있는 글 제목을 모음 (하위 분류까지 2단계)
#   2) 글마다 본문을 받아서 각주·외부 링크 같은 부분을 빼고 정리
#   3) 너무 짧은 글, 목록·동음이의 문서는 버리고 output/total_raw.jsonl 에 한 줄씩 저장
#
# 실행 방법 (backend/crawling 폴더에서, 가상환경 켠 상태로)
#   python crawl_wikipedia.py                 ← 기본 1200개
#   python crawl_wikipedia.py --target 2000   ← 개수 바꾸기
#
# ★ 지키는 규칙 (위키미디어 API 이용 규칙)
#   - 요청 사이에 1초씩 쉼 (서버에 부담 안 주기)
#   - User-Agent에 프로젝트 이름과 연락처를 적음 (누가 보내는 요청인지 알 수 있게)
#   - maxlag=5: 위키 서버가 바쁘면 알아서 기다렸다가 다시 보냄
#   - 중간에 꺼져도 다시 실행하면 이미 받은 글은 건너뛰고 이어서 받음
# =============================================================

import argparse
import json
import re
import time
from datetime import datetime, timezone
from pathlib import Path

import requests

API_URL = "https://ko.wikipedia.org/w/api.php"

# 누가 보내는 요청인지 알려주는 이름표 (위키미디어 규칙: 프로젝트 이름 + 연락 방법을 적어야 함)
# ★ 실행 전에 CONTACT를 팀 대표 이메일로 바꿔 주세요 (안 바꾸면 실행할 때 안내 문구가 나와요)
#   ※ 요청 헤더에는 영문·숫자만 들어갈 수 있어서 한글을 넣으면 요청이 전부 실패함
CONTACT = "sebinhan4@example.com"
USER_AGENT = f"SaenggakHanjul-StudentProject/1.0 (Kyungdong University capstone project; contact: {CONTACT})"

# 요청 사이 쉬는 시간(초) — 너무 줄이면 차단될 수 있음
REQUEST_DELAY = 1.0

# 보고서·설명문 주제로 쓸 분류 (위키백과의 "분류:" 문서 이름)
# 없는 분류 이름이 섞여 있어도 그냥 건너뛰니까 자유롭게 추가·삭제해도 됨
SEED_CATEGORIES = [
    "경제",
    "사회",
    "환경",
    "교육",
    "과학",
    "기술",
    "정치",
    "문화",
    "건강",
    "보건",
    "에너지",
    "교통",
    "정보 기술",
    "인공지능",
    "기후 변화",
    "노동",
    "복지",
    "인구",
]
CATEGORY_DEPTH = 2  # 분류 안의 하위 분류까지 몇 단계 내려갈지 (너무 깊으면 주제가 엉뚱해짐)

# 본문에서 잘라낼 부분 (이 제목의 문단부터 끝까지는 학습에 필요 없음)
CUT_SECTIONS = {"각주", "같이 보기", "외부 링크", "참고 문헌", "참고 자료", "내용주", "출처", "참조", "더 읽어보기"}

MIN_BODY_CHARS = 500  # 이보다 짧은 글은 버림 (설명이 너무 적음)
MAX_BODY_CHARS = 1500  # 이보다 길면 문단 단위로 잘라서 저장 (학습할 때 너무 긴 글은 부담)

# 저장 위치 (이 파일이 있는 폴더 아래 output/)
OUTPUT_DIR = Path(__file__).resolve().parent / "output"
RAW_PATH = OUTPUT_DIR / "total_raw.jsonl"


# ===================== API 요청 =====================

session = requests.Session()  # 연결을 재사용해서 매번 새로 접속하지 않음 (더 빠르고 서버 부담도 적음)
session.headers["User-Agent"] = USER_AGENT


def call_api(params: dict) -> dict:
    """위키백과 API에 요청 1번 보내고 JSON을 돌려줌 (실패하면 최대 3번까지 다시 시도)"""
    full_params = {"format": "json", "formatversion": "2", "maxlag": "5", **params}
    for attempt in range(1, 4):
        time.sleep(REQUEST_DELAY)  # ★ 매 요청 전에 쉬기
        try:
            response = session.get(API_URL, params=full_params, timeout=20)
            # 429(너무 많이 요청함)나 503(서버 바쁨)이면 조금 더 기다렸다가 다시
            if response.status_code in (429, 503):
                wait = int(response.headers.get("Retry-After", "10"))
                print(f"  서버가 바쁘대요. {wait}초 기다렸다가 다시 시도해요.")
                time.sleep(wait)
                continue
            response.raise_for_status()  # 그 밖의 에러(404, 500 등)는 예외로
            data = response.json()
            # maxlag 에러: 위키 서버가 밀려 있음 → 기다렸다가 다시
            if data.get("error", {}).get("code") == "maxlag":
                time.sleep(5)
                continue
            return data
        except (requests.RequestException, ValueError) as error:
            print(f"  요청 실패 ({attempt}/3): {error}")
            time.sleep(3 * attempt)
    return {}  # 3번 다 실패하면 빈 결과 (그 글은 건너뜀)


# ===================== 1) 글 제목 모으기 =====================


def collect_titles(limit: int) -> list[str]:
    """주제 분류들을 하위 분류까지 돌면서 글 제목을 모음 (넉넉하게 limit개까지)
    BFS(너비 우선 탐색): 가까운 분류부터 차례로 살펴봄 → 주제에서 너무 멀어지지 않음
    """
    titles: list[str] = []
    seen_titles: set[str] = set()
    seen_categories: set[str] = set()
    # 대기열: (분류 이름, 깊이)
    queue = [(f"분류:{name}", 0) for name in SEED_CATEGORIES]

    while queue and len(titles) < limit:
        category, depth = queue.pop(0)
        if category in seen_categories:
            continue
        seen_categories.add(category)
        print(f"[분류] {category} (깊이 {depth}) — 지금까지 제목 {len(titles)}개")

        cont = None  # 결과가 많으면 다음 페이지 표시(cmcontinue)를 받아서 이어서 요청
        while True:
            params = {
                "action": "query",
                "list": "categorymembers",
                "cmtitle": category,
                "cmtype": "page|subcat",  # 글과 하위 분류를 같이 받음
                "cmnamespace": "0|14",  # 0 = 일반 글, 14 = 분류
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
    """제목만 보고 학습에 안 맞는 글 거르기 (목록, 연도별 문서, 동음이의 문서 등)"""
    if "목록" in title or "동음이의" in title:
        return False
    if re.fullmatch(r"\d{3,4}년.*", title):  # "2020년 대한민국 경제" 같은 연도 기록
        return False
    return True


# ===================== 2) 본문 받기 + 정리 =====================


def fetch_article(title: str) -> dict | None:
    """글 하나의 본문(문법 기호 없는 평문)과 주소를 받아 옴 (동음이의 문서면 None)"""
    data = call_api(
        {
            "action": "query",
            "prop": "extracts|info|pageprops",
            "explaintext": "1",  # 위키 문법(링크, 표 등)을 빼고 글자만
            "exsectionformat": "wiki",  # 문단 제목을 "== 제목 ==" 모양으로 남김 → 문단을 나눌 때 씀
            "inprop": "url",  # 글 주소(출처 표기용)
            "ppprop": "disambiguation",  # 동음이의 문서인지 표시
            "redirects": "1",  # 다른 글로 넘겨주는 문서면 진짜 글로 따라감
            "titles": title,
        }
    )
    pages = data.get("query", {}).get("pages", [])
    if not pages:
        return None
    page = pages[0]
    if page.get("missing") or "disambiguation" in page.get("pageprops", {}):
        return None
    return {
        "page_id": page.get("pageid"),
        "title": page.get("title", title),
        "url": page.get("fullurl", ""),
        "extract": page.get("extract", ""),
    }


def split_sections(extract: str) -> list[tuple[str, str]]:
    """평문을 (문단 제목, 내용) 목록으로 나눔. 맨 앞 소개 부분의 제목은 ""(빈 글자)
    "== 역사 ==", "=== 초기 ===" 같은 줄이 문단 제목
    """
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
    """본문 정리 → (정리된 본문, 실제로 들어간 문단 제목 목록)
      - 각주·같이 보기·외부 링크 같은 문단부터 끝까지 버림
      - 내용이 빈 문단(제목만 있는 문단)은 버림
      - 너무 길면 문단 단위로 MAX_BODY_CHARS 근처에서 자름 (문장 중간에서 안 끊기게)
    """
    paragraphs: list[str] = []
    used_headings: list[str] = []
    total = 0
    for heading, content in split_sections(extract):
        if heading in CUT_SECTIONS:
            break  # 여기부터는 참고 자료 → 뒤는 전부 버림
        # 문단 안의 빈 줄 정리 + 줄마다 앞뒤 공백 제거
        lines = [line.strip() for line in content.splitlines() if line.strip()]
        if not lines:
            continue
        for line in lines:
            # 표·목록 찌꺼기처럼 너무 짧은 줄(문장이 아닌 것)은 버림
            if len(line) < 20 or not re.search(r"[.다요]\s*$", line):
                continue
            if total + len(line) > MAX_BODY_CHARS and paragraphs:
                return "\n\n".join(paragraphs), used_headings
            paragraphs.append(line)
            total += len(line)
            if heading and heading not in used_headings:
                used_headings.append(heading)
    return "\n\n".join(paragraphs), used_headings


# ===================== 실행 =====================


def load_done() -> set[str]:
    """이미 받아 둔 글 제목 (다시 실행했을 때 이어서 받으려고)"""
    done = set()
    if RAW_PATH.exists():
        with open(RAW_PATH, encoding="utf-8") as file:
            for line in file:
                try:
                    done.add(json.loads(line)["title"])
                except (json.JSONDecodeError, KeyError):
                    continue
    return done


def main() -> None:
    parser = argparse.ArgumentParser(description="한국어 위키백과에서 보고서·설명문 수집")
    parser.add_argument("--target", type=int, default=1200, help="모을 글 개수 (기본 1200)")
    args = parser.parse_args()

    if "example.com" in CONTACT:
        print("※ 파일 위쪽 CONTACT를 팀 이메일로 바꿔 주세요. (위키미디어 이용 규칙: 연락처를 적어야 해요)\n")
    if not CONTACT.isascii():
        print("❌ CONTACT에는 영문·숫자 이메일만 넣을 수 있어요. (한글이 있으면 요청이 전부 실패해요)")
        return

    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    done = load_done()
    if len(done) >= args.target:
        print(f"이미 {len(done)}개를 모아 뒀어요. 더 모으려면 --target 을 늘려 주세요.")
        return
    print(f"이미 모은 글: {len(done)}개 → 목표 {args.target}개까지 이어서 모아요.\n")

    # 짧은 글·동음이의 문서가 걸러지니까 목표보다 넉넉하게(3배) 제목을 모아 둠
    titles = [t for t in collect_titles(args.target * 3) if t not in done]
    print(f"\n후보 제목 {len(titles)}개 확보. 본문을 받아요. (1초에 1개씩이라 시간이 좀 걸려요)\n")

    saved = len(done)
    skipped = 0
    # "a": 이어 쓰기 모드 → 중간에 꺼져도 앞에 받은 건 그대로 남음
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
                # ★ 출처·라이선스 기록 (CC BY-SA는 출처 표기가 조건이라 꼭 같이 저장)
                "source": "한국어 위키백과",
                "license": "CC BY-SA 4.0",
                "retrieved_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
            }
            out.write(json.dumps(record, ensure_ascii=False) + "\n")
            out.flush()  # 바로 파일에 써서, 갑자기 꺼져도 지금까지 받은 건 남게
            saved += 1
            if saved % 50 == 0:
                print(f"  {saved}/{args.target}개 저장 (건너뜀 {skipped}개)")

    print(f"\n완료! 총 {saved}개 저장 → {RAW_PATH}")
    print("다음 단계: python build_training_data.py  (학습 데이터 JSONL 만들기)")


# 이 파일을 직접 실행했을 때만 main() 실행
if __name__ == "__main__":
    main()
