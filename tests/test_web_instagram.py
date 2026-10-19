import os
import unittest
from unittest.mock import patch

import httpx
from fastapi.testclient import TestClient

from src.web.app import create_app


class InstagramTests(unittest.TestCase):
    def client(self, handler):
        return TestClient(create_app(token='server-only-test-token-123456',
            instagram_transport=httpx.MockTransport(handler)), base_url='http://localhost')

    def test_success_is_reference_only_and_secret_stays_server_side(self):
        def handler(request):
            self.assertEqual(request.headers['Authorization'], 'Bearer instagram-private-test-token')
            self.assertNotIn('access_token', request.url.params)
            self.assertNotIn('X-SPOT-API-Key', request.headers)
            if request.url.path.endswith('recently_searched_hashtags'):
                return httpx.Response(200,json={'data':[]})
            if request.url.path.endswith('ig_hashtag_search'):
                return httpx.Response(200,json={'data':[{'id':'123456789'}]})
            return httpx.Response(200,json={'data':[
                {'permalink':'https://instagram.com/p/ABC12345/','caption':'실제 반환 본문'},
                {'permalink':'https://instagram.com.evil.test/p/ABC12345/','caption':'제외'}]})
        with patch.dict(os.environ,{'SPOT_INSTAGRAM_ACCESS_TOKEN':'instagram-private-test-token','SPOT_INSTAGRAM_USER_ID':'123456789'}),self.client(handler) as client:
            client.get('/')
            response=client.post('/api/instagram/search',json={'hashtag':'#행사'},headers={'Origin':'http://localhost'})
            self.assertEqual(response.status_code,200)
            self.assertEqual(len(response.json()['items']),1)
            self.assertEqual(response.json()['evidence_status'],'reference_only')
            self.assertNotIn('instagram-private-test-token',response.text)

    def test_auth_origin_validation_prevent_calls(self):
        with self.client(lambda r:self.fail('Unexpected provider call')) as client:
            self.assertEqual(client.post('/api/instagram/search',json={},headers={'Origin':'http://localhost'}).status_code,401)
            client.get('/')
            self.assertEqual(client.post('/api/instagram/search',json={'hashtag':'행사'}).status_code,403)
            self.assertEqual(client.post('/api/instagram/search',json={'hashtag':'잘못 된 입력'},headers={'Origin':'http://localhost'}).status_code,422)

    def test_safe_provider_errors_and_quota_fail_closed(self):
        for code,expected in [(190,'INSTAGRAM_TOKEN_EXPIRED'),(10,'INSTAGRAM_PERMISSION_REQUIRED'),(4,'INSTAGRAM_RATE_LIMIT'),(100,'INSTAGRAM_REQUEST_REJECTED')]:
            with patch.dict(os.environ,{'SPOT_INSTAGRAM_ACCESS_TOKEN':'instagram-private-test-token','SPOT_INSTAGRAM_USER_ID':'123456789'}),self.client(lambda r:httpx.Response(400,json={'error':{'code':code,'message':'instagram-private-test-token'}})) as client:
                client.get('/')
                response=client.post('/api/instagram/search',json={'hashtag':'행사'},headers={'Origin':'http://localhost'})
                self.assertEqual(response.json()['error']['code'],expected)
                self.assertNotIn('instagram-private-test-token',response.text)
        calls=[]
        def quota(request):
            calls.append(request)
            return httpx.Response(200,json={'data':[{'id':str(i),'name':str(i)} for i in range(30)]})
        with patch.dict(os.environ,{'SPOT_INSTAGRAM_ACCESS_TOKEN':'instagram-private-test-token','SPOT_INSTAGRAM_USER_ID':'123456789'}),self.client(quota) as client:
            client.get('/')
            response=client.post('/api/instagram/search',json={'hashtag':'새행사'},headers={'Origin':'http://localhost'})
            self.assertEqual(response.json()['error']['code'],'INSTAGRAM_HASHTAG_LIMIT')
            self.assertEqual(len(calls),1)


if __name__=='__main__':
    unittest.main()
