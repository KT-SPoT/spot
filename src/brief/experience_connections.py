"""Bounded planning questions from separate observations and reported actions.

No preference assignments, new evidence, provider calls or operational plans.
"""
import re


def reported_actions(case):
    text = str(case.get('observation') or '')
    name = str(case.get('event_name') or '')
    if not case.get('sources') or not text or ('...' in text and ('□' in text or '브리핑' in name)):
        return []
    tags = {h.get('mechanism') for h in case.get('adaptation_hypotheses', []) if isinstance(h, dict)}
    tags.update(case.get('taxonomy_tags', []))
    actions = []
    # A category alone (or the word 체험 alone) does not establish an action.
    if 'photo_sharing' in tags and re.search(r'촬영|사진|영상', text) and re.search(r'공유|SNS|소개|게시', text):
        promoter = bool(re.search(r'홍보대사|홍보활동|개인 SNS', name+' '+text))
        actions.append(('photo_sharing', '홍보자가 현장을 촬영해 소개한 방식' if promoter else '촬영 결과를 공유하는 방식',
                        '사진 촬영·정리·전송 등 실제 사용 과제를 보여주는 체험'))
    if 'collectible_reward' in tags and re.search(r'굿즈|소장|기념품|수집', text) and re.search(r'구매|판매|증정|제공|소장|수집', text):
        actions.append(('collectible_reward', '관련 물건을 구매·소장하도록 연결한 방식',
                        '기능 체험 결과를 완료 카드·사진 결과물 같은 가져갈 물건으로 연결하는 접점'))
    # News descriptions also report trying a product as "직접 보고 체험" or
    # "제품을 직접 경험". Retain these explicit actions without treating the
    # category or a recommendation to hold a future event as an actual trial.
    trial_sentences = [s for s in re.split(r'[.!?\n]', text)
                       if not re.search(r'해야\s*(?:함|한다|합니다)|하여야|권장|추천|넓혀야', s)]
    trial_pattern = r'직접\s+(?:(?:보고|만져보고|써보고)\s*)?(?:사용|체험|경험|만져)|게임을\s*체험|시연|써보|비교'
    if 'direct_product_trial' in tags and any(re.search(trial_pattern, s) for s in trial_sentences):
        actions.append(('direct_product_trial', '직접 사용·시연·비교하는 방식', '스마트폰 기능을 직접 써보고 차이를 비교하는 체험'))
    if 'mission_journey' in tags and re.search(r'미션|스탬프', text) and re.search(r'수행|완료|모으|달성', text):
        actions.append(('mission_journey', '과제를 수행하고 완료 결과를 확인하는 방식', '스마트폰 기능 비교를 작은 사용 과제와 완료 결과로 보여주는 체험'))
    return actions


def connections(case, quant, local=()):
    """Connect an observed action to a sourced regional planning lens."""
    from src.brief.regional_insights import regional_insights, case_connections
    return case_connections(case, regional_insights(quant, local), reported_actions(case))
