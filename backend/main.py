from database import engine, Base
import models
from sqlalchemy import text

# FastAPI: 백엔드 서버를 만드는 프레임워크
from fastapi import FastAPI

# CORSMiddleware: 다른 주소(포트)에서 오는 요청을 허용할지 정하는 도구
# 브라우저는 보안 때문에 React(5173번 포트) → FastAPI(8000번 포트)로 가는 요청을
# 기본적으로 막아버림 → 여기서 "5173은 허용해" 하고 알려줘야 연결이 됨
from fastapi.middleware.cors import CORSMiddleware

from routers.quiz import router as quiz_router
from routers.writing import router as writing_router

# app: 우리 백엔드 서버 본체
app = FastAPI()

Base.metadata.create_all(bind=engine)

# 서버에 CORS 규칙을 추가하는 부분
app.add_middleware(
    CORSMiddleware,
    # allow_origins: 요청을 허용할 프론트엔드 주소 목록
    # localhost와 127.0.0.1은 브라우저 입장에서 서로 다른 주소라서 둘 다 적어둠
    allow_origins=[
        "http://localhost:5173",
        "http://127.0.0.1:5173",
    ],
    # allow_credentials: 쿠키나 로그인 정보도 같이 주고받을 수 있게 허용
    # (나중에 로그인 기능 만들 때 필요함)
    allow_credentials=True,
    # allow_methods: GET, POST, PUT, DELETE 등 모든 요청 방식을 허용
    allow_methods=["*"],
    # allow_headers: 요청에 붙는 모든 헤더(추가 정보)를 허용
    allow_headers=["*"],
)

for route in quiz_router.routes:
    app.router.routes.append(route)

for route in writing_router.routes:
    app.router.routes.append(route)

# @app.get("/"): "http://127.0.0.1:8000/" 주소로 GET 요청이 오면
# 바로 아래 함수를 실행하라는 뜻 (서버가 살아있는지 확인하는 용도)
@app.get("/")
def root():
    # 딕셔너리를 return하면 FastAPI가 알아서 JSON으로 바꿔서 보내줌
    return {"message": "생각한줄 서버 실행 중"}


# @app.get("/api/test"): React의 App.jsx가 fetch로 부르는 바로 그 주소
# React 코드의 주소("/api/test")와 여기 주소가 글자 하나까지 똑같아야 연결됨
@app.get("/api/test")
def test():
    # React에서 data.message로 꺼내 쓰기 때문에 key 이름을 꼭 "message"로 맞춰야 함
    return {"message": "생각한줄 서버 연결 성공!"}

@app.get("/api/db-test")
def db_test():
    with engine.connect() as connection:
        result = connection.execute(text("SELECT 1"))
        value = result.scalar()

    return {
        "message": "PostgreSQL 연결 성공!",
        "result": value
    }