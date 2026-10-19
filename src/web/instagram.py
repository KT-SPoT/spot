"""Explicit read-only hashtag lookup. No tokens or raw provider errors returned."""
import re
from datetime import datetime, timezone
from urllib.parse import urlsplit

import httpx


class InstagramError(Exception):
    pass


async def search(token, user_id, version, hashtag, *, transport=None):
    if not token or not re.fullmatch(r'\d{5,30}', user_id or ''):
        raise InstagramError('INSTAGRAM_NOT_CONFIGURED')
    if not re.fullmatch(r'v\d{1,3}\.0', version):
        raise InstagramError('INSTAGRAM_NOT_CONFIGURED')
    async with httpx.AsyncClient(timeout=12, follow_redirects=False, transport=transport,
                                headers={'Authorization': 'Bearer ' + token}) as client:
        async def get(path, params):
            try:
                async with client.stream('GET', f'https://graph.facebook.com/{version}/{path}', params=params) as response:
                    body = bytearray()
                    async for chunk in response.aiter_bytes():
                        body.extend(chunk)
                        if len(body) > 500_000:
                            raise InstagramError('INSTAGRAM_UNAVAILABLE')
                    import json
                    data = json.loads(body)
                error = data.get('error', {}) if isinstance(data, dict) else {}
                code = error.get('code') if isinstance(error, dict) else None
                if code == 190:
                    raise InstagramError('INSTAGRAM_TOKEN_EXPIRED')
                if code in (10, 200) or response.status_code == 403:
                    raise InstagramError('INSTAGRAM_PERMISSION_REQUIRED')
                if code in (4, 17, 32, 613) or response.status_code == 429:
                    raise InstagramError('INSTAGRAM_RATE_LIMIT')
                if code == 100:
                    raise InstagramError('INSTAGRAM_REQUEST_REJECTED')
                if response.status_code != 200 or not isinstance(data, dict) or error:
                    raise InstagramError('INSTAGRAM_UNAVAILABLE')
                return data
            except (httpx.HTTPError, ValueError, TypeError):
                raise InstagramError('INSTAGRAM_UNAVAILABLE') from None

        # Provider history survives server restarts. Fail closed on incomplete history.
        history = await get(f'{user_id}/recently_searched_hashtags', {'fields': 'id,name', 'limit': 100})
        rows = history.get('data')
        if not isinstance(rows, list) or any(not isinstance(row, dict) for row in rows):
            raise InstagramError('INSTAGRAM_UNAVAILABLE')
        names = {str(row.get('name', '')).casefold() for row in rows}
        paging = history.get('paging', {})
        if not isinstance(paging, dict):
            raise InstagramError('INSTAGRAM_UNAVAILABLE')
        if paging.get('next') or len(rows) >= 30 and hashtag.casefold() not in names:
            raise InstagramError('INSTAGRAM_HASHTAG_LIMIT')
        found = await get('ig_hashtag_search', {'user_id': user_id, 'q': hashtag})
        matches = found.get('data')
        if not isinstance(matches, list):
            raise InstagramError('INSTAGRAM_UNAVAILABLE')
        items = []
        if matches:
            identity = str(matches[0].get('id', '')) if isinstance(matches[0], dict) else ''
            if not re.fullmatch(r'\d{5,30}', identity):
                raise InstagramError('INSTAGRAM_UNAVAILABLE')
            media = await get(f'{identity}/recent_media', {'user_id': user_id, 'fields': 'id,caption,permalink', 'limit': 6})
            if not isinstance(media.get('data'), list):
                raise InstagramError('INSTAGRAM_UNAVAILABLE')
            for row in media['data'][:6]:
                if not isinstance(row, dict):
                    continue
                url = row.get('permalink', '')
                try:
                    parsed = urlsplit(url)
                    if parsed.scheme != 'https' or parsed.hostname not in ('instagram.com', 'www.instagram.com') or parsed.username or parsed.password:
                        continue
                    if not re.fullmatch(r'/(p|reel)/[A-Za-z0-9_-]{5,64}/?', parsed.path):
                        continue
                    items.append({'url': 'https://www.instagram.com' + parsed.path, 'caption': str(row.get('caption', ''))[:1500]})
                except (ValueError, TypeError):
                    continue
        return {'hashtag': hashtag, 'items': items, 'collected_at': datetime.now(timezone.utc).isoformat(),
                'evidence_status': 'reference_only'}
