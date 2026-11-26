"""V7 전용 서버에만 연결한다. 초안·피드백·채점 클라이언트는 변경하지 않는다."""
import os
import requests
from fastapi import HTTPException
from factcheck_protocol import MODEL_SHA256,service_payload,input_digest,public_result


def check_facts(payload):
    url=os.getenv('FACTCHECK_LLM_URL','').strip().rstrip('/')
    token=(os.getenv('FACTCHECK_LLM_TOKEN') or os.getenv('THINKING_LLM_TOKEN','')).strip()
    if not url or not token:raise HTTPException(503,'자료 사실검사 연결이 준비되지 않았어요. 단원 채점은 계속 이용할 수 있어요.')
    expected=os.getenv('FACTCHECK_EXPECTED_SHA256',MODEL_SHA256).strip()
    if expected!=MODEL_SHA256:raise HTTPException(503,'선택한 V7 모델 설정을 확인해야 합니다.')
    try:data=service_payload(payload)
    except ValueError as exc:raise HTTPException(422,str(exc)) from exc
    try:
        response=requests.post(url+'/fact-check',json=data,headers={'X-LLM-Token':token},timeout=(3,35))
    except requests.Timeout as exc:raise HTTPException(504,'자료 사실검사 시간이 초과됐어요. 단원 채점은 계속 이용할 수 있어요.') from exc
    except requests.RequestException as exc:raise HTTPException(503,'자료 사실검사에 연결하지 못했어요. 단원 채점은 계속 이용할 수 있어요.') from exc
    if response.status_code==422:raise HTTPException(422,'검사할 자료나 본문이 너무 길거나 형식이 맞지 않아요. 내용을 줄여 주세요.')
    if response.status_code in (401,403,503):raise HTTPException(503,'자료 사실검사를 지금 이용할 수 없어요. 단원 채점은 계속 이용할 수 있어요.')
    try:
        response.raise_for_status();result=response.json()
        if not isinstance(result,dict) or set(result)!={'model_version','adapter_sha256','input_digest','diagnosis'}:
            raise ValueError('result_fields')
        if result['model_version']!='v7' or result['adapter_sha256']!=expected or result['input_digest']!=input_digest(data):
            raise ValueError('model_or_input_mismatch')
        return public_result(data,result['diagnosis'])
    except (requests.RequestException,ValueError,TypeError,KeyError) as exc:
        raise HTTPException(502,'자료 사실검사 결과를 확인하지 못했어요. 단원 채점은 계속 이용할 수 있어요.') from exc
