"""python install.py --root C:\\Users\\...\\Documents\\thinking"""
import argparse
import secrets
import shutil
from datetime import datetime
from pathlib import Path
p=argparse.ArgumentParser()
p.add_argument('--root', type=Path, required=True)
a=p.parse_args()
r=a.root.resolve()
if not (r/'backend/routers').is_dir() or not (r/'llm_training').is_dir():
    raise SystemExit('thinking 프로젝트 폴더를 지정해 주세요.')
source=Path(__file__).resolve().parent
stamp=datetime.now().strftime('%Y%m%d_%H%M%S_%f')
for rel in ['llm_training/common_llm.py','backend/routers/writing.py','llm_training/start_common.ps1']:
    dest=r/rel
    if dest.exists():
        shutil.copy2(dest, dest.with_name(dest.name+'.backup_'+stamp))
    shutil.copy2(source/rel, dest)
    print('설치:',dest)
key=r/'.thinking_llm_token'
if not key.exists():
    key.write_text(secrets.token_urlsafe(32),encoding='utf-8')
print('연결용 키 준비 완료. 키 파일은 공유하거나 Git에 올리지 마세요.')
