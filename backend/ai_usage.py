"""Server-owned daily free uses and purchased writing AI credits."""
from datetime import datetime, timedelta, timezone

from fastapi import HTTPException
from sqlalchemy import Column, Date, ForeignKey, Integer, update
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.dialects.sqlite import insert as sqlite_insert

from database import Base
from models import User

FREE_DAILY_USES = 3
KST = timezone(timedelta(hours=9))


class AiDailyUsage(Base):
    __tablename__ = "ai_daily_usage"
    user_id = Column(Integer, ForeignKey("users.user_id", ondelete="CASCADE"), primary_key=True)
    usage_date = Column(Date, primary_key=True)
    used = Column(Integer, nullable=False, default=0)


def today():
    return datetime.now(KST).date()


def get_usage(db, user_id, *, day=None):
    day = day or today()
    user = db.query(User).filter_by(user_id=user_id).populate_existing().first()
    if user is None:
        raise HTTPException(401, "로그인이 필요합니다.")
    used = db.query(AiDailyUsage.used).filter_by(user_id=user_id, usage_date=day).scalar() or 0
    credits = max(0, user.ai_credits or 0)
    remaining = max(0, FREE_DAILY_USES - used)
    unlimited = user.role == "admin"
    return {"date": day.isoformat(), "used": used, "limit": FREE_DAILY_USES,
            "remaining": remaining, "credits": credits, "unlimited": unlimited,
            "can_use": unlimited or remaining > 0 or credits > 0}


def require_available(db, user_id):
    if not get_usage(db, user_id)["can_use"]:
        raise HTTPException(402, "오늘 무료 AI 횟수와 보유 이용권을 모두 사용했어요. 이용권을 충전해 주세요.")


def consume(db, user_id):
    """Charge a successful result in the caller's transaction, free uses first.

    Recheck after generation: another tab may have spent the final use while the
    model ran. A PostgreSQL user-row lock and conditional updates prevent excess
    free uses or negative balances. No database lock is held during generation.
    The caller commits result persistence and this charge together.
    """
    day = today()
    user = db.query(User).filter_by(user_id=user_id).populate_existing().with_for_update().first()
    if user is None:
        raise HTTPException(401, "로그인이 필요합니다.")
    if user.role == "admin":
        return get_usage(db, user_id, day=day)
    dialect = db.get_bind().dialect.name
    insert = {"postgresql": pg_insert, "sqlite": sqlite_insert}.get(dialect)
    if insert is None:
        raise RuntimeError("AI 이용 횟수 DB는 PostgreSQL/SQLite를 지원합니다.")
    db.execute(insert(AiDailyUsage).values(user_id=user_id, usage_date=day, used=0)
               .on_conflict_do_nothing(index_elements=["user_id", "usage_date"]))
    free = db.execute(update(AiDailyUsage).where(
        AiDailyUsage.user_id == user_id, AiDailyUsage.usage_date == day,
        AiDailyUsage.used < FREE_DAILY_USES,
    ).values(used=AiDailyUsage.used + 1).execution_options(synchronize_session=False))
    if not free.rowcount:
        paid = db.execute(update(User).where(User.user_id == user_id, User.ai_credits > 0)
                          .values(ai_credits=User.ai_credits - 1)
                          .execution_options(synchronize_session=False))
        if not paid.rowcount:
            raise HTTPException(402, "남은 이용 횟수가 다른 요청에서 사용됐어요. 이용권을 확인해 주세요.")
    return get_usage(db, user_id, day=day)
