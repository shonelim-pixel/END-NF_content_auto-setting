#!/usr/bin/env python3
"""
============================================================
END NF 콘텐츠 시스템 - E2E 시뮬레이션 (6단계)
============================================================
전체 파이프라인을 로컬에서 시뮬레이션합니다.
실제 API 호출 없이 각 단계가 정상 연결되는지 확인.

사용법:
    python simulate_pipeline.py                 # 전체 시뮬레이션
    python simulate_pipeline.py --day thu       # 특정 요일
    python simulate_pipeline.py --live          # 실제 API 호출 포함
"""

import os
import sys
import json
import argparse
from datetime import datetime

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

PASS = "✅"
FAIL = "❌"
SKIP = "⏭️"
WARN = "⚠️"


def check_environment():
    """환경 설정 확인"""
    print(f"\n{'━'*60}")
    print("🔧 환경 설정 확인")
    print(f"{'━'*60}")

    checks = {
        "ANTHROPIC_API_KEY": os.environ.get("ANTHROPIC_API_KEY", ""),
        "TELEGRAM_BOT_TOKEN": os.environ.get("TELEGRAM_BOT_TOKEN", ""),
        "TELEGRAM_CHAT_ID": os.environ.get("TELEGRAM_CHAT_ID", ""),
        "NCBI_API_KEY": os.environ.get("NCBI_API_KEY", ""),
        "SMTP_USER": os.environ.get("SMTP_USER", ""),
    }

    all_critical = True
    for key, value in checks.items():
        if value:
            masked = value[:8] + "..." if len(value) > 8 else "***"
            print(f"  {PASS} {key}: {masked}")
        else:
            critical = key in ["ANTHROPIC_API_KEY", "TELEGRAM_BOT_TOKEN"]
            icon = FAIL if critical else WARN
            print(f"  {icon} {key}: 미설정 {'(필수)' if critical else '(선택)'}")
            if critical:
                all_critical = False

    return all_critical


def simulate_step1_collect(day: str, live: bool = False):
    """1단계: 데이터 수집 시뮬레이션"""
    print(f"\n{'━'*60}")
    print(f"📦 Step 1: 데이터 수집 ({'실제' if live else '시뮬레이션'})")
    print(f"{'━'*60}")

    from daily_runner import DailyOrchestrator

    orchestrator = DailyOrchestrator()

    if live:
        result = orchestrator.run_day(day)
    else:
        result = orchestrator.run_day(day, dry_run=True)
        # 시뮬레이션용 샘플 데이터 생성
        sample_file = os.path.join("data", "sample_daily_thu.json")
        if os.path.exists(sample_file):
            with open(sample_file, "r", encoding="utf-8") as f:
                result = json.load(f)
            result["day"] = day
            print(f"  {PASS} 샘플 데이터 로드: {len(result.get('items', []))}건")
        else:
            result = {
                "day": day,
                "title": f"시뮬레이션 ({day})",
                "total_items": 0,
                "items": [],
            }
            print(f"  {WARN} 샘플 데이터 없음 (빈 데이터로 진행)")

    # 결과 저장
    date_str = datetime.now().strftime("%Y%m%d")
    filepath = os.path.join("data", f"daily_{date_str}.json")
    os.makedirs("data", exist_ok=True)
    with open(filepath, "w", encoding="utf-8") as f:
        json.dump(result, f, ensure_ascii=False, indent=2)

    total = result.get("total_items", len(result.get("items", [])))
    print(f"  {PASS} 수집 결과: {total}건 → {filepath}")
    return result


def simulate_step2_generate(day: str, collect_result: dict, live: bool = False):
    """2단계: 글 생성 시뮬레이션"""
    print(f"\n{'━'*60}")
    print(f"✍️ Step 2: 글 생성 ({'실제' if live else '시뮬레이션'})")
    print(f"{'━'*60}")

    from content_generator import ContentGenerator

    generator = ContentGenerator()

    items = collect_result.get("items", [])

    if live and generator.client:
        result = generator.generate(day, items)
    else:
        # 미리보기 모드
        generator.client = None
        result = generator.generate(day, items)

    if result:
        content_len = len(result.get("content", ""))
        print(f"  {PASS} 글 생성: {content_len}자")
        if result.get("preview_mode"):
            print(f"  {WARN} 미리보기 모드 (API 키 설정 시 실제 생성)")
    else:
        print(f"  {FAIL} 글 생성 실패")

    return result


def simulate_step3_image(day: str, post_result: dict):
    """3단계: 이미지 프롬프트 생성"""
    print(f"\n{'━'*60}")
    print("🎨 Step 3: 이미지 프롬프트 생성")
    print(f"{'━'*60}")

    from image_prompt_generator import ImagePromptGenerator

    generator = ImagePromptGenerator()
    content = post_result.get("content", "")

    # 나노바나나 + 그록 동시
    for platform in ["nanobana", "grok"]:
        result = generator.generate(
            day=day,
            content_summary=content[:500],
            platform=platform,
            layout="single_image",
        )
        prompts = result.get("prompts", [])
        if prompts:
            print(f"  {PASS} [{platform}] {len(prompts)}개 프롬프트")
            print(f"       → {prompts[0].get('prompt_en', '')[:80]}...")

    # 카드뉴스도 테스트
    card_result = generator.generate(day=day, content_summary=content[:500],
                                      platform="nanobana", layout="card_3")
    card_count = len(card_result.get("prompts", []))
    print(f"  {PASS} [카드뉴스 3장] {card_count}개 슬라이드 프롬프트")

    return result


def simulate_step4_notify(post_result: dict, live: bool = False):
    """4단계: 알림 전송 시뮬레이션"""
    print(f"\n{'━'*60}")
    print(f"📮 Step 4: 알림 전송 ({'실제' if live else '시뮬레이션'})")
    print(f"{'━'*60}")

    from notification_sender import NotificationManager, MessageFormatter

    manager = NotificationManager()

    # 포맷 검증
    tg_msg = MessageFormatter.format_telegram(post_result)
    subject, email_body = MessageFormatter.format_email(post_result)

    print(f"  {PASS} 텔레그램 메시지: {len(tg_msg)}자")
    print(f"  {PASS} 이메일: '{subject}' ({len(email_body)}자)")

    if live:
        if manager.telegram.is_configured:
            ok = manager.telegram.send_message(tg_msg)
            print(f"  {'✅' if ok else '❌'} 텔레그램 전송: {'성공' if ok else '실패'}")
        else:
            print(f"  {SKIP} 텔레그램 미설정")

        if manager.email.is_configured:
            ok = manager.email.send(subject, email_body)
            print(f"  {'✅' if ok else '❌'} 이메일 전송: {'성공' if ok else '실패'}")
        else:
            print(f"  {SKIP} 이메일 미설정")
    else:
        print(f"  {SKIP} 시뮬레이션 모드 (실제 전송 안 함)")
        print(f"  💡 --live 옵션으로 실제 전송 테스트 가능")


def run_simulation(day: str, live: bool = False):
    """전체 파이프라인 시뮬레이션"""
    start_time = datetime.now()

    print(f"\n{'='*60}")
    print(f"🚀 END NF 콘텐츠 시스템 - E2E 시뮬레이션")
    print(f"   요일: {day.upper()}")
    print(f"   모드: {'실제 실행' if live else '시뮬레이션'}")
    print(f"   시각: {start_time.strftime('%Y-%m-%d %H:%M')}")
    print(f"{'='*60}")

    env_ok = check_environment()

    # Step 1: 수집
    collect_result = simulate_step1_collect(day, live)

    # Step 2: 글 생성
    post_result = simulate_step2_generate(day, collect_result, live)
    if not post_result:
        post_result = {"content": "", "title": "시뮬레이션", "day": day,
                       "generated_at": datetime.now().isoformat(), "input_items_count": 0}

    # Step 3: 이미지 프롬프트
    simulate_step3_image(day, post_result)

    # Step 4: 알림 전송
    simulate_step4_notify(post_result, live)

    # 완료 요약
    elapsed = (datetime.now() - start_time).total_seconds()
    print(f"\n{'='*60}")
    print(f"🏁 시뮬레이션 완료 ({elapsed:.1f}초)")
    print(f"{'='*60}")
    print(f"  📦 수집: {collect_result.get('total_items', len(collect_result.get('items', [])))}건")
    print(f"  ✍️ 글: {len(post_result.get('content', ''))}자")
    print(f"  🎨 이미지: 나노바나나+그록+카드뉴스")
    print(f"  📮 알림: {'실제 전송' if live else '포맷 검증만'}")

    if not env_ok:
        print(f"\n  {WARN} 환경변수 미설정 항목이 있습니다.")
        print(f"  💡 TELEGRAM_SETUP.md를 참고해 설정해주세요.")

    print(f"\n  📋 다음 단계:")
    print(f"  1. GitHub에 저장소 생성")
    print(f"  2. Secrets 설정 (ANTHROPIC_API_KEY, TELEGRAM_BOT_TOKEN 등)")
    print(f"  3. 코드 push → Actions 탭에서 수동 실행 테스트")
    print(f"  4. 매일 KST 06:00 자동 실행 확인")
    print(f"{'='*60}")


def main():
    parser = argparse.ArgumentParser(description="END NF E2E 시뮬레이션")
    parser.add_argument("--day", type=str, default="thu",
                        help="시뮬레이션 요일 (기본: thu)")
    parser.add_argument("--live", action="store_true",
                        help="실제 API 호출 포함")
    args = parser.parse_args()

    run_simulation(args.day, args.live)


if __name__ == "__main__":
    main()
