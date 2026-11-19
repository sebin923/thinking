"""Real local authenticated smoke checks; no production account/database writes."""
import json
import argparse
from pathlib import Path
import sys
import sqlite3
import requests

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'llm_training'))
from final_release import sha

OUT=ROOT/'llm_training/outputs/final_release_20261119'
RUNTIME=OUT/'local_web'
BASE='http://127.0.0.1:8000'


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    local_selection=ROOT/'llm_training/outputs/local_selection.json'
    parser.add_argument('--selection-file',type=Path,default=local_selection if local_selection.exists() else OUT/'selection.json')
    parser.add_argument('--evidence-dir',type=Path,default=OUT)
    parser.add_argument('--output-dir',type=Path,default=OUT)
    args=parser.parse_args()
    args.output_dir.mkdir(parents=True,exist_ok=True)
    selection=json.loads(args.selection_file.read_text(encoding='utf-8'))
    cfg=selection['applied_config']
    adapter=ROOT/'llm_training'/cfg['adapter']
    expected_sha=sha(adapter/'adapter_model.safetensors')
    token=(ROOT/'thinking_llm_token').read_text(encoding='utf-8-sig').strip()
    private=json.loads((RUNTIME/'private_config.json').read_text(encoding='utf-8'))
    checks=[];details=[]
    def check(name,condition):
        checks.append({'name':name,'passed':bool(condition)})
        print(('PASS ' if condition else 'FAIL ')+name,flush=True)
        if not condition:raise RuntimeError(name)
    def call(method,endpoint,**kwargs):
        response=session.request(method,BASE+endpoint,timeout=(10,180),**kwargs)
        details.append({'endpoint':endpoint,'status':response.status_code})
        check(endpoint,response.status_code==200)
        return response.json()
    session=requests.Session()
    session.trust_env=False
    gpu=requests.Session()
    gpu.trust_env=False
    check('Local-only database',session.get(BASE+'/api/local-status',timeout=10).json()['database']=='separate_local_sqlite')
    login=session.post(BASE+'/api/auth/login',json={'login_id':'thinking_demo','password':private['demo_password']},timeout=15)
    check('Normal authenticated login',login.status_code==200)
    session.headers['Authorization']='Bearer '+login.json()['access_token']
    pref=call('GET','/api/writing/preferences')
    prefs={k:pref[k] for k in ('preferred_tone','sentence_length','feedback_style','ai_assistance')}
    call('PUT','/api/writing/preferences',json=prefs)
    curated=cfg.get('writing_profile')=='curated_over1000_20261119'
    case_path=args.evidence_dir/('inputs.json' if curated else 'cases.json')
    cases=[c for c in json.loads(case_path.read_text(encoding='utf-8')) if c.get('split','fresh')=='fresh']
    labels={'report':'보고서','cover_letter':'자기소개서','speech':'발표문','free_writing':'자유 글쓰기'}
    outputs=[]
    checkpoint=args.output_dir/'smoke_outputs.json'
    signature={'adapter':expected_sha,'profile':cfg.get('writing_profile','legacy'),
        'preferences':prefs,'cases_sha256':sha(case_path)}
    if checkpoint.exists():
        cached=json.loads(checkpoint.read_text(encoding='utf-8'))
        if cached['signature']==signature:outputs=cached['outputs']
    for index in (9,19,29,39):
        case=cases[index]
        if any(o['genre']==case['genre'] for o in outputs):continue
        doc=call('POST','/api/documents',json={'document_type':labels[case['genre']],'title':'로컬 점검 '+case['topic']})
        for fact in case['facts']:call('POST','/api/thoughts',json={'document_id':doc['id'],'content':fact})
        draft=call('POST',f'/api/documents/{doc["id"]}/draft-common-ai')
        check(labels[case['genre']]+' actual selected weights',draft['loaded_identity']['adapter_sha256']==expected_sha)
        check(labels[case['genre']]+' normal model termination',draft['eos_stopped'])
        if curated:
            check(labels[case['genre']]+' review banner metadata',draft.get('local_review_only') is True)
            check(labels[case['genre']]+' evaluated generation limit',draft.get('generation_max_new_tokens')==512)
        outputs.append({'genre':case['genre'],'document_id':doc['id'],'draft':draft})
        checkpoint.write_text(json.dumps({'signature':signature,'outputs':outputs},ensure_ascii=False,indent=2),encoding='utf-8')
    health=gpu.get('http://127.0.0.1:8001/health',timeout=10).json()
    if not health.get('loaded'):
        warm=cases[0]
        response=gpu.post('http://127.0.0.1:8001/draft',headers={'X-LLM-Token':token},timeout=(10,180),
            json={'document_type':warm['genre'],'topic':warm['topic'],'facts':warm['facts'],'target_chars':150})
        check('Cold model load and real generation',response.status_code==200)
        health=gpu.get('http://127.0.0.1:8001/health',timeout=10).json()
    check('Loaded adapter fingerprint',health['loaded_identity']['adapter_sha256']==expected_sha)
    check('Loaded writing profile',health['loaded_identity']['profile']==cfg.get('writing_profile','legacy'))
    # Reproduce one frozen input through the actual API when the final profile passed.
    if selection['selected_candidate']:
        evidence=args.evidence_dir/'application_v2' if cfg.get('writing_profile')=='application_v2_20261119' else args.evidence_dir
        if cfg.get('writing_profile')=='application_v2_20261119':cases=json.loads((evidence/'fresh_cases.json').read_text(encoding='utf-8'))
        c=cases[0]
        response=gpu.post('http://127.0.0.1:8001/draft',headers={'X-LLM-Token':token},timeout=(10,180),
            json={'document_type':c['genre'],'topic':c['topic'],'facts':c['facts'],'target_chars':150})
        check('Actual API same-input generation',response.status_code==200)
        if curated:
            from curated_1459_study import digest
            check('Evaluation and serving prompt parity',response.json()['input_sha256']==digest(c['prompt']))
            check('Evaluation and serving decode limit',response.json()['generation_max_new_tokens']==512)
        else:
            previous=[json.loads(l) for l in (evidence/'generations.jsonl').read_text(encoding='utf-8').splitlines()]
            expected=next(r['text'] for r in previous if r['model']==selection['selected_candidate'] and r['case_id']==c['id'])
            check('Evaluation and serving parity',response.json()['content']==expected)
    saved=call('POST','/api/drafts',json={'document_id':outputs[0]['document_id'],'content':outputs[0]['draft']['content']})
    feedback=call('POST',f'/api/drafts/{saved["id"]}/feedback-ai')
    body=feedback['feedback']
    check('Feedback has actual quoted source',isinstance(body.get('overall_feedback'),str)
        and isinstance(body.get('highlights'),list)
        and all(h['original_text'] in outputs[0]['draft']['content'] for h in body['highlights']))
    call('POST','/api/learn/practice-recommendation',json={'unit_id':'local-final-check','type_label':'보고서',
        'unit_title':'확인한 범위 설명','task':'자료의 사실과 미확인 상태를 구분해 쓰세요.','rules':['누가 무엇을 했는지 구분한다.'],
        'candidates':[{'id':'a','title':'자료 목록 점검','summary':'전체와 일부 점검을 구분하는 자료'},
            {'id':'b','title':'장비 전달 기록','summary':'발송과 수신 확인을 구분하는 자료'}],'current_topic':''})
    # Isolated fixture for this synthetic smoke unit only. Real lesson progress is untouched.
    with sqlite3.connect(RUNTIME/'thinking_local.sqlite') as local_db:
        uid=local_db.execute('SELECT user_id FROM users WHERE login_id=?',('thinking_demo',)).fetchone()[0]
        row=local_db.execute('SELECT payload,revision FROM learning_progress WHERE user_id=?',(uid,)).fetchone()
        progress=json.loads(row[0]) if row else {'units':{},'wrong':{}}
        progress['units'].setdefault('local-final-check',{})['passed']=True
        payload=json.dumps(progress,ensure_ascii=False)
        if row:local_db.execute('UPDATE learning_progress SET payload=?,revision=? WHERE user_id=?',(payload,row[1]+1,uid))
        else:local_db.execute('INSERT INTO learning_progress(user_id,revision,payload,legacy_imported) VALUES(?,?,?,?)',(uid,0,payload,0))
    call('POST','/api/learn/writing-score',json={'unit_id':'local-final-check','type_label':'보고서','unit_title':'확인한 범위 설명',
        'rules':['누가 무엇을 했는지 구분한다.'],'task':'자료에 근거해 확인 범위를 쓰세요.',
        'practice':{'kind':'data','topic':'작업 기록 확인','facts':['검토자는 기록 10개 중 4개만 확인함','나머지 6개는 확인하지 않음']},
        'text':'검토자는 작업 기록 10개 중 4개를 확인했다. 나머지 6개는 아직 확인하지 않았다.',
        'training_consent':False})
    before=call('GET','/api/ai-usage/today')
    ambiguous=call('POST','/api/documents',json={'document_type':'자유 글쓰기','title':'뜻 확인 점검'})
    call('POST','/api/thoughts',json={'document_id':ambiguous['id'],'content':'도구는 보관함'})
    response=session.post(BASE+f'/api/documents/{ambiguous["id"]}/draft-common-ai',timeout=(10,180))
    if cfg.get('writing_profile') in ('final_20261119','application_v2_20261119','application_service_20261119','curated_over1000_20261119'):
        check('Ambiguous memo asks for clarification',response.status_code==422 and '뜻' in str(response.json()))
        after=call('GET','/api/ai-usage/today')
        check('Clarification does not charge usage',before==after)
    label={'Ver3':'Ver3 + 최종 작성 지시','Final2000':'최종 2,000개 모델','5000':'5,000개 모델 + 최종 작성 지시',
        'Balanced2000':'이전 2,000개 모델 + 최종 작성 지시','Curated1459':'정제 1,459개 모델'}.get(selection['selected_candidate'],'Ver3 기존 구성 유지')
    if selection.get('local_review_only'):label+=' (로컬 검토용)'
    value={'status':'functional_checks_passed','selected_label':label,'selected_candidate':selection['selected_candidate'],
        'summary':'네 글 유형 초안, 로그인, 피드백, 연습 추천과 채점 통과',
        'checks':checks,'requests':details,'outputs':outputs,'loaded_identity':health['loaded_identity'],
        'scope':'loopback only, separate SQLite, synthetic demo account','remote_deployment':False,
        'quality_gate_passed':selection.get('quality_gate_passed',True),'local_review_only':selection.get('local_review_only',False),
        'structured_mode':health.get('structured_mode'),'remaining_issue':'Other-person plans and source facts still need review; warnings do not certify factuality.'}
    (args.output_dir/'web_verification.json').write_text(json.dumps(value,ensure_ascii=False,indent=2),encoding='utf-8')
    print('LOCAL_WEB_VERIFIED',len(checks),flush=True)


if __name__=='__main__':main()
