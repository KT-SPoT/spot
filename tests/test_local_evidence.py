import os
import unittest
from datetime import date
from unittest.mock import patch

from src.scouts import local_evidence as evidence
from src.scouts.search_runtime import SearchError

ITEM = {"source_url": "https://example.org/news", "date_basis": "naver_provided_at"}
START, END = date(2026, 4, 1), date(2026, 10, 1)
SENTENCE = "부산 명지국제신도시에 새롭게 건립하는 공공도서관은 오는 12월에 준공하고 개관할 예정이다."


def page(body=SENTENCE, pub="2026-09-20"):
    return f'<meta property="article:published_time" content="{pub}"><article><p>{body}</p></article>'


class LocalEvidenceTests(unittest.TestCase):
    def test_interview_question_and_aspiration_are_not_changes(self):
        for text in ('명륜동 상권 등 지역 자산을 어떻게 미래 성장동력으로 키워나갈 계획입니까.',
                     '명륜동의 새로운 공공도서관이 주민 편의를 위해 내년에 개관했으면 좋겠다는 희망을 밝혔다.'):
            with patch.object(evidence, 'fetch_article', return_value=(page(text), ITEM['source_url'])):
                result = evidence.verify_source(ITEM, '명륜동', START, END, {'address':'부산 동래구 명륜동 386'})
            self.assertEqual(result['status'], 'rejected')
            self.assertEqual(result['reason'], 'QUESTION_OR_ASPIRATION_NOT_CHANGE')

    def test_repair_reports_share_event_without_merging_different_facilities(self):
        planned = '명륜동 방향 내성지하차도 포장공사는 오늘 오후 10시에 완료될 예정이다.'
        reopened = '명륜동 방향 내성지하차도는 지반침하 긴급 정비를 완료하고 오후 5시에 통행을 재개했다.'
        rows = []
        for text in (planned, reopened):
            with patch.object(evidence, 'fetch_article', return_value=(page(text), ITEM['source_url'])):
                rows.append(evidence.verify_source(dict(ITEM,title='내성지하차도 정비'), '명륜동', START, END, {'address':'부산 동래구 명륜동 386'}))
        self.assertEqual(rows[0]['event_key'], rows[1]['event_key'])
        self.assertIsNotNone(rows[0]['event_key'])
        self.assertEqual(rows[0]['change_state'], 'scheduled')
        self.assertEqual(rows[1]['change_state'], 'reported_repair_or_reopening')
        self.assertNotEqual(evidence.facility_event_key(planned), evidence.facility_event_key(planned.replace('내성','다른')))
        self.assertIsNone(evidence.facility_event_key('내성지하차도와 교대지하차도 정비 공사'))

    def test_holiday_march_groups_only_with_matching_route_time_and_destination(self):
        a = '개천절 집회. 오후 4시부터 새문안로와 자하문로를 따라 신교사거리까지 행진할 계획이다.'
        b = '개천절 교통통제. 오후 4시부터는 새문안로와 자하문로를 통해 신교사거리까지 행진할 계획이다.'
        self.assertIsNotNone(evidence.local_event_key(a))
        self.assertEqual(evidence.local_event_key(a), evidence.local_event_key(b))
        self.assertNotEqual(evidence.local_event_key(a), evidence.local_event_key(b.replace('4시','5시')))
        self.assertIsNone(evidence.local_event_key('개천절 새문안로에서 교통통제 예정'))

    def test_article_image_metadata_fallback_and_og_priority(self):
        parser = evidence.ArticleParser()
        parser.feed('<meta name="twitter:image" content="/twitter.jpg"><meta name="og:image" content="/article.jpg">')
        self.assertEqual(parser.image, '/article.jpg')

    def test_same_neighborhood_in_other_city_is_rejected(self):
        item = dict(ITEM, title='서울관광재단 명륜동 야간 노선 신설')
        html = page('서울 명륜동 상권과 연결되도록 야간 관광 코스 종착지를 새로 신설할 예정이라고 서울관광재단은 밝혔다.')
        with patch.object(evidence, 'fetch_article', return_value=(html, ITEM['source_url'])):
            result = evidence.verify_source(item,'명륜동',START,END,{'address':'부산 동래구 명륜동 386'})
        self.assertEqual(result['status'],'rejected')
        self.assertEqual(result['reason'],'OTHER_CITY_SAME_NEIGHBORHOOD')

    def test_thumbnail_comes_from_article_and_is_url_checked(self):
        html = page() + '<meta property="og:image" content="/photo.jpg">'
        with patch.object(evidence,'fetch_article',return_value=(html,ITEM['source_url'])), patch.object(evidence,'validate_url') as check:
            result = evidence.verify_source(ITEM,'명지국제신도시',START,END)
        check.assert_called_once_with('https://example.org/photo.jpg')
        self.assertEqual(result['thumbnail_url'],'https://example.org/photo.jpg')

    def test_cross_paragraph_project_context_is_retained_with_scope(self):
        html = page("명지지구 개발사업 실시계획 25차 변경 승인을 완료하고 23일 고시할 예정이라고 관계 기관은 밝혔다.")
        html += '<article><p>명지 중앙공원은 명지국제신도시의 핵심 공원으로 특화 계획에 따라 조성될 예정이다.</p></article>'
        with patch.object(evidence, "fetch_article", return_value=(html, ITEM["source_url"])):
            result = evidence.verify_source(ITEM,"명지국제신도시",START,END,{"address":"부산광역시 강서구 명지국제8로 246"})
        self.assertEqual(result["evidence_role"],"direct_change")
        self.assertIsNotNone(result["event_key"])

    def test_old_move_in_can_be_background_without_becoming_recent_change(self):
        html = page("명지국제신도시에서 2020년 7월 입주 완료한 아파트 단지는 올해 거래가격이 상승해 비교 자료로 언급됐다.")
        with patch.object(evidence,"fetch_article",return_value=(html,ITEM["source_url"])):
            result = evidence.verify_source(ITEM,"명지국제신도시",START,END,{"address":"부산광역시 강서구"})
        self.assertEqual(result["status"],"context_corroborated")
        self.assertEqual(result["evidence_role"],"background")
        self.assertEqual(result["change_state"],"not_applicable")

    def test_same_district_transport_is_context_without_claiming_store_area(self):
        html = page("강서구에서는 에코델타시티와 강서구청을 잇는 신설 버스 노선을 추진하며 대중교통 이용 여건을 개선할 계획이다.")
        with patch.object(evidence,"fetch_article",return_value=(html,ITEM["source_url"])):
            result = evidence.verify_source(ITEM,"명지국제신도시",START,END,{"address":"부산광역시 강서구"})
        self.assertEqual(result["evidence_role"],"surrounding_context")
        self.assertEqual(result["classification_basis"],"same_administrative_district")

    def test_unrelated_district_does_not_become_context(self):
        self.assertIsNone(evidence.context_evidence(["다른 도시의 새로운 아파트 공급이 임대 시장의 흐름과 관련된 보도에서 소개되고 있다."],"명지국제신도시",{"address":"부산광역시 강서구"},START))

    def test_missing_article_date_keeps_provided_date_caveat(self):
        html='<article><p>'+SENTENCE+'</p></article>'
        with patch.object(evidence,"fetch_article",return_value=(html,ITEM["source_url"])):
            result=evidence.verify_source(ITEM,"명지국제신도시",START,END,{"address":"부산광역시 강서구"})
        self.assertEqual(result["status"],"context_corroborated")
        self.assertEqual(result["date_basis"],"naver_provided_at")
        self.assertIsNone(result["article_published_at"])

    def check(self, html):
        with patch.object(evidence, "fetch_article", return_value=(html, ITEM["source_url"])):
            return evidence.verify_source(ITEM, "명지국제신도시", START, END)

    def test_planned_completion_never_becomes_completed(self):
        result = self.check(page())
        self.assertEqual(result["status"], "text_corroborated")
        self.assertEqual(result["change_state"], "scheduled")
        self.assertFalse(result["event_verified"])
        self.assertLessEqual(len(result["excerpt"]), 120)
        self.assertEqual(len(result["evidence_fingerprint"]), 64)

    def test_reported_opening_retains_reported_scope(self):
        result = self.check(page("부산 명지국제신도시에 건립된 새로운 공공도서관은 지역 주민을 위한 시설로 지난 20일 개관했다."))
        self.assertEqual(result["change_state"], "reported_opening")

    def test_sidebar_region_does_not_verify_wrong_area_body(self):
        html = page("부산 에코델타시티에는 새로운 공공도서관이 건립되어 주민들을 위한 서비스 제공을 위해 개관했다.")
        html += '<aside><p>' + SENTENCE + '</p></aside><h1>' + SENTENCE + '</h1>'
        result = self.check(html)
        self.assertEqual(result["status"], "unconfirmed")
        self.assertNotIn("excerpt", result)

    def test_region_and_change_in_separate_sentences_are_not_correlated(self):
        result = self.check(page("명지국제신도시에는 지역 주민들이 새로운 시설을 기다리고 있다. 에코델타시티에는 주민 편의를 위한 새로운 공공도서관이 개관했다."))
        self.assertEqual(result["status"], "unconfirmed")

    def test_original_article_date_overrides_recent_search_date(self):
        self.assertEqual(self.check(page(pub="2025-01-01"))["status"], "rejected")

    def test_historical_move_in_background_is_not_recent_change(self):
        result = self.check(page("명지국제신도시에서 2020년 7월 입주 완료한 아파트 단지는 올해 거래가격이 상승해 비교 자료로 언급됐다."))
        self.assertEqual(result["status"], "unconfirmed")

    def test_earlier_month_of_current_year_is_not_recent_change(self):
        result = self.check(page("명지국제신도시에서 2026년 3월 입주 완료한 아파트 단지는 올해 거래가격이 상승해 비교 자료로 언급됐다."))
        self.assertEqual(result["status"], "unconfirmed")

    def test_denied_opening_claim_does_not_become_opening(self):
        result = self.check(page("명지국제신도시의 새로운 도서관이 지난 20일 개관했다는 소문은 확인되지 않은 이야기라고 담당자가 밝혔다."))
        self.assertEqual(result["status"], "unconfirmed")

    def test_other_neighborhood_in_same_sentence_is_not_assigned_to_requested_area(self):
        result = self.check(page("명지국제신도시와 에코델타시티 등 신흥 주거지역을 중심으로 강서구 범방동에서는 신규 아파트에 입주할 예정이다."))
        self.assertEqual(result["status"], "unconfirmed")

    def test_missing_or_conflicting_dates_remain_unconfirmed(self):
        missing = self.check('<article><p>' + SENTENCE + '</p></article>')
        self.assertEqual(missing["status"], "candidate")
        conflict = self.check(page() + '<meta itemprop="datePublished" content="2026-09-21">')
        self.assertEqual(conflict["reason"], "CONFLICTING_ARTICLE_DATES")

    def test_structured_article_body_and_publication_date(self):
        import json
        html = '<script type="application/ld+json">' + json.dumps({"@type": "NewsArticle", "datePublished": "2026-09-20T23:00:00Z", "articleBody": SENTENCE}) + '</script>'
        result = self.check(html)
        self.assertEqual(result["status"], "text_corroborated")
        self.assertEqual(result["article_published_at"], "2026-09-21")

    def test_plain_paragraph_fallback_does_not_claim_full_article_extraction(self):
        result = self.check(page().replace('<article>', '<main>').replace('</article>', '</main>'))
        self.assertEqual(result["status"], "candidate")
        self.assertFalse(result["full_text_verified"])

    def test_offline_never_opens_article(self):
        with patch.dict(os.environ, {"SPOT_SCOUT_MODE": "offline"}), patch.object(evidence, "build_opener") as opener:
            with self.assertRaises(SearchError):
                evidence.fetch_article(ITEM["source_url"])
        opener.assert_not_called()

    def test_private_destination_and_redirect_are_blocked(self):
        with patch.object(evidence.socket, "getaddrinfo", return_value=[(2,1,6,'',('127.0.0.1',80))]):
            with self.assertRaises(SearchError):
                evidence.validate_url('http://localhost/private')
        with patch.object(evidence, "validate_url", side_effect=SearchError("UNSAFE_OR_UNRESOLVED_SOURCE_URL")):
            with self.assertRaises(SearchError):
                evidence.PublicRedirects().redirect_request(None,None,302,'',{},'http://localhost/private')

    def test_fetch_error_has_no_raw_error_or_url(self):
        with patch.object(evidence, "fetch_article", side_effect=SearchError("SOURCE_HTTP_ERROR",403)):
            result = evidence.verify_source(ITEM, "명지국제신도시", START, END)
        self.assertEqual(result["reason"], "SOURCE_HTTP_ERROR")
        self.assertNotIn("source_url", result)
