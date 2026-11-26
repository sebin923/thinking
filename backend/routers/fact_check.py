"""글쓰기 연습의 참고 검사. 진도·점수·학습 후보를 저장하지 않는다."""
from fastapi import APIRouter,Depends,HTTPException
from sqlalchemy.orm import Session
from database import get_db
from routers.auth import get_current_user
from routers.learn import LearnScoreIn
from learning_progress import LearningProgress
import models
from fact_check import check_facts

router=APIRouter(prefix='/api/learn',tags=['learn'])


@router.post('/fact-check')
def fact_check(data:LearnScoreIn,current_user:models.User=Depends(get_current_user),db:Session=Depends(get_db)):
    if not data.unit_id:raise HTTPException(422,'검사할 단원 ID가 필요합니다.')
    progress=db.get(LearningProgress,current_user.user_id)
    units=progress.payload.get('units',{}) if progress and isinstance(progress.payload,dict) else {}
    if not units.get(data.unit_id,{}).get('passed',False):
        raise HTTPException(403,'O/X 문제를 통과한 뒤 글쓰기 연습에서 검사할 수 있어요.')
    return check_facts(data.model_dump())
