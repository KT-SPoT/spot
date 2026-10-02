# SPOT

지역 맥락 탐색형 AI Research Agent.

SPOT은 KT Plaza 홍보기획 전 단계에서 상권·지역 변화·트렌드를 조사하고, 근거가 충분한지 Critic으로 검증한 뒤 Research Brief를 만드는 프로젝트입니다.

## Architecture

HTTP API와 n8n 가져오기 파일: [연결 안내](docs/N8N_API_SETUP.md).

```text
n8n Main Entry
  -> LangGraph
      -> Quant Scout / Local Scout (parallel)
      -> internal context summary
      -> Trend Scout (context-aware discovery)
      -> Critic
          -> retry selected Scout(s) when needed
          -> Research Brief
  -> n8n Response
```

- **n8n**: 외부 요청 수신, 입력 검증, LangGraph API 호출, 결과 반환
- **LangGraph**: Scout 실행, 상태 관리, Critic 판단, 재탐색 루프, Brief 생성
- **Scout modules**: 각 담당자가 공통 JSON 계약에 맞춰 독립 구현

## Collaboration model

- **GitHub**: 구현, AI coding 작업, Issue, branch, PR의 중심
- **Notion**: 프로젝트 정의, 공통 결정, 로드맵, 공용 문서
- **Notion MCP**: Integrator/팀장이 공통 문서를 관리
- Scout 담당 AI는 Notion MCP 없이도 `AGENTS.md`와 `docs/api-contract.md`를 기준으로 작업 가능

AI coding agent를 사용할 때는 먼저 [AGENTS.md](AGENTS.md)를 읽게 합니다.

## Team ownership

- Quant Scout: 유승우 — `feat/quant`
- Local Scout: 김태훈 — `feat/local`
- Trend Scout: 김건희 — `feat/trend`
- Integrator / Critic / Research Brief: 김민석 — `feat/critic`

## Shared contract

- Input: `SpotRequest v0.1`
- Output: `ScoutResult v0.1`
- Merge: `ResearchBundle v0.1`
- Critic: `CriticResult v0.1`
- Final: `ResearchBrief v0.1`

Implementation contract: [docs/api-contract.md](docs/api-contract.md)

## 로컬 mock smoke test

Scout를 Mock으로 대체한 smoke test는 외부 API를 호출하지 않고 다음 통합 경로를 검증합니다.

```text
SpotRequest
  -> Quant / Local placeholders (parallel)
  -> internal context summary -> Trend placeholder
  -> Merge
  -> Rule Critic
  -> Research Brief (Mock 근거는 제외하며 근거 부족을 표시)
```

저장소 루트에서 가상환경을 만들고 의존성을 설치한 뒤 테스트를 실행합니다.

```bash
python -m venv .venv
source .venv/bin/activate
python -m pip install -r requirements.txt -c constraints-test.txt
python -m unittest discover -s tests -v
```

Windows PowerShell에서는 `.venv\Scripts\Activate.ps1`로 가상환경을 활성화합니다.
현재 mock 흐름에는 API Key나 별도 환경변수가 필요하지 않습니다.

검증 환경은 Python 3.12.14 / Linux입니다. `constraints-test.txt`로 테스트 의존성 버전을 맞춥니다.
테스트는 Scout 호출을 mock으로 대체하므로 실제 Scout 개발 후에도 외부 API 없이 실행됩니다.
실제 Scout 샘플은 별도 계약 검사 도구로 확인하세요.

```bash
python -m src.validation path/to/scout_result.json --module quant --request-id spot-example-001
```

검사 범위·실패 정책·PR 인수 체크리스트: [통합 준비 가이드](docs/INTEGRATION_READINESS.md).

## Critic 기준 초안 및 합성 검증

Scout 인수용 독립 규칙 preview를 실행할 수 있습니다. [기준표와 검증 결과](docs/critic/CRITIC_RULES_V0_1.md)를 먼저 읽으세요.
`rule_status` 통과는 품질 최종 승인이 아니며, `quality_status`는 의미 검토 전까지 `manual_review`입니다.
현재 graph는 실제 규칙 Critic과 제한된 일시 오류 재조사를 사용합니다.
[현재 정책](docs/CRITIC_RETRY.md). 의미·사실 검토는 수동으로 남습니다.
선택적 [의미 Critic shadow 평가](docs/SEMANTIC_CRITIC.md)를 연결했습니다. 기본 꺼짐이며,
설정된 모델의 판정을 기록해 사람이 대조합니다. Brief 자동 변경·품질 승인·추가 재검색은 없습니다.

```bash
python -m src.critic.rules samples/critic/research_bundle.synthetic.json
python -m unittest discover -s tests -v
```

`samples/critic/rule_cases.synthetic.json`에는 실제 근거와 구분된 합성 시나리오 27개가 있습니다.

## Scout 통합 실행

Local은 요청 지역의 네이버 뉴스, Trend는 제품·인접 카테고리 관련 뉴스와 유튜브 메타데이터를 실행 시 조회합니다.
고정 사례는 사용하지 않으며 검색 결과는 원문·영상 확인 전까지 `partial` 후보자료입니다.
Local은 [원문 대조·문맥 분류](docs/LOCAL_SOURCE_VERIFICATION.md)를 수행하며 직접 변화·주변 행정구역 맥락·배경을 구분해 브리프에 인용합니다. 날짜·지역 연결의 불확실성은 표시하고 원문 근거가 없는 자료는 보류합니다. 원문 대조는 실제 사건 발생이나 점포 반경 검증을 뜻하지 않습니다.
키 설정·조회 범위·실패 정책: [실제 검색 가이드](docs/LIVE_SCOUT_RESEARCH.md).
현재 통합 입력은 조사 중심점이 미확정인 지역명이며, 반경 분석 결과로 사용하지 않습니다.

```bash
python -m src.integration_smoke samples/input/myeongji_international.provisional.json --mode offline --output samples/integration/myeongji-20260930-offline
```

offline은 외부 호출을 막고 세 Scout의 자료 미확보 경로를 실행합니다.
전체 JSON, 계약 검사, Critic 기준표 preview, 사람이 읽는 `SUMMARY.md`를 저장합니다.
Graph의 Critic은 규칙을 검사하며 Brief는 근거 요약 초안입니다. 명령 성공은 리서치 품질 승인을 뜻하지 않습니다.
live 실행 준비와 이번 결과: [Scout 통합 기록](docs/SCOUT_INTEGRATION_2026-09-30.md).

## 근거 기반 Research Brief

Graph는 Scout의 실제 근거를 요약하는 Research Brief 초안을 생성합니다.
Critic은 실제 규칙을 검사하며, 출처 원문의 의미·사실·지역 관련성은 추가 검토가 필요합니다.
저장된 결과로 API 재호출 없이 JSON과 Markdown 보고서를 만들 수도 있습니다.

```bash
python -m src.brief path/to/research_bundle.json --output path/to/brief
```

성비·연령대·자료 기준 시점을 위한 원문 보조자료 연결과 검증 방법:
[Research Brief 실행 가이드](docs/RESEARCH_BRIEF.md).

## Security

실제 API Key, n8n credential, token, password는 저장소에 커밋하지 않습니다.


## Project knowledge

- [Project definition](docs/PROJECT.md)
- [Architecture](docs/ARCHITECTURE.md)
- [API contract](docs/api-contract.md)
- [Current roadmap](docs/ROADMAP.md)
- [Decision log](docs/DECISIONS.md)
- Role guides: [Quant](docs/roles/QUANT.md) · [Local](docs/roles/LOCAL.md) · [Trend](docs/roles/TREND.md) · [Integrator](docs/roles/INTEGRATOR.md)
