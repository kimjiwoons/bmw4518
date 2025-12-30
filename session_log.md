# 프로젝트 세션 로그

## 메타 정보
- 프로젝트명: GeeLark ADB 네이버 검색 자동화
- 시작일: 2025-12-29
- 마지막 업데이트: 2025-12-30
- 현재 세션: #7

---

## 프로젝트 개요

네이버 모바일 검색에서 특정 도메인을 찾아 클릭하는 SEO 자동화 도구.
삼성 브라우저: CDP 비활성화, 순수 ADB + 템플릿 매칭 방식으로 동작 (완료).

---

## 완료된 작업
| 번호 | 작업명 | 수정/생성 파일 | 상세 내용 | 결과 |
|------|--------|----------------|-----------|------|
| 1 | OCR → 템플릿 매칭 교체 | adb/adb_auto.py | easyocr 제거, OpenCV 템플릿 매칭으로 교체. find_template() 메서드 추가 | 성공 |
| 2 | step5 삼성 브라우저 템플릿 매칭 | adb/adb_auto.py | CDP 없이 순수 ADB + 템플릿 매칭으로 "검색결과 더보기" 찾기 | 성공 |
| 3 | step6 삼성 브라우저 템플릿 매칭 | adb/adb_auto.py | 템플릿 매칭으로 클릭, 버튼 사라짐으로 페이지 전환 감지 | 성공 |
| 4 | 모바일 CDP 전체 비활성화 | adb/adb_auto.py | 탐지 위험 제거 위해 모든 브라우저 CDP 연결 비활성화 | 성공 |
| 5 | test_ocr.py 삭제 | adb/test_ocr.py | OCR 테스트 파일 제거 | 성공 |
| 6 | step7 삼성 브라우저 도메인 찾기 | adb/adb_auto.py | 템플릿 매칭으로 도메인 찾기, 서브링크 영역 제외, 무한 재시도 로직 구현 | 성공 |
| 7 | 삼성 브라우저 "계속" 버튼 처리 | adb/adb_auto.py | first_run_buttons에 "계속" 추가, _wait_for_page_load() 메서드 추가 | 성공 |
| 8 | 삼성 브라우저 페이지 로드 템플릿 매칭 | adb/adb_auto.py | _wait_for_page_load() XML→템플릿 매칭 변경, step2 무한 재시도 로직 | 성공 |
| 9 | 삼성 브라우저 "계속하기" 버튼 + 스와이프 새로고침 | adb/adb_auto.py | first_run_buttons에 "계속하기" 추가, 새로고침을 스와이프(pull-to-refresh)로 변경 | 성공 |
| 10 | find_element_by_text 정규식 수정 | adb/adb_auto.py | partial=False일 때 텍스트 캡처 그룹 누락 버그 수정 | 성공 |
| 11 | 크롬 step7 스크롤 50% 로직 | adb/adb_auto.py | CDP 계산값 50%만 먼저 스크롤, 이후 스크롤하면서 찾기 (30회) | 성공 |
| 12 | 크롬 첫 실행 + 번역 팝업 처리 | adb/adb_auto.py | "Use without an account" 버튼 추가, 번역 팝업 화면 하단 탭으로 닫기 | 성공 |
| 13 | 크롬 번역 팝업 우선 처리 | adb/adb_auto.py | 첫 실행 버튼 찾기 전 번역 팝업 먼저 감지/닫기 | 성공 |
| 14 | 브라우저별 스크롤 보정값 설정 | adb/config.py, adb/adb_auto.py | BROWSER_SCROLL_CONFIG 추가 (scroll_factor, search_direction) | 성공 |
| 15 | 크롬 번역 팝업 처리 제거 | adb/adb_auto.py | 번역 팝업 감지/닫기 로직이 엉뚱한 곳 클릭 → 제거 (나중에 해결) | 성공 |
| 16 | 도메인/제목/설명 랜덤 클릭 | adb/adb_auto.py | MobileCDP find_all_links_by_domain에 서브링크 필터링+광고 제외+링크타입 분류 추가, 도메인/제목/설명 중 랜덤 선택 후 영역 내 랜덤 좌표 클릭 | 성공 |
| 17 | test_step7_v2.py 작성 | adb/test_step7_v2.py | CDP 없이 uiautomator XML 파싱으로 도메인/제목/설명 찾기 테스트 스크립트 | 성공 |
| 18 | 서브링크 길이 조건 추가 | adb/test_step7_v2.py | sublink_max_length=10 이하일 때만 서브링크 키워드 체크 (제목/설명 오탐 방지) | 성공 |
| 19 | 도메인 아래 요소만 포함 | adb/test_step7_v2.py | elem_y < domain_y 조건으로 위쪽 검색결과 이미지 제외 | 성공 |
| 20 | 메인코드에 로직 통합 | adb/adb_auto.py | DOMAIN_CLICK_CONFIG 추가, find_all_elements_with_domain() 완전 재작성하여 제목/설명 찾기 로직 통합 | 성공 |
| 21 | DOMAIN_KEYWORDS 설정 추가 | adb/config.py, adb/adb_auto.py | 도메인별 제목 키워드 설정 (sidecut.co.kr → ["사이드컷", "sidecut"]), 영어 도메인으로 한글 제목 찾기 가능 | 성공 |
| 22 | XML 속성 순서 문제 해결 | adb/adb_auto.py | content-desc 패턴을 테스트 버전과 동일하게 변경 (OR 연산자로 두 가지 속성 순서 처리) | 성공 |
| 23 | CDP 전체 비활성화 | adb/adb_auto.py | _init_mobile_cdp()에서 모든 브라우저 CDP 명시적 비활성화 (탐지 위험 제거) | 성공 |
| 24 | 랜덤 클릭 단순화 | adb/adb_auto.py | _click_domain_link()를 테스트 버전처럼 단순화 (스크롤/재검색 제거, 바로 랜덤 선택) | 성공 |
| 25 | 첫 실행 버튼 중복 클릭 방지 | adb/adb_auto.py | handle_browser_first_run()에 last_clicked_bounds 추적, 같은 버튼 중복 클릭 방지 | 성공 |
| 26 | 첫 실행 버튼 클릭 후 바로 완료 | adb/adb_auto.py | button_ever_clicked 플래그 추가, 버튼 클릭 후 더 이상 버튼 없으면 바로 return True | 성공 |
| 27 | step7 테스트 스크립트 | adb/test_step7_main.py | 메인 코드 사용하여 step7 도메인 찾기/클릭만 테스트하는 스크립트 생성 | 성공 |
| 28 | 타입별 균등 랜덤 선택 (33%씩) | adb/adb_auto.py | _click_domain_link()를 타입별 균등 확률로 변경: 1)타입별 그룹화, 2)타입 먼저 선택(33%), 3)해당 타입 내 요소 선택 | 성공 |
| 29 | step7 상세 디버그 로깅 | adb/adb_auto.py | [STEP7-FIND], [STEP7-CLICK] 접두사로 모든 step7 관련 로그 통일, skipped_reasons 추적, 타입별 개수/선택 과정 상세 출력 | 성공 |
| 30 | _find_and_click_domain_in_page 통합 | adb/adb_auto.py | CDP 없을 때도 _click_domain_link() 사용하여 타입별 균등 선택 적용 | 성공 |
| 31 | 테스트 스크립트 타입별 균등 적용 | adb/test_step7_main.py | test_random_selection()도 메인 코드와 동일한 타입별 균등 랜덤 선택 적용, 기대 확률 표시 추가 | 성공 |
| 32 | 삼성만 좌표 기반 검색창 클릭 | adb/adb_auto.py | coordinate_only_browsers에서 firefox, opera, edge 제거. 삼성만 XML에서 웹 요소 안 보여서 좌표 모드 | 성공 |
| 33 | UI 요소 캐시 구현 | adb/config.py, adb/adb_auto.py | ElementCache 클래스 구현 (TTL 30분), find_element_by_resource_id에 캐시 적용. 삼성 제외 (좌표 기반) | 성공 |
| 34 | 페이지 전환 확인 캐시 비활성화 | adb/adb_auto.py | nx_query 찾을 때 use_cache=False 추가. 페이지 전환/로드 확인은 실제 화면 상태 필요 | 성공 |
| 35 | 기기별 파일 기반 캐시 | adb/config.py, adb/adb_auto.py | 브라우저 첫 실행 버튼 위치를 기기별 JSON 파일로 캐시. 파일 삭제하면 다시 덤프. cache/ 디렉토리에 element_cache_{device}.json 생성 | 성공 |

---

## 발생한 이슈 및 해결
| 이슈 | 원인 | 해결 방법 |
|------|------|-----------|
| 페이지 전환됐는데 실패 판정 | 캐시된 nx_query 값으로 "여전히 존재" 판단 | 페이지 전환/로드 확인 시 use_cache=False |
| CDP 좌표 불일치 | 삼성 브라우저 CDP 좌표가 실제 화면과 다름 | 템플릿 매칭으로 실제 화면 좌표 찾기 |
| easyocr 메모리 오류 | GPU 메모리 부족 | OpenCV 템플릿 매칭으로 대체 |
| pytesseract 한글 인식 불량 | 한글 글자 분리됨 | 템플릿 매칭으로 대체 |
| CDP 탐지 위험 | 서버에서 CDP 연결 감지 가능성 | 모바일 CDP 전체 비활성화 |
| 삼성 브라우저 "계속" 버튼 | 첫 화면에 "계속" 버튼 미처리 | first_run_buttons에 추가 + _wait_for_page_load() |
| JS 미로드 시 검색창 클릭 실패 | 검색창 클릭해도 입력창 안 뜸 | 템플릿 매칭으로 확인 + 새로고침 + 무한 재시도 |
| find_element_by_text 에러 | partial=False 정규식에 텍스트 캡처 그룹 없음 | 캡처 그룹 추가 (5개 → 5개 통일) |
| 크롬 step7 사이트 못 찾음 | CDP 계산값대로 스크롤하면 사이트가 이미 지나감 | 50%만 먼저 스크롤 후 스크롤하면서 찾기 |
| 크롬 첫 실행 화면 처리 안 됨 | "Use without an account" 버튼 미등록 | first_run_buttons에 추가 |
| 크롬 번역 팝업 | 초기화 시 번역 설정 리셋 | 화면 하단 탭으로 팝업 닫기 |
| 브라우저별 스크롤 차이 | 삼성:지나침, 크롬:부족 | BROWSER_SCROLL_CONFIG로 보정값/찾기방향 설정 |
| 크롬 번역 팝업 엉뚱한 클릭 | 팝업 감지 로직이 잘못된 곳 터치 | 일단 제거, 나중에 해결책 찾기 |
| 도메인 영역만 클릭 | uiautomator는 도메인 텍스트만 찾음 | MobileCDP로 도메인/제목/설명 링크 모두 찾기 + 서브링크 필터링 |
| 제목/설명이 서브링크로 SKIP | 서브링크 키워드("스노보드")가 제목에도 포함됨 | sublink_max_length=10 조건 추가, 짧은 텍스트만 서브링크 체크 |
| 다른 검색결과 이미지 클릭 | 도메인 위에 있는 요소도 포함됨 | elem_y < domain_y 조건으로 도메인 아래 요소만 포함 |
| MobileCDP 탐지 위험 | CDP 활성화 시 서버에서 감지 가능 | uiautomator XML 파싱 방식으로 전환 (CDP 없이 동작) |
| 제목 키워드 불일치 | 영어 도메인(sidecut)으로 한글 제목(사이드컷) 못 찾음 | DOMAIN_KEYWORDS 설정으로 도메인별 키워드 지정 |
| XML 속성 순서 불일치 | content-desc 패턴이 한 가지 속성 순서만 처리 | OR 연산자(\|)로 두 가지 순서 모두 처리 (테스트 버전 패턴 적용) |
| 크롬 CDP 활성화 시도 | 삼성만 비활성화, 크롬은 CDP 연결 시도 (버그로 실패) | _init_mobile_cdp()에서 모든 브라우저 명시적 비활성화 |
| 랜덤 클릭이 도메인만 선택 | _click_domain_link()의 스크롤/재검색 로직이 요소를 잃어버림 | 테스트 버전처럼 단순화 (바로 랜덤 선택) |
| 첫 실행 버튼 두 번 클릭 | 같은 버튼을 연속으로 클릭하여 콘텐츠 영역 터치 | last_clicked_bounds로 중복 클릭 방지 |
| 네이버 로드 감지 실패 | "naver" in xml 체크 실패, 첫 실행 버튼 계속 찾음 | button_ever_clicked 후 버튼 없으면 바로 완료 처리 |

---

## 현재 진행 중

(없음)

---

## 다음 단계 (TODO)
- [x] step7: 도메인 찾기 (삼성 브라우저용 템플릿 매칭 방식 구현) ✓
- [x] step7: 도메인/제목/설명 랜덤 클릭 (uiautomator XML 파싱 방식) ✓
- [x] step7: 타입별 균등 랜덤 선택 (33%씩) + 상세 디버그 로깅 ✓
- [ ] step4_5: 통합에서 도메인 찾기 (삼성 브라우저용)
- [ ] 도메인 텍스트 → 이미지 생성 → 템플릿 매칭 방식 검토
- [ ] 템플릿 파일 생성: template_search.png (검색창), template_domain.png, template_sublink.png
- [ ] 크롬 번역 팝업 처리 해결 (현재 제거됨)

---

## 중요 결정사항 및 메모

### 삼성 브라우저 특이사항
- ADB XML(uiautomator)에서 웹 요소가 안 보임
- CDP 좌표가 실제 화면 좌표와 다름
- 해결: 템플릿 매칭 사용

### 탐지 방지
- 모바일에서 CDP 연결 안 함 (탐지 위험)
- 스크롤 계산은 PC CDP가 담당
- 모바일은 순수 ADB 터치/스크롤만 사용

### 템플릿 파일
- `adb/template_more.png`: "검색결과 더보기" 버튼 템플릿
- `adb/template_search.png`: 네이버 검색창 템플릿 (페이지 로드 확인용) - 생성 필요
- `adb/template_domain.png`: 도메인 영역 템플릿 (step7용) - 생성 필요
- `adb/template_sublink.png`: 서브링크 영역 템플릿 (클릭 제외용) - 생성 필요
- 임계값: 0.7

### 브라우저별 스크롤 보정 (BROWSER_SCROLL_CONFIG)
```python
"samsung": {"scroll_factor": 0.9, "search_direction": "up"},   # 지나침 → 90%, 위로 찾기
"chrome":  {"scroll_factor": 1.1, "search_direction": "down"}, # 부족함 → 110%, 아래로 찾기
"opera":   {"scroll_factor": 1.1, "search_direction": "down"},
"edge":    {"scroll_factor": 1.1, "search_direction": "down"},
"firefox": {"scroll_factor": 1.0, "search_direction": "down"},
```

### 도메인 링크 랜덤 클릭 로직 (CDP 없이 uiautomator)
`find_all_elements_with_domain` 동작 (adb_auto.py):
1. XML에서 도메인 텍스트 찾기 (text 속성)
2. 도메인 아래 content-desc 속성에서 제목/설명 찾기
3. 서브링크 제외: 10자 이하 + 키워드 포함 시 SKIP
4. 제목 판단: 도메인 아래 100px 이내 + 도메인 키워드 포함
5. 설명 판단: 50자 이상

### 타입별 균등 랜덤 선택 (33%씩)
`_click_domain_link` 동작 (adb_auto.py):
1. 링크를 타입별로 그룹화: {'domain': [...], 'title': [...], 'desc': [...]}
2. 존재하는 타입만 필터 (없는 타입 제외)
3. **타입 먼저 랜덤 선택** (균등 확률: 3타입이면 33%씩)
4. 해당 타입 내에서 요소 랜덤 선택
5. 영역 내 랜덤 좌표 클릭 (15% 마진)
6. 페이지 전환 확인 → 실패 시 최대 3회 재시도

### step7 디버그 로그 접두사
- `[STEP7-FIND]`: 도메인/제목/설명 요소 찾기 관련 로그
- `[STEP7-CLICK]`: 요소 클릭 관련 로그
- `[STEP7]`: 스크롤/탐색 관련 로그

### DOMAIN_CLICK_CONFIG 설정
```python
DOMAIN_CLICK_CONFIG = {
    "desc_min_length": 50,           # 설명 최소 길이
    "sublink_keywords": ["강습요금", "대표자", "소개", ...],  # 서브링크 키워드
    "sublink_max_length": 10,        # 서브링크 최대 길이
    "max_distance_from_domain": 300, # 도메인과 최대 거리
    "title_distance": 100,           # 제목 판단 거리
}
```

### DOMAIN_KEYWORDS 설정 (config.py)
도메인별 제목 키워드 - 영어 도메인으로 한글 제목 찾을 때 사용
```python
DOMAIN_KEYWORDS = {
    "sidecut.co.kr": ["사이드컷", "sidecut", "신봉석"],
    # 새 도메인 추가 시 여기에 추가
}
```

### 첫 실행 버튼 처리 로직 (handle_browser_first_run)
```
1. XML에서 "naver" 또는 "검색" 있으면 → return True (완료)
2. 첫 실행 버튼 찾기 (Use without an account 등)
3. 같은 bounds의 버튼은 중복 클릭 방지 (last_clicked_bounds)
4. 버튼 클릭 후 → 다음에 버튼 없음 → return True (페이지 전환됨)
```

### UI 요소 캐시 설정 (ELEMENT_CACHE_CONFIG)
고정 UI 요소 위치 캐시로 속도 개선 (삼성 제외)
```python
ELEMENT_CACHE_CONFIG = {
    "ttl_seconds": 1800,  # 30분
    "enabled": True,
    # 크롬, 파이어폭스, 오페라, 엣지에서 사용
    # 삼성은 좌표 기반이라 해당 없음
    "cacheable_elements": [
        "MM_SEARCH_FAKE",  # 네이버 메인 검색창
        "query",           # 검색 모드 입력창
        "nx_query",        # 검색 결과 페이지 검색창
    ],
    "cache_dir": "cache",  # 캐시 파일 디렉토리
    "cacheable_text_elements": {  # 브라우저별 첫 실행 버튼
        "chrome": ["Use without an account", "동의 및 계속", ...],
        "samsung": ["계속", "동의", ...],
        # ... 기타 브라우저
    },
}
```
- 적용 브라우저: 크롬, 파이어폭스, 오페라, 엣지
- 삼성 브라우저: 좌표 기반이라 XML 덤프 안 함 → 캐시 해당 없음
- 캐시 히트 시 XML 덤프 생략 → 속도 향상
- 화면 크기별 캐시 키 분리
- `[CACHE]` 접두사 로그로 캐시 동작 확인

### 기기별 파일 캐시 (브라우저 첫 실행 버튼)
브라우저 버전이 기기마다 달라 첫 실행 버튼 위치가 다를 수 있음
```
adb/cache/
├── element_cache_98_98_125_37_20920.json   # 테스트폰1
├── element_cache_128_14_109_188_20569.json # 폰2
└── element_cache_128_14_109_189_20570.json # 폰3
```
- 첫 덤프 시 자동 캐시
- 브라우저 업데이트로 버튼 위치 변경 시: 캐시 파일 삭제 → 다시 덤프
- 캐시 키 형식: `text|{browser}|{button_text}|{width}x{height}`

### ADB 명령어
```bash
# 스크린샷
adb -s 98.98.125.37:21306 exec-out screencap -p > screenshot.png
```
