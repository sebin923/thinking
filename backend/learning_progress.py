"""회원별 글쓰기 연습 진도. revision으로 다른 탭/기기의 덮어쓰기를 방지한다."""
from copy import deepcopy
from datetime import datetime, timezone
import json
from sqlalchemy import Column, Integer, ForeignKey, JSON
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.dialects.sqlite import insert as sqlite_insert
from sqlalchemy.orm.attributes import flag_modified
from database import Base

class LearningProgress(Base):
    __tablename__ = 'learning_progress'
    user_id = Column(Integer, ForeignKey('users.user_id', ondelete='CASCADE'), primary_key=True)
    revision = Column(Integer, nullable=False, default=0)
    payload = Column(JSON, nullable=False, default=lambda: {'units': {}, 'wrong': {}})
    legacy_imported = Column(Integer, nullable=False, default=0)

def row_for(db, user_id):
    values = dict(user_id=user_id, revision=0, payload={'units': {}, 'wrong': {}}, legacy_imported=0)
    dialect = db.bind.dialect.name
    if dialect in ('postgresql','sqlite'):
        insert = pg_insert if dialect == 'postgresql' else sqlite_insert
        db.execute(insert(LearningProgress).values(**values).on_conflict_do_nothing(index_elements=['user_id']))
    else:
        raise RuntimeError('지원되는 진도 DB는 PostgreSQL/SQLite입니다.')
    return db.query(LearningProgress).filter_by(user_id=user_id).populate_existing().with_for_update().one()

def snapshot(row):
    return {'progress': deepcopy(row.payload), 'revision': row.revision, 'legacy_imported': bool(row.legacy_imported)}

def assign(row, payload):
    row.payload = deepcopy(payload)
    flag_modified(row, 'payload')
    row.revision += 1

WRITING_FIELDS = ('writing','writingAttempts','writingBest','completed','completedAt','completionSource')

def validated(payload):
    if set(payload) != {'units','wrong'} or not all(isinstance(payload[k],dict) for k in ('units','wrong')):
        raise ValueError('진도 형식이 올바르지 않습니다.')
    if len(payload['units']) > 300 or len(payload['wrong']) > 2000:
        raise ValueError('진도 항목이 너무 많습니다.')
    if len(json.dumps(payload,ensure_ascii=False).encode()) > 2_000_000:
        raise ValueError('진도 데이터가 너무 큽니다.')
    for group in ('units','wrong'):
        for key,item in payload[group].items():
            if not isinstance(key,str) or len(key)>2000 or not isinstance(item,dict):
                raise ValueError('진도 항목 형식이 올바르지 않습니다.')
    for item in payload['units'].values():
        for field in ('attempts','writingAttempts','writingBest','lastScore','bestScore','total'):
            if field in item and (type(item[field]) is not int or not 0 <= item[field] <= 1_000_000):
                raise ValueError('점수·횟수는 유효한 정수여야 합니다.')
        for key in ('passed','completed'):
            if key in item and type(item[key]) is not bool:raise ValueError('완료 값은 참/거짓이어야 합니다.')
    for item in payload['wrong'].values():
        if 'resolved' in item and type(item['resolved']) is not bool:raise ValueError('오답 해결 값이 올바르지 않습니다.')
    return deepcopy(payload)

def update_progress(db,user_id,payload,expected_revision):
    payload=validated(payload)
    row=row_for(db,user_id)
    if row.revision!=expected_revision:raise ValueError('conflict')
    # AI 점수·글쓰기 완료는 일반 저장 요청으로 만들거나 지울 수 없다.
    for key,old in row.payload['units'].items():
        item=payload['units'].setdefault(key,{})
        for field in WRITING_FIELDS:
            if field in old:item[field]=deepcopy(old[field])
            else:item.pop(field,None)
        if old.get('passed'):item['passed']=True;item['passedAt']=old.get('passedAt')
    for key,item in payload['units'].items():
        if key not in row.payload['units']:
            for field in WRITING_FIELDS:item.pop(field,None)
    assign(row,payload);db.commit();return snapshot(row)

def import_legacy(db,user_id,payload,expected_revision):
    payload=validated(payload);row=row_for(db,user_id)
    if row.revision!=expected_revision:raise ValueError('conflict')
    if not row.legacy_imported:
        merged=deepcopy(row.payload)
        for key,item in payload['units'].items():
            if key not in merged['units']:
                item['completionSource']='legacy_browser'
                merged['units'][key]=item
        for key,item in payload['wrong'].items():merged['wrong'].setdefault(key,item)
        assign(row,merged);row.legacy_imported=1
    db.commit();return snapshot(row)

def record_writing(db,user_id,unit_id,text,result):
    row=row_for(db,user_id);progress=deepcopy(row.payload)
    old=progress['units'].get(unit_id,{})
    now=datetime.now(timezone.utc).isoformat()
    passed=result['score']>=result.get('pass_score',90)
    first_complete=passed and not old.get('completed',False)
    progress['units'][unit_id]={**old,'writing':{'text':text,'score':result['score'],'criteria':result['criteria'],
        'overallFeedback':result['overall_feedback'],'nextStep':result['next_step'],'onTask':result['on_task'],'scoredAt':now},
        'writingAttempts':int(old.get('writingAttempts',0))+1,
        'writingBest':max(old.get('writingBest',0),result['score']),
        'completed':bool(old.get('completed') or passed),
        'completedAt':old.get('completedAt') or (now if passed else None),
        'completionSource':'server_grade' if passed else old.get('completionSource','server_grade')}
    assign(row,progress);db.commit()
    return {**snapshot(row),'first_complete':first_complete}
