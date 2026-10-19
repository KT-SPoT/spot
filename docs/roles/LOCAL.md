# Local Scout — 김태훈

## Mission
Find concrete evidence of **why this area is changing now**.

Focus areas:
- housing move-ins,
- schools,
- transport,
- public/commercial facilities,
- development plans,
- meaningful local events.

## Main branch
`feat/local`

## Main file
`src/scouts/local.py`

## Week 1 checklist
- [ ] choose one test area
- [ ] collect 3+ concrete recent local-change items
- [ ] preserve source URL and publication date
- [ ] distinguish generic area description from recent local change
- [ ] return a valid `ScoutResult v0.1`
- [ ] note successful and failed queries
- [ ] open a PR

## Current GitHub Issue
#2 — Local data PoC

## Quality bar
Avoid generic statements such as:
> New towns tend to have young families.

Prefer:
- named change,
- date,
- specific local evidence,
- why it matters,
- source.


## 2026-10-08: 지역 기본 맥락 조사
사용자 승인으로 Local은 뉴스 외에 매장 좌표 기반 Kakao 장소 검색과 공식 정부·지자체 시설 설명을 함께 수집한다. 카테고리/키워드별 가까운 장소를 최대 3개 보존하며 500m 이내와 요청 반경을 구분한다. 장소 검색 개수는 시설 전수나 지배적인 상권 유형, 직선거리는 실제 동선을 뜻하지 않는다. 공식 검색 결과는 원문 본문에서 시설명이 확인될 때만 채택하며 실패는 진단에 남긴다. 최근 변화 뉴스와 지역 배경을 분리한다.
