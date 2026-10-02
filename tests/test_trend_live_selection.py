"""Synthetic regressions for issues observed in bounded live Naver discovery."""
import unittest
from unittest.mock import patch

from src.scouts.trend import event_category, run_trend_scout
from src.brief.trend_groups import group_coverage
from src.brief.generator import generate_brief
from src.brief.renderer import render_markdown
from tests.test_trend_context import evidence
from tests.test_local import article


class LiveSelectionTests(unittest.TestCase):
    def run_rows(self, bundle, rows):
        with patch('src.scouts.search_runtime.news', return_value=rows), \
             patch('src.scouts.search_runtime.videos', return_value=[]):
            return run_trend_scout(bundle['request'])

    def test_industry_is_not_inferred_from_an_ancillary_minigame(self):
        bundle = evidence()
        row = article('화장품 안티에이징 팝업 오픈', 'https://example.org/beauty')
        row['description'] = '미니게임 체험, 인증샷 사진, 굿즈 제공'
        trend = self.run_rows(bundle, [row])
        self.assertEqual(trend['insights'][0]['event_category'], 'beauty')
        self.assertIn('game_interaction', trend['insights'][0]['taxonomy_tags'])
        self.assertEqual(event_category('지역 축제 게임 체험'), 'festival')
        self.assertEqual(event_category('버거 팝업 게임 체험'), 'food')

    def test_food_festival_are_not_lost_before_the_provider_cap(self):
        bundle = evidence()
        rows = [article(f'게임사 이름{i} 팝업 미니게임 체험 촬영 스탬프', f'https://example.org/game/{i}')
                for i in range(20)]
        rows += [article('음식 팝업 시식', 'https://example.org/food'),
                 article('지역 축제 스탬프', 'https://example.org/festival')]
        trend = self.run_rows(bundle, rows)
        self.assertEqual(len(trend['insights']), 10)
        self.assertEqual(len(trend['reference_cases']), 5)
        self.assertEqual({c['event_category'] for c in trend['reference_cases']}, {'game', 'food', 'festival'})

    def test_related_coverage_uses_one_reference_slot_with_all_selected_sources(self):
        bundle = evidence()
        rows = [article("가상몰, '4색 가을 축제' 개최", 'https://example.org/a'),
                article("가상몰, 점포별 4색 가을 축제 연다", 'https://example.org/b'),
                article('음식 팝업 시식', 'https://example.org/food')]
        trend = self.run_rows(bundle, rows)
        bundle['results']['trend'] = trend
        self.assertEqual(len(trend['reference_cases']), 2)
        self.assertEqual(sorted(len(c['related_case_ids']) for c in trend['reference_cases']), [1, 2])
        refs = [c for c in generate_brief(bundle)['trend_patterns'] if c.get('type') == 'reference_case']
        self.assertEqual(len(refs), 2)
        grouped = next(c for c in refs if c['article_count'] == 2)
        self.assertEqual(len(grouped['sources']), 2)
        # A reference cannot smuggle an unrelated case into the group.
        trend['reference_cases'] = [trend['reference_cases'][0]]
        trend['reference_cases'][0]['related_case_ids'] = [c['case_id'] for c in trend['insights']]
        brief = generate_brief(bundle)
        self.assertEqual(len([c for c in brief['trend_patterns'] if c.get('type') == 'reference_case']), 1)

    def test_generic_mechanics_and_different_days_do_not_merge_events(self):
        items = [dict(event_name="가상몰, '미니게임' 팝업", published_at='2026-10-01',
                      observation='미니게임 촬영 체험'),
                 dict(event_name='가상몰, 미니게임 축제', published_at='2026-10-01',
                      observation='미니게임 촬영 체험')]
        self.assertEqual(len(group_coverage(items)), 2)
        items[0].update(event_name="가상몰, '별빛친구' 팝업")
        items[1].update(event_name='가상몰, 별빛친구 축제', published_at='2026-10-02')
        self.assertEqual(len(group_coverage(items)), 2)

    def test_named_industries_keep_diversity_when_an_unclassified_case_scores_higher(self):
        bundle = evidence()
        names = ['별빛 팝업 미션 체험 사진 굿즈', '음식 팝업 시식', '지역 축제 체험',
                 '화장품 팝업 체험', '문화 콘텐츠 팝업 체험', '게임 전시회 굿즈']
        rows = [article(name, f'https://example.org/case/{i}') for i, name in enumerate(names)]
        trend = self.run_rows(bundle, rows)
        self.assertEqual({c['event_category'] for c in trend['reference_cases']},
                         {'game', 'food', 'festival', 'beauty', 'culture'})
        self.assertTrue(any(c['event_category'] == 'other' for c in trend['insights']))

    def test_audience_survey_is_useful_context_not_an_event_or_repeated_pattern(self):
        bundle = evidence()
        row = article('축제 참여 의사 조사', 'https://example.org/survey')
        row['description'] = '지역 축제 참여 의사는 30대, 생활 체험 참여 의사는 40대가 높았다.'
        trend = self.run_rows(bundle, [row])
        self.assertEqual(trend['reference_cases'], [])
        self.assertEqual(trend['patterns'], [])
        self.assertEqual(len(trend['audience_contexts']), 1)
        bundle['results']['trend'] = trend
        brief = generate_brief(bundle)
        self.assertEqual(brief['trend_patterns'][0]['type'], 'audience_context')
        self.assertIn('고객층 조사 맥락', render_markdown(brief))
        self.assertIn('체험 패턴 0개·참고 후보 0건', brief['overview']['area_summary'])
