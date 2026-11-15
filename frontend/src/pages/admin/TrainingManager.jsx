import {useEffect, useState} from 'react';
import {adminRequest, downloadDataset} from '../../api/trainingAdmin';
import './TrainingAdmin.css';
const labels = {pending:'검토 대기', approved:'승인', rejected:'제외', withdrawn:'동의 철회'};
const checks = {facts_checked:'주체·시간·부정 표현과 사실을 확인했습니다.', quality_checked:'과제 형식·분량·맞춤법·반복을 확인했습니다.', privacy_checked:'이름·연락처 등 개인정보가 없습니다.', author_confirmed:'작성자 본인의 글과 이용 권한을 확인했습니다.', context_confirmed:'입력 자료만으로 이 글을 작성할 수 있습니다.'};
const when = value => value ? new Date(value).toLocaleString('ko-KR') : '-';
export default function TrainingManager({token, onSessionExpired}) {
  const [view,setView]=useState('candidates'), [status,setStatus]=useState('pending'), [offset,setOffset]=useState(0);
  const [rows,setRows]=useState([]), [selected,setSelected]=useState(null), [history,setHistory]=useState([]);
  const [form,setForm]=useState({}), [real,setReal]=useState(false), [loading,setLoading]=useState(false), [busy,setBusy]=useState(false);
  const [error,setError]=useState(''), [notice,setNotice]=useState(''), [reload,setReload]=useState(0);
  function fail(e){setError(e.message); if(e.status===401) onSessionExpired?.();}
  useEffect(()=>{
    let active=true; setLoading(true);setError('');setRows([]);setSelected(null);
    const path=view==='candidates'?`/api/training/candidates?status=${status}&offset=${offset}`:`/api/training/${view}`;
    adminRequest(token,path).then(data=>{if(active)setRows(data);}).catch(e=>{if(active)fail(e);}).finally(()=>{if(active)setLoading(false);});
    return ()=>{active=false;};
  },[token,view,status,offset,reload]);
  useEffect(()=>{
    let active=true;setHistory([]);
    if(selected) adminRequest(token,`/api/training/candidates/${selected.id}/reviews`).then(data=>{if(active)setHistory(data);}).catch(e=>{if(active)fail(e);});
    return ()=>{active=false;};
  },[token,selected]);
  async function act(fn){setBusy(true);setError('');setNotice('');try{await fn();}catch(e){fail(e);}finally{setBusy(false);}}
  function select(row){setSelected(row);setForm({note:'',training_context:row.training_context||'',synthetic:row.synthetic});setReal(false);}
  async function review(decision){
    if(!window.confirm(decision==='approved'?'이 글을 학습 후보로 승인할까요?':'이 글을 학습 대상에서 제외할까요?'))return;
    await act(async()=>{await adminRequest(token,`/api/training/candidates/${selected.id}/review`,{...form,decision,expected_revision:selected.revision});setNotice('검토 결과를 저장했습니다.');setReload(x=>x+1);});
  }
  const approvable=selected?.consent && !form.synthetic && real && Object.keys(checks).every(k=>form[k]) && (selected?.source?.type_label!=='자기소개서'||form.training_context?.trim());
  return <div className="ta-admin">
    <h2>학습 데이터 관리</h2>
    <div className="ta-tools">{[['candidates','후보 검토'],['exports','데이터셋'],['runs','학습 실험 기록']].map(([key,label])=><button key={key} disabled={busy} aria-pressed={view===key} onClick={()=>{setView(key);setOffset(0);setNotice('');}}>{label}</button>)}<button disabled={busy||loading} onClick={()=>setReload(x=>x+1)}>새로고침</button></div>
    {error&&<p role="alert" className="ta-error">{error}</p>}{notice&&<p role="status">{notice}</p>}
    {view==='candidates'&&<label>검토 상태 <select value={status} disabled={busy} onChange={e=>{setStatus(e.target.value);setOffset(0);}}>{Object.entries(labels).map(([k,v])=><option key={k} value={k}>{v}</option>)}</select></label>}
    {loading?<p role="status">불러오는 중…</p>:<>
      {view==='candidates'&&<><div className="ta-table"><table><thead><tr><th>ID</th><th>유형·단원</th><th>AI 점수</th><th>제출일</th><th>검토</th></tr></thead><tbody>{rows.map(row=><tr key={row.id}><td>{row.id}</td><td>{row.source?.type_label||'-'} · {row.source?.unit_title||'철회된 글'}</td><td>{row.score}</td><td>{when(row.created_at)}</td><td><button disabled={busy} onClick={()=>select(row)}>상세 보기</button></td></tr>)}</tbody></table></div><Pager offset={offset} size={50} next={rows.length===50} disabled={busy} onChange={setOffset}/></>}
      {view==='exports'&&<><button disabled={busy} onClick={()=>act(async()=>{const data=await adminRequest(token,'/api/training/exports',{});setNotice(`데이터셋 생성: 학습 ${data.counts.train} / 검증 ${data.counts.valid} / 테스트 ${data.counts.test}건. 실제 학습은 실행하지 않았습니다.`);setReload(x=>x+1);})}>승인 글로 데이터셋 만들기</button><p>최근 100개를 표시합니다.</p>{rows.map(row=><article className="ta-card" key={row.id}><strong>{row.id}</strong><p>{when(row.created_at)} · 학습 {row.manifest.counts?.train||0} / 검증 {row.manifest.counts?.valid||0} / 테스트 {row.manifest.counts?.test||0}</p><p>{row.revoked?'무효화됨':!row.manifest.all_splits_nonempty?'분할 부족 — 학습 준비 전':'내보내기 완료 — 별도 품질 검증 필요'}</p><button disabled={busy||row.revoked} onClick={()=>act(()=>downloadDataset(token,row.id))}>ZIP 다운로드</button></article>)}</>}
      {view==='runs'&&<><p>최근 100개 실험 기록입니다.</p>{rows.map(row=><article className="ta-card" key={row.id}><strong>실험 #{row.id} · {when(row.created_at)}</strong><pre>{JSON.stringify(row.details,null,2)}</pre></article>)}</>}
      {!rows.length&&<p>표시할 항목이 없습니다.</p>}
    </>}
    {selected&&view==='candidates'&&<article className="ta-card ta-detail"><div className="ta-tools"><h3>후보 #{selected.id} · {labels[selected.status]}</h3><button disabled={busy} onClick={()=>setSelected(null)}>상세 닫기</button></div>
      <p>동의: {selected.consent?'있음':'철회'} · AI 점수: {selected.score} · 버전: {selected.revision}</p>
      <h4>과제</h4><pre>{selected.source?.task||'-'}</pre><h4>제공 자료</h4><pre>{selected.source?.material||'-'}</pre><h4>채점 기준</h4><ul>{selected.source?.rules?.map((r,i)=><li key={i}>{r}</li>)}</ul><h4>제출 글</h4><pre>{selected.answer||'철회로 삭제된 글입니다.'}</pre>
      <details><summary>AI 채점 상세</summary><pre>{JSON.stringify(selected.assessment,null,2)}</pre></details>
      {selected.status!=='withdrawn'&&<fieldset disabled={busy}><legend>관리자 검토</legend>{Object.entries(checks).map(([k,label])=><label className="ta-check" key={k}><input type="checkbox" checked={!!form[k]} onChange={e=>setForm({...form,[k]:e.target.checked})}/>{label}</label>)}
        <label className="ta-check"><input type="checkbox" checked={!!form.synthetic} onChange={e=>setForm({...form,synthetic:e.target.checked})}/>AI 작성·합성·데모 테스트 글입니다. (승인 제외)</label>
        <label className="ta-check"><input type="checkbox" checked={real} onChange={e=>setReal(e.target.checked)}/>실제 작성자가 제출한 글임을 확인했습니다.</label>
        <label className="ta-field">작성자가 확인한 사실 자료 (자기소개서 필수)<textarea maxLength={6000} value={form.training_context||''} onChange={e=>setForm({...form,training_context:e.target.value})}/></label>
        <label className="ta-field">검토 메모 (선택)<textarea maxLength={1000} value={form.note||''} onChange={e=>setForm({...form,note:e.target.value})}/></label>
        <div className="ta-tools"><button disabled={!approvable||busy} onClick={()=>review('approved')}>승인</button><button disabled={busy} onClick={()=>review('rejected')}>제외</button></div>
        <p>승인·제외를 변경하면 이 글이 들어간 기존 데이터셋이 무효화됩니다. 이미 다운로드한 파일은 별도로 폐기해야 합니다.</p>
      </fieldset>}
      <h4>검토 이력</h4>{history.length?history.map((r,i)=><p key={i}>{when(r.at)} · {labels[r.event.decision]||r.event.action||'검토'} {r.event.note&&`· ${r.event.note}`}</p>):<p>검토 이력이 없습니다.</p>}
    </article>}
  </div>;
}
export function Pager({offset,size,next,disabled,onChange}){return <div className="ta-tools"><button disabled={disabled||offset===0} onClick={()=>onChange(Math.max(0,offset-size))}>이전</button><span>{Math.floor(offset/size)+1}페이지</span><button disabled={disabled||!next} onClick={()=>onChange(offset+size)}>다음</button></div>;}
