"""Reinterpret stored Briefs without new Scout/API search calls.

python -m src.evaluate_regional_synthesis --live
Without --live, only the bounded inputs are prepared; no LLM is invoked.
"""
import argparse
import json
from pathlib import Path

from dotenv import load_dotenv

from src.brief.regional_insights import regional_insights
from src.brief.synthesis import apply_synthesis, build_synthesis_input, fingerprint, run_synthesis
from src.brief.connection_synthesis import apply_connection_synthesis, build_connection_input, run_connection_synthesis


def _write(path, value):
    path.write_text(json.dumps(value,ensure_ascii=False,indent=2,allow_nan=False),encoding='utf-8')


def _section(saved, synthesis, applied, connection=None):
    brief=saved['brief'];name=saved.get('request',{}).get('store',{}).get('name','조사 지역')
    q=[c for c in brief['unique_local_signals'] if c.get('module')=='quant']
    local=brief['local_changes']+[c for c in brief['unique_local_signals'] if c.get('module')=='local']
    before=regional_insights(q,local)
    lines=['## '+name,'','### 기존 방식','']
    lines += ['- '+r['title']+': '+r['interpretation'] for r in before[:3]]
    lines += ['','### 통합 해석','']
    cases={c.get('case_id'):c for c in applied['trend_patterns']}
    actions={a['action_id']:a for a in build_synthesis_input(brief)['experience_actions']}
    for row in applied['research_implications'] if synthesis.get('insights') else []:
        stage=connection if row.get('synthesis_stage')=='connections' else synthesis
        iid=row['synthesis_id'].removeprefix('connection/') if row.get('synthesis_stage')=='connections' else row['synthesis_id']
        item=next(i for i in stage['insights'] if i['insight_id']==iid)
        label='추가 인사이트' if row.get('contribution')=='regional_plus' else '기본 해석'
        lines += ['#### '+label+' · '+row['title'],'','**해석**  '+row['interpretation'],'',
                  '**기획 질문**  '+row['question'],'','**해석 범위**  '+row['counterpoint'],'',
                  '**관측**  '+row['observation'],'']
        for link in item['experience_links']:
            case=cases[actions[link['action_id']]['case_id']]
            lines += ['**체험 참고**  '+str(case.get('event_name','')),'',
                      link['why_this_case']+' '+link['comparison_question'],'']
            for source in case.get('sources',[]):
                url=source.get('source_url','').replace('(','%28').replace(')','%29')
                if url:lines.append(f"- 사례 출처: [{source.get('source_id','trend')}]({url})")
            lines.append('')
        sources={(c['module'],s['source_id']):s for c in row['basis'] for s in c['sources']}
        for (module,sid),source in sources.items():
            url=source.get('source_url','').replace('(','%28').replace(')','%29')
            lines.append(f"- 관측 출처: [{module}:{sid}]({url})")
        lines.append('')
    if not synthesis.get('insights'):
        lines += ['이번 검토에서 보고서에 채택할 통합 해석을 선정하지 않았습니다.','']
    return lines


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--input',action='append',dest='inputs')
    parser.add_argument('--output-dir',default='output/synthesis-pilot')
    parser.add_argument('--live',action='store_true')
    parser.add_argument('--connections',action='store_true',help='Add Local/Trend connections after reviewed regional synthesis.')
    parser.add_argument('--base-evaluation-dir',help='Reuse stored source-matched baseline reviews without regeneration.')
    parser.add_argument('--connection-candidate-dir',help='Review previously generated connection candidates without another generation call.')
    parser.add_argument('--candidate-file',action='append',dest='candidate_files',
                        help='Editorial candidate JSON, one per input. GPT only reviews it.')
    args=parser.parse_args()
    load_dotenv(encoding='utf-8-sig')
    paths=args.inputs or ['output/regional-validation/region-0.json','output/regional-validation/region-1.json']
    if args.candidate_files and len(args.candidate_files)!=len(paths):
        parser.error('--candidate-file count must match input count')
    if args.base_evaluation_dir and (not args.connections or args.candidate_files):
        parser.error('--base-evaluation-dir requires --connections and excludes --candidate-file')
    if args.connection_candidate_dir and not args.connections:
        parser.error('--connection-candidate-dir requires --connections')
    root=Path(args.output_dir);root.mkdir(parents=True,exist_ok=True)
    lines=['# 저장된 지역 조사 통합 해석 비교','',
        '기존에 저장된 조사 자료를 재해석한 검증본입니다. 새로운 상권·기사·영상 조회를 실행하지 않았습니다.',
        '매출액 구성은 조사 영역·업종의 집계이며, 개별 매장의 고객 구성이나 선호를 측정한 결과가 아닙니다.','']
    summary=[]
    if args.candidate_files:
        lines += ['본문은 관측에 맞게 편집한 해석 초안을 GPT Critic으로 검토한 예시입니다. 자동 생성 성능 평가는 별도 기록에 보존합니다.','']
    for index,path in enumerate(paths):
        saved=json.loads(Path(path).read_text(encoding='utf-8'))
        payload=build_synthesis_input(saved['brief'])
        _write(root/f'region-{index}-input.json',payload)
        if not args.live:
            if args.connections and args.base_evaluation_dir:
                base=json.loads((Path(args.base_evaluation_dir)/f'region-{index}-evaluation.json').read_text(encoding='utf-8'))
                connection_input=build_connection_input(saved['brief'],base,
                    reference_date=saved.get('request',{}).get('research',{}).get('reference_date'))
                _write(root/f'region-{index}-connection-input.json',connection_input)
            print(json.dumps({'region':index,'observations':len(payload['observations']),
                'actions':len(payload['experience_actions']),'llm_calls':0},ensure_ascii=False))
            continue
        if args.base_evaluation_dir:
            synthesis=json.loads((Path(args.base_evaluation_dir)/f'region-{index}-evaluation.json').read_text(encoding='utf-8'))
            apply_synthesis(saved['brief'],synthesis)
            baseline_calls=0
        elif args.candidate_files:
            candidate=json.loads(Path(args.candidate_files[index]).read_text(encoding='utf-8'))
            synthesis=run_synthesis(saved['brief'],caller=lambda payload:candidate)
            synthesis['generation_source']='agent_editorial'
            synthesis['call_count']=max(0,synthesis['call_count']-1)
            baseline_calls=synthesis['call_count']
        else:
            synthesis=run_synthesis(saved['brief'])
            synthesis['generation_source']='llm'
            baseline_calls=synthesis['call_count']
        applied=apply_synthesis(saved['brief'],synthesis)
        connection=None
        if args.connections:
            connection_caller=None
            if args.connection_candidate_dir:
                old=json.loads((Path(args.connection_candidate_dir)/f'region-{index}-connections.json').read_text(encoding='utf-8'))
                current=build_connection_input(saved['brief'],synthesis,
                    reference_date=saved.get('request',{}).get('research',{}).get('reference_date'))
                if old.get('connection_input_fingerprint')!=fingerprint(current):
                    parser.error('stored connection draft does not match current sources, baseline or reference date')
                candidates={'insights':old['generated_candidates']}
                connection_caller=lambda payload:candidates
            connection=run_connection_synthesis(saved['brief'],synthesis,
                reference_date=saved.get('request',{}).get('research',{}).get('reference_date'),caller=connection_caller)
            if connection_caller:
                connection['generation_source']='reused_model_draft'
                connection['call_count']=max(0,connection['call_count']-1)
            applied=apply_connection_synthesis(saved['brief'],synthesis,connection)
            _write(root/f'region-{index}-connections.json',connection)
        _write(root/f'region-{index}-evaluation.json',synthesis)
        _write(root/f'region-{index}-brief.json',{'request':saved.get('request'),'brief':applied})
        region_lines=_section(saved,synthesis,applied,connection)
        (root/f'region-{index}-comparison.md').write_text('\n'.join(region_lines),encoding='utf-8')
        lines += region_lines
        row={'region':index,'store':saved.get('request',{}).get('store',{}).get('name'),
             'input_file':str(path),'performed':synthesis['performed'],'code':synthesis['code'],
             'accepted_insights':len(synthesis['insights'])+(len(connection['insights']) if connection else 0),
             'connection_insights':len(connection['insights']) if connection else 0,
             'llm_calls':baseline_calls+(connection['call_count'] if connection else 0),
             'baseline_reused':bool(args.base_evaluation_dir), 'scout_calls':0,
             'experience_links':sum(len(i['experience_links']) for stage in (synthesis,connection or {}) for i in stage.get('insights',[]))}
        summary.append(row)
        print(json.dumps(row,ensure_ascii=False),flush=True)
    if args.live:
        _write(root/'summary.json',summary)
        (root/'comparison.md').write_text('\n'.join(lines)+'\n',encoding='utf-8')


if __name__=='__main__':main()
