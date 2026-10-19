# Scout 통합 실행 — 2026-09-30

## 이번에 확인한 것

최신 main에서 `feat/scout-integration` 브랜치를 만들고 아래 PR head를 병합했다.
Scout 내부 코드는 수정하지 않았다. 기존 Critic 기준표를 가져와 Graph 밖에서 검사했다.

| 구현 | PR / 커밋 |
|---|---|
| 공통 validator / CI | main `8a37fcfbc2651750d44d962c3a61d3017607619f` |
| Local | #5 `5a83b2779ffc50d0ea392e8d0e18bcf7e7d6d0eb` |
| Trend | #6 `e2f68438996582e856267bb6c9462cc1fc016e5c` |
| Quant | #7 `486d8f3e37cf5fec164d502742e855e57a59b905` |
| Critic 기준표 초안 | feat/critic `fbaf4183719eebaf0b3547bcbf93ef8c151ae7eb` |

실행 환경: Linux, Python 3.12.14, LangGraph 1.2.12, pyproj 3.8.0.
추가된 Quant 의존성 pyproj를 constraints에도 고정했다. pip check 통과.

## 입력과 범위

입력: `samples/input/myeongji_international.provisional.json`.
명지국제신도시, 기준일 2026-09-30, 최근 180일(4월 3일부터), 반경 요청 1000m.
지역명만 지정돼 있고 좌표가 없으므로 실제 반경 분석의 중심점이 확정되지 않았다.
실제 대리점의 존재나 주소를 이 입력으로 주장하지 않는다.

## 실제 실행 결과

| 모듈 | 상태 | 인사이트 / 출처 | 해석 |
|---|---|---|---|
| Quant | failed | 0 / 0 | 실제 Quant 함수가 키 없음 오류를 반환. API 조회·수치 검증은 미실행 |
| Local | partial | 2 / 4 | 강서선 트램 승인 계획, 에코델타시티 주택 선정. 생활권 자료이며 명지국제신도시 반경 근거 아님 |
| Trend | success | 10 / 18 | 기존 공개 사례 목록에서 기간으로 선택. 지역·제품 관련성 자동 필터 미구현 |

3월 29일 자율주행 예정 발표는 이번 기간 밖이므로 Local 결과에서 제외됐다.
Local의 partial은 담당자 구현의 최소 3건 기준 때문이다. 통합 계약 오류가 아니다.
Trend가 반환한 패턴은 미션 참여 7건, 직접 체험 6건, 테마 공간 탐색 6건이다.
사례가 여러 패턴에 속하므로 패턴별 건수를 합산해 사례 총수로 해석하지 않는다.
이번 실행에서 공개 자료 원문을 새로 검색하거나 사실을 독립적으로 재검증하지 않았다.

세 결과 모두 validator 통과했고, 실제 Scout 함수들을 호출한 Graph가
Merge → Mock Critic → Mock Research Brief → END까지 도달했다.
Quant 데이터 확보 성공이나 실제 Research Brief 완성을 뜻하지 않는다.

## Critic 기준표를 실제 출력에 적용한 결과

`rule_status=manual_review`, `quality_status=manual_review`.
Quant 실패·빈 근거, Local partial·경고, Trend 경고·게시일 미확인 출처 3건을 표시했다.
공통 계약 오류와 끊어진 출처 참조 등 `needs_fix` 수준의 finding은 없었다.
지역 관련성, 원문과 주장 일치, 상권 간 차이, 행사 목적과 연결은 사람이 확인해야 한다.
이 검사는 Graph의 Mock Critic을 대체하지 않았으며 retry routing을 추가하지 않았다.

## 재실행

저장소 루트에서:

```bash
python -m venv .venv
source .venv/bin/activate
python -m pip install -r requirements.txt -c constraints-test.txt
python -m pip check
python -m unittest discover -s tests -v
python -m src.integration_smoke samples/input/myeongji_international.provisional.json --mode offline --output samples/integration/myeongji-20260930-offline
```

Windows PowerShell에서는 두 번째 줄 대신 `.venv\Scripts\Activate.ps1`을 사용한다.
전체 테스트 41개 통과. 새 통합 테스트 3개는 실제 함수의 합류, 좌표 입력 시
Kakao 생략·SBIZ 키 필요 경로, 미확정 지역명으로 live 실행하지 않는 경로를 검증했다.
offline은 Quant의 dotenv 로딩과 두 키를 비활성화해서 제공자 네트워크 호출을 하지 않는다.
Quant 실패가 정상 형태로 반환돼도 CLI는 종료 코드 0이다. `validation.json`의
module_status를 함께 확인해야 하며, 종료 코드만으로 데이터 수집 성공을 판단하면 안 된다.

## 파일을 어떻게 읽으면 되는지

먼저 [실행 요약](../samples/integration/myeongji-20260930-offline/SUMMARY.md)을 읽는다.
전체 JSON은 프로그램 검증과 다음 단계 연결에 사용한다.
`local_result.json`, `trend_result.json`, `quant_result.json`은 함수의 전체 반환값이며,
`research_bundle.json`은 합친 결과, `critic_rule_preview.json`은 별도 기준표 검사다.
`research_brief_mock.json`은 데이터 기반 브리프가 아닌 기존 Mock 출력이다.

## 다음 실제 조회 준비

1. 명지국제신도시의 정확한 조사 주소 한 곳을 정한다. 좌표도 있으면 Kakao 호출을 생략한다.
2. 공통 입력을 복사해 address / lat / lng를 확정한 값으로 바꾸고 request_id를 새로 지정한다.
3. `.env.example`을 `.env`로 복사하고 `SBIZ365_CERT_KEY`를 설정한다.
   주소 변환이 필요하면 `KAKAO_REST_API_KEY`도 설정한다. 키는 Git에 포함하지 않는다.
4. 아래 명령으로 Quant 실제 조회를 포함한 통합 결과를 저장한다.

```bash
python -m src.integration_smoke path/to/confirmed-request.json --mode live --output samples/integration/myeongji-live
```

live는 Quant 제공자 네트워크 호출을 허용한다. Local·Trend는 여전히 기존 자료 목록을 사용한다.
새 출력은 커밋 전에 query_context와 오류 메시지에 민감한 정보가 없는지 확인한다.
표본 저장 후 실제 데이터 시점·지역 범위·단위를 확인하고, 근거를 읽을 수 있는
Research Brief 초안을 만든다. Scout가 던진 미처리 예외는 현재 Graph 실행을 중단하므로
발생 시 원인을 확인한 뒤 담당 모듈과 최소 수정 범위를 정한다.
