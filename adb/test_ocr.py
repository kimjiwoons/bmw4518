#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
OCR 테스트 스크립트
- 스크린샷 촬영 → OCR로 텍스트 찾기 → 클릭

사용법: python test_ocr.py [찾을텍스트] [클릭여부]
예시:
  python test_ocr.py                          # "검색결과 더보기" 찾기만
  python test_ocr.py "검색결과 더보기" click   # 찾고 클릭
  python test_ocr.py "네이버" click            # "네이버" 찾고 클릭
"""

import subprocess
import sys
import time

# OCR 관련
try:
    import easyocr
    import numpy as np
    from PIL import Image
    import io
    print("[OK] easyocr, numpy, PIL 로드 완료")
except ImportError as e:
    print(f"[ERROR] 필요한 패키지 설치: pip install easyocr numpy pillow")
    print(f"  오류: {e}")
    sys.exit(1)

# 설정
from config import PHONES, ADB_CONFIG

# ========================================
# ADB 함수들
# ========================================
def get_adb_address():
    """config에서 ADB 주소 가져오기"""
    for phone in PHONES:
        if PHONES[phone].get("adb_address"):
            return PHONES[phone]["adb_address"]
    return None

ADB_PATH = ADB_CONFIG.get("adb_path", "adb")
ADB_ADDRESS = get_adb_address()

print(f"[INFO] ADB 주소: {ADB_ADDRESS}")

def run_adb(command, timeout=30):
    """ADB 명령 실행"""
    full_cmd = f'{ADB_PATH} -s {ADB_ADDRESS} {command}'
    try:
        result = subprocess.run(full_cmd, shell=True, capture_output=True, timeout=timeout)
        return result
    except Exception as e:
        print(f"[ERROR] ADB 실행 실패: {e}")
        return None

def take_screenshot():
    """스크린샷 촬영 → PIL Image"""
    print("[INFO] 스크린샷 촬영 중...")
    cmd = f'{ADB_PATH} -s {ADB_ADDRESS} exec-out screencap -p'
    result = subprocess.run(cmd, shell=True, capture_output=True, timeout=10)
    if result.returncode == 0 and result.stdout:
        image = Image.open(io.BytesIO(result.stdout))
        print(f"[OK] 스크린샷: {image.size}")
        return image
    print("[ERROR] 스크린샷 실패")
    return None

def tap(x, y):
    """화면 탭"""
    print(f"[TAP] ({x}, {y})")
    run_adb(f'shell input tap {x} {y}')

# ========================================
# OCR 함수
# ========================================
OCR_READER = None

def init_ocr():
    """OCR 리더 초기화"""
    global OCR_READER
    if OCR_READER is None:
        print("[INFO] EasyOCR 초기화 중... (최초 1회)")
        OCR_READER = easyocr.Reader(['ko', 'en'], gpu=False)
        print("[OK] EasyOCR 초기화 완료")
    return OCR_READER

def find_text_ocr(target_text, do_click=False):
    """OCR로 텍스트 찾기"""

    # 1. 스크린샷
    screenshot = take_screenshot()
    if not screenshot:
        return None

    # 2. 리사이즈 (메모리 절약)
    original_size = screenshot.size
    scale = 0.5
    new_size = (int(original_size[0] * scale), int(original_size[1] * scale))
    screenshot_resized = screenshot.resize(new_size, Image.LANCZOS)
    print(f"[INFO] 리사이즈: {original_size} → {new_size}")

    # 3. OCR 실행
    print(f"[INFO] OCR 실행 중... ('{target_text}' 찾는 중)")
    reader = init_ocr()
    img_array = np.array(screenshot_resized)
    results = reader.readtext(img_array)

    print(f"[INFO] 감지된 텍스트 {len(results)}개:")

    found = None
    for i, (bbox, text, confidence) in enumerate(results):
        # 좌표 계산 (원본 크기로 복원)
        x1, y1 = bbox[0]
        x2, y2 = bbox[2]
        center_x = int((x1 + x2) / 2 / scale)
        center_y = int((y1 + y2) / 2 / scale)

        # 매칭 여부
        match = "★" if target_text in text else " "
        print(f"  [{match}] #{i}: '{text[:30]}' → ({center_x}, {center_y}) conf={confidence:.2f}")

        if target_text in text and found is None:
            found = {
                "text": text,
                "x": center_x,
                "y": center_y,
                "confidence": confidence
            }

    # 4. 결과
    if found:
        print(f"\n[FOUND] '{target_text}' 발견!")
        print(f"  좌표: ({found['x']}, {found['y']})")
        print(f"  신뢰도: {found['confidence']:.2f}")

        if do_click:
            print(f"\n[CLICK] 클릭 실행...")
            time.sleep(0.5)
            tap(found['x'], found['y'])
            print("[OK] 클릭 완료!")

        return found
    else:
        print(f"\n[NOT FOUND] '{target_text}' 못 찾음")
        return None

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

    print("=" * 50)
    print("OCR 테스트")
    print("=" * 50)
    print(f"찾을 텍스트: '{target}'")
    print(f"클릭 여부: {do_click}")
    print("=" * 50)

    result = find_text_ocr(target, do_click)

    print("\n" + "=" * 50)
    if result:
        print(f"[결과] 성공! 좌표: ({result['x']}, {result['y']})")
    else:
        print("[결과] 실패 - 텍스트를 찾지 못함")
    print("=" * 50)
