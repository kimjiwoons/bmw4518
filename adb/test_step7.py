#!/usr/bin/env python3
"""
7단계 테스트 스크립트 - 도메인/제목/설명 랜덤 클릭 테스트

사용법:
    python test_step7.py <ADB주소> <도메인> [브라우저]

예시:
    python test_step7.py 98.98.125.37:21306 sidecut.co.kr chrome
    python test_step7.py 98.98.125.37:21306 sidecut.co.kr samsung

사전 조건:
    - 브라우저에서 네이버 검색 결과 페이지가 열려있어야 함
    - 도메인이 화면에 보이는 상태여야 함 (또는 스크롤 몇번으로 찾을 수 있는 위치)
"""

import sys
import os

# 현재 디렉토리를 path에 추가
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from adb_auto import ADBController, NaverSearchAutomation, MobileCDP, log


def test_mobile_cdp_connection(adb_address, browser):
    """MobileCDP 연결 테스트"""
    log("=" * 50)
    log("[TEST] MobileCDP 연결 테스트")
    log("=" * 50)

    cdp = MobileCDP(adb_address, browser=browser)
    if cdp.connect():
        log(f"[OK] MobileCDP 연결 성공: {browser}")
        return cdp
    else:
        log(f"[FAIL] MobileCDP 연결 실패: {browser}")
        return None


def test_find_domain_links(cdp, domain):
    """도메인 링크 찾기 테스트"""
    log("=" * 50)
    log(f"[TEST] 도메인 링크 찾기: {domain}")
    log("=" * 50)

    if not cdp or not cdp.connected:
        log("[FAIL] MobileCDP 연결 안 됨")
        return []

    links = cdp.find_all_links_by_domain(domain)
    log(f"[결과] {len(links)}개 링크 발견")

    for i, link in enumerate(links):
        link_type = link.get('link_type', 'unknown')
        text = link.get('text', '')[:40]
        width = link.get('width', 0)
        height = link.get('height', 0)
        log(f"  [{i+1}] [{link_type}] {text}... ({width}x{height})")

    return links


def test_step7(adb_address, domain, browser="chrome"):
    """7단계 전체 테스트"""
    log("=" * 50)
    log(f"[TEST] 7단계 테스트: {domain} ({browser})")
    log("=" * 50)

    # 1. ADB 연결
    adb = ADBController(adb_address)
    if not adb.connect():
        log("[FAIL] ADB 연결 실패")
        return False

    log(f"[OK] ADB 연결: {adb_address} ({adb.screen_width}x{adb.screen_height})")

    # 2. NaverSearchAutomation 생성
    auto = NaverSearchAutomation(adb, cdp_info=None, browser=browser)

    # 3. MobileCDP 초기화
    auto._init_mobile_cdp()

    if auto.mobile_cdp and auto.mobile_cdp.connected:
        log(f"[OK] MobileCDP 활성화")
    else:
        log(f"[WARN] MobileCDP 비활성화, uiautomator 사용")

    # 4. 도메인 링크 찾기 (하이브리드)
    log("")
    log("=" * 50)
    log("[TEST] 하이브리드 도메인 찾기")
    log("=" * 50)

    links = auto._find_all_links_by_domain_hybrid(domain)
    log(f"[결과] {len(links)}개 링크 발견")

    for i, link in enumerate(links):
        link_type = link.get('link_type', 'unknown')
        source = link.get('source', 'unknown')
        text = link.get('text', '')[:40]
        bounds = link.get('bounds', (0,0,0,0))
        size = f"{bounds[2]-bounds[0]}x{bounds[3]-bounds[1]}"
        log(f"  [{i+1}] [{source}] [{link_type}] {text}... ({size})")

    # 5. 클릭 테스트 (실제 클릭하지 않음, 확인만)
    visible = [l for l in links if auto.viewport_top <= l["center_y"] <= auto.viewport_bottom]
    log(f"\n[INFO] 뷰포트 내 링크: {len(visible)}개")

    if visible:
        import random
        selected = random.choice(visible)
        link_type = selected.get('link_type', 'unknown')
        bounds = selected.get('bounds', (0,0,0,0))
        log(f"[선택됨] [{link_type}] {selected['text'][:40]}...")
        log(f"[클릭영역] bounds={bounds}, 크기={bounds[2]-bounds[0]}x{bounds[3]-bounds[1]}px")

        # 랜덤 클릭 좌표 계산 (실제 클릭은 안 함)
        x1, y1, x2, y2 = bounds
        margin_x = max(2, int((x2 - x1) * 0.15))
        margin_y = max(2, int((y2 - y1) * 0.15))
        click_x = random.randint(x1 + margin_x, max(x1 + margin_x, x2 - margin_x))
        click_y = random.randint(y1 + margin_y, max(y1 + margin_y, y2 - margin_y))
        log(f"[랜덤좌표] ({click_x}, {click_y})")

        # 실제 클릭?
        response = input("\n실제로 클릭하시겠습니까? (y/n): ").strip().lower()
        if response == 'y':
            log(f"[클릭] ({click_x}, {click_y})")
            adb.tap(click_x, click_y, randomize=False)
            log("[완료]")
        else:
            log("[스킵] 클릭 안 함")

    return True


def main():
    if len(sys.argv) < 3:
        print(__doc__)
        print("\n사용법: python test_step7.py <ADB주소> <도메인> [브라우저]")
        print("예시: python test_step7.py 98.98.125.37:21306 sidecut.co.kr chrome")
        sys.exit(1)

    adb_address = sys.argv[1]
    domain = sys.argv[2]
    browser = sys.argv[3] if len(sys.argv) > 3 else "chrome"

    # MobileCDP 연결 테스트
    cdp = test_mobile_cdp_connection(adb_address, browser)

    if cdp:
        # 도메인 링크 찾기 테스트
        test_find_domain_links(cdp, domain)
        cdp.disconnect()

    print("\n" + "=" * 50)
    print("[전체 테스트 시작]")
    print("=" * 50 + "\n")

    # 전체 7단계 테스트
    test_step7(adb_address, domain, browser)


if __name__ == "__main__":
    main()
