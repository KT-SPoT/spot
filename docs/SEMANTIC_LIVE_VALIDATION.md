# 의미 Critic 실제 모델 연결 검증 — 2026-10-02

모델: `gpt-4.1-mini`. OpenAI Chat Completions에 실제 요청했고 HTTP 200 및
로컬 응답 검증 통과를 확인했다. 사용자 API 키는 로컬 `.env`에만 보관했다.
연결 주소·모델을 설정했으며 자동 의미 평가는 아직 off다.

## 입력과 결과

`samples/critic/semantic_cases.synthetic.json`의 9개 가상 주장과 근거를
하나의 요청으로 묶어 평가했다. 실제 상권 자료가 아니라 명시적 합성 예제다.

| 실행 | 모델 요청 수 | verdict/action 기대값 일치 | 결과 |
| --- | ---: | ---: | --- |
| 최초 프롬프트 | 1 | 6 / 9 | 자료 부족과 명시적 충돌의 구분 문제 확인 |
| 기준 보완 후 | 1 | 9 / 9 | 전체 주장 응답 및 출처 검증 통과 |

첫 실행의 차이는 다음과 같다.

- 구매 의향 조사 없음: insufficient 대신 contradicted.
- 주거인구를 유동인구로 바꾼 주장: contradicted 대신 insufficient.
- 비교 지역 자료 없음: insufficient 대신 contradicted.

프롬프트에 **증거 부재는 반증이 아니며**, 모집단·진행 단계의 명시적 변경은
충돌이라는 기준을 추가했다. 복합 주장에 명시적 충돌이 있으면 그 충돌을 설명하도록 했다.
합성 기준표의 기대값을 모델 출력에 맞춰 바꾸지는 않았다.

이 결과는 두 번의 소량 API 요청에 대한 기능·예제 검증이다. 반복 안정성, 실제
지역별 정확도나 사실 진위 검증 완료를 의미하지 않는다. 모델 생성 이유까지
자동으로 참이라고 승인하지 않으며 최종 상태는 manual_review로 유지한다.

## 실제 자료 검증 — 사용자 승인 후 1회 실행

저장된 실제 상권/기사 자료를 OpenAI로 보내는 후속 평가는 자동 승인 검토에서
차단됐다. 합성 예제 평가와 별개로 실제 자료 외부 전송에 대한 사용자 승인이 필요하다.
재시도나 우회 전송은 하지 않았다.

외부 호출 없이 로컬에서 전송 예정 입력을 생성했다: 주장 16개, 정량 지표 및
출처 발췌·조회 범위, JSON 32,811 bytes. 키·URL·HTML 원본을 제외하고 입력을
검증했다. 키가 들어갈 수 있는 provider 원본이나 환경 변수는 전송하지 않는다.
해당 미리보기와 전체 모델 응답은 `.venv/verification/semantic-live/`에만 저장하며 Git에 넣지 않는다.

이후 사용자가 미리보기 자료의 OpenAI 전송 및 1회 평가를 명시적으로 승인했다.
승인 파일과 실제 생성 입력이 정확히 같은지 확인한 뒤 한 번 호출했다.
새 Scout 조회는 없었고 source_count=17인 기존 Brief는 변경 없이 유지됐다.

결과: `performed=false`, `code=INVALID_SOURCE_REFERENCE`.
AI 응답의 출처 연결 검증에 실패해 판정을 채택하지 않았다. 모델 응답 전체를
보관하지 않았으므로 어떤 인용이 실패했는지, 실패 원인을 단정하지 않는다.

입력 점검에서는 Quant 4개 주장에 metric_refs가 있지만 직접 source_ids가 없어
해당 주장 evidence가 비어 있는 연결 결함을 확인했다. 검증된 Brief 정량 카드의
metric_refs → 같은 Quant source registry로만 연결하도록 보완했다. 자료의 기간과
모집단을 보존하고, 매칭되지 않는 지표는 unverified_metric_refs로 표시한다.
관련 없는 수치나 다른 모듈의 출처를 빌리지 않는다.

보완은 로컬 자동 테스트와 저장 자료 입력 재생으로 확인한다. 승인된 1회 호출을
소비했으므로 수정 입력으로 추가 모델 호출은 하지 않았다. 자동 평가도 off로 유지했다.
실제 자료의 모델 판정 채택 및 정확도 검토는 아직 완료되지 않았다.

## 수정 입력 재평가와 조치 정책 보완

사용자의 다음 단계 요청으로 수정 입력(Quant 출처 연결 포함)을 실제 모델에
1회 재전송했다. 주장은 16개였으며 새 Scout 조회는 없었다. 이번 응답은
키 값 검사 후 로컬에 기록했고, 출처·주장 연결 오류는 발견되지 않았다.

초기 검증 결과는 INVALID_RESPONSE였다. 정확한 원인은 8개 insufficient 판정에
모델이 qualify 조치를 제안한 것이다. 모델 판정과 코드의 조치 대응표가 맞지 않았다.

알려진 모델 조치를 정책에 맞춰 적용하도록 보완했다. verdict와 reason은 유지한다.
insufficient는 manual_check, contradicted는 qualify, supported는 keep으로 적용하며
모델 제안과 적용 값을 action_normalizations에 기록한다. 알 수 없는 조치,
잘못된 출처, 없는 주장, 누락·중복 응답은 여전히 거부한다.

추가 API 호출 없이 기록된 실제 응답을 Graph에 재생한 결과:

- performed=true, code=EVALUATED, claim_count=16.
- supported 8개, insufficient 8개. 모델의 판정을 바꾸지 않았다.
- 조치 정책 적용 내역 8개. 최종 상태 manual_review, truth_verified=false.
- 기존 Brief 동일, source_count=17. 재생 시 모델/Scout 외부 호출 0회.
- 자동 테스트 134개, n8n 연결 구조 검증, 키 유출 검사 통과.

이는 실제 응답의 형식·출처 연결 및 정책 적용이 통과했다는 결과다.
모든 주장의 사실 진위, 타 지역 품질, 반복 안정성 검증 완료를 의미하지 않는다.
전체 응답·조치 적용 기록·읽기용 결과는 `.venv/verification/semantic-live-replay-v2-accepted/`에만
저장하며 Git에 넣지 않는다. 서버의 자동 의미 평가는 off를 유지했다.
