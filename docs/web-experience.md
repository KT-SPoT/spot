# 매장 홍보 근거를 찾는 SPoT 리서치

## 사용 흐름

1. `http://127.0.0.1:8768/`에서 지역 리서치를 시작한다.
2. 홍보할 제품·서비스 또는 제품군을 입력하고, 특히 알아보고 싶은 점은 선택적으로 적는다. 비워두면 기본 홍보 근거 탐색으로 접수하며 API의 기존 purpose 필드는 유지한다.
3. 매장명 또는 매장 주소를 검색한다. 검색 결과를 선택하면 주소와 좌표가 함께 입력되고 지도는 위치를 보여준다. 후보지 생성·추천·비교는 제공하지 않는다.
4. Quant·Local 병렬 조사 → Trend → 통합 → Critic → Brief 순서의 실제 작업 상태를 확인한다.
5. 결과의 AREA SUMMARY, KEY INSIGHTS와 Scout 상세 화면을 읽고, 근거 버튼이나 출처 분류 탭에서 원문을 연다.

## 구현 경계

- `KAKAO_REST_API_KEY`는 웹 서버에서만 사용한다. 지도는 로컬에 포함한 Leaflet 1.9.4와 OpenStreetMap 타일을 사용하므로 별도 카카오 JavaScript 키는 필요 없다. 검색/주소 공급자와 지도 저작자 표시를 유지한다.
- Kakao 호출은 고정된 HTTPS 목적지로만 전송하며 세션당 분당 30회로 제한한다. n8n 인증 헤더를 카카오에 전달하지 않는다. 기존 SpotRequest / ScoutResult v0.1 필수 필드는 변경하지 않는다.
- 작업 조회 응답에는 선택적 `progress: {stages, updated_at}`가 추가된다. stages는 실제 graph node의 `running`, `success`, `partial`, `failed`, `completed` 상태만 전달한다. 토큰·원문·예상 퍼센트는 포함하지 않는다. 기존 커스텀 runner도 계속 사용할 수 있다.
- AREA SUMMARY와 KEY INSIGHTS는 기존 Brief의 관측값·직접 지역 변화·전국 참고 사례에서 추출한다. 추가 GPT 호출 없이 표시하며, 배경 자료를 직접 변화로 승격하지 않는다. 숫자나 성과를 생성하지 않는다.
- Quant는 [그래프와 수치 표](QUANT_CHARTS.md)로 모집단별 성별·연령·요일·시간대를 표시한다. 같은 실행에 확보된 비율만 사용하며 과거 작업의 미확보 항목을 새로 채우지 않는다.
- Local 기사 이미지는 기존 원문 수집에서 확인한 `og:image`만 사용한다. URL은 공개 목적지 검사 후 사용하며 없거나 로드되지 않으면 텍스트 목록을 표시한다. 과거 결과에는 이미지가 없을 수 있다. 사진과 타일은 외부 네트워크가 필요하다.
- 출처는 메타데이터/URL에 따라 뉴스·공공데이터·보고서·기타로 분류한다. 자동 분류는 발행 기관의 공식 분류를 뜻하지 않는다.
- 명륜동처럼 같은 이름이 여러 도시에 있는 경우 검색에 요청 도시를 포함하며, 다른 광역시 제목과 요청 도시 부재가 함께 확인된 원문은 제외한다. 완전한 지리 경계 검증을 대신하지는 않는다.
- 작업/브라우저 소유권은 여전히 메모리 기반이며 서버 재시작 시 이전 작업 조회는 만료된다.

## 인사이트 대시보드 — 2026-10-03

- 승인한 시안의 네이비 탐색 메뉴와 블루·틸·앰버·바이올렛 팔레트를 적용했다.
  결과 개요는 AREA SUMMARY + 요청 위치 지도 → 주요 관측값 → 고객 분포와
  KEY INSIGHTS → Local·Trend 미리보기 순서로 구성한다.
- 지도는 요청 좌표와 반경을 표시한다. 소상공인 자료의 집계 영역과 요청
  원형 반경이 같다고 주장하지 않는다. 좌표가 없으면 주소와 안내만 표시한다.
- Key Insight와 카드의 근거 버튼은 기존 출처 창으로 연결된다. 모집단 선택은
  같은 브리프의 제공 비율만 바꾸며 추가 Scout/GPT 호출은 없다.
- Local·Trend는 확인된 원문 `verification.thumbnail_url`이 있을 때 이미지를
  표시하고, 없거나 로드가 실패하면 텍스트 또는 체험 패턴 표지로 표시한다.
  시안의 예시 수치·사진·지도·행사 문구를 실제 조사 결과로 사용하지 않는다.
- 완료 후 실행 단계의 큰 영역은 숨기고 결과를 먼저 보여준다. 진행 중 상태와
  Quant 실패 원인·미확보 항목·각 표의 기준 시점·출처 확인은 유지한다.

### 디자인 자산

- 서울 한강 사진: [Inkwon hwang / Unsplash](https://unsplash.com/photos/a-city-skyline-with-a-river-E3vnaw9q3Pg), Unsplash License. 메인 화면의 분위기 사진이며 조사 대상지의 사진으로 사용하지 않는다.
- 지도: [OpenStreetMap](https://www.openstreetmap.org/copyright), [타일 사용 정책](https://operations.osmfoundation.org/policies/tiles/). 지도 타일에 origin Referer를 전달하고 사전 다운로드하지 않는다.
- Leaflet: `src/web/static/LEAFLET-LICENSE.txt`에 BSD-2-Clause 라이선스를 포함한다.

## 검증

Python unittest 전체, `tests/test_web_brief.js`, `tests/test_web_workspace.js`, `tests/test_web_experience.js`와 n8n workflow 테스트를 실행한다. 매장·주소 검색은 mock transport로 인증 경계/입력/오류를 검사하고, 실제 동래점 검색 및 한 차례 실조사로 주소 자동 입력과 Quant 자료 확보를 확인했다. 삭제한 후보지 역지오코딩 경로는 404이며 공급자를 호출하지 않는다.
