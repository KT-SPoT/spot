# 근거 기반 Research Brief v0.1 구현

기존 Graph의 빈 Mock Brief를 Scout 결과를 읽는 근거 요약 초안으로 교체했다.
Scout 구현, 공통 입력·출력 필드, Critic과 재탐색 라우팅은 변경하지 않았다.
LLM 또는 추가 API 호출 없이 결정적으로 생성한다.

## 출력과 해석

기존 Brief 최상위 필드를 유지한다: schema_version, request_id, status, overview,
local_changes, unique_local_signals, trend_patterns, why_here_now,
research_implications, needs_manual_check, source_count.

- `manual_review`: 출처 연결 근거를 요약한 검토 전 초안. 품질 승인이 아니다.
- `failed`: 사용할 출처 연결 근거가 없어 재수집 또는 보완이 필요하다.
- 수치 카드에는 값·단위·자료 기준 시점·지역 범위·출처를 함께 보존한다.
- `unique_local_signals`는 정량·인구 근거를 담는 기존 필드다. 해당 수치만으로 다른 상권 대비
  차별성이 입증됐다는 뜻은 아니다. 차별성과 why here / why now는 검토 항목으로 남긴다.
- 지역 변화는 발표일과 사업 단계(계획 승인, 사업 선정 등)를 유지한다.
- 트렌드는 실제 연결된 고유 사례 수를 표시한다. 패턴 간 사례 중복은 합산하지 않는다.
- `source_count`는 브리프 카드에서 실제 인용한 고유 URL 수다. Scout의 전체 출처 수와 다를 수 있다.
- 실패·Mock·계약 오류 결과, 출처 연결이 불완전한 Local 주장·Trend 패턴은 요약에서 제외한다.
- 예산, 인력, 행사 운영 계획, 매출 예측, 고객 타깃 확정은 생성하지 않는다.

Critic은 아직 Mock이다. 별도 규칙 preview의 finding과 의미 검토 항목을 브리프에 반영하지만,
규칙 검사나 Mock Critic 상태를 품질 최종 승인으로 사용하지 않는다.

## Graph 실행

기존 `src.integration_smoke` 명령을 그대로 사용할 수 있다. 추가로 아래 파일을 저장한다.

- `research_brief.json`: 근거 카드가 있는 Brief
- `RESEARCH_BRIEF.md`: 사람이 읽을 보고서

offline 실행은 세 Scout의 외부 호출을 막으며 근거 부족을 표시한다. 실제 수집은 `--mode live`를 사용한다.
전부 Mock 또는 실패라면 Brief의 status는 failed다. 기존 CLI 종료 코드는 Graph와 계약
검증 성공 여부이므로 Brief와 모듈 상태를 함께 확인한다.

## 저장된 결과로만 브리프 생성

API 재호출 없이 실행할 수 있다.

```bash
python -m src.brief path/to/research_bundle.json --output path/to/brief
```

성비·연령대·정확한 자료 기준 시점은 현재 Quant의 평탄화된 출력에 없다.
같은 조회에서 보존한 소상공인365 provider archive가 있으면 선택적으로 연결한다.
이 파일은 Scout 공통 계약에 추가하는 필드가 아닌 로컬 보조 입력이다.

```bash
python -m src.brief path/to/research_bundle.json --quant-evidence path/to/provider_evidence.json --output path/to/brief
```

archive는 collector의 반환 구조(analysis, analy_date, reports)를 사용한다. 좌표·반경·업종·
분석 생성일 및 핵심 지표 값이 Scout 결과와 다르면 생성하지 않는다. 기존 Scout의 순수
HTML 파서를 재사용하며, raw HTML은 브리프에 포함하지 않는다.

보조 입력 없이 Graph를 실행하면 날짜와 성비는 ‘확인 필요’로 표시한다. 조회일을 자료
기준 시점으로 대체하거나 ‘주요 성별’ 문구로 비율을 추정하지 않는다.

출력 상태가 failed이면 독립 CLI는 종료 코드 1, 검토 가능한 초안이면 0을 반환한다.
Windows 콘솔에서는 Python UTF-8 모드를 사용한다. WSL 검증 환경은 Ubuntu 24.04 /
Python 3.12.3이며 테스트 의존성은 constraints-test.txt를 사용한다.

## 검증

```bash
python -m unittest discover -s tests -v
```

합성 데이터로 실패·Mock 배제, 출처 교차 참조, 날짜 미확보, 0과 bool 구분,
중복 사례·URL, 입력 불변성, 원문 보조자료 불일치, 성비 모집단 구분, CLI 내보내기를 검사한다.
키 없는 offline Graph와 저장된 실제 조회 결과를 사용한 별도 브리프 생성도 확인한다.

## 남은 작업

- Graph에서 Quant 원문 보조자료를 안전하게 보존·전달하는 방식 합의
- 실제 Critic과 의미 검토, 재탐색 정책
- 원문 지표의 집계 방법, 시점·범위 및 캠페인 관련성 확인
- 요청 항목 선택과 요약 형식 사용자 설정

API 키와 인증 URL을 Git에 넣지 않는다. 원문 archive와 실제 실행 산출물은 저장 전에
인증정보를 제거하고 로컬 보존한다.
