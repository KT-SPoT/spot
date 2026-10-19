import unittest
from src.brief.area_summary import area_summary

class AreaSummaryTests(unittest.TestCase):
    def test_customer_summary_is_not_used_as_place_context(self):
        text=area_summary({'overview':{'area_summary':'20대 매출 비중이 높음'},'unique_local_signals':[{'module':'quant','population_kind':'sales','shares':{'20s':{'share_pct':60}},'sources':[{}]}]})
        self.assertNotIn('20대',text)
        self.assertNotIn('미확보',text)

    def test_facilities_and_dated_local_news_keep_their_scope(self):
        source={'source_url':'https://example.com','published_at':'2026-05-18'}
        brief={'unique_local_signals':[{'module':'quant','title':'최다 주요시설 유형','value':'금융기관','sources':[source]}], 'local_changes':[{'title':'도로 통행 재개','sources':[source]}]*2}
        text=area_summary(brief)
        self.assertIn('주요시설 중 금융기관 유형',text)
        self.assertIn('2026-05-18 보도',text)
        self.assertEqual(text.count('도로 통행 재개'),1)
        self.assertNotIn('업무 중심',text)
