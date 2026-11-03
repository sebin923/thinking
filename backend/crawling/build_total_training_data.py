# =============================================================
# build_total_training_data.py — 통합 수집 데이터(total_articles.csv) → 학습 데이터(JSONL)
# -------------------------------------------------------------
# 입력: total_articles.csv (열: 번호, 제목, 글자 수, 문단 제목, 본문, 주소, 출처, 라이선스, 수집 시각)
#   출처별로 글 유형을 정해서 학습 데이터로 바꿈
#     - 한국어 위키백과 (+ 칼럼 소스, 자기소개서 소스) → category "report"       / 글 유형: 보고서
#       (칼럼·자소서 소스도 내용은 백과사전 설명문이라 보고서로 통일 — 팀 결정)
#     - 한국어 위키문헌 (근대 수필)                      → category "free_writing" / 글 유형: 자유 글쓰기
#     - 대한민국 정책브리핑 (연설문)                     → category "speech"       / 글 유형: 발표문
#       ※ 웹페이지를 통째로 긁어 와서 메뉴·댓글 규칙 같은 찌꺼기가 섞여 있음 → 연설 본문만 골라냄
#       ※ 정책브리핑 연설문은 "공공누리 제4유형(출처표시+상업적 이용금지+변경금지)" 자료 (팀이 알고 포함하기로 함)
#
# 정리 규칙 (본문·사실 목록 모두 적용)
#   - 괄호 안에 한자가 들어 있으면 그 괄호를 통째로 지움: 경제(經濟)는 → 경제는
#   - 따옴표 기호는 지우고 안의 글자는 남김: "녹색 성장"이라는 → 녹색 성장이라는
#
# 만드는 방법: 완성된 글(정답)의 모든 문장을 짧은 사실 메모로 바꿔서 "제공한 사실"로 넣음
#   → 정답에 있는 사실이 전부 메모에 있어야, AI가 지어내지 않고 주어진 사실로만 쓰는 법을 배움
#
# 결과 (입력 CSV와 같은 폴더의 training_output/)
#   total_train.jsonl    학습용 (글 유형별로 90%)
#   total_test.jsonl     시험용 (글 유형별로 10%, 학습 전·후 비교용)
#   total_sources.csv    학습 데이터에 들어간 글의 출처 목록 (출처 표기용)
#
# 실행: python build_total_training_data.py total_articles.csv
# =============================================================

import csv
import json
import random
import re
import sys
from collections import Counter, defaultdict
from pathlib import Path

RANDOM_SEED = 42  # 섞는 순서를 고정 → 몇 번 실행해도 학습/시험 나뉘는 게 똑같음
TEST_RATIO = 0.1  # 시험용으로 떼어 둘 비율

# 시스템 지시문 — 팀 학습 데이터(자기소개서 등)와 글자 하나까지 똑같이
SYSTEM_INSTRUCTION = (
    "너는 생각한줄의 한국어 글쓰기 도우미다. "
    "사용자의 요청 형식과 제공된 사실을 지킨다. "
    "제공되지 않은 개인 경험, 수치, 연구 결과, 출처는 꾸며내지 않는다."
)

# 글 유형별 설정: category 값 / "글 유형:" 줄 / "요청:" 줄 / 정답 최대 길이(글자)
TYPES = {
    "report": {
        "label": "보고서",
        "request": "제공한 사실만 활용하여 객관적이고 자연스러운 보고서 본문을 작성해 줘. 없는 내용은 추가하지 마.",
        "max_chars": 1600,
    },
    "free_writing": {
        "label": "자유 글쓰기",
        "request": "제공한 내용만 활용하여 생각과 느낌이 드러나는 자연스러운 글을 작성해 줘. 없는 내용은 추가하지 마.",
        "max_chars": 1600,
    },
    "speech": {
        "label": "발표문",
        "request": "제공한 내용만 활용하여 청중 앞에서 말하듯 자연스러운 발표문을 작성해 줘. 없는 내용은 추가하지 마.",
        "max_chars": 2000,  # 연설문은 길어서 앞부분을 문장 단위로 이만큼까지만 사용
    },
    "cover_letter": {
        "label": "자기소개서",
        "request": "제공한 사실만 활용하여 직무 역량과 경험이 돋보이는 자연스러운 자기소개서 본문을 작성해 줘. 없는 내용은 추가하지 마.",
        "max_chars": 1600,
    },
}


def category_of(source_or_row) -> str | None:
    """출처 이름 또는 row → category (모르는 출처면 None = 건너뜀)"""
    if isinstance(source_or_row, dict):
        row = source_or_row
        source = row["출처"]
        title = row.get("제목", "")
        if source.startswith("한국어 위키백과"):
            if "자기소개서" in title or "자소서" in title or "자기소개서 소스" in source:
                return "cover_letter"
            return "report"
        if source.startswith("한국어 위키문헌"):
            return "free_writing"
        if source.startswith("대한민국 정책브리핑"):
            return "speech"
        if source.startswith("자기소개서") or source.startswith("자소서"):
            return "cover_letter"
        return None
    
    source = source_or_row
    if source.startswith("한국어 위키백과"):
        return "report"
    if source.startswith("한국어 위키문헌"):
        return "free_writing"
    if source.startswith("대한민국 정책브리핑"):
        return "speech"
    if source.startswith("자기소개서") or source.startswith("자소서"):
        return "cover_letter"
    return None


# ===================== 정리 규칙 =====================

HANJA_CHAR = re.compile("[㐀-䶿一-鿿豈-﫿]")  # 한자 한 글자
QUOTE_CHARS = re.compile(r"[\"'“”‘’「」『』｢｣＂＇]")  # 지울 따옴표 기호 (반각·전각 낫표, 전각 따옴표 포함)


def remove_hanja_parens(text: str) -> str:
    """괄호 안에 한자가 1글자라도 있으면 그 괄호를 통째로 지움 (겹괄호는 바깥 괄호째로)
    예) 경제(經濟)는 → 경제는 / 국가(國家 (나라))는 → 국가는 / 장치(ESS) → 그대로
    """
    result = []
    i = 0
    while i < len(text):
        if text[i] != "(":
            result.append(text[i])
            i += 1
            continue
        depth = 0  # 지금 몇 겹 괄호 안인지
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
            # 짝이 없는 "(" → 그 글자만 두고 다음 글자부터 계속 검사
            result.append("(")
            i += 1
            continue
        group = text[i : j + 1]
        if HANJA_CHAR.search(group):
            while result and result[-1] == " ":  # 괄호 앞 빈칸도 정리
                result.pop()
        else:
            result.append(group)
        i = j + 1
    return "".join(result)


def clean_text(text: str) -> str:
    """한자 괄호 삭제 + 따옴표 삭제 + 띄어쓰기 정리 (줄바꿈은 유지)"""
    text = remove_hanja_parens(text)
    text = QUOTE_CHARS.sub("", text)
    lines = []
    for line in text.split("\n"):
        line = re.sub(r"[ \t]{2,}", " ", line)  # 빈칸 여러 개 → 하나
        line = re.sub(r"\s+([.,!?)])", r"\1", line)  # 문장 부호 앞 빈칸 삭제
        line = re.sub(r"\(\s*\)", "", line)  # 빈 괄호 삭제
        lines.append(line.strip())
    return "\n".join(lines)


# ===================== 정책브리핑: 연설 본문만 골라내기 =====================


# 연설 본문이 끝나는 표시 (이 줄부터는 저작권 안내·이전 기사 목록 같은 페이지 찌꺼기)
SPEECH_END_MARKERS = ("이 자료는", "공공누리가 부착되지 않은", "<자료출처", "이전다음기사 영역")
# 공공누리 표시가 없는 자료 → 담당자 허락 없이는 쓸 수 없어서 학습 데이터에서 뺌
NO_LICENSE_MARK = "공공누리가 부착되지 않은"


def extract_speech(raw: str, title: str) -> str | None:
    """웹페이지를 통째로 긁은 글에서 연설 본문만 꺼냄 (못 찾거나 쓸 수 없는 자료면 None)
    페이지 구조:  ... 연설자 : ○○ / 연설일 : ○○ / ... 인쇄하기 / 목록 / (제목+장소 한 줄, 없을 수도) / ★연설 본문★ / 이 자료는 ... (저작권 안내)
    """
    if NO_LICENSE_MARK in raw:
        return None  # 공공누리 미부착 = 허락 없이 사용 불가
    lines = [line.strip() for line in raw.split("\n")]
    try:
        speaker_at = next(i for i, line in enumerate(lines) if line.startswith("연설자"))
    except StopIteration:
        return None  # 연설자 줄이 없으면 연설문 페이지가 아님 (예: 뉴스·목록 페이지)
    try:
        start = next(i for i in range(speaker_at, len(lines)) if lines[i] == "목록") + 1
        end = next(i for i in range(start, len(lines)) if lines[i].startswith(SPEECH_END_MARKERS))
    except StopIteration:
        return None
    # 목록 바로 다음 줄이 "제목 (장소)" 줄이면 건너뜀 (본문이 아니라 제목 반복)
    head = re.sub(r"^\[[^\]]*\]\s*", "", title)[:8]  # "[모두발언] 협약형..." → "협약형..." 앞 8글자
    while start < end and not lines[start]:
        start += 1
    if start < end and head and lines[start].startswith(head):
        start += 1
    body_lines = [line for line in lines[start:end] if line]
    if not body_lines:
        return None
    # 연설문은 화면 폭에 맞춰 문장 중간에서 줄이 바뀌어 있음 → 줄을 이어 붙여 한 덩어리로
    text = " ".join(body_lines)
    text = re.sub(r"([.!?])(?=[가-힣A-Za-z])", r"\1 ", text)  # "있는데요.이 중에" → 마침표 뒤 띄우기
    return text


# ===================== 문장 → 사실 메모 =====================

# 문장 끝 → 메모 끝 바꾸기 (위에서부터 처음 맞는 규칙 하나만)
ENDING_RULES = [
    (r"(되었|됐)다$", "됨"),
    (r"(하였|했)다$", "함"),
    (r"된다$", "됨"),
    (r"한다$", "함"),
    (r"(이었|였|았|었)다$", r"\1음"),  # 보였다 → 보였음, 주었다 → 주었음
    (r"이다$", ""),  # 수도이다 → 수도
    (r"있다$", "있음"),
    (r"없다$", "없음"),
    (r"는다$", "음"),  # 않는다 → 않음
    (r"습니다$", "음"),  # 있습니다 → 있음, 했습니다 → 했음 (연설문 말투)
]
LEADING_WORDS = r"^(그러나|하지만|또한|또|그리고|한편|따라서|이에|이후|특히|즉|다만)\s*,?\s*"

HANGUL_START = 0xAC00  # "가"
JONG_COUNT = 28  # 받침 종류 수
JONG = {"ㄴ": 4, "ㅁ": 16, "ㅂ": 17, "ㅆ": 20}  # 받침 번호


def change_jong(char: str, new_jong: int) -> str:
    """한글 한 글자의 받침만 바꿈 (예: "랍" → "람")"""
    code = ord(char) - HANGUL_START
    return chr(HANGUL_START + code - code % JONG_COUNT + new_jong)


def jong_of(char: str) -> int | None:
    """한글 한 글자의 받침 번호 (한글이 아니면 None)"""
    code = ord(char) - HANGUL_START
    return code % JONG_COUNT if 0 <= code < 11172 else None


def nominalize(memo: str) -> str:
    """규칙에 안 걸린 끝맺음을 받침을 보고 메모 말투로
      - "바랍니다", "드립니다" (ㅂ받침+니다) → "바람", "드림"
      - "늘어났다" (ㅆ받침+다) → "늘어났음"
      - "쓰인다" (ㄴ받침+다) → "쓰임"
      - 그 밖은 그대로 (억지로 바꾸면 더 어색해서)
    """
    if memo.endswith("니다") and len(memo) >= 3 and jong_of(memo[-3]) == JONG["ㅂ"]:
        return memo[:-3] + change_jong(memo[-3], JONG["ㅁ"])
    if memo.endswith("다") and len(memo) >= 2:
        jong = jong_of(memo[-2])
        if jong == JONG["ㅆ"]:
            return memo[:-1] + "음"
        if jong == JONG["ㄴ"]:
            return memo[:-2] + change_jong(memo[-2], JONG["ㅁ"])
    return memo


# 기술 용어 및 개발 스택은 허용하고, 불필요한 일반 영어 노이즈(common 등)만 정밀 차단
ALLOWED_TECH_TERMS = {
    "java", "spring", "springboot", "react", "native", "mysql", "postgresql", 
    "redis", "aws", "s3", "ec2", "docker", "compose", "api", "rest", "sql", 
    "git", "json", "jsonl", "csv", "html", "css", "javascript"
}

def has_unwanted_mixed_english(sentence: str) -> bool:
    """기술 용어는 제외하고, 문맥에 어울리지 않는 일반 소문자 영단어가 섞여 있는지 판별"""
    words = sentence.split()
    for word in words:
        clean_word = re.sub(r'[^a-zA-Z]', '', word).lower()
        if len(clean_word) >= 3 and not clean_word.isupper():
            if clean_word not in ALLOWED_TECH_TERMS:
                return True
    return False


def split_sentences(text: str) -> list[str]:
    """글 → 문장 목록 (마침표·물음표·느낌표 뒤 공백 기준)"""
    sentences = []
    for paragraph in text.split("\n"):
        for sentence in re.split(r"(?<=[.!?])\s+", paragraph.strip()):
            if len(sentence) >= 5:
                eng_chars = sum(1 for c in sentence if "a" <= c.lower() <= "z")
                if len(sentence.strip()) > 0 and (eng_chars / len(sentence.strip())) > 0.5:
                    continue
                if has_unwanted_mixed_english(sentence):
                    continue
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
        memo = nominalize(memo)
    return re.sub(r"\s{2,}", " ", memo).strip(" ,")


def cut_by_sentence(sentences: list[str], max_chars: int) -> list[str]:
    """문장을 앞에서부터 담다가 max_chars를 넘기기 직전에 멈춤 (문장 중간에서 안 끊기게)"""
    picked, total = [], 0
    for sentence in sentences:
        if total + len(sentence) > max_chars and picked:
            break
        picked.append(sentence)
        total += len(sentence) + 1
    return picked


# ===================== 글 하나 → 학습 데이터 하나 =====================


def build_record(row: dict) -> tuple[dict, str] | None:
    category = category_of(row)
    if category is None:
        return None
    setting = TYPES[category]

    if category == "speech":
        raw = extract_speech(row["본문"], row["제목"])
        if raw is None:
            return None
        body = clean_text(raw)
        sentences = cut_by_sentence(split_sentences(body), setting["max_chars"])
        completion = " ".join(sentences)  # 연설문은 문단 구분이 없어서 한 덩어리로
    else:
        body = clean_text(row["본문"])
        # 문단은 유지하면서 문장 단위로 길이 제한
        paragraphs = [p for p in body.split("\n") if p]
        kept, total = [], 0
        for paragraph in paragraphs:
            sentences = split_sentences(paragraph)
            room = setting["max_chars"] - total
            part = cut_by_sentence(sentences, room) if total + len(paragraph) > setting["max_chars"] else sentences
            if not part:
                break
            kept.append(" ".join(part))
            total += sum(len(s) + 1 for s in part)
            if len(part) < len(sentences):
                break
        completion = "\n".join(kept)
        sentences = split_sentences(completion)

    memos = [m for m in (to_memo(s) for s in sentences) if len(m) >= 4]
    if len(memos) < 4 or len(completion) < 200:
        return None  # 너무 짧으면 학습 문제로 쓰기 어려움

    title = clean_text(row["제목"])
    memo_text = "\n".join(f"- {m}" for m in memos)
    user_prompt = (
        f"글 유형: {setting['label']}\n주제: {title}\n제공한 사실:\n{memo_text}\n요청: {setting['request']}"
    )
    record = {
        "category": category,
        "prompt": [
            {"role": "system", "content": SYSTEM_INSTRUCTION},
            {"role": "user", "content": user_prompt},
        ],
        "completion": [{"role": "assistant", "content": completion}],
    }
    return record, category


def main() -> None:
    if len(sys.argv) < 2:
        print("사용법: python build_total_training_data.py total_articles.csv")
        return
    csv_path = Path(sys.argv[1])
    out_dir = csv_path.parent / "training_output"
    out_dir.mkdir(exist_ok=True)

    # utf-8-sig: 엑셀용 CSV 맨 앞 표시(BOM)를 알아서 무시하고 읽음
    with open(csv_path, encoding="utf-8-sig", newline="") as file:
        rows = list(csv.DictReader(file))

    by_category = defaultdict(list)  # { category: [(학습 데이터, 원본 줄), ...] }
    skipped = Counter()
    for row in rows:
        built = build_record(row)
        if built is None:
            skipped[row["출처"]] += 1
            continue
        record, category = built
        by_category[category].append((record, row))

    # 글 유형별로 따로 섞어서 10%씩 시험용으로 → 시험 데이터에도 유형이 고르게 들어감
    rng = random.Random(RANDOM_SEED)
    train, test, used_rows = [], [], []
    for category in TYPES:
        items = by_category.get(category, [])
        rng.shuffle(items)
        n_test = max(1, int(len(items) * TEST_RATIO)) if len(items) >= 10 else 0
        test += [record for record, _ in items[:n_test]]
        train += [record for record, _ in items[n_test:]]
        used_rows += [(category, row) for _, row in items]
    rng.shuffle(train)  # 학습할 때 한 유형만 몰려 나오지 않게 섞기

    for name, records in (("total_train.jsonl", train), ("total_test.jsonl", test)):
        with open(out_dir / name, "w", encoding="utf-8") as file:
            for record in records:
                file.write(json.dumps(record, ensure_ascii=False) + "\n")

    with open(out_dir / "total_sources.csv", "w", encoding="utf-8-sig", newline="") as file:
        writer = csv.writer(file)
        writer.writerow(["category", "제목", "주소", "출처", "라이선스", "수집 시각"])
        for category, row in used_rows:
            writer.writerow([category, row["제목"], row["주소"], row["출처"], row["라이선스"], row["수집 시각"]])

    print(f"입력 글 {len(rows)}개 → 학습 데이터 {len(train) + len(test)}개")
    for category in TYPES:
        print(f"  {category:13s} {len(by_category.get(category, []))}개")
    print(f"  학습용 {len(train)}개 / 시험용 {len(test)}개 → {out_dir}")
    if skipped:
        print("  건너뛴 글:", dict(skipped))


if __name__ == "__main__":
    main()