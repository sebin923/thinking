from database import SessionLocal
import models

db = SessionLocal()

try:
    # 기존 데이터 삭제
    db.query(models.QuizResult).delete()
    db.query(models.Ranking).delete()
    db.query(models.Quiz).delete()
    db.commit()

    quizzes = [
        {
            "category": "spelling",
            "question": "도저히 견딜 수가 없어서 ‘____’ 울었다.",
            "answer": "금세",
            "options": ["금새", "금세"],
            "explanation": "'금세'는 '금시에'의 줄임말인 단어 자체의 표기입니다."
        },
        {
            "category": "spelling",
            "question": "친구와 약속을 했으면 ‘____’ 지켜야 한다.",
            "answer": "반드시",
            "options": ["반드시", "반듯이"],
            "explanation": "'틀림없이 꼭'이라는 뜻을 가진 단어는 '반드시'입니다."
        },
        {
            "category": "spelling",
            "question": "고개를 ‘____’ 펴고 당당하게 걸어라.",
            "answer": "반듯이",
            "options": ["반드시", "반듯이"],
            "explanation": "'비뚤어지지 않고 바르게'라는 뜻의 단어는 '반듯이'입니다."
        },
        {
            "category": "spelling",
            "question": "이유 없이 사람을 ‘____’ 하면 안 된다.",
            "answer": "애꿎은",
            "options": ["애꿎은", "애궂은"],
            "explanation": "'엉뚱하게 남에게 화를 입히는' 뜻의 단어는 '애꿎다'입니다."
        },
        {
            "category": "spelling",
            "question": "아무리 바빠도 아침밥은 ‘____’ 거르면 안 된다.",
            "answer": "절대",
            "options": ["절대", "절때"],
            "explanation": "'어떠한 경우에도'를 뜻하는 단어는 '절대'입니다."
        },

        # ----- 문법 퀴즈 (category: grammar) -----
        # 조사·어미를 알맞게 고르는 문제 (빈칸은 ____ 로 표시 → 화면에서 밑줄 칸으로 바뀜)
        {
            "category": "grammar",
            "question": "저는 어제 친구____ 영화를 봤어요.",
            "answer": "와",
            "options": ["와", "과"],
            "explanation": "앞말에 받침이 없으면 '와', 받침이 있으면 '과'를 씁니다. '친구'는 받침이 없으니 '친구와'가 맞습니다."
        },
        {
            "category": "grammar",
            "question": "숙제를 아직 ____ 했다.",
            "answer": "안",
            "options": ["안", "않"],
            "explanation": "'안'은 '아니'의 준말로 동사 앞에 씁니다. '않'은 '아니하-'의 준말이라 '하지 않았다'처럼 '-지 않다' 꼴로 씁니다."
        },
        {
            "category": "grammar",
            "question": "그는 학생____ 본분을 다했다.",
            "answer": "으로서",
            "options": ["으로서", "으로써"],
            "explanation": "자격이나 신분을 나타낼 때는 '(으)로서', 수단이나 도구를 나타낼 때는 '(으)로써'를 씁니다."
        },
        {
            "category": "grammar",
            "question": "사과____ 배든지 먹고 싶은 걸 골라.",
            "answer": "든지",
            "options": ["든지", "던지"],
            "explanation": "여러 가지 중에서 고를 때는 '-든지'를 씁니다. '-던지'는 지난 일을 떠올릴 때 씁니다."
        },
        {
            "category": "grammar",
            "question": "얼마나 놀랐____ 말이 나오지 않았다.",
            "answer": "던지",
            "options": ["던지", "든지"],
            "explanation": "지난 일을 떠올리며 그 정도를 말할 때는 '-던지'를 씁니다. '얼마나 놀랐던지'가 맞습니다."
        }
    ]

    for item in quizzes:
        quiz = models.Quiz(
            category=item["category"],
            question=item["question"],
            answer=item["answer"],
            options=item["options"],
            explanation=item["explanation"]
        )
        db.add(quiz)

    db.commit()
    print("퀴즈 더미데이터 입력 완료")

finally:
    db.close()