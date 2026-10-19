"""Readable report selection must not turn unrelated headlines into local facts."""
import copy
import unittest
from src.brief.pdf_editorial import select_local, trend_reading


class EditorialTests(unittest.TestCase):
    def test_local_uses_excerpt_and_preserves_other_reports(self):
        cards=[{'title':'신규 아파트 입주 소식','evidence':'지역의 과거 아파트 거래 가격을 비교했다.'},
               {'title':'복합개발 보도','evidence':'도심복합개발을 추진하기 위해 업무협약을 체결했다.'},
               {'title':'관련 개발 보도','evidence':'도심복합개발 사업에 참여한다.'}]
        before=copy.deepcopy(cards)
        main,extra=select_local(cards)
        self.assertEqual(len(main),3)
        self.assertEqual(main[0][1]['headline'],cards[0]['title'])
        self.assertEqual(main[0][1]['meaning'],'')
        self.assertEqual(len(extra),0)
        self.assertEqual(cards,before)

    def test_unclassified_news_is_kept_and_duplicate_sources_are_not_repeated(self):
        card={'title':'명동 두 번째 플래그십 오픈','evidence':'관광객에게 브랜드 공간을 선보일 계획이다.',
              'sources':[{'source_url':'https://news.example/a'}]}
        main,extra=select_local([card,{**card,'title':'같은 원문 재수집'}])
        self.assertEqual(len(main),1)
        self.assertIn('관광객',main[0][1]['fact'])
        self.assertEqual(extra,[])

    def test_trend_hint_requires_reported_element_and_existing_hypothesis(self):
        card={'observation':'현장 체험을 촬영하고 SNS로 소개한다.',
              'adaptation_hypotheses':[{'mechanism':'photo_sharing','statement':'지역 관측: 저녁 매출액 48%. 사례에서 참고할 행동: 촬영 결과 공유. 연결 단서: 카메라 기능 비교 접점을 검토합니다.'}]}
        reading=trend_reading(card)
        self.assertIn('촬영',reading['fact'])
        self.assertIn('카메라',reading['hint'])
        self.assertNotIn('인기',reading['meaning'])
        self.assertIsNone(trend_reading({**card,'observation':'개막을 알렸다.'}))
        self.assertIsNone(trend_reading({**card,'adaptation_hypotheses':[]}))
        self.assertIsNone(trend_reading({**card,'observation':'□ AI 발대식... 마라톤 체험을 촬영했다...'}))
