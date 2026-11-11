생각한줄 개인화 테스트 계정·문서 준비
2026-11-10 / 업로드한 models.py, auth.py, writing.py 기준

1. 압축 풀 위치
ZIP의 personalization_setup 폴더를 backend 폴더 안에 넣습니다.
예: C:\Users\1717-8\Documents\thinking\backend\personalization_setup\setup_personalization.py
기존 models.py, auth.py, writing.py, database.py, security.py를 교체하지 않습니다.
앞서 받은 personalization_accounts_ready.zip은 자료 확인용입니다.
이 ZIP에는 필요한 자료가 모두 있으므로 두 묶음을 합치거나 다시 입력하지 않습니다.

2. 실행
cd C:\Users\1717-8\Documents\thinking\backend
py .\personalization_setup\run_setup.py --check
if ($LASTEXITCODE -eq 0) {
    py .\personalization_setup\run_setup.py --apply
}

run_setup.py는 기존 가상환경에서 백엔드 모듈을 불러올 수 있는 Python을 찾아 실행합니다.
패키지 설치나 환경 변경은 하지 않습니다. 실행 파일을 찾지 못하면 아래 직접 실행 방식을 사용합니다.

기존 백엔드 Python으로 직접 실행하는 경우:
이 스크립트는 backend/database.py의 engine과 backend/security.py의 비밀번호 함수를 사용합니다.
.env나 DB 접속 문자열을 복사해서 보내지 않습니다. DB 연결은 기존 백엔드 설정을 사용합니다.
백엔드 서버는 필수로 켜 둘 필요가 없지만, 기존 DB 테이블은 있어야 합니다.

PowerShell에서 backend 폴더로 이동한 뒤, 백엔드를 실행하는 Python을 사용합니다.
아래 예시는 $py 변수에 해당 Python 경로를 지정한 경우입니다.

& $py .\personalization_setup\setup_personalization.py --check
if ($LASTEXITCODE -eq 0) {
    & $py .\personalization_setup\setup_personalization.py --apply
}

--check는 읽기 전용입니다. 기본값도 --check와 같습니다.
--apply에서 새 계정이 필요할 때 비밀번호를 두 번 입력합니다. 입력 문자는 화면에 나타나지 않습니다.
세 테스트 계정에 같은 비밀번호를 적용합니다. 12자 이상, UTF-8 기준 72바이트 이내로 입력합니다.
평문 비밀번호는 파일·로그에 남기지 않습니다. 기존 보안 함수로 해시하고 검증한 뒤 저장합니다.

3. 생성되는 계정
로그인 아이디         표시 이름               문체
persona_concise        개인화테스트_간결       짧고 담백하게
persona_formal         개인화테스트_격식       격식 있고 논리적으로
persona_friendly       개인화테스트_친근       쉽고 부드럽게

세 계정 모두 general 권한, active 상태이며 AI 이용 횟수는 기존 기본값과 같은 3회입니다.
다시 실행해도 이용 횟수나 비밀번호를 초기화하지 않습니다.
이메일은 로그인아이디@example.com, 전화번호는 00000000000인 합성 테스트 정보입니다.
실제 이메일 인증은 하지 않으며 email_verified=False입니다. 메일이나 문자는 보내지 않습니다.
전달받은 로그인 코드에는 이메일 인증 여부로 로그인을 막는 조건이 없습니다.
실행 시 현재 auth_schemas의 입력·출력 검증도 통과해야 저장됩니다.

4. 실제 앱 테이블에 저장
users: 테스트 계정 3개. 기본키는 user_id입니다.
user_writing_preferences: 계정별 설정 3개.
documents: 계정별 12개, 전체 36개. 상태는 완료이며 제목에 [개인화테스트/학습] 또는 [개인화테스트/검증]을 표시합니다.
thoughts: 각 문서의 사실 메모를 줄별로 저장합니다.
drafts: 문서별 수정 전 version=1과 수정 후 version=2, 전체 72개.
ai_feedbacks: 생성하지 않습니다. 존재하지 않는 AI 평가·피드백을 만들지 않습니다.
payments, rankings, quiz_results 및 기존 사용자 자료는 변경하지 않습니다.

두 개의 추적 테이블을 새로 만듭니다.
personalization_demo_accounts_v1: 계정 키와 실제 user_id 연결.
personalization_demo_records_v1: 문서·초안 ID, 분할, 합성 여부, 원본 해시 연결.
기존 앱 테이블의 열을 추가하거나 변경하지 않습니다.
같은 이름의 기존 계정이 추적 정보 없이 존재하면 자동으로 가져오거나 변경하지 않고 중단합니다.
같은 데이터로 재실행하면 기존 문서와 초안을 확인하고 건너뜁니다.
원본 데이터나 저장된 버전 1·2가 바뀌면 덮어쓰지 않고 중단합니다.
DB 저장은 하나의 트랜잭션으로 처리하며 중간 오류 시 이번 저장을 취소합니다.
동시 실행은 PostgreSQL의 트랜잭션 단위 잠금으로 제한합니다.

5. 저장 후 확인
& $py .\personalization_setup\setup_personalization.py --verify

기대 결과: 계정 3개 / 문서 36개 / 초안 72개 / train 27건, valid 9건.
setup_result.json에는 실제 user_id와 건수가 저장됩니다. 비밀번호는 없습니다.
로그인 아이디와 직접 입력한 비밀번호로 앱에 로그인해 문서 목록과 수정 전후 버전을 확인합니다.
글 유형은 보고서·발표문·자유 글쓰기입니다. 현재 writing.py의 공통 초안 API는 보고서·자기소개서만 허용하므로,
발표문·자유 글쓰기 문서를 저장했다고 해서 해당 공통 초안 API 지원 범위가 자동 확대되지는 않습니다.

6. DB에서 개인별 후보 추출
저장과 화면 확인을 마친 뒤 실행합니다. 이 명령은 모델을 학습시키지 않습니다.
& $py .\personalization_setup\setup_personalization.py --export

personalization_setup/export_날짜_시각/user_실제ID/train.jsonl, valid.jsonl로 저장됩니다.
계정별 학습 후보 9건과 검증 3건이며 세 사용자의 데이터를 섞지 않습니다.
입력은 DB 추적 레코드의 사실 메모, 정답은 연결된 실제 drafts의 버전 2입니다.
추출 전 문서 소유자, 버전, 본문, 생각 메모, 원본 해시를 확인합니다.
이후 사용자가 만든 버전 3 이상을 자동으로 학습에 추가하지 않습니다.
최종 시험용 data/heldout_test_prompts.json의 3개 새 주제는 학습하지 않습니다.

현재 /training-candidates API는 앞 버전의 AI 피드백이 있어야 후보를 반환합니다.
이번 데모에는 가짜 피드백을 넣지 않으므로 그 API에서 후보가 0건일 수 있습니다.
위 --export는 개인화 시연 후보를 위한 별도 경로이며 그 API를 변경하지 않습니다.

7. 개인화 비교 시 주의할 점
모든 자료는 AI가 만든 가상 수정 기록입니다. 실제 사용자 경험·동의·평가 기록이 아닙니다.
synthetic=true, human_approved=false, common_training_allowed=false를 추적 테이블과 추출 파일에 보존합니다.
별점이나 공통 모델 승인 자료로 자동 편입하지 않습니다.
앞으로 공통 학습 후보를 추출하는 별도 기능에서도 이 표식을 조회해 데모·검증 자료를 제외해야 합니다.
앱의 계정별 문체 설정만 바꿔도 출력이 달라질 수 있습니다. 개인 어댑터 자체의 효과를 비교할 때는
공통·개인 모델에 동일한 입력과 생성 설정을 사용하고, 개인 선호를 프롬프트에 추가하는 실험은 별도로 구분합니다.
계정당 9건은 기능 점검용 소량 자료이며 뚜렷한 개인화 효과를 보장하지 않습니다.

8. 검증 범위
업로드한 실제 models.py를 불러온 임시 SQLite DB에서 계정·문서·버전 연결, 중복 방지,
기존 계정 충돌, 계정 소유자 혼선, 중간 실패 시 데이터 취소, 분할별 추출을 검사했습니다.
사용자의 PostgreSQL/RDS, 실제 security.py와 auth_schemas, 브라우저 로그인은 이 환경에서 실행하지 못했습니다.
--check 및 --apply 실행 결과와 실제 로그인을 통해 해당 환경에서 확인해야 합니다.

참고 문서
https://docs.sqlalchemy.org/en/20/core/connections.html
https://www.postgresql.org/docs/current/functions-admin.html
