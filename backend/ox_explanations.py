"""O/X 해설에 남은 생성용 인용 표시만 제거한다."""
import re


CITATION_PLACEHOLDER = re.compile(r"\[cite:\s*\d+(?:\s*[,，]\s*\d+)*\s*\]", re.IGNORECASE)


def clean_ox_explanation(value):
    """나머지 문장·공백·출처 표기는 그대로 유지한다."""
    return CITATION_PLACEHOLDER.sub("", value) if isinstance(value, str) else value
