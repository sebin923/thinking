"""CLOVA 채점 결과를 검토 후보로 수집하고 승인 데이터만 내보낸다."""
import hashlib
import io
import json
import logging
import re
import unicodedata
import uuid
import zipfile
from sqlalchemy import text
from sqlalchemy.exc import SQLAlchemyError, IntegrityError
from training_models import TrainingCandidate as Candidate, TrainingReview as Review
from training_models import TrainingSplit as Split, TrainingExport as Export

log = logging.getLogger(__name__)
POLICY = 'common-training-v1'
GENRES = {'보고서', '자기소개서', '발표문', '자유 글쓰기'}

def normalized(value):
    return ' '.join(unicodedata.normalize('NFC', value).split())

def digest(value):
    return hashlib.sha256(json.dumps(value, ensure_ascii=False, sort_keys=True).encode()).hexdigest()

def serialize(value):
    return json.dumps(value, ensure_ascii=False, sort_keys=True)

def lock(db):
    # 승인/철회/내보내기 동시 요청 사이에서 스냅샷과 분할 배정을 직렬화한다.
    if db.bind.dialect.name == 'postgresql':
        db.execute(text('SELECT pg_advisory_xact_lock(742019311)'))

def collect(db, user_id, data, result):
    if not data.training_consent:
        return {'status': 'not_consented'}
    if result['score'] < 90 or result['on_task'] is not True or data.type_label not in GENRES:
        return {'status': 'not_eligible'}
    source = data.model_dump(include={'unit_id', 'type_label', 'unit_title', 'rules', 'task', 'material'})
    key = digest({'source': source, 'answer': normalized(data.text)})
    try:
        existing = db.query(Candidate).filter_by(user_id=user_id, sample_hash=key).first()
        if existing:
            return {'status': 'duplicate', 'id': existing.id, 'review_status': existing.status}
        item = Candidate(user_id=user_id, sample_hash=key, source=source, answer=data.text.strip(),
                         assessment=result, score=result['score'], consent=True)
        db.add(item)
        db.commit()
        return {'status': 'pending', 'id': item.id}
    except IntegrityError:
        db.rollback()
        # 중복 요청 경쟁도 채점을 실패시키지 않는다.
        return {'status': 'duplicate'}
    except SQLAlchemyError:
        db.rollback()
        log.warning('Training candidate persistence failed; grading result preserved')
        return {'status': 'save_failed'}

def details(item):
    return {k: getattr(item, k) for k in ('id', 'user_id', 'source', 'answer', 'assessment',
            'score', 'status', 'revision', 'consent', 'synthetic', 'training_context', 'created_at')}

def pii(value):
    return bool(re.search(r'[\w.+-]+@[\w.-]+\.[A-Za-z]{2,}|(?<!\d)01[016789][- ]?\d{3,4}[- ]?\d{4}(?!\d)|(?<!\d)\d{6}[- ]?[1-8]\d{6}(?!\d)', value))

def revoke_exports(db, candidate_id):
    for export in db.query(Export).filter_by(revoked=False):
        if any(x['id'] == candidate_id for x in export.manifest['members']):
            export.revoked = True
            export.payload = {}  # 개인 글 스냅샷도 지운다.

def sample(item):
    source = item.source
    context = item.training_context.strip() or source['material'].strip()
    return {
        'id': digest({'candidate': item.id, 'revision': item.revision}),
        'prompt': [
            {'role': 'system', 'content': '너는 한국어 글쓰기 도우미다. 제공한 사실과 생각만 사용하고 주체, 시간, 부정 표현을 유지한다. 근거 없는 경험이나 성과를 만들지 않고 요청에 맞는 완성된 본문만 작성한다.'},
            {'role': 'user', 'content': f"글 유형: {source['type_label']}\n요청: {source['task']}\n제공한 자료와 사실:\n{context}\n글쓰기 기준:\n" + '\n'.join(source['rules'])},
        ],
        'completion': [{'role': 'assistant', 'content': item.answer}],
    }

def export_dataset(db, actor_id):
    lock(db)
    candidates = db.query(Candidate).filter_by(status='approved', consent=True, synthetic=False).order_by(Candidate.id).all()
    if len(candidates) > 10000:
        raise ValueError('한 번에 10,000건까지 내보낼 수 있습니다.')
    payload = {name: [] for name in ('train', 'valid', 'test')}
    members, seen, excluded = [], set(), 0
    for item in candidates:
        row = sample(item)
        if pii(serialize(row)):
            excluded += 1
            continue
        answer_key = 'answer:' + digest(normalized(item.answer))
        if answer_key in seen:
            excluded += 1
            continue
        # 같은 과제/자료를 공유하는 글은 한 분할에만 둔다. 제목/계정 차이로 분리하지 않는다.
        group_key = 'group:' + digest([normalized(item.source['task']), normalized(item.source['material'])])
        group = db.get(Split, group_key)
        answer = db.get(Split, answer_key)
        proposed = group.split if group else ('train' if int(group_key[6:14], 16) % 100 < 80 else ('valid' if int(group_key[6:14], 16) % 100 < 90 else 'test'))
        if answer and answer.split != proposed:
            excluded += 1
            continue
        if not group:
            db.add(Split(key=group_key, split=proposed))
        if not answer:
            db.add(Split(key=answer_key, split=proposed))
        db.flush()
        seen.add(answer_key)
        payload[proposed].append(row)
        members.append({'id': item.id, 'revision': item.revision, 'split': proposed})
    if not members:
        raise ValueError('내보낼 승인 데이터가 없습니다.')
    files = {name + '.jsonl': ''.join(serialize(row) + '\n' for row in rows) for name, rows in payload.items()}
    export_id = uuid.uuid4().hex
    manifest = {
        'export_id': export_id, 'policy': POLICY, 'members': members,
        'counts': {name: len(rows) for name, rows in payload.items()},
        'sha256': {name: hashlib.sha256(content.encode()).hexdigest() for name, content in files.items()},
        'excluded_count': excluded, 'all_splits_nonempty': all(payload.values()),
        'quality_approved': False,
        'note': '관리자 검토 데이터. 분할이 비어 있거나 표본이 적으면 추가 수집하세요. 같은 export의 test를 고정해 모델을 비교하세요.',
    }
    db.add(Export(id=export_id, created_by=actor_id, manifest=manifest, payload=files))
    db.commit()
    return manifest

def validate_export(db, export):
    if export.revoked:
        raise ValueError('철회되거나 변경된 글이 있어 무효화된 데이터셋입니다. 새로 내보내세요.')
    for member in export.manifest['members']:
        item = db.get(Candidate, member['id'])
        if not item or not item.consent or item.status != 'approved' or item.synthetic or item.revision != member['revision']:
            export.revoked = True
            export.payload = {}
            db.commit()
            raise ValueError('후보 상태가 변경되어 이 데이터셋을 무효화했습니다.')

def zip_export(export):
    stream = io.BytesIO()
    with zipfile.ZipFile(stream, 'w', zipfile.ZIP_DEFLATED) as archive:
        for name, contents in export.payload.items():
            archive.writestr(name, contents)
        # 다운로드 파일에는 내부 사용자/후보 ID를 넣지 않는다.
        public_manifest = {k: v for k, v in export.manifest.items() if k != 'members'}
        archive.writestr('manifest.json', serialize(public_manifest))
    return stream.getvalue()
