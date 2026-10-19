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
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle, KeepTogether, PageBreak
from reportlab.graphics.shapes import Drawing, Rect, String, Line
from src.brief.pdf_editorial import excerpt, select_local, trend_reading
from src.brief.publication import publication_text
from src.brief.area_summary import area_summary

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
        bold = font.with_name('NanumGothicBold.ttf') if 'Nanum' in font.name else font.with_name('malgunbd.ttf')
        pdfmetrics.registerFont(TTFont('SpotKoreanBold', str(bold if bold.is_file() else font)))
    return 'SpotKorean'


def render_pdf(brief, request=None, discovery=None):
    """Embeds, manually linked videos and Instagram posts are deliberately absent."""
    request = request or {}; discovery = discovery or {}; font = _font()
    styles = {key: ParagraphStyle(key, fontName=font, fontSize=size, leading=leading,
              textColor=INK, spaceAfter=after, wordWrap='CJK', alignment=TA_LEFT)
              for key,size,leading,after in [('body',9,15,7),('small',7.5,12,5),
                  ('title',28,39,16),('heading',20,29,16),('sub',12,19,10)]}
    for key in ('title','heading','sub'):
        styles[key].keepWithNext = True
        styles[key].fontName = 'SpotKoreanBold'
    story=[]; sources={}
    def p(value,kind='body'):
        return Paragraph(escape(publication_text(value)).replace('\n','<br/>'),styles[kind])
    def add(value,kind='body'): story.append(p(value,kind))
    def heading(value): story.extend([PageBreak(),p(value,'heading')])
    def concise(value,limit=240):
        text=' '.join(publication_text(value).split())
        return text if len(text)<=limit else text[:limit].rstrip()+'…'
    def note(title,text):
        box=Table([[p(title,'sub')],[p(text)]],colWidths=[WIDTH],hAlign='LEFT')
        box.setStyle(TableStyle([('BACKGROUND',(0,0),(-1,-1),PAPER),('LEFTPADDING',(0,0),(-1,-1),14),('RIGHTPADDING',(0,0),(-1,-1),14),('TOPPADDING',(0,0),(-1,0),12),('BOTTOMPADDING',(0,-1),(-1,-1),12)]))
        story.extend([box,Spacer(1,5*mm)])
    def reading_block(number,card,reading,label):
        block=[Spacer(1,5*mm),p(f'{number:02} / {label}','small'),p(reading['headline'],'sub')]
        for title,key in [('무엇을 했나','fact'),('우리 지역에서 참고할 점','meaning'),('검토할 아이디어','hint')]:
            if reading.get(key):block.extend([p(title,'small'),p(reading[key])])
        date=str(card.get('published_at') or next((s.get('published_at') for s in card.get('sources',[]) if s.get('published_at')),None) or '날짜 미제공')[:10]
        stage=' · '+reading['stage'] if reading.get('stage') else ''
        block.append(p(f"{date}{stage} · {refs(card)}",'small'))
        story.append(KeepTogether(block))
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
        return '출처 '+', '.join(linked) if linked else ''
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
    story.extend([Spacer(1,7*mm),p('01  지역을 읽는 핵심 요약','heading')]);note('AREA SUMMARY',area_summary(brief))
    quant=[c for c in brief.get('unique_local_signals',[]) if c.get('module')=='quant']
    highlights=[c for c in quant if c.get('title') in ('월별 일평균 유동인구','업소당 월평균 매출액','주거인구','직장인구','핸드폰 소매업 업소 수','세대수') and 'value' in c][:6]
    if highlights:
        cells=[]
        for c in highlights:
            value=c['value'];value=f'{value:,}' if isinstance(value,(int,float)) else str(value)
            cells.append([p(c.get('title'),'small'),p(value+str(c.get('unit','')),'sub'),p(f"{c.get('reference_period') or '기준월 미제공'} · {refs(c)}",'small')])
        rows=[cells[i:i+3]+['']*(3-len(cells[i:i+3])) for i in range(0,len(cells),3)]
        cards=Table(rows,colWidths=[WIDTH/3]*3,hAlign='LEFT');cards.setStyle(TableStyle([('VALIGN',(0,0),(-1,-1),'TOP'),('BACKGROUND',(0,0),(-1,-1),PAPER),('BOX',(0,0),(-1,-1),.3,colors.white),('INNERGRID',(0,0),(-1,-1),4,colors.white),('LEFTPADDING',(0,0),(-1,-1),12),('TOPPADDING',(0,0),(-1,-1),12),('BOTTOMPADDING',(0,0),(-1,-1),10)]));story.extend([Spacer(1,5*mm),cards])
    story.extend([Spacer(1,7*mm),p('REPORT GUIDE','sub')]);add('고객 구성과 활동 시간 / 지역 관측과 기획 인사이트 / 전국 행사 참고 / 원본 출처','small')
    heading('02  상권과 고객 구성')
    add('소상공인365가 제공한 관측 지표입니다. 유동·주거·직장인구와 매출의 조사 대상·기간을 구분해 읽습니다.','small')
    metrics=[c for c in quant if 'value' in c]
    if metrics:
        rows=[[p('관측 항목','small'),p('값','small'),p('기준·근거','small')]]
        for c in metrics:
            value=c['value'];value=f'{value:,}' if isinstance(value,(int,float)) else str(value)
            rows.append([p(c.get('title'),'small'),p(value+str(c.get('unit','')),'small'),p(f"{c.get('reference_period') or '기준월 미제공'} / {c.get('scope') or '집계 범위 미제공'}\n{refs(c)}",'small')])
        table(rows,[65*mm,35*mm,74*mm])
    labels={'male':'남성','female':'여성','under_10':'10세 미만','teens':'10대','20s':'20대','30s':'30대','40s':'40대','50s':'50대','60_plus':'60대 이상',
            'mon':'월','tue':'화','wed':'수','thu':'목','fri':'금','sat':'토','sun':'일'}
    for c in quant:
        shares=c.get('shares');
        if not isinstance(shares,dict): continue
        values=[]
        for key,item in shares.items():
            if key=='total': continue
            value=item.get('share_pct') if isinstance(item,dict) else None
            if isinstance(value,bool) or not isinstance(value,(int,float)) or not math.isfinite(value) or not 0<=value<=100: continue
            label=labels.get(key,key.replace('_','~')+'시' if key in ('05_09','09_12','12_14','14_18','18_23','23_05') else key)
            values.append((label,value))
        if values:
            refs(c); block=[Spacer(1,6*mm),p(c.get('title'),'sub'),p(f"{c.get('scope') or '집계 범위 미제공'} · {c.get('reference_period') or '기준월 미제공'} · {refs(c)}",'small')]
            # All panels use the same 0-100% scale, including zero-valued observations.
            height=len(values)*19+24;chart=Drawing(WIDTH,height);start=72;bar_width=WIDTH-start-55
            for tick in (0,25,50,75,100):
                x=start+bar_width*tick/100;chart.add(Line(x,18,x,height,strokeColor=colors.HexColor('#e2e5df'),strokeWidth=.4));chart.add(String(x,3,str(tick)+'%',fontName=font,fontSize=7,fillColor=INK,textAnchor='middle'))
            peak=max(v for _,v in values)
            for i,(label,value) in enumerate(values):
                y=height-(i+1)*19+3;chart.add(String(0,y,label,fontName=font,fontSize=8,fillColor=INK));chart.add(Rect(start,y-1,bar_width*value/100,8,strokeColor=None,fillColor=ACCENT if value==peak else colors.HexColor('#9bb2a4')));chart.add(String(start+bar_width+10,y,f'{value:g}%',fontName=font,fontSize=8,fillColor=INK))
            block.append(chart);story.append(KeepTogether(block))
    local=brief.get('local_changes',[])+[c for c in brief.get('unique_local_signals',[]) if c.get('module')=='local']
    main_local,extra_local=select_local(local)
    heading('03  지역 소식과 생활권 맥락')
    add('지역에서 보도된 소식을 짧게 모았습니다. 기사별 장소와 시점을 함께 살펴보세요.','small')
    direct_ids={id(c) for c in brief.get('local_changes',[])}
    for i,(c,reading) in enumerate(main_local,1):
        date=str(c.get('published_at') or next((s.get('published_at') for s in c.get('sources',[]) if s.get('published_at')),'') or '')[:10]
        story.append(KeepTogether([Spacer(1,5*mm),p(f'{i:02}  '+reading['headline'],'sub'),
            p(reading['fact']),p(' · '.join(filter(None,[date,'지역 관련 보도' if id(c) in direct_ids else '주변 생활권 참고',refs(c)])),'small')]))
    if not main_local:add('이번 보고서는 상권 지표와 전국 체험 사례를 중심으로 구성했습니다.','body')
    cases=[c for c in brief.get('trend_patterns',[]) if c.get('type') in ('reference_case','audience_context')]
    main_trend=[];extra_trend=[]
    for c in cases:
        reading=trend_reading(c,brief)
        if reading:main_trend.append((c,reading))
        else:extra_trend.append(c)
    if main_trend:
        heading('04  전국 행사 참고와 홍보 연결점')
        add('상권 관측과 전국 사례를 함께 보며 검토할 기획 참고를 정리했습니다. 추가 행사 보도는 뒤의 참고 자료에서도 살펴볼 수 있습니다.','small')
    extra_trend.extend(c for c,_ in main_trend[3:])
    for i,(c,reading) in enumerate(main_trend[:3],1):
        reading_block(i,c,reading,c.get('event_name') or '전국 행사 참고')
    heading('05  기획에 활용할 연결점')
    note('WHY HERE, NOW?',brief.get('why_here_now'))
    for row in brief.get('research_implications',[]):
        if not row.get('observation'):continue
        add(row['title'],'sub');add(row['observation']);add(row['interpretation']+' '+row['question'])
        add(' / '.join(refs(card) for card in row.get('basis',[])),'small')
    from src.brief.planning_prompt import build_compact_clues
    clues=build_compact_clues(brief,request)
    add('인구·매출, 성별·연령, 요일·시간대는 별도 집계입니다. 행사 아이디어는 참고안입니다.','small')
    for field in clues['fields']:
        block=[Spacer(1,3*mm),p(f"{field['number']}. {field['label']}",'sub')]
        block.append(p(field['summary']) if field['summary'] else Spacer(1,6*mm))
        story.append(KeepTogether(block))
    story.extend([Spacer(1,6*mm),p('보고서 활용 범위','sub')])
    add('본문의 보도된 내용은 출처 자료의 요약이고, 참고할 이유와 매장 활용 힌트는 기획 제안입니다. 기사만으로 현재 방문객 증가나 특정 연령·성별의 선호·행사 성과를 판단하지 않습니다. 사업은 표시된 진행 단계로, 과거 보도는 표시된 날짜로 읽습니다.','small')
    add('매장 조사 반경과 주변 행정구역의 보도 범위는 다를 수 있습니다. 통계의 기준월·모집단은 표에 표시하며, 자료 생성일로 대체하지 않습니다. 뉴스 제공일과 원문 게시일이 다를 수 있으며, 제한된 검색 결과가 모든 사건을 포함하는 것은 아닙니다.','small')
    add('YouTube는 검색 정보와 출처를 수집하며 영상 본문을 분석하지 않습니다. 개인이 추가한 영상·Instagram 링크는 보고서의 근거에 포함하지 않습니다.','small')
    data_notes=[t.removeprefix('quant: ') for t in brief.get('needs_manual_check',[]) if t.startswith('quant: ') and not t.split(': ',1)[-1].replace('_','').isupper() and ('서로 다릅니다' in t or '제공되지' in t)]
    if data_notes:
        add('자료별 주의사항','sub')
        for text in dict.fromkeys(data_notes):add('- '+text,'small')
    extras=[('지역 참고 기사',c) for c in extra_local]+[('전국 행사 추가 자료',c) for c in extra_trend]
    if extras:
        heading('부록  추가 기사와 배경 자료')
        add('지역 보도의 추가 내용과 전국 행사의 참여 방식을 살펴볼 참고 자료입니다.','small')
        for label,c in extras:
            block=[Spacer(1,3*mm),p(label,'small'),p(c.get('title') or c.get('event_name') or '참고 기사','sub'),p(excerpt(c.get('evidence') or c.get('statement') or c.get('observation'))),p(refs(c),'small')]
            story.append(KeepTogether(block))
    heading('06  출처와 탐색 범위')
    add('본문 출처 번호와 대응하는 원본 링크입니다. 게시 시점·지역 범위·사업 단계를 원문에서 확인하세요.','small')
    if discovery.get('search_plan'):
        add('사용한 검색어','sub')
        for row in discovery['search_plan']:add(row['query'],'small');add(row['reason'],'small')
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
