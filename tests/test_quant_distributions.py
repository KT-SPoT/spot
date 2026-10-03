"""Same-run distribution cards: preserve percentages, scope, dates and missing values."""
import copy
import unittest
from unittest.mock import patch
from src.brief.quant_distributions import distribution_cards
from src.brief.generator import generate_brief
from src.brief.renderer import render_markdown
from src.critic.critic import run_critic
from src.critic.research_review import build_research_input
from src.critic.semantic import build_input
from tests.test_research_brief import fixture


def sections():
    return {'population': {'floating_population': {
        'weekday_weekend_and_day_of_week': {'regions': {'선택 영역': {
            'weekday': {'share_pct': 70}, 'weekend': {'share_pct': 30},
            'mon': {'share_pct': 0, 'count': 0}, 'fri': {'share_pct': 25.3, 'count': 253}}}},
        'time_band': {'reference_period': '제공 표 시점', 'regions': {'선택 영역': {
            '05_09': {'share_pct': None}, '14_18': {'share_pct': 37.2}}}}}},
        'sales': {'sales_characteristics': {
            'demographics': {'regions': {'선택 영역': {
                'amount_share_percent': {'male': 42.2, 'female': 57.8, '30s': 40},
                'transaction_share_percent': {'male': 99, 'female': 1}}}},
            'day_of_week': {'regions': {'다른 영역': {'amount_share_percent': {'mon': 100}}}},
            'time_band': {'regions': {'선택 영역': {'amount_share_percent': {'18_23': 23.4}}}}}}}


class QuantDistributionsTest(unittest.TestCase):
    def test_same_run_percentages_and_dates_survive_without_aggregate_or_foreign_area(self):
        data=sections();before=copy.deepcopy(data)
        cards=distribution_cards(data,[{'source_id':'q1'}],'선택 영역 / 반경 1000m')
        self.assertEqual(len(cards),5)
        flowday=next(c for c in cards if c['population_kind']=='floating_population' and c['distribution_kind']=='day')
        self.assertEqual(flowday['shares'],{'mon':{'share_pct':0,'count':0},'fri':{'share_pct':25.3,'count':253}})
        self.assertIsNone(flowday['reference_period'])
        flowtime=next(c for c in cards if c['population_kind']=='floating_population' and c['distribution_kind']=='time')
        self.assertEqual(flowtime['reference_period'],'제공 표 시점')
        self.assertNotIn('05_09',flowtime['shares'])
        salesgender=next(c for c in cards if c['population_kind']=='sales' and c['distribution_kind']=='gender')
        self.assertEqual(salesgender['shares']['male']['share_pct'],42.2)
        self.assertFalse(any(c['population_kind']=='sales' and c['distribution_kind']=='day' for c in cards))
        self.assertEqual(data,before)

    def test_no_evidence_or_invalid_percentages_never_become_bars(self):
        data=sections()
        self.assertEqual(distribution_cards(data,[],'test'),[])
        for value in (True,-1,101,float('nan'),float('inf'),'20'):
            data['population']['floating_population']['time_band']['regions']['선택 영역']['14_18']['share_pct']=value
            self.assertFalse(any(c['population_kind']=='floating_population' and c['distribution_kind']=='time'
                                 for c in distribution_cards(data,[{'source_id':'q'}],'test')))

    def test_brief_renderer_includes_timing_and_sales_but_primary_is_not_timing(self):
        bundle=fixture();before=copy.deepcopy(bundle)
        with patch('src.brief.quant_evidence.read_quant_evidence',return_value=sections()):
            brief=generate_brief(bundle,quant_evidence={})
        self.assertEqual(bundle,before)
        self.assertIn('유동인구 요일별 비중',render_markdown(brief))
        self.assertIn('25.3%',render_markdown(brief))
        self.assertIn('매출액 성별 비중',render_markdown(brief))
        self.assertNotIn('요일별 비중',brief['overview']['primary_customer_signal'])
        self.assertEqual(brief['source_count'],3)

    def test_age_only_and_one_gender_are_preserved_without_complement(self):
        for observed in ({'30s':{'share_pct':17.8}}, {'female':{'share_pct':62.1}}):
            with self.subTest(observed=observed):
                data={'population': {'resident_population': {'demographics': {'regions': {'선택 영역': observed}}}}}
                with patch('src.brief.quant_evidence.read_quant_evidence',return_value=data):
                    brief=generate_brief(fixture(),quant_evidence={})
                cards=[c for c in brief['unique_local_signals'] if c.get('shares')]
                self.assertEqual(len(cards),1)
                self.assertEqual(cards[0]['shares'],observed)

    def test_chart_only_cards_do_not_expand_existing_critic_input(self):
        bundle=fixture();critic=run_critic(bundle)
        baseline=build_research_input(bundle,critic)
        semantic_baseline=build_input(bundle,critic)
        brief=generate_brief(bundle,critic)
        brief['unique_local_signals'].append({'module':'quant','type':'quant_distribution',
            'title':'Large chart-only data '*10000,'shares':{'mon':{'share_pct':50}},
            'sources':bundle['results']['quant']['sources']})
        with patch('src.critic.research_review.generate_brief',return_value=brief):
            self.assertEqual(build_research_input(bundle,critic),baseline)
        with patch('src.critic.semantic.generate_brief',return_value=brief):
            self.assertEqual(build_input(bundle,critic),semantic_baseline)


if __name__=='__main__':unittest.main()
