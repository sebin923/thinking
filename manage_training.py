"""노트북에서 후보 검토/내보내기를 실행. 토큰을 파일에 저장하지 않는다."""
import argparse
import getpass
import json
from pathlib import Path
import urllib.request
import urllib.error

class Client:
    def __init__(self, url): self.url, self.token = url.rstrip('/'), ''
    def call(self, path, body=None, binary=False):
        headers = {'Content-Type': 'application/json'}
        if self.token: headers['Authorization'] = 'Bearer ' + self.token
        request = urllib.request.Request(self.url + path, headers=headers,
                    data=json.dumps(body, ensure_ascii=False).encode() if body is not None else None)
        try:
            with urllib.request.urlopen(request, timeout=60) as response:
                raw = response.read()
                return raw if binary else json.loads(raw)
        except urllib.error.HTTPError as exc:
            try: message=json.loads(exc.read()).get('detail',str(exc.code))
            except Exception: message=str(exc.code)
            raise ValueError(str(message)) from None

def show(value):print(json.dumps(value,ensure_ascii=False,indent=2))
def yes(label):return input(label + ' [확인했으면 yes]: ').strip().lower() == 'yes'

def main():
    parser=argparse.ArgumentParser()
    parser.add_argument('--url',default='http://127.0.0.1:8000',help='백엔드 또는 사이트 주소. /api 제외')
    args=parser.parse_args()
    c=Client(args.url)
    result=c.call('/api/auth/login',{'login_id':input('로그인 아이디: ').strip(),'password':getpass.getpass('비밀번호: ')})
    c.token=result['access_token']
    print('로그인 완료. 관리자 계정만 검토/내보내기가 가능합니다.')
    while True:
        print('\n1 후보 검토  2 승인 글 목록  3 데이터셋 만들기  4 기존 데이터셋 다운로드\n5 학습 실험 기록  6 내 후보/동의 철회  0 종료')
        choice=input('선택: ').strip()
        try:
            if choice=='0':break
            if choice=='1':
                offset=int(input('목록 시작 위치 [Enter=0]: ') or '0')
                rows=c.call(f'/api/training/candidates?offset={offset}')
                for row in rows:
                    print(f"ID {row['id']} | {row['score']}점 | {row['source'].get('type_label')} | {row['source'].get('unit_title')}")
                selected=input('검토할 ID [Enter=돌아가기]: ').strip()
                if not selected:continue
                row=next((x for x in rows if str(x['id'])==selected),None)
                if not row:raise ValueError('목록에 있는 ID를 선택하세요.')
                show(row)
                action=input('approve 승인 / reject 제외 / Enter 보류: ').strip()
                if action not in ('approve','reject'):continue
                body={'expected_revision':row['revision'],'decision':'approved' if action=='approve' else 'rejected'}
                if action=='approve':
                    for key,label in [('facts_checked','주체·시간·부정·사실 왜곡 없음'),('quality_checked','분량·맞춤법·자연스러움·반복을 확인'),('privacy_checked','이름·연락처 등 개인정보가 없음을 확인'),('author_confirmed','작성자 본인의 글과 이용 권한을 확인'),('context_confirmed','입력 자료만으로 정답 글을 작성할 수 있음을 확인')]:
                        body[key]=yes(label)
                    body['synthetic']=not yes('합성 데모 글이 아닌 실제 제출 글임을 확인')
                    context_file=input('작성자가 확인한 사실 자료 TXT 경로 [자기소개서 필수/그 외 Enter=원자료]: ').strip().strip('"')
                    if context_file:body['training_context']=Path(context_file).read_text(encoding='utf-8-sig')
                body['note']=input('검토 메모 [선택 사항]: ').strip()
                show(c.call(f"/api/training/candidates/{row['id']}/review",body))
            elif choice=='2':show(c.call('/api/training/candidates?status=approved'))
            elif choice=='3':
                result=c.call('/api/training/exports',{})
                show({k:v for k,v in result.items() if k!='members'})
                save(c,result['export_id'])
            elif choice=='4':
                show(c.call('/api/training/exports'))
                eid=input('다운로드할 export_id: ').strip()
                save(c,eid)
            elif choice=='5':
                filename=input('실험 기록 JSON 파일 경로: ').strip().strip('"')
                show(c.call('/api/training/runs',json.loads(Path(filename).read_text(encoding='utf-8-sig'))))
            elif choice=='6':
                show(c.call('/api/training/mine'))
                cid=input('철회할 본인 후보 ID [Enter=돌아가기]: ').strip()
                if cid and yes('이 후보의 학습 동의를 철회'):
                    show(c.call(f'/api/training/mine/{int(cid)}/withdraw',{}))
        except (ValueError, OSError) as exc:print('처리하지 못했습니다:',exc)

def save(c,eid):
    if len(eid)!=32 or any(ch not in '0123456789abcdef' for ch in eid):raise ValueError('export_id 형식 오류')
    data=c.call(f'/api/training/exports/{eid}/download',binary=True)
    output=Path.cwd()/f'qwen_training_{eid}.zip'
    if output.exists():raise ValueError('같은 파일이 이미 있습니다: '+str(output))
    output.write_bytes(data)
    print('저장:',output)

if __name__=='__main__':
    try:main()
    except (KeyboardInterrupt,EOFError):print('\n종료')
    except (ValueError,OSError) as exc:raise SystemExit(str(exc))
