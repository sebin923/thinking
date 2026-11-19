"""Frozen final dataset, one fresh training run, and same-profile comparison.

All generation is local. Original datasets, adapters and evaluations are read-only.
"""
import argparse
from collections import Counter, defaultdict
from copy import deepcopy
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import random
import re
from types import SimpleNamespace

from final_writing_profiles import PROFILE_NAME, profile_messages, fit_messages

ROOT=Path(__file__).resolve().parent
OUT=ROOT/'outputs/final_release_20261119'
DATA=ROOT/'data/final_2000_20261119'
PARENT=ROOT/'data/quality_2000_balanced_v2'
MODEL='Qwen/Qwen3.5-2B'
MAX_LENGTH=2048
ADAPTERS={
    'Ver3':ROOT/'outputs/qwen35_epoch_study_20261117_155715_800799/epoch_1/adapter',
    '5000':ROOT/'outputs/qwen35_fresh_20261118_133437_958159/adapter',
    'Balanced2000':ROOT/'outputs/qwen35_fresh_20261119_125527_590020/adapter',
}

def sha(path):return hashlib.sha256(Path(path).read_bytes()).hexdigest()
def digest(value):return hashlib.sha256(json.dumps(value,ensure_ascii=False,sort_keys=True).encode()).hexdigest()
def save(path,value):
    path.parent.mkdir(parents=True,exist_ok=True)
    path.write_text(json.dumps(value,ensure_ascii=False,indent=2),encoding='utf-8')
def lines(path):return [json.loads(x) for x in path.read_text(encoding='utf-8-sig').splitlines() if x.strip()]
def save_lines(path,rows):path.write_text(''.join(json.dumps(r,ensure_ascii=False)+'\n' for r in rows),encoding='utf-8')
def req(case):
    return SimpleNamespace(document_type=case['genre'],topic=case['topic'],facts=case['facts'],
        target_chars=round(sum(case['bounds'])/2),tone='기본',source_context=case.get('source_context',''))
def messages(case,processor):
    _,values=profile_messages(req(case),bounds=case['bounds'])
    return fit_messages(values,processor)
def source(row):
    return {'genre':row['category'],'topic':row.get('topic',''),
        'facts':row.get('request',{}).get('facts') or re.findall(r'^-\s*(.+)$',row['prompt'][-1]['content'],re.M),
        'bounds':row['requested_char_bounds'],
        'source_context':'가상 연습 사례' if '가상' in row.get('prompt',[{'content':''}])[-1]['content'] else ''}

def prepare():
    from final_eval_cases import cases
    from final_training_examples import examples
    from transformers import AutoProcessor
    OUT.mkdir(parents=True,exist_ok=True)
    if (DATA/'manifest.json').exists():raise RuntimeError('Final dataset already frozen; do not overwrite.')
    evals=cases()
    protocol={
        'created_utc':datetime.now(timezone.utc).isoformat(),'holdout_cases':40,'per_genre':10,
        'profile':PROFILE_NAME,'prompt_budget':1536,'max_new_tokens':768,
        'generation':{'do_sample':False,'repetition_penalty':1.0,'no_repeat_ngram_size':0,'enable_thinking':False},
        'selection_order':['fewest critical source errors','highest mean naturalness','highest length compliance','highest nonrepetition'],
        'release_gate':{'critical_errors':0,'naturalness_min':8.0,'length_compliance_min':0.8,
            'per_genre_naturalness_min':7.5},
        'if_no_candidate_passes':'Keep existing service selection and publish limitations; no unapproved quality claim.',
        'critical_error_definition':'Unsupported source event, changed actor/count/negation/state/condition, or omission changing essential meaning.',
        'ratings':{'naturalness':'0-10: 10 fluent coherent prose; 8 minor awkwardness; 6 multiple fragments or strained subjects; 4 pervasive memo syntax.',
            'faithfulness':'0-10: 10 all essential propositions preserved without additions; 9 slight nuance loss; 7 important omission; <=5 reversal or invented event.',
            'nonrepetition':'0-10: 10 no redundant proposition; 8 one avoidable restatement; 6 multiple restatements.',
            'reviewer':'Primary assistant, blinded output order. Not independent human review; descriptive results without statistical superiority claim.'},
        'training_examples':2000,'replaced_examples':100,'epochs':1,'fresh_from_base':True,
        'no_external_generation_api':True,'no_additional_completed_training_after_this_run':True}
    for name,value in [('cases.json',evals),('protocol.json',protocol)]:
        path=OUT/name
        if path.exists():assert json.loads(path.read_text(encoding='utf-8'))==value or name=='protocol.json'
        else:save(path,value)
    # The holdout is now written before the dataset is produced or inference runs.
    processor=AutoProcessor.from_pretrained(MODEL,local_files_only=True)
    tok=processor.tokenizer
    parents=lines(PARENT/'train.jsonl')
    groups=defaultdict(list)
    for r in parents:groups[(r['category'],r.get('scenario_family_id',r['id']))].append(r)
    removed=[]
    for kind in ('report','free_writing'):
        candidates=[]
        for (genre,family),members in sorted(groups.items()):
            if genre==kind and len(members)>1:
                candidates.append(sorted(members,key=lambda r:r['id'])[-1])
        assert len(candidates)>=50,(kind,len(candidates))
        # Deterministic family coverage; retain other variants of every removed family.
        candidates.sort(key=lambda r:digest(r['id']))
        removed.extend(candidates[:50])
    removed_ids={r['id'] for r in removed}
    kept=[deepcopy(r) for r in parents if r['id'] not in removed_ids]
    additions=examples()
    for item in additions:
        kept.append({'id':item['id'],'category':item['category'],'topic':item['topic'],
            'synthetic':True,'human_review':False,'scenario_family_id':item['scenario_family_id'],
            'request':{'document_type':item['category'],'topic':item['topic'],'facts':item['facts'],
                'target_chars':item['target_chars'],'tone':'기본'},
            'requested_char_bounds':item['bounds'],
            'completion':[{'role':'assistant','content':item['answer']}],
            'assertion_trace':[{'source_fact_index':i,'source':f,'rendered':c,'status':'preserved'}
                for i,(f,c) in enumerate(zip(item['facts'],item['canonical_clauses']))],
            'authoring':{k:v for k,v in item.items() if k not in ('facts','answer','canonical_clauses')},
            'revision':'final_2000_20261119'})
    assert len(kept)==2000 and Counter(r['category'] for r in kept)==Counter({k:500 for k in ('report','free_writing','cover_letter','speech')})
    assert len({r['id'] for r in kept})==2000
    DATA.mkdir(parents=True,exist_ok=True)
    lengths=defaultdict(list); warnings=[]; example_counts=Counter(); rewritten=[]
    for split in ('train','valid','test'):
        records=kept if split=='train' else deepcopy(lines(PARENT/f'{split}.jsonl'))
        for r in records:
            before=digest(r)
            c=source(r)
            if split=='train':prompt,stats=messages(c,processor)
            else:prompt,stats=r['prompt'],{'legacy_validation_prompt_unchanged':True}
            answer=r['completion'][0]['content']
            prefix=processor.apply_chat_template(prompt,tokenize=False,add_generation_prompt=True,enable_thinking=False)
            n=len(tok(prefix,add_special_tokens=False)['input_ids'])+len(tok(answer,add_special_tokens=False)['input_ids'])+1
            assert n<=MAX_LENGTH,(split,r['id'],n)
            if split=='train':assert r['requested_char_bounds'][0]<=len(answer)<=r['requested_char_bounds'][1],(r['id'],len(answer))
            if split=='train':
                assert isinstance(r.get('assertion_trace'),list) and r['assertion_trace'],r['id']
                for trace in r['assertion_trace']:
                    assert trace['source']==c['facts'][trace['source_fact_index']],(r['id'],'stale trace')
                    assert trace['rendered'] in answer,(r['id'],'target evidence absent',trace['rendered'])
            numeric_source=' '.join(c['facts'])
            if c['genre'] in ('cover_letter','speech'):numeric_source+=' '+c['topic']
            new_nums=set(re.findall(r'\d+',answer))-set(re.findall(r'\d+',numeric_source))
            if new_nums and split=='train':warnings.append({'id':r['id'],'new_numeric_tokens':sorted(new_nums)})
            r['prompt']=prompt
            if split=='train':
                r['final_profile']={'profile':PROFILE_NAME,'parent_row_sha256':before,'answer_sha256':digest(answer),
                    **stats,'total_tokens':n,'target_changed':False if r['id'] not in {a['id'] for a in additions} else None,
                    'independent_human_review':False,'external_api_used':False}
            lengths[split].append(n);example_counts[(split,len(prompt))]+=1
        rewritten.append(records)
        if split=='train':save_lines(DATA/f'{split}.jsonl',records)
        else:(DATA/f'{split}.jsonl').write_bytes((PARENT/f'{split}.jsonl').read_bytes())
    answers=[{''.join(r['completion'][0]['content'].split()) for r in rs} for rs in rewritten]
    assert not (answers[0]&answers[1] or answers[0]&answers[2] or answers[1]&answers[2]),'split answer overlap'
    training_facts={digest(source(r)['facts']) for r in kept}
    assert not training_facts&{digest(c['facts']) for c in evals},'holdout leakage'
    assert not warnings,warnings
    frozen_eval=[]
    for c in evals:
        prompt,stats=messages(c,processor)
        frozen_eval.append({**c,'prompt':prompt,'prompt_stats':stats})
    save(OUT/'evaluation_inputs.json',frozen_eval)
    save(DATA/'replacement_ledger.json',{'removed':[{'id':r['id'],'family':r['scenario_family_id'],'row_sha256':digest(r)} for r in removed],
        'added':[a['id'] for a in additions],'reason':'Retain other variants of existing families; add 50 distinct role/state/scope families.'})
    manifest={'status':'frozen_pretraining','count':2000,'categories':dict(Counter(r['category'] for r in kept)),
        'parent_train_sha256':sha(PARENT/'train.jsonl'),'target_answers_retained':1900,'new_primary_authored_examples':100,
        'primary_authored_families':50,'automatic_evidence_checks':'all rows, all existing trace assertions; no independent semantic approval',
        'independent_human_review':False,'max_sequence_length':MAX_LENGTH,'profile':PROFILE_NAME,
        'valid_test_policy':'Byte-identical to parent, including legacy prompts. Loss is on unchanged legacy validation; final quality uses separately frozen same-profile holdout.',
        'files':{s:{'sha256':sha(DATA/f'{s}.jsonl'),'count':len(rs),'min_tokens':min(lengths[s]),'max_tokens':max(lengths[s]),
            'mean_tokens':round(sum(lengths[s])/len(lengths[s]),1)} for s,rs in zip(('train','valid','test'),rewritten)},
        'source_code':{name:sha(ROOT/name) for name in ('final_release.py','final_eval_cases.py','final_training_examples.py','final_writing_profiles.py','train_qwen35.py')},
        'protocol_sha256':sha(OUT/'protocol.json'),'evaluation_inputs_sha256':sha(OUT/'evaluation_inputs.json'),
        'prompt_message_counts':{str(k):v for k,v in example_counts.items()},'external_api_used':False}
    save(DATA/'manifest.json',manifest)
    print(json.dumps(manifest,ensure_ascii=False,indent=2),flush=True)

def train():
    import train_qwen35 as trainer
    import sys
    manifest=json.loads((DATA/'manifest.json').read_text(encoding='utf-8'))
    for s in ('train','valid','test'):assert sha(DATA/f'{s}.jsonl')==manifest['files'][s]['sha256']
    state=OUT/'training_state.json'
    if state.exists():raise RuntimeError('Final training already started; inspect state instead of launching another run.')
    previous=set((ROOT/'outputs').glob('qwen35_fresh_*'))
    save(state,{'status':'running','fresh_from_base':True,'max_length':MAX_LENGTH,
        'manifest_sha256':sha(DATA/'manifest.json'),'started_utc':datetime.now(timezone.utc).isoformat()})
    trainer.MAX_LENGTH=MAX_LENGTH
    sys.argv=['train_qwen35.py','--data-dir',str(DATA),'--epochs','1']
    try:trainer.main()
    except BaseException as exc:
        save(state,{'status':'failed','error':str(exc),'no_completed_run':True});raise
    created=set((ROOT/'outputs').glob('qwen35_fresh_*'))-previous
    assert len(created)==1,created
    run=created.pop()
    save(state,{'status':'completed','run':str(run),'adapter':str(run/'adapter'),
        'adapter_sha256':sha(run/'adapter/adapter_model.safetensors'),'metrics_sha256':sha(run/'metrics.json'),
        'max_sequence_length':MAX_LENGTH,'wrapper_sha256':sha(Path(__file__)),
        'manifest_sha256':sha(DATA/'manifest.json'),'completed_utc':datetime.now(timezone.utc).isoformat()})
    print('FINAL_TRAINING_COMPLETED',str(run),flush=True)

def infer():
    import time
    import torch
    from peft import PeftModel
    from transformers import AutoProcessor,Qwen3_5ForConditionalGeneration
    from writing_prompts import finish_text
    protocol=json.loads((OUT/'protocol.json').read_text(encoding='utf-8'))
    state=json.loads((OUT/'training_state.json').read_text(encoding='utf-8'))
    assert state['status']=='completed'
    adapters={**ADAPTERS,'Final2000':Path(state['adapter'])}
    cases=json.loads((OUT/'evaluation_inputs.json').read_text(encoding='utf-8'))
    processor=AutoProcessor.from_pretrained(MODEL,local_files_only=True)
    tok=processor.tokenizer
    if tok.pad_token_id is None:tok.pad_token=tok.eos_token
    base=Qwen3_5ForConditionalGeneration.from_pretrained(MODEL,local_files_only=True,
        dtype=torch.bfloat16,device_map={'':0},attn_implementation='eager')
    model=None
    record_path=OUT/'generations.jsonl'
    records=lines(record_path) if record_path.exists() else []
    for name,adapter in adapters.items():
        if model is None:model=PeftModel.from_pretrained(base,str(adapter),adapter_name=name,is_trainable=False)
        else:model.load_adapter(str(adapter),adapter_name=name,is_trainable=False)
        model.set_adapter(name);model.eval()
        eos=model.generation_config.eos_token_id
        eos=list(eos) if isinstance(eos,(tuple,list)) else ([eos] if eos is not None else [])
        eos=list(set(eos+[tok.eos_token_id,tok.get_vocab()['<|im_end|>']]))
        for c in cases:
            if any(r['model']==name and r['case_id']==c['id'] for r in records):continue
            prefix=processor.apply_chat_template(c['prompt'],tokenize=False,add_generation_prompt=True,enable_thinking=False)
            inputs=tok(prefix,add_special_tokens=False,return_tensors='pt').to('cuda:0')
            started=time.monotonic()
            with torch.inference_mode():
                result=model.generate(**inputs,max_new_tokens=768,do_sample=False,use_cache=True,
                    repetition_penalty=1.0,no_repeat_ngram_size=0,eos_token_id=eos,pad_token_id=tok.pad_token_id)
            generated=result[0,inputs['input_ids'].shape[1]:].tolist()
            raw=tok.decode(generated,skip_special_tokens=True).strip()
            text=finish_text(raw,{'report':'보고서','cover_letter':'자기소개서','speech':'발표문','free_writing':'자유 글쓰기'}[c['genre']])
            record={'model':name,'case_id':c['id'],'genre':c['genre'],'text':text,'raw_text':raw,
                'chars':len(text),'in_bounds':c['bounds'][0]<=len(text)<=c['bounds'][1],
                'ended_with_eos':bool(generated and generated[-1] in eos),'tokens':len(generated),
                'seconds':round(time.monotonic()-started,2),'adapter_sha256':sha(adapter/'adapter_model.safetensors'),
                'input_sha256':digest(c['prompt']),'profile':PROFILE_NAME}
            records.append(record)
            with record_path.open('a',encoding='utf-8') as f:f.write(json.dumps(record,ensure_ascii=False)+'\n')
            print(name,c['id'],record['chars'],'EOS',record['ended_with_eos'],flush=True)
    assert len(records)==160
    print('INFERENCE_COMPLETED',len(records),flush=True)

def blind():
    assert not (OUT/'blind_key.json').exists(),'Already blinded'
    rs=lines(OUT/'generations.jsonl');assert len(rs)==160
    rng=random.Random(20261119);rng.shuffle(rs)
    save(OUT/'blind_key.json',{f'O{i:03d}':{'model':r['model'],'case_id':r['case_id']} for i,r in enumerate(rs,1)})
    cs={c['id']:c for c in json.loads((OUT/'cases.json').read_text(encoding='utf-8'))}
    save(OUT/'blind_outputs.json',[{'output_id':f'O{i:03d}','case':cs[r['case_id']],'text':r['text'],
        'chars':r['chars'],'in_bounds':r['in_bounds'],'ended_with_eos':r['ended_with_eos']} for i,r in enumerate(rs,1)])

if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('action',choices=['prepare','train','infer','blind'])
    globals()[p.parse_args().action]()
