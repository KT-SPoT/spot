"""Compare captured regional bundles across web hints, text, and PDF offline.

Run from the repository root with PYTHONPATH=.; this never loads .env or calls Scouts.
"""
import argparse
from copy import deepcopy
from io import BytesIO
import json
import math
from pathlib import Path
import subprocess
import shutil

from pypdf import PdfReader
from src.brief.generator import generate_brief
from src.brief.planning_prompt import build_planning_clues, render_handoff
from src.brief.pdf import render_pdf
from src.brief.renderer import render_markdown
from src.critic.research_review import build_research_input


def compact(text):
    return ''.join(text.split())


def compare(inputs, output, pdf_output):
    output.mkdir(parents=True, exist_ok=True)
    pdf_output.mkdir(parents=True, exist_ok=True)
    rows = []
    models = []
    cases = []
    for index, path in enumerate(inputs):
        bundle = json.loads(path.read_text(encoding='utf-8'))
        before = deepcopy(bundle)
        request = bundle['request']
        brief = generate_brief(bundle, bundle['critic'], quant_evidence=bundle.get('quant_evidence'))
        review_input = build_research_input(bundle, bundle['critic'], quant_evidence=bundle.get('quant_evidence'))
        linked_questions = [h['statement'] for c in brief['trend_patterns'] if c.get('type') == 'reference_case'
                            for h in c.get('adaptation_hypotheses', []) if h.get('statement', '').startswith('지역 관측:')]
        supplied_questions = [h['statement'] for c in review_input['cases']
                              for h in c.get('adaptation_hypotheses', []) if h.get('statement', '').startswith('지역 관측:')]
        assert linked_questions == supplied_questions, 'Critic must receive the same planning connections'
        clues = build_planning_clues(brief, request)
        payload = {'brief': brief, 'request': request}
        executable = shutil.which('node') or shutil.which('node.exe')
        if not executable:
            raise RuntimeError('Node runtime required for web/export parity check')
        node = subprocess.run([executable, '-e',
            "const h=require('./src/web/static/planning-hints.js');"
            "let s='';process.stdin.setEncoding('utf8');process.stdin.on('data',c=>s+=c);"
            "process.stdin.on('end',()=>{const d=JSON.parse(s);process.stdout.write(JSON.stringify(h.build(d.brief,d.request)));});"],
            input=json.dumps(payload, ensure_ascii=False), capture_output=True, text=True, encoding='utf-8', check=True)
        web = json.loads(node.stdout)
        for a, b in zip(clues['fields'], web['fields'], strict=True):
            assert a['hints'] == b['hints'], f"region {index}: web/text clue drift in {a['label']}"
        assert clues['opportunities'] == web['opportunities'], f'region {index}: opportunity drift'
        pdf = render_pdf(brief, request)
        reader = PdfReader(BytesIO(pdf))
        pdf_text = '\n'.join(page.extract_text() for page in reader.pages)
        pdf_compact = compact(pdf_text)
        assert compact(request['store']['name']) in pdf_compact
        assert compact(request['store']['address']) in pdf_compact
        hint_count = 0
        for field in clues['fields']:
            for hint in field['hints']:
                assert compact(hint) in pdf_compact, f"region {index}: PDF clue missing in {field['label']}"
                hint_count += 1
        quant = [c for c in brief['unique_local_signals'] if c.get('module') == 'quant']
        metric_count = share_count = 0
        for card in quant:
            assert compact(card['title']) in pdf_compact, f'region {index}: PDF quant title missing'
            value = card.get('value')
            if isinstance(value, (int, float)) and not isinstance(value, bool) and math.isfinite(value):
                assert compact(f"{value:,}{card.get('unit', '')}") in pdf_compact, f'region {index}: PDF metric missing'
                metric_count += 1
            for key, item in card.get('shares', {}).items():
                share = item.get('share_pct') if isinstance(item, dict) else None
                if key != 'total' and isinstance(share, (int, float)) and not isinstance(share, bool) and math.isfinite(share) and 0 <= share <= 100:
                    assert f'{share:g}%' in pdf_compact, f'region {index}: PDF share missing'
                    share_count += 1
        assert bundle == before, 'Export must not change captured observations'
        tag = f'region-{index}'
        (output / f'{tag}.json').write_text(json.dumps(payload, ensure_ascii=False), encoding='utf-8')
        (output / f'{tag}-brief.md').write_text(render_markdown(brief), encoding='utf-8')
        (output / f'{tag}-clues.txt').write_text(render_handoff(brief, request), encoding='utf-8')
        (pdf_output / f'SPOT-{tag}-research-report.pdf').write_bytes(pdf)
        models.append(web)
        names = {c['event_name'] for c in brief['trend_patterns'] if c.get('type') == 'reference_case'}
        cases.append(names)
        diagnostics = bundle['critic'].get('checks', {}).get('diagnostics', {})
        metrics = bundle['results']['quant']['metrics']
        rows.append({'store': request['store']['name'], 'reference_date': request['research']['reference_date'],
                     'module_status': bundle['module_status'], 'pdf_pages': len(reader.pages),
                     'matched_metrics': metric_count, 'matched_shares': share_count,
                     'matched_clues': hint_count, 'case_count': len(names),
                     'peak_sales_day': metrics.get('peak_sales_day'), 'sales_age': metrics.get('dominant_sales_age'),
                     'peak_floating_day': metrics.get('peak_floating_day'), 'floating_age': metrics.get('dominant_floating_age'),
                     'resident_population': metrics.get('resident_population'), 'worker_population': metrics.get('worker_population'),
                     'captured_gpt_status': diagnostics.get('gpt_status'), 'captured_verdicts': diagnostics.get('case_verdicts')})
    differences = []
    for i in range(1, len(models)):
        differences.append({'against_region': i,
                            'changed_fields': [a['label'] for a, b in zip(models[0]['fields'], models[i]['fields']) if (a['basis'], a['hints']) != (b['basis'], b['hints'])],
                            'shared_nationwide_cases': len(cases[0] & cases[i]),
                            'region_0_only_cases': len(cases[0] - cases[i]), 'other_region_only_cases': len(cases[i] - cases[0])})
    summary = {'provider_calls': 0, 'captured_data_not_fresh_research': True, 'regions': rows, 'comparisons': differences}
    (output / 'summary.json').write_text(json.dumps(summary, ensure_ascii=False, indent=2), encoding='utf-8')
    return summary


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('inputs', type=Path, nargs='+')
    parser.add_argument('--output', type=Path, default=Path('output/regional-validation'))
    parser.add_argument('--pdf-output', type=Path, default=Path('output/pdf/regional-validation'))
    args = parser.parse_args()
    print(json.dumps(compare(args.inputs, args.output, args.pdf_output), ensure_ascii=False, indent=2))
