# 배포 파일 안내

이 저장소는 EC2에서 실행할 웹·백엔드 코드와 GPU 서버를 호출하는 연결 코드를 관리합니다.
GPU 추론 서버·모델·학습 코드·수집 자료는 GPU PC에 따로 보관하며 Git 업로드에서 제외합니다.
기존 프론트와 단원 설명·O/X 문제는 이번 정리에서 변경하지 않습니다.

EC2 설정과 확인 순서는 [EC2 연결 안내](README_EC2_GPU.ko.md)를 참고하세요.
환경설정에는 GPU PC의 Tailscale 주소와 공유 토큰을 사용합니다. 실제 토큰과 DB 비밀번호는 Git에 넣지 않습니다.

`check_remote_llm.py`는 EC2에서 원격 GPU 연결을 확인하는 도구입니다.
`thinking-backend.service.example`과 `nginx-thinking.conf.example`은 기존 운영 환경에 맞춰 수정하는 견본입니다.
`notices/`와 `publish_ai_notice.py`는 공지 자료와 등록 도구이며 이번 코드 업로드에서 자동 실행하지 않습니다.

이번 변경은 개인화 주제 추천을 기존 API에 연결하고 피드백·채점 결과 검증을 보완합니다.
문법 퀴즈 난이도 처리와 DB O/X 조회는 최신 master 동작을 유지합니다.
코드 업로드 자체로 EC2 서비스가 갱신되거나 GPU 서버가 재시작되지는 않습니다.
