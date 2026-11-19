"""Blind review packets, frozen ratings, reporting and conservative selection."""
from collections import defaultdict
from datetime import datetime,timezone
import argparse
import json
from pathlib import Path
import statistics
from final_release import ROOT,OUT,ADAPTERS,sha,digest,save,lines


def packets():
    for prefix in ('','regression_'):
        outputs=json.loads((OUT/f'{prefix}blind_outputs.json').read_text(encoding='utf-8'))
        grouped=defaultdict(list)
        for r in outputs:grouped[r['case']['id']].append(r)
        packet=[]
        for key,rs in sorted(grouped.items()):
            bytext=defaultdict(list)
            for r in rs:bytext[r['text']].append(r)
            packet.append({'case':{k:v for k,v in rs[0]['case'].items() if k not in ('prompt','messages')},
                'outputs':[{'output_ids':sorted(r['output_id'] for r in same),'text':text,
                    'chars':same[0]['chars'],'in_bounds':same[0]['in_bounds'],'ended_with_eos':same[0]['ended_with_eos']}
                    for text,same in sorted(bytext.items(),key=lambda kv:min(r['output_id'] for r in kv[1]))]})
        save(OUT/f'{prefix}review_packets.json',packet)
        print(prefix or 'fresh',len(packet),'cases',sum(len(r['outputs']) for r in packet),'unique outputs')


def freeze():
    if (OUT/'ratings_frozen.json').exists():raise RuntimeError('Ratings already frozen')
    paths=sorted((OUT/'ratings_batches').glob('*.json'));assert paths
    ratings={}
    for p in paths:
        for row in json.loads(p.read_text(encoding='utf-8')):
            for oid in row['output_ids']:
                assert oid not in ratings,oid
                ratings[oid]={k:row[k] for k in ('naturalness','faithfulness','nonrepetition','critical','reason')}
    expected=set()
    for prefix in ('','regression_'):
        outputs=json.loads((OUT/f'{prefix}blind_outputs.json').read_text(encoding='utf-8'))
        for r in outputs:expected.add(r['output_id'])
        bytext=defaultdict(list)
        for r in outputs:bytext[(r['case']['id'],r['text'])].append(r['output_id'])
        for ids in bytext.values():
            assert len({digest(ratings[x]) for x in ids})==1,('identical outputs rated differently',ids)
    assert set(ratings)==expected,(expected-set(ratings),set(ratings)-expected)
    for oid,r in ratings.items():
        assert all(isinstance(r[k],(int,float)) and 0<=r[k]<=10 for k in ('naturalness','faithfulness','nonrepetition'))
        assert type(r['critical']) is bool and r['reason'].strip()
    save(OUT/'ratings.json',ratings)
    save(OUT/'ratings_frozen.json',{'frozen_utc':datetime.now(timezone.utc).isoformat(),
        'ratings_sha256':sha(OUT/'ratings.json'),'count':len(ratings),'blind_keys_not_read_by_reviewer_before_freeze':True,
        'batches':{p.name:sha(p) for p in paths},'independent_human_review':False})
    print('Ratings frozen:',len(ratings))


def summarize():
    frozen=json.loads((OUT/'ratings_frozen.json').read_text(encoding='utf-8'))
    assert sha(OUT/'ratings.json')==frozen['ratings_sha256']
    ratings=json.loads((OUT/'ratings.json').read_text(encoding='utf-8'))
    from final_release import DATA
    manifest=json.loads((DATA/'manifest.json').read_text(encoding='utf-8'))
    assert sha(OUT/'protocol.json')==manifest['protocol_sha256']
    assert sha(OUT/'evaluation_inputs.json')==manifest['evaluation_inputs_sha256']
    inputs=json.loads((OUT/'evaluation_inputs.json').read_text(encoding='utf-8'))
    cs=json.loads((OUT/'cases.json').read_text(encoding='utf-8'))
    assert [{k:v for k,v in c.items() if k not in ('prompt','prompt_stats')} for c in inputs]==cs
    results={}
    for prefix in ('','regression_'):
        keys=json.loads((OUT/f'{prefix}blind_key.json').read_text(encoding='utf-8'))
        outputs={r['output_id']:r for r in json.loads((OUT/f'{prefix}blind_outputs.json').read_text(encoding='utf-8'))}
        groups=defaultdict(list)
        for oid,key in keys.items():groups[key['model']].append({**ratings[oid],**key,
            **{k:outputs[oid][k] for k in ('in_bounds','ended_with_eos')},'genre':outputs[oid]['case']['genre']})
        def stats(rs):
            return {'count':len(rs),'naturalness':statistics.mean(r['naturalness'] for r in rs),
                'faithfulness':statistics.mean(r['faithfulness'] for r in rs),
                'nonrepetition':statistics.mean(r['nonrepetition'] for r in rs),
                'critical_count':sum(r['critical'] for r in rs),
                'critical_cases':[{'id':r['case_id'],'reason':r['reason']} for r in rs if r['critical']],
                'in_bounds':sum(r['in_bounds'] for r in rs),'eos_complete':sum(r['ended_with_eos'] for r in rs)}
        results[prefix or 'fresh']={name:{**stats(rs),'by_genre':{g:stats([r for r in rs if r['genre']==g]) for g in sorted({r['genre'] for r in rs})}} for name,rs in groups.items()}
    protocol=json.loads((OUT/'protocol.json').read_text(encoding='utf-8'))
    gates={}
    baseline=results['fresh']['Ver3']
    for name,v in results['fresh'].items():
        gates[name]={'fresh_source_errors':v['critical_count']==0,'known_source_errors':results['regression_'][name]['critical_count']==0,
            'naturalness':v['naturalness']>=protocol['release_gate']['naturalness_min'],
            'length':v['in_bounds']/v['count']>=protocol['release_gate']['length_compliance_min'],
            'genre_naturalness':all(s['naturalness']>=protocol['release_gate']['per_genre_naturalness_min'] for s in v['by_genre'].values()),
            'genre_vs_ver3':all(s['naturalness']>=baseline['by_genre'][g]['naturalness'] for g,s in v['by_genre'].items()),
            'faithfulness_vs_ver3':v['faithfulness']>=baseline['faithfulness']}
    eligible=[k for k,v in gates.items() if all(v.values())]
    eligible.sort(key=lambda k:(-results['fresh'][k]['naturalness'],-results['fresh'][k]['in_bounds'],-results['fresh'][k]['nonrepetition'],k!='Ver3',k))
    selected=eligible[0] if eligible else None
    result={'status':'complete','fresh_case_count':40,'models':results['fresh'],'known_regressions':results['regression_'],
        'application_priority':json.loads((OUT/'application_priority.json').read_text(encoding='utf-8')),
        'gates':gates,'selected_candidate':selected,'eligible_candidates':eligible,
        'ratings_sha256':sha(OUT/'ratings.json'),'protocol_sha256':sha(OUT/'protocol.json'),
        'limitations':['AI primary-agent review; not independent human evaluation.',
            'Small synthetic holdout with related scenario types; no statistical superiority or universal quality guarantee.',
            'Data provenance and training histories differ; this is not an isolated experiment on dataset size.',
            'Both evaluated models use final profiles; 5000 and prior-balanced comparisons were deferred at user request. Results cannot be mixed with earlier default-prompt scores.']}
    save(OUT/'result.json',result)
    report=['생각한줄 최종 모델 평가','새 합성 40문항, 각 장르 10문항, 같은 최종 작성 지시, AI 자체 블라인드 평가.',
        '자연스러움 / 사실 보존 / 반복 방지: 10점 척도. 중요 오류는 원문 사건·주체·수량·부정·상태·조건의 변경 또는 핵심 의미 누락.',
        '']
    for name in (k for k in ('Ver3','Final2000','5000','Balanced2000') if k in result['models']):
        v=result['models'][name];known=result['known_regressions'][name]
        report.append(f'{name}: 자연스러움 {v["naturalness"]:.3f}, 사실 보존 {v["faithfulness"]:.3f}, 반복 방지 {v["nonrepetition"]:.3f}, 중요 오류 {v["critical_count"]}/40, 분량 {v["in_bounds"]}/40, 기존 사례 중요 오류 {known["critical_count"]}/15')
        report.extend(f'  {g}: 자연스러움 {s["naturalness"]:.3f}, 중요 오류 {s["critical_count"]}/{s["count"]}, 분량 {s["in_bounds"]}/{s["count"]}' for g,s in v['by_genre'].items())
        report.append('  통과 기준: '+json.dumps(gates[name],ensure_ascii=False))
    report.extend(['','선정 후보: '+str(selected),'통과 후보가 없으면 기존 서비스 선정을 유지합니다.','',*result['limitations']])
    (OUT/'report.txt').write_text('\n'.join(report),encoding='utf-8')
    print('\n'.join(report))


def select():
    result=json.loads((OUT/'result.json').read_text(encoding='utf-8'))
    path=ROOT/'model_selection.json'
    backup=OUT/'original_model_selection.json'
    if not backup.exists():backup.write_bytes(path.read_bytes())
    name=result['selected_candidate']
    if name:
        assert path.read_bytes()==backup.read_bytes(),'Service selection changed during evaluation; preserve it for inspection.'
        adapters=dict(ADAPTERS)
        state=json.loads((OUT/'training_state.json').read_text(encoding='utf-8'))
        adapters['Final2000']=Path(state['adapter'])
        adapter=adapters[name]
        actual_sha=sha(adapter/'adapter_model.safetensors')
        records=[r for r in lines(OUT/'generations.jsonl') if r['model']==name]
        assert len(records)==40 and all(r['adapter_sha256']==actual_sha for r in records),'Selected weights differ from evaluated weights'
        value={'adapter':str(adapter.relative_to(ROOT)).replace('\\','/'),
            'writing_profile':'final_20261119','quality_approved':False,
            'local_validation':'Passed preregistered 40-case and known-case gates; AI self-review only.',
            'selection_evidence':'outputs/final_release_20261119/result.json',
            'adapter_sha256':actual_sha}
        path.write_text(json.dumps(value,ensure_ascii=False,indent=2),encoding='utf-8')
    else:
        value=json.loads(backup.read_text(encoding='utf-8'))
        assert json.loads(path.read_text(encoding='utf-8'))==value,'Unexpected service change'
    save(OUT/'selection.json',{'selected_candidate':name,'applied_config':value,
        'config_sha256':sha(path),'previous_config_sha256':sha(backup),'selection_changed':bool(name),
        'reason':'All preregistered gates passed.' if name else 'No candidate passed every gate; preserved prior service selection.'})
    print('Selection saved:',name or 'prior service preserved')


if __name__=='__main__':
    parser=argparse.ArgumentParser();parser.add_argument('action',choices=['packets','freeze','summarize','select'])
    globals()[parser.parse_args().action]()
