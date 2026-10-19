# Local / Trend 실제 검색

`SpotRequest v0.1 -> ScoutResult v0.1` 공통 필드는 유지한다. 고정 지역·수집일·사례 목록은 런타임에서 사용하지 않는다.

## 설정과 실행

저장소 루트의 Git 제외 `.env`에 `NAVER_CLIENT_ID`, `NAVER_CLIENT_SECRET`, `YOUTUBE_API_KEY`를 넣는다.
네이버 일반 검색 API의 Client ID/Secret 또는 API Hub의 API key ID/key 쌍이 필요하다. 키 하나만으로는 뉴스 검색을 실행할 수 없다.
`NAVER_SEARCH_PROVIDER=auto`는 일반 검색을 먼저 호출하고 인증 오류(401/403)일 때만 API Hub를 시도한다. `legacy`, `hub`로 명시할 수도 있다.
Quant에는 기존 Kakao·소상공인 키가 필요하다. 키나 응답 오류 본문은 출력하지 않는다.

```bash
python -m src.integration_smoke samples/input/myeongji_international.confirmed.json --mode live --output .venv/verification/live-research
```

입력 `research.reference_date`를 조사 기준일로 사용한다. 생략하면 `requested_at`, 둘 다 없으면 실행 당일(한국 시간)을 사용한다.
예제 입력의 과거 기준일을 오늘 조사하려면 입력 파일에서 날짜를 갱신하거나 해당 필드를 생략한다.
`lookback_days=0`도 유효하다. `collected_at`은 실제 API 응답을 받은 현재 시각이다.
`--mode offline`은 dotenv 및 외부 호출을 막는다. 키 없음·자료 없음·API 실패 시 고정 자료로 대체하지 않는다.

## 조사 범위

- Local: 점포명의 신도시명, 주소의 동/읍/면 또는 도로명 접두어로 지역 검색어를 만든다. 명지국제신도시와 에코델타시티를 한 지역으로 묶지 않는다. 지역 문맥을 추출할 수 없으면 실패한다. 기사 제목/요약의 지역명과 변화 표현을 대조한다.
- Trend: 게임 팝업·음식 팝업·지역 축제를 전국에서 검색한다. 연령·성별은 검색어 필수 조건 대신 후보 선정과 매장 응용 가설의 맥락으로 사용한다. 지역·제품 일치는 필수 조건이 아니며 `same_product` / `adjacent_category` / `cross_industry_transfer`는 설명용 메타데이터다. 뉴스 제목에는 오프라인 행사 표현이 있어야 한다. 유튜브는 업로드일과 제목·설명을 확인하며 영상을 시청했다고 표시하지 않는다.
- 네이버는 검색어당 최대 2페이지, 유튜브는 검색어당 검색 1회와 영상 메타데이터 조회 1회로 제한한다. Local 최대 15자료, Trend는 제공자별 최대 10자료를 반환한다. 같은 URL은 중복 제거한다. 전체 검색 결과를 빠짐없이 조사하는 방식은 아니다.
- 429 응답을 받은 제공자는 해당 실행에서 후속 검색을 건너뛴다. 다른 제공자의 자료는 계속 사용할 수 있다.

## 해석 제한

실제 검색 API로 수집했어도 행사 실체·독립 행사 여부·점포 반경은 검증하지 않았으므로 결과는 `partial`이다. 자료가 없으면 `failed`다.
Local은 [원문 대조·문맥 분류](LOCAL_SOURCE_VERIFICATION.md)를 추가 수행한다. 직접 변화와 주변 행정구역 맥락·배경 자료를 나누고 날짜·추출·지역 연결의 한계를 표시한다. 원문을 읽지 못하거나 연결 근거가 없는 자료는 수동 확인 후보로 남긴다. Trend는 검색 메타데이터 기반 후보를 유지한다.
네이버 `pubDate`는 네이버에 제공된 시각이고, 유튜브는 영상 업로드일이다. 행사 개최일과 다를 수 있다.
기사별 후보 수는 사건 수가 아니다. Trend 패턴은 관련 표현이 최소 2자료에서 반복된 후보이며 실제 경험 구조와 효과를 증명하지 않는다.
도로명에서 만든 Local 지역 검색어와 기사 표현은 행정 경계·거리 검증을 대신하지 않는다. 약칭으로만 쓰인 기사와 제목에 행사 표현이 없는 Trend 기사는 누락될 수 있다. 업종 분류는 제목 기반 추정이며 게임·촬영 등 참여 방식과 구분한다. 같은 날짜·지역·고유명 표현을 공유하는 관련 보도는 참고 슬롯 하나로 묶고 출처를 보존한다. 행사 참여 의사·설문 보도는 고객층 조사 맥락으로 별도 표시한다.

전국 실제 검색 및 보완 결과: [2026-10-02 검증](TREND_LIVE_VALIDATION.md).

공식 API 계약: [네이버 뉴스 검색](https://developers.naver.com/docs/serviceapi/search/news/news.md), [API Hub 뉴스 검색](https://api.ncloud-docs.com/docs/naver-api-hub-search-news), [YouTube 검색](https://developers.google.com/youtube/v3/docs/search/list), [영상 메타데이터](https://developers.google.com/youtube/v3/docs/videos/list).
