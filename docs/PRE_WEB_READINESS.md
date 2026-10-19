# 웹 구현 전 통합 검증 — 2026-10-02

## 구현 상태

- Quant·Local 병렬 → 인구/지역 맥락 → 전국·다업종 Trend → 규칙 Critic →
  선택적 GPT 연구 Critic → Research Brief 흐름을 유지했다.
- GPT는 출처를 재인증하지 않고 지역·고객 연결, 응용 논리, 차별성, 과장 여부를 검토한다.
  출처 ID는 모델이 생성하지 않고 실제 Scout 레지스트리에서 연결한다.
- 호응 자료는 선택 사항이다. generic은 참고 사례 삭제가 아니라 응용 가설 구체화 의견이다.
  모델 실패도 확보한 조사 자료를 폐기하거나 새 Scout 호출을 만들지 않는다.
- 결과는 JSON과 Markdown에 함께 표시하고, 웹 중계 계약·오류 처리를
  [WEB_INTEGRATION.md](WEB_INTEGRATION.md)에 정리했다.

## 실제 검증과 합성 검사 구분

이전 실제 네이버·Quant·Local 자료를 재사용해 새 연구 Critic으로 GPT 요청을 2회 했다.
첫 검증에서 5개 모두 needs_context였다. 일부 제안에서 매출 비중과 구매 고객을
혼동하는 문제를 발견해 지침을 구체화했다. 두 번째는 5개 모두 generic으로 판정했고
사례 ID·전체 응답 검사를 통과했다. 이는 현재 응용 가설의 구체성 부족을 찾은 결과이지
사례가 쓸모없거나 GPT의 사실 정확도가 입증됐다는 뜻은 아니다. 두 번째 응답의 제안에도
미확인 성별×연령 교차 고객군 표현이 남아 최소 정책 검사로 제안 문구를 보정했다.
검토 판정·사례는 보존하고 모델 제안이 보정됐다는 사실을 Markdown에 표시한다.
이 저장 자료 검증에서
새 Scout·기사·YouTube 호출은 0회다.

Python 전체 170개와 실제 n8n export의 Code 노드 검사가 통과했다.
새 합성 검사는 출처 ID를 모델에 요구하지 않는 경로, 사례 누락·추가·중복 거절,
모순된 유용 판정 거절, 다른 지역 입력, 미완료 보존·비밀값 없는 오류를 확인한다.
offline 로컬 HTTP에서도 다음 상태를 실제로 확인했다.

| 항목 | 결과 |
|---|---|
| health | 200 |
| 인증 없는 조회 | 401 |
| 필수 입력 누락 | 422 |
| 없는 작업 조회 | 404 |
| 정상 접수 → 완료·브리프 반환 | 202 → completed |
| 동일 입력 재접수 | 200, 동일 job_id |
| 같은 request_id의 다른 입력 | 409 |
| 응답 API 키 비노출 | 통과 |

대기열·만료·실행 실패·provider 실패·timeout 처리는 합성 회귀 검사로 검증했다.
로컬 HTTP offline 실행은 실제 외부 조사 결과를 주장하지 않는다.
저장 자료와 실행 결과는 Git에서 제외한 `.venv/verification/pre-web/`에 남겼다.

이어 독립 프로세스에서 실제 새 상권 요청 1건을 HTTP API로 실행했다.
Quant·Local·Naver Trend를 새로 조사하고 원문 확인과 GPT 연구 Critic을 연결했다.
접수 202 → completed, Quant success / Local partial / Trend partial,
GPT EVALUATED·1회, 고유 출처 20개, 응답 키 비노출을 확인했다.
YouTube는 이전 보류를 유지했다. 이 과정은 한 번 실행하고 종료하며 기존 `.env`나
상시 서버의 유료 호출 설정을 바꾸지 않았다. 결과는 `live-http-result.json`과
`LIVE_RESEARCH_BRIEF.md`다. 로컬 HTTP API 검증과 원격 n8n Cloud 경로 검증은 구분한다.

## 외부 연결 및 운영 설정

기존 `SPOT - Main Entry`에는 접수·조회 Webhook과 저장된 Header Auth가 있다.
사용자 승인 후 새 공개 HTTPS 개발 터널로 HTTP 노드 2개를 갱신했고, 기존 인증을 유지했다.
8767 서버는 live / semantic shadow / research Critic / 원문 확인으로 실행 중이다.
YouTube 키는 보존하고 `SPOT_TREND_VIDEO_MODE=off`로 조회만 보류한다.
실제 n8n Test Webhook에서 새 조사 접수 202 → 조회 200 completed를 확인했다.
Quant success / Local partial / Trend partial, 고유 출처 20개였다.
이 작업의 GPT 1회는 INVALID_RESPONSE로 종료됐으며 브리프는 보존됐다.
저장된 같은 브리프로 수동 GPT 재검토 1회를 수행한 결과 사례 5개의 형식 검사가 통과했다.
최초 응답 원문을 보관하지 않아 정확한 실패 원인은 확정하지 않는다.
수동 재검토 성공을 최초 작업의 Critic 성공으로 바꿔 보고하지 않는다.

운영 게시에 대한 별도 명시 승인을 받은 뒤 `SPOT - Main Entry`를 Publish했다.
운영 `/webhook/spot-research` 재접수는 200·동일 job_id,
`/webhook/spot-research-status`는 200·completed였다. 기존 입력을 재사용해
새 Scout/GPT 호출 없이 검증했다. 인증 없는 요청은 n8n Header Auth에서 403,
잘못된 job_id와 필수 입력 누락은 422로 거절됐다.
검증 기록은 `n8n-production-checks.json`, 실제 브리프는 `N8N_RESEARCH_BRIEF.md`다.

웹 화면·웹 서버 구현을 시작할 수 있는 개발 연결을 확인했다.
임시 터널·단일 메모리 worker의 한계는 운영 배포와 별도로 관리한다.
PC·터널 종료 시 연결이 끊기고 주소가 바뀔 수 있으므로 상시 호스팅은 후속 작업이다.

설계 참고: [OpenAI prompting](https://developers.openai.com/api/docs/guides/prompt-engineering),
[n8n Webhook의 test/production 경로](https://docs.n8n.io/integrations/builtin/core-nodes/n8n-nodes-base.webhook/).
