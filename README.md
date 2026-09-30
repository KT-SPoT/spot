# SPOT

지역 맥락 탐색형 AI Research Agent.

SPOT은 KT Plaza 홍보기획 전 단계에서 상권·지역 변화·트렌드를 조사하고, 근거가 충분한지 Critic으로 검증한 뒤 Research Brief를 만드는 프로젝트입니다.

## Architecture

```text
n8n Main Entry
  -> LangGraph
      -> Quant Scout
      -> Local Scout
      -> Trend Scout
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

Week 1 smoke test는 외부 API를 호출하지 않고 다음 통합 경로를 검증합니다.

```text
SpotRequest
  -> Quant / Local / Trend placeholders
  -> Merge
  -> Mock Critic
  -> Mock Research Brief
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

## Security

실제 API Key, n8n credential, token, password는 저장소에 커밋하지 않습니다.


## Project knowledge

- [Project definition](docs/PROJECT.md)
- [Architecture](docs/ARCHITECTURE.md)
- [API contract](docs/api-contract.md)
- [Current roadmap](docs/ROADMAP.md)
- [Decision log](docs/DECISIONS.md)
- Role guides: [Quant](docs/roles/QUANT.md) · [Local](docs/roles/LOCAL.md) · [Trend](docs/roles/TREND.md) · [Integrator](docs/roles/INTEGRATOR.md)
