# Instagram 공식 연결 안내

2026-10-03 Meta 공식 문서 확인 기준. SPoT은 현재 **사용자가 추가한 공개 게시물 링크를 표시**한다.
토큰 발급·App Review·Instagram 자료의 GPT 분석은 연결하지 않았다.
2026-10-04부터 Trend 사례 아래에서 사용자가 해시태그 하나를 지정해 서버의 공식 API로
공개 게시물을 조회하는 기능을 추가했다. 승인된 접근과 서버 토큰이 필요하며,
실제 계정으로 공개 검색 성공 여부는 아직 검증하지 않았다. 자동 Scout 수집은 아니다.

## 지금 가능한 화면 연결

Trend의 행사 사례를 선택하고 아래 Instagram 영역에 `https://www.instagram.com/p/게시물ID/`
또는 `/reel/게시물ID/`를 넣는다. 원본 링크와 요청 시 공식 임베드 미리보기를 표시한다.
사례당 최대 6개, 이 브라우저 탭에만 보관한다. 비공개·연령 제한·임베드 비허용 게시물과
Stories는 미리보기가 안 될 수 있다. 원본 링크로 확인한다.

이 링크는 조사 근거 수·PDF·흥부장 프롬프트·GPT 입력에 추가하지 않는다.
oEmbed로 얻은 내용과 메타데이터는 표시용이다. 이를 수집·저장해 분석 데이터로 사용하지 않는다.
공식 [oEmbed 안내](https://developers.facebook.com/documentation/instagram-platform/oembed)의 현재 예시는
`v26.0/instagram_oembed?url=...`이며 과거 토큰 요구사항을 현재 임베드의 조건으로 가정하지 않는다.
SPoT은 이 API를 호출하지 않고 사용자가 선택한 게시물을 공식 `embed.js`로 표시한다.

## 자동 조사에 권장하는 API

**Instagram API with Facebook Login**을 준비한다. 해시태그 검색·다른 전문 계정 조회에
필요한 기능을 이 방식으로 확인했다. 개인 계정 전체의 글을 키워드로 검색하는 API는 아니다.

| 기능 | 가능한 조사 | 제한 |
| --- | --- | --- |
| Hashtag Search | 지정 해시태그의 공개 top/recent 게시물 | 조회 전문 계정당 7일에 서로 다른 해시태그 30개; Stories 제외 |
| Business Discovery | 정확한 사용자 이름으로 다른 Business/Creator 계정과 미디어 조회 | 개인·연령 제한 계정 제외; 전체 키워드 검색 아님 |
| oEmbed / 공식 임베드 | 선정한 공개 게시물 표시 | 표시 전용; 연구 분석용 수집 도구로 사용하지 않음 |

좋아요·댓글 수는 해당 게시물에서의 반응 관측값일 뿐이다. 지역·성별·연령대 선호를
알려주는 자료로 바꾸지 않는다. 영상의 음원·다운로드 설정에 따라 일부 미디어 URL이 없을 수 있다.

## 설정 순서

1. SPoT 조회용 Instagram 계정을 **Business 또는 Creator** 계정으로 전환하고
   관리할 수 있는 Facebook Page에 연결한다. 해당 Page 권한도 확인한다.
2. [Meta for Developers](https://developers.facebook.com/)에서 앱을 만들고
   **Instagram API with Facebook Login** 설정을 진행한다. Instagram Login 방식과 혼동하지 않는다.
3. HTTPS 서버의 로그인 콜백 주소를 등록하고 Facebook Login을 통해 필요한 읽기 권한을 요청한다.
   계정·Page 조회에 필요한 권한은 현재 설정 화면과 아래 공식 가이드에 맞춘다.
   공식 시작 안내의 읽기 연결 권한은 `instagram_basic`, `pages_show_list`다.
   개별 조회 엔드포인트에 추가 권한이 있으면 해당 참조 문서를 따른다.
   게시·댓글 관리 권한은 이 리서치 기능에 요청하지 않는다.
   2026-10-04 연결 확인: 비즈니스 포트폴리오에 속한 Page가 `me/accounts`에서 비어 있었고,
   `pages_read_engagement`, `business_management`를 추가해 사용자 토큰을 다시 발급한 뒤
   사용자가 Page 조회 성공을 확인했다. 두 권한을 함께 변경했으므로 어느 하나만이 원인이라고
   단정하지 않는다. `business_management`는 넓은 비즈니스 관리 권한이므로 기본 필수 권한으로
   모든 앱에 요청하지 말고 실제 자산 구조와 의존성을 확인한다.
4. 개발 모드에서 앱 역할이 부여된 계정으로 연결과 전문 계정 ID를 확인한다.
   Access Token은 사용자에게 화면에서 복사·보관하도록 맡기고 서버 비밀 설정에만 넣는다.
   `GET /me/accounts`로 연결 Page를 선택한 뒤,
   `GET /{page-id}?fields=instagram_business_account`로 조회용 Instagram ID를 얻는다.
5. Hashtag Search를 운영하려면 **Instagram Public Content Access와 App Review**를 준비한다.
   실제 조회 화면·최소 권한·사용 목적·개인정보 처리 및 삭제 절차를 심사 자료로 설명한다.
   일반 사용자가 연결하려면 관련 권한의 운영 접근 수준도 확보해야 한다.
6. 승인 후 서버에서 소수의 관련 해시태그로 먼저 조회하고 7일 단위 사용 목록을 관리한다.
   같은 해시태그를 재검색해도 새 해시태그 예산이 생기지 않는다.
7. 토큰 갱신·만료 처리, 호출 제한·재시도, 보관/삭제 정책을 구현한 뒤 SPoT 자동 수집을 연결한다.
   API로 얻은 데이터를 GPT에 전달할 수 있는 범위는 승인된 용도와 Meta 정책을 확인한 후 별도로 정한다.

현재 앱 상태와 검수 준비 순서는 [검수 준비 문서](INSTAGRAM_REVIEW_PREP.md)를 참조한다.

## 서버 조회 흐름

아래는 구현용 경로 예시다. 토큰은 서버의 Authorization 헤더에 넣고 주소·로그·브라우저에 노출하지 않는다.

```text
GET https://graph.facebook.com/v26.0/ig_hashtag_search
    user_id={조회용_전문계정_ID}&q={해시태그}
  -> 해시태그 ID
GET https://graph.facebook.com/v26.0/{해시태그_ID}/top_media
    user_id={조회용_전문계정_ID}&fields=id,caption,permalink,timestamp,media_type
GET https://graph.facebook.com/v26.0/{해시태그_ID}/recent_media
    user_id={조회용_전문계정_ID}&fields=id,caption,permalink,timestamp,media_type

GET https://graph.facebook.com/v26.0/{조회용_전문계정_ID}
    fields=business_discovery.username({공식계정명}){username,media{permalink,caption,timestamp,media_type}}
```

서버 설정 이름(현재 웹 서버가 읽음, 설정 후 웹 서버 재시작):

```dotenv
SPOT_INSTAGRAM_ACCESS_TOKEN=
SPOT_INSTAGRAM_USER_ID=
SPOT_INSTAGRAM_GRAPH_VERSION=v26.0
```

실제 값은 `.env` 또는 배포 서버 비밀 저장소에만 넣는다. 깃에 올리거나 채팅으로 보내지 않는다.
예외·토큰 검사 결과에 원문 응답이나 토큰을 출력하지 않는다.

Trend → 행사 사례 → Instagram → 공식 API로 해시태그 찾기에서 조회한다.
권한 미승인·토큰 오류·7일 사용 한도를 별도 표시한다. 서버는 Meta의 최근 해시태그 목록을
먼저 확인하며 신규 해시태그 예산이 없거나 전체 목록 확인이 불가능하면 조회를 중단한다.
서버 전체 분당 6회, 화면당 최대 6개 결과이며 원본 링크와 캡션을 표시한다.
선택한 원본 링크만 기존 참고 링크 영역에 저장할 수 있고 조회 캡션은 저장하지 않는다.
이 결과는 Scout 근거·GPT·PDF·흥부장 출력에 포함하지 않는다.

## SPoT 자동 연결 후의 목표

공통 탐색 결과에서 발견한 행사명·공식 계정·해시태그를 좁혀 조회하고,
원본 주소·게시 시각·조회 시각·계정 유형·확인된 수치와 한계를 보존한다.
뉴스와 동일한 행사인지 자동 확정하지 않고 연결 후보로 둔다. 게시물 UI 표시와
연구 근거 수집은 별도 경로로 구현한다. 현재 수동 링크를 자동 수집 완료로 표시하지 않는다.

근거: [공식 시작 안내](https://developers.facebook.com/documentation/instagram-platform/instagram-api-with-facebook-login/get-started),
[공식 API 컬렉션](https://www.postman.com/meta/instagram/documentation/6yqw8pt/instagram-api),
[Hashtag Search](https://developers.facebook.com/documentation/instagram-platform/instagram-api-with-facebook-login/hashtag-search),
[Business Discovery](https://developers.facebook.com/documentation/instagram-platform/instagram-api-with-facebook-login/business-discovery).
