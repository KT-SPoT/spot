import os
import unittest
from unittest.mock import patch
import httpx
from fastapi.testclient import TestClient
from src.web.app import create_app


class PlaceTests(unittest.TestCase):
    def client(self, handler):
        return TestClient(create_app(token='only-server-token-123456789',
                                    place_transport=httpx.MockTransport(handler)),base_url='http://localhost')

    def test_search_returns_all_choices_without_secret(self):
        def handler(request):
            self.assertEqual(request.headers['Authorization'],'KakaoAK test-private-key')
            self.assertNotIn('X-SPOT-API-Key',request.headers)
            if 'keyword' in request.url.path:
                return httpx.Response(200,json={'documents':[{'place_name':name,'address_name':'부산 명륜동 386','x':'129.08','y':'35.20'} for name in ['동래점','다른 후보점']]})
            return httpx.Response(200,json={'documents':[]})
        with patch.dict(os.environ,{'KAKAO_REST_API_KEY':'test-private-key'}),self.client(handler) as client:
            self.assertEqual(client.get('/api/places/search?q=동래점').status_code,401)
            client.get('/')
            response=client.get('/api/places/search?q=동래점')
            self.assertEqual(len(response.json()['results']),2)
            self.assertNotIn('test-private-key',response.text)
            self.assertEqual(response.json()['results'][0]['lat'],35.20)

    def test_reverse_keeps_selected_point_and_does_not_fallback(self):
        def handler(request):
            self.assertEqual(request.url.params['x'],'129.08')
            return httpx.Response(200,json={'documents':[{'address':{'address_name':'부산 동래구 명륜동 386'},'road_address':None}]})
        with patch.dict(os.environ,{'KAKAO_REST_API_KEY':'test-private-key'}),self.client(handler) as client:
            client.get('/')
            value=client.get('/api/places/reverse?lat=35.2&lng=129.08').json()['results']
            self.assertEqual(value['kind'],'site')
            self.assertEqual(value['lng'],129.08)
            self.assertEqual(client.get('/api/places/reverse?lat=NaN&lng=129').status_code,422)

    def test_provider_errors_and_empty_address_are_safe(self):
        for code,documents,expected in [(401,[],503),(200,[],404)]:
            with patch.dict(os.environ,{'KAKAO_REST_API_KEY':'test-private-key'}),self.client(lambda r:httpx.Response(code,json={'documents':documents,'private':'test-private-key'})) as client:
                client.get('/')
                response=client.get('/api/places/reverse?lat=35.2&lng=129.08')
                self.assertEqual(response.status_code,expected)
                self.assertNotIn('test-private-key',response.text)


if __name__=='__main__': unittest.main()
