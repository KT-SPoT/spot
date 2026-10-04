"""A sourced Korean report from the completed Brief, without new provider calls."""
from html import escape
from io import BytesIO
import math
import os
from pathlib import Path
from threading import Lock
from urllib.parse import urlsplit

from reportlab.lib import colors
from reportlab.lib.enums import TA_LEFT
from reportlab.lib.styles import ParagraphStyle
from reportlab.lib.units import mm
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle, KeepTogether

LOCK = Lock()
INK = colors.HexColor('#263c32')
PAPER = colors.HexColor('#f1f2ed')
ACCENT = colors.HexColor('#9a503b')
WIDTH = 174 * mm


def _font():
    with LOCK:
        if 'SpotKorean' in pdfmetrics.getRegisteredFontNames():
            return 'SpotKorean'
        candidates = [os.getenv('SPOT_PDF_FONT_PATH', ''),
                      '/usr/share/fonts/truetype/nanum/NanumGothic.ttf',
                      '/mnt/c/Windows/Fonts/malgun.ttf', 'C:/Windows/Fonts/malgun.ttf']
        font = next((Path(p) for p in candidates if p and Path(p).is_file()), None)
        if font is None:
            raise RuntimeError('PDF_KOREAN_FONT_MISSING')
        pdfmetrics.registerFont(TTFont('SpotKorean', str(font)))
    return 'SpotKorean'


def render_pdf(brief, request=None, discovery=None):
    """Embeds, manually linked videos and Instagram posts are deliberately absent."""
    request = request or {}; discovery = discovery or {}; font = _font()
    styles = {key: ParagraphStyle(key, fontName=font, fontSize=size, leading=leading,
              textColor=INK, spaceAfter=after, wordWrap='CJK', alignment=TA_LEFT)
              for key,size,leading,after in [('body',9,15,7),('small',7.5,12,5),
                  ('title',25,35,15),('heading',15,23,11),('sub',11,18,8)]}
    for key in ('title','heading','sub'):
        styles[key].keepWithNext = True
    story=[]; sources={}
    def p(value,kind='body'):
        return Paragraph(escape(str(value or '자료 미확보')).replace('\n','<br/>'),styles[kind])
    def add(value,kind='body'): story.append(p(value,kind))
    def heading(value): story.extend([Spacer(1,7*mm),p(value,'heading')])
    def refs(card):
        linked=[]
        for source in card.get('sources',[]):
            url=source.get('source_url',''); parts=urlsplit(url)
            if parts.scheme in ('https','http') and parts.hostname and not parts.username and not parts.password:
                if url not in sources: sources[url]=(len(sources)+1,source)
                linked.append(str(sources[url][0]))
        for items in card.get('context_sources',{}).values():
            for source in items:
                refs({'sources':[source]})
        return '출처 '+', '.join(linked) if linked else '출처 미확보'
    def table(rows,widths):
        value=Table(rows,colWidths=widths,repeatRows=1,hAlign='LEFT')
        value.setStyle(TableStyle([('BACKGROUND',(0,0),(-1,0),PAPER),('VALIGN',(0,0),(-1,-1),'TOP'),
            ('LINEBELOW',(0,0),(-1,0),.8,INK),('LINEBELOW',(0,1),(-1,-1),.3,colors.HexColor('#d8ded7')),
            ('TOPPADDING',(0,0),(-1,-1),8),('BOTTOMPADDING',(0,0),(-1,-1),8)]))
        story.append(value)
    store=request.get('store',{}); campaign=request.get('campaign',{}); research=request.get('research',{})
    add('SPoT. / RESEARCH BRIEF','sub');add(store.get('name') or '지역 홍보 리서치','title')
    add(campaign.get('product') or '매장 지역·고객 맥락 리서치','sub')
    add(store.get('address') or '주소 미확인','small')
    add(f"자료 기준일 {research.get('reference_date') or '미확인'} · 고유 출처 {brief.get('source_count',0)}개 · 조사 초안",'small')
    if campaign.get('purpose'): add('조사 질문: '+campaign['purpose'])
    heading('01  지역 요약');add(brief.get('overview',{}).get('area_summary'))
    if brief.get('overview',{}).get('primary_customer_signal'):add(brief['overview']['primary_customer_signal'])
    add('인구·매출 구성은 관측 자료입니다. 고객 선호·구매 의향이나 행사 효과로 단정하지 않습니다.','small')
    heading('02  상권과 고객 구성')
    quant=[c for c in brief.get('unique_local_signals',[]) if c.get('module')=='quant']
    metrics=[c for c in quant if 'value' in c]
    if metrics:
        rows=[[p('관측 항목','small'),p('값','small'),p('기준·근거','small')]]
        for c in metrics:
            value=c['value'];value=f'{value:,}' if isinstance(value,(int,float)) else str(value)
            rows.append([p(c.get('title'),'small'),p(value+str(c.get('unit','')),'small'),p(f"{c.get('reference_period') or '기간 미확인'} / {c.get('scope') or '범위 미확인'}\n{refs(c)}",'small')])
        table(rows,[65*mm,35*mm,74*mm])
    else: add('정량 자료 미확보. 다른 조사 자료를 보존하며 수치를 추정하지 않습니다.')
    labels={'male':'남성','female':'여성','under_10':'10세 미만','teens':'10대','20s':'20대','30s':'30대','40s':'40대','50s':'50대','60_plus':'60대 이상',
            'mon':'월','tue':'화','wed':'수','thu':'목','fri':'금','sat':'토','sun':'일'}
    for c in quant:
        shares=c.get('shares');
        if not isinstance(shares,dict): continue
        rows=[]
        for key,item in shares.items():
            if key=='total': continue
            value=item.get('share_pct') if isinstance(item,dict) else None
            if isinstance(value,bool) or not isinstance(value,(int,float)) or not math.isfinite(value) or not 0<=value<=100: continue
            bar=Table([['']],colWidths=[max(0.5,value)*.8*mm],rowHeights=[3*mm])
            bar.setStyle(TableStyle([('BACKGROUND',(0,0),(-1,-1),INK)]))
            label=labels.get(key,key.replace('_','~')+'시' if key in ('05_09','09_12','12_14','14_18','18_23','23_05') else key)
            rows.append([p(label,'small'),bar,p(f'{value:g}%','small')])
        if rows:
            refs(c); block=[Spacer(1,6*mm),p(c.get('title'),'sub'),p(f"{c.get('scope') or '범위 미확인'} · {c.get('reference_period') or '기간 미확인'} · {refs(c)}",'small')]
            t=Table(rows,colWidths=[32*mm,110*mm,30*mm],hAlign='LEFT');t.setStyle(TableStyle([('VALIGN',(0,0),(-1,-1),'MIDDLE'),('TOPPADDING',(0,0),(-1,-1),5),('BOTTOMPADDING',(0,0),(-1,-1),5)]));block.append(t);story.append(KeepTogether(block))
    heading('03  지역 변화와 생활권 맥락')
    local=brief.get('local_changes',[])+[c for c in brief.get('unique_local_signals',[]) if c.get('module')=='local']
    if not local: add('출처가 연결된 지역 변화 자료 미확보.')
    for c in local:
        story.append(KeepTogether([p(c.get('title'),'sub'),p(c.get('evidence') or c.get('statement')),p(f"{c.get('published_at') or '날짜 미확인'} · {c.get('scope') or '지역 범위 확인 필요'} · {refs(c)}",'small')]))
    heading('04  전국 행사 참고와 홍보 연결점')
    cases=[c for c in brief.get('trend_patterns',[]) if c.get('type') in ('reference_case','audience_context')]
    if not cases: add('출처가 연결된 행사 참고 사례 미확보.')
    for i,c in enumerate(cases,1):
        add(f"{i:02}  {c.get('event_name') or '전국 참고 자료'}",'sub');add(c.get('observation'))
        add(f"{c.get('scope') or '검색 참고 자료'} · {refs(c)}",'small')
        for q in c.get('adaptation_hypotheses',[])[:3]: add('응용 질문: '+q['statement'])
        for fit in c.get('audience_fit',[])[:1]:add(fit.get('rationale'),'small')
    add('참여 방식 분류는 시장 추세·인기도의 증거가 아닙니다. 추가 Instagram 게시물과 수동 연결 영상은 이 보고서의 조사 근거에 포함하지 않습니다.','small')
    if discovery.get('search_plan'):
        heading('탐색 범위와 검색 이유')
        for row in discovery['search_plan']:add(row['query'],'sub');add(row['reason'],'small')
    heading('05  홍보 리서치 시사점')
    add(brief.get('why_here_now'))
    for item in brief.get('research_implications',[]):
        add(item.get('statement') or item.get('title') or item if isinstance(item,dict) else item)
    review=brief.get('research_review',{})
    if review:
        add('고객 연결·차별성 검토: '+('완료' if review.get('performed') else '미완료 / 꺼짐'),'small')
    heading('06  기획 전 확인할 사항')
    for text in brief.get('needs_manual_check',[])[:12]:add('- '+text,'small')
    if not brief.get('needs_manual_check'):add('출처별 시점·범위와 응용 가설을 확인해주세요.')
    heading('출처 목록')
    for url,(n,s) in sources.items():
        add(f"[{n}] {s.get('title') or s.get('source_name') or '원본 자료'}",'small')
        story.append(Paragraph(f'<link href="{escape(url,quote=True)}" color="#315c4d">{escape(url)}</link>',styles['small']))
    def page(canvas,document):
        canvas.setStrokeColor(INK);canvas.line(18*mm,282*mm,192*mm,282*mm)
        canvas.setFont(font,8);canvas.setFillColor(INK);canvas.drawString(18*mm,286*mm,'SPoT. / LOCAL EVIDENCE & PROMOTION RESEARCH')
        canvas.setFont(font,7);canvas.drawString(18*mm,13*mm,'출처와 관측 범위를 확인한 뒤 홍보 기획에 활용하세요.');canvas.drawRightString(192*mm,13*mm,str(document.page))
    output=BytesIO();document=SimpleDocTemplate(output,pagesize=(210*mm,297*mm),leftMargin=18*mm,rightMargin=18*mm,topMargin=23*mm,bottomMargin=23*mm,title='SPoT Research Brief',author='SPoT')
    document.build(story,onFirstPage=page,onLaterPages=page)
    return output.getvalue()
