# SPOT Decision Log

## 2026-10-03 — 홍보 기획 전 리서치로 범위 집중

- 사용자 결정: 출점 후보지 추천·발굴은 현재 SPoT 범위에서 제거한다.
- 매장명·주소 검색과 선택한 매장 위치 지도는 유지하되 지도 클릭으로 후보지를 생성하지 않는다.
- 리서치를 두 서비스로 나누지 않고 제품·매장 중심 홍보 근거 탐색 하나로 유지한다.
- 제품·서비스는 조사 대상, 목적은 선택적인 조사 질문으로 정의한다. 질문이 비면 기본 홍보 근거 탐색으로 접수한다.
- 제품 가치·고객 반응 자료·질문 기반 검색·Critic·브리프 연결은 후속 구현이다. [설계](PROMOTION_RESEARCH_DESIGN.md)에 현재 동작과 목표를 구분한다.
- 이 기록은 사용자의 직접 지시를 반영한 저장소 미러이며 Notion 동기화를 완료했다는 의미는 아니다.

## 2026-09-21

- SPOT is a Research Agent, not a finished event-plan generator.
- Instagram is expansion scope, not an MVP dependency.
- GitHub starts from a new repository.

## 2026-09-22 — technical coaching

- Keep n8n lightweight.
- Use LangGraph for Agent state, routing, Critic, and re-search.
- Separate deterministic Critic checks from semantic LLM checks.
- The important differentiator is **regional specificity and differentiation**, not the number of APIs or agents.
- Current 4-week MVP scope is feasible.
- If Scout work finishes early, add depth to Scout specialization instead of adding unrelated features.

## 2026-09-22 — collaboration model

- Notion is the human-facing project hub and decision/document space.
- GitHub is the implementation workspace and AI-readable project knowledge base.
- Scout AI work happens against GitHub, not Notion MCP.
- Notion MCP is used by the Integrator to maintain shared project documents.
- Shared contract changes are proposed through GitHub Issues, reviewed by the Integrator, then synchronized to Notion and GitHub documentation.
