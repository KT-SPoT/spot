# PC 없이 운영하는 SPoT 서버 준비

## 2026-10-08 분석 구조 운영 반영

- 서울 `spot-server-seoul`의 API·웹을 `spot-app:20261008-analysis-agent`로 갱신했다. 기존 버전 `spot-app:20261008-local-context`에서 실제 차이 8개 소스만 패치했다.
- 역할별 입력 분리, 지역 성격 → 관측 관계 → 홍보 기회 구조, 웹/PDF의 동일 분석 전달과 지역 범위 Critic을 운영 경로에 반영했다. 일반적 분석을 탈락시키는 기준은 추가하지 않았다.
- 생성 입력에 개별 최대 요일과 평일/주말 합계를 구분하고, 소비 시간을 실제 구매 목적·퇴근/관람 행동으로 단정하지 않도록 지침을 보완했다. 원본 관측은 보존한다.
- 백업: `/opt/spot/deploy/backup-analysis-agent-20261008`. 기존 인증·API 비밀값·n8n 설정은 유지했다. API·웹만 재시작했으며 다른 컨테이너를 삭제하지 않았다.
- 확인: 이미지 import, API health, 두 컨테이너의 HTTP 200, 14개 대상 소스의 줄바꿈 정규화 후 해시 일치, 역할별 입력, 저장된 실제 생성 분석의 Markdown/PDF 전달, 웹 experience.js 응답 해시 일치. PDF는 서버 폰트로 218127 bytes 생성.
- 배포 검증 중 새 Scout/GPT 호출 없음. 수정 지침으로 새 문장을 생성한 운영 E2E 시험은 하지 않았다. 기존 저장 보고서는 자동 재작성되지 않는다.
- 운영 주소가 브라우저에서 `ERR_BLOCKED_BY_CLIENT`로 차단되어 운영 화면의 시각 검증은 하지 못했다. 서버 내부 HTTP 및 자산 검사는 성공했다.
- 소스·검사·증빙: `output/deployment/analysis-agent-20261008/`. 초기 검사에서 CRLF/LF 차이를 분리하지 못해 해시 검사가 실패했고, 줄바꿈 정규화로 확인했다. 검사 스크립트의 자산 키 오타도 고친 뒤 웹 자산 일치를 확인했다. 운영 코드 장애로 판정하지 않는다.

준비된 구성은 Linux 상시 서버 한 대에서 API·웹·HTTPS 프록시를 실행한다.
웹과 연구 API를 GCP VM으로 이전했다. 팀 로그인 및 n8n Header Auth를 유지한다.
PC와 개발 터널 없이 서버에서 Scout/GPT 조사를 실행한다.

## 2026-10-06 서울 이전

- 프로젝트: `project-a5cc43f9-95b8-4269-b90`
- VM: `spot-server-seoul`, `asia-northeast3-a`, `e2-small` (2 GiB), 표준 디스크 30 GiB.
- 웹: https://web.34.50.4.140.sslip.io/
- 연구 API: https://api.34.50.4.140.sslip.io/
- 고정 주소: `spot-server-seoul-ip`. 기존 팀 로그인 설정을 복사했다.
- n8n Cloud `SPOT - Main Entry`의 접수·조회 노드를 서울 API로 변경하고
  `Seoul API migration 2026-10-06` 버전을 게시했다. 수신 webhook URL과 인증은 동일하다.
- 자동 정지: **2026-10-22 23:59 KST** (`2026-10-22T14:59:00Z`), 종료 동작 `STOP`.
  정지는 삭제가 아니다. 디스크·고정 IP·백업 비용은 정지 후에도 발생하므로
  프로젝트 종료 시 필요한 자료를 내려받고 남은 자원을 정리해야 한다.
- 연결된 결제 계정에서 무료 체험 잔액 ₩407,626, 만료일 2027-01-05를 확인했다.
  확인 시점의 값이며 사용량 반영 지연이 있을 수 있다. 유료 계정 업그레이드는 하지 않았다.
- 서울 VM·디스크·IPv4의 22일까지 예상 비용은 약 $11–12에 전송량과
  이전 중 중복 자원·스냅샷 비용이 더해진다. 무료 등급 VM은 아니며 유효한 체험 크레딧을 사용한다.
- HTTPS health 200, 비인증 연구 조회 401, 외부 docs 404, 웹 팀 로그인 401을 확인했다.
  n8n 운영 접수 202 및 실행 상태 조회까지 확인했다.
- 실제 남부산점 조사: 작업 완료, Quant `success`, Local/Trend `partial`,
  Brief `manual_review`. 서울 이전으로 소상공인 연결이 복구됐지만
  모든 출처의 완전 확보나 Critic 통과를 뜻하지 않는다.
  동일 결과에서 한글 PDF 173,541 bytes 생성 및 PDF 서명을 확인했다.
  검증 파일은 서울 서버 `/opt/spot/output/deployment/seoul-migration-smoke.pdf`에 보관한다.
- 이전 검증 후 오리건 `spot-server`를 정지했고 `TERMINATED`를 확인했다.
  복구용 원본 디스크·고정 IP·이전 스냅샷은 보존했다. 정지된 VM의 보존 자원에도
  저장 및 주소 요금이 발생한다. 사용자 PC에서 서울 HTTPS health 200도 확인했다.

아래의 초기 배포 준비 및 자체 n8n 구성 안내는 이력/대안이다. 현재 운영은 n8n Cloud를 사용한다.

### 2026-10-07 지역 해석·사례 연결 경로 적용

API와 웹에 `spot-app:20261007-connections-v3`를 적용했다. 기존 n8n Cloud URL과 인증은 유지하고
`SPOT_BRIEF_SYNTHESIS=connections`, `SPOT_SCOUT_MODE=live`, `SPOT_SEMANTIC_MODE=shadow`,
`SPOT_CRITIC_PROFILE=research`를 서버에서 명시적으로 설정했다. 기본 해석을 보존한 뒤
Local 맥락·Trend 행동의 연결을 별도로 생성·검토한다. 새 조사마다 최대 4회 GPT 호출이다.

기존 설정·변경 소스는 `/opt/spot/deploy/backup-connections-20261007-v2`와
`backup-connections-20261007-v3`, `backup-connections-20261007-v4`에 보존했다. 이전 이미지도 남아 있다. 준비 검사는 이미지 내
Python 컴파일·그래프 import이며, 교체 후 health를 최대 60초 재시도해 시작 준비를 확인한다.
처음 즉시 health 검사에 실패한 배포는 이전 버전으로 복구한 후 재시도했다.
최종 HTTPS health 200과 웹 팀 로그인 401을 확인했다. n8n 워크플로·프록시·자동 정지 설정은 수정하지 않았다.

동래·광화문 새 조사는 모두 기존 n8n 운영 경로로 완료됐다. 처음 실행에서 상권 해석 3개와
Local 참고 1개씩 채택됐고, YouTube 결과는 광화문 10건·동래 0건이었다. 실제 기사 행동 표현의
인식 누락을 추가 수정하고 같은 자료의 연결 단계 검증을 별도로 진행했다.
세부 결과는 [지역 해석 검증 기록](RESEARCH_SYNTHESIS_PILOT.md)에 남긴다.
교체로 웹 세션과 메모리 작업이 초기화되므로 적용 후에는 다시 로그인하여 새 조사를 요청한다.
이전 조사 결과 검증 파일은 컨테이너 교체 전 서울 서버의 사용자 홈에 별도로 보존했다.

### 2026-10-07 기획 단서 다운로드 수정

`planning-hints.js`가 정적 파일 허용 목록에서 누락되어 404였고, 다운로드 버튼은
해당 모듈이 없으면 안내 없이 종료했다. 허용 목록을 수정하고 버튼을 기존 세션 소유권
검사를 적용한 `/api/research/{job_id}/handoff` 내보내기로 연결했다.
서울 웹 이미지 `spot-app:20261007-hints-fix`를 배포했다. API 컨테이너는 재시작하지 않았다.
웹 재시작으로 접속 세션이 초기화되므로 기존 작업의 조회는 세션 만료로 실패할 수 있다.
서버 내보내기는 확보된 브리프를 사용하며 추가 Scout/GPT 조사 호출을 하지 않는다.

같은 날 사용자 요청에 따라 화면·TXT·PDF의 기획 단서를 여섯 항목의 짧은 요약으로
정리했다. 타깃 상품·직원 수는 빈칸, 상권·고객·요일·시간대는 별도 관측 요약,
판촉물 예산은 금액을 만들지 않고 출처가 있는 행사 참여 방식의 참고 아이디어를 제공한다.
요약에는 기사 본문·근거 URL·장문 안내를 넣지 않는다. 원본 조사 화면의 근거는 유지한다.
웹 운영 이미지는 `spot-app:20261007-compact-clues`이며 API의 실행 중 조사는 재시작하지 않았다.

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

## 무료 우선 배포 검토 (2026-10-06)

**현재 선택: GCP.** Oracle 가입 실패 후 사용자가 GCP로 전환을 요청했다.
아래 Oracle 내용은 이전 후보 검토 기록이며, 현재 배포 대상으로 사용하지 않는다.
기존 오리건 VM을 먼저 확인하고, 재사용할 수 없다면 `us-west1`의 `e2-micro`,
표준 영구 디스크 30 GB 이하를 기준으로 검토한다. 무료 한도는 결제 계정의
기존 사용량과 합산되므로 기존 VM·디스크 사용량을 확인해야 한다.
현재 확인한 `deploy` 프로젝트는 Compute Engine API가 비활성화돼 있으며,
콘솔에는 무료 체험 기간 종료 안내가 표시된다. 다른 프로젝트의 기존 서버 여부는 미확인이다.

이후 사용자가 부계정의 무료 체험을 시작했으며, 콘솔에서 새 프로젝트
`project-a5cc43f9-95b8-4269-b90`, 크레딧 407,626원, 체험 종료일
2027-01-05를 확인했다. 사용자 승인으로 Compute Engine API 활성화를 완료했다.
`spot-server` 생성 화면에는 `us-west1`, `e2-micro`, Ubuntu 24.04 LTS,
표준 영구 디스크 30 GB, 자동 스냅샷 없음, 서비스 계정 없음으로 구성했다.
HTTP/HTTPS와 SSH 관리 연결은 사용자가 승인했다. API 키는 아직 서버로 이전하지 않았다.
현재 콘솔의 VM 가격 미리보기는 무료 등급 할인과 외부 IPv4 비용을 모두 반영한
최종 청구액으로 사용하지 않는다. 체험 종료 후 운영 방식을 별도 결정해야 한다.

사용자가 서버 생성·HTTP/HTTPS·SSH 관리 연결을 승인했고 2026-10-06에
`spot-server`를 생성했다. 콘솔 실행 상태와 `us-west1-a`, Ubuntu 24.04,
`e2-micro`, 표준 디스크 30 GB, 서비스 계정 없음, HTTP/HTTPS 사용을 확인했다.
외부 주소는 현재 임시 IPv4 `136.87.17.88`이며 정적 주소로 예약하지 않았다.
이 기록은 VM 확보 완료를 뜻하며 SPoT 서비스 배포 완료를 뜻하지 않는다.
사용자가 Cloud Shell을 승인한 뒤 독립 Cloud Shell 화면에서 SSH 연결에 성공했다.
2026-10-06 확인 시 부하 평균은 0.00 / 0.01 / 0.03, 메모리는 953 MB 중
350 MB 사용, 602 MB 가용이었다. SSH 서비스도 active였다. 초기 CPU 경고만으로
VM 사양을 올리지 않는다. `deploy/bootstrap-ubuntu.sh`로 Ubuntu 24.04의
공식 Docker 저장소에서 실행 환경을 설치하고 2 GB swap을 준비한다.
swap은 빌드 시 메모리 부족에 대비하는 것이며 동시 서비스 성능을 보장하지 않는다.
설치 완료 후 Docker 29.8.2, Compose v5.6.0, Docker 서비스 active 및
swap 2047 MB를 확인했다. 비밀값이 없는 코드 묶음을 `/opt/spot`으로 복사했으며
전송 전후 SHA-256이 일치했다. `spot-app:20261006` 이미지 빌드에 성공했으며,
외부 네트워크를 차단한 컨테이너에서 API health, 미인증 요청의 401 차단,
웹 첫 화면 및 Trend 스크립트 응답을 검증했다. 웹 테스트는 허용된
`127.0.0.1` Host로 실행했다. 실제 서비스 기동·HTTPS·n8n 이전·실제 조사는 아직
검증하지 않았다. 검증 후 메모리 435 MB 사용, 517 MB 가용, swap 43 MB 사용이었다.

사용자가 Cloud Shell HTTPS 업로드 및 SSH 경유 키 이전을 승인해 2026-10-06에
필요한 키만 서비스별 `api.env`, `web.env`로 이전했다. 원본 로컬 `.env`는 유지했다.
서버의 `/opt/spot/deploy/secrets`는 root 소유 700, 두 설정 파일은 root 소유 600이다.
전송 묶음의 무결성을 확인했고 로컬·Cloud Shell·VM의 임시 복사본을 삭제했다.
네트워크를 차단한 임시 컨테이너에서 저장된 설정을 로드하고 UID 10001로
API health 및 웹 첫 화면의 200 응답을 확인했다. 검사 컨테이너는 종료·삭제했다.
실제 외부 API 호출은 하지 않았으며, 공개 HTTPS·상시 Compose 기동·n8n 연결은
아직 완료하지 않았다. 웹의 n8n 주소는 기존 Cloud origin을 유지한 상태다.

2026-10-06 기존 IPv4 `136.87.17.88`을 `spot-server-ip`로 예약했고 IN_USE를
확인했다. 웹/API 주소는 `web.136.87.17.88.sslip.io`,
`api.136.87.17.88.sslip.io`로 정했다. 별도 도메인 구매 없이 sslip.io DNS를 사용한다.
`compose.server.yaml`은 검증한 앱 이미지와 digest로 고정한 Caddy를 사용하며,
`Caddyfile.stage`로 팀 로그인 설정 전 웹을 503으로 차단한다. Compose의 api·web·proxy
실행을 확인했고 외부 HTTPS 검사에서 health 200, 미인증 작업 조회 401,
API `/docs` 404, 잠긴 웹 503을 확인했다. 앱 브라우저의 새 주소 열기는
ERR_BLOCKED_BY_CLIENT로 실패했으므로 실제 화면 접근을 확인했다고 기록하지 않는다.

사용자는 n8n Cloud 체험을 유지하다가 검증 성공 후 유료 플랜으로 전환할 계획임을
명확히 했다. 현재 운영 구성은 **n8n Cloud + GCP 웹·조사 API**다.
체험 종료 대비로 설치했던 n8n Community 2.41.7 컨테이너는 중지하고 운영
프록시 구성에서 제외했다. 복구 가능한 암호화 키와 `n8n_data` 볼륨은 보존한다.
Cloud의 `SPOT - Main Entry`는 기존 Header Auth를 유지하고 접수·조회 노드를
`https://api.136.87.17.88.sslip.io`로 변경해 `GCP API connection` 버전으로 게시했다.
유료 플랜 전환은 사용자가 진행하며 이번 배포에서 구독을 변경하지 않는다.
GCP 내부에서 조회 웹후크를 검사했을 때 미인증 요청은 403으로 차단됐지만,
인증된 운영·테스트 조회는 n8n의 `There was a problem executing the workflow`
메시지와 500을 반환했다. 새로운 실행 기록은 확인되지 않았고 구체적 원인은 아직
확정하지 않았다. GCP API health의 외부 HTTPS 200은 재확인했다. 따라서
워크플로 게시와 종단 간 연결 검증 성공을 구분하며, 실제 조사 완료로 기록하지 않는다.
이후 n8n 편집기를 새로고침하자 `Your trial is over. Upgrade now to keep automating.`
안내를 확인했다. 이전의 24시간 잔여 표시는 갱신되지 않은 화면 상태였다.
n8n Cloud 유지 계획에서는 사용자의 구독 전환이 선행돼야 한다. 전환 후 운영
조회 404 및 실제 접수·조사·PDF를 다시 검증해야 하며, 체험 종료만으로 모든
기술적 연결 문제가 해결됐다고 간주하지 않는다. 결제는 진행하지 않았다.
사용자가 유료 전환을 완료한 뒤 체험 종료 안내가 사라졌고, 인증된 운영 조회는
존재하지 않는 작업에 대한 정상 404를 반환했다. 웹과 동일하게 기본값을 채운
실제 지역 요청도 202로 접수됐다. 첫 요청은 소상공인365의 응답 없는 연결 종료
(`RemoteDisconnected`)가 처리되지 않아 전체 조사에 실패했다.
`quant_sbiz365._request_text`에서 연결 단절과 HTTP 프로토콜 오류를 비밀값 없는
`Sbiz365Error`로 변환하도록 보완했다. 기존 HTTP 상태 오류 처리는 유지한다.
새 Docker 이미지에서 연결 단절·기존 HTTP 오류 처리 회귀 검증 2건을 통과했고,
`spot-app:20261006-transport-fix-v2`로 API·웹을 재배포했다.
기관 통신 실패 자체가 해결됐다는 뜻은 아니며 실제 자료 수집 여부는 별도 확인한다.
보완 후 KT플라자 남부산점(부산 동구 부산진성공원로 23)의 실제 조사에서 접수
202, 작업 completed, GPT 검토 performed=True, 브리프 manual_review 및 PDF
생성(156,036 bytes, PDF signature)을 확인했다. Quant failed, Local partial,
Trend partial이므로 자료 완전성이나 소상공인365 연결 정상으로 기록하지 않는다.
PDF는 서버의 `output/deployment/gcp-deployment-smoke.pdf`에 저장했고 이번 검증은
생성 기능 검사이며 PDF 페이지의 시각 검수와 사용자 웹 세션의 내보내기 검증은 별도다.
`set-team-login.sh`는 사용자가 VM에서 직접 비밀번호를 두 번 입력하고 bcrypt
해시만 저장하도록 준비한 도구다. 값은 명령 인수나 로그에 넣지 않는다.
이 도구의 사용자 비밀번호 입력과 웹에서의 실제 조사·PDF 검증은 아직 남아 있다.
초기 비밀번호 설정에서 Caddy가 EOF를 반환한 원인은 stdin에 줄바꿈 없이
비밀번호를 전달한 것이었다. `set-team-login.sh`는 줄바꿈을 포함해 전달하도록
수정했다. 실제 비밀번호는 사용자가 다시 입력하며 채팅이나 로그에 출력하지 않는다.

외부 IPv4는 현재 시간당 $0.005이며 월 1시간 무료 한도를 제외하면 30일 상시 사용 시
약 $3.60이다. 무료 VM을 선택해도 서버 예산 월 1,000원 미만을 자동 충족하지 않는다.
추가 전송량·도메인·GPT·n8n Cloud 비용은 별도다. 기존 서버 확인 및 비용 검토 전에는
새 유료 자원 생성이나 결제 계정 업그레이드를 진행하지 않는다.
`e2-micro`는 메모리가 작으므로 API·웹의 동시 실행과 PDF 생성에 충분한지는
측정해야 한다. 기존 Compose를 그대로 실행하는 것으로 성능 검증을 대신하지 않는다.

GCP 근거:
[오리건 VM·디스크 무료 한도](https://docs.cloud.google.com/free/docs/free-cloud-features),
[외부 IPv4 요금](https://cloud.google.com/vpc/network-pricing).

### n8n을 같은 서버에서 실행하기

`compose.n8n.yaml`은 기존 Compose에 추가하는 선택 구성이다. `Caddyfile.n8n`으로
웹·연구 API·n8n의 HTTPS 주소를 분리한다. n8n의 5678 포트는 외부에 직접 공개하지 않는다.
실제 이미지 실행과 TLS 검증은 아직 하지 않았으며 서버 확보 후 진행한다.

`hosting.env`에 `SPOT_N8N_DOMAIN`과 검증한 공식 이미지의 고정 버전을
`SPOT_N8N_IMAGE`로 지정한다. `deploy/secrets/n8n.env`는 서버에서 소유자만 읽게
만들고 고정 `N8N_ENCRYPTION_KEY`를 설정한다. 키는 Git·채팅·로그에 출력하지 않는다.
n8n은 SQLite 및 계정·설정 파일을 `n8n_data` 볼륨에 저장한다. 볼륨과 암호화 키를
함께 백업하고, 삭제 옵션을 사용해 재배포하지 않는다. n8n 관리자 초기 계정은 사용자가
직접 만든다. 현재 Cloud 워크플로를 가져온 뒤 Header Auth를 새 n8n에 재등록해야 한다.
웹의 `SPOT_N8N_BASE_URL`도 새 HTTPS origin으로 변경한다.

```bash
docker compose --env-file deploy/hosting.env -f deploy/compose.yaml -f deploy/compose.n8n.yaml config --quiet
docker compose --env-file deploy/hosting.env -f deploy/compose.yaml -f deploy/compose.n8n.yaml up -d --build
```

참고: [n8n 공식 Docker 배포·데이터 보존 안내](https://github.com/n8n-io/n8n/blob/master/docker/images/n8n/README.md).

예산은 서버 월 1,000원 미만, 무료 우선이다. 아래는 배포 후보 검토이며 실제
계정·서버·DNS는 아직 확보하지 않았다. 현재 Compose에는 n8n 서비스가 없으므로
이 파일만 실행해도 n8n Cloud 비용까지 없어지는 것은 아니다.

- 우선 후보: Oracle Cloud의 Always Free 표시가 있는 Linux VM.
  현재 공식 한도는 Ampere A1 기준 총 2 OCPU / 12 GB 메모리에 해당한다.
  SPoT 웹·조사 API와 무료 n8n Community Edition을 한 VM에서 실행하는 구성을 검토한다.
  Arm 이미지 빌드와 의존성 호환은 실제 서버에서 확인해야 한다.
- Oracle은 무료 자원 부족으로 생성이 실패할 수 있고, 7일간의 CPU·네트워크·메모리
  사용 조건에 따라 유휴 VM을 회수할 수 있다. 무료 서버를 무중단 운영 보장으로 설명하지 않는다.
- Render 무료 웹 서비스는 15분간 요청이 없으면 절전한다. 현재 조사 작업과 세션은
  메모리에 있으므로, 절전·재시작 영향을 해결하지 않고 상시 서버의 대체로 채택하지 않는다.
- n8n Cloud 구독 비용을 피하려면 기존 워크플로를 내보내 자체 호스팅 n8n에 가져오고,
  Header Auth 자격 증명은 별도로 재등록해야 한다. n8n 데이터 볼륨과 암호화 키를 보존하고
  백업·복구를 검증한다. 이전 성공 전에는 현재 워크플로와 터널을 종료하지 않는다.
- 주소 비용도 예산에 포함한다. 보유 도메인 또는 무료 DNS 주소의 사용 가능 여부를 확인한다.
  API 사용료, 특히 GPT 호출 비용은 서버 무료 한도와 별개이며 이 예산에 포함됐다고 가정하지 않는다.

다음 순서는 계정 준비 → 무료 VM 확보 → 고정 HTTPS 주소 준비 → n8n 포함 배포 구성
완성 → 비밀값을 노출하지 않고 서버 설정 → 기존 워크플로 이전 → 연결·PDF·조사 검증이다.
유료 계정 전환이나 유료 자원 생성으로 무료 용량 부족을 우회하지 않는다.

공식 근거:
[Oracle Always Free 자원·회수 조건](https://docs.oracle.com/en-us/iaas/Content/FreeTier/freetier_topic-Always_Free_Resources.htm),
[Oracle 가입과 카드 인증](https://docs.oracle.com/en-us/iaas/Content/GSG/Tasks/signingup_topic-Sign_Up_for_Free_Oracle_Cloud_Promotion.htm),
[Render 무료 서비스 제한](https://render.com/docs/free),
[n8n Community Edition](https://docs.n8n.io/hosting/community-edition-features/).

공식 참고: [Caddy Basic Auth](https://caddyserver.com/docs/caddyfile/directives/basic_auth),
[Docker Compose 환경 설정](https://docs.docker.com/compose/how-tos/environment-variables/set-environment-variables/).

### 2026-10-08 — Reader layout finish
- Deployed `spot-app:20261008-reader-final` to existing Seoul API/web; source-only 7-file patch, credentials and other services preserved.
- PDF section 03 retains up to four distinct Local news items without requiring planning interpretations; Area Summary describes the planning implication of population/sales distributions; Trend uses action/context/idea blocks and collapsible source detail.
- Scoped validation: 53 Python tests and Trend Board JS checks passed; stored-data PDF pages 1/7/8 visually reviewed before deployment.
- One fresh Gwanghwamun request through production n8n completed: Quant success, Local/Trend partial, Local 1 item, YouTube 10 videos, four synthesis calls. Production PDF generated successfully (192823 bytes).
- Browser preview on localhost could not connect in this session; no claim of full production UI visual verification. Live output still needs human editorial review; the completed smoke check verifies execution and export, not all generated interpretations.
- Backup: `/opt/spot/deploy/backup-reader-final-20261008`; source patch helper: `output/deployment/reader-final-20261008/release.py`.

### 2026-10-08 — Overview role correction
- Deployed `spot-app:20261008-overview`; backup `/opt/spot/deploy/backup-overview-20261008`.
- Removed the client overwrite that renamed the store to its leading sales age. Regional summary now uses sourced facilities and explicitly dated Local headlines, not demographics or nationwide examples. Sparse place data remains a concise location description, without inventing a neighborhood type.
- KEY INSIGHTS reads up to three distinct generated interpretations with their underlying sources, instead of the first card from each Scout. Full interpretation text is readable, without the old two-line clipping.
- Validated: area-summary/PDF editorial 5 Python tests; web experience, workspace and trend-board JS checks; image import and deployed API health. No additional provider/GPT calls. Production visual review unavailable due browser URL policy.

## 2026-10-08 Local place context release

- Deployed image: `spot-app:20261008-local-context` on `spot-server-seoul` (`asia-northeast3-a`).
- Previous image: `spot-app:20261008-overview`; backup: `/opt/spot/deploy/backup-local-context-20261008`.
- Added bounded Kakao nearby-place collection, source links, straight-line distances, Local background section, overview map pins, and place-grounded Area Summary. Existing news remains separate recent-change evidence.
- Local places also pass through brief/synthesis and Trend context. Place search coverage must not be interpreted as facility census, visitor demographics, or measured movement.
- Validation: 53 related Python tests passed; web experience/workspace JavaScript tests passed. Live local checks returned different places for Dongnae, Gwanghwamun and Nambusan.
- Production smoke: API_HEALTH_OK; image import OK; 27 places returned around Gwanghwamun; source-linked Area Summary assertion passed. No GPT calls in this smoke.
- Official-government page collector is implemented, but no official body excerpt was accepted in these samples (production count 0). Do not claim verified official descriptions are already available.
- Browser rendering on the production SPoT page was not verified due browser access policy. Existing saved research does not automatically acquire new source observations; run a new research request.
