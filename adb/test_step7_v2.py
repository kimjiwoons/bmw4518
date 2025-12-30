#!/usr/bin/env python3
"""
7단계 테스트 스크립트 v2 - CDP 없이 uiautomator + 영역 추정

도메인 텍스트 위치를 기준으로 제목/설명 영역을 추정하여 랜덤 클릭

네이버 검색 결과 구조:
┌─────────────────────────────┐ ← 제목 영역 (도메인 위 약 50~80px)
│  사이드컷 헤어샵 - 강남점    │
├─────────────────────────────┤
│  sidecut.co.kr              │ ← 도메인 (uiautomator로 찾음)
├─────────────────────────────┤
│  › lessons  › about        │ ← 서브링크 (클릭 제외)
├─────────────────────────────┤
│  전문 헤어 서비스 제공...    │ ← 설명 영역 (서브링크 아래)
└─────────────────────────────┘

사용법:
    python test_step7_v2.py <ADB주소> <도메인> [브라우저]

예시:
    python test_step7_v2.py 98.98.125.37:21306 sidecut.co.kr chrome
"""

import sys
import os
import random
import time
import re

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from adb_auto import ADBController, log


class DomainClickArea:
    """도메인 클릭 영역 계산"""

    # 네이버 검색 결과 레이아웃 상수 (픽셀)
    TITLE_HEIGHT = 45  # 제목 영역 높이
    TITLE_GAP = 8      # 제목과 도메인 사이 간격
    DESC_GAP = 8       # 도메인/서브링크와 설명 사이 간격
    DESC_HEIGHT = 40   # 설명 영역 높이
    SUBLINK_HEIGHT = 35  # 서브링크 영역 높이

    def __init__(self, domain_bounds, has_sublink=False, screen_width=720):
        """
        Args:
            domain_bounds: 도메인 텍스트 bounds (x1, y1, x2, y2)
            has_sublink: 서브링크 존재 여부
            screen_width: 화면 너비
        """
        self.x1, self.y1, self.x2, self.y2 = domain_bounds
        self.has_sublink = has_sublink
        self.screen_width = screen_width

        # 클릭 영역 계산
        self.areas = self._calculate_areas()

    def _calculate_areas(self):
        """도메인/제목/설명 클릭 영역 계산"""
        areas = []

        # 화면 너비의 90%를 클릭 영역으로 사용 (좌우 여백 5%)
        left_margin = int(self.screen_width * 0.05)
        right_margin = int(self.screen_width * 0.95)

        # 1. 제목 영역 (도메인 위)
        title_y2 = self.y1 - self.TITLE_GAP
        title_y1 = title_y2 - self.TITLE_HEIGHT
        if title_y1 > 0:  # 화면 위로 벗어나지 않으면
            areas.append({
                "type": "title",
                "bounds": (left_margin, title_y1, right_margin, title_y2),
                "center_y": (title_y1 + title_y2) // 2
            })

        # 2. 도메인 영역 (현재 bounds)
        areas.append({
            "type": "domain",
            "bounds": (self.x1, self.y1, self.x2, self.y2),
            "center_y": (self.y1 + self.y2) // 2
        })

        # 3. 설명 영역 (도메인/서브링크 아래)
        if self.has_sublink:
            # 서브링크가 있으면 그 아래
            desc_y1 = self.y2 + self.SUBLINK_HEIGHT + self.DESC_GAP
        else:
            # 서브링크 없으면 도메인 바로 아래
            desc_y1 = self.y2 + self.DESC_GAP

        desc_y2 = desc_y1 + self.DESC_HEIGHT
        areas.append({
            "type": "desc",
            "bounds": (left_margin, desc_y1, right_margin, desc_y2),
            "center_y": (desc_y1 + desc_y2) // 2
        })

        return areas

    def get_random_click_position(self):
        """랜덤 영역 선택 후 그 안에서 랜덤 좌표 반환"""
        if not self.areas:
            return None, None, None

        # 랜덤 영역 선택
        selected = random.choice(self.areas)
        area_type = selected["type"]
        x1, y1, x2, y2 = selected["bounds"]

        # 영역 내 랜덤 좌표 (가장자리 15% 제외)
        margin_x = max(5, int((x2 - x1) * 0.15))
        margin_y = max(3, int((y2 - y1) * 0.15))

        click_x = random.randint(x1 + margin_x, max(x1 + margin_x, x2 - margin_x))
        click_y = random.randint(y1 + margin_y, max(y1 + margin_y, y2 - margin_y))

        return click_x, click_y, area_type

    def log_areas(self):
        """영역 정보 로깅"""
        log(f"[영역] 도메인 bounds: [{self.x1},{self.y1}][{self.x2},{self.y2}]")
        for area in self.areas:
            x1, y1, x2, y2 = area["bounds"]
            log(f"  [{area['type']}] ({x1},{y1})-({x2},{y2}) 크기:{x2-x1}x{y2-y1}")


def find_domain_and_sublinks(adb, domain):
    """도메인과 서브링크 찾기 (기존 adb 함수 사용)

    Returns:
        (domain_bounds, has_sublink): 도메인 bounds와 서브링크 존재 여부
    """
    # 기존 adb_auto.py의 find_all_elements_with_domain 사용
    links = adb.find_all_elements_with_domain(domain)

    log(f"[DEBUG] 도메인 링크 {len(links)}개 발견")

    if not links:
        # 서브링크도 찾아보기 (서브페이지 포함)
        base_domain = domain.split('/')[0]
        xml = adb.get_screen_xml(force=True)

        # 서브링크 패턴 확인
        has_sublink = False
        if xml and f"{base_domain}›" in xml or f"{base_domain} ›" in xml:
            has_sublink = True
            log("[DEBUG] 서브링크 존재 확인")

        return None, has_sublink

    # 첫 번째 링크의 bounds 사용
    first_link = links[0]
    domain_bounds = first_link.get("bounds")
    log(f"[DEBUG] 도메인 bounds: {domain_bounds}")

    # 서브링크 존재 여부 확인 (XML에서 직접 확인)
    xml = adb.get_screen_xml()
    has_sublink = False
    base_domain = domain.split('/')[0]
    if xml:
        # 서브링크 패턴: "sidecut.co.kr›" 또는 "sidecut.co.kr >"
        if f"{base_domain}›" in xml or f"{base_domain} ›" in xml or f"{base_domain}/" in xml:
            has_sublink = True
            log("[DEBUG] 서브링크 존재")

    return domain_bounds, has_sublink


def create_adb(adb_address):
    """ADB 컨트롤러 생성"""
    phone_config = {
        "adb_address": adb_address,
        "screen_width": 720,
        "screen_height": 1440
    }
    return ADBController(phone_config)


def test_domain_click(adb_address, domain, browser="chrome", do_click=False):
    """도메인 클릭 테스트"""
    log("=" * 60)
    log(f"[TEST] 도메인 클릭 테스트: {domain}")
    log("=" * 60)

    # 1. ADB 연결
    adb = create_adb(adb_address)
    if not adb.connect():
        log("[FAIL] ADB 연결 실패")
        return False

    log(f"[OK] ADB 연결: {adb_address} ({adb.screen_width}x{adb.screen_height})")

    # 2. 도메인 및 서브링크 찾기
    log("\n[STEP 1] 도메인 찾기...")
    domain_bounds, has_sublink = find_domain_and_sublinks(adb, domain)

    if not domain_bounds:
        log("[FAIL] 도메인을 찾을 수 없음")
        return False

    log(f"[OK] 도메인 발견, 서브링크: {'있음' if has_sublink else '없음'}")

    # 3. 클릭 영역 계산
    log("\n[STEP 2] 클릭 영역 계산...")
    click_area = DomainClickArea(domain_bounds, has_sublink, adb.screen_width)
    click_area.log_areas()

    # 4. 랜덤 클릭 좌표 계산
    log("\n[STEP 3] 랜덤 클릭 좌표 선택...")
    for i in range(5):  # 5번 샘플 출력
        x, y, area_type = click_area.get_random_click_position()
        log(f"  샘플 {i+1}: [{area_type}] ({x}, {y})")

    # 5. 실제 클릭 (옵션)
    x, y, area_type = click_area.get_random_click_position()
    log(f"\n[선택됨] [{area_type}] ({x}, {y})")

    if do_click:
        log(f"\n[클릭] ({x}, {y})")
        adb.tap(x, y, randomize=False)
        time.sleep(2)

        # 페이지 전환 확인
        xml = adb.get_screen_xml(force=True)
        nx = adb.find_element_by_resource_id("nx_query", xml)
        if not nx.get("found"):
            log("[성공] 페이지 이동!")
            return True
        else:
            log("[실패] 페이지 변경 안 됨")
            return False
    else:
        response = input("\n실제로 클릭하시겠습니까? (y/n): ").strip().lower()
        if response == 'y':
            log(f"[클릭] ({x}, {y})")
            adb.tap(x, y, randomize=False)
            log("[완료]")
            return True

    return True


def test_multiple_clicks(adb_address, domain, count=10):
    """여러 번 클릭 테스트 (클릭 분포 확인)"""
    log("=" * 60)
    log(f"[TEST] 클릭 분포 테스트: {count}회")
    log("=" * 60)

    adb = create_adb(adb_address)
    if not adb.connect():
        log("[FAIL] ADB 연결 실패")
        return

    domain_bounds, has_sublink = find_domain_and_sublinks(adb, domain)
    if not domain_bounds:
        log("[FAIL] 도메인 못 찾음")
        return

    click_area = DomainClickArea(domain_bounds, has_sublink, adb.screen_width)

    # 클릭 분포 집계
    type_counts = {"title": 0, "domain": 0, "desc": 0}

    for i in range(count):
        x, y, area_type = click_area.get_random_click_position()
        type_counts[area_type] = type_counts.get(area_type, 0) + 1

    log("\n[클릭 분포]")
    for area_type, cnt in type_counts.items():
        pct = cnt / count * 100
        bar = "█" * int(pct / 5)
        log(f"  {area_type:8s}: {cnt:3d}회 ({pct:5.1f}%) {bar}")


def main():
    if len(sys.argv) < 3:
        print(__doc__)
        print("\n사용법: python test_step7_v2.py <ADB주소> <도메인> [브라우저]")
        print("예시: python test_step7_v2.py 98.98.125.37:21306 sidecut.co.kr chrome")
        sys.exit(1)

    adb_address = sys.argv[1]
    domain = sys.argv[2]
    browser = sys.argv[3] if len(sys.argv) > 3 else "chrome"

    # 클릭 분포 테스트
    test_multiple_clicks(adb_address, domain, count=30)

    print("\n" + "=" * 60)

    # 실제 클릭 테스트
    test_domain_click(adb_address, domain, browser, do_click=False)


if __name__ == "__main__":
    main()
