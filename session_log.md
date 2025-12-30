# 프로젝트 세션 로그

## 메타 정보
- 프로젝트명: GeeLark ADB 네이버 검색 자동화
- 시작일: 2025-12-29
- 마지막 업데이트: 2025-12-30
- 현재 세션: #4

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

---

## 발생한 이슈 및 해결
| 이슈 | 원인 | 해결 방법 |
|------|------|-----------|
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

---

## 현재 진행 중

(없음)

---

## 다음 단계 (TODO)
- [x] step7: 도메인 찾기 (삼성 브라우저용 템플릿 매칭 방식 구현) ✓
- [ ] step4_5: 통합에서 도메인 찾기 (삼성 브라우저용)
- [ ] 도메인 텍스트 → 이미지 생성 → 템플릿 매칭 방식 검토
- [ ] 템플릿 파일 생성: template_search.png (검색창), template_domain.png, template_sublink.png

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

### 도메인 링크 랜덤 클릭 로직
MobileCDP `find_all_links_by_domain` 동작:
1. `a[href*="도메인"]`으로 모든 링크 찾기
2. 서브링크 제외 (`data-heatmap-target='.sublink'`)
3. 서브페이지 제외 (href가 도메인+경로로 끝나면 제외)
4. 광고 영역 제외 (tit_area, ad_area, powerlink)
5. 링크 타입 분류: domain/title/desc
6. 여러 링크 중 랜덤 선택 → 해당 영역 내 랜덤 좌표 클릭

### ADB 명령어
```bash
# 스크린샷
adb -s 98.98.125.37:21306 exec-out screencap -p > screenshot.png
```
