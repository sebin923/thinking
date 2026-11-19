"""Run the real web app on loopback using a separate local SQLite database.

The existing backend/.env and remote member database are not modified. The demo
account uses the normal login/password flow. Secrets stay in ignored runtime files.
"""
import argparse
import json
import os
from pathlib import Path
import secrets
import socket
import subprocess
import sys

ROOT=Path(__file__).resolve().parents[1]
RUNTIME=ROOT/'llm_training/outputs/final_release_20261119/local_web'


def runtime_config():
    RUNTIME.mkdir(parents=True,exist_ok=True)
    path=RUNTIME/'private_config.json'
    if path.exists():return json.loads(path.read_text(encoding='utf-8'))
    config={'jwt_secret':secrets.token_urlsafe(48),'demo_password':secrets.token_urlsafe(15)}
    path.write_text(json.dumps(config),encoding='utf-8')
    (RUNTIME/'로그인_정보.txt').write_text(
        '로컬 시연 전용 계정\n주소: http://127.0.0.1:5173\n아이디: thinking_demo\n비밀번호: '+config['demo_password']+
        '\n\n운영 회원 데이터와 분리된 로컬 저장소입니다.\n',encoding='utf-8')
    return config


def backend_app():
    config=runtime_config()
    sys.path.insert(0,str(ROOT/'backend'))
    # database.py creates a PostgreSQL engine but does not open a connection.
    # Replace it before the app registers tables or imports any routers.
    for key,value in {'DB_HOST':'localhost','DB_PORT':'5432','DB_NAME':'unused_local',
                      'DB_USER':'unused','DB_PASSWORD':'unused'}.items():os.environ[key]=value
    os.environ['JWT_SECRET_KEY']=config['jwt_secret']
    os.environ['COMMON_LLM_URL']='http://127.0.0.1:8001'
    os.environ['THINKING_LLM_TOKEN']=(ROOT/'thinking_llm_token').read_text(encoding='utf-8-sig').strip()
    from sqlalchemy import create_engine
    from sqlalchemy.orm import sessionmaker
    import database
    database.engine.dispose()
    database.engine=create_engine('sqlite:///'+str(RUNTIME/'thinking_local.sqlite'),
        connect_args={'check_same_thread':False})
    database.SessionLocal=sessionmaker(bind=database.engine,autocommit=False,autoflush=False)
    import main
    import models
    from security import hash_password
    with database.SessionLocal() as db:
        if db.query(models.User).filter_by(login_id='thinking_demo').first() is None:
            db.add(models.User(login_id='thinking_demo',name='로컬 시연',email='demo@thinking.invalid',
                phone='01000000000',password_hash=hash_password(config['demo_password']),
                email_verified=True,role='general',ai_credits=100,status='active'))
            db.commit()
    @main.app.get('/api/local-status')
    def local_status():return {'environment':'local_demo','database':'separate_local_sqlite','llm_url':'http://127.0.0.1:8001'}
    return main.app


def start(args):
    if not args.node or not Path(args.node).is_file():raise ValueError('--node must identify the available Node executable')
    for port in (8000,5173):
        with socket.socket() as connection:
            connection.settimeout(1)
            if connection.connect_ex(('127.0.0.1',port))==0:raise RuntimeError(f'Port {port} already in use; inspect before starting')
    runtime_config()
    metadata={}
    if args.with_model:
        local_selection=ROOT/'llm_training/outputs/local_selection.json'
        selection_path=args.selection_file or (local_selection if local_selection.exists() else ROOT/'llm_training/model_selection.json')
        selection=json.loads(Path(selection_path).read_text(encoding='utf-8'))
        selection=selection.get('applied_config',selection)
        adapter=(ROOT/'llm_training'/selection['adapter']).resolve()
        subprocess.run([str(ROOT/'llm_training/.venv/Scripts/python.exe'),str(ROOT/'deploy/gpu_server.py'),
            '--start','--adapter',str(adapter),'--profile',selection.get('writing_profile','legacy')],
            cwd=ROOT,check=True)
        metadata['llm']=json.loads((ROOT/'llm_training/outputs/gpu_server/server.json').read_text(encoding='utf-8'))
        metadata['selection_file']=str(Path(selection_path).resolve())
    for name,command,cwd in [
        ('backend',[sys.executable,str(Path(__file__).resolve()),'backend'],ROOT),
        ('frontend',[args.node,str(ROOT/'frontend/node_modules/vite/bin/vite.js'),'--host','127.0.0.1','--port','5173','--strictPort'],ROOT/'frontend')]:
        with (RUNTIME/f'{name}.out.log').open('ab') as out,(RUNTIME/f'{name}.err.log').open('ab') as err:
            process=subprocess.Popen(command,cwd=cwd,stdin=subprocess.DEVNULL,stdout=out,stderr=err,
                creationflags=subprocess.CREATE_NO_WINDOW if os.name=='nt' else 0)
        metadata[name]={'pid':process.pid,'url':f'http://127.0.0.1:{8000 if name=="backend" else 5173}'}
    (RUNTIME/'processes.json').write_text(json.dumps(metadata,indent=2),encoding='utf-8')
    print(json.dumps(metadata,indent=2))


if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('action',choices=['backend','check','start'])
    parser.add_argument('--node')
    parser.add_argument('--with-model',action='store_true',help='Start the explicitly selected completed model as well')
    parser.add_argument('--selection-file',type=Path,help='Explicit local-review model configuration; global service selection is preserved')
    args=parser.parse_args()
    if args.action=='backend':
        import uvicorn
        uvicorn.run(backend_app(),host='127.0.0.1',port=8000)
    elif args.action=='check':
        from fastapi.testclient import TestClient
        with TestClient(backend_app()) as client:
            config=runtime_config()
            response=client.post('/api/auth/login',json={'login_id':'thinking_demo','password':config['demo_password']})
            assert response.status_code==200,response.status_code
            assert response.json()['access_token']
            assert client.get('/api/local-status').json()['database']=='separate_local_sqlite'
            print('Local backend and normal authenticated login verified. No remote database connection.')
    else:start(args)
