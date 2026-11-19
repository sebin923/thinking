"""One fresh 1,459-row run and a frozen, same-prompt Ver3 comparison.

All model work stays local. Existing data, weights and model selection are
read-only. The run supervisor temporarily pauses and restores the exact local
model API; it never applies the newly trained adapter to the web application.
"""
from collections import Counter, defaultdict
from datetime import datetime, timezone
from pathlib import Path
import argparse
import gc
import hashlib
import json
import os
import random
import statistics
import subprocess
import sys
import time
import urllib.request

import refine_over1000 as data

ROOT=Path(__file__).resolve().parent
PROJECT=ROOT.parent
OUT=ROOT/'outputs/curated_1459_study_20261119'
DATA=data.DEST
MODEL='Qwen/Qwen3.5-2B'
VER3=ROOT/'outputs/qwen35_epoch_study_20261117_155715_800799/epoch_1/adapter'
sha=data.sha
digest=data.digest
lines=data.read_rows


def now():return datetime.now(timezone.utc).isoformat()


def save(path,value):
    path.parent.mkdir(parents=True,exist_ok=True)
    temporary=path.with_suffix(path.suffix+'.tmp')
    temporary.write_text(json.dumps(value,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
    temporary.replace(path)


def fresh_cases():
    cases=[]
    def add(genre,topic,facts,target=150):
        cases.append({'id':f'N-{len(cases)+1:02d}','split':'fresh','genre':genre,'topic':topic,
            'facts':facts.split('|'),'bounds':[round(target*.8),round(target*1.2)],'source_context':''})
    add('report','팸플릿 발행 월 확인','검토자는 작은 박물관 팸플릿 18부를 원본 파일과 대조함|5부에는 발행 월이 빠져 있었음|동료가 원본 파일에서 발행 월을 찾음|검토자는 누락된 팸플릿 번호만 메모에 적음|아직 팸플릿을 수정하지 않음|방문객의 이해도는 조사하지 않음')
    add('report','촬영 목록의 날짜','기록자는 촬영 목록 26건을 확인함|9건의 촬영 날짜가 비어 있었음|빈 날짜가 어떤 날인지는 확인하지 못함|기록자는 누락된 항목의 번호를 담당자에게 실제로 보냄|담당자가 받았다는 답은 아직 없음|사진의 촬영 장소는 이번에 확인하지 않음')
    add('report','번호 카드 반납','빌려준 번호 카드 12장 중 첫날 7장을 돌려받음|나머지 5장은 다음 날 돌려받음|기록 담당자는 받은 날짜별로 카드 번호를 나누어 적음|기록에서 12장의 번호를 모두 확인함|카드를 받은 사람의 이름은 기록하지 않음|카드의 마모 상태는 조사하지 않음')
    add('report','작품명 표기의 수정','점검자는 전시 표찰 14개의 작품명을 원본과 대조함|2개의 작품명에 오자가 있었음|점검자가 두 오자를 직접 고침|다른 검수자가 수정된 작품명을 원본과 다시 비교함|두 작품명이 원본과 같았음|관람 동선에 미치는 영향은 확인하지 않음')
    add('report','신청서 전달의 조건','담당자는 체험 신청서 23장을 제출 순서대로 정리함|연락처가 빈 신청서는 4장이었음|빈 연락처를 다른 자료로 추정해 채우지 않음|담당자는 네 신청서의 번호만 별도 표에 적음|관리자에게서 접수 가능하다는 확인을 받은 뒤에만 원본을 넘길 예정임|아직 그 확인은 받지 못했고 원본도 넘기지 않음',200)
    add('report','안내판 확인 범위','조사자는 건물 1층 안내판 8개를 확인함|확인한 것은 층별 시설 이름과 화살표 방향임|같은 층의 실제 출입문 표기와 비교했을 때 한 안내판의 시설 이름이 달랐음|조사자는 다른 이름과 안내판 위치를 사진으로 남김|화살표가 가리키는 경로를 끝까지 걸어 보지는 않음|관리자에게 확인 뒤 수정 여부를 정하자고 제안함|안내판을 직접 고치지는 않음',200)
    add('report','공연 자료의 파일 상태','편집자는 공연 소개 파일 16개를 열어 제목과 수정 시각을 기록함|파일 3개는 같은 제목이지만 수정 시각이 달랐음|편집자는 세 파일을 하나로 합치거나 지우지 않음|실제 최종본이 무엇인지는 제작자가 확인할 예정임|편집자는 서로 다른 세 수정 시각을 제작자에게 보냄|제작자의 답은 아직 오지 않음|인쇄 상태와 관객 반응은 점검 대상에 포함하지 않음',200)
    add('report','임시 보관 기준안','가상 팀의 공용 재료를 임시 보관할 기준안을 작성함|현재 사용 중인 재료와 사용 예정인 재료를 다른 칸으로 나누는 안임|담당자가 재료를 옮기기 전에 사용 상태를 확인하도록 제안함|실제 재료 이동은 하지 않음|기준안을 채택했는지도 아직 확인하지 못함|보관 공간이 줄었다는 결과는 측정하지 않음',200)
    add('report','포장 상자의 표식 대조','행사 준비자는 선물 상자 32개의 번호표를 배치 목록과 대조함|배치 목록에는 상자 번호와 전달할 장소가 서로 다른 칸에 적혀 있었음|준비자는 상자 번호를 장소 번호로 읽지 않도록 두 칸의 제목부터 확인함|상자 3개에는 전달 장소가 빠져 있어 그 상자의 번호를 별도 종이에 적음|다른 직원이 원본 접수 기록을 찾아 세 장소를 확인함|준비자는 확인된 장소를 배치 목록에만 보완했고 상자의 번호표는 아직 고치지 않음|포장을 마친 상자는 탁자 왼쪽에 두고 미확인 상자와 섞지 않음|확인자는 보완한 세 목록 항목을 원본 접수 기록과 다시 비교했고 모두 같았음|실제 전달은 다음 날 담당자가 맡을 예정이며 지금 전달을 완료한 상자는 없음|이 점검에서는 포장 안의 물품 수와 선물에 대한 반응은 조사하지 않음',350)
    add('report','영상 자막 파일의 정리','편집자는 상영회 영상의 자막 파일 11개를 파일명과 버전 번호로 정리함|같은 이름의 파일이라도 버전 번호가 다르면 별도 줄에 남겨 이전 파일을 덮어쓰지 않음|자막 담당자는 바뀐 문장 6개의 시작 시각과 끝 시각을 원본 작업표와 대조함|그중 시작 시각이 다른 2개 문장은 작업표에 맞춰 자막 파일에서 수정함|다른 검토자는 수정된 두 문장을 다시 열어 시각이 작업표와 같다는 것을 확인함|이전 버전은 보관 폴더로 옮기고 상영용 폴더에는 확인한 최종 파일만 둠|편집자는 두 폴더의 경로와 확인한 버전 번호를 인계 문서에 함께 적음|영상 전체를 상영 장비에서 재생한 것은 아니므로 전체 자막의 동기화가 맞는지는 아직 모름|실제 상영은 다음 주 예정이며 관객이 자막을 읽기 쉬운지는 조사하지 않음',350)
    add('cover_letter','대여 기록 대조','나는 동아리의 책 대여 기록 14건을 반납표와 대조함|날짜가 다른 2건의 번호를 기록함|동료는 이용자에게 날짜를 다시 물어볼 계획임|동료는 아직 연락하지 않음|나는 실제 책의 훼손 상태는 확인하지 않음|내가 확인한 내용과 동료의 계획을 구분해 설명하려 함')
    add('cover_letter','자료 전달 뒤의 상태','나는 설명회 자료를 항목별로 정리함|빠진 안내 항목 3개를 담당자에게 문자로 보냄|문자는 이미 보냈지만 담당자의 답은 아직 없음|담당자가 자료를 수정했는지는 모름|확인한 일과 이후 처리 상태를 구분해 알리는 태도를 중요하게 생각함')
    add('cover_letter','팀 발표의 역할','나는 팀 발표에서 표의 축 이름을 확인하는 일을 맡음|표의 단위를 바로잡음|다른 팀원은 발표 순서와 대본을 정함|나는 최종 발표에는 참석하지 못함|전체 팀의 점수는 확인하지 못함|내가 실제로 맡은 부분을 정확히 설명하는 태도가 중요하다고 생각함')
    add('cover_letter','분류를 보류한 항목','나는 신청 내용을 세 종류로 나누어 정리함|어느 종류인지 불분명한 항목 2개는 따로 남김|임의로 한 종류에 넣지 않고 작성자에게 확인을 요청함|확인 답은 아직 오지 않음|불확실한 상태를 구분하는 것이 내 강점이라고 생각함')
    add('cover_letter','공연 준비 자료의 범위','나는 공연 준비 모임에서 장면별 준비물 목록을 정리함|목록의 물건 이름은 대본에 적힌 이름과 대조함|실제 물건을 창고에서 찾아본 사람은 동료임|동료가 찾지 못한 3개는 준비 완료로 표시하지 않음|나는 미확인 항목을 담당자에게 전달할 계획이지만 아직 보내지 않음|공연 당일에는 이 일에 참여할 예정이 없음|문서에서 확인한 범위와 실제 준비 상태를 구별하려고 함',200)
    add('cover_letter','길 안내 초안 검토','나는 산책 안내 초안의 표기를 확인함|직접 가 본 곳은 도서관 입구와 공원 정문 두 곳뿐임|나머지 장소는 모임에서 받은 목록을 참고함|직접 확인한 표기와 전달받은 표기를 다른 칸에 적음|모든 길의 현재 통행 상태는 조사하지 않음|팀에서 지도를 최종 채택했는지는 아직 모름|정보가 어디에서 왔는지 드러내는 태도를 중요하게 생각함',200)
    add('cover_letter','가상 전시 기획 과제','이 내용은 가상 전시 기획을 연습한 사례임|나는 작품 설명의 출처가 있는 부분과 없는 부분을 나눔|출처가 없는 설명은 확인 필요라고 표시함|동료는 전시 제목을 정하는 일을 맡음|나는 관람객을 모집하거나 실제 전시를 열지 않음|설명의 출처 표시가 정확한지 다시 확인할 계획임|연습한 일과 실제 운영 경험을 구분해 말하려 함',200)
    add('cover_letter','문의 기록의 정리','나는 동아리 행사 문의를 제출 시각에 따라 정리함|확인된 답이 있는 문의와 담당자에게 물어봐야 할 문의를 나눔|확인하지 못한 질문에는 답을 추측해 넣지 않음|담당자는 남은 질문에 다음 날 답할 계획이라고 말함|아직 그 답을 받지 못함|전체 문의 해결률은 계산하지 않음|현재 답할 수 있는 범위를 분명히 알리는 태도를 중요하게 생각함',200)
    add('cover_letter','인쇄물 수정 내역을 남긴 경험','나는 모임 소개 책자의 수정 사항을 정리하는 일을 맡음|작품 번호와 설명의 연결이 다른 곳을 찾아 원본 목록과 대조했고 세 항목의 번호를 고침|책자에 나온 작가 이름의 철자를 확인한 사람은 동료이며 나는 그 확인을 대신했다고 쓰지 않음|동료가 확인한 철자는 수정 목록의 별도 칸에 적어 내 수정과 구분함|같은 페이지에서 바뀐 표현은 수정 전과 수정 후를 나란히 남겨 담당자가 비교할 수 있게 함|담당자가 읽어 달라고 요청한 두 부분은 원래 문장을 다시 읽고 뜻이 달라지지 않았는지 살핌|수정한 파일과 수정 목록은 담당자에게 실제로 보냈지만 인쇄 승인 답은 아직 받지 못함|이후 인쇄나 배포 작업에는 참여하지 않았고 독자의 반응도 확인하지 못함|이 경험에서는 내가 직접 확인한 부분과 전달받은 부분을 구분하며 기록을 남기는 태도를 실천함',350)
    add('cover_letter','신청 자료의 서로 다른 상태','나는 워크숍 신청 자료를 정리하며 제출된 신청서와 참가 확정 명단을 구분함|신청서를 냈다는 이유만으로 참가가 확정된 것으로 표시하지 않고 확정 안내가 있는지 먼저 확인함|확정 안내가 없는 신청서 다섯 장은 대기 상태로 두고 접수 시각과 연락 방법을 기록함|연락처가 없는 두 신청서는 임의로 보완하지 않고 담당자에게 별도로 전달함|실제 참가 여부를 결정한 사람은 운영자이며 나는 명단을 정리한 범위에서만 일을 맡음|동료는 확정된 참가자에게 준비물 안내를 보낼 계획이지만 그 안내는 아직 발송하지 않음|나는 정리한 두 목록의 항목 수를 다시 세어 원본 신청서 수와 맞는지 대조함|실제 워크숍 진행과 출석 확인에는 참여하지 않았고 행사 만족도도 조사하지 않음|서로 다른 진행 상태를 하나로 합치지 않고 확인된 상태를 정확히 전달하는 태도를 중요하게 생각함',350)
    add('speech','재료 봉투 준비 수량','체험에 사용할 재료 봉투는 24개 준비함|봉투 안의 작은 부품 수는 아직 세지 않음|참가자에게 봉투를 나눠 주는 일은 모임이 시작된 뒤 할 예정임|아직 참가자에게 준 봉투는 없음|봉투를 받으면 겉면의 색을 확인해 주세요.|색이 다른 봉투를 받았으면 진행자에게 알려 주세요.')
    add('speech','원본 전달 전에 받을 답','자료를 받으신 분은 받았다는 답을 보내 주세요.|그 답을 받은 뒤에만 원본 사진을 넘길 예정임|질문만 보내신 경우에는 수령 확인으로 처리하지 않음|아직 원본 사진을 보낸 사람은 없음|인쇄를 허락한 것은 아니며 사진 공개 여부는 따로 물어봐야 함')
    add('speech','의견 쪽지의 선택','의견 쪽지를 작성할지는 참가자가 선택할 수 있음|쪽지를 쓰지 않아도 활동에 계속 참여할 수 있음|아직 누구의 작성 여부도 확인하지 않음|이름은 적지 않아도 됨|모인 쪽지는 다음 모임 전에 진행자가 읽을 예정임|이번에 서로의 의견을 점수로 비교하지는 않을 예정임')
    add('speech','다음 모임 준비물','다음 모임에는 작은 가위를 가져와야 함|이미 가위를 갖고 있어야 한다는 뜻은 아님|빌릴 가위가 필요한 분은 전날까지 진행자에게 알려 주세요.|진행자는 빌릴 수 있는 수량을 확인할 예정임|아직 대여 가능하다는 답은 없음|종이는 모임에서 나누어 드릴 예정임')
    add('speech','활동 순서의 안내','오늘 활동은 오후 3시에 시작할 예정임|첫 활동은 설명 카드를 읽는 일이며 약 15분으로 계획함|그다음에는 짝과 질문 두 개를 나눌 예정임|발언하고 싶지 않은 분은 질문을 종이에 적어 주셔도 됨|진행자가 시간을 바꾸게 되면 칠판에도 수정 시각을 적겠음|이번 안내는 계획이며 아직 실제로 진행한 결과는 없음|각 활동이 끝나면 사용한 카드를 탁자 위에 두어 주세요.',200)
    add('speech','교환한 책을 소개하는 방법','책을 교환한 뒤에는 직접 읽은 부분 한 곳을 먼저 소개해 주세요.|아직 읽지 않은 뒷부분은 짐작해서 줄거리를 만들지 마세요.|읽기 전의 예상과 실제 읽고 확인한 내용을 다른 문장으로 말할 수 있음|오늘 소개 여부는 각자 선택할 수 있음|진행자는 소개한 책의 제목만 목록에 남길 예정임|발표 횟수로 참여도를 평가하지는 않겠음|이 방법으로 독서량이 늘었는지는 아직 조사하지 않음',200)
    add('speech','인용 문구 사용의 허락','이번 자료집에는 참여자가 남긴 “잠깐 멈춘 자리”라는 문구를 그대로 싣고자 함|허락받은 것은 이 문구 공개에 한정됨|그때 찍은 사진을 공개해도 된다는 허락은 아직 받지 않음|이름은 작성자가 원하는 표기를 확인한 뒤 넣을 예정임|문구의 뜻을 풀어 설명할 때에는 따옴표 밖에 쓰겠음|작성자가 공개 의사를 바꾸면 인쇄 전에 다시 확인하겠음',200)
    add('speech','짧은 시험의 결과와 한계','지난 준비 모임에서 안내 카드 네 장을 두 사람에게 읽어 달라고 부탁함|두 사람 모두 마지막 안내 칸을 찾았음|찾는 데 걸린 시간은 재지 않음|다른 참가자도 쉽게 찾는지는 아직 확인하지 않음|오늘은 두 사람이 실제로 짚은 칸의 위치만 보여 드리겠음|모든 사람에게 같은 효과가 있었다고 설명하지 않겠음|카드를 더 살펴볼 분은 끝난 뒤 진행자에게 알려 주세요.',200)
    add('speech','서로 다른 자료를 함께 읽는 순서','오늘은 같은 장소를 그린 지도 두 장을 나란히 놓고 표시가 다른 부분을 살펴보겠음|첫 지도는 지난주에 만든 초안이고 두 번째는 어제 직접 걸어 본 구간만 보완한 지도임|새 지도에 선이 없는 길은 존재하지 않는 길이 아니라 이번에 확인하지 않은 범위임|먼저 두 지도에서 출발점이 같은 곳을 찾고 그다음에 직접 확인한 구간의 실선을 읽어 주세요.|길 이름이 다르게 적힌 곳은 현장 표지판을 다시 볼 질문으로 남기고 지금 임의로 한쪽을 정하지 마세요.|진행자는 참여자가 남긴 질문을 모으되 이름을 공개할지는 각각 물어볼 예정임|지도에 개인의 집 위치나 이동 시간을 적어 내야 하는 것은 아니며 질문 작성 여부도 선택할 수 있음|아직 두 지도로 길을 안내한 결과는 없으므로 실제 이동이 쉬워졌다고 말하지 않겠음|활동 뒤에는 원본 두 장을 그대로 보관하고 새로 확인할 내용만 별도 종이에 적겠음',350)
    add('speech','작업 사진을 설명할 때의 구분','이번에는 작업하기 전과 뒤에 찍은 사진을 함께 보며 바뀐 부분을 설명해 보겠음|먼저 사진 아래에 적힌 촬영 시각과 작품 번호를 읽고 같은 작품인지 확인해 주세요.|첫 사진에는 부품을 붙이기 전 모습이 있고 두 번째 사진에는 붙인 뒤의 모습이 담겨 있음|사진만 보고 접착제가 마르는 데 걸린 시간까지 알 수 있는 것은 아니므로 확인하지 않은 시간은 적지 마세요.|사진 밖에서 한 작업이 있다면 직접 기록해 둔 내용이 있을 때에만 별도 문장으로 설명할 수 있음|오늘은 두 사람씩 짝을 지어 보이는 차이 두 개와 아직 알 수 없는 점 한 개를 나누어 적겠음|친구가 고른 차이를 자기 관찰처럼 대신 말하지 말고 누가 무엇을 짚었는지 구분해 주세요.|적은 종이를 제출할지는 각자 선택할 수 있으며 제출하지 않아도 함께 사진을 볼 수 있음|이 활동을 실제 모임에서 시행한 적은 아직 없으며 관찰 능력이 좋아졌다는 결과도 측정하지 않음',350)
    add('free_writing','창틀에 남긴 소리 기록','창가에서 녹음한 빗소리를 저녁에 다시 들음|녹음할 때 창문을 열지는 않음|공책에는 들린 소리만 짧게 적음|밖의 길을 직접 보지는 못함|직접 본 것과 들은 것을 섞지 않고 싶었음|다음 줄은 비워 둠')
    add('free_writing','친구가 옮긴 종이배','나는 흰 종이배를 접어 책상 가운데에 놓음|친구는 노란 종이배를 창가로 옮김|나는 친구의 종이배를 접거나 옮기지 않음|흰 종이배의 앞부분만 다시 펼침|다른 사람의 방법을 바로 판단하고 싶지는 않았음|그다음에 쓸 종이 색은 정하지 않음')
    add('free_writing','늦게 보낸 위치 안내','현장에서는 상자를 둔 위치를 동료에게 말하지 못함|집에 와서 위치를 문자로 보냄|문자에는 선반 번호 6번도 적음|동료의 답은 아직 오지 않음|내일 답부터 확인할 계획임|이미 한 일과 기다리는 일을 나누어 생각함')
    add('free_writing','여백을 남긴 공책','처음에는 빈 줄에 그림을 더 넣으려 함|접어 둔 초안을 다시 보고 그림을 넣지 않기로 함|실제로 마지막 줄은 비워 둠|공책은 아직 누구에게 보여 주지 않음|빈 줄을 모두 채워야 하는 것은 아니라고 생각함|보여 줄 날짜는 정하지 않음')
    add('free_writing','사진을 넣은 투명 파일','서랍에서 예전에 찍은 사진 두 장을 꺼냄|한 장의 뒷면에는 장소 이름이 적혀 있고 다른 한 장에는 날짜만 적혀 있었음|사진의 순서를 짐작해 새 번호를 붙이지 않음|두 장을 같은 투명 파일의 다른 칸에 넣음|적혀 있는 글자는 지우지 않음|기억나지 않는 순서보다 지금 남은 기록을 먼저 보려 했음|파일을 닫고 서랍에 다시 넣음',200)
    add('free_writing','엽서의 모서리를 펴며','책 사이에 넣어 둔 엽서를 꺼냄|오른쪽 모서리가 접혀 있었고 뒷면에는 짧은 인사가 남아 있었음|모서리를 한 번 폈지만 작은 선은 그대로 보였음|인사를 쓴 사람에게 새 답장을 쓰지는 않음|엽서는 버리지 않고 공책 안에 보관함|새 글을 더 쓰지 않아도 남은 말을 읽을 수 있다고 생각함|다시 꺼낼 날은 정하지 않음',200)
    add('free_writing','멈춘 연습의 표시','손목이 피곤해 종이 모형 만들기를 그날 멈춤|모형의 날개는 이미 접었고 받침은 아직 붙이지 않음|끝낸 부분 옆에는 작은 점을 찍음|남은 재료는 상자에 넣어 둠|다음 날 계속할지는 아직 정하지 않음|쉬기로 한 일을 영원히 그만둔 일로 부르고 싶지는 않았음|모형은 버리지 않고 책상 위에 둠',200)
    add('free_writing','번호만 남은 책갈피','오래된 책에서 책갈피 하나를 발견함|책갈피에는 27이라는 숫자만 적혀 있었음|누가 썼는지와 무엇을 세던 숫자인지는 알지 못함|나는 새 설명을 덧붙이지 않음|숫자를 지우지도 않고 책갈피를 다른 쪽에 끼우지도 않음|모르는 뜻을 서둘러 정하지 않아도 된다고 생각함|책은 원래 있던 선반에 돌려놓음',200)
    add('free_writing','접시를 놓을 자리를 바꾸며','친구와 작은 전시를 정리한 뒤 탁자 위에 접시 세 개가 남아 있었음|나는 빈 접시 두 개를 쟁반에 올렸고 친구는 종이가 붙은 접시를 목록과 대조함|종이에 적힌 작품 번호와 보관 상자 번호는 달라 같은 숫자라고 생각해서 옮기지 않음|친구가 읽어 준 목록에서 해당 줄을 찾은 뒤 나는 접시를 둘 상자의 위치만 손가락으로 짚음|실제로 마지막 접시를 상자에 넣은 사람은 친구였고 나는 빈 쟁반을 선반에 올림|탁자에는 종이를 떼어 낸 자국 하나가 남았지만 나는 새 종이로 가리지 않음|목록에 누가 무엇을 옮겼는지 짧게 적고 처음 전시를 준비할 때 찍은 사진도 다시 봄|사진 속에서는 가까워 보이던 물건들이 실제로는 서로 다른 상자로 돌아갔음|정리가 끝났다는 표시를 서둘러 하기보다 마지막으로 남은 번호를 한 번 더 읽고 싶었음',350)
    add('free_writing','다시 읽은 작업 순서','한동안 쉬었던 천 조각 잇기를 다시 시작하려고 상자를 열었음|상자 안에는 크기가 다른 조각 네 개와 전에 쓰던 작업 기록이 함께 들어 있었음|기록에는 두 조각을 이어 놓은 날만 적혀 있었고 나머지를 붙인 날짜는 없었음|나는 없는 날짜를 기억나는 것처럼 채우지 않고 이미 이어진 부분의 가장자리부터 살핌|큰 조각의 실 끝을 정리한 뒤 작은 조각 하나를 옆에 놓아 길이를 비교함|아직 새 조각을 꿰매지는 않았으며 바늘도 천에 꽂지 않은 채 접시에 놓음|그날 기록에는 상자를 열고 길이를 비교한 일만 적어 두어 완성한 것으로 읽히지 않게 함|처음에는 그날 바로 이어 붙이고 싶었지만 남은 순서를 다시 읽은 뒤 실제로는 거기서 손을 멈춤|다시 시작한 일이 작아 보여도 실제로 한 부분만 남기고 싶었고 계속할 날짜는 아직 정하지 않음',350)
    assert len(cases)==40 and Counter(c['genre'] for c in cases)==Counter({g:10 for g in data.GENRE_NAMES})
    return cases


def prepare():
    assert not (OUT/'protocol.json').exists(),'Study already frozen'
    data.verify()
    source=ROOT/'outputs/final_release_20261119'
    pools=[]
    for path in [source/'cases.json',source/'application_v2/fresh_cases.json',source/'regression_protocol.json']:
        v=json.loads(path.read_text(encoding='utf-8'));pools+=v['cases'] if isinstance(v,dict) else v
    wanted=['F-09','RP-N11','A-01','A-04','F-12','F-15','F-16','A-10',
            'F-27','F-29','A-15','A-17','F-39','RW-E-42','A-19','A-24']
    index={c['id']:c for c in pools}
    known=[{k:index[i][k] for k in ('id','genre','topic','facts','bounds')} for i in wanted]
    for c in known:c['split']='known_regression'
    fresh=fresh_cases()
    cases=fresh+known
    training=lines(DATA/'train.jsonl')
    overlaps=data.heldout_conflicts(training,[{'id':c['id'],'category':c['genre'],'facts':c['facts'],'origin':'study'} for c in cases])
    assert not overlaps,('heldout overlap',overlaps)
    for c in cases:
        c['prompt']=data.curated_messages(c['genre'],c['topic'],c['facts'],c['bounds'],bool(c.get('source_context')))
    assert len({digest(c['prompt']) for c in cases})==56
    OUT.mkdir(parents=True,exist_ok=True)
    save(OUT/'inputs.json',cases)
    protected={str(DATA.relative_to(ROOT)/f):sha(DATA/f) for f in ('train.jsonl','valid.jsonl','test.jsonl','manifest.json','curation_ledger.json')}
    protected.update({str(p.relative_to(ROOT)):sha(p) for p in [ROOT/'model_selection.json',source/'selection.json',
        ROOT/'train_qwen35.py',ROOT/'refine_over1000.py',ROOT/'writing_prompts.py',VER3/'adapter_model.safetensors']})
    protocol={'created_utc':now(),'profile':data.PROFILE,'models':['Ver3','Curated1459'],
        'inputs_sha256':sha(OUT/'inputs.json'),'protected_files':protected,'study_script_sha256':sha(Path(__file__)),
        'fresh_count':40,'known_count':16,'per_genre_fresh':10,'per_genre_known':4,
        'train':{'base_model':MODEL,'fresh_from_base':True,'epochs':1,'rows':1459,'learning_rate':2e-5,
            'seed':42,'batch_size':1,'gradient_accumulation_steps':4,'max_tokens':1024,
            'lora_r':8,'lora_alpha':16,'lora_dropout':.05},
        'generation':{'max_new_tokens':512,'do_sample':False,'enable_thinking':False,
            'repetition_penalty':1.0,'no_repeat_ngram_size':0,'batch_size':4,'seed':42},
        'gate':{'fresh_critical_errors':0,'known_critical_errors':0,'naturalness_min':8.0,
            'per_genre_naturalness_min':7.5,'length_compliance_min':.85,'all_ended_with_eos':True,
            'genre_naturalness_not_lower_than_ver3':True,'mean_faithfulness_not_lower_than_ver3':True},
        'rubric':{'naturalness':'0-10. 10 fluent connected prose; 8 minor awkwardness; 6 multiple strained sentences; 4 persistent fragments.',
            'faithfulness':'0-10. 10 essential source facts preserved; 9 minor nuance loss; 7 important omission; <=5 reversal or invented event.',
            'nonrepetition':'0-10. 10 no redundant proposition; 8 one avoidable restatement; 6 repeated restatements.',
            'critical':'Changed or invented actor/event/count/negation/state/condition, or omission changing essential meaning.'},
        'review':'Primary assistant blinded by randomized output IDs; identical same-case text rated once. Not independent human review.',
        'scope':'Fresh 40 scored separately from known 16. Both models use identical curated prompts and decode settings. '
            'Different datasets and training/prompt histories mean this is not a causal test of dataset quantity.',
        'web_policy':'No new adapter application. Restore the previous local API identity after GPU work.',
        'external_teacher_api':False}
    save(OUT/'protocol.json',protocol)
    print('FROZEN:1459 train,40 fresh +16 known,Ver3 and Curated1459',flush=True)


def check_protocol():
    p=json.loads((OUT/'protocol.json').read_text(encoding='utf-8'))
    assert sha(OUT/'inputs.json')==p['inputs_sha256']
    assert sha(Path(__file__))==p['study_script_sha256']
    data.assert_protected(p['protected_files'])
    return p


def train():
    p=check_protocol()
    state_path=OUT/'training_state.json'
    if state_path.exists():raise RuntimeError('Training already started; inspect its state, never silently launch a second run.')
    save(state_path,{'status':'preparing_model','started_utc':now(),'pid':os.getpid(),
        'manifest_sha256':sha(DATA/'manifest.json'),'fresh_from_base':True})
    import train_qwen35 as training
    from transformers import TrainerCallback
    original=training.Trainer
    start=time.monotonic()
    class Progress(TrainerCallback):
        def on_train_begin(self,args,state,control,**kwargs):self.write(state,'training')
        def on_step_end(self,args,state,control,**kwargs):self.write(state,'training')
        def on_log(self,args,state,control,logs=None,**kwargs):
            if logs and 'loss' in logs:self.write(state,'training',loss=logs['loss'])
        def write(self,state,stage,**extra):
            value={'stage':stage,'step':state.global_step,'max_steps':state.max_steps,
                'elapsed_seconds':round(time.monotonic()-start,1),'updated_utc':now(),**extra}
            save(OUT/'progress.json',value)
    class TrackedTrainer(original):
        def __init__(self,*args,**kwargs):
            super().__init__(*args,**kwargs)
            current=json.loads(state_path.read_text(encoding='utf-8'))
            current.update({'run':str(Path(self.args.output_dir).resolve()),'status':'baseline_evaluation'})
            save(state_path,current)
            self.add_callback(Progress())
    training.Trainer=TrackedTrainer
    sys.argv=['train_qwen35.py','--data-dir',str(DATA),'--epochs','1']
    try:
        training.main()
        value=json.loads(state_path.read_text(encoding='utf-8'));run=Path(value['run'])
        metrics=json.loads((run/'metrics.json').read_text(encoding='utf-8'))
        assert metrics['fresh_lora'] is True and metrics['epochs']==1
        assert metrics['data']['train']['count']==1459 and metrics['data']['train']['sha256']==sha(DATA/'train.jsonl')
        assert metrics['training_script_sha256']==p['protected_files']['train_qwen35.py']
        value.update({'status':'completed','completed_utc':now(),'adapter':str(run/'adapter'),
            'adapter_sha256':sha(run/'adapter/adapter_model.safetensors'),'metrics_sha256':sha(run/'metrics.json'),
            'before_loss':metrics['before']['eval_loss'],'after_loss':metrics['after']['eval_loss']})
        save(state_path,value)
        print('CURATED_TRAINING_COMPLETE',json.dumps(value,ensure_ascii=False),flush=True)
    except BaseException as exc:
        value=json.loads(state_path.read_text(encoding='utf-8'));value.update(status='failed',error=repr(exc),failed_utc=now())
        save(state_path,value);raise


def infer():
    protocol=check_protocol()
    state=json.loads((OUT/'training_state.json').read_text(encoding='utf-8'))
    assert state['status']=='completed'
    final=Path(state['adapter']);assert sha(final/'adapter_model.safetensors')==state['adapter_sha256']
    import torch
    from peft import PeftModel
    from transformers import AutoProcessor,Qwen3_5ForConditionalGeneration,set_seed
    from writing_prompts import finish_text
    set_seed(42)
    processor=AutoProcessor.from_pretrained(MODEL,local_files_only=True);tok=processor.tokenizer
    if tok.pad_token_id is None:tok.pad_token=tok.eos_token
    tok.padding_side='left'
    cases=json.loads((OUT/'inputs.json').read_text(encoding='utf-8'))
    base=Qwen3_5ForConditionalGeneration.from_pretrained(MODEL,local_files_only=True,
        dtype=torch.bfloat16,device_map={'':0},attn_implementation='eager')
    model=None
    settings=protocol['generation']
    for name,adapter in {'Ver3':VER3,'Curated1459':final}.items():
        if model is None:model=PeftModel.from_pretrained(base,str(adapter),adapter_name=name,is_trainable=False)
        else:model.load_adapter(str(adapter),adapter_name=name,is_trainable=False)
        model.set_adapter(name);model.eval()
        value=model.generation_config.eos_token_id
        eos=list(value) if isinstance(value,(list,tuple)) else ([] if value is None else [value])
        eos=sorted(set(eos+[tok.eos_token_id,tok.get_vocab()['<|im_end|>']]))
        adapter_sha=sha(adapter/'adapter_model.safetensors')
        for split,prefix in [('fresh',''),('known_regression','regression_')]:
            path=OUT/f'{prefix}generations.jsonl';previous=lines(path) if path.exists() else []
            for r in previous:
                case=next(c for c in cases if c['id']==r['case_id'])
                assert r['input_sha256']==digest(case['prompt']) and r['profile']==data.PROFILE
                if r['model']==name:assert r['adapter_sha256']==adapter_sha
            assert len({(r['model'],r['case_id']) for r in previous})==len(previous)
            pending=[c for c in cases if c['split']==split and not any(r['model']==name and r['case_id']==c['id'] for r in previous)]
            for offset in range(0,len(pending),settings['batch_size']):
                batch=pending[offset:offset+settings['batch_size']]
                prompts=[processor.apply_chat_template(c['prompt'],tokenize=False,add_generation_prompt=True,enable_thinking=False) for c in batch]
                inputs=tok(prompts,add_special_tokens=False,padding=True,return_tensors='pt').to('cuda:0')
                start=time.monotonic()
                with torch.inference_mode():
                    outputs=model.generate(**inputs,max_new_tokens=settings['max_new_tokens'],do_sample=False,
                        use_cache=True,repetition_penalty=1.0,no_repeat_ngram_size=0,eos_token_id=eos,pad_token_id=tok.pad_token_id)
                width=inputs['input_ids'].shape[1]
                for c,out in zip(batch,outputs):
                    ids=out[width:].tolist()
                    stops=[i for i,t in enumerate(ids) if t in eos]
                    if stops:ids=ids[:stops[0]+1]
                    raw=tok.decode(ids,skip_special_tokens=True).strip()
                    text=finish_text(raw,data.GENRE_NAMES[c['genre']])
                    r={'model':name,'case_id':c['id'],'genre':c['genre'],'raw_text':raw,'text':text,'chars':len(text),
                        'in_bounds':c['bounds'][0]<=len(text)<=c['bounds'][1],'ended_with_eos':bool(stops),
                        'tokens':len(ids),'batch_seconds':round(time.monotonic()-start,2),'adapter_sha256':adapter_sha,
                        'input_sha256':digest(c['prompt']),'profile':data.PROFILE}
                    with path.open('a',encoding='utf-8') as f:f.write(json.dumps(r,ensure_ascii=False)+'\n')
                    previous.append(r)
                    print('GENERATED',name,c['id'],'EOS',r['ended_with_eos'],'chars',len(text),flush=True)
                save(OUT/'progress.json',{'stage':'comparison_generation','model':name,'split':split,
                    'completed_outputs':sum(len(lines(OUT/f'{p}generations.jsonl')) if (OUT/f'{p}generations.jsonl').exists() else 0 for p in ('','regression_')),
                    'total_outputs':112,'updated_utc':now()})
    assert len(lines(OUT/'generations.jsonl'))==80 and len(lines(OUT/'regression_generations.jsonl'))==32
    save(OUT/'inference_state.json',{'status':'completed','completed_utc':now(),'outputs':112,
        'generation_sha256':{p:sha(OUT/f'{p}generations.jsonl') for p in ('','regression_')}})
    print('COMPARISON_GENERATION_COMPLETE',flush=True)


def blind():
    check_protocol()
    cases={c['id']:c for c in json.loads((OUT/'inputs.json').read_text(encoding='utf-8'))}
    for prefix,count,seed,letter in [('',80,1911459,'B'),('regression_',32,459191,'K')]:
        assert not (OUT/f'{prefix}blind_key.json').exists(),'Already blinded'
        rows=lines(OUT/f'{prefix}generations.jsonl');assert len(rows)==count
        random.Random(seed).shuffle(rows)
        save(OUT/f'{prefix}blind_key.json',{f'{letter}{i:03d}':{'model':r['model'],'case_id':r['case_id']} for i,r in enumerate(rows,1)})
        save(OUT/f'{prefix}blind_outputs.json',[{'output_id':f'{letter}{i:03d}',
            'case':{k:v for k,v in cases[r['case_id']].items() if k!='prompt'},
            **{k:r[k] for k in ('text','chars','in_bounds','ended_with_eos')}} for i,r in enumerate(rows,1)])
    import final_assessment as assessment
    assessment.OUT=OUT;assessment.packets()
    print('BLIND_REVIEW_READY',flush=True)


def freeze():
    import final_assessment as assessment
    assessment.OUT=OUT;assessment.freeze()


def report():
    protocol=check_protocol()
    frozen=json.loads((OUT/'ratings_frozen.json').read_text(encoding='utf-8'))
    assert sha(OUT/'ratings.json')==frozen['ratings_sha256']
    ratings=json.loads((OUT/'ratings.json').read_text(encoding='utf-8'))
    def stats(rs):
        return {'count':len(rs),'naturalness':statistics.mean(r['naturalness'] for r in rs),
            'faithfulness':statistics.mean(r['faithfulness'] for r in rs),'nonrepetition':statistics.mean(r['nonrepetition'] for r in rs),
            'critical_count':sum(r['critical'] for r in rs),'in_bounds':sum(r['in_bounds'] for r in rs),
            'eos_complete':sum(r['ended_with_eos'] for r in rs),
            'critical_cases':[{'id':r['case_id'],'reason':r['reason']} for r in rs if r['critical']]}
    results={}
    for prefix in ('','regression_'):
        key=json.loads((OUT/f'{prefix}blind_key.json').read_text(encoding='utf-8'))
        outputs={r['output_id']:r for r in json.loads((OUT/f'{prefix}blind_outputs.json').read_text(encoding='utf-8'))}
        groups=defaultdict(list)
        for oid,k in key.items():
            groups[k['model']].append({**ratings[oid],**k,'genre':outputs[oid]['case']['genre'],
                **{f:outputs[oid][f] for f in ('in_bounds','ended_with_eos')}})
        results[prefix or 'fresh']={name:{**stats(rs),'by_genre':{g:stats([r for r in rs if r['genre']==g]) for g in data.GENRE_NAMES}}
                                  for name,rs in groups.items()}
    baseline=results['fresh']['Ver3'];gates={}
    for name,value in results['fresh'].items():
        gates[name]={'fresh_no_critical':value['critical_count']==0,
            'known_no_critical':results['regression_'][name]['critical_count']==0,
            'naturalness':value['naturalness']>=8,'all_genres_min':all(s['naturalness']>=7.5 for s in value['by_genre'].values()),
            'length':value['in_bounds']/value['count']>=.85,'all_eos':value['eos_complete']==value['count'],
            'genre_vs_ver3':all(s['naturalness']>=baseline['by_genre'][g]['naturalness'] for g,s in value['by_genre'].items()),
            'faithfulness_vs_ver3':value['faithfulness']>=baseline['faithfulness']}
    state=json.loads((OUT/'training_state.json').read_text(encoding='utf-8'))
    result={'status':'complete','training':state,'profile':data.PROFILE,'fresh':results['fresh'],'known':results['regression_'],
        'gates':gates,'candidate_passed_all_gates':all(gates['Curated1459'].values()),
        'new_model_applied':False,'service_model_unchanged':True,'quality_approved':False,
        'ratings_sha256':frozen['ratings_sha256'],'protocol_sha256':sha(OUT/'protocol.json'),
        'limitations':['Primary assistant AI review, not independent human validation.',
            'Synthetic 40-case fresh sample; no universal or statistical superiority claim.',
            'Known 16 are development/regression evidence and are not pooled into fresh scores.',
            'Dataset content, prompt and training history differ; not a causal comparison of data quantity.']}
    save(OUT/'result.json',result)
    text=['정제 1,459개 새 모델과 Ver3 비교','새 문항 40개 + 기존 오류 점검 16개. 같은 프롬프트와 생성 조건. AI 자체 블라인드 평가.',
        f'기본 모델: {MODEL}, 새 LoRA 1에포크. 검증 손실 {state["before_loss"]:.4f} → {state["after_loss"]:.4f}.',
        '검증 손실은 보존된 이전 프롬프트로 측정되며 문장 품질 점수와 다릅니다.','']
    for name in ('Ver3','Curated1459'):
        v=results['fresh'][name];k=results['regression_'][name]
        text.append(f'{name}: 자연스러움 {v["naturalness"]:.3f}, 사실 보존 {v["faithfulness"]:.3f}, 반복 방지 {v["nonrepetition"]:.3f}, 중요 오류 {v["critical_count"]}/40, 분량 {v["in_bounds"]}/40, 기존 오류 {k["critical_count"]}/16')
        text.extend(f'  {data.GENRE_NAMES[g]}: 자연스러움 {s["naturalness"]:.3f}, 사실 보존 {s["faithfulness"]:.3f}, 중요 오류 {s["critical_count"]}/10, 분량 {s["in_bounds"]}/10' for g,s in v['by_genre'].items())
        text.append('  기준: '+json.dumps(gates[name],ensure_ascii=False))
    text+=['','새 모델 전체 기준 통과: '+str(result['candidate_passed_all_gates']),
        '새 모델의 웹 적용은 하지 않았습니다. 기존 로컬 모델로 API를 복구했습니다.',
        '합성 문항과 AI 자체 평가이므로 사람의 독립 검수나 모든 입력에서의 우월성을 뜻하지 않습니다.']
    (OUT/'비교_결과.txt').write_text('\n'.join(text)+'\n',encoding='utf-8')
    print('\n'.join(text))


def request_json(path,body=None,timeout=10):
    headers={'Content-Type':'application/json'}
    if body is not None:headers['x-llm-token']=(PROJECT/'thinking_llm_token').read_text(encoding='utf-8-sig').strip()
    req=urllib.request.Request('http://127.0.0.1:8001'+path,
        data=None if body is None else json.dumps(body,ensure_ascii=False).encode(),headers=headers)
    with urllib.request.urlopen(req,timeout=timeout) as r:return json.loads(r.read())


def pause_service():
    import psutil
    path=ROOT/'outputs/gpu_server/server.json'
    config=json.loads(path.read_text(encoding='utf-8'))
    health=request_json('/health')
    adapter=Path(config['adapter']);expected=sha(adapter/'adapter_model.safetensors')
    if health.get('loaded'):
        assert health['loaded_identity']['adapter_sha256']==expected
        assert health['loaded_identity']['profile']==config['profile']
    process=psutil.Process(config['pid'])
    def valid(p):
        cmd=p.cmdline()
        return 'common_llm:app' in cmd and '--port' in cmd and cmd[cmd.index('--port')+1]=='8001' and '127.0.0.1' in cmd
    assert valid(process),'Unexpected local process; do not stop'
    descendants=process.children(recursive=True)
    children=[c for c in descendants if valid(c)]
    # Windows venv launchers also own a conhost console helper. It has no
    # model or API; leave it to exit when its owning launcher exits.
    auxiliary=[c for c in descendants if c.name().lower()=='conhost.exe' and c.ppid()==process.pid]
    assert len(children)+len(auxiliary)==len(descendants),'Unexpected child process; do not stop'
    snapshot={'config':config,'health_before':health,'adapter_sha256':expected,
        'stopped_pids':[p.pid for p in children]+[process.pid],'paused_utc':now()}
    save(OUT/'local_runtime.json',snapshot)
    for p in list(reversed(children))+[process]:
        try:p.terminate();p.wait(timeout=10)
        except psutil.NoSuchProcess:pass
    return snapshot


def restore_service(snapshot):
    config=snapshot['config']
    assert sha(Path(config['adapter'])/'adapter_model.safetensors')==snapshot['adapter_sha256']
    subprocess.run([sys.executable,str(PROJECT/'deploy/gpu_server.py'),'--adapter',config['adapter'],
        '--profile',config['profile'],'--start'],check=True,cwd=PROJECT)
    start=time.monotonic()
    while True:
        try:
            health=request_json('/health');break
        except Exception:
            if time.monotonic()-start>45:raise
            time.sleep(1)
    response=request_json('/draft',{'document_type':'report','topic':'복구 확인용 기록',
        'facts':['담당자는 종이 이름표 8개의 번호를 목록과 대조함','번호가 다른 이름표는 없었음',
                 '종이 재질은 조사하지 않음'],'target_chars':120,'tone':'기본'},timeout=55)
    health=request_json('/health')
    assert health['loaded_identity']['adapter_sha256']==snapshot['adapter_sha256']
    assert health['loaded_identity']['profile']==config['profile']
    snapshot.update({'restored_utc':now(),'health_after':health,'restore_draft_returned':bool(response)})
    save(OUT/'local_runtime.json',snapshot)
    print('ORIGINAL_LOCAL_MODEL_RESTORED',flush=True)


def run():
    check_protocol()
    marker=OUT/'run_state.json'
    history=[]
    if marker.exists():
        prior=json.loads(marker.read_text(encoding='utf-8'))
        if prior['status']!='failed' or (OUT/'training_state.json').exists() or (OUT/'local_runtime.json').exists():
            raise RuntimeError('Study execution already started; inspect state before any further work.')
        history=prior.get('previous_attempts',[])+[prior]
    save(marker,{'status':'running','pid':os.getpid(),'started_utc':now(),'previous_attempts':history})
    snapshot=None;error=None
    try:
        snapshot=pause_service()
        for action in ('train','infer','blind'):
            save(OUT/'progress.json',{'stage':action,'updated_utc':now()})
            subprocess.run([sys.executable,str(Path(__file__)),action],check=True,cwd=PROJECT)
        save(marker,{'status':'awaiting_blind_review','completed_gpu_work_utc':now(),'previous_attempts':history})
    except BaseException as exc:
        error=exc;save(marker,{'status':'failed','error':repr(exc),'failed_utc':now(),'previous_attempts':history})
    finally:
        if snapshot:
            try:restore_service(snapshot)
            except BaseException as exc:
                save(OUT/'restore_error.json',{'error':repr(exc),'utc':now()})
                if error is None:raise
    if error is not None:raise error


if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('action',choices=['prepare','run','train','infer','blind','freeze','report'])
    globals()[p.parse_args().action]()
