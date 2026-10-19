"""Kakao Local search, using a server-only REST key and fixed destinations."""
import math
import httpx


class PlaceError(Exception):
    pass


async def lookup(key, path, params, transport=None):
    if not key:
        raise PlaceError("MAP_NOT_CONFIGURED")
    try:
        async with httpx.AsyncClient(timeout=10, transport=transport, follow_redirects=False) as client:
            response = await client.get('https://dapi.kakao.com/v2/local/' + path,
                                        params=params, headers={'Authorization': 'KakaoAK ' + key})
        if response.status_code != 200:
            raise PlaceError("PLACE_PROVIDER_UNAVAILABLE")
        documents = response.json()['documents']
        if not isinstance(documents,list) or any(not isinstance(item,dict) for item in documents):
            raise PlaceError("PLACE_PROVIDER_UNAVAILABLE")
        return documents[:30]
    except (httpx.HTTPError, ValueError, KeyError, TypeError):
        raise PlaceError("PLACE_PROVIDER_UNAVAILABLE") from None


async def search(key, query, transport=None):
    places = await lookup(key, 'search/keyword.json', {'query':query, 'size':15}, transport)
    addresses = await lookup(key, 'search/address.json', {'query':query, 'size':5}, transport)
    result, seen = [], set()
    for item in places + addresses:
        try:
            lat, lng = float(item['y']), float(item['x'])
            if not math.isfinite(lat + lng) or not (32 <= lat <= 39.5 and 124 <= lng <= 132):
                continue
        except (KeyError, ValueError, TypeError):
            continue
        address = item.get('road_address_name') or item.get('address_name', '')
        identity = (item.get('place_name',address),lat,lng)
        if identity in seen or not address:
            continue
        seen.add(identity)
        result.append({'name':identity[0], 'address':address, 'lat':lat, 'lng':lng,
                       'kind':'store' if item.get('place_name') else 'address'})
    return result
