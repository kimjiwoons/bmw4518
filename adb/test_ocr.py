#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
OCR 테스트 스크립트
"""

import subprocess
import sys
import time

def log(msg):
    """즉시 출력 (버퍼 flush)"""
    print(msg, flush=True)

log("[1] 스크립트 시작")

# OCR 관련
try:
    log("[2] easyocr import 중...")
    import easyocr
    log("[3] numpy import 중...")
    import numpy as np
    log("[4] PIL import 중...")
    from PIL import Image
    import io
    log("[OK] 모든 패키지 로드 완료")
except ImportError as e:
    log(f"[ERROR] 패키지 오류: {e}")
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
# OCR
# ========================================
OCR_READER = None

def do_ocr_test(target_text, do_click=False):
    global OCR_READER

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

        # 2. 리사이즈 (메모리 부족 방지: 30%)
        log("[STEP2] 리사이즈...")
        scale = 0.3
        orig = screenshot.size
        new_size = (int(orig[0] * scale), int(orig[1] * scale))
        resized = screenshot.resize(new_size, Image.LANCZOS)
        log(f"[STEP2] {orig} → {new_size} (scale={scale})")

        # 3. OCR 초기화
        log("[STEP3] OCR 초기화...")
        if OCR_READER is None:
            log("[STEP3] EasyOCR Reader 생성 중... (오래 걸림)")
            OCR_READER = easyocr.Reader(['ko', 'en'], gpu=False)
            log("[STEP3] Reader 생성 완료!")
        else:
            log("[STEP3] 기존 Reader 사용")

        # 4. numpy 변환
        log("[STEP4] numpy 변환...")
        img_array = np.array(resized)
        log(f"[STEP4] shape: {img_array.shape}, dtype: {img_array.dtype}")

        # 5. OCR 실행
        log("[STEP5] readtext 실행... (시간 소요)")
        results = OCR_READER.readtext(img_array)
        log(f"[STEP5] 완료! 감지된 텍스트: {len(results)}개")

        # 6. 결과 출력
        log("[STEP6] 결과 분석...")
        found = None
        for i, (bbox, text, conf) in enumerate(results):
            x1, y1 = bbox[0]
            x2, y2 = bbox[2]
            cx = int((x1 + x2) / 2 / scale)
            cy = int((y1 + y2) / 2 / scale)

            mark = "★" if target_text in text else " "
            log(f"  [{mark}] #{i}: '{text[:25]}' ({cx},{cy}) conf={conf:.2f}")

            if target_text in text and found is None:
                found = {"x": cx, "y": cy, "text": text, "conf": conf}

        # 7. 최종 결과
        log("=" * 50)
        if found:
            log(f"[SUCCESS] '{target_text}' 발견!")
            log(f"  좌표: ({found['x']}, {found['y']})")
            log(f"  신뢰도: {found['conf']:.2f}")

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
