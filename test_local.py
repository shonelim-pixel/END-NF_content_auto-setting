#!/usr/bin/env python3
"""
============================================================
END NF 콘텐츠 시스템 - 로컬 테스트 스크립트
============================================================
각 수집기와 오케스트레이터를 로컬에서 빠르게 테스트합니다.

사용법:
    python test_local.py              # 전체 테스트
    python test_local.py --quick      # 빠른 테스트 (API 호출 최소화)
    python test_local.py --module news # 특정 모듈만 테스트
"""

import sys
import os
import json
import argparse
from datetime import datetime

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

PASS = "✅"
FAIL = "❌"
SKIP = "⏭️"


def test_pubmed(quick=False):
    """PubMed 수집기 테스트"""
    print(f"\n{'='*50}")
    print("테스트: PubMed 수집기")
    print(f"{'='*50}")

    from pubmed_fetcher import PubMedFetcher
    fetcher = PubMedFetcher()

    # 1. 검색 테스트
    try:
        pmids = fetcher.search("neurofibromatosis", max_results=2, days_back=60)
        if pmids:
            print(f"  {PASS} 검색 성공: {len(pmids)}건 PMID 반환")
        else:
            print(f"  {FAIL} 검색 결과 없음 (API 접근 불가일 수 있음)")
            return False
    except Exception as e:
        print(f"  {FAIL} 검색 실패: {e}")
        return False

    # 2. 상세정보 테스트
    if not quick and pmids:
        try:
            articles = fetcher.fetch_details(pmids[:1])
            if articles:
                art = articles[0]
                print(f"  {PASS} 상세정보: '{art['title'][:50]}...'")
                print(f"       저널: {art['journal']}")
                print(f"       DOI: {art['doi']}")
            else:
                print(f"  {FAIL} 상세정보 파싱 실패")
        except Exception as e:
            print(f"  {FAIL} 상세정보 조회 실패: {e}")

    return True


def test_news(quick=False):
    """뉴스 수집기 테스트"""
    print(f"\n{'='*50}")
    print("테스트: 뉴스/RSS 수집기")
    print(f"{'='*50}")

    from news_fetcher import NewsFetcher
    fetcher = NewsFetcher()

    # 1. RSS 테스트
    try:
        items = fetcher.fetch_category("general", max_per_feed=3)
        if items:
            print(f"  {PASS} RSS 수집 성공: {len(items)}건")
            print(f"       첫 번째: '{items[0]['title'][:50]}...'")
        else:
            print(f"  {FAIL} RSS 수집 결과 없음")
    except Exception as e:
        print(f"  {FAIL} RSS 수집 실패: {e}")

    # 2. 레어노트 스크래핑 테스트
    try:
        items = fetcher.fetch_category("rarenote", max_per_feed=3)
        print(f"  {PASS if items else FAIL} 레어노트 스크래핑: {len(items)}건")
    except Exception as e:
        print(f"  {FAIL} 레어노트 실패: {e}")

    # 3. CTF 스크래핑 테스트
    try:
        items = fetcher.fetch_category("ctf", max_per_feed=3)
        print(f"  {PASS if items else FAIL} CTF 스크래핑: {len(items)}건")
    except Exception as e:
        print(f"  {FAIL} CTF 실패: {e}")

    return True


def test_clinical_trials(quick=False):
    """임상시험 수집기 테스트"""
    print(f"\n{'='*50}")
    print("테스트: 임상시험 수집기")
    print(f"{'='*50}")

    from clinical_trials_fetcher import ClinicalTrialsFetcher
    fetcher = ClinicalTrialsFetcher()

    try:
        trials = fetcher.search("neurofibromatosis", max_results=3)
        if trials:
            t = trials[0]
            print(f"  {PASS} 검색 성공: {len(trials)}건")
            print(f"       첫 번째: '{t['title'][:50]}...'")
            print(f"       상태: {t['status']}")
            print(f"       스폰서: {t['sponsor']}")
        else:
            print(f"  {FAIL} 검색 결과 없음")
    except Exception as e:
        print(f"  {FAIL} 임상시험 검색 실패: {e}")

    return True


def test_patient_stories(quick=False):
    """환자 이야기 수집기 테스트"""
    print(f"\n{'='*50}")
    print("테스트: 환자 이야기 수집기")
    print(f"{'='*50}")

    from patient_story_fetcher import PatientStoryFetcher
    fetcher = PatientStoryFetcher()

    # Reddit 테스트
    try:
        stories = fetcher.fetch_reddit(max_results=5)
        if stories:
            s = stories[0]
            print(f"  {PASS} Reddit: {len(stories)}건 (긍정도 최고: {s.get('positivity_score', 0)})")
        else:
            print(f"  {FAIL} Reddit 수집 결과 없음")
    except Exception as e:
        print(f"  {FAIL} Reddit 수집 실패: {e}")

    # CTF Stories 테스트
    if not quick:
        try:
            stories = fetcher.fetch_ctf_stories()
            print(f"  {PASS if stories else FAIL} CTF Stories: {len(stories)}건")
        except Exception as e:
            print(f"  {FAIL} CTF Stories 실패: {e}")

    return True


def test_orchestrator(quick=False):
    """오케스트레이터 테스트"""
    print(f"\n{'='*50}")
    print("테스트: 일일 오케스트레이터 (dry-run)")
    print(f"{'='*50}")

    from daily_runner import DailyOrchestrator, DAY_PLANS

    orchestrator = DailyOrchestrator()

    # dry-run으로 모든 요일 계획 확인
    for day, plan in DAY_PLANS.items():
        task_types = [t["type"] for t in plan["tasks"]]
        print(f"  {PASS} {day.upper()}: {plan['title']}")
        print(f"       태스크: {', '.join(task_types)}")

    # 정규화 테스트
    test_item = {
        "pmid": "12345",
        "title": "Test NF1 Research",
        "abstract": "Neurofibromatosis type 1 study.",
        "authors": ["Kim A"],
        "journal": "Test Journal",
        "pub_date": "2026",
        "doi": "10.1234/test",
        "url": "https://pubmed.ncbi.nlm.nih.gov/12345/",
    }
    normalized = orchestrator.normalize_item(test_item, "pubmed")
    print(f"\n  {PASS} 정규화 테스트: relevance_score={normalized['relevance_score']}")

    # 중복 제거 테스트
    items = [normalized, normalized]
    deduped = orchestrator.deduplicate(items)
    assert len(deduped) <= 1, "중복 제거 실패"
    print(f"  {PASS} 중복 제거: 2건 → {len(deduped)}건")

    return True


def test_content_generator(quick=False):
    """콘텐츠 생성기 테스트"""
    print(f"\n{'='*50}")
    print("테스트: Claude API 콘텐츠 생성기")
    print(f"{'='*50}")

    from content_generator import ContentGenerator, DAY_PROMPTS, SPECIAL_PROMPTS

    generator = ContentGenerator()

    # 1. 프롬프트 완성도 검증
    all_days = ["mon", "tue", "wed", "thu", "fri", "sat", "sun"]
    for day in all_days:
        prompt = DAY_PROMPTS.get(day)
        assert prompt, f"프롬프트 누락: {day}"
        assert "END NF 션입니다" in prompt["system"], f"스타일 가이드 누락: {day}"
        assert "{collected_data}" in prompt["user_template"], f"데이터 플레이스홀더 누락: {day}"
        print(f"  {PASS} {day.upper()}: {prompt['title']}")

    # 특집 프롬프트 검증
    for name, prompt in SPECIAL_PROMPTS.items():
        assert "END NF 션입니다" in prompt["system"]
        print(f"  {PASS} 특집 [{name}]: {prompt['title']}")

    # 2. 데이터 요약 변환 테스트
    sample_items = [
        {
            "source_type": "pubmed",
            "title": "NF1 Gene Therapy Advances",
            "summary": "New approach using CRISPR for NF1.",
            "url": "https://example.com",
            "journal": "Nature",
            "authors": ["Lee A", "Kim B"],
            "pub_date": "2026",
            "relevance_score": 8,
        },
        {
            "source_type": "news",
            "title": "Koselugo Update",
            "summary": "European approval news.",
            "url": "https://ctf.org/news",
            "source_name": "CTF News",
            "relevance_score": 10,
        },
    ]

    summary = generator._prepare_data_summary(sample_items)
    assert "Koselugo Update" in summary  # 관련성 높은 것이 먼저
    assert "[1]" in summary and "[2]" in summary
    print(f"\n  {PASS} 데이터 요약 변환: 2건 → {len(summary)}자")

    # 3. 미리보기 모드 테스트
    result = generator.generate("thu", sample_items)
    assert result.get("preview_mode") or result.get("content")
    print(f"  {PASS} 미리보기 생성: {len(result.get('content', ''))}자")

    # 4. 본문/이미지 분리 테스트
    test_text = "본문 내용입니다.\n\n[이미지 설명] 따뜻한 그림\n[프롬프트] warm illustration"
    content, image = generator._split_content_and_image(test_text)
    assert "본문 내용" in content
    assert "warm illustration" in image
    print(f"  {PASS} 본문/이미지 분리 정상")

    # 5. 샘플 데이터 파일 연동 테스트
    sample_file = os.path.join(os.path.dirname(__file__), "data", "sample_daily_thu.json")
    if os.path.exists(sample_file):
        result = generator.generate_from_daily_file(sample_file, "thu")
        assert result
        print(f"  {PASS} 샘플 파일 연동: {result.get('title')}")
    else:
        print(f"  {SKIP} 샘플 파일 없음 (data/sample_daily_thu.json)")

    return True


def main():
    parser = argparse.ArgumentParser(description="END NF 로컬 테스트")
    parser.add_argument("--quick", action="store_true", help="빠른 테스트")
    parser.add_argument("--module", type=str, default="all",
                        help="테스트 모듈 (pubmed, news, trials, stories, orchestrator, all)")
    args = parser.parse_args()

    print("🧪 END NF 콘텐츠 시스템 - 로컬 테스트")
    print(f"   시각: {datetime.now().strftime('%Y-%m-%d %H:%M')}")
    print(f"   모드: {'Quick' if args.quick else 'Full'}")
    print(f"   모듈: {args.module}")

    tests = {
        "pubmed": test_pubmed,
        "news": test_news,
        "trials": test_clinical_trials,
        "stories": test_patient_stories,
        "orchestrator": test_orchestrator,
        "generator": test_content_generator,
    }

    if args.module == "all":
        for name, test_fn in tests.items():
            test_fn(args.quick)
    elif args.module in tests:
        tests[args.module](args.quick)
    else:
        print(f"❌ 알 수 없는 모듈: {args.module}")
        print(f"   사용 가능: {', '.join(tests.keys())}")

    print(f"\n{'='*50}")
    print("🏁 테스트 완료!")
    print(f"{'='*50}")


if __name__ == "__main__":
    main()
