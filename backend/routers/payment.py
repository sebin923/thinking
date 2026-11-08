import os
import base64
import requests
from fastapi import APIRouter, Depends, HTTPException, Header
from pydantic import BaseModel
from sqlalchemy.orm import Session
from database import get_db
from models import User, Payment

# 만약 프로젝트 내에 로그인 유저를 가져오는 인증 함수가 있다면 아래 경로에 맞춰서 임포트하세요.
# 예시: from routers.auth import get_current_user (프로젝트 구조에 맞게 수정)
from routers.auth import get_current_user  # <-- 프로젝트에 있는 실제 인증 함수 임포트

router = APIRouter(prefix="/api/payments", tags=["Payment"])

class PaymentConfirmRequest(BaseModel):
    paymentKey: str
    orderId: str
    amount: int

def calculate_draft_count(amount: int) -> int:
    # 새로운 상품 가격표 반영 (1000원 -> 5회, 5000원 -> 30회, 8000원 -> 50회)
    if amount == 1000:
        return 5
    elif amount == 5000:
        return 30
    elif amount == 8000:
        return 50
    return 0

@router.post("/confirm")
def confirm_payment(
    request: PaymentConfirmRequest,
    authorization: str = Header(None),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)  # <-- 토큰으로 로그인된 유저를 바로 가져오는 의존성 주입
):
    if not authorization:
        raise HTTPException(status_code=401, detail="로그인이 필요합니다.")

    # 1. 엉뚱한 사람(.first()) 대신 의존성으로 주입받은 현재 로그인한 사용자를 사용
    user = current_user 
    if not user:
        raise HTTPException(status_code=404, detail="사용자를 찾을 수 없습니다.")

    toss_secret_key = os.getenv("TOSS_SECRET_KEY")
    
    url = "https://api.tosspayments.com/v1/payments/confirm"
    auth_str = f"{toss_secret_key}:"
    encoded_auth = base64.b64encode(auth_str.encode("utf-8")).decode("utf-8")
    
    headers = {
        "Authorization": f"Basic {encoded_auth}",
        "Content-Type": "application/json"
    }
    
    payload = {
        "paymentKey": request.paymentKey,
        "orderId": request.orderId,
        "amount": request.amount
    }

    response = requests.post(url, json=payload, headers=headers)
    
    if response.status_code != 200:
        error_data = response.json()
        raise HTTPException(
            status_code=response.status_code, 
            detail=error_data.get("message", "결제 승인 중 오류가 발생했습니다.")
        )

    added_count = calculate_draft_count(request.amount)

    try:
        new_payment = Payment(
            user_id=user.user_id,
            payment_key=request.paymentKey,
            order_id=request.orderId,
            amount=request.amount,
            draft_count=added_count,
            status="DONE"
        )
        db.add(new_payment)

        if hasattr(user, "ai_credits"):
            # 3. ai_credits 기본값 오류 수정: or 3 대신 or 0을 사용하도록 변경
            user.ai_credits = (user.ai_credits or 0) + added_count
        
        db.commit()
    except Exception as e:
        db.rollback()
        raise HTTPException(status_code=500, detail=f"데이터베이스 저장 실패: {str(e)}")

    return {
        "success": True,
        "message": f"AI 초안 {added_count}회가 성공적으로 충전되었어요."
    }