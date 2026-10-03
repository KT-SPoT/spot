"""Evidence-conditioned research lenses, without demographic taste assignments."""
from math import isfinite

AGE_KEYS = ('under_10', 'teens', '20s', '30s', '40s', '50s', '60_plus')
POPULATIONS = {'floating_population': '유동인구', 'resident_population': '주거인구',
               'worker_population': '직장인구', 'sales': '매출 비중'}
DAY_LABELS = dict(zip(('mon', 'tue', 'wed', 'thu', 'fri', 'sat', 'sun'),
                      ('월요일', '화요일', '수요일', '목요일', '금요일', '토요일', '일요일')))
TIME_BANDS = ('05_09', '09_12', '12_14', '14_18', '18_23', '23_05')


def share(value):
    return value if (isinstance(value, (int, float)) and not isinstance(value, bool)
                     and isfinite(value) and 0 <= value <= 100) else None


def refs(module, ids):
    return [{'module': module, 'source_id': sid} for sid in ids if isinstance(sid, str) and sid]


def audience_lenses(profile, context):
    """Rules describe comparison design, never popularity or a required audience."""
    kind = profile['population_kind']
    provenance = refs('quant', profile.get('source_ids', []))
    lenses = []

    def add(axis, rule, observation, question, sources=provenance):
        lenses.append({'axis': axis, 'rule': rule, 'observation': observation,
                       'question': question, 'context_source_refs': sources})

    values = profile.get('shares') if isinstance(profile.get('shares'), dict) else {}
    ages = {key: share(values.get(key, {}).get('share_pct')) for key in AGE_KEYS
            if isinstance(values.get(key), dict)}
    ages = {key: value for key, value in ages.items() if value is not None}
    # Require an approximately complete table; partial distributions cannot prove
    # that an audience is broad/concentrated. Thresholds are design heuristics.
    if len(ages) >= 2 and 99 <= sum(ages.values()) <= 101:
        maximum = max(ages.values())
        concentrated = maximum >= 50
        add('age_distribution', 'concentrated' if concentrated else 'distributed',
            f"{POPULATIONS[kind]} 연령 분포의 최대 비중 {maximum:g}%; 성별과의 교차 비율은 미확인.",
            '주요 연령대의 사용 장면과 그 밖의 연령대도 선택할 수 있는 사용 장면을 함께 비교할 수 있을까?'
            if concentrated else '한 연령대의 사용 장면으로 좁히지 않고 여러 사용 장면 중 직접 고르는 방식으로 비교할 수 있을까?')
    else:
        add('age_distribution', 'distribution_unavailable',
            '연령 전체 분포가 없어 주요 연령대만으로 참여 범위를 좁힐 수 없습니다.',
            '연령별 취향을 가정하지 않고 사용 장면을 직접 고르게 해 기능 차이를 설명할 수 있을까?')
    genders = [share(values.get(key, {}).get('share_pct')) if isinstance(values.get(key), dict) else None
               for key in ('male', 'female')]
    if all(value is not None for value in genders) and 99 <= sum(genders) <= 101:
        maximum = max(genders)
        concentrated = maximum >= 60
        add('gender_distribution', 'concentrated' if concentrated else 'balanced',
            f"{POPULATIONS[kind]} 성별 분포의 최대 비중 {maximum:g}%; 행사 선호 자료는 아닙니다.",
            '비중이 큰 성별 중심으로 해석해도 되는지, 다른 성별도 같은 비교 과정에 참여할 수 있는지 함께 검토할 수 있을까?'
            if concentrated else '특정 성별을 겨냥한 소재보다 누구나 선택 가능한 사용 장면으로 체험을 구성할 수 있을까?')

    timing = {row['population_kind']: row for row in context.get('timing_signals', [])
              if row.get('population_kind') in POPULATIONS and row.get('source_ids')}
    own = timing.get(kind)
    other_kind = 'sales' if kind == 'floating_population' else 'floating_population' if kind == 'sales' else None
    other = timing.get(other_kind)
    if own:
        day = DAY_LABELS.get(own.get('peak_day'))
        band = own.get('peak_time_band')
        # Allow only provider time-band codes, not arbitrary instructions/text.
        band = band if isinstance(band, str) and band in TIME_BANDS else None
        if day or band:
            observation = f"{POPULATIONS[kind]} 최다 관측: " + ' / '.join(filter(None, (day, band.replace('_', '~') + '시' if band else None)))
            matching = [key for key, allowed in (('peak_day', DAY_LABELS), ('peak_time_band', TIME_BANDS))
                        if other and own.get(key) in allowed and other.get(key) in allowed]
            comparable_periods = not (own.get('reference_period') and other and other.get('reference_period')
                                      and own['reference_period'] != other['reference_period'])
            if matching and comparable_periods:
                different = any(own[key] != other[key] for key in matching)
                add('timing', 'flow_sales_differ' if different else 'flow_sales_align',
                    observation + ('; 유동·매출 최다 요일/시간 일부가 다릅니다.' if different else '; 유동·매출의 확인 가능한 최다 요일/시간이 같습니다.')
                    + (' 기준 기간 동일 여부는 미확인입니다.' if not own.get('reference_period') or not other.get('reference_period') else ''),
                    '관심을 끄는 도입 체험과 제품 가치를 비교하는 체험을 서로 다른 방문 상황에 나눠 검토할 수 있을까?'
                    if different else '관심을 끄는 도입 체험에서 제품 가치 비교까지 같은 방문 흐름으로 연결할 수 있을까?',
                    refs('quant', own['source_ids'] + other['source_ids']))
            else:
                add('timing', 'single_population_peak', observation + '; 체류 시간·방문 목적은 미확인.'
                    + (' 유동·매출 기준 기간이 달라 같은 방문 흐름으로 묶지 않습니다.' if not comparable_periods else ''),
                    '최다 시간대의 통행·방문 상황에서도 한 단계 비교와 연속 비교 중 어떤 방식으로 기능 차이를 이해할 수 있을까?',
                    refs('quant', own['source_ids']))

    for local in context.get('local_signals', []):
        if local.get('verification_status') not in ('text_corroborated', 'context_corroborated') or not local.get('source_ids'):
            continue
        text = local.get('title', '') + ' ' + local.get('evidence', '')
        if kind in ('floating_population', 'worker_population') and any(word in text for word in ('교통', '버스', '통근', '도로')):
            rule, question = 'access_context', '이동 경로와 매장 발견 상황을 고려해 첫 비교 과제를 알아보기 쉽게 제시할 수 있을까?'
        elif kind == 'resident_population' and any(word in text for word in ('입주', '주거', '주택', '아파트')):
            rule, question = 'residential_context', '주거 변화 맥락을 생활 속 사용 장면 선택으로 연결할 수 있을까? 실제 입주·생활권 영향은 별도로 구분합니다.'
        else:
            continue
        # A surrounding/scheduled change remains such; never turn it into store demand.
        role = {'direct_change':'대상지 변화', 'surrounding_context':'주변 맥락', 'background':'지역 배경'}.get(local.get('evidence_role'), '범위 미확인')
        state = {'scheduled':'예정', 'completed':'완료', 'ongoing':'진행 중'}.get(local.get('change_state'), '진행 상태 미확인')
        observation = f"Local 맥락: {local.get('title', '')[:100]} ({role}, {state}); 점포 수요 영향 미확인."
        add('local_context', rule, observation, question, refs('local', local['source_ids']))
        break
    return lenses
