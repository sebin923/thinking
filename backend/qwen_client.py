"""학교 Qwen 서버로만 AI 요청을 보낸다."""
import os
import requests
from dotenv import load_dotenv
load_dotenv()
PROTOCOL = "qwen-unified-v1"

class QwenServiceError(ValueError):
    def __init__(self, message, status_code=502):
        super().__init__(message)
        self.status_code = status_code

def _post(path, payload):
    token = os.getenv("THINKING_LLM_TOKEN", "").strip()
    if not token:
        raise QwenServiceError("백엔드의 LLM 연결 키가 설정되지 않았습니다.", 503)
    url = os.getenv("COMMON_LLM_URL", "http://127.0.0.1:8001").rstrip("/")
    try:
        response = requests.post(url + path, json=payload,
            headers={"X-LLM-Token": token}, timeout=(5, 180), allow_redirects=False)
    except requests.Timeout as exc:
        raise QwenServiceError("AI 응답 시간이 초과되었습니다.", 504) from exc
    except requests.RequestException as exc:
        raise QwenServiceError("학교 AI 서버에 연결하지 못했습니다.", 503) from exc
    if response.status_code in (401, 403):
        raise QwenServiceError("백엔드와 AI 서버의 연결 키를 확인해 주세요.", 503)
    if response.status_code == 404:
        raise QwenServiceError("AI 서버를 새 버전으로 재시작해 주세요.", 503)
    if response.status_code == 409:
        raise QwenServiceError("사용 가능한 개인 모델이 없습니다.", 409)
    if response.status_code == 422:
        raise QwenServiceError("입력 길이 또는 생성 내용을 확인해 주세요. AI 서버가 결과를 반환하지 않았습니다.", 422)
    if response.status_code != 200:
        raise QwenServiceError("AI 서버가 요청을 처리하지 못했습니다. 서버 콘솔을 확인해 주세요.")
    try:
        data = response.json()
    except ValueError as exc:
        raise QwenServiceError("AI 서버 응답 형식이 올바르지 않습니다.") from exc
    if not isinstance(data, dict) or data.get("protocol") != PROTOCOL:
        raise QwenServiceError("AI 서버와 백엔드를 함께 업데이트해 주세요.", 503)
    return data

def generate_draft(*, facts, document_type, topic, user_preferences=None, user_id=None, mode="auto"):
    prefs = user_preferences or {}
    tone = {"natural":"친근", "formal":"격식", "confident":"격식",
        "기본":"기본", "담백":"담백", "격식":"격식", "친근":"친근"}.get(prefs.get("preferred_tone"), "기본")
    target = {"short":160,"normal":350,"long":500}.get(prefs.get("sentence_length"),350)
    data = _post("/draft", {"document_type":document_type,"topic":topic,"facts":facts,
        "tone":tone,"target_chars":target,"mode":mode,"user_id":user_id})
    if not isinstance(data.get("content"),str) or not data["content"].strip() or len(data["content"])>2000:
        raise QwenServiceError("AI가 유효한 초안을 반환하지 않았습니다.")
    if type(data.get("personalized")) is not bool or (mode=="personal" and not data["personalized"]):
        raise QwenServiceError("AI 모델 선택 결과가 올바르지 않습니다.")
    return {**data,"tone":tone,"personalization_type":"adapter" if data["personalized"] else "preference_prompt"}

def create_draft_with_ai(thought_text: str, document_type: str="", user_preferences=None):
    if not thought_text.strip():
        raise ValueError("초안을 작성할 생각 내용이 없습니다.")
    return generate_draft(facts=[thought_text],document_type=document_type or "자유 글쓰기",
        topic=document_type or "글쓰기",user_preferences=user_preferences,mode="common")["content"]

def create_feedback_with_ai(content: str, document_type: str="", user_preferences=None):
    if not content.strip():
        raise ValueError("피드백을 받을 글이 없습니다.")
    data = _post("/feedback",{"content":content,"document_type":document_type,"preferences":user_preferences or {}})
    result = data.get("feedback")
    if not isinstance(result,dict) or not isinstance(result.get("overall_feedback"),str) or not isinstance(result.get("highlights"),list):
        raise QwenServiceError("피드백 형식이 올바르지 않습니다.")
    return result

def structure_thought(thought_text: str):
    if not thought_text.strip():
        raise ValueError("구조화할 생각을 입력해 주세요.")
    data = _post("/structure",{"content":thought_text})
    result = data.get("structure")
    keys=("situation","problem","action","result","meaning")
    if not isinstance(result,dict) or any(not isinstance(result.get(k),str) for k in keys):
        raise QwenServiceError("구조화 결과가 올바르지 않습니다.")
    return {k:result[k] for k in keys}

def build_personalization_prompt(user_preferences=None):
    prefs=user_preferences or {}
    tone={"natural":"자연스럽게","formal":"격식 있게","confident":"명확하게"}.get(prefs.get("preferred_tone"),"자연스럽게")
    return f"한국어로 {tone} 작성하되 원문의 사실을 유지하세요."

