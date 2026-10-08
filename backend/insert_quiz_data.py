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

        # ----- 맞춤법 추가 문제 (도전 모드용) -----
        # 도전 모드는 틀릴 때까지 계속 푸는 방식이라 문제가 많을수록 좋음
        # 보기 순서는 화면에서 섞어서 보여주니까 여기서는 아무 순서로 써도 됨
        {
            "category": "spelling",
            "question": "‘____’ 고향 친구를 만나서 반가웠다.",
            "answer": "오랜만에",
            "options": ["오랫만에", "오랜만에"],
            "explanation": "'오래간만에'가 줄어든 말이라 '오랜만에'가 맞습니다."
        },
        {
            "category": "spelling",
            "question": "오늘은 ‘____’ 기분이 좋다.",
            "answer": "왠지",
            "options": ["왠지", "웬지"],
            "explanation": "'왜인지'가 줄어든 말이라 '왠지'로 씁니다."
        },
        {
            "category": "spelling",
            "question": "이 시간에 여기까지 ‘____’이야?",
            "answer": "웬일",
            "options": ["왠일", "웬일"],
            "explanation": "'어찌 된 일'이라는 뜻의 단어는 '웬일'입니다. '왠'은 '왠지'에만 쓴다고 기억하면 쉬워요."
        },
        {
            "category": "spelling",
            "question": "지갑을 잃어버렸어. 이제 ‘____’?",
            "answer": "어떡해",
            "options": ["어떻게", "어떡해"],
            "explanation": "'어떻게 해'가 줄어든 말은 '어떡해'입니다. '어떻게'는 '어떻게 왔어?'처럼 뒤에 다른 말이 이어질 때 씁니다."
        },
        {
            "category": "spelling",
            "question": "오늘이 ‘____’이지?",
            "answer": "며칠",
            "options": ["몇 일", "며칠"],
            "explanation": "'몇 일'이라는 표기는 없고, 항상 '며칠'로 씁니다."
        },
        {
            "category": "spelling",
            "question": "거기 들어가면 ‘____’.",
            "answer": "안 돼",
            "options": ["안 돼", "안 되"],
            "explanation": "'돼'는 '되어'의 준말입니다. 문장이 끝날 때는 '되어'로 바꿔 말이 되면 '돼'를 씁니다."
        },
        {
            "category": "spelling",
            "question": "밥을 먹고 나서 ‘____’를 했다.",
            "answer": "설거지",
            "options": ["설겆이", "설거지"],
            "explanation": "표준어는 '설거지'입니다. '설겆이'는 틀린 표기예요."
        },
        {
            "category": "spelling",
            "question": "모두 각자 맡은 ‘____’을 다하자.",
            "answer": "역할",
            "options": ["역할", "역활"],
            "explanation": "'부릴 역(役)'에 '나눌 할(割)'을 써서 '역할'입니다."
        },
        {
            "category": "spelling",
            "question": "살다 보니 참 ‘____’ 일도 다 있다.",
            "answer": "희한한",
            "options": ["희안한", "희한한"],
            "explanation": "'매우 드물거나 신기하다'는 뜻의 단어는 '희한하다'입니다."
        },
        {
            "category": "spelling",
            "question": "너무 ‘____’ 웃음만 나왔다.",
            "answer": "어이없어서",
            "options": ["어의없어서", "어이없어서"],
            "explanation": "'일이 너무 뜻밖이라 기가 막히다'는 뜻의 단어는 '어이없다'입니다."
        },
        {
            "category": "spelling",
            "question": "그 말을 마음속으로 몇 번이고 ‘____’.",
            "answer": "되뇌었다",
            "options": ["되뇌었다", "되뇌이었다"],
            "explanation": "기본형이 '되뇌다'라서 '되뇌었다'가 맞습니다. '되뇌이다'는 틀린 말이에요."
        },
        {
            "category": "spelling",
            "question": "‘____’ 그런 건 아니니까 오해하지 마.",
            "answer": "일부러",
            "options": ["일부로", "일부러"],
            "explanation": "'알면서도 굳이'라는 뜻의 단어는 '일부러'입니다."
        },
        {
            "category": "spelling",
            "question": "‘____’ 그렇게까지 할 필요는 없어.",
            "answer": "굳이",
            "options": ["굳이", "구지"],
            "explanation": "'굳다'에서 온 말이라 '굳이'로 쓰고 [구지]라고 읽습니다."
        },
        {
            "category": "spelling",
            "question": "그 일을 ‘____’ 생각해 보았다.",
            "answer": "곰곰이",
            "options": ["곰곰히", "곰곰이"],
            "explanation": "'곰곰'처럼 같은 말이 겹친 뒤에는 '-이'를 붙여 '곰곰이'로 씁니다."
        },
        {
            "category": "spelling",
            "question": "밖에 다녀오면 손을 ‘____’ 씻어라.",
            "answer": "깨끗이",
            "options": ["깨끗이", "깨끗히"],
            "explanation": "'ㅅ' 받침 뒤에서는 '-이'를 붙여 '깨끗이'로 씁니다."
        },
        {
            "category": "spelling",
            "question": "쉬는 시간마다 ‘____’ 책을 읽었다.",
            "answer": "틈틈이",
            "options": ["틈틈히", "틈틈이"],
            "explanation": "같은 말이 겹친 '틈틈' 뒤에는 '-이'를 붙여 '틈틈이'로 씁니다."
        },
        {
            "category": "spelling",
            "question": "제출하기 전에 서류를 ‘____’ 살펴보았다.",
            "answer": "꼼꼼히",
            "options": ["꼼꼼이", "꼼꼼히"],
            "explanation": "'꼼꼼하다'처럼 '-하다'가 붙는 말은 '-히'를 붙여 '꼼꼼히'로 씁니다."
        },
        {
            "category": "spelling",
            "question": "‘____’ 오늘 안에 끝내자.",
            "answer": "웬만하면",
            "options": ["웬만하면", "왠만하면"],
            "explanation": "'웬만하다'가 기본형이라 '웬만하면'이 맞습니다."
        },
        {
            "category": "spelling",
            "question": "이번 행사에는 ‘____’ 전문가들이 모였다.",
            "answer": "내로라하는",
            "options": ["내노라하는", "내로라하는"],
            "explanation": "'어떤 분야에서 대표할 만하다'는 뜻의 단어는 '내로라하다'입니다."
        },
        {
            "category": "spelling",
            "question": "어제 기말고사를 무사히 ‘____’.",
            "answer": "치렀다",
            "options": ["치뤘다", "치렀다"],
            "explanation": "기본형이 '치르다'라서 '치르- + -었다 → 치렀다'가 됩니다. '치루다'는 틀린 말이에요."
        },
        {
            "category": "spelling",
            "question": "실내에서는 큰 소리로 통화하는 것을 ‘____’ 주세요.",
            "answer": "삼가",
            "options": ["삼가해", "삼가"],
            "explanation": "기본형이 '삼가다'라서 '삼가 주세요'가 맞습니다. '삼가하다'는 없는 말이에요."
        },
        {
            "category": "spelling",
            "question": "‘____’를 베고 바로 잠들었다.",
            "answer": "베개",
            "options": ["베게", "베개"],
            "explanation": "머리를 괴는 물건은 '베개'입니다."
        },
        {
            "category": "spelling",
            "question": "점심으로 얼큰한 ‘____’을 먹었다.",
            "answer": "육개장",
            "options": ["육개장", "육계장"],
            "explanation": "'개장국'에 쇠고기(육)를 넣은 음식이라 '육개장'입니다."
        },
        {
            "category": "spelling",
            "question": "일이 ‘____’ 풀기가 어렵다.",
            "answer": "얽히고설켜",
            "options": ["얽히고섥혀", "얽히고설켜"],
            "explanation": "표준어는 '얽히고설키다'라서 '얽히고설켜'로 씁니다."
        },
        {
            "category": "spelling",
            "question": "물건값을 카드로 ‘____’했다.",
            "answer": "결제",
            "options": ["결재", "결제"],
            "explanation": "돈을 치르는 것은 '결제', 윗사람이 안건을 승인하는 것은 '결재'입니다."
        },
        {
            "category": "spelling",
            "question": "퀴즈의 정답을 모두 ‘____’.",
            "answer": "맞혔다",
            "options": ["맞췄다", "맞혔다"],
            "explanation": "정답을 골라내는 것은 '맞히다', 두 대상을 비교하거나 짝을 맞추는 것은 '맞추다'입니다."
        },
        {
            "category": "spelling",
            "question": "집에 가는 길에 편의점에 잠깐 ‘____’.",
            "answer": "들렀다",
            "options": ["들렀다", "들렸다"],
            "explanation": "기본형이 '들르다'라서 '들렀다'가 맞습니다. '들렸다'는 '소리가 들리다'의 '들리다'에서 온 말이에요."
        },
        {
            "category": "spelling",
            "question": "내일 다시 연락 ‘____’.",
            "answer": "할게",
            "options": ["할께", "할게"],
            "explanation": "[할께]로 소리 나도 적을 때는 '할게'로 씁니다."
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