# SPoT 분석 에이전트 전환 — 다음 모델 구현 작업서

작성: 2026-10-08. 상태: **설계·인수인계만 완료, 아래 변경은 아직 구현하지 않음**.
이 문서는 이번 대화에서 사용자가 승인한 방향을 구현에 전달한다. 과거 문서의 참신함 심사·검토 질문 중심 설계보다 이 최신 요구를 우선한다. Notion 동기화는 아직 하지 않았다.

## 1. 사용자가 원하는 결과

“데이터라는 재료를 제공하면 AI가 체계적인 분석으로 요리한다.”
자료 목록, 최대 비율 재진술, “설명하기 어렵다/검토해야 한다”만으로 끝나는 결과는 실패다.
출력의 흐름은 **지역의 생활·방문 맥락 → 관측된 패턴 → 통합 해석 → 홍보 기회**다.
- Quant: 인구·매출·시간 분포를 해석의 재료로 제공. 매출액 구성과 사람 수를 혼동하지 않는다.
- Local: 실제 시설·장소의 역할, 주변 환경, 최근 변화를 제공. 기사만으로 지역을 규정하지 않는다.
- Trend: 전국·타 업종 사례의 참여 방식을 지역 기회에 연결. 같은 연령 단어의 일치는 연결 이유가 아니다.
- 통합 분석기: 관측을 묶어 지역을 설명하고 기회를 도출. 독자가 다시 분석할 일을 떠넘기지 않는다.
- Critic: **지역 정보 혼입·공간 범위 혼동만 교정**. 참신함/차별성/일반성/기획 질문의 선명함/외부 성공 실적을 채택 기준으로 사용하지 않는다.

사용자가 좋다고 한 방향(설명용 가상 예시, 실제 광화문 결과로 복사 금지):
“업무·문화시설과 시간대 소비 패턴을 함께 읽어, 기존 일상 동선에 짧게 참여할 이유를 더하는 홍보 기회를 설명한다.”
지역 맥락은 시설명을 끼워 넣는 것이 아니라, 입력에 나온 시설의 역할과 공간 구성이 왜 그 해석에 연결되는지 설명하는 것이다.
장소 목록과 소비 시간만으로 실제 체류시간을 측정했다고 단정하지 않는다. ‘짧은 참여가 적합한 접근’이라는 제안과 ‘실제 방문객은 오래 머물지 않는다’는 사실 주장은 다르다.

## 2. 유지할 경계

- 분석적 해석과 기획 제안은 적극적으로 허용한다. 모든 문장에 유보 문구를 붙이지 않는다.
- 관측하지 않은 수치·장소·설문·반응·성과를 사실로 만들지 않는다. 이는 새로운 LLM Critic 심사 항목이 아니라 생성 원칙과 데이터 무결성 검사다.
- 출처 ID/숫자/기간/모집단/링크 검증, 스키마 검증, 보안 및 실패 처리는 유지한다.
- 일반적인 통찰도 정상 결과다. 지역 간 결과를 억지로 다르게 만들지 않는다.
- 전국 사례는 전국 참고임을 유지. 해당 매장에서 일어난 행사나 확인된 현지 선호처럼 쓰지 않는다.
- 확정 행사안·상품·예산·직원 수는 만들지 않는다. 흥부장 기획 단서의 상품/직원 수 빈칸 유지.
- 공개 보고서에 ‘근거 미확보/자료 미확보’를 채우지 않는다. 내부 진단은 유지하며 자료가 있는 척하지 않는다.
- 입력 필드 복원, 출점 추천, Instagram, 새 데이터 공급자, n8n 재설계는 이번 범위가 아니다.

## 3. 확인된 현재 코드와 병목

현재 브랜치: `codex/planning-prompt-handoff`. 많은 미커밋 변경과 untracked 구현 파일이 실제 작업본이다. reset/checkout/clean 금지. 먼저 git status 확인.

| 위치 | 현재 동작 / 수정 포인트 |
| --- | --- |
| src/brief/pipeline.py | 운영 connections 모드에서 run_synthesis → run_connection_synthesis를 사용. 새 병렬 파이프라인을 또 만들지 말고 기존 흐름 개선 |
| src/graph/graph.py semantic_node | synthesis 활성 시 기존 semantic review는 DEFERRED_TO_BRIEF_SYNTHESIS. research_review.py만 바꾸면 운영에는 적용 안 됨 |
| src/brief/synthesis.py SYNTHESIS_PROMPT | 방문 이유·행동 해석을 폭넓게 금지하고 planning_question 중심으로 유도. 적극적인 지역 해석/기회 도출로 전환 |
| candidate_schema / validate_candidates | 모델 스키마 evidence_ids 최대2, 코드 검증 최대5로 불일치. 실제 다중 관측 종합이 가능하도록 일치시키기 |
| build_synthesis_input | observations/experience_actions/relationship_notes. 수치쌍 중심이며 지역 정체성 입력은 별도 명확하지 않음. 매장 위치·조사 반경·범위와 장소 역할을 전달해야 지역 혼입 심사가 가능 |
| REVIEW_PROMPT / REVIEW_SCHEMA / validate_reviews / run_synthesis / apply_synthesis | grounding/overclaim 채택 게이트, specificity/question별 분류, experience link coherent 게이트 존재. 지역 범위 Critic으로 일관되게 변경하고 숨은 게이트도 제거/교체 |
| src/brief/connection_synthesis.py | REVIEW_PROMPT 재사용 및 별도 연결 리뷰, contextual/clear 추가 포인트 조건. 생성/검증/적용 모두 새 정책과 일치시키기 |
| src/critic/research_review.py / semantic.py | 비connections 경로의 specificity/differentiation 심사도 남음. 운영 경로와 정책이 달라지지 않도록 호환 처리 |
| src/brief/area_summary.py | 현재 장소 나열 기반 fallback. 분석된 지역 개요 우선, 생성 실패·이전 결과에만 fallback |
| src/web/static/experience.js regionalSummary | 프런트가 지역 개요를 다시 장소 목록으로 생성함. 백엔드 새 분석이 있어도 덮이는 문제 반드시 해결 |
| src/brief/generator.py / renderer.py / pdf.py / pdf_editorial.py / planning_prompt.py | 동일한 분석 결과를 웹·PDF·기획 단서로 연결. 각 출력에서 따로 모델 호출하지 않기 |
| src/brief/publication.py | 진단 문구 제거용. 의미 없는 분석을 문자열 삭제만으로 해결하지 않기 |

Local 장소 확장은 이미 배포됨: local_places.py, 장소 지도 핀/거리/링크, 공식 페이지 collector. 세 지역 실조회 확인. 공식 소개 본문 채택은 표본에서 0건이므로 이미 풍부한 지역 설명이 확보됐다고 가정하지 않는다.

## 4. 구현 순서 (작은 변경 묶음으로)

### A. 입력과 출력 설계
- 기존 저장 brief/bundle 재사용. 이전 GPT 문장은 관측으로 재사용하지 않는다.
- 통합 입력에 지역 식별(시·구·동/매장/좌표/반경), 관측의 공간 범위, 시점, 인구/매출의 집계대상, Local 장소 및 역할, 뉴스의 시점·단계, Trend 실제 참여 행동을 전달.
- 불필요한 연락처·인증값은 전달하지 않는다. 장소명·행정구역 등 분석에 필요한 공개 지명까지 지워버리지 않는다.
- 분석 초안 내부 구조 권장: 지역 설명(area_reading), 핵심 해석 1~3개(title/interpretation/opportunity/evidence_ids), 전국 참고 연결(action_id/relevance).
- ‘관측→해석→기회’를 모델이 명시적으로 작성하도록 하되 장황한 사고과정 출력은 요구하지 않는다.
- evidence_ids는 2개 초과 조합 허용, 필요한 출처만 붙인다. 하나의 근거로 유용한 해석도 허용.
- 가능하면 기존 overview.area_summary / research_implications에 호환 매핑. 공용 계약 필드 변경이 필요하면 AGENTS의 Issue/계약 절차 준수. 임의로 공개 필드 이름 바꾸지 않기.

### B. 지역 범위 Critic
권장 내부 판정: 지역 일치 / 명확한 혼입 / 범위 표현 교정. 확인할 수 없다는 이유만으로 분석 전체 폐기 금지.
- 다른 도시의 동명 장소·기사·통계가 해당 지역 근거로 쓰였는가?
- 시·구 전체 사업이나 반경 밖 시설을 매장 바로 앞의 상황처럼 썼는가?
- 전국 Trend 행사·참여자를 현지 행사·고객 반응으로 바꿨는가?
- 반경 밖 자료도 광역 맥락으로 명시하면 허용. 무조건 반경 밖=삭제가 아니다.
- 교정은 해당 주장/출처 연결만 대상으로 한다. 한 항목 문제로 전체 브리프를 비우지 않는다.
- 새 지리 검증 근거가 없는 상황에서 모델의 기억만으로 다른 지역이라고 단정하지 않는다.
- 생성→지역 검사→필요한 부분만 교정. 반복 생성 루프 금지; 교정 최대1회, 호출 수 기록.
- 참신함 점수·generic 탈락·coherent 선호심사 등 구정책을 다른 이름으로 되살리지 않는다.

### C. 출력 연결
- Area Summary: 지역이 어떤 곳인지와 그 지역을 이해하는 핵심 해석. 시설 목록이나 주요 매출 연령만으로 대체 금지.
- Key Insights: 결론과 홍보 기회가 보이는 1~3개. 내용이 없는데 3개를 강제하지 않는다.
- Trend: 실제 참여 방식 → 분석된 지역 기회와의 연결. 기사 요약만 복사하지 않는다.
- 웹/PDF/기획 단서는 하나의 분석 결과 사용. 원문/수치/근거 펼쳐보기 유지.
- 기존 저장 결과/LLM 장애는 기존 정보 화면으로 정상 표시. 생성에 실패한 것을 분석 완료로 표시하지 않는다.

## 5. 최소 검증 계획

프롬프트 변경만 하고 종료하지 말 것. 다음 행동 테스트를 우선한다.
1. 유용하지만 일반적인 분석이 채택된다. novelty/generic가 차단하지 않는다.
2. 다른 도시 동명 지명 혼입은 지적하고 해당 연결만 제외/교정한다.
3. 전국 팝업을 외부 참고로 연결하면 통과한다. 현지 고객 반응으로 바꾸면 범위 교정한다.
4. 광역 사업을 광역이라고 설명하면 허용, 매장 반경 안으로 둔갑시키면 교정한다.
5. 수치 나열이 아닌 다중 근거 해석이 화면·PDF에 그대로 전달된다. JS fallback이 덮지 않는다.
6. 출처 ID 오류/변조된 관측/잘못된 수치/LLM timeout은 기존 무결성 처리 유지.
7. 이전 brief 호환 및 호출 수 제한.

관련 테스트: test_regional_synthesis.py, test_connection_synthesis.py, test_brief_pipeline.py, test_research_review.py, test_area_summary.py, test_research_brief.py, test_web_experience.js, test_report_exports.py, test_pdf_editorial.py.
기존 ‘해석 단어가 들어가면 무조건 거절’ 기대값은 새 정책의 의도에 맞춰 바꾸되, 출처·숫자 검증 테스트까지 삭제하지 않는다.

재사용 자료(파일의 store/날짜/반경을 실제 확인; 번호만 보고 지역을 추정 금지):
- output/synthesis-baseline-plus/region-{0,1}-input.json, region-{0,1}-brief.json
- output/regional-validation/region-{0,1}.json
- output/local-place-check/region-{0,1,2}.json: 요청과 Local 장소 결과만 있음. 완전한 Quant/Trend 자료가 아님.
자료를 합칠 때 같은 위치·범위인지 확인하고 서로 다른 조사 시점을 보존한다. 없는 지역 자료를 복제하지 않는다.

실제 모델 확인은 기존 자료로 최초 지역당1회, 2~3지역 이내. 새 Scout 수집과 반복 보정은 기본으로 하지 않는다. 결과물은 output/analysis-agent-v2/에 저장하고 호출 수/사용 자료/남은 한계를 기록. 합성 fixture와 실데이터를 구별한다.
평가: 지역명만 바꾼 범용 문장인가, 관측 간 관계를 설명하는가, 사용자가 기획의 방향을 이해할 수 있는가. 억지로 지역 차이를 만드는 시험은 아니다.

## 6. 실행 환경 / 배포

- Python: WSL Ubuntu-24.04 `/opt/spot-venv/bin/python`, repo `/mnt/c/Users/User/Desktop/Spot`. Windows Python은 dotenv/langgraph 없으므로 설치 루프 피하기.
- 예: `wsl -d Ubuntu-24.04 --cd /mnt/c/Users/User/Desktop/Spot /opt/spot-venv/bin/python -m unittest tests.test_regional_synthesis tests.test_connection_synthesis tests.test_brief_pipeline tests.test_area_summary`
- JS: `node tests/test_web_experience.js`.
- 값이 들어 있는 .env/키/토큰 출력 금지. 테스트 증빙에도 인증 헤더·전체 URL 쿼리 노출 금지.
- 현재 운영 이미지: spot-app:20261008-local-context. VM spot-server-seoul, asia-northeast3-a, project-a5cc43f9-95b8-4269-b90, /opt/spot.
- 운영 SPOT_BRIEF_SYNTHESIS=connections, SCOUT_MODE=live, SEMANTIC_MODE=shadow, CRITIC_PROFILE=research (실제 변경 전 상태 확인).
- 배포 참고: docs/HOSTING_SETUP.md, output/deployment/local-context-20261008/release.py. 이전 이미지/백업 이름을 그대로 재사용하지 말고 실제 상태 확인 후 새 release 작성.
- 현재 작업은 준비 요청이다. 이 문서 작성 시 운영 코드·모델 설정·배포는 변경하지 않았다. 다음 사용자의 구현 지시로 구현 시작하며 운영 반영 범위는 그 요청과 기존 승인 범위를 확인한다.
- 브라우저 SPoT 접속이 정책 차단되면 다른 네트워크/브라우저 우회 금지. 가능한 코드 검증을 하고 시각 확인 한계를 명시.

## 7. 다음 모델에게 전달할 시작 문장

“docs/ANALYSIS_AGENT_HANDOFF.md를 읽고 순서대로 구현해줘. 단순 수집 결과를 지역 맥락·패턴·해석·홍보 기회로 분석하고, Critic은 지역 혼입/범위 혼동 교정만 맡겨줘. 현재 미커밋 작업을 보존하고 기존 실제 자료로 짧게 검증해줘. 운영 배포 전 변경 내용과 실제 생성된 분석 예시를 보여줘.”

## 완료 체크리스트

- [ ] 운영 connections 경로의 생성·Critic·적용 게이트 일관성
- [ ] 입력의 지역/공간/시점 맥락 및 다중 근거 연결
- [ ] 지역 해석과 홍보 기회가 담긴 실제 예시 2~3개
- [ ] 전국 사례 허용·지역 혼입 교정 테스트
- [ ] Area Summary 프런트 덮어쓰기 제거 및 PDF 일관성
- [ ] 실패·기존 결과 호환, 출처·숫자 무결성 유지
- [ ] 호출 수와 검증 범위 기록, 운영 반영 여부 명확히 보고

### 2026-10-08 구현 및 실제 출력 검증 결과

코드 연결과 지역 범위 Critic 변경은 구현했다. Python 관련 테스트 63개와 웹 개요/Trend 표시 테스트 통과. 실제 모델 호출은 사용자 승인한 총12회만 실행했고 운영 배포는 하지 않았다.
실제 생성에는 아직 수치 나열·교차 집단 추론·거리 해석 확대가 남아 있어 출력 품질 안정화 완료로 표시하지 않는다. 실제 예시와 한계: output/analysis-agent-v2/REVIEW.md. 추가 모델 호출 및 배포 없이 사용자에게 먼저 검토 결과를 전달한다.

### 후속 생성 가이드 보완

생성 스키마 각 필드에 결론·관측 관계·구체적인 홍보 기회 역할을 명시했다. 생성 입력에 짧은 작성 계획과 성별/연령 독립 분포 설명을 붙이고, 전국 사례 연결은 기사 요약 대신 참여 방식과 지역 접점을 두 문장으로 설명하도록 보완했다. 이는 생성 가이드이며 길이·참신함을 Critic 탈락 조건으로 추가하지 않았다. 원자료와 기존 화면은 보존한다. 관련 Python 36개 및 웹 개요 회귀 테스트 통과. 추가 API 호출 0회, 운영 배포 없음. 새 가이드의 실제 모델 출력 품질은 아직 검증하지 않았다.

### 역할별 입력과 개요 구조 분리

추가 승인 4회 재검증은 output/analysis-agent-v2/RECHECK_REVIEW.md에 기록했다. 이후 생성기 입력을 regional_setting / consumption_timing / sales_age_profile / sales_gender_profile / population_context로 분리했다. 모델에는 역할별 자료만 전달하며 중복된 평면 observations와 기존 관계 메모는 전달하지 않는다. 원자료 ID 레지스트리는 코드 검증용으로 유지한다.
area_reading의 내부 생성 필드는 regional_character / observed_connection / promotion_opening이다. 코드가 세 문장을 기존 interpretation과 planning_question에 매핑하므로 공용 Scout 인터페이스와 웹/PDF 필드는 바뀌지 않는다. Critic에 새 품질 게이트를 추가하지 않았다. 동래 개요가 탈락한 뒤 다른 기회가 개요로 승격되는 오류도 수정했다. 관련 Python 61개 및 웹 개요/Trend 회귀 테스트 통과. 이 구조 변경 이후 추가 모델 호출과 운영 배포는 없으며 실제 출력 품질은 아직 검증 전이다.
