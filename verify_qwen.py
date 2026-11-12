"""학교 Qwen 서버 점검. 기본은 상태만, --full은 실제 생성·피드백·구조화를 실행한다."""
import argparse
import json
import os
import sys
from pathlib import Path
from urllib.request import Request, urlopen
from urllib.error import HTTPError, URLError

PROTOCOL = "qwen-unified-v1"

def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--root", type=Path, required=True, help="thinking 프로젝트 폴더")
    p.add_argument("--url", default="http://100.120.168.56:8001")
    p.add_argument("--full", action="store_true")
    a = p.parse_args()
    token = os.getenv("THINKING_LLM_TOKEN", "").strip()
    if not token and (a.root / ".thinking_llm_token").is_file():
        token = (a.root / ".thinking_llm_token").read_text(encoding="utf-8-sig").strip()
    def call(path, payload=None):
        body = None if payload is None else json.dumps(payload, ensure_ascii=False).encode("utf-8")
        headers = {} if payload is None else {"X-LLM-Token": token, "Content-Type":"application/json"}
        req = Request(a.url.rstrip("/") + path, data=body, headers=headers)
        try:
            with urlopen(req, timeout=180 if body else 10) as response:
                data = json.loads(response.read().decode("utf-8"))
        except HTTPError as exc:
            detail = exc.read().decode("utf-8",errors="replace")
            if token:
                detail = detail.replace(token,"[키 숨김]")
            raise RuntimeError(f"{path}: HTTP {exc.code} {detail[:600]}") from exc
        except (URLError, TimeoutError, ValueError) as exc:
            raise RuntimeError(f"{path}: 연결 또는 응답 확인 실패 ({type(exc).__name__})") from exc
        if not isinstance(data, dict) or data.get("protocol") != PROTOCOL:
            raise RuntimeError("새 common_llm.py로 AI 서버를 재시작해 주세요.")
        return data
    try:
        health = call("/health")
        print(json.dumps(health, ensure_ascii=False, indent=2), flush=True)
        if not health.get("token_configured"):
            raise RuntimeError("학교 AI 서버에 연결 키를 설정하고 재시작해 주세요.")
        if not a.full:
            print("서버 버전·연결 확인 완료. 실제 생성 검사는 --full을 붙이세요.")
            return
        if not token:
            raise RuntimeError("연결 키 파일 또는 THINKING_LLM_TOKEN 환경변수가 필요합니다.")
        print("실제 Qwen 생성 검사 시작. 첫 요청은 모델을 불러오는 시간이 필요합니다.", flush=True)
        facts=["강의실 창가 블라인드 한 곳이 내려오지 않는다.","조교에게 상태를 알렸다.",
            "고장 원인은 아직 확인되지 않았다.","점검 날짜는 아직 정해지지 않았다."]
        draft = call("/draft", {"document_type":"보고서","topic":"강의실 블라인드 점검",
            "facts":facts,"tone":"기본","target_chars":160,"mode":"common"})
        if not draft.get("content") or draft.get("personalized") is not False:
            raise RuntimeError("공통 초안 응답을 확인해 주세요.")
        print("초안:",draft["content"],flush=True)
        print("확인 항목:",draft.get("checks",[]),flush=True)
        feedback=call("/feedback",{"document_type":"보고서","content":" ".join(facts)})
        print("피드백:",json.dumps(feedback.get("feedback"),ensure_ascii=False),flush=True)
        structure=call("/structure",{"content":" ".join(facts)})
        print("생각 구조화:",json.dumps(structure.get("structure"),ensure_ascii=False),flush=True)
        print("세 기능이 응답했습니다. 사실 보존·맞춤법·자연스러움은 출력 내용을 직접 확인하세요.")
    except (OSError, RuntimeError) as exc:
        print(str(exc),file=sys.stderr)
        sys.exit(1)

if __name__=="__main__":
    main()

