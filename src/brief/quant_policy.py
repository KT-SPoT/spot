"""Agency observations are a baseline; inferred preferences are not observations."""
from urllib.parse import urlsplit


def is_sbiz_observation_source(source):
    try:
        return (source.get('source_type') == 'government'
                and source.get('source_name') == '소상공인365 상세분석'
                and urlsplit(source.get('source_url', '')).hostname == 'bigdata.sbiz.or.kr')
    except (TypeError, ValueError):
        return False


def quant_basis(sources):
    return ('public_agency_api' if sources and all(is_sbiz_observation_source(s) for s in sources)
            else 'scout_reported_metric')
