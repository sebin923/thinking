# =============================================================
# routers/notice.py — 공지사항 보기 API (로그인 안 해도 누구나)
# -------------------------------------------------------------
#  GET /api/notices               공지 목록 (고정 공지 먼저 → 최신 순)
#  GET /api/notices/{notice_id}   공지 하나
#
# 등록·수정·삭제는 관리자만 할 수 있어서 routers/admin.py에 따로 있음
#   (POST·PUT·DELETE /api/admin/notices)
# =============================================================

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

import models
from admin_schemas import NoticeOut
from database import get_db

router = APIRouter(prefix="/api/notices", tags=["notice"])


@router.get("", response_model=list[NoticeOut])
def list_notices(db: Session = Depends(get_db)):
    """공지 목록
    정렬: ① 고정 공지(is_pinned = True)가 맨 위 ② 그 안에서는 최근에 등록한 공지가 위
    desc(): 큰 값이 먼저 → True(1)가 False(0)보다 먼저, 최근 날짜가 먼저
    """
    return (
        db.query(models.Notice)
        .order_by(
            models.Notice.is_pinned.desc(),
            models.Notice.created_at.desc(),
            models.Notice.notice_id.desc(),  # 등록 시각이 같으면 나중에 만든 번호가 위
        )
        .all()
    )


@router.get("/{notice_id}", response_model=NoticeOut)
def get_notice(notice_id: int, db: Session = Depends(get_db)):
    """공지 하나 (없는 번호면 404)"""
    notice = db.get(models.Notice, notice_id)
    if notice is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, detail="공지사항을 찾을 수 없어요.")
    return notice
