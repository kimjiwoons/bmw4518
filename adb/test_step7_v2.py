#!/usr/bin/env python3
"""
7단계 테스트 스크립트 v2 - CDP 없이 uiautomator로 도메인/제목/설명 찾기

XML에서 정확한 좌표를 찾아서 랜덤 클릭 (추정치 아님!)

네이버 검색 결과 구조 (실제 XML 분석 결과):
┌─────────────────────────────┐ y=689
│  sidecut.co.kr              │ ← 도메인 (text 속성)
├─────────────────────────────┤ y=740
│  곤지암 리조트 스키강습...   │ ← 제목 (content-desc 속성)
├─────────────────────────────┤ y=829
│  강습요금 · 대표자 소개 · ...│ ← 서브링크 (제외)
├─────────────────────────────┤ y=877
│  곤지암 리조트에서 20년...   │ ← 설명 (content-desc 속성)
└─────────────────────────────┘

사용법:
    python test_step7_v2.py <ADB주소> <도메인> [회사명키워드]

예시:
    python test_step7_v2.py 98.98.125.37:21306 sidecut.co.kr 사이드컷
"""

import sys
import os
import random
import time
import re

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from adb_auto import ADBController, log


# ============================================
# 설정 - 제목/설명 찾을 때 수정할 부분
# ============================================
CLICK_CONFIG = {
    # 제목 찾기: content-desc에 이 키워드가 포함되고, 도메인 아래 100px 이내
    "title_keywords": [],  # 실행 시 회사명으로 설정됨

    # 설명 최소 길이 (이 이상이면 설명으로 판단)
    "desc_min_length": 50,

    # 서브링크 키워드 (이 텍스트가 있고 짧은 텍스트면 서브링크로 판단)
    "sublink_keywords": ["강습요금", "대표자", "소개", "안내", "후기", "코치진"],

    # 서브링크 최대 길이 (이 길이 이하일 때만 서브링크 키워드 체크)
    "sublink_max_length": 10,

    # 도메인과 제목/설명 사이 최대 거리 (px)
    "max_distance_from_domain": 300,
}


class ClickableArea:
    """클릭 가능 영역"""
    def __init__(self, area_type, bounds, text=""):
        self.type = area_type  # "domain", "title", "desc"
        self.bounds = bounds   # (x1, y1, x2, y2)
        self.text = text

    @property
    def center_x(self):
        return (self.bounds[0] + self.bounds[2]) // 2

    @property
    def center_y(self):
        return (self.bounds[1] + self.bounds[3]) // 2

    def get_random_click_position(self):
        """영역 내 랜덤 클릭 좌표 반환"""
        x1, y1, x2, y2 = self.bounds
        margin_x = max(5, int((x2 - x1) * 0.15))
        margin_y = max(3, int((y2 - y1) * 0.15))

        click_x = random.randint(x1 + margin_x, max(x1 + margin_x, x2 - margin_x))
        click_y = random.randint(y1 + margin_y, max(y1 + margin_y, y2 - margin_y))

        return click_x, click_y

    def __repr__(self):
        x1, y1, x2, y2 = self.bounds
        return f"[{self.type}] ({x1},{y1})-({x2},{y2}) {self.text[:30]}..."


def parse_bounds(bounds_str):
    """bounds 문자열 파싱: "[24,686][210,728]" -> (24, 686, 210, 728)"""
    match = re.search(r'\[(\d+),(\d+)\]\[(\d+),(\d+)\]', bounds_str)
    if match:
        return tuple(map(int, match.groups()))
    return None


def find_clickable_areas(adb, domain, company_keyword=None):
    """
    XML에서 도메인/제목/설명 클릭 영역 찾기

    Args:
        adb: ADBController
        domain: 찾을 도메인 (예: "sidecut.co.kr")
        company_keyword: 회사명 키워드 (예: "사이드컷") - 제목 찾기용

    Returns:
        list[ClickableArea]: 클릭 가능한 영역들
    """
    xml = adb.get_screen_xml(force=True)
    if not xml:
        log("[ERROR] XML 가져오기 실패")
        return []

    areas = []
    domain_area = None
    base_domain = domain.split('/')[0]

    # 설정 업데이트
    if company_keyword:
        CLICK_CONFIG["title_keywords"] = [company_keyword, base_domain.split('.')[0]]

    log(f"[DEBUG] XML 길이: {len(xml)}")
    log(f"[DEBUG] 찾을 도메인: {base_domain}")
    log(f"[DEBUG] 제목 키워드: {CLICK_CONFIG['title_keywords']}")

    # 1. 도메인 찾기 (text 속성)
    # 패턴: text="sidecut.co.kr" ... bounds="[73,689][210,725]"
    domain_pattern = rf'<node[^>]+text="({re.escape(base_domain)})"[^>]+bounds="(\[[^\]]+\]\[[^\]]+\])"[^>]*/>'
    domain_match = re.search(domain_pattern, xml)

    if not domain_match:
        # bounds가 text 앞에 있는 경우
        domain_pattern2 = rf'<node[^>]+bounds="(\[[^\]]+\]\[[^\]]+\])"[^>]+text="({re.escape(base_domain)})"[^>]*/>'
        domain_match = re.search(domain_pattern2, xml)
        if domain_match:
            bounds_str, text = domain_match.groups()
        else:
            log(f"[ERROR] 도메인 '{base_domain}' 못 찾음")
            return []
    else:
        text, bounds_str = domain_match.groups()

    domain_bounds = parse_bounds(bounds_str)
    if domain_bounds:
        domain_area = ClickableArea("domain", domain_bounds, base_domain)
        areas.append(domain_area)
        log(f"[OK] 도메인: {domain_area}")

    if not domain_area:
        return []

    domain_y = domain_area.center_y

    # 2. 제목/설명 찾기 (content-desc 속성, clickable=true)
    # clickable View에서 content-desc가 있는 요소 찾기
    clickable_pattern = r'<node[^>]+content-desc="([^"]+)"[^>]+clickable="true"[^>]+bounds="(\[[^\]]+\]\[[^\]]+\])"[^>]*/?>|<node[^>]+bounds="(\[[^\]]+\]\[[^\]]+\])"[^>]+content-desc="([^"]+)"[^>]+clickable="true"[^>]*/?>'

    for match in re.finditer(clickable_pattern, xml):
        groups = match.groups()
        # 두 패턴 중 하나에 매칭
        if groups[0] and groups[1]:
            content_desc, bounds_str = groups[0], groups[1]
        elif groups[2] and groups[3]:
            bounds_str, content_desc = groups[2], groups[3]
        else:
            continue

        bounds = parse_bounds(bounds_str)
        if not bounds:
            continue

        # 빈 content-desc 제외
        if not content_desc.strip():
            continue

        # URL 인코딩 제외
        if '%2F' in content_desc or '%3A' in content_desc:
            continue

        # 도메인과의 거리 확인
        elem_y = (bounds[1] + bounds[3]) // 2
        distance = abs(elem_y - domain_y)

        # 도메인 아래에 있는 요소만 (위에 있는 건 다른 검색결과)
        if elem_y < domain_y:
            continue

        if distance > CLICK_CONFIG["max_distance_from_domain"]:
            continue

        # 서브링크 제외 (짧은 텍스트만 체크 - 제목/설명은 길어서 제외됨)
        is_sublink = False
        if len(content_desc) <= CLICK_CONFIG["sublink_max_length"]:
            for keyword in CLICK_CONFIG["sublink_keywords"]:
                if keyword in content_desc:
                    is_sublink = True
                    break
        if is_sublink:
            log(f"[SKIP] 서브링크: {content_desc[:40]}...")
            continue

        # 제목인지 설명인지 판단
        area_type = None

        # 제목: 도메인 아래 100px 이내, 키워드 포함
        if elem_y > domain_y and elem_y < domain_y + 100:
            for keyword in CLICK_CONFIG["title_keywords"]:
                if keyword.lower() in content_desc.lower():
                    area_type = "title"
                    break

        # 설명: 긴 텍스트 (50자 이상)
        if not area_type and len(content_desc) >= CLICK_CONFIG["desc_min_length"]:
            area_type = "desc"

        if area_type:
            area = ClickableArea(area_type, bounds, content_desc)
            areas.append(area)
            log(f"[OK] {area}")

    return areas


def create_adb(adb_address):
    """ADB 컨트롤러 생성"""
    phone_config = {
        "adb_address": adb_address,
        "screen_width": 720,
        "screen_height": 1440
    }
    return ADBController(phone_config)


def test_domain_click(adb_address, domain, company_keyword=None, do_click=False):
    """도메인 클릭 테스트"""
    log("=" * 60)
    log(f"[TEST] 도메인 클릭 테스트: {domain}")
    if company_keyword:
        log(f"[TEST] 회사명 키워드: {company_keyword}")
    log("=" * 60)

    # 1. ADB 연결
    adb = create_adb(adb_address)
    if not adb.connect():
        log("[FAIL] ADB 연결 실패")
        return False

    log(f"[OK] ADB 연결: {adb_address} ({adb.screen_width}x{adb.screen_height})")

    # 2. 클릭 가능 영역 찾기
    log("\n[STEP 1] 클릭 영역 찾기...")
    areas = find_clickable_areas(adb, domain, company_keyword)

    if not areas:
        log("[FAIL] 클릭 가능한 영역을 찾을 수 없음")
        return False

    # 3. 영역 정보 출력
    log(f"\n[STEP 2] 발견된 영역: {len(areas)}개")
    type_counts = {}
    for area in areas:
        type_counts[area.type] = type_counts.get(area.type, 0) + 1
        x1, y1, x2, y2 = area.bounds
        log(f"  [{area.type}] ({x1},{y1})-({x2},{y2}) 크기:{x2-x1}x{y2-y1}")

    log(f"\n[요약] 도메인:{type_counts.get('domain',0)}, 제목:{type_counts.get('title',0)}, 설명:{type_counts.get('desc',0)}")

    # 4. 랜덤 클릭 테스트
    log("\n[STEP 3] 랜덤 클릭 좌표 선택...")
    for i in range(5):
        selected = random.choice(areas)
        x, y = selected.get_random_click_position()
        log(f"  샘플 {i+1}: [{selected.type}] ({x}, {y})")

    # 5. 실제 클릭
    selected = random.choice(areas)
    x, y = selected.get_random_click_position()
    log(f"\n[선택됨] [{selected.type}] ({x}, {y})")
    log(f"[텍스트] {selected.text[:60]}...")

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


def test_multiple_clicks(adb_address, domain, company_keyword=None, count=30):
    """여러 번 클릭 테스트 (클릭 분포 확인)"""
    log("=" * 60)
    log(f"[TEST] 클릭 분포 테스트: {count}회")
    log("=" * 60)

    adb = create_adb(adb_address)
    if not adb.connect():
        log("[FAIL] ADB 연결 실패")
        return

    areas = find_clickable_areas(adb, domain, company_keyword)
    if not areas:
        log("[FAIL] 클릭 영역 못 찾음")
        return

    # 클릭 분포 집계
    type_counts = {"domain": 0, "title": 0, "desc": 0}

    for i in range(count):
        selected = random.choice(areas)
        type_counts[selected.type] = type_counts.get(selected.type, 0) + 1

    log("\n[클릭 분포]")
    for area_type, cnt in type_counts.items():
        pct = cnt / count * 100
        bar = "█" * int(pct / 5)
        log(f"  {area_type:8s}: {cnt:3d}회 ({pct:5.1f}%) {bar}")


def main():
    if len(sys.argv) < 3:
        print(__doc__)
        print("\n사용법: python test_step7_v2.py <ADB주소> <도메인> [회사명키워드]")
        print("예시: python test_step7_v2.py 98.98.125.37:21306 sidecut.co.kr 사이드컷")
        print("\n[설정 수정 방법]")
        print("이 파일의 CLICK_CONFIG 변수에서:")
        print("  - title_keywords: 제목 찾을 키워드")
        print("  - sublink_keywords: 서브링크 제외할 키워드")
        print("  - desc_min_length: 설명 최소 길이")
        sys.exit(1)

    adb_address = sys.argv[1]
    domain = sys.argv[2]
    company_keyword = sys.argv[3] if len(sys.argv) > 3 else None

    # 클릭 분포 테스트
    test_multiple_clicks(adb_address, domain, company_keyword, count=30)

    print("\n" + "=" * 60)

    # 실제 클릭 테스트
    test_domain_click(adb_address, domain, company_keyword, do_click=False)


if __name__ == "__main__":
    main()
