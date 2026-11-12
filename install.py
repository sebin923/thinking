"""첨부본과 일치하는 코드만 백업 후 교체한다."""
import argparse, ast, hashlib, json, os, re, shutil, tempfile
from pathlib import Path
from datetime import datetime
SOURCE=Path(__file__).resolve().parent
EXPORTS={"structure_thought","create_draft_with_ai","create_feedback_with_ai","build_personalization_prompt"}
SKIP={".git","__pycache__","node_modules","venv","data","outputs"}

def digest(data):
    return hashlib.sha256(data.decode("utf-8-sig").replace("\r\n","\n").encode("utf-8")).hexdigest()

def migrate(text,filename):
    tree=ast.parse(text,filename=filename)
    raw=text.encode("utf-8");offsets=[0]
    for line in text.splitlines(keepends=True):
        offsets.append(offsets[-1]+len(line.encode("utf-8")))
    edits=[]
    for n in ast.walk(tree):
        new=None
        if isinstance(n,ast.ImportFrom) and n.module=="clova" and n.level==0:
            if {a.name for a in n.names}-EXPORTS:
                raise ValueError(filename+": 별도 확인이 필요한 AI 함수 import가 있습니다.")
            start=offsets[n.lineno-1]+n.col_offset;end=offsets[n.end_lineno-1]+n.end_col_offset
            new=re.sub(r"\bfrom\s+clova\b","from qwen_client",raw[start:end].decode("utf-8"),count=1)
        elif isinstance(n,ast.Import) and any(a.name=="clova" for a in n.names):
            new="import "+", ".join("qwen_client as "+(a.asname or "clova") if a.name=="clova"
                else a.name+(" as "+a.asname if a.asname else "") for a in n.names)
        elif isinstance(n,ast.ImportFrom) and n.module and "clova" in n.module.lower():
            raise ValueError(filename+": 상대/패키지 AI import를 먼저 확인해야 합니다.")
        if new is not None:
            edits.append((offsets[n.lineno-1]+n.col_offset,offsets[n.end_lineno-1]+n.end_col_offset,new.encode("utf-8")))
    for start,end,new in sorted(edits,reverse=True):
        raw=raw[:start]+new+raw[end:]
    result=raw.decode("utf-8")
    if re.search(r"CLOVA_API_KEY|CLOVA_URL|clovastudio|ntruss\.com|_call_clova|import_module\([\"']clova|__import__\([\"']clova",result,re.I):
        raise ValueError(filename+": 직접 CLOVA를 호출하는 코드가 남아 있습니다. 이 파일도 수정해야 합니다.")
    return result

def plan(root,part):
    manifest=json.loads((SOURCE/"manifest.json").read_text(encoding="utf-8"))
    parts={"all":("backend","frontend","llm_training"),"backend":("backend",),"frontend":("frontend",),"school":("llm_training",)}[part]
    if not all((root/p).is_dir() for p in parts):
        raise ValueError("--root에는 thinking 프로젝트 폴더를 지정하세요.")
    changes={}
    for rel,info in manifest["files"].items():
        if rel.split("/")[0] not in parts:continue
        data=(SOURCE/rel).read_bytes();target=root/rel
        if digest(data)!=info["new_sha256"]:raise ValueError("배포 파일 변경: "+rel)
        if target.is_symlink():raise ValueError("심볼릭 링크는 자동 교체하지 않습니다: "+rel)
        if target.exists():
            old=digest(target.read_bytes())
            if old==info["new_sha256"]:continue
            if old!=info.get("old_sha256"):
                raise ValueError("첨부본 이후 변경된 파일은 덮어쓰지 않습니다: "+rel)
        elif info.get("old_sha256"):raise ValueError("기존 파일 없음: "+rel)
        changes[rel]=data
    if "backend" in parts:
        old=root/"backend/clova.py"
        if old.exists() and digest(old.read_bytes())!=manifest["clova_old_sha256"]:
            raise ValueError("backend/clova.py가 첨부본과 다릅니다.")
        for directory,dirs,names in os.walk(root/"backend",followlinks=False):
            dirs[:]=[d for d in dirs if d not in SKIP and not d.startswith(".venv") and not (Path(directory)/d).is_symlink()]
            for name in names:
                path=Path(directory)/name
                if path.suffix!=".py" or path==old:continue
                rel=path.relative_to(root).as_posix()
                if path.is_symlink():raise ValueError("심볼릭 링크 확인 필요: "+rel)
                text=changes.get(rel,path.read_bytes()).decode("utf-8-sig").replace("\r\n","\n")
                updated=migrate(text,rel)
                if updated!=text:changes[rel]=updated.encode("utf-8")
        if old.exists():changes["backend/clova.py"]=None
    for rel,data in changes.items():
        if data is not None and rel.endswith(".py"):compile(data,rel,"exec")
    return changes

def atomic_write(path,data):
    path.parent.mkdir(parents=True,exist_ok=True)
    mode=path.stat().st_mode&0o777 if path.exists() else 0o644
    with tempfile.NamedTemporaryFile(dir=path.parent,delete=False) as f:
        temp=Path(f.name);f.write(data)
    try:
        temp.chmod(mode);os.replace(temp,path)
    finally:temp.unlink(missing_ok=True)

def apply_changes(root,changes):
    if not changes:
        print("이미 적용된 상태입니다.");return
    backup=root.parent/(root.name+"_qwen_backup_"+datetime.now().strftime("%Y%m%d_%H%M%S_%f"))
    backup.mkdir()
    old={}
    for rel in changes:
        path=root/rel;old[rel]=path.read_bytes() if path.exists() else None
        if old[rel] is not None:
            dest=backup/rel;dest.parent.mkdir(parents=True,exist_ok=True);shutil.copy2(path,dest)
    (backup/"changed_files.json").write_text(json.dumps({p:"new" if v is None else "existing" for p,v in old.items()},indent=2),encoding="utf-8")
    done=[]
    try:
        for rel,data in changes.items():
            done.append(rel)
            if data is None:(root/rel).unlink()
            else:atomic_write(root/rel,data)
    except Exception:
        for rel in reversed(done):
            if old[rel] is None:(root/rel).unlink(missing_ok=True)
            else:atomic_write(root/rel,old[rel])
        raise
    print("적용 완료. 이전 코드 백업:",backup)
    print("서버 재시작과 프론트엔드 재빌드가 필요합니다. 키·DB·학습 자료는 수정하지 않았습니다.")

def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument("--root",type=Path,required=True)
    p.add_argument("--part",choices=("all","school","backend","frontend"),default="all")
    g=p.add_mutually_exclusive_group();g.add_argument("--check",action="store_true");g.add_argument("--apply",action="store_true")
    a=p.parse_args()
    try:
        root=a.root.resolve();changes=plan(root,a.part)
        for rel,data in changes.items():print(("백업 후 제거: " if data is None else "교체/추가: ")+rel)
        if a.apply:apply_changes(root,changes)
        else:print("점검 완료. 아직 수정하지 않았습니다. 적용하려면 --apply를 사용하세요.")
    except (OSError,ValueError,SyntaxError) as exc:p.exit(1,f"적용하지 못했습니다: {exc}\n")
if __name__=="__main__":main()

