"""Protect one-run execution and safe temporary API shutdown."""
from collections import Counter
from pathlib import Path
from types import SimpleNamespace
import json
import sys

import pytest

sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
import curated_1459_study as study


def test_fresh_cases_are_balanced_source_only_and_have_three_lengths():
    cases=study.fresh_cases()
    assert len(cases)==len({c['id'] for c in cases})==40
    assert Counter(c['genre'] for c in cases)==Counter({g:10 for g in study.data.GENRE_NAMES})
    assert len({study.digest(c['facts']) for c in cases})==40
    assert all(not {'answer','completion','gold'}&set(c) for c in cases)
    assert {tuple(c['bounds']) for c in cases}=={(120,180),(160,240),(280,420)}


@pytest.mark.parametrize('extra_child',[False,True])
def test_pause_stops_only_api_processes_and_rejects_unrelated_children(tmp_path,monkeypatch,extra_child):
    root=tmp_path/'llm_training';out=root/'outputs/study';adapter=root/'old_run/adapter'
    adapter.mkdir(parents=True)
    (adapter/'adapter_model.safetensors').write_bytes(b'old verified model')
    folder=root/'outputs/gpu_server';folder.mkdir(parents=True)
    config={'pid':100,'profile':'old_profile','adapter':str(adapter)}
    (folder/'server.json').write_text(json.dumps(config),encoding='utf-8')
    stopped=[]
    class Process:
        def __init__(self,pid):self.pid=pid
        def cmdline(self):
            return (['python','-m','uvicorn','common_llm:app','--host','127.0.0.1','--port','8001']
                    if self.pid in (100,101) else ['conhost.exe'] if self.pid==102 else ['unrelated'])
        def name(self):return 'conhost.exe' if self.pid==102 else 'python.exe'
        def ppid(self):return 100
        def children(self,recursive):return [Process(101),Process(102)]+([Process(103)] if extra_child else [])
        def terminate(self):stopped.append(self.pid)
        def wait(self,timeout):pass
    monkeypatch.setitem(sys.modules,'psutil',SimpleNamespace(Process=Process,NoSuchProcess=RuntimeError))
    monkeypatch.setattr(study,'ROOT',root);monkeypatch.setattr(study,'OUT',out)
    monkeypatch.setattr(study,'request_json',lambda _: {'loaded':True,'loaded_identity':{
        'adapter_sha256':study.sha(adapter/'adapter_model.safetensors'),'profile':'old_profile'}})
    if extra_child:
        with pytest.raises(AssertionError,match='Unexpected child'):study.pause_service()
        assert not stopped
    else:
        snapshot=study.pause_service()
        assert stopped==[101,100] and snapshot['stopped_pids']==[101,100]
        assert 102 not in stopped


def test_completed_or_incomplete_training_cannot_silently_start_again(tmp_path,monkeypatch):
    monkeypatch.setattr(study,'OUT',tmp_path)
    monkeypatch.setattr(study,'check_protocol',lambda: {})
    (tmp_path/'training_state.json').write_text('{"status":"completed"}')
    with pytest.raises(RuntimeError,match='Training already started'):study.train()
