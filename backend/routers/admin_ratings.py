"""기존 별점 데이터의 관리자 전용 조회. 원본 평가를 수정하거나 삭제하지 않는다."""
from fastapi import APIRouter, Depends, Query, HTTPException
from sqlalchemy import func
from sqlalchemy.orm import Session
from database import get_db
from routers.auth import get_current_user
from models import AiRating

router = APIRouter(prefix='/api/admin/ratings', tags=['admin-ratings'])

def require_admin(user=Depends(get_current_user)):
    if user.role != 'admin' or getattr(user, 'status', 'active') != 'active':
        raise HTTPException(403, '관리자만 이용할 수 있습니다.')
    return user

@router.get('')
def list_ratings(kind: str=Query('', max_length=20), model: str=Query('', max_length=30), stars: int | None=Query(None, ge=1, le=5), offset: int=Query(0, ge=0), user=Depends(require_admin), db: Session=Depends(get_db)):
    query = db.query(AiRating)
    if kind: query = query.filter(AiRating.kind == kind)
    if model: query = query.filter(AiRating.model == model)
    if stars is not None: query = query.filter(AiRating.rating == stars)
    distribution = {str(i): 0 for i in range(1, 6)}
    for rating, count in query.with_entities(AiRating.rating, func.count(AiRating.id)).group_by(AiRating.rating).all():
        if str(rating) in distribution: distribution[str(rating)] = count
    total = sum(distribution.values())
    rows = query.order_by(AiRating.created_at.desc(), AiRating.id.desc()).offset(offset).limit(20).all()
    return {'total': total, 'average': round(sum(int(k)*v for k,v in distribution.items()) / total, 2) if total else None,
            'distribution': distribution, 'items': [{key: getattr(row, key) for key in ('id','kind','model','rating','comment','document_id','created_at')} for row in rows],
            'kinds': [r[0] for r in db.query(AiRating.kind).distinct().order_by(AiRating.kind)],
            'models': [r[0] for r in db.query(AiRating.model).distinct().order_by(AiRating.model)]}

@router.get('/{rating_id}')
def rating_detail(rating_id: str, user=Depends(require_admin), db: Session=Depends(get_db)):
    row = db.get(AiRating, rating_id)
    if not row: raise HTTPException(404, '평가를 찾을 수 없습니다.')
    return {key: getattr(row, key) for key in ('id','kind','model','rating','comment','document_id','request_text','result_text','created_at')}
