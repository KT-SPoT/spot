import unittest
from unittest.mock import patch
from src.scouts.local_places import collect_places
from src.scouts.search_runtime import result, SearchError
from src.brief.area_summary import area_summary

REQUEST={'request_id':'places','store':{'lat':37.57,'lng':126.97,'address':'서울 종로구'},'research':{'radius_m':500}}
class PlaceTests(unittest.TestCase):
    def test_radius_dedup_provenance_and_summary(self):
        rows=[{'id':'1','place_name':'시험역','y':'37.5701','x':'126.97','place_url':'https://place.map.kakao.com/1','address_name':'서울 종로구'},
              {'id':'2','place_name':'다른 도시','y':'35','x':'129','place_url':'https://place.map.kakao.com/2'}]
        output=result(REQUEST,'local')
        with patch('src.scouts.local_places.search.credentials'),patch.dict('os.environ',{'KAKAO_REST_API_KEY':'test'}),patch('src.scouts.local_places.search.get_json',return_value={'documents':rows}),patch('src.scouts.local_places.official_context'):
            collect_places(REQUEST,output)
        self.assertEqual(len(output['insights']),1)
        c=output['insights'][0];self.assertEqual(c['evidence_role'],'background');self.assertLess(c['place']['distance_m'],500)
        c.update(module='local',sources=output['sources'])
        text=area_summary({'unique_local_signals':[c]})
        self.assertIn('시험역',text);self.assertNotIn('다른 도시',text);self.assertNotIn('직장인',text)
    def test_failure_and_offline_have_no_fake_place(self):
        output=result(REQUEST,'local')
        with patch('src.scouts.local_places.search.credentials',side_effect=SearchError('OFFLINE_MODE')),patch('src.scouts.local_places.search.get_json') as provider:
            collect_places(REQUEST,output)
        provider.assert_not_called();self.assertFalse(output['insights'])
    def test_official_search_snippet_not_used_as_evidence(self):
        from src.scouts.local_places import official_context
        output=result(REQUEST,'local')
        place={'place':{'name':'시험문화관','category':'문화'}}
        with patch.dict('os.environ',{'NAVER_CLIENT_ID':'test','NAVER_CLIENT_SECRET':'test'}),patch('src.scouts.local_places.search.get_json',return_value={'items':[{'link':'https://city.go.kr/a','title':'시험문화관','description':'설명'}]}),patch('src.scouts.local_places.fetch_article',return_value=('<p>다른 장소만 설명하는 내용으로서 이 문장은 요청한 시설에 대한 설명이나 근거로 사용해서는 안 됩니다.</p>','https://city.go.kr/a')):
            official_context(REQUEST['store'],[place],output)
        self.assertFalse(output['insights'])
