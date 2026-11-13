"""관리자: 검토/내보내기/실험 기록. 사용자: 본인 후보 조회/동의 철회."""
from typing import Literal
from fastapi import APIRouter, Depends, HTTPException, Query, Response
from pydantic import BaseModel, Field, StrictBool
from sqlalchemy.orm import Session
from database import get_db
from routers.auth import get_current_user
from training_models import TrainingCandidate as Candidate, TrainingReview as Review
from training_models import TrainingExport as Export, TrainingRun as Run
import training_collection as svc

router = APIRouter(prefix='/api/training', tags=['training-data'])

def admin(user=Depends(get_current_user)):
    if user.role != 'admin' or getattr(user, 'status', 'active') != 'active':
        raise HTTPException(403, '관리자만 이용할 수 있습니다.')
    return user

def candidate(db, candidate_id):
    item = db.get(Candidate, candidate_id)
    if not item:
        raise HTTPException(404, '후보를 찾을 수 없습니다.')
    return item

class ReviewIn(BaseModel):
    expected_revision: int = Field(ge=1)
    decision: Literal['approved', 'rejected']
    facts_checked: StrictBool = False
    quality_checked: StrictBool = False
    privacy_checked: StrictBool = False
    author_confirmed: StrictBool = False
    context_confirmed: StrictBool = False
    synthetic: StrictBool = False
    training_context: str = Field('', max_length=6000)
    note: str = Field('', max_length=1000)

@router.get('/mine')
def mine(user=Depends(get_current_user), db: Session=Depends(get_db), offset: int=Query(0, ge=0)):
    rows = db.query(Candidate).filter_by(user_id=user.user_id).order_by(Candidate.id.desc()).offset(offset).limit(50).all()
    return [svc.details(row) for row in rows]

@router.post('/mine/{candidate_id}/withdraw')
def withdraw(candidate_id: int, user=Depends(get_current_user), db: Session=Depends(get_db)):
    svc.lock(db)
    item = candidate(db, candidate_id)
    if item.user_id != user.user_id:
        raise HTTPException(404, '후보를 찾을 수 없습니다.')
    if item.status != 'withdrawn':
        item.consent = False
        item.status = 'withdrawn'
        item.revision += 1
        item.source, item.answer, item.assessment, item.training_context = {}, '', {}, ''
        # 관리자 메모에도 원문이 인용될 수 있어 철회 시 검토 메모를 지운다.
        db.query(Review).filter_by(candidate_id=item.id).delete()
        db.add(Review(candidate_id=item.id, actor_id=user.user_id, event={'action': 'withdrawn'}))
        svc.revoke_exports(db, item.id)
        db.commit()
    return {'status': 'withdrawn', 'note': '서버 보관 후보와 내보내기 사본을 철회했습니다. 이미 다운로드한 파일/학습한 모델은 별도로 처리해야 합니다.'}

@router.get('/candidates')
def candidates(status: Literal['pending','approved','rejected','withdrawn']='pending', offset: int=Query(0, ge=0), user=Depends(admin), db: Session=Depends(get_db)):
    return [svc.details(row) for row in db.query(Candidate).filter_by(status=status).order_by(Candidate.id).offset(offset).limit(50)]

@router.get('/candidates/{candidate_id}/reviews')
def reviews(candidate_id: int, user=Depends(admin), db: Session=Depends(get_db)):
    candidate(db, candidate_id)
    return [{'event': row.event, 'at': row.created_at, 'actor_id': row.actor_id} for row in db.query(Review).filter_by(candidate_id=candidate_id).order_by(Review.id)]

@router.post('/candidates/{candidate_id}/review')
def review(candidate_id: int, body: ReviewIn, user=Depends(admin), db: Session=Depends(get_db)):
    svc.lock(db)
    item = candidate(db, candidate_id)
    if not item.consent or item.status == 'withdrawn':
        raise HTTPException(409, '철회된 후보입니다.')
    if item.revision != body.expected_revision:
        raise HTTPException(409, '후보가 변경되었습니다. 다시 조회하세요.')
    if body.decision == 'approved':
        if not all((body.facts_checked, body.quality_checked, body.privacy_checked, body.author_confirmed, body.context_confirmed)) or body.synthetic:
            raise HTTPException(422, '사실·문장·개인정보·작성자·입력 근거 확인이 모두 필요하며 합성 글은 승인할 수 없습니다.')
        context = body.training_context.strip() or item.source['material'].strip()
        if not context or (item.source['type_label'] == '자기소개서' and not body.training_context.strip()):
            raise HTTPException(422, '작성자가 확인한 사실 자료를 training_context에 넣으세요. 자기소개서 문항만으로는 승인할 수 없습니다.')
        if svc.pii(context + item.answer + svc.serialize(item.source)):
            raise HTTPException(422, '연락처 등 개인정보 패턴이 있습니다. 비식별화한 글로 다시 제출하세요.')
    svc.revoke_exports(db, item.id)
    item.status, item.synthetic, item.training_context = body.decision, body.synthetic, body.training_context.strip()
    item.revision += 1
    db.add(Review(candidate_id=item.id, actor_id=user.user_id, event={**body.model_dump(exclude={'training_context'}), 'revision': item.revision}))
    db.commit()
    return svc.details(item)

@router.post('/exports')
def create_export(user=Depends(admin), db: Session=Depends(get_db)):
    try:
        return svc.export_dataset(db, user.user_id)
    except ValueError as exc:
        db.rollback()
        raise HTTPException(409, str(exc)) from exc

@router.get('/exports')
def list_exports(user=Depends(admin), db: Session=Depends(get_db)):
    return [{'id': row.id, 'manifest': row.manifest, 'revoked': row.revoked, 'created_at': row.created_at} for row in db.query(Export).order_by(Export.created_at.desc()).limit(100)]

@router.get('/exports/{export_id}/download')
def download(export_id: str, user=Depends(admin), db: Session=Depends(get_db)):
    svc.lock(db)
    export = db.get(Export, export_id)
    if not export:
        raise HTTPException(404, '데이터셋이 없습니다.')
    try:
        svc.validate_export(db, export)
    except ValueError as exc:
        raise HTTPException(409, str(exc)) from exc
    return Response(svc.zip_export(export), media_type='application/zip', headers={'Content-Disposition': f'attachment; filename="qwen_training_{export.id}.zip"'})

class RunIn(BaseModel):
    export_id: str = Field(min_length=32, max_length=32)
    base_model: str = Field(min_length=1, max_length=200)
    parameters: dict = Field(default_factory=dict)
    metrics: dict = Field(default_factory=dict)
    adapter_reference: str = Field('', max_length=500)
    note: str = Field('', max_length=1000)

@router.post('/runs')
def record_run(body: RunIn, user=Depends(admin), db: Session=Depends(get_db)):
    svc.lock(db)
    export = db.get(Export, body.export_id)
    if not export:
        raise HTTPException(404, '데이터셋이 없습니다.')
    try:
        svc.validate_export(db, export)
    except ValueError as exc:
        raise HTTPException(409, str(exc)) from exc
    if len(svc.serialize(body.model_dump())) > 50000:
        raise HTTPException(422, '실험 기록이 너무 큽니다.')
    item = Run(export_id=export.id, created_by=user.user_id, details={**body.model_dump(), 'quality_approved': False})
    db.add(item)
    db.commit()
    return {'id': item.id, 'details': item.details}

@router.get('/runs')
def runs(user=Depends(admin), db: Session=Depends(get_db)):
    return [{'id': row.id, 'details': row.details, 'created_at': row.created_at} for row in db.query(Run).order_by(Run.id.desc()).limit(100)]
