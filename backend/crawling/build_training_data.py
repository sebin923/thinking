# =============================================================
# build_training_data.py — 모은 위키백과 글 → Qwen 학습 데이터(JSONL) 만들기 (2단계: 변환)
# -------------------------------------------------------------
# 우리 서비스가 AI에게 시키는 일 = "사용자의 생각 메모 → 자연스러운 글(초안)"
# 그런데 크롤링하면 "완성된 글"만 생김 → 거꾸로 만들기
#   1) 완성된 글(정답)을 문장 단위로 나눔
#   2) 각 문장을 메모처럼 짧게 바꿈 ("서울은 한국의 수도이다." → "서울은 한국의 수도")
#   3) "메모 목록 → 원래 글" 짝을 학습 문제 하나로 만듦
#
# ★ 정리 규칙 (본문·메모 둘 다 적용)
#   - 괄호 안에 한자가 들어 있으면 그 괄호를 통째로 지움: 경제(經濟)는 → 경제는
#     (한자가 없는 괄호는 그대로: 에너지 저장 장치(ESS) → 그대로)
#   - 따옴표 기호는 지우고 안의 글자는 남김: "녹색 성장"이라는 → 녹색 성장이라는
#
# ★ 형식 (팀 학습 데이터 형식과 똑같이)
#   {"category": "report",
#    "prompt": [{"role": "system", ...}, {"role": "user", "content": "글 유형: 보고서\n주제: ...\n제공한 사실:\n- ...\n요청: ..."}],
#    "completion": [{"role": "assistant", "content": "정리된 본문"}]}
#
# ★ 왜 이렇게?
#   팀원 export_training.py의 시스템 지시문이 "사용자가 제공한 사실만 사용하고 내용을 지어내지 마"
#   → 메모에 글의 사실이 전부 들어 있어야, AI가 "없는 내용을 지어내는 법"이 아니라
#     "주어진 사실만으로 글을 다듬는 법"을 배움
#   (제목·문단 제목만 주고 긴 글을 쓰게 하면, 정보를 지어내는 버릇이 생김)
#
# 결과 파일 (output/ 폴더)
#   wiki_train.jsonl    학습용 (90%)
#   wiki_test.jsonl     시험용 (10%, 학습에 안 씀 → 학습 전·후 비교 테스트할 때 사용)
#   wiki_sources.csv    출처 목록 (제목, 주소, 라이선스) — CC BY-SA 출처 표기용
#
# 실행: python build_training_data.py
# =============================================================

import csv
import json
import random
import re
from pathlib import Path

OUTPUT_DIR = Path(__file__).resolve().parent / "output"
RAW_PATH = OUTPUT_DIR / "total_raw.jsonl"
TRAIN_PATH = OUTPUT_DIR / "wiki_train.jsonl"
TEST_PATH = OUTPUT_DIR / "wiki_test.jsonl"
SOURCES_PATH = OUTPUT_DIR / "wiki_sources.csv"

TEST_RATIO = 0.1  # 시험용으로 떼어 둘 비율
RANDOM_SEED = 42  # 섞는 순서를 고정 → 몇 번을 실행해도 학습/시험 나뉘는 게 똑같음

# 데이터 종류 이름 (팀 학습 데이터의 category 칸: 자기소개서는 "cover_letter", 보고서는 "report")
CATEGORY = "report"

# 시스템 지시문 — 팀 학습 데이터(자기소개서 등)와 글자 하나까지 똑같이 맞춤
# (학습 데이터끼리 지시문이 같아야 섞어서 학습해도 AI가 헷갈리지 않음)
SYSTEM_INSTRUCTION = (
    "너는 생각한줄의 한국어 글쓰기 도우미다. "
    "사용자의 요청 형식과 제공된 사실을 지킨다. "
    "제공되지 않은 개인 경험, 수치, 연구 결과, 출처는 꾸며내지 않는다."
)

# 사용자 요청 마지막 줄 (모든 데이터에 똑같이 들어감)
REQUEST_TEXT = "제공한 사실만 활용하여 객관적이고 자연스러운 보고서 본문을 작성해 줘. 없는 내용은 추가하지 마."

# 한자 글자 범위 (유니코드에서 한자가 모여 있는 구간: 기본 한자 + 확장 A + 호환 한자)
HANJA = "\u3400-\u4DBF\u4E00-\u9FFF\uF900-\uFAFF"
HANJA_CHAR = re.compile(f"[{HANJA}]")  # 한자 한 글자
# 지울 따옴표 기호들 (곧은 따옴표, 둥근 따옴표, 낫표)
QUOTE_CHARS = re.compile(r"[\"'“”‘’「」『』]")

# 문장 끝 → 메모 끝 바꾸기 규칙 (위에서부터 먼저 맞는 규칙 하나만 적용)
# 예) "설립되었다." → "설립됨", "증가하였다." → "증가함", "수도이다." → "수도"
ENDING_RULES = [
    (r"(되었|됐)다$", "됨"),
    (r"(하였|했)다$", "함"),
    (r"된다$", "됨"),
    (r"한다$", "함"),
    (r"(이었|였)다$", ""),
    (r"이다$", ""),
    (r"있다$", "있음"),
    (r"없다$", "없음"),
    (r"는다$", "음"),  # "않는다" → "않음", "믿는다" → "믿음"
    (r"(았|었)다$", "음"),
]

# 한글 한 글자 = 첫소리 + 가운데소리 + 끝소리(받침) 조합 (유니코드 계산으로 받침만 바꿀 수 있음)
HANGUL_START = 0xAC00  # "가"
JONG_COUNT = 28  # 받침 종류 수 (받침 없음 포함)
JONG_NIEUN = 4  # ㄴ 받침 번호
JONG_MIEUM = 16  # ㅁ 받침 번호
JONG_SSANGSIOT = 20  # ㅆ 받침 번호


def nominalize_ending(memo: str) -> str:
    """위 규칙에 안 걸린 "~다"로 끝나는 말을 메모 말투로 (받침을 보고 판단)
      - "늘어났다", "낮아졌다" (ㅆ 받침 + 다) → "늘어났음", "낮아졌음"
      - "쓰인다", "간다" (ㄴ 받침 + 다)     → "쓰임", "감"  (ㄴ 받침을 ㅁ 받침으로)
      - 그 밖 ("더디다" 등)                → 그대로 둠 (억지로 바꾸면 더 어색해서)
    """
    if len(memo) < 2 or not memo.endswith("다"):
        return memo
    last = memo[-2]  # "다" 바로 앞 글자
    code = ord(last) - HANGUL_START
    if not 0 <= code < 11172:  # 한글 글자가 아니면 그대로
        return memo
    jong = code % JONG_COUNT  # 받침 번호
    if jong == JONG_SSANGSIOT:
        return memo[:-1] + "음"
    if jong == JONG_NIEUN:
        changed = chr(ord(last) - JONG_NIEUN + JONG_MIEUM)  # ㄴ 받침 → ㅁ 받침
        return memo[:-2] + changed
    return memo

# 메모에서 뺄 문장 앞 연결어 ("그러나 ~" → "~")
LEADING_WORDS = r"^(그러나|하지만|또한|또|그리고|한편|따라서|이에|이후|특히|즉|다만)\s*,?\s*"


def remove_hanja_parens(text: str) -> str:
    """괄호 안에 한자가 1글자라도 있으면 그 괄호를 통째로 지움 (겹괄호도 바깥 괄호째로)
    예) 경제(經濟)는 → 경제는 / 국가(國家 (나라))는 → 국가는 / 장치(ESS) → 그대로
    방법: 글자를 하나씩 보면서 "(" 를 만나면 짝이 되는 ")" 까지(안쪽 괄호 포함) 한 덩어리로 묶고,
          그 덩어리에 한자가 있으면 버리고 없으면 그대로 붙임
    """
    result = []
    i = 0
    while i < len(text):
        if text[i] != "(":
            result.append(text[i])
            i += 1
            continue
        # 짝이 되는 닫는 괄호 찾기 (depth: 지금 몇 겹 괄호 안에 있는지)
        depth = 0
        j = i
        while j < len(text):
            if text[j] == "(":
                depth += 1
            elif text[j] == ")":
                depth -= 1
                if depth == 0:
                    break
            j += 1
        if j >= len(text):
            # 닫는 괄호가 없는 깨진 "(" → 이 글자만 그대로 두고 바로 다음 글자부터 계속 검사
            # (여기서 멈추면 그 뒤에 있는 한자 괄호를 못 지움)
            result.append("(")
            i += 1
            continue
        group = text[i : j + 1]  # "(" 부터 짝 ")" 까지
        if HANJA_CHAR.search(group):
            # 괄호 앞에 붙어 있던 빈칸도 같이 정리 ("경제 (經濟)는" → "경제는")
            while result and result[-1] == " ":
                result.pop()
        else:
            result.append(group)
        i = j + 1
    return "".join(result)


def clean_text(text: str) -> str:
    """정리 규칙 적용: 한자가 든 괄호 통째로 삭제 + 따옴표 기호 삭제 + 띄어쓰기 정리
    줄바꿈(문단 구분)은 그대로 둠
    """
    text = remove_hanja_parens(text)
    text = QUOTE_CHARS.sub("", text)
    lines = []
    for line in text.split("\n"):
        line = re.sub(r"[ \t]{2,}", " ", line)  # 빈칸 여러 개 → 하나
        line = re.sub(r"\s+([.,!?)])", r"\1", line)  # 문장 부호 앞 빈칸 삭제: "경제 ." → "경제."
        line = re.sub(r"\(\s*\)", "", line)  # 내용이 다 지워져 빈 괄호 "()"가 남았으면 삭제
        lines.append(line.strip())
    return "\n".join(lines)


def split_sentences(text: str) -> list[str]:
    """글 → 문장 목록 (마침표·물음표·느낌표 뒤 공백 기준)
    (?<=[.!?]): 앞 글자가 . ! ? 일 때만 나눔 → 문장 부호는 앞 문장에 남음
    """
    sentences = []
    for paragraph in text.split("\n"):
        for sentence in re.split(r"(?<=[.!?])\s+", paragraph.strip()):
            if len(sentence) >= 8:  # 너무 짧은 조각은 버림
                sentences.append(sentence)
    return sentences


def to_memo(sentence: str) -> str:
    """문장 하나 → 메모 한 줄 (사실은 그대로, 말투만 짧게)"""
    memo = sentence.strip().rstrip(".!?").strip()
    memo = re.sub(LEADING_WORDS, "", memo)
    for pattern, replacement in ENDING_RULES:
        if re.search(pattern, memo):
            memo = re.sub(pattern, replacement, memo)
            break
    else:
        # for ... else: 위 규칙 중 하나도 안 맞았을 때만 실행 → 받침을 보고 한 번 더 바꿔 봄
        memo = nominalize_ending(memo)
    # (괄호는 본문 정리 단계에서 한자 괄호만 이미 지웠음 → 나머지 괄호는 사실 정보라 남겨 둠)
    return re.sub(r"\s{2,}", " ", memo).strip(" ,")


def determine_document_type(title: str, body: str) -> str:
    """
    수집된 글의 제목과 내용 키워드를 기반으로
    보고서, 발표문, 자기소개서, 자유글쓰기, 기타 중 하나로 분류합니다.
    """
    combined_text = title + " " + body[:150]

    if any(k in combined_text for k in ["연설", "발표", "축사", "기조", "브리핑", "선언"]):
        return "발표문"
    elif any(k in combined_text for k in ["자기계발", "역량", "성장", "진로", "직무", "학습", "동기", "커리어", "취업", "교육", "경험", "도전"]):
        return "자기소개서"
    elif any(k in combined_text for k in ["에세이", "문화", "사상", "예술", "철학", "문학", "생각", "산문"]):
        return "자유글쓰기"
    elif any(k in combined_text for k in ["경제", "보고", "제도", "과학", "기술", "연구", "정책", "통계", "역사", "사회"]):
        return "보고서"
    else:
        return "기타"


def build_record(article: dict) -> dict | None:
    """위키백과 글 하나 → 학습 문제 하나 (팀 학습 데이터와 같은 category / prompt / completion 모양)"""
    # 1) 본문 정리 (한자 괄호·따옴표 삭제) + 문단 사이 빈 줄을 줄바꿈 하나로
    body = clean_text(article["body"])
    body = "\n".join(line for line in body.split("\n") if line)
    title = clean_text(article["title"])

    # 2) 정리된 본문의 모든 문장 → 사실 메모 (정답의 사실이 전부 메모에 들어가게)
    sentences = split_sentences(body)
    memos = [to_memo(s) for s in sentences]
    memos = [m for m in memos if len(m) >= 5]
    if len(memos) < 4:
        return None  # 메모가 너무 적으면 학습 문제로 쓰기 어려움

    memo_text = "\n".join(f"- {m}" for m in memos)
    user_prompt = f"글 유형: 보고서\n주제: {title}\n제공한 사실:\n{memo_text}\n요청: {REQUEST_TEXT}"

    doc_type = determine_document_type(article["title"], article["body"])

    user_prompt = (
        "작업: 초안 작성\n"
        f"글 유형: {doc_type}\n"
        f"제목: {article['title']}\n\n"
        f"[생각 메모]\n{memo_text}\n\n"
        f"생각 메모의 사실만 사용해서 자연스러운 {doc_type} 본문을 작성하세요."
    )
    return {
        "prompt": [
            {"role": "system", "content": SYSTEM_INSTRUCTION},
            {"role": "user", "content": user_prompt},
        ],
        # 정답: 정리된 위키백과 본문 (출처·라이선스는 wiki_sources.csv에 따로 남김)
        "completion": [{"role": "assistant", "content": body}],
        # 정답: 원래 위키백과 글 (문단은 빈 줄로 구분)
        "completion": [{"role": "assistant", "content": article["body"]}],
        # 학습에는 안 쓰지만 나중에 확인·출처 표기용으로 같이 남겨 둠 (document_type 메타데이터 추가)
        "meta": {
            "source": article["source"],
            "license": article["license"],
            "url": article["url"],
            "document_type": doc_type
        },
    }


def save_jsonl(path: Path, records: list[dict]) -> None:
    with open(path, "w", encoding="utf-8") as file:
        for record in records:
            file.write(json.dumps(record, ensure_ascii=False) + "\n")


def main() -> None:
    if not RAW_PATH.exists():
        print("먼저 python crawl_wikipedia.py 로 글을 모아 주세요.")
        return

    with open(RAW_PATH, encoding="utf-8") as file:
        articles = [json.loads(line) for line in file if line.strip()]

    # 같은 글이 두 번 들어간 경우 하나만 (page_id 기준)
    unique = {}
    for article in articles:
        unique.setdefault(article.get("page_id") or article["title"], article)
    articles = list(unique.values())

    records = [r for r in (build_record(a) for a in articles) if r]
    if len(records) < 2:
        print(f"학습 문제로 만들 수 있는 글이 {len(records)}개뿐이에요. crawl_wikipedia.py로 글을 더 모아 주세요.")
        return

    # 섞은 뒤 앞 10%는 시험용, 나머지는 학습용
    random.Random(RANDOM_SEED).shuffle(records)
    test_count = max(1, int(len(records) * TEST_RATIO))
    save_jsonl(TEST_PATH, records[:test_count])
    save_jsonl(TRAIN_PATH, records[test_count:])

    # 출처 목록 (엑셀에서도 한글이 안 깨지게 utf-8-sig)
    with open(SOURCES_PATH, "w", encoding="utf-8-sig", newline="") as file:
        writer = csv.writer(file)
        writer.writerow(["제목", "주소", "출처", "라이선스", "수집 시각"])
        for article in articles:
            writer.writerow(
                [article["title"], article["url"], article["source"], article["license"], article["retrieved_at"]]
            )

    print(f"원본 글 {len(articles)}개 → 학습 문제 {len(records)}개")
    print(f"  학습용 {len(records) - test_count}개 → {TRAIN_PATH}")
    print(f"  시험용 {test_count}개 → {TEST_PATH}")
    print(f"  출처 목록 → {SOURCES_PATH}")


# 이 파일을 직접 실행했을 때만 main() 실행
if __name__ == "__main__":
    main()