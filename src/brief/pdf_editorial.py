"""Presentation-only selection and interpretation; never creates observed facts."""
import re


def excerpt(value, terms=(), limit=230):
    text=' '.join(str(value or '').split())
    parts=[p.strip(' .…') for p in re.split(r'\.{3,}|…|(?<=다\.)\s+|(?<=\.)\s+',text) if p.strip(' .…')]
    matching=[p for p in parts if any(t in p for t in terms)]
    chosen=matching[:2] if matching else parts[:2]
    result='. '.join(chosen) or '보도 요약이 제공되지 않았습니다.'
    return result if len(result)<=limit else result[:limit].rstrip()+'…'


def local_reading(card):
    # The article headline may concern another neighborhood. Classify its actual excerpt.
    fact=str(card.get('evidence') or card.get('statement') or '')
    if any(t in fact for t in ('통행','교통','도로 정비','정비공사')):
        return {'topic':'access','headline':'이동 경로 변화는 매장 접근 안내의 점검 계기',
                'fact':excerpt(fact),'meaning':'통행·교통 보도는 방문자가 매장에 접근하는 경로를 살펴볼 자료입니다.',
                'hint':'실제 방문 경로와 현재 통행 상태를 확인한 뒤, 매장 위치·길찾기 안내를 점검하세요.',
                'stage':'통행 재개 보도' if '재개' in fact else '교통 관련 보도'}
    if any(t in fact for t in ('업무협약','MOU','도심복합개발','입주를','입주가','입주 시작')):
        planned=any(t in fact for t in ('업무협약','MOU','추진','참여한다'))
        return {'topic':'housing','headline':'주거 개발 소식은 생활권 변화의 추적 자료',
                'fact':excerpt(fact),'meaning':'주거 개발의 진행 단계는 향후 생활권 변화를 살펴볼 단서입니다. 준비 단계의 보도를 현재 고객 증가로 해석하지 않습니다.',
                'hint':'사업 위치·일정과 매장 생활권을 비교해, 생활정보 안내나 생활 속 휴대폰 사용 장면을 기획할 때 참고하세요.',
                'stage':'협약·추진 단계' if planned else '주거 변화 보도'}
    if any(t in fact for t in ('개관','개점','신설','개통')):
        return {'topic':'facility','headline':'시설 변화는 방문 목적과 이동 동선의 참고 자료',
                'fact':excerpt(fact),'meaning':'시설 이용 목적과 매장 방문 동선의 연결을 살펴볼 수 있습니다.',
                'hint':'시설의 운영 시점·위치를 확인하고, 방문 동선에 맞는 매장 발견·체험 안내를 검토하세요.',
                'stage':'시설 변화 보도'}
    return None


def select_local(cards):
    main=[];extra=[];topics=set()
    for card in cards:
        reading=local_reading(card)
        if reading and reading['topic'] not in topics:
            topics.add(reading['topic']);main.append((card,reading))
        else:
            # Related reports remain in the appendix; no assertion that they are the same event.
            extra.append(card)
    return main,extra


def trend_reading(card):
    fact=str(card.get('observation') or '')
    mechanisms={q.get('mechanism') for q in card.get('adaptation_hypotheses',[]) if isinstance(q,dict)}
    choices=[
        ('collectible_reward',('굿즈','수집','소장','기념품'), '체험을 행사 전후의 굿즈·소장 접점으로 확장',
         '현장 체험 외에 기념품·소장 요소를 통해 행사의 접점을 이어가는 방식을 참고할 수 있습니다.',
         '휴대폰 체험을 마친 뒤 촬영 결과물이나 작은 기념물을 가져가는 흐름을 검토하세요. 보상과 제품 기능 체험의 목적은 구분합니다.'),
        ('photo_sharing',('촬영','SNS','공유','유튜브'), '현장 체험을 촬영·공유 콘텐츠로 연결',
         '체험 장면을 촬영·소개하는 과정 자체를 행사의 또 다른 접점으로 활용하는 방식입니다.',
         '카메라 체험에서 촬영 → 결과물 비교 → 선택적 공유로 이어지는 동선을 검토하세요.'),
        ('direct_product_trial',('체험','직접 사용','비교'), '설명을 듣는 방문을 직접 해보는 경험으로 전환',
         '프로그램을 직접 체험하게 하는 참여 방식을 참고할 수 있습니다.',
         '매장에서 방문자가 일상 사용 장면을 골라 기능을 직접 써보고 비교하는 짧은 체험을 검토하세요.')]
    # Mixed news roundups do not establish one coherent event.
    if ('□' in fact or '브리핑' in str(card.get('event_name',''))) and '...' in fact:
        return None
    for mechanism,terms,headline,meaning,hint in choices:
        if mechanism in mechanisms and any(term in fact for term in terms):
            return {'headline':headline,'fact':excerpt(fact,terms),'meaning':meaning,'hint':hint}
    return None
