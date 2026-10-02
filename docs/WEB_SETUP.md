# SPOT 로컬 웹 MVP

매장·주소·상품·조사 목적을 입력하면 웹 서버가 기존 인증된 n8n 운영 Webhook으로
조사를 접수한다. 5초 간격으로 작업 상태를 조회하고, 완료 시 브리프·Scout 상태와
GPT 검토 완료 여부를 표시한다. Markdown 파일로 저장할 수 있다.
출력은 `textContent`로 표시하므로 조사 자료의 HTML·스크립트는 실행하지 않는다.

## 실행

기존 SPOT API·개발 터널·게시된 n8n 워크플로가 실행 중이어야 한다.
기존 `.env`의 `SPOT_API_TOKEN`을 서버에서 사용한다. n8n 인증값이 다른 경우
`SPOT_N8N_TOKEN`을 별도로 설정한다. 키는 브라우저에 전달하지 않는다.
`SPOT_N8N_BASE_URL`은 n8n HTTPS origin이며 기본값은 현재 프로젝트 Cloud 주소다.

```bash
python -m uvicorn src.web.app:create_app --factory --host 127.0.0.1 --port 8768 --workers 1 --no-access-log
```

브라우저에서 `http://127.0.0.1:8768`에 접속한다. WSL 환경에서는 설치된 Python으로
저장소 루트에서 실행한다. 새 조사 버튼은 실제 Scout·GPT 호출을 만들 수 있다.
YouTube 보류 설정은 기존 연구 서버의 설정을 따른다.

## 요청·소유권

- 서버가 HttpOnly·SameSite Strict 쿠키로 1시간 세션을 발급한다.
- 접수·조회는 동일 사이트이며 POST Origin을 검사한다. 허용 Host는 loopback뿐이다.
- 입력은 기존 ResearchRequest 모델로 검사한다. 좌표는 함께 입력하며 기준일은
  한국 시간의 오늘을 화면 기본값으로 사용한다.
- 세션별 요청 ID를 별도 namespace로 전달해 다른 세션의 같은 ID와 충돌하지 않는다.
- 세션이 접수한 job_id만 조회한다. 접속당 새 요청 최대 4개, 세션 최대 256개다.
- POST 연결 실패 시 자동 재접수하지 않는다. 같은 입력·ID로 수동 재연결하며,
  변경 입력은 새 요청으로 접수한다. GET 조회 오류도 명시적 다시 조회를 제공한다.
- 새로고침 시 같은 탭의 접수 ID·조회 작업을 복원한다. 접수 입력은 sessionStorage에
  저장되므로 공용 PC에서는 탭을 닫아 제거한다.

## 개발 범위

이 웹은 이 PC의 loopback에서 쓰는 MVP다. 로그인 없는 세션은 같은 PC의 브라우저를
구분하는 개발용 소유권이며 사용자 계정 인증을 대체하지 않는다.
외부 공개를 위해 bind 주소를 변경하지 않는다. 공개 배포 전에는 로그인,
HTTPS Secure 쿠키, 계정별 작업 소유권·요청 제한, 영구 작업 저장과 상시 SPOT 호스팅을
구현해야 한다. 세션과 작업은 각 서버 재시작 시 사라진다.
임시 연구 터널은 PC·터널 종료 시 끊기며 n8n Cloud 체험 기간도 별도 관리한다.

완료 상태는 실행 완료를 의미한다. 일부 Scout 자료 부족이나 GPT 응답 형식 오류는
별도로 표시하며, 확보한 브리프를 폐기하지 않는다. 고객 선호·행사 효과를 확정하지 않는다.

## 검증

`tests/test_web.py`는 외부 호출 없이 접수·조회, 키 비노출, 다른 세션 조회 거절,
Origin·입력 검사, timeout 후 동일 요청 재연결, upstream 오류·형식 오류와 접수 제한을 검증한다.
실제 브라우저 접수 결과와 화면은 Git에서 제외한 `.venv/verification/web/`에 보관한다.

2026-10-02 실제 브라우저에서 명지국제신도시 매장 입력으로 새 조사 1건을 접수했다.
웹 → n8n → SPOT API → 브리프 조회가 완료됐고, 고유 출처 20개,
정량 지표 20개·직접 지역 변화 3건·참고 후보 5건과 GPT 연구 검토가 표시됐다.
Quant success / Local partial / Trend partial이었다. YouTube 조회는 보류했다.
자료의 HTML 실행 차단과 안전한 출처 링크·표·섹션 표시는 Node 검사로 검증한다.
전체 Python 178개, 브리프 렌더러 및 기존 n8n 검사가 통과했다.
