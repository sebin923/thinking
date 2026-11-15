import { useEffect, useState } from 'react';
import { adminRequest } from '../../api/trainingAdmin';
import { Pager } from './TrainingManager';
import './TrainingAdmin.css';

const kindLabel = {
  draft: 'AI 초안',
  feedback: 'AI 피드백',
};

export default function RatingsManager({ token, onSessionExpired }) {
  const [filters, setFilters] = useState({ kind: '', stars: '' }), [offset, setOffset] = useState(0), [reload, setReload] = useState(0);
  const [data, setData] = useState(null), [selected, setSelected] = useState(null), [detail, setDetail] = useState(null), [error, setError] = useState(''), [loading, setLoading] = useState(false);
  function fail(e) { setError(e.message); if (e.status === 401) onSessionExpired?.(); }
  useEffect(() => {
    let active = true; setLoading(true); setError(''); setSelected(null); setData(null);
    const q = new URLSearchParams({ ...Object.fromEntries(Object.entries(filters).filter(([, v]) => v !== '')), offset });
    adminRequest(token, `/api/admin/ratings?${q}`).then(r => { if (active) setData(r); }).catch(e => { if (active) fail(e); }).finally(() => { if (active) setLoading(false); });
    return () => { active = false; };
  }, [token, filters, offset, reload]);
  useEffect(() => {
    let active = true; setDetail(null);
    if (selected) adminRequest(token, `/api/admin/ratings/${encodeURIComponent(selected)}`).then(r => { if (active) setDetail(r); }).catch(e => { if (active) fail(e); });
    return () => { active = false; };
  }, [token, selected]);

  function filter(key, value) { setFilters({ ...filters, [key]: value }); setOffset(0); }
  return <div className="ta-admin"><h2>별점·사용자 평가</h2>
    <div className="ta-tools"><label>
      평가 종류{" "}
      <select
        value={filters.kind}
        onChange={e => filter('kind', e.target.value)}
      >
        <option value="">전체</option>
        <option value="draft">AI 초안</option>
        <option value="feedback">AI 피드백</option>
      </select>
    </label>
      <label>별점 <select value={filters.stars} onChange={e => filter('stars', e.target.value)}><option value="">전체</option>{[1, 2, 3, 4, 5].map(s => <option key={s} value={s}>{s}점</option>)}</select></label><button disabled={loading} onClick={() => setReload(x => x + 1)}>새로고침</button></div>
    {error && <p role="alert" className="ta-error">{error}</p>}{loading && <p role="status">불러오는 중…</p>}
    {data && <><div className="ta-stats"><article><span>조건에 맞는 평가</span><strong>{data.total}건</strong></article><article><span>평균 별점</span><strong>{data.average ?? '-'} / 5</strong></article><article><span>낮은 평가 (1~2점)</span><strong>{data.distribution['1'] + data.distribution['2']}건</strong></article></div>
      <div className="ta-bars" aria-label="현재 검색 조건의 별점 분포">{[5, 4, 3, 2, 1].map(s => <div key={s}><span>{s}점</span><meter min="0" max={Math.max(data.total, 1)} value={data.distribution[s]} aria-label={`${s}점 ${data.distribution[s]}건`} /><span>{data.distribution[s]}건</span></div>)}</div>
      <div className="ta-table"><table><thead><tr><th>일시</th><th>평가 종류</th><th>별점</th><th>의견</th><th>상세</th></tr></thead><tbody>{data.items.map(r => <tr key={r.id}><td>{r.created_at}</td><td>{kindLabel[r.kind] || r.kind}</td><td>{r.rating} / 5</td><td>{r.comment || '의견 없음'}</td><td><button onClick={() => setSelected(r.id)}>보기</button></td></tr>)}</tbody></table></div>{!data.total && <p>조건에 맞는 평가가 없습니다.</p>}<Pager offset={offset} size={20} next={offset + data.items.length < data.total} disabled={loading} onChange={setOffset} /></>}
    {selected && <article className="ta-card"><div className="ta-tools"><h3>평가 상세</h3><button onClick={() => setSelected(null)}>닫기</button></div>{detail ? <><p>별점 {detail.rating} / 5 · 문서 ID {detail.document_id || '-'}</p><h4>사용자 의견</h4><pre>{detail.comment || '의견 없음'}</pre><h4>요청 원문</h4><pre>{detail.request_text || '저장된 내용 없음'}</pre><h4>평가한 AI 결과</h4><pre>{detail.result_text || '저장된 내용 없음'}</pre><p>기존 수집 코드에서 원문·결과는 최대 2,000자까지만 저장됩니다. 이 평가는 학습 동의를 뜻하지 않습니다.</p></> : <p>상세 조회 중…</p>}</article>}
  </div>;
}
