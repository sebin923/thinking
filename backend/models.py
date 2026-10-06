from sqlalchemy import Column, Integer, String, DateTime, ForeignKey, Text
from sqlalchemy.sql import func
from sqlalchemy.orm import relationship

from database import Base


class Document(Base):
    __tablename__ = "documents"

    id = Column(Integer, primary_key=True, index=True)

    # 글 종류: 자기소개서, 보고서 등
    document_type = Column(String(50), nullable=False)

    # 사용자가 정한 글 제목
    title = Column(String(200), nullable=False)

    # 작성 상태: 작성중, 완료 등
    status = Column(String(20), default="작성중")

    # 생성 시간
    created_at = Column(DateTime, server_default=func.now())

    # 마지막 수정 시간
    updated_at = Column(
        DateTime,
        server_default=func.now(),
        onupdate=func.now()
    )


class Thought(Base):
    __tablename__ = "thoughts"

    id = Column(Integer, primary_key=True, index=True)

    # 어떤 문서에 속한 생각인지
    document_id = Column(
        Integer,
        ForeignKey("documents.id", ondelete="CASCADE"),
        nullable=False
    )

    # 사용자가 입력한 키워드 / 메모 / 짧은 문장
    content = Column(Text, nullable=False)

    created_at = Column(DateTime, server_default=func.now())

    # 해당 생각이 어느 문서에 속하는지 연결
    document = relationship("Document")

class Structure(Base):
    __tablename__ = "structures"

    id = Column(Integer, primary_key=True, index=True)

    # 어떤 문서의 구조화 결과인지
    document_id = Column(
        Integer,
        ForeignKey("documents.id", ondelete="CASCADE"),
        nullable=False
    )

    # 구조화 항목
    situation = Column(Text)
    problem = Column(Text)
    action = Column(Text)
    result = Column(Text)
    meaning = Column(Text)

    created_at = Column(DateTime, server_default=func.now())

    document = relationship("Document")

class Draft(Base):
    __tablename__ = "drafts"

    id = Column(Integer, primary_key=True, index=True)

    # 어떤 문서의 초안인지
    document_id = Column(
        Integer,
        ForeignKey("documents.id", ondelete="CASCADE"),
        nullable=False
    )

    # 초안 내용
    content = Column(Text, nullable=False)

    # 초안 버전: 1, 2, 3 ...
    version = Column(Integer, nullable=False, default=1)

    created_at = Column(DateTime, server_default=func.now())

    document = relationship("Document")