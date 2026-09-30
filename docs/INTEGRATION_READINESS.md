# Scout 통합 준비 및 인수 체크리스트

## 현재 검증 범위

- Python 3.12.14 / Linux에서 검증. `constraints-test.txt`는 테스트 환경의 전체 의존성 스냅샷입니다.
- `requirements.txt`의 공통 의존성 범위는 유지합니다. Scout 패키지 추가 시 constraints 호환성을 다시 검증하세요.
- Windows 활성화 명령은 README에 있으나 Windows 실행 자체는 아직 검증하지 않았습니다.
- `test_graph_smoke.py`: graph가 참조하는 Scout 함수를 고정 mock으로 교체하여 외부 API 없이 E2E 실행.
- `test_graph_integration.py`: 합성 success/partial/failed 출력 보존, fan-in 순서, 예외 전파 검증.
- `test_validation.py`: 모든 모듈·상태, 필수 필드 누락, 자료형 오류, 잘못된 값, 요청 ID 불일치 검사.
- 테스트 안에서 만드는 합성 결과는 실제 조사 근거가 아닙니다. success 상태여도 품질 검증을 의미하지 않습니다.

## Local PR #5 인수 기록 — 2026-09-30

- 대상: `SRIMP-MAN/spot`의 `5a83b2779ffc50d0ea392e8d0e18bcf7e7d6d0eb`.
- 이번 공통 변경은 최신 main `105ea18`에서 만든 `feat/integrator`에 적용합니다.
- `samples/contracts/local_pr5.cases.json`은 위 Local 코드의 실제 고정 근거 PoC 출력 5개를 캡처한 파일입니다. 합성 테스트 결과와 구분합니다. 자동 검색이나 원문 사실 검증을 새로 수행하지 않았습니다.
- `tests/test_contract_samples.py`는 캡처 파일만 읽어 envelope·module·request_id·상태·배열 수를 검사합니다. Scout 함수를 호출하지 않습니다.

| 입력 | 상태 | insights | sources |
| --- | --- | --- | --- |
| 명지, 2026-09-22 / 180일 | success | 3 | 5 |
| 명지, 2026-09-22 / 30일 | partial | 0 | 0 |
| 명지, 2026-03-29 / 0일 | partial | 1 | 1 |
| 해운대 미지원 지역 | partial | 0 | 0 |
| 명지, 2026-09-30 / 180일 | partial | 2 | 4 |

검증: 공통 브랜치 테스트 12개, Local PR 코드와 공통 기반을 결합한 환경 테스트 19개 통과. Local 7개 테스트는 출력 단계·요약·provenance·중복 처리를 확인합니다. 실제 Local을 사용하고 Quant/Trend를 mock으로 둔 graph도 Mock Brief까지 도달하는지 별도로 검증합니다.

검증 범위는 기술적 호환성입니다. 반경 필터·자동 검색·다지역 지원·원문 품질 최종 승인은 이 PR 범위 밖입니다. Local PR 자체의 main 병합은 공통 기반 병합 후 별도 인수 단계입니다.

최신 main 기반 검사와 격리 PR 재검사:

```bash
python -m unittest discover -s tests -v
git fetch origin refs/pull/5/head
git worktree add --detach ../spot-local-check FETCH_HEAD
git -C ../spot-local-check fetch origin main
git -C ../spot-local-check merge FETCH_HEAD --no-edit
cd ../spot-local-check
python -m pip install -r requirements.txt -c constraints-test.txt
python -m unittest discover -s tests -v
```

기존 가상환경을 사용하거나 격리 작업 디렉터리에서 새 가상환경을 활성화하세요. 위 merge는 격리된 로컬 checkout에만 적용하며 원격 PR 브랜치를 변경하지 않습니다. 고정 샘플은 승인한 Scout 변경에서 다시 캡처해야 하며 runtime 결과와 자동 동기화되지 않습니다.

## 개별 출력 파일 검사

가상환경 활성화 후 저장소 루트에서 실제 출력 파일을 지정하세요.

```bash
python -m src.validation path/to/scout_result.json --module quant --request-id spot-example-001
```

- 정상: `valid: true`, 종료 코드 0. 계약 오류: 필드별 errors, 종료 코드 1.
- 파일 읽기/JSON 문법 오류: 종료 코드 2.
- 기존 `src/contracts.py`와 공통 envelope를 기준으로 검사하며 입력을 변경하거나 자동 보정하지 않습니다.
- metrics/patterns 등 확장 필드는 허용합니다. started_at/finished_at의 null도 기존 scaffold대로 허용합니다.
- sources/insights의 각 항목은 object인지 검사합니다. 상세 출처 필수화, 날짜 파싱·최신성, 근거 수·품질은 아직 검사하지 않습니다.
- 이 검사는 독립 인수 도구입니다. graph 실행 중 자동 적용하지 않으며, 불합격 결과는 통합 전에 담당자에게 반환합니다.
- 추가 필드 강제나 null 정책 변경은 공통 계약 합의 후 반영합니다.

## 현재 동작과 미정 정책

| 상황 | 현재 skeleton 동작 | 다음 결정 |
| --- | --- | --- |
| partial / failed 결과 반환 | Merge에 상태 그대로 보존, mock Critic와 Brief 실행 | 실제 Critic의 진행/재탐색/수동 확인 조건 |
| Scout 미처리 예외 | invoke 실패, Merge·Brief 실행 안 됨 | 예외를 failed로 바꿀 범위·중단 정책 |
| 결과 상태 필드 누락 | Merge에서 failed 기본값 사용 | validator로 인수 거절; 런타임 처리 정책 별도 |
| mock Critic | 항상 manual_review | 실제 결과 기반 판정 기준 |
| mock Brief | request_id만 받아 고정 mock 생성 | bundle 및 Critic 결과 전달 구조 |

예외 테스트는 현재 동작의 기록이지 최종 운영 정책 승인이 아닙니다. retry routing은 구현하지 않았습니다.

## Scout PR 제출 체크리스트

- [ ] 사용한 SpotRequest JSON과 대응하는 ScoutResult JSON 첨부 (비밀정보·개인정보 제거)
- [ ] 실제 데이터 / mock / 합성 테스트 데이터 구분
- [ ] 실행 명령, Python 버전, 추가 패키지 및 환경변수 이름만 기재 (키 값 제외)
- [ ] validator 통과 결과 및 테스트 명령 기재
- [ ] 검색 결과 없음 / API 오류 / 인증 실패·한도 초과 시 동작 설명
- [ ] source URL, 공개일·수집일 등 확보한 메타데이터 보존; 미확보 항목과 이유 명시
- [ ] 알려진 제약, 소요 시간과 호출 수·비용 기록 (측정하지 않았다면 미측정 표시)
- [ ] Scout import만으로 외부 호출하지 않기: 테스트는 함수 호출을 mock으로 대체합니다.
- [ ] 공유 필드 변경이 필요하면 구현에 앞서 계약 변경 제안 Issue 작성

## Integrator 인수 순서

1. PR diff에서 담당 Scout 밖의 변경과 공통 계약 영향을 확인합니다.
2. 제출 JSON을 validator로 검사하고 sources/날짜/실제 데이터 여부를 사람이 검토합니다.
3. 추가 패키지를 포함한 새 환경에서 offline 테스트를 실행합니다.
4. 준비된 Scout 하나만 통합하고 나머지는 mock으로 유지하여 데이터 보존을 확인합니다.
5. 실제 API 호출은 키·호출 비용을 확인한 뒤 별도 수동 검증합니다. CI에 실서비스 키를 넣지 않습니다.
6. 실제 결과가 쌓이면 Critic 기준, 예외 처리, retry 상한, Brief 입력 구조를 확정합니다.

## CI

`.github/workflows/tests.yml`은 main/feat 브랜치 push 및 PR에서 의존성 설치·pip check·offline 테스트를 수행합니다.
패키지 설치는 네트워크가 필요하지만 테스트 자체에는 API 키나 리서치 서비스 호출이 필요하지 않습니다.
실제 Scout 호출 테스트와 근거 품질 평가는 이 CI에 포함되지 않습니다.
GitHub Actions 실행 결과와 브랜치 보호의 필수 체크 지정은 별도로 확인해야 합니다.
