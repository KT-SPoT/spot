"""Opt-in regional reading and Local/Trend connections for the existing graph."""
from copy import deepcopy
import os

from src.brief.synthesis import apply_synthesis, run_synthesis
from src.brief.connection_synthesis import apply_connection_synthesis, run_connection_synthesis


def synthesis_enabled():
    return (os.getenv('SPOT_BRIEF_SYNTHESIS','off')=='connections'
            and os.getenv('SPOT_SCOUT_MODE')=='live'
            and os.getenv('SPOT_SEMANTIC_MODE','off')=='shadow'
            and os.getenv('SPOT_CRITIC_PROFILE','research')=='research')


def enrich_brief(brief, *, reference_date=None, request=None):
    original=deepcopy(brief)
    if not synthesis_enabled():
        return original
    if request and request.get("store"):
        original['_analysis_context']={'store':{k:request.get('store',{}).get(k) for k in ('name','address','lat','lng')},
            'research':{k:request.get('research',{}).get(k) for k in ('radius_m','reference_date','lookback_days')}}
    baseline=run_synthesis(original)
    original['regional_synthesis']=deepcopy(baseline)
    if not baseline.get('performed') or not baseline.get('insights'):
        original.pop('_analysis_context',None)
        return original
    # The model input ignores diagnostics and previous generated prose.
    enhanced=apply_synthesis(original,baseline)
    connection=run_connection_synthesis(original,baseline,reference_date=reference_date)
    enhanced=apply_connection_synthesis(original,baseline,connection)
    enhanced['connection_synthesis']=deepcopy(connection)
    enhanced.pop('_analysis_context',None)
    return enhanced


def execution_review(brief):
    stages=[brief.get('regional_synthesis',{}),brief.get('connection_synthesis',{})]
    performed=any(s.get('performed') and s.get('insights') for s in stages)
    return {'profile':'research','mode':'shadow','status':'manual_review',
        'performed':performed, 'code':'REGIONAL_SYNTHESIS_EVALUATED' if performed else 'REGIONAL_SYNTHESIS_NOT_APPLIED',
        'call_count':sum(s.get('call_count',0) for s in stages),'truth_verified':False,
        'findings':[], 'case_reviews':[]}
