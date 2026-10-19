
from __future__ import annotations
import json, re, sys
from html import unescape
from html.parser import HTMLParser
from pathlib import Path
from typing import Any

class TextParser(HTMLParser):
    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.parts=[]
    def handle_data(self,data):
        self.parts.append(data)

def text(s:str)->str:
    p=TextParser(); p.feed(s)
    return re.sub(r"\s+"," ",unescape("".join(p.parts))).strip()

def num(s:str):
    s=s.replace(",","").replace("%","").strip()
    if not s or s in {"-","null","None"}: return None
    try: v=float(s)
    except ValueError: return None
    return int(v) if v.is_integer() else v

class TableParser(HTMLParser):
    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.rows=[]; self.row=None; self.cell=None; self.parts=[]
    def finish_cell(self):
        if self.cell is not None and self.row is not None:
            self.cell["text"]=re.sub(r"\s+"," ","".join(self.parts)).strip()
            self.row.append(self.cell)
        self.cell=None; self.parts=[]
    def handle_starttag(self,tag,attrs):
        tag=tag.lower()
        if tag=="tr":
            if self.row:
                self.finish_cell(); self.rows.append(self.row)
            self.row=[]
        elif tag in {"th","td"} and self.row is not None:
            self.finish_cell()
            self.cell={"tag":tag,"attrs":dict(attrs),"text":""}
    def handle_endtag(self,tag):
        tag=tag.lower()
        if tag in {"th","td"}: self.finish_cell()
        elif tag=="tr":
            self.finish_cell()
            if self.row: self.rows.append(self.row)
            self.row=None
    def handle_data(self,data):
        if self.cell is not None: self.parts.append(data)

def table_after(html:str, marker:str)->str:
    pos=html.find(marker)
    if pos<0: raise ValueError(f"표 제목을 찾지 못했습니다: {marker}")
    m=re.search(r"<table\b[^>]*>.*?</table>",html[pos:],re.I|re.S)
    if not m: raise ValueError(f"표를 찾지 못했습니다: {marker}")
    return m.group(0)

def rows_after(html:str, marker:str):
    p=TableParser(); p.feed(table_after(html,marker)); p.finish_cell()
    if p.row: p.rows.append(p.row)
    return [[c["text"] for c in r] for r in p.rows]

def simple_series(html,marker,value_key):
    rs=rows_after(html,marker)
    periods=rs[1]
    regions={}
    for r in rs[2:]:
        if len(r)!=len(periods)+1: continue
        vals=[num(x) for x in r[1:]]
        regions[r[0]]={value_key:vals,"latest_value":vals[-1] if vals else None}
    return {"periods":periods,"regions":regions}

def apartment_building_units(html):
    rs=rows_after(html,"아파트 동/호 수 추이")
    periods=rs[0][1:]
    regions={}
    for r in rs[2:]:
        vals=[num(x) for x in r[1:]]
        if len(vals)!=len(periods)*2: continue
        by={}
        for i,p in enumerate(periods):
            by[p]={"buildings":vals[i*2],"units":vals[i*2+1]}
        regions[r[0]]={"by_period":by,"latest":by[periods[-1]] if periods else {}}
    return {"periods":periods,"regions":regions}

def distribution(html,marker):
    rs=rows_after(html,marker)
    cats=rs[0][1:]
    regions={}
    for r in rs[1:]:
        vals=[num(x) for x in r[1:]]
        if len(vals)!=len(cats): continue
        d=dict(zip(cats,vals))
        regions[r[0]]={"values":d,"total":sum(v for v in vals if isinstance(v,(int,float)))}
    return {"categories":cats,"regions":regions}

def facilities(html):
    rs=rows_after(html,"<dt>주요시설 현황</dt>")
    cats=rs[1]
    regions={}
    for r in rs[2:]:
        vals=[num(x) for x in r[1:]]
        if len(vals)==len(cats): regions[r[0]]=dict(zip(cats,vals))
    return {"categories":cats,"regions":regions}

def schools(html):
    rs=rows_after(html,"학교시설 (학교수/학생수)")
    cats=rs[0][2:]
    regions={}; current=None
    for r in rs[1:]:
        if len(r)>=2 and r[1]=="학교수":
            current=r[0]
            regions[current]={"school_count":dict(zip(cats,[num(x) for x in r[2:]]))}
        elif current and r and r[0]=="학생수":
            regions[current]["student_count"]=dict(zip(cats,[num(x) for x in r[1:]]))
    return {"categories":cats,"regions":regions}

def subway_usage(html):
    rs=rows_after(html,"<dt>지하철 이용 현황</dt>")
    periods=rs[1]
    stations=[]; message=None
    for r in rs[2:]:
        if len(r)==1:
            if "지하철" in r[0]: message=r[0]
        elif len(r)>=2:
            stations.append({
                "line":r[0],"station":r[1],
                "daily_average_boarding_alighting":dict(zip(periods,[num(x) for x in r[2:]]))
            })
    return {"available":bool(stations),"periods":periods,"stations":stations,"message":message}

def transport(html):
    rs=rows_after(html,"<dt>교통시설 현황 (시군구 기준)</dt>")
    cats=rs[0][1:]
    regions={}
    for r in rs[1:]:
        regions[r[0]]=dict(zip(cats,[num(x) for x in r[1:]]))
    return {"categories":cats,"regions":regions}

def analysis_texts(html):
    blocks=re.findall(
        r'<dl\b[^>]*class=["\'][^"\']*\banalyResult\b[^"\']*["\'][^>]*>(.*?)</dl>',
        html,re.I|re.S
    )
    return [text(b) for b in blocks if text(b)]

def selected(regions):
    for k,v in regions.items():
        if re.sub(r"\s+","",k)=="선택영역": return v
    return {}

def pct(cur,prev):
    if not isinstance(cur,(int,float)) or not isinstance(prev,(int,float)) or prev==0: return None
    return round((cur-prev)/prev*100,1)

def dominant(d):
    vals=[(k,v) for k,v in d.items() if isinstance(v,(int,float))]
    return max(vals,key=lambda x:x[1])[0] if vals else None

def parse_area_report(html_text:str)->dict[str,Any]:
    household=simple_series(html_text,"세대 수 추이","households")
    apt_count=simple_series(html_text,"공동주택 수 추이","housing_units")
    apt_bu=apartment_building_units(html_text)
    complex_size=distribution(html_text,"아파트 단지규모별 현황")
    area_dist=distribution(html_text,"아파트 면적별 현황")
    fac=facilities(html_text)
    sch=schools(html_text)
    subway=subway_usage(html_text)
    trans=transport(html_text)

    hs=selected(household["regions"]).get("households",[])
    aps=selected(apt_count["regions"]).get("housing_units",[])
    abu=selected(apt_bu["regions"]).get("latest",{})
    cs=selected(complex_size["regions"]).get("values",{})
    ad=selected(area_dist["regions"]).get("values",{})
    fs=selected(fac["regions"])
    ss=selected(sch["regions"])
    ts=selected(trans["regions"])

    school_total=sum(v for v in ss.get("school_count",{}).values() if isinstance(v,(int,float)))
    student_total=sum(v for v in ss.get("student_count",{}).values() if isinstance(v,(int,float)))

    warnings=[]
    if not subway["available"] and not subway["message"]:
        warnings.append({"code":"subway_usage_missing","message":"지하철 이용 현황 데이터와 안내 문구가 모두 없습니다."})

    return {
        "schema_version":"sbiz365.area.v0.1",
        "source":{"report":"sang_gwon6.sg","note":"HTML tables and analysis-result text normalized without executing JavaScript"},
        "household_trend":household,
        "apartment_status":{
            "housing_unit_trend":apt_count,
            "apartment_building_unit_trend":apt_bu,
            "complex_size_distribution":complex_size,
            "area_distribution":area_dist,
        },
        "nearby_facilities":{"major_facilities":fac,"school_facilities":sch},
        "transport":{"subway_usage":subway,"facility_counts":trans},
        "reported_analysis":{"texts":analysis_texts(html_text)},
        "derived_selected_area":{
            "latest_household_period":household["periods"][-1] if household["periods"] else None,
            "latest_households":hs[-1] if hs else None,
            "households_year_ago":hs[-3] if len(hs)>=3 else None,
            "households_year_over_year_change_percent":pct(hs[-1],hs[-3]) if len(hs)>=3 else None,
            "latest_apartment_period":apt_count["periods"][-1] if apt_count["periods"] else None,
            "latest_multi_family_housing_units":aps[-1] if aps else None,
            "multi_family_housing_units_year_ago":aps[-2] if len(aps)>=2 else None,
            "multi_family_housing_units_year_over_year_change_percent":pct(aps[-1],aps[-2]) if len(aps)>=2 else None,
            "latest_apartment_buildings":abu.get("buildings"),
            "latest_apartment_units":abu.get("units"),
            "dominant_apartment_complex_size":dominant(cs),
            "dominant_apartment_area_band":dominant(ad),
            "dominant_facility_type":dominant(fs),
            "school_count_total":school_total,
            "student_count_total":student_total,
            "subway_station_count":ts.get("지하철역"),
            "bus_stop_count":ts.get("버스정류장"),
            "subway_usage_available":subway["available"],
        },
        "warnings":warnings,
    }

def main():
    if len(sys.argv) not in (2,3):
        print("사용법: python quant_area.py <sang_gwon6.raw.html> [output.json]",file=sys.stderr)
        return 1
    ip=Path(sys.argv[1])
    op=Path(sys.argv[2]) if len(sys.argv)==3 else ip.with_suffix(".normalized.json")
    result=parse_area_report(ip.read_text(encoding="utf-8",errors="replace"))
    op.parent.mkdir(parents=True,exist_ok=True)
    op.write_text(json.dumps(result,ensure_ascii=False,indent=2),encoding="utf-8")
    d=result["derived_selected_area"]
    print("지역현황 파싱 성공")
    print(f"최신 세대수: {d['latest_households']}세대")
    print(f"세대수 전년동기대비: {d['households_year_over_year_change_percent']}%")
    print(f"최신 공동주택 수: {d['latest_multi_family_housing_units']}호")
    print(f"아파트 동/호 수: {d['latest_apartment_buildings']}동 / {d['latest_apartment_units']}호")
    print(f"주요 시설 유형: {d['dominant_facility_type']}")
    print(f"학교/학생 수: {d['school_count_total']}개 / {d['student_count_total']}명")
    print(f"지하철역/버스정류장: {d['subway_station_count']}개 / {d['bus_stop_count']}개")
    print(f"지하철 이용 데이터 존재: {d['subway_usage_available']}")
    if result["warnings"]:
        print("\n경고:")
        for w in result["warnings"]: print(f"- {w['code']}: {w['message']}")
    print(f"\n저장 위치: {op}")
    return 0

if __name__=="__main__":
    raise SystemExit(main())
