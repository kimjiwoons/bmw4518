# ============================================
# GeeLark ADB 자동화 - 설정 파일
# ============================================

# ============================================
# ADB 연결 정보
# ============================================
ADB_CONFIG = {
    # ADB 실행 파일 경로 (환경변수에 있으면 "adb"만 써도 됨)
    "adb_path": "adb",

    # 기본 타임아웃 (초)
    "command_timeout": 30,

    # ──────────────────────────────────────────
    # 브라우저 초기화 설정
    # ──────────────────────────────────────────
    # 매번 새 프로필로 시작 (브라우저 데이터 초기화)
    "clear_browser_data": True,
    # 초기화할 브라우저 패키지 (기본: 크롬)
    "browser_package": "com.android.chrome",
}

# ============================================
# 폰 목록 (테스트용 1대)
# 나중에 50~60대로 확장
# ============================================
PHONES = {
    "1": {
        "name": "테스트폰1",
        "adb_address": "98.98.125.37:20920",
        "login_code": "3f5d0d",  # GeeLark 로그인 코드
        "browser": "chrome",
        "screen_width": 720,
        "screen_height": 1440,
    },
    # 추후 추가 예시:
    # "2": {
    #     "name": "폰2",
    #     "adb_address": "128.14.109.188:20569",
    #     "browser": "samsung",
    #     "screen_width": 720,
    #     "screen_height": 1440,
    # },
    # "3": {
    #     "name": "폰3",
    #     "adb_address": "128.14.109.189:20570",
    #     "browser": "firefox",
    #     "screen_width": 720,
    #     "screen_height": 1440,
    # },
}

# ============================================
# 브라우저 설정
# ============================================
BROWSERS = {
    "chrome": {
        "package": "com.android.chrome",
        "activity": "com.google.android.apps.chrome.Main",
        "devtools_socket": "chrome_devtools_remote",  # CDP 소켓
        "cdp_port": 9222,  # 포트 포워딩용
    },
    "samsung": {
        "package": "com.sec.android.app.sbrowser",
        "activity": ".SBrowserMainActivity",
        "devtools_socket": "Terrace_devtools_remote",  # CDP 소켓
        "cdp_port": 9223,  # 포트 포워딩용
    },
    "firefox": {
        "package": "org.mozilla.firefox",
        "activity": ".App",
    },
    "opera": {
        "package": "com.opera.browser",
        "activity": ".Browser",
    },
    "edge": {
        "package": "com.microsoft.emmx",
        "activity": "com.microsoft.ruby.Main",
    },
}

# ============================================
# 네이버 검색 설정 (CDP 로직 100% 반영)
# ============================================
NAVER_CONFIG = {
    # 시작 URL
    "start_url": "https://m.naver.com",
    
    # 검색 결과 URL 패턴
    "search_url": "https://m.search.naver.com/search.naver?query=",
    
    # 검색 실행 모드: 1=엔터, 2=돋보기, 3=랜덤
    "search_mode": 2,
    
    # 통합 페이지에서 먼저 찾기
    "search_in_total_first": True,
    
    # 더보기 텍스트
    "target_text": "검색결과 더보기",
    
    # 최대 스크롤 횟수
    "max_scrolls": 50,
    
    # 통합 페이지 최대 스크롤
    "max_scrolls_total": 30,
    
    # 더보기 최대 페이지
    "max_page": 10,
    
    # 6단계 클릭 재시도
    "step6_click_retry": 5,
    
    # 전체 재시도
    "max_full_retry": 2,
    
    # 체류 시간 (초)
    "stay_min": 10,
    "stay_max": 20,
}

# ============================================
# Selectors (CDP와 동일)
# ============================================
SELECTORS = {
    # 메인 검색창
    "search_fake": ["MM_SEARCH_FAKE", "sch_input"],
    # 실제 입력창
    "search_real": ["query"],
    # 더보기 페이지 검색창
    "search_more": ["nx_query"],
    # 검색 버튼
    "search_button": ["sch_btn_search", "btn_search"],
    # 검색 결과 확인
    "search_result": ["search_result", "lst_total", "content", "api_subject_bx"],
}

# ============================================
# 읽기 멈춤 설정 (CDP와 동일)
# ============================================
READING_PAUSE_CONFIG = {
    "enabled": True,
    "probability": 0.1,    # 20% 확률
    "min_time": 2.0,
    "max_time": 4.0,
}

# ============================================
# 터치/탭 설정
# ============================================
TOUCH_CONFIG = {
    # 탭 후 대기 시간 (초)
    "after_tap_delay_min": 0.1,
    "after_tap_delay_max": 0.3,
    
    # 탭 좌표 랜덤 오프셋 (픽셀)
    "tap_random_x": 15,
    "tap_random_y": 10,
    
    # 탭 duration (밀리초) - 사람처럼 약간 누르고 있기
    "tap_duration_min": 50,
    "tap_duration_max": 150,
}

# ============================================
# 스크롤 설정
# ============================================
SCROLL_CONFIG = {
    # 스크롤 거리 (픽셀)
    "distance": 400,
    "distance_random": 200,
    
    # 스크롤 duration (밀리초)
    "duration_min": 300,
    "duration_max": 600,
    
    # 스크롤 후 대기 시간 (초)
    "after_scroll_delay_min": 0.5,
    "after_scroll_delay_max": 1.5,
}

# ============================================
# 타이핑 설정
# ============================================
TYPING_CONFIG = {
    # 글자 간 딜레이 (초)
    "char_delay_min": 0.05,
    "char_delay_max": 0.15,
    
    # 타이핑 전 대기 (초)
    "before_typing_delay_min": 0.3,
    "before_typing_delay_max": 0.8,
    
    # 타이핑 후 대기 (초)
    "after_typing_delay_min": 0.5,
    "after_typing_delay_max": 1.0,
}

# ============================================
# 대기 설정
# ============================================
WAIT_CONFIG = {
    # 페이지 로딩 대기 (초)
    "page_load_min": 2.0,
    "page_load_max": 4.0,
    
    # 요소 대기 최대 시간 (초)
    "element_timeout": 20,
    
    # 요소 체크 간격 (초)
    "element_check_interval": 0.3,
    
    # 요소 발견 후 추가 대기 (초)
    "after_element_found_min": 0.5,
    "after_element_found_max": 1.5,
    
    # 요소 찾기 최대 재시도 (2단계용)
    "max_element_retry": 30,
}

# ============================================
# 체류 설정
# ============================================
STAY_CONFIG = {
    # 타겟 사이트 체류 시간 (초)
    "target_stay_min": 10,
    "target_stay_max": 20,
}

# ============================================
# 재시도 설정
# ============================================
RETRY_CONFIG = {
    # 요소 찾기 재시도
    "max_element_retry": 30,
    
    # 전체 프로세스 재시도
    "max_full_retry": 2,
    
    # 재시도 전 대기 (초)
    "retry_delay": 2.0,
}

# ============================================
# 검색 모드 설정
# ============================================
SEARCH_CONFIG = {
    # 검색 실행 방식: "enter" = 엔터키, "button" = 돋보기 클릭, "random" = 랜덤
    "search_mode": "random",
    
    # 통합 검색에서 먼저 찾기
    "search_in_total_first": True,
    
    # 더보기 페이지에서 찾기
    "go_to_more": True,
    
    # 더보기 페이지 최대 페이지 수
    "max_more_pages": 5,
}

# ============================================
# 결과 파일 설정
# ============================================
RESULT_CONFIG = {
    # 결과 파일 경로
    "result_file": "C:\\exload\\python\\result.txt",
    
    # 결과 값
    "done_value": "SCROLL:DONE",
    "not_found_value": "SCROLL:NOTFOUND",
    "error_value": "SCROLL:ERROR",
}

# ============================================
# 좌표 설정 (720x1440 기준)
# 다른 해상도는 비율로 계산
# ============================================
COORDINATES = {
    # 네이버 메인 검색창 (MM_SEARCH_FAKE)
    # bounds="[143,295][603,393]" 에서 fallback 좌표 계산
    "naver_search_box": {
        "x": 373,  # (143+603)/2 = 373
        "y": 344,  # (295+393)/2 = 344
    },
    
    # 검색 버튼 (MM_SEARCH_FOCUS_BTN) - 상단 우측
    # bounds="[639,139][720,50]" 에서 계산 (비정상 bounds, 대략값 사용)
    "search_button": {
        "x": 680,  # 우측
        "y": 95,   # 상단
    },
    
    # 스크롤 시작/끝 Y 좌표 (해상도 1440 기준)
    "scroll_start_y": 1100,
    "scroll_end_y": 400,
    
    # 스크롤 X 좌표 (화면 중앙 근처)
    "scroll_x": 360,
}

# ============================================
# CDP 스크롤 계산 설정
# ============================================
CDP_CONFIG = {
    # CDP 포트
    "port": 9222,

    # CDP 사용 여부
    "enabled": True,

    # ──────────────────────────────────────────
    # Chrome 자동 실행 설정
    # ──────────────────────────────────────────
    # Chrome 자동 실행 여부
    "auto_launch_chrome": True,
    # Headless 모드 (브라우저 창 숨김)
    "headless": True,

    # ──────────────────────────────────────────
    # 스크롤 정보 캐시 설정
    # ──────────────────────────────────────────
    # 스크롤 정보 갱신 주기 (N회마다 1번 갱신)
    "cache_refresh_interval": 10,

    # ──────────────────────────────────────────
    # 뷰포트 보정
    # 실제 모바일 브라우저는 상태바/주소창 때문에
    # screen_height보다 뷰포트가 작음
    # ──────────────────────────────────────────
    # 상태바 높이 (픽셀) - 보통 48~56px
    "status_bar_height": 50,
    # 주소창 높이 (픽셀) - 크롬 기준 약 56px
    "address_bar_height": 56,
    # 하단 네비게이션 바 높이 (픽셀) - 있는 경우
    "nav_bar_height": 0,

    # ──────────────────────────────────────────
    # 스크롤 보정 계수
    # ADB swipe 거리와 실제 스크롤 거리 차이 보정
    # 1.0 = 동일, 0.85 = swipe 400px → 실제 340px 스크롤
    # ──────────────────────────────────────────
    "scroll_calibration": 0.85,

    # ──────────────────────────────────────────
    # 타겟 위치 설정
    # 요소가 화면의 어느 위치에 올 때 클릭할지
    # 0.0 = 최상단, 0.5 = 중앙, 1.0 = 최하단
    # ──────────────────────────────────────────
    # "검색결과 더보기" 타겟 위치 (화면 대비)
    "more_target_position": 0.4,
    # 도메인 링크 타겟 위치 (화면 대비)
    "domain_target_position": 0.35,

    # ──────────────────────────────────────────
    # 여유 스크롤 설정
    # 계산된 위치에 도달 후 추가 스크롤
    # ──────────────────────────────────────────
    # 여유 스크롤 횟수 (고정값 대신 비율 사용)
    "margin_scroll_ratio": 0.1,  # 계산값의 10% 추가
    # 최소 여유 스크롤
    "margin_scroll_min": 1,
    # 최대 여유 스크롤
    "margin_scroll_max": 5,

    # ──────────────────────────────────────────
    # 페이지 로딩 대기
    # ──────────────────────────────────────────
    "page_load_wait": 3.0,
    "after_scroll_wait": 0.3,
}

# ============================================
# 브라우저별 스크롤 보정 설정
# ============================================
BROWSER_SCROLL_CONFIG = {
    # 삼성: 지나치는 경향 → 보정값 줄임, 위로 찾기
    "samsung": {
        "scroll_factor": 0.9,      # 스크롤 90% (지나치니까)
        "search_direction": "up",   # 위로 스크롤하면서 찾기
    },
    # 크롬: 부족한 경향 → 보정값 늘림, 아래로 찾기
    "chrome": {
        "scroll_factor": 1.1,      # 스크롤 110% (부족하니까)
        "search_direction": "down", # 아래로 스크롤하면서 찾기
    },
    # 오페라: 크롬과 비슷
    "opera": {
        "scroll_factor": 1.1,
        "search_direction": "down",
    },
    # 엣지: 크롬과 비슷하게 설정
    "edge": {
        "scroll_factor": 1.1,
        "search_direction": "down",
    },
    # 파이어폭스: 기본값
    "firefox": {
        "scroll_factor": 1.0,
        "search_direction": "down",
    },
}

# ============================================
# 디버그 설정
# ============================================
DEBUG_CONFIG = {
    # 상세 로그 출력
    "verbose": True,

    # 스크린샷 저장 (디버깅용)
    "save_screenshots": False,
    "screenshot_path": "C:\\exload\\python\\screenshots\\",

    # CDP 디버그 모드 (계산 과정 상세 출력)
    "cdp_debug": True,
}

# ============================================
# Gboard 한글 키보드 레이아웃 (720x1440 해상도)
# 기준: ㄱ = (240, 1050)
# 키 간격: 가로 ~72px, 세로 ~72px
# ============================================
KEYBOARD_LAYOUT = {
    # 2행 (y = 1050) - ㅂㅈㄷㄱㅅㅛㅕㅑㅐㅔ (10키)
    # ㄱ=240, 간격 72px → 시작 x = 240 - 3*72 = 24
    'ㅂ': {'x': 24, 'y': 1050},
    'ㅈ': {'x': 96, 'y': 1050},
    'ㄷ': {'x': 168, 'y': 1050},
    'ㄱ': {'x': 240, 'y': 1050},
    'ㅅ': {'x': 312, 'y': 1050},
    'ㅛ': {'x': 384, 'y': 1050},
    'ㅕ': {'x': 456, 'y': 1050},
    'ㅑ': {'x': 528, 'y': 1050},
    'ㅐ': {'x': 600, 'y': 1050},
    'ㅔ': {'x': 672, 'y': 1050},
    
    # 3행 (y = 1122) - ㅁㄴㅇㄹㅎㅗㅓㅏㅣ (9키)
    # 9키라서 간격 80px, 시작 x=40
    'ㅁ': {'x': 40, 'y': 1122},
    'ㄴ': {'x': 120, 'y': 1122},
    'ㅇ': {'x': 200, 'y': 1122},
    'ㄹ': {'x': 280, 'y': 1122},
    'ㅎ': {'x': 360, 'y': 1122},
    'ㅗ': {'x': 440, 'y': 1122},
    'ㅓ': {'x': 520, 'y': 1122},
    'ㅏ': {'x': 600, 'y': 1122},
    'ㅣ': {'x': 680, 'y': 1122},
    
    # 4행 (y = 1194) - (Shift) ㅋㅌㅊㅍㅠㅜㅡ (Backspace)
    'shift': {'x': 54, 'y': 1194},
    'ㅋ': {'x': 132, 'y': 1194},
    'ㅌ': {'x': 204, 'y': 1194},
    'ㅊ': {'x': 276, 'y': 1194},
    'ㅍ': {'x': 348, 'y': 1194},
    'ㅠ': {'x': 420, 'y': 1194},
    'ㅜ': {'x': 492, 'y': 1194},
    'ㅡ': {'x': 564, 'y': 1194},
    'backspace': {'x': 666, 'y': 1194},
    
    # 5행 (y = 1266) - (?123) (,) (Space) (.) (Search)
    '?123': {'x': 54, 'y': 1266},
    ',': {'x': 162, 'y': 1266},
    'space': {'x': 360, 'y': 1266},
    '.': {'x': 558, 'y': 1266},
    'search': {'x': 655, 'y': 1302},  # 실측값 (720x1440 기준)
    
    # 쌍자음 (Shift + 자음)
    'ㄲ': {'x': 240, 'y': 1050, 'shift': True},
    'ㄸ': {'x': 168, 'y': 1050, 'shift': True},
    'ㅃ': {'x': 24, 'y': 1050, 'shift': True},
    'ㅆ': {'x': 312, 'y': 1050, 'shift': True},
    'ㅉ': {'x': 96, 'y': 1050, 'shift': True},
}
