from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from typing import List

import models
import schemas
from database import get_db

router = APIRouter(
    prefix="/api/quizzes",
    tags=["Quizzes"]
)

# 1. 퀴즈 목록 조회 (카테고리별: spelling / grammar)
@router.get("/", response_model=List[schemas.QuizResponse])
def get_quizzes(category: str, db: Session = Depends(get_db)):
    quizzes = db.query(models.Quiz).filter(models.Quiz.category == category).all()
    return quizzes

# 2. 퀴즈 제출 및 채점
@router.post("/submit", response_model=schemas.QuizSubmitResponse)
def submit_quiz(request: schemas.QuizSubmitRequest, db: Session = Depends(get_db)):
    quiz = db.query(models.Quiz).filter(models.Quiz.quiz_id == request.quiz_id).first()
    if not quiz:
        raise HTTPException(status_code=404, detail="해당 퀴즈를 찾을 수 없습니다.")

    is_correct = (quiz.answer.strip() == request.user_answer.strip())

    db_result = models.QuizResult(
        user_id=request.user_id,
        quiz_id=request.quiz_id,
        is_correct=is_correct,
        user_answer=request.user_answer
    )
    db.add(db_result)
    db.commit()
    db.refresh(db_result)

    return {
        "result_id": db_result.result_id,
        "is_correct": is_correct,
        "correct_answer": quiz.answer,
        "explanation": quiz.explanation
    }

# 3. 맞춤법 랭킹 점수 제출
@router.post("/rankings", response_model=schemas.RankingResponse)
def submit_ranking(request: schemas.RankingSubmitRequest, db: Session = Depends(get_db)):
    db_ranking = models.Ranking(
        user_id=request.user_id,
        category=request.category,
        score=request.score
    )
    db.add(db_ranking)
    db.commit()
    db.refresh(db_ranking)
    
    user = db.query(models.User).filter(models.User.user_id == request.user_id).first()
    # 닉네임이 없으면(회원가입에서 안 받음) 이름으로 대신 표시
    nickname = (user.nickname or user.name) if user else "알 수 없음"

    return {
        "ranking_id": db_ranking.ranking_id,
        "user_id": db_ranking.user_id,
        "nickname": nickname,
        "category": db_ranking.category,
        "score": db_ranking.score,
        "challenged_at": db_ranking.challenged_at
    }

# 4. 맞춤법 랭킹 조회 (category 필터링 추가)
# 도전 모드는 같은 사람이 여러 번 도전해서 기록이 여러 줄 쌓임
#  → 예전처럼 "점수 높은 줄 10개"만 자르면 한 사람이 TOP 10을 다 차지할 수 있음
#  → 그래서 "사람마다 최고 기록 1줄"만 남긴 뒤 위에서 10명을 자름
@router.get("/rankings", response_model=List[schemas.RankingResponse])
def get_rankings(category: str = "spelling", db: Session = Depends(get_db)):
    # 점수 높은 순, 점수가 같으면 먼저 달성한 기록(challenged_at이 빠른 것)이 위로
    all_rows = db.query(models.Ranking).filter(
        models.Ranking.category == category
    ).order_by(models.Ranking.score.desc(), models.Ranking.challenged_at.asc()).all()

    rankings = []
    seen_users = set()  # 이미 넣은 사람 번호 모음 (set: 중복 없는 묶음)
    for r in all_rows:
        # 위에서부터 보니까, 그 사람의 첫 줄 = 그 사람의 최고 기록
        if r.user_id in seen_users:
            continue
        seen_users.add(r.user_id)
        rankings.append(r)
        if len(rankings) == 10:  # 10명 채우면 끝
            break

    response_data = []
    for r in rankings:
        user = db.query(models.User).filter(models.User.user_id == r.user_id).first()
        response_data.append({
            "ranking_id": r.ranking_id,
            "user_id": r.user_id,
            # 닉네임이 없으면(회원가입에서 안 받음) 이름으로 대신 표시
            "nickname": (user.nickname or user.name) if user else "알 수 없음",
            "category": r.category,
            "score": r.score,
            "challenged_at": r.challenged_at
        })
        
    return response_data

# 5. 내가 틀린 문제(오답 복습) 목록 조회 API
@router.get("/incorrect/{user_id}", response_model=List[schemas.IncorrectQuizResponse])
def get_incorrect_quizzes(user_id: int, db: Session = Depends(get_db)):
    incorrect_results = db.query(models.QuizResult).filter(
        models.QuizResult.user_id == user_id,
        models.QuizResult.is_correct == False
    ).all()

    response_data = []
    for res in incorrect_results:
        quiz = db.query(models.Quiz).filter(models.Quiz.quiz_id == res.quiz_id).first()
        if quiz:
            response_data.append({
                "result_id": res.result_id,
                "quiz_id": quiz.quiz_id,
                "question": quiz.question,
                "options": quiz.options,
                "correct_answer": quiz.answer,
                "user_answer": res.user_answer,
                "explanation": quiz.explanation,
                "solved_at": res.solved_at
            })

    return response_data