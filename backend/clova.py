import os
import json
import uuid
import requests
from dotenv import load_dotenv

load_dotenv()

CLOVA_API_KEY = os.getenv("CLOVA_API_KEY")

CLOVA_URL = (
    "https://clovastudio.stream.ntruss.com/"
    "v3/chat-completions/HCX-007"
)


# --------------------------------------------------
# 1. 생각 구조화
# --------------------------------------------------
def structure_thought(thought_text: str):
    if not CLOVA_API_KEY:
        raise ValueError(
            "CLOVA_API_KEY가 없습니다. "
            ".env 파일을 확인해주세요."
        )

    headers = {
        "Authorization": f"Bearer {CLOVA_API_KEY}",
        "X-NCP-CLOVASTUDIO-REQUEST-ID": str(uuid.uuid4()),
        "Content-Type": "application/json"
    }

    body = {
        "messages": [
            {
                "role": "system",
                "content": (
                    "당신은 사용자가 입력한 경험을 "
                    "글쓰기 구조로 정리하는 글쓰기 보조 AI입니다. "

                    "반드시 사용자가 직접 입력한 내용만 사용하세요. "
                    "사용자가 말하지 않은 경험이나 사실을 "
                    "추측하거나 만들어내지 마세요. "

                    "다음 기준에 따라 각 항목을 명확하게 분리하세요. "

                    "situation은 경험이 발생한 배경이나 상황입니다. "

                    "problem은 사용자가 당시 겪은 문제, "
                    "어려움 또는 해결해야 했던 상황입니다. "

                    "action은 사용자가 문제를 해결하거나 "
                    "상황을 개선하기 위해 직접 한 행동입니다. "

                    "result는 action 이후 실제로 발생한 변화, "
                    "성과 또는 결과입니다. "

                    "meaning은 사용자가 그 경험을 통해 "
                    "직접 언급한 배운 점, 느낀 점 또는 의미입니다. "

                    "특히 action과 result를 하나로 합치지 마세요. "

                    "예를 들어 사용자가 "
                    "'메뉴를 외우고 반복해서 연습한 뒤 "
                    "혼자 주문을 받을 수 있게 되었다'라고 말했다면, "

                    "action은 "
                    "'메뉴를 외우고 반복해서 연습함', "

                    "result는 "
                    "'혼자 주문을 받을 수 있게 됨'으로 "
                    "분리해야 합니다. "

                    "사용자 입력에서 확인할 수 없는 항목은 "
                    "빈 문자열로 반환하세요."
                )
            },
            {
                "role": "user",
                "content": thought_text
            }
        ],

        "topP": 0.8,
        "topK": 0,
        "maxCompletionTokens": 1000,
        "temperature": 0.2,
        "repetitionPenalty": 1.1,

        "thinking": {
            "effort": "none"
        },

        "responseFormat": {
            "type": "json",
            "schema": {
                "type": "object",

                "properties": {
                    "situation": {
                        "type": "string",
                        "description": "경험이 발생한 배경이나 상황"
                    },

                    "problem": {
                        "type": "string",
                        "description": "사용자가 경험한 문제 또는 어려움"
                    },

                    "action": {
                        "type": "string",
                        "description": "문제를 해결하기 위해 사용자가 직접 한 행동"
                    },

                    "result": {
                        "type": "string",
                        "description": "사용자의 행동 이후 실제로 발생한 결과나 변화"
                    },

                    "meaning": {
                        "type": "string",
                        "description": "사용자가 직접 언급한 배운 점이나 경험의 의미"
                    }
                },

                "required": [
                    "situation",
                    "problem",
                    "action",
                    "result",
                    "meaning"
                ]
            }
        }
    }

    response = requests.post(
        CLOVA_URL,
        headers=headers,
        json=body,
        timeout=30
    )

    response.raise_for_status()

    data = response.json()

    content = data["result"]["message"]["content"]

    structure = json.loads(content)

    return structure


# --------------------------------------------------
# 2. AI 초안 작성
# --------------------------------------------------
def create_draft_with_ai(
    thought_text: str,
    document_type: str = ""
):
    if not CLOVA_API_KEY:
        raise ValueError(
            "CLOVA_API_KEY가 없습니다. "
            ".env 파일을 확인해주세요."
        )

    headers = {
        "Authorization": f"Bearer {CLOVA_API_KEY}",
        "X-NCP-CLOVASTUDIO-REQUEST-ID": str(uuid.uuid4()),
        "Content-Type": "application/json"
    }

    system_prompt = (
        "당신은 사용자의 글쓰기를 돕는 글쓰기 보조 AI입니다. "

        "사용자가 제공한 생각과 경험만 사용해서 "
        "자기소개서 또는 보고서 초안을 작성하세요. "

        "절대로 사용자에게 되묻지 마세요. "
        "추가 정보를 요청하지 마세요. "
        "답변은 반드시 완성된 초안 형태로 작성하세요. "

        "사용자가 제공하지 않은 경험, 성과, 수치, 사실은 "
        "절대 만들어내지 마세요. "

        "내용이 부족하더라도 질문하지 말고, "
        "주어진 내용만 바탕으로 짧은 초안을 작성하세요. "

        "문장은 자연스럽게 연결하되, "
        "사용자가 나중에 직접 수정할 수 있도록 "
        "과하게 완성된 대필문처럼 쓰지 마세요. "
    )

    if document_type:
        system_prompt += (
            f"현재 작성할 글의 종류는 '{document_type}'입니다. "
            "글의 종류에 맞는 문체와 흐름으로 작성하세요. "
        )

    body = {
        "messages": [
            {
                "role": "system",
                "content": system_prompt
            },
            {
                "role": "user",
                "content": (
                    f"글 종류: {document_type}\n\n"
                    f"사용자 생각:\n{thought_text}\n\n"
                    "위 내용을 바탕으로 초안을 작성하세요."
                )
            }
        ],

        "topP": 0.8,
        "topK": 0,
        "maxCompletionTokens": 1200,
        "temperature": 0.4,
        "repetitionPenalty": 1.1,

        "thinking": {
            "effort": "none"
        }
    }

    response = requests.post(
        CLOVA_URL,
        headers=headers,
        json=body,
        timeout=30
    )

    response.raise_for_status()

    data = response.json()

    return data["result"]["message"]["content"]


# --------------------------------------------------
# 직접 테스트할 때만 실행
# --------------------------------------------------
if __name__ == "__main__":
    test_text = (
        "카페 아르바이트를 시작했는데 "
        "처음에는 주문 실수가 많았다. "
        "메뉴를 외우고 반복해서 연습한 뒤 "
        "혼자 주문을 받을 수 있게 되었다."
    )

    print("===== 구조화 테스트 =====")

    structure_result = structure_thought(test_text)

    print(structure_result)

    print()

    print("===== 초안 테스트 =====")

    draft_result = create_draft_with_ai(
        test_text,
        "자기소개서"
    )

    print(draft_result)