"""Compare audience sensitivity on one frozen search snapshot; never call providers.

python -m src.evaluation.trend_audience --bundle saved-result.json \
    --cache search-cache.json --output .venv/verification/trend-audience
"""
import argparse
from copy import deepcopy
from hashlib import sha256
from itertools import combinations
import json
import os
from pathlib import Path
from unittest.mock import patch

from src.scouts import search_runtime as search
from src.scouts.trend import run_trend_scout
from src.validation import validate_scout_result

AGE_LABELS = {'20s':'20대','40s':'40대','60_plus':'60대 이상'}
GENDER_LABELS = {'male':'남성','female':'여성'}


def signature(value):
    return sha256(json.dumps(value,ensure_ascii=False,sort_keys=True).encode()).hexdigest()


def profile(context, age, gender, *, kind='floating_population'):
    """Synthetic intervention, not a changed official observation or joint cohort."""
    result = deepcopy(context)
    result['evaluation_only'] = True
    result['population_signals'] = [{
        'population_kind':kind, 'dominant_age':age, 'dominant_gender':gender,
        'age_share_pct':None, 'gender_share_pct':None, 'reference_period':None,
        'source_ids':['EVAL-QUANT-PROFILE'], 'evidence_basis':'synthetic_evaluation_input',
    }]
    result.setdefault('sources',{})['quant'] = [{'source_id':'EVAL-QUANT-PROFILE',
        'source_name':'합성 고객층 비교 입력 (공공 관측값 아님)', 'source_type':'synthetic'}]
    result.setdefault('limitations',[]).append('고객층만 바꾼 합성 비교 입력입니다. 실제 점포의 관측값으로 사용하지 않습니다.')
    return result


def replay(request, context, cache, details=None):
    before = signature([request,context,cache,details])
    calls=[]
    def news(query,start,end):
        if query not in cache:
            raise ValueError('Snapshot lacks a requested query; live fallback is forbidden')
        calls.append(query)
        return deepcopy(cache[query])
    def detail_reader(case,source,*_):
        cached = (details or {}).get(source['source_url'])
        if not cached:
            return {'status':'unavailable','reason':'NOT_IN_SAVED_DETAIL_SNAPSHOT',
                    'source_ids':[source['source_id']], 'reported_mechanisms':[], 'response_signals':[],
                    'event_verified':False, 'demographic_response_established':False}
        value=deepcopy(cached)
        value['source_ids']=[source['source_id']]
        for item in value.get('reported_mechanisms',[]) + value.get('response_signals',[]):
            item['source_ids']=[source['source_id']]
        return value
    def forbidden(*args,**kwargs):
        raise AssertionError('Evaluation must not contact external providers')
    with patch.dict(os.environ,{'SPOT_SCOUT_MODE':'evaluation_replay',
                               'SPOT_TREND_VIDEO_MODE':'off','SPOT_TREND_DETAIL_MODE':'off'}), \
         patch('src.scouts.search_runtime.news',side_effect=news) as provider, \
         patch('src.scouts.search_runtime.videos',side_effect=forbidden), \
         patch('src.scouts.search_runtime.get_json',side_effect=forbidden), \
         patch('src.scouts.local_evidence.fetch_article',side_effect=forbidden), \
         patch('src.scouts.trend_detail.fetch_article',side_effect=forbidden):
        provider.__name__='news'
        output=run_trend_scout(deepcopy(request),context=deepcopy(context),
                               detail_reader=detail_reader if details else None)
    if validate_scout_result(output,expected_module='trend',request_id=request['request_id']):
        raise ValueError('Invalid Scout contract in audience evaluation')
    if before != signature([request,context,cache,details]):
        raise AssertionError('Evaluation mutated an input snapshot')
    return output,calls


def projection(result):
    sources={s['source_id']:s['source_url'] for s in result['sources']}
    def url(case):
        return sources[case['source_ids'][0]]
    references=result['reference_cases']
    # Strip profiles/boilerplate before comparing substance. Changing an age label
    # alone must not be counted as a different adaptation or validation question.
    return {
        'queries':result['query_context']['search_queries'],
        'selected_urls':[url(c) for c in references],
        'scores':{url(c):c['reference_priority_score'] for c in result['insights']},
        'audience_labels':{url(c):c.get('audience_hypothesis') for c in references},
        'adaptations':{url(c):c.get('adaptation_hypotheses',[]) for c in references},
        'fit_questions':{url(c):[{'population_kind':f['population_kind'],
                                 'rationale':f['rationale'],'next_check':f['next_check']}
                                for f in c.get('audience_fit',[])] for c in references},
        'profile_echoes':{url(c):[f.get('observed_profile') for f in c.get('audience_fit',[])] for c in references},
    }


def compare(left,right):
    a,b=projection(left),projection(right)
    common=set(a['selected_urls']) & set(b['selected_urls'])
    union=set(a['selected_urls']) | set(b['selected_urls'])
    candidates=set(a['scores']) & set(b['scores'])
    return {
        'queries_equal':a['queries']==b['queries'],
        'selection_order_equal':a['selected_urls']==b['selected_urls'],
        'selection_overlap':len(common)/len(union) if union else None,
        'common_reference_count':len(common),
        'changed_score_count':sum(a['scores'][u]!=b['scores'][u] for u in candidates),
        'changed_audience_label_count':sum(a['audience_labels'][u]!=b['audience_labels'][u] for u in common),
        'changed_adaptation_count':sum(a['adaptations'][u]!=b['adaptations'][u] for u in common),
        'changed_fit_question_count':sum(a['fit_questions'][u]!=b['fit_questions'][u] for u in common),
        'changed_profile_echo_count':sum(a['profile_echoes'][u]!=b['profile_echoes'][u] for u in common),
    }


def evaluate(request,context,cache,details=None):
    outputs,labels={},{}
    for age in AGE_LABELS:
        for gender in GENDER_LABELS:
            key=f'{age}-{gender}'
            labels[key]={'age':age,'gender':gender,'label':f'{AGE_LABELS[age]} / {GENDER_LABELS[gender]}'}
            outputs[key],_=replay(request,profile(context,age,gender),cache,details)
    comparisons=[]
    for left,right in combinations(outputs,2):
        a,b=labels[left],labels[right]
        axis='gender_only' if a['age']==b['age'] else 'age_only' if a['gender']==b['gender'] else 'both'
        comparisons.append({'left':left,'right':right,'axis':axis,**compare(outputs[left],outputs[right])})
    first=next(iter(outputs));again,_=replay(request,profile(context,'20s','male'),cache,details)
    repeatable=projection(outputs[first])==projection(again)
    empty=deepcopy(context);empty['population_signals']=[];empty['sources']['quant']=[]
    missing,_=replay(request,empty,cache,details)
    mixed=profile(context,'20s','female')
    mixed['population_signals'].append(profile(context,'60_plus','male',kind='sales')['population_signals'][0])
    mixed_output,_=replay(request,mixed,cache,details)
    refs=mixed_output['reference_cases']
    missing_clean=all(not c.get('audience_fit') for c in missing['reference_cases'])
    expected_profiles={('floating_population','20s','female'),('sales','60_plus','male')}
    mixed_separated=bool(refs) and all({(f['population_kind'],f.get('observed_profile',{}).get('dominant_age'),
                                        f.get('observed_profile',{}).get('dominant_gender'))
                                       for f in c.get('audience_fit',[])}==expected_profiles for c in refs)
    summary={
        'input_kind':'real_search_snapshot_with_synthetic_audience_interventions',
        'network_calls':{'naver':0,'youtube':0,'gpt':0,'articles':0},
        'reference_date':request.get('research',{}).get('reference_date'),
        'search_snapshot_rows':sum(len(items) for items in cache.values()),
        'profile_count':len(outputs), 'repeatable':repeatable,
        'missing_profile_has_no_fit':missing_clean, 'mixed_population_kept_separate':mixed_separated,
        'cases':[{**labels[key],'key':key,'candidate_count':len(result['insights']),
                  'reference_count':len(result['reference_cases']),
                  'references':[{'title':c['event_name'],'url':u} for c,u in zip(result['reference_cases'],projection(result)['selected_urls'])]}
                 for key,result in outputs.items()],
        'comparisons':comparisons,
    }
    for label,field in [('selection_changes','selection_order_equal'),('adaptation_changes','changed_adaptation_count'),('fit_question_changes','changed_fit_question_count')]:
        summary[label]=sum(not row[field] if field=='selection_order_equal' else row[field]>0 for row in comparisons)
    summary['verdict']='partial_audience_conditioning' if summary['adaptation_changes']==0 and summary['fit_question_changes']==0 else 'audience_sensitive_output_requires_quality_review'
    if not any(row['reference_count'] for row in summary['cases']):
        summary['verdict']='insufficient_reference_evidence'
    if not repeatable or not missing_clean or (refs and not mixed_separated):
        summary['verdict']='evaluation_invariant_failed'
    return summary,outputs


def render_report(summary):
    lines=['# Trend 고객층 비교 검증','',
           '동일한 저장 뉴스 자료에 합성 고객층만 바꿔 비교했습니다. 실제 상권의 성별·연령 관측을 수정한 결과가 아닙니다.',
           f"조사 기준일: {summary['reference_date']} / 검색 행 {summary['search_snapshot_rows']}개 / 비교 입력 {summary['profile_count']}개.",
           '새 네이버·YouTube·GPT·기사 호출은 모두 0회입니다. 오늘 새로 수집한 트렌드 검증은 아닙니다.','',
           '| 고객층 비교 입력 | 후보 | 참고 사례 |','|---|---:|---:|']
    for row in summary['cases']:
        lines.append(f"| {row['label']} | {row['candidate_count']} | {row['reference_count']} |")
    lines.extend(['','| 비교 | 변경 축 | 사례 겹침 | 순서 동일 | 점수 변경 | 응용 문장 변경 | 조사 질문 변경 |',
                  '|---|---|---:|---|---:|---:|---:|'])
    labels={row['key']:row['label'] for row in summary['cases']}
    for row in summary['comparisons']:
        if row['axis']=='both':continue
        overlap='자료 없음' if row['selection_overlap'] is None else f"{row['selection_overlap']:.0%}"
        lines.append(f"| {labels[row['left']]} ↔ {labels[row['right']]} | {row['axis']} | {overlap} | {'예' if row['selection_order_equal'] else '아니오'} | {row['changed_score_count']} | {row['changed_adaptation_count']} | {row['changed_fit_question_count']} |")
    lines.extend(['',f"반복 실행 동일: {summary['repeatable']} / 고객층 미확보 시 가설 미생성: {summary['missing_profile_has_no_fit']} / 유동·매출 모집단 분리: {summary['mixed_population_kept_separate']}",
                  '',f"판정: `{summary['verdict']}`",'',
                  '사례가 겹친다는 사실만으로 실패로 판정하지 않습니다. 전국 공통 사례도 고객층별 검토 대상이 될 수 있습니다.',
                  '성별·연령 표기만 바뀐 경우는 응용 내용 변화로 세지 않습니다. 기사에 고객층 단어가 없으면 점수도 같을 수 있습니다.',
                  '이 검증은 고객층 입력의 반영 정도를 확인하며 실제 선호·호응·매출 효과를 검증하지 않습니다.'])
    return '\n'.join(lines)+'\n'


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--bundle',type=Path,required=True)
    parser.add_argument('--cache',type=Path,required=True)
    parser.add_argument('--output',type=Path,required=True)
    args=parser.parse_args()
    try:
        stored=json.loads(args.bundle.read_text(encoding='utf-8-sig'))
        bundle=stored.get('research_bundle',stored)
        trend=bundle['results']['trend'];request=bundle['request']
        context=trend['query_context']['upstream_context']
        cache={entry['query']:entry['items'] for entry in json.loads(args.cache.read_text(encoding='utf-8-sig'))}
        sources={s['source_id']:s['source_url'] for s in trend['sources']}
        details={sources[c['source_ids'][0]]:c['case_detail'] for c in trend['reference_cases'] if c.get('case_detail')}
        summary,outputs=evaluate(request,context,cache,details)
    except (OSError,KeyError,ValueError,TypeError):
        parser.error('Cannot evaluate supplied snapshots; no live provider fallback was attempted')
    args.output.mkdir(parents=True,exist_ok=True)
    (args.output/'summary.json').write_text(json.dumps(summary,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
    (args.output/'COMPARISON.md').write_text(render_report(summary),encoding='utf-8')
    (args.output/'outputs.json').write_text(json.dumps(outputs,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
    print(json.dumps({key:summary[key] for key in ('verdict','profile_count','reference_date','search_snapshot_rows','selection_changes','adaptation_changes','fit_question_changes','repeatable','missing_profile_has_no_fit','mixed_population_kept_separate','network_calls')},ensure_ascii=False,indent=2))
    return 1 if summary['verdict']=='evaluation_invariant_failed' else 0


if __name__=='__main__':
    raise SystemExit(main())
