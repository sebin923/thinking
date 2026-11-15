from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session
from database import get_db
from routers.auth import get_current_user
import learning_progress as svc

router=APIRouter(prefix='/api/learn/progress',tags=['learn-progress'])
class SaveProgress(BaseModel):
    expected_revision:int=Field(ge=0)
    progress:dict

@router.get('')
def get_progress(user=Depends(get_current_user),db:Session=Depends(get_db)):
    row=svc.row_for(db,user.user_id);result=svc.snapshot(row);db.commit();return result

def save(body,user,db,legacy=False):
    try:
        fn=svc.import_legacy if legacy else svc.update_progress
        return fn(db,user.user_id,body.progress,body.expected_revision)
    except ValueError as exc:
        db.rollback()
        if str(exc)=='conflict':raise HTTPException(409,'다른 탭이나 기기에서 진도가 변경됐어요. 화면을 새로고침한 뒤 다시 시도해 주세요.') from exc
        raise HTTPException(422,str(exc)) from exc

@router.put('')
def put_progress(body:SaveProgress,user=Depends(get_current_user),db:Session=Depends(get_db)):
    return save(body,user,db)

@router.post('/import-legacy')
def import_progress(body:SaveProgress,user=Depends(get_current_user),db:Session=Depends(get_db)):
    return save(body,user,db,True)
