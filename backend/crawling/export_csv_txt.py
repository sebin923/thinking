# =============================================================
# export_csv_txt.py — 크롤링한 위키백과 글을 CSV / TXT 파일로 저장 (사람이 보기 편한 형태)
# -------------------------------------------------------------
# crawl_wikipedia.py가 만든 output/wiki_raw.jsonl 은 프로그램용 형식(한 줄에 JSON 하나)이라
# 엑셀이나 메모장으로 보기 불편함 → 이 파일로 바꿔서 저장
#
# 만들어지는 파일 (output/ 폴더)
#   wiki_articles.csv     엑셀로 여는 표 (번호, 제목, 글자 수, 문단 제목, 본문, 주소, 출처, 라이선스, 수집 시각)
#   wiki_all.txt          모든 글을 한 파일에 이어 붙인 텍스트 (글 사이에 ==== 구분선)
#   txt/0001_제목.txt      글 하나당 텍스트 파일 하나
#
# 실행: python export_csv_txt.py   (crawl_wikipedia.py 다음에 실행)
# =============================================================

import csv
import json
import re
from pathlib import Path

OUTPUT_DIR = Path(__file__).resolve().parent / "output"
RAW_PATH = OUTPUT_DIR / "wiki_raw.jsonl"
CSV_PATH = OUTPUT_DIR / "wiki_articles.csv"
ALL_TXT_PATH = OUTPUT_DIR / "wiki_all.txt"
TXT_DIR = OUTPUT_DIR / "txt"


def safe_filename(title: str) -> str:
    """제목 → 윈도우에서 파일 이름으로 쓸 수 있는 글자로
    \\ / : * ? " < > | 는 파일 이름에 못 써서 _ 로 바꾸고, 너무 길면 50자로 자름
    """
    name = re.sub(r'[\\/:*?"<>|]', "_", title).strip(" .")
    return name[:50] or "제목없음"


def header_lines(number: int, article: dict) -> str:
    """TXT 파일 맨 위에 붙일 정보 (출처 표기 겸용)"""
    return (
        f"[{number}] {article['title']}\n"
        f"출처: {article['source']} ({article['url']})\n"
        f"라이선스: {article['license']} / 수집: {article['retrieved_at']}\n"
    )


def main() -> None:
    if not RAW_PATH.exists():
        print("먼저 python crawl_wikipedia.py 로 글을 모아 주세요.")
        return

    with open(RAW_PATH, encoding="utf-8") as file:
        articles = [json.loads(line) for line in file if line.strip()]
    if not articles:
        print("모은 글이 없어요.")
        return

    # ----- 1) CSV (엑셀용) -----
    # utf-8-sig: 파일 맨 앞에 표시를 붙여서 엑셀에서 한글이 안 깨짐
    # newline="": 윈도우에서 줄이 하나씩 띄워져 보이는 문제 방지
    with open(CSV_PATH, "w", encoding="utf-8-sig", newline="") as file:
        writer = csv.writer(file)
        writer.writerow(["번호", "제목", "글자 수", "문단 제목", "본문", "주소", "출처", "라이선스", "수집 시각"])
        for number, article in enumerate(articles, start=1):  # enumerate: 번호를 1부터 같이 붙여 줌
            writer.writerow(
                [
                    number,
                    article["title"],
                    len(article["body"]),
                    " / ".join(article.get("headings", [])),
                    article["body"],  # 줄바꿈이 있어도 csv 모듈이 알아서 따옴표로 감싸서 한 칸에 들어감
                    article["url"],
                    article["source"],
                    article["license"],
                    article["retrieved_at"],
                ]
            )

    # ----- 2) 전체를 한 파일에 (메모장으로 훑어보기용) -----
    with open(ALL_TXT_PATH, "w", encoding="utf-8") as file:
        for number, article in enumerate(articles, start=1):
            file.write(header_lines(number, article))
            file.write("\n" + article["body"] + "\n")
            file.write("\n" + "=" * 60 + "\n\n")  # 글과 글 사이 구분선

    # ----- 3) 글 하나당 파일 하나 -----
    TXT_DIR.mkdir(parents=True, exist_ok=True)
    for number, article in enumerate(articles, start=1):
        # 0001_재생에너지.txt 처럼 번호를 4자리로 맞추면 파일 탐색기에서 순서대로 정렬됨
        path = TXT_DIR / f"{number:04d}_{safe_filename(article['title'])}.txt"
        with open(path, "w", encoding="utf-8") as file:
            file.write(header_lines(number, article) + "\n" + article["body"] + "\n")

    print(f"글 {len(articles)}개를 저장했어요.")
    print(f"  엑셀용 표   → {CSV_PATH}")
    print(f"  전체 텍스트 → {ALL_TXT_PATH}")
    print(f"  글별 텍스트 → {TXT_DIR}\\ (파일 {len(articles)}개)")


if __name__ == "__main__":
    main()
