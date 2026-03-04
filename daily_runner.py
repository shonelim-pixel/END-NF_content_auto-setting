"""
============================================================
END NF 콘텐츠 시스템 - 일일 오케스트레이터 (2단계 핵심)
============================================================
요일별로 적절한 수집기를 자동 실행하고, 결과를 통합/정규화합니다.

사용법:
    python daily_runner.py                  # 오늘 요일에 맞게 자동 실행
    python daily_runner.py --day mon        # 특정 요일 실행
    python daily_runner.py --day all        # 전체 요일 실행 (테스트)
    python daily_runner.py --dry-run        # 수집 없이 실행 계획만 출력

환경변수:
    NCBI_API_KEY: PubMed API 키 (선택)
    TELEGRAM_BOT_TOKEN: 텔레그램 봇 토큰 (5단계)
    TELEGRAM_CHAT_ID: 텔레그램 채팅 ID (5단계)
    ANTHROPIC_API_KEY: Claude API 키 (3단계)
"""

import os
import sys
import json
import logging
import hashlib
import traceback
from datetime import datetime, timedelta
from pathlib import Path
import argparse

# 프로젝트 루트를 PYTHONPATH에 추가
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from pubmed_fetcher import PubMedFetcher
from news_fetcher import NewsFetcher
from clinical_trials_fetcher import ClinicalTrialsFetcher
from patient_story_fetcher import PatientStoryFetcher

# ── 로깅 설정 ──
LOG_DIR = os.path.join(os.path.dirname(__file__), "logs")
DATA_DIR = os.path.join(os.path.dirname(__file__), "data")
ARCHIVE_DIR = os.path.join(DATA_DIR, "archive")
DEDUP_FILE = os.path.join(DATA_DIR, "seen_items.json")

os.makedirs(LOG_DIR, exist_ok=True)
os.makedirs(DATA_DIR, exist_ok=True)
os.makedirs(ARCHIVE_DIR, exist_ok=True)

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    handlers=[
        logging.FileHandler(
            os.path.join(LOG_DIR, f"daily_{datetime.now().strftime('%Y%m%d')}.log"),
            encoding="utf-8",
        ),
        logging.StreamHandler(),
    ],
)
logger = logging.getLogger("endnf")


# ── 요일별 실행 계획 ──
DAY_PLANS = {
    "mon": {
        "title": "📚 월요일: NF 관련 최신 국제 논문/연구",
        "tasks": [
            {"type": "pubmed", "params": {"days_back": 7, "max_per_query": 5}},
            {"type": "news", "params": {"categories": ["general", "rarenote", "ctf"]}},
        ],
    },
    "tue": {
        "title": "💛 화요일: 환자/가족 응원 메시지 + 감동 이야기",
        "tasks": [
            {"type": "patient_stories", "params": {"sources": ["reddit", "ctf"]}},
            {"type": "news", "params": {"categories": ["rarenote"]}},
        ],
    },
    "wed": {
        "title": "🌍 수요일: 해외 NF 커뮤니티 소식",
        "tasks": [
            {"type": "news", "params": {"categories": ["community", "ctf"]}},
        ],
    },
    "thu": {
        "title": "💊 목요일: NF 치료제 개발 / 임상시험",
        "tasks": [
            {"type": "clinical_trials", "params": {"max_results": 15, "days_back": 30}},
            {"type": "news", "params": {"categories": ["treatment", "ctf"]}},
        ],
    },
    "fri": {
        "title": "📋 금요일: 희귀질환 정책/제도 뉴스",
        "tasks": [
            {"type": "news", "params": {"categories": ["policy_kr", "policy_global", "rarenote"]}},
        ],
    },
    "sat": {
        "title": "🌿 토요일: NF 환자 일상 / 힐링 콘텐츠",
        "tasks": [
            {"type": "patient_stories", "params": {"sources": ["healing"]}},
            {"type": "news", "params": {"categories": ["rarenote"]}},
        ],
    },
    "sun": {
        "title": "📰 일요일: 주간 하이라이트 + 다음 주 예고",
        "tasks": [
            {"type": "weekly_summary", "params": {}},
        ],
    },
}


class DailyOrchestrator:
    """일일 콘텐츠 수집 오케스트레이터"""

    def __init__(self):
        self.pubmed = PubMedFetcher()
        self.news = NewsFetcher()
        self.trials = ClinicalTrialsFetcher()
        self.stories = PatientStoryFetcher()
        self.results = {}
        self.errors = []
        self.seen_hashes = self._load_seen_items()

    # ── 중복 제거 ──

    def _load_seen_items(self) -> set:
        """이전에 수집한 아이템 해시 로드"""
        if os.path.exists(DEDUP_FILE):
            try:
                with open(DEDUP_FILE, "r") as f:
                    data = json.load(f)
                    # 최근 30일 항목만 유지
                    cutoff = (datetime.now() - timedelta(days=30)).isoformat()
                    recent = {k: v for k, v in data.items() if v > cutoff}
                    return set(recent.keys())
            except Exception:
                pass
        return set()

    def _save_seen_items(self):
        """수집한 아이템 해시 저장"""
        data = {h: datetime.now().isoformat() for h in self.seen_hashes}
        with open(DEDUP_FILE, "w") as f:
            json.dump(data, f)

    def _item_hash(self, item: dict) -> str:
        """아이템 고유 해시 생성"""
        key_parts = []
        for k in ["pmid", "nct_id", "url", "link", "title"]:
            if k in item and item[k]:
                key_parts.append(str(item[k]))
        key = "|".join(key_parts)
        return hashlib.md5(key.encode()).hexdigest()

    def deduplicate(self, items: list) -> list:
        """중복 아이템 제거"""
        unique = []
        for item in items:
            h = self._item_hash(item)
            if h not in self.seen_hashes:
                self.seen_hashes.add(h)
                unique.append(item)
        return unique

    # ── 데이터 정규화 ──

    def normalize_item(self, item: dict, source_type: str) -> dict:
        """다양한 소스의 데이터를 통일된 형식으로 정규화"""
        normalized = {
            "id": self._item_hash(item),
            "source_type": source_type,
            "title": "",
            "summary": "",
            "url": "",
            "language": "en",
            "relevance_score": 0,
            "collected_at": datetime.now().isoformat(),
            "raw_data": item,
        }

        if source_type == "pubmed":
            normalized.update({
                "title": item.get("title", ""),
                "summary": item.get("abstract", "")[:300],
                "url": item.get("url", ""),
                "language": "en",
                "authors": item.get("authors", []),
                "journal": item.get("journal", ""),
                "pub_date": item.get("pub_date", ""),
            })

        elif source_type == "clinical_trial":
            normalized.update({
                "title": item.get("title", ""),
                "summary": item.get("brief_summary", "")[:300],
                "url": item.get("url", ""),
                "language": "en",
                "status": item.get("status", ""),
                "phase": item.get("phase", []),
                "sponsor": item.get("sponsor", ""),
                "is_new_this_week": item.get("is_new_this_week", False),
                "last_update": item.get("last_update", ""),
                "start_date": item.get("start_date", ""),
                "nct_id": item.get("nct_id", ""),
            })

        elif source_type == "news":
            normalized.update({
                "title": item.get("title", ""),
                "summary": item.get("description", "")[:300],
                "url": item.get("link", "") or item.get("url", ""),
                "language": item.get("language", "en"),
                "source_name": item.get("source_name", ""),
                "pub_date": item.get("pub_date", ""),
            })

        elif source_type == "patient_story":
            normalized.update({
                "title": item.get("title", ""),
                "summary": item.get("body", "")[:300],
                "url": item.get("url", ""),
                "language": "en",
                "positivity_score": item.get("positivity_score", 0),
                "pub_date": item.get("pub_date", "") or item.get("created_utc", ""),
                "source_name": item.get("source_name", "") or item.get("subreddit", ""),
            })

        # NF 관련성 점수 계산
        normalized["relevance_score"] = self._calc_relevance(normalized)

        return normalized

    def _calc_relevance(self, item: dict) -> int:
        """NF 관련성 점수 계산"""
        score = 0
        text = f"{item.get('title', '')} {item.get('summary', '')}".lower()

        high_keywords = ["neurofibromatosis", "nf1", "nf2", "schwannomatosis",
                         "plexiform", "selumetinib", "koselugo", "신경섬유종"]
        medium_keywords = ["neurofibroma", "mek inhibitor", "rare disease",
                           "희귀질환", "유전질환", "ctf", "children's tumor"]

        for kw in high_keywords:
            if kw in text:
                score += 3
        for kw in medium_keywords:
            if kw in text:
                score += 1

        # 최근 7일 신규 임상시험에 가산점
        if item.get("is_new_this_week"):
            score += 5

        return min(score, 10)

    # ── 태스크 실행기 ──

    def run_pubmed(self, params: dict) -> list:
        """PubMed 논문 수집 태스크"""
        logger.info("📚 PubMed 논문 수집 시작")
        try:
            results = self.pubmed.fetch_nf_latest(
                days_back=params.get("days_back", 7),
                max_per_query=params.get("max_per_query", 5),
            )
            all_articles = []
            for query, articles in results.items():
                for art in articles:
                    normalized = self.normalize_item(art, "pubmed")
                    all_articles.append(normalized)
            return self.deduplicate(all_articles)
        except Exception as e:
            logger.error(f"❌ PubMed 수집 실패: {e}")
            self.errors.append({"task": "pubmed", "error": str(e)})
            return []

    def run_news(self, params: dict) -> list:
        """뉴스/RSS 수집 태스크"""
        categories = params.get("categories", [])
        logger.info(f"📰 뉴스 수집 시작: {categories}")
        all_news = []
        try:
            for cat in categories:
                items = self.news.fetch_category(cat, max_per_feed=10)
                for item in items:
                    normalized = self.normalize_item(item, "news")
                    all_news.append(normalized)
            return self.deduplicate(all_news)
        except Exception as e:
            logger.error(f"❌ 뉴스 수집 실패: {e}")
            self.errors.append({"task": "news", "error": str(e)})
            return []

    def run_clinical_trials(self, params: dict) -> list:
        """임상시험 수집 태스크"""
        logger.info("🔬 임상시험 수집 시작")
        try:
            results = self.trials.fetch_all_nf(
                max_per_query=params.get("max_results", 10),
            )
            all_trials = []
            for query, trials in results.items():
                for trial in trials:
                    normalized = self.normalize_item(trial, "clinical_trial")
                    all_trials.append(normalized)
            return self.deduplicate(all_trials)
        except Exception as e:
            logger.error(f"❌ 임상시험 수집 실패: {e}")
            self.errors.append({"task": "clinical_trials", "error": str(e)})
            return []

    def run_patient_stories(self, params: dict) -> list:
        """환자 이야기 수집 태스크"""
        sources = params.get("sources", ["all"])
        logger.info(f"💛 환자 이야기 수집 시작: {sources}")
        all_stories = []
        try:
            if "reddit" in sources or "all" in sources:
                reddit = self.stories.fetch_reddit(max_results=15)
                for item in reddit:
                    all_stories.append(self.normalize_item(item, "patient_story"))

            if "ctf" in sources or "all" in sources:
                ctf = self.stories.fetch_ctf_stories()
                for item in ctf:
                    all_stories.append(self.normalize_item(item, "patient_story"))

            if "healing" in sources:
                healing = self.stories.fetch_healing_content()
                for item in healing:
                    all_stories.append(self.normalize_item(item, "patient_story"))

            return self.deduplicate(all_stories)
        except Exception as e:
            logger.error(f"❌ 환자 이야기 수집 실패: {e}")
            self.errors.append({"task": "patient_stories", "error": str(e)})
            return []

    def run_weekly_summary(self, params: dict) -> list:
        """주간 하이라이트 생성 (이번 주 수집 데이터 기반)"""
        logger.info("📰 주간 하이라이트 생성")

        # 이번 주 아카이브 파일 로드
        week_data = []
        today = datetime.now()
        for i in range(6):  # 월~토
            day = today - timedelta(days=today.weekday() - i)
            filename = f"daily_{day.strftime('%Y%m%d')}.json"
            filepath = os.path.join(DATA_DIR, filename)
            if os.path.exists(filepath):
                try:
                    with open(filepath, "r", encoding="utf-8") as f:
                        data = json.load(f)
                        week_data.extend(data.get("items", []))
                except Exception:
                    continue

        # 관련성 높은 순으로 정렬
        week_data.sort(key=lambda x: x.get("relevance_score", 0), reverse=True)

        summary = {
            "type": "weekly_summary",
            "title": f"주간 하이라이트 ({today.strftime('%Y.%m.%d')})",
            "total_items_this_week": len(week_data),
            "top_items": week_data[:10],  # 상위 10개
            "generated_at": datetime.now().isoformat(),
        }

        return [summary]

    # ── 메인 실행 ──

    def run_day(self, day: str, dry_run: bool = False) -> dict:
        """
        특정 요일의 전체 수집 파이프라인 실행

        Args:
            day: mon, tue, wed, thu, fri, sat, sun
            dry_run: True면 실행 계획만 출력

        Returns:
            수집 결과 딕셔너리
        """
        plan = DAY_PLANS.get(day)
        if not plan:
            logger.error(f"❌ 알 수 없는 요일: {day}")
            return {}

        logger.info("=" * 70)
        logger.info(f"🚀 {plan['title']}")
        logger.info(f"   날짜: {datetime.now().strftime('%Y-%m-%d %H:%M KST')}")
        logger.info(f"   태스크: {len(plan['tasks'])}개")
        logger.info("=" * 70)

        if dry_run:
            logger.info("🏃 DRY RUN - 실행하지 않고 계획만 출력합니다.")
            for i, task in enumerate(plan["tasks"], 1):
                logger.info(f"  {i}. [{task['type']}] params={task['params']}")
            return {"plan": plan, "dry_run": True}

        # 태스크 실행
        all_items = []
        task_results = {}

        task_runner = {
            "pubmed": self.run_pubmed,
            "news": self.run_news,
            "clinical_trials": self.run_clinical_trials,
            "patient_stories": self.run_patient_stories,
            "weekly_summary": self.run_weekly_summary,
        }

        for task in plan["tasks"]:
            task_type = task["type"]
            task_params = task["params"]

            logger.info(f"\n{'─'*50}")
            logger.info(f"▶ 태스크: {task_type}")

            runner = task_runner.get(task_type)
            if runner:
                try:
                    items = runner(task_params)
                    task_results[task_type] = len(items)
                    all_items.extend(items)
                    logger.info(f"  ✅ {len(items)}건 수집")
                except Exception as e:
                    logger.error(f"  ❌ 실행 실패: {e}")
                    logger.error(traceback.format_exc())
                    self.errors.append({"task": task_type, "error": str(e)})
            else:
                logger.warning(f"  ⚠️ 알 수 없는 태스크 타입: {task_type}")

        # 관련성 점수 순 정렬
        all_items.sort(key=lambda x: x.get("relevance_score", 0), reverse=True)

        # 결과 저장
        result = {
            "day": day,
            "title": plan["title"],
            "date": datetime.now().strftime("%Y-%m-%d"),
            "total_items": len(all_items),
            "task_results": task_results,
            "errors": self.errors,
            "items": all_items,
            "generated_at": datetime.now().isoformat(),
        }

        self._save_daily_result(day, result)
        self._save_seen_items()

        # 실행 요약
        logger.info(f"\n{'='*70}")
        logger.info(f"📊 수집 완료 요약")
        logger.info(f"   총 수집: {len(all_items)}건")
        for task_type, count in task_results.items():
            logger.info(f"   - {task_type}: {count}건")
        if self.errors:
            logger.warning(f"   ⚠️ 에러: {len(self.errors)}건")
            for err in self.errors:
                logger.warning(f"     - {err['task']}: {err['error']}")
        logger.info(f"{'='*70}")

        return result

    def _save_daily_result(self, day: str, result: dict):
        """일일 결과 저장"""
        date_str = datetime.now().strftime("%Y%m%d")

        # 당일 결과
        filename = f"daily_{date_str}.json"
        filepath = os.path.join(DATA_DIR, filename)
        with open(filepath, "w", encoding="utf-8") as f:
            json.dump(result, f, ensure_ascii=False, indent=2)
        logger.info(f"💾 저장: {filepath}")

        # 아카이브
        archive_filename = f"daily_{day}_{date_str}.json"
        archive_path = os.path.join(ARCHIVE_DIR, archive_filename)
        with open(archive_path, "w", encoding="utf-8") as f:
            json.dump(result, f, ensure_ascii=False, indent=2)
        logger.info(f"📦 아카이브: {archive_path}")

    def run_all_days(self, dry_run: bool = False):
        """모든 요일 실행 (테스트용)"""
        for day in ["mon", "tue", "wed", "thu", "fri", "sat", "sun"]:
            self.errors = []
            self.run_day(day, dry_run)


def get_today_day() -> str:
    """KST 기준 오늘 요일 반환"""
    # UTC+9 적용
    from datetime import timezone
    kst = timezone(timedelta(hours=9))
    now = datetime.now(kst)
    day_map = {0: "mon", 1: "tue", 2: "wed", 3: "thu", 4: "fri", 5: "sat", 6: "sun"}
    return day_map[now.weekday()]


def main():
    parser = argparse.ArgumentParser(description="END NF 일일 콘텐츠 오케스트레이터")
    parser.add_argument("--day", type=str, default="",
                        help="실행 요일 (mon~sun 또는 all). 미지정 시 오늘 요일")
    parser.add_argument("--dry-run", action="store_true",
                        help="실행하지 않고 계획만 출력")
    args = parser.parse_args()

    orchestrator = DailyOrchestrator()

    if args.day == "all":
        orchestrator.run_all_days(args.dry_run)
    else:
        day = args.day or get_today_day()
        logger.info(f"📅 실행 요일: {day.upper()}")
        orchestrator.run_day(day, args.dry_run)


if __name__ == "__main__":
    main()
