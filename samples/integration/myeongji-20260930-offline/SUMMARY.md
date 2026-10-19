# Scout 통합 실행 요약

- 실행 모드: offline
- Graph 종료까지 도달: True
- 공통 계약 검증 통과: True
- Graph의 Critic / Research Brief는 Mock입니다.
- 별도 Critic 기준표 검사는 품질 승인이나 사실 검증을 대신하지 않습니다.

| 모듈 | 상태 | 인사이트 | 출처 |
|---|---|---:|---:|
| quant | failed | 0 | 0 |
| local | partial | 2 | 4 |
| trend | success | 10 | 18 |

## quant

Quant Scout 실행에 실패했습니다.


errors:
- {"code": "MISSING_KAKAO_REST_API_KEY", "message": "환경변수 KAKAO_REST_API_KEY가 없습니다."}

## local

부산광역시 강서구 에코델타시티·명지 생활권에서 2026-04-03~2026-09-30 조회기간 내 최근 변화 2건을 확인했다: 광역교통계획의 강서선 트램 전환 승인(approved_plan), 청년·산단근로자 특화 공공임대주택 993호 선정(selected_future_project).

- 2026년 6월 24일 보도는 에코델타시티 광역교통개선대책 변경안이 최종 승인됐고, 기존 BRT 대신 연장 6.6km 강서선 트램을 반영했다고 전했다.
- 2026년 상반기 특화주택 공모에 에코델타시티 15BL 사업이 선정됐다. 청년·산단근로자용 200호를 포함해 총 993호와 육아친화시설을 공급하며 2029년 준공을 목표로 한다.

warnings:
- 트램은 변경계획 승인 단계이며 개통된 시설이 아니다.
- 특화주택은 공모 선정 단계이며 현재 입주가 완료됐다는 의미가 아니다.
- WEEK1_AREA_SCOPE: 근거는 개별 점포 반경이 아니라 에코델타시티·명지 생활권 단위다.
- INSUFFICIENT_RECENT_EVIDENCE: 조회기간 내 변화가 2건으로 최소 기준 3건보다 적다.

## trend

검증된 체험형 마케팅 사례 10건에서 미션 기반 참여 동선 (7건), 직접 제품·기능 체험 (6건), 세계관·테마 공간 탐색 (6건) 패턴이 반복적으로 확인되었습니다.

- Mystery at the Grooms'
- Youth Adventure 2026
- Galaxy Z Flip8·Fold8 체험공간
- MY LIFE WITH ROBLOX 2026
- 신일 바람 정거장
- Supersonic Travel Lounge
- Push As You Are - Oakley Meta Pop-up
- TFT Wild Fanfest
- 2026 Mexico K-Expo AI Experience
- Light Up Your SEOUL - 서울의 밤, 반짝임을 켜다

warnings:
- CURATED_VERIFIED_CASE_POOL_USED
- NO_LIVE_API_CALL
- REQUEST_RELEVANCE_FILTER_NOT_IMPLEMENTED
