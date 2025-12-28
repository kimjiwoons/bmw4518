#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
이미지 템플릿 매칭 테스트
- 저장된 템플릿 이미지를 스크린샷에서 찾아 클릭
"""

import subprocess
import sys
import time
import random

def log(msg):
    print(msg, flush=True)

log("[1] 스크립트 시작")

try:
    log("[2] opencv import 중...")
    import cv2
    import numpy as np
    log("[OK] 패키지 로드 완료")
except ImportError as e:
    log(f"[ERROR] 패키지 오류: {e}")
    log("설치: pip install opencv-python numpy")
    sys.exit(1)

# 설정
from config import PHONES, ADB_CONFIG

def get_adb_address():
    for phone in PHONES:
        if PHONES[phone].get("adb_address"):
            return PHONES[phone]["adb_address"]
    return None

ADB_PATH = ADB_CONFIG.get("adb_path", "adb")
ADB_ADDRESS = get_adb_address()
log(f"[INFO] ADB: {ADB_ADDRESS}")

# ========================================
# ADB 함수
# ========================================
def take_screenshot():
    log("[SCREEN] 스크린샷 촬영...")
    cmd = f'{ADB_PATH} -s {ADB_ADDRESS} exec-out screencap -p'
    result = subprocess.run(cmd, shell=True, capture_output=True, timeout=10)
    if result.returncode == 0 and result.stdout:
        img_array = np.frombuffer(result.stdout, dtype=np.uint8)
        img = cv2.imdecode(img_array, cv2.IMREAD_COLOR)
        if img is not None:
            log(f"[SCREEN] 완료: {img.shape[1]}x{img.shape[0]}")
            return img
    log("[SCREEN] 실패!")
    return None

def tap(x, y):
    log(f"[TAP] ({x}, {y})")
    cmd = f'{ADB_PATH} -s {ADB_ADDRESS} shell input tap {x} {y}'
    subprocess.run(cmd, shell=True)

def save_screenshot(filename="screenshot.png"):
    """현재 화면 저장"""
    img = take_screenshot()
    if img is not None:
        cv2.imwrite(filename, img)
        log(f"[SAVE] {filename} 저장 완료!")
        return True
    return False

# ========================================
# 템플릿 매칭
# ========================================
def find_template(template_path, threshold=0.8, do_click=False):
    """템플릿 이미지를 화면에서 찾기"""

    log("=" * 50)
    log(f"[FIND] 템플릿: {template_path}")
    log(f"[FIND] 임계값: {threshold}, 클릭: {do_click}")
    log("=" * 50)

    try:
        # 1. 템플릿 로드
        log("[STEP1] 템플릿 로드...")
        template = cv2.imread(template_path)
        if template is None:
            log(f"[ERROR] 파일 없음: {template_path}")
            return None
        h, w = template.shape[:2]
        log(f"[STEP1] 크기: {w}x{h}")

        # 2. 스크린샷
        log("[STEP2] 스크린샷...")
        screenshot = take_screenshot()
        if screenshot is None:
            return None

        # 3. 매칭
        log("[STEP3] 매칭 중...")
        result = cv2.matchTemplate(screenshot, template, cv2.TM_CCOEFF_NORMED)
        min_val, max_val, min_loc, max_loc = cv2.minMaxLoc(result)
        log(f"[STEP3] 유사도: {max_val:.3f}")

        # 4. 결과
        log("=" * 50)
        if max_val >= threshold:
            # 템플릿 영역 좌표
            x1, y1 = max_loc[0], max_loc[1]
            x2, y2 = x1 + w, y1 + h
            cx = x1 + w // 2
            cy = y1 + h // 2
            log(f"[SUCCESS] 발견! 영역: ({x1},{y1})-({x2},{y2}), 중심: ({cx},{cy})")

            if do_click:
                # 템플릿 영역 안에서 랜덤 클릭 (가장자리 10% 제외)
                margin_x = int(w * 0.1)
                margin_y = int(h * 0.1)
                rand_x = random.randint(x1 + margin_x, x2 - margin_x)
                rand_y = random.randint(y1 + margin_y, y2 - margin_y)
                log(f"[CLICK] 랜덤 위치: ({rand_x}, {rand_y})")
                time.sleep(0.3)
                tap(rand_x, rand_y)
                log("[CLICK] 완료!")
            return {"x": cx, "y": cy, "conf": max_val, "bounds": (x1, y1, x2, y2)}
        else:
            log(f"[FAIL] 못 찾음 ({max_val:.3f} < {threshold})")
            return None

    except Exception as e:
        log(f"[ERROR] {e}")
        import traceback
        traceback.print_exc()
        return None

# ========================================
# 메인
# ========================================
if __name__ == "__main__":
    if len(sys.argv) < 2:
        log("")
        log("사용법:")
        log("  1. 스크린샷 저장:  python test_template.py save")
        log("  2. 템플릿 찾기:    python test_template.py find template.png")
        log("  3. 찾고 클릭:      python test_template.py find template.png click")
        log("")
        sys.exit(0)

    cmd = sys.argv[1]

    if cmd == "save":
        save_screenshot("screenshot.png")
        log("")
        log("다음 단계:")
        log("1. screenshot.png를 그림판으로 열기")
        log("2. '검색결과 더보기' 부분만 선택해서 잘라내기")
        log("3. template.png로 저장")
        log("4. python test_template.py find template.png click")

    elif cmd == "find":
        if len(sys.argv) < 3:
            log("[ERROR] 템플릿 파일 경로 필요!")
            sys.exit(1)
        template_path = sys.argv[2]
        do_click = len(sys.argv) > 3 and sys.argv[3].lower() == "click"
        find_template(template_path, threshold=0.7, do_click=do_click)

    log("[END] 종료")
