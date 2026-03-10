"""
============================================================
END NF 콘텐츠 시스템 v2 - 오케스트레이터
============================================================
타입별(story/info/welfare) 수집 + 로테이션 + 백로그 + 폴백 로직

사용법:
    python daily_runner.py                          # 자동 감지 (화→story, 금→info)
    python daily_runner.py --type story              # 1회차: 우리의 이야기
    python daily_runner.py --type info               # 2회차: 알아두면 좋은 소식
    python daily_runner.py --type info --week 2      # 2회차: 2주차 강제 지정
    python daily_runner.py --type welfare --topic 1  # 특별편: 산정특례 가이드
    python daily_runner.py --dry-run                 # 실행 계획만 출력

환경변수:
    NCBI_API_KEY: PubMed API 키 (선택)
    TELEGRAM_BOT_TOKEN: 텔레그램 봇 토큰
    TELEGRAM_CHAT_ID: 텔레그램 채팅 ID
    ANTHROPIC_API_KEY: Claude API 키
"""

import os
import sys
import json
import logging
import hashlib
import traceback
from datetime import datetime, timedelta, timezone
from pathlib import Path
import argparse
import math

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
HISTORY_FILE = os.path.join(os.path.dirname(__file__), "content_history.json")

os.makedirs(LOG_DIR, exist_ok=True)
os.makedirs(DATA_DIR, exist_ok=True)
os.makedirs(ARCHIVE_DIR, exist_ok=True)

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    handlers=[
        logging.FileHandler(
            os.path.join(LOG_DIR, f"daily_{datetime.now(timezone(timedelta(hours=9))).strftime('%Y%m%d')}.log"),
            encoding="utf-8",
        ),
        logging.StreamHandler(),
    ],
)
logger = logging.getLogger("endnf")


# ── 타입별 실행 계획 ──
TYPE_PLANS = {
    "story": {
        "title": "💛 화요일: 우리의 이야기",
        "tasks": [
            {"type": "patient_stories", "params": {"sources": ["reddit", "ctf"]}},
            {"type": "news", "params": {"categories": ["rarenote", "ctf", "community"]}},
        ],
    },
    "info_week1": {
        "title": "💡 금요일 1주차: NF 연구·신약·임상시험",
        "tasks": [
            {"type": "pubmed", "params": {"days_back": 30, "max_per_query": 5,
                                           "search_terms": ["neurofibromatosis", "NF1 gene therapy",
                                                            "selumetinib neurofibromatosis", "MEK inhibitor NF1",
                                                            "plexiform neurofibroma treatment"]}},
            {"type": "clinical_trials", "params": {"max_results": 15, "days_back": 30}},
            {"type": "news", "params": {"categories": ["treatment", "ctf"]}},
        ],
    },
    "info_week2": {
        "title": "💡 금요일 2주차: 유전질환 치료 연구 동향",
        "tasks": [
            {"type": "pubmed", "params": {"days_back": 30, "max_per_query": 5,
                                           "search_terms": ["gene therapy rare disease",
                                                            "CRISPR genetic disorder treatment",
                                                            "precision medicine inherited disease",
                                                            "RAS pathway targeted therapy"]}},
            {"type": "news", "params": {"categories": ["treatment", "rarenote"]}},
        ],
    },
    "info_week3": {
        "title": "💡 금요일 3주차: CTF·글로벌 NF 소식",
        "tasks": [
            {"type": "news", "params": {"categories": ["ctf", "community", "general"]}},
            {"type": "patient_stories", "params": {"sources": ["ctf"]}},
        ],
    },
    "info_week4": {
        "title": "💡 금요일 4주차: 교차 주제",
        "tasks": [
            {"type": "pubmed", "params": {"days_back": 30, "max_per_query": 3,
                                           "search_terms": ["neurofibromatosis", "NF1 gene therapy"]}},
            {"type": "news", "params": {"categories": ["ctf", "treatment", "rarenote"]}},
        ],
    },
    "welfare": {
        "title": "📋 특별편: 복지 가이드 시리즈",
        "tasks": [
            {"type": "news", "params": {"categories": ["policy_kr", "policy_global", "rarenote"]}},
        ],
    },
}


def get_week_of_month(dt=None):
    """해당 월의 몇 주차인지 계산 (1~5)"""
    if dt is None:
        kst = timezone(timedelta(hours=9))
        dt = datetime.now(kst)
    first_day = dt.replace(day=1)
    # ISO 기준 주차 계산
    week = math.ceil((dt.day + first_day.weekday()) / 7)
    return min(week, 5)


def get_today_day() -> str:
    """KST 기준 오늘 요일 반환"""
    kst = timezone(timedelta(hours=9))
    now = datetime.now(kst)
    day_map = {0: "mon", 1: "tue", 2: "wed", 3: "thu", 4: "fri", 5: "sat", 6: "sun"}
    return day_map[now.weekday()]


def get_content_type_for_today() -> str:
    """오늘 요일에 맞는 콘텐츠 타입 반환"""
    day = get_today_day()
    if day == "tue":
        return "story"
    elif day == "fri":
        return "info"
    else:
        # 화/금 외에는 수동 지정 필요
        return "story"


class ContentHistory:
    """콘텐츠 이력 관리 (반복 방지)"""

    def __init__(self):
        self.data = self._load()

    def _load(self) -> dict:
        if os.path.exists(HISTORY_FILE):
            try:
                with open(HISTORY_FILE, "r", encoding="utf-8") as f:
                    return json.load(f)
            except Exception:
                pass
        return {
            "sent_items": [],
            "backlog": [],
            "evergreen_index": {},
            "education_series_index": {},
            "rotation_log": {},
        }

    def save(self):
        with open(HISTORY_FILE, "w", encoding="utf-8") as f:
            json.dump(self.data, f, ensure_ascii=False, indent=2)

    def is_sent(self, source_id: str) -> bool:
        """이미 발송된 콘텐츠인지 확인 (60일 쿨다운)"""
        cutoff = (datetime.now() - timedelta(days=60)).isoformat()
        for item in self.data["sent_items"]:
            if item.get("source_id") == source_id:
                if item.get("cooldown_until", "") > cutoff:
                    return True
        return False

    def record_sent(self, source_id: str, content_type: str, title: str, **kwargs):
        """발송 기록"""
        now = datetime.now()
        self.data["sent_items"].append({
            "date": now.strftime("%Y-%m-%d"),
            "content_type": content_type,
            "source_id": source_id,
            "title": title,
            "cooldown_until": (now + timedelta(days=60)).isoformat(),
            **kwargs,
        })
        # 오래된 기록 정리 (180일 이전)
        cutoff = (now - timedelta(days=180)).isoformat()
        self.data["sent_items"] = [
            s for s in self.data["sent_items"] if s.get("date", "") > cutoff[:10]
        ]
        self.save()

    def add_to_backlog(self, items: list, content_type: str):
        """미사용 소재를 백로그에 저장"""
        for item in items:
            source_id = item.get("id", item.get("url", ""))
            if not source_id or self.is_sent(source_id):
                continue
            # 이미 백로그에 있는지 확인
            existing = {b.get("source_id") for b in self.data["backlog"]}
            if source_id not in existing:
                self.data["backlog"].append({
                    "collected_date": datetime.now().strftime("%Y-%m-%d"),
                    "source_id": source_id,
                    "source_type": item.get("source_type", ""),
                    "title": item.get("title", ""),
                    "content_type": content_type,
                    "used": False,
                    "item_data": item,
                })
        self.save()

    def get_from_backlog(self, content_type: str) -> dict:
        """백로그에서 미사용 소재 1건 꺼내기 (오래된 순)"""
        for entry in self.data["backlog"]:
            if not entry.get("used") and entry.get("content_type") == content_type:
                if not self.is_sent(entry.get("source_id", "")):
                    entry["used"] = True
                    self.save()
                    return entry.get("item_data", entry)
        return {}

    def get_next_evergreen(self) -> str:
        """가장 오래 미사용된 에버그린 ID 반환"""
        idx = self.data.get("evergreen_index", {})
        # 한번도 안 쓴 것 우선
        from content_generator import EVERGREEN_TOPICS
        for eg_id in EVERGREEN_TOPICS:
            if eg_id not in idx or idx[eg_id].get("last_used") is None:
                return eg_id
        # 가장 오래된 것
        sorted_egs = sorted(idx.items(), key=lambda x: x[1].get("last_used", ""))
        if sorted_egs:
            return sorted_egs[0][0]
        return list(EVERGREEN_TOPICS.keys())[0] if EVERGREEN_TOPICS else ""

    def record_evergreen_used(self, eg_id: str):
        if "evergreen_index" not in self.data:
            self.data["evergreen_index"] = {}
        self.data["evergreen_index"][eg_id] = {"last_used": datetime.now().isoformat()}
        self.save()

    def get_next_education(self) -> tuple:
        """가장 오래 미사용된 교육 시리즈 ID와 주제 반환"""
        idx = self.data.get("education_series_index", {})
        from content_generator import EDUCATION_TOPICS
        for edu_id, topic in EDUCATION_TOPICS.items():
            if edu_id not in idx or idx[edu_id].get("last_used") is None:
                return edu_id, topic
        sorted_edus = sorted(idx.items(), key=lambda x: x[1].get("last_used", ""))
        if sorted_edus:
            edu_id = sorted_edus[0][0]
            return edu_id, EDUCATION_TOPICS.get(edu_id, "")
        return "", ""

    def record_education_used(self, edu_id: str):
        if "education_series_index" not in self.data:
            self.data["education_series_index"] = {}
        self.data["education_series_index"][edu_id] = {"last_used": datetime.now().isoformat()}
        self.save()

    def log_rotation(self, year_month: str, week: int, topic: str):
        if "rotation_log" not in self.data:
            self.data["rotation_log"] = {}
        if year_month not in self.data["rotation_log"]:
            self.data["rotation_log"][year_month] = {}
        self.data["rotation_log"][year_month][f"week{week}"] = topic
        self.save()


class DailyOrchestrator:
    """콘텐츠 수집 오케스트레이터 v2"""

    def __init__(self):
        self.pubmed = PubMedFetcher()
        self.news = NewsFetcher()
        self.trials = ClinicalTrialsFetcher()
        self.stories = PatientStoryFetcher()
        self.history = ContentHistory()
        self.results = {}
        self.errors = []
        self.seen_hashes = self._load_seen_items()

    # ── 중복 제거 ──

    def _load_seen_items(self) -> set:
        if os.path.exists(DEDUP_FILE):
            try:
                with open(DEDUP_FILE, "r") as f:
                    data = json.load(f)
                    cutoff = (datetime.now() - timedelta(days=60)).isoformat()
                    recent = {k: v for k, v in data.items() if v > cutoff}
                    return set(recent.keys())
            except Exception:
                pass
        return set()

    def _save_seen_items(self):
        data = {h: datetime.now().isoformat() for h in self.seen_hashes}
        with open(DEDUP_FILE, "w") as f:
            json.dump(data, f)

    def _item_hash(self, item: dict) -> str:
        key_parts = []
        for k in ["pmid", "nct_id", "url", "link", "title"]:
            if k in item and item[k]:
                key_parts.append(str(item[k]))
        key = "|".join(key_parts)
        return hashlib.md5(key.encode()).hexdigest()

    def deduplicate(self, items: list) -> list:
        unique = []
        for item in items:
            h = self._item_hash(item)
            if h not in self.seen_hashes:
                self.seen_hashes.add(h)
                unique.append(item)
        return unique

    # ── 데이터 정규화 ──

    def normalize_item(self, item: dict, source_type: str) -> dict:
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
                "authors": item.get("authors", []),
                "journal": item.get("journal", ""),
                "pub_date": item.get("pub_date", ""),
            })
        elif source_type == "clinical_trial":
            normalized.update({
                "title": item.get("title", ""),
                "summary": item.get("brief_summary", "")[:300],
                "url": item.get("url", ""),
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
                "positivity_score": item.get("positivity_score", 0),
                "pub_date": item.get("pub_date", "") or item.get("created_utc", ""),
                "source_name": item.get("source_name", "") or item.get("subreddit", ""),
            })

        normalized["relevance_score"] = self._calc_relevance(normalized)
        return normalized

    def _calc_relevance(self, item: dict) -> int:
        score = 0
        text = f"{item.get('title', '')} {item.get('summary', '')}".lower()
        high_kw = ["neurofibromatosis", "nf1", "nf2", "schwannomatosis",
                    "plexiform", "selumetinib", "koselugo", "신경섬유종"]
        med_kw = ["neurofibroma", "mek inhibitor", "rare disease",
                   "희귀질환", "유전질환", "ctf", "children's tumor",
                   "gene therapy", "crispr", "precision medicine"]
        for kw in high_kw:
            if kw in text:
                score += 3
        for kw in med_kw:
            if kw in text:
                score += 1
        if item.get("is_new_this_week"):
            score += 5
        return min(score, 10)

    # ── 태스크 실행기 ──

    def run_pubmed(self, params: dict) -> list:
        logger.info("📚 PubMed 논문 수집 시작")
        try:
            results = self.pubmed.fetch_nf_latest(
                days_back=params.get("days_back", 30),
                max_per_query=params.get("max_per_query", 5),
            )
            all_articles = []
            for query, articles in results.items():
                for art in articles:
                    all_articles.append(self.normalize_item(art, "pubmed"))
            return self.deduplicate(all_articles)
        except Exception as e:
            logger.error(f"❌ PubMed 수집 실패: {e}")
            self.errors.append({"task": "pubmed", "error": str(e)})
            return []

    def run_news(self, params: dict) -> list:
        categories = params.get("categories", [])
        logger.info(f"📰 뉴스 수집 시작: {categories}")
        all_news = []
        try:
            for cat in categories:
                items = self.news.fetch_category(cat, max_per_feed=10)
                for item in items:
                    all_news.append(self.normalize_item(item, "news"))
            return self.deduplicate(all_news)
        except Exception as e:
            logger.error(f"❌ 뉴스 수집 실패: {e}")
            self.errors.append({"task": "news", "error": str(e)})
            return []

    def run_clinical_trials(self, params: dict) -> list:
        logger.info("🔬 임상시험 수집 시작")
        try:
            results = self.trials.fetch_all_nf(
                max_per_query=params.get("max_results", 10),
            )
            all_trials = []
            for query, trials in results.items():
                for trial in trials:
                    all_trials.append(self.normalize_item(trial, "clinical_trial"))
            return self.deduplicate(all_trials)
        except Exception as e:
            logger.error(f"❌ 임상시험 수집 실패: {e}")
            self.errors.append({"task": "clinical_trials", "error": str(e)})
            return []

    def run_patient_stories(self, params: dict) -> list:
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

    # ── 메인 실행 ──

    def run_content_type(self, content_type: str, week: int = 0,
                         welfare_topic: int = 0, dry_run: bool = False) -> dict:
        """
        콘텐츠 타입별 수집 파이프라인 실행

        Args:
            content_type: story, info, welfare
            week: 로테이션 주차 (info 타입, 0이면 자동 계산)
            welfare_topic: 복지 가이드 회차 (1~12)
            dry_run: True면 실행 계획만 출력
        """
        # info 타입: 주차 결정
        rotation_week = week
        if content_type == "info":
            if not rotation_week:
                rotation_week = get_week_of_month()
            if rotation_week > 4:
                rotation_week = 4  # 5주차는 4주차 로직
            plan_key = f"info_week{rotation_week}"
            kst = timezone(timedelta(hours=9))
            year_month = datetime.now(kst).strftime("%Y-%m")
            rotation_names = {1: "research", 2: "gene_therapy", 3: "ctf_news", 4: "crossover"}
            self.history.log_rotation(year_month, rotation_week, rotation_names.get(rotation_week, ""))
        elif content_type == "welfare":
            plan_key = "welfare"
        else:
            plan_key = "story"

        plan = TYPE_PLANS.get(plan_key)
        if not plan:
            logger.error(f"❌ 알 수 없는 계획: {plan_key}")
            return {}

        logger.info("=" * 70)
        logger.info(f"🚀 {plan['title']}")
        logger.info(f"   날짜: {datetime.now().strftime('%Y-%m-%d %H:%M')}")
        logger.info(f"   콘텐츠 타입: {content_type} (plan: {plan_key})")
        if content_type == "info":
            logger.info(f"   로테이션 주차: {rotation_week}주차")
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

        # 이미 발송한 소재 필터링
        filtered_items = []
        for item in all_items:
            source_id = item.get("id", item.get("url", ""))
            if not self.history.is_sent(source_id):
                filtered_items.append(item)

        logger.info(f"\n  📊 수집 {len(all_items)}건 → 필터링 후 {len(filtered_items)}건")

        # 관련성 점수 순 정렬
        filtered_items.sort(key=lambda x: x.get("relevance_score", 0), reverse=True)

        # ── 폴백 로직 ──
        fallback_used = ""
        fallback_data = {}

        if len(filtered_items) == 0:
            logger.warning("⚠️ 신규 소재 없음 → 폴백 로직 시작")

            if content_type == "story":
                # 1회차 폴백: 백로그 → 에버그린
                backlog_item = self.history.get_from_backlog("story")
                if backlog_item:
                    logger.info("  📦 백로그에서 소재 가져옴")
                    filtered_items = [backlog_item] if isinstance(backlog_item, dict) else []
                    fallback_used = "backlog"
                else:
                    eg_id = self.history.get_next_evergreen()
                    logger.info(f"  🌿 에버그린 콘텐츠 사용: {eg_id}")
                    fallback_used = "evergreen"
                    fallback_data = {"evergreen_id": eg_id}

            elif content_type == "info":
                # 2회차 폴백: 교육 시리즈 → 복지 가이드 특별편
                edu_id, edu_topic = self.history.get_next_education()
                if edu_id:
                    logger.info(f"  📖 교육 시리즈 사용: {edu_id}")
                    fallback_used = "education"
                    fallback_data = {"education_id": edu_id, "education_topic": edu_topic}
                else:
                    logger.info("  📋 교육 시리즈 소진 → 복지 가이드 특별편으로 전환")
                    fallback_used = "welfare_fallback"
        else:
            # 미사용 소재를 백로그에 저장 (상위 1개만 사용, 나머지 보관)
            if len(filtered_items) > 1:
                self.history.add_to_backlog(filtered_items[1:], content_type)

        # 결과 저장
        result = {
            "content_type": content_type,
            "plan_key": plan_key,
            "title": plan["title"],
            "date": datetime.now().strftime("%Y-%m-%d"),
            "total_items": len(filtered_items),
            "task_results": task_results,
            "errors": self.errors,
            "items": filtered_items,
            "fallback_used": fallback_used,
            "fallback_data": fallback_data,
            "rotation_week": rotation_week if content_type == "info" else 0,
            "welfare_topic": welfare_topic,
            "generated_at": datetime.now().isoformat(),
        }

        self._save_daily_result(content_type, result)
        self._save_seen_items()

        # 실행 요약
        logger.info(f"\n{'='*70}")
        logger.info(f"📊 수집 완료 요약")
        logger.info(f"   콘텐츠 타입: {content_type}")
        logger.info(f"   총 수집: {len(filtered_items)}건")
        for task_type, count in task_results.items():
            logger.info(f"   - {task_type}: {count}건")
        if fallback_used:
            logger.info(f"   🔄 폴백: {fallback_used}")
        if self.errors:
            logger.warning(f"   ⚠️ 에러: {len(self.errors)}건")
        logger.info(f"{'='*70}")

        return result

    def _save_daily_result(self, content_type: str, result: dict):
        kst = timezone(timedelta(hours=9))
        date_str = datetime.now(kst).strftime("%Y%m%d")
        filename = f"daily_{date_str}.json"
        filepath = os.path.join(DATA_DIR, filename)
        with open(filepath, "w", encoding="utf-8") as f:
            json.dump(result, f, ensure_ascii=False, indent=2)
        logger.info(f"💾 저장: {filepath}")

        archive_filename = f"daily_{content_type}_{date_str}.json"
        archive_path = os.path.join(ARCHIVE_DIR, archive_filename)
        with open(archive_path, "w", encoding="utf-8") as f:
            json.dump(result, f, ensure_ascii=False, indent=2)
        logger.info(f"📦 아카이브: {archive_path}")


def main():
    parser = argparse.ArgumentParser(description="END NF 콘텐츠 오케스트레이터 v2")
    parser.add_argument("--type", type=str, default="",
                        help="콘텐츠 타입 (story/info/welfare)")
    parser.add_argument("--week", type=int, default=0,
                        help="로테이션 주차 강제 지정 (1~4, info 타입에서 사용)")
    parser.add_argument("--topic", type=int, default=0,
                        help="복지 가이드 회차 (1~12, welfare 타입에서 사용)")
    parser.add_argument("--dry-run", action="store_true",
                        help="실행하지 않고 계획만 출력")
    # 하위호환
    parser.add_argument("--day", type=str, default="",
                        help="(하위호환) 요일 → 타입 자동 변환")
    args = parser.parse_args()

    orchestrator = DailyOrchestrator()

    # 콘텐츠 타입 결정
    content_type = args.type
    if not content_type:
        if args.day:
            day_to_type = {"tue": "story", "fri": "info", "mon": "info", "thu": "info"}
            content_type = day_to_type.get(args.day, "story")
        else:
            content_type = get_content_type_for_today()

    logger.info(f"📅 콘텐츠 타입: {content_type}")

    result = orchestrator.run_content_type(
        content_type=content_type,
        week=args.week,
        welfare_topic=args.topic,
        dry_run=args.dry_run,
    )


if __name__ == "__main__":
    main()
