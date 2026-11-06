import os
import base64
import requests
from fastapi import APIRouter, Depends, HTTPException, Header
from pydantic import BaseModel
from sqlalchemy.orm import Session
from database import get_db
from models import User, Payment

router = APIRouter(prefix="/api/payments", tags=["Payment"])

class PaymentConfirmRequest(BaseModel):
    paymentKey: str
    orderId: str
    amount: int

def calculate_draft_count(amount: int) -> int:
    if amount == 1000:
        return 10
    elif amount == 2500:
        return 30
    elif amount == 7000:
        return 100
    return 0

@router.post("/confirm")
def confirm_payment(
    request: PaymentConfirmRequest,
    authorization: str = Header(None),
    db: Session = Depends(get_db)
):
    if not authorization:
        raise HTTPException(status_code=401, detail="로그인이 필요합니다.")

    user = db.query(User).first() 
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
            user.ai_credits = (user.ai_credits or 3) + added_count
        
        db.commit()
    except Exception as e:
        db.rollback()
        raise HTTPException(status_code=500, detail=f"데이터베이스 저장 실패: {str(e)}")

    return {
        "success": True,
        "message": f"AI 초안 {added_count}회가 성공적으로 충전되었어요."
    }