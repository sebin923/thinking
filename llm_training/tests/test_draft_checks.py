"""Observed draft failures and legitimate prose that must not trigger warnings."""
from pathlib import Path
import sys
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from common_llm import checks_for


class DraftChecksTest(unittest.TestCase):
    def test_detects_instruction_copied_as_prose(self):
        text = '자료를 확인했다. 독자: 자료를 확인하는 독자 문체: 객관적인 설명체.'
        self.assertIn('지시문 또는 작성 안내 혼입 의심', checks_for(text, len(text), True))

    def test_detects_output_bounds_in_body(self):
        text = '발표문은 공백 포함 160~240자로 작성되었습니다.'
        self.assertIn('지시문 또는 작성 안내 혼입 의심', checks_for(text, len(text), True))

    def test_detects_multiple_unfinished_memo_endings(self):
        text = '나는 버스에 서있었음. 접힌 시간표를 꺼내봄. 서두를 필요 없다는 생각듦.'
        self.assertTrue(any('메모체 종결' in c for c in checks_for(text, len(text), True)))

    def test_detects_narrated_prompt_metadata(self):
        text = '문체는 객관적인 설명체입니다. 내용은 주제와 확인한 상황을 짧게 밝힙니다. 메모는 축약어와 명사형 종결을 다듬습니다.'
        self.assertIn('지시문 또는 작성 안내 혼입 의심', checks_for(text, len(text), True))

    def test_does_not_flag_one_general_style_description(self):
        text = '이 소설의 문체는 담백하고 문장이 짧다. 화자는 창가의 화분을 바라본다.'
        self.assertEqual([], checks_for(text, len(text), True))

    def test_keeps_legitimate_quotations(self):
        text = '안내문에는 “독자: 학생, 공백 포함 160~240자”라고 적혀 있었다. 메모의 “아직 안했음. 결과 모름.”을 읽었다.'
        self.assertEqual([], checks_for(text, len(text), True))

    def test_keeps_complete_prose_and_season_noun(self):
        text = '봄에 화분 세 개를 확인했다. 물은 선생님이 주셨으며 다음날의 상태는 아직 확인하지 않았다.'
        self.assertEqual([], checks_for(text, len(text), True))

    def test_keeps_real_writing_experience(self):
        text = '저는 동아리 발표문을 작성했습니다. 받은 질문 세 가지를 기록했습니다.'
        self.assertEqual([], checks_for(text, len(text), True))

    def test_keeps_existing_length_and_stop_checks(self):
        self.assertEqual(['요청 분량 밖: 3자 / 목표 100자', '출력 토큰 제한 도달: 마지막 문장 확인 필요'], checks_for('했다.', 100, False))

    def test_warns_about_repetition_without_rewriting(self):
        text = '담당자는 확인한 내용을 별도 목록에 기록했다. 담당자는 확인한 내용을 별도 목록에 기록했다.'
        self.assertIn('동일 문장 반복', checks_for(text, len(text), True))
        self.assertEqual(2, text.count('담당자는'))


if __name__ == '__main__':
    unittest.main()
