#!/usr/bin/env python3
"""
Step7 테스트 스크립트 - 메인 코드 사용
현재 화면에서 도메인/제목/설명 찾고 랜덤 클릭 테스트

사용법:
  python test_step7_main.py [domain] [--click] [--repeat N]

예시:
  python test_step7_main.py sidecut.co.kr           # 찾기만 (클릭 안함)
  python test_step7_main.py sidecut.co.kr --click   # 찾고 클릭
  python test_step7_main.py sidecut.co.kr --repeat 10  # 10번 랜덤 선택 테스트
"""

import sys
import os
import random

# 현재 디렉토리를 path에 추가
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from adb_auto import ADBController, NaverSearchAutomation, log
from config import PHONES, DOMAIN_KEYWORDS

def test_find_domain(adb, domain):
    """도메인/제목/설명 찾기 테스트"""
    log("=" * 60)
    log(f"[테스트] 도메인 찾기: {domain}")
    log("=" * 60)

    # NaverSearchAutomation 인스턴스 생성
    automation = NaverSearchAutomation(adb, cdp_info=None, browser="chrome")

    # 도메인 찾기 (하이브리드)
    links = automation._find_all_links_by_domain_hybrid(domain)

    if not links:
        log("[결과] 도메인을 찾지 못했습니다.")
        return []

    # viewport 내 링크만 필터링
    visible = [l for l in links if automation.viewport_top <= l["center_y"] <= automation.viewport_bottom]

    log(f"\n[결과] 총 {len(links)}개 발견, viewport 내 {len(visible)}개")
    log(f"viewport: {automation.viewport_top:.0f} ~ {automation.viewport_bottom:.0f}")

    # 타입별 통계
    types = {}
    for l in visible:
        t = l.get('link_type', 'unknown')
        types[t] = types.get(t, 0) + 1

    log(f"\n[통계] 도메인:{types.get('domain',0)}, 제목:{types.get('title',0)}, 설명:{types.get('desc',0)}")

    # 상세 정보 출력
    log("\n[상세 목록]")
    for i, l in enumerate(visible):
        link_type = l.get('link_type', 'unknown')
        text = l.get('text', '')[:50]
        bounds = l.get('bounds', (0,0,0,0))
        log(f"  {i+1}. [{link_type:6}] {text}... bounds={bounds}")

    return visible

def test_random_selection(visible_links, repeat=10):
    """랜덤 선택 테스트 (클릭 없이) - 타입별 균등 확률"""
    log("\n" + "=" * 60)
    log(f"[테스트] 타입별 균등 랜덤 선택 {repeat}회 시뮬레이션")
    log("=" * 60)

    if not visible_links:
        log("[에러] 선택할 링크 없음")
        return

    # 타입별 그룹화 (메인 코드와 동일)
    links_by_type = {'domain': [], 'title': [], 'desc': []}
    for l in visible_links:
        t = l.get('link_type', 'unknown')
        if t in links_by_type:
            links_by_type[t].append(l)

    # 존재하는 타입만 필터
    available_types = [t for t, items in links_by_type.items() if items]
    log(f"\n[타입별 개수]")
    for t in available_types:
        log(f"  {t}: {len(links_by_type[t])}개")
    log(f"\n[선택 가능 타입] {available_types} (각 {100/len(available_types):.1f}% 확률)")

    # 선택 카운트
    type_count = {t: 0 for t in available_types}
    selections = []

    # 랜덤 선택 시뮬레이션 (타입 먼저 균등 선택, 그 안에서 요소 선택)
    for i in range(repeat):
        # 1. 타입 먼저 선택 (균등 확률)
        selected_type = random.choice(available_types)
        # 2. 해당 타입 내에서 요소 선택
        selected = random.choice(links_by_type[selected_type])

        type_count[selected_type] += 1
        selections.append(selected_type)

    log(f"\n[선택 결과] {repeat}회:")
    for link_type in available_types:
        count = type_count[link_type]
        pct = count / repeat * 100
        expected = 100 / len(available_types)
        log(f"  {link_type:8}: {count}회 ({pct:.1f}%) [기대: {expected:.1f}%]")

    log(f"\n[선택 순서] {' → '.join(selections)}")

def test_click_domain(adb, domain):
    """도메인 클릭 테스트 (실제 클릭)"""
    log("=" * 60)
    log(f"[테스트] 도메인 클릭: {domain}")
    log("=" * 60)

    automation = NaverSearchAutomation(adb, cdp_info=None, browser="chrome")
    links = automation._find_all_links_by_domain_hybrid(domain)

    if not links:
        log("[실패] 도메인을 찾지 못했습니다.")
        return False

    visible = [l for l in links if automation.viewport_top <= l["center_y"] <= automation.viewport_bottom]

    if not visible:
        log("[실패] viewport 내 링크 없음")
        return False

    # 실제 클릭 (메인 코드 로직 사용)
    return automation._click_domain_link(visible, domain)

def main():
    import argparse
    parser = argparse.ArgumentParser(description='Step7 테스트 - 메인 코드 사용')
    parser.add_argument('domain', nargs='?', default='sidecut.co.kr', help='찾을 도메인')
    parser.add_argument('--click', action='store_true', help='실제 클릭 수행')
    parser.add_argument('--repeat', type=int, default=10, help='랜덤 선택 시뮬레이션 횟수')
    parser.add_argument('--phone', default='테스트폰1', help='사용할 폰 이름')
    args = parser.parse_args()

    # 폰 설정 찾기
    phone_config = None
    for config in PHONES.values():
        if config.get("name") == args.phone:
            phone_config = config
            break

    if not phone_config:
        log(f"[에러] 폰 '{args.phone}' 설정을 찾을 수 없습니다.")
        log(f"가능한 폰: {[c.get('name') for c in PHONES.values()]}")
        return

    log(f"[INFO] 폰: {args.phone}")
    log(f"[INFO] ADB: {phone_config['adb_address']}")
    log(f"[INFO] 도메인: {args.domain}")

    # ADB 연결
    adb = ADBController(phone_config)
    if not adb.connect():
        log("[에러] ADB 연결 실패")
        return

    # DOMAIN_KEYWORDS 확인
    keywords = DOMAIN_KEYWORDS.get(args.domain, [args.domain.split('.')[0]])
    log(f"[INFO] 키워드: {keywords}")

    # 도메인 찾기
    visible = test_find_domain(adb, args.domain)

    if visible:
        # 랜덤 선택 시뮬레이션
        test_random_selection(visible, args.repeat)

        # 실제 클릭
        if args.click:
            log("\n" + "=" * 60)
            log("[실제 클릭 수행]")
            log("=" * 60)
            result = test_click_domain(adb, args.domain)
            log(f"\n[최종 결과] {'성공' if result else '실패'}")

    log("\n[완료]")

if __name__ == "__main__":
    main()
