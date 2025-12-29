#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
GeeLark ADB 네이버 검색 자동화 v3
CDP 스크롤 계산 + ADB 실행 통합 버전

사용법: python adb_auto_cdp.py 검색어 도메인 [검색모드] [폰번호] [마지막]
"""

import subprocess
import time
import random
import sys
import re
import json

# CDP 관련 (선택적)
try:
    import requests
    import websocket
    CDP_AVAILABLE = True
except ImportError:
    CDP_AVAILABLE = False

# 템플릿 매칭 관련 (OpenCV)
try:
    import cv2
    import numpy as np
    TEMPLATE_MATCHING_AVAILABLE = True
except ImportError:
    TEMPLATE_MATCHING_AVAILABLE = False

import os
import signal
import atexit

from config import (
    PHONES, ADB_CONFIG, NAVER_CONFIG,
    SCROLL_CONFIG, TOUCH_CONFIG, TYPING_CONFIG, WAIT_CONFIG,
    COORDINATES, SELECTORS, READING_PAUSE_CONFIG, KEYBOARD_LAYOUT,
    CDP_CONFIG, DEBUG_CONFIG
)


# ============================================
# CDP 스크롤 정보 캐시 (N회마다 갱신, 파일 저장)
# ============================================
class CDPScrollCache:
    """CDP 스크롤 정보 캐시 - N회마다 갱신, 파일로 영구 저장"""

    def __init__(self, cache_file=None):
        self._refresh_interval = CDP_CONFIG.get("cache_refresh_interval", 10)

        # 캐시 파일 경로 설정
        if cache_file:
            self._cache_file = cache_file
        else:
            # 기본 경로: 스크립트 위치에 cdp_scroll_cache.json
            script_dir = os.path.dirname(os.path.abspath(__file__))
            self._cache_file = os.path.join(script_dir, "cdp_scroll_cache.json")

        # 파일에서 캐시 로드
        self._cache = {}  # {"keyword|domain": scroll_info}
        self._call_count = {}  # {"keyword|domain": count}
        self._load_from_file()

    def _make_key(self, keyword, domain):
        """키 생성 (JSON 호환)"""
        return f"{keyword}|{domain}"

    def _load_from_file(self):
        """파일에서 캐시 로드"""
        try:
            if os.path.exists(self._cache_file):
                with open(self._cache_file, 'r', encoding='utf-8') as f:
                    data = json.load(f)
                    self._cache = data.get("cache", {})
                    self._call_count = data.get("call_count", {})
                    print(f"[INFO] [캐시] 파일에서 로드: {len(self._cache)}개 항목")
        except Exception as e:
            print(f"[ERROR] [캐시] 파일 로드 실패: {e}")
            self._cache = {}
            self._call_count = {}

    def _save_to_file(self):
        """파일에 캐시 저장"""
        try:
            data = {
                "cache": self._cache,
                "call_count": self._call_count
            }
            with open(self._cache_file, 'w', encoding='utf-8') as f:
                json.dump(data, f, ensure_ascii=False, indent=2)
        except Exception as e:
            print(f"[ERROR] [캐시] 파일 저장 실패: {e}")

    def get(self, keyword, domain):
        """캐시된 스크롤 정보 반환 (없거나 갱신 필요시 None)"""
        key = self._make_key(keyword, domain)
        count = self._call_count.get(key, 0)

        # 첫 호출이거나 N회 도달시 갱신 필요
        if count == 0 or count >= self._refresh_interval:
            self._call_count[key] = 0
            self._save_to_file()
            return None

        return self._cache.get(key)

    def set(self, keyword, domain, scroll_info):
        """스크롤 정보 캐시"""
        key = self._make_key(keyword, domain)
        self._cache[key] = scroll_info
        self._call_count[key] = 1
        self._save_to_file()

    def increment(self, keyword, domain):
        """호출 횟수 증가"""
        key = self._make_key(keyword, domain)
        self._call_count[key] = self._call_count.get(key, 0) + 1
        self._save_to_file()

    def get_count(self, keyword, domain):
        """현재 호출 횟수"""
        key = self._make_key(keyword, domain)
        return self._call_count.get(key, 0)


# 전역 캐시 인스턴스
_scroll_cache = CDPScrollCache()


# ============================================
# Chrome 브라우저 자동 실행 (Headless)
# ============================================
class ChromeLauncher:
    """Chrome 브라우저 자동 실행 관리"""

    def __init__(self, port=9222):
        self.port = port
        self.process = None
        self._find_chrome_path()

    def _find_chrome_path(self):
        """Chrome 실행 파일 경로 찾기"""
        # Windows
        windows_paths = [
            r"C:\Program Files\Google\Chrome\Application\chrome.exe",
            r"C:\Program Files (x86)\Google\Chrome\Application\chrome.exe",
            os.path.expanduser(r"~\AppData\Local\Google\Chrome\Application\chrome.exe"),
        ]

        # Linux
        linux_paths = [
            "/usr/bin/google-chrome",
            "/usr/bin/google-chrome-stable",
            "/usr/bin/chromium",
            "/usr/bin/chromium-browser",
            "/snap/bin/chromium",
        ]

        # macOS
        mac_paths = [
            "/Applications/Google Chrome.app/Contents/MacOS/Google Chrome",
            "/Applications/Chromium.app/Contents/MacOS/Chromium",
        ]

        all_paths = windows_paths + linux_paths + mac_paths

        for path in all_paths:
            if os.path.exists(path):
                self.chrome_path = path
                return

        # PATH에서 찾기
        for cmd in ["google-chrome", "google-chrome-stable", "chromium", "chromium-browser", "chrome"]:
            try:
                # Windows는 'where', Linux/Mac은 'which' 사용
                which_cmd = "where" if os.name == 'nt' else "which"
                result = subprocess.run([which_cmd, cmd], capture_output=True, text=True)
                if result.returncode == 0 and result.stdout.strip():
                    # Windows 'where'는 여러 줄 반환 가능, 첫 번째만 사용
                    self.chrome_path = result.stdout.strip().split('\n')[0]
                    return
            except:
                pass

        self.chrome_path = None

    def is_running(self):
        """CDP 포트가 열려있는지 확인"""
        try:
            import requests
            response = requests.get(f"http://localhost:{self.port}/json", timeout=2)
            return response.status_code == 200
        except:
            return False

    def kill_existing(self):
        """기존 Chrome 디버깅 프로세스 종료"""
        try:
            if os.name == 'nt':  # Windows
                # 포트 사용하는 프로세스 찾아서 종료
                result = subprocess.run(
                    f'netstat -ano | findstr :{self.port}',
                    shell=True, capture_output=True, text=True
                )
                if result.stdout:
                    for line in result.stdout.strip().split('\n'):
                        parts = line.split()
                        if len(parts) >= 5:
                            pid = parts[-1]
                            subprocess.run(f'taskkill /F /PID {pid}', shell=True, capture_output=True)
            else:  # Linux/Mac
                subprocess.run(
                    f"pkill -f 'chrome.*--remote-debugging-port={self.port}'",
                    shell=True, capture_output=True
                )
                subprocess.run(f"fuser -k {self.port}/tcp", shell=True, capture_output=True)
            time.sleep(1)
            log(f"[Chrome] 기존 디버깅 프로세스 종료됨 (port={self.port})")
        except Exception as e:
            log(f"[Chrome] 기존 프로세스 종료 중 오류: {e}", "WARN")

    def launch(self, headless=True, force_restart=False):
        """Chrome 디버깅 모드로 실행"""
        if self.is_running():
            if force_restart:
                log("[Chrome] 기존 Chrome 종료 후 재시작...")
                self.kill_existing()
                time.sleep(1)
            else:
                log("[Chrome] 이미 실행 중")
                return True

        if not self.chrome_path:
            log("[Chrome] Chrome 실행 파일을 찾을 수 없음", "ERROR")
            return False

        # Chrome 실행 인자
        args = [
            self.chrome_path,
            f"--remote-debugging-port={self.port}",
            "--remote-allow-origins=*",  # WebSocket 403 에러 방지
            "--no-first-run",
            "--no-default-browser-check",
            "--disable-extensions",
            "--disable-popup-blocking",
            "--disable-translate",
            "--disable-background-networking",
            "--disable-sync",
            "--disable-default-apps",
            "--mute-audio",
            "--user-data-dir=" + os.path.join(os.path.expanduser("~"), ".chrome-cdp-debug"),
        ]

        if headless:
            args.append("--headless=new")

        try:
            # 백그라운드로 실행
            if os.name == 'nt':  # Windows
                self.process = subprocess.Popen(
                    args,
                    stdout=subprocess.DEVNULL,
                    stderr=subprocess.DEVNULL,
                    creationflags=subprocess.CREATE_NO_WINDOW
                )
            else:  # Linux/Mac
                self.process = subprocess.Popen(
                    args,
                    stdout=subprocess.DEVNULL,
                    stderr=subprocess.DEVNULL,
                    preexec_fn=os.setpgrp
                )

            # 시작 대기
            for _ in range(30):  # 최대 3초
                time.sleep(0.1)
                if self.is_running():
                    log(f"[Chrome] 실행 성공 (headless={headless}, port={self.port})")
                    return True

            log("[Chrome] 실행 타임아웃", "ERROR")
            return False

        except Exception as e:
            log(f"[Chrome] 실행 실패: {e}", "ERROR")
            return False

    def close(self):
        """Chrome 종료"""
        if self.process:
            try:
                self.process.terminate()
                self.process.wait(timeout=5)
                log("[Chrome] 종료됨")
            except:
                try:
                    self.process.kill()
                except:
                    pass
            self.process = None


# 전역 Chrome 인스턴스 (프로그램 종료시 자동 정리)
_chrome_launcher = None

def _cleanup_chrome():
    global _chrome_launcher
    if _chrome_launcher:
        _chrome_launcher.close()

atexit.register(_cleanup_chrome)


def log(message, level="INFO"):
    """로그 출력 (모든 레벨 콘솔 출력)"""
    import traceback as tb
    print(f"[{level}] {message}")

    # ERROR 레벨일 때 스택 트레이스도 출력
    if level == "ERROR":
        # 현재 예외가 있으면 출력
        import sys
        if sys.exc_info()[0] is not None:
            tb.print_exc()


def random_delay(min_sec, max_sec):
    delay = random.uniform(min_sec, max_sec)
    time.sleep(delay)
    return delay


# ============================================
# 모바일 브라우저 CDP (읽기 전용 - 요소 찾기만!)
# ============================================
class MobileCDP:
    """모바일 브라우저 CDP 연결 (읽기 전용)

    주의: 이 클래스는 요소 찾기와 좌표 확인만 합니다!
    실제 입력(탭, 스크롤)은 ADB로 해야 감지를 피할 수 있습니다.
    """

    def __init__(self, adb_address, browser="chrome"):
        from config import BROWSERS
        self.adb_address = adb_address
        self.browser = browser
        self.browser_info = BROWSERS.get(browser, BROWSERS["chrome"])
        self.port = self.browser_info.get("cdp_port", 9222)
        self.socket_name = self.browser_info.get("devtools_socket")
        self.ws = None
        self.msg_id = 0
        self.connected = False
        self.adb_path = ADB_CONFIG.get("adb_path", "adb")

    def setup_port_forwarding(self):
        """ADB 포트 포워딩 설정"""
        if not self.socket_name:
            log(f"[MobileCDP] {self.browser}는 CDP를 지원하지 않음")
            return False

        try:
            # 기존 포워딩 제거
            cmd = f'{self.adb_path} -s {self.adb_address} forward --remove tcp:{self.port}'
            subprocess.run(cmd, shell=True, capture_output=True)

            # 새 포워딩 설정
            cmd = f'{self.adb_path} -s {self.adb_address} forward tcp:{self.port} localabstract:{self.socket_name}'
            result = subprocess.run(cmd, shell=True, capture_output=True, text=True)

            if result.returncode == 0:
                log(f"[MobileCDP] 포트 포워딩 설정: tcp:{self.port} → {self.socket_name}")
                return True
            else:
                log(f"[MobileCDP] 포트 포워딩 실패: {result.stderr}", "ERROR")
                return False
        except Exception as e:
            log(f"[MobileCDP] 포트 포워딩 오류: {e}", "ERROR")
            return False

    def connect(self):
        """모바일 브라우저 CDP 연결"""
        if not CDP_AVAILABLE:
            log("[MobileCDP] requests/websocket 모듈 없음")
            return False

        if not self.setup_port_forwarding():
            return False

        try:
            time.sleep(0.5)  # 포워딩 안정화 대기
            response = requests.get(f"http://localhost:{self.port}/json", timeout=5)
            tabs = response.json()

            ws_url = None
            for tab in tabs:
                if tab.get("type") == "page" and "naver" in tab.get("url", "").lower():
                    ws_url = tab["webSocketDebuggerUrl"]
                    break

            # 네이버 탭 없으면 첫 번째 페이지 탭 사용
            if not ws_url:
                for tab in tabs:
                    if tab.get("type") == "page":
                        ws_url = tab["webSocketDebuggerUrl"]
                        break

            if not ws_url:
                log("[MobileCDP] 탭을 찾을 수 없음")
                return False

            # Origin 헤더 없이 연결 시도 (CORS 우회)
            self.ws = websocket.create_connection(
                ws_url,
                timeout=10,
                suppress_origin=True
            )
            self.connected = True
            log(f"[MobileCDP] {self.browser} 브라우저 연결 성공!")
            return True

        except Exception as e:
            log(f"[MobileCDP] 연결 실패: {e}", "ERROR")
            return False

    def disconnect(self):
        """연결 종료"""
        if self.ws:
            try:
                self.ws.close()
            except:
                pass
        self.ws = None
        self.connected = False

    def send(self, method, params=None, timeout=10):
        """CDP 명령 전송 (읽기 전용 명령만!)"""
        if not self.connected:
            return {}

        self.msg_id += 1
        msg = {"id": self.msg_id, "method": method}
        if params:
            msg["params"] = params
        self.ws.send(json.dumps(msg))

        start_time = time.time()
        self.ws.settimeout(1.0)

        while (time.time() - start_time) < timeout:
            try:
                response = json.loads(self.ws.recv())
                if "id" in response and response["id"] == self.msg_id:
                    return response.get("result", {})
            except websocket.WebSocketTimeoutException:
                continue
            except Exception as e:
                log(f"[MobileCDP] 수신 오류: {e}", "ERROR")
                return {}

        return {}

    def find_element_by_text(self, text, tag="*", viewport_only=True, exact_match=False):
        """텍스트로 요소 찾기 → 좌표 반환 (읽기 전용!)

        Args:
            text: 찾을 텍스트
            tag: 태그 필터 (기본: 모든 태그)
            viewport_only: True면 현재 뷰포트 안에 있는 요소만 반환
            exact_match: True면 정확한 텍스트 매칭 (부모 요소 제외)

        Returns:
            dict: {"found": True, "x": 360, "y": 500, "text": "...", "in_viewport": True}
        """
        if not self.connected:
            return {"found": False}

        try:
            # JavaScript로 요소 찾기 (DOM 읽기만 - 감지 불가)
            # PC CDP와 동일한 필터 적용: 텍스트 길이 < 50, 높이 < 150
            # exact_match: 정확한 매칭으로 부모 컨테이너 매칭 방지
            viewport_check = "rect.top > 0 && rect.top < viewportHeight &&" if viewport_only else ""
            match_condition = f"txt === '{text}'" if exact_match else f"txt.includes('{text}') && txt.length < 50"
            js_code = f'''
            (function() {{
                var elements = document.querySelectorAll('*');
                var viewportHeight = window.innerHeight;
                var candidates = [];

                for (var el of elements) {{
                    var txt = el.textContent ? el.textContent.trim() : '';
                    if ({match_condition}) {{
                        // 가시성 체크: 숨겨진 요소 제외
                        var style = window.getComputedStyle(el);
                        if (style.display === 'none' || style.visibility === 'hidden' || style.opacity === '0') {{
                            continue;
                        }}
                        // offsetParent가 null이면 숨겨진 요소 (fixed 제외)
                        if (el.offsetParent === null && style.position !== 'fixed') {{
                            continue;
                        }}

                        var rect = el.getBoundingClientRect();
                        // 클릭 가능한 요소인지 확인
                        var isClickable = el.tagName === 'A' || el.tagName === 'BUTTON' ||
                                        el.onclick !== null ||
                                        style.cursor === 'pointer';
                        if (rect.width > 50 && rect.height > 0 && rect.height < 150 && {viewport_check} true) {{
                            // 우선순위: A > BUTTON > 기타 clickable > DIV
                            var priority = 0;
                            if (el.tagName === 'A') priority = 100;
                            else if (el.tagName === 'BUTTON') priority = 90;
                            else if (isClickable) priority = 50;
                            else priority = 10;

                            candidates.push({{
                                priority: priority,
                                found: true,
                                x: Math.round(rect.left + rect.width / 2),
                                y: Math.round(rect.top + rect.height / 2),
                                width: rect.width,
                                height: rect.height,
                                text: txt.substring(0, 50),
                                in_viewport: rect.top > 0 && rect.bottom < viewportHeight,
                                viewport_height: viewportHeight,
                                clickable: isClickable,
                                tag: el.tagName
                            }});
                        }}
                    }}
                }}

                // 우선순위가 높은 요소 반환 (A > BUTTON > clickable > DIV)
                if (candidates.length > 0) {{
                    candidates.sort(function(a, b) {{ return b.priority - a.priority; }});
                    return candidates[0];
                }}
                return {{found: false}};
            }})()
            '''

            result = self.send("Runtime.evaluate", {
                "expression": js_code,
                "returnByValue": True
            })

            if result and "result" in result:
                value = result["result"].get("value", {})
                if value.get("found"):
                    tag = value.get('tag', '?')
                    clickable = value.get('clickable', False)
                    log(f"[MobileCDP] 요소 발견: '{text}' → ({value['x']}, {value['y']}) <{tag}> clickable={clickable}")
                    return value

            return {"found": False}

        except Exception as e:
            log(f"[MobileCDP] 요소 찾기 오류: {e}", "ERROR")
            return {"found": False}

    def debug_find_all_elements(self, text):
        """디버그: 텍스트와 매칭되는 모든 요소 출력"""
        if not self.connected:
            return []

        try:
            js_code = f'''
            (function() {{
                var results = [];
                var elements = document.querySelectorAll('*');
                var viewportHeight = window.innerHeight;
                var idx = 0;
                for (var el of elements) {{
                    var txt = el.textContent ? el.textContent.trim() : '';
                    // 정확한 매칭 또는 포함 매칭
                    if (txt === '{text}' || (txt.includes('{text}') && txt.length < 100)) {{
                        var style = window.getComputedStyle(el);
                        var rect = el.getBoundingClientRect();
                        var isClickable = el.tagName === 'A' || el.tagName === 'BUTTON' ||
                                        el.onclick !== null || style.cursor === 'pointer';

                        results.push({{
                            idx: idx++,
                            tag: el.tagName,
                            id: el.id || '',
                            className: el.className ? el.className.substring(0, 50) : '',
                            x: Math.round(rect.left + rect.width / 2),
                            y: Math.round(rect.top + rect.height / 2),
                            width: Math.round(rect.width),
                            height: Math.round(rect.height),
                            text: txt.substring(0, 30),
                            textLen: txt.length,
                            exactMatch: txt === '{text}',
                            clickable: isClickable,
                            visible: style.display !== 'none' && style.visibility !== 'hidden' && style.opacity !== '0',
                            inViewport: rect.top > 0 && rect.bottom < viewportHeight
                        }});
                    }}
                }}
                return {{viewportHeight: viewportHeight, count: results.length, elements: results}};
            }})()
            '''

            result = self.send("Runtime.evaluate", {
                "expression": js_code,
                "returnByValue": True
            })

            if result and "result" in result:
                data = result["result"].get("value", {})
                log(f"[DEBUG] viewport={data.get('viewportHeight')}, 매칭 요소 {data.get('count')}개:")
                for el in data.get("elements", []):
                    mark = "✓" if el.get("exactMatch") else " "
                    vis = "V" if el.get("visible") else "H"
                    vp = "IN" if el.get("inViewport") else "OUT"
                    click = "C" if el.get("clickable") else "-"
                    log(f"  [{mark}] #{el['idx']} <{el['tag']}> ({el['x']},{el['y']}) {el['width']}x{el['height']} [{vis}|{vp}|{click}] txt={el['textLen']}ch id={el.get('id','')[:15]} class={el.get('className','')[:20]}")
                return data.get("elements", [])

            return []
        except Exception as e:
            log(f"[DEBUG] 오류: {e}", "ERROR")
            return []

    def find_link_by_domain(self, domain, viewport_only=True):
        """도메인으로 링크 찾기 → 좌표 반환 (읽기 전용!)

        Args:
            domain: 찾을 도메인
            viewport_only: True면 현재 뷰포트 안에 있는 링크만 반환

        Returns:
            dict: {"found": True, "x": 360, "y": 500, "href": "..."}
        """
        if not self.connected:
            return {"found": False}

        try:
            # 도메인 포함된 링크 찾기
            viewport_check = "rect.top > 0 && rect.top < viewportHeight &&" if viewport_only else ""
            js_code = f'''
            (function() {{
                var links = document.querySelectorAll('a[href*="{domain}"]');
                var viewportHeight = window.innerHeight;
                for (var link of links) {{
                    var rect = link.getBoundingClientRect();
                    if (rect.width > 0 && rect.height > 0 && {viewport_check} true) {{
                        return {{
                            found: true,
                            x: Math.round(rect.left + rect.width / 2),
                            y: Math.round(rect.top + rect.height / 2),
                            width: rect.width,
                            height: rect.height,
                            href: link.href,
                            text: link.textContent.substring(0, 50)
                        }};
                    }}
                }}
                return {{found: false}};
            }})()
            '''

            result = self.send("Runtime.evaluate", {
                "expression": js_code,
                "returnByValue": True
            })

            if result and "result" in result:
                value = result["result"].get("value", {})
                if value.get("found"):
                    log(f"[MobileCDP] 링크 발견: {domain} → ({value['x']}, {value['y']})")
                    return value

            return {"found": False}

        except Exception as e:
            log(f"[MobileCDP] 링크 찾기 오류: {e}", "ERROR")
            return {"found": False}

    def find_all_links_by_domain(self, domain, viewport_only=True):
        """도메인으로 모든 링크 찾기 → 좌표 목록 반환 (읽기 전용!)

        Args:
            domain: 찾을 도메인
            viewport_only: True면 현재 뷰포트 안에 있는 링크만 반환

        Returns:
            list: [{"found": True, "x": 360, "y": 500, "href": "..."}, ...]
        """
        if not self.connected:
            return []

        try:
            viewport_check = "rect.top > 0 && rect.top < viewportHeight &&" if viewport_only else ""
            js_code = f'''
            (function() {{
                var links = document.querySelectorAll('a[href*="{domain}"]');
                var viewportHeight = window.innerHeight;
                var results = [];
                for (var link of links) {{
                    var rect = link.getBoundingClientRect();
                    if (rect.width > 0 && rect.height > 0 && {viewport_check} true) {{
                        results.push({{
                            found: true,
                            x: Math.round(rect.left + rect.width / 2),
                            y: Math.round(rect.top + rect.height / 2),
                            width: rect.width,
                            height: rect.height,
                            href: link.href,
                            text: link.textContent.substring(0, 50),
                            center_x: Math.round(rect.left + rect.width / 2),
                            center_y: Math.round(rect.top + rect.height / 2)
                        }});
                    }}
                }}
                return results;
            }})()
            '''

            result = self.send("Runtime.evaluate", {
                "expression": js_code,
                "returnByValue": True
            })

            if result and "result" in result:
                links = result["result"].get("value", [])
                if links:
                    log(f"[MobileCDP] 도메인 링크 {len(links)}개 발견: {domain}")
                    return links

            return []

        except Exception as e:
            log(f"[MobileCDP] 링크 목록 오류: {e}", "ERROR")
            return []

    def get_scroll_position(self):
        """현재 스크롤 위치 확인 (읽기 전용!)"""
        if not self.connected:
            return 0

        try:
            result = self.send("Runtime.evaluate", {
                "expression": "window.scrollY || document.documentElement.scrollTop",
                "returnByValue": True
            })

            if result and "result" in result:
                return result["result"].get("value", 0)
            return 0
        except:
            return 0

    def get_page_height(self):
        """페이지 전체 높이 (읽기 전용!)"""
        if not self.connected:
            return 0

        try:
            result = self.send("Runtime.evaluate", {
                "expression": "document.documentElement.scrollHeight",
                "returnByValue": True
            })

            if result and "result" in result:
                return result["result"].get("value", 0)
            return 0
        except:
            return 0

    def get_element_scroll_info(self, text):
        """요소까지 스크롤하는데 필요한 정보 계산 (읽기 전용!)

        Returns:
            dict: {
                "found": True,
                "current_scroll": 1234,  # 현재 scrollY
                "element_viewport_y": 500,  # 요소의 뷰포트 상대 Y
                "element_absolute_y": 1734,  # 요소의 문서 절대 Y
                "scroll_needed": 800,  # 뷰포트 중앙에 오려면 필요한 스크롤
                "viewport_height": 800
            }
        """
        if not self.connected:
            return {"found": False}

        try:
            js_code = f'''
            (function() {{
                var elements = document.querySelectorAll('*');
                for (var el of elements) {{
                    if (el.textContent && el.textContent.includes('{text}')) {{
                        var rect = el.getBoundingClientRect();
                        if (rect.width > 0 && rect.height > 0) {{
                            var scrollY = window.scrollY || document.documentElement.scrollTop;
                            var viewportHeight = window.innerHeight;
                            var elementViewportY = rect.top + rect.height / 2;
                            var elementAbsoluteY = scrollY + elementViewportY;
                            var viewportCenter = viewportHeight / 2;
                            var scrollNeeded = elementAbsoluteY - scrollY - viewportCenter;

                            return {{
                                found: true,
                                current_scroll: Math.round(scrollY),
                                element_viewport_y: Math.round(elementViewportY),
                                element_absolute_y: Math.round(elementAbsoluteY),
                                scroll_needed: Math.round(scrollNeeded),
                                viewport_height: Math.round(viewportHeight),
                                text: el.textContent.substring(0, 30)
                            }};
                        }}
                    }}
                }}
                return {{found: false}};
            }})()
            '''

            result = self.send("Runtime.evaluate", {
                "expression": js_code,
                "returnByValue": True
            })

            if result and "result" in result:
                value = result["result"].get("value", {})
                if value.get("found"):
                    log(f"[MobileCDP] 스크롤 정보: 현재={value['current_scroll']}, "
                        f"요소절대위치={value['element_absolute_y']}, "
                        f"필요스크롤={value['scroll_needed']}")
                    return value

            return {"found": False}

        except Exception as e:
            log(f"[MobileCDP] 스크롤 정보 오류: {e}", "ERROR")
            return {"found": False}


# ============================================
# CDP 스크롤 계산기 (정확도 향상 버전)
# ============================================
class CDPCalculator:
    """PC 크롬에서 스크롤 위치를 미리 계산 (모바일 뷰포트 정확히 반영)"""

    def __init__(self, port=None):
        self.port = port or CDP_CONFIG.get("port", 9222)
        self.ws = None
        self.msg_id = 0
        self.connected = False
        self.debug = DEBUG_CONFIG.get("cdp_debug", False)

        # 뷰포트 정보 (계산 후 저장)
        self.screen_width = 0
        self.screen_height = 0
        self.effective_viewport_height = 0  # 실제 스크롤 가능 영역

    def _debug_log(self, message):
        """디버그 로그"""
        if self.debug:
            log(f"[CDP-DEBUG] {message}")

    def connect(self):
        """CDP 연결"""
        if not CDP_AVAILABLE:
            log("[CDP] requests/websocket 모듈 없음, CDP 계산 비활성화")
            return False

        try:
            response = requests.get(f"http://localhost:{self.port}/json", timeout=3)
            tabs = response.json()

            ws_url = None
            for tab in tabs:
                if tab.get("type") == "page":
                    ws_url = tab["webSocketDebuggerUrl"]
                    break

            if not ws_url:
                log("[CDP] 탭을 찾을 수 없음")
                return False

            self.ws = websocket.create_connection(ws_url, timeout=5)
            self.connected = True
            log("[CDP] 연결 성공!")
            return True

        except Exception as e:
            log(f"[CDP] 연결 실패: {e}", "ERROR")
            log("[CDP] 크롬이 --remote-debugging-port=9222 로 실행되었는지 확인")
            return False

    def send(self, method, params=None, timeout=30):
        """CDP 명령 전송

        Args:
            method: CDP 메서드명
            params: 파라미터
            timeout: 응답 대기 시간 (초)
        """
        if not self.connected:
            return {}

        self.msg_id += 1
        msg = {"id": self.msg_id, "method": method}
        if params:
            msg["params"] = params
        self.ws.send(json.dumps(msg))

        # 타임아웃까지 응답 대기
        start_time = time.time()
        self.ws.settimeout(1.0)  # recv()당 1초 타임아웃

        while (time.time() - start_time) < timeout:
            try:
                response = json.loads(self.ws.recv())
                # 응답 메시지인 경우 (이벤트는 id가 없음)
                if "id" in response and response["id"] == self.msg_id:
                    return response.get("result", {})
                # 이벤트 메시지는 무시하고 계속 대기
            except websocket.WebSocketTimeoutException:
                # 타임아웃은 정상, 계속 대기
                continue
            except Exception as e:
                log(f"[CDP] WebSocket 수신 오류: {e}", "ERROR")
                return {}

        log(f"[CDP] 응답 대기 타임아웃 ({method})", "WARN")
        return {}

    def set_viewport(self, screen_width, screen_height):
        """뷰포트 크기 설정 (실제 모바일 브라우저 환경 반영)"""
        self.screen_width = screen_width
        self.screen_height = screen_height

        # 실제 뷰포트 계산 (상태바, 주소창 제외)
        status_bar = CDP_CONFIG.get("status_bar_height", 50)
        address_bar = CDP_CONFIG.get("address_bar_height", 56)
        nav_bar = CDP_CONFIG.get("nav_bar_height", 0)

        # 실제 브라우저 뷰포트 높이
        self.effective_viewport_height = screen_height - status_bar - address_bar - nav_bar

        self._debug_log(f"화면: {screen_width}x{screen_height}")
        self._debug_log(f"상태바: {status_bar}, 주소창: {address_bar}, 네비바: {nav_bar}")
        self._debug_log(f"실제 뷰포트: {self.effective_viewport_height}px")

        # Page, Network 도메인 활성화
        self.send("Page.enable", {})
        self.send("Network.enable", {})

        # UA 모바일로 설정
        self.send("Emulation.setUserAgentOverride", {
            "userAgent": "Mozilla/5.0 (Linux; Android 14; SM-S928N) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0.0.0 Mobile Safari/537.36",
            "acceptLanguage": "ko-KR,ko;q=0.9",
            "platform": "Linux armv81"
        })

        # CDP 뷰포트 = 실제 브라우저 뷰포트와 동일하게 설정
        self.send("Emulation.setDeviceMetricsOverride", {
            "width": screen_width,
            "height": self.effective_viewport_height,
            "deviceScaleFactor": 2,
            "mobile": True,
            "screenWidth": screen_width,
            "screenHeight": screen_height
        })

        log(f"[CDP] 뷰포트 설정: {screen_width}x{self.effective_viewport_height} (실제 브라우저 영역)")

    def navigate(self, url):
        """페이지 이동"""
        wait_time = CDP_CONFIG.get("page_load_wait", 3.0)
        self.send("Page.navigate", {"url": url})
        time.sleep(wait_time)

    def evaluate(self, expression):
        """JS 실행"""
        result = self.send("Runtime.evaluate", {
            "expression": expression,
            "returnByValue": True
        })
        return result.get("result", {}).get("value")

    def get_viewport_height(self):
        """실제 뷰포트 높이 (JS에서)"""
        return self.evaluate("window.innerHeight") or 0

    def get_scroll_height(self):
        """전체 문서 높이"""
        return self.evaluate("document.documentElement.scrollHeight") or 0

    def get_scroll_position(self):
        """현재 스크롤 위치"""
        return self.evaluate("window.scrollY") or 0

    def get_element_info(self, text, exact_match=False):
        """텍스트로 요소 찾기 (개선된 버전)

        Returns:
            dict: {found, y, screenY, height, clickable, elementType}
        """
        match_condition = f"txt === '{text}'" if exact_match else f"txt.includes('{text}') && txt.length < 50"

        js = f"""
        (function() {{
            const elements = [...document.querySelectorAll('*')];
            for (const el of elements) {{
                const txt = el.textContent.trim();
                if ({match_condition}) {{
                    const rect = el.getBoundingClientRect();
                    if (rect.height > 0 && rect.height < 150 && rect.width > 50) {{
                        // 클릭 가능한 요소인지 확인
                        const isClickable = el.tagName === 'A' || el.tagName === 'BUTTON' ||
                                          el.onclick !== null ||
                                          window.getComputedStyle(el).cursor === 'pointer';

                        return {{
                            found: true,
                            y: rect.top + window.scrollY,
                            screenY: rect.top,
                            height: rect.height,
                            width: rect.width,
                            centerX: rect.left + rect.width / 2,
                            centerY: rect.top + rect.height / 2,
                            clickable: isClickable,
                            elementType: el.tagName,
                            text: txt.substring(0, 50)
                        }};
                    }}
                }}
            }}
            return {{ found: false }};
        }})()
        """
        result = self.evaluate(js)
        if result and result.get("found"):
            self._debug_log(f"요소 발견: '{result.get('text', '')[:30]}' Y={result['y']:.0f}")
        return result

    def get_domain_info(self, domain):
        """도메인 링크 찾기 (cdp_touch_scroll_v4.py 방식)

        - sidecut.co.kr 지정 시: sidecut.co.kr만 매칭 (서브페이지 제외)
        - sidecut.co.kr/lessons 지정 시: 정확히 그 경로만 매칭
        - sublink 제외 (data-heatmap-target=".sublink")

        Returns:
            dict: {found, y, screenY, height, href, text}
        """
        # 경로 포함 여부 확인
        has_path = '/' in domain and not domain.endswith('/')
        base_domain = domain.split('/')[0]

        js = f"""
        (function() {{
            const targetDomain = "{domain}";
            const baseDomain = "{base_domain}";
            const hasPath = {"true" if has_path else "false"};
            const debugLogs = [];

            // 베이스 도메인이 포함된 모든 링크 찾기
            const allLinks = document.querySelectorAll('a[href*="' + baseDomain + '"]');
            debugLogs.push('[CDP] 총 ' + allLinks.length + '개 링크 발견 (base: ' + baseDomain + ')');

            for (const link of allLinks) {{
                const href = link.getAttribute('href');
                if (!href) continue;

                // sublink 제외 (서브링크는 위치 겹침 문제)
                const heatmapTarget = link.getAttribute('data-heatmap-target');
                if (heatmapTarget === '.sublink') {{
                    debugLogs.push('[CDP] 제외(sublink): ' + href.substring(0, 60));
                    continue;
                }}

                // 정확한 매칭 체크
                let isMatch = false;
                if (hasPath) {{
                    // 경로가 지정된 경우: 정확한 경로 매칭
                    if (href.endsWith(targetDomain) || href.endsWith(targetDomain + '/')) {{
                        isMatch = true;
                    }}
                }} else {{
                    // 경로가 없는 경우: 메인 도메인만 (서브링크 제외)
                    if (href.endsWith(targetDomain + '/') || href.endsWith(targetDomain)) {{
                        isMatch = true;
                    }}
                }}

                if (!isMatch) {{
                    debugLogs.push('[CDP] 제외(경로불일치): ' + href.substring(0, 60));
                    continue;
                }}

                // 웹사이트 영역 체크 (type-web 클래스 확인)
                let isWebArea = false;
                let parent = link.parentElement;
                while (parent) {{
                    if (parent.classList && parent.classList.contains('type-web')) {{
                        isWebArea = true;
                        break;
                    }}
                    if (parent.getAttribute && parent.getAttribute('data-sds-comp') === 'Profile') {{
                        isWebArea = true;
                        break;
                    }}
                    parent = parent.parentElement;
                }}

                const rect = link.getBoundingClientRect();
                if (rect.height > 0 && rect.width > 50) {{
                    debugLogs.push('[CDP] ✓ 매칭! href=' + href.substring(0, 60) + ' Y=' + (rect.top + window.scrollY).toFixed(0));
                    return {{
                        found: true,
                        y: rect.top + window.scrollY,
                        screenY: rect.top,
                        height: rect.height,
                        width: rect.width,
                        centerX: rect.left + rect.width / 2,
                        centerY: rect.top + rect.height / 2,
                        href: link.href,
                        text: link.textContent.trim().substring(0, 50),
                        isWebArea: isWebArea,
                        debugLogs: debugLogs
                    }};
                }}
            }}

            return {{ found: false, debugLogs: debugLogs }};
        }})()
        """
        result = self.evaluate(js)
        # 디버그 로그 출력
        if result and result.get("debugLogs"):
            for debug_log in result["debugLogs"]:
                log(debug_log)
        if result and result.get("found"):
            log(f"[CDP] 도메인 발견: '{result.get('text', '')[:30]}' href={result.get('href', '')[:50]}")
        else:
            log(f"[CDP] 도메인 못 찾음: {domain}")
        return result

    def scroll_to(self, y):
        """스크롤 이동"""
        self.evaluate(f"window.scrollTo(0, {y})")
        time.sleep(CDP_CONFIG.get("after_scroll_wait", 0.3))

    def click(self, x, y):
        """터치 클릭"""
        self.send("Input.dispatchTouchEvent", {
            "type": "touchStart",
            "touchPoints": [{"x": x, "y": y, "radiusX": 5, "radiusY": 5, "force": 0.5}]
        })
        time.sleep(0.05)
        self.send("Input.dispatchTouchEvent", {
            "type": "touchEnd",
            "touchPoints": []
        })

    def _calculate_scroll_count(self, element_y, target_position, scroll_distance):
        """스크롤 횟수 계산 (정확도 향상)

        Args:
            element_y: 요소의 절대 Y 좌표 (문서 기준)
            target_position: 화면에서 요소가 위치할 비율 (0.0~1.0)
            scroll_distance: ADB 스크롤 1회 거리 (픽셀)

        Returns:
            int: 필요한 스크롤 횟수
        """
        # 타겟 위치 (화면에서 몇 번째 픽셀에 요소가 올지)
        target_screen_y = self.effective_viewport_height * target_position

        # 필요한 스크롤 양 (픽셀)
        scroll_needed = element_y - target_screen_y

        # 스크롤 보정 계수 적용
        calibration = CDP_CONFIG.get("scroll_calibration", 0.85)
        effective_scroll = scroll_distance * calibration

        # 스크롤 횟수 계산
        if effective_scroll <= 0:
            return 0

        raw_count = scroll_needed / effective_scroll

        # 여유 스크롤 계산 - 도메인 찾기는 여유 최소화
        margin_ratio = CDP_CONFIG.get("margin_scroll_ratio", 0.1)
        margin_min = CDP_CONFIG.get("margin_scroll_min", 1)
        margin_max = CDP_CONFIG.get("margin_scroll_max", 5)

        margin = int(raw_count * margin_ratio)
        margin = max(margin_min, min(margin, margin_max))

        final_count = max(0, int(raw_count) + margin)

        # 디버그 로그 (항상 출력)
        log(f"[CDP-계산] 요소Y={element_y:.0f}, 뷰포트={self.effective_viewport_height}, 타겟비율={target_position}")
        log(f"[CDP-계산] 타겟Y={target_screen_y:.0f}, 필요스크롤={scroll_needed:.0f}px")
        log(f"[CDP-계산] 스크롤거리={scroll_distance}, 보정={calibration}, 유효거리={effective_scroll:.0f}px")
        log(f"[CDP-계산] 기본횟수={raw_count:.1f}, 여유={margin}, 최종={final_count}회")

        return final_count

    def _calculate_scroll_count_no_margin(self, element_y, target_position, scroll_distance):
        """도메인 찾기용 스크롤 횟수 계산 (마진 없음, 보정 없음, 오버슈팅 방지)

        보상 스크롤은 400px 기준으로 동작하므로 calibration 적용하면 오버슈팅됨.
        예: 1593px 필요 → 340px 기준 4.68회 → 5회 → 2000px 스와이프 → 오버슈팅

        Args:
            element_y: 요소의 절대 Y 좌표 (문서 기준)
            target_position: 화면에서 요소가 위치할 비율 (0.0~1.0)
            scroll_distance: ADB 스크롤 1회 거리 (픽셀)

        Returns:
            int: 필요한 스크롤 횟수
        """
        # 타겟 위치
        target_screen_y = self.effective_viewport_height * target_position

        # 필요한 스크롤 양
        scroll_needed = element_y - target_screen_y

        # 보정계수 없이 계산 (보상 스크롤은 400px 기준이므로)
        if scroll_distance <= 0:
            return 0

        raw_count = scroll_needed / scroll_distance

        # 마진 없이 내림 (오버슈팅보다 언더슈팅이 나음)
        final_count = max(0, int(raw_count))

        # 디버그 로그
        log(f"[CDP-계산-도메인] 요소Y={element_y:.0f}, 뷰포트={self.effective_viewport_height}, 타겟비율={target_position}")
        log(f"[CDP-계산-도메인] 타겟Y={target_screen_y:.0f}, 필요스크롤={scroll_needed:.0f}px")
        log(f"[CDP-계산-도메인] 스크롤거리={scroll_distance} (보정없음)")
        log(f"[CDP-계산-도메인] 기본횟수={raw_count:.1f}, 마진=0, 최종={final_count}회 (내림)")

        return final_count

    def calculate_scroll_info(self, keyword, domain, screen_width, screen_height):
        """검색어로 스크롤 정보 미리 계산 (정확도 향상 버전)

        Returns:
            dict: {
                more_scroll_count: "검색결과 더보기"까지 스크롤 횟수,
                more_element_y: "검색결과 더보기" Y좌표,
                domain_scroll_count: 도메인까지 스크롤 횟수 (-1이면 못 찾음),
                domain_element_y: 도메인 Y좌표,
                domain_page: 도메인이 있는 페이지 번호,
                viewport_height: 실제 뷰포트 높이,
                scroll_distance: ADB 스크롤 1회 거리,
                calculated: 계산 성공 여부
            }
        """
        log("[CDP] 스크롤 위치 계산 시작...")

        result = {
            "more_scroll_count": 0,
            "more_element_y": 0,
            "domain_scroll_count": -1,
            "domain_element_y": 0,
            "domain_page": 1,
            "viewport_height": 0,
            "scroll_distance": 0,
            "calculated": False
        }

        if not self.connected:
            log("[CDP] 연결 안 됨")
            return result

        try:
            # 뷰포트 설정
            self.set_viewport(screen_width, screen_height)
            result["viewport_height"] = self.effective_viewport_height

            # ADB 스크롤 거리
            scroll_distance = SCROLL_CONFIG.get("distance", 400)
            result["scroll_distance"] = scroll_distance

            # 1. 통합 검색 페이지 이동
            import urllib.parse
            encoded_keyword = urllib.parse.quote(keyword)
            search_url = f"https://m.search.naver.com/search.naver?query={encoded_keyword}"

            log(f"[CDP] 통합 페이지 이동: {keyword}")
            self.navigate(search_url)

            # CDP 뷰포트 확인
            cdp_viewport = self.get_viewport_height()
            doc_height = self.get_scroll_height()
            self._debug_log(f"CDP 뷰포트: {cdp_viewport}px, 문서높이: {doc_height}px")

            # "검색결과 더보기" 위치 계산
            more_info = self.get_element_info("검색결과 더보기")

            if more_info and more_info.get("found"):
                more_y = more_info["y"]
                result["more_element_y"] = more_y

                target_pos = CDP_CONFIG.get("more_target_position", 0.4)
                result["more_scroll_count"] = self._calculate_scroll_count(
                    more_y, target_pos, scroll_distance
                )

                log(f"[CDP] '검색결과 더보기' Y={more_y:.0f}, 스크롤={result['more_scroll_count']}회")
            else:
                log("[CDP] '검색결과 더보기' 못 찾음, 기본값 사용")
                result["more_scroll_count"] = 30

            # 2. 더보기 페이지에서 도메인 찾기
            more_page_url = f"https://m.search.naver.com/search.naver?where=m_web&query={encoded_keyword}&sm=mtb_pge&start=1"

            log(f"[CDP] 더보기 페이지 이동...")
            self.navigate(more_page_url)

            # 도메인 위치 계산 (최대 5페이지까지 탐색)
            max_pages = 5
            for page in range(1, max_pages + 1):
                if page > 1:
                    # 다음 페이지로 이동
                    page_url = f"https://m.search.naver.com/search.naver?where=m_web&query={encoded_keyword}&sm=mtb_pge&start={1 + (page-1)*10}"
                    self._debug_log(f"페이지 {page} 이동...")
                    self.navigate(page_url)

                domain_info = self.get_domain_info(domain)

                if domain_info and domain_info.get("found"):
                    domain_y = domain_info["y"]
                    result["domain_element_y"] = domain_y
                    result["domain_page"] = page

                    # 디버그: 어떤 href를 찾았는지 출력
                    log(f"[CDP] 찾은 href: {domain_info.get('href', 'N/A')[:70]}")
                    log(f"[CDP] 찾은 텍스트: {domain_info.get('text', 'N/A')[:50]}")

                    target_pos = CDP_CONFIG.get("domain_target_position", 0.35)
                    # 도메인은 마진 없이 계산 (오버슈팅 방지)
                    result["domain_scroll_count"] = self._calculate_scroll_count_no_margin(
                        domain_y, target_pos, scroll_distance
                    )

                    log(f"[CDP] '{domain}' 발견! 페이지={page}, Y={domain_y:.0f}, 스크롤={result['domain_scroll_count']}회")
                    break
            else:
                log(f"[CDP] '{domain}' {max_pages}페이지 내 못 찾음")
                result["domain_scroll_count"] = -1

            result["calculated"] = True
            log("[CDP] 계산 완료!")

        except Exception as e:
            log(f"[CDP] 계산 오류: {e}")
            import traceback
            self._debug_log(traceback.format_exc())

        return result

    def close(self):
        """연결 종료"""
        if self.ws:
            try:
                self.ws.close()
            except:
                pass
            self.connected = False
            log("[CDP] 연결 종료")


class ADBController:
    def __init__(self, phone_config):
        self.adb_path = ADB_CONFIG["adb_path"]
        self.adb_address = phone_config["adb_address"]
        self.login_code = phone_config.get("login_code", "")
        self.screen_width = phone_config.get("screen_width", 720)
        self.screen_height = phone_config.get("screen_height", 1440)
        self._last_xml = None
        self._last_xml_time = 0
        self._scroll_debt = 0  # 보상 스크롤용 오차 누적
    
    def run_adb(self, command, timeout=None):
        timeout = timeout or ADB_CONFIG["command_timeout"]
        full_command = f'{self.adb_path} -s {self.adb_address} {command}'
        try:
            result = subprocess.run(
                full_command, shell=True, capture_output=True,
                timeout=timeout, encoding='utf-8', errors='ignore'
            )
            return result.stdout.strip() if result.stdout else ""
        except Exception as e:
            log(f"ADB 실행 실패: {e}", "ERROR")
            return None
    
    def shell(self, command):
        return self.run_adb(f'shell {command}')
    
    # ──────────────────────────────────────────
    # 연결
    # ──────────────────────────────────────────
    def connect(self):
        log(f"ADB 연결 시도: {self.adb_address}")
        result = self.run_adb(f"connect {self.adb_address}")

        if result and ("connected" in result.lower() or "already" in result.lower()):
            log("ADB 연결 성공!")
            if self.login_code:
                log(f"GeeLark 로그인: {self.login_code}")
                self.shell(f"glogin {self.login_code}")
                time.sleep(1)

            # 실제 화면 크기 자동 감지
            self._detect_screen_size()
            return True
        log(f"ADB 연결 실패: {result}", "ERROR")
        return False

    def _detect_screen_size(self):
        """ADB에서 실제 화면 크기 자동 감지"""
        try:
            result = self.shell("wm size")
            if result:
                # "Physical size: 720x1440" 형식 파싱
                match = re.search(r'(\d+)x(\d+)', result)
                if match:
                    width = int(match.group(1))
                    height = int(match.group(2))
                    self.screen_width = width
                    self.screen_height = height
                    log(f"[ADB] 화면 크기 감지: {width}x{height}")
                    return
            log(f"[ADB] 화면 크기 감지 실패, 기본값 사용: {self.screen_width}x{self.screen_height}", "WARN")
        except Exception as e:
            log(f"[ADB] 화면 크기 감지 오류: {e}", "ERROR")

    # ──────────────────────────────────────────
    # 스크린샷 + OCR
    # ──────────────────────────────────────────
    def take_screenshot(self):
        """스크린샷을 찍고 PIL Image로 반환"""
        try:
            # 스크린샷을 바이너리로 직접 가져오기
            cmd = f'{self.adb_path} -s {self.adb_address} exec-out screencap -p'
            result = subprocess.run(cmd, shell=True, capture_output=True, timeout=10)
            if result.returncode == 0 and result.stdout:
                image = Image.open(io.BytesIO(result.stdout))
                log(f"[OCR] 스크린샷 촬영: {image.size}")
                return image
            log("[OCR] 스크린샷 실패", "ERROR")
            return None
        except Exception as e:
            log(f"[OCR] 스크린샷 오류: {e}", "ERROR")
            return None

    def find_template(self, template_path, threshold=0.7, do_click=False):
        """템플릿 이미지를 화면에서 찾기

        Args:
            template_path: 템플릿 이미지 경로
            threshold: 유사도 임계값 (0.0~1.0, 기본 0.7)
            do_click: True면 찾은 위치 클릭

        Returns:
            dict: {"found": True, "x": cx, "y": cy, "conf": 0.95, "bounds": (x1,y1,x2,y2)}
        """
        if not TEMPLATE_MATCHING_AVAILABLE:
            log("[TEMPLATE] opencv 미설치", "ERROR")
            return {"found": False}

        try:
            # 1. 템플릿 로드
            template = cv2.imread(template_path)
            if template is None:
                log(f"[TEMPLATE] 파일 없음: {template_path}", "ERROR")
                return {"found": False}
            h, w = template.shape[:2]
            log(f"[TEMPLATE] 템플릿 로드: {w}x{h}")

            # 2. 스크린샷 촬영 (ADB exec-out screencap -p → numpy array)
            log("[TEMPLATE] 스크린샷 촬영...")
            cmd = f'{self.adb_path} -s {self.adb_address} exec-out screencap -p'
            result = subprocess.run(cmd, shell=True, capture_output=True, timeout=10)
            if result.returncode != 0 or not result.stdout:
                log("[TEMPLATE] 스크린샷 실패", "ERROR")
                return {"found": False}

            img_array = np.frombuffer(result.stdout, dtype=np.uint8)
            screenshot = cv2.imdecode(img_array, cv2.IMREAD_COLOR)
            if screenshot is None:
                log("[TEMPLATE] 이미지 디코딩 실패", "ERROR")
                return {"found": False}
            log(f"[TEMPLATE] 스크린샷: {screenshot.shape[1]}x{screenshot.shape[0]}")

            # 3. 템플릿 매칭
            log("[TEMPLATE] 매칭 중...")
            match_result = cv2.matchTemplate(screenshot, template, cv2.TM_CCOEFF_NORMED)
            min_val, max_val, min_loc, max_loc = cv2.minMaxLoc(match_result)
            log(f"[TEMPLATE] 유사도: {max_val:.3f} (임계값: {threshold})")

            # 4. 결과 판정
            if max_val >= threshold:
                x1, y1 = max_loc[0], max_loc[1]
                x2, y2 = x1 + w, y1 + h
                cx = x1 + w // 2
                cy = y1 + h // 2
                log(f"[TEMPLATE] 발견! 영역: ({x1},{y1})-({x2},{y2}), 중심: ({cx},{cy})")

                if do_click:
                    # 템플릿 영역 안에서 랜덤 클릭 (가장자리 10% 제외)
                    margin_x = int(w * 0.1)
                    margin_y = int(h * 0.1)
                    rand_x = random.randint(x1 + margin_x, x2 - margin_x)
                    rand_y = random.randint(y1 + margin_y, y2 - margin_y)
                    log(f"[TEMPLATE] 랜덤 클릭: ({rand_x}, {rand_y})")
                    time.sleep(0.3)
                    self.tap(rand_x, rand_y, randomize=False)  # 이미 랜덤화됨

                return {
                    "found": True,
                    "x": cx,
                    "y": cy,
                    "center_x": cx,
                    "center_y": cy,
                    "width": w,
                    "height": h,
                    "bounds": (x1, y1, x2, y2),
                    "conf": max_val,
                    "source": "template"
                }
            else:
                log(f"[TEMPLATE] 못 찾음 ({max_val:.3f} < {threshold})")
                return {"found": False}

        except Exception as e:
            log(f"[TEMPLATE] 오류: {e}", "ERROR")
            import traceback
            traceback.print_exc()
            return {"found": False}

    # ──────────────────────────────────────────
    # 터치
    # ──────────────────────────────────────────
    def tap(self, x, y, randomize=True):
        if randomize:
            x += random.randint(-TOUCH_CONFIG["tap_random_x"], TOUCH_CONFIG["tap_random_x"])
            y += random.randint(-TOUCH_CONFIG["tap_random_y"], TOUCH_CONFIG["tap_random_y"])
        x = max(0, min(int(x), self.screen_width))
        y = max(0, min(int(y), self.screen_height))
        log(f"탭: ({x}, {y})")
        self.shell(f"input tap {x} {y}")
        random_delay(TOUCH_CONFIG["after_tap_delay_min"], TOUCH_CONFIG["after_tap_delay_max"])
    
    def tap_element(self, element):
        """요소 내 랜덤 위치 클릭 (CDP 스타일)"""
        if not element or not element.get("found"):
            return False
        
        bounds = element.get("bounds")
        if not bounds:
            return False
        
        x1, y1, x2, y2 = bounds
        
        # bounds 유효성 검사
        if x1 == 0 and y1 == 0 and x2 == 0 and y2 == 0:
            log("[경고] bounds 무효 [0,0][0,0]")
            return False
        
        # 요소 내부 랜덤 좌표 (가장자리 15% 제외)
        margin_x = max(2, int((x2 - x1) * 0.15))
        margin_y = max(2, int((y2 - y1) * 0.15))
        
        x = random.randint(x1 + margin_x, max(x1 + margin_x, x2 - margin_x))
        y = random.randint(y1 + margin_y, max(y1 + margin_y, y2 - margin_y))
        
        log(f"요소 탭: [{x1},{y1}][{x2},{y2}] → ({x}, {y})")
        self.tap(x, y, randomize=False)
        return True
    
    def swipe(self, x1, y1, x2, y2, duration_ms=None):
        if duration_ms is None:
            duration_ms = random.randint(SCROLL_CONFIG["duration_min"], SCROLL_CONFIG["duration_max"])
        log(f"스와이프: ({int(x1)}, {int(y1)}) → ({int(x2)}, {int(y2)}), {duration_ms}ms")
        self.shell(f"input swipe {int(x1)} {int(y1)} {int(x2)} {int(y2)} {duration_ms}")
    
    def scroll_down(self, distance=None, fixed=False, compensated=False):
        """아래로 스크롤 (컨텐츠가 위로 올라감 = 아래 내용 보기)

        Args:
            distance: 스크롤 거리 (None이면 설정값 사용)
            fixed: True면 랜덤 없이 고정 거리 사용
            compensated: True면 보상 스크롤 모드 (랜덤이지만 총 이동량 정확)

        보상 스크롤 모드:
            - 랜덤하게 스크롤하되, 오차를 누적해서 다음 스크롤에서 보상
            - 예: 목표 400px인데 450px 갔으면, 다음엔 350px 목표로 조정
            - 결과: 자연스러운 랜덤 + 정확한 총 이동량
        """
        base_distance = SCROLL_CONFIG["distance"]  # 400
        random_range = SCROLL_CONFIG["distance_random"]  # 100

        if distance is not None:
            # 직접 거리 지정된 경우
            actual_distance = distance
        elif fixed:
            # 고정 모드: 정확히 base_distance
            actual_distance = base_distance
        elif compensated:
            # 보상 스크롤 모드: 랜덤이지만 오차 보상
            # 이전 오차를 반영한 목표 거리
            target = base_distance - self._scroll_debt

            # 목표 기준으로 랜덤 범위 설정 (300~400 범위, 400 초과 안함)
            # 계산이 400px 기준이므로 오버슈팅 방지
            min_dist = max(base_distance - random_range, target - random_range // 2)
            max_dist = min(base_distance, target + random_range // 2)  # 400px 상한

            # 범위가 역전되면 보정
            if min_dist > max_dist:
                min_dist, max_dist = max_dist, min_dist

            actual_distance = random.randint(int(min_dist), int(max_dist))

            # 오차 누적 (실제 - 기준)
            self._scroll_debt += (actual_distance - base_distance)
        else:
            # 일반 랜덤 모드
            actual_distance = base_distance + random.randint(-random_range, random_range)

        # X 좌표
        if fixed:
            x = COORDINATES["scroll_x"]
        else:
            x = COORDINATES["scroll_x"] + random.randint(-30, 30)

        start_y = COORDINATES["scroll_start_y"]  # 1100
        end_y = start_y - actual_distance

        self.swipe(x, start_y, x, end_y)

        # 읽기 멈춤 (확률적) - fixed 모드에서는 비활성화
        if not fixed and READING_PAUSE_CONFIG["enabled"] and random.random() < READING_PAUSE_CONFIG["probability"]:
            pause = random.uniform(READING_PAUSE_CONFIG["min_time"], READING_PAUSE_CONFIG["max_time"])
            log(f"읽기 멈춤: {pause:.1f}초")
            time.sleep(pause)

        return actual_distance

    def reset_scroll_debt(self):
        """스크롤 오차 누적 초기화 (새 스크롤 시퀀스 시작 시 호출)"""
        self._scroll_debt = 0

    def get_scroll_debt(self):
        """현재 스크롤 오차 확인"""
        return self._scroll_debt
    
    def scroll_up(self, distance=None):
        """위로 스크롤 (컨텐츠가 아래로 내려감 = 위 내용 보기)"""
        if distance is None:
            distance = SCROLL_CONFIG["distance"] + random.randint(
                -SCROLL_CONFIG["distance_random"], SCROLL_CONFIG["distance_random"])
        
        x = COORDINATES["scroll_x"] + random.randint(-30, 30)
        start_y = COORDINATES["scroll_end_y"]  # 400
        end_y = start_y + distance  # 800쯤 (아래로 스와이프)
        
        self.swipe(x, start_y, x, end_y)
    
    # ──────────────────────────────────────────
    # 키 입력
    # ──────────────────────────────────────────
    def press_enter(self):
        log("엔터 키")
        self.shell("input keyevent 66")
        random_delay(0.3, 0.6)
    
    def press_back(self):
        log("뒤로가기")
        self.shell("input keyevent 4")
        random_delay(0.5, 1.0)
    
    # ──────────────────────────────────────────
    # 한글 키보드 입력
    # ──────────────────────────────────────────
    def input_text(self, text):
        """텍스트 입력 - 가상 키보드 탭 방식"""
        log(f"텍스트 입력: {text}")
        
        has_korean = any('\uac00' <= c <= '\ud7a3' or '\u3131' <= c <= '\u3163' for c in text)
        
        if has_korean:
            return self.input_korean_keyboard(text)
        else:
            escaped = text.replace(' ', '%s').replace('&', '\\&')
            self.shell(f'input text "{escaped}"')
            random_delay(TYPING_CONFIG["after_typing_delay_min"], TYPING_CONFIG["after_typing_delay_max"])
            return True
    
    def input_korean_keyboard(self, text):
        """한글 키보드 자판 탭으로 입력"""
        log(f"한글 키보드 입력: {text}")
        
        jamos = self._decompose_korean(text)
        log(f"자모 분리: {''.join(jamos)}")
        
        for jamo in jamos:
            if jamo == ' ':
                self._tap_key('space')
            elif jamo in KEYBOARD_LAYOUT:
                self._tap_key(jamo)
            else:
                log(f"[경고] 키보드에 없는 문자: {jamo}")
            
            time.sleep(random.uniform(0.08, 0.18))
        
        random_delay(0.3, 0.5)
        return True
    
    def _decompose_korean(self, text):
        """한글을 자모로 분리"""
        result = []
        
        CHOSUNG = ['ㄱ', 'ㄲ', 'ㄴ', 'ㄷ', 'ㄸ', 'ㄹ', 'ㅁ', 'ㅂ', 'ㅃ', 'ㅅ', 'ㅆ', 'ㅇ', 'ㅈ', 'ㅉ', 'ㅊ', 'ㅋ', 'ㅌ', 'ㅍ', 'ㅎ']
        JUNGSUNG = ['ㅏ', 'ㅐ', 'ㅑ', 'ㅒ', 'ㅓ', 'ㅔ', 'ㅕ', 'ㅖ', 'ㅗ', 'ㅘ', 'ㅙ', 'ㅚ', 'ㅛ', 'ㅜ', 'ㅝ', 'ㅞ', 'ㅟ', 'ㅠ', 'ㅡ', 'ㅢ', 'ㅣ']
        JONGSUNG = ['', 'ㄱ', 'ㄲ', 'ㄳ', 'ㄴ', 'ㄵ', 'ㄶ', 'ㄷ', 'ㄹ', 'ㄺ', 'ㄻ', 'ㄼ', 'ㄽ', 'ㄾ', 'ㄿ', 'ㅀ', 'ㅁ', 'ㅂ', 'ㅄ', 'ㅅ', 'ㅆ', 'ㅇ', 'ㅈ', 'ㅊ', 'ㅋ', 'ㅌ', 'ㅍ', 'ㅎ']
        
        COMPLEX_VOWEL = {
            'ㅘ': ['ㅗ', 'ㅏ'], 'ㅙ': ['ㅗ', 'ㅐ'], 'ㅚ': ['ㅗ', 'ㅣ'],
            'ㅝ': ['ㅜ', 'ㅓ'], 'ㅞ': ['ㅜ', 'ㅔ'], 'ㅟ': ['ㅜ', 'ㅣ'],
            'ㅢ': ['ㅡ', 'ㅣ'], 'ㅒ': ['ㅑ', 'ㅣ'], 'ㅖ': ['ㅕ', 'ㅣ'],
        }
        
        COMPLEX_JONG = {
            'ㄳ': ['ㄱ', 'ㅅ'], 'ㄵ': ['ㄴ', 'ㅈ'], 'ㄶ': ['ㄴ', 'ㅎ'],
            'ㄺ': ['ㄹ', 'ㄱ'], 'ㄻ': ['ㄹ', 'ㅁ'], 'ㄼ': ['ㄹ', 'ㅂ'],
            'ㄽ': ['ㄹ', 'ㅅ'], 'ㄾ': ['ㄹ', 'ㅌ'], 'ㄿ': ['ㄹ', 'ㅍ'],
            'ㅀ': ['ㄹ', 'ㅎ'], 'ㅄ': ['ㅂ', 'ㅅ'],
        }
        
        for char in text:
            if '\uac00' <= char <= '\ud7a3':
                code = ord(char) - 0xAC00
                cho = code // 588
                jung = (code % 588) // 28
                jong = code % 28
                
                result.append(CHOSUNG[cho])
                
                vowel = JUNGSUNG[jung]
                if vowel in COMPLEX_VOWEL:
                    result.extend(COMPLEX_VOWEL[vowel])
                else:
                    result.append(vowel)
                
                if jong > 0:
                    jongchar = JONGSUNG[jong]
                    if jongchar in COMPLEX_JONG:
                        result.extend(COMPLEX_JONG[jongchar])
                    else:
                        result.append(jongchar)
            elif '\u3131' <= char <= '\u3163':
                result.append(char)
            else:
                result.append(char)
        
        return result
    
    def _tap_key(self, key):
        """키보드 키 탭 - 화면 크기에 맞게 비율 계산"""
        if key not in KEYBOARD_LAYOUT:
            log(f"[경고] 키 없음: {key}")
            return

        # 기준 화면 크기 (KEYBOARD_LAYOUT 좌표 기준)
        base_width, base_height = 720, 1440
        scale_x = self.screen_width / base_width
        scale_y = self.screen_height / base_height

        coords = KEYBOARD_LAYOUT[key]

        if coords.get('shift'):
            shift_coords = KEYBOARD_LAYOUT['shift']
            sx = int(shift_coords['x'] * scale_x) + random.randint(-5, 5)
            sy = int(shift_coords['y'] * scale_y) + random.randint(-3, 3)
            self.shell(f"input tap {sx} {sy}")
            time.sleep(random.uniform(0.05, 0.1))

        x = int(coords['x'] * scale_x) + random.randint(-8, 8)
        y = int(coords['y'] * scale_y) + random.randint(-5, 5)
        self.shell(f"input tap {x} {y}")
    
    # ──────────────────────────────────────────
    # 브라우저 제어
    # ──────────────────────────────────────────
    def clear_browser_data(self, package="com.android.chrome"):
        """브라우저 데이터 초기화 (새 프로필처럼 시작)"""
        log(f"[ADB] 브라우저 데이터 초기화: {package}")
        result = self.shell(f"pm clear {package}")
        if result and "Success" in result:
            log("[ADB] 브라우저 데이터 초기화 완료!")
            time.sleep(1)  # 초기화 후 안정화 대기
            return True
        else:
            log(f"[ADB] 브라우저 데이터 초기화 실패: {result}", "WARN")
            return False

    def handle_browser_first_run(self, browser="chrome", max_attempts=10):
        """브라우저 첫 실행 설정 화면 자동 처리

        Args:
            browser: 브라우저 종류 (chrome, samsung, edge, opera, firefox)
            max_attempts: 최대 시도 횟수

        Returns:
            bool: 처리 완료 여부
        """
        log(f"[ADB] 브라우저 첫 실행 설정 확인 ({browser})...")

        # 브라우저별 첫 실행 버튼 텍스트
        first_run_buttons = {
            "chrome": [
                "동의 및 계속",  # Accept & Continue (한글)
                "Accept & continue",  # Accept & Continue (영어)
                "동의",
                "계속",
                "아니요",  # No thanks for sync
                "No thanks",
                "건너뛰기",
                "Skip",
                "사용 안함",
                "No, thanks",
            ],
            "samsung": [
                "계속",  # Continue 버튼 (첫 화면)
                "동의",
                "시작",
                "Start",
                "확인",
                "OK",
                "건너뛰기",
                "Skip",
            ],
            "edge": [
                "수락",
                "Accept",
                "시작",
                "Start",
                "건너뛰기",
                "Skip",
                "아니요",
                "No thanks",
            ],
            "opera": [
                "동의",
                "Accept",
                "시작",
                "Start",
                "건너뛰기",
                "Skip",
            ],
            "firefox": [
                "시작하기",
                "Get started",
                "건너뛰기",
                "Skip",
                "나중에",
                "Later",
            ],
        }

        buttons_to_find = first_run_buttons.get(browser, first_run_buttons["chrome"])

        for attempt in range(max_attempts):
            time.sleep(1)
            xml = self.get_screen_xml(force=True)

            if not xml:
                continue

            # 네이버 페이지가 로드되면 설정 완료
            if "naver" in xml.lower() or "검색" in xml:
                log("[ADB] 브라우저 설정 완료, 네이버 페이지 로드됨")
                return True

            # 첫 실행 버튼 찾아서 클릭
            button_found = False
            for button_text in buttons_to_find:
                element = self.find_element_by_text(button_text, partial=False, xml=xml)
                if element and element.get("found"):
                    log(f"[ADB] 첫 실행 버튼 발견: '{button_text}'")
                    self.tap_element(element)
                    time.sleep(0.5)
                    button_found = True
                    break

            if not button_found:
                # 부분 매칭으로 재시도
                for button_text in buttons_to_find:
                    element = self.find_element_by_text(button_text, partial=True, xml=xml)
                    if element and element.get("found"):
                        log(f"[ADB] 첫 실행 버튼 발견 (부분): '{button_text}'")
                        self.tap_element(element)
                        time.sleep(0.5)
                        button_found = True
                        break

            if not button_found:
                log(f"[ADB] 첫 실행 버튼 없음, 대기 중... ({attempt + 1}/{max_attempts})")

        log("[ADB] 첫 실행 설정 처리 완료 (또는 타임아웃)")
        return True

    def open_url(self, url, browser="chrome", handle_first_run=True, max_retry=3):
        """URL 열기 + 브라우저 실행 확인

        Args:
            url: 열 URL
            browser: 브라우저 종류 (chrome, samsung, edge, opera, firefox)
            handle_first_run: 첫 실행 설정 자동 처리 여부
            max_retry: 최대 재시도 횟수
        """
        from config import BROWSERS

        # 브라우저 패키지 정보
        browser_info = BROWSERS.get(browser, BROWSERS.get("chrome"))
        package = browser_info["package"]

        for attempt in range(1, max_retry + 1):
            log(f"URL 열기 (시도 {attempt}/{max_retry}, {browser}): {url}")

            # 브라우저별 URL 열기
            self.shell(f'am start -a android.intent.action.VIEW -d "{url}" -p {package}')

            time.sleep(2)

            # 첫 실행 설정 처리
            if handle_first_run:
                self.handle_browser_first_run(browser, max_attempts=5)

            # 브라우저 로딩 확인 (최대 5초)
            for _ in range(10):
                xml = self.get_screen_xml(force=True)
                if xml and len(xml) > 500:
                    if "naver" in xml.lower() or "MM_SEARCH" in xml or "검색" in xml:
                        log(f"[확인] 브라우저 로딩 완료!")
                        random_delay(1.0, 2.0)
                        return True
                time.sleep(0.5)

            if attempt < max_retry:
                log(f"[재시도] 브라우저 로딩 안 됨...")
                self.shell("input keyevent 3")
                time.sleep(1)

        log("[실패] 브라우저 실행 실패", "ERROR")
        return False
    
    # ──────────────────────────────────────────
    # UI Automator
    # ──────────────────────────────────────────
    def get_screen_xml(self, force=False):
        """화면 UI XML (캐싱)"""
        now = time.time()
        if not force and self._last_xml and (now - self._last_xml_time) < 0.3:
            return self._last_xml
        
        self.shell("uiautomator dump /sdcard/screen.xml")
        xml = self.shell("cat /sdcard/screen.xml")
        
        self._last_xml = xml
        self._last_xml_time = now
        return xml
    
    def find_element_by_resource_id(self, resource_id, xml=None):
        """리소스 ID로 요소 찾기"""
        if xml is None:
            xml = self.get_screen_xml(force=True)
        if not xml:
            return {"found": False}
        
        # bounds와 resource-id 순서 무관하게 찾기
        pattern1 = rf'resource-id="[^"]*{re.escape(resource_id)}[^"]*"[^>]*bounds="\[(\d+),(\d+)\]\[(\d+),(\d+)\]"'
        pattern2 = rf'bounds="\[(\d+),(\d+)\]\[(\d+),(\d+)\]"[^>]*resource-id="[^"]*{re.escape(resource_id)}[^"]*"'
        
        match = re.search(pattern1, xml) or re.search(pattern2, xml)
        
        if match:
            x1, y1, x2, y2 = map(int, match.groups())
            return {
                "found": True,
                "bounds": (x1, y1, x2, y2),
                "center_x": (x1 + x2) // 2,
                "center_y": (y1 + y2) // 2,
                "width": x2 - x1,
                "height": y2 - y1
            }
        return {"found": False}
    
    def find_element_by_text(self, text, partial=True, xml=None):
        """텍스트로 요소 찾기"""
        if xml is None:
            xml = self.get_screen_xml(force=True)
        if not xml:
            return {"found": False}
        
        # 더 정확한 패턴: node 전체에서 text와 bounds 추출
        if partial:
            # text="...검색결과 더보기..." 포함
            node_pattern = rf'<node[^>]+text="([^"]*{re.escape(text)}[^"]*)"[^>]+bounds="\[(\d+),(\d+)\]\[(\d+),(\d+)\]"[^>]*/?>'
        else:
            # text="검색결과 더보기" 정확히
            node_pattern = rf'<node[^>]+text="{re.escape(text)}"[^>]+bounds="\[(\d+),(\d+)\]\[(\d+),(\d+)\]"[^>]*/?>'
        
        match = re.search(node_pattern, xml)
        
        if match:
            matched_text, x1, y1, x2, y2 = match.groups()
            x1, y1, x2, y2 = int(x1), int(y1), int(x2), int(y2)
            
            # bounds 유효성
            if x1 == 0 and y1 == 0 and x2 == 0 and y2 == 0:
                return {"found": False}
            
            return {
                "found": True,
                "text": matched_text,
                "bounds": (x1, y1, x2, y2),
                "center_x": (x1 + x2) // 2,
                "center_y": (y1 + y2) // 2
            }
        
        # 패턴 2: bounds가 text 앞에 있는 경우
        if partial:
            node_pattern2 = rf'<node[^>]+bounds="\[(\d+),(\d+)\]\[(\d+),(\d+)\]"[^>]+text="([^"]*{re.escape(text)}[^"]*)"[^>]*/?>'
        else:
            node_pattern2 = rf'<node[^>]+bounds="\[(\d+),(\d+)\]\[(\d+),(\d+)\]"[^>]+text="{re.escape(text)}"[^>]*/?>'
        
        match = re.search(node_pattern2, xml)
        
        if match:
            x1, y1, x2, y2, matched_text = match.groups()
            x1, y1, x2, y2 = int(x1), int(y1), int(x2), int(y2)
            
            if x1 == 0 and y1 == 0 and x2 == 0 and y2 == 0:
                return {"found": False}
            
            return {
                "found": True,
                "text": matched_text,
                "bounds": (x1, y1, x2, y2),
                "center_x": (x1 + x2) // 2,
                "center_y": (y1 + y2) // 2
            }
        
        return {"found": False}
    
    def find_all_elements_with_domain(self, domain, xml=None):
        """도메인이 포함된 모든 요소 찾기 (정확한 경로 매칭)

        - sidecut.co.kr 지정 시: sidecut.co.kr만 매칭 (서브페이지 제외)
        - sidecut.co.kr/lessons 지정 시: 정확히 그 경로만 매칭
        """
        if xml is None:
            xml = self.get_screen_xml(force=True)
        if not xml:
            return []

        # 경로 포함 여부 확인
        has_path = '/' in domain and not domain.endswith('/')
        base_domain = domain.split('/')[0]

        links = []
        found_count = 0
        # text 또는 content-desc에서 베이스 도메인 포함된 요소 찾기
        node_pattern = rf'<node[^>]+(?:text|content-desc)="([^"]*{re.escape(base_domain)}[^"]*)"[^>]+bounds="\[(\d+),(\d+)\]\[(\d+),(\d+)\]"[^>]*/>'

        for match in re.finditer(node_pattern, xml, re.IGNORECASE):
            text_found, x1, y1, x2, y2 = match.groups()
            x1, y1, x2, y2 = int(x1), int(y1), int(x2), int(y2)
            found_count += 1

            # 유효한 bounds만
            if x1 == 0 and y1 == 0 and x2 == 0 and y2 == 0:
                log(f"[ADB] 제외(bounds=0): {text_found[:50]}")
                continue

            # URL 인코딩된 텍스트 제외 (파비콘, 이미지 URL 등)
            # sunny?src=https%3A%2F%2Fsidecut.co.kr%2Ffavicon 같은 것
            if '%2F' in text_found or '%3A' in text_found or 'sunny?' in text_found.lower():
                log(f"[ADB] 제외(URL인코딩): {text_found[:50]}")
                continue

            # http로 시작하는 URL 제외
            if text_found.lower().startswith(('http://', 'https://')):
                log(f"[ADB] 제외(http): {text_found[:50]}")
                continue

            # 정확한 매칭 체크
            is_match = False
            if has_path:
                # 경로가 지정된 경우: 정확한 경로 포함
                if domain in text_found:
                    is_match = True
            else:
                # 경로가 없는 경우: 메인 도메인만 (서브링크 제외)
                # "sidecut.co.kr"은 매칭, "sidecut.co.kr › lessons"나 "sidecut.co.kr/lessons"는 제외
                # 도메인 뒤에 / 또는 › 또는 > 가 있으면 서브페이지
                text_after_domain = text_found.split(domain)[-1].strip() if domain in text_found else ""
                if domain in text_found and not text_after_domain.startswith(('/', '›', '>')):
                    is_match = True
                else:
                    log(f"[ADB] 제외(서브페이지): {text_found[:50]} (뒤: '{text_after_domain[:20]}')")

            if not is_match:
                continue

            log(f"[ADB] ✓ 매칭! {text_found[:40]} bounds=[{x1},{y1}][{x2},{y2}]")
            links.append({
                "found": True,
                "text": text_found,
                "bounds": (x1, y1, x2, y2),
                "center_x": (x1 + x2) // 2,
                "center_y": (y1 + y2) // 2
            })

        log(f"[ADB] 총 {found_count}개 요소 검사, {len(links)}개 매칭")
        return links
    
    def click_search_button(self):
        """검색 버튼 클릭 - 키보드 검색 버튼 우선"""

        # 1순위: 키보드의 검색 버튼 - 화면 크기에 맞게 비율 계산
        # 기준값: 720x1440 화면에서 (655, 1302) - 실측값
        base_x, base_y = 655, 1302
        base_width, base_height = 720, 1440

        scale_x = self.screen_width / base_width
        scale_y = self.screen_height / base_height

        tap_x = int(base_x * scale_x)
        tap_y = int(base_y * scale_y)

        log(f"키보드 검색 버튼: ({tap_x}, {tap_y}) [화면: {self.screen_width}x{self.screen_height}]")
        self.tap(tap_x, tap_y, randomize=True)
        return True
        
        # 2순위: UI에서 검색 버튼 찾기 (화면 오른쪽만)
        xml = self.get_screen_xml(force=True)
        half_width = self.screen_width // 2
        
        button_patterns = [
            r'<node[^>]+content-desc="[^"]*검색[^"]*"[^>]+bounds="\[(\d+),(\d+)\]\[(\d+),(\d+)\]"',
            r'<node[^>]+resource-id="[^"]*search[^"]*btn[^"]*"[^>]+bounds="\[(\d+),(\d+)\]\[(\d+),(\d+)\]"',
        ]
        
        for pattern in button_patterns:
            for match in re.finditer(pattern, xml, re.IGNORECASE):
                x1, y1, x2, y2 = map(int, match.groups())
                cx = (x1 + x2) // 2
                
                # 화면 오른쪽에 있는 버튼만
                if cx > half_width and x2 - x1 > 0 and y2 - y1 > 0:
                    cy = (y1 + y2) // 2
                    log(f"검색 버튼 발견: [{x1},{y1}][{x2},{y2}]")
                    self.tap(cx, cy, randomize=False)
                    return True
        
        log("[경고] 검색 버튼 못 찾음")
        return False


# ============================================
# 네이버 검색 자동화
# ============================================
class NaverSearchAutomation:
    def __init__(self, adb: ADBController, cdp_info=None, browser="chrome"):
        self.adb = adb
        self.viewport_top = adb.screen_height * 0.15
        self.viewport_bottom = adb.screen_height * 0.85
        self.cdp_info = cdp_info  # CDP 계산 결과
        self.browser = browser  # 사용할 브라우저

        # 모바일 CDP (브라우저 열린 후 연결됨)
        self.mobile_cdp = None
        self._mobile_cdp_initialized = False

    def _init_mobile_cdp(self):
        """모바일 브라우저 CDP 초기화 - 전체 비활성화

        스크롤 계산은 PC CDP가 해주므로 모바일에서는 CDP 연결 불필요.
        CDP 연결 시 탐지 위험이 있으므로 전체 비활성화.
        """
        self.mobile_cdp = None
        self._mobile_cdp_initialized = True
        log("[INFO] 모바일 CDP 비활성화 (순수 ADB 모드)")
        return

    def _find_element_by_text_hybrid(self, text, check_viewport=True, exact_match=False):
        """하이브리드 요소 찾기: MobileCDP 우선, 실패시 uiautomator

        Args:
            text: 찾을 텍스트
            check_viewport: 뷰포트 범위 체크 여부
            exact_match: True면 정확한 텍스트 매칭 (부모 요소 매칭 방지)

        Returns:
            dict: {"found": True, "center_x": x, "center_y": y, ...}
        """
        # 1순위: MobileCDP (읽기 전용 - 감지 불가!)
        if self.mobile_cdp and self.mobile_cdp.connected:
            # viewport_only=False: 위치 정보 필요하므로 모든 요소 검색
            result = self.mobile_cdp.find_element_by_text(text, viewport_only=False, exact_match=exact_match)
            if result.get("found"):
                # MobileCDP 좌표는 브라우저 뷰포트 기준!
                browser_y = result["y"]
                browser_viewport_height = result.get("viewport_height", 800)

                # 브라우저 주소창 오프셋 (브라우저 좌표 → 화면 좌표)
                # 삼성브라우저: 뷰포트가 전체 화면 기준, offset 거의 불필요
                # 테스트: offset 25 → 카페탭 클릭 (40px 아래로 틀어짐)
                # 수정: offset 0 또는 음수 필요
                browser_offset = 0
                screen_y = browser_y + browser_offset

                # MobileCDP 좌표 → ADBController 형식으로 변환 (화면 좌표로!)
                element = {
                    "found": True,
                    "center_x": result["x"],
                    "center_y": screen_y,  # 화면 좌표로 변환!
                    "bounds": (
                        result["x"] - result.get("width", 100) // 2,
                        screen_y - result.get("height", 50) // 2,
                        result["x"] + result.get("width", 100) // 2,
                        screen_y + result.get("height", 50) // 2
                    ),
                    "text": result.get("text", text),
                    "source": "mobile_cdp",
                    "browser_y": browser_y  # 원본 브라우저 좌표 (뷰포트 체크용)
                }

                # 뷰포트 체크 (브라우저 뷰포트 기준: 0 ~ innerHeight)
                if check_viewport:
                    # 브라우저 뷰포트 안에 있으면 발견!
                    # 약간의 여유를 두고 체크 (상단 50px, 하단 50px 여유)
                    if 50 < browser_y < (browser_viewport_height - 50):
                        log(f"[CDP찾기] '{text}' 발견 → 브라우저({result['x']}, {browser_y}) → 화면({element['center_x']}, {screen_y})")
                        return element
                    else:
                        log(f"[CDP찾기] '{text}' 뷰포트 밖 (y={browser_y}, viewport=0~{browser_viewport_height})")
                        return {"found": False, "out_of_viewport": True, "y": browser_y}
                else:
                    log(f"[CDP찾기] '{text}' 발견 → 화면({element['center_x']}, {screen_y})")
                    return element

        # 2순위: uiautomator (기존 방식)
        xml = self.adb.get_screen_xml(force=True)
        element = self.adb.find_element_by_text(text, xml=xml)

        if element.get("found") and check_viewport:
            cy = element["center_y"]
            if self.viewport_top <= cy <= self.viewport_bottom:
                element["source"] = "uiautomator"
                return element
            else:
                return {"found": False, "out_of_viewport": True, "y": cy}

        if element.get("found"):
            element["source"] = "uiautomator"

        return element

    def _find_link_by_domain_hybrid(self, domain):
        """하이브리드 도메인 링크 찾기: MobileCDP 우선

        Returns:
            dict: {"found": True, "center_x": x, "center_y": y, "href": ...}
        """
        # 1순위: MobileCDP
        if self.mobile_cdp and self.mobile_cdp.connected:
            result = self.mobile_cdp.find_link_by_domain(domain)
            if result.get("found"):
                element = {
                    "found": True,
                    "center_x": result["x"],
                    "center_y": result["y"],
                    "bounds": (
                        result["x"] - result.get("width", 100) // 2,
                        result["y"] - result.get("height", 50) // 2,
                        result["x"] + result.get("width", 100) // 2,
                        result["y"] + result.get("height", 50) // 2
                    ),
                    "href": result.get("href", ""),
                    "text": result.get("text", ""),
                    "source": "mobile_cdp"
                }
                log(f"[CDP찾기] 도메인 '{domain}' 발견 → ({element['center_x']}, {element['center_y']})")
                return element

        # 2순위: uiautomator 도메인 검색
        links = self.adb.find_domain_links(domain)
        if links:
            for link in links:
                cy = link["center_y"]
                if self.viewport_top <= cy <= self.viewport_bottom:
                    link["source"] = "uiautomator"
                    return link

        return {"found": False}

    def _find_all_links_by_domain_hybrid(self, domain):
        """하이브리드 도메인 링크 모두 찾기: MobileCDP 우선

        Returns:
            list: [{"found": True, "center_x": x, "center_y": y, "href": ...}, ...]
        """
        # 1순위: MobileCDP (읽기 전용 - 감지 불가!)
        if self.mobile_cdp and self.mobile_cdp.connected:
            results = self.mobile_cdp.find_all_links_by_domain(domain)
            if results:
                # MobileCDP 형식 → ADB 형식 변환
                links = []
                for r in results:
                    links.append({
                        "found": True,
                        "center_x": r["center_x"],
                        "center_y": r["center_y"],
                        "bounds": (
                            r["x"] - r.get("width", 100) // 2,
                            r["y"] - r.get("height", 50) // 2,
                            r["x"] + r.get("width", 100) // 2,
                            r["y"] + r.get("height", 50) // 2
                        ),
                        "href": r.get("href", ""),
                        "text": r.get("text", ""),
                        "source": "mobile_cdp"
                    })
                return links

        # 2순위: uiautomator
        xml = self.adb.get_screen_xml(force=True)
        links = self.adb.find_all_elements_with_domain(domain, xml)
        for link in links:
            link["source"] = "uiautomator"
        return links

    # ========================================
    # 1단계: 네이버 메인 이동
    # ========================================
    def step1_go_to_naver(self):
        log("=" * 50)
        log("[1단계] 네이버 메인으로 이동")
        log("=" * 50)

        if not self.adb.open_url(NAVER_CONFIG["start_url"], browser=self.browser, max_retry=3):
            return False

        # 브라우저 열린 후 MobileCDP 연결 (요소 찾기용)
        time.sleep(1)  # 페이지 로드 대기
        self._init_mobile_cdp()

        return True

    # ========================================
    # 페이지 로드 대기 (삼성 브라우저용)
    # ========================================
    def _wait_for_page_load(self):
        """
        삼성 브라우저: 검색창 클릭 전 페이지 로드 대기
        - "계속" 버튼 처리 (무한 반복)
        - 검색창 템플릿 매칭으로 로드 확인 (무한 반복)
        """
        log("[대기] 삼성 브라우저 페이지 로드 확인 중...")
        template_path = os.path.join(os.path.dirname(__file__), "template_search.png")

        attempt = 0
        while True:  # 무한 반복
            attempt += 1
            time.sleep(1)

            # "계속" 버튼 확인 (XML로)
            xml = self.adb.get_screen_xml(force=True)
            if xml:
                continue_btn = self.adb.find_element_by_text("계속", partial=False, xml=xml)
                if continue_btn.get("found"):
                    log("[대기] '계속' 버튼 발견, 클릭...")
                    self.adb.tap_element(continue_btn)
                    time.sleep(1)
                    continue

            # 검색창 템플릿 매칭으로 페이지 로드 확인
            if os.path.exists(template_path):
                result = self.adb.find_template(template_path, threshold=0.7, do_click=False)
                if result.get("found"):
                    log("[대기] 검색창 템플릿 발견! 페이지 로드 완료")
                    return True
                else:
                    log(f"[대기] 검색창 템플릿 없음, 대기 중... (#{attempt})")
            else:
                # 템플릿 파일 없으면 5초 대기 후 진행
                log(f"[대기] template_search.png 없음, 5초 대기 후 진행...")
                time.sleep(5)
                return True

    # ========================================
    # 2단계: 검색창 클릭 (CDP 로직 동일)
    # ========================================
    def step2_click_search_box(self):
        log("=" * 50)
        log("[2단계] 검색창 클릭")
        log("=" * 50)

        max_retry = WAIT_CONFIG.get("max_element_retry", 30)
        clicks_before_reload = 5

        # 요소 기반 안 되는 브라우저는 처음부터 좌표 모드
        coordinate_only_browsers = ["samsung", "firefox", "opera", "edge"]
        use_coordinate_fallback = self.browser in coordinate_only_browsers

        # 삼성 브라우저: 무한 재시도 (디버깅용)
        is_samsung = self.browser == "samsung"
        if is_samsung:
            max_retry = 999999  # 사실상 무한

        if use_coordinate_fallback:
            log(f"[좌표 모드] {self.browser} 브라우저는 좌표 기반 클릭 사용")
            # 삼성 브라우저: 페이지 로드 대기 (검색창 클릭 전)
            if is_samsung:
                self._wait_for_page_load()

        for retry in range(1, max_retry + 1):
            # 5번마다 메인 재이동 (CDP 동일)
            if retry > 1 and (retry - 1) % clicks_before_reload == 0:
                log(f"[재이동] {clicks_before_reload}번 실패, 네이버 재이동...")
                self.adb.open_url(NAVER_CONFIG["start_url"], browser=self.browser, max_retry=1)

            # 좌표 모드가 아니면 요소 찾기 시도
            element = None
            if not use_coordinate_fallback:
                xml = self.adb.get_screen_xml(force=True)
                element = self.adb.find_element_by_resource_id("MM_SEARCH_FAKE", xml)
                if not element.get("found"):
                    element = self.adb.find_element_by_resource_id("query", xml)

                # 요소 못 찾으면 3번째 시도부터 좌표 기반으로 전환
                if not element.get("found"):
                    if retry >= 3:
                        log(f"[전환] 요소 찾기 실패, 좌표 기반 클릭으로 전환")
                        use_coordinate_fallback = True
                    else:
                        log(f"[재시도 {retry}/{max_retry}] 검색창 못 찾음")
                        time.sleep(0.5)
                        continue

            # 클릭 실행
            scale_x = self.adb.screen_width / 720
            scale_y = self.adb.screen_height / 1440

            if use_coordinate_fallback:
                # 좌표 기반 클릭 (네이버 검색창 위치)
                base_x, base_y = 156, 318  # 네이버 메인 검색창 (실측값)
                tap_x = int(base_x * scale_x)
                tap_y = int(base_y * scale_y)
                log(f"[좌표 클릭] 검색창 ({tap_x}, {tap_y})")
                self.adb.tap(tap_x, tap_y)
            else:
                # 화면 범위 체크
                cy = element.get("center_y", -1)
                if cy < 0 or cy > self.adb.screen_height:
                    log(f"[재시도 {retry}/{max_retry}] 검색창이 화면 밖")
                    time.sleep(0.5)
                    continue
                # 검색창 클릭
                if not self.adb.tap_element(element):
                    continue

            log(f"[클릭 {retry}/{max_retry}] 검색 모드 확인 중...")
            time.sleep(1.0)

            # 검색 모드 전환 확인
            xml = self.adb.get_screen_xml(force=True)

            # 요소로 확인 시도
            query = self.adb.find_element_by_resource_id("query", xml)
            if query.get("found"):
                qy = query.get("center_y", -1)
                if 0 <= qy <= self.adb.screen_height:
                    log("[성공] 검색 모드 전환됨!")
                    self.adb.tap_element(query)
                    time.sleep(0.3)
                    return True

            # 좌표 모드일 때 (삼성 브라우저 등)
            if use_coordinate_fallback:
                time.sleep(1.5)  # 검색 모드 전환 대기

                # 삼성 브라우저: 템플릿 매칭으로 검색 모드 전환 확인
                if is_samsung:
                    template_path = os.path.join(os.path.dirname(__file__), "template_search.png")
                    if os.path.exists(template_path):
                        result = self.adb.find_template(template_path, threshold=0.7, do_click=False)
                        if result.get("found"):
                            # 검색창 템플릿이 아직 보임 = 클릭 실패 (JS 미로드)
                            log(f"[실패] 검색창 아직 보임 (JS 미로드), 새로고침 후 재시도... (#{retry})")
                            # 새로고침
                            self.adb.open_url(NAVER_CONFIG["start_url"], browser=self.browser, max_retry=1)
                            time.sleep(2)
                            self._wait_for_page_load()  # 다시 로드 대기
                            continue  # 무한 재시도
                        else:
                            # 검색창 템플릿 안 보임 = 검색 모드 전환됨
                            log("[성공] 검색 모드 전환됨! (템플릿 확인)")
                            return True
                    else:
                        log("[성공] 검색 모드 전환됨! (좌표 기반, 템플릿 없음)")
                        return True
                else:
                    log("[성공] 검색 모드 전환됨! (좌표 기반)")
                    return True

            time.sleep(0.5)

        log(f"[실패] 검색창 클릭 {max_retry}번 실패", "ERROR")
        return False
    
    # ========================================
    # 3단계: 검색어 입력
    # ========================================
    def step3_input_keyword(self, keyword):
        log("=" * 50)
        log(f"[3단계] 검색어 입력: {keyword}")
        log("=" * 50)
        
        self.adb.input_text(keyword)
        random_delay(0.3, 0.5)
        return True
    
    # ========================================
    # 4단계: 검색 실행 (CDP 로직 동일)
    # ========================================
    def step4_execute_search(self):
        log("=" * 50)
        log("[4단계] 검색 실행")
        log("=" * 50)
        
        # 검색 모드 (1=엔터, 2=돋보기, 3=랜덤)
        search_mode = NAVER_CONFIG.get("search_mode", 3)
        if search_mode == 3:
            search_mode = random.choice([1, 2])
        
        mode_name = "엔터" if search_mode == 1 else "돋보기"
        log(f"검색 방식: {mode_name}")
        
        search_success = False
        
        if search_mode == 1:
            self.adb.press_enter()
            search_success = True
        else:
            # 돋보기 버튼 클릭 시도
            if self.adb.click_search_button():
                search_success = True
            else:
                # 못 찾으면 엔터로 대체 (CDP 동일)
                log("돋보기 못 찾음, 엔터로 대체")
                self.adb.press_enter()
                search_success = True
        
        # 검색 결과 대기 (CDP: 10초)
        log("[대기] 검색 결과 로딩...")
        time.sleep(2)
        
        # 1차 확인
        for _ in range(8):  # 4초
            xml = self.adb.get_screen_xml(force=True)
            if xml and ("search" in xml.lower() or "검색" in xml):
                log("[성공] 검색 결과 로딩 완료!")
                return True
            time.sleep(0.5)
        
        # 1차 실패 → 엔터로 재시도 (CDP 동일)
        log("[재시도] 검색 결과 없음, 엔터로 재검색...")
        self.adb.press_enter()
        time.sleep(2)
        
        # 2차 확인
        for _ in range(8):
            xml = self.adb.get_screen_xml(force=True)
            if xml and ("search" in xml.lower() or "검색" in xml):
                log("[성공] 검색 결과 로딩 완료!")
                return True
            time.sleep(0.5)
        
        log("[경고] 검색 결과 확인 안 됨, 진행...")
        return True
    
    # ========================================
    # 4.5단계: 통합에서 도메인 찾기
    # ========================================
    def step4_5_find_in_total(self, domain):
        log("=" * 50)
        log(f"[4.5단계] 통합에서 '{domain}' 찾기")
        log("=" * 50)
        
        max_scrolls = NAVER_CONFIG.get("max_scrolls_total", 30)
        same_pos_count = 0
        
        for scroll_count in range(max_scrolls):
            xml = self.adb.get_screen_xml(force=True)
            links = self.adb.find_all_elements_with_domain(domain, xml)
            
            if links:
                # 화면 중앙에 있는 링크
                visible = [l for l in links if self.viewport_top <= l["center_y"] <= self.viewport_bottom]
                
                if visible:
                    log(f"[통합] {domain} 발견! {len(visible)}개 링크")
                    
                    # 추가 랜덤 스크롤 (자연스럽게) - CDP 동일
                    extra = random.randint(30, 100) * random.choice([1, -1])
                    self.adb.scroll_down(extra)
                    time.sleep(random.uniform(0.3, 0.5))
                    
                    # 다시 확인
                    xml = self.adb.get_screen_xml(force=True)
                    links = self.adb.find_all_elements_with_domain(domain, xml)
                    visible = [l for l in links if self.viewport_top <= l["center_y"] <= self.viewport_bottom]
                    
                    if visible:
                        selected = random.choice(visible)
                        log(f"[클릭] {selected['text'][:50]}...")
                        self.adb.tap_element(selected)
                        random_delay(2.0, 3.0)
                        return True
            
            self.adb.scroll_down()
            
            if scroll_count % 5 == 0:
                log(f"[4.5단계] 스크롤 {scroll_count}/{max_scrolls}...")
            
            random_delay(0.3, 0.5)
        
        log(f"[4.5단계] 통합에서 {domain} 못 찾음")
        return False
    
    # ========================================
    # 삼성 브라우저: 템플릿 매칭으로 실제 화면 확인
    # ========================================
    def _verify_more_button_visible(self):
        """삼성 브라우저: 템플릿 매칭으로 '검색결과 더보기' 버튼이 실제 화면에 보이는지 확인

        Returns:
            bool: True면 화면에 보임, False면 안 보임
        """
        if self.browser != "samsung" or not TEMPLATE_MATCHING_AVAILABLE:
            return True  # 삼성 아니면 그냥 통과 (CDP 결과 신뢰)

        script_dir = os.path.dirname(os.path.abspath(__file__))
        template_path = os.path.join(script_dir, "template_more.png")

        if not os.path.exists(template_path):
            log("[TEMPLATE] 템플릿 파일 없음, CDP 결과 신뢰")
            return True  # 템플릿 없으면 그냥 통과

        log("[TEMPLATE] 삼성 브라우저 - 실제 화면에 버튼 있는지 확인...")
        result = self.adb.find_template(template_path, threshold=0.7, do_click=False)

        if result.get("found"):
            log(f"[TEMPLATE] ✓ 화면에서 확인됨 (유사도: {result.get('conf', 0):.3f})")
            return True
        else:
            log(f"[TEMPLATE] ✗ 화면에서 안 보임 (CDP는 찾았지만 실제 없음)")
            return False

    # ========================================
    # 5단계: "검색결과 더보기" 찾기
    # ========================================
    def step5_scroll_to_more(self):
        log("=" * 50)
        log("[5단계] '검색결과 더보기' 찾기")
        log("=" * 50)

        target = NAVER_CONFIG.get("target_text", "검색결과 더보기")
        max_scrolls = NAVER_CONFIG.get("max_scrolls", 50)
        short_scroll = int(self.adb.screen_height * 0.3)

        # ========================================
        # 삼성 브라우저: CDP 없이 순수 ADB + 템플릿 매칭
        # ========================================
        if self.browser == "samsung" and TEMPLATE_MATCHING_AVAILABLE:
            log("[5단계] 삼성 브라우저 - 순수 ADB + 템플릿 매칭 모드")

            script_dir = os.path.dirname(os.path.abspath(__file__))
            template_path = os.path.join(script_dir, "template_more.png")

            if not os.path.exists(template_path):
                log(f"[ERROR] 템플릿 파일 없음: {template_path}", "ERROR")
                return None

            # 1단계: PC에서 계산된 스크롤 횟수만큼 스크롤
            if self.cdp_info and self.cdp_info.get("more_scroll_count", 0) > 0:
                scroll_count = self.cdp_info["more_scroll_count"]
                log(f"[5단계] 계산된 스크롤 횟수: {scroll_count}번")
            else:
                scroll_count = 15  # 기본값
                log(f"[5단계] 스크롤 횟수 기본값 사용: {scroll_count}번")

            # 스크롤 오차 초기화
            self.adb.reset_scroll_debt()

            # 스크롤 실행
            for i in range(scroll_count):
                self.adb.scroll_down(compensated=True)

                # 읽기 멈춤 (확률적)
                if READING_PAUSE_CONFIG["enabled"] and random.random() < READING_PAUSE_CONFIG["probability"]:
                    pause = random.uniform(READING_PAUSE_CONFIG["min_time"], READING_PAUSE_CONFIG["max_time"])
                    log(f"읽기 멈춤: {pause:.1f}초")
                    time.sleep(pause)
                else:
                    time.sleep(random.uniform(0.1, 0.2))

                if (i + 1) % 10 == 0:
                    log(f"[5단계] 스크롤 {i + 1}/{scroll_count}...")

            log(f"[5단계] 스크롤 완료, 최종 오차: {self.adb.get_scroll_debt()}px")

            # 2단계: 템플릿 매칭으로 찾기
            log("[5단계] 템플릿 매칭으로 '검색결과 더보기' 찾기...")
            result = self.adb.find_template(template_path, threshold=0.7, do_click=False)

            if result.get("found"):
                log(f"[발견] 템플릿 매칭 성공! 위치: ({result['x']}, {result['y']})")
                return result

            # 3단계: 못 찾으면 위로 200~300px씩 스크롤하면서 템플릿 비교
            log("[5단계] 템플릿 못 찾음, 위로 스크롤하면서 찾기...")
            max_up_scrolls = 30  # 최대 30번 위로 스크롤

            for i in range(max_up_scrolls):
                # 200~300px 랜덤 스크롤
                scroll_amount = random.randint(200, 300)
                self.adb.scroll_up(scroll_amount)
                time.sleep(random.uniform(0.3, 0.5))

                # 템플릿 매칭
                result = self.adb.find_template(template_path, threshold=0.7, do_click=False)

                if result.get("found"):
                    log(f"[발견] 템플릿 매칭 성공! 위치: ({result['x']}, {result['y']}) (스크롤 {i+1}번 후)")
                    return result

                if (i + 1) % 5 == 0:
                    log(f"[5단계] 위로 스크롤 {i + 1}/{max_up_scrolls}...")

            log(f"[실패] '{target}' 못 찾음 (템플릿 매칭 실패)", "ERROR")
            return None

        # ========================================
        # 다른 브라우저: 기존 CDP 방식
        # ========================================
        # CDP 계산값 사용 (있으면)
        if self.cdp_info and self.cdp_info.get("calculated") and self.cdp_info.get("more_scroll_count", 0) > 0:
            cdp_scroll = self.cdp_info["more_scroll_count"]
            log(f"[CDP] 계산값 사용: {cdp_scroll}번 스크롤")

            # 스크롤 오차 초기화
            self.adb.reset_scroll_debt()

            # CDP 계산대로 스크롤
            for i in range(cdp_scroll):
                self.adb.scroll_down(compensated=True)

                # 읽기 멈춤 (확률적)
                if READING_PAUSE_CONFIG["enabled"] and random.random() < READING_PAUSE_CONFIG["probability"]:
                    pause = random.uniform(READING_PAUSE_CONFIG["min_time"], READING_PAUSE_CONFIG["max_time"])
                    log(f"읽기 멈춤: {pause:.1f}초")
                    time.sleep(pause)
                else:
                    time.sleep(random.uniform(0.1, 0.2))

                if (i + 1) % 10 == 0:
                    log(f"[5단계] 스크롤 {i + 1}/{cdp_scroll}...")

            log(f"[CDP] 스크롤 완료, 최종 오차: {self.adb.get_scroll_debt()}px")

            # 디버그: 모든 매칭 요소 출력
            if self.mobile_cdp and self.mobile_cdp.connected:
                self.mobile_cdp.debug_find_all_elements(target)

            # 요소 찾기 (exact_match=True: 정확한 매칭으로 부모 요소 제외)
            element = self._find_element_by_text_hybrid(target, check_viewport=True, exact_match=True)
            if element.get("found"):
                # 삼성 브라우저: 템플릿 매칭으로 실제 화면에 있는지 확인
                if self._verify_more_button_visible():
                    log(f"[발견] '{target}' y={element['center_y']}")
                    return element
                else:
                    log("[5단계] CDP는 찾았지만 화면에 없음, 스크롤 계속...")

            # 지나쳤으면 위로 300px씩 올리면서 찾기
            if element.get("out_of_viewport") and element.get("y", 0) < 0:
                log(f"[5단계] 지나침 (y={element.get('y')}), 위로 300px씩 스크롤...")
                for scroll_i in range(20):
                    self.adb.scroll_up(300)
                    time.sleep(0.3)

                    # 매 5번째 스크롤마다 디버그 출력
                    if scroll_i % 5 == 4 and self.mobile_cdp and self.mobile_cdp.connected:
                        self.mobile_cdp.debug_find_all_elements(target)

                    element = self._find_element_by_text_hybrid(target, check_viewport=True, exact_match=True)
                    if element.get("found"):
                        # 삼성 브라우저: 템플릿 매칭으로 실제 화면에 있는지 확인
                        if self._verify_more_button_visible():
                            # 클릭 전 디버그 출력
                            if self.mobile_cdp and self.mobile_cdp.connected:
                                self.mobile_cdp.debug_find_all_elements(target)
                            log(f"[발견] '{target}' y={element['center_y']}")
                            return element
                        # 템플릿 검증 실패 시 계속 스크롤
            else:
                # 아직 안 나왔으면 아래로 더 스크롤
                log("[5단계] 아직 안 보임, 아래로 추가 스크롤...")
                for _ in range(15):
                    self.adb.scroll_down(short_scroll)
                    time.sleep(0.3)
                    element = self._find_element_by_text_hybrid(target, check_viewport=True, exact_match=True)
                    if element.get("found"):
                        # 삼성 브라우저: 템플릿 매칭으로 실제 화면에 있는지 확인
                        if self._verify_more_button_visible():
                            log(f"[발견] '{target}' y={element['center_y']}")
                            return element
                        # 템플릿 검증 실패 시 계속 스크롤

            log(f"[실패] '{target}' 못 찾음", "ERROR")
            return None

        # CDP 없으면 기존 방식 (매번 덤프) - 하이브리드로 요소 찾기
        log("[5단계] 기존 방식 (CDP 계산값 없음)")
        for scroll_count in range(max_scrolls):
            element = self._find_element_by_text_hybrid(target, check_viewport=True, exact_match=True)

            if element.get("found"):
                # 삼성 브라우저: 템플릿 매칭으로 실제 화면에 있는지 확인
                if self._verify_more_button_visible():
                    log(f"[발견] '{target}' y={element['center_y']} ({element.get('source', 'unknown')})")
                    return element
                # 템플릿 검증 실패 시 계속 스크롤

            # 뷰포트 위에 있으면 위로 스크롤
            if element.get("out_of_viewport") and element.get("y", 0) < self.viewport_top:
                self.adb.scroll_up(short_scroll)
                continue

            self.adb.scroll_down(short_scroll)

            if scroll_count % 10 == 0:
                log(f"[5단계] 스크롤 {scroll_count}/{max_scrolls}...")
        
        log(f"[실패] '{target}' 못 찾음", "ERROR")
        return None
    
    # ========================================
    # 6단계: "검색결과 더보기" 클릭 (CDP 로직 동일)
    # ========================================
    def step6_click_more(self, element):
        log("=" * 50)
        log("[6단계] '검색결과 더보기' 클릭")
        log("=" * 50)

        max_retry = NAVER_CONFIG.get("step6_click_retry", 5)
        target = NAVER_CONFIG.get("target_text", "검색결과 더보기")

        # 클릭 전 안정화 대기 (CDP 동일)
        random_delay(0.5, 1.0)

        # 삼성 브라우저: 템플릿 매칭으로 정확한 좌표 찾기 (CDP 좌표 오차 문제 해결)
        if self.browser == "samsung" and TEMPLATE_MATCHING_AVAILABLE:
            # 템플릿 파일 경로 (스크립트 디렉토리에 위치)
            script_dir = os.path.dirname(os.path.abspath(__file__))
            template_path = os.path.join(script_dir, "template_more.png")

            if os.path.exists(template_path):
                log("[TEMPLATE] 삼성 브라우저 - 템플릿 매칭으로 정확한 좌표 찾기")
                template_element = self.adb.find_template(template_path, threshold=0.7, do_click=True)
                if template_element.get("found"):
                    log(f"[TEMPLATE] '{target}' 좌표: ({template_element['x']}, {template_element['y']})")
                    # 템플릿 매칭에서 이미 클릭했으므로 로딩 대기만
                    return self._wait_for_more_page_load()
                else:
                    # 템플릿 매칭 실패 → fallback 클릭 금지!
                    log("[TEMPLATE] 템플릿 매칭 실패 - 화면에 버튼이 보이지 않음", "WARNING")
                    log("[TEMPLATE] fallback 클릭 금지, 재시도 필요 (스크롤/위치 확인)")
                    return False  # 클릭하지 않고 실패 반환
            else:
                log(f"[TEMPLATE] 템플릿 파일 없음: {template_path}", "ERROR")
                return False  # 템플릿 파일 없으면 진행 불가

        for click_try in range(1, max_retry + 1):
            time.sleep(random.uniform(0.3, 0.6))

            self.adb.tap_element(element)
            log(f"[클릭 {click_try}/{max_retry}] 로딩 대기...")

            # 10초 단위로 체크하면서 재클릭 (CDP 동일: 10초 * 5회 = 50초)
            max_reclick = 5

            for reclick_try in range(max_reclick):
                # 10초 대기 (0.5초 * 20)
                for _ in range(20):
                    xml = self.adb.get_screen_xml(force=True)
                    nx = self.adb.find_element_by_resource_id("nx_query", xml)

                    if nx.get("found"):
                        log("[성공] 더보기 페이지 로딩 완료!")
                        random_delay(1.0, 2.0)
                        return True
                    time.sleep(0.5)

                # URL 안 바뀌면 재클릭 (CDP 동일)
                if reclick_try < max_reclick - 1:
                    log(f"[재클릭] 페이지 변경 없음, 재클릭 {reclick_try + 2}/{max_reclick}...")
                    # 삼성 브라우저: 템플릿 매칭으로 다시 찾기
                    if self.browser == "samsung" and TEMPLATE_MATCHING_AVAILABLE:
                        script_dir = os.path.dirname(os.path.abspath(__file__))
                        template_path = os.path.join(script_dir, "template_more.png")
                        if os.path.exists(template_path):
                            template_element = self.adb.find_template(template_path, threshold=0.7, do_click=True)
                            if template_element.get("found"):
                                continue  # 클릭 완료, 다음 대기 루프로
                    # fallback: 기존 방식
                    element = self._find_element_by_text_hybrid(target, check_viewport=False)
                    if element.get("found"):
                        self.adb.tap_element(element)

            # 타임아웃
            log(f"[타임아웃] 페이지 로딩 50초 초과")
            return False

        log(f"[실패] 더보기 클릭 {max_retry}번 실패", "ERROR")
        return False

    def _wait_for_more_page_load(self):
        """템플릿 클릭 후 더보기 페이지 로딩 대기"""
        log("[대기] 더보기 페이지 로딩 대기 중...")

        # 삼성 브라우저: 템플릿이 사라졌는지 확인 (더보기 버튼 없으면 페이지 전환됨)
        if self.browser == "samsung" and TEMPLATE_MATCHING_AVAILABLE:
            script_dir = os.path.dirname(os.path.abspath(__file__))
            template_path = os.path.join(script_dir, "template_more.png")

            time.sleep(2.0)  # 페이지 전환 대기

            for check in range(10):  # 최대 5초 (0.5초 * 10)
                result = self.adb.find_template(template_path, threshold=0.7, do_click=False)
                if not result.get("found"):
                    log("[성공] 더보기 버튼 사라짐 - 페이지 전환 완료!")
                    random_delay(1.0, 2.0)
                    return True
                time.sleep(0.5)

            log("[실패] 더보기 버튼이 아직 있음 - 클릭 안 먹힘?", "WARNING")
            return False

        # 기존 방식: nx_query 찾기
        max_wait = 50
        for _ in range(max_wait * 2):
            xml = self.adb.get_screen_xml(force=True)
            nx = self.adb.find_element_by_resource_id("nx_query", xml)

            if nx.get("found"):
                log("[성공] 더보기 페이지 로딩 완료!")
                random_delay(1.0, 2.0)
                return True
            time.sleep(0.5)

        log("[타임아웃] 페이지 로딩 50초 초과")
        return False

    # ========================================
    # 7단계 삼성 브라우저: 템플릿 매칭으로 도메인 찾기
    # ========================================
    def _step7_samsung_template_matching(self, domain):
        """삼성 브라우저 전용: 템플릿 매칭으로 도메인 찾아서 클릭

        로직:
        1. 스크롤 계산값의 50%만 스크롤 (랜덤 보상값 적용)
        2. 스크롤하면서 도메인 템플릿 매칭
        3. 찾으면 서브링크 영역 제외하고 랜덤 클릭
        4. 페이지 전환 확인, 실패 시 무한 재시도
        """
        log("[7단계] 삼성 브라우저 - 템플릿 매칭 모드")

        script_dir = os.path.dirname(os.path.abspath(__file__))
        domain_template = os.path.join(script_dir, "template_domain.png")
        sublink_template = os.path.join(script_dir, "template_sublink.png")

        # 템플릿 파일 확인
        if not os.path.exists(domain_template):
            log(f"[ERROR] 도메인 템플릿 없음: {domain_template}", "ERROR")
            log("[INFO] template_domain.png 파일을 adb/ 폴더에 추가하세요")
            return False

        # 1단계: 스크롤 계산값의 50%만 스크롤
        if self.cdp_info and self.cdp_info.get("domain_scroll_count", 0) > 0:
            full_scroll = self.cdp_info["domain_scroll_count"]
            half_scroll = max(1, full_scroll // 2)  # 50%
            log(f"[7단계] 계산값 {full_scroll}의 50% = {half_scroll}번 스크롤")
        else:
            half_scroll = 5  # 기본값
            log(f"[7단계] 스크롤 횟수 기본값: {half_scroll}번")

        # 스크롤 오차 초기화
        self.adb.reset_scroll_debt()

        # 50% 스크롤 실행
        for i in range(half_scroll):
            self.adb.scroll_down(compensated=True)

            if READING_PAUSE_CONFIG["enabled"] and random.random() < READING_PAUSE_CONFIG["probability"]:
                pause = random.uniform(READING_PAUSE_CONFIG["min_time"], READING_PAUSE_CONFIG["max_time"])
                log(f"읽기 멈춤: {pause:.1f}초")
                time.sleep(pause)
            else:
                time.sleep(random.uniform(0.1, 0.2))

            if (i + 1) % 5 == 0:
                log(f"[7단계] 스크롤 {i + 1}/{half_scroll}...")

        log(f"[7단계] 50% 스크롤 완료, 오차: {self.adb.get_scroll_debt()}px")

        # 2단계: 스크롤하면서 도메인 템플릿 매칭
        log("[7단계] 템플릿 매칭으로 도메인 찾기 시작...")
        max_scroll_attempts = 50  # 최대 스크롤 횟수

        for attempt in range(max_scroll_attempts):
            # 도메인 템플릿 매칭
            result = self.adb.find_template(domain_template, threshold=0.7, do_click=False)

            if result.get("found"):
                log(f"[발견] 도메인 템플릿 매칭 성공! 위치: ({result['x']}, {result['y']})")

                # 3단계: 서브링크 영역 제외하고 클릭 영역 계산
                click_x, click_y = self._calculate_click_position(
                    result, sublink_template
                )

                # 4단계: 무한 재시도 클릭
                return self._click_domain_with_retry(click_x, click_y, domain_template)

            # 못 찾으면 위로 스크롤 (200~300px 랜덤)
            scroll_amount = random.randint(200, 300)
            self.adb.scroll_up(scroll_amount)
            time.sleep(random.uniform(0.3, 0.5))

            if (attempt + 1) % 10 == 0:
                log(f"[7단계] 스크롤하며 찾는 중... {attempt + 1}/{max_scroll_attempts}")

        log("[실패] 도메인 템플릿 못 찾음", "ERROR")
        return False

    def _calculate_click_position(self, domain_result, sublink_template):
        """클릭 가능 영역 계산 (서브링크 제외)

        Args:
            domain_result: 도메인 템플릿 매칭 결과 {x, y, bounds: (x1,y1,x2,y2), ...}
            sublink_template: 서브링크 템플릿 파일 경로

        Returns:
            (click_x, click_y): 클릭할 좌표
        """
        x1, y1, x2, y2 = domain_result["bounds"]
        domain_width = x2 - x1
        domain_height = y2 - y1

        # 서브링크 템플릿 매칭 시도
        exclude_y_start = y2  # 기본값: 서브링크 없으면 전체 영역 사용

        if os.path.exists(sublink_template):
            sublink_result = self.adb.find_template(sublink_template, threshold=0.7, do_click=False)

            if sublink_result.get("found"):
                sx1, sy1, sx2, sy2 = sublink_result["bounds"]
                log(f"[서브링크] 제외 영역: ({sx1},{sy1})-({sx2},{sy2})")

                # 서브링크가 도메인 영역 내에 있으면 제외
                if sy1 > y1 and sy1 < y2:
                    exclude_y_start = sy1
                    log(f"[클릭영역] y: {y1} ~ {exclude_y_start} (서브링크 위)")
        else:
            log("[INFO] 서브링크 템플릿 없음, 상단 70% 영역만 클릭")
            exclude_y_start = y1 + int(domain_height * 0.7)

        # 클릭 가능 영역 내에서 랜덤 좌표 선택
        margin_x = int(domain_width * 0.1)
        margin_y = int((exclude_y_start - y1) * 0.1)

        click_x = random.randint(x1 + margin_x, x2 - margin_x)
        click_y = random.randint(y1 + margin_y, exclude_y_start - margin_y)

        log(f"[클릭좌표] 랜덤 선택: ({click_x}, {click_y})")
        return click_x, click_y

    def _click_domain_with_retry(self, click_x, click_y, domain_template):
        """도메인 클릭 후 페이지 전환 확인, 실패 시 무한 재시도

        Args:
            click_x, click_y: 클릭할 좌표
            domain_template: 도메인 템플릿 (사라졌는지 확인용)

        Returns:
            True: 페이지 전환 성공
            (무한 루프로 실패 시 여기서 멈춤 - 디버깅용)
        """
        retry_count = 0

        while True:  # 무한 재시도
            retry_count += 1
            log(f"[클릭] 시도 #{retry_count}: ({click_x}, {click_y})")

            # 클릭
            self.adb.tap(click_x, click_y, randomize=False)
            time.sleep(2.0)  # 페이지 전환 대기

            # 페이지 전환 확인: 도메인 템플릿이 사라졌는지 체크
            result = self.adb.find_template(domain_template, threshold=0.7, do_click=False)

            if not result.get("found"):
                log("[성공] 도메인 템플릿 사라짐 - 페이지 전환 완료!")
                random_delay(1.0, 2.0)
                return True

            # 템플릿이 아직 있으면 클릭 실패 (빈 곳 클릭했거나 링크 아님)
            log(f"[재시도] 페이지 전환 안 됨, 다시 클릭... (시도 #{retry_count})")

            # 새로운 클릭 위치 계산 (약간 다른 위치로)
            click_x += random.randint(-20, 20)
            click_y += random.randint(-20, 20)

            time.sleep(random.uniform(0.5, 1.0))

    # ========================================
    # 7단계: 더보기 페이지에서 도메인 찾기
    # ========================================
    def step7_find_domain(self, domain):
        log("=" * 50)
        log(f"[7단계] '{domain}' 찾기")
        log("=" * 50)

        # ========================================
        # 삼성 브라우저: 템플릿 매칭으로 도메인 찾기
        # ========================================
        if self.browser == "samsung" and TEMPLATE_MATCHING_AVAILABLE:
            return self._step7_samsung_template_matching(domain)

        # CDP 계산값 사용 (있으면)
        if self.cdp_info and self.cdp_info.get("calculated") and self.cdp_info.get("domain_scroll_count", -1) >= 0:
            cdp_scroll = self.cdp_info["domain_scroll_count"]
            log(f"[CDP] 계산값 사용: {cdp_scroll}번 스크롤 (보상 모드)")

            # 스크롤 오차 초기화
            self.adb.reset_scroll_debt()

            # 덤프 없이 빠르게 스크롤 (compensated=True: 랜덤이지만 총 이동량 정확)
            for i in range(cdp_scroll):
                self.adb.scroll_down(compensated=True)

                if READING_PAUSE_CONFIG["enabled"] and random.random() < READING_PAUSE_CONFIG["probability"]:
                    pause = random.uniform(READING_PAUSE_CONFIG["min_time"], READING_PAUSE_CONFIG["max_time"])
                    log(f"읽기 멈춤: {pause:.1f}초")
                    time.sleep(pause)
                else:
                    time.sleep(random.uniform(0.1, 0.2))

                if (i + 1) % 10 == 0:
                    log(f"[7단계] 스크롤 {i + 1}/{cdp_scroll}...")

            log(f"[CDP] 스크롤 완료, 최종 오차: {self.adb.get_scroll_debt()}px")

            # 여유분 스크롤 제거 - 오버슈팅 방지
            # 못 찾으면 추가 스크롤하면 됨

            # 덤프해서 도메인 찾기
            return self._find_and_click_domain_final(domain)
        
        # CDP 없거나 도메인 못 찾은 경우 → 기존 방식 (페이지별 탐색)
        log("[7단계] 기존 방식 (CDP 없음)")
        
        max_page = NAVER_CONFIG.get("max_page", 10)
        start_page = 2
        
        for page_num in range(start_page, max_page + 1):
            log(f"[탐색] {page_num}페이지...")
            
            if self._find_and_click_domain_in_page(domain):
                return True
            
            if page_num < max_page:
                next_page = page_num + 1
                log(f"[이동] {next_page}페이지로...")
                
                if not self._click_page_number(next_page):
                    log(f"[실패] {next_page}페이지 버튼 못 찾음")
                    break
                
                random_delay(1.5, 2.5)
        
        log(f"[실패] {domain} 못 찾음 ({max_page}페이지까지)", "ERROR")
        return False
    
    def _find_and_click_domain_final(self, domain):
        """CDP 스크롤 후 도메인 찾아서 클릭 (하이브리드: MobileCDP 우선)"""
        short_scroll = int(self.adb.screen_height * 0.3)

        # 먼저 현재 위치에서 찾기 (하이브리드)
        links = self._find_all_links_by_domain_hybrid(domain)
        visible = [l for l in links if self.viewport_top <= l["center_y"] <= self.viewport_bottom]

        if visible:
            source = visible[0].get("source", "unknown")
            log(f"[7단계] 링크 발견 ({source})")
            return self._click_domain_link(visible, domain)

        # 못 찾으면 추가 스크롤
        log("[7단계] CDP 위치에서 못 찾음, 추가 스크롤...")
        for _ in range(15):
            self.adb.scroll_down(short_scroll)
            time.sleep(0.3)

            links = self._find_all_links_by_domain_hybrid(domain)
            visible = [l for l in links if self.viewport_top <= l["center_y"] <= self.viewport_bottom]

            if visible:
                source = visible[0].get("source", "unknown")
                log(f"[7단계] 링크 발견 ({source})")
                return self._click_domain_link(visible, domain)

        return False
    
    def _click_domain_link(self, visible_links, domain):
        """도메인 링크 클릭 (하이브리드)"""
        log(f"[발견] {domain} 링크 {len(visible_links)}개!")

        # 요소 위치에 따라 스크롤 방향 결정 (viewport 밖으로 나가지 않도록)
        first_link = visible_links[0]
        center_y = first_link["center_y"]
        screen_middle = self.adb.screen_height // 2

        if center_y < screen_middle:
            # 상단에 있으면 위로 스크롤 (요소를 아래로)
            extra = -random.randint(30, 80)
            log(f"[스크롤] 요소 상단({center_y}) → 위로 {abs(extra)}px")
        else:
            # 하단에 있으면 아래로 스크롤 (요소를 위로)
            extra = random.randint(30, 80)
            log(f"[스크롤] 요소 하단({center_y}) → 아래로 {extra}px")

        self.adb.scroll_down(extra)
        time.sleep(0.3)

        # 다시 확인 (하이브리드)
        links = self._find_all_links_by_domain_hybrid(domain)
        visible = [l for l in links if self.viewport_top <= l["center_y"] <= self.viewport_bottom]
        
        if visible:
            for click_try in range(3):
                selected = random.choice(visible)
                log(f"[클릭 {click_try + 1}/3] {selected['text'][:50]}...")
                self.adb.tap_element(selected)
                time.sleep(2)
                
                xml = self.adb.get_screen_xml(force=True)
                nx = self.adb.find_element_by_resource_id("nx_query", xml)
                
                if not nx.get("found"):
                    log("[성공] 페이지 이동!")
                    return True
                
                log("[재시도] 페이지 변경 안 됨")
        
        return False
    
    def _find_and_click_domain_in_page(self, domain):
        """현재 페이지에서 도메인 찾아서 클릭 (하이브리드: MobileCDP 우선)"""
        max_scrolls = 30
        short_scroll = int(self.adb.screen_height * 0.3)

        for scroll_count in range(max_scrolls):
            # 하이브리드 도메인 찾기
            links = self._find_all_links_by_domain_hybrid(domain)

            if links:
                visible = [l for l in links if self.viewport_top <= l["center_y"] <= self.viewport_bottom]

                if visible:
                    source = visible[0].get("source", "unknown")
                    log(f"[발견] {domain} 링크 {len(visible)}개! ({source})")

                    # 추가 랜덤 스크롤 (CDP 동일)
                    extra = random.randint(30, 80) * random.choice([1, -1])
                    self.adb.scroll_down(extra)
                    time.sleep(0.3)

                    # 다시 확인 (하이브리드)
                    links = self._find_all_links_by_domain_hybrid(domain)
                    visible = [l for l in links if self.viewport_top <= l["center_y"] <= self.viewport_bottom]

                    if visible:
                        for click_try in range(3):
                            selected = random.choice(visible)
                            log(f"[클릭 {click_try + 1}/3] {selected['text'][:50]}...")
                            self.adb.tap_element(selected)
                            time.sleep(2)

                            xml = self.adb.get_screen_xml(force=True)
                            nx = self.adb.find_element_by_resource_id("nx_query", xml)

                            if not nx.get("found"):
                                log("[성공] 페이지 이동!")
                                return True

                            log("[재시도] 페이지 변경 안 됨")

                        return False

            self.adb.scroll_down(short_scroll)

            if scroll_count % 10 == 0:
                log(f"[7단계] 스크롤 {scroll_count}/{max_scrolls}...")

        return False

    def _click_page_number(self, page_num):
        """페이지 번호 버튼 클릭 (CDP 동일)"""
        max_scroll = 15
        
        for _ in range(max_scroll):
            xml = self.adb.get_screen_xml(force=True)
            element = self.adb.find_element_by_text(str(page_num), partial=False, xml=xml)
            
            if element.get("found"):
                bounds = element.get("bounds", (0, 0, 0, 0))
                if bounds[0] == 0 and bounds[1] == 0 and bounds[2] == 0 and bounds[3] == 0:
                    self.adb.scroll_down()
                    time.sleep(0.2)
                    continue
                
                cy = element["center_y"]
                
                if self.viewport_top <= cy <= self.viewport_bottom:
                    self.adb.tap_element(element)
                    return True
                
                if cy > self.viewport_bottom:
                    self.adb.scroll_down()
                else:
                    self.adb.scroll_up()
            else:
                self.adb.scroll_down()
            
            time.sleep(0.2)
        
        return False
    
    # ========================================
    # 8단계: 체류
    # ========================================
    def step8_stay(self):
        log("=" * 50)
        log("[8단계] 타겟 사이트 체류")
        log("=" * 50)
        
        stay = random.uniform(NAVER_CONFIG.get("stay_min", 10), NAVER_CONFIG.get("stay_max", 20))
        log(f"[체류] {stay:.1f}초...")
        time.sleep(stay)
        return True
    
    # ========================================
    # 9단계: 뒤로가기
    # ========================================
    def step9_go_back(self, is_last=False):
        log("=" * 50)
        log("[9단계] 뒤로가기")
        log("=" * 50)
        
        if is_last:
            log("마지막 키워드 - 뒤로가기 생략")
            return True
        
        self.adb.press_back()
        random_delay(1.0, 2.0)
        log("[완료] 검색 페이지로 복귀")
        return True
    
    # ========================================
    # 전체 실행
    # ========================================
    def run(self, keyword, domain, search_in_total=True, go_to_more=True, is_last=False):
        log("=" * 60)
        log(f"검색 시작: '{keyword}' → {domain}")
        log(f"옵션: 통합={search_in_total}, 더보기={go_to_more}, 마지막={is_last}")
        log("=" * 60)
        
        # 1단계
        if not self.step1_go_to_naver():
            return "ERROR"
        
        # 2단계
        if not self.step2_click_search_box():
            return "RETRY"
        
        # 3단계
        if not self.step3_input_keyword(keyword):
            return "ERROR"
        
        # 4단계
        if not self.step4_execute_search():
            return "ERROR"
        
        # 4.5단계
        if search_in_total:
            if self.step4_5_find_in_total(domain):
                log(f"[성공] 통합에서 {domain} 클릭!")
                self.step8_stay()
                self.step9_go_back(is_last)
                return "DONE"
            
            if not go_to_more:
                return "NOTFOUND"
            
            log("통합에 없음, 더보기로...")
        
        if not go_to_more:
            return "NOTFOUND"
        
        # 5단계
        more_el = self.step5_scroll_to_more()
        if not more_el:
            return "RETRY"
        
        # 6단계
        if not self.step6_click_more(more_el):
            return "RETRY"
        
        # 7단계
        if not self.step7_find_domain(domain):
            return "NOTFOUND"
        
        log(f"[성공] {domain} 클릭!")
        
        # 8단계
        self.step8_stay()
        
        # 9단계
        self.step9_go_back(is_last)
        
        return "DONE"


# ============================================
# CDP 스크롤 정보 가져오기 (자동 브라우저 실행 + 캐시)
# ============================================
def get_cdp_scroll_info(keyword, domain, screen_width, screen_height, force_refresh=False):
    """CDP 스크롤 정보 가져오기

    - Chrome 자동 실행 (headless)
    - 10회마다 스크롤 정보 갱신
    - force_refresh=True면 강제 갱신

    Returns:
        dict: 스크롤 정보 또는 None
    """
    global _chrome_launcher, _scroll_cache

    if not CDP_AVAILABLE:
        log("[CDP] requests/websocket 모듈 없음")
        return None

    # 캐시 확인 (force_refresh가 아닐 때만)
    if not force_refresh:
        cached = _scroll_cache.get(keyword, domain)
        if cached:
            count = _scroll_cache.get_count(keyword, domain)
            refresh_interval = CDP_CONFIG.get("cache_refresh_interval", 10)
            log(f"[CDP] 캐시 사용 ({count}/{refresh_interval}회)")
            _scroll_cache.increment(keyword, domain)
            return cached

    log(f"[CDP] 스크롤 정보 갱신 (force={force_refresh})")

    # Chrome 자동 실행
    if _chrome_launcher is None:
        _chrome_launcher = ChromeLauncher(port=CDP_CONFIG.get("port", 9222))

    headless = CDP_CONFIG.get("headless", True)

    # Chrome 실행 (없으면 시작)
    if not _chrome_launcher.is_running():
        log(f"[CDP] Chrome 자동 실행 (headless={headless})...")
        if not _chrome_launcher.launch(headless=headless):
            log("[CDP] Chrome 실행 실패", "ERROR")
            return None

    # CDP 연결 시도
    cdp = CDPCalculator(port=CDP_CONFIG.get("port", 9222))

    if not cdp.connect():
        # 연결 실패시 Chrome 재시작 후 재시도
        log("[CDP] 연결 실패, Chrome 재시작 후 재시도...")
        _chrome_launcher.kill_existing()
        time.sleep(2)

        if not _chrome_launcher.launch(headless=headless, force_restart=True):
            log("[CDP] Chrome 재시작 실패", "ERROR")
            return None

        time.sleep(1)
        cdp = CDPCalculator(port=CDP_CONFIG.get("port", 9222))

        if not cdp.connect():
            log("[CDP] 재시도 후에도 연결 실패", "ERROR")
            return None

    try:
        cdp_info = cdp.calculate_scroll_info(keyword, domain, screen_width, screen_height)

        if cdp_info and cdp_info.get("calculated"):
            # 캐시에 저장
            _scroll_cache.set(keyword, domain, cdp_info)
            refresh_interval = CDP_CONFIG.get("cache_refresh_interval", 10)
            log(f"[CDP] 스크롤 정보 캐시됨 (다음 {refresh_interval - 1}회 재사용)")
        return cdp_info

    finally:
        cdp.close()


# ============================================
# 메인 (무한 재시도 루프 포함)
# ============================================
def main():
    from config import BROWSERS

    if len(sys.argv) < 3:
        print("사용법: python adb_auto.py 검색어 도메인 [검색모드] [폰번호] [마지막] [브라우저]")
        print("예시: python adb_auto.py 곤지암스키강습 sidecut.co.kr")
        print("예시: python adb_auto.py 곤지암스키강습 sidecut.co.kr total")
        print("예시: python adb_auto.py 곤지암스키강습 sidecut.co.kr more 1 1 samsung")
        print("")
        print("[검색모드] total=통합에서만, more=더보기에서, both=통합→더보기 (기본값)")
        print("[폰번호] config.py PHONES 키 (기본값: 1)")
        print("[마지막] 0=중간, 1=마지막 키워드")
        print("[브라우저] chrome, samsung, edge, opera, firefox (기본값: chrome)")
        return

    keyword = sys.argv[1]
    domain = sys.argv[2]

    # 검색 모드
    search_in_total = True
    go_to_more = True

    if len(sys.argv) >= 4:
        mode = sys.argv[3].lower()
        if mode == "total":
            search_in_total = True
            go_to_more = False
        elif mode == "more":
            search_in_total = False
            go_to_more = True
        else:
            search_in_total = True
            go_to_more = True

    phone_key = sys.argv[4] if len(sys.argv) >= 5 else "1"
    is_last = sys.argv[5] in ["1", "true", "last"] if len(sys.argv) >= 6 else False

    # 브라우저 선택
    browser = sys.argv[6].lower() if len(sys.argv) >= 7 else "chrome"
    if browser not in BROWSERS:
        print(f"[오류] 지원하지 않는 브라우저: {browser}")
        print(f"[지원 브라우저] {', '.join(BROWSERS.keys())}")
        return

    if phone_key not in PHONES:
        print(f"[오류] 폰 '{phone_key}' 없음")
        return

    phone_config = PHONES[phone_key]

    # ============================================
    # 무한 재시도 루프 (브라우저 실행 실패시 처음부터)
    # ============================================
    full_restart_count = 0

    while True:  # 무한 루프
        full_restart_count += 1

        print("\n" + "=" * 60)
        print(f"[ADB + CDP 통합 네이버 검색 v4] (시도 #{full_restart_count})")
        print(f"[검색어] {keyword}")
        print(f"[도메인] {domain}")
        print(f"[모드] 통합:{search_in_total}, 더보기:{go_to_more}")
        print(f"[폰] {phone_config.get('name', phone_key)}")
        print(f"[브라우저] {browser}")
        print(f"[마지막] {'YES' if is_last else 'NO'}")
        print("=" * 60)

        # ADB 연결
        adb = ADBController(phone_config)
        if not adb.connect():
            log(f"[무한재시도] ADB 연결 실패, 5초 후 재시도... (#{full_restart_count})")
            time.sleep(5)
            continue

        # 브라우저 데이터 초기화 (새 프로필)
        if ADB_CONFIG.get("clear_browser_data", False):
            # 선택된 브라우저의 패키지 사용
            browser_package = BROWSERS[browser]["package"]
            if not adb.clear_browser_data(browser_package):
                log("[무한재시도] 브라우저 초기화 실패, 처음부터 재시도...", "ERROR")
                time.sleep(3)
                continue  # 처음부터 다시 (ADB 재연결부터)

        # CDP 계산 (자동 브라우저 실행 + 캐시)
        cdp_info = None

        if go_to_more and CDP_AVAILABLE:
            # force_refresh: 전체 재시작시에만 강제 갱신
            force_refresh = (full_restart_count > 1)
            cdp_info = get_cdp_scroll_info(
                keyword, domain,
                adb.screen_width, adb.screen_height,
                force_refresh=force_refresh
            )

            # CDP 계산 실패시 재시도
            if cdp_info is None or not cdp_info.get("calculated"):
                log("[무한재시도] CDP 스크롤 계산 실패, 처음부터 재시도...", "ERROR")
                time.sleep(3)
                continue

        print("")

        # 자동화 실행 (브라우저 전달)
        automation = NaverSearchAutomation(adb, cdp_info, browser=browser)
        max_retry = NAVER_CONFIG.get("max_full_retry", 2)

        need_full_restart = False

        for retry in range(max_retry + 1):
            if retry > 0:
                log(f"\n[전체 재시도 {retry}/{max_retry}]")

            result = automation.run(keyword, domain, search_in_total, go_to_more, is_last)

            if result == "DONE":
                print("\n" + "=" * 60)
                print("[완료] 성공!")
                print("=" * 60)
                return  # 성공 → 종료

            elif result == "NOTFOUND":
                print("\n" + "=" * 60)
                print(f"[결과] {domain} 못 찾음")
                print("=" * 60)
                return  # 못 찾음 → 종료

            elif result == "RETRY" and retry < max_retry:
                continue

            elif result == "ERROR" or result == "RETRY":
                # 재시도 횟수 소진 또는 에러 → 처음부터 다시
                need_full_restart = True
                break

        if need_full_restart:
            log(f"\n[무한재시도] 전체 프로세스 재시작... (#{full_restart_count})")
            log("[무한재시도] CDP 정보 갱신 + ADB 재연결")
            time.sleep(3)
            continue

        # 여기까지 오면 알 수 없는 상태
        print("\n" + "=" * 60)
        print("[실패] 알 수 없는 오류")
        print("=" * 60)
        return


if __name__ == "__main__":
    main()