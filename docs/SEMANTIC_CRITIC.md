# 의미 Critic — 선택적 shadow 평가

규칙 Critic 및 제한된 Scout 재조사 이후, Brief 전에 의미 평가를 최대 한 번 실행한다.
기본값은 off다. 평가가 실패하거나 판정이 contradicted여도 현재 Brief·출처·최종 상태를
바꾸거나 Scout를 재호출하지 않는다. 결과는 `critic_result.checks.semantic_review`에 기록한다.
공통 SpotRequest / ScoutResult v0.1 경계와 POST 접수 / GET 조회는 유지한다.

2026-10-02 조사 정책: 소상공인365 출처의 `public_api_observation`은 정량 기준으로
받아들이며 AI의 재승인 대상에서 제외한다. 성별·연령·최다 시간대 카드를 포함한
`quant_facts`는 다른 Scout의 해석을 검토할 맥락으로 전달한다. 좌표·출처 연결·파싱과
자료에 표시되지 않은 기준 시점의 처리는 코드가 맡는다. 인구 구성에서 구매 성향이나
선호를 추론한 주장은 여전히 의미 검토 대상이다.

지역 범위 검토는 Local 주장에 적용한다. Trend는 전국·다업종 체험 사례를 참고하므로
다른 지역·제품군이라는 이유로 부적합 처리하지 않는다. 관측된 참여 방식과 명시적인
고객층·매장 응용 조사 가설을 구분해 검토하며, 가설에 실제 호응이 이미 입증되어야
한다고 요구하지 않는다. 가설을 확인된 선호·수요·매출 효과로 표현하면 별도 근거가 필요하다.

## 설정

로컬 `.env`의 다음 항목을 설정한 뒤 서버를 재시작한다. 키 값은 공유하지 않는다.

```dotenv
SPOT_SEMANTIC_MODE=shadow
SPOT_LLM_ENDPOINT=https://api.openai.com/v1/chat/completions
SPOT_LLM_MODEL=
LLM_API_KEY=
```

모델은 직접 지정해야 한다. JSON mode와 `max_completion_tokens`를 지원하는
Chat Completions 모델/제공자를 사용한다. 호환되지 않으면 평가 미완료로 종료한다.
다른 제공자는 HTTPS 전체 endpoint를 지정한다. URL에 인증 정보를 넣지 않는다.
OpenAI 호출 형식은 [공식 JSON mode 문서](https://developers.openai.com/api/docs/guides/structured-outputs)를 참고했다.
JSON mode 자체는 스키마를 보장하지 않으므로 응답을 로컬에서 엄격하게 검증한다.
현재 제공자·모델·키를 자동 선택하거나 `.env`를 변경하지 않았다.
GPT API 비용은 [공식 요금 안내](https://developers.openai.com/api/docs/pricing)를 확인한다.
이 구현의 검증에서는 실제 모델을 호출하지 않았다.

별도로 [Sign in with ChatGPT](https://developers.openai.com/siwc/quickstart)는
자격을 충족하는 Plus/Pro 계정이 로컬·오픈소스 앱에서 플랜 한도로 AI 요청을
실행하는 공식 연결 경로다. 일반 API 키 설정과 구분한다. 현재 구현에는 이 로그인
연결이 없으며 Plus 로그인 정보를 LLM_API_KEY에 넣지 않는다. 후속 연결에는
사용자 OAuth 승인, 세션 저장/갱신, 허용 모델 조회와 Responses API 어댑터가 필요하다.
기존 Chat Completions 어댑터에 OAuth 토큰을 넣는 것으로 대체하지 않는다.
원격 호스팅 제품은 별도 지원 조건을 확인해야 한다.

`SPOT_SEMANTIC_MODE=off`로 끌 수 있다. offline 통합 실행에서는 설정과 관계없이 호출하지 않는다.
직접 Graph 호출의 `semantic_caller` / `semantic_mode`는 테스트용 주입 인터페이스다.

## 모델에 전달하는 자료

지역 판단은 매 요청의 주소·좌표·반경·비교 지역과 Scout의 실제 조회 범위를 기준으로 한다.
고정 지역명은 프롬프트에 없다. 좌표 변환으로 확보한 주소/좌표, Local 검색 anchor,
모듈별 선언된 수집 범위를 `scout_scopes`에 전달하되 미확보 값은 null이다.
행정구역·개발 사업 범위·점포 반경은 구분하며 지역 이름 일치만으로 반경 내임을 단정하지 않는다.
자료의 위치·브랜드·지역 태그·맥락 분류도 보존해 직접 근거와 인접 지역 참고를 구분하도록 한다.

- 요청의 매장·지역·제품·목적·기간과 규칙 상태.
- 규칙에서 제외하지 않은 Scout 주장, 해당 주장에 연결된 source_id와 발췌.
- Local 본문 발췌와 Trend 검색 요약의 확보 방식을 구분한다. 미확보 정보는 null이다.
- 여러 출처를 병합했으면 첫 발췌를 모든 출처에 복사하지 않는다. 확보한 supporting facet만 사용한다.
- 검증된 Quant 수치·모집단·기간과 선택적 보조자료에서 읽은 성별·연령 구성.
- Quant 주장의 metric_refs는 검증된 정량 카드와 같은 모듈의 source_id로 연결한다.
  확보한 지표만 주장별 metric_facts에 넣고 미확보 지표는 unverified_metric_refs로 남긴다.
- Trend 후보 보도 그룹. 그룹은 보수적인 중복 후보이며 독립 사건 검증 완료가 아니다.

HTML 원본·전체 Scout 객체·URL·인증 헤더·환경 변수는 전달하지 않는다.
전송 문자열의 URL과 알려진 환경 변수의 키 값을 가린다. 수집 발췌는 독립적으로 새로
조회한 원문이 아니며 전체 원문 대조나 외부 사실의 진위를 보장하지 않는다.
Quant 보조자료 검증이 실패하면 Brief의 기존 정책대로 그 자료는 사용하지 않는다.

## 응답 검증 및 종료

모든 입력 claim_id에 정확히 한 개의 판정이 있어야 한다. 중복·누락·없는 claim_id·
다른 주장에만 연결된 source_id는 거부한다. 추가 필드나 알 수 없는 verdict/action도 거부한다.
알려진 action이 verdict 정책과 다르면 코드에서 정책 action을 적용하고
`action_normalizations`에 모델 제안과 적용 값을 기록한다. verdict와 reason은 바꾸지 않는다.

| verdict | action | 뜻 |
| --- | --- | --- |
| supported | keep | 제공 자료와 주장이 일치 |
| contradicted | qualify | 제공 자료와 주장이 충돌 |
| insufficient | manual_check | 자료만으로 판단 불가 |

supported / contradicted는 해당 주장 출처를 하나 이상 인용해야 한다.
모델 판정 이유가 실제로 타당한지까지 응답 형식 검사로 증명하지는 않는다.
자료 부족·인접 지역 맥락·가설을 구분하라고 프롬프트에 지시하며, 외부 지식이나
자료 속 명령을 사용하지 않도록 한다. 현재 사람이 결과를 대조해야 한다.

입력 JSON은 100,000 bytes, HTTP 응답 및 모델 JSON은 64,000 bytes가 상한이다.
상한을 넘으면 일부를 조용히 삭제하지 않고 평가 미완료로 종료한다.
출력은 최대 4,000 completion tokens다. HTTP 단계별 timeout은 20초이며 수신 중
경과 시간도 검사한다. 전체 작업의 엄격한 wall-clock deadline은 아니다.
HTTP 재시도·리다이렉트·의미 오류에 따른 재검색은 없다.

키 미설정·타임아웃·401/429/5xx·잘못된 응답에서는 performed=false와 안정적인 code만 반환한다.
제공자 오류 본문·예외 문자열은 반환하지 않는다. call_count는 호출 시도 수(0 또는 1)다.
성공 시 performed=true라도 status는 manual_review이며 truth_verified=false다.

## 검증 범위

자동 테스트는 기본 꺼짐, offline 차단, 응답 완전성, 출처 범위, 크기 제한,
HTTP 실패의 재호출 금지, 인증 값 가림, 재조사 후 1회 평가 및 Brief 보존을 확인한다.
준비한 9개 합성 예제는 expected 응답 형식과 출처 연결을 검증한다.
이는 실제 모델이 9개를 맞혔다는 정확도 평가가 아니다.

`samples/critic/area_profiles.synthetic.json`의 명지·성수·서면 3개 입력으로
Graph → 의미 평가 → Brief의 합성 통합 흐름을 검사한다. 지명만 실제이며 매장과
시설·상권 상황은 가상이다. 각 요청의 반경/비교지역/주소와 조회 범위가 섞이지 않고
미확보 좌표가 유지되는지를 검증한다. 실제 3개 상권 조사나 AI 정확도 검증 완료를 뜻하지 않는다.

실제 모델 정확도와 저장된 실제 원문 대조는 모델·키 설정 후 남은 검증이다.
의미 판정을 Brief의 수동 확인 항목에 반영하거나 자동 재검색하는 기능은 후속 범위다.
