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