"""Chart-ready percentages from already validated, same-run provider sections."""
from copy import deepcopy
from math import isfinite

GENDER_KEYS = ('male', 'female')
AGE_KEYS = ('under_10', 'teens', '20s', '30s', '40s', '50s', '60_plus')
DAY_KEYS = ('mon', 'tue', 'wed', 'thu', 'fri', 'sat', 'sun')
TIME_KEYS = ('05_09', '09_12', '12_14', '14_18', '18_23', '23_05')


def valid_share(value):
    return type(value) in (int, float) and isfinite(value) and 0 <= value <= 100


def distribution_cards(sections, sources, scope):
    if not sources:
        return []
    flow = sections.get('population', {}).get('floating_population', {})
    sales = sections.get('sales', {}).get('sales_characteristics', {})
    specs = [
        ('floating_population', 'day', '유동인구 요일별 비중', flow.get('weekday_weekend_and_day_of_week', {}), DAY_KEYS),
        ('floating_population', 'time', '유동인구 시간대별 비중', flow.get('time_band', {}), TIME_KEYS),
        ('sales', 'gender', '매출액 성별 비중', sales.get('demographics', {}), GENDER_KEYS),
        ('sales', 'age', '매출액 연령별 비중', sales.get('demographics', {}), AGE_KEYS[1:]),
        ('sales', 'day', '매출액 요일별 비중', sales.get('day_of_week', {}), DAY_KEYS),
        ('sales', 'time', '매출액 시간대별 비중', sales.get('time_band', {}), TIME_KEYS),
    ]
    cards = []
    for population, dimension, title, table, keys in specs:
        selected = table.get('regions', {}).get('선택 영역', {})
        shares = {}
        for key in keys:
            if population == 'sales':
                entry = {'share_pct': selected.get('amount_share_percent', {}).get(key)}
            else:
                entry = selected.get(key)
            if isinstance(entry, dict) and valid_share(entry.get('share_pct')):
                shares[key] = {'share_pct': entry['share_pct']}
                count = entry.get('count')
                if type(count) in (int, float) and isfinite(count) and count >= 0:
                    shares[key]['count'] = count
        if shares:
            cards.append({'module': 'quant', 'type': 'quant_distribution',
                          'population_kind': population, 'distribution_kind': dimension,
                          'title': title, 'statement': f'{title}: 제공 표의 구성비',
                          'shares': shares, 'reference_period': table.get('reference_period'),
                          'scope': scope, 'sources': deepcopy(sources)})
    return cards
