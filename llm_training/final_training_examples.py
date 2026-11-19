"""Primary-authored final training additions: 50 families, two factual variants.

Only synthetic training sources are authored here. No evaluation answer is used.
Each complete source clause is paired with its literal memo form and evidence.
"""
import re


def particle(noun, consonant, vowel):
    code = ord(noun[-1]) - 0xAC00
    return noun + (consonant if 0 <= code <= 11171 and code % 28 else vowel)


def memo(text):
    # These transformations are applied only to newly authored, unambiguous facts.
    for ending,replacement in [('들었다.','들음'),('보았다.','봄'),('폈다.','폄'),('꺼냈다.','꺼냄'),
        ('보냈다.','보냄'),('넣었다.','넣음'),('두었다.','둠'),('적었다.','적음'),
        ('세었다.','셈'),('싶었다.','싶었음'),('모른다.','모름'),
        ('했다.','했음'),('였다.','였음'),('었다.','었음'),('았다.','았음'),
        ('있다.','있음'),('없다.','없음'),('한다.','함')]:
        if text.endswith(ending):return text[:-len(ending)]+replacement
    return text


def examples():
    rows=[]
    def add(kind,family,variant,topic,clauses,answer=None,raw=None):
        answer=answer or ' '.join(clauses)
        facts=raw or [memo(s) for s in clauses]
        target=max(100,round(len(answer)/50)*50)
        assert round(target*.8)<=len(answer)<=round(target*1.2),(family,len(answer),target)
        assert re.findall(r'\d+',' '.join(facts))==re.findall(r'\d+',' '.join(clauses))
        rows.append({'id':f'FINAL-{kind}-{family:02d}-{variant}','category':kind,
            'scenario_family_id':f'FINAL-{kind}-{family:02d}','topic':topic,'facts':facts,
            'canonical_clauses':clauses,'answer':answer,'target_chars':target,
            'bounds':[round(target*.8),round(target*1.2)],'synthetic':True,
            'independent_human_review':False,'author':'primary_assistant_source_controlled',
            'authoring_method':'Explicit source facts first; two planned/completed or role/scope variants. Canonical clauses are training-only evidence.'})

    # Report families 1..5: finder and recorder are distinct people.
    for i,(item,n,k,field,negative) in enumerate([
        ('독서실 대여증',15,3,'반납 기한','이용자의 대기 시간'),
        ('공방 신청 카드',28,4,'재료 종류','참가자의 만족도'),
        ('영상 자료 표지',17,2,'상영 연도','영상의 화질'),
        ('기록물 보관표',34,5,'분류 번호','기록물의 보존 상태'),
        ('도구 대여표',26,6,'보관 칸','도구의 작동 상태')],1):
        base=[f'담당자는 {item} {n}개를 원본과 대조했다.',f'{k}개에는 {field} 정보가 없었다.']
        add('report',i,'A',item+'의 누락 기록',base+[
            f'다른 직원은 원본에서 해당 {field} 정보를 찾아냈다.',
            f'담당자는 찾아낸 정보를 별도 메모에 적었다.',
            f'아직 {item}에 정보를 옮겨 적지 않았다.',f'{particle(negative,"은","는")} 평가하지 않았다.'])
        add('report',i,'B',item+'의 실제 보완',base+[
            f'담당자는 원본에서 해당 정보를 찾아 {k}개 항목에 실제로 기입했다.',
            f'다른 직원은 보완된 {k}개 항목을 원본과 다시 대조했다.',
            '보완된 정보는 모두 원본과 같았다.',f'{particle(negative,"은","는")} 평가하지 않았다.'])

    # Report families 6..10: sample observations cannot become whole-group results.
    for i,(item,n,checked,missing,field) in enumerate([
        ('악기 케이스',36,12,3,'물품 번호'),('전시 상자',30,10,2,'작품 이름'),
        ('체육 용품 통',42,14,4,'보관 장소'),('도서 꾸러미',27,9,2,'분류 이름'),
        ('촬영 장비 함',24,8,3,'대여 날짜')],6):
        add('report',i,'A',item+'의 부분 점검',[
            f'점검자는 {item} {n}개 중 앞줄 {checked}개만 확인했다.',
            f'확인한 앞줄에서 {particle(field,"이","가")} 없는 항목은 {missing}개였다.',
            f'나머지 {n-checked}개는 조사하지 않았다.',
            f'점검자는 누락된 {missing}개 항목의 위치를 기록했다.',
            f'전체 {n}개에 누락이 {missing}개뿐이라고 단정하지 않았다.'])
        total=missing+2
        add('report',i,'B',item+'의 전체 점검',[
            f'점검자는 {item} {n}개를 모두 확인했다.',
            f'전체에서 {particle(field,"이","가")} 없는 항목은 {total}개였다.',
            f'점검자는 해당 {total}개 항목의 위치를 기록했다.',
            '관리자에게 표기 보완을 제안했지만 아직 수정하지 않았다.',
            '내용물의 사용 가능 상태는 시험하지 않았다.'])

    # Report families 11..15: anonymous receipt and explicit receipt stay distinct.
    for i,(item,n,first,day1,day2) in enumerate([
        ('천 가방',37,22,'월요일','화요일'),('안전 조끼',26,15,'수요일','목요일'),
        ('공연 의상',32,18,'금요일','다음 월요일'),('도화지 묶음',23,14,'화요일','수요일'),
        ('실습 앞치마',41,24,'목요일','금요일')],11):
        add('report',i,'A',item+'의 날짜별 수령',[
            f'빌려준 {item} {n}개 중 {day1}에 {first}개를 돌려받았다.',
            f'나머지 {n-first}개는 {day2}에 돌려받았다.',
            '기록자는 받은 날짜별로 물품 번호를 나누어 적었다.',
            f'최종 기록에서 {n}개 번호가 모두 확인됐다.',
            '세탁 횟수와 다음 대여 가능 여부는 조사하지 않았다.'])
        add('report',i,'B',item+'의 한 날짜 수령',[
            f'물품 수령자는 빌려준 {item} {n}개를 모두 {day1}에 돌려받았다.',
            '별도의 기록자는 수령자가 받은 물품 번호를 적었다.',
            f'최종 기록에서 {n}개 번호가 모두 확인됐다.',
            f'{day2}에 나누어 받은 것으로 기록하지 않았다.',
            '세탁 횟수와 다음 대여 가능 여부는 조사하지 않았다.'])

    # Report families 16..20: conditional publication is different from publication.
    for i,(item,n,k,field) in enumerate([
        ('견학 안내문',11,2,'집합 장소'),('연습실 공지',16,3,'사용 시각'),
        ('수업 준비 카드',22,4,'재료 이름'),('전시 관람 안내',14,2,'입장 순서'),
        ('봉사 모임 공지',18,3,'담당 부서')],16):
        add('report',i,'A',item+'의 게시 대기',[
            f'작성자는 {item} {n}장을 준비했다.',
            f'동료는 {k}장에 {field} 정보가 없다는 점을 기록했다.',
            f'작성자는 누락된 {k}장을 보완해 다시 출력했다.',
            '관리자가 문구를 확인하면 게시할 계획이다.',
            '관리자의 확인 답은 아직 없으며 실제로 게시하지 않았다.',
            '이용자 반응은 조사하지 않았다.'])
        add('report',i,'B',item+'의 게시 완료',[
            f'작성자는 {item} {n}장을 준비했다.',
            f'동료는 {k}장에 {field} 정보가 없다는 점을 기록했다.',
            f'작성자는 누락된 {k}장을 보완해 다시 출력했다.',
            '관리자는 보완된 문구를 확인했다고 답했다.',
            '작성자는 확인 답을 받은 뒤 안내문을 실제로 게시했다.',
            '이용자 반응은 조사하지 않았다.'])

    # Report families 21..25: actual transmission and receipt are separate facts.
    for i,(item,n,k,field) in enumerate([
        ('자원봉사 명단',35,4,'희망 시간'),('장비 신청표',27,3,'사용 장소'),
        ('합주 참가표',31,5,'연습 날짜'),('강좌 신청 명단',46,6,'연락 방법'),
        ('방문 예약표',39,2,'방문 목적')],21):
        base=[f'검토자는 {item} {n}개 항목을 확인했다.',f'{k}개 항목에는 {particle(field,"이","가")} 없었다.',
              f'검토자는 누락된 {k}개 항목의 번호를 별도 메모에 적었다.']
        add('report',i,'A',item+'의 전달 준비',base+[
            '메모를 담당자에게 보낼 계획이지만 아직 보내지 않았다.',
            '원본 명단은 아직 수정하지 않았다.','이용자의 불편은 조사하지 않았다.'])
        add('report',i,'B',item+'의 실제 전달',base+[
            '검토자는 메모를 담당자에게 문자로 실제로 보냈다.',
            '담당자가 받았다는 답은 아직 없다.','원본 명단은 아직 수정하지 않았다.',
            '이용자의 불편은 조사하지 않았다.'])

    # Free-writing families 1..5: already sent messages never become future wishes.
    for i,(event,detail) in enumerate([
        ('친구가 악보의 박자를 천천히 짚어 준 일','박자를 나누어 설명한 부분'),
        ('동료가 촬영 순서를 차분히 알려 준 일','기기를 켜는 순서를 알려 준 부분'),
        ('친구가 낯선 길의 방향을 설명해 준 일','갈림길을 따로 짚어 준 부분'),
        ('동료가 자료 찾는 법을 알려 준 일','폴더 이름을 함께 읽어 준 부분'),
        ('친구가 종이 접는 순서를 보여 준 일','모서리를 맞추는 법을 보여 준 부분')],1):
        base=[event+'이 고마웠다.','그 자리에서는 고맙다는 말을 하지 못했다.']
        add('free_writing',i,'A','나중에 전한 구체적인 고마움',base+[
            '집에 돌아온 뒤 도움이 된 내용을 메시지로 실제로 전했다.',
            detail+'이 도움이 됐다고 적었다.','답장은 아직 받지 못했다.',
            '고마운 마음을 구체적인 말로 전하고 싶었다.'])
        add('free_writing',i,'B','아직 보내지 않은 고마움',base+[
            detail+'이 도움이 됐다는 문장을 공책에 적었다.',
            '그 문장은 아직 메시지로 보내지 않았다.','언제 보낼지는 정하지 않았다.',
            '고마운 마음을 구체적인 말로 전하고 싶었다.'])

    # Free-writing families 6..10: unfolded and still-folded states are different.
    for i,(paper,side,other) in enumerate([
        ('얇은 지도 종이','왼쪽','오른쪽'),('보라색 포장지','아래쪽','위쪽'),
        ('무늬가 있는 편지지','오른쪽','왼쪽'),('공연 안내 종이','위쪽','아래쪽'),
        ('그림이 없는 엽서','왼쪽','오른쪽')],6):
        common=[f'{paper}를 책상에 놓았다.']
        add('free_writing',i,'A','다시 편 모서리',common+[
            f'{side} 모서리를 한 번 접었다가 다시 폈다.',f'{other} 모서리에는 손대지 않았다.',
            '다시 편 자리에는 가는 선이 남아 있었다.','접었던 일을 지우지 않아도 된다고 생각했다.',
            '이 종이를 다음에 어디에 쓸지는 정하지 않았다.'])
        add('free_writing',i,'B','접힌 채로 둔 모서리',common+[
            f'{side} 모서리를 한 번 접고 펼치지 않은 채 두었다.',f'{other} 모서리에는 손대지 않았다.',
            '접힌 모양을 잠깐 더 보고 싶었다.','지금 당장 모양을 바꿀 필요는 없다고 생각했다.',
            '이 종이를 다음에 어디에 쓸지는 정하지 않았다.'])

    # Free-writing families 11..15: partial progress is not whole completion.
    for i,(task,n,k,detail) in enumerate([
        ('사진 분류',8,3,'풍경 사진'),('재료 상자 정리',7,2,'종이가 든 상자'),
        ('악보 표시',6,2,'첫 부분의 악보'),('서랍 정리',5,1,'가장 위의 작은 칸'),
        ('책갈피 만들기',9,4,'초록색 종이 책갈피')],11):
        add('free_writing',i,'A',task+'의 작은 진전',[
            f'{task}에서 처리할 항목은 {n}개였다.',f'그중 {k}개만 마쳤다.',
            f'마친 것은 {detail}에 해당하는 항목이었다.',f'나머지 {n-k}개는 아직 남아 있었다.',
            '일부를 마친 것과 전체를 끝낸 것을 구분해 생각했다.','작은 진전도 그대로 인정하고 싶었다.'])
        add('free_writing',i,'B',task+'를 모두 마친 날',[
            f'{task}에서 처리할 항목은 {n}개였다.',f'먼저 {detail}에 해당하는 {k}개를 마쳤다.',
            f'나머지 {n-k}개도 그날 모두 마쳤다.','항목마다 완료 표시를 남겼다.',
            '처음 끝낸 부분과 나중에 끝낸 부분을 구분해 생각했다.','일의 순서를 있는 그대로 기억하고 싶었다.'])

    # Free-writing families 16..20: thought labels and desires remain distinct.
    for i,(source,heard,observed) in enumerate([
        ('분수의 물소리','낮에 녹음한 물소리를 저녁에 다시 들었다.','녹음할 때 분수 안쪽을 들여다보지는 않았다.'),
        ('낙엽의 바람 소리','공원에서 녹음한 바람 소리를 밤에 다시 들었다.','녹음할 때 나무 뒤쪽을 보지는 않았다.'),
        ('연습실의 종소리','연습실에서 녹음한 종소리를 집에서 다시 들었다.','종을 직접 만지지는 않았다.'),
        ('먼 기차의 소리','멀리서 녹음한 기차 소리를 저녁에 다시 들었다.','기차 안에 타 보지는 않았다.'),
        ('복도의 발소리','복도에서 녹음한 발소리를 집에서 다시 들었다.','소리를 낸 사람의 얼굴은 보지 못했다.')],16):
        clauses=[heard,observed,'공책에는 들은 소리만 짧게 적었다.',
            '직접 본 것과 들은 것을 구분해 생각했다.','녹음에 담기지 않은 장면은 짐작해서 적지 않았다.',
            '당장 결론을 붙이지 않고 잠깐 그대로 두고 싶었다.']
        raw=[memo(x) for x in clauses];raw[3]='화자의 생각: 직접 본 것과 들은 것을 구분하는 마음'
        add('free_writing',i,'A',source+'를 다시 들으며',clauses,raw=raw)
        wanted=[heard,observed,'공책에는 들은 소리만 짧게 적었다.',
            '직접 본 것과 들은 것을 구분하고 싶었다.','녹음에 담기지 않은 장면은 짐작해서 적지 않았다.',
            '당장 결론을 붙이지 않고 잠깐 그대로 두고 싶었다.']
        raw=[memo(x) for x in wanted];raw[3]='당시 마음: 직접 본 것과 들은 것을 구분하고 싶었음'
        add('free_writing',i,'B',source+'에 남은 생각',wanted,raw=raw)

    # Free-writing families 21..25: a pause does not imply an invented restart.
    for i,(hobby,tool,container) in enumerate([
        ('점토 작업','모형 도구','나무 상자'),('붓글씨 연습','붓','천 주머니'),
        ('우쿨렐레 연습','우쿨렐레','케이스'),('사진 연습','카메라','보관 가방'),
        ('자수 연습','자수 도구','작은 통')],21):
        add('free_writing',i,'A',particle(hobby,'을','를')+' 잠시 쉬며',[
            f'시간 여유가 부족해 {particle(hobby,"을","를")} 한동안 쉬기로 했다.',
            f'{particle(tool,"은","는")} {container}에 넣어 보관했다.','하던 작업의 기록은 책상 위에 그대로 두었다.',
            '다시 시작할 날짜는 정하지 않았다.','이번 휴식이 영원한 포기인지는 아직 모른다.',
            '쉬는 시간을 서둘러 이름 붙이고 싶지는 않았다.'])
        add('free_writing',i,'B',particle(hobby,'을','를')+' 다시 시작하며',[
            f'한동안 쉬었던 {particle(hobby,"을","를")} 그날 다시 시작했다.',f'{container}에서 {particle(tool,"을","를")} 꺼냈다.',
            '책상 위에 남겨 두었던 작업 기록을 다시 읽었다.','처음부터 모든 작업을 끝내지는 않았다.',
            '그날 실제로 한 부분만 기록에 적었다.','다시 시작한 일을 크게 꾸미지 않고 남기고 싶었다.'])
    assert len(rows)==100 and len({r['scenario_family_id'] for r in rows})==50
    assert len({r['answer'] for r in rows})==100
    return rows
