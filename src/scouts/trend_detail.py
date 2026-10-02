"""Bounded original-text checks and audience transfer questions, never preferences."""
import hashlib
import re
from copy import deepcopy

from src.scouts import search_runtime as search
from src.scouts.local_evidence import ArticleParser, fetch_article, publication_dates
from src.scouts.trend_relevance import contains_experience_keyword

MAX_DETAIL_CASES = 5
MECHANISM_QUESTIONS = {
    'mission_journey': ('미션·스탬프 단계를 휴대폰 기능 비교 과정으로 옮기는', '어느 기능 비교 단계에서 참여하거나 중단할 의향이 있는지'),
    'photo_sharing': ('촬영·공유 요소를 휴대폰 촬영 결과물 비교로 옮기는', '촬영 결과물의 차이를 이해하고 공유할 의향이 있는지'),
    'collectible_reward': ('굿즈·수집 요소를 휴대폰 기능 탐색에 연결하는', '보상에 대한 관심과 제품 기능에 대한 관심을 구분할 수 있는지'),
    'game_interaction': ('게임·도전 요소를 휴대폰 조작 경험 비교로 옮기는', '짧은 조작 과제에서 제품의 차이를 이해할 수 있는지'),
    'direct_product_trial': ('직접 체험 요소를 휴대폰 사용 장면 비교로 옮기는', '설명을 듣는 방식과 직접 비교하는 방식 중 무엇이 이해에 도움이 되는지'),
    'worldbuilding_exploration': ('세계관 요소를 휴대폰 사용 장면의 이야기로 옮기는', '이야기에 대한 관심이 제품 사용 장면의 이해로 이어지는지'),
    'food_discovery': ('취향 탐색 요소를 휴대폰 사용 방식 선택으로 옮기는', '서로 다른 사용 방식을 비교하며 자신에게 맞는 기능을 설명할 수 있는지'),
}


class TrendArticleParser(ArticleParser):
    def __init__(self):
        super().__init__()
        self.titles = []
        self.title_tag = None

    def handle_starttag(self, tag, attrs):
        values = dict(attrs)
        if tag == 'meta' and values.get('property') == 'og:title':
            self.titles.append(values.get('content', ''))
        if tag in ('title', 'h1'):
            self.title_tag = tag
        super().handle_starttag(tag, attrs)

    def handle_endtag(self, tag):
        if tag == self.title_tag:
            self.title_tag = None
        super().handle_endtag(tag)

    def handle_data(self, data):
        if self.title_tag:
            self.titles.append(data)
        super().handle_data(data)


def title_matches(expected, actual):
    def words(value):
        return set(re.findall(r'[a-z0-9가-힣]{2,}', value.lower()))
    wanted = words(expected)
    return bool(wanted) and len(wanted & words(actual)) / len(wanted) >= 0.6


def check_detail(case, source, patterns, start, end, *, fetcher=None):
    result = {'status': 'unavailable', 'checked_at': search.now(),
              'method': 'bounded_article_keyword_check', 'event_verified': False,
              'source_ids': [source['source_id']], 'reported_mechanisms': [],
              'response_signals': [], 'demographic_response_established': False}
    try:
        html, _ = (fetcher or fetch_article)(source['source_url'])
        parser = TrendArticleParser()
        parser.feed(html)
        blocks, extraction = parser.document()
    except search.SearchError as error:
        return {**result, 'reason': error.code}
    except Exception:
        return {**result, 'reason': 'ARTICLE_PARSE_FAILED'}
    result['extraction_method'] = extraction
    if not any(title_matches(case.get('event_name', ''), title) for title in parser.titles):
        return {**result, 'status': 'unconfirmed', 'reason': 'ARTICLE_IDENTITY_NOT_MATCHED'}
    dates = publication_dates(parser.dates)
    if len(dates) > 1:
        return {**result, 'status': 'rejected', 'reason': 'CONFLICTING_ARTICLE_DATES'}
    publication = next(iter(dates), None)
    result['article_published_at'] = publication.isoformat() if publication else None
    if publication and not start <= publication <= end:
        return {**result, 'status': 'rejected', 'reason': 'ARTICLE_OUTSIDE_LOOKBACK'}
    if not blocks:
        return {**result, 'status': 'unconfirmed', 'reason': 'ARTICLE_TEXT_UNAVAILABLE'}
    text = ' '.join(blocks[:40])[:16000]
    # No raw HTML/full articles leave the reader; preserve only term-level checks.
    for key, (_, terms) in patterns.items():
        hits = [term for term in terms if contains_experience_keyword(term, text.lower(), text.lower().replace(' ', ''))]
        if hits:
            result['reported_mechanisms'].append({'mechanism': key, 'matched_terms': hits,
                                                  'source_ids': [source['source_id']]})
    for sentence in re.split(r'(?<=[.!?。])\s+', text):
        if re.search(r'예정|계획|목표|기대|하면|추진|부인|아니|않았|미확인', sentence):
            continue
        attendance = re.search(r'(?:방문객|참여자|관람객|참가자)[^.!?。]{0,30}?(\d[\d,.]*\s*(?:만|천)?\s*명)', sentence)
        if attendance:
            result['response_signals'].append({'kind': 'reported_attendance',
                'reported_value': attendance[1], 'source_ids': [source['source_id']],
                'limitation': '본문의 집계 주장; 해당 행사 귀속·집계 방법·실제 방문·연령별 반응 미검증'})
        if re.search(r'성황|큰 호응|뜨거운 호응|인기', sentence):
            result['response_signals'].append({'kind': 'promotional_response_wording',
                'source_ids': [source['source_id']], 'limitation': '정성·홍보 표현; 측정된 호응이나 연령별 선호 아님'})
    result['response_signals'] = list({str(s): s for s in result['response_signals']}.values())[:3]
    result.update(status='text_corroborated', text_fingerprint=hashlib.sha256(text.encode()).hexdigest(),
                  reason='ARTICLE_WORDING_NOT_EVENT_OR_AUDIENCE_VERIFICATION')
    return result


def audience_fit_questions(case, context):
    detail = case.get('case_detail', {})
    mechanisms = ([m['mechanism'] for m in detail.get('reported_mechanisms', [])]
                  if detail.get('status') == 'text_corroborated' else case.get('taxonomy_tags', []))
    if not mechanisms:
        return []
    questions = [MECHANISM_QUESTIONS[m] for m in mechanisms if m in MECHANISM_QUESTIONS][:2]
    if not questions:
        return []
    transfer = ' / '.join(q[0] for q in questions)
    next_check = ' / '.join(q[1] for q in questions)
    purpose = {'floating_population': '통행 중 관심·체험 참여 의향',
               'resident_population': '생활 속 사용 장면의 공감과 참여 의향',
               'worker_population': '업무·통근 사용 장면의 공감과 참여 의향',
               'sales': '제품 가치 이해와 직접 비교 방식의 적합성'}
    result = []
    for profile in context.get('population_signals', [])[:4]:
        kind = profile.get('population_kind')
        if kind not in purpose or not profile.get('source_ids'):
            continue
        result.append({'kind': 'research_hypothesis', 'population_kind': kind,
            'observed_profile': {k: deepcopy(profile.get(k)) for k in
                ('dominant_age', 'dominant_gender', 'age_share_pct', 'gender_share_pct', 'reference_period')},
            'context_source_refs': [{'module': 'quant', 'source_id': sid} for sid in profile['source_ids']],
            'mechanisms': mechanisms[:4], 'mechanism_source_ids': detail.get('source_ids', []) if detail.get('status') == 'text_corroborated' else case.get('source_ids', []),
            'mechanism_basis': 'article_keyword_check' if detail.get('status') == 'text_corroborated' else 'search_metadata',
            'rationale': f'{transfer} 가설입니다. {purpose[kind]}을 조사합니다. 성별·연령 구성만으로 선호를 확정하지 않습니다.',
            'next_check': f'다음 확인: 해당 모집단의 고객 인터뷰에서 {next_check} 확인합니다. 행사별 성별·연령 반응 자료가 확보되면 대조합니다.',
            'fit_status': 'hypothesis_not_proven_preference'})
    return result


def enrich_references(output, context, patterns, start, end, *, reader=None):
    sources = {s['source_id']: s for s in output['sources']}
    cases = {c['case_id']: c for c in output['insights']}
    log = []
    for reference in output['reference_cases'][:MAX_DETAIL_CASES]:
        case = cases[reference['case_id']]
        source = sources.get(case['source_ids'][0])
        if reader and source and source.get('source_type') == 'news':
            detail = reader(case, source, patterns, start, end)
            case['case_detail'] = detail
            if detail['status'] == 'text_corroborated':
                case['limitations'] = ['기사 제목·본문 표현을 대조했습니다. 실제 행사 여부·참여 고객은 확인하지 않았습니다.'] + case.get('limitations', [])[1:]
            log.append({'case_id': case['case_id'], 'status': detail['status'], 'reason': detail.get('reason')})
        case['audience_fit'] = audience_fit_questions(case, context)
        reference.update(deepcopy({k: case[k] for k in ('case_detail', 'audience_fit', 'limitations') if k in case}))
    output['query_context']['detail_checks'] = log
    if log:
        output['warnings'] = [w for w in output['warnings'] if w != 'SEARCH_METADATA_ONLY_EVENTS_UNVERIFIED']
        output['warnings'].append('OPTIONAL_ARTICLE_WORDING_CHECKS_NOT_EVENT_OR_AUDIENCE_VERIFICATION')
