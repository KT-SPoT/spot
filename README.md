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

## Security

실제 API Key, n8n credential, token, password는 저장소에 커밋하지 않습니다.
