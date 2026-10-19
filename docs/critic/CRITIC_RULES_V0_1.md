# Critic 규칙 기준표와 검증 샘플 — draft-0.1

2026-10-01 업데이트: 이 preview 엔진의 기준은 유지하고, 별도 실제
Critic wrapper와 graph 라우팅을 연결했습니다. 현재 실행 정책은
[CRITIC_RETRY.md](../CRITIC_RETRY.md)를 따릅니다. 아래는 preview 작성 당시의 범위 기록입니다.

작성·검증일: 2026-09-30 / 담당: 김민석 / 브랜치: `feat/critic`

## 목적과 적용 범위

Scout 구현을 기다리는 동안 인수 기준을 재현 가능한 테스트로 준비한다. `src/critic/rules.py`는 ResearchBundle을 읽는 독립 preview 평가기다. 현재 graph의 Mock Critic, Brief, retry routing에는 연결하지 않는다. 공통 ScoutResult / CriticResult 필드나 상태를 변경하지 않는다.

이 초안은 날짜·출처 참조·중복 등 기계적 점검을 다룬다. URL 접근·원문 진위·지역 구체성·차별성·캠페인 관련성을 승인하지 않는다. `quality_status`는 항상 `manual_review`다. 보고서의 `rule_status`는 공통 CriticResult의 `status`와 별개다.

## 판정과 우선순위

| preview 판정 | 의미 | 다음 행동 |
| --- | --- | --- |
| needs_fix | 계약/ID 오류, 끊어진 참조, 잘못된 날짜·미래 게시일, 사례 수 모순 | 해당 필드·모듈을 수정하고 재검사 |
| manual_review | 미확보 메타데이터, 오래된 자료, partial/failed, mock, 경고, 의미 검토 필요 | 원인과 보완 가능성 확인; 자동 재시도 금지 |
| pass | 이 초안의 기계적 점검에서 수정·수동 확인 사유 미발견 | 품질 최종 승인 아님. 남은 의미·사실 검토 수행 |

혼합된 사유의 우선순위는 needs_fix > manual_review > pass다. 합성 데이터 표시는 정보 항목이며 실제 조사 근거로 취급하지 않는다. CLI 종료 코드 0은 preview 실행/형식 점검 성공일 뿐, manual_review 결과도 포함한다.

## 기준표

| ID | 확인 대상 | 수정 필요 | 수동 확인 및 한계 |
| --- | --- | --- | --- |
| R00 | bundle 구조·버전·요청 ID·조회 기간 | 구조/ID 불일치, 잘못된 기준일·기간 | 입력을 자동 보정하지 않음 |
| R01 | Scout 공통 envelope·module_status | 기존 validator 오류, Merge 상태 불일치 | 기존 공통 계약 그대로 사용 |
| R02 | Scout 상태·mock·오류·경고 | 공통 상태값 오류는 R01 | partial/failed, mock, 오류, 실행 경고. 전체 중단이나 retry를 결정하지 않음 |
| R03 | insights·sources 존재 및 개수 | 빈 출처를 참조하면 R04 | 빈 근거는 보완 사유 확인. 개수는 진단값; Scout별 최소 수 미확정 |
| R04 | 출처 ID·이름·종류·URL·수집일·주장별 참조 | 출처 ID 충돌, 잘못된 URL/수집일, 존재하지 않는 source_ids | null/미확보는 계약 위반으로 단정하지 않음. Quant metric_refs 연결은 별도 설계 |
| R05 | Local/Trend 출처 게시일·최근 인용 자료 | 잘못된 게시일, 기준일 이후 게시일 | 미확보/기간 밖 날짜, 최근 인용 근거 없음. Quant API 게시일 null에 이 규칙을 적용하지 않음 |
| R06 | 동일 URL·명시된 event_key | 동일 event_key 중복 | 같은 URL은 독립 근거로 부풀리지 않음. event_key 없는 사건의 의미 중복은 검토 미완료 |
| R07 | Local 변화 단계·지역 태그 | 문장 의미는 자동 판정하지 않음 | change_state/지역 태그 미확보. 태그 존재만으로 운영 상태·지역 특수성을 승인하지 않음 |
| R08 | Trend 패턴 출처·사례 참조·횟수 | count 형식/고유 사례 수 모순, 끊어진 사례·출처 참조 | 1개 사례는 반복 패턴 아님. case 목록이 없으면 source 수로 case 수를 추정하지 않음 |

## 날짜 및 추적 정책

- reference_date는 YYYY-MM-DD, lookback_days는 0 이상 정수로 읽는다. bool/문자열 숫자·음수는 보정하지 않는다. 이는 preview 입력 정책이며 Scout 내부의 기본값 처리를 바꾸지 않는다.
- 기간 양 끝 포함: [reference_date - lookback_days, reference_date]. 0일은 기준일 당일만 의미한다.
- 게시일은 날짜 또는 timezone을 포함한 ISO datetime을 받는다. datetime은 KST 날짜로 변환한다.
- 수집일은 timezone을 포함한 datetime이다. 수집일이 분석 기준일 이후인 것만으로 미래 근거로 단정하지 않는다. 실제 수집 여부·시간의 진위는 원문/provenance 검토 대상이며 이 도구는 현재 시각과 비교하지 않는다.
- Local/Trend 최신성은 실제 source_ids/example_source_ids로 인용된 출처에만 집계한다. 인용하지 않은 최근 자료를 추가해 오래된 주장을 통과시키지 않는다.
- Quant API의 published_at/source_url null 및 metric_refs만 있는 형태는 기존 Notion 예시에서 허용된다. 게시일 null로 실패시키지 않으며, 주장별 추적 미확보는 수동 확인으로 기록한다.
- 실제 Local/Trend의 source_id·event_key·case_id 등을 있으면 사용한다. 새 필수 필드를 공통 계약에 추가하지 않는다.
- 모든 Scout 경고는 정보성 합성 표식을 제외하고 수동 확인 사유로 보존한다. 고정 사례·관련성 미구현 등의 경고가 있는 결과를 자동 승인하지 않는다.

## 기존 기준과 팀 합의 항목

기존 Notion '07. 테스트·성공 기준 & 결정 로그' 초안의 핵심 인사이트 출처 존재, 최근 지역 변화 1개 이상, 지역 구체 신호 2개 이상, 유사 상권 차이 1개 이상은 유지한다. 지역 구체 신호·차이의 의미 판단을 태그 개수로 대신하지 않는다.

1주차 제출 목표(Local 3건, Trend 5건)는 제출 목표이며, 본 preview의 최종 품질 pass 수치가 아니다. Scout별 최소 근거 수, source 신뢰도, Quant metrics 추적, 비교 데이터 표현, retry 대상/횟수/수동 전환은 실제 샘플과 함께 팀 합의가 필요하다.

## 검증 샘플

모든 값은 합성이며 실제 지역 사실·API 측정값이 아니다. `example.invalid` URL은 의도적으로 접근하지 않는다.

- 단일 실행 입력: `samples/critic/research_bundle.synthetic.json`
- 27개 독립 시나리오 및 예상 판정: `samples/critic/rule_cases.synthetic.json`
- 예상 판정은 상태뿐 아니라 핵심 finding code를 함께 검사한다.
- C17은 '예정' 태그와 운영 단정 문장이 충돌해도 규칙만으로 의미 검증이 되지 않는 한계를 명시적으로 테스트한다.

| 사례 | 내용 | 예상 rule_status |
| --- | --- | --- |
| C01 | 기계적 조건 충족. 의미·사실 검증은 보류 | pass |
| C02 | partial 결과를 전체 실패로 단정하지 않음 | manual_review |
| C03 | Quant 실패, 다른 결과 보존 | manual_review |
| C04 | success로 표시된 mock도 실제 근거로 승인하지 않음 | manual_review |
| C05 | Scout request_id 불일치 | needs_fix |
| C06 | Scout 필수 필드 누락 | needs_fix |
| C07 | 모듈 자체 누락 | needs_fix |
| C08 | insight가 있는데 sources 비어 있음 | needs_fix |
| C09 | 게시일 null: 최신성 확인 불가 | manual_review |
| C10 | 기준일 이후 출처 | needs_fix |
| C11 | 조회 기간 밖의 배경 자료 | manual_review |
| C12 | 잘못된 게시일 | needs_fix |
| C13 | 존재하지 않는 source_id 참조 | needs_fix |
| C14 | 출처 ID 충돌 | needs_fix |
| C15 | 다른 ID로 같은 URL을 중복 등록 | manual_review |
| C16 | 동일 사건을 다른 insight_id로 중복 계산 | needs_fix |
| C17 | 예정 단계 태그가 있어도 문장의 실제 운영 단정은 의미 검토 대상 | pass |
| C18 | 변화 단계 미확보 | manual_review |
| C19 | 패턴 횟수 부풀림 | needs_fix |
| C20 | 패턴에 존재하지 않는 사례 연결 | needs_fix |
| C21 | 한 사례를 반복 패턴이라고 표현 | manual_review |
| C22 | Quant API의 URL·게시일 미확보와 metric_refs만 있는 경우 | manual_review |
| C23 | collected_at은 기준일 이후의 실제 수집 시각도 허용 | pass |
| C24 | UTC 날짜를 KST로 바꾸면 기준일 이후 | needs_fix |
| C25 | Merge module_status 불일치 | needs_fix |
| C26 | 실행 경고는 원인 확인 대상으로 보존 | manual_review |
| C27 | 패턴 사례 목록이 없으면 출처 수로 사례 수를 추정하지 않음 | manual_review |

## 실행 및 검증 결과

검증 환경: Python 3.12.14 / Linux / 기존 constraints-test.txt 의존성 환경. 외부 API·LLM 호출 및 API 키 사용 없음.

```bash
python -m unittest discover -s tests -v
python -m src.critic.rules samples/critic/research_bundle.synthetic.json
```

- 전체 unittest 26개 통과: 새 Critic 테스트 15개 + 기존 계약·graph 테스트 11개.
- 합성 시나리오 27/27 예상 결과 일치: 규칙 pass 3, manual_review 11, needs_fix 13.
- 모든 시나리오 quality_status = manual_review; 실제 품질 최종 승인 0건.
- 추가 검증: 입력 비변경, 기간 경계/0일, timezone, 미처리 malformed 입력, 인용되지 않은 최근 자료, 모듈 간 잘못된 출처 연결, 사례 중복, CLI 종료 코드, 결정성.
- CLI: needs_fix=1, 그 외=0, 파일/JSON 읽기 오류=2. rule_status와 quality_status를 반드시 별도로 확인한다.
- 이번 테스트에는 최신 Local PR/Trend 원문 사실 검증 및 실제 Scout 통합은 포함되지 않는다.

## 다음 작업

1. 최신 Local PR 회귀 검증 및 Trend PR 출처/테스트 보완 검토.
2. Quant 실제 결과 확보 후 metric_refs 추적 방법과 모듈별 최소 기준 합의.
3. 합성 샘플에서 만든 규칙을 실제 ResearchBundle에 preview 적용하고 오탐/미탐 조정.
4. bundle와 Critic 결과를 읽는 Research Brief 입력 구조 구현.
5. 실제 CriticResult 변환과 graph 연결, retry 상한 및 중단 정책은 별도 단계에서 구현.
