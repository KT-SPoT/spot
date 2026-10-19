# SPOT API / n8n 연결

현재 연구 Critic·웹 구현 전 검증 결과는 [PRE_WEB_READINESS.md](PRE_WEB_READINESS.md),
웹 서버 경유 입력·조회·오류 경계는 [WEB_INTEGRATION.md](WEB_INTEGRATION.md)를 참고한다.

## 1. Linux에서 API 실행

저장소 루트에서 실행합니다. 기존 provider 키는 `.env`에 그대로 둡니다.

```bash
python -m pip install -r requirements-api.txt -c constraints-test.txt
python -m src.api.configure
python -m uvicorn src.api.app:create_app --factory --host 127.0.0.1 --port 8765 --workers 1 --no-access-log
```

`configure`는 비어 있는 `SPOT_API_TOKEN`만 생성하며 값을 출력하지 않습니다.
기존 provider 설정과 이미 설정된 토큰을 보존합니다. 처음에는
`SPOT_API_MODE=offline`으로 연결만 확인합니다. 실제 조사할 때 `.env`의
`SPOT_API_MODE=live`로 바꾸고 서버를 재시작합니다. 실행 중인 셸에 같은 환경변수가
있으면 셸 값이 우선합니다. Live 요청은 provider 사용량을 소모합니다.

현재 PC의 준비된 WSL 환경에서는 다음처럼 실행할 수 있습니다.

```powershell
wsl -d Ubuntu-24.04 -u root --exec /bin/bash -lc 'cd /mnt/c/Users/User/Desktop/Spot && /opt/spot-venv/bin/python -m uvicorn src.api.app:create_app --factory --host 127.0.0.1 --port 8765 --workers 1 --no-access-log'
```

`http://127.0.0.1:8765/health`는 연결 확인용입니다. `/docs`에서는
Authorize에 별도 API 토큰을 입력해 요청을 테스트할 수 있습니다.
제공자 키는 요청 본문에 넣지 않습니다.

## 2. n8n에서 파일 가져오기

[spot-research-api.json](../workflows/n8n/spot-research-api.json)을
n8n의 **Import from File**로 가져옵니다. 파일은 비활성 상태이며 키·Credential
ID를 포함하지 않습니다. 팀의 기존 `SPOT - Main Entry`를 덮어쓰지 않습니다.

두 HTTP Request 노드를 설정합니다.

| 노드 | 주소 |
|---|---|
| Create SPOT job | `https://실제-SPOT-서버/v1/research/jobs` |
| Get SPOT job | 표현식의 `https://spot-api.example.invalid` 부분을 실제 서버 주소로 변경 |

서버용 **Header Auth Credential**을 만듭니다.
- Name: `X-SPOT-API-Key`
- Value: 로컬 `.env`의 `SPOT_API_TOKEN` 값
- 이 Credential을 두 HTTP Request 노드에 선택

Webhook 두 노드에도 호출자용 **Header Auth Credential**을 선택합니다.
예를 들어 Name을 `X-SPOT-Entry-Key`로 정하고 Value를 별도로 설정합니다.
외부 호출자는 이 Entry 키만 사용하고, SPOT 서버 토큰과 provider 키는 n8n/서버에 둡니다.

Cloud n8n은 PC의 `localhost`에 접속할 수 없습니다. 실제 연결에는 Cloud n8n이
접속 가능한 HTTPS 서버 또는 별도 개발 터널 주소가 필요합니다. 이 작업에서는
공개 배포·터널·팀 n8n 활성화를 수행하지 않습니다. 같은 PC의 자체 호스팅 n8n은
설치 방식에 따라 WSL/컨테이너에서 접근 가능한 주소를 사용합니다.

Webhook의 **Test URL**을 선택하고 **Listen for test event**로 테스트합니다.
운영에는 설정 확인 후 Production URL을 사용합니다.

## 3. 요청과 결과 조회

1. Submit research의 POST Webhook에 SpotRequest JSON 전송
2. HTTP 202 응답의 `job_id` 저장
3. Research status의 GET Webhook에 `?job_id=작업번호` 전송
4. `queued`/`running`이면 약 5초 후 같은 GET 재조회
5. `completed`이면 `result.research_brief` 또는 `result.research_brief_markdown` 사용
6. `failed`이면 `error.code` 확인; 새 조사 실행은 새 request_id로 요청

입력 예시는 [spot_request.api.example.json](../samples/input/spot_request.api.example.json)을
사용합니다. 테스트용 합성 점포이며 실제 조사 주소로 바꿔야 합니다.
reference_date를 생략하면 한국 시간의 요청일을 사용합니다. 예시에는 수집 날짜를
고정하지 않습니다. 기본 radius_m=1000, lookback_days=180이며 0일도 보존합니다.
request_id를 생략하면 n8n 실행 번호로 생성합니다. 같은 요청을 재전송할 때는
동일한 request_id와 동일한 정규화 입력(기준 날짜 포함)을 유지하세요.

접수 응답 예시(합성 작업 번호):

```json
{
  "job_id": "aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa",
  "request_id": "spot-n8n-example-001",
  "status": "queued",
  "status_path": "/v1/research/jobs/aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa",
  "poll_after_seconds": 5
}
```

완료는 그래프 실행 완료를 뜻합니다. 근거 부족이면 완료된 작업의 Brief 상태가
`failed`일 수 있습니다. `module_status`, Brief 상태와 `needs_manual_check`를 함께
확인하세요. Critic은 실제 규칙을 검사하며 `critic_is_mock=false`입니다.
`critic_result`와 `retry_history`에 검증 및 최대 1회 재조사 결과가 있습니다.
의미·사실 검토는 아직 수동입니다. [종료·재조사 정책](CRITIC_RETRY.md).
API 브리프는 같은 실행의 Quant 원문을 내부적으로 연결해 인구 비율을
표시하고 관련 트렌드 보도를 묶습니다. [기준과 한계](BRIEF_ENRICHMENT.md).

## HTTP API 동작

- `GET /health`: 연결 확인; 인증 불필요
- `POST /v1/research/jobs`: SpotRequest v0.1 본문, 헤더 인증; 신규 202, 동일 요청 재접수 200
- `GET /v1/research/jobs/{job_id}`: 헤더 인증; 상태와 완료 시 브리프 반환
- 401 인증 오류 / 422 입력 오류 / 409 같은 request_id의 다른 입력 / 429 대기열 초과 / 404 작업 없음·만료

API는 매장 이름·주소, 상품·목적을 필수로 검사하고 좌표는 둘 다 또는 둘 다 null로
받습니다. HTTP 입력 제한은 radius_m 1–10000, lookback_days 0–3650입니다.
Scout 입력·출력 공통 계약은 변경하지 않습니다. 전체 Scout 원본·환경변수·예외 본문은
HTTP 응답에 노출하지 않으며 브리프의 키 값과 인증 URL 쿼리를 가립니다.

이 MVP는 한 프로세스·한 조사 worker, 최대 4개 진행/대기 작업, 최대 32개 기록입니다.
완료 기록은 1시간 뒤 만료하거나 기록 한도에 도달하면 오래된 완료 기록부터 제거합니다.
중복 방지도 기록이 남아 있는 동안 적용됩니다. 서버 재시작 시 기록이 사라집니다.
항상 `--workers 1`로 실행하고 `--reload`는 사용하지 마세요. 영구 저장·복수 서버·작업 취소는
후속 범위입니다. 조회를 중단해도 진행 중인 조사는 계속 실행되므로 GET 조회만 재시도하세요.

n8n 응답은 API HTTP 상태를 보존합니다. 연결 실패는 503 `SPOT_API_UNREACHABLE`로 반환합니다.
Provider 부족이나 실패는 완료 결과의 module_status에 남습니다. POST 자동 재시도는 꺼두었습니다.

## 검증

```bash
python -m unittest discover -s tests -v
node tests/test_n8n_workflow.js
```

HTTP 테스트는 합성 runner와 실제 그래프의 offline 모드를 사용합니다. 외부 provider를
호출하지 않습니다. n8n 검증은 가져올 JSON의 연결·인증 설정과 실제 Code 노드 내용을 실행합니다.
2026-10-01 팀의 기존 `SPOT - Main Entry`에 접수·조회 노드와 저장된 인증을
연결했습니다. 임시 HTTPS 개발 터널을 통한 offline 및 live 테스트에서 접수
202/조회 200을 확인했습니다. Live 결과에는 세 인구 모집단의 비율과 관련
보도 4건/1건의 두 후보 묶음, 고유 출처 20개가 포함됐습니다. 유튜브는
테스트에서 제외했고 실제 인증 값의 응답 노출이 없는지 확인했습니다.
운영 Publish는 하지 않았으며 PC/터널 종료 시 연결은 끊깁니다.

참고: [HTTP Request](https://docs.n8n.io/integrations/builtin/core-nodes/n8n-nodes-base.httprequest/),
[Webhook](https://docs.n8n.io/integrations/builtin/core-nodes/n8n-nodes-base.webhook/),
[Respond to Webhook](https://docs.n8n.io/integrations/builtin/core-nodes/n8n-nodes-base.respondtowebhook/),
[Import/export](https://docs.n8n.io/workflows/export-import/).
