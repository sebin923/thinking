from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from pydantic import BaseModel
from typing import Optional
from database import get_db
from models import Document, QuizResult, Quiz, User

router = APIRouter(
    prefix="/api/mypage",
    tags=["MyPage"]
)

# 회원정보 수정을 위한 요청 스키마
class UserUpdateSchema(BaseModel):
    nickname: Optional[str] = None
    name: Optional[str] = None
    phone: Optional[str] = None


@router.get("/posts/{user_id}")
def get_my_posts(user_id: int, db: Session = Depends(get_db)):
    """
    1. 내 글 조회
    사용자가 작성한 문서(documents) 목록을 조회합니다.
    """
    posts = db.query(Document).filter(Document.user_id == user_id).all()
    
    if not posts:
        return []
        
    return {
        "status": "success",
        "data": posts
    }


@router.get("/quiz-history/{user_id}")
def get_quiz_history(user_id: int, db: Session = Depends(get_db)):
    """
    2. 학습 기록 조회
    quiz_results 테이블에서 사용자의 전체 퀴즈 풀이 이력을 조회합니다.
    """
    history = db.query(QuizResult).filter(QuizResult.user_id == user_id).all()
    
    if not history:
        return {
            "status": "success",
            "message": "학습 기록이 없습니다.",
            "data": []
        }
        
    return {
        "status": "success",
        "data": history
    }


@router.get("/incorrect-quizzes/{user_id}")
def get_incorrect_quizzes(user_id: int, db: Session = Depends(get_db)):
    """
    3. 오답 다시 풀기
    quiz_results와 quizzes 테이블을 조인하여 틀린 문제의 상세 정보를 조회합니다.
    """
    incorrect_results = db.query(QuizResult).filter(
        QuizResult.user_id == user_id,
        QuizResult.is_correct == False
    ).all()
    
    if not incorrect_results:
        return {
            "status": "success",
            "message": "틀린 문제가 없습니다.",
            "data": []
        }
        
    response_data = []
    for res in incorrect_results:
        quiz = db.query(Quiz).filter(Quiz.quiz_id == res.quiz_id).first()
        if quiz:
            response_data.append({
                "result_id": res.result_id,
                "quiz_id": quiz.quiz_id,
                "question": quiz.question,
                "options": quiz.options,
                "correct_answer": quiz.answer,
                "user_answer": res.user_answer,
                "explanation": quiz.explanation,
                "solved_at": getattr(res, 'solved_at', None)
            })
            
    return {
        "status": "success",
        "data": response_data
    }


@router.put("/user/{user_id}")
def update_user_info(user_id: int, request: UserUpdateSchema, db: Session = Depends(get_db)):
    """
    4. 회원정보 수정
    사용자의 닉네임, 이름, 전화번호 등의 정보를 수정합니다.
    """
    user = db.query(User).filter(User.user_id == user_id).first()
    if not user:
        raise HTTPException(status_code=404, detail="사용자를 찾을 수 없습니다.")
    
    if request.nickname is not None:
        user.nickname = request.nickname
    if request.name is not None:
        user.name = request.name
    if request.phone is not None:
        user.phone = request.phone
        
    db.commit()
    db.refresh(user)
    
    return {
        "status": "success",
        "message": "회원정보가 성공적으로 수정되었습니다.",
        "data": {
            "user_id": user.user_id,
            "login_id": user.login_id,
            "nickname": user.nickname,
            "name": user.name,
            "phone": user.phone
        }
    }


@router.delete("/user/{user_id}")
def delete_account(user_id: int, db: Session = Depends(get_db)):
    """
    5. 회원 탈퇴
    사용자 계정을 데이터베이스에서 삭제합니다.
    """
    user = db.query(User).filter(User.user_id == user_id).first()
    if not user:
        raise HTTPException(status_code=404, detail="사용자를 찾을 수 없습니다.")
    
    db.delete(user)
    db.commit()
    
    return {
        "status": "success",
        "message": "회원 탈퇴가 완료되었습니다."
    }