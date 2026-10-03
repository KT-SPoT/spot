# PC 없이 운영하는 SPoT 서버 준비

준비된 구성은 Linux 상시 서버 한 대에서 API·웹·HTTPS 프록시를 실행한다.
아직 서버/도메인을 선택하거나 실제 게시하지 않았다. 임시 터널을 제거하려면
**연구 API도 서버로 옮겨야 한다**. 웹만 배포하면 PC 의존은 남는다.

```text
브라우저 -> HTTPS 웹 + 팀 로그인 -> SPoT 웹 -> 인증된 n8n 접수·조회
                                              -> HTTPS 연구 API -> Scout / GPT
```

## 준비한 파일

- `deploy/Dockerfile`: Python 3.12 + API·웹 의존성 + PDF 한글 글꼴, 일반 사용자로 실행.
- `deploy/compose.yaml`: API·웹 내부 포트만 사용, 외부는 프록시의 80/443만 공개,
  중단 후 자동 재시작. 서비스별 설정은 Docker secret으로 읽는다.
- `deploy/Caddyfile`: 웹 전체 팀 로그인, HTTPS, 연구 API의 접수·조회·health만 전달.
- `SPOT_WEB_PUBLIC_ORIGIN`: 정확한 HTTPS origin 검사, Secure 쿠키와 POST Origin 검사.

**첫 배포의 운영 범위:** 팀 공용 로그인 + 세션별 작업 소유권이다. 개인별 계정 서비스는 아니다.
작업·세션·내보내기 캐시는 메모리에 있으며 기본 1시간 후 또는 서버 재시작 시 사라진다.
웹 sessionStorage 기록은 서버 영구 기록을 대체하지 않는다. 재시작 시 실행 중 작업을
자동 재호출하지 않는다. 중단 후 같은 요청을 다시 보내면 새 호출이 생길 수 있다.
외부 고객용 운영 전에 작업 DB·계정별 소유권·요금 한도·백업을 추가해야 한다.

## 서버에서 설정할 것

1. 상시 Linux VM, Docker Compose, 고정 IP와 웹/API용 도메인 두 개를 준비한다.
   두 도메인의 DNS를 서버로 연결한다. 80/443만 외부에서 접근하게 한다.
2. 저장소를 서버에 내려받고 `deploy/secrets/`에 아래 파일을 **서버에서 직접** 만든다.
   실제 값은 깃·채팅·이미지 빌드에 넣지 않는다. 소유자만 읽게 권한을 제한한다.
   - `api.env`: 기존 Scout 키, GPT 키, `SPOT_API_TOKEN`, API 호출 정책, `SPOT_API_MODE=live`.
   - `web.env`: `SPOT_N8N_TOKEN`, `SPOT_N8N_BASE_URL`, `KAKAO_REST_API_KEY`만 필요.
   - `web-login.caddy`: 아래 형식의 로그인 설정. 해시값은 Caddy의 대화형
     `caddy hash-password`로 생성한다. 일반 비밀번호를 파일에 쓰지 않는다.
3. `deploy/hosting.env`에는 비밀이 아닌 `SPOT_WEB_DOMAIN`, `SPOT_API_DOMAIN`만 적는다.
4. 아래 명령으로 검증·실행한다. 현재 개발 PC에서는 Docker 미설치로 이미지 빌드와 TLS는 검증하지 않았다.

```caddyfile
basic_auth {
    team {생성한_bcrypt_해시}
}
```

```bash
docker compose --env-file deploy/hosting.env -f deploy/compose.yaml config --quiet
docker compose --env-file deploy/hosting.env -f deploy/compose.yaml build
docker compose --env-file deploy/hosting.env -f deploy/compose.yaml run --rm --no-deps proxy caddy validate --config /etc/caddy/Caddyfile
docker compose --env-file deploy/hosting.env -f deploy/compose.yaml up -d
```

5. n8n `SPOT - Main Entry`의 create/status HTTP 노드를 새 API 도메인의
   `/v1/research/jobs`, `/v1/research/jobs/{job_id}`로 바꾼다. 기존 Header Auth는 유지한다.
   API 토큰이 서버 설정과 일치하는지 값은 출력하지 않고 확인한다. 테스트 후 Publish한다.
6. 웹 비로그인 차단·다른 세션 조회 차단·PDF 한글 출력·조회 재시도를 먼저 검증한다.
   그다음 승인한 실제 조사 1건으로 n8n·Scout·GPT 연결을 확인하고 이전 터널을 종료한다.

정확한 서버 재시작·작업 만료 조건은 화면과 이용자 안내에 유지한다.
n8n Cloud 계정 상태·기관 API 점검·YouTube 쿼터는 서버 이전으로 해결되지 않는다.

공식 참고: [Caddy Basic Auth](https://caddyserver.com/docs/caddyfile/directives/basic_auth),
[Docker Compose 환경 설정](https://docs.docker.com/compose/how-tos/environment-variables/set-environment-variables/).
