#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
OCR 테스트 스크립트 (pytesseract 버전)
"""

import subprocess
import sys
import time

def log(msg):
    print(msg, flush=True)

log("[1] 스크립트 시작")

# pytesseract
try:
    log("[2] pytesseract import 중...")
    import pytesseract
    log("[3] PIL import 중...")
    from PIL import Image
    import io
    log("[OK] 패키지 로드 완료")
except ImportError as e:
    log(f"[ERROR] 패키지 오류: {e}")
    log("설치: pip install pytesseract pillow")
    sys.exit(1)

# Tesseract 경로 설정 (Windows)
pytesseract.pytesseract.tesseract_cmd = r'C:\Program Files\Tesseract-OCR\tesseract.exe'

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
        image = Image.open(io.BytesIO(result.stdout))
        log(f"[SCREEN] 완료: {image.size}")
        return image
    log("[SCREEN] 실패!")
    return None

def tap(x, y):
    log(f"[TAP] ({x}, {y})")
    cmd = f'{ADB_PATH} -s {ADB_ADDRESS} shell input tap {x} {y}'
    subprocess.run(cmd, shell=True)

# ========================================
# OCR (pytesseract)
# ========================================
def do_ocr_test(target_text, do_click=False):
    log("=" * 50)
    log(f"[TEST] 찾을 텍스트: '{target_text}'")
    log(f"[TEST] 클릭 여부: {do_click}")
    log("=" * 50)

    try:
        # 1. 스크린샷
        log("[STEP1] 스크린샷...")
        screenshot = take_screenshot()
        if not screenshot:
            log("[FAIL] 스크린샷 실패")
            return

        # 2. 이미지 전처리 (인식률 향상)
        log("[STEP2] 이미지 전처리...")
        # RGBA → RGB
        if screenshot.mode == 'RGBA':
            screenshot = screenshot.convert('RGB')
        # 그레이스케일 변환
        screenshot = screenshot.convert('L')
        # 대비 증가
        from PIL import ImageEnhance
        enhancer = ImageEnhance.Contrast(screenshot)
        screenshot = enhancer.enhance(2.0)  # 대비 2배
        log(f"[STEP2] mode: {screenshot.mode}, size: {screenshot.size}")

        # 3. OCR 실행 (한글) - PSM 6: 단일 텍스트 블록으로 인식
        log("[STEP3] pytesseract OCR 실행 (lang=kor, psm=6)...")
        # 박스 정보 포함해서 OCR
        custom_config = r'--oem 3 --psm 6'
        data = pytesseract.image_to_data(screenshot, lang='kor', config=custom_config, output_type=pytesseract.Output.DICT)
        log(f"[STEP3] 완료! 감지된 항목: {len(data['text'])}개")

        # 4. 결과 분석
        log("[STEP4] 결과 분석...")
        found = None
        n_boxes = len(data['text'])

        for i in range(n_boxes):
            text = data['text'][i].strip()
            if not text:
                continue

            x = data['left'][i]
            y = data['top'][i]
            w = data['width'][i]
            h = data['height'][i]
            conf = int(data['conf'][i])

            cx = x + w // 2
            cy = y + h // 2

            mark = "★" if target_text in text else " "
            if conf > 0:  # 신뢰도가 있는 것만 출력
                log(f"  [{mark}] '{text[:20]}' ({cx},{cy}) conf={conf}")

            if target_text in text and found is None:
                found = {"x": cx, "y": cy, "text": text, "conf": conf}

        # 5. 최종 결과
        log("=" * 50)
        if found:
            log(f"[SUCCESS] '{target_text}' 발견!")
            log(f"  좌표: ({found['x']}, {found['y']})")
            log(f"  신뢰도: {found['conf']}")

            if do_click:
                log("[CLICK] 클릭 실행...")
                time.sleep(0.3)
                tap(found['x'], found['y'])
                log("[CLICK] 완료!")
        else:
            log(f"[FAIL] '{target_text}' 못 찾음")
        log("=" * 50)

    except Exception as e:
        log(f"[ERROR] 예외 발생!")
        log(f"[ERROR] 타입: {type(e).__name__}")
        log(f"[ERROR] 내용: {e}")
        import traceback
        traceback.print_exc()

# ========================================
# 메인
# ========================================
if __name__ == "__main__":
    target = "검색결과 더보기"
    do_click = False

    if len(sys.argv) > 1:
        target = sys.argv[1]
    if len(sys.argv) > 2 and sys.argv[2].lower() == "click":
        do_click = True

    do_ocr_test(target, do_click)
    log("[END] 스크립트 종료")
